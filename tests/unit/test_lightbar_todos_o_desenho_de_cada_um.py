"""L12 — o "Todos" pinta o mesmo número de jogador nos quatro."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("lightbar todos o desenho de cada um")

from typing import Any

import pytest

gi = pytest.importorskip("gi")

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app import draft_config as draft_mod
from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin
from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

UNIQ_1 = "aa:bb:cc:00:00:01"
UNIQ_2 = "aa:bb:cc:00:00:02"
ROXO = (129, 61, 156)

MESA = {0: (UNIQ_1, 1), 1: (UNIQ_2, 2)}


class _Caixa:
    def __init__(self) -> None:
        self.active = False

    def connect(self, *_a: Any, **_kw: Any) -> None:
        return None

    def get_active(self) -> bool:
        return self.active

    def set_active(self, valor: bool) -> None:
        self.active = bool(valor)


def _aceitou(uniq: str | None) -> dict[str, Any]:
    """Corpo de um ``led.player_set`` que ESCREVEU em ``uniq`` (BG-01)."""
    return {
        "status": "ok",
        "bits": [],
        "aplicado_em": [uniq] if uniq else [],
        "guardado_em": [],
    }


class _Host(LightbarActionsMixin):
    """Host da aba com DOIS controles na mesa e o alvo em "Todos"."""

    def __init__(self, draft: draft_mod.DraftConfig) -> None:
        self.draft = draft
        self._edit_target_uniq = None
        self._target_uniq_by_index = {i: u for i, (u, _s) in MESA.items()}
        self._target_slot_by_index = {i: s for i, (_u, s) in MESA.items()}
        self._widgets: dict[str, Any] = {"auto_player_colors_check": _Caixa()}
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


def _draft() -> draft_mod.DraftConfig:
    return draft_mod.DraftConfig.from_profile(
        Profile(
            name="vitoria",
            match=MatchAny(),
            priority=5,
            leds=LedsConfig(
                lightbar=ROXO,
                player_leds=[False] * 5,
                lightbar_brightness=1.0,
                auto_player_colors=True,
            ),
        )
    )


def test_o_perfil_nao_pode_guardar_o_numero_do_vizinho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O que o teste acima mede no FIO, este mede no PERFIL — e é pior."""
    pytest.xfail(
        "L12 — mesmo defeito do teste acima, medido no rascunho: "
        "`_persist_leds_update` grava o MESMO desenho no override de cada MAC. "
        "Sai com a resposta dela."
    )


