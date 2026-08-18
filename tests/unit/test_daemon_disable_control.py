"""Desligar/desativar o daemon sem desinstalar (FEAT-DAEMON-DISABLE-CONTROL-01).

`disable()` para o daemon e desabilita o auto-start mantendo a unit instalada
(distinto de pause em runtime e de uninstall). `enable()` faz o inverso.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import hefesto_dualsense4unix.daemon.service_install as si


def test_enable_enables_autostart_and_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    inst = si.ServiceInstaller()
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(inst, "_systemctl", lambda *a, **_k: calls.append(a) or None)
    inst.enable()
    assert ("enable", si.SERVICE_NORMAL) in calls
    assert ("start", si.SERVICE_NORMAL) in calls


def test_disable_stops_and_disables_keeping_unit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    inst = si.ServiceInstaller()
    # Simula unit instalada para o _disable_if_installed disparar o disable.
    (tmp_path / si.SERVICE_NORMAL).write_text("[Unit]\n", encoding="utf-8")
    monkeypatch.setattr(si, "user_unit_dir", lambda: tmp_path)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(inst, "_systemctl", lambda *a, **_k: calls.append(a) or None)
    inst.disable()
    assert ("disable", si.SERVICE_NORMAL) in calls
    assert ("stop", si.SERVICE_NORMAL) in calls
    # A unit NÃO foi removida (disable != uninstall).
    assert (tmp_path / si.SERVICE_NORMAL).exists()
