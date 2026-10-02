"""O que sobrou da aba Status da janela GTK: leituras do ``state_full``.

A janela, os cards e a máquina de reconexão saíram em 02/10/2026
(A-DIETA-DO-CODIGO-01). Ficam as leituras que a interface reusa:
:func:`texto_de_controle_nao_adotado` e os ``staticmethod`` de
:class:`StatusActionsMixin` (``_por_numero_de_identidade``,
``_connected_controllers``, ``_bateria_da_mesa``).
"""
# ruff: noqa: E402
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app import mesa
from hefesto_dualsense4unix.app.actions.base import (
    WidgetAccessMixin,
)
from hefesto_dualsense4unix.app.alvo_de_edicao import (
    AlvoDeEdicao,
)

# GRID_BOTOES/ALL_BUTTONS/L2_R2_THRESHOLD moraram aqui até o STATUS-02;
from hefesto_dualsense4unix.interface.cartao_do_controle import (
    ALL_BUTTONS,
    GRID_BOTOES,
    L2_R2_THRESHOLD,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


MINUTOS_ENTRE_TENTATIVAS = 2


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


    _no_jogo_paineis: Any = None
    _no_jogo_keys: Any = None
    _no_jogo_slot: Any = None
    _no_jogo_contexto: Any = None
    _no_jogo_recado: Any = None
    _no_jogo_perfil: Any = None
    _no_jogo_vazio: Any = None


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
    def _connected_controllers(state: dict[str, Any]) -> list[dict[str, Any]]:
        """Espelho de `app.mesa.controles_conectados` (ONDA0-Z5/T5).

        FEAT-DSX-MULTI-CONTROLLER-01. Mora aqui só para os leitores antigos
        que ainda chamam `self._connected_controllers(...)`; a lógica dona
        vive em `app/mesa.py`, sem GTK, para as outras dez abas usarem.
        """
        return mesa.controles_conectados(state)


__all__ = [
    "ALL_BUTTONS",
    "GRID_BOTOES",
    "L2_R2_THRESHOLD",
    "MINUTOS_ENTRE_TENTATIVAS",
    "StatusActionsMixin",
    "texto_de_controle_nao_adotado",
]
