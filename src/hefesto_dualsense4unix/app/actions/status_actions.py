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
from collections.abc import Mapping
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app import ipc_bridge, mesa
from hefesto_dualsense4unix.app.actions.base import (
    WidgetAccessMixin,
    numero_do_controle,
)
from hefesto_dualsense4unix.app.actions.external_controllers import (
    button_labels_for,
    external_key,
    friendly_type,
    slot_label,
    slot_of,
    transport_label,
)
from hefesto_dualsense4unix.app.actions.home_actions import (
    aviso_do_wrapper,
    id_da_pagina,
    id_da_pagina_corrente,
    vpad_degradation_text,
)
from hefesto_dualsense4unix.app.actions.rumble_actions import (
    COMO_DEVOLVER_AO_JOGO,
)
from hefesto_dualsense4unix.app.alvo_de_edicao import (
    MOTIVO_DAEMON_DESLIGADO,
    MOTIVO_MESA_VAZIA,
    MOTIVO_SEM_ESTADO,
    AlvoDeEdicao,
    alvo_de_edicao,
    definir_alvo,
    esquecer_alvo,
)
from hefesto_dualsense4unix.app.constants import (
    LIVE_POLL_INTERVAL_MS,
    RECONNECT_FAIL_THRESHOLD,
    RECONNECT_POLL_INTERVAL_S,
    STATE_POLL_INTERVAL_MS,
)
from hefesto_dualsense4unix.app.ipc_bridge import call_async

# GRID_BOTOES/ALL_BUTTONS/L2_R2_THRESHOLD moraram aqui até o STATUS-02;
from hefesto_dualsense4unix.app.widgets.controller_card import (
    ALL_BUTTONS,
    GRID_BOTOES,
    L2_R2_THRESHOLD,
    CaixaDeTetoElastico,
    ControllerCard,
)
from hefesto_dualsense4unix.app.widgets.painel_no_jogo import (
    COR_DO_AVISO_DE_PERFIL,
    TEXTO_SEM_CONTROLE,
    PainelNoJogo,
    aviso_do_perfil,
    jogo_steam_aberto,
    recado_global,
    texto_do_contexto,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.markup import escapar_markup

logger = get_logger(__name__)

ABA_STATUS = "tab_status_box"

ABA_NO_JOGO = "tab_no_jogo_box"

#: * **1** faria a aba piscar — o tique é de 2 Hz e um `daemon.state_full` que
FALHAS_ATE_ESVAZIAR_NO_JOGO = 3

COLUNA_BERCO_DA_ROTA = 4
ALTURA_BERCO_DA_ROTA = 2


_display_slot = numero_do_controle


ContagemDeControles = mesa.ContagemDeControles
texto_de_contagem = mesa.texto_de_contagem


MINUTOS_ENTRE_TENTATIVAS = 2

POSICAO_DO_BANNER_NAO_ADOTADO = 2


def texto_de_controle_nao_adotado(state: dict[str, Any] | None) -> str:
    """Aviso de que há controle LIGADO que o sistema não entregou ao Hefesto.

    CONTROLE-QUE-NAO-ENTROU-01 (09/08/2026). Medido na máquina dela: dois
    DualSense ligados e pareados, e a janela mostrava UM — sem, em lugar
    nenhum do produto, uma pista do porquê. O driver do kernel havia abortado
    o segundo na probe; ele conecta no rádio, acende a luz do próprio firmware
    e não ganha hidraw, nó de LED nem dispositivo de entrada. Para o Hefesto,
    que enumera handles abertos, ele não existe.

    O texto tem três partes obrigatórias, e cada uma desfaz uma leitura errada
    que a tela de hoje produz:

    - **o que está acontecendo, na língua dela** — "está ligado, mas não
      chegou até aqui". As palavras do defeito (probe, hidraw, driver, órfão)
      não aparecem: elas descrevem o mecanismo, e o mecanismo não é o que ela
      vê. O que ela vê é um controle aceso que a janela não conta;
    - **que o produto tenta sozinho, e em quanto tempo** — a cura existe e é
      automática (`bt_rebind_orphans.sh`, chamado pela vigia
      `bt_health_watchdog.sh` a cada ``MINUTOS_ENTRE_TENTATIVAS`` minutos).
      Sem esta parte o aviso seria só um susto: ela desligaria o controle bom
      para "resolver";
    - **a saída, se a tentativa não pegar** — desligar o controle no botão PS
      e ligar de novo. É a mesma cura manual que o script loga quando desiste,
      e reconectar dá orçamento novo de tentativas por construção (o id do
      device muda).

    Devolve ``""`` quando não há nada a dizer: daemon sem resposta, payload
    torto ou daemon antigo sem a chave. Um aviso deste peso não pode acender
    por ausência de dado.
    """
    if not isinstance(state, dict):
        return ""
    bloco = state.get("controles_sem_driver")
    if not isinstance(bloco, dict):
        return ""
    quantos = bloco.get("quantidade")
    if not isinstance(quantos, int) or isinstance(quantos, bool) or quantos <= 0:
        return ""
    if quantos == 1:
        return _(
            "Um controle está ligado, mas o sistema não conseguiu entregá-lo "
            "ao Hefesto — ele acende e não aparece aqui. O Hefesto tenta "
            "trazê-lo sozinho, e a próxima tentativa é em até {min} minutos. "
            "Se ele não voltar, desligue o controle segurando o botão PS por "
            "10 segundos e ligue de novo."
        ).format(min=MINUTOS_ENTRE_TENTATIVAS)
    return _(
        "{n} controles estão ligados, mas o sistema não conseguiu entregá-los "
        "ao Hefesto — eles acendem e não aparecem aqui. O Hefesto tenta "
        "trazê-los sozinho, e a próxima tentativa é em até {min} minutos. Se "
        "eles não voltarem, desligue cada um segurando o botão PS por 10 "
        "segundos e ligue de novo."
    ).format(n=quantos, min=MINUTOS_ENTRE_TENTATIVAS)


def _lista_de_jogadores(quantos: int) -> str:
    """``"P2, P3 e P4"`` — quem saiu, por nome, a partir de P2."""
    nomes = [f"P{n}" for n in range(2, 2 + max(0, quantos))]
    if len(nomes) <= 1:
        return "".join(nomes)
    return f"{', '.join(nomes[:-1])} e {nomes[-1]}"


def texto_do_coop_derrubado(bloco_coop: object) -> str:
    """Frase do banner quando o jogo derruba o co-op — ``""`` quando não há.

    CONTAGEM-E-COOP-01 (E1a). O daemon publica o fato desde 29/07
    (`ipc_handlers.py:2094-2095`: `coop.derrubado_por_steam_input` e
    `coop.secundarios_derrubados`) e NENHUMA linha da janela o lia. Pior que
    calada, a janela ficava enganosa: `CoopManager.disable()` não zera
    `coop_enabled`, então o `state_full` segue publicando `coop.enabled=True`
    com `coop.players=1` — de fora, indistinguível de "ela desligou o co-op".

    A frase tem de dizer o PREÇO, não o fato, e as três partes são
    obrigatórias porque cada uma desfaz uma mentira medida:

    - o NÚMERO vem de ``secundarios_derrubados``, nunca de ``players``
      (que já voltou a 1 no tique seguinte — é o defeito original);
    - a NEGAÇÃO ("não foi você") desfaz a ambiguidade do `enabled=True`;
    - a PROMESSA de volta é verdadeira: `resume_vpads_after_steam_input`
      chama `coop.sync(force=True)` (`gamepad.py:593`), e mesmo pelo
      caminho manual o ciclo normal recria os secundários porque `disable()`
      não desligou `coop_enabled`.

    Devolve ``""`` também quando o gatilho está aceso mas o número é zero: as
    duas mortes do contador (`gamepad.py:552` e `:1987`) existem para
    o aviso não sobreviver ao retorno do co-op, e aviso pendurado sem número
    seria a mentira nova que elas evitam.

    QUEM saiu (``P2, P3 e P4``) fica só no tooltip, e é medição, não gosto: o
    banner é uma linha só e os dois badges podem acender juntos. Medido no
    `header_bar` do glade, com a janela dela em 953px de largura (a de agora):
    banner limpo 397px, só o aviso 815px, só a vibração travada 548px — e os
    DOIS juntos **966px**, 13px além da janela. Treze pixels não são folga
    (lição da CI de 29/07, que mede com outras fontes), e tirar a lista de
    jogadores da linha derruba o par para 890px — 63px de sobra. As três
    partes obrigatórias — o número, a negação e a promessa de volta —
    continuam todas aqui.
    """
    if not isinstance(bloco_coop, dict):
        return ""
    if not bool(bloco_coop.get("derrubado_por_steam_input")):
        return ""
    quantos = bloco_coop.get("secundarios_derrubados")
    if not isinstance(quantos, int) or isinstance(quantos, bool) or quantos <= 0:
        return ""
    if quantos == 1:
        return _("1 jogador saiu — não foi você; volta sozinho")
    return _("{n} jogadores saíram — não foi você; voltam sozinhos").format(
        n=quantos
    )


def tooltip_do_coop_derrubado(bloco_coop: object) -> str:
    """O preço por extenso, para o tooltip do badge — ``""`` sem queda."""
    if not isinstance(bloco_coop, dict) or not texto_do_coop_derrubado(bloco_coop):
        return ""
    quantos = int(bloco_coop["secundarios_derrubados"])
    quem = _lista_de_jogadores(quantos)
    if quantos == 1:
        return _(
            "Neste jogo quem entrega o controle é a Steam: os controles "
            "virtuais foram recolhidos, e por isso {quem} saiu do co-op. A "
            "sua cor e os seus gatilhos continuam valendo.\n\n"
            "Você não desligou nada — ele volta sozinho quando você fechar o "
            "jogo."
        ).format(quem=quem)
    return _(
        "Neste jogo quem entrega o controle é a Steam: os controles virtuais "
        "foram recolhidos, e por isso {quem} saíram do co-op. A sua cor e os "
        "seus gatilhos continuam valendo.\n\n"
        "Você não desligou nada — os {n} voltam sozinhos quando você fechar o "
        "jogo."
    ).format(quem=quem, n=quantos)


class StatusActionsMixin(WidgetAccessMixin):
    """Atualiza a aba Status em tempo real."""

    _reconnect_state: str = "online"
    _consecutive_failures: int = 0
    _first_poll_succeeded: bool = False
    _live_inflight: bool = False
    # 1 worker que os 3 pollers de `daemon.state_full` compartilham.
    _profile_inflight: bool = False
    _reconnect_inflight: bool = False
    _profile_falhas_seguidas: int = 0
    _status_cards: dict[tuple[Any, ...], Any]
    _status_card_keys: list[tuple[Any, ...]]
    _target_combo: Any
    _target_combo_rows: list[tuple[str, int | None]]
    _target_combo_updating: bool
    _target_combo_visible: bool
    _target_combo_active: int
    _target_buttons: list[Any]
    # 8BIT-02: controles externos (não-DualSense) no seletor do topo + a ficha
    # botões próprios (fora do grupo de rádio dos DualSense).
    _external_buttons: list[Any]
    _externals: list[dict[str, Any]]
    _externals_fetch_ts: float = 0.0
    _externals_inflight: bool = False
    _externals_sig: tuple[str, ...] | None = None
    # sync com o `output_target_index` do daemon a 2 Hz e é atualizado NA
    _alvo_de_edicao: AlvoDeEdicao
    _target_uniq_by_index: dict[int, str | None]
    _target_label_by_index: dict[int, str]
    _edit_badge: Any = None
    _target_strip: Any = None
    _numero_faixa: Any = None
    _numero_box: Any = None
    _numero_botoes: list[Any]
    _numero_total: int = 0
    _numero_updating: bool = False
    _numero_visivel: bool = False
    _edit_target_slot: int | None = None
    _target_slot_by_index: dict[int, int | None]
    #: luzes, ACIMA da escolha manual. Lido do `state_full` aqui e consumido
    _coop_ligado: bool = False
    #: fica guardado até o modo sair. Lido do `state_full` aqui (mesmo tique do
    _modo_nativo_ligado: bool = False
    _rumble_badge: Any = None
    _mic_monitor: Any = None
    _banner_nao_adotado: Any = None

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
        self._montar_banner_nao_adotado()
        botao_rota = self._get("btn_som_no_controle")
        if botao_rota is not None and hasattr(botao_rota, "connect"):
            botao_rota.connect("clicked", self._on_rota_de_som_clicada)
        GLib.timeout_add(LIVE_POLL_INTERVAL_MS, self._tick_live_state)
        GLib.timeout_add(STATE_POLL_INTERVAL_MS, self._tick_profile_state)
        GLib.timeout_add_seconds(
            RECONNECT_POLL_INTERVAL_S, self._tick_reconnect_state
        )
        GLib.idle_add(lambda: self._tick_live_state() and False)
        GLib.idle_add(lambda: self._tick_profile_state() and False)
        self._first_poll_succeeded = False
        GLib.timeout_add_seconds(5, self._check_initial_poll_fallback)
        # timers que ela usa. Ela NÃO ganha timer próprio — ver
        self.install_no_jogo_tab()


    _no_jogo_paineis: Any = None
    _no_jogo_keys: Any = None
    _no_jogo_slot: Any = None
    _no_jogo_contexto: Any = None
    _no_jogo_recado: Any = None
    _no_jogo_perfil: Any = None
    _no_jogo_vazio: Any = None

    def install_no_jogo_tab(self) -> None:
        """Monta a aba "No jogo" — cabeçalho de contexto + berço dos painéis.

        O pedido dela, literal (09/08/2026): *"eu sei que a aba status é uma
        coisa, mas isso converter em input seja via xbox ou dualsense ou nativo
        é outra"*. A aba Status responde pelo controle FÍSICO; esta responde
        pelo que atravessa para o JOGO, e é ela que fecha a pergunta *"funciona
        nos três modos?"* sem terminal e sem o testador da Steam.

        **Três decisões de montagem, e o preço de cada uma na mesa.**

        *Página própria, e não uma seção da aba Status.* A aba Status está
        exatamente no orçamento de largura — dois cards pedem 1180px numa
        janela de 1180 —, e não há rolagem horizontal para onde fugir: um
        widget novo dentro do card sobe intacto até a janela. Uma página nova
        não disputa largura com ninguém. O preço é uma aba a mais na tira, que
        é `scrollable` desde sempre.

        *Teto elástico por código, e não pela lista do `app.py`.* O
        `_PAGINAS_COM_TETO_ELASTICO` mora noutro arquivo; a mesma
        `CaixaDeTetoElastico` que ele usa é pública e entra aqui direto. A aba
        para nos mesmos 1400px das outras na tela de 1920 dela, sem uma segunda
        lista de páginas para alguém esquecer de atualizar.

        *Nada de `GLib` novo.* O gate de timers desta mixin
        (`test_status_cards`) conta as ocorrências no fonte, e o número não
        muda: quem pinta esta aba é o tique de 2 Hz que já existia.
        """
        pagina = self._get(ABA_NO_JOGO)
        if pagina is None or not hasattr(pagina, "pack_start"):
            return
        self._no_jogo_paineis = {}
        self._no_jogo_keys = []

        miolo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        self._no_jogo_contexto = Gtk.Label(label="")
        self._no_jogo_contexto.set_xalign(0.0)
        self._no_jogo_contexto.set_line_wrap(True)
        self._no_jogo_contexto.set_max_width_chars(100)
        self._no_jogo_contexto.set_halign(Gtk.Align.START)
        self._no_jogo_contexto.get_style_context().add_class(
            "hefesto-titulo-secao"
        )
        miolo.pack_start(self._no_jogo_contexto, False, False, 0)

        self._no_jogo_recado = Gtk.Label(label="")
        self._no_jogo_recado.set_xalign(0.0)
        self._no_jogo_recado.set_line_wrap(True)
        self._no_jogo_recado.set_max_width_chars(84)
        self._no_jogo_recado.set_halign(Gtk.Align.START)
        self._no_jogo_recado.get_style_context().add_class("dim-label")
        self._no_jogo_recado.set_no_show_all(True)
        miolo.pack_start(self._no_jogo_recado, False, False, 0)

        self._no_jogo_perfil = Gtk.Label(label="")
        self._no_jogo_perfil.set_xalign(0.0)
        self._no_jogo_perfil.set_line_wrap(True)
        self._no_jogo_perfil.set_max_width_chars(84)
        self._no_jogo_perfil.set_halign(Gtk.Align.START)
        self._no_jogo_perfil.set_no_show_all(True)
        miolo.pack_start(self._no_jogo_perfil, False, False, 0)

        self._no_jogo_vazio = Gtk.Label(label=TEXTO_SEM_CONTROLE)
        self._no_jogo_vazio.set_xalign(0.0)
        self._no_jogo_vazio.set_halign(Gtk.Align.START)
        self._no_jogo_vazio.get_style_context().add_class("dim-label")
        self._no_jogo_vazio.set_no_show_all(True)
        miolo.pack_start(self._no_jogo_vazio, False, False, 0)

        self._no_jogo_slot = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12
        )
        miolo.pack_start(self._no_jogo_slot, False, False, 0)

        pagina.pack_start(CaixaDeTetoElastico(miolo), True, True, 0)
        pagina.show_all()
        self._nascer_aba_no_jogo_escondida()


    def _pagina_do_notebook(self, page_id: str) -> Any:
        """O filho DIRETO do notebook cuja página é ``page_id``. ``None`` = não há."""
        notebook = self._get("main_notebook")
        if notebook is None or not hasattr(notebook, "get_children"):
            return None
        for filho in notebook.get_children():
            if id_da_pagina(filho) == page_id:
                return filho
        return None

    def _nascer_aba_no_jogo_escondida(self) -> None:
        """A aba "No jogo" nasce FORA da tira, e é o tique que a traz."""
        alvo = self._pagina_do_notebook(ABA_NO_JOGO)
        if alvo is None or not hasattr(alvo, "hide"):
            return
        with contextlib.suppress(Exception):
            alvo.show_all()
            alvo.set_no_show_all(True)
            alvo.hide()

    def _sync_visibilidade_no_jogo(self, state: dict[str, Any] | None) -> None:
        """Põe/tira a aba "No jogo" da tira conforme haja jogo da Steam aberto."""
        aberto = jogo_steam_aberto(state)
        if aberto is None:
            return
        alvo = self._pagina_do_notebook(ABA_NO_JOGO)
        if alvo is None or not hasattr(alvo, "hide"):
            return
        with contextlib.suppress(Exception):
            if aberto:
                alvo.show()
                return
            if not alvo.get_visible():
                return
            self._sair_da_aba_no_jogo()
            alvo.hide()

    def _sair_da_aba_no_jogo(self) -> None:
        """Leva o foco para a aba Status se ela estiver NA aba que vai sumir."""
        notebook = self._get("main_notebook")
        if notebook is None or id_da_pagina_corrente(notebook) != ABA_NO_JOGO:
            return
        destino = self._pagina_do_notebook(ABA_STATUS)
        if destino is None:
            return
        indice = notebook.page_num(destino)
        if isinstance(indice, int) and indice >= 0:
            notebook.set_current_page(indice)

    def _sync_paineis_no_jogo(self, state: dict[str, Any] | None) -> None:
        """Repinta a aba "No jogo" a partir do ``state_full``.

        Chamada pelo tique LENTO (2 Hz) e só com esta aba à vista, exatamente
        como o tique de 10 Hz da aba Status só trabalha com a Status à vista
        (BUG-STATUS-TICK-HIDDEN-TAB-01: com outra aba na frente, pintar é gasto
        de CPU que ninguém vê — e um poller cego já custou 104% de um núcleo
        nesta casa).

        2 Hz e não 10: o que muda aqui é a SITUAÇÃO de um recurso, que dura
        segundos (`ATIVIDADE_FRESCA_S` é 3,0 s), nunca um valor por quadro. E a
        carona no tique lento é o que mantém o gate de timers intacto — nenhum
        `GLib.timeout_add` novo.

        ``state`` ``None`` = daemon desligado: o cabeçalho passa a dizer isso e
        os painéis somem, em vez de congelarem o último estado bom. Painel
        parado com número de três minutos atrás ao lado da palavra "no jogo
        agora" é a mentira confortável que esta aba existe para não contar.
        """
        slot = self._no_jogo_slot
        if slot is None:
            return
        self._sync_visibilidade_no_jogo(state)
        notebook = self._get("main_notebook")
        if (
            notebook is not None
            and id_da_pagina_corrente(notebook) != ABA_NO_JOGO
        ):
            return
        self._no_jogo_contexto.set_text(texto_do_contexto(state))
        recado = recado_global(state)
        self._no_jogo_recado.set_text(recado or "")
        self._no_jogo_recado.set_visible(recado is not None)
        aviso = aviso_do_perfil(state)
        if aviso is not None:
            self._no_jogo_perfil.set_markup(
                f'<span foreground="{COR_DO_AVISO_DE_PERFIL}">'
                f"{escapar_markup(aviso)}</span>"
            )
        else:
            self._no_jogo_perfil.set_text("")
        self._no_jogo_perfil.set_visible(aviso is not None)
        conectados = (
            self._connected_controllers(state)
            if isinstance(state, dict) and recado is None
            else []
        )
        keys = self._status_card_keys_for(conectados)
        if keys != self._no_jogo_keys:
            self._rebuild_paineis_no_jogo(slot, keys)
        self._no_jogo_vazio.set_visible(
            recado is None and isinstance(state, dict) and not conectados
        )
        for key, entry in zip(
            keys,
            StatusActionsMixin._conectados_na_ordem_dos_cards(conectados),
            strict=True,
        ):
            painel = self._no_jogo_paineis.get(key)
            if painel is not None and isinstance(state, dict):
                painel.atualizar(entry, state)

    def _rebuild_paineis_no_jogo(self, slot: Any, keys: list[Any]) -> None:
        """Recria os painéis — o conjunto de controles mudou."""
        for filho in list(slot.get_children()):
            slot.remove(filho)
            filho.destroy()
        self._no_jogo_paineis = {}
        self._no_jogo_keys = list(keys)
        for key in keys:
            painel = PainelNoJogo()
            slot.pack_start(painel, False, False, 0)
            self._no_jogo_paineis[key] = painel
        slot.show_all()


    def set_status_tab_visivel(self, visivel: bool) -> None:
        """Liga/desliga a captura de áudio do microfone dos controles."""
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


    _rota_de_som: Any = None
    _rota_inflight: bool = False
    _rota_sink: str = ""
    #: Dicionário VAZIO é "ainda não li", e é o que mantém os cards calados
    _canais_de_som: Mapping[str, str] = {}
    _regra_do_sono: bool | None = None
    _ultimo_estado_global: dict[str, str] = {}  # noqa: RUF012

    @staticmethod
    def _bateria_da_mesa(state: dict[str, Any]) -> tuple[float, str]:
        """``(fração, texto)`` da barra de bateria — ``"— %"`` quando não há fonte.

        STATUS-DIZ-O-QUE-VÊ-01/T12 (25/08/2026). **É a afirmação mais
        silenciosa e mais crível da aba, e por isso a mais cara quando erra.**

        Duas medições se somam para exigir esta guarda:

        * o mapa de canais rebaixou `energia.bateria.percentual` do DualSense
          de **medido** para **inferência de código** em 15/08/2026 (D-14) —
          *"a evidência registrada descreve LEITURA DE FONTE (arquivo, linha,
          grep), não medição no aparelho"*;
        * e o daemon publica, no MESMO payload, um topo que discorda da
          lista. Medido em 23/08 às 21h53, com **zero** DualSense no sistema:
          ``daemon.status`` e o topo do ``state_full`` diziam
          ``connected: true, battery_pct: 75``, enquanto
          ``controllers[0]`` dizia ``connected: false``. A barra afirmava
          **75 %** de um controle que não existe.

        A régua de "quem está na mesa" é a da Z5 (`app/mesa.py`, dono único),
        e esta função a CONSOME: quando o daemon publica a lista de
        controles, é ela que manda. Quando não publica — daemon antigo, ou
        payload parcial —, o topo continua valendo: recusar o número aí seria
        trocar um erro por outro, e a ausência de lista não é evidência de
        mesa vazia.

        Não é para tirar o número. É para o número parar de aparecer quando a
        fonte dele não existe.
        """
        bruto = state.get("battery_pct")
        tem_numero = isinstance(bruto, (int, float)) and not isinstance(bruto, bool)
        mesa_publicada = isinstance(state.get("controllers"), list)
        if mesa_publicada and not StatusActionsMixin._connected_controllers(state):
            return (0.0, "— %")
        if not tem_numero:
            return (0.0, "— %")
        assert isinstance(bruto, (int, float))
        return (bruto / 100, f"{bruto} %")

    def _set_battery_text(self, texto: str) -> None:
        """Escreve o número da bateria na barra E no rótulo ao lado dela."""
        barra = self._get("status_battery_bar")
        if barra is not None:
            with contextlib.suppress(Exception):
                barra.set_text(texto)
        rotulo = self._get("status_battery_pct")
        if rotulo is not None:
            with contextlib.suppress(Exception):
                rotulo.set_text(texto)

    def _sink_do_controle_para_a_rota(self, monitor: Any, uniqs: tuple[str, ...]) -> str:
        """Sink que o botão da rota tem como alvo; "" quando não há certeza."""
        if monitor is None:
            return ""
        nomes = set()
        for uniq in uniqs:
            with contextlib.suppress(Exception):
                nome = monitor.sink_de(uniq)
                if nome:
                    nomes.add(nome)
        return nomes.pop() if len(nomes) == 1 else ""

    def _refresh_rota_de_som(self) -> None:
        """Relê a rota e repinta o botão — leitura FORA da thread do GTK."""
        botao = self._get("btn_som_no_controle")
        if botao is None or not hasattr(botao, "set_sensitive"):
            return
        if self._rota_inflight:
            return
        self._rota_inflight = True
        rota = self._rota_de_som
        if rota is None:
            try:
                from hefesto_dualsense4unix.app.audio_saida import RotaDeSaida
            except Exception as exc:
                logger.debug("rota_de_som_indisponivel", err=str(exc))
                self._rota_inflight = False
                return
            rota = RotaDeSaida()
            self._rota_de_som = rota
        sink = self._rota_sink

        def _ler() -> Any:
            from hefesto_dualsense4unix.app.audio_saida import (
                regra_nunca_dorme_instalada,
            )

            return (rota.estado(sink), regra_nunca_dorme_instalada())

        ipc_bridge.run_in_thread(
            _ler, self._on_rota_lida, self._on_rota_falhou
        )

    def _on_rota_lida(self, leitura: Any) -> bool:
        """Aplica rótulo, sensibilidade e dica — já na thread do GTK."""
        self._rota_inflight = False
        from hefesto_dualsense4unix.app.audio_saida import acao_da_rota

        estado, regra = leitura
        self._canais_de_som = dict(getattr(estado, "canais", {}) or {})
        self._regra_do_sono = bool(regra)
        acao = acao_da_rota(estado)
        botao = self._get("btn_som_no_controle")
        if botao is not None and hasattr(botao, "set_sensitive"):
            botao.set_label(acao.rotulo)
            botao.set_sensitive(acao.sensivel)
            botao.set_tooltip_text(acao.dica)
        self._rota_acao = acao
        return False

    def _on_rota_falhou(self, _exc: Exception) -> bool:
        self._rota_inflight = False
        return False

    def _aplicar_rota_do_sistema(self, para_o_controle: bool) -> None:
        """Manda (ou devolve) o som do SISTEMA, a pedido do seletor do card."""
        rota = self._rota_de_som
        if rota is None:
            return
        sink = self._rota_sink
        if para_o_controle:
            if sink:
                self._run_blocking_seguro(
                    lambda: rota.mandar_para_o_controle(sink)
                )
        else:
            self._run_blocking_seguro(rota.voltar_ao_anterior)

    @staticmethod
    def _run_blocking_seguro(fn: Any) -> None:
        """Roda o `pactl` fora da thread do GTK, engolindo o que falhar."""
        with contextlib.suppress(Exception):
            fn()

    def _on_rota_de_som_clicada(self, _botao: Any = None) -> None:
        """O clique: troca a saída padrão do sistema, fora da thread do GTK."""
        acao = getattr(self, "_rota_acao", None)
        if acao is None or not acao.sensivel or not acao.alvo:
            return
        rota = self._rota_de_som
        if rota is None:
            return
        alvo = acao.alvo
        volta = acao.alvo != self._rota_sink

        def _trocar() -> bool:
            if volta:
                return bool(rota.voltar_ao_anterior())
            return bool(rota.mandar_para_o_controle(alvo))

        def _fim(_ok: Any) -> bool:
            self._refresh_rota_de_som()
            return False

        ipc_bridge.run_in_thread(_trocar, _fim)


    @staticmethod
    def _conectados_na_ordem_dos_cards(
        conectados: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """A mesa na ordem em que os cards nascem — a MESMA ordem da fita."""
        return StatusActionsMixin._por_numero_de_identidade(conectados)

    @staticmethod
    def _status_card_keys_for(
        conectados: list[dict[str, Any]],
    ) -> list[tuple[Any, ...]]:
        """Chaves estáveis dos cards: ``(index, uniq)`` por controle CONECTADO."""
        keys: list[tuple[Any, ...]] = []
        vistos: dict[tuple[Any, Any], int] = {}
        for pos, c in enumerate(
            StatusActionsMixin._conectados_na_ordem_dos_cards(conectados)
        ):
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
            return
        if getattr(self, "_status_cards", None) is None:
            self._status_cards = {}
            self._status_card_keys = []
        conectados = self._connected_controllers(state)
        keys = self._status_card_keys_for(conectados)
        if keys != self._status_card_keys:
            self._rebuild_status_cards(slot, keys)
        monitor = self._mic_monitor
        uniqs = tuple(
            str(c.get("uniq"))
            for c in conectados
            if isinstance(c.get("uniq"), str) and c.get("uniq")
        )
        if monitor is not None:
            monitor.set_controles(uniqs)
        self._rota_sink = self._sink_do_controle_para_a_rota(monitor, uniqs)
        for key, entry in zip(
            keys,
            StatusActionsMixin._conectados_na_ordem_dos_cards(conectados),
            strict=True,
        ):
            card = self._status_cards.get(key)
            if card is None:
                continue
            uniq = entry.get("uniq")
            tem_uniq = monitor is not None and isinstance(uniq, str) and bool(uniq)
            leitura = monitor.leitura(uniq) if tem_uniq else None
            card.update(entry, state, leitura)
            # `LeituraMic`: o nome do sink é fato da SAÍDA e sobrevive à
            pedir = getattr(card, "definir_pedido_de_rota", None)
            if pedir is not None:
                pedir(self._aplicar_rota_do_sistema)
            sink_do_card = monitor.sink_de(uniq) if tem_uniq else ""
            definir_sink = getattr(card, "definir_sink_de_saida", None)
            if definir_sink is not None:
                definir_sink(sink_do_card)
            # caso do rádio, em que o DualSense não publica placa de som.
            definir_canal = getattr(card, "definir_estado_do_canal", None)
            if definir_canal is not None:
                definir_canal(
                    self._canais_de_som.get(sink_do_card, "")
                    if sink_do_card
                    else "",
                    regra_instalada=self._regra_do_sono,
                )
            dono = getattr(card, "definir_dono_do_rascunho", None)
            if dono is not None:
                dono(self)

    def _rebuild_status_cards(
        self, slot: Any, keys: list[tuple[Any, ...]]
    ) -> None:
        """Recria os cards — o conjunto de controles mudou."""
        for child in list(slot.get_children()):
            slot.remove(child)
            child.destroy()
        self._status_cards = {}
        self._status_card_keys = list(keys)
        compact = len(keys) >= 2
        colunas = 1
        for pos, key in enumerate(keys):
            card = ControllerCard(
                compact=False, mostrar_estado_global=not compact
            )
            self._status_cards[key] = card
            card.set_hexpand(True)
            card.set_valign(Gtk.Align.START)
            slot.attach(card, pos % colunas, pos // colunas, 1, 1)
            card.show_all()
        self._alojar_botao_da_rota()
        self._set_frame_estado_visivel(compact or not keys)
        self._espelhar_estado_global_nos_cards()

    def _alojar_botao_da_rota(self) -> None:
        """Garante que o botão da rota de som tem pai — hoje, sempre o berço."""
        botao = self._get("btn_som_no_controle")
        if botao is None or not hasattr(botao, "get_parent"):
            return
        primeiro = (
            next(iter(self._status_cards.values()), None)
            if len(self._status_cards) == 1
            else None
        )
        destino = getattr(primeiro, "_speaker_rota_slot", None)
        if destino is None:
            self._devolver_botao_da_rota_ao_berco(botao)
            return
        pai = botao.get_parent()
        if pai is destino:
            return
        with contextlib.suppress(Exception):
            if pai is not None:
                pai.remove(botao)
            destino.pack_start(botao, True, True, 0)
            destino.show_all()

    def _devolver_botao_da_rota_ao_berco(self, botao: Any) -> None:
        """Recoloca o botão da rota no grid do frame Estado, se ele saiu."""
        berco = self._get("status_grid")
        if berco is None or not hasattr(berco, "attach"):
            return
        pai = botao.get_parent()
        if pai is berco:
            return
        with contextlib.suppress(Exception):
            if pai is not None:
                pai.remove(botao)
            berco.attach(
                botao, COLUNA_BERCO_DA_ROTA, 0, 1, ALTURA_BERCO_DA_ROTA
            )
            botao.show()

    def _clear_status_cards(self) -> None:
        """Remove todos os cards (daemon offline — nenhum controle conhecido)."""
        slot = self._get("status_players_slot")
        if slot is not None and hasattr(slot, "get_children"):
            for child in list(slot.get_children()):
                slot.remove(child)
                child.destroy()
        self._status_cards = {}
        self._status_card_keys = []
        self._set_frame_estado_visivel(True)


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
        """Cria o seletor de controle-alvo como BOTÕES segmentados no banner."""
        self._target_combo_rows = []
        self._target_combo_updating = False
        self._target_combo_visible = False
        self._target_combo_active = -1
        self._target_buttons = []
        # 8BIT-02: controles externos (não-DualSense) no seletor do topo + a
        self._external_buttons = []
        self._externals = []
        self._externals_fetch_ts = 0.0
        self._externals_inflight = False
        self._externals_sig = None
        # DESCONHECIDO e só vira alvo quando o `state_full` ou o clique dela
        esquecer_alvo(self, MOTIVO_SEM_ESTADO)
        self._target_uniq_by_index = {}
        self._target_label_by_index = {}
        self._edit_badge = None
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
        moldura_do_hover = Gtk.EventBox()
        with contextlib.suppress(Exception):
            moldura_do_hover.set_visible_window(False)
        moldura_do_hover.add(faixa)
        moldura_do_hover.show()
        header_bar.pack_end(moldura_do_hover, False, False, 0)
        self._target_strip = faixa
        self._target_strip_hover = moldura_do_hover
        self._montar_numero_selector(header_bar)
        badge = Gtk.Label()
        with contextlib.suppress(Exception):
            badge.get_style_context().add_class("dim-label")
        badge.set_no_show_all(True)
        badge.hide()
        header_bar.pack_end(badge, False, False, 6)
        self._edit_badge = badge
        rumble_badge = Gtk.Label()
        rumble_badge.set_use_markup(True)
        rumble_badge.set_no_show_all(True)
        rumble_badge.hide()
        header_bar.pack_end(rumble_badge, False, False, 6)
        self._rumble_badge = rumble_badge
        coop_badge = Gtk.Label()
        coop_badge.set_use_markup(True)
        coop_badge.set_no_show_all(True)
        coop_badge.hide()
        header_bar.pack_end(coop_badge, False, False, 6)
        self._coop_badge = coop_badge

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
            btn.set_mode(False)
            btn.set_tooltip_text(label)
            btn.connect("toggled", self._on_target_button_toggled, index)
            btn.show()
            box.pack_start(btn, False, False, 0)
            self._target_buttons.append(btn)
        self._external_buttons = []
        externals = getattr(self, "_externals", [])
        # Slot GLOBAL: continua a numeração dos DualSense. SELETOR-UNO-01: a
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

    def _maybe_fetch_externals(self) -> None:
        """Atualiza o inventário de externos (8BIT-01) com throttle (~4 s)."""
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

    def _set_target_strip_visible(self, visivel: bool) -> None:
        """Mostra/esconde a fita de chips (legenda inclusa) — PLAYER-01."""
        alvo = getattr(self, "_target_strip", None) or getattr(
            self, "_target_combo", None
        )
        if alvo is None:
            return
        if visivel:
            alvo.show()
        else:
            alvo.hide()


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
            btn.set_mode(False)
            btn.set_tooltip_text(
                f"Faz deste o controle número {numero}. "
                "Quem tem esse número hoje fica com o deste — "
                "os dois trocam, e mais ninguém se mexe."
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
        uniq = alvo_de_edicao(self).uniq
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
        alvo = alvo_de_edicao(self)
        if alvo.desconhecido:
            self._status_toast("numero", alvo.recusa() or "")
            return
        uniq = alvo.uniq
        if not uniq:
            self._status_toast(
                "numero",
                "Escolha um controle no cabeçalho antes de trocar o número",
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
                    or "Não consegui trocar o número — o Hefesto pode estar "
                    "desligado (ligue na aba Sistema)",
                )
            return False

        ipc_bridge.run_in_thread(
            lambda: ipc_bridge.identity_number_set(uniq, numero), on_success=_fim
        )


    @staticmethod
    def _edit_badge_text(label: str | None, *, com_endereco: bool = True) -> str:
        """Texto do badge de edição por-controle; vazio = badge escondido."""
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
        """Deriva o alvo de EDIÇÃO (uniq) do índice do seletor."""
        uniq: str | None = None
        label: str | None = None
        slot: int | None = None
        atual = alvo_de_edicao(self)
        if target_index is not None:
            slot = getattr(self, "_target_slot_by_index", {}).get(target_index)
        self._edit_target_slot = slot
        if target_index is not None:
            uniq = getattr(self, "_target_uniq_by_index", {}).get(target_index)
            label = getattr(self, "_target_label_by_index", {}).get(target_index)
            if uniq is None and label is None and atual.uniq is not None:
                logger.debug(
                    "edit_target_alvo_sumiu_do_estado_mantendo",
                    indice=target_index,
                )
                return
            if uniq is None and label is not None:
                logger.debug(
                    "edit_target_sem_mac_edita_global", indice=target_index
                )
        novo = definir_alvo(self, uniq, label)
        if novo == atual:
            return
        self._update_edit_badge()
        self._refresh_target_tabs()

    def _esquecer_edit_target(self, motivo: str) -> None:
        """Declara que a janela NÃO sabe qual é o alvo — e por quê (P3)."""
        if alvo_de_edicao(self).desconhecido:
            return
        esquecer_alvo(self, motivo)
        self._edit_target_slot = None
        self._update_edit_badge()
        self._refresh_target_tabs()

    def _update_edit_badge(self) -> None:
        """Mostra/esconde o badge conforme o alvo de edição atual."""
        badge = getattr(self, "_edit_badge", None)
        if badge is None:
            return
        alvo = alvo_de_edicao(self)
        texto = self._edit_badge_text(
            alvo.label,
            com_endereco=bool(alvo.uniq),
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

    def _sync_modo_nativo_manda_no_output(self, state: dict[str, Any]) -> None:
        """Publica ``_modo_nativo_ligado`` para as abas Gatilhos e Lightbar."""
        self._modo_nativo_ligado = bool(state.get("native_mode"))

    def _update_rumble_badge(self, state: dict[str, Any]) -> None:
        """Denuncia no banner que a vibração está travada.

        Só (0,0) — o silêncio deliberado — e valores fixos não-zero merecem
        aviso: nos dois o FF do jogo é ignorado. Em passthrough
        (`rumble_active is None`, o normal para jogar) o badge some.

        **A DICA MUDOU EM 06/09/2026 (VIBRACAO-O-QUE-SOBROU-01, linha 177 do
        CSV da paridade), e as DUAS metades dela estavam erradas:**

        * *"travada pela aba Rumble"* — não há aba com esse nome, e MEDIDO nos
          dois gestos da aba Vibração (`interface/pacotes/a05_vibracao`), essa
          aba **não consegue travar**: `testar` e `parar` os dois terminam em
          `rumble_passthrough(True)`. Quem trava é outra superfície, e afirmar
          a culpada manda caçar no lugar errado — então a frase deixou de
          afirmar quem travou;
        * *"aba Rumble → “Deixar o jogo controlar a vibração”"* — o botão de
          devolver saiu com a janela GTK e a interface nova nunca o teve. A
          frase agora vem inteira do dono
          (`rumble_actions.COMO_DEVOLVER_AO_JOGO`) e nomeia o "Parar" da aba
          Vibração, que é o botão que existe e que devolve a mão ao jogo.
        """
        badge = getattr(self, "_rumble_badge", None)
        if badge is None:
            return
        ativo = state.get("rumble_active")
        if not isinstance(ativo, (list, tuple)) or len(ativo) != 2:
            badge.hide()
            return
        if tuple(ativo) == (0, 0):
            texto = "Vibração em silêncio"
        else:
            texto = f"Vibração fixa em {ativo[0]}/{ativo[1]}"
        badge.set_markup(
            f'<span foreground="#ffb86c">{texto}</span>'
        )
        badge.set_tooltip_text(
            "A vibração está travada e o jogo não consegue mexer nela. Para "
            f"devolver ao jogo, {COMO_DEVOLVER_AO_JOGO}."
        )
        badge.show()

    def _update_coop_badge(self, state: dict[str, Any]) -> None:
        """Avisa no banner que o JOGO derrubou o co-op — e some quando ele volta."""
        badge = getattr(self, "_coop_badge", None)
        if badge is None:
            return
        texto = texto_do_coop_derrubado(state.get("coop"))
        if not texto:
            badge.hide()
            return
        badge.set_markup(f'<span foreground="#ff5555">{texto}</span>')
        badge.set_tooltip_text(tooltip_do_coop_derrubado(state.get("coop")))
        badge.show()

    def _refresh_target_tabs(self) -> None:
        """Re-popula as abas por-controle para exibir os valores do alvo novo."""
        for nome in (
            "_refresh_lightbar_from_draft",
            "_refresh_triggers_from_draft",
            "_refresh_rumble_from_draft",
        ):
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
        self._update_target_maps(conectados)
        target_index = state.get("output_target_index")
        if not isinstance(target_index, int) or isinstance(target_index, bool):
            target_index = None
        externals = getattr(self, "_externals", [])
        contagem = self._contagem_de_controles(state)
        total = contagem.na_mesa
        # PERFIL-05: numeração dos externos usa a contagem REAL de DualSense
        self._dualsense_count = contagem.adotados
        if total < 1:
            self._esquecer_edit_target(MOTIVO_MESA_VAZIA)
            self._refresh_numero_selector(0)
            if self._target_combo_visible:
                self._set_target_strip_visible(False)
                self._target_combo_visible = False
            return
        #   1. com um único DualSense com nó no kernel (o estado medido em
        editavel = contagem.adotados >= 1
        if editavel:
            if target_index is not None:
                self._sync_edit_target(target_index)
            if contagem.adotados == 1:
                # DualSense o seletor mostra só o botão do próprio controle,
                # por-controle desligada quando só um DualSense tinha nó no
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
            rows = []
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
        self._sync_edit_target(index)
        call_async(
            "controller.target.set",
            {"index": index},
            on_success=lambda _r: False,
            on_failure=lambda _e: False,
        )


    def _tick_live_state(self) -> bool:
        """Roda a 10 Hz: dispara RPC em thread worker; nunca bloqueia GTK."""
        # aba Status — com outra aba à vista, 10 Hz de state_full só saturam o
        notebook = self._get("main_notebook")
        if notebook is not None and id_da_pagina_corrente(notebook) != ABA_STATUS:
            return True
        if self._live_inflight:
            return True
        self._live_inflight = True
        call_async(
            "daemon.state_full",
            None,
            on_success=self._on_live_state_result,
            on_failure=self._on_live_state_failure,
        )
        return True

    def _on_live_state_result(self, state: Any) -> bool:
        """Callback de sucesso — executa na thread principal via GLib.idle_add."""
        self._live_inflight = False
        if isinstance(state, dict):
            self._first_poll_succeeded = True
            self._render_live_state(state)
        else:
            self._reset_live_widgets()
        return False

    def _on_live_state_failure(self, _exc: Exception) -> bool:
        """Callback de falha — executa na thread principal via GLib.idle_add."""
        self._live_inflight = False
        self._reset_live_widgets()
        return False

    def _tick_profile_state(self) -> bool:
        """Roda a 2 Hz: perfil ativo + metadata que muda devagar."""
        if self._profile_inflight:
            return True
        self._profile_inflight = True
        call_async(
            "daemon.state_full",
            None,
            on_success=self._on_profile_state_result,
            on_failure=self._on_profile_state_failure,
        )
        return True

    def _on_profile_state_result(self, state: Any) -> bool:
        """Callback de sucesso para o tick lento — executa na thread GTK."""
        self._profile_inflight = False
        if isinstance(state, dict):
            self._first_poll_succeeded = True
            self._profile_falhas_seguidas = 0
            self._render_slow_state(state)
        return False

    def _on_profile_state_failure(self, _exc: Exception) -> bool:
        """Callback de falha do tick lento — libera o guard e conta a falha."""
        self._profile_inflight = False
        self._profile_falhas_seguidas += 1
        if self._profile_falhas_seguidas >= FALHAS_ATE_ESVAZIAR_NO_JOGO:
            with contextlib.suppress(Exception):
                self._sync_paineis_no_jogo(None)
        return False

    def _tick_reconnect_state(self) -> bool:
        """Roda a 0.5 Hz: coordena a máquina de estado do header via thread worker."""
        with contextlib.suppress(Exception):
            self._refresh_rota_de_som()
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
        return False

    def _check_initial_poll_fallback(self) -> bool:
        """Pinta fallback acionável se 5 s passaram sem nenhum poll OK."""
        if self._first_poll_succeeded:
            return False
        header = self._get("header_connection")
        if header is not None:
            header.set_markup(
                '<span foreground="#ff5555">'
                "&#9675; Desconectado — abra a aba Sistema e clique em "
                "\"Reiniciar\""
                "</span>"
            )
        self._set_estado_global("status_daemon", "Sem resposta (ligue na aba Sistema)")
        self._set_label("status_connection", "—")
        self._set_label("status_transport", "—")
        self._set_estado_global("status_active_profile", "—")
        battery = self._get("status_battery_bar")
        if battery is not None:
            battery.set_fraction(0.0)
        self._set_battery_text("— %")
        self._reconnect_state = "offline"
        self._consecutive_failures = max(
            self._consecutive_failures, RECONNECT_FAIL_THRESHOLD
        )
        return False

    def _on_reconnect_state_failure(self, _exc: Exception) -> bool:
        self._reconnect_inflight = False
        self._update_reconnect_state(None)
        return False


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


    @staticmethod
    def _connected_controllers(state: dict[str, Any]) -> list[dict[str, Any]]:
        """Espelho de `app.mesa.controles_conectados` (ONDA0-Z5/T5).

        FEAT-DSX-MULTI-CONTROLLER-01. Mora aqui só para os leitores antigos
        que ainda chamam `self._connected_controllers(...)`; a lógica dona
        vive em `app/mesa.py`, sem GTK, para as outras dez abas usarem.
        """
        return mesa.controles_conectados(state)

    def _contagem_de_controles(self, state: dict[str, Any]) -> ContagemDeControles:
        """Espelho de `app.mesa.contagem_de_controles` (ONDA0-Z5/T5).

        Todo lugar que precisa responder "quantos controles" passa por aqui —
        cabeçalho, linha "Conectado", fita de chips, faixa de números, linha de
        bateria e a base da numeração dos externos.

        ``getattr`` defensivo em ``_externals``: hosts parciais de teste montam
        a mixin sem passar pelo ``_init_controller_target_combo`` (que semeia a
        lista), e este caminho roda a 2 Hz.
        """
        return mesa.contagem_de_controles(state, len(getattr(self, "_externals", [])))

    @staticmethod
    def _controllers_transports(conectados: list[dict[str, Any]]) -> str:
        """'BT + USB' (transportes em texto plano, primário primeiro)."""
        return " + ".join(
            (c.get("transport") or "?").upper() for c in conectados
        )

    def _render_online(self, state: dict[str, Any]) -> None:
        """Header canônico de estado ONLINE —  verde + transport."""
        header = self._get("header_connection")
        conectados = self._connected_controllers(state)
        # lado. O gate também passou a ser `na_mesa`: com 1 DualSense + 1
        contagem = self._contagem_de_controles(state)
        texto_contagem = texto_de_contagem(contagem)
        controllers_bloco = state.get("controllers")
        conhece_a_mesa = isinstance(controllers_bloco, list)
        if conhece_a_mesa:
            ha_alguem = bool(conectados)
            transport_do_primario = (
                conectados[0].get("transport") or "—" if conectados else "—"
            )
        else:
            ha_alguem = bool(state.get("connected"))
            transport_do_primario = state.get("transport") or "—"
        if header is not None:
            if ha_alguem and texto_contagem:
                partes = " + ".join(
                    f"<b>{(c.get('transport') or '?').upper()}</b>"
                    if c.get("is_primary")
                    else (c.get("transport") or "?").upper()
                    for c in conectados
                )
                corpo = f"{texto_contagem}: {partes}" if partes else texto_contagem
                header.set_markup(
                    f'<span foreground="#50fa7b">&#9679; {corpo}</span>'
                )
            elif ha_alguem:
                header.set_markup(
                    f'<span foreground="#50fa7b">&#9679; Conectado Via '
                    f"{transport_do_primario.upper()}</span>"
                )
            else:
                header.set_markup(
                    '<span foreground="#ff5555">&#9675; Controle Desconectado</span>'
                )
        self._set_estado_global("status_daemon", "Ligado")

    def _render_reconnecting(self) -> None:
        """Header intermediário — U+25D0 laranja + "tentando reconectar..."."""
        header = self._get("header_connection")
        if header is not None:
            header.set_markup(
                '<span foreground="#ffb86c">&#9680; Tentando Reconectar...</span>'
            )
        self._set_estado_global("status_daemon", "Reconectando")

    def _render_offline(self) -> None:
        """O banner do serviço fora do ar."""
        header = self._get("header_connection")
        if header is not None:
            header.set_markup(
                '<span foreground="#ff5555">'
                "&#9675; Hefesto desligado — abra a aba Sistema e clique em "
                "\"Reiniciar\""
                "</span>"
            )
        self._set_estado_global("status_daemon", "Desligado")
        self._set_label("status_connection", "—")
        self._set_label("status_transport", "—")
        self._set_estado_global("status_active_profile", "—")
        self._set_battery_row_visible(True)
        bar = self._get("status_battery_bar")
        if bar is not None:
            bar.set_fraction(0.0)
        self._set_battery_text("— %")
        self._clear_status_cards()
        combo = getattr(self, "_target_combo", None)
        if combo is not None:
            self._set_target_strip_visible(False)
            self._target_combo_visible = False
        self._refresh_numero_selector(0)
        self._esquecer_edit_target(MOTIVO_DAEMON_DESLIGADO)
        self._refresh_vpad_banner(None)
        self._refresh_wrapper_banner(None)
        self._refresh_banner_nao_adotado(None)
        self._sync_paineis_no_jogo(None)
        self._reset_live_widgets()

    @staticmethod
    def _popup_is_open() -> bool:
        """True se um popup (combo/menu) detém um grab GTK neste instante."""
        grab = getattr(Gtk, "grab_get_current", None)
        return grab is not None and grab() is not None

    def _render_live_state(self, state: dict[str, Any]) -> None:
        # ele detém um grab GTK. As atualizações a 10 Hz (os sticks do DualSense
        if self._popup_is_open():
            return
        # rápido só distribui `controllers[i]` do state_full para o card de
        self._sync_status_cards(state)

    def _render_slow_state(self, state: dict[str, Any]) -> None:
        self._sync_visibilidade_no_jogo(state)
        if self._popup_is_open():
            return
        self._maybe_fetch_externals()
        self._update_rumble_badge(state)
        self._update_coop_badge(state)
        self._sync_coop_governa_luzes(state)
        self._sync_modo_nativo_manda_no_output(state)
        active_profile = state.get("active_profile") or "Nenhum"

        conectados = self._connected_controllers(state)
        contagem = self._contagem_de_controles(state)
        texto_contagem = texto_de_contagem(contagem)
        controllers_bloco = state.get("controllers")
        conhece_a_mesa = isinstance(controllers_bloco, list)
        if conhece_a_mesa:
            connected = bool(conectados)
            transport = (
                conectados[0].get("transport") or "—" if conectados else "—"
            )
        else:
            connected = bool(state.get("connected"))
            transport = state.get("transport") or "—"
        # `connected and` de propósito: sem DualSense conectado, `adotados` é 0 e
        if connected and texto_contagem:
            self._set_label("status_connection", f"Conectado ({texto_contagem})")
            self._set_label("status_transport", self._controllers_transports(conectados))
        else:
            self._set_label(
                "status_connection", "Conectado" if connected else "Desconectado"
            )
            self._set_label(
                "status_transport", transport.upper() if transport != "—" else "—"
            )
        self._set_estado_global("status_active_profile", active_profile)
        self._set_estado_global("status_daemon", "Ligado")

        self._set_battery_row_visible(contagem.adotados <= 1)
        battery_bar = self._get("status_battery_bar")
        if battery_bar is not None and contagem.adotados <= 1:
            fracao, texto = self._bateria_da_mesa(state)
            battery_bar.set_fraction(fracao)
            self._set_battery_text(texto)

        self._refresh_controller_target_combo(state)

        # UX-03: banner de degradação do vpad (máscara DualSense em uinput).
        self._refresh_vpad_banner(state)

        self._refresh_wrapper_banner(state)

        self._refresh_banner_nao_adotado(state)

        self._sync_status_cards(state)

        self._sync_paineis_no_jogo(state)

    def _set_estado_global(self, widget_id: str, texto: str) -> None:
        """Escreve "Perfil ativo"/"Hefesto" nos DOIS lugares que os mostram."""
        self._set_label(widget_id, texto)
        self._ultimo_estado_global = {
            **self._ultimo_estado_global,
            widget_id: texto,
        }
        self._espelhar_estado_global_nos_cards()

    def _espelhar_estado_global_nos_cards(self) -> None:
        """Repassa o último par conhecido aos cards que existem AGORA."""
        perfil = self._ultimo_estado_global.get("status_active_profile", "")
        daemon = self._ultimo_estado_global.get("status_daemon", "")
        for card in getattr(self, "_status_cards", {}).values():
            definir = getattr(card, "definir_estado_global", None)
            if definir is not None:
                with contextlib.suppress(Exception):
                    definir(perfil, daemon)

    def _set_frame_estado_visivel(self, visivel: bool) -> None:
        """Mostra/esconde o frame "Estado" inteiro."""
        frame = self._get("frame_status_estado")
        if frame is None or not hasattr(frame, "set_visible"):
            return
        with contextlib.suppress(Exception):
            frame.set_visible(visivel)
            pai = frame.get_parent()
            if pai is not None and type(pai).__name__ == "CaixaDeTetoElastico":
                pai.set_visible(visivel)

    def _set_battery_row_visible(self, visible: bool) -> None:
        """Mostra/esconde a linha de bateria do frame Estado."""
        for widget_id in (
            "status_battery_caption",
            "status_battery_bar",
            "status_battery_pct",
        ):
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
        aviso = aviso_do_wrapper(state)
        if aviso:
            banner.set_text(aviso)
        banner.set_visible(bool(aviso))


    def _montar_banner_nao_adotado(self) -> None:
        """Cria o banner do controle que o sistema não entregou ao Hefesto."""
        caixa = self._get(ABA_STATUS)
        if caixa is None or not hasattr(caixa, "pack_start"):
            return
        banner = Gtk.Label()
        banner.set_line_wrap(True)
        banner.set_xalign(0.0)
        with contextlib.suppress(Exception):
            banner.get_style_context().add_class(
                "hefesto-dualsense4unix-status-warn"
            )
        banner.set_no_show_all(True)
        banner.hide()
        caixa.pack_start(banner, False, False, 0)
        with contextlib.suppress(Exception):
            caixa.reorder_child(banner, POSICAO_DO_BANNER_NAO_ADOTADO)
        self._banner_nao_adotado = banner

    def _refresh_banner_nao_adotado(self, state: dict[str, Any] | None) -> None:
        """Acende/apaga o aviso a partir do `controles_sem_driver` do daemon.

        Mesmo desenho dos banners do vpad e do wrapper: a decisão inteira mora
        na função pura (`texto_de_controle_nao_adotado`) e aqui só se pinta.
        `state=None` (daemon sem resposta) apaga — sem daemon não há varredura
        do sistema, e um aviso pendurado sobre um estado morto seria pior que
        o silêncio.
        """
        banner = getattr(self, "_banner_nao_adotado", None)
        if banner is None:
            return
        aviso = texto_de_controle_nao_adotado(state)
        if aviso:
            banner.set_text(aviso)
        banner.set_visible(bool(aviso))

    def _reset_live_widgets(self) -> None:
        """IPC sem resposta neste tick: os cards mostram "—"."""
        for card in getattr(self, "_status_cards", {}).values():
            card.reset_inputs()


__all__ = [
    "ABA_NO_JOGO",
    "ABA_STATUS",
    "ALL_BUTTONS",
    "GRID_BOTOES",
    "L2_R2_THRESHOLD",
    "MINUTOS_ENTRE_TENTATIVAS",
    "POSICAO_DO_BANNER_NAO_ADOTADO",
    "ContagemDeControles",
    "StatusActionsMixin",
    "texto_de_contagem",
    "texto_de_controle_nao_adotado",
    "texto_do_coop_derrubado",
    "tooltip_do_coop_derrubado",
]
