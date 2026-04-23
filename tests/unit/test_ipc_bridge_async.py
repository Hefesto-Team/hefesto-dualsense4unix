"""Testes de call_async em ipc_bridge.

Verifica que:
  (a) call_async não bloqueia a thread chamadora;
  (b) callback de sucesso é invocado com o resultado;
  (c) callback de falha invocado em IpcError/FileNotFoundError;
  (d) timeout honrado — worker retorna rápido, sem esperar forever.

Usa unittest.mock.patch para isolar de socket real.
"""
from __future__ import annotations

import threading
import time
import types
from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers de stub GTK-less
# ---------------------------------------------------------------------------


class _FakeGLib:
    """Substituto de gi.repository.GLib para testes sem display."""

    recorded_calls: ClassVar[list[tuple]] = []

    @classmethod
    def idle_add(cls, fn, *args):
        """Executa o callback imediatamente (sem loop GTK) e registra."""
        cls.recorded_calls.append((fn, args))
        fn(*args)
        return 0

    @classmethod
    def reset(cls) -> None:
        cls.recorded_calls.clear()


def _make_fake_glib_module() -> types.ModuleType:
    """Retorna um módulo stub com GLib."""
    mod = types.ModuleType("gi.repository")
    mod.GLib = _FakeGLib
    return mod


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_glib_and_executor():
    """Reseta estado compartilhado entre testes."""
    _FakeGLib.reset()
    import hefesto.app.ipc_bridge as bridge
    bridge._EXECUTOR = None
    yield
    if bridge._EXECUTOR is not None:
        bridge._EXECUTOR.shutdown(wait=True)
        bridge._EXECUTOR = None


def test_call_async_nao_bloqueia():
    """call_async retorna imediatamente sem bloquear a thread chamadora."""
    import hefesto.app.ipc_bridge as bridge

    bloqueio = threading.Event()

    def _run_call_lento(*_args, **_kwargs):
        bloqueio.wait(timeout=2)
        return {"connected": True}

    on_success = MagicMock(return_value=False)

    with (
        patch("hefesto.app.ipc_bridge._run_call", side_effect=_run_call_lento),
        patch.dict("sys.modules", {"gi.repository": _make_fake_glib_module()}),
    ):
        inicio = time.monotonic()
        bridge.call_async("daemon.state_full", None, on_success=on_success)
        duracao = time.monotonic() - inicio

    bloqueio.set()

    assert duracao < 0.3, f"call_async bloqueou por {duracao:.2f}s"


def test_call_async_callback_sucesso():
    """on_success é chamado com o resultado do RPC."""
    import hefesto.app.ipc_bridge as bridge

    resultado_esperado = {"connected": True, "transport": "USB"}
    recebido: list = []

    def on_success(val: object) -> bool:
        recebido.append(val)
        return False

    with (
        patch("hefesto.app.ipc_bridge._run_call", return_value=resultado_esperado),
        patch.dict("sys.modules", {"gi.repository": _make_fake_glib_module()}),
    ):
        bridge.call_async("daemon.state_full", None, on_success=on_success)
        if bridge._EXECUTOR:
            bridge._EXECUTOR.shutdown(wait=True)

    assert recebido == [resultado_esperado]


def test_call_async_callback_falha_ipc_error():
    """on_failure é chamado quando _run_call levanta IpcError."""
    import hefesto.app.ipc_bridge as bridge
    from hefesto.cli.ipc_client import IpcError

    erros: list = []

    def on_success(_val: object) -> bool:
        pytest.fail("on_success não deveria ser chamado em caso de erro")
        return False

    def on_failure(exc: Exception) -> bool:
        erros.append(exc)
        return False

    excecao_esperada = IpcError(-1, "conexão timeout")

    with (
        patch("hefesto.app.ipc_bridge._run_call", side_effect=excecao_esperada),
        patch.dict("sys.modules", {"gi.repository": _make_fake_glib_module()}),
    ):
        bridge.call_async(
            "daemon.state_full",
            None,
            on_success=on_success,
            on_failure=on_failure,
        )
        if bridge._EXECUTOR:
            bridge._EXECUTOR.shutdown(wait=True)

    assert len(erros) == 1
    assert isinstance(erros[0], IpcError)


def test_call_async_callback_falha_file_not_found():
    """on_failure é chamado quando _run_call levanta FileNotFoundError."""
    import hefesto.app.ipc_bridge as bridge

    erros: list = []

    def on_failure(exc: Exception) -> bool:
        erros.append(exc)
        return False

    with (
        patch(
            "hefesto.app.ipc_bridge._run_call",
            side_effect=FileNotFoundError("socket não encontrado"),
        ),
        patch.dict("sys.modules", {"gi.repository": _make_fake_glib_module()}),
    ):
        bridge.call_async(
            "daemon.state_full",
            None,
            on_success=lambda _: False,
            on_failure=on_failure,
        )
        if bridge._EXECUTOR:
            bridge._EXECUTOR.shutdown(wait=True)

    assert len(erros) == 1
    assert isinstance(erros[0], FileNotFoundError)


def test_call_async_timeout_honrado():
    """Worker com timeout curto retorna rapidamente via on_failure."""
    import hefesto.app.ipc_bridge as bridge
    from hefesto.cli.ipc_client import IpcError

    falhas: list = []

    def on_failure(exc: Exception) -> bool:
        falhas.append(exc)
        return False

    with (
        patch(
            "hefesto.app.ipc_bridge._run_call",
            side_effect=IpcError(-1, "conexão timeout"),
        ),
        patch.dict("sys.modules", {"gi.repository": _make_fake_glib_module()}),
    ):
        inicio = time.monotonic()
        bridge.call_async(
            "daemon.state_full",
            None,
            on_success=lambda _: False,
            on_failure=on_failure,
            timeout_s=0.05,
        )
        if bridge._EXECUTOR:
            bridge._EXECUTOR.shutdown(wait=True)
        duracao = time.monotonic() - inicio

    assert falhas, "on_failure deveria ter sido chamado"
    assert duracao < 1.0, f"Levou {duracao:.2f}s — timeout não honrado"

# "A obstinação pelo detalhe é o que separa o artesão do improvisador." — Sêneca (adaptado)
