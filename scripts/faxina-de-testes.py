#!/usr/bin/env python3
"""Faxina do lixo que a suíte JÁ deixou em `/tmp` — o passivo, não o futuro.

O futuro está resolvido no `tests/conftest.py` (BERCO-DE-TMP-01): desde
07/08/2026 toda sessão de `pytest` cria `/tmp/hefesto-berco-<pid>`, aponta
`tempfile`/`TMPDIR` para lá e leva o berço embora no fim. Este script existe
para o que ficou para trás ANTES disso — medido em 07/08/2026, no `/tmp` dela:

    906  diretórios `tmp<8>`, dos quais 892 ainda continham os arquivos que
         só os testes de migração de perfil escrevem;
     99  `pulse-<12>` vazios (a libpulse, um por execução da suíte);
      3  `hefesto-arvore-congelada-<8>` que o `atexit` não alcançou porque a
         sessão foi morta;
      1  `hefesto_teste_pactl_chamadas.txt`, caminho FIXO num teste.

===========================================================================
O CRITÉRIO — escrito antes do código, e ele é POSITIVO
===========================================================================

Uma entrada só é apagada quando existe PROVA DE QUEM A CRIOU. Nunca o
contrário: *"não reconheço este arquivo, então apago"* é como se apaga a
configuração de alguém. As quatro regras, cada uma com a sua prova:

  R1  `hefesto-berco-<pid>/`  — o nome é escrito por `tests/conftest.py`, e o
      `<pid>` é o da sessão de `pytest` que o criou. Só vira alvo quando esse
      pid NÃO está vivo. Sessão viva (a sua, a de outro agente) nunca entra.

  R2  `hefesto-arvore-congelada-<8>/` — prefixo escrito por
      `tests/conftest.py::arvore_congelada`. Só vira alvo depois da idade
      mínima, para nunca pegar a cópia de uma sessão que está rodando agora.

  R3  `tmp<8>/` ASSINADO pelos testes de migração de perfil: contém pelo menos
      um dos dois marcadores que só aquelas migrações escrevem
      (`.coop_default_on_migrated`, `.flavor_xbox_migrated`) **e** todo nome lá
      dentro pertence ao conjunto FECHADO que aqueles dois arquivos de teste
      escrevem. Um único nome fora do conjunto e o diretório é RECUSADO, com o
      motivo impresso — porque aí ele pode ser de outra coisa.

  R4  `hefesto_teste_pactl_chamadas.txt` — nome literal que só existia em
      `tests/unit/test_doctor_mic_camada2.py` (corrigido em 07/08). Só vira
      alvo se o conteúdo começar com `pactl `, que é o que aquele teste grava.

Fora disso, e por decisão declarada, este script NÃO apaga:

  - `pytest-of-<user>/` — é do pytest, que já guarda as 3 últimas execuções e
    pode estar com uma delas EM USO por outra sessão. Entra só no relatório,
    com o tamanho, para a decisão ser dela;
  - `pulse-<12>/` — quem cria é a libpulse, e ela também roda fora da suíte.
    Relatório, não faxina;
  - qualquer coisa fora da raiz, de outro dono, ou alcançada por link.

E os `.lock` órfãos de `~/.config/hefesto-dualsense4unix/profiles/` NÃO são
assunto deste script, por mais que pareçam lixo: eles são do PRODUTO, não do
teste. Medido em 07/08 — `delete_profile` (`profiles/loader.py:990`) remove o
`.json` e deixa o `.json.lock` do `filelock`; os três órfãos de 06/08
(`meu_perfil`, `pragmata2`, `sackboy_nativo`) têm mtime igual, ao microssegundo,
ao nome do arquivo que o histórico guardou no mesmo instante. Isso é conserto
no produto, e a decisão de mexer na config dela é dela.

===========================================================================
Uso
===========================================================================

    scripts/faxina-de-testes.py             # só RELATA (padrão)
    scripts/faxina-de-testes.py --apagar    # apaga o que as regras provaram
    scripts/faxina-de-testes.py --raiz DIR  # outra raiz (bancada de teste)

O padrão é relatar porque a decisão de apagar o que já está no disco dela é
dela, não do script.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

#: Nome do berço de sessão que `tests/conftest.py` escreve (BERCO-DE-TMP-01).
BERCO_PREFIXO = "hefesto-berco-"

#: Nome da cópia congelada criada por `tests/conftest.py::arvore_congelada`.
CONGELADA_PREFIXO = "hefesto-arvore-congelada-"

#: Marcadores que SÓ as migrações de perfil escrevem. A presença de um deles é
#: metade da prova da R3; a outra metade é o conjunto fechado abaixo.
MARCADORES_DE_MIGRACAO = frozenset({
    ".coop_default_on_migrated",
    ".flavor_xbox_migrated",
})

#: O conjunto FECHADO de nomes que os dois arquivos de teste de migração
#: escrevem no diretório temporário deles. Conferido em 07/08/2026 contra
#: `tests/unit/test_coop_default_on_migration.py` e
#: `tests/unit/test_preset_flavor_migration.py`. Se algum deles ganhar um nome
#: novo, esta lista tem de ganhar junto — e até lá o diretório novo é
#: RECUSADO, que é o lado seguro do erro.
NOMES_DA_MIGRACAO = frozenset({
    ".coop_default_on_migrated",
    ".coop_default_on_migrated.lock",
    ".flavor_xbox_migrated",
    ".flavor_xbox_migrated.lock",
    "antigo.json",
    "coop_local.json",
    "meu_jogo.json",
    "navegador.json",
    "quebrado.json",
    "sackboy_nativo.json",
    "sem_opiniao.json",
})

#: Registro de caminho fixo que `test_doctor_mic_camada2.py` deixava para trás.
REGISTRO_DO_PACTL = "hefesto_teste_pactl_chamadas.txt"

#: Primeira linha que aquele teste grava — a prova de conteúdo da R4.
REGISTRO_DO_PACTL_COMECO = "pactl "

#: Idade mínima, em horas, para as regras que dependem de tempo (R2). Uma
#: sessão de suíte inteira levou 232 s na medição de 07/08; uma hora é folga
#: de mais de uma ordem de grandeza.
IDADE_MINIMA_H_PADRAO = 1.0

#: Prefixos que entram no RELATÓRIO e nunca na faxina.
SO_RELATO = ("pytest-of-", "pulse-")

#: Raízes que este script recusa de saída, aconteça o que acontecer.
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
    """Devolve o motivo da recusa, ou None quando a raiz pode ser varrida.

    O `$HOME` dela é recusado por nome, e não por heurística: um script de
    faxina que aceite `$HOME` como raiz é um script que um dia vai receber
    `$HOME` como raiz.
    """
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
        return None  # Nem parece nosso: nem entra no relatório.
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
    """Percorre os filhos DIRETOS de `raiz` e classifica cada um.

    Devolve (alvos provados, recusas com motivo, contagem do que é só relato).
    """
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
        if entrada.is_symlink():
            continue  # Link nunca é seguido: o alvo dele pode ser qualquer coisa.
        if not _nosso(entrada):
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
