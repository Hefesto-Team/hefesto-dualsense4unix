"""Handler IPC do gamepad virtual (FEAT-DSX-GAMEPAD-FLAVOR-01)."""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin


class _FakeConfig:
    gamepad_flavor = "dualsense"


class _FakeDaemon:
    def __init__(self) -> None:
        self.calls: list[tuple[bool, str | None]] = []
        self.config = _FakeConfig()

    def set_gamepad_emulation(self, enabled: bool, flavor: str | None = None) -> bool:
        self.calls.append((enabled, flavor))
        if flavor:
            self.config.gamepad_flavor = flavor
        return True


class _Handlers(IpcHandlersMixin):
    def __init__(self, daemon: object) -> None:
        self.daemon = daemon


@pytest.mark.asyncio
async def test_liga_dualsense() -> None:
    d = _FakeDaemon()
    res = await _Handlers(d)._handle_gamepad_emulation_set(
        {"enabled": True, "flavor": "dualsense"}
    )
    assert res == {"status": "ok", "enabled": True, "flavor": "dualsense"}
    assert d.calls == [(True, "dualsense")]


@pytest.mark.asyncio
async def test_liga_xbox() -> None:
    d = _FakeDaemon()
    res = await _Handlers(d)._handle_gamepad_emulation_set(
        {"enabled": True, "flavor": "xbox"}
    )
    assert res["enabled"] is True
    assert res["flavor"] == "xbox"


@pytest.mark.asyncio
async def test_desliga() -> None:
    d = _FakeDaemon()
    res = await _Handlers(d)._handle_gamepad_emulation_set({"enabled": False})
    assert res["enabled"] is False
    assert d.calls == [(False, None)]


@pytest.mark.asyncio
async def test_enabled_obrigatorio_bool() -> None:
    with pytest.raises(ValueError, match="enabled"):
        await _Handlers(_FakeDaemon())._handle_gamepad_emulation_set({"enabled": "sim"})


@pytest.mark.asyncio
async def test_flavor_precisa_ser_string() -> None:
    with pytest.raises(ValueError, match="flavor"):
        await _Handlers(_FakeDaemon())._handle_gamepad_emulation_set(
            {"enabled": True, "flavor": 7}
        )


@pytest.mark.asyncio
async def test_sem_daemon_erro() -> None:
    with pytest.raises(ValueError, match="daemon"):
        await _Handlers(None)._handle_gamepad_emulation_set({"enabled": True})
