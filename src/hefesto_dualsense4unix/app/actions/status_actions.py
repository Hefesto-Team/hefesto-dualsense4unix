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

import contextlib
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
from hefesto_dualsense4unix.utils.i18n import _

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
        - ``"online"``: último poll retornou dict; header mostra glyph
          U+25CF (black circle) verde + "Conectado Via <USB|BT>".
        - ``"reconnecting"``: IPC falhou 1..N-1 vezes consecutivas; header
          mostra glyph U+25D0 (left half black circle) laranja com texto
          "Tentando Reconectar...".
        - ``"offline"``: N falhas consecutivas (N=RECONNECT_FAIL_THRESHOLD);
          header mostra glyph U+25CB (white circle) vermelho + "Daemon
          Offline". Glyphs emitidos como NCR no markup Pango (ADR-011) para
          escapar do sanitizer global de geometric shapes.
    """

    _reconnect_state: str = "online"
    _consecutive_failures: int = 0
    # UI-STATUS-OFFLINE-FALLBACK-01: marca True na primeira resposta IPC
    # bem-sucedida (qualquer tick). Permite que o fallback dedicado pinte
    # uma mensagem clara em até 5 s caso o daemon nunca responda.
    _first_poll_succeeded: bool = False
    # BUG-LIVE-TICK-NO-INFLIGHT-GUARD-01: coalesce do tick rápido (10 Hz). Sem
    # isso, com o executor de 1 worker e o daemon lento, os call_async se
    # acumulavam numa fila ilimitada. Setado antes do call_async, limpo nos
    # callbacks (sucesso e falha).
    _live_inflight: bool = False
    # GUI-ESTABILIDADE-COSMIC-REMEDIATION-01 / R4: mesmo coalesce para os ticks
    # lento (2 Hz) e de reconnect (0.5 Hz), reduzindo a contenção no executor de
    # 1 worker que os 3 pollers de `daemon.state_full` compartilham.
    _profile_inflight: bool = False
    _reconnect_inflight: bool = False
    # GUI-ESTABILIDADE-COSMIC-REMEDIATION-01 / R3: último valor escrito em cada
    # widget de live-state. `_render_live_state` só chama set_fraction/set_text/
    # set_markup quando o valor muda desde o último tick (diff), evitando repaint
    # contínuo a 10 Hz mesmo com o controle parado (jank no NVIDIA/XWayland).
    _last_l2: int | None = None
    _last_r2: int | None = None
    _last_lx: int | None = None
    _last_ly: int | None = None
    _last_rx: int | None = None
    _last_ry: int | None = None
    _last_buttons: frozenset[str]
    _button_glyphs: dict[str, ButtonGlyph]
    _stick_left: StickPreviewGtk
    _stick_right: StickPreviewGtk
    # FEAT-DSX-CONTROLLER-SELECTOR-01: seletor de controle-alvo no banner.
    _target_combo: Any
    _target_combo_rows: list[tuple[str, int | None]]
    _target_combo_updating: bool
    _target_combo_visible: bool
    _target_combo_active: int
    _target_buttons: list[Any]

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
        self._init_controller_target_combo()
        GLib.timeout_add(LIVE_POLL_INTERVAL_MS, self._tick_live_state)
        GLib.timeout_add(STATE_POLL_INTERVAL_MS, self._tick_profile_state)
        GLib.timeout_add_seconds(
            RECONNECT_POLL_INTERVAL_S, self._tick_reconnect_state
        )
        # Primeira leitura imediata — resolve a janela de 100-500 ms em que
        # o default do Glade ("Consultando...") ficava visível sem motivo.
        # BUG-GUI-IDLE-ADD-BUSY-LOOP-01: `_tick_live_state`/`_tick_profile_state`
        # retornam True (mantém o timeout_add vivo). Passar essas funções direto
        # ao `idle_add` virava um busy-loop a 100% CPU (idle_add reagenda
        # enquanto o callback retorna True), acumulando call_async no executor.
        # Wrappers one-shot disparam o tick uma vez e retornam False.
        GLib.idle_add(lambda: self._tick_live_state() and False)
        GLib.idle_add(lambda: self._tick_profile_state() and False)
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
    # Seletor de controle-alvo (FEAT-DSX-CONTROLLER-SELECTOR-01)
    # ------------------------------------------------------------------

    @staticmethod
    def _controller_target_rows(
        conectados: list[dict[str, Any]],
    ) -> list[tuple[str, int | None]]:
        """Linhas do seletor: ``[(rótulo, índice_do_controle | None)]``.

        Posição 0 é sempre "Todos os controles" (None = broadcast). As demais,
        uma por controle conectado, rotuladas "Controle N — TRANSPORTE" (N =
        index+1, 1-based, batendo com a CLI e o applet). O índice carregado é o
        ``index`` 0-based do bloco ``controllers`` (o mesmo que o IPC
        ``controller.target.set`` espera). FEAT-DSX-CONTROLLER-SELECTOR-01.
        """
        rows: list[tuple[str, int | None]] = [(_("Todos os controles"), None)]
        for c in conectados:
            idx = int(c.get("index", 0))
            transporte = (c.get("transport") or "?").upper()
            rows.append(
                (_("Controle {n} — {t}").format(n=idx + 1, t=transporte), idx)
            )
        return rows

    @staticmethod
    def _target_active_position(
        rows: list[tuple[str, int | None]], target_index: int | None
    ) -> int:
        """Posição na combo correspondente ao alvo atual; 0 ("Todos") se não achar."""
        for pos, (_label, idx) in enumerate(rows):
            if idx == target_index:
                return pos
        return 0

    def _init_controller_target_combo(self) -> None:
        """Cria o seletor de controle-alvo como BOTÕES segmentados no banner.

        NÃO é dropdown: popups de combo são fechados pelo cosmic-comp (bug de foco
        do COSMIC — cosmic-epoch#2497 / [[gui-combo-flicker-jitter-relayout]]) em
        ~40-95% dos cliques, faça o que fizermos. Botões sempre visíveis (sem
        popup/grab) são imunes. Cada alvo vira um GtkRadioButton em modo toggle
        (visual de 'segmented control' via classe 'linked'). Oculto por padrão; só
        aparece com 2+ controles. FEAT-DSX-CONTROLLER-SELECTOR-01.
        """
        self._target_combo_rows = []
        self._target_combo_updating = False
        self._target_combo_visible = False
        self._target_combo_active = -1
        self._target_buttons = []
        header_bar = self._get("header_bar")
        if header_bar is None:
            self._target_combo = None
            return
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        box.get_style_context().add_class("linked")
        box.set_valign(Gtk.Align.CENTER)
        box.set_tooltip_text(
            "Controle alvo das ações (lightbar, gatilhos, LEDs, rumble). "
            "'Todos' aplica a todos os controles."
        )
        box.set_no_show_all(True)
        box.hide()
        header_bar.pack_end(box, False, False, 0)
        self._target_combo = box

    @staticmethod
    def _short_target_label(label: str) -> str:
        """'Todos os controles' -> 'Todos'; 'Controle 1 — BT' -> '1 · BT'."""
        if label.startswith("Todos"):
            return "Todos"
        return label.replace("Controle ", "").replace(" — ", " · ")

    def _rebuild_target_buttons(
        self, box: Any, rows: list[tuple[str, int | None]]
    ) -> None:
        """Recria os GtkRadioButton (modo toggle) do seletor a partir das linhas."""
        for child in list(box.get_children()):
            box.remove(child)
            child.destroy()
        self._target_buttons = []
        group = None
        for label, index in rows:
            btn = Gtk.RadioButton.new_with_label_from_widget(
                group, self._short_target_label(label)
            )
            if group is None:
                group = btn
            btn.set_mode(False)  # toggle button (sem a bolinha de radio)
            btn.set_tooltip_text(label)
            btn.connect("toggled", self._on_target_button_toggled, index)
            btn.show()
            box.pack_start(btn, False, False, 0)
            self._target_buttons.append(btn)

    def _set_target_active(self, pos: int) -> None:
        """Marca o botão na posição ``pos`` como ativo (sem disparar IPC)."""
        if 0 <= pos < len(self._target_buttons):
            self._target_buttons[pos].set_active(True)

    def _refresh_controller_target_combo(self, state: dict[str, Any]) -> None:
        """Atualiza os botões do seletor; reflete ``output_target_index``.

        IDEMPOTENTE: só reconstrói/marca quando rótulos/posição/visibilidade
        mudam. Some com <2 controles. FEAT-DSX-CONTROLLER-SELECTOR-01.
        """
        box = getattr(self, "_target_combo", None)
        if box is None:
            return
        conectados = self._connected_controllers(state)
        if len(conectados) < 2:
            if self._target_combo_visible:  # só esconde na TRANSIÇÃO
                box.hide()
                self._target_combo_visible = False
            return
        rows = self._controller_target_rows(conectados)
        target_index = state.get("output_target_index")
        if not isinstance(target_index, int) or isinstance(target_index, bool):
            target_index = None
        labels = [label for label, _ in rows]
        rows_changed = labels != [label for label, _ in self._target_combo_rows]
        want_pos = self._target_active_position(rows, target_index)
        if (
            not rows_changed
            and want_pos == self._target_combo_active
            and self._target_combo_visible
        ):
            return
        self._target_combo_updating = True
        try:
            if rows_changed:
                self._rebuild_target_buttons(box, rows)
                self._target_combo_rows = rows
            self._set_target_active(want_pos)
            self._target_combo_active = want_pos
            if not self._target_combo_visible:
                box.show()
                self._target_combo_visible = True
        finally:
            self._target_combo_updating = False

    def _on_target_button_toggled(self, button: Any, index: int | None) -> None:
        """Aplica a escolha (só no botão que ficou ATIVO; ignora set programático)."""
        if getattr(self, "_target_combo_updating", False):
            return
        if not button.get_active():
            return
        call_async(
            "controller.target.set",
            {"index": index},
            on_success=lambda _r: False,
            on_failure=lambda _e: False,
        )

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    def _tick_live_state(self) -> bool:
        """Roda a 10 Hz: dispara RPC em thread worker; nunca bloqueia GTK."""
        # BUG-LIVE-TICK-NO-INFLIGHT-GUARD-01: pula este tick se o anterior ainda
        # não retornou — evita acúmulo ilimitado no executor de 1 worker.
        if self._live_inflight:
            return True
        self._live_inflight = True
        call_async(
            "daemon.state_full",
            None,
            on_success=self._on_live_state_result,
            on_failure=self._on_live_state_failure,
        )
        return True  # mantém o timer vivo

    def _on_live_state_result(self, state: Any) -> bool:
        """Callback de sucesso — executa na thread principal via GLib.idle_add."""
        self._live_inflight = False
        if isinstance(state, dict):
            # UI-STATUS-OFFLINE-FALLBACK-01: marca pelo menos um poll OK.
            self._first_poll_succeeded = True
            self._render_live_state(state)
        else:
            # BUG-FAST-TICK-CLOBBERS-RECONNECT-01: o tick rápido NÃO pinta o
            # header de offline (isso é da máquina de reconnect, a 2s); só zera
            # os widgets de live-state para não exibir dados stale.
            self._reset_live_widgets()
        return False  # não repetir via GLib

    def _on_live_state_failure(self, _exc: Exception) -> bool:
        """Callback de falha — executa na thread principal via GLib.idle_add."""
        self._live_inflight = False
        # Ver BUG-FAST-TICK-CLOBBERS-RECONNECT-01: só reseta widgets, não o header.
        self._reset_live_widgets()
        return False  # não repetir via GLib

    def _tick_profile_state(self) -> bool:
        """Roda a 2 Hz: perfil ativo + metadata que muda devagar."""
        # R4: pula este tick se o anterior ainda não retornou — evita acúmulo
        # no executor de 1 worker compartilhado pelos 3 pollers.
        if self._profile_inflight:
            return True
        self._profile_inflight = True
        call_async(
            "daemon.state_full",
            None,
            on_success=self._on_profile_state_result,
            on_failure=self._on_profile_state_failure,
        )
        return True  # mantém o timer vivo

    def _on_profile_state_result(self, state: Any) -> bool:
        """Callback de sucesso para o tick lento — executa na thread GTK."""
        self._profile_inflight = False
        if isinstance(state, dict):
            self._first_poll_succeeded = True
            self._render_slow_state(state)
        return False  # não repetir via GLib

    def _on_profile_state_failure(self, _exc: Exception) -> bool:
        """Callback de falha do tick lento — libera o guard de inflight."""
        self._profile_inflight = False
        return False  # não repetir via GLib

    def _tick_reconnect_state(self) -> bool:
        """Roda a 0.5 Hz: coordena a máquina de estado do header via thread worker."""
        # R4: pula este tick se o anterior ainda não retornou (mesmo motivo do
        # guard de inflight dos ticks rápido e lento).
        if self._reconnect_inflight:
            return True
        self._reconnect_inflight = True
        call_async(
            "daemon.state_full",
            None,
            on_success=self._on_reconnect_state_result,
            on_failure=self._on_reconnect_state_failure,
        )
        return True

    def _on_reconnect_state_result(self, state: Any) -> bool:
        self._reconnect_inflight = False
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
            # ADR-011: glyphs Geometric Shape (U+25CB ) via NCR — hooks
            # globais de sanitização strippam o literal, mas Pango respeita
            # a entidade `&#9675;`.
            header.set_markup(
                '<span foreground="#d33">'
                "&#9675; Desconectado — abra a aba Daemon e clique em Iniciar"
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
        self._reconnect_inflight = False
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

    @staticmethod
    def _connected_controllers(state: dict[str, Any]) -> list[dict[str, Any]]:
        """Controles conectados (FEAT-DSX-MULTI-CONTROLLER-01).

        Vem de `state["controllers"]` (bloco do `daemon.state_full`); o primário
        é o primeiro da lista (ordem de inserção). Lista vazia se o daemon não
        expõe o bloco (versão antiga) — os renderers caem no caminho single.
        """
        controllers = state.get("controllers")
        if not isinstance(controllers, list):
            return []
        return [
            c for c in controllers if isinstance(c, dict) and c.get("connected")
        ]

    @staticmethod
    def _controllers_transports(conectados: list[dict[str, Any]]) -> str:
        """'BT + USB' (transportes em texto plano, primário primeiro)."""
        return " + ".join(
            (c.get("transport") or "?").upper() for c in conectados
        )

    def _render_online(self, state: dict[str, Any]) -> None:
        """Header canônico de estado ONLINE —  verde + transport.

        Delega o pinta-completo-da-aba a `_render_live_state` e
        `_render_slow_state` (já chamados pelos ticks rápidos). Aqui só
        firma o header de forma idempotente.
        """
        connected = bool(state.get("connected"))
        transport = state.get("transport") or "—"
        header = self._get("header_connection")
        conectados = self._connected_controllers(state)
        if header is not None:
            if connected and len(conectados) > 1:
                # FEAT-DSX-MULTI-CONTROLLER-01: N controles — primário em negrito.
                partes = " + ".join(
                    f"<b>{(c.get('transport') or '?').upper()}</b>"
                    if c.get("is_primary")
                    else (c.get("transport") or "?").upper()
                    for c in conectados
                )
                header.set_markup(
                    f'<span foreground="#2d8">&#9679; {len(conectados)} controles: '
                    f"{partes}</span>"
                )
            elif connected:
                header.set_markup(
                    f'<span foreground="#2d8">&#9679; Conectado Via {transport.upper()}</span>'
                )
            else:
                header.set_markup(
                    '<span foreground="#d33">&#9675; Controle Desconectado</span>'
                )
        self._set_label("status_daemon", "Online")

    def _render_reconnecting(self) -> None:
        """Header intermediário — U+25D0 laranja + "tentando reconectar...".

        ADR-011: U+25D0 CIRCLE WITH LEFT HALF BLACK é Geometric Shape, não
        emoji. Emitido como NCR `&#9680;` para escapar do sanitizer global.
        """
        header = self._get("header_connection")
        if header is not None:
            header.set_markup(
                '<span foreground="#d90">&#9680; Tentando Reconectar...</span>'
            )
        self._set_label("status_daemon", "Reconectando")

    def _render_offline(self) -> None:
        header = self._get("header_connection")
        if header is not None:
            header.set_markup(
                '<span foreground="#d33">&#9675; Daemon Offline</span>'
            )
        self._set_label("status_daemon", "Offline")
        self._set_label("status_connection", "—")
        self._set_label("status_transport", "—")
        self._set_label("status_active_profile", "—")
        bar = self._get("status_battery_bar")
        if bar is not None:
            bar.set_fraction(0.0)
            bar.set_text("— %")
        # FEAT-DSX-CONTROLLER-SELECTOR-01: sem daemon, esconde o seletor.
        # Reseta _target_combo_visible junto (espelha o caminho <2 controles em
        # _refresh_controller_target_combo): sem isso o flag fica stale=True e,
        # ao reconectar com os MESMOS 2+ controles, o early-return idempotente
        # não chega ao box.show() e o seletor some pra sempre.
        combo = getattr(self, "_target_combo", None)
        if combo is not None:
            combo.hide()
            self._target_combo_visible = False
        self._reset_live_widgets()

    @staticmethod
    def _popup_is_open() -> bool:
        """True se um popup (combo/menu) detém um grab GTK neste instante.

        Usado para pausar os renders periódicos e não fechar o popup via
        re-layout (BUG-COMBO-POPUP-FLICKER-02). Robusto a um ``Gtk`` stubado nos
        testes (sem ``grab_get_current``) — nesse caso retorna ``False``.
        """
        grab = getattr(Gtk, "grab_get_current", None)
        return grab is not None and grab() is not None

    def _render_live_state(self, state: dict[str, Any]) -> None:
        # BUG-COMBO-POPUP-FLICKER-02: enquanto um popup (combo/menu) está aberto,
        # ele detém um grab GTK. As atualizações a 10 Hz dos labels (os sticks do
        # DualSense TREMEM em repouso → o texto "X: 128 Y: 127" muda de largura →
        # `queue_resize` → re-layout da janela) fechavam o popup na hora — em
        # XWayland E em Wayland nativo. Pausa o render vivo enquanto houver grab
        # ativo; retoma sozinho quando o popup fecha. Sem isso, NENHUM combo da
        # GUI consegue ficar aberto para a usuária escolher.
        if self._popup_is_open():
            return
        # GUI-ESTABILIDADE-COSMIC-REMEDIATION-01 / R3: NÃO reescrevemos o header
        # aqui a 10 Hz. O header é responsabilidade exclusiva de `_render_online`
        # (chamado pela máquina de reconnect a 0.5 Hz) e de
        # `_update_reconnect_state`. Reescrevê-lo a cada tick rápido gerava
        # repaint contínuo do banner mesmo com o controle parado (jank). Todos os
        # writes abaixo são DIFFADOS contra o último valor: só chamamos
        # set_fraction/set_text/set_markup quando o valor muda desde o tick
        # anterior.

        l2 = int(state.get("l2_raw", 0))
        r2 = int(state.get("r2_raw", 0))
        if l2 != self._last_l2:
            l2_bar = self._get("live_l2_bar")
            if l2_bar is not None:
                l2_bar.set_fraction(l2 / 255)
                l2_bar.set_text(f"{l2} / 255")
            self._last_l2 = l2
        if r2 != self._last_r2:
            r2_bar = self._get("live_r2_bar")
            if r2_bar is not None:
                r2_bar.set_fraction(r2 / 255)
                r2_bar.set_text(f"{r2} / 255")
            self._last_r2 = r2

        # Sticks — atualiza preview e labels numéricos, diffados por posição.
        lx = int(state.get("lx", 128))
        ly = int(state.get("ly", 128))
        rx = int(state.get("rx", 128))
        ry = int(state.get("ry", 128))

        # BUG-STATUS-LABEL-REFLOW-01: campo de LARGURA FIXA (3 chars, padding de
        # espaço em fonte monospace). Antes o texto "X: {lx}" mudava de largura ao
        # cruzar dígitos (5→10→100) → queue_resize → re-layout do painel a 10 Hz:
        # os glyphs/botões "respiravam" (aumentam e diminuem) durante o jogo. Com
        # o campo constante, a largura natural do label não muda → sem reflow.
        if lx != self._last_lx or ly != self._last_ly:
            if hasattr(self, "_stick_left"):
                self._stick_left.update(lx, ly)
            lx_label = self._get("live_lx_label")
            if lx_label is not None:
                lx_label.set_markup(
                    f'<span font_family="monospace" size="small">X: {lx:>3}  Y: {ly:>3}</span>'
                )
            self._last_lx = lx
            self._last_ly = ly
        if rx != self._last_rx or ry != self._last_ry:
            if hasattr(self, "_stick_right"):
                self._stick_right.update(rx, ry)
            rx_label = self._get("live_rx_label")
            if rx_label is not None:
                rx_label.set_markup(
                    f'<span font_family="monospace" size="small">X: {rx:>3}  Y: {ry:>3}</span>'
                )
            self._last_rx = rx
            self._last_ry = ry

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
        # BUG-GLYPH-SHARE-NAME-MISMATCH-01: o daemon emite "create" (BTN_SELECT),
        # mas o glyph/asset chama-se "share". Acende o glyph share quando o
        # daemon reporta create (ou share, por robustez).
        efetivos["share"] = ("share" in buttons_pressed) or ("create" in buttons_pressed)

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
        # Mesma proteção do render vivo (BUG-COMBO-POPUP-FLICKER-02): não mexe nos
        # widgets enquanto um popup está aberto, para não fechá-lo via re-layout.
        if self._popup_is_open():
            return
        connected = bool(state.get("connected"))
        transport = state.get("transport") or "—"
        battery = state.get("battery_pct")
        active_profile = state.get("active_profile") or "Nenhum"

        conectados = self._connected_controllers(state)
        if len(conectados) > 1:
            self._set_label(
                "status_connection", f"Conectado ({len(conectados)} controles)"
            )
            self._set_label("status_transport", self._controllers_transports(conectados))
        else:
            self._set_label(
                "status_connection", "Conectado" if connected else "Desconectado"
            )
            self._set_label(
                "status_transport", transport.upper() if transport != "—" else "—"
            )
        self._set_label("status_active_profile", active_profile)
        self._set_label("status_daemon", "Online")

        battery_bar = self._get("status_battery_bar")
        if battery_bar is not None:
            # UX-BATTERY-LABEL-01: o texto precisa estar VISÍVEL (show_text) e,
            # com 2+ controles, dizer DE QUAL controle é a leitura (a bateria
            # do state_full é a do primário) — antes a barra ficava muda e
            # ambígua com dois controles conectados.
            with contextlib.suppress(Exception):
                battery_bar.set_show_text(True)
            if battery is None:
                battery_bar.set_fraction(0.0)
                battery_bar.set_text("— %")
            else:
                battery_bar.set_fraction(battery / 100)
                suffix = " (Controle 1)" if len(conectados) > 1 else ""
                battery_bar.set_text(f"{battery} %{suffix}")

        # FEAT-DSX-CONTROLLER-SELECTOR-01: atualiza o seletor de controle-alvo
        # (aparece só com 2+ controles).
        self._refresh_controller_target_combo(state)

    def _reset_live_widgets(self) -> None:
        l2_bar = self._get("live_l2_bar")
        if l2_bar is not None:
            l2_bar.set_fraction(0.0)
            l2_bar.set_text("0 / 255")
        r2_bar = self._get("live_r2_bar")
        if r2_bar is not None:
            r2_bar.set_fraction(0.0)
            r2_bar.set_text("0 / 255")

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
        # R3: sincroniza o cache de diff com os valores de repouso que acabamos
        # de pintar, para o próximo tick não reescrever à toa (nem pular por
        # cache stale ao reconectar com o controle em repouso).
        self._last_l2 = 0
        self._last_r2 = 0
        self._last_lx = 128
        self._last_ly = 128
        self._last_rx = 128
        self._last_ry = 128

        # Títulos sem markup colorido
        titulo_esq = self._get("stick_left_title")
        titulo_dir = self._get("stick_right_title")
        if titulo_esq is not None:
            titulo_esq.set_markup("Analógico Esquerdo (L3)")
        if titulo_dir is not None:
            titulo_dir.set_markup("Analógico Direito (R3)")
