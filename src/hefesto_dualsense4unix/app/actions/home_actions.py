"""Aba Início — comutador de MODO do sistema + controles + desligar de verdade.

FEAT-GUI-HOME-TAB-01. A primeira aba responde as três perguntas que a interface
antiga espalhava por quatro lugares:

1. "Em que modo o sistema está?" — comutador Desktop / Jogo (gamepad) / Jogo
   nativo, com co-op e máscara (DualSense/Xbox) quando fazem sentido. Reflete
   também o modo ligado POR PERFIL (FEAT-PROFILE-MODE-01).
2. "Quais controles estão conectados?" — um card por controle físico, com
   transporte, papel (P1/P2…), bateria e o fim do MAC como identificador
   discreto (FEAT-STATE-PER-CONTROLLER-01), além do aviso de grab degradado
   (input dobrado).
3. "Como desligo o hefesto DE VERDADE?" — botão dedicado que para o daemon e
   NÃO o religa ao reabrir/atualizar a GUI (diferente do "Parar" da aba
   Daemon, que o `ensure_daemon_running` ressuscitava sem avisar).

Todo widget é montado em código dentro de `tab_home_box` (Glade só reserva o
container) — padrão dos widgets dinâmicos, imune ao bug de popup do cosmic-comp
(botões sempre visíveis, sem dropdown).
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.ipc_bridge import call_async
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Intervalo do poller da aba Início (só age com a aba visível).
HOME_POLL_INTERVAL_MS = 2000

#: BUG-HOME-IPC-TIMEOUT-01: trocar de modo cria uinput + grab (bem mais que os
#: 0.25s default do call_async) — sem folga, o toast dizia "Falha" com o modo
#: JÁ aplicado. Mesma folga do Aplicar do rodapé (footer_actions).
_MODE_IPC_TIMEOUT_S = 2.0

# UX-MODE-TERMS-01: rótulos pela AÇÃO da usuária ("o que o controle faz
# agora"), não pela tecnologia — "gamepad virtual"/"nativo" viravam jargão.
_MODE_ITEMS = [
    ("desktop", "Controlar o PC"),
    ("gamepad", "Jogar pelo Hefesto"),
    ("native", "Jogar direto (Sony)"),
]

_MODE_DESCRIPTIONS = {
    "desktop": (
        "O controle vira mouse/teclado do computador (ajustes nas abas "
        "Mouse e Teclado)."
    ),
    "gamepad": (
        "Recomendado para a maioria dos jogos: o Hefesto cuida de LEDs, "
        "vibração e de um controle por jogador. Para a vibração funcionar e o "
        "controle não aparecer duplicado no jogo, use a máscara Xbox 360 e cole "
        "as opções da Steam (aba Daemon → \"Copiar opções p/ jogos\")."
    ),
    # SPRINT-GAME-RUMBLE-01: o nativo entrega gatilhos adaptativos, mas deixa o
    # jogo falar direto com o DualSense — inclusive pelo canal de áudio (haptics
    # do PS5), que é o que dispara o travamento/desconexão em alguns títulos.
    "native": (
        "Para jogos com suporte PS5 nativo: entrega os gatilhos adaptativos da "
        "Sony, mas o jogo fala direto com o controle — em alguns títulos isso "
        "desconecta o controle no meio da partida. Se acontecer, use \"Jogar "
        "pelo Hefesto\"."
    ),
}

_GLOSSARY = (
    "Modo jogo (aba Emulação): suspende só mouse/teclado virtuais.  ·  "
    "Pausar: congela o daemon sem soltar o controle.  ·  "
    "Jogar direto: solta o controle para o jogo.  ·  "
    "Desligar Hefesto: para o daemon até você religar."
)


def _format_controller_subtitle(
    transport: object, *, is_primary: bool, battery_pct: object
) -> str:
    """Linha secundária do card de controle (função pura — testável sem GTK).

    FEAT-STATE-PER-CONTROLLER-01: acrescenta a bateria ("· 87%") quando o
    daemon a reportou para ESTE controle; None/ausente fica de fora (nada de
    "0%" falso em controle recém-plugado). `bool` é rejeitado (subclasse de
    int) por blindagem contra payload malformado.
    """
    parts = [str(transport or "?").upper()]
    if is_primary:
        parts.append("primário")
    if isinstance(battery_pct, int) and not isinstance(battery_pct, bool):
        parts.append(f"{battery_pct}%")
    return "  ·  ".join(parts)


def _format_controller_uniq_suffix(uniq: object) -> str | None:
    """Identificador discreto do controle: o fim do MAC ("…c311f0").

    FEAT-STATE-PER-CONTROLLER-01: os 6 últimos dígitos hex distinguem
    controles fisicamente idênticos — os 6 primeiros são o prefixo do
    fabricante (iguais em todos os DualSense). Devolve None quando o backend
    não tem o MAC (key de fallback por path) — o card simplesmente omite a
    linha.
    """
    if not isinstance(uniq, str) or not uniq:
        return None
    return "…" + uniq[-6:]


class HomeActionsMixin(WidgetAccessMixin):
    """Mixin da aba Início (página 0 do notebook)."""

    def install_home_tab(self) -> None:
        """Monta o conteúdo dinâmico da aba Início. Idempotente."""
        from gi.repository import GLib, Gtk

        box = self._get("tab_home_box")
        if box is None or getattr(self, "_home_installed", False):
            return
        self._home_installed = True
        self._home_guard = False
        self._home_inflight = False

        # --- Frame: modo do sistema ---------------------------------------
        from hefesto_dualsense4unix.app.widgets.segmented_selector import (
            SegmentedSelector,
        )

        frame_mode = Gtk.Frame(label="O que o controle faz agora")
        mode_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        mode_box.set_margin_top(10)
        mode_box.set_margin_bottom(10)
        mode_box.set_margin_start(12)
        mode_box.set_margin_end(12)

        # wrap=True: FlowBox — lado a lado em janela larga, empilha na estreita
        # (sem estourar o frame sob tiling do COSMIC).
        selector = SegmentedSelector(wrap=True)
        selector.set_items(_MODE_ITEMS)
        selector.connect("changed", self._on_home_mode_changed)
        self._home_mode_selector = selector
        mode_box.pack_start(selector, False, False, 0)

        desc = Gtk.Label(label="")
        desc.set_xalign(0.0)
        desc.set_line_wrap(True)
        desc.get_style_context().add_class("dim-label")
        self._home_mode_desc = desc
        mode_box.pack_start(desc, False, False, 0)

        # BUG-HOME-MASK-CLIP-01: co-op e máscara em LINHAS separadas — na mesma
        # HBox o seletor de máscara estourava a largura do frame e era cortado
        # na borda direita (visto ao vivo 2026-07-13). A linha própria dá ao
        # seletor a largura toda para os 2 botões.
        opts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        # FEAT-COOP-DEFAULT-ON-01: já vem ligado por padrão; o checkbox é o
        # opt-out ("todos os controles agem como o mesmo jogador" ao desmarcar).
        coop_check = Gtk.CheckButton(
            label="Cada controle é um jogador (padrão com 2+ controles)"
        )
        coop_check.connect("toggled", self._on_home_coop_toggled)
        self._home_coop_check = coop_check
        opts.pack_start(coop_check, False, False, 0)

        mask_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        # UX (auditoria): rotula pela CONSEQUÊNCIA, não pela tecnologia — a ordem
        # e os textos deixam claro que Xbox é o que faz o jogo vibrar.
        flavor_label = Gtk.Label(label="O jogo vê o controle como:")
        mask_row.pack_start(flavor_label, False, False, 0)
        flavor = SegmentedSelector(wrap=True)
        flavor.set_items(
            [
                ("xbox", "Xbox 360 (vibra)"),
                ("dualsense", "DualSense (botões PS, sem vibrar)"),
            ]
        )
        flavor.connect("changed", self._on_home_flavor_changed)
        self._home_flavor_selector = flavor
        mask_row.pack_start(flavor, True, True, 0)
        opts.pack_start(mask_row, False, False, 0)
        self._home_gamepad_opts = opts
        mode_box.pack_start(opts, False, False, 0)

        origin = Gtk.Label(label="")
        origin.set_xalign(0.0)
        origin.get_style_context().add_class("dim-label")
        self._home_origin_label = origin
        mode_box.pack_start(origin, False, False, 0)

        frame_mode.add(mode_box)
        box.pack_start(frame_mode, False, False, 0)

        # --- Frame: controles conectados -----------------------------------
        frame_ctrl = Gtk.Frame(label="Controles")
        ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        # Cards de tamanho IGUAL (homogeneous): sem isso o card do primário
        # (linha extra "primário") ficava mais largo que o dos demais.
        ctrl_box.set_homogeneous(True)
        ctrl_box.set_margin_top(10)
        ctrl_box.set_margin_bottom(10)
        ctrl_box.set_margin_start(12)
        ctrl_box.set_margin_end(12)
        self._home_controllers_box = ctrl_box
        frame_ctrl.add(ctrl_box)
        box.pack_start(frame_ctrl, False, False, 0)

        # --- Frame: sessão (desligar de verdade) ---------------------------
        frame_sess = Gtk.Frame(label="Sessão")
        sess_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sess_box.set_margin_top(10)
        sess_box.set_margin_bottom(10)
        sess_box.set_margin_start(12)
        sess_box.set_margin_end(12)

        shutdown_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        shutdown_btn = Gtk.Button(label="Desligar Hefesto (voltar ao Linux puro)")
        shutdown_btn.get_style_context().add_class("destructive-action")
        shutdown_btn.connect("clicked", self._on_home_shutdown_clicked)
        self._home_shutdown_btn = shutdown_btn
        shutdown_row.pack_start(shutdown_btn, False, False, 0)
        sess_status = Gtk.Label(label="")
        sess_status.set_xalign(0.0)
        self._home_session_label = sess_status
        shutdown_row.pack_start(sess_status, False, False, 0)
        sess_box.pack_start(shutdown_row, False, False, 0)

        hint = Gtk.Label(label=_GLOSSARY)
        hint.set_xalign(0.0)
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("dim-label")
        sess_box.pack_start(hint, False, False, 0)

        frame_sess.add(sess_box)
        box.pack_start(frame_sess, False, False, 0)
        box.show_all()

        # Poller: só age com a aba Início visível (página 0).
        GLib.timeout_add(HOME_POLL_INTERVAL_MS, self._tick_home_state)

    # --- refresh ----------------------------------------------------------

    def _tick_home_state(self) -> bool:
        notebook = self._get("main_notebook")
        if notebook is not None and notebook.get_current_page() == 0:
            self._refresh_home_tab()
        return True  # timer permanente

    def _refresh_home_tab(self) -> None:
        """Reconcilia o comutador/cards com o estado VIVO do daemon."""
        if not getattr(self, "_home_installed", False):
            return
        if getattr(self, "_home_inflight", False):
            return
        self._home_inflight = True

        def _ok(state: Any) -> bool:
            self._home_inflight = False
            if isinstance(state, dict):
                self._render_home(state)
            return False

        def _fail(_exc: Exception) -> bool:
            self._home_inflight = False
            self._render_home(None)
            return False

        call_async("daemon.state_full", None, _ok, _fail)

    def _render_home(self, state: dict[str, Any] | None) -> None:
        from gi.repository import Gtk

        offline = state is None
        selector = self._home_mode_selector
        self._home_guard = True
        try:
            if offline:
                self._home_session_label.set_text(
                    "Daemon desligado — religue na aba Daemon (Iniciar)."
                )
                selector.set_sensitive(False)
                self._home_coop_check.set_sensitive(False)
                self._home_flavor_selector.set_sensitive(False)
                # BUG-HOME-OFFLINE-STALE-01: sem limpar, descrição/origem/
                # opções do gamepad ficavam do último estado online.
                self._home_mode_desc.set_text("")
                self._home_origin_label.set_text("")
                self._home_gamepad_opts.set_visible(False)
                self._render_home_controllers([])
                return
            assert state is not None
            selector.set_sensitive(True)
            self._home_coop_check.set_sensitive(True)
            self._home_flavor_selector.set_sensitive(True)
            self._home_session_label.set_text("")

            gamepad = state.get("gamepad_emulation") or {}
            if state.get("native_mode"):
                mode = "native"
            elif gamepad.get("enabled"):
                mode = "gamepad"
            else:
                mode = "desktop"
            selector.set_active_id(mode)
            self._home_mode_desc.set_text(_MODE_DESCRIPTIONS.get(mode, ""))
            self._home_gamepad_opts.set_visible(mode == "gamepad")
            self._home_gamepad_opts.set_no_show_all(mode != "gamepad")

            coop = state.get("coop") or {}
            self._home_coop_check.set_active(bool(coop.get("enabled")))
            flavor = gamepad.get("flavor") or "xbox"
            self._home_flavor_selector.set_active_id(str(flavor))

            origin_bits: list[str] = []
            if state.get("native_mode") and state.get("native_mode_origin") == "profile":
                origin_bits.append("nativo ligado pelo perfil ativo")
            if state.get("mode_from_profile") == "gamepad":
                origin_bits.append("gamepad ligado pelo perfil ativo")
            if bool(coop.get("enabled")) and coop.get("players"):
                origin_bits.append(f"co-op: {coop.get('players')} jogador(es)")
            self._home_origin_label.set_text(" · ".join(origin_bits))

            self._render_home_controllers(
                list(state.get("controllers") or []),
                grab_state=state.get("primary_grab_state"),
                gamepad_on=bool(gamepad.get("enabled")),
            )
            # Gtk referenciado para manter o import local óbvio (sem uso direto
            # neste ramo; os cards usam via _render_home_controllers).
            _ = Gtk
        finally:
            self._home_guard = False

    def _render_home_controllers(
        self,
        controllers: list[dict[str, Any]],
        *,
        grab_state: str | None = None,
        gamepad_on: bool = False,
    ) -> None:
        from gi.repository import Gtk

        box = self._home_controllers_box
        for child in box.get_children():
            box.remove(child)
        if not controllers:
            empty = Gtk.Label(label="Nenhum controle conectado.")
            empty.get_style_context().add_class("dim-label")
            box.pack_start(empty, False, False, 0)
            box.show_all()
            return
        for idx, ctrl in enumerate(controllers):
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            card.get_style_context().add_class("hefesto-dualsense4unix-card")
            card.set_margin_end(6)
            is_primary = bool(ctrl.get("is_primary"))
            title = Gtk.Label()
            player = f"P{idx + 1}"
            name = f"Controle {idx + 1} — {player}"
            title.set_markup(f"<b>{name}</b>" if is_primary else name)
            title.set_xalign(0.0)
            card.pack_start(title, False, False, 0)
            sub = Gtk.Label(
                label=_format_controller_subtitle(
                    ctrl.get("transport"),
                    is_primary=is_primary,
                    battery_pct=ctrl.get("battery_pct"),
                )
            )
            sub.set_xalign(0.0)
            sub.get_style_context().add_class("dim-label")
            card.pack_start(sub, False, False, 0)
            # FEAT-STATE-PER-CONTROLLER-01: fim do MAC como identificador
            # discreto — distingue "Controle 1"/"Controle 2" fisicamente iguais.
            uniq_txt = _format_controller_uniq_suffix(ctrl.get("uniq"))
            if uniq_txt is not None:
                uid = Gtk.Label(label=uniq_txt)
                uid.set_xalign(0.0)
                uid.get_style_context().add_class("dim-label")
                card.pack_start(uid, False, False, 0)
            if is_primary and gamepad_on and grab_state == "failed":
                warn = Gtk.Label(label="grab falhou — input pode dobrar no jogo")
                warn.set_xalign(0.0)
                warn.get_style_context().add_class("hefesto-dualsense4unix-status-err")
                card.pack_start(warn, False, False, 0)
            box.pack_start(card, True, True, 0)
        box.show_all()

    # --- handlers -----------------------------------------------------------

    def _on_home_mode_changed(self, selector: Any) -> None:
        # "changed" do SegmentedSelector é sem argumentos (como GtkComboBox);
        # o id ativo vem de get_active_id() — BUG-HOME-SEGMENTED-SIGNATURE-01.
        mode_id = selector.get_active_id()
        if getattr(self, "_home_guard", False) or not mode_id:
            return
        self._home_mode_desc.set_text(_MODE_DESCRIPTIONS.get(mode_id, ""))

        def _done(_result: Any) -> bool:
            self._status_toast("home", f"Modo aplicado: {mode_id}")
            self._refresh_home_tab()
            return False

        def _fail(exc: Exception) -> bool:
            self._status_toast("home", f"Falha ao mudar o modo ({exc})")
            self._refresh_home_tab()
            return False

        if mode_id == "native":
            call_async(
                "native.mode.set",
                {"enabled": True},
                _done,
                _fail,
                timeout_s=_MODE_IPC_TIMEOUT_S,
            )
        elif mode_id == "gamepad":
            flavor = self._home_flavor_selector.get_active_id() or "xbox"
            # Ordem FIFO do worker: sair do nativo antes de ligar o gamepad.
            call_async(
                "native.mode.set",
                {"enabled": False},
                lambda _r: False,
                lambda _e: False,
                timeout_s=_MODE_IPC_TIMEOUT_S,
            )
            call_async(
                "gamepad.emulation.set",
                {"enabled": True, "flavor": flavor},
                _done,
                _fail,
                timeout_s=_MODE_IPC_TIMEOUT_S,
            )
        else:  # desktop
            # FEAT-COOP-DEFAULT-ON-01: NÃO desliga o co-op aqui — desligar o
            # gamepad já desmonta os jogadores; preservar a preferência faz o
            # co-op voltar sozinho ao reentrar em "Jogar pelo Hefesto".
            call_async(
                "native.mode.set",
                {"enabled": False},
                lambda _r: False,
                lambda _e: False,
                timeout_s=_MODE_IPC_TIMEOUT_S,
            )
            call_async(
                "gamepad.emulation.set",
                {"enabled": False},
                _done,
                _fail,
                timeout_s=_MODE_IPC_TIMEOUT_S,
            )

    def _on_home_coop_toggled(self, check: Any) -> None:
        if getattr(self, "_home_guard", False):
            return
        enabled = bool(check.get_active())

        def _done(result: Any) -> bool:
            players = (result or {}).get("players") if isinstance(result, dict) else None
            extra = f" ({players} jogadores)" if players else ""
            self._status_toast(
                "home", ("Co-op ligado" if enabled else "Co-op desligado") + extra
            )
            self._refresh_home_tab()
            return False

        def _fail(exc: Exception) -> bool:
            self._status_toast("home", f"Falha no co-op ({exc})")
            self._refresh_home_tab()
            return False

        call_async(
            "coop.set",
            {"enabled": enabled},
            _done,
            _fail,
            timeout_s=_MODE_IPC_TIMEOUT_S,
        )

    def _on_home_flavor_changed(self, selector: Any) -> None:
        flavor_id = selector.get_active_id()
        if getattr(self, "_home_guard", False) or not flavor_id:
            return
        mode = self._home_mode_selector.get_active_id()
        if mode != "gamepad":
            return

        def _done(_result: Any) -> bool:
            self._status_toast("home", f"Máscara do gamepad: {flavor_id}")
            return False

        call_async(
            "gamepad.emulation.set",
            {"enabled": True, "flavor": flavor_id},
            _done,
            lambda _e: False,
            timeout_s=_MODE_IPC_TIMEOUT_S,
        )

    def _on_home_shutdown_clicked(self, _button: object) -> None:
        """Desliga o daemon DE VERDADE (com confirmação não-bloqueante)."""
        from gi.repository import Gtk

        window = self._get("main_window")
        dialog = Gtk.MessageDialog(
            transient_for=window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Desligar o Hefesto?",
        )
        dialog.format_secondary_text(
            "O daemon para e o controle volta ao comportamento puro do Linux.\n"
            "A GUI continua aberta e NÃO religa o daemon sozinha — religue na "
            "aba Daemon (Iniciar) ou feche e abra o painel."
        )

        def _on_response(dlg: Any, response: int) -> None:
            dlg.destroy()
            if response != Gtk.ResponseType.YES:
                return
            # FEAT-GUI-HOME-TAB-01: o ensure_daemon_running respeita este flag —
            # sem ele, reabrir/atualizar a GUI ressuscitava o daemon parado.
            self._user_stopped_daemon = True

            def _worker_ok(result: Any) -> bool:
                # BUG-HOME-SHUTDOWN-FALSE-OK-01: systemctl com rc!=0 (sem
                # sessão systemd, daemon avulso) NÃO desligou nada — o toast
                # não pode mentir nem armar o _user_stopped_daemon à toa.
                rc = getattr(result, "returncode", 1)
                if rc == 0:
                    self._status_toast(
                        "home", "Hefesto desligado — controle no modo puro do Linux"
                    )
                else:
                    self._user_stopped_daemon = False
                    err = (getattr(result, "stderr", b"") or b"").decode(
                        "utf-8", "replace"
                    ).strip()
                    self._status_toast(
                        "home",
                        "Falha ao desligar via systemd"
                        + (f" ({err})" if err else "")
                        + " — se o daemon roda avulso, pare-o na aba Daemon.",
                    )
                self._refresh_home_tab()
                return False

            from hefesto_dualsense4unix.app.ipc_bridge import run_in_thread

            def _stop() -> Any:
                import subprocess

                return subprocess.run(
                    ["systemctl", "--user", "stop", "hefesto-dualsense4unix.service"],
                    capture_output=True,
                    timeout=10,
                    check=False,
                )

            run_in_thread(_stop, _worker_ok, lambda _e: False)

        dialog.connect("response", _on_response)
        dialog.show()


__all__ = ["HOME_POLL_INTERVAL_MS", "HomeActionsMixin"]
