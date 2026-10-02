#!/usr/bin/env python3
"""Faxina do lixo que a suíte JÁ deixou em `/tmp` — o passivo, não o futuro."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

BERCO_PREFIXO = "hefesto-berco-"

CONGELADA_PREFIXO = "hefesto-arvore-congelada-"

MARCADORES_DE_MIGRACAO = frozenset({
    ".coop_default_on_migrated",
    ".flavor_xbox_migrated",
})

NOMES_DA_MIGRACAO = frozenset({
    ".coop_default_on_migrated",
    ".coop_default_on_migrated.lock",
    ".coop_local_match_migrated",
    ".coop_local_match_migrated.lock",
    ".flavor_xbox_migrated",
    ".flavor_xbox_migrated.lock",
    ".modo_jogo_nos_presets_migrated",
    ".modo_jogo_nos_presets_migrated.lock",
    "acao.json",
    "antigo.json",
    "coop_local.json",
    "meu_jogo.json",
    "navegador.json",
    "quebrado.json",
    "sackboy_nativo.json",
    "sem_opiniao.json",
})

REGISTRO_DO_PACTL = "hefesto_teste_pactl_chamadas.txt"

REGISTRO_DO_PACTL_COMECO = "pactl "

IDADE_MINIMA_H_PADRAO = 1.0

SO_RELATO = ("pytest-of-", "pulse-")

RAIZES_PROIBIDAS = frozenset({"/", "/etc", "/usr", "/var", "/boot", "/home", "/root"})


@dataclass(frozen=True)
class Alvo:
    """Uma entrada que alguma regra PROVOU ser lixo de teste."""

    caminho: Path
    regra: str
    prova: str


@dataclass(frozen=True)
class Recusa:
    """Uma entrada que se pareceu com lixo e NÃO foi provada. Fica."""

    caminho: Path
    motivo: str


def raiz_permitida(raiz: Path) -> str | None:
    """Devolve o motivo da recusa, ou None quando a raiz pode ser varrida."""
    try:
        resolvida = raiz.resolve(strict=True)
    except OSError:
        return f"raiz inexistente: {raiz}"
    if not resolvida.is_dir():
        return f"raiz não é diretório: {resolvida}"
    if str(resolvida) in RAIZES_PROIBIDAS:
        return f"raiz proibida: {resolvida}"
    lar = Path(os.path.expanduser("~")).resolve()
    if resolvida == lar or lar in resolvida.parents or resolvida in lar.parents:
        return f"raiz dentro (ou acima) do HOME: {resolvida}"
    return None


def _pid_vivo(pid: int) -> bool:
    """Mesma regra do `tests/conftest.py`: na dúvida, VIVO."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _pid_do_berco(nome: str) -> int | None:
    if not nome.startswith(BERCO_PREFIXO):
        return None
    resto = nome[len(BERCO_PREFIXO) :]
    return int(resto) if resto.isdigit() else None


def _nosso(entrada: Path) -> bool:
    """True só quando a entrada é do usuário que está rodando o script."""
    try:
        return entrada.lstat().st_uid == os.getuid()
    except OSError:
        return False


def _idade_s(entrada: Path, agora: float) -> float:
    try:
        return agora - entrada.lstat().st_mtime
    except OSError:
        return 0.0


def _e_tmp_anonimo(nome: str) -> bool:
    """`tmp` + 8 caracteres é o formato de `tempfile.mkdtemp()` sem prefixo."""
    if not nome.startswith("tmp") or len(nome) != 11:
        return False
    return all(c.islower() or c.isdigit() or c == "_" for c in nome[3:])


def _classificar_tmp_anonimo(entrada: Path) -> Alvo | Recusa | None:
    """R3 — o diretório está ASSINADO pelos testes de migração de perfil?"""
    try:
        nomes = {p.name for p in entrada.iterdir()}
    except OSError as exc:
        return Recusa(entrada, f"ilegível ({exc.__class__.__name__})")
    if not nomes & MARCADORES_DE_MIGRACAO:
        return None
    intrusos = sorted(nomes - NOMES_DA_MIGRACAO)
    if intrusos:
        return Recusa(
            entrada,
            "tem o marcador da migração MAS também nome fora do conjunto "
            f"fechado: {', '.join(intrusos[:4])}",
        )
    if any((entrada / n).is_dir() for n in nomes):
        return Recusa(entrada, "tem subdiretório; a migração só escreve arquivos")
    return Alvo(
        entrada,
        "R3",
        f"assinado pelos testes de migração ({len(nomes)} arquivo(s), todos do "
        "conjunto fechado)",
    )


def _classificar_registro_do_pactl(entrada: Path) -> Alvo | Recusa:
    """R4 — o registro de caminho fixo, provado pelo conteúdo."""
    try:
        comeco = entrada.read_text(encoding="utf-8", errors="replace")[:16]
    except OSError as exc:
        return Recusa(entrada, f"ilegível ({exc.__class__.__name__})")
    if not comeco.startswith(REGISTRO_DO_PACTL_COMECO):
        return Recusa(entrada, "nome bate, conteúdo NÃO começa com 'pactl '")
    return Alvo(entrada, "R4", "registro do dublê de pactl (conteúdo confere)")


def recolher(
    raiz: Path, idade_minima_s: float, agora: float
) -> tuple[list[Alvo], list[Recusa], list[tuple[str, int]]]:
    """Percorre os filhos DIRETOS de `raiz` e classifica cada um."""
    alvos: list[Alvo] = []
    recusas: list[Recusa] = []
    relato: dict[str, int] = {p: 0 for p in SO_RELATO}

    try:
        entradas = sorted(raiz.iterdir())
    except OSError:
        return alvos, recusas, sorted(relato.items())

    for entrada in entradas:
        nome = entrada.name
        for prefixo in SO_RELATO:
            if nome.startswith(prefixo):
                relato[prefixo] += 1
                break
        if any(nome.startswith(p) for p in SO_RELATO):
            continue
        if not _nosso(entrada):
            continue
        if entrada.is_symlink():
            continue

        pid = _pid_do_berco(nome)
        if pid is not None and entrada.is_dir():
            if _pid_vivo(pid):
                recusas.append(Recusa(entrada, f"berço de sessão VIVA (pid {pid})"))
            else:
                alvos.append(Alvo(entrada, "R1", f"berço da sessão morta {pid}"))
            continue

        if nome.startswith(CONGELADA_PREFIXO) and entrada.is_dir():
            idade = _idade_s(entrada, agora)
            if idade < idade_minima_s:
                recusas.append(
                    Recusa(entrada, f"cópia congelada recente ({idade:.0f}s)")
                )
            else:
                alvos.append(
                    Alvo(entrada, "R2", f"cópia congelada órfã ({idade / 3600:.1f} h)")
                )
            continue

        if nome == REGISTRO_DO_PACTL and entrada.is_file():
            veredito = _classificar_registro_do_pactl(entrada)
            (alvos if isinstance(veredito, Alvo) else recusas).append(veredito)  # type: ignore[arg-type]
            continue

        if _e_tmp_anonimo(nome) and entrada.is_dir():
            veredito = _classificar_tmp_anonimo(entrada)
            if isinstance(veredito, Alvo):
                alvos.append(veredito)
            elif isinstance(veredito, Recusa):
                recusas.append(veredito)
            continue

    return alvos, recusas, sorted(relato.items())


def _tamanho(caminho: Path) -> int:
    if caminho.is_file():
        try:
            return caminho.stat().st_size
        except OSError:
            return 0
    total = 0
    for atual in caminho.rglob("*"):
        try:
            if atual.is_file() and not atual.is_symlink():
                total += atual.stat().st_size
        except OSError:
            continue
    return total


def _humano(n: int) -> str:
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n:.0f} {unidade}" if unidade == "B" else f"{n:.1f} {unidade}"
        n = int(n / 1024)
    return f"{n} B"  # pragma: no cover — inalcançável, o laço sempre devolve


def apagar(alvo: Alvo) -> bool:
    """Remove o alvo. Devolve True quando ele deixou de existir."""
    if alvo.caminho.is_dir() and not alvo.caminho.is_symlink():
        shutil.rmtree(alvo.caminho, ignore_errors=True)
    else:
        try:
            alvo.caminho.unlink()
        except OSError:
            return False
    return not alvo.caminho.exists()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Faxina do lixo que a suíte deixou em /tmp (padrão: só relata).",
    )
    parser.add_argument("--raiz", default="/tmp", help="raiz a varrer (padrão: /tmp)")
    parser.add_argument(
        "--apagar",
        action="store_true",
        help="apaga de verdade (sem isto, só relata)",
    )
    parser.add_argument(
        "--idade-minima-h",
        type=float,
        default=IDADE_MINIMA_H_PADRAO,
        help=f"idade mínima das regras por tempo (padrão: {IDADE_MINIMA_H_PADRAO})",
    )
    args = parser.parse_args(argv)

    raiz = Path(args.raiz)
    recusa = raiz_permitida(raiz)
    if recusa is not None:
        print(f"RECUSADO: {recusa}", file=sys.stderr)
        return 2

    alvos, recusas, relato = recolher(
        raiz.resolve(), args.idade_minima_h * 3600.0, time.time()
    )

    total = 0
    print(f"Faxina de testes em {raiz.resolve()}")
    print(f"  modo: {'APAGAR' if args.apagar else 'só relato (use --apagar)'}\n")

    if alvos:
        print(f"PROVADO como lixo de teste ({len(alvos)}):")
        for alvo in alvos:
            tam = _tamanho(alvo.caminho)
            total += tam
            marca = ""
            if args.apagar:
                marca = " -> apagado" if apagar(alvo) else " -> FALHOU"
            print(f"  [{alvo.regra}] {alvo.caminho.name}  ({_humano(tam)}) "
                  f"— {alvo.prova}{marca}")
        print(f"  total: {_humano(total)}\n")
    else:
        print("PROVADO como lixo de teste: nada.\n")

    if recusas:
        print(f"PARECIDO, mas NÃO provado — fica onde está ({len(recusas)}):")
        for r in recusas:
            print(f"  {r.caminho.name} — {r.motivo}")
        print()

    for prefixo, quantos in relato:
        if quantos:
            print(f"Só relato: {quantos} entrada(s) `{prefixo}*` — quem cria não é "
                  "esta suíte; a decisão de apagar é dela.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
