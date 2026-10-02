"""AGORA E DEPOIS — a escolha dela para de voltar sozinha, e o clique para de aplicar."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("AGORA-E-DEPOIS-01: a escolha pendente")

import sys
import types
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.app.actions import (
    footer_actions,
    home_actions,
    mode_transition,
    relancar,
)


class _StyleCtx:
    def __init__(self) -> None:
        self.classes: list[str] = []

    def add_class(self, name: str) -> None:
        if name not in self.classes:
            self.classes.append(name)

    def remove_class(self, name: str) -> None:
        if name in self.classes:
            self.classes.remove(name)


class _FakeWidget:
    """O subconjunto de `Gtk` que o `_render_home` toca."""

    def __init__(self, label: str | None = None, **_kwargs: object) -> None:
        self.label = label
        self.children: list[_FakeWidget] = []
        self.style = _StyleCtx()
        self.sensitive = True
        self.visible = True
        self.active_id: str | None = None

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

    def set_label(self, text: str) -> None:
        self.label = text

    def get_label(self) -> str:
        return str(self.label or "")

    def get_text(self) -> str:
        return str(self.label or "")

    def get_active_id(self) -> str | None:
        return self.active_id

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = value

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_no_show_all(self, _value: bool) -> None:
        pass

    def set_active(self, _value: bool) -> None:
        pass

    def set_active_id(self, value: str) -> None:
        self.active_id = value

    def pack_start(self, child: _FakeWidget, *_args: object) -> None:
        self.children.append(child)

    def get_children(self) -> list[_FakeWidget]:
        return list(self.children)

    def remove(self, child: _FakeWidget) -> None:
        self.children.remove(child)

    def show_all(self) -> None:
        pass


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_FakeWidget,
        Box=_FakeWidget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


@pytest.fixture()
def sem_ipc(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Grava toda chamada IPC dos dois módulos que a aba Início usava."""
    chamadas: list[tuple[str, dict[str, Any]]] = []

    def _fake(
        method: str,
        params: dict[str, Any] | None = None,
        _done: Any = None,
        _fail: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        chamadas.append((method, dict(params or {})))

    monkeypatch.setattr(home_actions, "call_async", _fake)
    monkeypatch.setattr(mode_transition, "call_async", _fake)
    return chamadas


def _estado(
    *, modo: str = "gamepad", mascara: str = "dualsense", jogo: bool = False
) -> dict[str, Any]:
    return {
        "gamepad_emulation": {"enabled": modo == "gamepad", "flavor": mascara},
        "native_mode": modo == "native",
        "controllers": [
            {"index": 0, "connected": True, "transport": "usb", "is_primary": True}
        ],
        "game_signal": {"authority": "game" if jogo else "daemon"},
    }


class TestALinhaDoPendente:
    def test_a_frase_pura_compoe_os_dois_campos(self) -> None:
        assert relancar.texto_do_pendente() == ""
        so_modo = relancar.texto_do_pendente(modo="Jogar pelo Hefesto")
        assert "vai mudar para" in so_modo and "Jogar pelo Hefesto" in so_modo
        dois = relancar.texto_do_pendente(
            modo="Jogar pelo Hefesto", mascara="DualSense (botões PlayStation)"
        )
        assert "Jogar pelo Hefesto" in dois and "DualSense" in dois


class _Dialogo:
    """Captura o diálogo em vez de abri-lo, e deixa o teste responder por ela."""

    def __init__(self) -> None:
        self.aberto = False
        self.botoes: list[str] = []
        self._on_response: Any = None

    def construir(
        self,
        _parent: Any,
        *,
        titulo: str,
        corpo: str,
        botoes: list[tuple[str, int]],
        on_response: Any,
        destrutivo: int | None = None,
    ) -> Any:
        self.aberto = True
        self.titulo = titulo
        self.corpo = corpo
        self.botoes = [rotulo for rotulo, _ in botoes]
        self._on_response = on_response
        return MagicMock()

    def responder(self, resposta: int) -> None:
        assert self._on_response is not None, "o diálogo não chegou a abrir"
        self._on_response(MagicMock(), resposta)


@pytest.fixture()
def ipc_do_rodape(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, dict[str, Any]]]:
    """Grava o que sai pelos DOIS canos do "Aplicar": a transição e o rascunho."""
    chamadas: list[tuple[str, dict[str, Any]]] = []

    def _transicao(
        method: str,
        params: dict[str, Any] | None = None,
        on_done: Any = None,
        _on_fail: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        chamadas.append((method, dict(params or {})))
        if on_done is not None:
            on_done({"status": "ok"})

    def _draft(
        method: str,
        params: dict[str, Any] | None = None,
        on_success: Any = None,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        chamadas.append((method, {}))
        if on_success is not None:
            on_success({"status": "ok", "applied": ["leds"]})

    monkeypatch.setattr(mode_transition, "call_async", _transicao)
    monkeypatch.setattr(footer_actions.ipc_bridge, "call_async", _draft)
    return chamadas


