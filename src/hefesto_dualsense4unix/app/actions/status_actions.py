"""Aba Status: polling ao vivo de daemon.state_full + update dos widgets.

Inclui a máquina de estado de reconnect (UX-RECONNECT-01): um tick dedicado
a cada 2s (`RECONNECT_POLL_INTERVAL_S`) observa o IPC e move o header entre
três estados visuais — `online`, `reconnecting`, `offline`. O polling rápido
dos widgets de live-state é independente e preserva a fluidez da aba Status.

Redesign UI-STATUS-STICKS-REDESIGN-01:
  - Bloco "Sticks e botões" virou Grid 2 colunas no GLADE.
  - Coluna esquerda: 2 StickPreviewGtk (L3 e R3) inseridos por código.
  - Coluna direita: Grid 4x4 de ButtonGlyph inserido por código.
  - `_on_state_update` diffa `buttons_pressed` contra `_last_buttons` para
    evitar queue_draw desnecessário a 10 Hz.
"""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.constants import (
    LIVE_POLL_INTERVAL_MS,
    RECONNECT_FAIL_THRESHOLD,
    RECONNECT_POLL_INTERVAL_S,
    STATE_POLL_INTERVAL_MS,
)
from hefesto_dualsense4unix.app.ipc_bridge import call_async
from hefesto_dualsense4unix.gui.widgets import BUTTON_GLYPH_LABELS, ButtonGlyph, StickPreviewGtk

# ---------------------------------------------------------------------------
# Configuração do grid de glyphs (4x4)
# ---------------------------------------------------------------------------

# Ordem de leitura: linha 0..3, coluna 0..3
GRID_BOTOES: list[list[str]] = [
    ["cross",    "circle",   "square",   "triangle"],
    ["dpad_up",  "dpad_down", "dpad_left", "dpad_right"],
    ["l1",       "r1",       "l2",       "r2"],
    ["share",    "options",  "ps",       "touchpad"],
]

# Todos os 16 botões do grid numa lista plana (para iteração)
ALL_BUTTONS: list[str] = [b for linha in GRID_BOTOES for b in linha]

# Threshold para L2/R2 analógicos
L2_R2_THRESHOLD = 30

# Roxo Drácula em markup Pango
_ROXO_DRACULA = "#bd93f9"


class StatusActionsMixin(WidgetAccessMixin):
    """Atualiza a aba Status em tempo real.

    Assume que `self.builder` contém os widgets do `main.glade`:
        status_connection, status_transport, status_battery_bar,
        status_active_profile, status_daemon,
        live_l2_bar, live_r2_bar, live_lx_label, live_rx_label,
        stick_left_preview_slot, stick_right_preview_slot,
        buttons_glyphs_slot,
        stick_left_title, stick_right_title,
        header_connection.

    Estados do reconnect (`_reconnect_state`):
        - ``"online"``: último poll retornou dict; header mostra  verde.
        - ``"reconnecting"``: IPC falhou 1..N-1 vezes consecutivas; header
          mostra  laranja com texto "tentando reconectar...".
        - ``"offline"``: N falhas consecutivas (N=RECONNECT_FAIL_THRESHOLD);
          header mostra  vermelho "daemon offline".
    """

    _reconnect_state: str = "online"
    _consecutive_failures: int = 0
    # UI-STATUS-OFFLINE-FALLBACK-01: marca True na primeira resposta IPC
    # bem-sucedida (qualquer tick). Permite que o fallback dedicado pinte
    # uma mensagem clara em até 5 s caso o daemon nunca responda.
    _first_poll_succeeded: bool = False
    _last_buttons: frozenset[str]
    _button_glyphs: dict[str, ButtonGlyph]
    _stick_left: StickPreviewGtk
    _stick_right: StickPreviewGtk

    def install_status_polling(self) -> None:
        """Liga os timers da aba Status e inicializa os widgets de sticks/glyphs.

        Chamado uma vez no on_mount após o builder estar disponível.

        BUG-GUI-DAEMON-STATUS-INITIAL-01: o primeiro tick dos timers acontecia
        somente após ``LIVE_POLL_INTERVAL_MS`` (100 ms) e
        ``STATE_POLL_INTERVAL_MS`` (500 ms). Entre abrir a janela e o primeiro
        poll de ``daemon.state_full``, o usuário via os valores default do
        Glade — ``status_daemon = "Offline"`` — apesar do daemon estar ativo.
        Fix: disparar um tick imediato de cada timer via ``GLib.idle_add`` logo
        antes de entrar no loop do GTK. ``_tick_live_state`` e
        ``_tick_profile_state`` são idempotentes e já usam thread worker para
        o IPC — nunca bloqueiam a thread GTK. Se o IPC não responder rápido o
        suficiente, os labels continuam mostrando "Consultando..." (novo
        default do Glade) em vez do falso-negativo "Offline".
        """
        self._last_buttons = frozenset()
        self._button_glyphs = {}
        self._init_stick_previews()
        self._init_button_glyphs()
        GLib.timeout_add(LIVE_POLL_INTERVAL_MS, self._tick_live_state)
        GLib.timeout_add(STATE_POLL_INTERVAL_MS, self._tick_profile_state)
        GLib.timeout_add_seconds(
            RECONNECT_POLL_INTERVAL_S, self._tick_reconnect_state
        )
        # Primeira leitura imediata — resolve a janela de 100-500 ms em que
        # o default do Glade ("Consultando...") ficava visível sem motivo.
        GLib.idle_add(self._tick_live_state)
        GLib.idle_add(self._tick_profile_state)
        # UI-STATUS-OFFLINE-FALLBACK-01: se 5 s passarem sem nenhum poll
        # bem-sucedido, pinta header com mensagem acionável em vez de manter
        # "Consultando..." indefinidamente (acontece quando o daemon nunca
        # subiu no boot — usuário precisa do passo de Daemon > Start).
        self._first_poll_succeeded = False
        GLib.timeout_add_seconds(5, self._check_initial_poll_fallback)

    # ------------------------------------------------------------------
    # Inicialização dos widgets dinâmicos
    # ------------------------------------------------------------------

    def _init_stick_previews(self) -> None:
        """Cria e insere os dois StickPreviewGtk nos slots do GLADE."""
        slot_esq = self._get("stick_left_preview_slot")
        slot_dir = self._get("stick_right_preview_slot")
        if slot_esq is None or slot_dir is None:
            return

        self._stick_left = StickPreviewGtk(label="L3")
        self._stick_left.set_size_request(120, 120)
        slot_esq.pack_start(self._stick_left, False, False, 0)
        self._stick_left.show()

        self._stick_right = StickPreviewGtk(label="R3")
        self._stick_right.set_size_request(120, 120)
        slot_dir.pack_start(self._stick_right, False, False, 0)
        self._stick_right.show()

    def _init_button_glyphs(self) -> None:
        """Cria o Grid 4x4 de ButtonGlyph e insere no slot do GLADE."""
        slot = self._get("buttons_glyphs_slot")
        if slot is None:
            return

        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(8)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)

        for row, linha in enumerate(GRID_BOTOES):
            for col, nome in enumerate(linha):
                tooltip = BUTTON_GLYPH_LABELS.get(nome, nome)
                # Tamanho 40px equilibra a grade com os sticks 120x120
                # (layout de 3 colunas homogêneas).
                glyph = ButtonGlyph(nome, size=40, tooltip_pt_br=tooltip)
                self._button_glyphs[nome] = glyph
                grid.attach(glyph, col, row, 1, 1)

        slot.pack_start(grid, False, False, 0)
        grid.show_all()

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    def _tick_live_state(self) -> bool:
        """Roda a 10 Hz: dispara RPC em thread worker; nunca bloqueia GTK."""
        call_async(
            "daemon.state_full",
            None,
            on_success=self._on_live_state_result,
            on_failure=self._on_live_state_failure,
        )
        return True  # mantém o timer vivo

    def _on_live_state_result(self, state: Any) -> bool:
        """Callback de sucesso — executa na thread principal via GLib.idle_add."""
        if isinstance(state, dict):
            # UI-STATUS-OFFLINE-FALLBACK-01: marca pelo menos um poll OK.
            self._first_poll_succeeded = True
            self._render_live_state(state)
        else:
            self._render_offline()
        return False  # não repetir via GLib

    def _on_live_state_failure(self, _exc: Exception) -> bool:
        """Callback de falha — executa na thread principal via GLib.idle_add."""
        self._render_offline()
        return False  # não repetir via GLib

    def _tick_profile_state(self) -> bool:
        """Roda a 2 Hz: perfil ativo + metadata que muda devagar."""
        call_async(
            "daemon.state_full",
            None,
            on_success=self._on_profile_state_result,
            on_failure=lambda _exc: False,
        )
        return True  # mantém o timer vivo

    def _on_profile_state_result(self, state: Any) -> bool:
        """Callback de sucesso para o tick lento — executa na thread GTK."""
        if isinstance(state, dict):
            self._first_poll_succeeded = True
            self._render_slow_state(state)
        return False  # não repetir via GLib

    def _tick_reconnect_state(self) -> bool:
        """Roda a 0.5 Hz: coordena a máquina de estado do header via thread worker."""
        call_async(
            "daemon.state_full",
            None,
            on_success=self._on_reconnect_state_result,
            on_failure=self._on_reconnect_state_failure,
        )
        return True

    def _on_reconnect_state_result(self, state: Any) -> bool:
        if isinstance(state, dict):
            self._first_poll_succeeded = True
        self._update_reconnect_state(state if isinstance(state, dict) else None)
        return False  # não repetir via GLib

    def _check_initial_poll_fallback(self) -> bool:
        """Pinta fallback acionável se 5 s passaram sem nenhum poll OK.

        UI-STATUS-OFFLINE-FALLBACK-01: o default do Glade é "Consultando..."
        em todos os labels. Se o daemon nunca subiu, os 3 timers continuam
        rodando mas o usuário fica olhando "Consultando..." sem entender que
        precisa abrir a aba Daemon e clicar em Iniciar.
        """
        if self._first_poll_succeeded:
            return False  # one-shot, não reagendar
        header = self._get("header_connection")
        if header is not None:
            header.set_markup(
                '<span foreground="#d33">'
                " Desconectado — abra a aba Daemon e clique em Iniciar"
                "</span>"
            )
        self._set_label("status_daemon", "Offline (sem resposta do daemon)")
        self._set_label("status_connection", "—")
        self._set_label("status_transport", "—")
        self._set_label("status_active_profile", "—")
        battery = self._get("status_battery_bar")
        if battery is not None:
            battery.set_fraction(0.0)
            battery.set_text("— %")
        # Mantém máquina de reconnect coerente.
        self._reconnect_state = "offline"
        self._consecutive_failures = max(
            self._consecutive_failures, RECONNECT_FAIL_THRESHOLD
        )
        return False  # one-shot

    def _on_reconnect_state_failure(self, _exc: Exception) -> bool:
        self._update_reconnect_state(None)
        return False

    # ------------------------------------------------------------------
    # Máquina de estado do reconnect
    # ------------------------------------------------------------------

    def _update_reconnect_state(self, state_full: dict[str, Any] | None) -> None:
        """Avança a máquina de estado de reconnect e repinta o header.

        Transições:
            * sucesso (state_full != None): qualquer estado → ``online``.
            * falha: incrementa `_consecutive_failures`.
              - < threshold: estado vai para ``reconnecting``.
              - >= threshold: estado vai para ``offline``.
        """
        if state_full is not None:
            self._consecutive_failures = 0
            self._reconnect_state = "online"
            self._render_online(state_full)
            return

        self._consecutive_failures += 1
        if self._consecutive_failures >= RECONNECT_FAIL_THRESHOLD:
            if self._reconnect_state != "offline":
                self._reconnect_state = "offline"
            self._render_offline()
        else:
            if self._reconnect_state != "reconnecting":
                self._reconnect_state = "reconnecting"
            self._render_reconnecting()

    # ------------------------------------------------------------------
    # Renderers de estado
    # ------------------------------------------------------------------

    def _render_online(self, state: dict[str, Any]) -> None:
        """Header canônico de estado ONLINE —  verde + transport.

        Delega o pinta-completo-da-aba a `_render_live_state` e
        `_render_slow_state` (já chamados pelos ticks rápidos). Aqui só
        firma o header de forma idempotente.
        """
        connected = bool(state.get("connected"))
        transport = state.get("transport") or "—"
        header = self._get("header_connection")
        if connected:
            header.set_markup(
                f'<span foreground="#2d8"> Conectado Via {transport.upper()}</span>'
            )
        else:
            header.set_markup(
                '<span foreground="#d33"> Controle Desconectado</span>'
            )
        self._set_label("status_daemon", "Online")

    def _render_reconnecting(self) -> None:
        """Header intermediário —  laranja + "tentando reconectar...".

        U+25D0 CIRCLE WITH LEFT HALF BLACK é Geometric Shape, não emoji.
        """
        header = self._get("header_connection")
        header.set_markup(
            '<span foreground="#d90"> Tentando Reconectar...</span>'
        )
        self._set_label("status_daemon", "Reconectando")

    def _render_offline(self) -> None:
        header = self._get("header_connection")
        header.set_markup(
            '<span foreground="#d33"> Daemon Offline</span>'
        )
        self._set_label("status_daemon", "Offline")
        self._set_label("status_connection", "—")
        self._set_label("status_transport", "—")
        self._set_label("status_active_profile", "—")
        self._get("status_battery_bar").set_fraction(0.0)
        self._get("status_battery_bar").set_text("— %")
        self._reset_live_widgets()

    def _render_live_state(self, state: dict[str, Any]) -> None:
        connected = bool(state.get("connected"))
        transport = state.get("transport") or "—"
        header = self._get("header_connection")
        # Só pintamos o header aqui se estamos em estado ONLINE; isso evita
        # que o tick rápido sobrescreva "Tentando Reconectar..." durante a
        # janela em que a máquina de reconnect ainda está tentando recuperar
        # o IPC (UX-RECONNECT-01 + POLISH-CAPS-01).
        if getattr(self, "_reconnect_state", "online") == "online":
            if connected:
                header.set_markup(
                    f'<span foreground="#2d8"> Conectado Via {transport.upper()}</span>'
                )
            else:
                header.set_markup(
                    '<span foreground="#d33"> Controle Desconectado</span>'
                )

        l2 = int(state.get("l2_raw", 0))
        r2 = int(state.get("r2_raw", 0))
        l2_bar = self._get("live_l2_bar")
        r2_bar = self._get("live_r2_bar")
        l2_bar.set_fraction(l2 / 255)
        l2_bar.set_text(f"{l2} / 255")
        r2_bar.set_fraction(r2 / 255)
        r2_bar.set_text(f"{r2} / 255")

        # Sticks — atualiza preview e labels numéricos
        lx = int(state.get("lx", 128))
        ly = int(state.get("ly", 128))
        rx = int(state.get("rx", 128))
        ry = int(state.get("ry", 128))

        if hasattr(self, "_stick_left"):
            self._stick_left.update(lx, ly)
        if hasattr(self, "_stick_right"):
            self._stick_right.update(rx, ry)

        lx_label = self._get("live_lx_label")
        if lx_label is not None:
            lx_label.set_markup(
                f'<span font_family="monospace" size="small">X: {lx}  Y: {ly}</span>'
            )
        rx_label = self._get("live_rx_label")
        if rx_label is not None:
            rx_label.set_markup(
                f'<span font_family="monospace" size="small">X: {rx}  Y: {ry}</span>'
            )

        # Botões pressionados — diff antes de redesenhar (performance 10 Hz)
        buttons_raw: list[str] = state.get("buttons", []) or []
        buttons_pressed = frozenset(buttons_raw)
        self._refresh_glyphs(state, buttons_pressed)

    def _refresh_glyphs(
        self, state: dict[str, Any], buttons_pressed: frozenset[str]
    ) -> None:
        """Atualiza ButtonGlyphs e títulos de sticks quando o estado muda."""
        last: frozenset[str] = getattr(self, "_last_buttons", frozenset())

        l2_raw = int(state.get("l2_raw", 0))
        r2_raw = int(state.get("r2_raw", 0))
        l2_lit = l2_raw > L2_R2_THRESHOLD
        r2_lit = r2_raw > L2_R2_THRESHOLD

        # Compõe conjunto efetivo incluindo L2/R2 analógicos
        efetivos: dict[str, bool] = {nome: (nome in buttons_pressed) for nome in ALL_BUTTONS}
        efetivos["l2"] = l2_lit
        efetivos["r2"] = r2_lit

        # Verifica se algo mudou (diff)
        last_l2 = getattr(self, "_last_l2_lit", False)
        last_r2 = getattr(self, "_last_r2_lit", False)
        if buttons_pressed == last and l2_lit == last_l2 and r2_lit == last_r2:
            return

        self._last_buttons = buttons_pressed
        self._last_l2_lit = l2_lit
        self._last_r2_lit = r2_lit

        for nome, glyph in self._button_glyphs.items():
            glyph.set_pressed(efetivos.get(nome, False))

        # Títulos dos sticks: roxo Drácula se L3/R3 pressionados
        l3_pressed = "l3" in buttons_pressed
        r3_pressed = "r3" in buttons_pressed

        if hasattr(self, "_stick_left"):
            self._stick_left.set_l3_pressed(l3_pressed)
        if hasattr(self, "_stick_right"):
            self._stick_right.set_l3_pressed(r3_pressed)

        titulo_esq = self._get("stick_left_title")
        titulo_dir = self._get("stick_right_title")
        if titulo_esq is not None:
            if l3_pressed:
                titulo_esq.set_markup(
                    f'<span foreground="{_ROXO_DRACULA}">Analógico Esquerdo (L3)</span>'
                )
            else:
                titulo_esq.set_markup("Analógico Esquerdo (L3)")
        if titulo_dir is not None:
            if r3_pressed:
                titulo_dir.set_markup(
                    f'<span foreground="{_ROXO_DRACULA}">Analógico Direito (R3)</span>'
                )
            else:
                titulo_dir.set_markup("Analógico Direito (R3)")

    def _render_slow_state(self, state: dict[str, Any]) -> None:
        connected = bool(state.get("connected"))
        transport = state.get("transport") or "—"
        battery = state.get("battery_pct")
        active_profile = state.get("active_profile") or "Nenhum"

        self._set_label(
            "status_connection", "Conectado" if connected else "Desconectado"
        )
        self._set_label("status_transport", transport.upper() if transport != "—" else "—")
        self._set_label("status_active_profile", active_profile)
        self._set_label("status_daemon", "Online")

        battery_bar = self._get("status_battery_bar")
        if battery is None:
            battery_bar.set_fraction(0.0)
            battery_bar.set_text("— %")
        else:
            battery_bar.set_fraction(battery / 100)
            battery_bar.set_text(f"{battery} %")

    def _reset_live_widgets(self) -> None:
        self._get("live_l2_bar").set_fraction(0.0)
        self._get("live_l2_bar").set_text("0 / 255")
        self._get("live_r2_bar").set_fraction(0.0)
        self._get("live_r2_bar").set_text("0 / 255")

        lx_label = self._get("live_lx_label")
        if lx_label is not None:
            lx_label.set_markup(
                '<span font_family="monospace" size="small">X: 128  Y: 128</span>'
            )
        rx_label = self._get("live_rx_label")
        if rx_label is not None:
            rx_label.set_markup(
                '<span font_family="monospace" size="small">X: 128  Y: 128</span>'
            )

        # Sticks ao centro
        if hasattr(self, "_stick_left"):
            self._stick_left.update(128, 128)
            self._stick_left.set_l3_pressed(False)
        if hasattr(self, "_stick_right"):
            self._stick_right.update(128, 128)
            self._stick_right.set_l3_pressed(False)

        # Glyphs todos apagados
        for glyph in getattr(self, "_button_glyphs", {}).values():
            glyph.set_pressed(False)
        self._last_buttons = frozenset()
        self._last_l2_lit = False
        self._last_r2_lit = False

        # Títulos sem markup colorido
        titulo_esq = self._get("stick_left_title")
        titulo_dir = self._get("stick_right_title")
        if titulo_esq is not None:
            titulo_esq.set_markup("Analógico Esquerdo (L3)")
        if titulo_dir is not None:
            titulo_dir.set_markup("Analógico Direito (R3)")
