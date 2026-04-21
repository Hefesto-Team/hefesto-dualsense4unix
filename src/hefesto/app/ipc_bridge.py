"""Cliente IPC síncrono para a GUI GTK.

A GUI roda em loop GTK síncrono; asyncio vive embutido em chamadas curtas
por `asyncio.run()`. Para operações muito rápidas (get_status, set_rumble)
isso é aceitável. Poll contínuo usa `GLib.timeout_add` + asyncio.run por
tick.
"""
from __future__ import annotations

import asyncio
from typing import Any

from hefesto.cli.ipc_client import IpcClient, IpcError


def _run_call(method: str, params: dict[str, Any] | None = None) -> Any:
    async def _do() -> Any:
        async with IpcClient.connect() as client:
            return await client.call(method, params or {})

    return asyncio.run(_do())


def daemon_state_full() -> dict[str, Any] | None:
    """Retorna estado completo via IPC; None se daemon offline."""
    try:
        result = _run_call("daemon.state_full")
        if isinstance(result, dict):
            return result
        return None
    except (FileNotFoundError, ConnectionError, IpcError, OSError):
        return None


def daemon_status_basic() -> dict[str, Any] | None:
    try:
        result = _run_call("daemon.status")
        if isinstance(result, dict):
            return result
        return None
    except (FileNotFoundError, ConnectionError, IpcError, OSError):
        return None


def profile_list() -> list[dict[str, Any]]:
    """Lista perfis. Preferência: daemon (traz 'active'); fallback: disco."""
    try:
        result = _run_call("profile.list")
        if isinstance(result, dict):
            profiles = list(result.get("profiles", []))
            if profiles:
                return profiles
    except (FileNotFoundError, ConnectionError, IpcError, OSError):
        pass

    try:
        from hefesto.profiles.loader import load_all_profiles

        return [
            {
                "name": p.name,
                "priority": p.priority,
                "match_type": p.match.type,
                "active": False,
            }
            for p in load_all_profiles()
        ]
    except Exception:
        return []


def profile_switch(name: str) -> bool:
    try:
        _run_call("profile.switch", {"name": name})
        return True
    except Exception:
        return False


def trigger_set(side: str, mode: str, params: list[int]) -> bool:
    try:
        _run_call("trigger.set", {"side": side, "mode": mode, "params": params})
        return True
    except Exception:
        return False


def led_set(rgb: tuple[int, int, int]) -> bool:
    try:
        _run_call("led.set", {"rgb": list(rgb)})
        return True
    except Exception:
        return False


def rumble_set(weak: int, strong: int) -> bool:
    try:
        _run_call("rumble.set", {"weak": weak, "strong": strong})
        return True
    except Exception:
        return False


__all__ = [
    "daemon_state_full",
    "daemon_status_basic",
    "led_set",
    "profile_list",
    "profile_switch",
    "rumble_set",
    "trigger_set",
]
