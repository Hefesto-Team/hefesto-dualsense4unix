"""Aba Status: polling ao vivo de daemon.state_full + update dos widgets.

Inclui a máquina de estado de reconnect (UX-RECONNECT-01): um tick dedicado
a cada 2s (`RECONNECT_POLL_INTERVAL_S`) observa o IPC e move o header entre
três estados visuais — `online`, `reconnecting`, `offline`. O polling rápido
dos widgets de live-state é independente e preserva a fluidez da aba Status.

Redesign STATUS-02 (aba Status vira 1 card por controle):
  - O Glade da aba tem só o frame "Estado" + um GtkScrolledWindow com o GRID
    `status_players_slot`; os cards (`ControllerCard`) são montados por
    código, um por controle CONECTADO do bloco `controllers` do state_full.
    STATUS-GRID-2COL-01: o slot é um GtkGrid de DUAS colunas (era um box
    vertical). Empilhados, dois controles somavam altura e a aba só cabia
    com rolagem; lado a lado eles dividem a mesma faixa vertical.
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

# MIC-FAIXA-01: o Pango entra OPCIONAL, e não no import direto, por uma
# armadilha que este projeto já pagou: na CI o `gi` importa, mas os typelibs
# são PARCIAIS — não há `Pango` nem `Gtk.DrawingArea`. Um `from gi.repository
# import Pango` no topo não vira skip: derruba a COLETA de todo módulo de teste
# que encoste aqui, e a CI reprova em massa com ImportError. É o mesmo motivo
# pelo qual `sensor_widgets` mede `hasattr(Gtk, "DrawingArea")` em vez de
# confiar no import. Sem Pango, o motivo da faixa simplesmente não elipsa — o
# texto continua lá, e o tooltip completo também.
try:
    from gi.repository import Pango
except ImportError:  # pragma: no cover — só em typelib parcial (CI headless)
    Pango = None

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.base import (
    WidgetAccessMixin,
    numero_do_controle,
)
from hefesto_dualsense4unix.app.actions.external_controllers import (
    brand_of,
    button_labels_for,
    external_key,
    friendly_type,
    slot_label,
    slot_of,
    transport_label,
)
from hefesto_dualsense4unix.app.actions.home_actions import (
    controles_na_mesa,
    e_externo,
    via_curta,
    vpad_degradation_text,
    wrapper_banner_text,
)
from hefesto_dualsense4unix.app.actions.rumble_actions import (
    BTN_GIVE_BACK_TO_GAME,
)
from hefesto_dualsense4unix.app.constants import (
    LIVE_POLL_INTERVAL_MS,
    RECONNECT_FAIL_THRESHOLD,
    RECONNECT_POLL_INTERVAL_S,
    STATE_POLL_INTERVAL_MS,
)
from hefesto_dualsense4unix.app.ipc_bridge import call_async
from hefesto_dualsense4unix.app.mic_monitor import (
    DiagnosticoMic,
    audio_do_entry,
    diagnosticar_mic,
)

# GRID_BOTOES/ALL_BUTTONS/L2_R2_THRESHOLD moraram aqui até o STATUS-02;
# re-exportados (ver __all__) para os consumidores históricos da mixin.
from hefesto_dualsense4unix.app.widgets.controller_card import (
    ALL_BUTTONS,
    GRID_BOTOES,
    L2_R2_THRESHOLD,
    ControllerCard,
)
from hefesto_dualsense4unix.app.widgets.sensor_widgets import MicMeter, selo_mic
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


#: Número de exibição de um controle. A regra vive em `base.numero_do_controle`
#: para as telas não divergirem; o nome antigo segue como alias do módulo.
_display_slot = numero_do_controle


# ---------------------------------------------------------------------------
# Faixa de microfone do rodapé (MIC-FAIXA-01)
# ---------------------------------------------------------------------------

#: Colunas da faixa. Com quatro controles são DUAS linhas, não quatro — a
#: altura do rodapé é orçamento apertado (ver o comentário no glade).
MIC_FAIXA_COLUNAS = 2

#: Medidor da faixa: um pouco mais baixo que os 26px do mockup, pela mesma
#: conta de altura. A largura é a do mockup — as 14 amostras continuam
#: legíveis.
_MIC_FAIXA_MEDIDOR_PX = (72, 22)

#: O que a faixa diz quando não há UM controle com microfone na mesa. Ela
#: continua na tela: o espaço do microfone é permanente, e "a faixa sumiu" foi
#: justamente a queixa que abriu esta entrega.
TEXTO_MIC_SEM_CONTROLE = (
    "Nenhum controle com microfone na mesa — o medidor aparece aqui assim que "
    "um DualSense conectar."
)

#: Selo de mute ainda não lido. Escrever "ATIVO" aqui afirmaria que o
#: microfone está aberto sem ter lido nada (regra do `selo_mic`).
_SELO_MIC_DESCONHECIDO = "—"


class _LinhaMic:
    """Uma linha da faixa: um controle, seu medidor e o porquê de não medir.

    A linha NUNCA se esconde e nunca deixa de ser empacotada — nem sem source,
    nem por Bluetooth, nem com o daemon calado. O que muda é o CONTEÚDO: com
    captura viva o medidor desenha a onda; sem ela o medidor fica vazio (não
    em zero: ver `MicMeter.set_inativo`) e o texto ao lado diz qual das causas
    está segurando e qual é o gesto que a cura.
    """

    def __init__(self, rotulo: str) -> None:
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        nome = Gtk.Label(label=rotulo)
        nome.set_xalign(0.0)
        self.box.pack_start(nome, False, False, 0)
        medidor = MicMeter()
        medidor.set_size_request(*_MIC_FAIXA_MEDIDOR_PX)
        medidor.set_valign(Gtk.Align.CENTER)
        self.medidor = medidor
        self.box.pack_start(medidor, False, False, 0)
        selo = Gtk.Label()
        selo.set_valign(Gtk.Align.CENTER)
        selo.get_style_context().add_class("hefesto-selo")
        self.selo = selo
        self.box.pack_start(selo, False, False, 0)
        motivo = Gtk.Label()
        motivo.set_xalign(0.0)
        # Elipse em vez de quebra de linha: a faixa mora num orçamento de
        # altura fixo, e um texto que quebra em duas linhas empurraria os
        # cards para fora da janela. O texto inteiro fica no tooltip.
        if Pango is not None:
            motivo.set_ellipsize(Pango.EllipsizeMode.END)
        motivo.get_style_context().add_class("dim-label")
        self.motivo = motivo
        self.box.pack_start(motivo, True, True, 0)
        self._ultimo: tuple[Any, ...] | None = None

    def aplicar(self, diag: DiagnosticoMic) -> None:
        """Pinta a linha a partir do diagnóstico (diff no que é texto).

        O nível NÃO entra no diff de propósito: ele é o dado que muda a cada
        bloco de 100 ms e é a onda andando que mostra que o medidor está vivo.
        O resto (selo, motivo, cura) só é reescrito quando muda de verdade —
        a 10 Hz, remarcar markup igual é trabalho puro de layout.
        """
        if diag.medindo:
            self.medidor.set_nivel(diag.nivel or 0.0)
        else:
            self.medidor.set_inativo()
        chave = (diag.motivo, diag.muted, diag.texto, diag.cura, diag.fonte)
        if chave == self._ultimo:
            return
        self._ultimo = chave
        selo = selo_mic(diag.muted)
        if selo is None:
            self.selo.set_markup(_SELO_MIC_DESCONHECIDO)
        else:
            texto, fundo, cor = selo
            self.selo.set_markup(
                f'<span background="{fundo}" foreground="{cor}"> {texto} </span>'
            )
        completo = " ".join(parte for parte in (diag.texto, diag.cura) if parte)
        self.motivo.set_text(completo)
        self.box.set_tooltip_text(completo or diag.fonte or None)


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
    # secreta que abre ao clicar. CONTAGEM-01/5: o cache do inventário deixou
    # de ter fetch próprio (throttle + in-flight, que sumiram junto) — quem o
    # alimenta é `_sync_externals_from_state`, com a lista do `state_full`.
    _external_buttons: list[Any]
    _externals: list[dict[str, Any]]
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
    # PLAYER-01 (25/07): o seletor "Número deste controle" — a ENTREGA
    # PRINCIPAL da sprint. A fita de chips do cabeçalho MOSTRA o número de
    # identidade mas nunca teve como MUDÁ-LO: não existia, em lugar nenhum do
    # projeto, comando que atribuísse um número a um controle (só o
    # `identity.renumber`, que compacta todos e mora na aba Início). Estes
    # botões falam com o `identity.number.set`, criado nesta mesma sprint.
    # `_edit_target_slot` é o número de identidade do alvo, mantido em sync
    # pelo tick lento — separado do `_edit_target_uniq` (o endereço) e do
    # índice de enumeração, que são as outras duas coisas que o chip carrega.
    _target_strip: Any = None
    _numero_faixa: Any = None
    _numero_box: Any = None
    _numero_botoes: list[Any]
    _numero_total: int = 0
    _numero_updating: bool = False
    _numero_visivel: bool = False
    _edit_target_slot: int | None = None
    _target_slot_by_index: dict[int, int | None]
    #: PLAYER-01: co-op ligado = a camada de co-op manda no desenho das 5
    #: luzes, ACIMA da escolha manual. Lido do `state_full` aqui e consumido
    #: pela aba Lightbar (que não tem poller próprio).
    _coop_ligado: bool = False
    #: Badge do banner que denuncia rumble travado em silêncio.
    _rumble_badge: Any = None
    # S2: monitor do microfone (nível + mute). Lazy e DESLIGADO por padrão —
    # quem o liga é o gancho de troca de aba (`set_status_tab_visivel`). Ele
    # é o único sensor do card que não vem pelo IPC: capturar áudio é da
    # sessão gráfica, não do daemon.
    _mic_monitor: Any = None
    # MIC-FAIXA-01: linhas da faixa de microfone do rodapé, uma por controle
    # com microfone. `None` em `_mic_faixa_keys` = nada montado ainda.
    _mic_faixa_linhas: list[Any]
    _mic_faixa_keys: tuple[tuple[str, str], ...] | None = None

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
        self._mic_faixa_linhas = []
        self._mic_faixa_keys = None
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
    # Microfone: a captura só existe com a aba Status à vista (S2)
    # ------------------------------------------------------------------

    def set_status_tab_visivel(self, visivel: bool) -> None:
        """Liga/desliga a captura de áudio do microfone dos controles.

        Chamado pelo `switch-page` do notebook (que identifica a aba pelo id
        do Glade, não pela posição). Sair da aba MATA o `parec` de cada
        controle: manter um processo capturando o microfone da usuária com a
        janela em outra aba — ou minimizada — seria custo e intromissão sem
        ninguém olhando o medidor.

        O monitor nasce na primeira vez que a aba é aberta; antes disso não
        existe thread nenhuma. Falha de import/inicialização é silenciosa
        (mesma linha do tema sem CSS): a aba abre, os outros dois sensores
        continuam, e o módulo de microfone simplesmente não aparece.
        """
        monitor = self._mic_monitor
        if monitor is None:
            if not visivel:
                return
            try:
                from hefesto_dualsense4unix.app.mic_monitor import MicMonitor
            except Exception as exc:
                logger.debug("mic_monitor_indisponivel", err=str(exc))
                return
            monitor = MicMonitor()
            self._mic_monitor = monitor
        with contextlib.suppress(Exception):
            monitor.set_ativo(visivel)

    def parar_mic_monitor(self) -> None:
        """Encerra o monitor do microfone (fechamento da janela)."""
        monitor = self._mic_monitor
        self._mic_monitor = None
        if monitor is not None:
            with contextlib.suppress(Exception):
                monitor.stop()

    # ------------------------------------------------------------------
    # Faixa de microfone do rodapé (MIC-FAIXA-01)
    # ------------------------------------------------------------------

    @staticmethod
    def _mic_faixa_chaves(
        conectados: list[dict[str, Any]],
    ) -> list[tuple[str, str]]:
        """``[(uniq, rótulo)]`` — uma entrada por controle com microfone.

        Só DualSense: os externos não têm microfone que o Hefesto saiba ler, e
        uma linha para eles diria "sem microfone" onde a verdade é "esse
        controle não tem". ``uniq`` ausente vira "" — a linha CONTINUA
        existindo (o espaço é permanente), e o diagnóstico dirá que não dá
        para atribuir uma source a um controle sem endereço.
        """
        chaves: list[tuple[str, str]] = []
        for pos, entry in enumerate(conectados):
            uniq = entry.get("uniq")
            transporte = str(entry.get("transport") or "?").upper()
            numero = _display_slot(entry) or (pos + 1)
            chaves.append(
                (
                    uniq if isinstance(uniq, str) and uniq else "",
                    f"Controle {numero} — {transporte}",
                )
            )
        return chaves

    @staticmethod
    def _transportes_por_uniq(
        conectados: list[dict[str, Any]],
    ) -> dict[str, str]:
        """``{uniq: "usb"|"bt"}`` — o que a atribuição de source precisa saber.

        Uma source `alsa_*` só pode ser de um controle no cabo (por rádio o
        DualSense não expõe placa de áudio). Sem este mapa, a mesa mista — um
        no cabo e três por rádio, o caso normal desta casa — deixava a única
        source ALSA com quatro candidatos e a faixa dizia "não dá para saber
        de quem é" justamente para quem estava no cabo.
        """
        vias: dict[str, str] = {}
        for entry in conectados:
            uniq = entry.get("uniq")
            via = str(entry.get("transport") or "").lower()
            if isinstance(uniq, str) and uniq and via:
                vias[uniq] = via
        return vias

    def _sync_mic_strip(self, state: dict[str, Any]) -> None:
        """Monta/atualiza a faixa de microfone a partir do ``state_full``.

        A faixa é PERMANENTE. Não há neste método um único caminho que
        esconda, despacote ou deixe de criar a faixa: sem controle, sem
        source, por rádio com a ponte desligada ou com o nome ambíguo, o que
        muda é o TEXTO. A regra veio da mantenedora, e vale como contrato:
        *"sabemos que não funciona sem cabo, mas o espaço deve estar sempre
        presente"* — uma tela que muda de forma conforme o transporte não dá
        onde olhar.
        """
        slot = self._get("status_mic_slot")
        if slot is None or not hasattr(slot, "attach"):
            # Builder fake de testes de outras áreas, ou glade antigo em
            # upgrade parcial. Não é caminho de esconder — é ausência do
            # widget, e aí não há o que pintar.
            return
        if getattr(self, "_mic_faixa_linhas", None) is None:
            self._mic_faixa_linhas = []
        conectados = self._connected_controllers(state)
        chaves = self._mic_faixa_chaves(conectados)
        if tuple(chaves) != self._mic_faixa_keys:
            self._rebuild_mic_strip(slot, chaves)
        if not chaves:
            return

        monitor = self._mic_monitor
        fontes = None
        portas: dict[str, bool] = {}
        if monitor is not None:
            with contextlib.suppress(Exception):
                fontes = monitor.fontes()
            with contextlib.suppress(Exception):
                portas = monitor.portas()
        uniqs = [uniq for uniq, _rotulo in chaves if uniq]
        transportes = self._transportes_por_uniq(conectados)
        # BT-MIC-REGISTRY-01: a ponte de áudio por Bluetooth está DE PÉ agora?
        # Não basta a env var existir — o `state_full` publica o subsystem
        # vivo, e é dele que sai a diferença entre "ligue a ponte" e "a ponte
        # está ligada e mesmo assim não há source".
        bt_mic = state.get("bt_mic")
        ponte = bool(bt_mic.get("running")) if isinstance(bt_mic, dict) else False
        for (uniq, _rotulo), entry, linha in zip(
            chaves, conectados, self._mic_faixa_linhas, strict=False
        ):
            leitura = None
            if monitor is not None and uniq:
                with contextlib.suppress(Exception):
                    leitura = monitor.leitura(uniq)
            mic_mudo, mic_mudo_desejado = audio_do_entry(entry)
            linha.aplicar(
                diagnosticar_mic(
                    fontes=fontes,
                    uniq=uniq,
                    uniqs_com_audio=uniqs,
                    transporte=str(entry.get("transport") or ""),
                    leitura=leitura,
                    mic_mudo=mic_mudo,
                    mic_mudo_desejado=mic_mudo_desejado,
                    ponte_bt_ligada=ponte,
                    portas=portas,
                    transportes=transportes,
                )
            )

    def _rebuild_mic_strip(
        self, slot: Any, chaves: list[tuple[str, str]]
    ) -> None:
        """Recria as linhas da faixa — o conjunto de controles mudou.

        Sem controle nenhum a faixa recebe UMA linha de texto explicando a
        ausência, e não zero linhas: o rodapé continua ocupando o mesmo lugar
        na tela, que é o ponto.
        """
        for child in list(slot.get_children()):
            slot.remove(child)
            child.destroy()
        self._mic_faixa_linhas = []
        self._mic_faixa_keys = tuple(chaves)
        if not chaves:
            vazio = Gtk.Label(label=TEXTO_MIC_SEM_CONTROLE)
            vazio.set_xalign(0.0)
            vazio.set_line_wrap(True)
            with contextlib.suppress(Exception):
                vazio.get_style_context().add_class("dim-label")
            slot.attach(vazio, 0, 0, MIC_FAIXA_COLUNAS, 1)
            vazio.show_all()
            return
        for pos, (_uniq, rotulo) in enumerate(chaves):
            linha = _LinhaMic(rotulo)
            self._mic_faixa_linhas.append(linha)
            slot.attach(
                linha.box,
                pos % MIC_FAIXA_COLUNAS,
                pos // MIC_FAIXA_COLUNAS,
                1,
                1,
            )
            linha.box.show_all()

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
        if slot is None or not hasattr(slot, "attach"):
            # Builder fake de testes de outras áreas (ou Glade antigo em
            # upgrade parcial): sem slot real, a aba segue sem cards.
            return
        if getattr(self, "_status_cards", None) is None:
            self._status_cards = {}
            self._status_card_keys = []
        conectados = self._connected_controllers(state)
        keys = self._status_card_keys_for(conectados)
        # CONTAGEM-01 (fechamento do defeito visto na tela em 26/07): a aba
        # dizia "Conectado (4 controles)" no topo e mostrava DOIS cards. A
        # primeira entrega deixou o externo fora da grade de propósito — não
        # lemos input, bateria nem sensores dele, e preencher aquelas áreas
        # seria inventar dado. O argumento vale para o CONTEÚDO do card e não
        # para a existência dele: a mesma tela afirmando quatro e desenhando
        # dois é exatamente o que esta sprint existe para matar. O externo
        # ganha um card de IDENTIDADE — quem é, por onde entrou, e por que não
        # tem número nosso —, sem uma única área de dado fingido.
        # Lido do payload aqui mesmo, e não de `self._externals`, para não
        # depender da ORDEM em que os dois sincronizadores rodam no tique.
        bruto_ext = state.get("external_controllers")
        externos = (
            [e for e in bruto_ext if isinstance(e, dict)]
            if isinstance(bruto_ext, list)
            else []
        )
        keys_ext: list[tuple[Any, ...]] = [
            ("externo", e.get("uniq") or e.get("path") or pos)
            for pos, e in enumerate(externos)
        ]
        if keys + keys_ext != self._status_card_keys:
            self._rebuild_status_cards(slot, keys, externos)
        monitor = self._mic_monitor
        if monitor is not None:
            monitor.set_controles(
                tuple(
                    str(c.get("uniq"))
                    for c in conectados
                    if isinstance(c.get("uniq"), str) and c.get("uniq")
                ),
                # MIC-FAIXA-01: o transporte viaja junto porque é ele que
                # decide quais sources podem ser deste controle — e o monitor
                # tem de atribuir EXATAMENTE como a faixa diagnostica.
                self._transportes_por_uniq(conectados),
            )
        for key, entry in zip(keys, conectados, strict=True):
            card = self._status_cards.get(key)
            if card is None:
                continue
            card.update(entry, state)

    def _card_de_identidade_externo(self, entry: dict[str, Any]) -> Any:
        """Card de um controle EXTERNO na aba Status: só identidade.

        CONTAGEM-01. Ele não tem gauge, stick, bateria nem giroscópio — e é
        proposital: não lemos nada disso de um externo, e desenhar a moldura
        vazia diria "sem sinal" onde a verdade é "não medimos". O card diz
        quem é, por onde entrou e por que não tem número nosso; nada mais.
        """
        from gi.repository import Gtk

        from hefesto_dualsense4unix.app.actions.home_actions import (
            EXTERNO_SEM_NUMERO_NOSSO,
        )

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        card.get_style_context().add_class("hefesto-dualsense4unix-card")
        numero = numero_do_controle(entry)
        titulo = Gtk.Label()
        titulo.set_markup(
            f"Controle {numero} — {transport_label(entry)} · Jogador —"
        )
        titulo.set_xalign(0.0)
        card.pack_start(titulo, False, False, 0)
        sub = Gtk.Label(label=f"{brand_of(entry)} · {friendly_type(entry)}")
        sub.set_xalign(0.0)
        sub.get_style_context().add_class("dim-label")
        card.pack_start(sub, False, False, 0)
        nota = Gtk.Label(label=EXTERNO_SEM_NUMERO_NOSSO)
        nota.set_xalign(0.0)
        nota.set_line_wrap(True)
        nota.get_style_context().add_class("dim-label")
        card.pack_start(nota, False, False, 0)
        return card

    def _rebuild_status_cards(
        self,
        slot: Any,
        keys: list[tuple[Any, ...]],
        externos: list[dict[str, Any]] | None = None,
    ) -> None:
        """Recria os cards — o conjunto de controles mudou.

        STATUS-GRID-2COL-01: os cards vão para um GtkGrid em DUAS colunas, não
        mais empilhados. Empilhado, cada controle somava a própria altura e
        dois já estouravam a janela — a aba só respondia com rolagem. Lado a
        lado, dois controles ocupam a MESMA faixa vertical de um (e quatro
        viram 2x2, que é o teto real: 4 jogadores no co-op).
        """
        externos = externos or []
        for child in list(slot.get_children()):
            slot.remove(child)
            child.destroy()
        self._status_cards = {}
        keys_ext: list[tuple[Any, ...]] = [
            ("externo", e.get("uniq") or e.get("path") or pos)
            for pos, e in enumerate(externos)
        ]
        self._status_card_keys = list(keys) + keys_ext
        # 2+ cards → sticks de 90px (compact); card único mantém o layout
        # equivalente ao da aba antiga (sticks 120px). O total conta os
        # externos: com um DualSense e um Nintendo a grade já é de dois.
        compact = len(keys) + len(externos) >= 2
        colunas = 2 if compact else 1
        for pos, key in enumerate(keys):
            card = ControllerCard(compact=compact)
            self._status_cards[key] = card
            # `hexpand` + column-homogeneous do Glade: as colunas dividem a
            # largura em partes iguais em vez de a 1ª tomar tudo e a 2ª ficar
            # espremida (o card tem conteúdo de largura natural bem diferente
            # conforme os sensores presentes).
            card.set_hexpand(True)
            card.set_valign(Gtk.Align.START)
            slot.attach(card, pos % colunas, pos // colunas, 1, 1)
            card.show_all()
        # Os externos entram DEPOIS dos DualSense, na mesma grade e na mesma
        # ordem da fita de chips e da aba Início — a tela toda conta a mesma
        # mesa. Eles ficam fora de `_status_cards` de propósito: aquele dicionário
        # é dos cards que recebem `update()` a 10 Hz, e o card de identidade não
        # tem nada que mude a cada tique.
        for pos_ext, entry in enumerate(externos):
            pos = len(keys) + pos_ext
            card_ext = self._card_de_identidade_externo(entry)
            card_ext.set_hexpand(True)
            card_ext.set_valign(Gtk.Align.START)
            slot.attach(card_ext, pos % colunas, pos // colunas, 1, 1)
            card_ext.show_all()

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
    def _por_numero_de_identidade(
        conectados: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Conectados na ordem do NÚMERO exibido (PLAYER-01, absorve UI-SELETOR-01).

        O seletor mostrava "Sony 2 · BT | Sony 1 · BT | ..." — os números
        estavam certos, quem estava errada era a ORDEM. A causa é a separação
        que dá nome a esta sprint: o laço percorria os conectados na ordem em
        que o daemon os devolve (ordem de ENUMERAÇÃO/conexão) e usava o número
        de identidade apenas no RÓTULO. Como o número é estável por MAC entre
        replugs e a ordem de conexão não é, os dois divergem sempre que alguém
        liga os controles fora de ordem — que é o caso normal.

        A separação é o ponto: aqui muda só a ORDEM DE EXIBIÇÃO. O índice
        0-based de enumeração continua viajando dentro de cada linha, porque é
        ele que o ``controller.target.set`` espera — reordenar o índice junto
        seria um defeito pior que o atual (a usuária clicaria no chip do 1 e
        editaria outro controle).

        Quem não tem ``player_slot`` (registro sem opinião ainda, controle sem
        MAC) vai para o FIM preservando a ordem relativa — ``sorted`` é
        estável, então o desempate é a ordem de enumeração de sempre.
        """

        def _chave(entry: dict[str, Any]) -> tuple[int, int]:
            slot = entry.get("player_slot")
            if isinstance(slot, int) and not isinstance(slot, bool):
                return (0, slot)
            return (1, 0)

        return sorted(conectados, key=_chave)

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

        PLAYER-01 (absorve UI-SELETOR-01): a ORDEM das linhas passa a ser a do
        número de identidade (``_por_numero_de_identidade``); o índice que cada
        linha CARREGA segue o da enumeração. São dois campos — eram um só,
        usado para as duas coisas.
        """
        rows: list[tuple[str, int | None]] = [(_("Todos os controles"), None)]
        for c in StatusActionsMixin._por_numero_de_identidade(conectados):
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
        # "ficha secreta" que abre ao clicar num deles. CONTAGEM-01/5: o cache
        # vem do `state_full`, não mais de busca própria.
        self._external_buttons = []
        self._externals = []
        self._externals_sig = None
        # PERFIL-04: estado do alvo de edição por-controle.
        self._edit_target_uniq = None
        self._edit_target_label = None
        self._target_uniq_by_index = {}
        self._target_label_by_index = {}
        self._edit_badge = None
        # PLAYER-01: estado do seletor "Número deste controle" (ver
        # `_refresh_numero_selector`).
        self._numero_faixa = None
        self._numero_box = None
        self._numero_botoes = []
        self._numero_total = 0
        self._numero_updating = False
        self._numero_visivel = False
        self._edit_target_slot = None
        self._target_slot_by_index = {}
        self._target_strip = None
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
        self._target_combo = box
        # PLAYER-01 entrega 3: o chip carregava TRÊS papéis e só um estava
        # dito — ele MOSTRA o número de identidade, ENVIA o índice de
        # enumeração e SIGNIFICA "alvo das edições". O terceiro, que é o único
        # que muda o que os botões das outras abas fazem, vivia num tooltip
        # (invisível até alguém parar o ponteiro em cima). Vira legenda fixa
        # ao lado da fita, e a fita ganha faixa própria com ela.
        faixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        faixa.set_valign(Gtk.Align.CENTER)
        legenda = Gtk.Label(label=_("Ajustes vão para:"))
        with contextlib.suppress(Exception):
            legenda.get_style_context().add_class("dim-label")
        faixa.pack_start(legenda, False, False, 0)
        faixa.pack_start(box, False, False, 0)
        legenda.show()
        box.show()
        faixa.set_no_show_all(True)
        faixa.hide()
        header_bar.pack_end(faixa, False, False, 0)
        self._target_strip = faixa
        self._montar_numero_selector(header_bar)
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
        # A vibração pode ficar TRAVADA em silêncio (botão "Parar"): o estado
        # sobrevive a troca de perfil, reconexão e abertura de jogo, e só sai
        # pelo "Devolver ao jogo". O aviso existia apenas na aba Rumble — quem
        # está jogando não tem essa aba aberta e conclui que a vibração quebrou.
        # Aqui ele fica no banner, visível de qualquer aba.
        rumble_badge = Gtk.Label()
        rumble_badge.set_use_markup(True)
        rumble_badge.set_no_show_all(True)
        rumble_badge.hide()
        header_bar.pack_end(rumble_badge, False, False, 6)
        self._rumble_badge = rumble_badge

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
        # Slot GLOBAL: continua a numeração dos DualSense. SELETOR-UNO-01: a
        # contagem vem do refresh (len(conectados)) — derivar de len(botões)-1
        # assumia a linha "Todos", que deixou de ser incondicional.
        dualsense_count = getattr(
            self, "_dualsense_count", max(0, len(self._target_buttons) - 1)
        )
        rotulos = button_labels_for(externals, dualsense_count)
        for i, (ext, rotulo) in enumerate(zip(externals, rotulos, strict=False)):
            slot = slot_of(ext, dualsense_count, i)
            titulo = (
                f"Controle {slot_label(slot)}"
                if slot is not None
                else "Controle externo"
            )
            eb = Gtk.Button.new_with_label(rotulo)
            eb.set_tooltip_text(
                f"{titulo}: {friendly_type(ext)} — "
                f"{transport_label(ext)} "
                "(clique para ver; o Hefesto não mexe no que ele faz)"
            )
            with contextlib.suppress(Exception):
                eb.get_style_context().add_class("hefesto-external-btn")
            eb.connect("clicked", self._on_external_clicked, external_key(ext), slot)
            eb.show()
            box.pack_start(eb, False, False, 0)
            self._external_buttons.append(eb)

    def _sync_externals_from_state(self, state: dict[str, Any]) -> None:
        """Semeia os chips de externo a partir do `state_full` (CONTAGEM-01/5).

        Aqui morreu a SEGUNDA rota de dados. Até 25/07 esta mixin buscava o
        inventário sozinha (`controller.list {external:true}` a cada 4 s, com
        throttle e in-flight próprios) porque o `state_full` publicava os
        externos só como CONTAGEM — não dava para montar chip com um número.
        Com a lista no payload (entrega 1), a busca deixou de ter motivo, e
        manter as duas era garantir que voltassem a divergir: a fita de chips
        já mostrava quatro enquanto cabeçalho e cartões mostravam dois, e essa
        janela de discordância era exatamente a diferença de tempo entre uma
        rota e a outra.

        A chave AUSENTE (daemon anterior a esta leva, ou sem registro de
        externos) preserva o que já estava na tela em vez de zerar a fita: não
        saber não é o mesmo que "não há nenhum".
        """
        externos = state.get("external_controllers")
        if isinstance(externos, list):
            self._externals = [e for e in externos if isinstance(e, dict)]

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

    def _set_target_strip_visible(self, visivel: bool) -> None:
        """Mostra/esconde a fita de chips (legenda inclusa) — PLAYER-01.

        A visibilidade migrou do ``box`` dos chips para a FAIXA que o embrulha
        junto com a legenda "Ajustes vão para:" — esconder só o box deixaria a
        legenda órfã no cabeçalho. Fallback para o próprio box quando não há
        faixa: hosts parciais de teste montam o seletor injetando
        ``_target_combo`` direto, sem passar por
        ``_init_controller_target_combo``.
        """
        alvo = getattr(self, "_target_strip", None) or getattr(
            self, "_target_combo", None
        )
        if alvo is None:
            return
        if visivel:
            alvo.show()
        else:
            alvo.hide()

    # ------------------------------------------------------------------
    # "Número deste controle" (PLAYER-01) — a entrega principal da sprint
    # ------------------------------------------------------------------

    def _montar_numero_selector(self, header_bar: Any) -> None:
        """Cria a faixa "Número deste controle: [1][2][3][4]" no cabeçalho.

        BOTÕES segmentados, nunca dropdown — o cosmic-comp fecha popups de
        combo em ~40-95% dos cliques (cosmic-epoch#2497), e a fita de alvo ao
        lado existe nessa forma pelo mesmo motivo. Fica ao lado do chip de
        propósito: a queixa é justamente que "a escolha do player não
        sincroniza com o botão superior que informa o controle e o player" —
        o lugar de trocar o número é encostado no lugar que o mostra.

        Só aparece com um controle escolhido E dois ou mais na mesa (ver
        ``_refresh_numero_selector``): com um controle só, o único número
        possível é 1 e um seletor de uma opção é ruído.
        """
        faixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        faixa.set_valign(Gtk.Align.CENTER)
        legenda = Gtk.Label(label=_("Número deste controle:"))
        with contextlib.suppress(Exception):
            legenda.get_style_context().add_class("dim-label")
        caixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        caixa.get_style_context().add_class("linked")
        caixa.set_valign(Gtk.Align.CENTER)
        caixa.set_tooltip_text(
            "Muda o NÚMERO deste controle — o do cabeçalho, dos cartões e do "
            "LED de número. Não é o desenho das 5 luzes da aba Lightbar, que "
            "é só aparência."
        )
        faixa.pack_start(legenda, False, False, 0)
        faixa.pack_start(caixa, False, False, 0)
        legenda.show()
        caixa.show()
        faixa.set_no_show_all(True)
        faixa.hide()
        header_bar.pack_end(faixa, False, False, 0)
        self._numero_faixa = faixa
        self._numero_box = caixa

    def _rebuild_numero_buttons(self, caixa: Any, total: int) -> None:
        """Recria os botões 1..``total`` do seletor de número (PLAYER-01)."""
        for child in list(caixa.get_children()):
            caixa.remove(child)
            child.destroy()
        self._numero_botoes = []
        grupo = None
        for numero in range(1, total + 1):
            btn = Gtk.RadioButton.new_with_label_from_widget(grupo, str(numero))
            if grupo is None:
                grupo = btn
            btn.set_mode(False)  # toggle (visual de segmented control)
            btn.set_tooltip_text(
                f"Faz deste o controle número {numero}. "
                "Os outros deslizam para abrir lugar."
            )
            btn.connect("toggled", self._on_numero_button_toggled, numero)
            btn.show()
            caixa.pack_start(btn, False, False, 0)
            self._numero_botoes.append(btn)

    def _refresh_numero_selector(self, total: int) -> None:
        """Sincroniza o seletor de número com o alvo e a mesa (PLAYER-01).

        ``total`` é quantos controles estão na mesa AGORA (DualSense adotados
        + externos numerados) — o espaço de numeração é ÚNICO entre os dois
        (R-24/NUM-01), então oferecer só a contagem de DualSense esconderia
        números legítimos.

        Aparece com um controle de endereço estável escolhido e 2+ na mesa;
        some fora disso. IDEMPOTENTE: só reconstrói quando a contagem muda, e
        o ``_numero_updating`` impede que a marcação programática do botão
        dispare um pedido de troca (o eco que faria a janela mandar um
        ``identity.number.set`` a cada tique de 2 Hz).
        """
        faixa = getattr(self, "_numero_faixa", None)
        caixa = getattr(self, "_numero_box", None)
        if faixa is None or caixa is None:
            return
        uniq = getattr(self, "_edit_target_uniq", None)
        slot = getattr(self, "_edit_target_slot", None)
        if not uniq or total < 2:
            if self._numero_visivel:
                faixa.hide()
                self._numero_visivel = False
            return
        if total != self._numero_total:
            self._rebuild_numero_buttons(caixa, total)
            self._numero_total = total
        self._numero_updating = True
        try:
            if isinstance(slot, int) and 1 <= slot <= len(self._numero_botoes):
                self._numero_botoes[slot - 1].set_active(True)
        finally:
            self._numero_updating = False
        if not self._numero_visivel:
            faixa.show()
            self._numero_visivel = True

    def _on_numero_button_toggled(self, button: Any, numero: int) -> None:
        """Pede ao daemon que este controle passe a ser o número ``numero``.

        Só o botão que ficou ATIVO age (o grupo emite ``toggled`` também no
        que desliga), e a marcação programática do sync é ignorada pelo
        ``_numero_updating`` — sem isso, cada tique de 2 Hz reenviaria o
        pedido.

        Nada é escrito na janela por conta própria: quem repinta o chip, os
        cartões e o LED é o PRÓXIMO ``state_full``, que traz o ``player_slot``
        recalculado pelo daemon. É deliberado — a janela pintar o número novo
        antes de o daemon confirmar é como se cria a terceira verdade que esta
        sprint existe para matar ("três superfícies, dois números, o mesmo
        controle").
        """
        if getattr(self, "_numero_updating", False):
            return
        if not button.get_active():
            return
        uniq = getattr(self, "_edit_target_uniq", None)
        if not uniq:
            self._status_toast(
                "numero",
                "escolha um controle no cabeçalho antes de trocar o número",
            )
            return

        def _fim(resultado: Any) -> bool:
            ok, motivo = resultado
            if ok:
                self._status_toast(
                    "numero", f"Pronto — este controle agora é o {numero}."
                )
            else:
                self._status_toast(
                    "numero",
                    motivo
                    or "não consegui trocar o número — o Hefesto pode estar "
                    "desligado (ligue na aba Sistema)",
                )
            return False

        ipc_bridge.run_in_thread(
            lambda: ipc_bridge.identity_number_set(uniq, numero), on_success=_fim
        )

    # ------------------------------------------------------------------
    # Alvo de edição por-controle (PERFIL-04)
    # ------------------------------------------------------------------

    @staticmethod
    def _edit_badge_text(label: str | None, *, com_endereco: bool = True) -> str:
        """Texto do badge de edição por-controle; vazio = badge escondido.

        PLAYER-01 entrega 3: o selo "Editando: Controle 3" já dizia METADE do
        que o chip significa (que ele é um seletor de ALVO, não só um mostrador
        de número) — mas só aparecia quando havia endereço estável, que é
        justamente o caso em que a informação é menos surpreendente. Com
        ``com_endereco=False`` (controle sem MAC, handle por path) ele passa a
        aparecer TAMBÉM, dizendo a verdade incômoda: a edição daquele alvo cai
        na rota global e vale para todos.
        """
        if not label:
            return ""
        if com_endereco:
            return _("Editando: {alvo}").format(alvo=label)
        return _("Editando: {alvo} — sem endereço fixo, vale para todos").format(
            alvo=label
        )

    def _update_target_maps(self, conectados: list[dict[str, Any]]) -> None:
        """Recalcula index→uniq, index→rótulo e index→NÚMERO do ``state_full``.

        O ``uniq`` (MAC normalizado, estável entre USB e BT) vem do bloco
        ``controllers`` que o daemon já expõe. Controle sem MAC (key por
        path) fica com uniq None — a edição dele segue GLOBAL, como hoje.

        PLAYER-01: o mapa index→NÚMERO é novo e é o terceiro campo que o chip
        confundia num só. Ele guarda o ``player_slot`` CRU (``None`` quando o
        registro ainda não tem opinião) — de propósito diferente do
        ``_display_slot`` usado no rótulo, que cai na posição 1-based quando
        não há slot. Para EXIBIR, o palpite ajuda; para MANDAR TROCAR o
        número, palpite é mentira: sem slot de verdade não há o que permutar,
        e o seletor de número some em vez de oferecer uma escolha falsa.
        """
        uniq_by_index: dict[int, str | None] = {}
        label_by_index: dict[int, str] = {}
        slot_by_index: dict[int, int | None] = {}
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
            slot_cru = c.get("player_slot")
            slot_by_index[idx] = (
                slot_cru
                if isinstance(slot_cru, int) and not isinstance(slot_cru, bool)
                else None
            )
        self._target_uniq_by_index = uniq_by_index
        self._target_label_by_index = label_by_index
        self._target_slot_by_index = slot_by_index

    def _sync_edit_target(self, target_index: int | None) -> None:
        """Deriva o alvo de EDIÇÃO (uniq) do índice do seletor.

        Idempotente: só atualiza badge e re-popula as abas por-controle
        (lightbar/gatilhos) quando o alvo efetivamente muda. ``None`` =
        "Todos" (edição global, badge some).

        PLAYER-01: o NÚMERO do alvo (``_edit_target_slot``) é atualizado
        ANTES do curto-circuito de idempotência. Hoje o rótulo carrega o
        número dentro dele ("Controle 2 (BT)"), então na prática os dois
        mudam juntos — mas amarrar a leitura do número à igualdade do TEXTO
        do rótulo é exatamente o tipo de acoplamento que esta sprint está
        desfazendo. Atualizar antes custa uma atribuição e não tem como
        divergir.
        """
        uniq: str | None = None
        label: str | None = None
        slot: int | None = None
        if target_index is not None:
            slot = getattr(self, "_target_slot_by_index", {}).get(target_index)
        self._edit_target_slot = slot
        if target_index is not None:
            uniq = getattr(self, "_target_uniq_by_index", {}).get(target_index)
            label = getattr(self, "_target_label_by_index", {}).get(target_index)
            # R-16: o controle escolhido caiu, mas o índice ainda é o alvo dela.
            # Zerar aqui trocaria o destino da PRÓXIMA escrita em silêncio: o
            # badge sumia e o "Aplicar no controle" seguinte ia pela rota
            # global, apagando o override por-MAC dos outros. Mantemos o alvo e
            # deixamos o rótulo dizer a verdade.
            if uniq is None and label is None and self._edit_target_uniq is not None:
                logger.debug(
                    "edit_target_alvo_sumiu_do_estado_mantendo",
                    indice=target_index,
                )
                return
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
        """Mostra/esconde o badge conforme o alvo de edição atual.

        PLAYER-01: o selo aparece SEMPRE que há um alvo escolhido — antes ele
        exigia endereço estável, e o caso sem endereço (a edição vai pela rota
        global e vale para todos) era justamente o que mais merecia ser dito.
        """
        badge = getattr(self, "_edit_badge", None)
        if badge is None:
            return
        texto = self._edit_badge_text(
            self._edit_target_label,
            com_endereco=bool(self._edit_target_uniq),
        )
        if texto:
            badge.set_text(texto)
            badge.show()
        else:
            badge.hide()

    def _sync_coop_governa_luzes(self, state: dict[str, Any]) -> None:
        """Publica ``_coop_ligado`` para a aba Lightbar (PLAYER-01 entrega 5).

        A camada de co-op sobrescreve o desenho das 5 luzes ACIMA da escolha
        manual, por construção: com o co-op ativo, escolher desenho na aba
        Lightbar não adianta. Quem lê o ``state_full`` é esta aba, então é
        daqui que o dado sai — e só se repinta a moldura na TRANSIÇÃO do
        flag, nunca a 2 Hz (o ``_refresh_lightbar_from_draft`` refaz a aba
        inteira e não tem por que rodar sem motivo).
        """
        coop = state.get("coop")
        ligado = bool(coop.get("enabled")) if isinstance(coop, dict) else False
        if ligado == bool(getattr(self, "_coop_ligado", False)):
            return
        self._coop_ligado = ligado
        refresh = getattr(self, "_refresh_lightbar_from_draft", None)
        if callable(refresh):
            with contextlib.suppress(Exception):
                refresh()

    def _update_rumble_badge(self, state: dict[str, Any]) -> None:
        """Denuncia no banner que a vibração está travada pela GUI.

        Só (0,0) — o silêncio do botão "Parar" — e valores fixos não-zero
        merecem aviso: nos dois o FF do jogo é ignorado. Em passthrough
        (`rumble_active is None`, o normal para jogar) o badge some.
        """
        badge = getattr(self, "_rumble_badge", None)
        if badge is None:
            return
        ativo = state.get("rumble_active")
        if not isinstance(ativo, (list, tuple)) or len(ativo) != 2:
            badge.hide()
            return
        if tuple(ativo) == (0, 0):
            texto = "vibração em silêncio"
        else:
            texto = f"vibração fixa em {ativo[0]}/{ativo[1]}"
        badge.set_markup(
            f'<span foreground="#ffb86c">{texto}</span>'
        )
        badge.set_tooltip_text(
            "A vibração está travada pela aba Rumble e o jogo não consegue "
            "mexer nela. Para devolver ao jogo: aba Rumble → "
            f"“{BTN_GIVE_BACK_TO_GAME}”."
        )
        badge.show()

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
        # SELETOR-UNO-01 (22/07, pedido da mantenedora): o seletor aparece com
        # 1+ controle NO TOTAL — mesmo sozinho, o controle ganha o botão com
        # número e via ("Sony 1 · BT"), no mesmo formato dos externos.
        #
        # CONTAGEM-01: a soma sai da mesma função que o cabeçalho e os cartões
        # usam, sobre o mesmo payload. Somar `len(conectados) + len(externals)`
        # aqui dava o número certo por acaso — enquanto `_externals` viesse de
        # outro lugar, era o quarto ponto da janela a contar por conta própria.
        total = len(controles_na_mesa(state))
        # PERFIL-05: numeração dos externos usa a contagem REAL de DualSense
        # (antes derivava de len(botões)-1, que assumia a linha "Todos").
        self._dualsense_count = len(conectados)
        if total < 1:
            self._sync_edit_target(None)
            # PLAYER-01: sem controle nenhum não há número para escolher.
            self._refresh_numero_selector(0)
            if self._target_combo_visible:  # só esconde na TRANSIÇÃO
                self._set_target_strip_visible(False)
                self._target_combo_visible = False
            return
        # R-16 (auditoria 23/07): o alvo de edição segue o GESTO dela, não a
        # CONTAGEM de controles.
        #
        # Antes: `editavel = len(conectados) >= 2` e, abaixo do limiar,
        # `_sync_edit_target(None)` FORÇAVA a escrita global — e este método
        # roda no tick de 2 Hz, sem guarda de aba visível. Dois estragos:
        #
        #   1. com um único DualSense com nó no kernel (o estado medido em
        #      23/07: o roxo estava sem uhid), `_edit_target_uniq` ficava
        #      permanentemente None e a edição "controle a controle" estava
        #      literalmente DESLIGADA — sem nenhuma mensagem dizendo isso;
        #   2. um controle caindo no meio da edição zerava o alvo por baixo das
        #      abas: o badge sumia e o "Aplicar no controle" seguinte ia pela
        #      rota global, apagando o override dos outros.
        #
        # Override por-MAC é o valor CERTO mesmo com um controle só (ele
        # sobrevive ao replug e ao perfil). `None` passa a significar
        # exclusivamente "ela clicou em Todos".
        editavel = len(conectados) >= 1
        if editavel:
            # Só sincroniza quando há um alvo derivado do estado; a ausência de
            # `target_index` não é ordem de ir para global.
            if target_index is not None:
                self._sync_edit_target(target_index)
            if len(conectados) == 1:
                # SELETOR-UNO-01 (decisão da mantenedora, 22/07): com UM
                # DualSense o seletor mostra só o botão do próprio controle,
                # sem a linha "Todos". A UI segue igual.
                #
                # O que muda com o R-16 é o ÍNDICE que essa linha carrega: era
                # `None` (= broadcast global), sob a premissa de que "com um
                # controle só, Todos e ele são a mesma coisa". Não são: o
                # override por-MAC sobrevive ao replug e à troca de perfil; a
                # escrita global, não. Era essa premissa que deixava a edição
                # por-controle desligada quando só um DualSense tinha nó no
                # kernel — o estado medido em 23/07.
                c = conectados[0]
                transporte = (c.get("transport") or "?").upper()
                rows: list[tuple[str, int | None]] = [
                    (
                        _("Controle {n} — {t}").format(
                            n=_display_slot(c), t=transporte
                        ),
                        int(c.get("index", 0)),
                    )
                ]
            else:
                rows = self._controller_target_rows(conectados)
        else:
            # Só externos conectados: nenhum radio (não há alvo de edição);
            # os botões de externos entram no _rebuild normalmente.
            rows = []
        # PLAYER-01: o seletor de NÚMERO sincroniza ANTES do curto-circuito de
        # idempotência abaixo. Ele depende do alvo e da contagem da mesa, não
        # dos rótulos dos chips: com os mesmos chips e a mesma posição ativa (o
        # caso comum, que é onde o early-return dispara), um controle entrando
        # ou saindo mudaria a faixa de números e nada a atualizaria.
        self._refresh_numero_selector(total)
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
                self._set_target_strip_visible(True)
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
                '<span foreground="#ff5555">'
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
    def _controllers_transports(mesa: list[dict[str, Any]]) -> str:
        """'BT + USB' (vias em texto plano, primário primeiro).

        CONTAGEM-01: recebe a MESA (DualSense adotados + externos), não só a
        lista de DualSense — senão a linha "Como conectou" listaria duas vias
        embaixo de um cabeçalho que diz quatro controles. A tradução da via de
        cada espécie mora em `via_curta` (dono único).
        """
        return " + ".join(via_curta(c) for c in mesa)

    def _render_online(self, state: dict[str, Any]) -> None:
        """Header canônico de estado ONLINE —  verde + transport.

        Delega o pinta-completo-da-aba a `_render_live_state` e
        `_render_slow_state` (já chamados pelos ticks rápidos). Aqui só
        firma o header de forma idempotente.

        CONTAGEM-01, entrega 2: o número do cabeçalho é o da MESA. Ele contava
        `len(conectados)` — só DualSense — e era o "2 controles: USB + BT" que
        aparecia por cima de uma fita de chips mostrando quatro. E a decisão
        de "há controle?" também passou para a mesa: o `connected` do payload
        fala só do DualSense primário, então com dois externos e nenhum
        DualSense o cabeçalho afirmava "Controle Desconectado" com dois
        controles ligados na frente dela.
        """
        connected = bool(state.get("connected"))
        transport = state.get("transport") or "—"
        header = self._get("header_connection")
        mesa = controles_na_mesa(state)
        if header is not None:
            if len(mesa) > 1:
                # FEAT-DSX-MULTI-CONTROLLER-01: N controles — primário em negrito.
                partes = " + ".join(
                    f"<b>{via_curta(c)}</b>"
                    if c.get("is_primary") and not e_externo(c)
                    else via_curta(c)
                    for c in mesa
                )
                header.set_markup(
                    f'<span foreground="#50fa7b">&#9679; {len(mesa)} controles: '
                    f"{partes}</span>"
                )
            elif mesa or connected:
                # `mesa` vazia com `connected` verdadeiro = payload sem o bloco
                # `controllers` (daemon anterior ao multi-controle, dublê de
                # teste). O transporte do topo ainda responde por ele — o
                # caminho degradado de sempre, preservado de propósito.
                via = via_curta(mesa[0]) if mesa else "?"
                if via == "?" and transport != "—":
                    via = str(transport).upper()
                header.set_markup(
                    f'<span foreground="#50fa7b">&#9679; Conectado Via {via}</span>'
                )
            else:
                header.set_markup(
                    '<span foreground="#ff5555">&#9675; Controle Desconectado</span>'
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
                '<span foreground="#ffb86c">&#9680; Tentando Reconectar...</span>'
            )
        self._set_label("status_daemon", "Reconectando")

    def _render_offline(self) -> None:
        header = self._get("header_connection")
        if header is not None:
            header.set_markup(
                '<span foreground="#ff5555">'
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
            self._set_target_strip_visible(False)
            self._target_combo_visible = False
        # PLAYER-01: sem daemon não há número para trocar — a faixa some junto.
        self._refresh_numero_selector(0)
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
        # MIC-FAIXA-01: a faixa do rodapé anda no tick RÁPIDO porque a onda do
        # medidor é o dado que se move — a 2 Hz ela pareceria travada.
        self._sync_mic_strip(state)

    def _render_slow_state(self, state: dict[str, Any]) -> None:
        # Mesma proteção do render vivo (BUG-COMBO-POPUP-FLICKER-02): não mexe nos
        # widgets enquanto um popup está aberto, para não fechá-lo via re-layout.
        if self._popup_is_open():
            return
        # CONTAGEM-01, entrega 5: os externos chegam pelo MESMO `state_full`
        # que traz os DualSense. A busca própria e assíncrona
        # (`controller.list {external:true}` a cada 4 s) foi removida: era ela
        # que fazia a fita de chips enxergar quatro enquanto o resto da janela
        # dizia dois — duas rotas de dados para a mesma pergunta divergem, é
        # só questão de qual chega primeiro.
        self._sync_externals_from_state(state)
        self._update_rumble_badge(state)
        self._sync_coop_governa_luzes(state)
        connected = bool(state.get("connected"))
        transport = state.get("transport") or "—"
        battery = state.get("battery_pct")
        active_profile = state.get("active_profile") or "Nenhum"

        conectados = self._connected_controllers(state)
        # CONTAGEM-01, entrega 2: "Conectado (N controles)" conta a MESA. Este
        # rótulo era o terceiro lugar a repetir `len(conectados)` — a aba
        # Status dizia dois com quatro controles na mesa, pela mesma causa do
        # cabeçalho. O ramo de baixo preserva o caminho degradado (payload sem
        # o bloco `controllers`), pelo mesmo motivo do `_render_online`.
        mesa = controles_na_mesa(state)
        if len(mesa) > 1:
            self._set_label("status_connection", f"Conectado ({len(mesa)} controles)")
            self._set_label("status_transport", self._controllers_transports(mesa))
        else:
            self._set_label(
                "status_connection", "Conectado" if (mesa or connected) else "Desconectado"
            )
            via = via_curta(mesa[0]) if mesa else "?"
            if via == "?":
                via = transport.upper() if transport != "—" else "—"
            self._set_label("status_transport", via)
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
        # MIC-FAIXA-01: e o conjunto de LINHAS da faixa junto, pelo mesmo
        # motivo — a faixa tem de estar montada no instante em que a aba
        # aparece, não 100 ms depois.
        self._sync_mic_strip(state)

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
