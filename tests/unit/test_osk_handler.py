"""Testes do `_OSKController` — abrir/fechar onboard/wvkbd-mobintl."""
from __future__ import annotations

from typing import Any

import pytest

from hefesto.core.keyboard_mappings import TOKEN_CLOSE_OSK, TOKEN_OPEN_OSK
from hefesto.daemon.subsystems.keyboard import _OSKController


class _FakeProc:
    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid
        self._alive = True
        self.terminated = False

    def poll(self) -> int | None:
        return None if self._alive else 0

    def terminate(self) -> None:
        self._alive = False
        self.terminated = True


def test_sem_binario_nao_duplica_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """3 chamadas a open() sem binário não criam Popen e marcam flag 1x."""
    monkeypatch.setattr(
        "hefesto.daemon.subsystems.keyboard.shutil.which", lambda _name: None
    )
    spawned: list[Any] = []
    monkeypatch.setattr(
        "hefesto.daemon.subsystems.keyboard.subprocess.Popen",
        lambda *a, **k: spawned.append(("Popen", a, k)),
    )
    ctrl = _OSKController()
    ctrl.open()
    ctrl.open()
    ctrl.open()
    assert spawned == []
    assert ctrl._missing_warned is True


def test_onboard_spawn_e_fechamento(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hefesto.daemon.subsystems.keyboard.shutil.which",
        lambda name: f"/usr/bin/{name}" if name == "onboard" else None,
    )
    spawned: list[list[str]] = []
    fake_proc = _FakeProc()

    def _popen(argv: list[str], **_: Any) -> _FakeProc:
        spawned.append(argv)
        return fake_proc

    monkeypatch.setattr(
        "hefesto.daemon.subsystems.keyboard.subprocess.Popen", _popen
    )

    ctrl = _OSKController()
    ctrl.open()
    assert spawned == [["onboard"]]
    # Segunda chamada open() é no-op (processo já vivo).
    ctrl.open()
    assert len(spawned) == 1

    ctrl.close()
    assert fake_proc.terminated is True
    # close() com processo morto é no-op seguro.
    ctrl.close()


def test_wvkbd_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Se `onboard` ausente mas `wvkbd-mobintl` presente, usa o fallback."""

    def _which(name: str) -> str | None:
        return "/usr/bin/wvkbd-mobintl" if name == "wvkbd-mobintl" else None

    monkeypatch.setattr(
        "hefesto.daemon.subsystems.keyboard.shutil.which", _which
    )
    spawned: list[list[str]] = []

    def _popen(argv: list[str], **_: Any) -> _FakeProc:
        spawned.append(argv)
        return _FakeProc()

    monkeypatch.setattr(
        "hefesto.daemon.subsystems.keyboard.subprocess.Popen", _popen
    )
    ctrl = _OSKController()
    ctrl.open()
    assert spawned == [["wvkbd-mobintl"]]


def test_dispatch_token_open_close(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hefesto.daemon.subsystems.keyboard.shutil.which",
        lambda name: f"/usr/bin/{name}" if name == "onboard" else None,
    )
    popens: list[list[str]] = []
    fake_proc = _FakeProc()
    monkeypatch.setattr(
        "hefesto.daemon.subsystems.keyboard.subprocess.Popen",
        lambda argv, **_: (popens.append(argv) or fake_proc),  # type: ignore[func-returns-value]
    )
    ctrl = _OSKController()
    ctrl.dispatch_token(TOKEN_OPEN_OSK, "press")
    assert popens == [["onboard"]]
    ctrl.dispatch_token(TOKEN_CLOSE_OSK, "press")
    assert fake_proc.terminated is True


def test_dispatch_token_release_e_noop() -> None:
    """Release não deve abrir/fechar — evita fechar logo após open em L3."""
    ctrl = _OSKController()
    # Sem mockar Popen: se release fosse abrir, subprocess real rodaria.
    ctrl.dispatch_token(TOKEN_OPEN_OSK, "release")
    ctrl.dispatch_token(TOKEN_CLOSE_OSK, "release")
    assert ctrl._process is None
