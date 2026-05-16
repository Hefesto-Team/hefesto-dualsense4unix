"""Testes do `desktop_notifications` (FEAT-COSMIC-TRAY-FALLBACK-01).

Cobre:
  - `notify()` retorna False sem jeepney.
  - `notify()` deduplica via `once_key`.
  - `statusnotifierwatcher_available()` retorna bool sem traceback.
  - Estrutura da chamada D-Bus (signature, args).
"""
from __future__ import annotations

import sys
import types
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.integrations import desktop_notifications


class _FakeReply:
    def __init__(self, body: tuple[Any, ...]) -> None:
        self.body = body


class _FakeConn:
    instances: ClassVar[list[_FakeConn]] = []

    def __init__(
        self,
        reply_body: tuple[Any, ...] | None = None,
        raise_on_send: Exception | None = None,
    ) -> None:
        self.reply_body = (12345,) if reply_body is None else reply_body
        self.raise_on_send = raise_on_send
        self.closed = False
        self.calls: list[Any] = []
        _FakeConn.instances.append(self)

    def send_and_get_reply(self, msg: Any, *, timeout: float | None = None) -> _FakeReply:
        self.calls.append({"msg": msg, "timeout": timeout})
        if self.raise_on_send is not None:
            raise self.raise_on_send
        return _FakeReply(self.reply_body)

    def close(self) -> None:
        self.closed = True


def _install_fake_jeepney(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reply_body: tuple[Any, ...] | None = None,
    raise_on_send: Exception | None = None,
    raise_on_open: Exception | None = None,
) -> list[_FakeConn]:
    _FakeConn.instances = []

    def _open_dbus_connection(bus: str = "SESSION") -> _FakeConn:
        if raise_on_open is not None:
            raise raise_on_open
        return _FakeConn(reply_body=reply_body, raise_on_send=raise_on_send)

    class _DBusAddress:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    captured_calls: list[Any] = []

    def _new_method_call(*args: Any, **kwargs: Any) -> dict[str, Any]:
        captured_calls.append({"args": args, "kwargs": kwargs})
        return {"call": True, "args": args}

    jeepney_mod = types.ModuleType("jeepney")
    jeepney_mod.DBusAddress = _DBusAddress  # type: ignore[attr-defined]
    jeepney_mod.new_method_call = _new_method_call  # type: ignore[attr-defined]
    jeepney_mod._captured_calls = captured_calls  # type: ignore[attr-defined]

    jeepney_io = types.ModuleType("jeepney.io")
    jeepney_io_blocking = types.ModuleType("jeepney.io.blocking")
    jeepney_io_blocking.open_dbus_connection = _open_dbus_connection  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "jeepney", jeepney_mod)
    monkeypatch.setitem(sys.modules, "jeepney.io", jeepney_io)
    monkeypatch.setitem(sys.modules, "jeepney.io.blocking", jeepney_io_blocking)

    return _FakeConn.instances


@pytest.fixture(autouse=True)
def _reset_once_cache() -> None:
    desktop_notifications.reset_once_cache()


class TestNotify:
    """Função notify()."""

    def test_sem_jeepney_retorna_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in ("jeepney", "jeepney.io", "jeepney.io.blocking"):
            monkeypatch.setitem(sys.modules, name, None)  # type: ignore[arg-type]
        assert desktop_notifications.notify("titulo", "corpo") is False

    def test_caminho_feliz_retorna_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_jeepney(monkeypatch, reply_body=(42,))
        assert desktop_notifications.notify("titulo", "corpo") is True

    def test_dbus_signature_susssasa_sv_i(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Args do new_method_call seguem a signature do org.freedesktop.Notifications."""
        _install_fake_jeepney(monkeypatch, reply_body=(1,))
        desktop_notifications.notify(
            "titulo",
            "corpo",
            app_name="App",
            icon="ic",
            timeout_ms=2000,
        )
        captured = sys.modules["jeepney"]._captured_calls  # type: ignore[attr-defined]
        assert captured
        last = captured[-1]
        assert last["args"][1] == "Notify"
        assert last["args"][2] == "susssasa{sv}i"
        notify_args = last["args"][3]
        assert notify_args[0] == "App"
        assert notify_args[1] == 0
        assert notify_args[2] == "ic"
        assert notify_args[3] == "titulo"
        assert notify_args[4] == "corpo"
        assert notify_args[5] == []
        assert notify_args[6] == {}
        assert notify_args[7] == 2000

    def test_excecao_no_send_retorna_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_jeepney(monkeypatch, raise_on_send=TimeoutError("daemon morto"))
        assert desktop_notifications.notify("x") is False

    def test_excecao_no_open_retorna_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_jeepney(monkeypatch, raise_on_open=OSError("dbus down"))
        assert desktop_notifications.notify("x") is False

    def test_conexao_sempre_fechada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conns = _install_fake_jeepney(monkeypatch, raise_on_send=RuntimeError("y"))
        desktop_notifications.notify("titulo")
        assert len(conns) == 1
        assert conns[0].closed is True

    def test_once_key_deduplica(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conns = _install_fake_jeepney(monkeypatch, reply_body=(1,))
        r1 = desktop_notifications.notify("a", once_key="aviso_x")
        r2 = desktop_notifications.notify("a", once_key="aviso_x")
        r3 = desktop_notifications.notify("a", once_key="aviso_x")
        assert r1 is True
        assert r2 is False
        assert r3 is False
        # Apenas uma conn criada.
        assert len(conns) == 1

    def test_once_key_diferentes_keys_passam(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        conns = _install_fake_jeepney(monkeypatch, reply_body=(1,))
        r1 = desktop_notifications.notify("a", once_key="x")
        r2 = desktop_notifications.notify("b", once_key="y")
        assert r1 is True
        assert r2 is True
        assert len(conns) == 2

    def test_sem_once_key_nunca_deduplica(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        conns = _install_fake_jeepney(monkeypatch, reply_body=(1,))
        for _ in range(5):
            assert desktop_notifications.notify("a") is True
        assert len(conns) == 5

    def test_reset_once_cache_volta_a_emitir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_jeepney(monkeypatch, reply_body=(1,))
        assert desktop_notifications.notify("a", once_key="x") is True
        assert desktop_notifications.notify("a", once_key="x") is False
        desktop_notifications.reset_once_cache()
        assert desktop_notifications.notify("a", once_key="x") is True


class TestStatusNotifierWatcherAvailable:
    """Função statusnotifierwatcher_available()."""

    def test_sem_jeepney_retorna_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in ("jeepney", "jeepney.io", "jeepney.io.blocking"):
            monkeypatch.setitem(sys.modules, name, None)  # type: ignore[arg-type]
        assert desktop_notifications.statusnotifierwatcher_available() is False

    def test_dbus_responde_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_jeepney(monkeypatch, reply_body=(True,))
        assert desktop_notifications.statusnotifierwatcher_available() is True

    def test_dbus_responde_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_jeepney(monkeypatch, reply_body=(False,))
        assert desktop_notifications.statusnotifierwatcher_available() is False

    def test_dbus_excecao_retorna_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_jeepney(monkeypatch, raise_on_send=RuntimeError("x"))
        assert desktop_notifications.statusnotifierwatcher_available() is False

    def test_dbus_body_vazio_retorna_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_jeepney(monkeypatch, reply_body=())
        assert desktop_notifications.statusnotifierwatcher_available() is False

    def test_dbus_args_corretos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_jeepney(monkeypatch, reply_body=(True,))
        desktop_notifications.statusnotifierwatcher_available()
        captured = sys.modules["jeepney"]._captured_calls  # type: ignore[attr-defined]
        last = captured[-1]
        assert last["args"][1] == "NameHasOwner"
        assert last["args"][2] == "s"
        assert last["args"][3] == ("org.kde.StatusNotifierWatcher",)
