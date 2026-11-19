"""O computador tem bateria? O espelho Python do ``_doctor_tem_bateria`` do ``doctor.sh``.

Bateria do computador é uma fonte em ``/sys/class/power_supply`` com ``type=Battery`` e ``scope``
diferente de ``Device``: a bateria de um controle ou de um mouse (``scope=Device``) não faz do
computador um notebook, e o nome (``BAT0``, ``BATT``, ``CMB0``) não conta.
"""
from __future__ import annotations

from pathlib import Path

FONTES = Path("/sys/class/power_supply")


def _campo(fonte: Path, nome: str) -> str:
    try:
        return (fonte / nome).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def tem_bateria(fontes: Path = FONTES) -> bool:
    """``True`` se alguma fonte em ``fontes`` é a bateria do computador."""
    try:
        todas = list(fontes.iterdir())
    except OSError:
        return False
    return any(
        _campo(fonte, "type") == "Battery" and _campo(fonte, "scope") != "Device"
        for fonte in todas
    )


__all__ = ["FONTES", "tem_bateria"]
