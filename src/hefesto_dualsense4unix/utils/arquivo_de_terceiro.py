"""O dono dos arquivos de terceiro: lê dizendo o motivo, escreve inteiro com cópia e poda as cópias.

Os arquivos da Steam, do Heroic, do Bottles e dos prefixos Wine não são do Hefesto. Cada escrita
guarda a cópia de antes, troca o arquivo por inteiro e deixa na pasta só a primeira cópia (o estado
de antes do Hefesto) e as ``ULTIMAS`` mais novas de cada família.
"""
from __future__ import annotations

import contextlib
import os
import re
import shutil
import stat
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ULTIMAS = 5

FAMILIAS = (
    "hefesto-camadas",
    "hefesto-launch",
    "hefesto-opcoes",
    "hefesto-proton",
    "hefesto-tabela",
    "steam-input",
    "steam-input-fora-da-lista",
    "steam-input-ponte",
)

_MODO_DO_ARQUIVO_NOVO = 0o644


@dataclass(frozen=True)
class Leitura:
    """O que a leitura achou: o texto, ou o motivo em frase, ou a ausência (que não é defeito)."""

    texto: str | None
    motivo: str = ""
    ausente: bool = False

    @property
    def ilegivel(self) -> bool:
        return bool(self.motivo)


def ler(arquivo: Path | str, *, errors: str = "strict") -> Leitura:
    """Lê ``arquivo`` em UTF-8 sem traduzir quebras de linha; nunca levanta.

    Arquivo ausente volta com ``ausente``; o que existe e não se lê (``OSError`` ou byte fora de
    UTF-8) volta com o ``motivo`` em frase, e o texto fica ``None``.
    """
    arquivo = Path(arquivo)
    try:
        bruto = arquivo.read_bytes()
    except FileNotFoundError:
        return Leitura(None, ausente=True)
    except OSError as exc:
        return Leitura(None, f"{arquivo.name} não abre ({exc.strerror or exc})")
    try:
        return Leitura(bruto.decode("utf-8", errors))
    except UnicodeDecodeError as exc:
        return Leitura(None, f"{arquivo.name} tem um byte que não é UTF-8 (posição {exc.start})")


def _copias(arquivo: Path, familia: str) -> list[tuple[int, Path]]:
    """As cópias desta família exata ao lado de ``arquivo``, da mais velha para a mais nova."""
    padrao = re.compile(rf"^{re.escape(arquivo.name)}\.bak\.{re.escape(familia)}-(\d+)$")
    achadas = []
    with contextlib.suppress(OSError):
        for candidata in arquivo.parent.iterdir():
            casou = padrao.match(candidata.name)
            if casou:
                achadas.append((int(casou.group(1)), candidata))
    return sorted(achadas)


def podar(arquivo: Path | str, familia: str | None = None, *, mais_novas: int = ULTIMAS) -> int:
    """Apaga as cópias de ``arquivo`` além da primeira e das ``mais_novas``.

    Conta por família exata (``steam-input`` não casa ``steam-input-ponte``); sem ``familia``,
    poda cada uma das ``FAMILIAS``. Devolve quantas apagou.
    """
    arquivo = Path(arquivo)
    apagadas = 0
    for nome in (familia,) if familia else FAMILIAS:
        copias = _copias(arquivo, nome)
        guardar = {c for _, c in copias[:1] + copias[-mais_novas:]}
        for _, copia in copias:
            if copia not in guardar:
                with contextlib.suppress(OSError):
                    copia.unlink()
                    apagadas += 1
    return apagadas


def _copiar_antes(arquivo: Path, familia: str) -> Path:
    anteriores = _copias(arquivo, familia)
    carimbo = max(int(time.time()), anteriores[-1][0] + 1 if anteriores else 0)
    copia = arquivo.with_name(f"{arquivo.name}.bak.{familia}-{carimbo}")
    provisoria = arquivo.with_name(f".{copia.name}.hefesto-copia")
    try:
        shutil.copy2(arquivo, provisoria)
        provisoria.replace(copia)
    except BaseException:
        provisoria.unlink(missing_ok=True)
        raise
    return copia


def _trocar_por_inteiro(arquivo: Path, bruto: bytes, modo: int) -> None:
    fd, temporario = tempfile.mkstemp(prefix=f".{arquivo.name}.", suffix=".hefesto-tmp",
                                      dir=arquivo.parent)
    provisorio = Path(temporario)
    try:
        try:
            os.fchmod(fd, modo)
            resto = memoryview(bruto)
            while resto:
                resto = resto[os.write(fd, resto):]
            os.fsync(fd)
        finally:
            os.close(fd)
        provisorio.replace(arquivo)
    except BaseException:
        provisorio.unlink(missing_ok=True)
        raise


def escrever(
    arquivo: Path | str,
    texto: str,
    *,
    familia: str,
    errors: str = "strict",
    conferir: bool = True,
) -> Path | None:
    """Troca ``arquivo`` por ``texto`` inteiro, com a cópia de antes e a poda das cópias.

    Cópia ao lado como ``<arquivo>.bak.<familia>-<carimbo>`` (o carimbo nunca repete dentro da
    família), temporário na mesma pasta com o modo do arquivo, ``fsync``, ``os.replace`` e, com
    ``conferir``, releitura dos bytes. Falha levanta ``OSError`` com o arquivo de antes intacto,
    sem temporário nem cópia nova. Devolve a cópia (``None`` se o arquivo ainda não existia).
    """
    arquivo = Path(arquivo)
    bruto = texto.encode("utf-8", errors)
    try:
        modo = stat.S_IMODE(arquivo.stat().st_mode)
    except FileNotFoundError:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        modo = _MODO_DO_ARQUIVO_NOVO
        copia = None
    else:
        copia = _copiar_antes(arquivo, familia)
    try:
        _trocar_por_inteiro(arquivo, bruto, modo)
    except BaseException:
        if copia is not None:
            copia.unlink(missing_ok=True)
        raise
    if conferir and arquivo.read_bytes() != bruto:
        raise OSError(f"a releitura de {arquivo} não é o que acabou de ser gravado")
    podar(arquivo, familia)
    return copia
