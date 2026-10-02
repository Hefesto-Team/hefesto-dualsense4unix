"""A fonte ÚNICA que os portões leem quando perguntam "o instalador faz X?"."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

INSTALL = RAIZ / "install.sh"

CAMADA_DE_MAQUINA = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"

ARQUIVOS = (INSTALL, CAMADA_DE_MAQUINA)

SEPARADOR = (
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# ACIMA: install.sh · ABAIXO: scripts/lib/camada_de_maquina.sh\n"
    "# Emendados por tests/unit/fonte_do_instalador.py — leia o docstring de lá.\n"
    "# ---------------------------------------------------------------------------\n"
)


def texto_do_instalador() -> str:
    """O texto do `install.sh` MAIS o da camada de máquina, nesta ordem."""
    return SEPARADOR.join(caminho.read_text(encoding="utf-8") for caminho in ARQUIVOS)


def texto_do_install_sh() -> str:
    """Só o `install.sh`."""
    return INSTALL.read_text(encoding="utf-8")


def texto_da_camada_de_maquina() -> str:
    """Só a lib das curas de HOST."""
    return CAMADA_DE_MAQUINA.read_text(encoding="utf-8")


def existe_o_instalador() -> bool:
    """Os dois arquivos estão no disco?"""
    return all(caminho.exists() for caminho in ARQUIVOS)
