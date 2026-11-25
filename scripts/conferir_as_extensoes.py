#!/usr/bin/env python3
"""conferir_as_extensoes.py — cada extensão confere a própria casa contra o Hefesto de hoje.

Recebe a pasta de uma ou mais extensões e, de cada uma, confere:

- o ``hefesto-mod.json`` pela mesma régua com que o Hefesto o aceita (``ler_manifesto``);
- a versão, igual no manifesto, no topo do ``CHANGELOG.md`` e no ``pyproject.toml`` (quando ele
  declara uma na tabela ``[project]``);
- a licença, igual no ``LICENSE``, no manifesto e no ``README.md``;
- as seções mínimas do ``README.md``: instalar, testes e licença;
- o leitor do lançador, rodado pelo mesmo ``ler_por_processo`` do Hefesto, na caixa quando o
  ``bwrap`` abre, numa casa vazia: o que ele imprime tem de ser uma biblioteca que o Hefesto lê.

A saída diz uma linha por extensão; o código de saída é 1 se alguma recusou. O Hefesto é o da
árvore deste script (``--hefesto`` aponta outra); no CI de cada extensão, o checkout do ``main``.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

SECOES_MINIMAS: tuple[tuple[str, ...], ...] = (
    ("Instalar",),
    ("Testes", "A suíte", "Provas"),
    ("Licença",),
)
SPDX_DO_TEXTO: tuple[tuple[str, frozenset[str]], ...] = (
    ("mit license", frozenset({"MIT"})),
    ("gnu general public license", frozenset({"GPL-3.0-only", "GPL-3.0-or-later"})),
)
PRAZO_DA_SONDA_S = 10


def _entrar_no_hefesto(raiz: Path) -> None:
    fonte = str(raiz / "src")
    if (raiz / "src").is_dir() and fonte not in sys.path:
        sys.path.insert(0, fonte)


def versao_do_changelog(texto: str) -> str | None:
    """A primeira versão numerada do ``CHANGELOG.md``; «Na próxima versão» não conta."""
    achado = re.search(r"^##\s+\[?v?(\d+(?:\.\d+)+)", texto, re.MULTILINE)
    return achado.group(1) if achado else None


def versao_do_pyproject(texto: str) -> str | None:
    """A ``version`` da tabela ``[project]`` do ``pyproject.toml``."""
    tabela = re.search(r"^\[project\]\s*$(.*?)(?=^\[|\Z)", texto, re.MULTILINE | re.DOTALL)
    if tabela is None:
        return None
    achado = re.search(r'^version\s*=\s*"([^"]+)"', tabela.group(1), re.MULTILINE)
    return achado.group(1) if achado else None


def licencas_do_arquivo(texto: str) -> frozenset[str]:
    """Os identificadores SPDX que o texto do ``LICENSE`` admite; vazio se ele não se reconhece."""
    cabeca = texto[:400].casefold()
    for marca, ids in SPDX_DO_TEXTO:
        if marca in cabeca:
            return ids
    return frozenset()


def secoes_do_readme(texto: str) -> list[str]:
    """Os títulos das seções (``##``) do ``README.md``, na ordem."""
    return [m.group(1).strip() for m in re.finditer(r"^##\s+(.+?)\s*$", texto, re.MULTILINE)]


def _ler(arquivo: Path) -> str | None:
    try:
        return arquivo.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def conferir_a_versao(pasta: Path, versao: str) -> list[str]:
    """Manifesto, topo do CHANGELOG e ``pyproject.toml`` dizem a mesma versão."""
    achadas = {"hefesto-mod.json": versao}
    changelog = _ler(pasta / "CHANGELOG.md")
    topo = None if changelog is None else versao_do_changelog(changelog)
    if topo is None:
        return ["o CHANGELOG.md não tem versão numerada no topo"]
    achadas["CHANGELOG.md"] = topo
    pyproject = _ler(pasta / "pyproject.toml")
    numero = None if pyproject is None else versao_do_pyproject(pyproject)
    if numero is not None:
        achadas["pyproject.toml"] = numero
    if len(set(achadas.values())) == 1:
        return []
    dizem = ", ".join(f"{arquivo} {numero}" for arquivo, numero in achadas.items())
    return [f"a versão diverge: {dizem}"]


def conferir_a_licenca(pasta: Path, licenca: str) -> list[str]:
    """``LICENSE``, manifesto e ``README.md`` dizem a mesma licença."""
    recusas: list[str] = []
    arquivo = _ler(pasta / "LICENSE")
    if arquivo is None:
        recusas.append("falta o arquivo LICENSE")
    elif licenca not in licencas_do_arquivo(arquivo):
        recusas.append(f"o LICENSE não é o da licença {licenca} do manifesto")
    readme = _ler(pasta / "README.md")
    if readme is not None and not re.search(rf"(?<![\w.-]){re.escape(licenca)}(?![\w-])", readme):
        recusas.append(f"o README.md não diz a licença {licenca} do manifesto")
    return recusas


def conferir_o_readme(pasta: Path) -> list[str]:
    """O README existe e tem as seções mínimas."""
    readme = _ler(pasta / "README.md")
    if readme is None:
        return ["falta o README.md"]
    titulos = [t.casefold() for t in secoes_do_readme(readme)]
    return [f"o README.md não tem a seção «{nomes[0]}»" for nomes in SECOES_MINIMAS
            if not any(t.startswith(n.casefold()) for t in titulos for n in nomes)]


def caixa_que_abre() -> str | bool:
    """O ``bwrap`` quando ele existe e abre uma caixa aqui; ``False`` quando não abre."""
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        return False
    try:
        aberta = subprocess.run([bwrap, "--ro-bind", "/", "/", "true"], check=False,
                                capture_output=True, timeout=PRAZO_DA_SONDA_S)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return bwrap if aberta.returncode == 0 else False


@contextlib.contextmanager
def _casa_vazia() -> Iterator[Path]:
    casa = Path(tempfile.mkdtemp(prefix="ce-"))
    guardado = {n: os.environ.get(n) for n in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME")}
    os.environ["HOME"] = str(casa)
    os.environ.pop("XDG_CONFIG_HOME", None)
    os.environ.pop("XDG_DATA_HOME", None)
    try:
        yield casa
    finally:
        for nome, valor in guardado.items():
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor
        shutil.rmtree(casa, ignore_errors=True)


def conferir_o_leitor(pasta: Path, manifesto: Any, caixa: str | bool) -> list[str]:
    """O leitor do lançador, rodado pelo Hefesto numa casa vazia, entrega uma biblioteca lida."""
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    bloco = manifesto.lancador
    if not isinstance(bloco, dict) or "leitor" not in bloco:
        return []
    try:
        lancador = censo.lancador_da_modificacao(manifesto.id, bloco, pasta)
    except ValueError as erro:
        return [f"o bloco lancador não passa: {erro}"]
    if lancador.leitor is None:
        return []
    with _casa_vazia():
        biblioteca = censo.ler_por_processo(lancador.leitor, bwrap=caixa)
    if biblioteca.estado == censo.LIDO:
        return []
    motivo = "; ".join(biblioteca.erros) or biblioteca.estado
    return [f"o leitor não entrega uma biblioteca que o Hefesto leia: {motivo}"]


def conferir(pasta: Path, caixa: str | bool) -> tuple[str, list[str]]:
    """O nome da extensão e as suas recusas; lista vazia é extensão em ordem."""
    from hefesto_dualsense4unix.mods.manifesto import ManifestoRecusadoError, ler_manifesto

    try:
        manifesto = ler_manifesto(pasta)
    except ManifestoRecusadoError as erro:
        return pasta.name, [f"o manifesto não passa pelo Hefesto: {erro}"]
    recusas = [*conferir_a_versao(pasta, manifesto.versao),
               *conferir_a_licenca(pasta, manifesto.licenca),
               *conferir_o_readme(pasta),
               *conferir_o_leitor(pasta, manifesto, caixa)]
    return f"{manifesto.id} {manifesto.versao}", recusas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("pastas", nargs="+", type=Path, help="a pasta de cada extensão")
    ap.add_argument("--hefesto", type=Path, default=Path(__file__).resolve().parents[1],
                    help="a árvore do Hefesto (a deste script, por padrão)")
    ap.add_argument("--sem-caixa", action="store_true", help="roda o leitor sem o bwrap")
    args = ap.parse_args(argv)
    _entrar_no_hefesto(args.hefesto.resolve())
    caixa = False if args.sem_caixa else caixa_que_abre()
    if caixa is False and not args.sem_caixa:
        print("aviso: o bwrap não abre aqui; o leitor roda sem a caixa")
    falhou = False
    for pasta in args.pastas:
        nome, recusas = conferir(pasta.resolve(), caixa)
        if not recusas:
            print(f"ok {nome}")
            continue
        falhou = True
        for frase in recusas:
            print(f"recusa {nome}: {frase}")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
