"""NO-JOGO-SEM-FALSO-VERDE-01/T5 (a E2 da MESA-CHEIA-07) — a cor do painel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("a cor do painel da aba No jogo")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
pytest.importorskip("gi.repository.Gtk", reason="precisa da typelib Gtk")

from hefesto_dualsense4unix.interface import painel_no_jogo as pnj_mod

_janelas_vivas: list[Any] = []

_ROXO = (128, 0, 255)


def _entry(indice: int, rgb: Any, **extra: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "index": indice,
        "connected": True,
        "transport": "usb",
        "is_primary": indice == 0,
        "player": indice + 1,
        "player_slot": indice + 1,
        "lightbar_on": True,
        "lightbar_source": "sysfs",
        "lightbar_rgb": list(rgb) if rgb is not None else None,
    }
    entry.update(extra)
    return entry


def _estado(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "connected": True,
        "native_mode": False,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
        "controllers": [dict(e) for e in entries],
        "rumble_ff": {
            "per_vpad": [
                {"player": e["player"], "visto_ha_s": {"touchpad_click": 0.5}}
                for e in entries
            ]
        },
    }


def test_o_painel_nao_tem_leitura_de_cor_propria() -> None:
    """A contraprova estrutural da mordida 1, no fonte."""
    texto = Path(pnj_mod.__file__).read_text(encoding="utf-8")

    assert "lightbar_rgb" not in texto
    assert "cor_do_swatch" in texto


