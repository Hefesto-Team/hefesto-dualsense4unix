#!/usr/bin/env python3
"""check_numeros_da_sony.py — os números da Sony têm um dono só (`core/numeros_da_sony.py`).

O VID `0x054C` e os PIDs `0x0CE6`/`0x0DF2` estavam escritos à mão em quinze módulos, com conjuntos que
divergiam (o `evdev_reader` reconhecia o Edge, o `launch_env` só o DualSense de linha). Uma revisão de hardware
com PID novo exigia caçar os quinze.

A catraca conta as LINHAS de `src/**/*.py` que carregam o literal fora do dono. O piso é a conta de hoje e só
desce: acima dele reprova (literal novo, copie do dono); abaixo dele também reprova, pedindo para BAIXAR o piso,
porque um piso folgado deixa o literal voltar sem ninguém ver. Cada módulo que migra para o dono desce o piso.

Sem `src/` não há o que contar: sai «NÃO MEDIDO» na primeira linha, que o `portoes.sh` não conta como verde.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RAIZ_PADRAO = Path(__file__).resolve().parents[1]

#: O dono, relativo à raiz: o único arquivo que pode carregar o literal.
DONO = "src/hefesto_dualsense4unix/core/numeros_da_sony.py"

#: As linhas com o literal fora do dono, em 22/10/2026 (eram 40 antes de as roupas do pad irem ao dono).
PISO = 35

LITERAL = re.compile(r"0x054[cC]|0x0[cC][eE]6|0x0[dD][fF]2")


def linhas_com_o_literal(raiz: Path) -> list[tuple[str, int]]:
    """(caminho relativo, número da linha) de cada linha com o literal, fora do dono."""
    achados: list[tuple[str, int]] = []
    for arquivo in sorted((raiz / "src").rglob("*.py")):
        relativo = arquivo.relative_to(raiz).as_posix()
        if relativo == DONO:
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for numero, linha in enumerate(texto.splitlines(), start=1):
            if LITERAL.search(linha):
                achados.append((relativo, numero))
    return achados


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--raiz", type=Path, default=RAIZ_PADRAO)
    analisador.add_argument("--piso", type=int, default=PISO)
    analisador.add_argument("--listar", action="store_true", help="imprime cada linha achada")
    args = analisador.parse_args(argv)

    if not (args.raiz / "src").is_dir():
        print(f"NÃO MEDIDO: {args.raiz} não tem src/ para contar.")
        return 1

    achados = linhas_com_o_literal(args.raiz)
    por_arquivo: dict[str, int] = {}
    for relativo, _ in achados:
        por_arquivo[relativo] = por_arquivo.get(relativo, 0) + 1

    if args.listar:
        for relativo, numero in achados:
            print(f"{relativo}:{numero}")

    total = len(achados)
    if total > args.piso:
        print(
            f"VERMELHO: {total} linha(s) com o número da Sony fora de {DONO} (piso {args.piso}). "
            "Importe do dono em vez de escrever o literal."
        )
        for relativo, quantas in sorted(por_arquivo.items()):
            print(f"  {relativo}: {quantas}")
        return 1
    if total < args.piso:
        print(
            f"VERMELHO: só {total} linha(s) com o número da Sony fora do dono, e o piso diz {args.piso}. "
            f"Baixe PISO para {total} em scripts/check_numeros_da_sony.py: a catraca só desce."
        )
        return 1
    print(f"ok: {total} linha(s) com o número da Sony fora do dono, em {len(por_arquivo)} arquivo(s) (piso {args.piso}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
