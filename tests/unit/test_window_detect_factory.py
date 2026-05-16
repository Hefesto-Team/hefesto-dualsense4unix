"""Testes da factory `detect_window_backend` em `window_detect`.

Cobre os 4 cenários de seleção de backend conforme variáveis de ambiente:
  1. X11 puro (DISPLAY sem WAYLAND_DISPLAY) → XlibBackend.
  2. Wayland puro (WAYLAND_DISPLAY sem DISPLAY) → _WaylandCascadeBackend
     (BUG-COSMIC-WLR-BACKEND-REGRESSION-01, v3.1.0).
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
    """WAYLAND_DISPLAY presente, sem DISPLAY → _WaylandCascadeBackend
    (cascade portal XDG → wlrctl → None). A partir de v3.1.0
    (BUG-COSMIC-WLR-BACKEND-REGRESSION-01)."""

    def test_retorna_wayland_cascade_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        backend = detect_window_backend()
        assert type(backend).__name__ == "_WaylandCascadeBackend"

    def test_cascade_compoe_portal_e_wlrctl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        backend = detect_window_backend()
        assert type(backend._portal).__name__ == "WaylandPortalBackend"  # type: ignore[attr-defined]
        assert type(backend._wlrctl).__name__ == "WlrctlBackend"  # type: ignore[attr-defined]

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

    def test_cascade_usa_portal_se_respondeu(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Portal retorna WindowInfo → cascade devolve sem consultar wlrctl."""
        from unittest.mock import MagicMock

        from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo

        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        backend = detect_window_backend()

        portal_info = WindowInfo(wm_class="from_portal", app_id="from_portal")
        backend._portal.get_active_window_info = MagicMock(return_value=portal_info)  # type: ignore[attr-defined]
        wlrctl_spy = MagicMock()
        backend._wlrctl.get_active_window_info = wlrctl_spy  # type: ignore[attr-defined]

        info = backend.get_active_window_info()
        assert info is portal_info
        wlrctl_spy.assert_not_called()

    def test_cascade_cai_para_wlrctl_se_portal_falha(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Portal retorna None → cascade tenta wlrctl."""
        from unittest.mock import MagicMock

        from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo

        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        backend = detect_window_backend()

        wlr_info = WindowInfo(wm_class="from_wlrctl", app_id="from_wlrctl")
        backend._portal.get_active_window_info = MagicMock(return_value=None)  # type: ignore[attr-defined]
        backend._wlrctl.get_active_window_info = MagicMock(return_value=wlr_info)  # type: ignore[attr-defined]

        info = backend.get_active_window_info()
        assert info is wlr_info

    def test_cascade_retorna_none_se_ambos_falham(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ambos portal e wlrctl retornam None → cascade retorna None."""
        from unittest.mock import MagicMock

        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        backend = detect_window_backend()

        backend._portal.get_active_window_info = MagicMock(return_value=None)  # type: ignore[attr-defined]
        backend._wlrctl.get_active_window_info = MagicMock(return_value=None)  # type: ignore[attr-defined]

        info = backend.get_active_window_info()
        assert info is None


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
