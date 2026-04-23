"""Testes da detecção de janela ativa X11."""
from __future__ import annotations

import pytest

from hefesto.integrations.xlib_window import (
    UNKNOWN_WINDOW,
    XlibClient,
    get_active_window_info,
)


def test_sem_display_cai_em_unknown(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    client = XlibClient()
    assert client.is_connected() is False
    assert client.active_window_info() == UNKNOWN_WINDOW


def test_unknown_constante_tem_campos_esperados():
    keys = {"wm_class", "wm_name", "pid", "exe_basename"}
    assert set(UNKNOWN_WINDOW.keys()) == keys


def test_exe_basename_fallback_pid_invalido():
    from hefesto.integrations.xlib_window import _exe_basename_from_pid

    assert _exe_basename_from_pid(0) == ""
    # PID 1 (init) existe mas pode negar leitura — esperamos string (vazia ou nome)
    result = _exe_basename_from_pid(1)
    assert isinstance(result, str)


def test_get_active_window_info_sem_display(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    info = get_active_window_info()
    assert info["wm_class"] == "unknown"


def test_xlib_client_mockado_retorna_dados(monkeypatch: pytest.MonkeyPatch):
    """Simula conexão X11 com display mockado, confirma leitura correta."""

    class FakeProperty:
        def __init__(self, value):
            self.value = value

    class FakeWin:
        def get_wm_class(self):
            return ("firefox", "Firefox")

        def get_wm_name(self):
            return "Mozilla Firefox"

        def get_full_property(self, atom, _type):
            # pid = 12345
            return FakeProperty([12345])

    class FakeRoot:
        def get_full_property(self, atom, _type):
            # NET_ACTIVE_WINDOW -> id da janela
            return FakeProperty([42])

    class FakeScreen:
        root = FakeRoot()

    class FakeDisplay:
        def screen(self):
            return FakeScreen()

        def intern_atom(self, name: str) -> int:
            return 1

        def create_resource_object(self, kind: str, wid: int):
            assert wid == 42
            return FakeWin()

    monkeypatch.setenv("DISPLAY", ":0")

    # Substitui _exe_basename_from_pid pra não depender de /proc real
    from hefesto.integrations import xlib_window

    monkeypatch.setattr(xlib_window, "_exe_basename_from_pid", lambda pid: "firefox-bin")

    client = XlibClient(display=FakeDisplay())
    info = client.active_window_info()
    assert info["wm_class"] == "Firefox"  # segundo elemento da tupla (V3-6)
    assert info["wm_name"] == "Mozilla Firefox"
    assert info["pid"] == 12345
    assert info["exe_basename"] == "firefox-bin"


def test_xlib_client_sem_active_window(monkeypatch: pytest.MonkeyPatch):
    class FakeRootEmpty:
        def get_full_property(self, atom, _type):
            return None

    class FakeScreen:
        root = FakeRootEmpty()

    class FakeDisplay:
        def screen(self):
            return FakeScreen()

        def intern_atom(self, name: str) -> int:
            return 1

    client = XlibClient(display=FakeDisplay())
    info = client.active_window_info()
    assert info == UNKNOWN_WINDOW


def test_xlib_client_query_excecao(monkeypatch: pytest.MonkeyPatch):
    class ExplodingDisplay:
        def screen(self):
            raise RuntimeError("boom")

        def intern_atom(self, name: str) -> int:
            return 1

    client = XlibClient(display=ExplodingDisplay())
    info = client.active_window_info()
    assert info == UNKNOWN_WINDOW
