"""Testes unit para `firmware_updater.py`.

Mocks subprocess para evitar depender de `dualsensectl` instalado.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hefesto.integrations.firmware_updater import (
    FIRMWARE_BLOB_SIZE,
    ControllerNotConnectedError,
    DualsensectlNotAvailableError,
    FirmwareError,
    FirmwareUpdateFailedError,
    FirmwareUpdater,
    FirmwareUpdateTimeoutError,
    InvalidBlobError,
    _parse_info_output,
)

SAMPLE_INFO_OUTPUT = """Hardware: 617
Build date: Jul  4 2025 10:10:32
Firmware: 110002a (type 3)
Fw version: 65596 131082 6
Sw series: 4
Update version: 0630
"""


class TestIsAvailable:
    def test_presente(self) -> None:
        with patch(
            "hefesto.integrations.firmware_updater.shutil.which",
            return_value="/usr/bin/dualsensectl",
        ):
            updater = FirmwareUpdater()
            assert updater.is_available() is True

    def test_ausente(self) -> None:
        with patch("hefesto.integrations.firmware_updater.shutil.which", return_value=None):
            updater = FirmwareUpdater()
            assert updater.is_available() is False


class TestParseInfoOutput:
    def test_output_canonico(self) -> None:
        info = _parse_info_output(SAMPLE_INFO_OUTPUT)
        assert info.hardware == "617"
        assert info.build_date == "Jul  4 2025 10:10:32"
        assert info.firmware_version == "110002a (type 3)"
        assert info.update_version == "0630"
        assert info.fw_version == "65596 131082 6"
        assert info.sw_series == "4"
        assert info.raw == SAMPLE_INFO_OUTPUT

    def test_output_vazio(self) -> None:
        info = _parse_info_output("")
        assert info.hardware == ""
        assert info.update_version == ""

    def test_output_com_linhas_extra(self) -> None:
        output = SAMPLE_INFO_OUTPUT + "Extra info: ignorada\nOutra coisa: também\n"
        info = _parse_info_output(output)
        assert info.update_version == "0630"


class TestGetInfo:
    def _proc(
        self, returncode: int, stdout: str = "", stderr: str = ""
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["dualsensectl", "info"],
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def test_sem_binario_levanta(self) -> None:
        updater = FirmwareUpdater()
        with patch.object(updater, "is_available", return_value=False), pytest.raises(
            DualsensectlNotAvailableError
        ):
            updater.get_info()

    def test_sucesso_parseia_output(self) -> None:
        updater = FirmwareUpdater()
        with patch.object(updater, "is_available", return_value=True), patch(
            "hefesto.integrations.firmware_updater.subprocess.run",
            return_value=self._proc(0, SAMPLE_INFO_OUTPUT, ""),
        ):
            info = updater.get_info()
            assert info.hardware == "617"
            assert info.update_version == "0630"

    def test_sem_controle_levanta(self) -> None:
        updater = FirmwareUpdater()
        with patch.object(updater, "is_available", return_value=True), patch(
            "hefesto.integrations.firmware_updater.subprocess.run",
            return_value=self._proc(1, "", "No device found"),
        ), pytest.raises(ControllerNotConnectedError):
            updater.get_info()

    def test_timeout_levanta(self) -> None:
        updater = FirmwareUpdater()
        with patch.object(updater, "is_available", return_value=True), patch(
            "hefesto.integrations.firmware_updater.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="dualsensectl", timeout=5.0),
        ), pytest.raises(FirmwareUpdateTimeoutError):
            updater.get_info()

    def test_retorno_generico_levanta_firmware_error(self) -> None:
        updater = FirmwareUpdater()
        with patch.object(updater, "is_available", return_value=True), patch(
            "hefesto.integrations.firmware_updater.subprocess.run",
            return_value=self._proc(2, "", "Erro genérico do binário"),
        ), pytest.raises(FirmwareError):
            updater.get_info()


class TestApplyBlobValidation:
    def test_sem_binario_levanta(self, tmp_path: Path) -> None:
        blob = tmp_path / "fw.bin"
        blob.write_bytes(b"\x00" * FIRMWARE_BLOB_SIZE)
        updater = FirmwareUpdater()
        with patch.object(updater, "is_available", return_value=False), pytest.raises(
            DualsensectlNotAvailableError
        ):
            updater.apply(blob)

    def test_arquivo_nao_existe(self, tmp_path: Path) -> None:
        updater = FirmwareUpdater()
        with patch.object(updater, "is_available", return_value=True), pytest.raises(
            InvalidBlobError
        ):
            updater.apply(tmp_path / "inexistente.bin")

    def test_arquivo_pequeno(self, tmp_path: Path) -> None:
        blob = tmp_path / "fw.bin"
        blob.write_bytes(b"\x00" * 1024)
        updater = FirmwareUpdater()
        with patch.object(updater, "is_available", return_value=True), pytest.raises(
            InvalidBlobError
        ):
            updater.apply(blob)


class TestApplyFluxo:
    def _make_popen(self, lines: list[str], returncode: int = 0) -> MagicMock:
        proc = MagicMock()
        proc.stdout = iter(lines)
        proc.returncode = returncode
        proc.wait = MagicMock(return_value=returncode)
        proc.kill = MagicMock()
        return proc

    def _blob(self, tmp_path: Path) -> Path:
        p = tmp_path / "fw.bin"
        p.write_bytes(b"\x00" * FIRMWARE_BLOB_SIZE)
        return p

    def test_progress_callback_chamado(self, tmp_path: Path) -> None:
        blob = self._blob(tmp_path)
        updater = FirmwareUpdater()
        fake_proc = self._make_popen(
            [
                "Checking firmware header...\n",
                "Writing firmware:   0% \r",
                "Writing firmware:  25% \r",
                "Writing firmware:  50% \r",
                "Writing firmware: 100% Done!\n",
                "Updating firmware for DualSense\n",
            ],
            returncode=0,
        )
        progress_values: list[int] = []
        with patch.object(updater, "is_available", return_value=True), patch.object(
            updater, "get_info", side_effect=[
                MagicMock(update_version="0458"),
                MagicMock(update_version="0630"),
            ],
        ), patch(
            "hefesto.integrations.firmware_updater.subprocess.Popen",
            return_value=fake_proc,
        ):
            result = updater.apply(blob, progress_callback=progress_values.append)
        assert progress_values == [0, 25, 50, 100]
        assert result.previous_update_version == "0458"
        assert result.new_update_version == "0630"

    def test_returncode_diferente_de_zero_levanta(self, tmp_path: Path) -> None:
        blob = self._blob(tmp_path)
        updater = FirmwareUpdater()
        fake_proc = self._make_popen(
            [
                "Checking firmware header...\n",
                "Error: invalid firmware binary\n",
            ],
            returncode=3,
        )
        with patch.object(updater, "is_available", return_value=True), patch.object(
            updater, "get_info", return_value=MagicMock(update_version="0630"),
        ), patch(
            "hefesto.integrations.firmware_updater.subprocess.Popen",
            return_value=fake_proc,
        ), pytest.raises(FirmwareUpdateFailedError, match="código 3"):
            updater.apply(blob)

    def test_timeout_kill_process(self, tmp_path: Path) -> None:
        blob = self._blob(tmp_path)
        updater = FirmwareUpdater()
        fake_proc = MagicMock()
        fake_proc.stdout = iter(["Writing firmware: 50%\n"])
        fake_proc.wait = MagicMock(
            side_effect=subprocess.TimeoutExpired(cmd="dualsensectl", timeout=600.0)
        )
        fake_proc.kill = MagicMock()
        with patch.object(updater, "is_available", return_value=True), patch.object(
            updater, "get_info", return_value=MagicMock(update_version="0458"),
        ), patch(
            "hefesto.integrations.firmware_updater.subprocess.Popen",
            return_value=fake_proc,
        ), pytest.raises(FirmwareUpdateTimeoutError):
            updater.apply(blob)
        fake_proc.kill.assert_called_once()

    def test_progresso_callback_nao_duplica_percent(self, tmp_path: Path) -> None:
        blob = self._blob(tmp_path)
        updater = FirmwareUpdater()
        fake_proc = self._make_popen(
            [
                "Writing firmware: 50%\r",
                "Writing firmware: 50%\r",
                "Writing firmware: 75%\r",
            ],
            returncode=0,
        )
        progress_values: list[int] = []
        with patch.object(updater, "is_available", return_value=True), patch.object(
            updater, "get_info", return_value=MagicMock(update_version="0458"),
        ), patch(
            "hefesto.integrations.firmware_updater.subprocess.Popen",
            return_value=fake_proc,
        ):
            updater.apply(blob, progress_callback=progress_values.append)
        assert progress_values == [50, 75]
