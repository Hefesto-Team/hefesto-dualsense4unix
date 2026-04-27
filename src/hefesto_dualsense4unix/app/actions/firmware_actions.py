"""Aba Firmware: update via `dualsensectl` (opção A+UI do survey §0.5)."""
# ruff: noqa: E402
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.ipc_bridge import _get_executor
from hefesto_dualsense4unix.integrations.firmware_updater import (
    FIRMWARE_BLOB_SIZE,
    MIN_BLOB_SIZE_BYTES,
    ControllerNotConnectedError,
    DualsensectlNotAvailableError,
    FirmwareError,
    FirmwareInfo,
    FirmwareUpdater,
)

if TYPE_CHECKING:
    from hefesto_dualsense4unix.integrations.firmware_updater import FirmwareApplyResult

logger = logging.getLogger(__name__)

_INSTALL_HELP = (
    "dualsensectl não encontrado. Instale via Flathub "
    "(https://flathub.org/apps/com.github.nowrep.dualsensectl) "
    "ou compile do fonte (https://github.com/nowrep/dualsensectl) "
    "e reabra a aba."
)

_RISK_BANNER = (
    "RISCO DE BRICK. USE APENAS BLOBS OFICIAIS SONY "
    "(fwupdater.dl.playstation.net). NÃO DESCONECTE DURANTE O UPDATE."
)


class FirmwareActionsMixin(WidgetAccessMixin):
    """Controla a aba Firmware."""

    _firmware_updater: FirmwareUpdater
    _firmware_selected_blob: Path | None
    _firmware_in_progress: bool

    def install_firmware_tab(self) -> None:
        self._firmware_updater = FirmwareUpdater()
        self._firmware_selected_blob = None
        self._firmware_in_progress = False

        self._set_firmware_label("firmware_current_version_label", "—")
        self._set_firmware_label("firmware_hardware_label", "—")
        self._set_firmware_label("firmware_build_date_label", "—")
        self._set_firmware_label("firmware_file_entry", "")
        self._set_firmware_label("firmware_status_label", "Pronto.")
        self._set_firmware_label("firmware_risk_banner_label", _RISK_BANNER)
        self._set_progress(0, "")

        available = self._firmware_updater.is_available()
        self._set_button_enabled("firmware_check_btn", available)
        self._set_button_enabled("firmware_browse_btn", available)
        self._set_button_enabled("firmware_apply_btn", False)
        if not available:
            self._set_firmware_label("firmware_status_label", _INSTALL_HELP)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def on_firmware_check(self, _btn: Gtk.Button) -> None:
        if self._firmware_in_progress:
            return
        self._set_firmware_label(
            "firmware_status_label", "Consultando controle..."
        )

        def _worker() -> None:
            try:
                info = self._firmware_updater.get_info()
                GLib.idle_add(self._on_firmware_info_ok, info)
            except DualsensectlNotAvailableError as exc:
                GLib.idle_add(self._on_firmware_info_fail, _INSTALL_HELP, str(exc))
            except ControllerNotConnectedError as exc:
                GLib.idle_add(
                    self._on_firmware_info_fail,
                    "Nenhum DualSense conectado. Plugue via USB-C.",
                    str(exc),
                )
            except FirmwareError as exc:
                GLib.idle_add(
                    self._on_firmware_info_fail,
                    "Falha ao consultar firmware.",
                    str(exc),
                )

        _get_executor().submit(_worker)

    def on_firmware_browse(self, _btn: Gtk.Button) -> None:
        if self._firmware_in_progress:
            return
        window = self._get("main_window")
        dialog = Gtk.FileChooserDialog(
            title="Selecione o blob de firmware (.bin)",
            parent=window,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            "Cancelar",
            Gtk.ResponseType.CANCEL,
            "Selecionar",
            Gtk.ResponseType.OK,
        )
        bin_filter = Gtk.FileFilter()
        bin_filter.set_name("Firmware .bin")
        bin_filter.add_pattern("*.bin")
        dialog.add_filter(bin_filter)

        response = dialog.run()
        path_text = ""
        if response == Gtk.ResponseType.OK:
            path_text = dialog.get_filename() or ""
        dialog.destroy()

        if not path_text:
            return

        blob = Path(path_text)
        if not blob.is_file():
            self._set_firmware_label(
                "firmware_status_label",
                f"Arquivo não encontrado: {blob.name}",
            )
            return

        size = blob.stat().st_size
        if size < MIN_BLOB_SIZE_BYTES:
            self._set_firmware_label(
                "firmware_status_label",
                f"Arquivo muito pequeno ({size} bytes; blob oficial tem "
                f"{FIRMWARE_BLOB_SIZE}). Provavelmente truncado.",
            )
            self._set_button_enabled("firmware_apply_btn", False)
            return

        self._firmware_selected_blob = blob
        self._set_firmware_label("firmware_file_entry", str(blob))
        self._set_firmware_label(
            "firmware_status_label",
            f"Arquivo selecionado ({size} bytes). Clique em Aplicar quando estiver pronto.",
        )
        self._set_button_enabled("firmware_apply_btn", True)

    def on_firmware_apply(self, _btn: Gtk.Button) -> None:
        if self._firmware_in_progress:
            return
        blob = self._firmware_selected_blob
        if blob is None:
            self._set_firmware_label(
                "firmware_status_label", "Selecione primeiro um arquivo .bin."
            )
            return

        if not self._confirm_apply(blob):
            self._set_firmware_label(
                "firmware_status_label", "Update cancelado."
            )
            return

        self._firmware_in_progress = True
        self._set_button_enabled("firmware_check_btn", False)
        self._set_button_enabled("firmware_browse_btn", False)
        self._set_button_enabled("firmware_apply_btn", False)
        self._set_progress(0, "Preparando update...")

        def _progress_cb(pct: int) -> None:
            GLib.idle_add(self._on_firmware_progress, pct)

        def _worker() -> None:
            try:
                result = self._firmware_updater.apply(
                    blob, progress_callback=_progress_cb
                )
                GLib.idle_add(self._on_firmware_apply_ok, result)
            except FirmwareError as exc:
                GLib.idle_add(self._on_firmware_apply_fail, str(exc))

        _get_executor().submit(_worker)

    # ------------------------------------------------------------------
    # Callbacks na main thread (via GLib.idle_add)
    # ------------------------------------------------------------------

    def _on_firmware_info_ok(self, info: FirmwareInfo) -> bool:
        self._set_firmware_label(
            "firmware_current_version_label",
            f"{info.update_version or '?'} (fw {info.firmware_version or '?'})",
        )
        self._set_firmware_label(
            "firmware_hardware_label", info.hardware or "—"
        )
        self._set_firmware_label(
            "firmware_build_date_label", info.build_date or "—"
        )
        self._set_firmware_label("firmware_status_label", "Controle detectado.")
        return False

    def _on_firmware_info_fail(self, short: str, detail: str) -> bool:
        logger.info("firmware_info_falhou detail=%s", detail)
        self._set_firmware_label("firmware_status_label", short)
        return False

    def _on_firmware_progress(self, pct: int) -> bool:
        self._set_progress(pct, f"Aplicando firmware: {pct}%")
        return False

    def _on_firmware_apply_ok(self, result: FirmwareApplyResult) -> bool:
        self._firmware_in_progress = False
        self._set_button_enabled("firmware_check_btn", True)
        self._set_button_enabled("firmware_browse_btn", True)
        self._set_button_enabled("firmware_apply_btn", False)
        self._firmware_selected_blob = None
        self._set_firmware_label("firmware_file_entry", "")
        self._set_progress(100, "Concluído.")
        prev = result.previous_update_version or "?"
        new = result.new_update_version or "?"
        self._set_firmware_label(
            "firmware_status_label",
            f"Firmware atualizado: 0x{prev} → 0x{new}. Reconecte o controle se necessário.",
        )
        return False

    def _on_firmware_apply_fail(self, message: str) -> bool:
        self._firmware_in_progress = False
        self._set_button_enabled("firmware_check_btn", True)
        self._set_button_enabled("firmware_browse_btn", True)
        self._set_button_enabled(
            "firmware_apply_btn", self._firmware_selected_blob is not None
        )
        logger.warning("firmware_apply_falhou message=%s", message)
        self._set_progress(0, "")
        self._set_firmware_label(
            "firmware_status_label",
            f"Falha: {_friendly_error(message)}",
        )
        return False

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _set_firmware_label(self, widget_id: str, text: str) -> None:
        widget: Any = self._get(widget_id)
        if widget is None:
            return
        if hasattr(widget, "set_text"):
            widget.set_text(text)
        elif hasattr(widget, "set_label"):
            widget.set_label(text)

    def _set_progress(self, pct: int, text: str) -> None:
        bar: Any = self._get("firmware_progress_bar")
        if bar is None:
            return
        fraction = max(0.0, min(1.0, pct / 100.0))
        bar.set_fraction(fraction)
        if text:
            bar.set_text(text)
            bar.set_show_text(True)
        else:
            bar.set_show_text(False)

    def _set_button_enabled(self, widget_id: str, enabled: bool) -> None:
        widget: Any = self._get(widget_id)
        if widget is not None and hasattr(widget, "set_sensitive"):
            widget.set_sensitive(enabled)

    def _confirm_apply(self, blob: Path) -> bool:
        window = self._get("main_window")
        dialog = Gtk.MessageDialog(
            parent=window,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=_RISK_BANNER,
        )
        dialog.format_secondary_text(
            f"Aplicar firmware:\n\n{blob}\n\n"
            "O processo pode durar 1-3 minutos. O controle reiniciará ao final. "
            "Clique OK apenas se o blob for oficial da Sony."
        )
        response = dialog.run()
        dialog.destroy()
        return bool(response == Gtk.ResponseType.OK)


def _friendly_error(message: str) -> str:
    """Traduz códigos de erro conhecidos em texto mais acessível."""
    lower = message.lower()
    if "código 3" in lower or "0x03" in lower or "code 3" in lower:
        return (
            "Blob inválido — verifique se é o modelo correto "
            "(DualSense vs DualSense Edge)."
        )
    if "código 2" in lower or "0x02" in lower:
        return "Tamanho do blob inválido — arquivo provavelmente corrompido."
    if "timeout" in lower:
        return "Tempo excedido — reconecte controle e tente de novo."
    if "no device" in lower or "nenhum controle" in lower:
        return "Controle desconectado — plugue via USB-C e tente de novo."
    return message


__all__ = ["FirmwareActionsMixin"]
