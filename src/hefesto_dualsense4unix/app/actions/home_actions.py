"""Aba Início — comutador de MODO do sistema + controles + desligar de verdade.

FEAT-GUI-HOME-TAB-01. A primeira aba responde as três perguntas que a interface
antiga espalhava por quatro lugares:

1. "Em que modo o sistema está?" — comutador Desktop / Jogo (gamepad) / Jogo
   nativo, com a máscara (DualSense/Xbox) quando faz sentido. Reflete também o
   modo ligado POR PERFIL (FEAT-PROFILE-MODE-01). LEIGO-01: não há mais toggle
   de co-op — cada controle é um jogador, sempre; a aba só INFORMA quantos.
2. "Quais controles estão conectados?" — um card por controle físico, com
   transporte, jogador (P1/P2…, o número que o JOGO vê — LEIGO-01b), bateria e o
   aviso de grab degradado (input dobrado). LEIGO-02: o fim do MAC saiu do card
   — ela distingue os controles pela COR da luz e pelo LED de jogador, não por
   um hash que não está escrito em lugar nenhum do aparelho.
3. "Como desligo o hefesto DE VERDADE?" — botão dedicado que para o daemon e
   NÃO o religa ao reabrir/atualizar a GUI (diferente do "Desligar o Hefesto"
   da aba Sistema, que o `ensure_daemon_running` ressuscitava sem avisar).

Todo widget é montado em código dentro de `tab_home_box` (Glade só reserva o
container) — padrão dos widgets dinâmicos, imune ao bug de popup do cosmic-comp
(botões sempre visíveis, sem dropdown).
"""
from __future__ import annotations

import contextlib
from typing import Any

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_GAMEPAD,
    MODE_IPC_TIMEOUT_S,
    STATE_IPC_TIMEOUT_S,
    apply_mode,
    mode_of_state,
)
from hefesto_dualsense4unix.app.ipc_bridge import call_async
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Intervalo do poller da aba Início (só age com a aba visível).
HOME_POLL_INTERVAL_MS = 2000

#: HARM-01: a folga da troca de modo mora em `mode_transition` (dono único) —
#: aqui ela vale também para o co-op e a máscara, que criam/desmontam os mesmos
#: uinput e não cabem nos 0.25s default do call_async.
_MODE_IPC_TIMEOUT_S = MODE_IPC_TIMEOUT_S

#: HARM-15: o refresh também não cabe nos 0.25s default do call_async — sem folga
#: o `_fail` pintava a aba inteira de "Daemon desligado" com o daemon VIVO. Vem de
#: `mode_transition` (dono único): a aba Mouse lê o MESMO state_full para saber o
#: modo e precisa exatamente da mesma folga.
_STATE_IPC_TIMEOUT_S = STATE_IPC_TIMEOUT_S

# UX-MODE-TERMS-01: rótulos pela AÇÃO da usuária ("o que o controle faz
# agora"), não pela tecnologia — "gamepad virtual"/"nativo" viravam jargão.
_MODE_ITEMS = [
    ("desktop", "Controlar o PC"),
    ("gamepad", "Jogar pelo Hefesto"),
    ("native", "Jogar direto (Sony)"),
]

# LEIGO-02: "(vibra)"/"(sem vibrar)" eram verdade enquanto a máscara DualSense
# não vibrava; com o vpad uhid (SPRINT-UHID-VPAD-01) as duas vibram, então o
# rótulo antigo virou MENTIRA. O que resta de diferença é o que a usuária vê na
# tela do jogo: os desenhos dos botões. Xbox segue na lista porque há jogos que
# só entendem XInput.
_FLAVOR_ITEMS = [
    ("xbox", "Xbox 360"),
    ("dualsense", "DualSense (botões PlayStation)"),
]

_MODE_DESCRIPTIONS = {
    "desktop": (
        "O controle vira mouse/teclado do computador (ajustes nas abas "
        "Mouse e Teclado)."
    ),
    # LEIGO-02: a recomendação de 3 linhas ("use a máscara Xbox 360 e cole as
    # opções da Steam") existia só para contornar a máscara DualSense que não
    # vibrava. O SPRINT-UHID-VPAD-01 curou isso (o gamepad virtual é um
    # DualSense de verdade via /dev/uhid, e vibra) — o trade-off morreu com ele,
    # e a frase que o explicava morre junto.
    "gamepad": (
        "Escolha certa para quase todos os jogos: o Hefesto acende as luzes, "
        "faz o controle vibrar e dá um jogador para cada controle."
    ),
    # SPRINT-GAME-RUMBLE-01: sem o Hefesto no meio, o jogo fala direto com o
    # DualSense — inclusive pelo canal de áudio (haptics do PS5), que é o que
    # dispara o travamento/desconexão em alguns títulos.
    "native": (
        "Só para jogos feitos para o PlayStation 5: os gatilhos ficam duros de "
        "apertar, como no PS5. Alguns jogos derrubam o controle no meio da "
        "partida neste modo — se acontecer, volte para \"Jogar pelo Hefesto\"."
    ),
}

# LEIGO-02: o glossário enfileirava 4 conceitos, dois deles mortos — "Pausar"
# não é mais botão de lugar nenhum e "Jogar direto" já é um dos três botões
# logo acima (com descrição própria). Sobram os dois que a aba NÃO explica por
# si: o "Modo jogo" (que mora em outra aba) e o desligar de verdade.
# ONDA-U (U1): o "ligar de novo" deixou de mandar pra aba Sistema — o mesmo
# botão vira "Ligar o Hefesto" nesta própria aba (toggle in-place).
_GLOSSARY = (
    "Modo jogo (aba Emulação): pausa só o mouse/teclado, sem soltar o "
    "controle.  ·  "
    'Desligar Hefesto: para tudo até você clicar em "Ligar o Hefesto" aqui '
    "mesmo, nesta aba."
)

# ONDA-U (U1): rótulos do botão único de energia da aba Início — ele TROCA de
# texto/ação conforme o daemon está online ou offline (nunca dois botões).
_BTN_LABEL_ONLINE = "Desligar Hefesto (voltar ao Linux puro)"
_BTN_LABEL_OFFLINE = "Ligar o Hefesto"


def _mode_label(mode_id: object) -> str:
    """Rótulo do modo como a usuária o lê no botão (LEIGO-02) — função pura.

    Os toasts ecoavam o id interno ("gamepad", "native"): palavras que não
    aparecem em lugar nenhum da interface. O fallback devolve o próprio id para
    um modo desconhecido (payload de daemon mais novo) ser visível em vez de
    virar texto vazio.
    """
    return dict(_MODE_ITEMS).get(str(mode_id), str(mode_id))


def _flavor_label(flavor_id: object) -> str:
    """Idem para a aparência do controle no jogo ("xbox" → "Xbox 360")."""
    return dict(_FLAVOR_ITEMS).get(str(flavor_id), str(flavor_id))


# UX-03 (SPRINT-UX-AUTOSWITCH-01): texto do banner de degradação do vpad.
# "Reconecte o controle" foi REFUTADO pela revisão adversarial — a promoção
# uinput→uhid só acontece no boot do daemon (único call site do
# `upgrade_primary_vpad_to_uhid` é o connect, `lifecycle.py`), então reconectar
# NÃO cura nada; o conselho honesto é reiniciar o Hefesto pela aba Sistema.
VPAD_DEGRADED_TEXT = (
    "O gamepad virtual subiu no modo simples: a vibração e a separação do "
    "controle físico não estão garantidas. Reinicie o Hefesto na aba Sistema."
)

# DEDUP-06: um jogador do co-op degradado em uinput com o jogo aberto sob o
# IGNORE congelado é AQUELE jogador com zero controle — o banner do primário
# não o cobria (a dedup quebrada voltava a ser silenciosa, o que o item P0
# proíbe). Sempre banner inline, nunca popover (cosmic-epoch#2497).
VPAD_COOP_DEGRADED_TEXT = (
    "O gamepad virtual de um dos jogadores do co-op subiu no modo simples: "
    "aquele jogador pode ficar sem vibração — e sem controle, se o jogo foi "
    "aberto com a desduplicação ligada. Reinicie o Hefesto na aba Sistema."
)

# DEDUP-06 (achado novo da revisão): Modo Nativo com o físico em Bluetooth é
# estruturalmente frágil — o SDL pode não enxergar o DualSense BT nem sem
# launch option (o backend evdev deferencia ao HIDAPI, que não lê o hidraw BT).
NATIVE_BT_FRAGIL_TEXT = (
    "Modo Nativo com o controle em Bluetooth: alguns jogos não enxergam o "
    "DualSense por BT (limite do SDL). Se o jogo não vir o controle, use o "
    "cabo USB ou volte para a emulação de gamepad."
)


# GUI-05 item 3 (honestidade do dedup): texto do banner "jogo sem wrapper".
# Discreto e pro leigo — diz a consequência (duplicar) e o caminho (aba
# Sistema), sem jargão de env/vdf.
WRAPPER_MISSING_TEXT = (
    "O jogo está rodando sem o hefesto-launch — controles podem duplicar. "
    "Copie as opções na aba Sistema."
)


def wrapper_banner_text(state: dict[str, Any] | None) -> str | None:
    """Texto do banner "jogo sem wrapper"; ``None`` quando não há aviso.

    Contrato do `state_full.gamepad_emulation.wrapper_used` (produzido pelo
    daemon cruzando o marker do `hefesto-launch` com a janela steam_app):

    - ``False`` = há jogo aberto E ele NÃO passou pelo wrapper → banner;
    - ``True`` = o jogo abriu pelo wrapper → sem banner;
    - ``None``/ausente = sem jogo aberto, ou daemon antigo sem o campo →
      sem banner (nunca alarme falso por payload incompleto).

    Só o ``False`` LITERAL acende — função pura, consumida pelas abas Início
    e Status (mesmo desenho do `vpad_degradation_text`).
    """
    if not isinstance(state, dict):
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    if gamepad.get("wrapper_used") is False:
        return WRAPPER_MISSING_TEXT
    return None


def vpad_degradation_text(state: dict[str, Any] | None) -> str | None:
    """Texto do banner de degradação do vpad; ``None`` quando não há aviso.

    UX-03: o `state_full.gamepad_emulation` expõe `backend` ("uhid" = DualSense
    Edge real com hidraw; "uinput" = fallback sem hidraw). Máscara DualSense no
    backend uinput significa vibração in-game morta e separação do controle
    físico não garantida — sem o banner, a usuária conclui que "o hefesto não
    funciona". Função pura (padrão `_flavor_label`), consumida pelas abas
    Início e Status.

    DEDUP-06 (o guard anti-veneno): o banner também fala pelos jogadores do
    co-op — `dedup_ok=False` com motivo `jogador_N_uinput` acende o aviso
    mesmo com o vpad primário saudável — e pelo estado BT+Nativo
    (`native_bt_fragil` do state_full), que tem aviso próprio.

    Sem alarme falso: backend ausente/"" é transitório real (vpad subindo, o
    `_gamepad_device` ainda None — o `ipc_handlers` só emite a chave com device
    vivo) e NÃO acende o banner; `dedup_motivo="vpad_ausente"` idem (mesmo
    transitório visto pelo guard); máscara xbox em uinput é o desenho normal;
    fora do modo gamepad não há vpad a avaliar.
    """
    if not isinstance(state, dict):
        return None
    if state.get("native_bt_fragil") is True:
        return NATIVE_BT_FRAGIL_TEXT
    if mode_of_state(state) != MODE_GAMEPAD:
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    if gamepad.get("flavor") != "dualsense":
        return None
    if gamepad.get("backend") == "uinput":
        return VPAD_DEGRADED_TEXT
    motivo = gamepad.get("dedup_motivo")
    if (
        gamepad.get("dedup_ok") is False
        and isinstance(motivo, str)
        and "jogador" in motivo
    ):
        return VPAD_COOP_DEGRADED_TEXT
    return None


# ONDA-U (U2/U10): texto do "Renumerar agora" quando bloqueado por sessão de
# jogo aberta — mesmo gate do IPC (`identity.renumber`), pra usuária ver o
# "porquê" ANTES de clicar, em vez de levar um {ok: false} sem explicação.
RENUMBER_GAME_OPEN_TEXT = (
    "Feche o jogo para renumerar — evita repintar o controle em uso no meio "
    "da partida."
)


def _renumber_gate_text(state: dict[str, Any] | None) -> str | None:
    """Aviso do "Renumerar agora" bloqueado; ``None`` = liberado — função pura
    (padrão ``vpad_degradation_text``/``wrapper_banner_text``).

    Espelha o MESMO critério do handler de ``identity.renumber``
    (``display_authority == 'game'`` via ``state_full.game_signal.
    authority``) — nunca uma segunda fonte da verdade; se o daemon ainda não
    fiou o sinal (``game_signal`` ausente/authority desconhecida), o botão
    fica liberado (sem alarme falso).
    """
    if not isinstance(state, dict):
        return None
    game_signal = state.get("game_signal")
    if not isinstance(game_signal, dict):
        return None
    if game_signal.get("authority") == "game":
        return RENUMBER_GAME_OPEN_TEXT
    return None


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


def _format_players_hint(controllers: list[dict[str, Any]]) -> str:
    """Frase que substituiu o checkbox de co-op (LEIGO-01) — função pura.

    Só fala quando há o que dizer: com um controle só não existe pergunta a
    responder. E só afirma "N jogadores" quando o daemon de fato numerou N
    jogadores distintos (campo `player`) — enquanto o segundo jogador não subiu,
    o jogo ainda vê um gamepad só e a frase seria mentira.
    """
    if len(controllers) < 2:
        return ""
    players = {
        c.get("player")
        for c in controllers
        if isinstance(c.get("player"), int) and not isinstance(c.get("player"), bool)
    }
    if len(players) < 2:
        return ""
    return f"{len(controllers)} controles = {len(players)} jogadores"


def _format_controller_title(position: int, player: object) -> str:
    """Título do card: "Controle 2 — P3" (função pura).

    LEIGO-01b: `position` (1-based) é só a ordem na lista — a identificação
    física do card. O número do JOGADOR vem do daemon e pode divergir da ordem
    (índices são reusados quando alguém sai e outro entra). Sem número de
    jogador (modo desktop/nativo, jogador ainda subindo) o card só se identifica,
    em vez de inventar um "P" que o jogo não confirma.
    """
    name = f"Controle {position}"
    if isinstance(player, int) and not isinstance(player, bool):
        return f"{name} — P{player}"
    return name


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

        # --- Banner: degradação do vpad (UX-03) -----------------------------
        # Rótulo simples e sempre inline no topo da aba — nada de popup nem
        # popover (cosmic-epoch#2497 fecha qualquer popup no COSMIC). Invisível
        # por padrão; o `_render_home` liga/desliga a partir do
        # `gamepad_emulation.backend` do state_full (`vpad_degradation_text`).
        vpad_banner = Gtk.Label(label="")
        vpad_banner.set_xalign(0.0)
        vpad_banner.set_line_wrap(True)
        vpad_banner.get_style_context().add_class(
            "hefesto-dualsense4unix-status-warn"
        )
        vpad_banner.set_no_show_all(True)
        vpad_banner.set_visible(False)
        self._home_vpad_banner = vpad_banner
        box.pack_start(vpad_banner, False, False, 0)

        # --- Banner: jogo aberto SEM o wrapper (GUI-05 item 3) --------------
        # Mesmo desenho do banner do vpad: label inline, invisível por padrão;
        # o `_render_home` liga/desliga a partir do
        # `gamepad_emulation.wrapper_used` do state_full (`wrapper_banner_text`).
        wrapper_banner = Gtk.Label(label="")
        wrapper_banner.set_xalign(0.0)
        wrapper_banner.set_line_wrap(True)
        wrapper_banner.get_style_context().add_class(
            "hefesto-dualsense4unix-status-warn"
        )
        wrapper_banner.set_no_show_all(True)
        wrapper_banner.set_visible(False)
        self._home_wrapper_banner = wrapper_banner
        box.pack_start(wrapper_banner, False, False, 0)

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
        # LEIGO-01: onde havia um checkbox de co-op agora só há INFORMAÇÃO.
        # Ninguém pluga dois controles esperando que os dois movam o MESMO
        # personagem, então não existe escolha a oferecer — cada controle é um
        # jogador, sempre. O texto é preenchido no _render_home a partir dos
        # jogadores que o daemon reporta; com um controle só, fica vazio.
        players_hint = Gtk.Label(label="")
        players_hint.set_xalign(0.0)
        players_hint.set_line_wrap(True)
        players_hint.get_style_context().add_class("dim-label")
        self._home_players_hint = players_hint
        opts.pack_start(players_hint, False, False, 0)

        mask_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        # UX (auditoria): rotula pela CONSEQUÊNCIA, não pela tecnologia.
        flavor_label = Gtk.Label(label="O jogo vê o controle como:")
        mask_row.pack_start(flavor_label, False, False, 0)
        flavor = SegmentedSelector(wrap=True)
        flavor.set_items(_FLAVOR_ITEMS)
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
        ctrl_frame_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        # Cards de tamanho IGUAL (homogeneous): sem isso o card do primário
        # (linha extra "primário") ficava mais largo que o dos demais.
        ctrl_box.set_homogeneous(True)
        ctrl_box.set_margin_top(10)
        ctrl_box.set_margin_start(12)
        ctrl_box.set_margin_end(12)
        self._home_controllers_box = ctrl_box
        ctrl_frame_box.pack_start(ctrl_box, False, False, 0)

        # ONDA-U (U2/U10): "Renumerar agora" — compacta a numeração de
        # exibição (DualSense + externos, IPC `identity.renumber`) para 1..N
        # preservando a ordem relativa. Fica junto dos cards: é aqui que a
        # numeração aparece ("sony 1 / sony 4" com só 2 controles).
        renumber_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        renumber_row.set_margin_start(12)
        renumber_row.set_margin_end(12)
        renumber_row.set_margin_bottom(10)
        renumber_btn = Gtk.Button(label="Renumerar agora")
        renumber_btn.connect("clicked", self._on_home_renumber_clicked)
        self._home_renumber_btn = renumber_btn
        renumber_row.pack_start(renumber_btn, False, False, 0)
        renumber_hint = Gtk.Label(label="")
        renumber_hint.set_xalign(0.0)
        renumber_hint.set_line_wrap(True)
        renumber_hint.get_style_context().add_class("dim-label")
        self._home_renumber_hint = renumber_hint
        renumber_row.pack_start(renumber_hint, False, False, 0)
        ctrl_frame_box.pack_start(renumber_row, False, False, 0)

        frame_ctrl.add(ctrl_frame_box)
        box.pack_start(frame_ctrl, False, False, 0)

        # --- Frame: sessão (desligar de verdade) ---------------------------
        frame_sess = Gtk.Frame(label="Sessão")
        sess_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sess_box.set_margin_top(10)
        sess_box.set_margin_bottom(10)
        sess_box.set_margin_start(12)
        sess_box.set_margin_end(12)

        shutdown_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        # ONDA-U (U1): botão ÚNICO — o `_render_home` troca rótulo/estilo
        # entre "Desligar"/"Ligar" conforme o daemon está online/offline; o
        # clique sempre passa por `_on_home_power_clicked` (dispatcher).
        shutdown_btn = Gtk.Button(label=_BTN_LABEL_ONLINE)
        shutdown_btn.get_style_context().add_class("destructive-action")
        shutdown_btn.connect("clicked", self._on_home_power_clicked)
        self._home_shutdown_btn = shutdown_btn
        self._home_offline = False
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

        call_async("daemon.state_full", None, _ok, _fail,
                   timeout_s=_STATE_IPC_TIMEOUT_S)

    def _render_home(self, state: dict[str, Any] | None) -> None:
        from gi.repository import Gtk

        offline = state is None
        selector = self._home_mode_selector
        self._home_guard = True
        try:
            if offline:
                self._home_session_label.set_text("O Hefesto está desligado.")
                selector.set_sensitive(False)
                self._home_players_hint.set_text("")
                self._home_flavor_selector.set_sensitive(False)
                # BUG-HOME-OFFLINE-STALE-01: sem limpar, descrição/origem/
                # opções do gamepad ficavam do último estado online.
                self._home_mode_desc.set_text("")
                self._home_origin_label.set_text("")
                self._home_gamepad_opts.set_visible(False)
                # UX-03: offline não é degradação do vpad — o banner some junto.
                self._home_vpad_banner.set_visible(False)
                # GUI-05: idem para o aviso "jogo sem wrapper".
                self._home_wrapper_banner.set_visible(False)
                self._render_home_controllers([])
                # ONDA-U (U1): toggle in-place — o botão de "Desligar" vira
                # "Ligar o Hefesto" bem aqui, nada de mandar pra aba Sistema.
                self._home_offline = True
                self._home_shutdown_btn.set_label(_BTN_LABEL_OFFLINE)
                self._home_shutdown_btn.get_style_context().remove_class(
                    "destructive-action"
                )
                self._home_shutdown_btn.get_style_context().add_class(
                    "suggested-action"
                )
                # ONDA-U (U2/U10): sem daemon, "Renumerar agora" não tem quem
                # atenda o IPC.
                self._home_renumber_btn.set_sensitive(False)
                self._home_renumber_hint.set_text("")
                return
            assert state is not None
            selector.set_sensitive(True)
            self._home_flavor_selector.set_sensitive(True)
            self._home_session_label.set_text("")
            # ONDA-U (U1): online devolve o botão único ao estado "Desligar".
            self._home_offline = False
            self._home_shutdown_btn.set_label(_BTN_LABEL_ONLINE)
            self._home_shutdown_btn.get_style_context().remove_class(
                "suggested-action"
            )
            self._home_shutdown_btn.get_style_context().add_class(
                "destructive-action"
            )
            # ONDA-U (U2/U10): gate do botão espelha o do IPC — jogo aberto
            # desabilita e explica o porquê ANTES do clique.
            aviso_renumerar = _renumber_gate_text(state)
            self._home_renumber_btn.set_sensitive(aviso_renumerar is None)
            self._home_renumber_hint.set_text(aviso_renumerar or "")

            gamepad = state.get("gamepad_emulation") or {}
            # HARM-01: a leitura do modo também tem um dono só — a Emulação
            # deriva do MESMO payload pela MESMA regra, então as duas abas não
            # podem mais discordar sobre em que modo o sistema está.
            mode = mode_of_state(state) or "desktop"
            selector.set_active_id(mode)
            self._home_mode_desc.set_text(_MODE_DESCRIPTIONS.get(mode, ""))
            self._home_gamepad_opts.set_visible(mode == "gamepad")
            self._home_gamepad_opts.set_no_show_all(mode != "gamepad")

            flavor = gamepad.get("flavor") or "xbox"
            self._home_flavor_selector.set_active_id(str(flavor))

            # UX-03: banner de degradação do vpad — visível SÓ quando a máscara
            # DualSense caiu no backend uinput (função pura decide; backend
            # ausente/"" é transitório e não acende nada).
            aviso_vpad = vpad_degradation_text(state)
            if aviso_vpad:
                self._home_vpad_banner.set_text(aviso_vpad)
            self._home_vpad_banner.set_visible(bool(aviso_vpad))

            # GUI-05 item 3: banner "jogo sem wrapper" — só o False LITERAL de
            # `gamepad_emulation.wrapper_used` acende (função pura decide).
            aviso_wrapper = wrapper_banner_text(state)
            if aviso_wrapper:
                self._home_wrapper_banner.set_text(aviso_wrapper)
            self._home_wrapper_banner.set_visible(bool(aviso_wrapper))

            origin_bits: list[str] = []
            if state.get("native_mode") and state.get("native_mode_origin") == "profile":
                origin_bits.append("nativo ligado pelo perfil ativo")
            if state.get("mode_from_profile") == "gamepad":
                origin_bits.append("gamepad ligado pelo perfil ativo")
            # LEIGO-01: a contagem de jogadores saiu daqui — dizia "co-op: N
            # jogador(es)" (jargão) e agora mora na frase do próprio bloco do
            # gamepad, contada a partir dos jogadores que o daemon numerou.
            self._home_origin_label.set_text(" · ".join(origin_bits))

            # HARM-CARD-FANTASMA-01: `describe_controllers` devolve UMA entrada
            # com connected=False quando não há nenhum controle — sem filtrar, a
            # aba inventava um card "Controle 1 — P1 · ?" com o cabo na mesa. A
            # aba Status (_connected_controllers) e o applet já filtravam; a
            # Início era a única que não.
            connected = [
                c
                for c in (state.get("controllers") or [])
                if isinstance(c, dict) and c.get("connected")
            ]
            self._home_players_hint.set_text(_format_players_hint(connected))
            self._render_home_controllers(
                connected,
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
            # LEIGO-01b: o número do jogador vem do daemon (`player`), NUNCA de
            # idx+1 — a posição na lista não é o que o jogo vê.
            name = _format_controller_title(idx + 1, ctrl.get("player"))
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
            # LEIGO-02: aqui saía o fim do MAC ("…c311f0"). Ele não serve a
            # nenhuma tarefa dela: o número não está gravado no controle
            # físico, então não há como casar card com aparelho por ele. Quem
            # distingue os controles na mesa é a COR da lightbar e o LED de
            # jogador — o card já mostra o número do jogador.
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
            # LEIGO-02: o toast dizia "Modo aplicado: gamepad" — o id interno,
            # uma palavra que não existe em botão nenhum. Ecoa o rótulo que ela
            # acabou de clicar.
            self._status_toast("home", f"Pronto — agora: {_mode_label(mode_id)}")
            self._refresh_home_tab()
            return False

        def _fail(exc: Exception) -> bool:
            self._status_toast("home", f"Falha ao mudar o modo ({exc})")
            self._refresh_home_tab()
            return False

        # HARM-01: a sequência (sair do nativo antes de ligar o gamepad, com a
        # folga de 2s) mora em `mode_transition` — a Início é a dona do modo,
        # não da mecânica; a Emulação chama exatamente o mesmo caminho.
        apply_mode(
            mode_id,
            flavor=self._home_flavor_selector.get_active_id(),
            on_done=_done,
            on_fail=_fail,
        )

    def _on_home_flavor_changed(self, selector: Any) -> None:
        flavor_id = selector.get_active_id()
        if getattr(self, "_home_guard", False) or not flavor_id:
            return
        mode = self._home_mode_selector.get_active_id()
        if mode != "gamepad":
            return

        def _done(_result: Any) -> bool:
            # LEIGO-02: era "Máscara do gamepad: xbox" — jargão + id cru.
            self._status_toast(
                "home", f"O jogo agora vê: {_flavor_label(flavor_id)}"
            )
            return False

        def _fail(_exc: Exception) -> bool:
            # EMU-06: sem callback de falha, a troca podia falhar em silêncio e
            # o botão "pulava" de volta ~2s depois (o poller reconcilia) sem
            # nenhuma explicação. Avisa e reconcilia agora, como o seletor de
            # modo.
            self._status_toast(
                "home",
                "Não consegui trocar o que o jogo vê — o Hefesto pode estar "
                "desligado.",
            )
            self._refresh_home_tab()
            return False

        call_async(
            "gamepad.emulation.set",
            {"enabled": True, "flavor": flavor_id},
            _done,
            _fail,
            timeout_s=_MODE_IPC_TIMEOUT_S,
        )

    def _on_home_renumber_clicked(self, _button: object) -> None:
        """U2/U10: dispara ``identity.renumber`` e traduz o resultado em toast.

        Contrato fixado com o daemon (sprint ONDA-U): método
        ``identity.renumber``, args ``{}``. Retorno
        ``{ok: true, renumbered: {uniq: slot}}`` ou ``{ok: false, reason}``.
        O gate visual (``_render_home``/``_renumber_gate_text``) já desabilita
        o botão com jogo aberto, mas o handler NÃO confia só nisso — o
        daemon decide de verdade (o estado do poll pode estar defasado em
        até ``HOME_POLL_INTERVAL_MS``); aqui só se traduz a resposta.
        """

        def _ok(result: Any) -> bool:
            if not isinstance(result, dict) or not result.get("ok"):
                reason = result.get("reason") if isinstance(result, dict) else None
                if reason == "sessao_de_jogo_aberta":
                    msg = "Feche o jogo antes de renumerar."
                else:
                    msg = "Não consegui renumerar — tente de novo."
                self._status_toast("home", msg)
                return False
            renumerados = result.get("renumbered")
            n = len(renumerados) if isinstance(renumerados, dict) else 0
            if n:
                self._status_toast(
                    "home",
                    f"Numeração compactada — {n} controle(s) renumerado(s).",
                )
            else:
                self._status_toast("home", "Numeração já estava compacta.")
            self._refresh_home_tab()
            return False

        def _fail(_exc: Exception) -> bool:
            self._status_toast(
                "home",
                "Não consegui renumerar — o Hefesto pode estar desligado.",
            )
            return False

        call_async("identity.renumber", {}, _ok, _fail, timeout_s=_MODE_IPC_TIMEOUT_S)

    def _on_home_power_clicked(self, button: object) -> None:
        """Dispatcher do botão único de energia da aba Início (ONDA-U, U1).

        Offline: reusa o MESMO caminho de ``on_daemon_start``
        (``DaemonActionsMixin`` — ``systemctl --user start`` em thread
        worker, com toast e reset do flag ``_user_stopped_daemon``) — nada de
        duplicar a lógica de subir o daemon. ``getattr`` defensivo (mesmo
        padrão de ``_edit_uniq`` em ``lightbar_actions``): os dois mixins só
        convivem de fato na instância composta (``HefestoApp``), nunca
        isolados nos testes. Online: mantém o fluxo de confirmação existente
        (``_on_home_shutdown_clicked``). O estado vem de ``self._home_offline``,
        mantido pelo ``_render_home``.
        """
        if getattr(self, "_home_offline", False):
            start = getattr(self, "on_daemon_start", None)
            if callable(start):
                start(button)
            return
        self._on_home_shutdown_clicked(button)

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
        # GUI-05/P5: sem a classe de tema o diálogo herdava o claro do sistema
        # (precedente: gui_dialogs._apply_app_theme).
        with contextlib.suppress(Exception):
            dialog.get_style_context().add_class("hefesto-dualsense4unix-window")
        dialog.format_secondary_text(
            "O controle continua funcionando nos jogos, mas sem luzes, sem "
            "gatilhos e sem os seus ajustes.\n"
            "Esta janela continua aberta e NÃO liga o Hefesto de novo sozinha "
            # ONDA-U (U1): "Ligar o Hefesto" agora é o MESMO botão desta aba
            # (toggle in-place) — o aviso não manda mais pra aba Sistema.
            "— para ligar de novo, clique em \"Ligar o Hefesto\" aqui mesmo, "
            "nesta aba."
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
                    logger.warning("home_shutdown_falhou", erro=err)
                    self._status_toast(
                        "home",
                        "Não consegui desligar o Hefesto — tente pela aba "
                        "Sistema.",
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


__all__ = [
    "HOME_POLL_INTERVAL_MS",
    "RENUMBER_GAME_OPEN_TEXT",
    "VPAD_DEGRADED_TEXT",
    "WRAPPER_MISSING_TEXT",
    "HomeActionsMixin",
    "vpad_degradation_text",
    "wrapper_banner_text",
]
