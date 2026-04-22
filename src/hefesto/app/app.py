"""HefestoApp GTK: janela principal + Notebook de abas + tray icon.

A janela fecha pro tray (close-to-tray); daemon segue rodando.
'Sair' no menu do tray encerra o processo de verdade.
"""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, Gtk

from hefesto.app.actions.daemon_actions import DaemonActionsMixin
from hefesto.app.actions.emulation_actions import EmulationActionsMixin
from hefesto.app.actions.lightbar_actions import LightbarActionsMixin
from hefesto.app.actions.mouse_actions import MouseActionsMixin
from hefesto.app.actions.profiles_actions import ProfilesActionsMixin
from hefesto.app.actions.rumble_actions import RumbleActionsMixin
from hefesto.app.actions.status_actions import StatusActionsMixin
from hefesto.app.actions.triggers_actions import TriggersActionsMixin
from hefesto.app.constants import ICON_PATH, MAIN_GLADE
from hefesto.app.ipc_bridge import profile_list, profile_switch
from hefesto.app.tray import AppTray
from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)


class HefestoApp(
    StatusActionsMixin,
    TriggersActionsMixin,
    LightbarActionsMixin,
    RumbleActionsMixin,
    ProfilesActionsMixin,
    DaemonActionsMixin,
    EmulationActionsMixin,
    MouseActionsMixin,
):
    """Aplicação GTK do Hefesto."""

    def __init__(self) -> None:
        self.builder = Gtk.Builder()
        if not MAIN_GLADE.exists():
            raise FileNotFoundError(f"main.glade não encontrado em {MAIN_GLADE}")
        self.builder.add_from_file(str(MAIN_GLADE))

        self.window = self.builder.get_object("main_window")
        if self.window is None:
            raise RuntimeError("main_window não encontrada em main.glade")

        self.window.set_title("Hefesto - DSX para Unix")
        self.window.set_wmclass("hefesto", "Hefesto")
        if ICON_PATH.exists():
            self.window.set_icon_from_file(str(ICON_PATH))

        self._install_banner_logo()

        self.tray: AppTray | None = None
        self._quitting = False

        self.builder.connect_signals(self._signal_handlers())

    def _signal_handlers(self) -> dict[str, object]:
        return {
            "on_window_delete_event": self.on_window_delete_event,
            # Triggers
            "on_trigger_left_mode_changed": self.on_trigger_left_mode_changed,
            "on_trigger_right_mode_changed": self.on_trigger_right_mode_changed,
            "on_trigger_left_apply": self.on_trigger_left_apply,
            "on_trigger_right_apply": self.on_trigger_right_apply,
            "on_trigger_left_reset": self.on_trigger_left_reset,
            "on_trigger_right_reset": self.on_trigger_right_reset,
            # Lightbar + Player LEDs
            "on_lightbar_color_set": self.on_lightbar_color_set,
            "on_lightbar_apply": self.on_lightbar_apply,
            "on_lightbar_off": self.on_lightbar_off,
            "on_player_leds_preset_all": self.on_player_leds_preset_all,
            "on_player_leds_preset_p1": self.on_player_leds_preset_p1,
            "on_player_leds_preset_p2": self.on_player_leds_preset_p2,
            "on_player_leds_preset_none": self.on_player_leds_preset_none,
            # Rumble
            "on_rumble_apply": self.on_rumble_apply,
            "on_rumble_test_500ms": self.on_rumble_test_500ms,
            "on_rumble_stop": self.on_rumble_stop,
            # Perfis
            "on_profile_row_activated": self.on_profile_row_activated,
            "on_profile_new": self.on_profile_new,
            "on_profile_duplicate": self.on_profile_duplicate,
            "on_profile_remove": self.on_profile_remove,
            "on_profile_activate": self.on_profile_activate,
            "on_profile_reload": self.on_profile_reload,
            "on_profile_match_type_changed": self.on_profile_match_type_changed,
            "on_profile_save": self.on_profile_save,
            # Daemon
            "on_daemon_start": self.on_daemon_start,
            "on_daemon_stop": self.on_daemon_stop,
            "on_daemon_restart": self.on_daemon_restart,
            "on_daemon_refresh": self.on_daemon_refresh,
            "on_daemon_view_logs": self.on_daemon_view_logs,
            "on_daemon_autostart_toggled": self.on_daemon_autostart_toggled,
            "on_daemon_service_restart": self.on_daemon_service_restart,
            # Emulação
            "on_emulation_refresh": self.on_emulation_refresh,
            "on_emulation_test_device": self.on_emulation_test_device,
            "on_emulation_open_toml": self.on_emulation_open_toml,
            # Mouse
            "on_mouse_toggle_set": self.on_mouse_toggle_set,
            "on_mouse_speed_changed": self.on_mouse_speed_changed,
            "on_mouse_scroll_speed_changed": self.on_mouse_scroll_speed_changed,
        }

    # --- banner ---

    def _install_banner_logo(self) -> None:
        """Carrega o PNG do logo escalado para 64x64 e aplica no GtkImage do banner."""
        logo_widget = self.builder.get_object("app_logo")
        if logo_widget is None:
            logger.warning("banner_logo_widget_ausente")
            return
        if not ICON_PATH.exists():
            logger.warning("banner_logo_png_ausente", path=str(ICON_PATH))
            return
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(ICON_PATH),
                width=64,
                height=64,
                preserve_aspect_ratio=True,
            )
        except Exception as exc:  # GLib.Error ou OSError
            logger.warning("banner_logo_falha_pixbuf", error=str(exc))
            return
        logo_widget.set_from_pixbuf(pixbuf)

    # --- handlers ---

    def on_window_delete_event(self, _widget: Any, _event: Any) -> bool:
        """Intercepta fechamento da janela: esconde pro tray em vez de encerrar.

        Retorna True pra cancelar o destroy default do GTK.
        """
        if self._quitting:
            return False
        if self.tray is not None and self.tray.is_available():
            self.window.hide()
            return True
        Gtk.main_quit()
        return False

    def quit_app(self) -> None:
        self._quitting = True
        if self.tray is not None:
            self.tray.stop()
        Gtk.main_quit()

    def show_window(self) -> None:
        self.window.show_all()
        self.window.present()

    # --- run ---

    def show(self) -> None:
        self.window.show_all()
        self.install_status_polling()
        self.install_triggers_tab()
        self.install_lightbar_tab()
        self.install_rumble_tab()
        self.install_profiles_tab()
        self.install_daemon_tab()
        self.install_emulation_tab()
        self.install_mouse_tab()
        # BUG-DAEMON-AUTOSTART-01: dispara start do daemon em thread worker
        # se a unit está instalada mas o service não está ativo. Jamais
        # bloqueia a thread GTK; falha silenciosa via logger.warning.
        self.ensure_daemon_running()

    def run(self, *, start_hidden: bool = False) -> None:
        self.tray = AppTray(
            on_show_window=self.show_window,
            on_quit=self.quit_app,
            on_list_profiles=profile_list,
            on_switch_profile=profile_switch,
        )
        self.tray.start()
        if start_hidden and self.tray.is_available():
            self.install_status_polling()
            self.install_triggers_tab()
            self.install_lightbar_tab()
            self.install_rumble_tab()
            self.install_profiles_tab()
            self.install_daemon_tab()
            self.install_emulation_tab()
            self.install_mouse_tab()
            # BUG-DAEMON-AUTOSTART-01: mesmo no modo oculto, garantir daemon.
            self.ensure_daemon_running()
            logger.info("hefesto_start_hidden")
        else:
            self.show()
        Gtk.main()


def main() -> None:
    app = HefestoApp()
    app.run()


if __name__ == "__main__":
    main()
