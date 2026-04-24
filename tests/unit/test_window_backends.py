"""Testes do WaylandPortalBackend — degradação sem jeepney, caminho feliz
com jeepney mockado, zero ThreadPoolExecutor/asyncio.run por chamada,
propagação de timeout nativo.

Sprint: AUDIT-FINDING-WAYLAND-PORTAL-PERF-01.
"""
from __future__ import annotations

import sys
import threading
import types
from typing import Any, ClassVar

import pytest

from hefesto.integrations.window_backends import wayland_portal

# ---------------------------------------------------------------------------
# Helpers — stub do pacote `jeepney` injetado via sys.modules
# ---------------------------------------------------------------------------


class _FakeReply:
    def __init__(self, body: tuple[Any, ...]) -> None:
        self.body = body


class _FakeConn:
    instances: ClassVar[list[_FakeConn]] = []

    def __init__(self, reply_body: tuple[Any, ...] | None = None,
                 raise_on_send: Exception | None = None) -> None:
        self.reply_body = reply_body or ("handle_xyz", {})
        self.raise_on_send = raise_on_send
        self.closed = False
        self.timeouts_received: list[float | None] = []
        _FakeConn.instances.append(self)

    def send_and_get_reply(self, msg: Any, *, timeout: float | None = None) -> _FakeReply:
        self.timeouts_received.append(timeout)
        if self.raise_on_send is not None:
            raise self.raise_on_send
        return _FakeReply(self.reply_body)

    def close(self) -> None:
        self.closed = True


def _install_fake_jeepney(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reply_body: tuple[Any, ...] | None = None,
    raise_on_open: Exception | None = None,
    raise_on_send: Exception | None = None,
) -> list[_FakeConn]:
    """Injeta um pacote `jeepney` falso em sys.modules.

    Retorna a lista compartilhada de conexões criadas (para asserts).
    """
    _FakeConn.instances = []

    def _open_dbus_connection(bus: str = "SESSION") -> _FakeConn:
        if raise_on_open is not None:
            raise raise_on_open
        return _FakeConn(reply_body=reply_body, raise_on_send=raise_on_send)

    class _DBusAddress:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    def _new_method_call(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"call": True, "args": args}

    jeepney_mod = types.ModuleType("jeepney")
    jeepney_mod.DBusAddress = _DBusAddress  # type: ignore[attr-defined]
    jeepney_mod.new_method_call = _new_method_call  # type: ignore[attr-defined]

    jeepney_io = types.ModuleType("jeepney.io")
    jeepney_io_blocking = types.ModuleType("jeepney.io.blocking")
    jeepney_io_blocking.open_dbus_connection = _open_dbus_connection  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "jeepney", jeepney_mod)
    monkeypatch.setitem(sys.modules, "jeepney.io", jeepney_io)
    monkeypatch.setitem(sys.modules, "jeepney.io.blocking", jeepney_io_blocking)

    return _FakeConn.instances


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_sem_jeepney_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem jeepney instalado, get_active_window_info degrada para None."""
    # Garante que qualquer jeepney em cache seja invisível via ImportError.
    for name in ("jeepney", "jeepney.io", "jeepney.io.blocking"):
        monkeypatch.setitem(sys.modules, name, None)  # type: ignore[arg-type]

    backend = wayland_portal.WaylandPortalBackend()
    assert backend.get_active_window_info() is None


def test_caminho_feliz_com_jeepney_mockado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reply válido do portal deve produzir WindowInfo com app_id/title/pid."""
    _install_fake_jeepney(
        monkeypatch,
        reply_body=(
            "handle_xyz",
            {"app-id": "org.mozilla.Firefox", "title": "Mozilla Firefox", "pid": 1234},
        ),
    )
    backend = wayland_portal.WaylandPortalBackend()
    info = backend.get_active_window_info()
    assert info is not None
    assert info.app_id == "org.mozilla.Firefox"
    assert info.wm_class == "org.mozilla.Firefox"
    assert info.title == "Mozilla Firefox"
    assert info.pid == 1234


def test_reply_vazio_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_jeepney(monkeypatch, reply_body=("handle_xyz", {}))
    backend = wayland_portal.WaylandPortalBackend()
    assert backend.get_active_window_info() is None


def test_reply_sem_segundo_elemento_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_jeepney(monkeypatch, reply_body=("handle_xyz",))
    backend = wayland_portal.WaylandPortalBackend()
    assert backend.get_active_window_info() is None


def test_excecao_no_send_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_jeepney(monkeypatch, raise_on_send=TimeoutError("portal timeout"))
    backend = wayland_portal.WaylandPortalBackend()
    assert backend.get_active_window_info() is None


def test_excecao_no_open_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_jeepney(monkeypatch, raise_on_open=OSError("dbus down"))
    backend = wayland_portal.WaylandPortalBackend()
    assert backend.get_active_window_info() is None


def test_timeout_explicito_propagado_ao_jeepney(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confirma que send_and_get_reply recebe timeout=_PORTAL_TIMEOUT_SECONDS."""
    conns = _install_fake_jeepney(
        monkeypatch,
        reply_body=("handle", {"app-id": "a", "title": "b", "pid": 1}),
    )
    backend = wayland_portal.WaylandPortalBackend()
    backend.get_active_window_info()
    assert len(conns) == 1
    assert conns[0].timeouts_received == [wayland_portal._PORTAL_TIMEOUT_SECONDS]


def test_conexao_sempre_fechada_mesmo_com_excecao(monkeypatch: pytest.MonkeyPatch) -> None:
    """finally em _try_jeepney garante conn.close() mesmo se send falhar."""
    conns = _install_fake_jeepney(monkeypatch, raise_on_send=RuntimeError("x"))
    backend = wayland_portal.WaylandPortalBackend()
    backend.get_active_window_info()
    assert len(conns) == 1
    assert conns[0].closed is True


def test_multiplas_chamadas_nao_criam_threadpoolexecutor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invariante central da sprint: nenhuma thread extra por chamada.

    Substitui `concurrent.futures.ThreadPoolExecutor` por um sentinela que
    marca a flag se for instanciado. Roda 20 chamadas de
    get_active_window_info e confirma que a flag permaneceu False.
    """
    import concurrent.futures as _cf

    pool_created = {"flag": False}

    original_pool = _cf.ThreadPoolExecutor

    class _SentinelPool(original_pool):  # type: ignore[misc,valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pool_created["flag"] = True
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(_cf, "ThreadPoolExecutor", _SentinelPool)

    _install_fake_jeepney(
        monkeypatch,
        reply_body=("h", {"app-id": "x", "title": "y", "pid": 7}),
    )
    backend = wayland_portal.WaylandPortalBackend()
    for _ in range(20):
        backend.get_active_window_info()
    assert pool_created["flag"] is False


def test_multiplas_chamadas_nao_criam_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invariante: threading.active_count() estável entre chamadas."""
    _install_fake_jeepney(
        monkeypatch,
        reply_body=("h", {"app-id": "z", "title": "t", "pid": 9}),
    )
    backend = wayland_portal.WaylandPortalBackend()
    baseline = threading.active_count()
    for _ in range(30):
        backend.get_active_window_info()
    # Permite flutuação mínima (garbage collector, daemon threads do pytest).
    assert threading.active_count() <= baseline + 1


def test_nao_chama_asyncio_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invariante: asyncio.run não é invocado pelo backend."""
    import asyncio

    called = {"count": 0}
    original_run = asyncio.run

    def _spy_run(*args: Any, **kwargs: Any) -> Any:
        called["count"] += 1
        return original_run(*args, **kwargs)

    monkeypatch.setattr(asyncio, "run", _spy_run)

    _install_fake_jeepney(
        monkeypatch,
        reply_body=("h", {"app-id": "q", "title": "r", "pid": 2}),
    )
    backend = wayland_portal.WaylandPortalBackend()
    for _ in range(5):
        backend.get_active_window_info()
    assert called["count"] == 0


def test_dbus_fast_foi_removido() -> None:
    """Regressão: _try_dbus_fast não deve existir mais no módulo."""
    assert not hasattr(wayland_portal, "_try_dbus_fast")


def test_handle_counter_incrementa_por_chamada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_jeepney(
        monkeypatch,
        reply_body=("h", {"app-id": "a", "title": "b", "pid": 1}),
    )
    backend = wayland_portal.WaylandPortalBackend()
    h1 = backend._next_handle()
    h2 = backend._next_handle()
    assert h1 != h2
    assert h1.startswith("hefesto_")
    assert h2.endswith("_2")


def test_parse_portal_result_sem_app_id() -> None:
    """Reply com title/pid mas sem app-id → wm_class='unknown'."""
    info = wayland_portal._parse_portal_result({"title": "Terminal", "pid": 42})
    assert info is not None
    assert info.wm_class == "unknown"
    assert info.app_id == ""
    assert info.title == "Terminal"
    assert info.pid == 42


def test_parse_portal_result_app_id_alternativo() -> None:
    """Aceita variante `app_id` (underscore) além de `app-id`."""
    info = wayland_portal._parse_portal_result({"app_id": "foo", "title": "bar"})
    assert info is not None
    assert info.app_id == "foo"
    assert info.wm_class == "foo"


def test_parse_portal_result_vazio() -> None:
    assert wayland_portal._parse_portal_result({}) is None


# ---------------------------------------------------------------------------
# BUG-COSMIC-PORTAL-UNSUPPORTED-01 — threshold + recovery
# ---------------------------------------------------------------------------


def test_portal_unsupported_apos_threshold_falhas(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """Após N falhas consecutivas, backend loga warning único e para de
    consultar o portal. Previne ruído em COSMIC alpha que ainda não
    implementa GetActiveWindow."""
    import logging

    _install_fake_jeepney(
        monkeypatch,
        raise_on_send=RuntimeError("no such method"),
    )
    backend = wayland_portal.WaylandPortalBackend()

    # Primeiras N chamadas ainda tocam o portal — todas falham → None.
    for _ in range(backend._UNSUPPORTED_THRESHOLD):
        assert backend.get_active_window_info() is None

    baseline_calls = len(_FakeConn.instances)

    caplog.set_level(logging.WARNING, logger="hefesto.integrations.window_backends.wayland_portal")

    # A próxima chamada deve retornar None IMEDIATAMENTE sem abrir conexão.
    assert backend.get_active_window_info() is None
    assert len(_FakeConn.instances) == baseline_calls

    # Chamadas subsequentes idem — warning é emitido só uma vez.
    for _ in range(10):
        backend.get_active_window_info()
    assert len(_FakeConn.instances) == baseline_calls


def test_portal_recupera_se_volta_a_responder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Se portal volta a responder dentro do threshold, contador reseta e
    backend volta ao normal."""
    backend = wayland_portal.WaylandPortalBackend()

    # 2 falhas consecutivas (< threshold=3)
    _install_fake_jeepney(monkeypatch, raise_on_send=RuntimeError("fail"))
    for _ in range(2):
        assert backend.get_active_window_info() is None
    assert backend._consecutive_failures == 2

    # Próxima chamada responde com sucesso → contador reseta.
    _install_fake_jeepney(
        monkeypatch,
        reply_body=("h", {"app-id": "foo", "title": "bar", "pid": 1}),
    )
    info = backend.get_active_window_info()
    assert info is not None
    assert info.app_id == "foo"
    assert backend._consecutive_failures == 0
    assert backend._unsupported_warned is False


def test_compositor_hint_usa_xdg_current_desktop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "COSMIC:GNOME")
    backend = wayland_portal.WaylandPortalBackend()
    assert backend._compositor_hint() == "COSMIC:GNOME"


def test_compositor_hint_fallback_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    monkeypatch.delenv("XDG_SESSION_DESKTOP", raising=False)
    backend = wayland_portal.WaylandPortalBackend()
    assert backend._compositor_hint() == "unknown"
