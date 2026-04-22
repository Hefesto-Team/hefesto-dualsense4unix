"""HefestoApp GTK: janela principal + Notebook de abas + tray icon.

A janela fecha pro tray (close-to-tray); daemon segue rodando.
'Sair' no menu do tray encerra GUI + daemon (BUG-MULTI-INSTANCE-01).

Single-instance (BUG-TRAY-SINGLE-FLASH-01): modelo "primeira vence". Se uma
GUI já está rodando, a nova invocação traz a existente ao foco (xdotool ou
SIGUSR1) e sai com exit 0 — evita o efeito "abre e fecha" causado pela race
de dois eventos udev ADD em <200ms.
"""
# ruff: noqa: E402
from __future__ import annotations

import os
import signal
import subprocess
import sys
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


def _activate_window_by_pid(predecessor_pid: int) -> None:
    """Traz a janela do predecessor ao foco via xdotool; fallback via SIGUSR1.

    Tenta localizar o WID da janela com título contendo "Hefesto" associado ao
    `predecessor_pid`. Se encontrado, usa `xdotool windowactivate`. Caso xdotool
    não esteja disponível ou não retorne WID, envia SIGUSR1 ao predecessor — a
    GUI instala um handler que chama `GLib.idle_add(self.show_window)`.
    """
    wid: str | None = None
    try:
        result = subprocess.run(
            ["xdotool", "search", "--pid", str(predecessor_pid), "--name", "Hefesto"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            wids = result.stdout.strip().splitlines()
            if wids:
                wid = wids[0]
    except (FileNotFoundError, subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
        logger.warning("activate_window_xdotool_search_falhou", err=str(exc))

    if wid:
        try:
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", wid],
                capture_output=True,
                timeout=2,
                check=False,
            )
            logger.info("activate_window_xdotool_ok", wid=wid, pid=predecessor_pid)
            return
        except (FileNotFoundError, subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
            logger.warning("activate_window_xdotool_activate_falhou", err=str(exc))

    # Fallback: SIGUSR1 — a GUI escuta e faz show_window via GLib.idle_add.
    try:
        os.kill(predecessor_pid, signal.SIGUSR1)
        logger.info("activate_window_sigusr1_enviado", pid=predecessor_pid)
    except (ProcessLookupError, PermissionError) as exc:
        logger.warning("activate_window_sigusr1_falhou", pid=predecessor_pid, err=str(exc))


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
        # BUG-TRAY-SINGLE-FLASH-01: "primeira vence" — traz predecessor ao foco
        # e sai limpo em vez de matá-lo (evita efeito "abre e fecha" no tray).
        from hefesto.utils.single_instance import acquire_or_bring_to_front

        pid = acquire_or_bring_to_front("gui", bring_to_front_cb=_activate_window_by_pid)
        if pid is None:
            # Predecessor vivo encontrado e trazido ao foco — sair limpo.
            sys.exit(0)

        # Instala handler SIGUSR1: pedido externo de "mostrar janela".
        # Usa GLib.idle_add para garantir execução na thread GTK principal.
        from gi.repository import GLib

        signal.signal(signal.SIGUSR1, lambda _sig, _frame: GLib.idle_add(self.show_window))

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
            "on_lightbar_brightness_changed": self.on_lightbar_brightness_changed,
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
            "on_daemon_migrate_to_systemd": self.on_daemon_migrate_to_systemd,
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
        """Encerra GUI e daemon (BUG-MULTI-INSTANCE-01).

        'Sair' do menu do tray encerra tudo. 'Fechar janela' (X no header)
        continua só escondendo pro tray via `on_window_delete_event`.
        """
        self._quitting = True
        if self.tray is not None:
            self.tray.stop()
        try:
            subprocess.run(
                ["systemctl", "--user", "stop", "hefesto.service"],
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            logger.warning("quit_app_systemctl_falhou", erro=str(exc))
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
