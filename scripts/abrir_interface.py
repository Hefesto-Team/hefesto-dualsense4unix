#!/usr/bin/env python3
"""Calço do `run.sh --gui`: o corpo da abertura da janela mora em `interface/abrir.py`.

O-ICONE-DO-DOCK-E-O-DO-HEFESTO-01 (07/10/2026): havia DUAS portas para a mesma janela, e só esta vestia a
identidade (prgname, classe e ícone); o console script `hefesto-dualsense4unix-gui`, que a bandeja, o
Flatpak e o pip usam, ia direto ao piloto e a janela saía `hefesto-dualsense4unix-gui`, sem `.desktop`
que a case. O corpo (a guarda da tela, o saneamento do GdkPixbuf, o diário, a vez única, a identidade e,
só depois, o piloto) foi para o pacote, porque o wheel não leva `scripts/`. As duas portas dão na mesma
função, e este arquivo só põe a árvore no caminho.

A guarda de tela deste caminho segue como era: ele NÃO põe o padrão `HEFESTO_NA_TELA=1` (quem o põe é a
entrada do produto), logo os instrumentos que chamam o `run.sh` continuam na tela de mentira.
"""
from __future__ import annotations

import sys
from pathlib import Path

_RAIZ_TELA = str(Path(__file__).resolve().parents[1] / "src")
if _RAIZ_TELA not in sys.path:
    sys.path.insert(0, _RAIZ_TELA)


def main(argv: list[str] | None = None) -> int:
    from hefesto_dualsense4unix.interface import abrir

    return abrir.abrir(argv)


if __name__ == "__main__":
    sys.exit(main())
