"""`_render_home` vs o estado do daemon — os dois jeitos que a aba Início mentia.

HARM-CARD-FANTASMA-01: `describe_controllers` devolve UMA entrada com
``connected=False`` quando não há controle nenhum. A aba Status
(`_connected_controllers`) e o applet filtravam por ``connected``; a Início não
— e inventava um card "Controle 1 — P1 · ?" com o cabo na mesa.

HARM-15: o refresh chamava `call_async` SEM ``timeout_s``, caindo no default de
0,25 s — resposta mais lenta do daemon (hotplug, co-op subindo) ia para o
`_fail` e pintava a aba de "Daemon desligado" com o daemon VIVO.

Ambos herméticos: Gtk fake em ``sys.modules`` (o render importa
``gi.repository`` dentro da função) e `call_async` monkeypatchado.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin


class _StyleCtx:
    def __init__(self) -> None:
        self.classes: list[str] = []

    def add_class(self, name: str) -> None:
        self.classes.append(name)


class _FakeWidget:
    def __init__(self, label: str | None = None, **_kwargs: object) -> None:
        self.label = label
        self.children: list[_FakeWidget] = []
        self.style = _StyleCtx()
        self.sensitive = True
        self.visible = True

    def get_style_context(self) -> _StyleCtx:
        return self.style

    def set_xalign(self, _value: float) -> None:
        pass

    def set_margin_end(self, _value: int) -> None:
        pass

    def set_markup(self, markup: str) -> None:
        self.label = markup

    def set_text(self, text: str) -> None:
        self.label = text

    def get_text(self) -> str:
        return str(self.label or "")

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = value

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_no_show_all(self, _value: bool) -> None:
        pass

    def set_active(self, _value: bool) -> None:
        pass

    def set_active_id(self, _value: str) -> None:
        pass

    def pack_start(self, child: _FakeWidget, *_args: object) -> None:
        self.children.append(child)

    def get_children(self) -> list[_FakeWidget]:
        return list(self.children)

    def remove(self, child: _FakeWidget) -> None:
        self.children.remove(child)

    def show_all(self) -> None:
        pass


class _HomeStub:
    _render_home = HomeActionsMixin._render_home
    _render_home_controllers = HomeActionsMixin._render_home_controllers
    _refresh_home_tab = HomeActionsMixin._refresh_home_tab

    def __init__(self) -> None:
        self._home_installed = True
        self._home_inflight = False
        self._home_guard = False
        self._home_controllers_box = _FakeWidget()
        self._home_mode_selector = _FakeWidget()
        self._home_players_hint = _FakeWidget()
        self._home_flavor_selector = _FakeWidget()
        self._home_mode_desc = _FakeWidget()
        self._home_origin_label = _FakeWidget()
        self._home_session_label = _FakeWidget()
        self._home_gamepad_opts = _FakeWidget()


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_FakeWidget,
        Box=_FakeWidget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


def _state(controllers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "gamepad_emulation": {"enabled": True, "flavor": "xbox"},
        "native_mode": False,
        "coop": {"enabled": True, "players": len(controllers)},
        "controllers": controllers,
    }


def _card_labels(host: _HomeStub) -> list[str]:
    return [
        str(child.label)
        for card in host._home_controllers_box.get_children()
        for child in ([card, *card.children])
    ]


class TestCardFantasma:
    def test_entrada_desconectada_nao_vira_card(self, fake_gtk: None) -> None:
        """O payload de "nenhum controle" é uma entrada com connected=False."""
        host = _HomeStub()

        host._render_home(
            _state([{"index": 0, "connected": False, "transport": None,
                     "is_primary": True}])
        )

        (placeholder,) = host._home_controllers_box.get_children()
        assert placeholder.label == "Nenhum controle conectado."

    def test_so_os_conectados_viram_card(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(
            _state(
                [
                    {"index": 0, "connected": True, "transport": "usb",
                     "is_primary": True, "battery_pct": 95},
                    {"index": 1, "connected": False, "transport": "bt",
                     "is_primary": False},
                ]
            )
        )

        cards = host._home_controllers_box.get_children()
        assert len(cards) == 1
        assert any("USB" in label for label in _card_labels(host))

    def test_controles_conectados_seguem_renderizando(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(
            _state(
                [
                    {"index": 0, "connected": True, "transport": "usb",
                     "is_primary": True},
                    {"index": 1, "connected": True, "transport": "bt",
                     "is_primary": False},
                ]
            )
        )

        assert len(host._home_controllers_box.get_children()) == 2


class TestRefreshTimeout:
    def test_state_full_pede_folga_maior_que_o_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Com o default de 0,25s a aba declarava o daemon morto sob carga."""
        calls: list[tuple[str, float]] = []

        def _fake_call_async(
            method: str,
            _params: dict[str, Any] | None,
            _done: Any = None,
            _fail: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            calls.append((method, timeout_s))

        monkeypatch.setattr(home_actions, "call_async", _fake_call_async)
        host = _HomeStub()

        host._refresh_home_tab()

        assert calls == [("daemon.state_full", home_actions._STATE_IPC_TIMEOUT_S)]
        assert home_actions._STATE_IPC_TIMEOUT_S > 0.25
