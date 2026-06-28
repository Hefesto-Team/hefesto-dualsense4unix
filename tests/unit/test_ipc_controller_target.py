"""IPC do seletor de controle (FEAT-DSX-CONTROLLER-SELECTOR-01).

Cobre `controller.target.set` (índice válido, null/broadcast, fora de faixa,
tipos inválidos, backend sem suporte) e a exposição de `output_target_index`
no `daemon.state_full`.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.state_store import StateStore


def _controllers(n: int) -> list[dict[str, Any]]:
    return [
        {"index": i, "connected": True, "transport": "usb", "is_primary": i == 0}
        for i in range(n)
    ]


class _FakeController:
    """Backend com suporte a alvo de output, imitando o real."""

    def __init__(self, target: int | None = None, count: int = 2) -> None:
        self._target = target
        self._controllers = _controllers(count)
        self.set_calls: list[int | None] = []

    def is_connected(self) -> bool:
        return False

    def describe_controllers(self) -> list[dict[str, Any]]:
        return list(self._controllers)

    def get_output_target_index(self) -> int | None:
        return self._target

    def set_output_target(self, index: int | None) -> int | None:
        self.set_calls.append(index)
        if index is None or not (0 <= index < len(self._controllers)):
            self._target = None
        else:
            self._target = index
        return self._target


class _BareController:
    """Backend legado/fake sem suporte a alvo (single-instance)."""

    def is_connected(self) -> bool:
        return False


class _Handlers(IpcHandlersMixin):
    def __init__(self, controller: object, daemon: object = None) -> None:
        self.controller = controller  # type: ignore[assignment]
        self.store = StateStore()
        self.daemon = daemon  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_target_set_define_indice() -> None:
    c = _FakeController(count=2)
    res = await _Handlers(c)._handle_controller_target_set({"index": 1})
    assert res == {"status": "ok", "target_index": 1}
    assert c.set_calls == [1]


@pytest.mark.asyncio
async def test_target_set_none_broadcast() -> None:
    c = _FakeController(target=1, count=2)
    res = await _Handlers(c)._handle_controller_target_set({"index": None})
    assert res == {"status": "ok", "target_index": None}
    assert c.set_calls == [None]


@pytest.mark.asyncio
async def test_target_set_index_ausente_e_broadcast() -> None:
    c = _FakeController(target=1, count=2)
    res = await _Handlers(c)._handle_controller_target_set({})
    assert res == {"status": "ok", "target_index": None}


@pytest.mark.asyncio
async def test_target_set_fora_de_faixa_vira_none() -> None:
    c = _FakeController(count=1)
    res = await _Handlers(c)._handle_controller_target_set({"index": 9})
    assert res["target_index"] is None


@pytest.mark.asyncio
async def test_target_set_bool_invalido() -> None:
    with pytest.raises(ValueError, match="index"):
        await _Handlers(_FakeController())._handle_controller_target_set({"index": True})


@pytest.mark.asyncio
async def test_target_set_string_invalido() -> None:
    with pytest.raises(ValueError, match="index"):
        await _Handlers(_FakeController())._handle_controller_target_set({"index": "1"})


@pytest.mark.asyncio
async def test_target_set_backend_sem_metodo_e_tolerado() -> None:
    res = await _Handlers(_BareController())._handle_controller_target_set({"index": 1})
    assert res == {"status": "ok", "target_index": None}


@pytest.mark.asyncio
async def test_state_full_expoe_output_target_index() -> None:
    c = _FakeController(target=1, count=2)
    res = await _Handlers(c)._handle_daemon_state_full({})
    assert res["output_target_index"] == 1
    assert "controllers" in res


@pytest.mark.asyncio
async def test_state_full_target_none_quando_todos() -> None:
    c = _FakeController(target=None, count=2)
    res = await _Handlers(c)._handle_daemon_state_full({})
    assert res["output_target_index"] is None


@pytest.mark.asyncio
async def test_state_full_target_none_backend_sem_metodo() -> None:
    res = await _Handlers(_BareController())._handle_daemon_state_full({})
    assert res["output_target_index"] is None
