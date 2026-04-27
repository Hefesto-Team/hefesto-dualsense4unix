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

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, Gtk

from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin
from hefesto_dualsense4unix.app.actions.emulation_actions import EmulationActionsMixin
from hefesto_dualsense4unix.app.actions.firmware_actions import FirmwareActionsMixin
from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
from hefesto_dualsense4unix.app.actions.input_actions import InputActionsMixin
from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin
from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin
from hefesto_dualsense4unix.app.actions.rumble_actions import RumbleActionsMixin
from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.app.actions.triggers_actions import TriggersActionsMixin
from hefesto_dualsense4unix.app.constants import ICON_PATH, MAIN_GLADE
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.app.ipc_bridge import profile_list, profile_switch
from hefesto_dualsense4unix.app.theme import apply_theme
from hefesto_dualsense4unix.app.tray import AppTray
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def _activate_window_by_pid(predecessor_pid: int) -> None:
    """Traz a janela do predecessor ao foco via xdotool; fallback via SIGUSR1.

    Tenta localizar o WID da janela com título contendo "Hefesto - Dualsense4Unix" associado ao
    `predecessor_pid`. Se encontrado, usa `xdotool windowactivate`. Caso xdotool
    não esteja disponível ou não retorne WID, envia SIGUSR1 ao predecessor — a
    GUI instala um handler que chama `GLib.idle_add(self.show_window)`.
    """
    wid: str | None = None
    try:
        result = subprocess.run(
            ["xdotool", "search", "--pid", str(predecessor_pid), "--name", "Hefesto - Dualsense4Unix"],  # noqa: E501
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
    InputActionsMixin,
    FirmwareActionsMixin,
    FooterActionsMixin,
):
    """Aplicação GTK do Hefesto - Dualsense4Unix."""

    def __init__(self) -> None:
        # BUG-TRAY-SINGLE-FLASH-01: "primeira vence" — traz predecessor ao foco
        # e sai limpo em vez de matá-lo (evita efeito "abre e fecha" no tray).
        from hefesto_dualsense4unix.utils.single_instance import acquire_or_bring_to_front

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

        apply_theme(self.window)

        self.window.set_title("Hefesto - Dualsense4Unix")
        self.window.set_wmclass("hefesto", "Hefesto-Dualsense4Unix")
        if ICON_PATH.exists():
            self.window.set_icon_from_file(str(ICON_PATH))

        self._install_banner_logo()

        self.tray: AppTray | None = None
        self._quitting = False

        # FEAT-PROFILE-STATE-01: draft central imutavel compartilhado por todos os mixins.
        # Populado com defaults seguros agora; sobrescrito por _load_draft_from_active_profile
        # apos daemon conectar (em show() e run()).
        self.draft: DraftConfig = DraftConfig.default()

        self.builder.connect_signals(self._signal_handlers())

    def _signal_handlers(self) -> dict[str, object]:
        return {
            "on_window_delete_event": self.on_window_delete_event,
            # Triggers
            "on_trigger_left_mode_changed": self.on_trigger_left_mode_changed,
            "on_trigger_right_mode_changed": self.on_trigger_right_mode_changed,
            "on_trigger_left_preset_changed": self.on_trigger_left_preset_changed,
            "on_trigger_right_preset_changed": self.on_trigger_right_preset_changed,
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
            "on_player_led_toggled": self.on_player_led_toggled,
            "on_player_leds_apply": self.on_player_leds_apply,
            # Rumble — política de intensidade (FEAT-RUMBLE-POLICY-01)
            "on_rumble_policy_economia": self.on_rumble_policy_economia,
            "on_rumble_policy_balanceado": self.on_rumble_policy_balanceado,
            "on_rumble_policy_max": self.on_rumble_policy_max,
            "on_rumble_policy_auto": self.on_rumble_policy_auto,
            "on_rumble_policy_slider_changed": self.on_rumble_policy_slider_changed,
            # Rumble — testar motores
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
            "on_profile_advanced_toggle": self.on_profile_advanced_toggle,
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
            # Mouse (aba "Mouse e Teclado")
            "on_mouse_toggle_set": self.on_mouse_toggle_set,
            "on_mouse_speed_changed": self.on_mouse_speed_changed,
            "on_mouse_scroll_speed_changed": self.on_mouse_scroll_speed_changed,
            # Teclado — key_bindings CRUD (FEAT-KEYBOARD-UI-01, lição 77.1)
            "on_key_binding_add": self.on_key_binding_add,
            "on_key_binding_remove": self.on_key_binding_remove,
            "on_key_binding_restore_defaults": self.on_key_binding_restore_defaults,
            # Firmware (FEAT-FIRMWARE-UPDATE-GUI-01)
            "on_firmware_check": self.on_firmware_check,
            "on_firmware_browse": self.on_firmware_browse,
            "on_firmware_apply": self.on_firmware_apply,
            # Rodapé — ações globais (UI-GLOBAL-FOOTER-ACTIONS-01)
            "on_apply_draft": self.on_apply_draft,
            "on_save_profile": self.on_save_profile,
            "on_import_profile": self.on_import_profile,
            "on_restore_default": self.on_restore_default,
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

        Ordem importa: chamamos `Gtk.main_quit()` ANTES do cleanup. O
        `tray.stop()` faz uma call síncrona via D-Bus que pode travar
        indefinidamente em ambientes sem StatusNotifierWatcher robusto
        (Pop Shell sem TopIcons, COSMIC alpha etc). Se travasse antes do
        `main_quit`, o loop GTK ficava preso e a GUI nunca encerrava. Ao
        quitar o loop primeiro e jogar o cleanup numa thread daemon, o
        processo sempre encerra mesmo se o cleanup nunca retornar.
        """
        self._quitting = True
        Gtk.main_quit()
        threading.Thread(target=self._shutdown_backend, daemon=True).start()

    def _shutdown_backend(self) -> None:
        """Cleanup pós-quit (tray + daemon systemd + daemon avulso).

        Pode travar sem reter o processo porque a thread é daemon.

        Ordem das ações (TRAY-QUIT-CLEAN-01):
          1. tray.stop() — remove ícone do painel.
          2. systemctl --user stop — encerra daemon gerenciado por systemd.
          3. Fallback: lê pid file canônico de `acquire_or_takeover("daemon")`
             e envia SIGTERM ao daemon avulso (não-systemd) com grace 3s,
             escalando para SIGKILL. Defesa anti-recycle via
             `is_hefesto_dualsense4unix_process`.

        Idempotência: se daemon já morreu pelo systemctl stop, `is_alive`
        retorna False e nada mais é feito.
        """
        try:
            if self.tray is not None:
                self.tray.stop()
        except Exception as exc:
            logger.warning("quit_app_tray_stop_falhou", erro=str(exc))
        try:
            subprocess.run(
                ["systemctl", "--user", "stop", "hefesto-dualsense4unix.service"],
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            logger.warning("quit_app_systemctl_falhou", erro=str(exc))

        # Fallback: daemon avulso (não-systemd) sobrevive ao stop acima.
        # Lê pid canônico que `acquire_or_takeover("daemon")` escreve em
        # daemon/main.py — existe mesmo quando o daemon não é systemd-managed.
        from hefesto_dualsense4unix.utils.single_instance import (
            is_alive,
            is_hefesto_dualsense4unix_process,
        )
        from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

        try:
            pid_path = runtime_dir() / "daemon.pid"
        except Exception as exc:
            logger.warning("quit_app_runtime_dir_falhou", erro=str(exc))
            return

        try:
            raw = pid_path.read_text(encoding="ascii").strip()
            pid = int(raw)
        except (FileNotFoundError, OSError, ValueError):
            return

        if pid <= 0 or not is_alive(pid):
            return

        if not is_hefesto_dualsense4unix_process(pid):
            logger.warning("quit_app_pid_recycle_detectado", pid=pid)
            return

        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("quit_app_daemon_avulso_sigterm", pid=pid)
        except ProcessLookupError:
            return
        except PermissionError as exc:
            logger.warning("quit_app_sigterm_perm", pid=pid, erro=str(exc))
            return

        # Espera grace 3s polling 100ms.
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if not is_alive(pid):
                logger.info("quit_app_daemon_avulso_encerrado", pid=pid)
                return
            time.sleep(0.1)

        try:
            os.kill(pid, signal.SIGKILL)
            logger.warning("quit_app_daemon_avulso_sigkill", pid=pid)
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            logger.warning("quit_app_sigkill_perm", pid=pid, erro=str(exc))

        # Garantia broad-stroke: mata tudo que ainda esteja com nome hefesto.
        # Cobre child Popen (não-systemd), GUIs zumbi de fork antigo, daemons
        # spawned por hotplug-gui, instâncias Flatpak. Idempotente — se já
        # morreu, pkill retorna 1 silente.
        for pat in ("hefesto_dualsense4unix", "hefesto-dualsense4unix daemon",
                    "br.andrefarias.Hefesto"):
            with contextlib.suppress(FileNotFoundError, subprocess.SubprocessError):
                subprocess.run(["pkill", "-KILL", "-f", pat],
                               capture_output=True, timeout=2, check=False)

    def show_window(self) -> None:
        self.window.show_all()
        self.window.present()

    # --- draft ---

    def _load_draft_from_active_profile(self) -> None:
        """Carrega DraftConfig a partir do perfil ativo via IPC.

        Tenta ``profile.get_active`` e depois ``daemon.state_full``. Se daemon
        offline ou perfil não encontrado, mantém o default seguro em self.draft.
        Executado em thread worker (chamado via ThreadPoolExecutor); nunca
        bloqueia a thread GTK.
        """
        from hefesto_dualsense4unix.app.ipc_bridge import daemon_state_full
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles

        try:
            state = daemon_state_full()
            active_name: str | None = None
            if state is not None:
                active_name = state.get("active_profile")

            if active_name:
                try:
                    profile = next(
                        p for p in load_all_profiles() if p.name == active_name
                    )
                    self.draft = DraftConfig.from_profile(profile)
                    logger.info(
                        "draft_carregado_do_perfil_ativo",
                        perfil=active_name,
                    )
                    return
                except StopIteration:
                    logger.warning(
                        "draft_perfil_ativo_nao_encontrado_em_disco",
                        perfil=active_name,
                    )
        except Exception as exc:
            logger.warning("draft_load_falhou", erro=str(exc))

        logger.info("draft_usando_defaults_seguros")

    def _on_notebook_switch_page(
        self, _notebook: object, _page: object, page_num: int
    ) -> None:
        """Dispara refresh de widgets da aba destino ao trocar de aba.

        Cada mixin implementa ``_refresh_widgets_from_draft()``; a chamada e
        protegida por ``_guard_refresh`` internamente para evitar loop.
        A correspondencia entre page_num e o mixin e baseada na ordem das abas
        no GtkNotebook definida no Glade.

        Páginas (indice zero, ordem do notebook):
          0 = Status, 1 = Triggers, 2 = Lightbar, 3 = Rumble,
          4 = Perfis, 5 = Daemon, 6 = Emulacao, 7 = Mouse
        """
        refresh_map = {
            1: getattr(self, "_refresh_triggers_from_draft", None),
            2: getattr(self, "_refresh_lightbar_from_draft", None),
            3: getattr(self, "_refresh_rumble_from_draft", None),
            7: getattr(self, "_refresh_mouse_from_draft", None),
        }
        fn = refresh_map.get(page_num)
        if fn is not None:
            fn()

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
        self.install_input_tab()
        self.install_firmware_tab()
        # Conecta switch-page do GtkNotebook para refresh de draft por aba.
        notebook = self.builder.get_object("main_notebook")
        if notebook is not None:
            notebook.connect("switch-page", self._on_notebook_switch_page)
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
            self.install_input_tab()
            # Conecta switch-page do GtkNotebook para refresh de draft por aba.
            notebook = self.builder.get_object("main_notebook")
            if notebook is not None:
                notebook.connect("switch-page", self._on_notebook_switch_page)
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
