"""Toda cor da interface sai da paleta Drácula — inclusive as inline no Python."""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
GUI = RAIZ / "gui"
APP = RAIZ / "app"

PALETA = {
    "#282a36", "#44475a", "#f8f8f2", "#6272a4", "#8be9fd", "#50fa7b",
    "#ffb86c", "#ff79c6", "#bd93f9", "#ff5555", "#f1fa8c",
    "#21222c", "#2b2d3a", "#343746", "#c8ccda", "#8b8fa8",
    "#403b55", "#4a4363",
    "#242630",
    "#3b1e6e",
}

PERMITIDAS = {
    "#000", "#fff", "#ff0",
    "#6ffb90", "#3ee066", "#3d3630", "#4a4136", "#2c3a32", "#35473b",
    "#332e42", "#3d3651",
}

_HEX = re.compile(r"(?<![\w&])#[0-9a-fA-F]{3,8}\b")


def _cores_de(texto: str) -> set[str]:
    return {c.lower() for c in _HEX.findall(texto)}


def _fora_da_paleta(cores: set[str]) -> set[str]:
    return cores - PALETA - PERMITIDAS


def test_cores_do_python_da_gui_saem_da_paleta() -> None:
    """QUALQUER hex nos módulos da GUI, não só `foreground="..."`."""
    intrusas: dict[str, set[str]] = {}
    for arquivo in APP.rglob("*.py"):
        fora = _fora_da_paleta(_cores_de(arquivo.read_text(encoding="utf-8")))
        if fora:
            intrusas[arquivo.name] = fora

    assert not intrusas, (
        "cores fora da paleta nos módulos da GUI: "
        + "; ".join(f"{k}: {sorted(v)}" for k, v in sorted(intrusas.items()))
    )


