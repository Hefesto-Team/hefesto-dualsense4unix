"""Aba Status: polling ao vivo de daemon.state_full + update dos widgets.

Inclui a máquina de estado de reconnect (UX-RECONNECT-01): um tick dedicado
a cada 2s (`RECONNECT_POLL_INTERVAL_S`) observa o IPC e move o header entre
três estados visuais — `online`, `reconnecting`, `offline`. O polling rápido
dos widgets de live-state é independente e preserva a fluidez da aba Status.

Redesign STATUS-02 (aba Status vira 1 card por controle):
  - O Glade da aba tem só o frame "Estado" + um GtkScrolledWindow com o box
    `status_players_slot`; os cards (`ControllerCard`) são montados por
    código, um por controle CONECTADO do bloco `controllers` do state_full.
  - Reconstrução de cards SÓ quando o conjunto `(index, uniq)` muda
    (2 ticks com o mesmo conjunto = os MESMOS widgets, sem rebuild); a
    entrada-placeholder offline é filtrada por `connected`
    (HARM-CARD-FANTASMA-01) e não vira card fantasma.
  - O tick rápido distribui `controllers[i]` para o card i; o diff por
    seção vive dentro do card (`ControllerCard.update`).
  - Gate de timers (aceite do STATUS-02): NENHUMA ocorrência NOVA de
    timeout/idle do GLib em relação ao baseline da mixin — 2 periódicos em
    ms (100/500), 1 periódico em segundos (reconnect), 1 one-shot de 5 s e
    2 idle one-shot. `tests/unit/test_status_cards.py` trava esse diff.
"""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.actions.external_controllers import (
    button_labels_for,
    external_key,
    friendly_type,
    slot_label,
    slot_of,
    transport_label,
)
from hefesto_dualsense4unix.app.actions.home_actions import (
    vpad_degradation_text,
    wrapper_banner_text,
)
from hefesto_dualsense4unix.app.constants import (
    LIVE_POLL_INTERVAL_MS,
    RECONNECT_FAIL_THRESHOLD,
    RECONNECT_POLL_INTERVAL_S,
    STATE_POLL_INTERVAL_MS,
)
from hefesto_dualsense4unix.app.ipc_bridge import call_async

# GRID_BOTOES/ALL_BUTTONS/L2_R2_THRESHOLD moraram aqui até o STATUS-02;
# re-exportados (ver __all__) para os consumidores históricos da mixin.
from hefesto_dualsense4unix.app.widgets.controller_card import (
    ALL_BUTTONS,
    GRID_BOTOES,
    L2_R2_THRESHOLD,
    ControllerCard,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def _display_slot(entry: dict[str, Any]) -> int:
    """Numero de exibicao de um controle na GUI.

    Usa o ``player_slot`` de sessão — a identidade ESTÁVEL que sobrevive a
    desconectar/reconectar (o MESMO numero mostrado nos cards, na linha de
    comando e no applet), para o seletor e o card nunca discordarem sobre qual
    controle e o "Controle 1". Sem slot (controle sem MAC / registro ausente),
    cai na posicao 1-based (``index + 1``).
    """
    slot = entry.get("player_slot")
    if isinstance(slot, int) and not isinstance(slot, bool):
        return slot
    idx = entry.get("index")
    if isinstance(idx, int) and not isinstance(idx, bool):
        return idx + 1
    return 1


class StatusActionsMixin(WidgetAccessMixin):
    """Atualiza a aba Status em tempo real.

    Assume que `self.builder` contém os widgets do `main.glade`:
        status_connection, status_transport, status_battery_bar,
        status_battery_caption, status_active_profile, status_daemon,
        status_players_slot (box dos cards por controle — STATUS-02),
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
    # STATUS-02: cards por controle, keyed por `(index, uniq)` (com sufixo
    # posicional defensivo em duplicata). Os caches de diff dos widgets de
    # live-state (R3) migraram para DENTRO de cada ControllerCard.
    _status_cards: dict[tuple[Any, ...], Any]
    _status_card_keys: list[tuple[Any, ...]]
    # FEAT-DSX-CONTROLLER-SELECTOR-01: seletor de controle-alvo no banner.
    _target_combo: Any
    _target_combo_rows: list[tuple[str, int | None]]
    _target_combo_updating: bool
    _target_combo_visible: bool
    _target_combo_active: int
    _target_buttons: list[Any]
    # 8BIT-02: controles externos (não-DualSense) no seletor do topo + a ficha
    # secreta que abre ao clicar. Cache do inventário (fetch com throttle) +
    # botões próprios (fora do grupo de rádio dos DualSense).
    _external_buttons: list[Any]
    _externals: list[dict[str, Any]]
    _externals_fetch_ts: float = 0.0
    _externals_inflight: bool = False
    _externals_sig: tuple[str, ...] | None = None
    # PERFIL-04 (sprint perfis-por-controle): alvo de EDIÇÃO derivado do
    # seletor — o MAC normalizado (uniq) do controle selecionado, ou None em
    # "Todos"/alvo sem MAC (aí a edição segue GLOBAL, como sempre). As abas
    # Lightbar/Gatilhos leem `_edit_target_uniq` para gravar no override do
    # perfil (draft.controllers) e exibir os valores efetivos do alvo. Fica
    # em sync com o `output_target_index` do daemon a 2 Hz e é atualizado NA
    # HORA no clique do seletor (a próxima mexida já cai no override certo).
    _edit_target_uniq: str | None = None
    _edit_target_label: str | None = None
    _target_uniq_by_index: dict[int, str | None]
    _target_label_by_index: dict[int, str]
    _edit_badge: Any = None

    def install_status_polling(self) -> None:
        """Liga os timers da aba Status e prepara o container dos cards.

        Chamado uma vez no on_mount após o builder estar disponível. Os
        widgets de live-state não são mais singletons: cada controle ganha
        um ControllerCard montado sob demanda em `_sync_status_cards`
        (STATUS-02) — aqui só se zera o estado do conjunto.

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
        self._status_cards = {}
        self._status_card_keys = []
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
    # Cards por controle (STATUS-02)
    # ------------------------------------------------------------------

    @staticmethod
    def _status_card_keys_for(
        conectados: list[dict[str, Any]],
    ) -> list[tuple[Any, ...]]:
        """Chaves estáveis dos cards: ``(index, uniq)`` por controle CONECTADO.

        O filtro de ``connected`` já aconteceu (`_connected_controllers`) —
        é ele que impede o card fantasma da entrada-placeholder offline
        (HARM-CARD-FANTASMA-01: `describe_controllers` devolve UMA entrada
        com connected=False quando não há controle nenhum). ``uniq`` None
        (handle keyed por path, sem MAC) é chave VÁLIDA: o índice
        desambigua. Duplicata exata (defensivo — não deveria existir) ganha
        um sufixo posicional para nunca colidir no dict de cards.
        """
        keys: list[tuple[Any, ...]] = []
        vistos: dict[tuple[Any, Any], int] = {}
        for pos, c in enumerate(conectados):
            indice = c.get("index")
            if not isinstance(indice, int) or isinstance(indice, bool):
                indice = pos
            raw_uniq = c.get("uniq")
            uniq = raw_uniq if isinstance(raw_uniq, str) and raw_uniq else None
            base = (indice, uniq)
            repeticao = vistos.get(base, 0)
            vistos[base] = repeticao + 1
            keys.append(base if repeticao == 0 else (indice, uniq, repeticao))
        return keys

    def _sync_status_cards(self, state: dict[str, Any]) -> None:
        """Monta/atualiza os cards por controle a partir do ``state_full``.

        Reconstrução SÓ quando o CONJUNTO de chaves muda (2 ticks com o
        mesmo conjunto = os MESMOS objetos de widget, sem rebuild — jank
        zero a 10 Hz); o resto é `ControllerCard.update` com diff interno.
        Com 0 controles não há card nenhum e quem responde é o fallback
        offline existente da aba (UI-STATUS-OFFLINE-FALLBACK-01).
        """
        slot = self._get("status_players_slot")
        if slot is None or not hasattr(slot, "pack_start"):
            # Builder fake de testes de outras áreas (ou Glade antigo em
            # upgrade parcial): sem slot real, a aba segue sem cards.
            return
        if getattr(self, "_status_cards", None) is None:
            self._status_cards = {}
            self._status_card_keys = []
        conectados = self._connected_controllers(state)
        keys = self._status_card_keys_for(conectados)
        if keys != self._status_card_keys:
            self._rebuild_status_cards(slot, keys)
        for key, entry in zip(keys, conectados, strict=True):
            card = self._status_cards.get(key)
            if card is not None:
                card.update(entry, state)

    def _rebuild_status_cards(
        self, slot: Any, keys: list[tuple[Any, ...]]
    ) -> None:
        """Recria os cards — o conjunto de controles mudou."""
        for child in list(slot.get_children()):
            slot.remove(child)
            child.destroy()
        self._status_cards = {}
        self._status_card_keys = list(keys)
        # 2+ cards → sticks de 90px (compact); card único mantém o layout
        # equivalente ao da aba antiga (sticks 120px).
        compact = len(keys) >= 2
        for key in keys:
            card = ControllerCard(compact=compact)
            self._status_cards[key] = card
            slot.pack_start(card, False, False, 0)
            card.show_all()

    def _clear_status_cards(self) -> None:
        """Remove todos os cards (daemon offline — nenhum controle conhecido)."""
        slot = self._get("status_players_slot")
        if slot is not None and hasattr(slot, "get_children"):
            for child in list(slot.get_children()):
                slot.remove(child)
                child.destroy()
        self._status_cards = {}
        self._status_card_keys = []

    # ------------------------------------------------------------------
    # Seletor de controle-alvo (FEAT-DSX-CONTROLLER-SELECTOR-01)
    # ------------------------------------------------------------------

    @staticmethod
    def _controller_target_rows(
        conectados: list[dict[str, Any]],
    ) -> list[tuple[str, int | None]]:
        """Linhas do seletor: ``[(rótulo, índice_do_controle | None)]``.

        Posição 0 é sempre "Todos os controles" (None = broadcast). As demais,
        uma por controle conectado, rotuladas "Controle N — TRANSPORTE" — N é o
        ``player_slot`` de sessão (COR-01/D6: o MESMO número dos cards, da linha
        de comando e do applet, estável entre replugs), com fallback para a
        posição 1-based quando não há slot. O índice CARREGADO na linha segue o
        ``index`` 0-based do bloco ``controllers`` (o mesmo que o IPC
        ``controller.target.set`` espera). FEAT-DSX-CONTROLLER-SELECTOR-01.
        """
        rows: list[tuple[str, int | None]] = [(_("Todos os controles"), None)]
        for c in conectados:
            idx = int(c.get("index", 0))
            transporte = (c.get("transport") or "?").upper()
            rows.append(
                (_("Controle {n} — {t}").format(n=_display_slot(c), t=transporte), idx)
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
        # 8BIT-02: controles externos (não-DualSense) no seletor do topo + a
        # "ficha secreta" que abre ao clicar num deles. Cache do inventário
        # (fetch opt-in, caro — throttle no tick lento) + botões próprios.
        self._external_buttons = []
        self._externals = []
        self._externals_fetch_ts = 0.0
        self._externals_inflight = False
        self._externals_sig = None
        # PERFIL-04: estado do alvo de edição por-controle.
        self._edit_target_uniq = None
        self._edit_target_label = None
        self._target_uniq_by_index = {}
        self._target_label_by_index = {}
        self._edit_badge = None
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
        # PERFIL-04: badge "Editando: Controle N (BT)" — rótulo inline no
        # banner (nunca popup — cosmic-epoch#2497), visível só quando um
        # controle com MAC está selecionado. Deixa explícito que as abas
        # Lightbar/Gatilhos estão editando UM controle dentro do perfil.
        badge = Gtk.Label()
        with contextlib.suppress(Exception):
            badge.get_style_context().add_class("dim-label")
        badge.set_no_show_all(True)
        badge.hide()
        header_bar.pack_end(badge, False, False, 6)
        self._edit_badge = badge

    @staticmethod
    def _short_target_label(label: str) -> str:
        """'Todos os controles' -> 'Todos'; 'Controle 1 — BT' -> 'Sony 1 · BT'.

        Os controles adotados são sempre DualSense (backend DualSense-only), então
        o chip do seletor mostra a marca 'Sony' + o número (``player_slot``), para
        ficar consistente com o botão do controle externo ('8BitDo 3 · BT'). O
        rótulo canônico 'Controle N' segue INTACTO no tooltip e no badge de edição
        (convenção unificada COR-01/D6) — só o texto compacto do chip ganha a marca.
        """
        if label.startswith("Todos"):
            return "Todos"
        return label.replace("Controle ", "Sony ").replace(" — ", " · ")

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
        # 8BIT-02: os externos NÃO entram no grupo de rádio (não são alvo de
        # edição do output). São GtkButton comuns; clicar abre a ficha secreta
        # só daquele controle (janela read-only), sem trocar o alvo de edição.
        self._external_buttons = []
        externals = getattr(self, "_externals", [])
        # Slot GLOBAL: continua a numeração dos DualSense (rows menos "Todos").
        dualsense_count = max(0, len(self._target_buttons) - 1)
        rotulos = button_labels_for(externals, dualsense_count)
        for i, (ext, rotulo) in enumerate(zip(externals, rotulos, strict=False)):
            slot = slot_of(ext, dualsense_count, i)
            eb = Gtk.Button.new_with_label(rotulo)
            eb.set_tooltip_text(
                f"Controle {slot_label(slot)}: {friendly_type(ext)} — "
                f"{transport_label(ext)} "
                "(clique para ver; o Hefesto não mexe no que ele faz)"
            )
            with contextlib.suppress(Exception):
                eb.get_style_context().add_class("hefesto-external-btn")
            eb.connect("clicked", self._on_external_clicked, external_key(ext), slot)
            eb.show()
            box.pack_start(eb, False, False, 0)
            self._external_buttons.append(eb)

    def _maybe_fetch_externals(self) -> None:
        """Atualiza o inventário de externos (8BIT-01) com throttle (~4 s).

        Caro (enumera evdev + sonda de holders — 10-40 ms + subprocess), então
        NUNCA no caminho quente: só no tick lento, e no máximo a cada 4 s. O
        resultado alimenta os botões de externos no próximo refresh do seletor.

        No-op sem o seletor inicializado (`_init_controller_target_combo` não
        rodou): cobre os testes de widget parciais e evita IPC fora da GUI real.
        """
        if getattr(self, "_target_combo", None) is None:
            return
        now = GLib.get_monotonic_time() / 1_000_000.0
        if self._externals_inflight or (now - self._externals_fetch_ts) < 4.0:
            return
        self._externals_fetch_ts = now
        self._externals_inflight = True
        call_async(
            "controller.list",
            {"external": True},
            on_success=self._on_externals_result,
            on_failure=lambda _e: self._on_externals_done(),
            # O inventário externo enumera TODOS os /dev/input + sonda de
            # holders (subprocess) — 10-40 ms + ~até 1 s. O default de 0.25 s
            # do call_async estouraria; damos folga (é opt-in, tick lento).
            timeout_s=3.0,
        )

    def _on_externals_result(self, result: Any) -> bool:
        ext = result.get("external") if isinstance(result, dict) else None
        self._externals = ext if isinstance(ext, list) else []
        return self._on_externals_done()

    def _on_externals_done(self) -> bool:
        self._externals_inflight = False
        return False

    def _on_external_clicked(
        self, _button: Any, key: str, slot: int | None
    ) -> None:
        """Abre a ficha secreta read-only do controle externo `key` (8BIT-02).

        `slot` = número GLOBAL de co-op (mesmo do LED de player) — a ficha o
        mostra para GUI e LED nunca discordarem. NUMA-05: ``None`` (registry
        ainda sem opinião) é repassado como está — a ficha mostra "—", nunca
        inventa uma posição.
        """
        ext = next(
            (e for e in getattr(self, "_externals", []) if external_key(e) == key),
            None,
        )
        if ext is None:
            return
        from hefesto_dualsense4unix.app import gui_dialogs

        window = self._get("main_window")
        with contextlib.suppress(Exception):
            gui_dialogs.show_external_controller(parent=window, entry=ext, slot=slot)

    def _set_target_active(self, pos: int) -> None:
        """Marca o botão na posição ``pos`` como ativo (sem disparar IPC)."""
        if 0 <= pos < len(self._target_buttons):
            self._target_buttons[pos].set_active(True)

    # ------------------------------------------------------------------
    # Alvo de edição por-controle (PERFIL-04)
    # ------------------------------------------------------------------

    @staticmethod
    def _edit_badge_text(label: str | None) -> str:
        """Texto do badge de edição por-controle; vazio = badge escondido."""
        if not label:
            return ""
        return _("Editando: {alvo}").format(alvo=label)

    def _update_target_maps(self, conectados: list[dict[str, Any]]) -> None:
        """Recalcula index→uniq e index→rótulo a partir do ``state_full``.

        O ``uniq`` (MAC normalizado, estável entre USB e BT) vem do bloco
        ``controllers`` que o daemon já expõe. Controle sem MAC (key por
        path) fica com uniq None — a edição dele segue GLOBAL, como hoje.
        """
        uniq_by_index: dict[int, str | None] = {}
        label_by_index: dict[int, str] = {}
        for c in conectados:
            idx = int(c.get("index", 0))
            raw_uniq = c.get("uniq")
            uniq_by_index[idx] = (
                raw_uniq if isinstance(raw_uniq, str) and raw_uniq else None
            )
            transporte = (c.get("transport") or "?").upper()
            label_by_index[idx] = _("Controle {n} ({t})").format(
                n=_display_slot(c), t=transporte
            )
        self._target_uniq_by_index = uniq_by_index
        self._target_label_by_index = label_by_index

    def _sync_edit_target(self, target_index: int | None) -> None:
        """Deriva o alvo de EDIÇÃO (uniq) do índice do seletor.

        Idempotente: só atualiza badge e re-popula as abas por-controle
        (lightbar/gatilhos) quando o alvo efetivamente muda. ``None`` =
        "Todos" (edição global, badge some).
        """
        uniq: str | None = None
        label: str | None = None
        if target_index is not None:
            uniq = getattr(self, "_target_uniq_by_index", {}).get(target_index)
            label = getattr(self, "_target_label_by_index", {}).get(target_index)
            if uniq is None and label is not None:
                # Alvo sem MAC estável (regra do sprint): edita o global,
                # com trilha em vez de silêncio.
                logger.debug(
                    "edit_target_sem_mac_edita_global", indice=target_index
                )
        if uniq == self._edit_target_uniq and label == self._edit_target_label:
            return
        self._edit_target_uniq = uniq
        self._edit_target_label = label
        self._update_edit_badge()
        self._refresh_target_tabs()

    def _update_edit_badge(self) -> None:
        """Mostra/esconde o badge conforme o alvo de edição atual."""
        badge = getattr(self, "_edit_badge", None)
        if badge is None:
            return
        texto = self._edit_badge_text(
            self._edit_target_label if self._edit_target_uniq else None
        )
        if texto:
            badge.set_text(texto)
            badge.show()
        else:
            badge.hide()

    def _refresh_target_tabs(self) -> None:
        """Re-popula as abas por-controle para exibir os valores do alvo novo."""
        for nome in ("_refresh_lightbar_from_draft", "_refresh_triggers_from_draft"):
            fn = getattr(self, nome, None)
            if fn is None:
                continue
            try:
                fn()
            except Exception as exc:
                logger.warning(
                    "edit_target_refresh_aba_falhou", metodo=nome, erro=str(exc)
                )

    def _refresh_controller_target_combo(self, state: dict[str, Any]) -> None:
        """Atualiza os botões do seletor; reflete ``output_target_index``.

        IDEMPOTENTE: só reconstrói/marca quando rótulos/posição/visibilidade
        mudam. Some com <2 controles. FEAT-DSX-CONTROLLER-SELECTOR-01.
        """
        box = getattr(self, "_target_combo", None)
        if box is None:
            return
        conectados = self._connected_controllers(state)
        # PERFIL-04: mantém os mapas index→uniq/rótulo e o alvo de edição em
        # sync com o daemon (cobre alvo trocado por CLI/applet e o boot).
        self._update_target_maps(conectados)
        target_index = state.get("output_target_index")
        if not isinstance(target_index, int) or isinstance(target_index, bool):
            target_index = None
        # getattr defensivo: Hosts de teste montam o seletor sem passar pelo
        # `_init_controller_target_combo` (que semeia `_externals`).
        externals = getattr(self, "_externals", [])
        # 8BIT-02: o seletor aparece com 2+ controles NO TOTAL (DualSense +
        # externos) — assim o 8BitDo/Nintendo entra no topo mesmo com 1 DualSense.
        total = len(conectados) + len(externals)
        if total < 2:
            self._sync_edit_target(None)
            if self._target_combo_visible:  # só esconde na TRANSIÇÃO
                box.hide()
                self._target_combo_visible = False
            return
        # Edição por-controle SÓ existe com 2+ DualSense (os externos não são
        # alvo — o Hefesto não mexe neles). Com <2 DualSense, só "Todos".
        editavel = len(conectados) >= 2
        self._sync_edit_target(target_index if editavel else None)
        rows: list[tuple[str, int | None]] = (
            self._controller_target_rows(conectados)
            if editavel
            else [(_("Todos os controles"), None)]
        )
        ext_sig = tuple(external_key(e) for e in externals)
        labels = [label for label, _ in rows]
        rows_changed = (
            labels != [label for label, _ in self._target_combo_rows]
            or ext_sig != self._externals_sig
        )
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
                self._externals_sig = ext_sig
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
        # PERFIL-04: o alvo de edição muda NA HORA (não espera o tick de 2 Hz)
        # — a usuária clica "1 · BT" e a próxima mexida na lightbar já cai no
        # override certo do draft. Se o IPC falhar, o sync de 2 Hz reconverge
        # com o estado real do daemon.
        self._sync_edit_target(index)
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
        # BUG-STATUS-TICK-HIDDEN-TAB-01: sticks/glyphs/gatilhos só existem na
        # aba Status (página 1) — com outra aba visível, 10 Hz de state_full
        # só saturam o worker compartilhado. O poller lento (2 Hz) segue vivo
        # para header/reconnect.
        notebook = self._get("main_notebook")
        if notebook is not None and notebook.get_current_page() != 1:
            return True
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
        precisa abrir a aba Sistema e ligar o Hefesto.
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
                "&#9675; Desconectado — abra a aba Sistema e clique em \"Ligar o Hefesto\""
                "</span>"
            )
        self._set_label("status_daemon", "Sem resposta (ligue na aba Sistema)")
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
        self._set_label("status_daemon", "Ligado")

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
                '<span foreground="#d33">'
                "&#9675; Hefesto desligado — abra a aba Sistema e clique em "
                "\"Ligar o Hefesto\""
                "</span>"
            )
        self._set_label("status_daemon", "Desligado")
        self._set_label("status_connection", "—")
        self._set_label("status_transport", "—")
        self._set_label("status_active_profile", "—")
        # STATUS-02: offline volta ao layout single — a linha de bateria do
        # frame Estado reaparece (os cards vão embora junto com o daemon).
        self._set_battery_row_visible(True)
        bar = self._get("status_battery_bar")
        if bar is not None:
            bar.set_fraction(0.0)
            bar.set_text("— %")
        # STATUS-02: sem daemon não há controle conhecido — nenhum card
        # (o fallback offline da aba é o frame Estado + header, como sempre).
        self._clear_status_cards()
        # FEAT-DSX-CONTROLLER-SELECTOR-01: sem daemon, esconde o seletor.
        # Reseta _target_combo_visible junto (espelha o caminho <2 controles em
        # _refresh_controller_target_combo): sem isso o flag fica stale=True e,
        # ao reconectar com os MESMOS 2+ controles, o early-return idempotente
        # não chega ao box.show() e o seletor some pra sempre.
        combo = getattr(self, "_target_combo", None)
        if combo is not None:
            combo.hide()
            self._target_combo_visible = False
        # PERFIL-04: sem daemon não há alvo de edição por-controle — a edição
        # volta ao global e o badge some (idempotente se já estava global).
        self._sync_edit_target(None)
        # UX-03: daemon offline não é degradação do vpad — o banner some junto.
        self._refresh_vpad_banner(None)
        # GUI-05: idem para o aviso "jogo sem wrapper".
        self._refresh_wrapper_banner(None)
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
        # ele detém um grab GTK. As atualizações a 10 Hz (os sticks do DualSense
        # TREMEM em repouso → re-layout da janela) fechavam o popup na hora — em
        # XWayland E em Wayland nativo. Pausa o render vivo enquanto houver grab
        # ativo; retoma sozinho quando o popup fecha. Sem isso, NENHUM combo da
        # GUI consegue ficar aberto para a usuária escolher.
        if self._popup_is_open():
            return
        # GUI-ESTABILIDADE-COSMIC-REMEDIATION-01 / R3: o header NÃO é reescrito
        # aqui a 10 Hz (é da máquina de reconnect, a 0.5 Hz). STATUS-02: o tick
        # rápido só distribui `controllers[i]` do state_full para o card de
        # cada controle — o diff por widget vive DENTRO do ControllerCard.
        self._sync_status_cards(state)

    def _render_slow_state(self, state: dict[str, Any]) -> None:
        # Mesma proteção do render vivo (BUG-COMBO-POPUP-FLICKER-02): não mexe nos
        # widgets enquanto um popup está aberto, para não fechá-lo via re-layout.
        if self._popup_is_open():
            return
        # 8BIT-02: inventário de externos (opt-in, caro) atualizado no tick lento
        # com throttle próprio — alimenta os botões de externos do seletor.
        self._maybe_fetch_externals()
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
        self._set_label("status_daemon", "Ligado")

        # STATUS-02: com 2+ controles cada card tem a PRÓPRIA bateria — a
        # linha do frame Estado (que só sabia falar do primário, com o
        # sufixo ambíguo "(Controle 1)" do UX-BATTERY-LABEL-01) some em vez
        # de duplicar/ambiguar a leitura.
        self._set_battery_row_visible(len(conectados) <= 1)
        battery_bar = self._get("status_battery_bar")
        if battery_bar is not None and len(conectados) <= 1:
            # UX-BATTERY-LABEL-01: o texto precisa estar VISÍVEL (show_text).
            with contextlib.suppress(Exception):
                battery_bar.set_show_text(True)
            if battery is None:
                battery_bar.set_fraction(0.0)
                battery_bar.set_text("— %")
            else:
                battery_bar.set_fraction(battery / 100)
                battery_bar.set_text(f"{battery} %")

        # FEAT-DSX-CONTROLLER-SELECTOR-01: atualiza o seletor de controle-alvo
        # (aparece só com 2+ controles).
        self._refresh_controller_target_combo(state)

        # UX-03: banner de degradação do vpad (máscara DualSense em uinput).
        self._refresh_vpad_banner(state)

        # GUI-05 item 3: banner "jogo sem wrapper" (honestidade do dedup).
        self._refresh_wrapper_banner(state)

        # STATUS-02: o tick lento também mantém o CONJUNTO de cards em dia —
        # com a aba Status fora de foco o tick rápido pausa, e sem isto a
        # troca de aba mostraria cards do conjunto antigo por até 100 ms.
        self._sync_status_cards(state)

    def _set_battery_row_visible(self, visible: bool) -> None:
        """Mostra/esconde a linha de bateria do frame Estado (caption + barra)."""
        for widget_id in ("status_battery_caption", "status_battery_bar"):
            widget = self._get(widget_id)
            if widget is not None and hasattr(widget, "set_visible"):
                widget.set_visible(visible)

    def _refresh_vpad_banner(self, state: dict[str, Any] | None) -> None:
        """UX-03: banner de degradação do vpad primário na aba Status.

        Consome `gamepad_emulation.backend` do state_full pela MESMA função
        pura da aba Início (`vpad_degradation_text`) — as duas abas nunca
        discordam sobre o estado do vpad. O widget é um GtkLabel fixo do Glade
        (`status_vpad_banner`), sempre inline: nada de popup/popover
        (cosmic-epoch#2497). Backend ausente/"" é transitório e não acende.
        """
        banner = self._get("status_vpad_banner")
        if banner is None:
            return
        aviso = vpad_degradation_text(state)
        if aviso:
            banner.set_text(aviso)
        banner.set_visible(bool(aviso))

    def _refresh_wrapper_banner(self, state: dict[str, Any] | None) -> None:
        """GUI-05 item 3: banner "jogo sem wrapper" na aba Status.

        Consome `gamepad_emulation.wrapper_used` do state_full pela MESMA
        função pura da aba Início (`wrapper_banner_text`) — as duas abas nunca
        discordam. Widget fixo do Glade (`status_wrapper_banner`), sempre
        inline: nada de popup/popover (cosmic-epoch#2497). Campo ausente/None
        (sem jogo aberto, daemon antigo) não acende nada.
        """
        banner = self._get("status_wrapper_banner")
        if banner is None:
            return
        aviso = wrapper_banner_text(state)
        if aviso:
            banner.set_text(aviso)
        banner.set_visible(bool(aviso))

    def _reset_live_widgets(self) -> None:
        """IPC sem resposta neste tick: os cards mostram "—".

        Contrato do STATUS-02: NUNCA exibir o último valor de inputs como se
        estivesse vivo — cada card troca a área de inputs pelo "—" (sem
        leitor) e invalida os caches de diff, para o próximo tick bom
        repintar tudo.
        """
        for card in getattr(self, "_status_cards", {}).values():
            card.reset_inputs()


__all__ = [
    "ALL_BUTTONS",
    "GRID_BOTOES",
    "L2_R2_THRESHOLD",
    "StatusActionsMixin",
]
