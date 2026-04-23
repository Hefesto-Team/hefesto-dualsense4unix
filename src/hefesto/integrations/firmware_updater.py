"""Wrapper subprocess para `dualsensectl` firmware update.

Backend da aba Firmware da GUI. Encapsula invocações do binário
`dualsensectl` expondo API Python tipada. O `dualsensectl` já
implementa o protocolo DFU real do DualSense (merge 2026-02-19,
PR #53); este módulo só orquestra chamadas e traduz saídas.

Ver `docs/research/firmware-dualsense-2026-04-survey.md` §0 para
contexto técnico do protocolo.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

BINARY = "dualsensectl"

SUBPROCESS_TIMEOUT_INFO_SEC = 5.0
SUBPROCESS_TIMEOUT_UPDATE_SEC = 600.0

FIRMWARE_BLOB_SIZE = 950_272
MIN_BLOB_SIZE_BYTES = 900 * 1024


@dataclass(frozen=True)
class FirmwareInfo:
    """Snapshot do firmware atual reportado pelo controle."""

    hardware: str
    build_date: str
    firmware_version: str
    update_version: str
    fw_type: str
    fw_version: str
    sw_series: str
    raw: str


@dataclass(frozen=True)
class FirmwareApplyResult:
    """Resultado de um apply bem-sucedido."""

    previous_update_version: str
    new_update_version: str


class FirmwareError(Exception):
    """Erro raiz da integração firmware."""


class DualsensectlNotAvailableError(FirmwareError):
    """`dualsensectl` não encontrado no PATH."""


class ControllerNotConnectedError(FirmwareError):
    """Nenhum DualSense conectado via USB."""


class InvalidBlobError(FirmwareError):
    """Blob rejeitado: tamanho errado, header inválido ou modelo incompatível."""


class FirmwareUpdateFailedError(FirmwareError):
    """Falha durante o processo de escrita (código de erro do controle)."""


class FirmwareUpdateTimeoutError(FirmwareError):
    """Tempo de update excedido."""


_INFO_LINE_RE = re.compile(r"^([A-Za-z][\w\s]*?):\s*(.+?)\s*$")
_PROGRESS_RE = re.compile(r"Writing firmware:\s*(\d+)%")


class FirmwareUpdater:
    """Cliente subprocess do `dualsensectl`."""

    def __init__(self, binary: str = BINARY) -> None:
        self.binary = binary

    def is_available(self) -> bool:
        """True se o binário existe e é executável no PATH."""
        return shutil.which(self.binary) is not None

    def get_info(self) -> FirmwareInfo:
        """Retorna `FirmwareInfo` lendo `dualsensectl info`.

        Levanta `DualsensectlNotAvailableError` se binário ausente,
        `ControllerNotConnectedError` se sem controle plugado.
        """
        if not self.is_available():
            raise DualsensectlNotAvailableError(
                "dualsensectl não encontrado no PATH. "
                "Instale via gerenciador de pacotes da sua distro."
            )

        try:
            proc = subprocess.run(
                [self.binary, "info"],
                timeout=SUBPROCESS_TIMEOUT_INFO_SEC,
                check=False,
                capture_output=True,
                text=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise FirmwareUpdateTimeoutError(
                f"dualsensectl info excedeu {SUBPROCESS_TIMEOUT_INFO_SEC}s"
            ) from exc
        except (FileNotFoundError, OSError) as exc:
            raise DualsensectlNotAvailableError(str(exc)) from exc

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            if "No device" in stderr or "not found" in stderr.lower():
                raise ControllerNotConnectedError(
                    "Nenhum DualSense conectado via USB. "
                    "Plug o controle via cabo USB-C e tente de novo."
                )
            raise FirmwareError(
                f"dualsensectl info falhou (código {proc.returncode}): {stderr}"
            )

        return _parse_info_output(proc.stdout)

    def apply(
        self,
        firmware_bin: Path,
        progress_callback: Callable[[int], None] | None = None,
    ) -> FirmwareApplyResult:
        """Aplica `firmware_bin` via `dualsensectl update`.

        `progress_callback` recebe percentual 0-100 conforme o binário
        emite `Writing firmware: NN%`. Chamado na thread do subprocess
        — consumidor deve usar `GLib.idle_add` se atualizar UI.

        Levanta:
            DualsensectlNotAvailableError: binário ausente.
            InvalidBlobError: arquivo inexistente, extensão errada ou
                tamanho inválido antes de chamar o binário.
            FirmwareUpdateFailedError: binário retornou código != 0 ou
                stderr com mensagem de erro do firmware.
            FirmwareUpdateTimeoutError: update excedeu o timeout.
        """
        if not self.is_available():
            raise DualsensectlNotAvailableError(
                "dualsensectl não encontrado no PATH."
            )

        blob = Path(firmware_bin)
        if not blob.is_file():
            raise InvalidBlobError(f"Arquivo não encontrado: {blob}")
        size = blob.stat().st_size
        if size < MIN_BLOB_SIZE_BYTES:
            raise InvalidBlobError(
                f"Arquivo muito pequeno ({size} bytes). "
                f"Blob oficial tem {FIRMWARE_BLOB_SIZE} bytes — "
                "o arquivo pode estar truncado ou corrompido."
            )

        previous_version = ""
        try:
            previous_version = self.get_info().update_version
        except FirmwareError:
            logger.warning("nao_foi_possivel_obter_versao_anterior")

        try:
            proc = subprocess.Popen(
                [self.binary, "update", str(blob)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except (FileNotFoundError, OSError) as exc:
            raise DualsensectlNotAvailableError(str(exc)) from exc

        assert proc.stdout is not None
        last_reported = -1
        collected_lines: list[str] = []

        try:
            for raw_line in proc.stdout:
                line = raw_line.rstrip("\n\r")
                collected_lines.append(line)
                if progress_callback is not None:
                    for chunk in raw_line.split("\r"):
                        match = _PROGRESS_RE.search(chunk)
                        if match:
                            pct = int(match.group(1))
                            if pct != last_reported:
                                progress_callback(pct)
                                last_reported = pct
            proc.wait(timeout=SUBPROCESS_TIMEOUT_UPDATE_SEC)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            raise FirmwareUpdateTimeoutError(
                f"update excedeu {SUBPROCESS_TIMEOUT_UPDATE_SEC}s"
            ) from exc

        if proc.returncode != 0:
            stderr_joined = "\n".join(collected_lines[-20:])
            raise FirmwareUpdateFailedError(
                f"dualsensectl update falhou (código {proc.returncode}): "
                f"{stderr_joined}"
            )

        new_version = previous_version
        try:
            new_version = self.get_info().update_version
        except FirmwareError:
            logger.warning("nao_foi_possivel_obter_versao_apos_update")

        return FirmwareApplyResult(
            previous_update_version=previous_version,
            new_update_version=new_version,
        )


def _parse_info_output(stdout: str) -> FirmwareInfo:
    """Parseia saída padrão de `dualsensectl info` para `FirmwareInfo`."""
    kv: dict[str, str] = {}
    for line in stdout.splitlines():
        match = _INFO_LINE_RE.match(line)
        if match:
            kv[match.group(1).strip().lower()] = match.group(2).strip()

    return FirmwareInfo(
        hardware=kv.get("hardware", ""),
        build_date=kv.get("build date", ""),
        firmware_version=kv.get("firmware", ""),
        update_version=kv.get("update version", ""),
        fw_type=kv.get("firmware", "").split("(type")[-1].rstrip(")").strip()
        if "type" in kv.get("firmware", "")
        else "",
        fw_version=kv.get("fw version", ""),
        sw_series=kv.get("sw series", ""),
        raw=stdout,
    )


__all__ = [
    "BINARY",
    "FIRMWARE_BLOB_SIZE",
    "MIN_BLOB_SIZE_BYTES",
    "SUBPROCESS_TIMEOUT_INFO_SEC",
    "SUBPROCESS_TIMEOUT_UPDATE_SEC",
    "ControllerNotConnectedError",
    "DualsensectlNotAvailableError",
    "FirmwareApplyResult",
    "FirmwareError",
    "FirmwareInfo",
    "FirmwareUpdateFailedError",
    "FirmwareUpdateTimeoutError",
    "FirmwareUpdater",
    "InvalidBlobError",
]
