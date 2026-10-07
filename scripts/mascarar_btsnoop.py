#!/usr/bin/env python3
"""Mascara o MAC de hardware REAL dentro de uma captura `.btsnoop` BINÁRIA."""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

_OUIS_REAIS_OCTETOS = (
    ("d8", "44", "89"),
    ("a0", "fa", "9c"),
    ("e4", "17", "d8"),
    ("e0", "f6", "b5"),
    ("48", "b2", "5d"),
    ("14", "3a", "9a"),
    ("d4", "2f", "4b"),
    ("44", "46", "48"),
    ("ac", "a7", "f1"),
)

ASSINATURA_BTSNOOP = b"btsnoop\x00"
TAMANHO_CABECALHO = 16
TAMANHO_CABECALHO_REGISTRO = 24

TAMANHO_MAC = 6

ORDEM_BE = "big-endian"
ORDEM_LE = "little-endian"


@dataclass(frozen=True)
class Ocorrencia:
    """Um endereço de hardware real achado dentro de bytes."""

    inicio: int
    ordem: str
    oui: str
    mac: str
    mascarado: bool

    def __str__(self) -> str:
        estado = "já mascarado" if self.mascarado else "CRU"
        return f"offset {self.inicio} ({self.ordem}): {self.mac} — {estado}"


def _oui_bytes(octetos: tuple[str, str, str]) -> bytes:
    return bytes(int(o, 16) for o in octetos)


def ocorrencias(dados: bytes) -> list[Ocorrencia]:
    """Acha todo MAC de OUI real em ``dados``, nas DUAS ordens de byte."""
    achados: list[Ocorrencia] = []
    for octetos in _OUIS_REAIS_OCTETOS:
        oui_be = _oui_bytes(octetos)
        oui_le = oui_be[::-1]
        rotulo = ":".join(octetos)

        pos = dados.find(oui_be)
        while pos != -1:
            if pos + TAMANHO_MAC <= len(dados):
                campo = dados[pos : pos + TAMANHO_MAC]
                achados.append(
                    Ocorrencia(
                        inicio=pos,
                        ordem=ORDEM_BE,
                        oui=rotulo,
                        mac=campo.hex(":"),
                        mascarado=campo[3] == 0 and campo[4] == 0,
                    )
                )
            pos = dados.find(oui_be, pos + 1)

        pos = dados.find(oui_le)
        while pos != -1:
            inicio = pos - (TAMANHO_MAC - len(oui_le))
            if inicio >= 0:
                campo = dados[inicio : inicio + TAMANHO_MAC]
                achados.append(
                    Ocorrencia(
                        inicio=inicio,
                        ordem=ORDEM_LE,
                        oui=rotulo,
                        mac=campo[::-1].hex(":"),
                        mascarado=campo[1] == 0 and campo[2] == 0,
                    )
                )
            pos = dados.find(oui_le, pos + 1)

    return sorted(achados, key=lambda o: (o.inicio, o.ordem))


def cruas(dados: bytes) -> list[Ocorrencia]:
    """Só as ocorrências que ainda NÃO estão mascaradas — as que vazam."""
    return [o for o in ocorrencias(dados) if not o.mascarado]


class BtsnoopInvalidoError(ValueError):
    """O arquivo não é um `.btsnoop` que este script saiba tratar."""


def faixas_de_payload(dados: bytes) -> list[tuple[int, int]]:
    """Percorre o formato e devolve as faixas ``[inicio, fim)`` de dados."""
    if not dados.startswith(ASSINATURA_BTSNOOP):
        raise BtsnoopInvalidoError(
            "assinatura ausente: os 8 primeiros bytes não são `btsnoop\\0`"
        )
    if len(dados) < TAMANHO_CABECALHO:
        raise BtsnoopInvalidoError(
            f"arquivo com {len(dados)} B: menor que o cabeçalho de "
            f"{TAMANHO_CABECALHO} B"
        )

    faixas: list[tuple[int, int]] = []
    pos = TAMANHO_CABECALHO
    while pos < len(dados):
        fim_do_cabecalho = pos + TAMANHO_CABECALHO_REGISTRO
        if fim_do_cabecalho > len(dados):
            raise BtsnoopInvalidoError(
                f"registro truncado no offset {pos}: faltam bytes de cabeçalho"
            )
        incluidos = int.from_bytes(dados[pos + 4 : pos + 8], "big")
        fim_do_payload = fim_do_cabecalho + incluidos
        if fim_do_payload > len(dados):
            raise BtsnoopInvalidoError(
                f"registro no offset {pos} promete {incluidos} B de dados e o "
                f"arquivo acaba antes"
            )
        faixas.append((fim_do_cabecalho, fim_do_payload))
        pos = fim_do_payload
    return faixas


def _dentro_de_payload(faixas: list[tuple[int, int]], inicio: int, fim: int) -> bool:
    return any(a <= inicio and fim <= b for a, b in faixas)


def mascarar(dados: bytes) -> tuple[bytes, list[Ocorrencia]]:
    """Devolve ``(bytes mascarados, ocorrências que estavam cruas)``."""
    faixas = faixas_de_payload(dados)
    achados = cruas(dados)
    fora = [
        o
        for o in achados
        if not _dentro_de_payload(faixas, o.inicio, o.inicio + TAMANHO_MAC)
    ]
    if fora:
        raise BtsnoopInvalidoError(
            "ocorrência fora de payload — recuso mascarar estrutura do "
            "formato:\n  " + "\n  ".join(str(o) for o in fora)
        )

    saida = bytearray(dados)
    for o in achados:
        if o.ordem == ORDEM_BE:
            saida[o.inicio + 3] = 0
            saida[o.inicio + 4] = 0
        else:
            saida[o.inicio + 1] = 0
            saida[o.inicio + 2] = 0

    if len(saida) != len(dados):
        raise BtsnoopInvalidoError(
            f"a saída teria {len(saida)} B contra {len(dados)} B da entrada — "
            "recuso escrever: `.btsnoop` de tamanho diferente é captura "
            "falsificada"
        )
    return bytes(saida), achados


def _relatorio(caminho: Path, dados: bytes) -> int:
    todas = ocorrencias(dados)
    por_ordem = {
        ORDEM_BE: [o for o in todas if o.ordem == ORDEM_BE],
        ORDEM_LE: [o for o in todas if o.ordem == ORDEM_LE],
    }
    print(f"{caminho}: {len(dados)} B")
    for ordem in (ORDEM_BE, ORDEM_LE):
        achados = por_ordem[ordem]
        crus = [o for o in achados if not o.mascarado]
        print(f"  {ordem:<13} {len(achados)} ocorrência(s), {len(crus)} crua(s)")
        for o in achados:
            print(f"    {o}")
    return len([o for o in todas if not o.mascarado])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Mascara (octetos 4 e 5 zerados) o MAC real dentro de um .btsnoop, "
            "procurando nas duas ordens de byte e preservando o tamanho."
        )
    )
    parser.add_argument("entrada", type=Path, help="captura .btsnoop de origem")
    parser.add_argument(
        "-o",
        "--saida",
        type=Path,
        help="arquivo a escrever (obrigatório fora de --conferir)",
    )
    parser.add_argument(
        "--conferir",
        action="store_true",
        help="só relata as ocorrências nas duas ordens; não escreve nada. "
        "Sai 1 se sobrar alguma crua.",
    )
    args = parser.parse_args(argv)

    try:
        dados = args.entrada.read_bytes()
    except OSError as erro:
        print(f"não consegui ler {args.entrada}: {erro}", file=sys.stderr)
        return 2

    if args.conferir:
        return 1 if _relatorio(args.entrada, dados) else 0

    if args.saida is None:
        parser.error("faltou -o/--saida (ou use --conferir)")

    try:
        saida, achados = mascarar(dados)
    except BtsnoopInvalidoError as erro:
        print(f"{args.entrada}: {erro}", file=sys.stderr)
        return 2

    args.saida.write_bytes(saida)
    conferencia = args.saida.read_bytes()
    if len(conferencia) != len(dados):
        print(
            f"{args.saida}: escrevi {len(conferencia)} B contra {len(dados)} B "
            "da entrada — o arquivo está errado",
            file=sys.stderr,
        )
        return 2
    if cruas(conferencia):
        print(f"{args.saida}: ainda há MAC cru depois de mascarar", file=sys.stderr)
        return 2

    print(
        f"{args.saida}: {len(achados)} ocorrência(s) mascarada(s), "
        f"{len(conferencia)} B (mesmo tamanho da entrada)"
    )
    for o in achados:
        print(f"  {o}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
