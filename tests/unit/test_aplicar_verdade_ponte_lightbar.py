"""APLICAR-VERDADE-01/E2 — a ponte parou de estreitar a verdade."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("aplicar-verdade ponte lightbar")

from typing import Any

import gi
import pytest

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.actions import lightbar_actions
from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin, frase_do_envio
from hefesto_dualsense4unix.app.textos_de_aplicacao import (
    frase_do_desfecho,
)
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

FRASE_APLICAR_OFFLINE = (
    "Não consegui aplicar a cor — o Hefesto pode estar desligado "
    "(ligue na aba Sistema)"
)
FRASE_APAGAR_OFFLINE = "Falha (daemon offline?)"

RESPOSTA_LEDS_FORA: dict[str, Any] = {
    "status": "ok",
    "applied": [],
    "failed": {"leds": "hidraw: Permission denied"},
}


class _Host(LightbarActionsMixin):
    """Hospedeiro mínimo do mixin: draft + toast espião, sem display."""

    def __init__(self, draft: DraftConfig) -> None:
        self.draft = draft
        self._edit_target_uniq = None
        self._widgets: dict[str, Any] = {}
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


def _host() -> _Host:
    """Host no caminho degradado COR-04: alvo "Todos" e nenhum MAC conhecido."""
    perfil = Profile(
        name="vitoria",
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(
            lightbar=(129, 61, 156),
            lightbar_brightness=1.0,
            auto_player_colors=False,
        ),
    )
    return _Host(DraftConfig.from_profile(perfil))


def _selar_daemon(
    monkeypatch: pytest.MonkeyPatch, resposta: Any, *, respondeu: bool = True
) -> None:
    """Sela a saída IPC: nenhum teste daqui toca no daemon real."""
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "_safe_call",
        lambda *_a, **_kw: (respondeu, resposta),
    )


def _gdk_rgba_ok() -> bool:
    """A CI headless de release tem um Gdk parcial sem RGBA (o "Apagar"
    constrói um) — mesmo skip de ``test_lightbar_auto_colors``."""
    try:
        from gi.repository import Gdk

        return hasattr(Gdk, "RGBA")
    except Exception:
        return False


def _ultimo_toast(host: _Host) -> str:
    assert host._toasts, "a aba não disse nada — o toast do resultado sumiu"
    return host._toasts[-1]


UNIQ_ALVO = "aabbcc000001"

def _host_que_a_heuristica_leria_como_aplicado() -> _Host:
    host = _host()
    host._edit_target_uniq = UNIQ_ALVO
    host._edit_target_label = "Controle 1 (USB)"
    host._target_uniq_by_index = {0: UNIQ_ALVO}
    host._modo_nativo_ligado = False
    host._coop_ligado = False
    host._current_rgb = (10, 20, 30)
    host._current_brightness = 0.8
    return host


def _selar_corpo(monkeypatch: pytest.MonkeyPatch, corpo: Any) -> None:
    """Sela a rota `led.set` por MAC com um corpo escolhido do daemon."""
    monkeypatch.setattr(
        lightbar_actions,
        "led_set_detalhado",
        lambda *_a, **_kw: corpo,
    )


def test_a_regua_do_ramo_aplicado(monkeypatch: pytest.MonkeyPatch) -> None:
    """O acoplamento REAL de `frase_do_envio`, medido em vez de suposto.

    `frase_do_envio` reconhece o ramo do aplicado de `frase_do_desfecho` pela
    FORMA com que ele sai de lá — `"<assunto> aplicado"` e
    `"<assunto> aplicado em N controles"`. No dia em que aquela frase mudar de
    forma, esta aba deixa de reconhecê-la e passa a mostrar na tela a palavra
    "aplicado", que ela recusa por medição. Este teste reprova nesse dia, em
    vez de a divergência sair na tela do usuário.
    """
    corpo_um = {"status": "ok", "aplicado_em": ["a"], "guardado_em": []}
    corpo_tres = {"status": "ok", "aplicado_em": ["a", "b", "c"], "guardado_em": []}
    host = _host_que_a_heuristica_leria_como_aplicado()

    for corpo in (corpo_um, corpo_tres):
        assert frase_do_desfecho("Assunto", corpo, host).startswith(
            "Assunto aplicado"
        ), "o ramo do aplicado mudou de forma — `frase_do_envio` não o vê mais"
        assert frase_do_envio("Assunto", "a frase desta aba", corpo, host) == (
            "a frase desta aba"
        )
