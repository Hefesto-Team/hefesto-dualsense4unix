"""Testes do AUTOSWITCH-FLOOD-FIX-01.

Cobre:
  - build_window_reader() instancia o backend UMA vez (não por tick) e converte
    WindowInfo -> dict legado (ou _UNKNOWN_WINDOW quando None).
  - detect_window_backend() loga 'autoswitch_compositor_unsupported' uma única
    vez (once-guard), rebaixando repetições para debug.
  - _ensure_display_env() importa WAYLAND_DISPLAY/DISPLAY de
    `systemctl --user show-environment` quando ambos faltam no os.environ.
"""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.integrations import window_detect
from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo


class _FakeBackend:
    def __init__(self, info: WindowInfo | None) -> None:
        self._info = info
        self.calls = 0

    def get_active_window_info(self) -> WindowInfo | None:
        self.calls += 1
        return self._info


def test_build_window_reader_instancia_backend_uma_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O backend é detectado 1x em build_window_reader, não a cada leitura."""
    detect_calls = 0
    backend = _FakeBackend(WindowInfo(wm_class="Firefox", title="Moz"))

    def _fake_detect() -> Any:
        nonlocal detect_calls
        detect_calls += 1
        return backend

    monkeypatch.setattr(window_detect, "detect_window_backend", _fake_detect)
    reader = window_detect.build_window_reader()

    for _ in range(10):
        info = reader()

    assert detect_calls == 1, "detect_window_backend deveria ser chamado 1x, não por tick"
    assert backend.calls == 10, "cada leitura deve consultar o backend cacheado"
    assert info["wm_class"] == "Firefox"
    assert info["wm_name"] == "Moz"


def test_build_window_reader_dict_unknown_quando_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backend sem janela (None) -> dict legado com wm_class=unknown."""
    monkeypatch.setattr(
        window_detect, "detect_window_backend", lambda: _FakeBackend(None)
    )
    reader = window_detect.build_window_reader()
    info = reader()
    assert info["wm_class"] == "unknown"
    assert info["pid"] == 0
    assert "wm_name" in info and "exe_basename" in info


def test_once_guard_warning_so_uma_vez(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem display, o warning de compositor não-suportado loga 1x e depois debug."""
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(window_detect, "_unsupported_warned", False)
    fake_logger = MagicMock()
    monkeypatch.setattr(window_detect, "logger", fake_logger)

    for _ in range(5):
        window_detect.detect_window_backend()

    warn_calls = [
        c
        for c in fake_logger.warning.call_args_list
        if c.args and c.args[0] == "autoswitch_compositor_unsupported"
    ]
    debug_calls = [
        c
        for c in fake_logger.debug.call_args_list
        if c.args and c.args[0] == "autoswitch_compositor_unsupported"
    ]
    assert len(warn_calls) == 1, "warning deve disparar exatamente uma vez (once-guard)"
    assert len(debug_calls) == 4, "repetições devem cair para debug"


def test_ensure_display_env_importa_do_systemd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_ensure_display_env injeta WAYLAND_DISPLAY/DISPLAY do show-environment."""
    from hefesto_dualsense4unix.daemon.subsystems import autoswitch

    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/systemctl")

    def _fake_run(*_args: Any, **_kwargs: Any) -> Any:
        out = "WAYLAND_DISPLAY=wayland-9\nDISPLAY=:7\nLANG=pt_BR.UTF-8\n"
        return MagicMock(stdout=out)

    monkeypatch.setattr("subprocess.run", _fake_run)

    autoswitch._ensure_display_env()

    assert os.environ.get("WAYLAND_DISPLAY") == "wayland-9"
    assert os.environ.get("DISPLAY") == ":7"


def test_ensure_display_env_noop_quando_ja_presente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Se já há display no env, não chama systemctl (sem subprocess)."""
    from hefesto_dualsense4unix.daemon.subsystems import autoswitch

    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    called = MagicMock()
    monkeypatch.setattr("subprocess.run", called)
    autoswitch._ensure_display_env()
    called.assert_not_called()
