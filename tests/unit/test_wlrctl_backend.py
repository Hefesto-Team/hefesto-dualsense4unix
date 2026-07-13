"""Testes do `WlrctlBackend` (BUG-COSMIC-WLR-BACKEND-REGRESSION-01).

Cobre:
  - Detecção de binário ausente (shutil.which → None).
  - Parsing de JSON do `wlrctl toplevel list --json --state activated`.
  - Tratamento de erros: timeout, returncode != 0, JSON inválido.
  - Compatibilidade com formato `app_id` vs. `appId`.
  - Fallback gracioso para None.
"""
from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo
from hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel import (
    WlrctlBackend,
)


class TestWlrctlBackendInit:
    """Detecção de presença do binário `wlrctl` no init."""

    def test_bin_ausente_marca_unavailable(self) -> None:
        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.shutil.which",
            return_value=None,
        ):
            backend = WlrctlBackend()
        assert backend._available is False

    def test_bin_presente_marca_available(self) -> None:
        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.shutil.which",
            return_value="/usr/bin/wlrctl",
        ):
            backend = WlrctlBackend()
        assert backend._available is True

    def test_bin_ausente_get_info_retorna_none_sem_chamar_subprocess(self) -> None:
        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.shutil.which",
            return_value=None,
        ):
            backend = WlrctlBackend()

        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run"
        ) as mock_run:
            info = backend.get_active_window_info()
        assert info is None
        mock_run.assert_not_called()


def _make_backend_available() -> WlrctlBackend:
    """Cria backend com `_available=True` independente do PATH real."""
    with patch(
        "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.shutil.which",
        return_value="/usr/bin/wlrctl",
    ):
        return WlrctlBackend()


class TestWlrctlBackendParsing:
    """Parsing do JSON de `wlrctl toplevel list --json --state activated`."""

    def test_caminho_feliz_retorna_window_info(self) -> None:
        backend = _make_backend_available()

        fake_result = MagicMock(spec=subprocess.CompletedProcess)
        fake_result.returncode = 0
        fake_result.stdout = json.dumps(
            [{"app_id": "firefox", "title": "Mozilla Firefox"}]
        )
        fake_result.stderr = ""

        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            return_value=fake_result,
        ):
            info = backend.get_active_window_info()

        assert isinstance(info, WindowInfo)
        assert info.wm_class == "firefox"
        assert info.app_id == "firefox"
        assert info.title == "Mozilla Firefox"
        assert info.pid == 0
        assert info.exe_basename == ""

    def test_camel_case_app_id(self) -> None:
        """Algumas versões do wlrctl emitem `appId` em vez de `app_id`."""
        backend = _make_backend_available()

        fake_result = MagicMock(spec=subprocess.CompletedProcess)
        fake_result.returncode = 0
        fake_result.stdout = json.dumps([{"appId": "steam", "title": "Steam"}])
        fake_result.stderr = ""

        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            return_value=fake_result,
        ):
            info = backend.get_active_window_info()

        assert info is not None
        assert info.app_id == "steam"
        assert info.wm_class == "steam"

    def test_lista_vazia_retorna_none(self) -> None:
        backend = _make_backend_available()

        fake_result = MagicMock(spec=subprocess.CompletedProcess)
        fake_result.returncode = 0
        fake_result.stdout = json.dumps([])
        fake_result.stderr = ""

        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            return_value=fake_result,
        ):
            info = backend.get_active_window_info()
        assert info is None

    def test_stdout_vazio_retorna_none(self) -> None:
        backend = _make_backend_available()

        fake_result = MagicMock(spec=subprocess.CompletedProcess)
        fake_result.returncode = 0
        fake_result.stdout = "   \n  "
        fake_result.stderr = ""

        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            return_value=fake_result,
        ):
            info = backend.get_active_window_info()
        assert info is None

    def test_sem_app_id_e_sem_title(self) -> None:
        """Toplevel sem app_id nem title → wm_class=unknown."""
        backend = _make_backend_available()

        fake_result = MagicMock(spec=subprocess.CompletedProcess)
        fake_result.returncode = 0
        fake_result.stdout = json.dumps([{}])
        fake_result.stderr = ""

        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            return_value=fake_result,
        ):
            info = backend.get_active_window_info()

        assert info is not None
        assert info.wm_class == "unknown"
        assert info.app_id == ""
        assert info.title == ""


class TestWlrctlBackendErrosSubprocess:
    """Erros transientes do subprocess: timeout, returncode, FileNotFoundError."""

    def test_timeout_retorna_none(self) -> None:
        backend = _make_backend_available()
        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="wlrctl", timeout=1.0),
        ):
            info = backend.get_active_window_info()
        assert info is None

    def test_file_not_found_marca_indisponivel(self) -> None:
        """Se wlrctl some entre init e chamada, marca _available=False."""
        backend = _make_backend_available()
        assert backend._available is True

        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            info = backend.get_active_window_info()

        assert info is None
        assert backend._available is False

    def test_returncode_nao_zero_retorna_none(self) -> None:
        backend = _make_backend_available()

        fake_result = MagicMock(spec=subprocess.CompletedProcess)
        fake_result.returncode = 2
        fake_result.stdout = ""
        fake_result.stderr = "wlrctl: cannot connect to compositor"

        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            return_value=fake_result,
        ):
            info = backend.get_active_window_info()
        assert info is None

    def test_oserror_retorna_none(self) -> None:
        backend = _make_backend_available()
        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            side_effect=OSError("dummy"),
        ):
            info = backend.get_active_window_info()
        assert info is None

    def test_json_invalido_retorna_none(self) -> None:
        backend = _make_backend_available()

        fake_result = MagicMock(spec=subprocess.CompletedProcess)
        fake_result.returncode = 0
        fake_result.stdout = "<not json>"
        fake_result.stderr = ""

        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            return_value=fake_result,
        ):
            info = backend.get_active_window_info()
        assert info is None

    def test_json_nao_e_lista(self) -> None:
        """wlrctl pode retornar dict em variantes antigas — também retorna None."""
        backend = _make_backend_available()

        fake_result = MagicMock(spec=subprocess.CompletedProcess)
        fake_result.returncode = 0
        fake_result.stdout = json.dumps({"app_id": "firefox"})
        fake_result.stderr = ""

        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            return_value=fake_result,
        ):
            info = backend.get_active_window_info()
        assert info is None


class TestWlrctlProtocoloNaoSuportado:
    """FEAT-WINDOW-DETECT-DIAG-01: compositor sem o protocolo wlr (COSMIC).

    O cosmic-comp não expõe `wlr-foreign-toplevel-management`; o wlrctl
    imprime "Foreign Toplevel Management interface not found!" no stderr e
    sai com rc 0 OU 1 conforme a versão. Antes isso era falha transiente
    (retry eterno a 2 Hz); agora marca o backend indisponível de vez.
    """

    def _fake_result(self, rc: int) -> MagicMock:
        fake = MagicMock(spec=subprocess.CompletedProcess)
        fake.returncode = rc
        fake.stdout = ""
        fake.stderr = "Foreign Toplevel Management interface not found!"
        return fake

    @pytest.mark.parametrize("rc", [0, 1])
    def test_interface_not_found_marca_indisponivel(self, rc: int) -> None:
        backend = _make_backend_available()

        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            return_value=self._fake_result(rc),
        ):
            info = backend.get_active_window_info()

        assert info is None
        assert backend.available is False
        assert backend.protocol_unsupported is True

    def test_apos_deteccao_nao_chama_mais_subprocess(self) -> None:
        """Indisponível permanente: o retry a 2 Hz não re-executa o binário."""
        backend = _make_backend_available()

        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            return_value=self._fake_result(0),
        ) as mock_run:
            backend.get_active_window_info()
            backend.get_active_window_info()
            backend.get_active_window_info()

        assert mock_run.call_count == 1

    def test_stderr_generico_nao_marca_protocolo(self) -> None:
        """Erro comum (sem o marcador) segue transiente — não desliga o backend."""
        backend = _make_backend_available()

        fake = MagicMock(spec=subprocess.CompletedProcess)
        fake.returncode = 2
        fake.stdout = ""
        fake.stderr = "wlrctl: cannot connect to compositor"

        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
            return_value=fake,
        ):
            info = backend.get_active_window_info()

        assert info is None
        assert backend.available is True
        assert backend.protocol_unsupported is False

    def test_bin_ausente_nao_e_protocolo_nao_suportado(self) -> None:
        """Diagnóstico distingue 'binário ausente' de 'compositor sem protocolo'."""
        with patch(
            "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.shutil.which",
            return_value=None,
        ):
            backend = WlrctlBackend()
        assert backend.available is False
        assert backend.protocol_unsupported is False


@pytest.mark.parametrize(
    "input_data,expected_wm_class",
    [
        ([{"app_id": "code"}], "code"),
        ([{"appId": "Spotify"}], "Spotify"),
        ([{"app_id": "", "title": "X"}], "unknown"),
        ([{"app_id": "kitty", "title": "kitty"}], "kitty"),
    ],
)
def test_parametrizado_app_id_variantes(
    input_data: list[dict[str, str]], expected_wm_class: str
) -> None:
    backend = _make_backend_available()

    fake_result = MagicMock(spec=subprocess.CompletedProcess)
    fake_result.returncode = 0
    fake_result.stdout = json.dumps(input_data)
    fake_result.stderr = ""

    with patch(
        "hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel.subprocess.run",
        return_value=fake_result,
    ):
        info = backend.get_active_window_info()

    assert info is not None
    assert info.wm_class == expected_wm_class
