"""Subcomando `doctor` no CLI (FEAT-DOCTOR-CLI-AND-CHECKS-01)."""
from __future__ import annotations

import asyncio

import pytest

from hefesto_dualsense4unix.cli import cmd_doctor


def test_find_doctor_sh_locates_repo_script() -> None:
    """No layout editable, acha scripts/doctor.sh na raiz do repo."""
    path = cmd_doctor._find_doctor_sh()
    assert path is not None
    assert path.name == "doctor.sh"
    assert path.is_file()


def test_daemon_checks_offline_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem daemon (IPC offline), retorna um WARN em vez de explodir."""

    def _boom(*_a: object, **_k: object) -> object:
        raise FileNotFoundError("socket ausente")

    monkeypatch.setattr(cmd_doctor.IpcClient, "connect", _boom)
    rows = asyncio.run(cmd_doctor._daemon_checks())
    assert rows, "esperava ao menos uma linha de check"
    assert any("offline" in msg for _tag, msg in rows)
