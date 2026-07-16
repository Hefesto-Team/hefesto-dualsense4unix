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
from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin
from hefesto_dualsense4unix.app.actions.input_actions import InputActionsMixin
from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin
from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin
from hefesto_dualsense4unix.app.actions.rumble_actions import RumbleActionsMixin
from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.app.actions.triggers_actions import TriggersActionsMixin
from hefesto_dualsense4unix.app.compact_window import CompactWindow
from hefesto_dualsense4unix.app.compact_window import is_enabled as compact_window_enabled
from hefesto_dualsense4unix.app.constants import ICON_PATH, MAIN_GLADE
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.app.ipc_bridge import profile_list, profile_switch
from hefesto_dualsense4unix.app.theme import apply_theme
from hefesto_dualsense4unix.app.tray import AppTray, _desktop_is_cosmic
from hefesto_dualsense4unix.integrations.desktop_notifications import (
    statusnotifierwatcher_available,
)
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
    HomeActionsMixin,
    StatusActionsMixin,
    TriggersActionsMixin,
    LightbarActionsMixin,
    RumbleActionsMixin,
    ProfilesActionsMixin,
    DaemonActionsMixin,
    EmulationActionsMixin,
    InputActionsMixin,
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

        # SIGUSR2: pedido externo de "quit" — equivalente ao clique 'Sair' do tray.
        # Útil para automação de testes do caminho de shutdown limpo
        # (BUG-GUI-QUIT-RESIDUAL-01 #32) sem requerer interação com cosmic-panel.
        signal.signal(signal.SIGUSR2, lambda _sig, _frame: GLib.idle_add(self.quit_app))

        # BUG-GUI-IGNORES-SIGTERM-DURING-DIALOG-01: SIGTERM/SIGINT robusto
        # com fallback two-strikes + watchdog.
        # Quando um Gtk.MessageDialog modal está aberto (`dialog.run()`
        # bloqueia a thread principal), o GLib mainloop não processa idle
        # callbacks — um `quit_app` agendado via `GLib.idle_add` fica
        # enfileirado e nunca executa. Three defenses:
        #   1. Chama `Gtk.main_quit()` DIRETO no handler (thread-safe via
        #      gdk_threads, executa mesmo com mainloop "ocupado").
        #   2. Agenda `quit_app` via idle_add para o caminho com cleanup.
        #   3. Arma timer 2s: se ainda vivo, força `os._exit(128+sig)`.
        # Plus: chamada 2ª SIGTERM em <5s pula direto para hard exit
        # (cobre o caso em que o mainloop está em D-state — idle nunca roda).
        self._last_term_signal_at: float = 0.0

        def _on_term_signal(sig: int, _frame: object) -> None:
            now = time.monotonic()
            if now - self._last_term_signal_at < 5.0:
                # 2ª chamada em <5s: hard exit, bypass do mainloop.
                logger.warning("gui_hard_exit_via_signal_repeat", sig=sig)
                os._exit(128 + sig)
            self._last_term_signal_at = now
            logger.info("gui_signal_quit_solicitado", sig=sig)
            # Defesa 1: main_quit direto (não passa pelo idle loop).
            with contextlib.suppress(Exception):
                Gtk.main_quit()
            # Defesa 2: idle_add para o caminho de cleanup completo.
            GLib.idle_add(self.quit_app)
            # Defesa 3: watchdog — se ainda vivo após 2s, force.
            def _watchdog() -> None:
                time.sleep(2.0)
                logger.warning("gui_hard_exit_via_watchdog", sig=sig)
                os._exit(128 + sig)
            threading.Thread(
                target=_watchdog, daemon=True, name="hefesto-gui-term-watchdog"
            ).start()

        signal.signal(signal.SIGTERM, _on_term_signal)
        signal.signal(signal.SIGINT, _on_term_signal)

        self.builder = Gtk.Builder()
        # FEAT-I18N-INFRASTRUCTURE-01 (v3.4.0): vincula o builder ao mesmo
        # domínio gettext usado pelo `_()` do Python. Labels com
        # `translatable="yes"` no Glade resolvem via locale ativo
        # (init_locale() em app/main.py).
        from hefesto_dualsense4unix.utils.i18n import TEXTDOMAIN

        self.builder.set_translation_domain(TEXTDOMAIN)
        if not MAIN_GLADE.exists():
            raise FileNotFoundError(f"main.glade não encontrado em {MAIN_GLADE}")
        self.builder.add_from_file(str(MAIN_GLADE))

        self.window = self.builder.get_object("main_window")
        if self.window is None:
            raise RuntimeError("main_window não encontrada em main.glade")

        apply_theme(self.window)

        # BUG-FOOTER-CORTADO: envolve as abas sem scroll num GtkScrolledWindow para
        # a janela poder encolher e o rodapé (Aplicar/Salvar/...) nunca ser cortado
        # sob tiling do COSMIC (que ignora a largura/altura mínima da janela).
        self._wrap_notebook_pages_in_scroll()

        self.window.set_title("Hefesto - Dualsense4Unix")
        # BUG-DOCK-ICON-WMCLASS-MISMATCH-01 (v3.4.3): WM_CLASS instance
        # tem que casar com basename do .desktop (`hefesto-dualsense4unix.
        # desktop`) para a dock COSMIC / GNOME associar o ícone do app.
        # Antes era `("hefesto", "Hefesto-Dualsense4Unix")` — instance
        # não casava e a dock mostrava ícone genérico.
        self.window.set_wmclass(
            "hefesto-dualsense4unix", "Hefesto-Dualsense4Unix"
        )
        if ICON_PATH.exists():
            self.window.set_icon_from_file(str(ICON_PATH))

        self._install_banner_logo()

        self.tray: AppTray | None = None
        # FEAT-COMPACT-WINDOW-FALLBACK-01 (v3.3.0): surrogate de tray
        # quando AppIndicator/StatusNotifierWatcher ausente (COSMIC).
        self.compact_window: CompactWindow | None = None
        self._quitting = False

        # FEAT-PROFILE-STATE-01: draft central imutavel compartilhado por todos os mixins.
        # Populado com defaults seguros agora; sobrescrito por _bootstrap_draft_async
        # apos daemon conectar (em show() e run()) — BUG-DRAFT-NEVER-LOADED-01.
        self.draft: DraftConfig = DraftConfig.default()
        # Nome do perfil ativo (preenchido pelo bootstrap do draft). Usado pelo
        # rodapé "Salvar Perfil" para pré-preencher o nome — BUG-FOOTER-ACTIVE-NAME-01.
        self._active_profile_name: str = ""

        self.builder.connect_signals(self._signal_handlers())

    def _signal_handlers(self) -> dict[str, object]:
        return {
            "on_window_delete_event": self.on_window_delete_event,
            # Triggers — os handlers de MODO (on_trigger_*_mode_changed) NÃO entram
            # aqui: FEAT-DSX-COMBO-TO-SEGMENTED-01 troca o combo por SegmentedSelector
            # e conecta "changed" no código (install_triggers_tab), não pelo Glade.
            # FIX-GUI-COSMIC-REMEDIATION-01 (B3): on_trigger_left/right_preset_changed
            # removidos daqui — o glade não os referencia e a ligação é feita em
            # código (triggers_actions.py), então as entradas estavam mortas.
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
            "on_player_leds_preset_p3": self.on_player_leds_preset_p3,
            "on_player_leds_preset_p4": self.on_player_leds_preset_p4,
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
            "on_rumble_passthrough": self.on_rumble_passthrough,
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
            # on_daemon_restart removido: botão "Reiniciar" redundante saiu do glade
            # (GUI-ESTABILIDADE-COSMIC-REMEDIATION-01 T5). Caminho único de restart é
            # on_daemon_service_restart (btn_restart_daemon).
            "on_daemon_refresh": self.on_daemon_refresh,
            "on_daemon_view_logs": self.on_daemon_view_logs,
            "on_daemon_autostart_toggled": self.on_daemon_autostart_toggled,
            "on_daemon_service_restart": self.on_daemon_service_restart,
            "on_daemon_migrate_to_systemd": self.on_daemon_migrate_to_systemd,
            # Anti-storm / sistema (FEAT-DSX-UNIFY-01)
            "on_storm_fix_safe": self.on_storm_fix_safe,
            # SPRINT-GAME-RUMBLE-01 + DEDUP-04: copia a Opção de Inicialização
            # da Steam (agora a string CONSTANTE do wrapper hefesto-launch).
            "on_storm_copy_launch": self.on_storm_copy_launch,
            # DEDUP-05: migração assistida — troca as opções antigas do
            # Hefesto pela chamada do wrapper nos localconfig.vdf.
            "on_steam_apply_launch": self.on_steam_apply_launch,
            # Emulação
            "on_emulation_refresh": self.on_emulation_refresh,
            "on_emulation_test_device": self.on_emulation_test_device,
            "on_emulation_open_toml": self.on_emulation_open_toml,
            # Emulação — microfone do DualSense
            "on_emulation_mic_on": self.on_emulation_mic_on,
            "on_emulation_mic_off": self.on_emulation_mic_off,
            # Emulação — gamepad virtual com máscara (FEAT-DSX-GAMEPAD-FLAVOR-01)
            "on_emulation_gamepad_off": self.on_emulation_gamepad_off,
            "on_emulation_gamepad_dualsense": self.on_emulation_gamepad_dualsense,
            "on_emulation_gamepad_xbox": self.on_emulation_gamepad_xbox,
            # Emulação — modo jogo (pausar/retomar)
            "on_emulation_pause": self.on_emulation_pause,
            "on_emulation_resume": self.on_emulation_resume,
            # Emulação — Steam Input (verificar/desligar)
            "on_emulation_steam_input_check": self.on_emulation_steam_input_check,
            "on_emulation_steam_input_disable": self.on_emulation_steam_input_disable,
            # Mouse (aba "Mouse e Teclado")
            "on_mouse_toggle_set": self.on_mouse_toggle_set,
            "on_mouse_speed_changed": self.on_mouse_speed_changed,
            "on_mouse_scroll_speed_changed": self.on_mouse_scroll_speed_changed,
            # Teclado — key_bindings CRUD (FEAT-KEYBOARD-UI-01, lição 77.1)
            "on_key_binding_add": self.on_key_binding_add,
            "on_key_binding_remove": self.on_key_binding_remove,
            "on_key_binding_restore_defaults": self.on_key_binding_restore_defaults,
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
        # Esconde pro tray apenas se há acesso persistente REAL (ícone de
        # bandeja utilizável OU janela compacta opt-in ativa). Sem isso,
        # fechar = encerrar — senão o app ficaria órfão e invisível no COSMIC
        # sem o applet de status (BUG-COMPACT-WINDOW-ORPHAN-ON-CLOSE-01).
        if self._has_persistent_access():
            self.window.hide()
            return True
        Gtk.main_quit()
        return False

    def _has_persistent_access(self) -> bool:
        """True se o usuário consegue reabrir/controlar o app após fechar a
        janela principal.

        Acesso persistente = janela compacta ativa OU ícone de bandeja
        realmente visível. Em COSMIC o indicator só aparece com o
        StatusNotifierWatcher (cosmic-applet-status-area) presente; sem ele,
        esconder a janela deixaria o app inacessível.
        """
        if self.compact_window is not None:
            return True
        if self.tray is None or not self.tray.is_available():
            return False
        # Em COSMIC o indicator só é visível com o StatusNotifierWatcher
        # (cosmic-applet-status-area) presente; fora do COSMIC, basta o tray.
        if _desktop_is_cosmic():
            return statusnotifierwatcher_available()
        return True

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

    def _start_notification_action_listener(self) -> None:
        """Listener D-Bus para ActionInvoked das notificações (v3.3.0).

        FEAT-NOTIFY-ACTION-OPEN-01: quando o usuário clica em "Abrir
        Hefesto" no botão de uma notificação (controlador desconectado,
        bateria baixa), restaura a janela principal via GLib.idle_add.

        Implementação: thread daemon que consome sinais
        `org.freedesktop.Notifications::ActionInvoked` via jeepney sync.
        Silenciosa em falhas (jeepney ausente, D-Bus indisponível) —
        notificações continuam funcionando sem o listener.
        """

        def _worker() -> None:
            try:
                from jeepney import MatchRule
                from jeepney.bus_messages import message_bus
                from jeepney.io.blocking import open_dbus_connection
            except ImportError:
                logger.debug("notify_action_listener_jeepney_missing")
                return

            try:
                conn = open_dbus_connection(bus="SESSION")
            except Exception as exc:
                logger.debug("notify_action_listener_connect_failed", err=str(exc))
                return

            try:
                rule = MatchRule(
                    type="signal",
                    interface="org.freedesktop.Notifications",
                    member="ActionInvoked",
                    path="/org/freedesktop/Notifications",
                )
                conn.send_and_get_reply(message_bus.AddMatch(rule))
                logger.info("notify_action_listener_started")
                while not self._quitting:
                    try:
                        msg = conn.receive(timeout=1.0)
                    except Exception:
                        continue
                    if msg is None or msg.header.message_type.name != "signal":
                        continue
                    if msg.header.fields.get(3) != "ActionInvoked":  # MEMBER
                        continue
                    body: Any = msg.body or ()
                    # body = (notification_id: u, action_key: s)
                    if not isinstance(body, tuple) or len(body) < 2:
                        continue
                    if body[1] == "open":
                        logger.info("notify_action_open_invoked")
                        GLib.idle_add(self.show_window)
            except Exception as exc:
                logger.debug("notify_action_listener_loop_failed", err=str(exc))
            finally:
                with contextlib.suppress(Exception):
                    conn.close()

        # GLib import só aqui — listener é opt-in via runtime.
        from gi.repository import GLib

        threading.Thread(
            target=_worker,
            daemon=True,
            name="hefesto-notify-action-listener",
        ).start()

    # --- draft ---

    def _compute_draft_from_active_profile(self) -> tuple[DraftConfig | None, str]:
        """Calcula o DraftConfig do perfil ativo via IPC + disco. SEM efeitos colaterais.

        Roda em thread worker (faz IPC ``daemon.state_full`` + I/O de disco
        ``load_all_profiles``); NUNCA toca ``self.draft`` nem widgets — a thread
        GTK aplica o resultado em ``_bootstrap_draft_async`` via GLib.idle_add.

        Retorna ``(draft, active_name)``; ``(None, "")`` se daemon offline ou
        perfil não encontrado (o chamador mantém o default seguro).
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
                    logger.info("draft_carregado_do_perfil_ativo", perfil=active_name)
                    draft = DraftConfig.from_profile(profile)
                    # BUG-MOUSE-GUI-SYNC-01 (A1): sobrepõe o bloco VIVO do daemon
                    # (emulação ligada por CLI/applet/flag de boot) para a aba
                    # Mouse não mentir. Overlay programático NÃO marca dirty.
                    # BUG-MOUSE-OVERLAY-CLOBBERS-SECTION-01: SÓ para perfis SEM
                    # seção mouse (``in_profile`` False). Quando o perfil TEM seção
                    # mouse (point_and_click), o overlay do estado vivo era
                    # persistido por cima do valor do perfil ao Salvar — se o lock
                    # manual tivesse bloqueado a ativação, o vivo (off/6) sobrescrevia
                    # o perfil (on/8). Para perfil COM seção, a aba mostra o valor do
                    # PERFIL (= o que será salvo); a edição explícita da aba (dirty)
                    # é o caminho para mudar a seção.
                    me = state.get("mouse_emulation") if state is not None else None
                    if isinstance(me, dict) and not draft.mouse.in_profile:
                        try:
                            allowed = {"enabled", "speed", "scroll_speed"}
                            overlay = {k: v for k, v in me.items() if k in allowed}
                            draft = draft.model_copy(
                                update={"mouse": draft.mouse.model_copy(update=overlay)}
                            )
                        except Exception as exc:
                            logger.warning(
                                "draft_overlay_mouse_invalido", erro=str(exc)
                            )
                    return draft, active_name
                except StopIteration:
                    logger.warning(
                        "draft_perfil_ativo_nao_encontrado_em_disco",
                        perfil=active_name,
                    )
        except Exception as exc:
            logger.warning("draft_load_falhou", erro=str(exc))

        logger.info("draft_usando_defaults_seguros")
        return None, ""

    def _bootstrap_draft_async(self) -> None:
        """Carrega o draft do perfil ativo em worker e aplica na thread GTK.

        BUG-DRAFT-NEVER-LOADED-01: antes ``_load_draft_from_active_profile`` era
        código morto — nunca chamado — então ``self.draft`` ficava em
        ``DraftConfig.default()`` a sessão inteira. Consequência: o rodapé
        "Salvar Perfil" gravava defaults por cima do perfil ativo (perda de dados)
        e "Aplicar" resetava o hardware. Disparado ao final de ``show()`` e do
        ramo oculto de ``run()``, após o daemon estar (ou começar a) rodar.
        """
        from hefesto_dualsense4unix.app import ipc_bridge
        from hefesto_dualsense4unix.app.actions.footer_actions import _refresh_all_tabs

        def _apply(result: tuple[DraftConfig | None, str]) -> bool:
            draft, active_name = result
            if draft is not None:
                self.draft = draft
                self._active_profile_name = active_name
                _refresh_all_tabs(self)
            return False  # GLib.idle_add não repete

        ipc_bridge.run_in_thread(
            self._compute_draft_from_active_profile,
            on_success=_apply,
        )

    def _on_notebook_switch_page(
        self, _notebook: object, _page: object, page_num: int
    ) -> None:
        """Dispara refresh de widgets da aba destino ao trocar de aba.

        Cada mixin implementa ``_refresh_widgets_from_draft()``; a chamada e
        protegida por ``_guard_refresh`` internamente para evitar loop.
        A correspondencia entre page_num e o mixin e baseada na ordem das abas
        no GtkNotebook definida no Glade.

        Páginas (indice zero, ordem do notebook — FEAT-GUI-HOME-TAB-01
        acrescentou "Início" como página 0, deslocando as demais):
          0 = Início, 1 = Status, 2 = Triggers, 3 = Lightbar, 4 = Rumble,
          5 = Perfis, 6 = Sistema, 7 = Emulacao, 8 = Mouse, 9 = Teclado
        """
        refresh_map = {
            # FEAT-GUI-HOME-TAB-01: comutador de modo reconcilia ao ser exibido.
            0: getattr(self, "_refresh_home_tab", None),
            2: getattr(self, "_refresh_triggers_from_draft", None),
            3: getattr(self, "_refresh_lightbar_from_draft", None),
            4: getattr(self, "_refresh_rumble_from_draft", None),
            # BUG-PROFILES-ACTIVE-STALE-01: autoswitch/hotkey trocam o perfil
            # sem passar pela GUI — re-marcar o ativo (negrito) ao exibir a aba.
            5: getattr(self, "_sync_selection_with_active_profile", None),
            # BUG-DAEMON-TAB-STALE-01: status do daemon re-renderiza ao entrar
            # na aba (daemon pode ter subido/caído por fora via CLI/systemd).
            # M7 (auditoria): também reavalia o cartão anti-storm ao exibir a aba.
            6: getattr(self, "_refresh_daemon_tab_on_show", None),
            # BUG-EMULATION-TAB-NO-REFRESH-01 (T3): a aba Emulação se
            # reconcilia ao ser exibida — se o daemon subiu após o boot, a aba
            # deixava de mostrar "—"/offline só ao entrar nela. _refresh_emulation_tab
            # é criado em emulation_actions.py (Sprint 4); getattr é seguro se ausente.
            7: getattr(self, "_refresh_emulation_tab", None),
            # BUG-MOUSE-GUI-SYNC-01 (A1): a aba Mouse sincroniza também com o
            # estado VIVO do daemon (draft imediato + state_full assíncrono).
            8: getattr(self, "_refresh_mouse_tab", None),
            # BUG-KEYBOARD-TAB-NO-REFRESH-01: aba Teclado também precisa
            # re-sincronizar os bindings do draft ao ser exibida.
            9: getattr(self, "_refresh_key_bindings_from_draft", None),
        }
        fn = refresh_map.get(page_num)
        if fn is not None:
            fn()

    # --- run ---

    def _wrap_notebook_pages_in_scroll(self) -> None:
        """Torna as abas roláveis para o RODAPÉ nunca ser cortado (BUG-FOOTER-CORTADO).

        O `GtkNotebook` pede como altura mínima o MAIOR mínimo entre TODAS as
        páginas (medido: ~606px, puxado por Perfis/Emulação). Sob tiling do COSMIC
        — que ignora `width/height-request` da janela — a janela não encolhe abaixo
        de header+notebook+rodapé e o rodapé de ações (Aplicar/Salvar Perfil/
        Importar/Restaurar) é empurrado para fora da área visível.

        Envolvendo cada página num `GtkScrolledWindow` (scroll vertical), o mínimo
        da página cai para ~0 e o rodapé fica SEMPRE visível, em qualquer tamanho
        de janela. Exceção: a aba **Sistema** (`daemon_box`), cujo conteúdo
        principal já é um `GtkScrolledWindow` (o log) com auto-scroll — envolvê-la
        de novo quebraria essa rolagem; o mínimo dela já é pequeno. Idempotente.
        """
        notebook = self.builder.get_object("main_notebook")
        if notebook is None:
            return
        # EST-10: identificar a aba pelo WIDGET, não pelo texto visível. O `skip`
        # era `{"Daemon"}` comparado com `label.get_text()` — renomear a aba (o
        # SPRINT-LEIGO-01 troca "Daemon" por "Sistema") faria o skip parar de
        # casar em silêncio, envolvendo o log num segundo ScrolledWindow e
        # quebrando o auto-scroll. O id do Glade não muda quando o rótulo muda.
        skip_pages = {
            page
            for page in (self.builder.get_object("daemon_box"),)  # log com scroll próprio
            if page is not None
        }
        pages: list[tuple[Any, Any]] = []
        while notebook.get_n_pages() > 0:
            page = notebook.get_nth_page(0)
            label = notebook.get_tab_label(page)  # ref mantém o widget vivo
            notebook.remove_page(0)
            pages.append((page, label))
        for page, label in pages:
            if page not in skip_pages and not isinstance(page, Gtk.ScrolledWindow):
                scroller = Gtk.ScrolledWindow()
                scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                scroller.set_propagate_natural_width(True)
                scroller.set_propagate_natural_height(True)
                scroller.add(page)
                scroller.show_all()
                notebook.append_page(scroller, label)
            else:
                notebook.append_page(page, label)

    def show(self) -> None:
        # FIX-GUI-COSMIC-REMEDIATION-01 (R1 — janela preta): instalar TODAS as
        # abas + conectar switch-page ANTES de window.show_all(). Antes o
        # show_all() vinha primeiro e os install_*_tab() reparentavam/rebuildavam
        # widgets dinâmicos (sticks, grid de glyphs, SegmentedSelectors) DEPOIS
        # do mapa — a race de primeiro-frame do XWayland+NVIDIA no COSMIC
        # apresentava um buffer ainda não pintado (janela totalmente preta).
        self.install_home_tab()
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
        self.window.show_all()
        self._force_initial_repaint()
        # BUG-DAEMON-AUTOSTART-01: dispara start do daemon em thread worker
        # se a unit está instalada mas o service não está ativo. Jamais
        # bloqueia a thread GTK; falha silenciosa via logger.warning.
        self.ensure_daemon_running()
        # BUG-DRAFT-NEVER-LOADED-01: carrega o draft do perfil ativo (worker).
        self._bootstrap_draft_async()

    def _force_initial_repaint(self) -> None:
        """Contorna a race de primeiro-frame XWayland+NVIDIA no COSMIC: injeta um
        damage total ~60ms após o mapa para o compositor apresentar o buffer."""
        from gi.repository import GLib

        def _kick() -> bool:
            gdkwin = self.window.get_window()
            if gdkwin is not None:
                gdkwin.invalidate_rect(None, True)
            self.window.queue_draw()
            return False  # one-shot

        GLib.timeout_add(60, _kick)

    def _compact_state_snapshot(self) -> dict[str, Any] | None:
        """Snapshot síncrono de `daemon.state_full` para a CompactWindow.

        FEAT-COMPACT-WINDOW-FALLBACK-01: chamada do tick periódico da
        janela compacta. Reusa `ipc_bridge.daemon_state_full()` que já
        timeout-protege a chamada IPC. None se daemon offline.
        """
        from hefesto_dualsense4unix.app.ipc_bridge import daemon_state_full

        try:
            return daemon_state_full()
        except Exception as exc:
            logger.debug("compact_state_fetch_failed", err=str(exc))
            return None

    def run(self, *, start_hidden: bool = False) -> None:
        self.tray = AppTray(
            on_show_window=self.show_window,
            on_quit=self.quit_app,
            on_list_profiles=profile_list,
            on_switch_profile=profile_switch,
            # FEAT-DSX-MULTI-CONTROLLER-01: status item mostra "N controles".
            on_state=self._compact_state_snapshot,
        )
        self.tray.start()
        # FEAT-COMPACT-WINDOW-FALLBACK-01: a janela compacta agora é OPT-IN
        # (HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW=1). Por padrão NÃO aparece —
        # a versão "always-on-top sem moldura" no COSMIC era intrusiva. Sem
        # tray, o caminho é o applet "Área de status" (Configurações > Painel)
        # ou a janela principal; fechar a principal encerra o app quando não
        # há bandeja real (ver _has_persistent_access), evitando órfão.
        if compact_window_enabled():
            self.compact_window = CompactWindow(
                on_show_window=self.show_window,
                on_quit=self.quit_app,
                on_list_profiles=profile_list,
                on_switch_profile=profile_switch,
                on_state=self._compact_state_snapshot,
            )
            if self.compact_window.start():
                logger.info("compact_window_active", reason="opt_in")

        # FEAT-NOTIFY-ACTION-OPEN-01 (v3.3.0): listener para botões
        # "Abrir Hefesto" das notificações D-Bus (controlador desconectado,
        # bateria baixa). Best-effort: silencioso se jeepney/D-Bus offline.
        self._start_notification_action_listener()
        if start_hidden and self.tray.is_available():
            # BUG-HOME-TAB-HIDDEN-INSTALL-01: sem instalar a Início aqui, abrir
            # a janela depois (show_window) deixava a página 0 em branco.
            self.install_home_tab()
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
            # BUG-DRAFT-NEVER-LOADED-01: carrega o draft do perfil ativo (worker).
            self._bootstrap_draft_async()
            logger.info("hefesto_start_hidden")
        else:
            self.show()
        Gtk.main()


def main() -> None:
    app = HefestoApp()
    app.run()


if __name__ == "__main__":
    main()
