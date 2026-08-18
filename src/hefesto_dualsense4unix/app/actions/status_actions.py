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
from dataclasses import dataclass
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app import ipc_bridge
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
    id_da_pagina,
    id_da_pagina_corrente,
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

# GRID_BOTOES/ALL_BUTTONS/L2_R2_THRESHOLD moraram aqui até o STATUS-02;
# re-exportados (ver __all__) para os consumidores históricos da mixin.
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

#: Id do Glade da aba Status. Fonte única: `HefestoApp._ABA_STATUS` lê daqui, e
#: é por ele que o tick de 10 Hz pergunta se a aba está à vista — nunca pelo
#: número da página (EST-10).
ABA_STATUS = "tab_status_box"

#: Id do Glade da aba "No jogo" (ESCONDER-EM-VEZ-DE-SAIR, 09/08/2026).
#:
#: Mesma disciplina do `ABA_STATUS` logo acima, e pelo mesmo motivo medido: o
#: tique pergunta se ESTA aba está à vista pelo id do Glade, nunca pelo número
#: da página — inserir uma aba renumera todas, e um gate por índice passaria a
#: pintar a aba errada em silêncio (EST-10 / JANELA-FIEL-01).
ABA_NO_JOGO = "tab_no_jogo_box"

#: A coluna e a altura do botão da rota de som NO BERÇO (o `status_grid` do
#: frame Estado). Elas repetem o empacotamento do Glade porque a devolução
#: acontece em código — o botão sai do berço para o card e pode voltar, e
#: voltar para uma linha própria faria o grid ganhar altura que ele não tem
#: (é o que `test_o_botao_ocupa_o_vao_horizontal_que_ja_existia` reprova).
COLUNA_BERCO_DA_ROTA = 4
ALTURA_BERCO_DA_ROTA = 2


#: Número de exibição de um controle. A regra vive em `base.numero_do_controle`
#: para as telas não divergirem; o nome antigo segue como alias do módulo.
_display_slot = numero_do_controle


@dataclass(frozen=True)
class ContagemDeControles:
    """A contagem de controles da janela — os DOIS espaços, num só lugar.

    CONTAGEM-E-COOP-01 (29/07). A mesma tela dizia números diferentes para
    "quantos controles": o cabeçalho e a linha "Conectado (N controles)"
    contavam só os DualSense adotados, enquanto a fita de chips do topo e a
    faixa "Número deste controle" contavam adotados + externos. Com dois
    DualSense e dois externos vivos, o cabeçalho dizia "2 controles" ao lado
    de quatro chips e de uma faixa oferecendo os números 1 a 4.

    A resposta certa NÃO é somar tudo em um número só: os dois espaços são
    reais e cada um tem razão histórica registrada —

    - ``adotados`` — DualSense que o Hefesto governa (tem vpad, card, bateria,
      alvo de edição). É a base da numeração dos externos (``_dualsense_count``
      → `external_controllers.slot_of`) e o denominador dos cards
      (`_status_card_keys_for`, filtrado por ``connected``);
    - ``externos`` — Nintendo Pro, 8BitDo… que o daemon NUMERA mas não adota.
      Read-only POR DECISÃO DE PRODUTO (EXT-COUNT-01, 25/07: "numerar e acender
      o LED certo != adotar o controle"), então eles não têm card nem bateria —
      mas dividem o MESMO espaço de numeração dos adotados (R-24/NUM-01), e é
      por isso que a faixa de números tem de oferecer 1..``na_mesa``.

    Inflar ``adotados`` com os externos regrediria as duas coisas: os cards
    ganhariam entradas sem controle por trás e o rótulo dos externos deslizaria
    (o ponto cego do incidente de 14:42 citado em `slot_of`).

    A cura, então, é DERIVAR tudo daqui e NOMEAR cada número na tela — ver
    :func:`texto_de_contagem`.
    """

    adotados: int
    externos: int

    @property
    def na_mesa(self) -> int:
        """Quantos controles estão na mesa — o espaço de numeração (R-24/NUM-01)."""
        return self.adotados + self.externos


def texto_de_contagem(contagem: ContagemDeControles) -> str:
    """Frase NOMEADA da contagem, ou ``""`` quando não há plural a explicar.

    CONTAGEM-E-COOP-01: quem lê a tela precisa saber de QUAL número se trata.
    Três regimes:

    - ``na_mesa <= 1``: string vazia — não há contagem a exibir e quem chama
      segue pelo caminho single de sempre ("Conectado Via USB");
    - sem externos: ``"3 controles"`` — o texto de sempre, e aqui ele não
      mente: ``na_mesa == adotados``, nenhuma ambiguidade a desfazer (mantido
      idêntico também para não crescer a largura do cabeçalho no caso comum,
      lição dos 12px de folga da CI de 29/07);
    - com externos: ``"2 do Hefesto + 2 externos"`` — o número do cabeçalho
      passa a explicar por que a fita ao lado tem quatro chips.
    """
    adotados = contagem.adotados
    externos = contagem.externos
    if contagem.na_mesa <= 1:
        return ""
    if externos == 0:
        return _("{n} controles").format(n=adotados)
    parte_ext = (
        _("1 externo") if externos == 1 else _("{n} externos").format(n=externos)
    )
    if adotados == 0:
        # Defensivo: `state["connected"]` é do DualSense primário, então este
        # regime não deveria alcançar a tela — mas "0 do Hefesto" seria pior.
        return _("{ext} (nenhum do Hefesto)").format(ext=parte_ext)
    return _("{n} do Hefesto + {ext}").format(n=adotados, ext=parte_ext)


#: CONTROLE-QUE-NAO-ENTROU-01 (09/08/2026): de quantos em quantos minutos o
#: produto TENTA sozinho trazer de volta o controle que o sistema não adotou.
#: Não é número escolhido aqui: é o `OnUnitActiveSec` de
#: `assets/systemd/hefesto-bt-health-watchdog.timer`, a vigia que chama o
#: `bt_rebind_orphans.sh`. O texto da tela promete ESTE número, então ele tem
#: de sair do mesmo lugar que o cumpre — há teste que confere os dois.
MINUTOS_ENTRE_TENTATIVAS = 2

#: Posição do banner na caixa da aba Status: logo abaixo dos dois banners do
#: glade (`status_vpad_banner` = 0, `status_wrapper_banner` = 1) e acima do
#: frame "Estado". Ele não pôde nascer no glade como os outros dois — este
#: widget é montado em código —, e sem a reordenação `pack_start` o jogaria
#: para o fim da aba, abaixo dos cards, que é onde ninguém procura o motivo de
#: um controle estar faltando.
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
    """``"P2, P3 e P4"`` — quem saiu, por nome, a partir de P2.

    O P1 NUNCA entra: ele não é jogador do co-op (o vpad dele tem observável
    próprio, `steam_input.vpad_suspenso`), e o contador do daemon já conta só
    os SECUNDÁRIOS (`gamepad.steam_input_coop_derrubados`).
    """
    nomes = [f"P{n}" for n in range(2, 2 + max(0, quantos))]
    if len(nomes) <= 1:
        return "".join(nomes)
    return f"{', '.join(nomes[:-1])} e {nomes[-1]}"


def texto_do_coop_derrubado(bloco_coop: object) -> str:
    """Frase do banner quando o jogo derruba o co-op — ``""`` quando não há.

    CONTAGEM-E-COOP-01 (E1a). O daemon publica o fato desde 29/07
    (`ipc_handlers.py:1657-1662`: `coop.derrubado_por_steam_input` e
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
      chama `coop.sync(force=True)` (`gamepad.py:598-608`), e mesmo pelo
      caminho manual o ciclo normal recria os secundários porque `disable()`
      não desligou `coop_enabled`.

    Devolve ``""`` também quando o gatilho está aceso mas o número é zero: as
    duas mortes do contador (`gamepad.py:565-579` e `:1401-1411`) existem para
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
    """O preço por extenso, para o tooltip do badge — ``""`` sem queda.

    NOTA DATADA — 07/08/2026. Este tooltip abria com *"O jogo assumiu o
    controle: o Hefesto saiu da frente dele"*, e a segunda metade da frase
    está **refutada** pela medição dela de 06/08 (`CONTROLE-SONY-MEDIDO-01`,
    seção *A INVERSÃO*, grau MEDIDO): num jogo desta lista o Hefesto entrega
    a **entrada** e **mantém a saída** — os gatilhos dela seguraram e a cor
    dela ficou. Pior: quem lia "o jogo assumiu o controle" concluía que a luz
    e os gatilhos tinham virado do jogo, que é exatamente o que acontece
    **fora** da lista, não dentro. O que de fato cai aqui é o co-op, e cai
    porque os gamepads virtuais dos secundários são recolhidos
    (`gamepad.suspend_vpads_for_steam_input`) — a queda é da ENTRADA, e o
    texto agora nomeia isso.
    """
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
    #: MESA-CHEIA-09 (conserto 1.3): Modo Nativo ligado = o JOGO é dono do
    #: `hidraw` e o backend muta TODA escrita de output — o que a aba manda
    #: fica guardado até o modo sair. Lido do `state_full` aqui (mesmo tique do
    #: co-op) e consumido pelos toasts das abas Gatilhos e Lightbar, que não
    #: têm poller próprio.
    _modo_nativo_ligado: bool = False
    #: Badge do banner que denuncia rumble travado em silêncio.
    _rumble_badge: Any = None
    # S2: monitor do microfone (nível + mute). Lazy e DESLIGADO por padrão —
    # quem o liga é o gancho de troca de aba (`set_status_tab_visivel`). Ele
    # é o único sensor do card que não vem pelo IPC: capturar áudio é da
    # sessão gráfica, não do daemon.
    _mic_monitor: Any = None
    # CONTROLE-QUE-NAO-ENTROU-01: o banner do controle que está ligado e que o
    # sistema não conseguiu entregar ao Hefesto. Montado em CÓDIGO (ver
    # `_montar_banner_nao_adotado`), e não no glade como os dois banners
    # vizinhos — o `main.glade` é de outra frente nesta leva.
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
        # SOM-04: o botão da rota de som. Ligado por CÓDIGO e não por `signal`
        # do Glade, no molde do seletor de número: assim um Glade antigo (ou o
        # builder dublado de um teste de outra área) não derruba a montagem da
        # aba inteira por causa de um handler que não existe. Ele nasce
        # insensível no Glade e só ganha rótulo e sentido depois da primeira
        # leitura do `pactl`, que acontece fora da thread do GTK.
        botao_rota = self._get("btn_som_no_controle")
        if botao_rota is not None and hasattr(botao_rota, "connect"):
            botao_rota.connect("clicked", self._on_rota_de_som_clicada)
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
        # ESCONDER-EM-VEZ-DE-SAIR: a aba "No jogo" nasce aqui, junto com os
        # timers que ela usa. Ela NÃO ganha timer próprio — ver
        # `_sync_paineis_no_jogo`.
        self.install_no_jogo_tab()

    # ------------------------------------------------------------------
    # Aba "No jogo": o que atravessa para o jogo (ESCONDER-EM-VEZ-DE-SAIR)
    # ------------------------------------------------------------------

    #: Painéis da aba "No jogo", por chave de controle. `None` = a aba nunca
    #: foi montada (glade antigo, ou builder dublado de outra área de teste).
    _no_jogo_paineis: Any = None
    #: O conjunto de chaves com que os painéis de hoje foram construídos —
    #: mesmo mecanismo do `_status_card_keys`, e a MESMA função que o produz.
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
            # Glade antigo, ou builder dublado de teste de outra área: a aba
            # simplesmente não existe, e a janela abre igual. Mesma linha do
            # `_sync_status_cards` quando o slot não está lá.
            return
        self._no_jogo_paineis = {}
        self._no_jogo_keys = []

        miolo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        # A linha de contexto: em que modo e com que máscara a janela está
        # AGORA. Ela existe porque a pergunta que a aba fecha é sobre os três
        # modos — sem o modo escrito ao lado da resposta, a foto da tela não
        # diz de qual dos três ela é.
        self._no_jogo_contexto = Gtk.Label(label="")
        self._no_jogo_contexto.set_xalign(0.0)
        self._no_jogo_contexto.set_line_wrap(True)
        self._no_jogo_contexto.set_max_width_chars(100)
        self._no_jogo_contexto.set_halign(Gtk.Align.START)
        self._no_jogo_contexto.get_style_context().add_class(
            "hefesto-titulo-secao"
        )
        miolo.pack_start(self._no_jogo_contexto, False, False, 0)

        # O recado que vale para a JANELA inteira. A Conexão Nativa e o
        # "Controlar o PC" tiram o Hefesto da frente de TODOS os controles ao
        # mesmo tempo, e a explicação é uma só — repetida dentro de um painel
        # por controle ela saía duas vezes, palavra por palavra (medido na foto
        # de 10/08 com dois controles na mesa). Ele SUBSTITUI os painéis.
        self._no_jogo_recado = Gtk.Label(label="")
        self._no_jogo_recado.set_xalign(0.0)
        self._no_jogo_recado.set_line_wrap(True)
        self._no_jogo_recado.set_max_width_chars(84)
        self._no_jogo_recado.set_halign(Gtk.Align.START)
        self._no_jogo_recado.get_style_context().add_class("dim-label")
        self._no_jogo_recado.set_no_show_all(True)
        miolo.pack_start(self._no_jogo_recado, False, False, 0)

        # PERFIL-MUDO-01 (10/08/2026): o perfil que ela escreveu PARA este jogo
        # e que o jogo abriu sem. Fica ACIMA dos painéis e não os substitui: os
        # recursos continuam sendo a resposta da aba, e este é o aviso de que
        # eles estão respondendo com a configuração ERRADA. Sem ele, a aba
        # dizia "vibração: no jogo agora" com toda a razão — e com a vibração
        # do `fallback`, não a do perfil dela.
        #
        # Não é `dim-label`: o resto desta aba é observação, e isto é a única
        # linha que pede uma decisão dela. A cor sai por `set_markup` e não por
        # classe de CSS pela razão já MEDIDA nesta aba (ver `COR_DA_SITUACAO`):
        # a regra `.hefesto-dualsense4unix-window label` do tema tem
        # especificidade maior, e a classe é aplicada sem pintar nada.
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
        # `no_show_all`: quem decide se esta frase aparece é o tique, e um
        # `show_all()` de fora (a janela nasce com um) a traria de volta em
        # cima dos painéis — que foi exatamente o que a primeira foto mostrou.
        self._no_jogo_vazio.set_no_show_all(True)
        miolo.pack_start(self._no_jogo_vazio, False, False, 0)

        # EMPILHA-01 vale aqui também, e por antecipação: os painéis são baixos
        # (seis linhas) e empilhados eles leem como uma lista de controles. A
        # rolagem vertical desta página já existe (`_wrap_notebook_pages_in_scroll`).
        self._no_jogo_slot = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12
        )
        miolo.pack_start(self._no_jogo_slot, False, False, 0)

        pagina.pack_start(CaixaDeTetoElastico(miolo), True, True, 0)
        pagina.show_all()
        self._nascer_aba_no_jogo_escondida()

    # ------------------------------------------------------------------
    # ABA-DO-JOGO-01: a aba EXISTE só enquanto há jogo da Steam aberto
    # ------------------------------------------------------------------

    def _pagina_do_notebook(self, page_id: str) -> Any:
        """O filho DIRETO do notebook cuja página é ``page_id``. ``None`` = não há.

        Não é o mesmo widget que ``self._get(page_id)`` devolve, e a diferença é
        a que faz a aba aparecer ou não: `_wrap_notebook_pages_in_scroll` (em
        `app.py`, no `__init__`) embrulha oito das nove páginas num
        `GtkScrolledWindow`, e é o EMBRULHO que o notebook conhece. Esconder a
        caixa de dentro deixaria a aba na tira, clicável, abrindo uma página em
        branco — pior que o defeito.

        O desembrulho é o `id_da_pagina` de sempre (dono único, EST-10), então
        isto continua valendo se um dia o embrulho mudar de forma.
        """
        notebook = self._get("main_notebook")
        if notebook is None or not hasattr(notebook, "get_children"):
            return None
        for filho in notebook.get_children():
            if id_da_pagina(filho) == page_id:
                return filho
        return None

    def _nascer_aba_no_jogo_escondida(self) -> None:
        """A aba "No jogo" nasce FORA da tira, e é o tique que a traz.

        ABA-DO-JOGO-01, o pedido dela: *"essa aba no jogo só deveria aparecer
        quando efetivamente eu tivesse com um jogo steam aberto"*.

        A ordem das três chamadas é a cura, e cada uma tem um porquê:

        1. ``show_all()`` no embrulho — marca os filhos como visíveis AGORA,
           enquanto ainda dá; sem isto, o ``show()`` do dia em que o jogo abrir
           revelaria uma página com o miolo ainda escondido;
        2. ``set_no_show_all(True)`` — o ``window.show_all()`` de `app.show()`
           roda DEPOIS de toda montagem e traria a aba de volta, todo boot. É o
           mesmo trinco que o `_no_jogo_vazio` já usa três telas acima, e pela
           mesma razão medida;
        3. ``hide()`` — e só então ela some da tira.

        Nasce escondida, e não visível-até-a-primeira-resposta, porque o
        contrário é a aba PISCANDO em todo boot sem jogo: a tira abriria com ela
        e a perderia meio segundo depois, na primeira leitura de estado.
        """
        alvo = self._pagina_do_notebook(ABA_NO_JOGO)
        if alvo is None or not hasattr(alvo, "hide"):
            return
        with contextlib.suppress(Exception):
            alvo.show_all()
            alvo.set_no_show_all(True)
            alvo.hide()

    def _sync_visibilidade_no_jogo(self, state: dict[str, Any] | None) -> None:
        """Põe/tira a aba "No jogo" da tira conforme haja jogo da Steam aberto.

        ABA-DO-JOGO-01. Este é o gate de EXISTÊNCIA da aba, e ele não é o gate
        que já morava aqui: o de `_sync_paineis_no_jogo` decide se REPINTA (e só
        trabalha com a aba à vista, BUG-STATUS-TICK-HIDDEN-TAB-01). Confundir os
        dois foi exatamente o que deixou a aba na tira desde 09/08 — uma página
        fixa do Glade, montada sem condição nenhuma, com um gate de pintura que
        parecia responder por ela. Por isso este roda ANTES daquele, e nunca
        atrás dele: uma aba escondida jamais é a aba à vista, e o gate de pintura
        engoliria a chamada para sempre.

        ``None`` de `jogo_steam_aberto` não mexe em nada — nem mostra nem
        esconde. São os três casos em que ninguém sabe a resposta (daemon
        desligado, sonda ainda não feita, daemon mais velho que este código), e
        em todos eles a única coisa honesta é deixar a tela como está.

        **Quando ela está NA aba e o jogo fecha**, o foco vai para a Status antes
        de a página sumir. Não é zelo: medido no GTK3 desta casa, esconder a
        página corrente faz o notebook cair sozinho na página SEGUINTE — com o
        layout de hoje, "Gatilhos". Ela estaria lendo o que atravessa para o jogo
        e acordaria editando a curva do L2. A Status é o destino porque é a
        vizinha e a outra metade da mesma pergunta: aquela responde pelo controle
        FÍSICO, esta respondia pelo que atravessa para o JOGO.

        **E o "Controlar o PC"?** O recado dele (`TEXTO_DESKTOP`, via
        `recado_global`) continua nesta aba e continua alcançável — porque o
        único instante em que ele acrescenta alguma coisa é justamente com um
        jogo aberto: aí "o Hefesto não entrega controle nenhum ao jogo" explica
        um jogo que não responde ao controle, e a frase termina apontando o
        gesto que resolve. Com o jogo fechado a mesma frase é só a descrição de
        um modo que ela escolheu de propósito — e a tela que fala desse modo, com
        o comutador para sair dele, é a aba Início, que nunca esteve escondida.
        Nenhum conteúdo ficou sem casa.
        """
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
        # ABA-DO-JOGO-01: a EXISTÊNCIA da aba se decide aqui, uma linha ACIMA do
        # gate de pintura, e a ordem é a cura inteira — atrás dele esta chamada
        # nunca aconteceria com a aba escondida, e a aba escondida nunca voltaria.
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
        # PERFIL-MUDO-01: aparece nos TRÊS modos, inclusive junto do recado
        # global. O perfil que não entrou é fato do disco e da janela em foco —
        # não depende de haver gamepad virtual —, e calar sobre ele na Conexão
        # Nativa esconderia justamente o caso em que o perfil dela era quem
        # ligaria o modo certo.
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
        # A frase "Nenhum controle conectado." só faz sentido quando a resposta
        # SERIA por controle: no Nativo e no "Controlar o PC" o recado global já
        # explicou tudo, e dizer que não há controle ao lado dele seria falso —
        # há controle, ele é que não passa por aqui.
        self._no_jogo_vazio.set_visible(
            recado is None and isinstance(state, dict) and not conectados
        )
        for key, entry in zip(keys, conectados, strict=True):
            painel = self._no_jogo_paineis.get(key)
            if painel is not None and isinstance(state, dict):
                painel.atualizar(entry, state)

    def _rebuild_paineis_no_jogo(self, slot: Any, keys: list[Any]) -> None:
        """Recria os painéis — o conjunto de controles mudou.

        Mesma regra dos cards da aba Status: reconstrução SÓ quando o conjunto
        de chaves ``(index, uniq)`` muda, e a chave sai da MESMA função
        (`_status_card_keys_for`). Duas regras de identidade de controle na
        mesma janela divergiriam na primeira mudança do co-op.
        """
        for filho in list(slot.get_children()):
            slot.remove(filho)
            filho.destroy()
        self._no_jogo_paineis = {}
        self._no_jogo_keys = list(keys)
        for key in keys:
            # Sem `hexpand` e sem `halign` daqui: o teto de largura do painel é
            # dele (`LARGURA_PAINEL` + `halign=START`, no próprio widget), e
            # mandar `FILL` daqui o desfazia — a primeira foto saiu com uma
            # moldura de 1400px em volta de 430px de tinta.
            painel = PainelNoJogo()
            slot.pack_start(painel, False, False, 0)
            self._no_jogo_paineis[key] = painel
        slot.show_all()

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
    # SOM-04, entrega 2: mandar o som do sistema para o controle (e desfazer)
    # ------------------------------------------------------------------

    #: Objeto da rota, criado na primeira leitura. Ele não guarda estado de
    #: tela: o estado é lido do `pactl` a cada ciclo, e o único dado que
    #: sobrevive é o sink anterior, que mora no `gui_preferences.json`.
    _rota_de_som: Any = None
    #: Guarda de reentrância, no molde do `_reconnect_inflight`: as leituras
    #: são subprocessos e um ciclo não pode empilhar em cima do outro.
    _rota_inflight: bool = False
    #: Sink do controle resolvido pelo `mic_monitor` no último tique rápido.
    #: "" = não dá para saber, e é o que deixa o botão parado.
    _rota_sink: str = ""
    #: SOM-ACORDADO-01 — ``{nome do sink: acordado|dormindo}``, da última
    #: leitura da rota (0,5 Hz, thread worker). Vem de carona porque a leitura
    #: é a MESMA (`pactl list sinks short`): um leitor, um subprocesso, e o
    #: estado de todos os canais para todos os cards. É o que torna isto
    #: universal — 1 ou 7 controles custam a mesma leitura, e nada aqui depende
    #: de MAC, de ordem de conexão nem de número mágico.
    #:
    #: Dicionário VAZIO é "ainda não li", e é o que mantém os cards calados
    #: nos primeiros dois segundos em vez de afirmarem "acordado" por omissão.
    _canais_de_som: Mapping[str, str] = {}
    #: A regra do WirePlumber que impede o sono está instalada? Lida uma vez
    #: por ciclo, junto da rota, porque é um `os.path.isfile` — barato, mas
    #: ainda assim disco, e disco não vai na thread do GTK a 10 Hz.
    #: ``None`` = ninguém perguntou ainda.
    _regra_do_sono: bool | None = None
    #: CARD-ÚNICO-01 — o último "Perfil ativo"/"Hefesto" escrito, por id de
    #: widget. Ele existe para o card que NASCE depois da escrita receber o
    #: valor certo já na primeira pintura (ver
    #: `_espelhar_estado_global_nos_cards`).
    #:
    #: Ele é REATRIBUÍDO, nunca mutado no lugar: `self._d[k] = v` num
    #: atributo de CLASSE escreve no dicionário da classe, que é o mesmo
    #: objeto para toda instância — duas janelas (ou dois testes na mesma
    #: sessão) veriam o estado uma da outra. A reatribuição cria o de
    #: instância na primeira escrita, que é o comportamento pretendido.
    _ultimo_estado_global: dict[str, str] = {}  # noqa: RUF012

    def _set_battery_text(self, texto: str) -> None:
        """Escreve o número da bateria na barra E no rótulo ao lado dela.

        ESTADO-TRES-LINHAS-01. A barra deixou de desenhar o próprio texto
        (`show-text=False` no glade) quando passou a ocupar a largura toda:
        o GtkProgressBar centra o texto, e centrado numa barra de 1244px o
        "75 %" ficava a 609px de cada borda — o defeito que ela apontou nas
        barras de L2/R2, na mesma tela.

        O `set_text` da barra CONTINUA sendo chamado de propósito: ele é o que
        os testes e o `get_text()` leem, e é o dono do valor. Este método é o
        único lugar que espelha esse valor no rótulo visível — dois escritores
        derivariam, e esta casa já pagou por isso.
        """
        barra = self._get("status_battery_bar")
        if barra is not None:
            with contextlib.suppress(Exception):
                barra.set_text(texto)
        rotulo = self._get("status_battery_pct")
        if rotulo is not None:
            with contextlib.suppress(Exception):
                rotulo.set_text(texto)

    def _sink_do_controle_para_a_rota(self, monitor: Any, uniqs: tuple[str, ...]) -> str:
        """Sink que o botão da rota tem como alvo; "" quando não há certeza.

        Quem resolve "qual sink é de qual controle" é o ``mic_monitor``, que já
        é o leitor de PipeWire da janela — este método só ESCOLHE entre o que
        ele resolveu, e nunca vai ao sistema por conta própria.

        A conferência de que os nomes resolvidos são UM só é o coração do
        método, e desde 15/08/2026 ela é a única coisa que segura o botão:
        antes o ``escolher_sink`` devolvia "" para todo mundo assim que havia
        dois controles, e o botão morria por falta de resposta; agora ele
        responde certo por controle (casamento pelo dispositivo USB), e o que
        sobra é a pergunta que a janela não pode responder sozinha — **em qual
        dos controles ela quer ouvir**.

        Este botão é UM, no cabeçalho da aba, e o alvo dele é global. Com dois
        sinks distintos, escolher um seria a janela decidindo por ela; a
        resposta honesta continua sendo não escolher, e a dica do botão
        (``DICA_ROTA_SEM_SINK``) diz isso com todas as letras. Quem escolhe por
        controle é o seletor "Todo o som do PC" DENTRO do card, que já recebe
        o sink certo por :meth:`definir_sink_de_saida`.
        """
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
        """Relê a rota e repinta o botão — leitura FORA da thread do GTK.

        Roda a 0,5 Hz, de carona no tique de reconexão, e a carona é a
        entrega: o gate de timers desta mixin trava o número de
        ``GLib.timeout_add`` e o tique rápido é de 10 Hz — três `pactl` por
        ciclo a 10 Hz seriam trinta subprocessos por segundo para responder a
        uma pergunta que muda por gesto humano.
        """
        botao = self._get("btn_som_no_controle")
        if botao is None or not hasattr(botao, "set_sensitive"):
            return  # Glade antigo ou builder dublado: a aba segue sem o botão
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
            # SOM-ACORDADO-01: a regra do WirePlumber vai JUNTO, na mesma
            # worker. É um `os.path.isfile`, mas disco na thread do GTK a 10 Hz
            # é a mesma classe de defeito do subprocess — e aqui ele sai de
            # graça, de carona numa leitura que já existe.
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
        # SOM-ACORDADO-01: guardado aqui e ENTREGUE aos cards pelo tique de
        # 10 Hz (`_sync_status_cards`), que é o dono da fiação deles. Escrever
        # nos cards daqui seria um segundo caminho até o mesmo widget, e o
        # card pode nem existir quando esta leitura chega (a aba recria os
        # cards a cada troca do conjunto de controles).
        self._canais_de_som = dict(getattr(estado, "canais", {}) or {})
        self._regra_do_sono = bool(regra)
        acao = acao_da_rota(estado)
        botao = self._get("btn_som_no_controle")
        if botao is not None and hasattr(botao, "set_sensitive"):
            botao.set_label(acao.rotulo)
            botao.set_sensitive(acao.sensivel)
            botao.set_tooltip_text(acao.dica)
        self._rota_acao = acao
        return False  # contrato do GLib.idle_add

    def _on_rota_falhou(self, _exc: Exception) -> bool:
        self._rota_inflight = False
        return False

    def _aplicar_rota_do_sistema(self, para_o_controle: bool) -> None:
        """Manda (ou devolve) o som do SISTEMA, a pedido do seletor do card.

        SOM-CANAL-01/E3. É a lógica que era do botão "Ouvir no controle",
        agora chamada pelo estado "Todo o som do PC" do seletor.

        **O caso sem desfazer honesto continua tratado**, e é o que a sprint
        manda preservar: se o som já está no controle e não fomos NÓS que o
        pusemos lá, não há sink anterior guardado — e `voltar_ao_anterior`
        devolve False em vez de chutar um destino. O `acao_da_rota` continua
        sendo o dono dessa decisão.
        """
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
        """Roda o `pactl` fora da thread do GTK, engolindo o que falhar.

        O chamador já está numa thread de trabalho (`run_in_thread` do card),
        então aqui é só a guarda: um `pactl` que falhe não pode derrubar o
        clique dela.
        """
        with contextlib.suppress(Exception):
            fn()

    def _on_rota_de_som_clicada(self, _botao: Any = None) -> None:
        """O clique: troca a saída padrão do sistema, fora da thread do GTK.

        Nunca decide o alvo aqui — quem decide é ``acao_da_rota``, e um alvo
        vazio quer dizer que não há clique honesto a dar (mais de um controle,
        ou som já no controle sem memória de quem o pôs lá). O botão já está
        insensível nesses casos; esta guarda é a segunda tranca, para o dia em
        que alguém dispare o `clicked` por teclado ou por teste.
        """
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
            # Repinta na hora, sem esperar o tique de 2 s: o botão que acabou
            # de ser clicado tem de dizer o que faz AGORA.
            self._refresh_rota_de_som()
            return False

        ipc_bridge.run_in_thread(_trocar, _fim)

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

        CONTAGEM-E-COOP-01: ``len(keys)`` é, por construção, o
        ``ContagemDeControles.adotados`` — a mesma lista filtrada. Card de
        externo NÃO existe (EXT-COUNT-01: read-only por decisão de produto), e é
        por isso que os cards contam ``adotados`` e nunca ``na_mesa``.
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
        # SOM-04: o alvo do botão de rota sai daqui, e é só uma consulta a
        # dicionário — nada de subprocess a 10 Hz. Quem foi ao PipeWire foi o
        # `mic_monitor`, na cadência de 3 s dele.
        self._rota_sink = self._sink_do_controle_para_a_rota(monitor, uniqs)
        for key, entry in zip(keys, conectados, strict=True):
            card = self._status_cards.get(key)
            if card is None:
                continue
            uniq = entry.get("uniq")
            tem_uniq = monitor is not None and isinstance(uniq, str) and bool(uniq)
            leitura = monitor.leitura(uniq) if tem_uniq else None
            card.update(entry, state, leitura)
            # SOM-04, entrega 1: o sink de saída DESTE controle, para o som de
            # confirmação do bloco "Alto-falante" sair no alto-falante certo e
            # nunca no sink padrão (medido: `paplay --device=<inexistente>` sai
            # com zero e toca no PADRÃO — com o dela no HDMI, a confirmação
            # sairia pela televisão).
            #
            # Vai por método próprio, com guarda de existência, e não dentro da
            # `LeituraMic`: o nome do sink é fato da SAÍDA e sobrevive à
            # ausência de microfone — sem `parec` na máquina, ou por Bluetooth
            # sem a ponte de mic, não há captura nenhuma e o alto-falante
            # continua lá. A guarda existe porque a fiação do card é de outra
            # leva: enquanto ela não entrar isto é inerte, e no dia em que
            # entrar não é preciso tocar aqui.
            # SOM-CANAL-01: quem executa a camada 1 (o default sink) quando
            # ela troca o canal no seletor do card. O card pede; a aba faz —
            # a rota do sistema é um fato GLOBAL, e há um default sink só.
            pedir = getattr(card, "definir_pedido_de_rota", None)
            if pedir is not None:
                pedir(self._aplicar_rota_do_sistema)
            sink_do_card = monitor.sink_de(uniq) if tem_uniq else ""
            definir_sink = getattr(card, "definir_sink_de_saida", None)
            if definir_sink is not None:
                definir_sink(sink_do_card)
            # SOM-ACORDADO-01, a metade "ligar isso a interface" da decisão
            # dela. Consulta a DICIONÁRIO, como o alvo da rota logo acima:
            # quem foi ao PipeWire foi a leitura de 0,5 Hz, e a este tique de
            # 10 Hz só chega o resultado. Sem sink do card não há canal a
            # descrever, e "" é o que mantém o rótulo da moldura calado — é o
            # caso do rádio, em que o DualSense não publica placa de som.
            definir_canal = getattr(card, "definir_estado_do_canal", None)
            if definir_canal is not None:
                definir_canal(
                    self._canais_de_som.get(sink_do_card, "")
                    if sink_do_card
                    else "",
                    regra_instalada=self._regra_do_sono,
                )
            # SOM-02/E4: quem GUARDA o rascunho do perfil em edição. O bloco
            # "Alto-falante" registra nele o que ficou de pé DEPOIS de o daemon
            # confirmar — é isso que faz o "Salvar Perfil" persistir o volume
            # dela em vez do número velho.
            dono = getattr(card, "definir_dono_do_rascunho", None)
            if dono is not None:
                dono(self)

    def _rebuild_status_cards(
        self, slot: Any, keys: list[tuple[Any, ...]]
    ) -> None:
        """Recria os cards — o conjunto de controles mudou.

        STATUS-GRID-2COL-01: os cards vão para um GtkGrid em DUAS colunas, não
        mais empilhados. Empilhado, cada controle somava a própria altura e
        dois já estouravam a janela — a aba só respondia com rolagem. Lado a
        lado, dois controles ocupam a MESMA faixa vertical de um (e quatro
        viram 2x2, que é o teto real: 4 jogadores no co-op).
        """
        for child in list(slot.get_children()):
            slot.remove(child)
            child.destroy()
        self._status_cards = {}
        self._status_card_keys = list(keys)
        # 2+ cards → sticks de 90px (compact); card único mantém o layout
        # equivalente ao da aba antiga (sticks 120px).
        compact = len(keys) >= 2
        # EMPILHA-01 (02/08/2026) — decisão DELA, olhando a tela com dois
        # controles: *"os dois blocos não deveriam estar lado a lado mas um em
        # cima do outro de forma que o scroll surgisse pra comportar os
        # diferentes controles"*.
        #
        # Isto REVISA a STATUS-GRID-2COL-01, e a decisão antiga não é apagada:
        # ela dizia que "empilhado, cada card somava a própria altura e dois já
        # estouravam a janela — a aba só respondia com rolagem, justamente o
        # que as sprints S3/S5 tiraram das outras abas". A observação
        # continua correta; o que mudou foi o julgamento sobre ela, e é dela: a
        # rolagem vertical aqui é ACEITÁVEL, e ler dois controles lado a lado
        # não é. Um card por linha também é o que escala para os quatro
        # jogadores do co-op sem espremer nada.
        colunas = 1
        for pos, key in enumerate(keys):
            # EMPILHA-02: com UMA coluna, todo card recebe a largura inteira
            # — então nenhum deles desenha no tamanho compacto. O que continua
            # dependendo da quantidade é o par GLOBAL: com 2+ controles quem
            # responde por perfil e daemon é o frame "Estado", que volta à
            # tela, e repeti-lo em cada card seria a duplicação que a
            # STATUS-SIMETRIA-02 curou na bateria.
            card = ControllerCard(
                compact=False, mostrar_estado_global=not compact
            )
            self._status_cards[key] = card
            # `hexpand` + column-homogeneous do Glade: as colunas dividem a
            # largura em partes iguais em vez de a 1ª tomar tudo e a 2ª ficar
            # espremida (o card tem conteúdo de largura natural bem diferente
            # conforme os sensores presentes).
            card.set_hexpand(True)
            card.set_valign(Gtk.Align.START)
            slot.attach(card, pos % colunas, pos // colunas, 1, 1)
            card.show_all()
        self._alojar_botao_da_rota()
        # CARD-ÚNICO-01: quem manda no frame "Estado" é a existência de um
        # card ÚNICO. Com um controle só ele some inteiro (o card diz tudo o
        # que ele dizia); com nenhum, ou com 2+, ele volta — no primeiro caso
        # porque é a única voz da aba, no segundo porque perfil e daemon são
        # fatos globais e não cabem repetidos num card por controle.
        self._set_frame_estado_visivel(compact or not keys)
        self._espelhar_estado_global_nos_cards()

    def _alojar_botao_da_rota(self) -> None:
        """Muda o botão da rota de som para o bloco Alto-falante do 1º card.

        SOM-ROTA-NO-CARD-01, pedido dela em 01/08: *"aquele botão de voltar ao
        anterior sai de lá de cima e fica no espaço onde tem 'não ajustado' no
        alto-falante"*.

        O botão é o do GLADE, e continua sendo UM só. A segunda razão da
        SOM-04 para ele morar no frame Estado — a saída padrão do sistema é um
        fato do SISTEMA, e com dois cards haveria dois botões para um único
        interruptor global — continua inteira. Por isso ele é REPARENTADO para
        o card primário em vez de cada card ganhar o seu: com 2+ controles o
        sink sequer é resolvido (`_sink_do_controle_para_a_rota` devolve "" de
        propósito) e o botão nasce insensível, então um botão só, no primeiro
        card, é também o mais honesto.

        Idempotente: sai cedo se o botão já está no slot certo. Os cards são
        reconstruídos a cada troca de conjunto, e o `Gtk.Container.remove` do
        pai antigo é obrigatório — um widget com dois pais é erro de GTK, não
        de desenho.
        """
        botao = self._get("btn_som_no_controle")
        if botao is None or not hasattr(botao, "get_parent"):
            return  # Glade antigo ou builder dublado: a aba segue sem o botão
        # EMPILHA-02 — a pergunta dela, olhando a tela com dois controles:
        # *"o botão ouvir no controle faz sentido ali?"*.
        #
        # **Com 2+ controles, sim: o lugar dele é o frame "Estado".** A razão
        # é a mesma da SOM-04 e não mudou: a saída padrão do sistema é um fato
        # do SISTEMA, não daquele controle. Pôr o botão no card do Controle 1
        # sugere que ele manda o som para AQUELE controle — e o interruptor é
        # um só, global. O frame Estado é o lugar dos fatos globais da aba, e
        # é onde ele já estava no print dela.
        #
        # Com UM controle é o contrário, e é o que ela pediu na
        # SOM-ROTA-NO-CARD-01: não há ambiguidade possível, e o botão fica
        # onde a ação acontece.
        #
        # Antes da EMPILHA-02 isto funcionava por ACIDENTE — o card compacto
        # não tinha bloco de som, então o `destino` saía `None` com 2+
        # controles. Agora todo card tem o bloco, e a regra precisa ser dita.
        primeiro = (
            next(iter(self._status_cards.values()), None)
            if len(self._status_cards) == 1
            else None
        )
        destino = getattr(primeiro, "_speaker_rota_slot", None)
        if destino is None:
            # ROTA-ORFA-01 — sem destino, o botão VOLTA para o berço, e isto
            # não é zelo: medido em 01/08/2026 nesta árvore, com GTK 3.24 e o
            # glade real. Plugar um segundo controle recria os cards, e o
            # `child.destroy()` do card antigo deixava o botão ÓRFÃO
            # (`get_parent() is None`) — vivo, porque o Builder o referência,
            # mas fora da tela e sem casa. Ela perdia o "desfazer" da rota de
            # som exatamente no co-op, e só o recuperava despligando um
            # controle. O berço tem lugar para ele: é de onde ele saiu.
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
        """Recoloca o botão da rota no grid do frame Estado, se ele saiu.

        O berço é o `status_grid`, coluna 4 — o lugar que o glade lhe dá e o
        vão horizontal que ele já pagava. Idempotente: sai cedo se ele já
        está lá, e não faz nada se o grid não existe (builder dublado).
        """
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
        # Sem card nenhum, o frame Estado é a ÚNICA voz da aba — é ele que diz
        # que o daemon não responde, e é onde o botão da rota de som volta a
        # morar. Esconder aqui deixaria a aba Status em branco no exato
        # momento em que ela mais precisa explicar o que houve.
        self._set_frame_estado_visivel(True)

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
        # CONTAGEM-E-COOP-01 (E1a): o aviso de que o JOGO derrubou o co-op.
        # Mora no banner pela MESMA razão escrita acima para o badge de
        # vibração: quem está jogando não tem a aba Status aberta, e o co-op
        # some sem uma palavra. Aqui ele é visível de qualquer aba.
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

    def _sync_modo_nativo_manda_no_output(self, state: dict[str, Any]) -> None:
        """Publica ``_modo_nativo_ligado`` para as abas Gatilhos e Lightbar.

        MESA-CHEIA-09 (conserto 1.3). Em Modo Nativo o backend muta toda
        escrita de output (`_output_mute`) — a rota sysfs do LED é desabilitada,
        o `0x31` avulso é pulado e o `report_thread` não escreve nada. O ajuste
        fica GUARDADO e vale no desmute, e é isso que os toasts precisam dizer.

        Só guarda o flag: ao contrário do co-op, nenhuma moldura muda de
        desenho por causa dele, e repintar a aba a 0,5 Hz custaria sem motivo.
        """
        self._modo_nativo_ligado = bool(state.get("native_mode"))

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
            texto = "Vibração em silêncio"
        else:
            texto = f"Vibração fixa em {ativo[0]}/{ativo[1]}"
        badge.set_markup(
            f'<span foreground="#ffb86c">{texto}</span>'
        )
        badge.set_tooltip_text(
            "A vibração está travada pela aba Rumble e o jogo não consegue "
            "mexer nela. Para devolver ao jogo: aba Rumble → "
            f"“{BTN_GIVE_BACK_TO_GAME}”."
        )
        badge.show()

    def _update_coop_badge(self, state: dict[str, Any]) -> None:
        """Avisa no banner que o JOGO derrubou o co-op — e some quando ele volta.

        CONTAGEM-E-COOP-01 (E1a). O ramo que ESCONDE é tão obrigatório quanto o
        que mostra: as duas mortes do contador no daemon (`gamepad.py:565-579`
        e `:1401-1411`) existem para o aviso não sobreviver ao retorno dos
        jogadores, e um badge pendurado seria a mentira nova que elas evitam.
        """
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
        """Re-popula as abas por-controle para exibir os valores do alvo novo.

        POR-UNIDADE-01 (10/08/2026): a aba Rumble entra na lista. Ela passou a
        exibir a INTENSIDADE efetiva do alvo (``effective_rumble_for``), e sem
        este refresh a troca de peça no seletor deixaria a tela mostrando a
        intensidade da peça ANTERIOR — o mesmo defeito que a lista existe para
        evitar na Lightbar e nos Gatilhos.
        """
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
        # PERFIL-04: mantém os mapas index→uniq/rótulo e o alvo de edição em
        # sync com o daemon (cobre alvo trocado por CLI/applet e o boot).
        self._update_target_maps(conectados)
        target_index = state.get("output_target_index")
        if not isinstance(target_index, int) or isinstance(target_index, bool):
            target_index = None
        # getattr defensivo: Hosts de teste montam o seletor sem passar pelo
        # `_init_controller_target_combo` (que semeia `_externals`).
        externals = getattr(self, "_externals", [])
        # CONTAGEM-E-COOP-01: a conta vem da função única (era `len(conectados) +
        # len(externals)` inline aqui — o denominador que divergia do cabeçalho).
        contagem = self._contagem_de_controles(state)
        # SELETOR-UNO-01 (22/07, pedido da mantenedora): o seletor aparece com
        # 1+ controle NO TOTAL — mesmo sozinho, o controle ganha o botão com
        # número e via ("Sony 1 · BT"), no mesmo formato dos externos.
        total = contagem.na_mesa
        # PERFIL-05: numeração dos externos usa a contagem REAL de DualSense
        # (antes derivava de len(botões)-1, que assumia a linha "Todos").
        self._dualsense_count = contagem.adotados
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
        editavel = contagem.adotados >= 1
        if editavel:
            # Só sincroniza quando há um alvo derivado do estado; a ausência de
            # `target_index` não é ordem de ir para global.
            if target_index is not None:
                self._sync_edit_target(target_index)
            if contagem.adotados == 1:
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
        # aba Status — com outra aba à vista, 10 Hz de state_full só saturam o
        # worker compartilhado. O poller lento (2 Hz) segue vivo para
        # header/reconnect.
        notebook = self._get("main_notebook")
        if notebook is not None and id_da_pagina_corrente(notebook) != ABA_STATUS:
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
        # SOM-04 pega CARONA neste tique, e a carona é decisão registrada: o
        # gate de timers desta mixin (test_status_cards) trava o número de
        # `GLib.timeout_add`, e a rota de som muda por gesto humano — 0,5 Hz é
        # imperceptível e evita três `pactl` por ciclo a 10 Hz. Vem antes do
        # guard de inflight do reconnect de propósito: são leituras
        # independentes, e um IPC pendurado não pode congelar o botão de som.
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
        self._set_estado_global("status_daemon", "Sem resposta (ligue na aba Sistema)")
        self._set_label("status_connection", "—")
        self._set_label("status_transport", "—")
        self._set_estado_global("status_active_profile", "—")
        battery = self._get("status_battery_bar")
        if battery is not None:
            battery.set_fraction(0.0)
        self._set_battery_text("— %")
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

    def _contagem_de_controles(self, state: dict[str, Any]) -> ContagemDeControles:
        """A ÚNICA contagem de controles da janela (CONTAGEM-E-COOP-01).

        Todo lugar que precisa responder "quantos controles" passa por aqui —
        cabeçalho, linha "Conectado", fita de chips, faixa de números, linha de
        bateria e a base da numeração dos externos. Antes, cada um refazia a
        conta inline (``len(conectados)`` em quatro pontos, ``len(conectados) +
        len(externals)`` em um) e a mesma tela divergia.

        ``getattr`` defensivo em ``_externals``: hosts parciais de teste montam
        a mixin sem passar pelo ``_init_controller_target_combo`` (que semeia a
        lista), e este caminho roda a 2 Hz.
        """
        return ContagemDeControles(
            adotados=len(self._connected_controllers(state)),
            externos=len(getattr(self, "_externals", [])),
        )

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
        # CONTAGEM-E-COOP-01: a contagem do cabeçalho vem da MESMA função da
        # fita de chips e da faixa de números. Antes era `len(conectados)` —
        # que ignorava os externos e dizia "2 controles" com quatro chips ao
        # lado. O gate também passou a ser `na_mesa`: com 1 DualSense + 1
        # externo, o cabeçalho antigo caía no caminho single e não dizia uma
        # palavra sobre o segundo controle da mesa.
        contagem = self._contagem_de_controles(state)
        texto_contagem = texto_de_contagem(contagem)
        if header is not None:
            if connected and texto_contagem:
                # FEAT-DSX-MULTI-CONTROLLER-01: N controles — primário em negrito.
                # Os transportes são dos ADOTADOS (só deles o daemon sabe a via);
                # sem nenhum adotado, o corpo é só a contagem nomeada.
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
            elif connected:
                header.set_markup(
                    f'<span foreground="#50fa7b">&#9679; Conectado Via {transport.upper()}</span>'
                )
            else:
                header.set_markup(
                    '<span foreground="#ff5555">&#9675; Controle Desconectado</span>'
                )
        self._set_estado_global("status_daemon", "Ligado")

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
        self._set_estado_global("status_daemon", "Reconectando")

    def _render_offline(self) -> None:
        header = self._get("header_connection")
        if header is not None:
            header.set_markup(
                '<span foreground="#ff5555">'
                "&#9675; Hefesto desligado — abra a aba Sistema e clique em "
                "\"Ligar o Hefesto\""
                "</span>"
            )
        self._set_estado_global("status_daemon", "Desligado")
        self._set_label("status_connection", "—")
        self._set_label("status_transport", "—")
        self._set_estado_global("status_active_profile", "—")
        # STATUS-02: offline volta ao layout single — a linha de bateria do
        # frame Estado reaparece (os cards vão embora junto com o daemon).
        self._set_battery_row_visible(True)
        bar = self._get("status_battery_bar")
        if bar is not None:
            bar.set_fraction(0.0)
        self._set_battery_text("— %")
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
        # CONTROLE-QUE-NAO-ENTROU-01: sem daemon não há varredura do sistema —
        # o aviso apaga em vez de sobreviver a um estado morto.
        self._refresh_banner_nao_adotado(None)
        # ESCONDER-EM-VEZ-DE-SAIR: sem daemon não há o que atravessar para o
        # jogo, e o último estado bom não pode ficar na tela como se fosse de
        # agora — o `None` faz a aba dizer "O Hefesto está desligado." e
        # esvaziar os painéis.
        self._sync_paineis_no_jogo(None)
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
        self._update_rumble_badge(state)
        self._update_coop_badge(state)
        self._sync_coop_governa_luzes(state)
        self._sync_modo_nativo_manda_no_output(state)
        connected = bool(state.get("connected"))
        transport = state.get("transport") or "—"
        battery = state.get("battery_pct")
        active_profile = state.get("active_profile") or "Nenhum"

        conectados = self._connected_controllers(state)
        # CONTAGEM-E-COOP-01: mesma função, mesmo texto NOMEADO do cabeçalho —
        # as duas linhas da mesma tela não podem mais divergir.
        contagem = self._contagem_de_controles(state)
        texto_contagem = texto_de_contagem(contagem)
        # `connected and` de propósito: sem DualSense conectado, `adotados` é 0 e
        # o texto só existiria por causa dos externos — dizer "Conectado" ali
        # seria mentira (a linha é do controle do Hefesto).
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

        # STATUS-02: com 2+ controles cada card tem a PRÓPRIA bateria — a
        # linha do frame Estado (que só sabia falar do primário, com o
        # sufixo ambíguo "(Controle 1)" do UX-BATTERY-LABEL-01) some em vez
        # de duplicar/ambiguar a leitura.
        # CONTAGEM-E-COOP-01: `adotados`, NÃO `na_mesa` — externo não tem card
        # nem bateria lida pelo Hefesto (EXT-COUNT-01), então um externo na mesa
        # não pode fazer a linha de bateria do primário desaparecer.
        self._set_battery_row_visible(contagem.adotados <= 1)
        battery_bar = self._get("status_battery_bar")
        if battery_bar is not None and contagem.adotados <= 1:
            # UX-BATTERY-LABEL-01: o texto precisa estar VISÍVEL. Desde a
            # ESTADO-TRES-LINHAS-01 quem o mostra é o rótulo ao lado da barra,
            # e não a barra — ver `_set_battery_text`.
            if battery is None:
                battery_bar.set_fraction(0.0)
                self._set_battery_text("— %")
            else:
                battery_bar.set_fraction(battery / 100)
                self._set_battery_text(f"{battery} %")

        # FEAT-DSX-CONTROLLER-SELECTOR-01: atualiza o seletor de controle-alvo
        # (aparece só com 2+ controles).
        self._refresh_controller_target_combo(state)

        # UX-03: banner de degradação do vpad (máscara DualSense em uinput).
        self._refresh_vpad_banner(state)

        # GUI-05 item 3: banner "jogo sem wrapper" (honestidade do dedup).
        self._refresh_wrapper_banner(state)

        # CONTROLE-QUE-NAO-ENTROU-01: o controle ligado que o sistema não
        # conseguiu entregar ao Hefesto. Vai no tique LENTO de propósito: o
        # dado é uma varredura do sistema com TTL no daemon, e ele muda por
        # gesto humano (ligar/desligar controle), nunca a 10 Hz.
        self._refresh_banner_nao_adotado(state)

        # STATUS-02: o tick lento também mantém o CONJUNTO de cards em dia —
        # com a aba Status fora de foco o tick rápido pausa, e sem isto a
        # troca de aba mostraria cards do conjunto antigo por até 100 ms.
        self._sync_status_cards(state)

        # ESCONDER-EM-VEZ-DE-SAIR: a aba "No jogo" pega carona neste tique, e a
        # carona é a decisão — um timer próprio quebraria o gate de timers
        # desta mixin sem entregar nada, porque o dado que ela mostra muda em
        # segundos. Quem decide se há trabalho a fazer é o gate de aba à vista,
        # lá dentro.
        self._sync_paineis_no_jogo(state)

    def _set_estado_global(self, widget_id: str, texto: str) -> None:
        """Escreve "Perfil ativo"/"Hefesto" nos DOIS lugares que os mostram.

        CARD-ÚNICO-01. Desde esta leva o par tem duas casas, e elas nunca
        aparecem juntas: o card do controle único (onde ela pediu que ficasse)
        e o frame "Estado" do glade, que responde quando não há card único —
        com nenhum controle, e com 2+, em que perfil e daemon são fatos
        GLOBAIS e apareceriam repetidos num card por controle.

        O ponto de escrita é UM só de propósito. A alternativa — cada caminho
        (offline, reconectando, desligado, ligado) lembrar de escrever nos dois
        — é exatamente a forma como esta casa já produziu o defeito de *"a
        config que eu deixo nunca é respeitada"*: escritores sem dono.
        """
        self._set_label(widget_id, texto)
        self._ultimo_estado_global = {
            **self._ultimo_estado_global,
            widget_id: texto,
        }
        self._espelhar_estado_global_nos_cards()

    def _espelhar_estado_global_nos_cards(self) -> None:
        """Repassa o último par conhecido aos cards que existem AGORA.

        Chamado também logo depois de os cards nascerem, e é o que evita o
        card aparecer com "Nenhum / Consultando..." por um tique: o
        `_render_state` escreve o par ANTES de sincronizar os cards, então o
        card recém-criado perderia essa escrita e só a receberia no ciclo
        seguinte — 100 ms de texto errado a cada troca de controle.
        """
        perfil = self._ultimo_estado_global.get("status_active_profile", "")
        daemon = self._ultimo_estado_global.get("status_daemon", "")
        # `getattr` e não `self._status_cards`: os cards nascem no primeiro
        # `_sync_status_cards`, e há caminhos que escrevem o par ANTES disso —
        # o de reconexão é o principal, e ele roda em janelas dubladas que
        # nunca montam card nenhum.
        for card in getattr(self, "_status_cards", {}).values():
            definir = getattr(card, "definir_estado_global", None)
            if definir is not None:
                with contextlib.suppress(Exception):
                    definir(perfil, daemon)

    def _set_frame_estado_visivel(self, visivel: bool) -> None:
        """Mostra/esconde o frame "Estado" inteiro.

        CARD-ÚNICO-01, pedido dela: *"apaga estado"*. Ele não foi apagado do
        glade, e a razão é medida: sem controle nenhum não existe card, e a
        aba Status ficaria MUDA — sem dizer que o daemon está parado nem
        oferecer o botão da rota de som. O frame virou o que ele sempre foi na
        prática, e agora só isso: o fallback.

        Quem some junto é a `CaixaDeTetoElastico` que o `app.py` põe em volta
        dele na montagem — esconder só o frame deixaria a caixa ocupando a
        altura do espaçamento da aba, e ela veria o vão sem enxergar a causa.
        """
        frame = self._get("frame_status_estado")
        if frame is None or not hasattr(frame, "set_visible"):
            return
        with contextlib.suppress(Exception):
            frame.set_visible(visivel)
            pai = frame.get_parent()
            if pai is not None and type(pai).__name__ == "CaixaDeTetoElastico":
                pai.set_visible(visivel)

    def _set_battery_row_visible(self, visible: bool) -> None:
        """Mostra/esconde a linha de bateria do frame Estado.

        São TRÊS widgets desde a ESTADO-TRES-LINHAS-01 — o rótulo "Bateria:",
        a barra e o número ao lado dela. Esquecer o terceiro deixaria um
        "75 %" órfão na tela com dois controles, que é justamente o caso em
        que a linha some (cada card tem a própria bateria).
        """
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
        aviso = wrapper_banner_text(state)
        if aviso:
            banner.set_text(aviso)
        banner.set_visible(bool(aviso))

    # ------------------------------------------------------------------
    # CONTROLE-QUE-NAO-ENTROU-01: o controle ligado que não chegou até aqui
    # ------------------------------------------------------------------

    def _montar_banner_nao_adotado(self) -> None:
        """Cria o banner do controle que o sistema não entregou ao Hefesto.

        Nasce em CÓDIGO, e não no `main.glade` como os dois banners vizinhos.
        Isso muda uma coisa e só uma: ele precisa ser REORDENADO depois do
        `pack_start`, porque a caixa da aba é vertical e o padrão empurraria o
        aviso para o fim — abaixo dos cards, que é o lugar em que ninguém
        procura o motivo de um controle estar faltando.

        Nasce escondido e com `no_show_all`, igual aos vizinhos: sem isso, um
        `show_all` da aba acenderia o aviso com a tela em ordem, que é
        exatamente a mentira nova que este banner existe para não criar.

        MEDIDO nesta bancada em 09/08, com a janela em 1920 e os dois banners
        acesos lado a lado: este e o `status_vpad_banner` do glade saem em
        ``x=13`` e ``width=1894``, com a mesma classe de estilo e a mesma cor
        resolvida. É de propósito que não se corrige a largura aqui: os três
        banners da aba são um padrão só, e um deles estreito (com a
        `CaixaDeTetoElastico` do card, por exemplo) daria à aba duas larguras
        de aviso em vez de uma. Se um dia esse teto valer, vale para os três,
        e o lugar é o glade — que não é desta leva.

        No-op silencioso quando não há caixa (builder dublado de teste de
        outra área, ou glade antigo): a aba abre sem o banner, como abria
        ontem.
        """
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
        """IPC sem resposta neste tick: os cards mostram "—".

        Contrato do STATUS-02: NUNCA exibir o último valor de inputs como se
        estivesse vivo — cada card troca a área de inputs pelo "—" (sem
        leitor) e invalida os caches de diff, para o próximo tick bom
        repintar tudo.
        """
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
