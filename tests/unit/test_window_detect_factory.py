"""Testes da factory `detect_window_backend` em `window_detect`.

Cobre os 4 cenários de seleção de backend conforme variáveis de ambiente:
  1. X11 puro (DISPLAY sem WAYLAND_DISPLAY) → XlibBackend.
  2. Wayland puro (WAYLAND_DISPLAY sem DISPLAY) → WaylandPortalBackend.
  3. XWayland (ambas presentes) → XlibBackend (preferido).
  4. Nenhum display → NullBackend.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations.window_backends.null import NullBackend
from hefesto_dualsense4unix.integrations.window_backends.xlib import XlibBackend
from hefesto_dualsense4unix.integrations.window_detect import (
    detect_window_backend,
    get_active_window_info,
)


class TestDetectWindowBackendX11:
    """DISPLAY presente, sem WAYLAND_DISPLAY → XlibBackend."""

    def test_retorna_xlib_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        backend = detect_window_backend()
        assert isinstance(backend, XlibBackend)

    def test_tipo_correto(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISPLAY", ":99")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        backend = detect_window_backend()
        assert type(backend).__name__ == "XlibBackend"


class TestDetectWindowBackendWayland:
    """WAYLAND_DISPLAY presente, sem DISPLAY → WaylandPortalBackend."""

    def test_retorna_wayland_portal_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        backend = detect_window_backend()
        assert type(backend).__name__ == "WaylandPortalBackend"

    def test_nao_e_xlib(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
        backend = detect_window_backend()
        assert not isinstance(backend, XlibBackend)

    def test_nao_e_null(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        backend = detect_window_backend()
        assert not isinstance(backend, NullBackend)


class TestDetectWindowBackendXWayland:
    """Ambas variáveis presentes (XWayland) → XlibBackend (preferido)."""

    def test_retorna_xlib_em_xwayland(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        backend = detect_window_backend()
        assert isinstance(backend, XlibBackend)

    def test_nao_usa_wayland_portal_em_xwayland(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISPLAY", ":1")
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        backend = detect_window_backend()
        assert type(backend).__name__ != "WaylandPortalBackend"


class TestDetectWindowBackendNenhum:
    """Sem DISPLAY e sem WAYLAND_DISPLAY → NullBackend."""

    def test_retorna_null_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        backend = detect_window_backend()
        assert isinstance(backend, NullBackend)

    def test_null_retorna_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        backend = detect_window_backend()
        assert backend.get_active_window_info() is None

    def test_get_active_window_info_legado_sem_display(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """API legada retorna dict com wm_class=unknown quando sem display."""
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        info = get_active_window_info()
        assert isinstance(info, dict)
        assert info["wm_class"] == "unknown"
        assert "wm_name" in info
        assert "pid" in info
        assert "exe_basename" in info


class TestNullBackendDireto:
    """NullBackend isolado."""

    def test_get_active_window_info_retorna_none(self) -> None:
        backend = NullBackend()
        assert backend.get_active_window_info() is None


class TestWindowInfoAsDict:
    """WindowInfo.as_dict() mantém compatibilidade com API legada."""

    def test_as_dict_campos_completos(self) -> None:
        from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo

        info = WindowInfo(
            wm_class="Firefox",
            pid=1234,
            app_id="firefox",
            title="Mozilla Firefox",
            exe_basename="firefox-bin",
        )
        d = info.as_dict()
        assert d["wm_class"] == "Firefox"
        assert d["wm_name"] == "Mozilla Firefox"
        assert d["pid"] == 1234
        assert d["exe_basename"] == "firefox-bin"

    def test_as_dict_defaults(self) -> None:
        from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo

        info = WindowInfo()
        d = info.as_dict()
        assert d["wm_class"] == "unknown"
        assert d["pid"] == 0
