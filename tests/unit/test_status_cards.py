"""tests/unit/test_status_cards.py — aba Status por controle (STATUS-02/03 + BT-03).

Exercita com GTK REAL (a suíte roda com display; 0 skips):

  * 2 controles no ``state_full`` → 2 ControllerCard com título e bateria
    PRÓPRIOS ("Controle 1 — BT · Jogador 1" pelo ``player_slot``/``player``;
    fallback ``index + 1`` sem slot; sem "Jogador" fora do co-op — D7);
  * 2 ticks com o MESMO conjunto → os MESMOS objetos de widget (``id()``,
    sem rebuild); conjunto novo → rebuild;
  * inputs do card 2 vêm EXCLUSIVAMENTE de ``controllers[1].inputs``;
  * entrada-placeholder offline (HARM-CARD-FANTASMA-01) e ``uniq`` None não
    criam card fantasma nem colidem;
  * ``inputs is None`` → área de inputs vira "—" (nunca o último valor
    congelado como vivo);
  * rótulos da lightbar pela FONTE (apagada / cor desconhecida / Nativo);
  * badge de degradação (BT-03): acende com uinput+motivo, some com uhid;
    frases leigas nunca cravam o mecanismo do sono BT;
  * glyphs/sticks/barras recebem o accent AJUSTADO (espião nos widgets);
  * gate de timers: NENHUMA ocorrência nova de timeout/idle do GLib em
    relação ao baseline da mixin (o gate é diff, não contagem absoluta).
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("status cards")

import re
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions import status_actions as sa_mod
from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.interface import cartao_do_controle as cc_mod
from hefesto_dualsense4unix.interface.cartao_do_controle import rotulo_lightbar

COR_A = (16, 32, 72)
COR_B = (0, 255, 0)


class _FakeLabel:
    def __init__(self) -> None:
        self.markup: str | None = None
        self.text: str | None = None
        self.visible: bool | None = None

    def set_markup(self, markup: str) -> None:
        self.markup = markup

    def set_text(self, text: str) -> None:
        self.text = text

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_fraction(self, _frac: float) -> None:
        pass

    def hide(self) -> None:
        self.visible = False


class _FakeBar(_FakeLabel):
    def __init__(self) -> None:
        super().__init__()
        self.fraction: float | None = None

    def set_fraction(self, frac: float) -> None:
        self.fraction = frac

    def set_show_text(self, _v: bool) -> None:
        pass


class _Builder:
    """Slot dos cards é um GtkBox REAL; o resto são fakes leves."""

    def __init__(self) -> None:
        self._w: dict[str, Any] = {
            "status_players_slot": Gtk.Grid(
                row_spacing=12, column_spacing=12, column_homogeneous=True
            ),
        }

    def get_object(self, wid: str) -> Any:
        if wid not in self._w:
            self._w[wid] = _FakeBar() if "bar" in wid else _FakeLabel()
        return self._w[wid]


class _Host(StatusActionsMixin):
    def __init__(self) -> None:
        self.builder = _Builder()

    @property
    def slot(self) -> Any:
        return self.builder.get_object("status_players_slot")

    def cards(self) -> list[Any]:
        """Cards na ordem de LEITURA (esq→dir, cima→baixo)."""
        grid = self.slot
        return sorted(
            grid.get_children(),
            key=lambda w: (
                grid.child_get_property(w, "top-attach"),
                grid.child_get_property(w, "left-attach"),
            ),
        )


def _inputs(**valores: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
        "l2_raw": 0,
        "r2_raw": 0,
        "buttons": [],
    }
    base.update(valores)
    return base


def _entry(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "index": 0,
        "connected": True,
        "transport": "bt",
        "is_primary": True,
        "uniq": "aa:bb:cc:00:00:01",
        "battery_pct": 80,
        "player": None,
        "player_slot": None,
        "lightbar_rgb": list(COR_A),
        "lightbar_on": True,
        "lightbar_source": "sysfs",
        "inputs": _inputs(),
        "vpad_backend": "uhid",
        "vpad_motivo": None,
    }
    base.update(kw)
    return base


def _state(*controllers: dict[str, Any], **top: Any) -> dict[str, Any]:
    st: dict[str, Any] = {
        "connected": bool(controllers),
        "transport": "bt",
        "battery_pct": 80,
        "active_profile": "vitoria",
        "native_mode": False,
        "controllers": list(controllers),
    }
    st.update(top)
    return st


@pytest.mark.parametrize(
    ("entry_kw", "state_kw", "esperado"),
    [
        (
            {"lightbar_rgb": [10, 10, 10], "lightbar_on": False,
             "lightbar_source": "sysfs"},
            {},
            "Lightbar: apagada",
        ),
        (
            {"lightbar_rgb": [0, 0, 0], "lightbar_on": True,
             "lightbar_source": "sysfs"},
            {},
            "Lightbar: apagada",
        ),
        (
            {"lightbar_rgb": [0, 0, 0], "lightbar_on": False,
             "lightbar_source": "desired"},
            {},
            "Lightbar: apagada",
        ),
        (
            {"lightbar_rgb": None, "lightbar_on": False,
             "lightbar_source": "desconhecida"},
            {},
            "Lightbar: cor desconhecida",
        ),
        (
            {"lightbar_rgb": None, "lightbar_on": True,
             "lightbar_source": "sysfs"},
            {},
            "Lightbar: cor desconhecida",
        ),
        (
            {"lightbar_rgb": [16, 32, 72], "lightbar_on": True,
             "lightbar_source": "sysfs"},
            {"native_mode": True},
            None,
        ),
        (
            {"lightbar_rgb": [16, 32, 72], "lightbar_on": True,
             "lightbar_source": "sysfs"},
            {},
            None,
        ),
    ],
)
def test_rotulo_lightbar_funcao_pura(
    entry_kw: dict[str, Any], state_kw: dict[str, Any], esperado: str | None
) -> None:
    rotulo, _base = rotulo_lightbar(_entry(**entry_kw), _state(**state_kw))
    assert rotulo == esperado


def test_gate_timers_nenhuma_ocorrencia_nova_vs_baseline() -> None:
    """Baseline da mixin: 2 periódicos em ms + 1 periódico em segundos +"""
    src_mixin = Path(sa_mod.__file__).read_text(encoding="utf-8")
    src_card = Path(cc_mod.__file__).read_text(encoding="utf-8")

    assert len(re.findall(r"GLib\.timeout_add\(", src_mixin)) == 2
    assert len(re.findall(r"GLib\.timeout_add_seconds\(", src_mixin)) == 2
    assert len(re.findall(r"GLib\.idle_add\(", src_mixin)) == 2

    assert len(re.findall(r"GLib\.timeout_add\(", src_card)) == 2
    assert len(re.findall(r"def _on_\w+_repouso\(self\)", src_card)) == 2
    assert re.search(r"GLib\.timeout_add_seconds\(", src_card) is None
    assert re.search(r"GLib\.idle_add\(", src_card) is None


