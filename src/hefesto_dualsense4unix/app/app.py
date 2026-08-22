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
from typing import Any, ClassVar

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, Gtk

from hefesto_dualsense4unix.app.actions.carona_do_wrapper import GESTO_APLICAR
from hefesto_dualsense4unix.app.actions.config_actions import (
    ABA_CONFIG,
    ConfigActionsMixin,
)
from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin
from hefesto_dualsense4unix.app.actions.emulation_actions import EmulationActionsMixin
from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin, id_da_pagina
from hefesto_dualsense4unix.app.actions.input_actions import InputActionsMixin
from hefesto_dualsense4unix.app.actions.launch_wrapper_dialog import (
    LaunchWrapperDialogMixin,
)
from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin
from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin
from hefesto_dualsense4unix.app.actions.rumble_actions import RumbleActionsMixin
from hefesto_dualsense4unix.app.actions.status_actions import ABA_STATUS, StatusActionsMixin
from hefesto_dualsense4unix.app.actions.triggers_actions import TriggersActionsMixin
from hefesto_dualsense4unix.app.compact_window import CompactWindow
from hefesto_dualsense4unix.app.compact_window import is_enabled as compact_window_enabled
from hefesto_dualsense4unix.app.constants import ICON_PATH, MAIN_GLADE
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.app.ipc_bridge import profile_list, profile_switch
from hefesto_dualsense4unix.app.theme import apply_theme
from hefesto_dualsense4unix.app.tray import AppTray, _desktop_is_cosmic
from hefesto_dualsense4unix.app.widgets.controller_card import (
    LARGURA_CARD_ELASTICA,
    CaixaDeTetoElastico,
)
from hefesto_dualsense4unix.integrations.desktop_notifications import (
    statusnotifierwatcher_available,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: JANELA-FIEL-01/E1: prazo do latch `_draft_reload_inflight` — seis ticks do
#: poller de 2 Hz. Mesma receita (e mesma lição) do `_home_inflight` da aba
#: Início: sem prazo, um worker que NUNCA volta prende o latch para sempre e a
#: janela para de reconciliar em silêncio, seguindo a editar e a salvar o perfil
#: ANTERIOR pelo resto da sessão. O prazo é lido no próprio tick, por carimbo de
#: tempo — sem thread nem timer novo.
DRAFT_RELOAD_INFLIGHT_TIMEOUT_S = 3.0


class CaixaDeTetoDePagina(CaixaDeTetoElastico):
    """O teto elástico do card, com a ALTURA contada na largura cortada.

    LARGURA-01/E4-E5. A `CaixaDeTetoElastico` corta a alocação de largura e
    devolve o excedente como margem, mas continua respondendo à pergunta de
    altura pela largura CHEIA — e a diferença entre as duas é conteúdo que
    ninguém alcança.

    Medido nesta bancada, aba Lightbar com a janela em 1920: a página informa
    440px de altura (calculados sobre 1894px de largura) e o conteúdo, já
    cortado em 1400px, precisa de 484px. Um parágrafo que cabia em duas linhas
    na largura cheia passa a ocupar três na cortada; os 44px de diferença são
    exatamente o custo em altura que a sprint mediu para esta aba.

    Enquanto a janela é alta, ninguém vê. Numa janela larga e BAIXA — o caso
    do tiling do COSMIC, que é a razão de as páginas serem roláveis
    (BUG-FOOTER-CORTADO) — o rolador dimensiona a barra pelo número informado
    e os 44px finais ficam abaixo do corte, sem barra que chegue até eles.

    Só a pergunta muda; o corte da alocação continua sendo o da classe base,
    que é o mecanismo que a SOM-01 mediu e que o card usa.
    """

    def do_get_preferred_height_for_width(self, largura: int) -> tuple[int, int]:
        return Gtk.Bin.do_get_preferred_height_for_width(  # type: ignore[no-any-return]
            self, min(largura, LARGURA_CARD_ELASTICA)
        )


class EstadoIndisponivelError(Exception):
    """A leitura de `daemon.state_full` não voltou — dá para tentar de novo.

    JANELA-FIEL-01/E1: `_compute_draft_from_active_profile` devolvia `(None, "")`
    para duas coisas que não são a mesma: o daemon não ter respondido
    (TRANSITÓRIO — o socket some quando ele cai ou reinicia, e o timeout é de
    0,25 s) e o perfil ativo não existir em disco (PERMANENTE). Sem distinguir,
    ou o latch de reconciliação ficava preso no primeiro caso, ou soltá-lo
    reabria o loop de IPC+I/O a 2 Hz no segundo.
    """


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
    LaunchWrapperDialogMixin,
    StatusActionsMixin,
    TriggersActionsMixin,
    LightbarActionsMixin,
    RumbleActionsMixin,
    ProfilesActionsMixin,
    DaemonActionsMixin,
    EmulationActionsMixin,
    InputActionsMixin,
    FooterActionsMixin,
    ConfigActionsMixin,
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
        # R-08 (auditoria 23/07): reconciliação do draft com o perfil ATIVO.
        # O bootstrap só rodava em show()/run(), e o perfil muda por quatro
        # caminhos que a GUI conhece (botão Ativar, tray, hotkey PS+D-pad e o
        # AUTOSWITCH ao abrir o jogo). Sem recarregar, as abas passavam a
        # editar e salvar o perfil ERRADO — e o "Aplicar" do rodapé empurrava
        # as seções do perfil antigo por cima do perfil do jogo.
        #
        # `_draft_reload_for` guarda o nome pelo qual o último recarregamento
        # foi DISPARADO, e é marcado ANTES do disparo. Deliberadamente separado
        # de `_active_profile_name`: aquele só é escrito quando o draft carrega
        # com sucesso, então um perfil ativo que não existe em disco o deixaria
        # stale e o tick de 2 Hz redispararia IPC+I/O para sempre.
        #
        # JANELA-FIEL-01/E1: o latch só continua marcado quando a tentativa
        # PROVOU que não adianta repetir (o daemon respondeu e o perfil não está
        # em disco). Falha de leitura de estado — `EstadoIndisponivelError` — o
        # solta, porque ali nada foi provado; e o `_draft_reload_inflight` tem
        # prazo, para o caso de o worker não voltar nunca.
        self._draft_reload_for: str | None = None
        self._draft_reload_inflight: bool = False
        self._draft_reload_inflight_since: float = 0.0
        # Snapshot do draft como ele veio do disco. `draft != baseline` é a
        # definição de "edição pendente" — o gate que impede a reconciliação de
        # jogar fora o trabalho dela sem avisar.
        self._draft_baseline: DraftConfig | None = None

        self.builder.connect_signals(self._signal_handlers())

    def _signal_handlers(self) -> dict[str, object]:
        return {
            "on_window_delete_event": self.on_window_delete_event,
            # Triggers — os handlers de MODO (on_trigger_*_mode_changed) NÃO entram
            # aqui: FEAT-DSX-COMBO-TO-SEGMENTED-01 troca o combo por SegmentedSelector
            # e conecta "changed" no código (install_triggers_tab), não pelo Glade.
            # FIX-GUI-COSMIC-REMEDIATION-01 (B3): on_trigger_left/right_preset_changed
            # removidos daqui — o glade não os referencia e a ligação é feita em  # (noqa-acento)
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
            # ONDA-U (U3-B): "on_profile_row_activated" foi REMOVIDO junto com
            # o handler no mixin e o binding "row-activated" do glade (ver
            # profiles_actions.py) — duplo-clique não ativa mais o perfil.
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
            # PLAT-01: trava o CompatToolMapping da Steam na versão de Proton
            # validada pelo Hefesto (contrato integrations/proton_pin).
            "on_proton_lock": self.on_proton_lock,
            # Emulação
            "on_emulation_refresh": self.on_emulation_refresh,
            "on_emulation_test_device": self.on_emulation_test_device,
            # BOTÃO-QUE-NÃO-MENTE-01 (entregas 5 e 6): o
            # "on_emulation_open_toml" saiu daqui junto com o método. O botão
            # dele já tinha saído do glade na entrega 3; o nome sobrevivia
            # neste mapa apontando para um handler que ninguém podia chamar.

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
            # EMULACAO-NO-JOGO-01/E1: o interruptor do teclado emulado. Sem esta
            # entrada o `<signal>` do glade vira botão MORTO em silêncio — é o
            # BUG-GUI-EMULATION-HANDLERS-UNWIRED-01 ("clico e não aplica").
            "on_keyboard_toggle_set": self.on_keyboard_toggle_set,
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

    # --- tick de estado ---

    def _render_slow_state(self, state: dict[str, Any]) -> None:
        """Tick lento (2 Hz) da aba Status + lembrete do wrapper (DEDUP-05).

        Zero timers novos: o diálogo "1x por jogo" engancha no MESMO tick de
        ``daemon.state_full`` que a GUI já tem — o ``super()`` pinta a aba
        Status como sempre (StatusActionsMixin) e, em seguida, o
        ``LaunchWrapperDialogMixin`` decide (função pura + cache por appid) se
        o jogo em foco merece o lembrete do ``hefesto-launch``. O mixin nunca
        propaga exceção — um defeito no lembrete não pode quebrar o render.
        """
        super()._render_slow_state(state)
        # R-08: o perfil ativo muda por fora da GUI (autoswitch/tray/hotkey) —
        # o draft precisa acompanhar, senão as abas editam o perfil errado.
        with contextlib.suppress(Exception):
            self._reconciliar_draft_com_perfil_ativo(state)
        self._maybe_prompt_wrapper_dialog(state)

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
        # S2: janela indo para o tray é janela sem aba Status à vista — a
        # captura do microfone morre junto (o `switch-page` não dispara ao
        # esconder a janela, então este é o único ponto que fecha a janela
        # de "capturando com ninguém olhando").
        parar_mic = getattr(self, "set_status_tab_visivel", None)
        if parar_mic is not None:
            parar_mic(False)
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
        # S2: mata as threads/subprocessos de captura do microfone ANTES do
        # main_quit — são threads daemon, mas um `parec` órfão continuaria
        # segurando o microfone da usuária até o processo morrer.
        parar_mic = getattr(self, "parar_mic_monitor", None)
        if parar_mic is not None:
            with contextlib.suppress(Exception):
                parar_mic()
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
        """Traz a janela para a frente (SIGUSR1, tray, notificação).

        DIÁLOGO-QUE-MATA-A-JANELA-01 (06/08/2026): levantar SÓ a janela
        principal não bastava — se há um diálogo modal bloqueante aberto, a
        principal é justamente a que está sob o grab, e presenteá-la não
        devolve nada a ela. MEDIDO em 06/08: `GLib.idle_add` (por onde este
        método chega, vindo do handler de SIGUSR1) **roda dentro do laço
        aninhado do `dialog.run()`**, então este é o caminho externo que
        alcança um diálogo perdido: `kill -USR1 <pid da GUI>`.
        """
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.app import gui_dialogs

            gui_dialogs.presentar_dialogos_em_curso()
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

        Retorna ``(draft, active_name)`` quando leu tudo; ``(None, "")`` quando a
        leitura foi BOA mas não há perfil a carregar (daemon sem perfil ativo, ou
        perfil ativo que não existe em disco) — falha PERMANENTE, que tentar de
        novo não cura.

        Levanta ``EstadoIndisponivelError`` quando a leitura não voltou (daemon
        caiu/reiniciou no instante da chamada, timeout de 0,25 s). Essa é a falha
        TRANSITÓRIA, e distingui-la é o que permite ao chamador soltar o latch de
        reconciliação sem reabrir o loop de IPC+I/O descrito no ``__init__``.
        """
        from hefesto_dualsense4unix.app.ipc_bridge import daemon_state_full
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles

        try:
            state = daemon_state_full()
        except Exception as exc:
            logger.warning("draft_load_falhou", erro=str(exc))
            raise EstadoIndisponivelError(str(exc)) from exc
        if state is None:
            logger.warning("draft_load_sem_resposta_do_daemon")
            raise EstadoIndisponivelError("daemon.state_full não respondeu")

        try:
            active_name: str | None = state.get("active_profile")

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
                    me = state.get("mouse_emulation")
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
            # Falha do lado do DISCO (listar/validar perfis), com a leitura de
            # estado já confirmada. Não vira `EstadoIndisponivelError` de
            # propósito: um perfil corrompido falharia igual a cada tentativa, e
            # soltar o latch por causa dele reabriria o loop de I/O a 2 Hz.
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
            self._draft_reload_inflight = False
            draft, active_name = result
            if draft is not None:
                self.draft = draft
                self._active_profile_name = active_name
                # R-08: a linha de base do "sujo" acompanha o que veio do disco.
                self._draft_baseline = draft
                _refresh_all_tabs(self)
            return False  # GLib.idle_add não repete

        def _falhou(exc: BaseException) -> bool:
            # Sem isto, um erro no worker deixaria `_draft_reload_inflight`
            # preso em True e a reconciliação morreria em silêncio pelo resto
            # da sessão.
            self._draft_reload_inflight = False
            if isinstance(exc, EstadoIndisponivelError):
                # A leitura não voltou: o alvo continua por tentar, e prendê-lo
                # aqui deixaria as abas editando o perfil ANTERIOR para sempre.
                self._draft_reload_for = None
                logger.warning(
                    "gui_draft_reload_sem_estado",
                    erro=str(exc),
                )
            return False

        self._draft_reload_inflight = True
        self._draft_reload_inflight_since = time.monotonic()
        ipc_bridge.run_in_thread(
            self._compute_draft_from_active_profile,
            on_success=_apply,
            on_failure=_falhou,
        )

    def _tem_edicao_pendente(self) -> bool:
        """True quando o draft em memória diverge do que veio do disco (R-08)."""
        baseline = self._draft_baseline
        return baseline is not None and self.draft != baseline

    def _reconciliar_draft_com_perfil_ativo(self, state: dict[str, Any]) -> None:
        """Recarrega o draft quando o perfil ativo muda por fora da GUI.

        R-08 (auditoria 23/07). Roda no tick lento que já existe — zero timers
        novos, e o `state` já traz `active_profile`.

        Com edição pendente NÃO troca em silêncio: avisa e espera. Recarregar
        por baixo de uma edição é perda de trabalho, que é justamente a queixa
        que este conjunto de correções ataca — trocar um jeito de perder
        alterações por outro não seria correção.

        JANELA-FIEL-01/E1: os dois latches param a reconciliação e por isso
        nenhum dos dois é definitivo. O de voo (`_draft_reload_inflight`) tem
        PRAZO — passado ele a chamada anterior é dada como perdida e uma nova
        sai; a resposta atrasada da abandonada só desliga o latch de novo, o que
        no pior caso adianta um recarregamento, nunca trava. O de alvo
        (`_draft_reload_for`) só segura quem já provou que repetir não adianta:
        falha de leitura de estado o solta em `_bootstrap_draft_async`.
        """
        ativo = state.get("active_profile")
        if not isinstance(ativo, str) or not ativo:
            return
        if ativo == self._active_profile_name:
            return
        if self._draft_reload_inflight:
            agora = time.monotonic()
            atraso = agora - self._draft_reload_inflight_since
            if atraso < DRAFT_RELOAD_INFLIGHT_TIMEOUT_S:
                return
            logger.warning(
                "gui_draft_reload_em_voo_dado_por_perdido",
                segundos=round(atraso, 1),
                para=ativo,
            )
        elif self._draft_reload_for == ativo:
            return
        if self._tem_edicao_pendente():
            self._status_toast(
                "draft-reload",
                f"O perfil ativo virou '{ativo}', mas suas alterações são de "
                f"'{self._active_profile_name or '—'}'. Salve ou use "
                "'Restaurar Padrão' para acompanhar o perfil novo.",
            )
            return
        # Marcado ANTES do disparo: o tick roda a 2 Hz e o worker é assíncrono.
        self._draft_reload_for = ativo
        logger.info(
            "gui_draft_reconciliado",
            de=self._active_profile_name or None,
            para=ativo,
        )
        # NUNCA-TROCA-O-ALVO-01 (06/08/2026): esta troca é LEGÍTIMA — não havia
        # nada a perder no instante do tique — mas ela move o alvo dos dois
        # botões de salvar sem que ela tenha encostado em nada, e era isso que
        # fazia o diálogo do rodapé nascer perguntando "substituir
        # 'sackboy_nativo'?" logo depois de ela ter ativado 'vitoria' na mão.
        # O silêncio aqui era a metade não medida do defeito: recarregar em
        # silêncio é seguro para os DADOS e enganoso para ELA. A janela passa a
        # dizer, no vocabulário do outro ramo, para onde o Salvar aponta agora.
        self._status_toast(
            "draft-reload",
            f"O perfil ativo virou '{ativo}' — as abas passaram a mostrar "
            f"esse perfil, e é nele que 'Salvar Perfil' grava agora.",
        )
        self._bootstrap_draft_async()

    #: Id do Glade da aba Status. Consumido aqui pelo gate da captura de
    #: microfone no `switch-page` (S2) e, em `status_actions`, pelo gate do tick
    #: de 10 Hz — o valor é um só, de lá.
    _ABA_STATUS: ClassVar[str] = ABA_STATUS

    #: Aba (id do Glade) -> nomes dos refreshers a chamar quando ela é exibida.
    #: Identificar pelo WIDGET, não pelo índice: a fusão de "Mouse" e "Teclado"
    #: na aba "Navegação DSX" renumerou as páginas, e um mapa por índice teria
    #: passado a chamar o refresher errado em silêncio — sem exceção, sem log,
    #: só a aba mostrando dado velho. Mesma lição do EST-10 em
    #: `_wrap_notebook_pages_in_scroll`: o id do Glade não muda quando a ordem
    #: ou o rótulo mudam.
    _REFRESH_POR_ABA: ClassVar[dict[str, tuple[str, ...]]] = {
        # FEAT-GUI-HOME-TAB-01: comutador de modo reconcilia ao ser exibido.
        "tab_home_box": ("_refresh_home_tab",),
        "tab_triggers_box": ("_refresh_triggers_from_draft",),
        "tab_lightbar_box": ("_refresh_lightbar_from_draft",),
        "tab_rumble_box": ("_refresh_rumble_from_draft",),
        # BUG-PROFILES-ACTIVE-STALE-01: autoswitch/hotkey trocam o perfil sem
        # passar pela GUI — re-marcar o ativo (negrito) ao exibir a aba.
        "profiles_paned": ("_sync_selection_with_active_profile",),
        # BUG-DAEMON-TAB-STALE-01: status do daemon re-renderiza ao entrar na
        # aba (o daemon pode ter subido/caído por fora, via CLI ou systemd).
        # M7 (auditoria): também reavalia o cartão anti-storm.
        "daemon_box": ("_refresh_daemon_tab_on_show",),
        # BUG-EMULATION-TAB-NO-REFRESH-01 (T3): se o daemon subiu após o boot, a
        # aba ficava em "—"/offline até alguém entrar nela.
        "emulation_box": ("_refresh_emulation_tab",),
        # A aba unificada roda os DOIS refreshers que antes eram de uma aba cada:
        # BUG-MOUSE-GUI-SYNC-01 (A1) sincroniza com o estado vivo do daemon e
        # BUG-KEYBOARD-TAB-NO-REFRESH-01 recarrega os bindings do draft.
        # EMULACAO-NO-JOGO-01/E1: `_refresh_keyboard_switch` NÃO entrou aqui, e
        # a razão é medida. Ele seria o lugar certo — o interruptor do teclado
        # vive nesta aba — mas hoje ele é o ÚNICO escritor da
        # `keyboard_emulation.flag` em todo o projeto (`grep`: não há CLI nem
        # applet chamando `keyboard.emulation.set`), então não existe caminho
        # pelo qual a posição dele mude sem passar por esta janela: reconciliar
        # ao entrar na aba não corrige staleness nenhuma HOJE. Ele é populado no
        # bootstrap (`install_emulation_tab`) e reconciliado pelo
        # `_refresh_emulation_tab`. Quando nascer um segundo escritor (a CLI
        # `keyboard on/off`, o applet), o nome entra nesta tupla — e junto tem de
        # entrar a linha correspondente em
        # `tests/unit/test_notebook_switch_page.py`, que congela esta lista com
        # `==` e reprova qualquer acréscimo.
        "tab_navegacao_dsx": (
            "_refresh_mouse_tab",
            "_refresh_key_bindings_from_draft",
        ),
    }

    def _on_notebook_switch_page(
        self, notebook: Any, page: Any, _page_num: int
    ) -> None:
        """Dispara o refresh dos widgets da aba destino ao trocar de aba.

        Cada mixin implementa o seu ``_refresh_*``; a chamada é protegida por
        ``_guard_refresh`` internamente para evitar loop. A aba é identificada
        pelo id do Glade (ver ``_REFRESH_POR_ABA``), não pela posição.

        ``page`` pode ser o ``GtkScrolledWindow`` que
        ``_wrap_notebook_pages_in_scroll`` colocou em volta da página — quem
        desembrulha é ``id_da_pagina``, o MESMO desembrulho que os pollers de
        Status e Início usam para saber qual aba está à vista.
        """
        nome = id_da_pagina(page)
        # S2: a captura de áudio do microfone existe SÓ enquanto a aba Status
        # está à vista — entrar liga, sair desliga. É o mesmo id de Glade que
        # o mapa abaixo usa; a página nunca é identificada por posição.
        visivel = getattr(self, "set_status_tab_visivel", None)
        if visivel is not None:
            visivel(nome == self._ABA_STATUS)
        # CONFIG-01: na aba Configurações o seletor de controle do cabeçalho não
        # tem sentido — o que se declara lá vale para a mesa inteira. A chamada
        # é simétrica à de cima, e mora AQUI e não no `_REFRESH_POR_ABA` de
        # propósito: aquele mapa só dispara ao ENTRAR na aba destino, então a
        # fita ficaria esmaecida para sempre depois da primeira visita.
        inativar = getattr(self, "set_alvo_inativo", None)
        if inativar is not None:
            inativar(nome == ABA_CONFIG)
        for atributo in self._REFRESH_POR_ABA.get(nome or "", ()):
            fn = getattr(self, atributo, None)
            if fn is not None:
                fn()

    # --- run ---

    def _envolver_estado_em_teto_elastico(self) -> None:
        """Dá ao frame "Estado" o mesmo teto elástico do card (SOM-01).

        O card de um controle cresce com a janela até um teto e centra a sobra.
        O `frame_status_estado` vem do glade e não tem código nosso, então
        ficava travado no piso — na tela maximizada, um frame de 1040px em cima
        de um card de 1400px. Envolvê-lo na `CaixaDeTetoElastico` faz os dois
        pararem no MESMO número, pelo MESMO mecanismo.

        Idempotente: se o frame já está dentro da caixa, não faz nada. Tolerante
        a glade sem o frame (dublê de teste) e a ambiente sem GTK.
        """
        from gi.repository import Gtk

        from hefesto_dualsense4unix.app.widgets.controller_card import (
            CaixaDeTetoElastico,
        )

        frame = self.builder.get_object("frame_status_estado")
        if frame is None:
            return
        pai = frame.get_parent()
        if pai is None or isinstance(pai, CaixaDeTetoElastico):
            return
        posicao = None
        if isinstance(pai, Gtk.Box):
            posicao = pai.child_get_property(frame, "position")
        pai.remove(frame)
        caixa = CaixaDeTetoElastico(frame)
        caixa.show_all()
        pai.add(caixa)
        if posicao is not None and isinstance(pai, Gtk.Box):
            pai.reorder_child(caixa, posicao)

    #: Páginas (id do Glade) que recebem o MESMO teto elástico do card.
    #:
    #: LARGURA-01/E4 (Início e Rumble, coluna única) e E5 (Gatilhos, Lightbar,
    #: Perfis e Navegação, duas colunas). Medido pela sprint com a janela em
    #: 1920: cada página recebia ~1894px e nenhuma das nove precisa de mais de
    #: 1166px — o resto virava vão sem dono. O custo em altura do teto, medido
    #: na mesma bancada, é de 0px em quatro delas e no máximo 44px na Lightbar,
    #: e no tamanho de projeto (1180px) ele nem entra em ação.
    #:
    #: A aba **Sistema** (`daemon_box`) fica de fora POR ESCRITO, e o motivo é
    #: medido: a linha mais longa do log pede 1400px exatos, o
    #: `daemon_log_scroll` tem `hscrollbar-policy: never` e o `daemon_status_text`
    #: quebra por palavra — um teto de 1400px na página deixaria ~1370px úteis e
    #: partiria essa linha em duas. A aba **Emulação** também fica: o vão dela é
    #: ENTRE os dois cartões do topo, que já param no tamanho natural, e a
    #: simulação em 1400 mediu os mesmos 715px (o teto não muda nada ali). A aba
    #: **Status** já tem o seu, pelo `_envolver_estado_em_teto_elastico`.
    _PAGINAS_COM_TETO_ELASTICO: ClassVar[tuple[str, ...]] = (
        "tab_home_box",
        "tab_rumble_box",
        "tab_triggers_box",
        "tab_lightbar_box",
        "profiles_paned",
        "tab_navegacao_dsx",
    )

    def _envolver_paginas_em_teto_elastico(self) -> None:
        """Põe o teto elástico do card em volta do CONTEÚDO de seis abas.

        A caixa entra DENTRO da página, e não em volta dela. A diferença não é
        de estilo: `id_da_pagina` reconhece a aba pelo nome de Buildable do
        widget que o notebook devolve, e um `Gtk.Bin` nosso não tem nome de
        Buildable nenhum — medido, `Gtk.Buildable.get_name` devolve `None`
        mesmo depois de `set_name`. Envolver a página por fora faria
        `_on_notebook_switch_page` e os pollers de Início e Status deixarem de
        reconhecer qualquer aba, **em silêncio**: sem exceção, sem log, só o
        refresh que nunca mais roda. Por dentro, a página segue sendo a página.

        Os filhos mudam de casa para um miolo novo, com a mesma orientação, o
        mesmo espaçamento e as MESMAS propriedades de empacotamento — expandir,
        preencher, espaço e ponta. Sem isso um filho com `expand` viraria um
        filho sem, e a aba mudaria de desenho por um efeito colateral do teto.

        Roda DEPOIS dos `install_*_tab`, e isso é requisito: a aba Início é
        montada em código (`install_home_tab` empacota banners e frames direto
        no `tab_home_box`), então um teto instalado antes ficaria com o miolo
        vazio e o conteúdo real fora dele.

        Idempotente. Tolerante a glade sem a página (dublê de teste).
        """
        for nome in self._PAGINAS_COM_TETO_ELASTICO:
            pagina = self.builder.get_object(nome)
            if not isinstance(pagina, Gtk.Box):
                continue
            filhos = pagina.get_children()
            if len(filhos) == 1 and isinstance(filhos[0], CaixaDeTetoDePagina):
                continue
            miolo = Gtk.Box(
                orientation=pagina.get_orientation(),
                spacing=pagina.get_spacing(),
            )
            for filho in filhos:
                empacotamento = {
                    chave: pagina.child_get_property(filho, chave)
                    for chave in ("expand", "fill", "padding", "pack-type")
                }
                pagina.remove(filho)
                # `pack_start`/`pack_end` acrescentam na mesma lista, na ordem
                # em que `get_children` a devolveu — a posição é preservada.
                empacotar = (
                    miolo.pack_end
                    if empacotamento["pack-type"] == Gtk.PackType.END
                    else miolo.pack_start
                )
                empacotar(
                    filho,
                    empacotamento["expand"],
                    empacotamento["fill"],
                    empacotamento["padding"],
                )
            caixa = CaixaDeTetoDePagina(miolo)
            pagina.pack_start(caixa, True, True, 0)
            caixa.show_all()

    def _wrap_notebook_pages_in_scroll(self) -> None:
        """Torna as abas roláveis para o RODAPÉ nunca ser cortado (BUG-FOOTER-CORTADO).

        O `GtkNotebook` pede como altura mínima o MAIOR mínimo entre TODAS as
        páginas (medido: ~606px, puxado por Perfis/Emulação). Sob tiling do COSMIC
        — que ignora `width/height-request` da janela — a janela não encolhe abaixo
        de header+notebook+rodapé e o rodapé de ações (Aplicar/Salvar Perfil/
        Importar/Restaurar) é empurrado para fora da área visível.

        Envolvendo cada página num `GtkScrolledWindow` (scroll vertical), o mínimo
        da página cai para ~0 e o rodapé fica SEMPRE visível, em qualquer tamanho
        de janela. Exceção: a aba **Sistema**, cujo conteúdo principal já é um
        `GtkScrolledWindow` (o log) com auto-scroll — envolvê-la de novo
        quebraria essa rolagem; o mínimo dela já é pequeno. Idempotente.

        Desde a JANELA-CORTADA-01 quem envolve a aba Sistema é o PRÓPRIO glade
        (`scroll_daemon_box` em volta do `daemon_box`), então a página que chega
        aqui JÁ É um `ScrolledWindow` e quem a pula é a guarda `isinstance`, não
        mais o `skip_pages`. Veja o comentário do EST-10 logo abaixo.
        """
        self._envolver_estado_em_teto_elastico()
        notebook = self.builder.get_object("main_notebook")
        if notebook is None:
            return
        # EST-10: identificar a aba pelo WIDGET, não pelo texto visível. O `skip`
        # era `{"Daemon"}` comparado com `label.get_text()` — renomear a aba (o
        # SPRINT-LEIGO-01 troca "Daemon" por "Sistema") faria o skip parar de
        # casar em silêncio, envolvendo o log num segundo ScrolledWindow e
        # quebrando o auto-scroll. O id do Glade não muda quando o rótulo muda.
        #
        # ATENÇÃO (18/08, ao mesclar o v0.9.4.3): este `skip_pages` HOJE não casa
        # com nada. A JANELA-CORTADA-01 pôs um `scroll_daemon_box` no glade em
        # volta do `daemon_box`, então a PÁGINA do notebook passou a ser o
        # scroller, e não o `daemon_box` que está aqui. Quem protege o auto-scroll
        # do log agora é a guarda `not isinstance(page, Gtk.ScrolledWindow)` do
        # laço. O conjunto fica como cinto de segurança: se algum dia o glade
        # voltar a entregar o `daemon_box` cru, o EST-10 volta a valer sozinho.
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
        self.install_config_tab()
        # LARGURA-01/E4-E5: o teto elástico das seis páginas entra AQUI, e não
        # junto com os roladores em `__init__`: a aba Início é montada em código
        # pelo `install_home_tab` logo acima, e um teto instalado antes ficaria
        # com o miolo vazio e o conteúdo dela do lado de fora.
        self._envolver_paginas_em_teto_elastico()
        # Conecta switch-page do GtkNotebook para refresh de draft por aba.
        notebook = self.builder.get_object("main_notebook")
        if notebook is not None:
            notebook.connect("switch-page", self._on_notebook_switch_page)
        self._caber_na_area_util()
        self.window.show_all()
        self._force_initial_repaint()
        # BUG-DAEMON-AUTOSTART-01: dispara start do daemon em thread worker
        # se a unit está instalada mas o service não está ativo. Jamais
        # bloqueia a thread GTK; falha silenciosa via logger.warning.
        self.ensure_daemon_running()
        # BUG-DRAFT-NEVER-LOADED-01: carrega o draft do perfil ativo (worker).
        self._bootstrap_draft_async()

    def _teto_da_area_util(self) -> tuple[int, int] | None:
        """Largura/altura máximas que a janela pode ocupar neste monitor.

        `get_workarea()` já desconta os painéis que o compositor declara — nesta
        bancada (Pop!_OS 22.04 / GNOME, 1920x1080) ele devolve 1920x952, tirando
        os 31px da barra de topo e os 97px da dock. A margem abaixo cobre a
        decoração da janela, que o compositor desenha POR FORA do tamanho do
        cliente, e a dock que flutua por cima sem se declarar (COSMIC).
        """
        from gi.repository import Gdk

        margem_altura = 80
        margem_largura = 40

        display = Gdk.Display.get_default()
        if display is None:
            return None
        monitor = None
        gdkwin = self.window.get_window()
        if gdkwin is not None:
            monitor = display.get_monitor_at_window(gdkwin)
        if monitor is None:
            monitor = display.get_primary_monitor() or display.get_monitor(0)
        if monitor is None:
            return None
        area = monitor.get_workarea()
        return (
            max(640, area.width - margem_largura),
            max(480, area.height - margem_altura),
        )

    def _caber_na_area_util(self) -> None:
        """A janela nunca ocupa mais do que a tela comporta.

        BUG-JANELA-MAIOR-QUE-A-TELA-01 (medido em 18/08/2026, Pop!_OS 22.04 com
        GNOME, 1920x1080): com um controle CONECTADO o card entra, o conteúdo
        passa a pedir mais que os 830px do `default-height`, e a janela nasceu
        com 955px — três a mais que os 952px de área útil, sem contar a
        decoração. O rodapé (Aplicar/Salvar Perfil/Importar/Restaurar) saiu por
        baixo da borda, e a decoração daquela sessão não oferecia maximizar:
        não havia gesto nenhum para corrigir de dentro.

        O `_wrap_notebook_pages_in_scroll` já cuidava do rodapé sob tiling do
        COSMIC, mas ele resolve o mínimo do NOTEBOOK, não o tamanho com que a
        janela nasce numa sessão flutuante.

        O corte não pode sair só daqui: logo após `show_all()` o `get_size()`
        ainda devolve o `default-height` do glade, porque o compositor ainda não
        negociou nada — foi assim que a primeira tentativa desta cura não cortou
        coisa alguma. Por isso o ajuste fica ARMADO no `size-allocate`, que é
        onde o tamanho real aparece, e se desarma sozinho na primeira correção.
        """
        teto = self._teto_da_area_util()
        if teto is None:
            return
        teto_largura, teto_altura = teto

        # O mínimo declarado no glade não pode passar do teto, senão o
        # compositor devolve a altura do pedido e o corte vira enfeite.
        min_largura, min_altura = self.window.get_size_request()
        if (min_largura > 0 and min_largura > teto_largura) or (
            min_altura > 0 and min_altura > teto_altura
        ):
            self.window.set_size_request(
                min(min_largura, teto_largura) if min_largura > 0 else -1,
                min(min_altura, teto_altura) if min_altura > 0 else -1,
            )

        self._ajuste_de_tela_pendente = True
        self.window.connect("size-allocate", self._on_alocacao_verifica_tela)

    def _ceder_altura_do_log(self, teto_altura: int) -> None:
        """Encolhe o log da aba Sistema quando o piso da janela não cabe na tela.

        Cortar a janela por fora não basta: o GTK não a deixa encolher abaixo do
        MÍNIMO do conteúdo, e foi por isso que o `resize()` desta cura, sozinho,
        não moveu um pixel. Medido nesta bancada, o piso era 913px contra 872 de
        área útil — header 127 + notebook 734 + rodapé 52.

        Dentro do notebook, quem sustentava os 734 era a aba **Sistema** (686),
        a única então fora de um `ScrolledWindow` — o log já tem rolagem própria,
        e envolvê-lo num segundo quebraria o auto-scroll (EST-10). As outras nove
        abas pediam 46 ou menos.

        Isso valia até 18/08. A JANELA-CORTADA-01 pôs um `scroll_daemon_box` no
        glade em volta do `daemon_box`, e a aba Sistema deixou de ser exceção:
        hoje TODAS as dez páginas chegam ao notebook dentro de um scroller. Este
        método não ficou inútil por isso — ele age sobre o `min_content_height`
        do log, que continua sendo a folga elástica —, mas passa a ser a SEGUNDA
        linha de defesa: com o mínimo do notebook já em ~0, o `faltam <= 0`
        costuma desarmá-lo sozinho. Ele existe para a tela em que nem isso basta.

        Então a folga sai de onde ela é elástica por natureza: o `min_content_
        height` do log. Ele só encolhe o quanto faltar, nunca abaixo de 60px, e
        somente quando falta — em tela que comporta a janela inteira, este método
        não toca em nada e o log mantém os 140px do glade. A altura NATURAL não
        muda: com espaço, o log continua abrindo nos 280px de sempre.
        """
        piso_do_log = 60
        log = self.builder.get_object("daemon_log_scroll")
        if log is None:
            return
        piso_janela, _ = self.window.get_preferred_height()
        faltam = piso_janela - teto_altura
        if faltam <= 0:
            return
        atual = log.get_min_content_height()
        novo = max(piso_do_log, atual - faltam)
        if novo >= atual:
            logger.info(
                "log_nao_tem_folga_suficiente",
                faltam=faltam,
                min_content_atual=atual,
                piso=piso_do_log,
            )
            return
        log.set_min_content_height(novo)
        logger.info(
            "log_cedeu_altura_para_a_janela_caber",
            faltam=faltam,
            de=atual,
            para=novo,
        )

    def _on_alocacao_verifica_tela(self, _widget: Any, _alocacao: Any) -> None:
        """Corta a janela na primeira alocação que estourar a área útil."""
        if not getattr(self, "_ajuste_de_tela_pendente", False):
            return
        teto = self._teto_da_area_util()
        if teto is None:
            return
        teto_largura, teto_altura = teto
        largura, altura = self.window.get_size()
        if largura <= teto_largura and altura <= teto_altura:
            return
        self._ajuste_de_tela_pendente = False
        # A ordem importa: o `resize` sozinho não move nada enquanto o MÍNIMO do
        # conteúdo for maior que o teto — o GTK simplesmente devolve o pedido.
        # Primeiro se abre espaço, depois se corta.
        self._ceder_altura_do_log(teto_altura)
        nova_largura = min(largura, teto_largura)
        nova_altura = min(altura, teto_altura)
        self.window.resize(nova_largura, nova_altura)
        logger.info(
            "janela_ajustada_a_tela",
            pedida=f"{largura}x{altura}",
            aplicada=f"{nova_largura}x{nova_altura}",
            teto=f"{teto_largura}x{teto_altura}",
        )

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

    def _trocar_perfil_de_fora(self, name: str) -> bool:
        """Trocar de perfil pela BANDEJA ou pela janela compacta.

        CARONA-DO-WRAPPER-01: o pedido dela foi *"ao clicarmos em aplicar ou
        salvar o perfil **seja dentro ou fora da guia de perfis**"*, e estes
        dois menus são o "fora" que fica mais longe da guia — a bandeja é o
        caminho de quem nem abriu a janela.

        A carona vem DEPOIS da troca e não depende do resultado dela, pela
        mesma razão do "Ativar" da aba: o wrapper que a Steam comeu continua
        comido mesmo que o daemon esteja parado e a troca falhe.

        Não há rodapé garantido aqui — a janela principal pode nem estar
        montada. Isso custa a FRASE, nunca o REPARO: ``_carona_toast`` já cai
        na statusbar e o degrau inteiro corre dentro do try do
        ``_carona_ao_terminar``. Reparar calado é melhor que não reparar.
        """
        try:
            trocou = profile_switch(name)
        finally:
            self.pegar_carona_no_gesto(GESTO_APLICAR)
        return trocou

    def run(self, *, start_hidden: bool = False) -> None:
        self.tray = AppTray(
            on_show_window=self.show_window,
            on_quit=self.quit_app,
            on_list_profiles=profile_list,
            on_switch_profile=self._trocar_perfil_de_fora,
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
                on_switch_profile=self._trocar_perfil_de_fora,
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
            # BUG-HOME-TAB-HIDDEN-INSTALL-01, de novo: quem sobe minimizado na
            # bandeja (o caminho de quem tem autostart) abriria a janela com a
            # aba Configurações em branco se este `install_` só existisse no
            # `show()`. Não havia teste guardando as duas listas — passa a
            # haver: `test_config_01_a_aba_nasce_vazia.py`.
            self.install_config_tab()
            # LARGURA-01/E4-E5: pelo mesmo motivo do caminho visível — depois
            # dos `install_*_tab`, porque a aba Início nasce em código.
            self._envolver_paginas_em_teto_elastico()
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
