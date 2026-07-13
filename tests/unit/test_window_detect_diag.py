"""Testes do FEAT-WINDOW-DETECT-DIAG-01 (diagnóstico do detector de janela).

Cobre:
  - `build_window_reader()` retorna `WindowReaderDiag` com `backend_name`
    correto por cenário de ambiente (X11, XWayland, Wayland puro, headless),
    mantendo retrocompatibilidade com a API legada (callable de dict).
  - `backend_name` dinâmico da cascata Wayland: migra portal -> wlrctl ->
    null conforme os backends desistem/ficam indisponíveis.
  - Metadados por leitura: `last_read_useful`, `useful_reads`,
    `last_useful_class` ("unknown" e vazio NÃO contam como útil).
  - `StateStore`: `set_window_detect_backend` / `record_window_detect_read`
    e as properties `window_detect_backend` / `window_detect_healthy` /
    `window_detect_last_class` (unknown não derruba healthy).
  - Subsystem autoswitch: `_build_diag_window_reader` semeia o store e grava
    backend/healthy/last_class a cada leitura com reader fake.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.autoswitch import _build_diag_window_reader
from hefesto_dualsense4unix.integrations import window_detect
from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo
from hefesto_dualsense4unix.integrations.window_detect import (
    WindowReaderDiag,
    build_window_reader,
)


class _FakeBackend:
    """Backend fake com nome declarado e resposta fixa."""

    def __init__(self, info: WindowInfo | None, name: str = "fake") -> None:
        self._info = info
        self.backend_name = name
        self.calls = 0

    def get_active_window_info(self) -> WindowInfo | None:
        self.calls += 1
        return self._info


class _AnonBackend:
    """Backend fake SEM atributo backend_name (cai no nome da classe)."""

    def get_active_window_info(self) -> WindowInfo | None:
        return None


class TestBackendNamePorCenarioDeEnv:
    """`build_window_reader().backend_name` por cenário de ambiente."""

    def test_x11_puro_reporta_xlib(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        reader = build_window_reader()
        assert isinstance(reader, WindowReaderDiag)
        assert reader.backend_name == "xlib"

    def test_xwayland_reporta_xlib(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISPLAY", ":1")
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        assert build_window_reader().backend_name == "xlib"

    def test_wayland_puro_comeca_em_portal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem leitura ainda, a cascata reporta o primeiro da fila (portal)."""
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        assert build_window_reader().backend_name == "portal"

    def test_headless_reporta_null(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert build_window_reader().backend_name == "null"

    def test_backend_sem_nome_cai_no_nome_da_classe(self) -> None:
        reader = WindowReaderDiag(_AnonBackend())
        assert reader.backend_name == "_anonbackend"


class TestCascataBackendNameDinamico:
    """A cascata Wayland migra portal -> wlrctl -> null conforme desistem."""

    def _make_cascade(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        return window_detect.detect_window_backend()

    def test_leitura_util_do_wlrctl_muda_o_nome(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        cascade = self._make_cascade(monkeypatch)
        cascade._portal.get_active_window_info = MagicMock(return_value=None)
        cascade._wlrctl.get_active_window_info = MagicMock(
            return_value=WindowInfo(wm_class="steam", app_id="steam")
        )
        cascade._wlrctl._available = True

        assert cascade.backend_name == "portal"
        info = cascade.get_active_window_info()
        assert info is not None
        assert cascade.backend_name == "wlrctl"

    def test_portal_desiste_e_wlrctl_disponivel_reporta_wlrctl(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cascade = self._make_cascade(monkeypatch)
        # Simula o portal após o threshold de falhas consecutivas.
        cascade._portal._consecutive_failures = (
            cascade._portal._UNSUPPORTED_THRESHOLD
        )
        cascade._wlrctl._available = True
        assert cascade.backend_name == "wlrctl"

    def test_ambos_indisponiveis_reporta_null(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cascade = self._make_cascade(monkeypatch)
        cascade._portal._consecutive_failures = (
            cascade._portal._UNSUPPORTED_THRESHOLD
        )
        cascade._wlrctl._available = False
        assert cascade.backend_name == "null"

    def test_wlrctl_que_funcionava_e_sumiu_degrada_o_nome(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Última fonte útil era wlrctl, mas ele ficou indisponível -> null."""
        cascade = self._make_cascade(monkeypatch)
        cascade._last_source = "wlrctl"
        cascade._portal._consecutive_failures = (
            cascade._portal._UNSUPPORTED_THRESHOLD
        )
        cascade._wlrctl._available = False
        assert cascade.backend_name == "null"


class TestLeituraUtil:
    """Metadados por leitura do WindowReaderDiag."""

    def test_leitura_util_atualiza_metadados(self) -> None:
        backend = _FakeBackend(WindowInfo(wm_class="Sackboy", title="Sackboy"))
        reader = WindowReaderDiag(backend)

        info = reader()

        assert info["wm_class"] == "Sackboy"
        assert reader.last_read_useful is True
        assert reader.useful_reads == 1
        assert reader.last_useful_class == "Sackboy"

    def test_none_do_backend_vira_unknown_nao_util(self) -> None:
        reader = WindowReaderDiag(_FakeBackend(None))

        info = reader()

        assert info["wm_class"] == "unknown"
        assert reader.last_read_useful is False
        assert reader.useful_reads == 0
        assert reader.last_useful_class is None

    def test_unknown_explicito_nao_conta_como_util(self) -> None:
        reader = WindowReaderDiag(_FakeBackend(WindowInfo(wm_class="unknown")))
        reader()
        assert reader.last_read_useful is False
        assert reader.last_useful_class is None

    def test_unknown_depois_de_util_preserva_last_useful_class(self) -> None:
        """Alt-tab para o desktop vazio não apaga a última classe útil."""
        backend = _FakeBackend(WindowInfo(wm_class="Celeste"))
        reader = WindowReaderDiag(backend)
        reader()
        backend._info = None
        reader()

        assert reader.last_read_useful is False
        assert reader.useful_reads == 1
        assert reader.last_useful_class == "Celeste"


class TestStoreWindowDetect:
    """Escritas e properties do StateStore (FEAT-WINDOW-DETECT-DIAG-01)."""

    def test_estado_inicial(self) -> None:
        store = StateStore()
        assert store.window_detect_backend is None
        assert store.window_detect_healthy is False
        assert store.window_detect_last_class is None

    def test_seed_xlib_nasce_saudavel(self) -> None:
        store = StateStore()
        store.set_window_detect_backend("xlib", healthy=True)
        assert store.window_detect_backend == "xlib"
        assert store.window_detect_healthy is True
        assert store.window_detect_last_class is None

    def test_leitura_util_liga_healthy_e_grava_classe(self) -> None:
        store = StateStore()
        store.set_window_detect_backend("wlrctl", healthy=False)
        store.record_window_detect_read("wlrctl", "steam")
        assert store.window_detect_healthy is True
        assert store.window_detect_last_class == "steam"

    def test_unknown_nao_derruba_healthy_nem_apaga_classe(self) -> None:
        """Desktop vazio (unknown) não regride o diagnóstico."""
        store = StateStore()
        store.set_window_detect_backend("xlib", healthy=True)
        store.record_window_detect_read("xlib", "Sackboy")
        store.record_window_detect_read("xlib", "unknown")
        assert store.window_detect_healthy is True
        assert store.window_detect_last_class == "Sackboy"

    def test_wm_class_vazia_ou_none_nao_conta(self) -> None:
        store = StateStore()
        store.set_window_detect_backend("portal", healthy=False)
        store.record_window_detect_read("portal", "")
        store.record_window_detect_read("portal", None)
        assert store.window_detect_healthy is False
        assert store.window_detect_last_class is None

    def test_backend_e_regravado_a_cada_leitura(self) -> None:
        """A cascata pode migrar em runtime — o store acompanha."""
        store = StateStore()
        store.set_window_detect_backend("portal", healthy=False)
        store.record_window_detect_read("wlrctl", "unknown")
        assert store.window_detect_backend == "wlrctl"

    def test_novo_seed_zera_last_class(self) -> None:
        store = StateStore()
        store.record_window_detect_read("xlib", "Celeste")
        store.set_window_detect_backend("xlib", healthy=True)
        assert store.window_detect_last_class is None


class TestSubsystemDiagReader:
    """`_build_diag_window_reader` semeia e grava no store (reader fake)."""

    class _FakeDiagReader:
        """Duble do WindowReaderDiag retornado por build_window_reader."""

        def __init__(self, backend_name: str, readings: list[dict[str, Any]]) -> None:
            self.backend_name = backend_name
            self._readings = readings
            self._i = 0

        def __call__(self) -> dict[str, Any]:
            reading = self._readings[min(self._i, len(self._readings) - 1)]
            self._i += 1
            return reading

    def _patch_builder(
        self, monkeypatch: pytest.MonkeyPatch, fake: _FakeDiagReader
    ) -> None:
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.window_detect.build_window_reader",
            lambda: fake,
        )

    def test_seed_xlib_presume_saudavel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = StateStore()
        fake = self._FakeDiagReader("xlib", [{"wm_class": "unknown"}])
        self._patch_builder(monkeypatch, fake)

        _build_diag_window_reader(store)

        assert store.window_detect_backend == "xlib"
        assert store.window_detect_healthy is True
        assert store.window_detect_last_class is None

    def test_seed_null_nasce_nao_saudavel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = StateStore()
        fake = self._FakeDiagReader("null", [{"wm_class": "unknown"}])
        self._patch_builder(monkeypatch, fake)

        _build_diag_window_reader(store)

        assert store.window_detect_backend == "null"
        assert store.window_detect_healthy is False

    def test_leitura_util_grava_no_store_e_propaga_dict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = StateStore()
        fake = self._FakeDiagReader(
            "wlrctl", [{"wm_class": "steam", "wm_name": "Steam"}]
        )
        self._patch_builder(monkeypatch, fake)

        reader = _build_diag_window_reader(store)
        info = reader()

        assert info["wm_class"] == "steam"  # API legada preservada
        assert store.window_detect_backend == "wlrctl"
        assert store.window_detect_healthy is True
        assert store.window_detect_last_class == "steam"

    def test_unknown_persistente_nao_liga_healthy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = StateStore()
        fake = self._FakeDiagReader("portal", [{"wm_class": "unknown"}])
        self._patch_builder(monkeypatch, fake)

        reader = _build_diag_window_reader(store)
        for _ in range(5):
            reader()

        assert store.window_detect_healthy is False
        assert store.window_detect_last_class is None

    def test_wm_class_nao_string_vira_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Leitura defensiva: wm_class não-str não explode nem conta útil."""
        store = StateStore()
        fake = self._FakeDiagReader("xlib", [{"wm_class": 123}])
        self._patch_builder(monkeypatch, fake)

        reader = _build_diag_window_reader(store)
        reader()

        assert store.window_detect_last_class is None
