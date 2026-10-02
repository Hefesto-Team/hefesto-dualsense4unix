"""Subsystem: o nó de som de CADA DualSense — e ele não sabe o que é transporte.

SOM-QUE-SAI-01. Embrulha :mod:`integrations.alto_falante_bt` no contrato
``Subsystem`` do daemon (``start``/``stop``/``is_enabled``). É fino de
propósito: toda a lógica de PipeWire, Opus e protocolo mora no módulo de
integração, que roda igual pelo CLI, pela interface ou por aqui. Espelho de
``daemon/subsystems/bt_mic.py``, a metade de ENTRADA, que **não é tocada**.

O DEFEITO QUE ELE EXISTE PARA MATAR
------------------------------------
A placa ALSA do DualSense é do **TRANSPORTE**, não da unidade — medido por
INVERSÃO em 15/08/2026, com os quatro aparelhos trocados de braço: quem foi
para o fio ganhou placa, quem foi para o ar perdeu. A consequência para quem
joga é a que esta sprint ataca: **ela tira o cabo no meio da partida e o
dispositivo de saída que o jogo escolheu desaparece do sistema.** Não é o som
que fica ruim — é a rota que some debaixo do jogo.

Depois deste subsystem, o jogo aponta para **um nó que não sai do lugar**: o
nome vem do ``uniq`` do controle (``hefesto_som_<hex6>``), e o cabo, o rádio e
o "não tem para onde ir" acontecem por baixo dele. É o mesmo contrato do
gamepad virtual, que é o precedente que ela citou: *o jogo escolhe um
dispositivo, não um transporte* (``integrations/virtual_pad.py``).

AS TRÊS DECISÕES DELA, E ELAS SÃO CURTAS
-----------------------------------------
``D-0609-O-NO-DE-SOM-VIVE-COM-O-CONTROLE`` (06/09/2026, por delegação,
reversível numa frase — ``docs/data/decisoes-dela.csv:213``):

1. **REVERTIDA POR ELA EM 08/09/2026.** Dizia *"o nó vive só enquanto há
   controle"* — decisão por DELEGAÇÃO, e declarada reversível numa frase. Ela
   reverteu com todas as letras em `D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-
   SEMPRE` (*"concordo com as 5"*): **nó que some quebra o jogo que o
   escolheu.** O que vai e volta é a ROTA, e o nó fica;
2. **no cabo ele não vira saída padrão.** ``priority.session`` baixa
   (``integrations.alto_falante_bt.PRIORIDADE_SESSAO_DO_SOM``). Publicar o nó
   é uma coisa; mandar o som do sistema para ele é outra, e a segunda é dela;
3. **a escolha entre ``0x32`` e ``0x39`` caiu em 10/09/2026**: o som saiu pelo
   ``0x35`` (a orelha dela, 70 s), e é esse degrau que a ``PonteDeSomPorRadio``
   que este subsystem sobe por controle no rádio escreve (``ARRANJO_035``).

O QUE ELE NÃO FAZ, E É METADE DO VALOR DE LER ISTO
---------------------------------------------------
* **não escreve no aparelho do cabo.** No cabo o som é da placa USB do
  próprio controle; no rádio, :meth:`AltoFalanteSubsystem._casar_as_pontes`
  sobe uma ``PonteDeSomPorRadio`` por controle, e é ela que escreve o
  ``0x35`` no hidraw. A régua que fica é a da
  **FALÁCIA DO CANAL QUE RESPONDE** — concluir que, porque um canal
  responde, ele FAZ o que se esperava dele: o mapa segura o degrau em
  ``MONTOU`` até a orelha dela ouvir o caminho inteiro do produto
  (``audio.saida_dedicada@dualsense``, AS-FRASES-QUE-A-BANCADA-ACHOU-01);
* **PASSOU A LIGAR — 09/09/2026, SOM-POR-CONTROLE-01.** Esta linha dizia *"não
  liga o monitor ao sink USB do controle no cabo"*, e era verdade: o
  ``module-loopback`` e o casamento por dispositivo USB estavam fora da posse
  daquela sprint. Estão dentro desta. Quem resolve a rota é
  ``integrations.alto_falante_bt.rota_do_no`` — uma pergunta, um dono;
* **não escolhe o número do rótulo.** O «Controle N» de «Alto-falante do
  Controle N» é a conta DA CASA, e este subsystem só a alcança — ver
  :meth:`AltoFalanteSubsystem.numero_do_assento` e
  ``daemon/subsystems/base.numero_do_assento_na_mesa``.

UM DONO DO CICLO DE VIDA — 28/09/2026 (O-ALTO-FALANTE-TEM-UM-CAMINHO-SO-01)
--------------------------------------------------------------------------
O nó de som de cada controle, no cabo e no rádio, de um a quatro, nasce e
morre AQUI (:class:`GerenciadorDeNosDeSom`), por
:class:`~integrations.alto_falante_bt.SinkVirtualPipeWire`. O segundo
publicador que existia — o plano da janela em ``app/audio_saida``
(``plano_de_publicacao``, ``argv_para_publicar_o_no``) — nunca foi executado
por ninguém e saiu; as invariantes dele são cobradas deste gerenciador em
``tests/unit/test_o_alto_falante_virtual_esconde_o_transporte.py``, contra um
servidor de som de mentira.

O ÓRFÃO GANHOU A ROTA, E DEPOIS GANHOU AS TRÊS LINHAS DO REGISTRO
------------------------------------------------------------------
**As duas razões de 07/09 para não o ligar caíram em 09/09**, e as duas eram
razões de verdade:

* *"sem o ``module-loopback``, o nó publicado é um sumidouro"* — agora
  :class:`~integrations.alto_falante_bt.SinkVirtualPipeWire` sobe o loopback
  junto, e a pergunta *"onde este nó entrega?"* passou a ter **um** dono
  (``integrations.alto_falante_bt.rota_do_no``). Eram duas respostas
  escritas; ficou uma;
* *"os quatro nascem com o MESMO rótulo"* — agora cada um nasce «Alto-falante
  do Controle N», com o número do ASSENTO, pelo mesmo gancho do «Microfone do
  Controle N» (decisão dela de 09/09, *"4a"*).

**ELE DEIXOU DE SER ÓRFÃO EM 10/09/2026 — SOM-FIADO-01.** As três linhas do
registro existem, e são as três que a receita exige:
``daemon/subsystems/__init__.py`` (a lista), ``daemon/lifecycle.py``
(o ``_safe_start("alto_falante", …)`` no ``run()``) e ``daemon/connection.py``
(o ``_stop_alto_falante`` no ``shutdown()``). Fazer só duas é a armadilha que o
``subsystems/__init__.py`` nomeia: sobe o subsystem e nunca o para, e o nó fica
na lista de saída dela **depois de o daemon morrer**.

**E EM 12/09/2026 O DAEMON PASSOU A ENTRAR PELO CONSTRUTOR** (TRES-CONTAS-PARA-
UM-NUMERO-01): é por ele que o «Controle N» do rótulo chega ao mesmo número do
cartão dela, perguntando o ``player_slot`` ao ``identity_registry``.

A régua que trava o par continua sendo
``tests/unit/test_o_no_de_som_nao_nasce_sumidouro.py`` — e ela sempre permitiu
esta cura: *"ela NÃO proíbe ligar o subsystem; ela trava o PAR — se ele subir,
o nó tem de ter rota"*.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.daemon.ganho_da_haptica import GANHO, placas_do_piso
from hefesto_dualsense4unix.daemon.subsystems.base import numero_do_assento_na_mesa
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)


def _mesmo_controle(a: object, b: object) -> bool:
    """Os dois endereços são o mesmo controle, pelos dígitos (``norm_mac``, o dono da chave)."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    if not a or not b:
        return False
    return (norm_mac(str(a)) or str(a).lower()) == (norm_mac(str(b)) or str(b).lower())


#: Cadência da varredura de hotplug (sysfs). Não é polling de áudio: é só
#: *"apareceu/sumiu controle?"*. O mesmo número da metade de entrada.
RECONCILIA_S = 5.0

#: O QUE ACORDA A VOLTA ANTES DO RELÓGIO — A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-
#: DO-JOGO-01, 28/09/2026: o retrato do som mudando nas saídas ou nos fluxos
#: (o jogo abriu ou fechou um fluxo), e o aviso de quem precisa da volta agora
#: (o controle que entra na partida, a resposta dela ao «Ligar aqui»).
#:
#: FATO SUBSTITUÍDO: aqui morava o VIGIA DO MODO (HAPTICA-RADIO-INICIO-01,
#: 19/09), que a cada 0,4 s adivinhava o modo de cada controle e acordava a
#: volta quando o palpite divergia da ponte. O palpite não sabia quando a
#: ponte NÃO PODIA virar o modo dele (sem fonte, sem vaga), e acordava a volta
#: a cada fatia, para sempre — daí a espera da tentativa que falhou, de 26/09,
#: que era um remendo em cima do laço. A volta agora acorda quando o que ELA
#: leu mudou (:meth:`AltoFalanteSubsystem._a_mesa_do_som_mudou`), e uma
#: tentativa que falha espera a mudança seguinte, ou o relógio.
_O_QUE_A_VOLTA_OUVE: tuple[str, ...] = ("sinks", "sink-inputs")

#: Quanto tempo a ponte que NÃO SUBIU segura a rota daquele controle —
#: RADIO-AFOGADO-01, 22/09/2026.
#:
#: Com a ponte nascendo sob demanda, «a ponte não está de pé» virou o estado de
#: REPOUSO, e não uma falha: dizer que não há rota por causa dele foi o que
#: prendeu o nó de som num laço — sem nó não há o que tocar, sem alguém tocando
#: a ponte não sobe, e sem ponte o nó não nascia.
#:
#: O que continua sendo falha é o `subir()` que FALHOU, com o som dela na mão.
#: Esse fica lembrado, e o nó some com a frase honesta. **Mas com prazo:** uma
#: falha passageira (o broker ocupado por um instante) calaria o alto-falante
#: daquele controle até ela reconectá-lo, porque sem nó ela não tem como
#: pedir de novo.
RECUSA_DA_PONTE_S = 60.0

#: O PAR DO BOTÃO «Háptica» da aba Vibração —
#: A-ABA-VIBRACAO-TEM-O-SENSOR-HAPTICO-E-DOIS-TESTES-01, 02/10/2026. Um pouco
#: abaixo da meia escala: a amplitude do tocador é ``nível / 255``
#: (``endpoint_de_haptica.bloco_da_haptica``), e o ganho da linha «Sensor
#: Háptico» multiplica depois (a placa no cabo, a bomba no rádio). 127 dá
#: 0,498, e no teto do ganho (``HAPTICA_PCT_MAX``, 200%) dá 0,996, sem cortar;
#: 128 já passaria de 1,0.
PAR_DO_TESTE_DA_HAPTICA: tuple[int, int] = (127, 127)

#: Os doze dígitos hex de um MAC. Um ``uniq`` que não os tenha não é endereço,
#: e `norm_mac` só FILTRA hex — sem esta trava, `"a"` viraria uma chave válida
#: e casaria com qualquer coisa. Mesma régua da metade de entrada.
_UNIQ_HEX = 12

#: O transporte suposto quando quem chamou não disse qual é. É o CABO porque é
#: o único onde há rota hoje, e supor rádio faria o nó recusar antes de tentar.
TRANSPORTE_CABO = "usb"


@dataclass(frozen=True)
class ControleNaLista:
    """Um DualSense visto pelo sysfs, com o transporte AO LADO e nunca DENTRO.

    O ``transporte`` existe para o diagnóstico e para o relatório — **nunca
    para o nome do nó**. Se algum dia ele entrar na identidade, o defeito que
    este subsystem existe para matar volta com outra roupa.
    """

    uniq: str
    caminho: str
    transporte: str


class GerenciadorDeNosDeSom:
    """Sobe/derruba um :class:`SinkVirtualPipeWire` por controle na lista.

    ``reconciliar()`` é idempotente e barato: um controle que sai da lista tem
    o nó derrubado, e os outros ficam de pé.

    **O CICLO DE VIDA É O DE 08/09/2026, e é dela.** Este texto dizia *"é ele
    que faz o «vive só enquanto há controle»"* — a decisão de 06/09, por
    delegação. Ela a reverteu (`D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE`):
    o nó que ela quer é FIXO, e é a ROTA que vai e volta. Enquanto o subsystem
    não estiver registrado, quem publica os quatro nós fixos não existe — este
    gerenciador segue a lista viva, e o que a decisão dela cobra dele é
    **não derrubar o que não saiu**, que é o que ele já faz.
    """

    def __init__(
        self,
        *,
        fabrica: Any = None,
        fonte_por_controle: Any = None,
        ponte_do_radio_por_controle: Any = None,
    ) -> None:
        self._fabrica = fabrica
        self._fonte_por_controle = fonte_por_controle
        #: UMA PONTE POR CONTROLE NO RÁDIO — 10/09/2026. Recebe o ``uniq`` e
        #: devolve um callable que responde *"a ponte deste controle está no
        #: ar?"*. `None` = ninguém injetou ponte, e :func:`rota_do_no` recusa o
        #: rádio com a frase honesta, que é o comportamento de sempre.
        #:
        #: **A INJEÇÃO É O PONTO.** Este gerenciador não abre hidraw nem sobe
        #: thread: ele sabe QUAIS controles existem e qual é a mesa, e nada
        #: mais. Quem constrói a ponte é quem tem o broker na mão.
        self._ponte_do_radio_por_controle = ponte_do_radio_por_controle
        self._nos: dict[str, Any] = {}
        self._acordar = threading.Event()

    @property
    def nos(self) -> dict[str, Any]:
        return dict(self._nos)

    def _construir(
        self,
        uniq: str,
        transporte: str,
        mesa: tuple[str, ...],
        *,
        descricao: str | None = None,
    ) -> Any:
        """O nó daquele controle, JÁ com rótulo próprio e rota resolvida.

        O rótulo e a rota nascem aqui e não dentro do nó porque quem sabe a
        MESA é este gerenciador: ``sink_do_controle`` precisa da lista inteira
        de ``uniq`` para casar a placa USB certa. Com um só, dois DualSense no
        cabo entregam o som do P2 no alto-falante do P1.

        O parâmetro ``descricao``  (noqa-acento) nome de parâmetro
        existe para UM chamador — a VOLTA de :meth:`_republicar`,
        que precisa reerguer o nó com o rótulo que estava no ar, e não com o de
        agora. Sem ela a volta seria uma segunda tentativa do mesmo ato que
        acabou de falhar, e não um desfazer.
        """
        if self._fabrica is not None:
            return self._fabrica(uniq)
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            SinkVirtualPipeWire,
            descricao_do_alto_falante,
        )

        return SinkVirtualPipeWire(
            uniq=uniq,
            descricao=(
                descricao_do_alto_falante(uniq) if descricao is None else descricao
            ),
            rota=self._rota_de_agora(uniq, transporte, mesa),
        )

    def _rota_de_agora(self, uniq: str, transporte: str, mesa: tuple[str, ...]) -> Any:
        """A rota que este controle teria se o nó nascesse AGORA.

        Um lugar só para a pergunta, porque ela tem DOIS chamadores desde
        SOM-JUNTO-01: :meth:`_construir`, para o nó que nasce, e
        :meth:`_reafinar`, para o que já está de pé. Duas cópias divergiriam no
        dia em que alguém acrescentasse um ingrediente a uma delas — e a que
        ficasse para trás seria justamente a do nó vivo, que é a que some sem
        sintoma.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import rota_do_no

        return rota_do_no(
            uniq,
            transporte,
            mesa,
            fonte=self._fonte_do_no(uniq),
            ponte_do_radio=self._ponte_do_radio(uniq),
        )

    # -----------------------------------------------------------------
    # SOM-JUNTO-01 (17/09/2026) — a escolha dela chega ao nó que JÁ ESTÁ DE PÉ
    # -----------------------------------------------------------------
    # A queixa dela: *"o som se eu clicar em um dos 3 botões ele tem que sair o
    # som via canal de audio externo do controle"*.  # (noqa-acento): a digitação é dela
    #
    # Dos três botões do card Alto-falante, o do meio — «No
    # controle e na TV» — grava `speaker.fonte="mix"` no perfil e NUNCA chegava
    # ao aparelho: a fonte só era resolvida ao CONSTRUIR o nó, e a varredura
    # fechava a porta antes de perguntar qualquer coisa (`if uniq in self._nos:
    # continue`). Medido com quatro varreduras trocando a fonte no meio: uma
    # construção, nó vivo em `sfx`, perfil em `mix`, zero `module-loopback`.
    #
    # O QUE NÃO SE PODE FAZER PARA CURAR ISSO, e é decisão dela:
    # `D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE` proíbe derrubar o nó por
    # varredura — o jogo escolheu `hefesto_som_<hex6>`, e tirá-lo do servidor
    # tira o dispositivo debaixo dele. Por isso a cura NÃO reconstrói o nó:
    # `SinkVirtualPipeWire.religar` troca só os `module-loopback`, e o
    # `module-null-sink` fica com o mesmo id e o mesmo nome.

    def _reafinar(
        self, uniq: str, no: Any, transporte: str, mesa: tuple[str, ...]
    ) -> None:
        """A rota do nó VIVO passa a ser a de agora — e o nó não sai do lugar.

        **O QUE ISTO CUSTA, medido e escrito para ninguém se assustar depois:**
        um :func:`rota_do_no` por nó de pé, por varredura. No cabo isso é um
        ``pactl list sinks short`` (mais o longo, quando há placa de DualSense
        na lista) e, em ``mix``, um ``pactl get-default-sink``. Com a mesa de
        quatro cheia e :data:`RECONCILIA_S` em 5 s, são menos de um subprocesso
        por segundo. **Não é a tempestade de syscalls do mapa de motores do
        `gamepad.py`**, e o preço de não pagá-lo é a escolha dela presa até o
        daemon reiniciar, que é o defeito que esta sprint fechou.

        O que NÃO se lê aqui é o perfil: a fonte vem do cache por
        ``(nome, mtime)`` de :meth:`AltoFalanteSubsystem._fontes_do_perfil`.
        """
        religar = getattr(no, "religar", None)
        if self._fabrica is not None or not callable(religar):
            # Com fábrica injetada o dono do nó é quem a injetou, e perguntar
            # `rota_do_no` aqui mandaria um `pactl` de verdade para a máquina
            # de quem roda a suíte.
            return
        try:
            rota = self._rota_de_agora(uniq, transporte, mesa)
        except Exception:  # nunca derruba a varredura
            logger.debug("som_rota_de_agora_ilegivel", uniq=uniq, exc_info=True)
            return
        if not self._vale_religar(uniq, rota):
            return
        try:
            religar(rota)
        except Exception:  # nunca derruba a varredura
            logger.debug("som_religacao_falhou", uniq=uniq, exc_info=True)

    def _vale_religar(self, uniq: str, rota: Any) -> bool:
        """Esta rota nova merece encostar num nó que está tocando?

        DUAS recusas, e cada uma é um jeito de a varredura estragar o que
        funciona:

        * **perder a rota nunca desliga o que está ligado.** ``tem_rota=False``
          é *"agora não sei para onde"* — o servidor em recuo, a placa que
          ainda não enumerou, a ponte que caiu — e responder a isso arrancando
          o ``module-loopback`` é trocar um silêncio de cinco segundos por um
          permanente. Quando souber de novo, a assinatura volta a bater e nada
          acontece;
        * **o nó nunca vira alvo de si mesmo.** ``sink_do_controle`` devolve o
          PRÓPRIO ``hefesto_som_<hex6>`` como recuo quando não acha placa da
          Sony — e o nó, estando VIVO, aparece nessa lista. Sem esta recusa a
          varredura montaria ``source=X.monitor sink=X``, e pior: a assinatura
          passaria a depender de o nó estar de pé, que é a receita exata do nó
          que renasce a cada varredura.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

        if rota is None or not getattr(rota, "tem_rota", False):
            return False
        alvo = str(getattr(rota, "sink", "") or "")
        if alvo and alvo == nome_do_sink(uniq):
            logger.debug("som_rota_para_si_mesma", uniq=uniq, sink=alvo)
            return False
        return True

    # -----------------------------------------------------------------
    # O-NOME-DO-SOM-RENOMEIA-JUNTO-01 (20/09/2026) — o rótulo segue o assento
    # -----------------------------------------------------------------

    def _o_rotulo_envelheceu(self, uniq: str, no: Any) -> bool:
        """O nome que este nó VIVO carrega ficou para trás do assento de agora?

        A medição que originou isto está em
        :func:`~integrations.dualsense_bt_audio.rotulo_envelheceu`, e o resumo
        é: ela mandou som para «Alto-falante do Controle 3» e ouviu no Player
        1. O rótulo é a fotografia do assento de quando o nó nasceu, e um
        controle que entra na mesa empurra o assento de OUTRO sem que o nó do
        outro renasça.

        **TRÊS RECUSAS, e cada uma é um jeito de a cura virar defeito maior:**

        * **nó sem rótulo legível não se toca.** Um nó cujo campo do rótulo
          texto é um nó de que não sabemos o nome — e *"não sei"* nunca
          autoriza derrubar o que está de pé. É também o que mantém as fábricas
          injetadas da suíte fora deste caminho;
        * **perder o número nunca conta** — a regra mora em
          :func:`rotulo_envelheceu`, e sem ela a varredura republicaria o nó de
          cinco em cinco segundos toda vez que o numerador piscasse;
        * **nunca por cima de quem está TOCANDO.** Renomear é republicar (não há
          ``update-sink-proplist`` no ``pactl`` do PipeWire — medido), e
          republicar tira o dispositivo debaixo do jogo. ``estado()`` que não
          responda vale como *"pode estar tocando"*, pela mesma razão escrita em
          :meth:`~integrations.alto_falante_bt.SinkVirtualPipeWire.estado`:
          *"não sei" não é "ninguém está tocando"*.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            descricao_do_alto_falante,
        )
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            rotulo_envelheceu,
        )

        no_ar = getattr(no, "descricao", None)  # (noqa-acento) nome de atributo
        if not isinstance(no_ar, str) or not no_ar:
            return False
        try:
            de_agora = descricao_do_alto_falante(uniq)
        except Exception:  # nunca derruba a varredura
            logger.debug("som_rotulo_de_agora_ilegivel", uniq=uniq, exc_info=True)
            return False
        if not rotulo_envelheceu(no_ar, de_agora):
            return False
        if self._esta_tocando(no):
            logger.info(
                "som_rotulo_velho_espera_o_silencio",
                uniq=uniq,
                no_ar=no_ar,
                de_agora=de_agora,
            )
            return False
        logger.info(
            "som_rotulo_envelheceu", uniq=uniq, no_ar=no_ar, de_agora=de_agora
        )
        return True

    def _esta_tocando(self, no: Any) -> bool:
        """Alguém está mandando som para este nó AGORA — ou não dá para saber.

        As duas respostas somam de propósito: quem chama isto decide se
        DERRUBA o nó, e o lado seguro de *"não sei"* é não derrubar.
        """
        estado = getattr(no, "estado", None)
        if not callable(estado):
            return False
        try:
            atual = estado()
        except Exception:  # pragma: no cover - defensivo
            return True
        if atual is None:
            return True
        return str(atual).strip().upper() == "RUNNING"

    def _ponte_do_radio(self, uniq: str) -> Any:
        """O callable que diz se a ponte DESTE controle está no ar — ou `None`.

        `None` não é falha: é *"ninguém me deu ponte"*, e :func:`rota_do_no`
        responde com a frase honesta. O que ele NÃO pode virar é um `lambda:
        True` otimista — isso publicaria a rota sobre uma ponte que não existe,
        e o nó voltaria a ser o sumidouro que
        `tests/unit/test_o_no_de_som_nao_nasce_sumidouro.py` trava.
        """
        if self._ponte_do_radio_por_controle is None:
            return None
        try:
            return self._ponte_do_radio_por_controle(uniq)
        except Exception:  # pragma: no cover - defensivo
            logger.debug("som_ponte_do_radio_ilegivel", uniq=uniq, exc_info=True)
            return None

    def _fonte_do_no(self, uniq: str) -> str:
        """``mix`` ou ``sfx`` para este controle — o padrão dela quando ninguém disse.

        A escolha mora no PERFIL (``ControllerOverrides.speaker.fonte``) e
        chega aqui por injeção, nunca por leitura de disco no laço: ler o
        perfil a cada varredura é a tempestade de syscalls que o mapa de
        motores do ``gamepad.py`` já pagou uma vez.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import FONTE_PADRAO

        if self._fonte_por_controle is None:
            return FONTE_PADRAO
        try:
            return self._fonte_por_controle(uniq) or FONTE_PADRAO
        except Exception:  # pragma: no cover - defensivo
            logger.debug("som_fonte_ilegivel", uniq=uniq, exc_info=True)
            return FONTE_PADRAO

    def reconciliar(self, controles: list[Any] | None = None) -> None:
        """Casa os nós vivos com a lista de controles recebida.

        **Tirar um controle da lista DERRUBA o nó dele e deixa os outros de
        pé.** Sem isso, um controle sumir derrubaria o som dos quatro — que é
        exatamente o defeito de "a rota some debaixo do jogo", só que causado
        por nós.

        **E QUEM JÁ ESTÁ DE PÉ TEM A ROTA REAFINADA — SOM-JUNTO-01.** O nó não
        renasce; o que vai e volta é a rota, por
        :meth:`~integrations.alto_falante_bt.SinkVirtualPipeWire.religar`.
        Rota de assinatura igual não custa um ``pactl``, e é por isso que esta
        varredura pode rodar de 5 em 5 s sem mexer em nada.

        Aceita ``str`` (só o ``uniq``) e :class:`ControleNaLista` (o ``uniq``
        **e** o transporte). A segunda forma é a que resolve rota; a primeira
        sobrevive porque as réguas de ciclo de vida a usam, e trocá-las por
        objeto não mediria nada de novo.
        """
        vistos: dict[str, str] = {}
        for item in controles or []:
            uniq = item if isinstance(item, str) else str(getattr(item, "uniq", ""))
            if not uniq or uniq in vistos:
                continue
            transporte = (
                "" if isinstance(item, str) else str(getattr(item, "transporte", ""))
            )
            vistos[uniq] = transporte
        alvos = list(vistos)
        mesa = tuple(alvos)
        for uniq in list(self._nos):
            if uniq not in alvos:
                self._derrubar(uniq)
        for uniq in alvos:
            transporte = vistos[uniq] or TRANSPORTE_CABO
            # **E O RÓTULO VELHO REPUBLICA O NÓ — O-NOME-DO-SOM-RENOMEIA-JUNTO-01,
            # 20/09/2026.** Não há renomear no lugar (o `pactl` do PipeWire não
            # tem `update-sink-proplist` — medido), então o nó RENASCE com o
            # nome de agora. As três recusas que impedem isto de virar um nó
            # piscando estão em `_o_rotulo_envelheceu`; a ORDEM que impede o nó
            # de sumir está em `_republicar`.
            if uniq in self._nos and self._o_rotulo_envelheceu(uniq, self._nos[uniq]):
                self._republicar(uniq, transporte, mesa)
            if uniq in self._nos:
                # **NÃO É MAIS UM `continue` SECO — SOM-JUNTO-01, 17/09/2026.**
                # Esta linha fechava a porta antes de perguntar qualquer coisa,
                # e era ela que prendia a escolha dela no disco: a fonte só era
                # resolvida ao CONSTRUIR, e o nó nunca renascia. O nó continua
                # sem renascer — quem vai e volta é a ROTA.
                self._reafinar(uniq, self._nos[uniq], transporte, mesa)
                continue
            no = self._erguer(uniq, transporte, mesa)
            if no is not None:
                self._nos[uniq] = no

    def _erguer(
        self,
        uniq: str,
        transporte: str,
        mesa: tuple[str, ...],
        *,
        descricao: str | None = None,
    ) -> Any:
        """Constrói e SOBE o nó daquele controle. `None` = não subiu.

        **UM DONO SÓ PARA «PÔR UM NÓ DE PÉ», e a razão é medida:** desde
        `O-NOME-DO-SOM-RENOMEIA-JUNTO-01` há DOIS momentos em que um nó nasce —
        o do controle que chega e o do rótulo que envelheceu
        (:meth:`_republicar`) — e uma segunda cópia destas guardas divergiria
        no dia em que alguém acrescentasse uma. A que ficasse para trás seria
        a do renascimento, que é a que some sem sintoma.

        Este método **não** escreve em ``self._nos``: quem o chama decide o que
        fazer com o nó que voltou, e é isso que deixa a volta de
        :meth:`_republicar` ser uma volta.
        """
        no = self._construir(uniq, transporte, mesa, descricao=descricao)
        # SEM ROTA, SEM NÓ — e a razão é a invariante 4 que o plano da janela
        # escrevia (`app/audio_saida.py`, até 28/09/2026): *"um
        # `module-null-sink` sozinho seria exatamente o sink que aceita o
        # áudio e o joga fora"*. Publicar
        # aqui poria uma entrada MUDA por DualSense na lista de som dela;
        # ela escolhe uma das quatro e o som some.
        #
        # Isto NÃO contradiz `D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE`.
        # A decisão dela é sobre o nó não sumir debaixo do jogo quando o
        # controle troca de transporte ou pisca; esta guarda é sobre nunca
        # PUBLICAR um nó que não entrega em lugar nenhum. `rota.motivo`
        # carrega a frase honesta, e é ela que a tela mostra.
        rota = getattr(no, "rota", None)
        if rota is not None and not getattr(rota, "tem_rota", True):
            logger.info(
                "som_no_sem_rota",
                uniq=uniq,
                motivo=str(getattr(rota, "motivo", "")),
            )
            return None
        try:
            subiu = bool(no.iniciar())
        except Exception as exc:  # nunca derruba a varredura
            logger.debug("som_no_falhou", uniq=uniq, err=str(exc))
            return None
        if not subiu:
            logger.info("som_no_nao_subiu", uniq=uniq)
            return None
        return no

    def _republicar(self, uniq: str, transporte: str, mesa: tuple[str, ...]) -> bool:
        """O nó renasce com o rótulo de agora. False = ficou exatamente como estava.

        **PRIMEIRO CONSTRÓI, DEPOIS DERRUBA — e a ordem É a cura.** Medido pelo
        conferente em 20/09/2026, sobre a primeira versão desta cura: ela fazia
        ``_derrubar(uniq)`` e deixava o nó renascer pelo caminho de baixo; com a
        rota não resolvendo naquele instante — a placa USB do cabo sumindo por
        uma varredura, a ponte do rádio ainda não de pé —, a guarda «SEM ROTA,
        SEM NÓ» recusava o renascimento e **o nó SUMIA da mesa dela**.
        ``set(ger.nos)`` vazio onde havia dois. Um jogo que tivesse escolhido
        o «Alto-falante do Controle 3» perdia o dispositivo debaixo de si, e
        pelo motivo mais bobo possível: o nome estava desatualizado.

        **A REGRA QUE SOBRA: um rótulo velho é melhor que nó nenhum.** O nome
        errado é uma queixa; o nó que some é a queda do som. Por isso as três
        respostas possíveis são todas com nó de pé:

        * a rota de agora não resolve → **não se toca no nó**, e o rótulo
          espera a próxima varredura;
        * o nó novo sobe → ele entra no lugar, com o nome de agora;
        * o nó novo NÃO sobe → a VOLTA reergue o nó com o rótulo que estava no
          ar (:meth:`_construir` recebe o rótulo pronto), e não com o de agora —
          repetir o ato que acabou de falhar não é desfazer.

        Só quando nem a volta sobe é que a mesa fica sem este nó, e aí ela
        ficaria de qualquer jeito: o caminho de nascimento da varredura
        seguinte tenta de novo, porque o ``uniq`` já não está em ``_nos``.
        """
        velho = self._nos.get(uniq)
        if velho is None:
            return False
        no_ar = getattr(velho, "descricao", None)  # (noqa-acento) nome de atributo
        try:
            novo = self._construir(uniq, transporte, mesa)
        except Exception:  # nunca derruba a varredura
            logger.debug("som_rotulo_novo_ilegivel", uniq=uniq, exc_info=True)
            return False
        rota = getattr(novo, "rota", None)
        if rota is not None and not getattr(rota, "tem_rota", True):
            # A RECUSA QUE SALVA O NÓ. Sem ela o `_derrubar` de baixo já teria
            # acontecido, e a mesa ficaria sem o nó por causa do NOME.
            logger.info(
                "som_rotulo_velho_espera_a_rota",
                uniq=uniq,
                motivo=str(getattr(rota, "motivo", "")),
            )
            return False
        self._derrubar(uniq)
        try:
            subiu = bool(novo.iniciar())
        except Exception as exc:  # nunca derruba a varredura
            logger.debug("som_no_falhou", uniq=uniq, err=str(exc))
            subiu = False
        if subiu:
            self._nos[uniq] = novo
            return True
        logger.warning("som_rotulo_velho_nao_renasceu", uniq=uniq, no_ar=str(no_ar or ""))
        de_volta = self._erguer(
            uniq, transporte, mesa, descricao=str(no_ar) if no_ar else None
        )
        if de_volta is not None:
            self._nos[uniq] = de_volta
            logger.info("som_no_voltou_com_o_rotulo_velho", uniq=uniq)
        else:
            logger.warning("som_no_sumiu_ao_republicar", uniq=uniq)
        return False

    def _derrubar(self, uniq: str) -> None:
        no = self._nos.pop(uniq, None)
        if no is None:
            return
        with contextlib.suppress(Exception):
            no.parar()
        logger.info("som_no_derrubado", uniq=uniq)

    def dormir(self, segundos: float) -> bool:
        """True quando é para parar. Bloqueia num Event, nunca num sleep."""
        return self._acordar.wait(segundos)

    def parar(self) -> None:
        """Derruba todos os nós. Idempotente."""
        for uniq in list(self._nos):
            self._derrubar(uniq)
        self._acordar.set()


def _uniq_de_perfil(uniq: str) -> str:
    """O `uniq` na grafia que o PERFIL usa: doze hex minúsculos, sem separador.

    O sysfs entrega `aa:bb:cc:dd:ee:ff` e o `Profile.controllers` é chaveado
    por `aabbccddeeff` — o schema recusa a outra forma. Casar as duas grafias
    à mão em cada chamador é como esta casa já perdeu uma escolha dela: a
    chave não bate, `get` devolve `None`, e ninguém vê erro nenhum.
    """
    return "".join(c for c in uniq.lower() if c in "0123456789abcdef")[:12]


def _carimbo_do_perfil(nome: str) -> Any:
    """`(mtime_ns do perfil, selo do maquina.json)` — `None` quando não dá para saber.

    É o que invalida o cache das fontes. `None` (arquivo não encontrado, erro
    de `stat`) força a releitura na varredura seguinte, que é o lado seguro:
    ler demais custa uma syscall, ler de menos entrega a escolha de ontem.
    """
    try:
        # `_profile_path` é privado do loader, e usá-lo é deliberado: a
        # alternativa seria redigitar aqui `profiles_dir() / f"{slug}.json"`,
        # e uma segunda regra de "onde mora o perfil" é como esta casa já
        # perdeu escrita dela — o `slugify` e a recusa de travessia moram lá.
        from hefesto_dualsense4unix.profiles.loader import _profile_path
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
            selo_da_maquina,
        )

        # O padrão do computador entra na fonte (O-QUE-E-DO-COMPUTADOR-NAO-
        # MUDA-COM-O-JOGO-01): mudar o `maquina.json` também relê.
        return (Path(_profile_path(nome)).stat().st_mtime_ns, selo_da_maquina())
    except Exception:
        return None


def _fontes_por_controle(nome: str) -> dict[str, str]:
    """`{uniq: "mix"|"sfx"}` dos overrides daquele perfil. `{}` é honesto.

    Só entra quem DECLAROU: `speaker.fonte is None` significa *"sem opinião"*
    em todo o esquema de perfil, e transformá-lo em `sfx` aqui apagaria a
    diferença entre «ela escolheu efeitos» e «ela não escolheu nada» — que é
    a distinção que faz o padrão poder mudar um dia sem reescrever perfil.
    """
    try:
        from hefesto_dualsense4unix.profiles.loader import load_profile
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale

        perfil = o_que_vale(load_profile(nome))
    except Exception:
        logger.debug("som_perfil_ilegivel", perfil=nome, exc_info=True)
        return {}

    fontes: dict[str, str] = {}
    for chave, override in (getattr(perfil, "controllers", None) or {}).items():
        alto_falante = getattr(override, "speaker", None)
        fonte = getattr(alto_falante, "fonte", None)
        if fonte:
            fontes[_uniq_de_perfil(str(chave))] = str(fonte)
    return fontes


def controles_na_lista(raiz: str | None = None) -> list[ControleNaLista]:
    """Todo DualSense que o sysfs mostra, **nos dois transportes**.

    A metade de entrada só precisa dos de Bluetooth (o microfone no cabo já
    funciona sozinho); aqui a pergunta é outra e a resposta tem de ser dos
    dois lados, porque o nó existe justamente para não mudar quando o controle
    troca de braço.

    Reusa a leitura de ``uevent`` e as constantes de identidade da ENTRADA em
    vez de reimplementá-las — três instrumentos respondendo *"isto é um
    DualSense?"* de três jeitos é como esta casa já fabricou uma resposta
    errada, e o precedente tem nome (``identidade_do_vpad.py``). Os nomes com
    ``_`` são privados daquele módulo: a alternativa seria redigitar o vendor,
    os dois produtos e o parser aqui, que é a duplicação que a regra proíbe.
    Import tardio para que importar o subsystem não arraste a libopus nem o
    ``pactl`` — mesma razão do import tardio da metade de entrada.
    """
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as entrada

    achados: list[ControleNaLista] = []
    try:
        entradas = sorted(Path(raiz or entrada._SYSFS_HIDRAW).iterdir())
    except OSError:
        return achados
    for item in entradas:
        info = entrada._uevent(item)
        partes = info.get("HID_ID", "").split(":")
        if len(partes) != 3:
            continue
        try:
            bus, vendor, produto = (int(p, 16) for p in partes)
        except ValueError:
            continue
        if vendor != entrada._VENDOR_SONY or produto not in entrada._PRODUTOS_DUALSENSE:
            continue
        # O vpad do próprio hefesto se apresenta como 0x0DF2 em BUS_USB. Sem o
        # filtro de bus da entrada, o `HID_PHYS` é a ÚNICA rede que sobra — e
        # publicar um nó de som para o nosso próprio gamepad virtual seria o
        # produto conversando consigo mesmo.
        if info.get("HID_PHYS", "") == entrada._PHYS_VPAD:
            continue
        achados.append(
            ControleNaLista(
                uniq=info.get("HID_UNIQ", ""),
                caminho=f"/dev/{item.name}",
                transporte="rádio" if bus == entrada._BUS_BLUETOOTH else "cabo",
            )
        )
    return achados


class AltoFalanteSubsystem:
    """Mantém um nó de som por DualSense presente, em qualquer transporte."""

    name = "alto_falante"

    #: O que a última volta viu do jogo pela PISTA do evdev
    #: (``quem_o_jogo_le.RetratoDoJogo``): os pids, os ``eventN`` e os
    #: ``hidrawN`` que ele segura. Desde 28/09 só a linha
    #: ``haptica_portao_fechado`` pergunta, e só quando ela muda — a partida
    #: não sai mais daqui. **Mora no corpo da classe, e não no ``__init__``** —
    #: dublê montado por ``object.__new__`` não roda o ``__init__``, e estado
    #: novo que só nasce lá deixa o dublê mais POBRE que o produto.
    _retrato_do_jogo: Any = None
    #: Os ``uniq`` cujo evdev um processo de jogo segurava na última pergunta
    #: — a PISTA ``evdev_le_este`` da linha ``haptica_portao_fechado``, que
    #: não vota (A-HAPTICA-QUEM-JOGA-02).
    _lidos_pelo_evdev: frozenset[str] = frozenset()
    #: ``{uniq: motivo}`` de quem está com o portão da háptica fechado AGORA —
    #: o endpoint tocando e o controle fora de quem joga. Lembrado para a
    #: linha ``haptica_portao_fechado`` sair só na mudança. Imutável no corpo
    #: da classe; cada mudança troca o dicionário inteiro.
    _portao_fechado: Mapping[str, str] = MappingProxyType({})
    #: Os donos dos fluxos que tocavam nos endpoints de háptica na última volta
    #: (os clientes do servidor de som) — a partida do jogo. ``None`` = a
    #: volta não soube (o servidor não respondeu), e a partida não mudou.
    _donos_da_volta: frozenset[str] | None = None
    #: Os ``uniq`` dos controles no rádio da última volta: os nós que decidem
    #: a volta são os deles (o endpoint de háptica e o nó de som).
    _no_radio: frozenset[str] = frozenset()
    #: Quais desses nós tinham fluxo quando a última volta COMEÇOU. A volta
    #: acorda antes do relógio quando isto muda — ver :meth:`_a_mesa_do_som_mudou`.
    _o_que_a_volta_viu: frozenset[str] | None = None
    #: Alguém pediu a volta agora (o controle que entrou na partida, a resposta
    #: dela ao «Ligar aqui»). Lido e zerado pelo laço.
    _volta_pedida: bool = False
    #: ``{uniq: marca do aparelho}`` de cada DualSense da mesa na última volta
    #: (A-HAPTICA-E-POR-APARELHO-01, 02/10/2026; de 28/09 a 02/10 era
    #: ``_lugar_de``, o lugar à mesa). A marca é a de
    #: ``dualsense_bt_audio.marca_do_aparelho``, a mesma no cabo e no rádio, e
    #: renumerar a mesa não a muda. Imutável no corpo da classe; cada volta
    #: troca o dicionário inteiro.
    _aparelho_de: Mapping[str, str] = MappingProxyType({})
    #: ``{uniq: nome do endpoint}`` que a ponte de cada controle lê no modo
    #: háptica (``""`` no modo som), escrito quando a ponte sobe. A ponte que lê
    #: outro endpoint que não o do aparelho dela desce e sobe
    #: (:meth:`_casar_as_pontes`). Imutável no corpo da classe, como o
    #: ``_aparelho_de``.
    _endpoint_da_ponte: Mapping[str, str] = MappingProxyType({})
    #: ``{uniq: nome do endpoint}`` que a ponte de cada controle ESCUTA: o que
    #: ela leva ao rádio no modo háptica, e o que ela só ouve no modo som
    #: (``""`` quando não ouve nenhum). A-HAPTICA-POR-AUDIO-E-O-ALTO-FALANTE-
    #: CHEGAM-AO-RADIO-01: a ponte do som que não escuta o endpoint aberto do
    #: aparelho sobe de novo com o ouvido (:meth:`_casar_as_pontes`). Ponte sem
    #: registro (dublê) não tem a resposta, e fica como está.
    _ouvido_da_ponte: Mapping[str, str] = MappingProxyType({})
    #: Os laços do cabo (``integrations/haptica_do_cabo.HapticaDoCabo``). Nasce
    #: na primeira volta que precisa dele (:meth:`_o_cabo`) — dublê montado por
    #: ``__new__`` também o ganha.
    _cabo: Any = None
    #: ``{uniq: OuvidoDaPlaca}`` de cada controle no cabo com placa de quatro
    #: canais: o monitor da placa lido só para o ouvido, de onde a luz «no ar»
    #: do cabo responde (O-GANHO-DA-HAPTICA-TEM-DONO-01, item 8, 02/10/2026).
    _ouvidos_das_placas: Mapping[str, Any] = MappingProxyType({})
    #: A HÁPTICA FINA DO RUMBLE — NO-MODO-XBOX-TUDO-FUNCIONA-01, parte 4
    #: (29/09/2026). ``{marca: TocadorDoRumble}``: o rumble do pad sem háptica
    #: (o ``uinput``), tocado no endpoint do aparelho de quem recebe (desde
    #: 02/10; era o do lugar). Nasce no primeiro rumble que o pede
    #: (:meth:`_tocador_do_aparelho`). Como o resto do estado novo, mora no
    #: corpo da classe e troca inteiro.
    _tocadores: Mapping[str, Any] = MappingProxyType({})
    #: ``{uniq: (reaplicar, (marca, quer, leva))}`` de quem tem rumble não nulo
    #: agora, com o retrato que o fio da vibração viu (:meth:`_retrato_do_rumble`).
    #: A volta compara com o de agora e, quando muda, reaplica
    #: (:meth:`_conferir_o_rumble`).
    _rumble_vivo: Mapping[str, tuple[Any, tuple[str | None, bool, bool]]] = MappingProxyType({})
    #: Os clientes do servidor de som que são os NOSSOS tocadores: um tocador
    #: não é jogo, e a partida não o conta (:meth:`_donos_dos_fluxos`).
    _clientes_do_rumble: frozenset[str] = frozenset()
    #: As marcas dos aparelhos cujo endpoint tem fluxo de JOGO: ali a háptica é
    #: a do jogo, e o rumble segue pelos motores (o «ou» da sprint).
    _aparelhos_com_jogo: frozenset[str] = frozenset()
    #: As marcas dos aparelhos cujo endpoint nasceu com um jogo já tocando nos
    #: endpoints: o registro do lançamento não os tem, e o diário já disse
    #: (``haptica_aparelho_sem_registro_no_jogo``). Zera quando a partida fecha.
    _sem_registro_no_jogo: frozenset[str] = frozenset()
    #: Os controles do rádio com o alto-falante tocando: pelo rádio som e
    #: vibração são exclusivos, e a háptica fina não tira o som de ninguém.
    _radio_com_som: frozenset[str] = frozenset()
    #: ``{uniq: quando foi rebatido}`` dos controles com o teste «Háptica» da
    #: aba Vibração ligado (:meth:`testar_a_haptica`). A janela rebate a cada
    #: segundo; o que ninguém rebate solta sozinho
    #: (:meth:`_conferir_o_teste_da_haptica`).
    _teste_da_haptica: Mapping[str, float] = MappingProxyType({})
    _trava_do_rumble = threading.Lock()

    #: O GOVERNADOR DO RÁDIO (GOVERNADOR-DO-RADIO-01, 23/09/2026): quem dá a
    #: vaga de cada ponte, por adaptador, e manda ceder na fonte quando o
    #: adaptador não escoa. Nasce no ``start()``; ``None`` num dublê montado
    #: por ``__new__`` ou antes de subir, e aí a ponte sobe como sempre subiu.
    #: O ``state_full`` lê a amostra de ar DELE — um medidor só no daemon.
    governador: Any = None
    #: ``(uniq, modo)`` de quem tem som esperando uma vaga que o governador
    #: ainda não deu (o adaptador cheio, à espera da resposta dela; ou o
    #: adaptador parado). Refeito a cada volta. Quando ela responde «Ligar
    #: aqui», :meth:`_esquecer_a_espera` tira o controle daqui e acorda a volta.
    _esperando_vaga: frozenset[tuple[str, str]] = frozenset()

    def __init__(
        self,
        *,
        gerenciador: Any = None,
        fonte_de_controles: Any = None,
        daemon: Any = None,
        governador: Any = None,
    ) -> None:
        #: O `Daemon`, e é por ele que o «Controle N» do nó chega ao mesmo
        #: número do cartão — ver `numero_do_assento` e
        #: `subsystems/base.slot_de_sessao`. Entra o DAEMON e não o registro
        #: porque a fiação do `identity_registry` (`lifecycle._wire_identity_
        #: registry`) acontece DEPOIS deste `start()`.
        self._daemon: Any = daemon
        self._governador_injetado = governador
        self._gerenciador_injetado = gerenciador
        self._gerenciador: Any = None
        #: UMA ponte por controle no rádio, pelo `uniq`.
        self._pontes: dict[str, Any] = {}
        #: O endpoint de háptica por APARELHO, pela marca dele — o alto-falante
        #: de quatro canais que o JOGO enxerga. Ele não é o
        #: `hefesto_som_<hex6>`: aquele é a saída da MÁQUINA para o controle, e
        #: a pessoa o escolhe. Era um por lugar de 28/09 a 02/10/2026; é um por
        #: DualSense da mesa, nos dois transportes, desde a
        #: A-HAPTICA-E-POR-APARELHO-01.
        self._endpoints: dict[str, Any] = {}
        #: "som" ou "haptica": qual arranjo a ponte daquele controle está
        #: mandando AGORA. O escritor é um só, e trocar de arranjo exige
        #: derrubar e subir — é por isso que o modo é lembrado.
        self._modo_da_ponte: dict[str, str] = {}
        #: `uniq -> quando o `subir()` falhou` — ver :data:`RECUSA_DA_PONTE_S`.
        self._ponte_recusada: dict[str, float] = {}
        #: Quantos aparelhos ficaram sem âncora USB na última volta —
        #: lembrado para o aviso sair na MUDANÇA, e não a cada `RECONCILIA_S`.
        self._faltam_ancoras = 0
        #: `({uniq: fonte}, (nome do perfil, carimbo))` — SFX-POR-CONTROLE-01.
        self._fontes_em_cache: tuple[dict[str, str], Any] = ({}, None)
        #: `{uniq de perfil: fonte}` — a escolha VIVA, a que ela acabou de
        #: fazer na tela. Ela vence o perfil e mora na memória do daemon; ver
        #: :meth:`escolher_a_fonte`.
        self._fonte_viva: dict[str, str] = {}
        #: O `StateStore` do daemon, que sabe o perfil ATIVO agora.
        self._store: Any = None
        self._fonte = fonte_de_controles or controles_na_lista
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        self._backend: Any = None
        #: O numerador de assento que estava instalado quando este subsystem
        #: subiu. `Ellipsis` = ele não instalou nada (já havia dono) e não tem
        #: nada a devolver no `stop` — ver :meth:`start`.
        self._numerador_anterior: Any = Ellipsis
        #: Quem respondia a `fonte` antes de nós — devolvido no `stop()`.
        self._dizedor_anterior: Any = None
        #: O que acorda o laço antes do relógio: o ouvinte do retrato do som
        #: (:meth:`_ouvir_o_retrato`) e quem pede a volta
        #: (:meth:`_acordar_a_volta`). Um ``Event`` e não o ``Condition`` do
        #: retrato: com duas fontes de aviso, esperar no retrato perderia o
        #: pedido que chegasse entre olhar e dormir.
        self._acordar = threading.Event()
        #: A thread que escuta o retrato do som e acorda o laço.
        self._ouvinte: threading.Thread | None = None
        # A TROCA DE SINAL ACORDA A VOLTA — A-HAPTICA-POR-AUDIO-E-O-ALTO-
        # FALANTE-CHEGAM-AO-RADIO-01. O retrato do som só avisa quando um FLUXO
        # nasce ou morre; o sinal que passa do endpoint ao alto-falante com os
        # dois fluxos abertos não mudava entrada nenhuma da volta, e o modo
        # certo só chegava na volta seguinte por outro motivo. Referência
        # fraca: o subsystem que morre sai da lista sozinho.
        from hefesto_dualsense4unix.integrations.alto_falante_bt import OUVIDO

        OUVIDO.escutar(self._acordar_a_volta)

    # -- contrato Subsystem ----------------------------------------------

    def is_enabled(self, config: DaemonConfig) -> bool:
        """Sempre. O nó tem de estar no ar antes de o jogo escolher a saída.

        **Ligado não quer dizer tocando.** Sem controle na lista, ``alvos()``
        devolve ``[]``, nenhum módulo é carregado, nenhum byte de áudio passa
        por lugar nenhum e o custo em repouso é uma varredura de sysfs a cada
        :data:`RECONCILIA_S`. A privacidade não entra nesta conta como entra na
        do microfone: um alto-falante não escuta.

        ``config`` fica na assinatura porque o contrato ``Subsystem`` é esse.
        """
        del config
        return True

    def alvos(self, controles: list[Any]) -> list[Any]:
        """Os controles que ganham nó — os que têm identidade legível.

        Um controle sem ``HID_UNIQ`` NUNCA entra: sem endereço não há de quem
        seja o nó, e dois anônimos disputariam o mesmo nome. Ausência é
        resposta.

        **Devolve o CONTROLE e não o ``uniq``**, como o ``bt_mic.alvos`` já
        fazia: quem resolve a rota precisa do TRANSPORTE ao lado, e voltar a
        pedi-lo depois seria uma segunda varredura de sysfs com a chance de
        discordar da primeira.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

        vistos: list[Any] = []
        conhecidos: set[str] = set()
        for controle in controles:
            uniq = str(getattr(controle, "uniq", "") or "")
            if not nome_do_sink(uniq) or uniq in conhecidos:
                continue
            conhecidos.add(uniq)
            vistos.append(controle)
        return vistos

    def _controles_da_mesa(self) -> list[dict[str, Any]]:
        """``describe_controllers()`` do backend, ou ``[]`` quando ele não sabe.

        ``getattr`` porque nem todo backend é o de produção: os dublês da suíte
        e o backend de um controle só não conhecem a pergunta, e um backend que
        não conhece a pergunta não pode virar portão silencioso.
        """
        descrever = getattr(self._backend, "describe_controllers", None)
        if not callable(descrever):
            return []
        try:
            itens = descrever()
        except Exception:  # pragma: no cover - defensivo
            logger.debug("som_mesa_ilegivel", exc_info=True)
            return []
        if not isinstance(itens, list):
            return []
        return [item for item in itens if isinstance(item, dict)]

    def numero_do_assento(self, uniq: str) -> int | None:
        """O «Controle N» deste controle — o MESMO que a tela imprime no cartão.

        **A DÍVIDA DAS DUAS IMPLEMENTAÇÕES MORREU EM 12/09/2026**
        (TRES-CONTAS-PARA-UM-NUMERO-01). Esta função e a
        ``BtMicSubsystem.numero_do_assento`` eram a MESMA regra escrita duas
        vezes, e a régua que as amarrava era o que sobrava por não haver um dono
        só. Agora as duas chamam
        ``subsystems/base.numero_do_assento_na_mesa`` — e aquela função não
        conta nada: **ela pergunta o ``player_slot`` ao dono**, o
        ``identity_registry``, e aplica a regra da casa.

        Os dois rótulos que ela lê — «Alto-falante do Controle N» e «Microfone
        do Controle N» — continuam obrigados a dizer o MESMO número sobre o
        MESMO aparelho, lado a lado na mesma lista de som. Agora eles o dizem
        porque é o mesmo código, não porque duas cópias combinaram.

        E o número passou a ser o da TELA. Antes era a posição entre os
        conectados, que é a ordem dos HANDLES — na mesa dela, às 22h de 09/09,
        isso batizou de «Microfone do Controle 2» o aparelho cujo cartão dizia
        P1.

        **CONTINUA NÃO SENDO ``coop.resolve_player_numbers``:** com o co-op
        desligado ele responde ``1`` para todos, e a lista dela ganharia quatro
        «Alto-falante do Controle 1».

        Sem daemon vivo não há número: ``None`` é *"não sei"*, e o rótulo nasce
        sem número — nunca com um inventado.
        """
        return numero_do_assento_na_mesa(
            [i for i in self._controles_da_mesa() if i.get("connected")],
            uniq,
            daemon=self._daemon,
        )

    def uniqs_com_no(self) -> frozenset[str]:
        """Os ``uniq`` cujo nó está DE PÉ agora — o efeito, não o pedido."""
        gerenciador = self._gerenciador
        if gerenciador is None:
            return frozenset()
        try:
            return frozenset(gerenciador.nos)
        except Exception:  # best-effort: o relato nunca derruba o state_full
            logger.debug("som_nos_ilegiveis", exc_info=True)
            return frozenset()

    def pontes_de_pe(self) -> dict[str, str]:
        """``{uniq: "som" | "haptica"}`` das pontes do rádio NO AR agora.

        AR-MEDIDO-01 (23/09/2026): é o que o orçamento de ar conta (R10 dela,
        «pontes de som e vibração: N de 2»). LEITURA pura, do mesmo jeito que
        :meth:`uniqs_com_no`: o efeito, não o pedido — a ponte sob demanda
        que desceu por silêncio não ocupa o ar, e não entra.
        """
        try:
            pontes = dict(self._pontes)
            modos = dict(self._modo_da_ponte)
        except RuntimeError:  # o dicionário mudou no meio da cópia: não sei
            return {}
        saida: dict[str, str] = {}
        for uniq, ponte in pontes.items():
            modo = modos.get(uniq)
            if modo not in ("som", "haptica"):
                continue
            try:
                de_pe = bool(ponte.esta_de_pe())
            except Exception:  # best-effort: o relato nunca derruba o state_full
                continue
            if de_pe:
                saida[uniq] = modo
        return saida

    # -----------------------------------------------------------------
    # SFX-POR-CONTROLE-01 (10/09/2026) — a fonte de CADA controle
    # -----------------------------------------------------------------
    # `GerenciadorDeNosDeSom` aceita `fonte_por_controle` desde que nasceu, e
    # **ninguém o injetava** — exatamente a mesma família do
    # `ponte_do_radio_por_controle` que a A1 fiou. Consequência para quem joga:
    # o campo `speaker.fonte` do perfil dela existia, a aba o gravava, e todo
    # nó nascia com `FONTE_PADRAO`. A escolha morria no disco.
    #
    # A DIFERENÇA ENTRE AS DUAS FONTES É A CENA DELA:
    #
    # * `sfx` — o nó fica LIVRE para a corrente que o jogo mandar. É o tiro
    #   saindo no plástico DAQUELE jogador, e é o padrão;
    # * `mix` — o monitor da SAÍDA PADRÃO cai também neste nó. É o «HDMI
    #   completo» dela: o que a TV recebe, o controle recebe junto.
    #
    # Numa mesa de quatro isso é por pessoa: o P1 pode querer o mix inteiro no
    # ouvido e o P2 só os efeitos do jogo. Um nó que ignora a escolha entrega
    # a mesma coisa aos quatro.

    def _fonte_do_controle(self, uniq: str) -> str:
        """`mix` ou `sfx` para ESTE controle, lido do perfil ativo dela.

        **NÃO LÊ DISCO NO LAÇO.** A varredura roda a cada
        :data:`RECONCILIA_S`; reler o perfil ali seria a tempestade de syscalls
        que o mapa de motores do `gamepad.py` já pagou uma vez. O cache é por
        `(nome do perfil, mtime do arquivo)`, então a escolha dela vale na
        varredura seguinte ao "Salvar" e nem um instante depois.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import FONTE_PADRAO

        # A ESCOLHA VIVA VENCE O PERFIL, e a razão está medida — 20/09/2026,
        # `O-BOTAO-ENTREGA-O-QUE-PROMETE-01`. Com ela de ouvido, às 04:30, os
        # quatro controles estavam com o botão do meio aceso e o som do PC saiu
        # **só na TV**: *"so saiu na tv."* A escolha dela ia para o PERFIL, e
        # este método só sabia ler perfil ATIVO — sem perfil ativo, ou com a
        # escolha ainda não salva, `_fontes_do_perfil` devolve `{}` e o nó fica
        # no padrão para sempre. O clique nunca chegava ao aparelho.
        #
        # O perfil continua sendo onde a escolha DURA; este dicionário é onde
        # ela vale AGORA, e some com o daemon de propósito: ele é memória de
        # sessão, não uma segunda gravação concorrendo com o disco.
        viva = self._fonte_viva.get(_uniq_de_perfil(uniq))
        if viva:
            return viva
        fontes = self._fontes_do_perfil()
        return fontes.get(_uniq_de_perfil(uniq)) or FONTE_PADRAO

    def escolher_a_fonte(self, uniq: str, fonte: str) -> bool:
        """`mix` ou `sfx` para ESTE controle, valendo no nó que já está de pé.

        Quem chama é o `speaker.set` do IPC, que é o caminho por onde a tela
        fala com o daemon. O efeito chega ao nó na varredura seguinte, pelo
        `_reafinar` que a SOM-JUNTO-01 construiu: o `module-null-sink` fica com
        o mesmo id e o mesmo nome, e o que vai e volta é o `module-loopback` do
        monitor da saída padrão.

        **Não grava disco.** Quem guarda a escolha entre sessões é o perfil, e
        ele tem dono (`profiles.schema.SpeakerOverrides.fonte`). Dois
        escritores para a mesma escolha é como ela se perde: um grava, o outro
        relê o que não mudou, e a última palavra vira sorteio.

        Devolve `False` para valor que :func:`rota_do_no` não saiba tratar —
        tipo fechado, a mesma disciplina do `Literal` do perfil.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            FONTE_MIX,
            FONTE_SFX,
        )

        if fonte not in (FONTE_MIX, FONTE_SFX):
            return False
        self._fonte_viva[_uniq_de_perfil(uniq)] = fonte
        logger.info("som_fonte_escolhida", uniq=uniq, fonte=fonte)
        return True

    def fonte_escolhida(self, uniq: str) -> str:
        """A fonte que vale para este controle AGORA — a viva, ou a do perfil.

        Existe para o IPC responder o que ficou valendo sem duplicar a regra de
        precedência do método acima.
        """
        return self._fonte_do_controle(uniq)

    def _fontes_do_perfil(self) -> dict[str, str]:
        """`{uniq: fonte}` do perfil ativo — e `{}` é resposta honesta.

        Sem perfil ativo, com o arquivo ilegível, ou sem a seção `speaker` em
        override nenhum, a resposta é vazia e cada nó fica com o padrão. O que
        ela NUNCA pode ser é um palpite: publicar `mix` em quem não pediu põe
        o áudio do sistema inteiro no ouvido daquele jogador.
        """
        from hefesto_dualsense4unix.utils.session import load_last_profile

        try:
            nome = (
                getattr(getattr(self, "_store", None), "active_profile", None)
                or load_last_profile()
            )
        except Exception:  # pragma: no cover - defensivo
            nome = None
        if not nome:
            self._fontes_em_cache = ({}, None)
            return {}

        carimbo = _carimbo_do_perfil(nome)
        cacheado, chave = self._fontes_em_cache
        if chave == (nome, carimbo):
            return cacheado

        fontes = _fontes_por_controle(nome)
        self._fontes_em_cache = (fontes, (nome, carimbo))
        logger.debug("som_fontes_relidas", perfil=nome, controles=len(fontes))
        return fontes

    # -----------------------------------------------------------------
    # SOM-FIADO-01 (10/09/2026) — a ponte por rádio sobe DE VERDADE
    # -----------------------------------------------------------------
    # `PonteDeSomPorRadio` nasceu em 10/09 com régua e com o report que TOCOU,
    # e **ninguém a construía**: o único lugar onde o nome aparecia fora do
    # módulo que a define era a assinatura de um construtor. O degrau era
    # MONTOU, e a conferência daquele dia pegou o mapa chamando isso de "existe
    # no produto".
    #
    # É AQUI QUE A FIAÇÃO ACONTECE, e ela é POR CONTROLE: uma ponte por `uniq`,
    # com o hidraw DAQUELE controle e o monitor do nó DAQUELE controle. Uma
    # ponte compartilhada mandaria o som do P2 pelo alto-falante do P1 — a
    # mesma família do `sink_do_controle` no cabo.

    def _ponte_do_radio_de(self, uniq: str) -> Any:
        """O callable que diz se este controle TEM CAMINHO pelo rádio.

        **A PERGUNTA MUDOU DE SENTIDO EM 22/09/2026 — RADIO-AFOGADO-01, e a
        mudança foi medida no aparelho dela.** Até aqui este método respondia
        *"a ponte está no ar AGORA?"*, e isso estava certo enquanto a ponte era
        permanente. Ela deixou de ser: agora só sobe com alguém tocando, porque
        de pé em silêncio ela afogava o rádio e derrubava três dos quatro
        controles da mesa.

        Com o sentido velho, o produto travava num laço fechado — e ele
        apareceu no diário dela no minuto seguinte à instalação, `som_no_sem_
        rota` a cada cinco segundos:

            o nó de som só nasce com rota  →  a rota só existe com a ponte de
            pé  →  a ponte só sobe se alguém tocar NO NÓ  →  o nó não existe.

        Então a resposta honesta de hoje é *"há caminho"*, e ela tem três
        partes, nesta ordem:

        1. a ponte está de pé — o caminho não é promessa, é fato;
        2. o `subir()` FALHOU há pouco (:data:`RECUSA_DA_PONTE_S`) — aí não há
           caminho, e o nó some com a frase honesta em vez de engolir áudio;
        3. esta máquina consegue subir a ponte — `a_ponte_do_radio_pode_subir`
           responde pela `libopus` e `ha_gravador_de_monitor` pelo `pw-record`
           / `parec`. Com os dois, há caminho, e ele se abre em cerca de dois
           segundos quando o primeiro som chegar; sem qualquer um deles a
           ponte não tem como subir NUNCA, e publicar o nó seria o sumidouro.

        **ISTO NÃO É O `lambda: True` OTIMISTA que a doutrina velha proibia.**
        Aquele dizia *sim* sem perguntar nada a ninguém; este pergunta à
        máquina e à última tentativa. O que a régua do sumidouro trava — que
        todo `module-null-sink` publicado tenha por onde entregar — continua
        de pé: no rádio quem entrega é a ponte, e a ponte sobe quando houver o
        que entregar.
        """
        ponte = self._pontes.get(uniq)
        if ponte is not None:
            return ponte.esta_de_pe
        quando = self._ponte_recusada.get(uniq)
        if quando is not None:
            if time.monotonic() - quando < RECUSA_DA_PONTE_S:
                return None
            self._ponte_recusada.pop(uniq, None)
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            a_ponte_do_radio_pode_subir,
            ha_gravador_de_monitor,
        )

        pode, _porque = a_ponte_do_radio_pode_subir()
        if not pode or not ha_gravador_de_monitor():
            return None
        return lambda: True

    def _renovar_o_rotulo_da_haptica(self, endpoint: Any) -> None:
        """O «Háptica do Controle N» segue o número — e NUNCA com jogo aberto.

        A-HAPTICA-TEM-NOME-DE-CONTROLE-01 (24/09/2026), de volta com a
        A-HAPTICA-E-POR-APARELHO-01 (02/10): o nó é do aparelho, e o número
        dele anda com a mesa. A regra de QUANDO o rótulo envelhece é a do
        alto-falante (``dualsense_bt_audio.rotulo_envelheceu``), e renomear é
        republicar (``EndpointDeHaptica.renovar_o_rotulo``). A guarda é mais
        dura que a do nó do som, porque este nó é o que a háptica do jogo usa
        (:meth:`_a_haptica_esta_em_uso`): republicar tira o endpoint e o
        devolve, e o GE conta cada entrada e saída de endpoint Sony como
        hotplug. Se o rótulo renovado com o fluxo aberto quebra o jogo é o
        passo 0 da sprint, e é de bancada; até lá, o rótulo espera o jogo
        fechar, como em 24/09.

        Nunca levanta, e só pergunta alguma coisa ao servidor ou ao ``/proc``
        quando o rótulo de fato envelheceu — o caso raro, no número que anda.
        """
        envelheceu = getattr(endpoint, "rotulo_envelheceu", None)
        renovar = getattr(endpoint, "renovar_o_rotulo", None)
        if not callable(envelheceu) or not callable(renovar):
            return
        try:
            if not envelheceu():
                return
            if self._a_haptica_esta_em_uso(endpoint):
                logger.debug("haptica_rotulo_velho_espera_o_jogo_fechar")
                return
            renovar()
        except Exception:  # nunca derruba a volta
            logger.debug("haptica_rotulo_nao_renovou", exc_info=True)
        # NEM A VOLTA SUBIU: o nó não está no servidor, e quem nasce é a
        # próxima volta, pelo caminho de sempre.
        if getattr(endpoint, "module_id", "") is None:
            self._endpoints.pop(str(getattr(endpoint, "marca", "") or ""), None)

    def _a_haptica_esta_em_uso(self, endpoint: Any) -> bool:
        """Há jogo usando — ou podendo usar — o endpoint de háptica agora?"""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            sink_esta_tocando,
        )

        nome = str(getattr(endpoint, "nome", "") or "")
        if nome and nome in {self._endpoint_da_ponte.get(u) for u in self._pontes}:
            return True
        if sink_esta_tocando(nome, na_duvida=True):
            return True
        return self._ha_jogo_aberto()

    def _ha_jogo_aberto(self) -> bool:
        """Algum processo da máquina é um jogo, pelo ambiente e não pelo nome.

        É a pergunta de ``quem_o_jogo_le.pids_de_jogo``, e ela não depende de
        lista de jogos nem de lançador.
        """
        from hefesto_dualsense4unix.integrations.quem_o_jogo_le import pids_de_jogo

        try:
            return bool(pids_de_jogo())
        except Exception:  # pragma: no cover - defensivo: na dúvida, há jogo
            return True

    def _aparelhos_da_mesa(self, controles: list[Any]) -> dict[str, str]:
        """``{uniq: marca}`` de cada DualSense da mesa. Um aparelho por controle.

        A-HAPTICA-E-POR-APARELHO-01, 02/10/2026: a marca é a do aparelho
        (``dualsense_bt_audio.marca_do_aparelho``), e não o número dele. De
        28/09 a 02/10 aqui morava o ``_lugares_da_mesa``, que sentava cada
        controle num dos quatro lugares pelo número do dono; o número anda com
        a mesa, e a háptica do aparelho não anda junto. Quem não dá identidade
        (sem ``uniq`` de seis hex) fica fora: um endpoint anônimo seria de dois.
        """
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            marca_do_aparelho,
        )

        postos: dict[str, str] = {}
        tomadas: set[str] = set()
        for uniq in sorted({str(getattr(c, "uniq", "") or "") for c in controles} - {""}):
            marca = marca_do_aparelho(uniq)
            if marca and marca not in tomadas:
                postos[uniq] = marca
                tomadas.add(marca)
        self._aparelho_de = MappingProxyType(dict(postos))
        return postos

    def _endpoint_de(self, uniq: str) -> Any:
        """O endpoint do aparelho deste controle, ou ``None``."""
        marca = self._aparelho_de.get(uniq)
        return None if marca is None else self._endpoints.get(marca)

    def _aparelhos_de_pe(self, aparelho_de: Mapping[str, str]) -> dict[str, str]:
        """``{marca: uniq}`` dos endpoints que ficam de pé nesta volta.

        Um por DualSense da mesa, em qualquer transporte; e o do aparelho que
        SAIU fica enquanto um jogo toca nele: o nó que some debaixo do jogo
        leva a háptica da partida junto (a decisão dela de 08/09, «nó que some
        quebra o jogo que o escolheu»). Servidor mudo é «toca» — na dúvida, o
        nó fica.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import sink_esta_tocando

        de_pe = {marca: uniq for uniq, marca in aparelho_de.items()}
        for marca, endpoint in list(self._endpoints.items()):
            if marca in de_pe:
                continue
            if sink_esta_tocando(str(getattr(endpoint, "nome", "") or ""), na_duvida=True):
                de_pe[marca] = str(getattr(endpoint, "uniq", "") or "")
        return de_pe

    def _avisar_quem_o_jogo_nao_conhece(self, marca: str) -> None:
        """O endpoint que nasce com um jogo tocando: o registro do lançamento não o tem.

        A-HAPTICA-E-POR-APARELHO-01, item 5 — o preço que ela aceitou na
        pergunta [27]: o device KS se grava no lançamento, e o aparelho que
        chega com o jogo aberto ganha um endpoint que o jogo não conhece até
        reabrir. Uma linha por aparelho e partida, para a bancada e o doctor
        saberem por quê. A partida é a da volta anterior: algum jogo dono de
        fluxo nos endpoints (:meth:`_donos_dos_fluxos`).
        """
        if not self._donos_da_volta or marca in self._sem_registro_no_jogo:
            return
        self._sem_registro_no_jogo = self._sem_registro_no_jogo | {marca}
        logger.info("haptica_aparelho_sem_registro_no_jogo", controle=marca)

    def _o_cabo(self) -> Any:
        """O dono dos laços do cabo, criado na primeira vez que se pede."""
        if self._cabo is None:
            from hefesto_dualsense4unix.integrations.haptica_do_cabo import HapticaDoCabo

            self._cabo = HapticaDoCabo()
        return self._cabo

    # -- a háptica fina do rumble (NO-MODO-XBOX-TUDO-FUNCIONA-01, parte 4) --

    def levar_o_rumble(
        self,
        uniq: str,
        fraco: int,
        forte: int,
        *,
        reaplicar: Callable[[], object] | None = None,
    ) -> bool:
        """O rumble de um pad sem háptica vira háptica no endpoint do aparelho de ``uniq``.

        NO-MODO-XBOX-TUDO-FUNCIONA-01, parte 4, 29/09/2026. Quem chama é o
        ``rumble_sink`` do pad ``uinput`` (``gamepad.apply_game_rumble``), no
        fio da vibração dele: aqui nada espera. O par já vem com o degrau e a
        barra de cada motor aplicados.

        Devolve ``True`` quando a háptica LEVA o rumble até o controle — o
        tocador do aparelho de pé, e o laço do cabo com os motores abertos ou a
        ponte do rádio lendo aquele endpoint. Aí quem chama deixa os motores do
        HID em zero: o bit que pede rumble ao firmware cala a háptica por áudio
        (``docs/protocol/dualsense-referencia-canonica.md``, «O bit que MATA os
        haptics»). ``False`` = o HID segue levando, como sempre levou; o tocador
        sobe mesmo assim, e a volta reaplica quando o caminho abrir
        (:meth:`_conferir_o_rumble`). Nada se perde na troca.

        Não converte (e cala o tocador de quem pediu) quando o aparelho não tem
        endpoint, quando o JOGO toca naquele endpoint (a háptica é a dele) e,
        pelo rádio, quando o alto-falante do controle está tocando.
        """
        if not self._tocadores and not (fraco or forte):
            return False
        chave = self._chave_do_rumble(uniq)
        quer = chave is not None and self._quer_a_haptica_fina(chave)
        marca = self._aparelho_de.get(chave) if chave is not None else None
        for outro, tocador in list(self._tocadores.items()):
            if any(tocador.nivel) and _mesmo_controle(tocador.dono, uniq) and (
                not quer or outro != marca
            ):
                tocador.calar()
        if not quer or chave is None or marca is None:
            self._esquecer_o_rumble(uniq)
            return False
        endpoint = self._endpoints.get(marca)
        self._tocador_do_aparelho(marca).levar(
            fraco, forte, sink=str(getattr(endpoint, "nome", "") or ""), dono=chave
        )
        retrato = self._retrato_do_rumble(chave)
        with self._trava_do_rumble:
            vivos = {u: v for u, v in self._rumble_vivo.items() if u != chave}
            if fraco or forte:
                vivos[chave] = (reaplicar, retrato)
            self._rumble_vivo = MappingProxyType(vivos)
        return retrato[2]

    def testar_a_haptica(self, uniq: str, ligado: bool) -> dict[str, Any]:
        """O botão «Háptica» da aba Vibração: o par de teste no tocador DESTE controle.

        A-ABA-VIBRACAO-TEM-O-SENSOR-HAPTICO-E-DOIS-TESTES-01 (a resposta [24]
        dela, 29/09/2026). O teste é o rumble convertido de sempre
        (:meth:`levar_o_rumble`) com o par :data:`PAR_DO_TESTE_DA_HAPTICA`: a
        mesma porta, o mesmo caminho (o laço do cabo, a ponte do rádio em
        háptica) e as mesmas recusas — o endpoint com fluxo de jogo, o
        alto-falante tocando pelo rádio, o ganho em 0. Nessas, o tocador não
        toca, e a resposta diz ``leva: False``; a luz «no ar» é quem diz se
        chegou.

        ``ligado`` falso cala o tocador. Ligar de novo é o rebate: a janela o
        manda a cada segundo, e o teste que ninguém rebate solta sozinho
        (:meth:`_conferir_o_teste_da_haptica`). Nunca levanta.
        """
        chave = self._chave_do_rumble(uniq)
        if chave is None:
            return {
                "status": "sem_controle",
                "motivo": "este controle não está na mesa, ou não tem háptica",
            }
        if not ligado:
            self._soltar_o_teste_da_haptica(chave)
            return {"status": "ok", "uniq": chave, "ligado": False, "leva": False}
        with self._trava_do_rumble:
            self._teste_da_haptica = MappingProxyType(
                {**self._teste_da_haptica, chave: time.monotonic()}
            )
        leva = self.levar_o_rumble(chave, *PAR_DO_TESTE_DA_HAPTICA)
        # A VOLTA AGORA, e não no relógio: ela abre o caminho (o laço do cabo,
        # a ponte do rádio) e escreve o ganho de agora na placa do cabo — o
        # arraste da «Sensor Háptico» rebate o teste, e a mão sente na hora.
        self._acordar_a_volta()
        return {
            "status": "ok",
            "uniq": chave,
            "ligado": True,
            "leva": bool(leva),
            "par": list(PAR_DO_TESTE_DA_HAPTICA),
        }

    def _soltar_o_teste_da_haptica(self, chave: str) -> None:
        """O tocador deste controle cala, e o teste sai da lista."""
        with self._trava_do_rumble:
            self._teste_da_haptica = MappingProxyType(
                {u: t for u, t in self._teste_da_haptica.items() if u != chave}
            )
        self.levar_o_rumble(chave, 0, 0)

    def _conferir_o_teste_da_haptica(self) -> None:
        """O teste que a janela deixou de rebater solta: o tocador não fica preso ligado.

        É o par do teto do rumble fixado (``rumble.TETO_DO_RUMBLE_FIXADO_S``),
        e pelo mesmo motivo: a janela que fecha sem o «Parar» (ou morre) não
        pode deixar o controle vibrando. A conta é na volta, que roda ao menos
        a cada :data:`RECONCILIA_S`.
        """
        if not self._teste_da_haptica:
            return
        from hefesto_dualsense4unix.daemon.subsystems.rumble import TETO_DO_RUMBLE_FIXADO_S

        agora = time.monotonic()
        for chave, quando in list(self._teste_da_haptica.items()):
            if agora - quando > TETO_DO_RUMBLE_FIXADO_S:
                logger.info("haptica_teste_solto_sem_rebate", controle=self._aparelho_de.get(chave))
                self._soltar_o_teste_da_haptica(chave)

    def _retrato_do_rumble(self, chave: str) -> tuple[str | None, bool, bool]:
        """``(marca, quer a háptica fina, a háptica leva)`` deste controle agora."""
        return (
            self._aparelho_de.get(chave),
            self._quer_a_haptica_fina(chave),
            self._a_haptica_leva(chave),
        )

    def _esquecer_o_rumble(self, uniq: str) -> None:
        with self._trava_do_rumble:
            if any(_mesmo_controle(u, uniq) for u in self._rumble_vivo):
                self._rumble_vivo = MappingProxyType({
                    u: v for u, v in self._rumble_vivo.items() if not _mesmo_controle(u, uniq)
                })

    def _chave_do_rumble(self, uniq: str) -> str | None:
        """O ``uniq`` na grafia da mesa (a chave de :attr:`_aparelho_de`), pelos dígitos."""
        if uniq in self._aparelho_de:
            return uniq
        for chave in list(self._aparelho_de):
            if _mesmo_controle(chave, uniq):
                return chave
        return None

    def _tocador_do_aparelho(self, marca: str) -> Any:
        """O tocador do aparelho, criado no primeiro rumble que o pede."""
        tocador = self._tocadores.get(marca)
        if tocador is not None:
            return tocador
        from hefesto_dualsense4unix.integrations import endpoint_de_haptica

        with self._trava_do_rumble:
            tocador = self._tocadores.get(marca)
            if tocador is None:
                tocador = endpoint_de_haptica.TocadorDoRumble(
                    marca, ao_mudar=self._acordar_a_volta
                )
                self._tocadores = MappingProxyType({**self._tocadores, marca: tocador})
        return tocador

    def _parar_o_tocador(self, marca: str) -> None:
        """O tocador sai ANTES do endpoint do aparelho, como o laço e a ponte."""
        tocador = self._tocadores.get(marca)
        if tocador is None:
            return
        with self._trava_do_rumble:
            self._tocadores = MappingProxyType(
                {n: t for n, t in self._tocadores.items() if n != marca}
            )
        tocador.parar()

    def _quer_a_haptica_fina(self, chave: str) -> bool:
        """O aparelho tem endpoint, o jogo não toca nele, e a háptica dele não está em 0."""
        marca = self._aparelho_de.get(chave)
        if marca is None or marca in self._aparelhos_com_jogo or chave in self._radio_com_som:
            return False
        endpoint = self._endpoints.get(marca)
        return bool(
            endpoint is not None and GANHO.pct(chave) > 0  # em 0, o HID leva o rumble
            and getattr(endpoint, "module_id", None) is not None
            and getattr(endpoint, "nome", "")
        )

    def _recebe_o_rumble(self, uniq: str) -> bool:
        """O tocador do aparelho deste controle está de pé tocando o rumble DELE.

        É o terceiro lado do portão (o laço do cabo e a ponte do rádio): o jogo
        que só manda rumble já disse a quem ele vai — o pad daquele jogador —,
        e a escolha (b) dela vale para o áudio que o jogo ESPELHA nos quatro.
        """
        if not self._tocadores:
            return False
        chave = self._chave_do_rumble(uniq)
        if chave is None or not self._quer_a_haptica_fina(chave):
            return False
        marca = self._aparelho_de.get(chave)
        tocador = self._tocadores.get(marca) if marca is not None else None
        return bool(tocador is not None and tocador.vivo and tocador.dono == chave)

    def _a_haptica_leva(self, chave: str) -> bool:
        """O caminho do tocador ao controle está de pé AGORA, e é o deste controle."""
        if not self._recebe_o_rumble(chave):
            return False
        marca = self._aparelho_de.get(chave)
        cabo = self._cabo
        if cabo is not None and marca is not None:
            rota = cabo.aparelhos().get(marca)
            if rota is not None and getattr(rota, "dono", "") == chave:
                return cabo.portao(marca) is True
        ponte = self._pontes.get(chave)
        endpoint = self._endpoints.get(marca) if marca is not None else None
        if ponte is None or endpoint is None:
            return False
        if self._modo_da_ponte.get(chave) != "haptica":
            return False
        if self._endpoint_da_ponte.get(chave) != getattr(endpoint, "nome", None):
            return False
        de_pe = getattr(ponte, "esta_de_pe", None)
        try:
            return bool(de_pe()) if callable(de_pe) else False
        except Exception:
            return False

    def _ver_quem_toca_nos_endpoints(self) -> None:
        """Quem toca nos endpoints além dos nossos tocadores — só com tocador na mesa.

        Sem tocador nenhum, nada se pergunta: é o caminho de todo modo que não
        é o do pad sem háptica, e ele não paga nada por esta cura.
        """
        if not self._tocadores:
            self._clientes_do_rumble = frozenset()
            return
        from hefesto_dualsense4unix.integrations.endpoint_de_haptica import (
            fluxos_nos_endpoints,
        )

        nomes = {
            marca: str(getattr(ep, "nome", "") or "")
            for marca, ep in list(self._endpoints.items())
        }
        try:
            lido = fluxos_nos_endpoints([n for n in nomes.values() if n])
        except Exception as exc:  # a pergunta nunca derruba a volta
            logger.debug("haptica_fina_fluxos_ilegiveis", err=str(exc))
            lido = None
        if lido is None:
            return
        nossos, com_outro = lido
        self._clientes_do_rumble = nossos
        self._aparelhos_com_jogo = frozenset(
            marca for marca, nome in nomes.items() if nome and nome in com_outro
        )

    def _conferir_os_tocadores(self, aparelho_de: Mapping[str, str]) -> None:
        """O tocador cujo dono saiu da mesa cala: não há controle a quem levá-lo."""
        for marca, tocador in list(self._tocadores.items()):
            dono = tocador.dono
            if dono and any(tocador.nivel) and aparelho_de.get(dono) != marca:
                tocador.calar()

    def _conferir_o_rumble(self) -> None:
        """Quem tem rumble vivo e viu o caminho abrir, fechar ou trocar reaplica.

        O ``rumble_sink`` só é chamado quando o JOGO muda o pedido; o caminho da
        háptica abre DEPOIS (o tocador sobe, a volta abre o portão). Sem isto o
        rumble que já estava tocando seguiria pelo HID até o jogo mudar de
        ideia — e, ao contrário, o que ia pela háptica ficaria mudo quando o
        caminho caísse.
        """
        from hefesto_dualsense4unix.daemon.battery_journal import mascarar_endereco

        for chave, (reaplicar, antes) in dict(self._rumble_vivo).items():
            agora = self._retrato_do_rumble(chave)
            if agora == antes or not callable(reaplicar):
                continue
            logger.info(
                "haptica_fina_do_rumble_mudou",
                uniq=mascarar_endereco(chave),
                controle=agora[0],
                leva=agora[2],
            )
            try:
                reaplicar()
            except Exception as exc:  # a volta nunca cai por um reaplicar
                logger.debug("haptica_fina_reaplicar_falhou", err=str(exc))

    def _o_jogo_manda_nos_motores(self) -> bool:
        """No Modo Nativo o dono dos motores é o jogo, no cabo E no rádio.

        Uma pergunta só para os dois transportes, e quem responde é o dono das
        três portas do rumble (``rumble.modo_nativo_manda_nos_motores``). O
        laço do cabo a faz desde 29/09 (NO-MODO-XBOX-TUDO-FUNCIONA-01, parte
        4); a ponte do rádio passou a fazê-la em 02/10
        (NO-NATIVO-PELO-RADIO-O-JOGO-E-DONO-DOS-MOTORES-01): no Nativo o daemon
        só lê o físico do posto, e ninguém via os secundários mexerem.
        """
        from hefesto_dualsense4unix.daemon.subsystems import rumble

        return rumble.modo_nativo_manda_nos_motores(getattr(self, "_daemon", None))

    def _casar_o_cabo(
        self,
        controles: list[Any],
        jogando: set[str],
        motores: list[str] | None,
    ) -> None:
        """Um laço por DualSense no cabo, do endpoint do aparelho à placa dele.

        A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01, itens 3 e 4, pelo aparelho desde
        a A-HAPTICA-E-POR-APARELHO-01 (02/10/2026). Os motores do laço
        (os traseiros) abrem só para quem joga — a escolha (b) dela, a mesma
        do rádio; a frente (o alto-falante) passa sempre. A placa é a do dono
        (``alto_falante_bt.sink_do_controle``), e só vale se for uma placa de
        quatro canais que não é nossa (``motores``, a leitura da volta): sem
        ela o controle segue pela placa, sem laço, e o registro lhe dá o bloco
        pelo ``BUSNUM-DEVNUM`` (``audio_ks_dualsense.controles_do_registro``).

        ``motores`` ``None`` é o servidor que não respondeu: o laço de quem
        segue no cabo FICA como está — ele é um processo do
        PipeWire, e não depende do ``pipewire-pulse`` que travou. Só cai o de
        quem saiu do cabo, que o ``/sys`` diz sem perguntar ao servidor.

        **NO MODO NATIVO O DONO DOS MOTORES É O JOGO** (NO-MODO-XBOX-TUDO-
        FUNCIONA-01, parte 4, 29/09/2026): o co-op desmonta e o daemon só lê o
        físico do posto (o limite de ``quem_mexe.py``), e a (b) fechava os
        motores dos secundários, que vibravam direto pela placa até 28/09. O
        laço abre os motores de todo controle no cabo, e quem responde é o
        mesmo dono das três portas do rumble
        (``rumble.modo_nativo_manda_nos_motores``), a cada volta.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            e_radio,
            sink_do_controle,
            sink_esta_tocando,
        )
        from hefesto_dualsense4unix.integrations.endpoint_de_haptica import MARCA_DO_NOME
        from hefesto_dualsense4unix.integrations.haptica_do_cabo import (
            RotaDoCabo,
            alvo_do_no,
        )

        o_jogo_manda = self._o_jogo_manda_nos_motores()

        def _abre(uniq: str) -> bool:
            return o_jogo_manda or uniq.lower() in jogando or self._recebe_o_rumble(uniq)

        na_mesa = [str(getattr(c, "uniq", "") or "") for c in controles]
        na_mesa = [u for u in na_mesa if u]
        no_cabo = [
            str(getattr(c, "uniq", "") or "")
            for c in controles
            if not e_radio(str(getattr(c, "transporte", "") or ""))
        ]
        cabo = self._cabo
        if not [u for u in no_cabo if u] and (cabo is None or not cabo.aparelhos()):
            self._casar_os_ouvidos_das_placas({})
            return
        rotas: dict[str, Any] = {}
        abertos: set[str] = set()
        if motores is None:
            antes = cabo.aparelhos() if cabo is not None else {}
            for marca, rota in antes.items():
                dono = str(getattr(rota, "dono", "") or "")
                if dono in no_cabo and self._aparelho_de.get(dono) == marca:
                    rotas[marca] = rota
                    if _abre(dono):
                        abertos.add(marca)
            logger.debug("haptica_do_cabo_servidor_mudo", ficam=sorted(rotas))
            self._o_cabo().casar(rotas, abertos)
            return
        placas = set(motores)
        ouvir: dict[str, str] = {}
        for uniq in no_cabo:
            placa = sink_do_controle(uniq, na_mesa) if uniq else ""
            if not placa or placa not in placas or MARCA_DO_NOME in placa:
                continue
            # A PLACA É OUVIDA COM OU SEM LAÇO: o jogo que toca nela pelo nome
            # também vibra este controle (a luz «no ar», :meth:`haptica_no_ar`).
            ouvir[uniq] = placa
            marca = self._aparelho_de.get(uniq)
            endpoint = self._endpoint_de(uniq)
            if marca is None or endpoint is None or getattr(endpoint, "module_id", None) is None:
                continue
            captura, destino = alvo_do_no(str(endpoint.nome)), alvo_do_no(placa)
            if not captura or not destino:
                continue
            rotas[marca] = RotaDoCabo(
                captura=captura, destino=destino, origem=str(endpoint.nome), dono=uniq
            )
            este_joga = _abre(uniq)
            if este_joga:
                abertos.add(marca)
            # O PORTÃO PERGUNTA AO OUVIDO (A-HAPTICA-POR-AUDIO-E-O-ALTO-FALANTE-
            # CHEGAM-AO-RADIO-01): no cabo ninguém escuta o endpoint (o laço
            # soma na placa, sem ponte), e o «não sei» do ouvido cai no fluxo,
            # como antes.
            sinal = self._o_no_tem_sinal(str(endpoint.nome))
            self._vigiar_o_portao(
                uniq,
                fechado=(
                    sink_esta_tocando(str(endpoint.nome)) if sinal is None else sinal
                ) and not este_joga,
                controles=controles,
            )
        self._o_cabo().casar(rotas, abertos)
        self._casar_os_ouvidos_das_placas(ouvir)

    def _casar_os_ouvidos_das_placas(self, ouvir: Mapping[str, str]) -> None:
        """Um ouvido por controle no cabo, na placa dele; quem saiu ou trocou de placa desce.

        O-GANHO-DA-HAPTICA-TEM-DONO-01, item 8. Quem desce, desce ANTES de o
        novo subir: dois gravadores com o mesmo rótulo confundiriam a
        conferência do alvo.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import OuvidoDaPlaca

        vivos = dict(self._ouvidos_das_placas)
        for uniq, ouvido in list(vivos.items()):
            if ouvir.get(uniq) != getattr(ouvido, "placa", None) or not ouvido.vivo:
                vivos.pop(uniq)
                ouvido.descer()
        for uniq, placa in ouvir.items():
            if uniq in vivos:
                continue
            ouvido = OuvidoDaPlaca(placa=placa, uniq=uniq)
            if ouvido.subir():
                vivos[uniq] = ouvido
            else:
                logger.debug("haptica_ouvido_da_placa_sem_fonte", motivo=ouvido.motivo)
        self._ouvidos_das_placas = MappingProxyType(vivos)

    def haptica_no_ar(self, uniq: str) -> bool:
        """Há háptica chegando a ESTE controle agora? LEITURA pura, nunca levanta.

        O-GANHO-DA-HAPTICA-TEM-DONO-01, item 8 (02/10/2026): é a luz «no ar»
        da linha da háptica. O sinal é o do :data:`OUVIDO`, o dono do «tem
        sinal agora?»: no cabo, o monitor da placa do controle
        (:meth:`_casar_os_ouvidos_das_placas`); no rádio, o endpoint que a
        ponte EM HÁPTICA lê. A ponte no som não leva háptica, e a háptica com o
        ganho em 0 não mexe o motor: as duas respondem ``False``.
        """
        try:
            if GANHO.fator(uniq) <= 0:
                return False
            for dono, ouvido in dict(self._ouvidos_das_placas).items():
                if _mesmo_controle(dono, uniq):
                    return self._o_no_tem_sinal(str(ouvido.placa)) is True
            for dono, modo in dict(self._modo_da_ponte).items():
                if not _mesmo_controle(dono, uniq):
                    continue
                lendo = self._endpoint_da_ponte.get(dono) or ""
                return modo == "haptica" and bool(lendo) and (
                    self._o_no_tem_sinal(lendo) is True
                )
        except Exception:  # a leitura da tela nunca derruba o subsystem
            logger.debug("haptica_no_ar_ilegivel", exc_info=True)
        return False

    def _o_ganho_nas_placas(self, controles: list[Any], placas: list[str]) -> set[str]:
        """Relê o ganho do perfil e o escreve na placa de cada controle no cabo.

        Devolve as placas com dono (:mod:`daemon.ganho_da_haptica`).
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import e_radio

        GANHO.ler_do_daemon(getattr(self, "_daemon", None))
        na_mesa = [u for u in (str(getattr(c, "uniq", "") or "") for c in controles) if u]
        no_cabo = [
            str(getattr(c, "uniq", "") or "")
            for c in controles
            if not e_radio(str(getattr(c, "transporte", "") or ""))
        ]
        return GANHO.escrever_nas_placas(no_cabo, na_mesa, placas)

    def _avisar_ancoras_que_faltam(self, faltam: int, aparelhos: int) -> None:
        """O aparelho sem âncora USB fica sem endpoint — e diz isso.

        **POR APARELHO DESDE 02/10/2026** (A-HAPTICA-E-POR-APARELHO-01; de 28/09
        a 02/10 a conta era por lugar): um endpoint por DualSense da mesa, nos
        dois transportes. O controle sem âncora segue pela placa no cabo e fica
        sem vibração no rádio.

        **INSTALL-UNIVERSAL, 18/09/2026.** O endpoint da háptica precisa de uma
        âncora por controle (um aparelho USB com interface e sem placa de som),
        e o :func:`distribuir_ancoras` só entrega enquanto houver: o que sobra
        era pulado por um ``continue`` mudo. Num desktop sobram âncoras; num
        notebook com a mesa de quatro, podem faltar — e a vibração de um
        jogador sumia sem rastro.

        O aviso sai **na mudança**, porque esta volta roda a cada
        :data:`RECONCILIA_S`, e um aviso por volta encheria o journal. Nada vai
        para a tela (a dívida é nossa, não dela): o ``doctor.sh`` conta as
        mesmas âncoras e diz o gesto.
        """
        if faltam == self._faltam_ancoras:
            return
        if faltam > 0:
            logger.warning("haptica_sem_ancora", faltam=faltam, aparelhos=aparelhos)
        else:
            logger.info("haptica_ancoras_bastam", aparelhos=aparelhos)
        self._faltam_ancoras = faltam

    def _quem_o_jogo_le(self, controles: list[Any]) -> set[str]:
        """Os ``uniq`` (em minúsculas) cujo evdev algum processo de jogo segura. PISTA, NÃO VOTO.

        QUEM-JOGA-E-QUEM-VIBRA-01 (20/09) fez disto o voto do portão da
        háptica. A A-HAPTICA-QUEM-JOGA-02 (26/09) o tirou de lá: o GE não segura
        evdev de DualSense nenhum, e em 21/09 o evdev deixou os QUATRO entrarem
        num jogo de um jogador. **E DESDE 28/09 A PARTIDA TAMBÉM NÃO SAI DAQUI**
        (A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01): quem a abre é o dono
        do fluxo no endpoint (:meth:`_quem_mexeu_na_partida`), e esta
        varredura de ``/proc`` deixou de rodar a cada volta. Ela roda só quando
        a linha ``haptica_portao_fechado`` vai sair (:meth:`_vigiar_o_portao`),
        para dizer o que o jogo segura — é por ela que o detentor de 21/09, se
        voltar, aparece no diário.

        Devolve conjunto VAZIO quando não há jogo, quando `/proc` não se lê, ou
        quando o que o jogo abriu não se traduz em controle nenhum.

        A lista de físicos vem de TODOS os controles da mesa, e não só dos do
        rádio: com máscara, o evdev que o jogo seguraria é o do vpad, e quem o
        alimenta pode ser o do cabo. Quem diz QUEM ALIMENTA cada vpad é o
        co-op, e não a forja do MAC (A-HAPTICA-SEGUE-QUEM-ALIMENTA-O-VPAD-01):
        o MAC diz de quem o vpad nasceu, e o posto troca de mão sem renascer.

        **A pergunta ao co-op tem ``try`` próprio** (A-HAPTICA-QUEM-JOGA-02): ela
        só serve para traduzir o evdev de um vpad, e o erro dela não pode levar
        junto a varredura inteira. Sem tradutor, o vpad não se traduz: nunca se
        chuta um físico.
        """
        from hefesto_dualsense4unix.integrations.quem_o_jogo_le import (
            dono_do_vpad_pelo_coop,
            quem_o_jogo_le,
        )

        self._retrato_do_jogo = None
        fisicos = [str(getattr(c, "uniq", "") or "") for c in controles]
        fisicos = [u for u in fisicos if u]
        if not fisicos:
            return set()
        coop = getattr(getattr(self, "_daemon", None), "_coop_manager", None)
        # AUSÊNCIA É RESPOSTA, e ela é registrada nos dois `except`: calar sem
        # dizer por quê é o defeito que esta casa mais persegue.
        dono: Any = None
        try:
            dono = dono_do_vpad_pelo_coop(coop, fisicos)
        except Exception as erro:
            logger.info("haptica_nao_sei_quem_joga", motivo=str(erro))
        try:
            return quem_o_jogo_le(
                fisicos=fisicos, dono_do_vpad=dono, ao_ver_o_jogo=self._ver_o_jogo
            )
        except Exception as erro:
            logger.info("haptica_nao_sei_quem_joga", motivo=str(erro))
            return set()

    def _ver_o_jogo(self, retrato: Any) -> None:
        """Guarda o que a varredura da pista viu do jogo (ver ``_retrato_do_jogo``)."""
        self._retrato_do_jogo = retrato

    def _donos_dos_fluxos(self) -> frozenset[str] | None:
        """Os clientes do servidor de som que tocam nos endpoints de háptica. ``None`` = não sei.

        A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01: a partida é o dono do
        fluxo no endpoint, e não qualquer processo com
        ``STEAM_COMPAT_DATA_PATH`` no ambiente. Um processo auxiliar da Steam
        (o ``run`` do GE-Proton) não abre fluxo no endpoint de controle
        nenhum, e por isso não abre partida. Sem endpoint não há de quem
        perguntar: a resposta é vazia, e não «não sei».
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import donos_dos_fluxos

        nomes = [str(getattr(ep, "nome", "") or "") for ep in self._endpoints.values()]
        nomes = [n for n in nomes if n]
        if not nomes:
            return frozenset()
        try:
            donos = donos_dos_fluxos(nomes)
        except Exception as erro:  # a pergunta nunca derruba a volta
            logger.debug("haptica_donos_ilegiveis", err=str(erro))
            return None
        # O TOCADOR DO RUMBLE NÃO É JOGO (NO-MODO-XBOX-TUDO-FUNCIONA-01): quem o
        # separa é :meth:`_ver_quem_toca_nos_endpoints`, na mesma volta.
        nossos = self._clientes_do_rumble
        if donos is not None and nossos:
            donos = frozenset(d for d in donos if d not in nossos)
        return donos

    def _clientes_vivos(self, donos: frozenset[Any]) -> frozenset[Any] | None:
        """Dos donos de fluxo de antes, os que seguem conectados ao servidor de som.

        É assim que a partida sabe que o jogo que fechou o fluxo ainda vive (e
        segue a mesma), ou que o dono novo é outro jogo (e a marca zera) — sem
        PID e sem ``/proc``. ``None`` = não sei.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import clientes_conectados

        try:
            conectados = clientes_conectados()
        except Exception as erro:  # a pergunta nunca derruba a volta
            logger.debug("haptica_clientes_ilegiveis", err=str(erro))
            return None
        if conectados is None:
            return None
        return frozenset(d for d in donos if str(d) in conectados)

    def _quem_mexeu_na_partida(self, controles: list[Any]) -> set[str]:
        """Os ``uniq`` (em minúsculas) de quem teve entrada desde que o jogo abriu.

        A-HAPTICA-QUEM-JOGA-01, decisão ``D-2609-QUEM-JOGA-E-QUEM-MEXE``: quem
        joga é o controle FÍSICO que teve entrada — botão, gatilho ou eixo
        fora da zona morta — desde que o jogo abriu. E é a escolha (b) dela de
        27/09 para o jogo que espelha a vibração nos quatro, como o PRAGMATA
        mediu na noite: vibra quem está com o controle na mão, e o controle
        parado na mão não vibra. O laço do daemon marca (``quem_mexe``); aqui
        a volta diz à partida quem é dono de fluxo nos endpoints, e ela abre,
        segue ou fecha (A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01). Sem
        resposta do servidor, a partida fica como está: na dúvida, não mexe.

        Devolve na grafia da lista de controles, a mesma com que o portão
        compara.
        """
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import quem_mexe_de
        from hefesto_dualsense4unix.integrations.quem_o_jogo_le import _digitos

        marcas = quem_mexe_de(getattr(self, "_daemon", None))
        if marcas is None:
            return set()
        donos = self._donos_dos_fluxos()
        self._donos_da_volta = donos
        if donos is not None:
            marcas.acompanhar_o_jogo(donos, vivos=self._clientes_vivos)
        mexeram = marcas.quem_joga()
        if not mexeram:
            return set()
        uniqs = (str(getattr(c, "uniq", "") or "") for c in controles)
        return {u.lower() for u in uniqs if u and _digitos(u) in mexeram}

    def _por_que_o_portao_fecha(self) -> str:
        """O motivo de um controle estar fora de quem joga, pela partida da volta."""
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import marcas_da_partida

        if self._donos_da_volta is None:
            return "nao_sei"
        if marcas_da_partida(getattr(self, "_daemon", None)) is None:
            return "sem_jogo"
        return "nao_mexeu"

    def _vigiar_o_portao(self, uniq: str, *, fechado: bool, controles: list[Any]) -> None:
        """A linha ``haptica_portao_fechado``, SÓ quando o estado anômalo muda.

        A-HAPTICA-QUEM-JOGA-01, a Parte 1: *o portão diz por que fechou*. O
        estado anômalo é o endpoint de háptica daquele controle TOCANDO e o
        controle FORA de quem joga — o PRAGMATA de 26/09 passou sete minutos
        nele sem uma linha no diário. Uma linha por controle quando o estado
        começa ou muda de motivo, com o que o jogo segura (os ``eventN`` e os
        ``hidrawN`` de vpad): com o PRAGMATA, ``evdev_do_jogo=0
        hidraw_de_vpad=2`` teria dito a causa sem ninguém medir. E com a pista
        do evdev (``evdev_le_este``, A-HAPTICA-QUEM-JOGA-02). O repouso
        (endpoint sem fluxo) não loga, e sair do estado também não.

        **A PISTA SÓ SE PERGUNTA AQUI** (A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-
        DO-JOGO-01): a varredura de ``/proc`` roda quando a linha sai, e não a
        cada volta.
        """
        anterior = self._portao_fechado.get(uniq)
        if not fechado:
            if anterior is not None:
                self._portao_fechado = {
                    u: m for u, m in self._portao_fechado.items() if u != uniq
                }
            return
        motivo = self._por_que_o_portao_fecha()
        if anterior == motivo:
            return
        self._portao_fechado = {**self._portao_fechado, uniq: motivo}
        from hefesto_dualsense4unix.daemon.battery_journal import mascarar_endereco

        self._lidos_pelo_evdev = frozenset(self._quem_o_jogo_le(controles))
        evdev, hidraw = self._o_que_o_jogo_segura()
        logger.info(
            "haptica_portao_fechado",
            uniq=mascarar_endereco(uniq),
            motivo=motivo,
            evdev_do_jogo=evdev,
            hidraw_de_vpad=hidraw,
            evdev_le_este=uniq.lower() in self._lidos_pelo_evdev,
        )

    def _o_que_o_jogo_segura(self) -> tuple[int | None, int | None]:
        """``(eventN, hidrawN de vpad)`` que o jogo segura, do retrato da pista.

        ``None`` quando não se sabe — sem retrato, ou o sysfs que não se leu.
        **Nunca levanta**: uma exceção aqui derrubaria a volta inteira por
        causa de uma linha de diário.
        """
        retrato = self._retrato_do_jogo
        if retrato is None:
            return None, None
        try:
            from hefesto_dualsense4unix.integrations.quem_o_jogo_le import hidraws_de_vpad

            return len(retrato.eventos), len(hidraws_de_vpad(retrato.hidraws))
        except Exception as exc:
            logger.debug("haptica_portao_sem_contagem", err=str(exc))
            return None, None

    def _casar_as_pontes(self, controles: list[Any]) -> None:
        """Os endpoints dos aparelhos, a ponte de cada controle no rádio e o laço do cabo.

        Roda na thread de reconciliação, junto com os nós — as duas coisas
        respondem à mesma lista, e separá-las abriria a janela em que o nó
        existe e a ponte não (ou o contrário). ``controles`` são os DualSense
        da mesa nos DOIS transportes: cada um tem o endpoint dele
        (A-HAPTICA-E-POR-APARELHO-01, 02/10/2026).
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            ARRANJO_HAPTICA_032,
            CANAIS_DA_HAPTICA,
            PonteDeSomPorRadio,
            e_radio,
            fonte_do_monitor_do_no,
            garantir_motores_audiveis,
            nome_do_sink,
            rodar_pactl,
            sink_esta_tocando,
            sinks_com_motores,
        )
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            o_microfone_esta_no_ar,
        )
        from hefesto_dualsense4unix.integrations.endpoint_de_haptica import (
            EndpointDeHaptica,
            ancoras,
            distribuir_ancoras,
            endpoints_de_pe,
            varrer_endpoints_orfaos,
        )

        vivos: dict[str, str] = {}
        for c in controles:
            uniq = str(getattr(c, "uniq", "") or "")
            if uniq and e_radio(str(getattr(c, "transporte", "") or "")):
                vivos[uniq] = str(getattr(c, "caminho", "") or "")

        from hefesto_dualsense4unix.integrations.filho_de_som import (
            derrubar_leitor_de_pipe,
        )

        # A QUEDA: a ponte de quem saiu desce AQUI, e `descer()` colhe o
        # gravador dela. Esta função roda ANTES de `gerenciador.reconciliar` em
        # `_reconciliar`, então o `pw-record` já foi colhido quando o nó sai —
        # e a régua `test_o_gravador_da_ponte_morre_antes_do_no.py` pina a
        # ordem (SOM-TRAVA-NA-QUEDA-01, 13/09/2026).
        for uniq in [u for u in self._pontes if u not in vivos]:
            ponte = self._pontes.pop(uniq, None)
            if ponte is not None:
                ponte.descer()
                logger.info("som_ponte_derrubada", uniq=uniq)
        # O APARELHO DE CADA CONTROLE, nos dois transportes — A-HAPTICA-E-POR-
        # APARELHO-01, 02/10/2026. O endpoint é do APARELHO: renumerar a mesa
        # não troca o endpoint, a ponte nem o laço de ninguém.
        aparelho_de = self._aparelhos_da_mesa(controles)
        de_pe_agora = self._aparelhos_de_pe(aparelho_de)
        self._conferir_os_tocadores(aparelho_de)

        # O ENDPOINT DO APARELHO CAI DEPOIS DA PONTE E DO LAÇO, nunca antes: os
        # dois leem o monitor dele, e derrubar o nó primeiro deixaria a leitura
        # pendurada — e o laço cujo alvo some pode ser religado à fonte padrão
        # (SOM-ECO-02). As pontes de quem saiu já desceram acima.
        for marca in [m for m in self._endpoints if m not in de_pe_agora]:
            self._o_cabo().soltar(marca)
            self._parar_o_tocador(marca)
            endpoint = self._endpoints.pop(marca, None)
            if endpoint is not None:
                endpoint.parar()
        # O QUE O PROCESSO ANTERIOR DEIXOU — 18/09/2026, e ele não é teórico:
        # na mesa dela havia VINTE E DOIS `module-null-sink` onde deviam existir
        # quatro. O laço acima só alcança o que ESTE processo criou; o servidor
        # de som é outro processo e sobrevive ao restart do daemon. Sem esta
        # varredura, cada reinício somava mais um nó com o mesmo nome à lista de
        # saídas de som dela. É a mesma classe — e a mesma cura — do canal órfão
        # do microfone (`bt_mic.VarredorDeCanaisOrfaos`). E é ela que derruba,
        # na primeira volta depois do install, os endpoints por lugar de 28/09
        # a 02/10 (``LUGAR<n>`` não é de aparelho nenhum).
        #
        # UMA pergunta ao servidor por volta, e ela serve às duas coisas: à
        # varredura e à semente das âncoras logo abaixo.
        de_pe: dict[str, list[tuple[str, str]]] | None = None
        with contextlib.suppress(Exception):
            de_pe = endpoints_de_pe()
        with contextlib.suppress(Exception):
            varrer_endpoints_orfaos(de_pe_agora, de_pe=de_pe)

        # UMA ÂNCORA POR APARELHO, e ela VIVE ENQUANTO O NÓ EXISTIR. É a mesma
        # decisão dela de 08/09 para o nó do som ("nó que some quebra o jogo
        # que o escolheu"), e aqui ela pesa mais: se o nó cair no meio da
        # partida, a háptica morre com o jogo aberto. Âncoras iguais são
        # ContainerIds iguais, e aí a háptica do jogador 2 iria para o device
        # do jogador 1. A distribuição respeita a POSSE — a memória deste
        # processo e o que o servidor já tem de pé — e só as livres vão para
        # quem não tem (INSTALL-UNIVERSAL, 18/09/2026).
        postas = distribuir_ancoras(
            de_pe_agora, ancoras(), de_pe,
            ja_postas={m: e.ancora for m, e in self._endpoints.items()},
            ocupados=set(aparelho_de.values()),
        )
        for marca, uniq in de_pe_agora.items():
            posta = postas.get(marca)
            atual = self._endpoints.get(marca)
            if atual is not None:
                if posta is None:
                    continue
                if posta.syspath == atual.ancora.syspath:
                    # A ÂNCORA É A MESMA, E O RÓTULO PODE TER ENVELHECIDO: o
                    # «Háptica do Controle N» segue o número do aparelho, e só
                    # renasce sem jogo aberto (`_renovar_o_rotulo_da_haptica`).
                    self._renovar_o_rotulo_da_haptica(atual)
                    continue
                # O APARELHO DA ÂNCORA SAIU DO BARRAMENTO: o nó declara um
                # caminho que o Wine já não resolve, e o próximo jogo não casa
                # o device KS. Troca-se a âncora — mas nunca com o jogo tocando
                # no nó, que morreria no meio da partida; a troca espera a
                # próxima volta sem stream.
                #
                # QUEM DIZ SE O JOGO TOCA É O SERVIDOR, AGORA. O modo da ponte
                # é o da volta ANTERIOR e não basta sozinho: o jogo que abre o
                # nó nesta mesma volta, a fonte da háptica que não subiu (a
                # ponte fica no som com o jogo tocando) e o controle sem ponte
                # (hidraw que não abre, sem libopus) derrubavam o nó com o
                # jogo aberto. E servidor mudo não é "ninguém toca": na
                # dúvida, o nó fica (`na_duvida=True`).
                #
                # LIMITE CONHECIDO: entre o jogo ENUMERAR o endpoint — é aí que
                # ele guarda o ContainerId que sobe do `sysfs.path` — e abrir o
                # primeiro stream, ainda não há sink-input. Se o aparelho da
                # âncora sair nessa janela, o nó troca e o jogo fica com um
                # ContainerId que não casa mais. A janela é estreita; se a
                # bancada mostrar o caso, a guarda passa a ser "nenhum
                # processo Wine/Proton vivo".
                lido = {self._endpoint_da_ponte.get(u) for u in self._pontes}
                if atual.nome in lido or sink_esta_tocando(atual.nome, na_duvida=True):
                    continue
                self._o_cabo().soltar(marca)
                self._parar_o_tocador(marca)
                self._endpoints.pop(marca, None)
                atual.parar()
                logger.info("haptica_endpoint_reancorado", controle=marca, ancora=posta.syspath)
            if posta is None or not uniq:
                continue
            endpoint = EndpointDeHaptica(uniq=uniq, ancora=posta)
            if endpoint.iniciar():
                self._endpoints[marca] = endpoint
                if atual is None and getattr(endpoint, "module_id", None) is not None:
                    self._avisar_quem_o_jogo_nao_conhece(marca)
        if not self._donos_da_volta:
            self._sem_registro_no_jogo = frozenset()
        self._avisar_ancoras_que_faltam(
            sum(1 for m in de_pe_agora if m not in self._endpoints and m not in postas),
            len(de_pe_agora),
        )

        # OS MOTORES DOS SINKS DE 4 CANAIS — HAPTICA-CABO-VOLUME-01 (Z2),
            # 19/09/2026, medido no aparelho dela com o controle NO CABO:
            #
            #     repouso 20  ·  40% (como nasce) 67  ·  100% 1093
            #
            # O WirePlumber dá 40% aos quatro canais de todo sink novo, e os
            # 3-4 são os MOTORES. A vibração dos jogos da Sony saía 16x mais
            # fraca, em qualquer computador. Só os TRASEIROS sobem: os da
            # frente são o alto-falante, e aquele volume é escolha dela.
            #
            # Custa UMA leitura por volta e só escreve quando está abaixo do
            # piso — o valor persiste no WirePlumber, então age uma vez e cala.
        #
        # PELO SERVIDOR, E NÃO PELO `uniq`: a primeira volta desta cura chamou
        # `nome_do_sink(uniq)`, que devolve o null-sink de SOM por rádio — dois
        # canais, motor nenhum. A cura rodou e não mexeu em nada. Os sinks que
        # têm motores vêm de duas origens diferentes (o ALSA, no cabo; e o
        # `EndpointDeHaptica`, para o Wine) e nenhum dos dois nomes se deriva do
        # `uniq`.
        #
        # E O «NÃO SEI» DO SERVIDOR NÃO É «NÃO HÁ PLACA» (conferência de
        # 28/09/2026): `sinks_com_motores` devolve a lista vazia nos dois
        # casos, e o laço do cabo lia a vazia como «a placa saiu» e caía no meio
        # da partida — com o `pipewire-pulse` travado (a queda de um controle
        # pelo rádio já o deixou horas sem responder), o cabo perdia a vibração
        # que não depende dele. Quem pergunta anota se houve resposta; sem
        # resposta, `motores` é ``None`` e o laço fica (:meth:`_casar_o_cabo`).
        motores: list[str] | None = None
        with contextlib.suppress(Exception):
            respostas: list[bool] = []

            def _perguntar(argv: list[str]) -> str | None:
                saida = rodar_pactl(argv)
                respostas.append(saida is not None)
                return saida

            lidos = list(sinks_com_motores(_perguntar))
            motores = lidos if all(respostas) else None
            # O GANHO DA HÁPTICA TEM DONO (O-GANHO-DA-HAPTICA-TEM-DONO-01): a
            # placa de um controle no cabo recebe o ganho dele, e o piso de
            # 100 % fica só para quem não tem dono.
            com_dono = self._o_ganho_nas_placas(controles, lidos)
            for sink_com_motor in placas_do_piso(lidos, com_dono):
                garantir_motores_audiveis(sink_com_motor)

        # QUEM O JOGO ESTÁ LENDO — QUEM-JOGA-E-QUEM-VIBRA-01, 20/09/2026.
        # Correção dela, e ela derrubou a premissa da sprint anterior: *"é um
        # jogo de um player e o erro era que o player 3 tava recebendo a
        # vibração de forma espelhada"*. Antes desta linha, o modo háptica
        # entrava em TODO controle cujo endpoint tivesse stream — e num jogo de
        # um jogador isso não é ninguém além de quem segura o controle.
        #
        # QUEM JOGA É QUEM MEXEU DESDE QUE O JOGO ABRIU — decisão
        # D-2609-QUEM-JOGA-E-QUEM-MEXE, A-HAPTICA-QUEM-JOGA-01 e -02, 26/09/2026.
        # O FD ABERTO PELO JOGO NÃO VOTA, nem o `hidraw` nem o `eventN`: o
        # winedevice do GE segura o hidraw de TODOS os vpads e evdev nenhum (o
        # PRAGMATA de 26/09 ficou sem ninguém), e em 21/09 o evdev pôs os QUATRO
        # em háptica num jogo de um jogador. Um fd diz o que o processo abriu,
        # não quem está jogando.
        #
        # A PARTIDA É O DONO DO FLUXO NO ENDPOINT — A-HAPTICA-DO-RADIO-OBEDECE-
        # AO-SINAL-DO-JOGO-01, 28/09/2026. A varredura do `environ` de todo
        # processo a cada volta saiu: um `run` auxiliar do GE-Proton abria e
        # fechava a partida, e cada abertura zerava quem já jogava. Quem abre a
        # partida é o cliente que toca nos endpoints, perguntado ao servidor de
        # som (`_quem_mexeu_na_partida`); o evdev é pista, e só se pergunta
        # quando a linha do portão fechado sai.
        # O NOSSO TOCADOR NÃO É JOGO (NO-MODO-XBOX-TUDO-FUNCIONA-01, 29/09/2026):
        # antes de a partida perguntar quem toca, a volta separa o fluxo do
        # rumble convertido do fluxo do jogo.
        self._ver_quem_toca_nos_endpoints()
        jogando = self._quem_mexeu_na_partida(controles)

        # Quem saiu da mesa sai da memória do portão: se voltar no mesmo
        # estado, é outro endpoint, e a linha sai de novo. Pela MESA, e não só
        # pelo rádio: o cabo também tem portão desde 28/09.
        self._portao_fechado = {
            u: m for u, m in self._portao_fechado.items() if u in aparelho_de
        }
        # O CABO PASSA PELO ENDPOINT DO APARELHO — A-HAPTICA-E-POR-APARELHO-01:
        # um laço por DualSense no cabo, do endpoint dele à placa, com os
        # motores só para quem joga (a escolha (b) dela, no cabo também); no
        # Modo Nativo, para todos, porque o dono dos motores é o jogo.
        try:
            self._casar_o_cabo(controles, jogando, motores)
        except Exception:  # o laço do cabo nunca derruba a ponte do rádio
            logger.warning("haptica_do_cabo_falhou", exc_info=True)

        governador = self.governador
        esperando: set[tuple[str, str]] = set()
        com_som: set[str] = set()
        # NO MODO NATIVO O JOGO É O DONO DOS MOTORES, TAMBÉM PELO RÁDIO —
        # NO-NATIVO-PELO-RADIO-O-JOGO-E-DONO-DOS-MOTORES-01, 02/10/2026. A
        # mesma pergunta do laço do cabo (:meth:`_o_jogo_manda_nos_motores`):
        # o daemon só lê o físico do posto, e a escolha (b) deixava a ponte dos
        # secundários fora da háptica que o jogo manda a eles. A ponte só
        # escreve o bloco com sinal, e o governador segue contando as vagas.
        o_jogo_manda = self._o_jogo_manda_nos_motores()
        for uniq, caminho in vivos.items():
            # A PONTE QUE TERMINOU SOZINHA SAI DA LISTA — GOVERNADOR-DO-RADIO-01.
            # A fonte secou, a escrita foi recusada, ou o teto de ceder a
            # derrubou (o adaptador parou de escoar). Guardá-la aqui prenderia
            # o controle a uma ponte morta: o `continue` do modo igual abaixo
            # nunca a trocaria, e a ponte sob demanda não religaria.
            morta = self._pontes.get(uniq)
            terminou = getattr(morta, "terminou_sozinha", None)
            if morta is not None and callable(terminou) and terminou() is True:
                self._pontes.pop(uniq, None)
                self._modo_da_ponte.pop(uniq, None)
                logger.info("som_ponte_terminou_sozinha", uniq=uniq, motivo=morta.motivo)
            # O MODO PODE MUDAR COM A PONTE DE PÉ: o jogo abre o endpoint no
            # meio da partida, e é aí que a háptica passa a valer. Quem muda de
            # modo desce e sobe de novo — o escritor é UM SÓ, e trocar o
            # arranjo com a bomba rodando mudaria o corpo do report no meio.
            # A PONTE LÊ O ENDPOINT DO APARELHO (A-HAPTICA-E-POR-APARELHO-01,
            # 02/10/2026; de 28/09 a 02/10, o do lugar): renumerar a mesa não
            # troca a ponte.
            endpoint = self._endpoint_de(uniq)
            # O GATE TEM DOIS LADOS, e os dois precisam ser verdade: o jogo
            # abriu o canal DAQUELE endpoint E aquele controle JOGA — mexeu
            # desde que o jogo abriu. Só o primeiro deixava três controles
            # vibrarem num jogo de um jogador. E o jogo que ESPELHA a vibração
            # nos quatro (o PRAGMATA, medido na noite de 27/09) cai na escolha
            # (b) dela: vibra quem está com o controle na mão.
            #
            # **O CANAL ABERTO É ESCUTA, E NÃO ENVIO** (A-HAPTICA-DO-RADIO-
            # OBEDECE-AO-SINAL-DO-JOGO-01): a ponte lê o monitor o tempo todo e
            # só escreve o bloco que tem sinal nos motores. No menu, com o
            # fluxo aberto e mudo, o rádio fica livre.
            este_joga = o_jogo_manda or uniq.lower() in jogando
            # QUEM FICA COM O RÁDIO É QUEM TEM SINAL, e não quem tem fluxo —
            # A-HAPTICA-POR-AUDIO-E-O-ALTO-FALANTE-CHEGAM-AO-RADIO-01, 29/09/2026.
            # A Forja abre o alto-falante e a háptica de cada jogador em toda
            # sala e toca só num deles: pelo fluxo, a ponte ia à háptica e o
            # canto de O Canto saía mudo pelo rádio (e tocava no cabo). Quem
            # responde é o OUVIDO (:meth:`_o_no_tem_sinal`), com o que a ponte
            # leu dos dois monitores.
            som_sinal = self._o_no_tem_sinal(nome_do_sink(uniq))
            som_toca = som_sinal is True
            # «NÃO SEI» NÃO É «MUDO»: sem ninguém escutando o nó do som (a
            # ponte ainda não subiu, ou espera vaga), vale o fluxo, como antes.
            # Só o fluxo ESCUTADO e mudo deixa de segurar o rádio. O fluxo é
            # perguntado só por quem precisa: custa duas viagens ao `pactl`.
            # O RUMBLE CONVERTIDO É O TERCEIRO LADO (NO-MODO-XBOX-TUDO-FUNCIONA-01,
            # 29/09/2026): o jogo que só manda rumble já disse de quem é. Mas
            # pelo rádio som e vibração são exclusivos, e a háptica fina não
            # tira o alto-falante de ninguém: com ele TOCANDO (com sinal, e não
            # só com o fluxo aberto e mudo), o HID leva.
            pelo_rumble = False
            if not este_joga and self._recebe_o_rumble(uniq):
                if som_toca if som_sinal is not None else sink_esta_tocando(
                    nome_do_sink(uniq), na_duvida=True
                ):
                    com_som.add(uniq)
                else:
                    pelo_rumble = True
            endpoint_aberto = endpoint is not None and sink_esta_tocando(endpoint.nome)
            # A HÁPTICA DESLIGADA NÃO PEDE O RÁDIO (O-GANHO-DA-HAPTICA-TEM-DONO-01,
            # item 6): com o ganho dela em 0 neste controle, a ponte não vai à
            # háptica para mandar silêncio, e o alto-falante fica com o rádio.
            candidata = endpoint_aberto and (este_joga or pelo_rumble) and GANHO.pct(uniq) > 0
            modo = self._modo_pelo_sinal(
                uniq,
                candidata=candidata,
                som_toca=som_toca,
                haptica_toca=(
                    self._o_no_tem_sinal(endpoint.nome) if endpoint is not None else None
                ),
            )
            self._vigiar_o_portao(
                uniq,
                fechado=endpoint_aberto and not este_joga and not pelo_rumble
                and uniq not in com_som,
                controles=controles,
            )
            # A PONTE DO SOM SÓ EXISTE ENQUANTO HÁ SOM — RADIO-AFOGADO-01,
            # 22/09/2026, e é o defeito que tirou três dos quatro controles
            # dela da mesa. Ela escrevia 100 reports de 334 B por segundo por
            # controle (93,75 desde 29/09), tocasse alguém ou não; o teto
            # medido desta mesa é DUAS pontes, e a terceira derrubou os quatro
            # em 11 a 89 segundos. Os números, a corrente até o `EAGAIN` do bluetoothd e
            # a razão de portão nenhum ter visto isto estão em
            # `tests/unit/test_a_ponte_do_som_nao_afoga_o_radio.py`.
            #
            # O PREÇO, MEDIDO NA MESA DELA e não estimado: **255 ms** do
            # primeiro quadro de áudio à ponte de pé. O relógio, do diário de
            # 22/09/2026 às 17:57:45 — som às .967, `vigia_do_modo_acordou_a_
            # volta modo=som` às 45.162 (195 ms) e `som_radio_ponte_de_pe` às
            # 45.221 (mais 59 ms). A queda leva 318 ms.
            #
            # FATO SUBSTITUÍDO: esta linha dizia *"1,45 s … perto de dois
            # segundos"*, estimando por uma subida do diário que incluía o
            # pedido do canal do microfone. Medida sozinha, a ponte sobe em
            # 59 ms — e a diferença entre 255 ms e dois segundos é a diferença
            # entre ela não notar e ela reclamar.
            #
            # **A DÚVIDA É ASSIMÉTRICA, e é ela que faz a cura valer.** As
            # duas respostas fixas de `na_duvida` erram de um lado: `True`
            # devolve a enxurrada toda vez que o `pactl` engasga; `False`
            # calaria o alto-falante de um jogo aberto. Quem JÁ TEM ponte fica
            # com ela na dúvida; quem não tem não ganha uma.
            if modo == "som" and not sink_esta_tocando(
                nome_do_sink(uniq), na_duvida=uniq in self._pontes
            ):
                self._descer_ponte_ociosa(uniq)
                continue
            # COM SOM É O ALTO-FALANTE TOCANDO, com sinal: a ponte do som de pé
            # sobre um fluxo ESCUTADO e mudo não tira o rumble convertido de
            # ninguém. O fluxo que ninguém escutou ainda segura, como antes (o
            # portão logo acima já disse que ele está aberto).
            if modo == "som" and som_sinal is not False:
                com_som.add(uniq)
            # A PONTE QUE LÊ OUTRO ENDPOINT DESCE E SOBE (conferência de
            # 28/09/2026): a ponte em modo háptica lê o endpoint de QUANDO
            # subiu, e o do aparelho é o de agora. Ponte sem registro (dublê,
            # ou de antes desta volta saber) é «não sei», e «não sei» não
            # derruba ponte.
            lendo = endpoint.nome if (modo == "haptica" and endpoint is not None) else ""
            # O OUVIDO DA HÁPTICA NO MODO SOM: com o endpoint do aparelho aberto,
            # a ponte do som escuta ele também, senão o sinal que o jogo põe
            # nele nunca seria ouvido e a ponte ficaria no som para sempre. A
            # ponte do som que subiu sem ele (o endpoint abriu depois) sobe de
            # novo com ele — só com o alto-falante mudo, quando o respiro de
            # 255 ms não corta nada.
            ouvir_a_haptica = (
                endpoint.nome if (modo == "som" and endpoint_aberto and endpoint is not None)
                else ""
            )
            if uniq in self._pontes:
                lia = self._endpoint_da_ponte.get(uniq)
                sem_ouvido = (
                    bool(ouvir_a_haptica) and not som_toca
                    and self._ouvido_da_ponte.get(uniq, ouvir_a_haptica) != ouvir_a_haptica
                )
                if (
                    self._modo_da_ponte.get(uniq) == modo and lia in (None, lendo)
                    and not sem_ouvido
                ):
                    continue
                anterior = self._pontes.pop(uniq)
                anterior.descer()
                if sem_ouvido and self._modo_da_ponte.get(uniq) == modo:
                    logger.info("som_ponte_ganha_o_ouvido", uniq=uniq)
                elif self._modo_da_ponte.get(uniq) == modo:
                    logger.info("som_ponte_troca_de_endpoint", uniq=uniq, modo=modo)
                else:
                    logger.info("som_ponte_troca_de_modo", uniq=uniq, modo=modo)
            if not caminho:
                continue
            # A VAGA VEM ANTES DO GRAVADOR — GOVERNADOR-DO-RADIO-01. Até 2
            # pontes por adaptador (R3); a terceira espera a resposta dela na
            # tela, e o nó continua publicado (ela escolheu esta saída, e a
            # pergunta não pode tirá-la). Pedir depois de subir o `pw-record`
            # criaria e mataria um gravador a cada volta de espera.
            vaga: Any = None
            if governador is not None:
                from hefesto_dualsense4unix.daemon.subsystems.governador_do_radio import (
                    Recusa,
                )

                # O PEDIDO QUE LEVANTA NÃO DERRUBA A PONTE — O-ALTO-FALANTE-
                # DIZ-ATIVO-01, 23/09/2026. O `pedir_vaga` roda o
                # `plano_de_radio` sem `try` (A-COSTURA-DA-ONDA-2-01), e uma
                # exceção aqui subia até `_reconciliar`: nenhuma ponte da mesa
                # subia e nenhum nó era publicado naquela volta. A cura mora no
                # CHAMADOR: o pedido que falha é «não sei», e a ponte sobe como
                # subia antes do governador existir — sem vaga, que é o mesmo
                # caminho do dublê montado por `__new__`.
                try:
                    vaga = governador.pedir_vaga(uniq, modo)
                except Exception:
                    logger.warning(
                        "governador_pedido_de_vaga_falhou", uniq=uniq, modo=modo, exc_info=True
                    )
                    vaga = None
                if isinstance(vaga, Recusa):
                    esperando.add((uniq, modo))
                    continue
            fonte, gravador, motivo = fonte_do_monitor_do_no(
                nome_do_sink(uniq), uniq=uniq, papel="som"
            )
            if fonte is None:
                if vaga is not None:
                    vaga.soltar("o som não teve fonte")
                # Sem fonte não há ponte, e sem ponte ninguém derrubaria o
                # processo que subiu: ele é colhido aqui mesmo.
                if gravador is not None:
                    derrubar_leitor_de_pipe(gravador)
                # E ISTO TAMBÉM É RECUSA — RADIO-AFOGADO-01. Chegar aqui quer
                # dizer que alguém ESTÁ tocando neste controle (o portão do som
                # já deixou passar) e mesmo assim não houve PCM: ou o gravador
                # não subiu, ou o nó sumiu debaixo dele. Nos dois casos o nó
                # daquele controle não tem por onde entregar, e continuar
                # publicado o faria engolir o áudio dela.
                self._ponte_recusada[uniq] = time.monotonic()
                logger.info("som_ponte_sem_fonte", uniq=uniq, motivo=motivo)
                continue
            # O CAMINHO VAI NO FECHO, e o `functools.partial` diz o tipo: um
            # `lambda c=caminho: …` amarra igual, mas o mypy não infere o tipo
            # do default e o portão reprova.
            # O BIT DO MICROFONE VAI JUNTO, E ELE É PERGUNTADO A CADA REPORT
            # — 10/09/2026, queixa dela com o som tocando pelo rádio. O `0x35`
            # carrega, no bit 0 dos enables, o mesmo microfone; a ponte nascia
            # com ele em ZERO e o repetia cem vezes por segundo, desligando
            # o microfone dela enquanto o som saía. Quem responde é o
            # `BtMicSubsystem`, pelo gancho — nenhum subsystem importa o
            # outro. `functools.partial` e não `lambda` pela mesma razão do
            # `abrir_hidraw` acima: o mypy infere o tipo do primeiro.
            # A FONTE DA HÁPTICA SÓ SOBE NO MODO DELA: um `pw-record` lendo o
            # monitor sem ninguém consumir enche o cano e trava o processo.
            fonte_h: Any = None
            gravador_h: Any = None
            if modo == "haptica" and endpoint is not None:
                # O `papel` É O QUE SEPARA OS DOIS GRAVADORES DESTE MESMO
                # CONTROLE — 20/09/2026. Sem ele, o do som e o da háptica
                # disputariam um nome só; e sem o `uniq`, os TRÊS controles do
                # rádio disputavam o nome `hefesto-ponte-sink`, que foi o que
                # deixou dois deles sem vibrar no PRAGMATA.
                fonte_h, gravador_h, motivo_h = fonte_do_monitor_do_no(
                    endpoint.nome,
                    uniq=uniq,
                    papel="haptica",
                    canais=CANAIS_DA_HAPTICA,
                )
                if fonte_h is None:
                    if gravador_h is not None:
                        derrubar_leitor_de_pipe(gravador_h)
                    gravador_h = None
                    modo = "som"
                    logger.info("haptica_sem_fonte", uniq=uniq, motivo=motivo_h)
                    # E A PORTA DOS FUNDOS: cair para o alto-falante sem
                    # ninguém tocando nele devolveria a enxurrada por aqui. O
                    # gravador do som já subiu neste ponto, e quem desiste o
                    # colhe — ninguém mais o faria.
                    if not sink_esta_tocando(nome_do_sink(uniq)):
                        if gravador is not None:
                            derrubar_leitor_de_pipe(gravador)
                        if vaga is not None:
                            vaga.soltar("a vibração não teve fonte")
                        self._descer_ponte_ociosa(uniq)
                        continue
            elif ouvir_a_haptica:
                # O OUVIDO DA HÁPTICA NO MODO SOM: o mesmo gravador do modo da
                # háptica, lido só para o OUVIDO. Sem ele a ponte sobe como
                # sempre subiu, e o modo segue pelo que se sabe.
                fonte_h, gravador_h, motivo_h = fonte_do_monitor_do_no(
                    ouvir_a_haptica,
                    uniq=uniq,
                    papel="haptica",
                    canais=CANAIS_DA_HAPTICA,
                )
                if fonte_h is None:
                    if gravador_h is not None:
                        derrubar_leitor_de_pipe(gravador_h)
                    gravador_h = None
                    ouvir_a_haptica = ""
                    logger.info("haptica_sem_ouvido", uniq=uniq, motivo=motivo_h)
            ponte = PonteDeSomPorRadio(
                uniq=uniq,
                abrir_hidraw=functools.partial(self._abrir_hidraw, caminho),
                fonte_de_pcm=fonte,
                com_microfone=functools.partial(o_microfone_esta_no_ar, uniq),
                gravador=gravador,
                arranjo=ARRANJO_HAPTICA_032 if modo == "haptica" else None,
                fonte_de_haptica=fonte_h,
                gravador_da_haptica=gravador_h,
                vaga=vaga,
                no_do_som=nome_do_sink(uniq),
                no_da_haptica=(
                    endpoint.nome
                    if (modo == "haptica" and endpoint is not None) else ouvir_a_haptica
                ),
                ganho_da_haptica=functools.partial(GANHO.fator, uniq),
            )
            if ponte.subir():
                self._pontes[uniq] = ponte
                self._modo_da_ponte[uniq] = modo
                self._endpoint_da_ponte = MappingProxyType({
                    **self._endpoint_da_ponte,
                    uniq: endpoint.nome if (modo == "haptica" and endpoint is not None) else "",
                })
                self._ouvido_da_ponte = MappingProxyType({
                    **self._ouvido_da_ponte,
                    uniq: endpoint.nome
                    if (modo == "haptica" and endpoint is not None) else ouvir_a_haptica,
                })
                # SUBIU: o caminho está provado, e a recusa velha não vale mais.
                self._ponte_recusada.pop(uniq, None)
            else:
                ponte.descer()
                # NÃO SUBIU com o som dela na mão: isto é falha de verdade, e
                # o nó daquele controle tem de sumir com a frase honesta em vez
                # de engolir áudio. Ver :data:`RECUSA_DA_PONTE_S`.
                self._ponte_recusada[uniq] = time.monotonic()
                logger.info("som_ponte_nao_subiu", uniq=uniq, motivo=ponte.motivo)
        self._esperando_vaga = frozenset(esperando)
        self._radio_com_som = frozenset(com_som)
        self._conferir_o_teste_da_haptica()
        self._conferir_o_rumble()

    def _esquecer_a_espera(self, uniq: str) -> None:
        """Ela respondeu «Ligar aqui»: quem esperava vaga deixa de esperar.

        O controle sai de :attr:`_esperando_vaga` e a volta é ACORDADA
        (:meth:`_acordar_a_volta`): a ponte sobe logo, e não na volta seguinte,
        cinco segundos depois.
        """
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        # PELOS DÍGITOS, como o governador (conferência de 23/09/2026): a tela
        # pode mandar o `uniq` com ou sem os dois-pontos, e o governador já o
        # autorizou pela chave normalizada. Comparar o texto cru deixava a
        # autorização valer e a volta sem acordar — cinco segundos a mais.
        alvo = norm_mac(uniq) or uniq.lower()
        self._esperando_vaga = frozenset(
            (u, m) for u, m in self._esperando_vaga if (norm_mac(u) or u.lower()) != alvo
        )
        self._acordar_a_volta()

    def _acordar_a_volta(self, _por_quem: str = "") -> None:
        """Pede a volta AGORA, sem esperar o relógio. Nunca levanta.

        A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01: quem precisa da volta
        avisa, e ninguém fica perguntando. Os dois que avisam são o controle
        que entra na partida (``QuemMexe.ao_marcar``, o argumento é o endereço
        dele) — a ponte da háptica dele sobe na hora, e não na volta seguinte —
        e a resposta dela ao «Ligar aqui» (:meth:`_esquecer_a_espera`).
        """
        self._volta_pedida = True
        acordar = getattr(self, "_acordar", None)
        if acordar is not None:
            acordar.set()

    def _o_no_tem_sinal(self, nome: str) -> bool | None:
        """O nó tem sinal agora? ``None`` = ninguém o escuta. Nunca levanta.

        A-HAPTICA-POR-AUDIO-E-O-ALTO-FALANTE-CHEGAM-AO-RADIO-01, 29/09/2026.
        O dono da resposta é o :data:`~hefesto_dualsense4unix.integrations.
        alto_falante_bt.OUVIDO`, com o que as pontes leram dos monitores; este
        método é a única porta do subsystem para ele. Os que decidem se o NÓ
        fica de pé (a reancoragem e :meth:`_aparelhos_de_pe`) seguem no fluxo de
        propósito: nó que some quebra o jogo que o escolheu, e ali o fluxo
        aberto é a pergunta. E a ponte ociosa desce pelo fluxo, e não pelo
        sinal: a ponte é o ouvido do nó, e derrubá-la pelo silêncio deixaria o
        nó sem quem o escute.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import OUVIDO

        try:
            return OUVIDO.tem_sinal(nome)
        except Exception:  # o ouvido nunca derruba a volta
            logger.debug("som_ouvido_ilegivel", no=nome, exc_info=True)
            return None

    def _modo_pelo_sinal(
        self, uniq: str, *, candidata: bool, som_toca: bool, haptica_toca: bool | None
    ) -> str:
        """O modo da ponte de ``uniq``: quem tem SINAL fica com o rádio.

        A-HAPTICA-POR-AUDIO-E-O-ALTO-FALANTE-CHEGAM-AO-RADIO-01, 29/09/2026.
        ``candidata`` é o portão de sempre (o jogo abriu o endpoint do aparelho E
        este controle joga, ou o rumble convertido é dele): sem ele, som.

        * só o alto-falante com sinal: som (``0x35``), mesmo com o fluxo da
          háptica aberto e mudo — a Forja em O Canto;
        * só a háptica com sinal: háptica (``0x32`` com o bloco ``0x11``);
        * os dois com sinal: o alto-falante ganha — a D-2909-NO-RADIO-O-ALTO-
          FALANTE-GANHA estendida ao fluxo de háptica do jogo, por delegação;
        * nenhum com sinal, com a háptica ESCUTADA e muda (``False``) e a
          ponte no som: ela fica no som — é O Canto entre dois cantos;
        * a háptica que ninguém escuta (``None``): a háptica, no mesmo tempo
          de hoje. A ponte da háptica escuta os dois e só manda o que tem
          sinal, e o som que começar a tocar a devolve ao alto-falante.

        A janela do sinal (:data:`~hefesto_dualsense4unix.integrations.
        alto_falante_bt.JANELA_DO_SINAL_S`) é a histerese: uma cena com tiro e
        fala tem sinal nos dois, e a ponte fica no som, sem alternar.
        """
        if not candidata or som_toca:
            return "som"
        if haptica_toca is True:
            return "haptica"
        if (
            haptica_toca is False
            and uniq in self._pontes
            and self._modo_da_ponte.get(uniq) == "som"
        ):
            return "som"
        return "haptica"

    def _descer_ponte_ociosa(self, uniq: str) -> None:
        """A ponte de quem não tem o que tocar desce. Idempotente.

        RADIO-AFOGADO-01, 22/09/2026. Separado de
        :meth:`_casar_as_pontes` porque a desistência tem DUAS portas — o modo
        do som sem som, e a háptica que caiu para o som sem som — e escrever a
        queda duas vezes é como uma delas envelhece sem a outra.

        **NÃO MEXE NO ENDPOINT.** O nó de quatro canais fica publicado com a
        ponte deitada: nó que some quebra o jogo que já o escolheu, e essa é
        decisão dela de 08/09. O que cai é o ESCRITOR, não o que o jogo vê.
        """
        ponte = self._pontes.pop(uniq, None)
        self._modo_da_ponte.pop(uniq, None)
        if ponte is not None:
            ponte.descer()
            logger.info("som_ponte_ociosa_descida", uniq=uniq)

    def _abrir_hidraw(self, caminho: str) -> int | None:
        """O fd de escrita daquele nó, pelo BROKER — nunca por `os.open` cru.

        Com o co-op ligado os hidraw dos físicos estão escondidos, e só o
        broker os entrega. É a mesma porta que todo instrumento desta casa usa.
        """
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            abrir_hidraw,
        )

        try:
            return abrir_hidraw(caminho, escrita=True).fd
        except Exception:
            logger.debug("som_hidraw_nao_abriu", caminho=caminho, exc_info=True)
            return None

    async def start(self, ctx: DaemonContext) -> None:
        """Sobe a thread de reconciliação. Idempotente.

        Nada de bloquear o event loop: a varredura do sysfs e o ``pactl`` do
        ``load-module`` rodam na thread.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            registrar_dizedor_da_fonte,
        )

        self._backend = getattr(ctx, "controller", None)
        if self._thread is not None and self._thread.is_alive():
            return
        self._instalar_o_numerador()
        self._store = getattr(ctx, "store", None)
        self._gerenciador = self._gerenciador_injetado or GerenciadorDeNosDeSom(
            ponte_do_radio_por_controle=self._ponte_do_radio_de,
            fonte_por_controle=self._fonte_do_controle,
        )
        # A FONTE VAI À TELA PELO MESMO DONO QUE O DAEMON JÁ CONSULTA —
        # 10/09/2026 (SOM-NA-TELA-01). Sem este gancho a aba teria de abrir o
        # perfil por conta própria a cada tique, e a casa passaria a ter dois
        # leitores da mesma escolha dela.
        self._dizedor_anterior = registrar_dizedor_da_fonte(self._fonte_do_controle)
        # O GOVERNADOR NASCE ANTES DA PRIMEIRA VOLTA: a primeira ponte já pede
        # vaga a ele. Um governador que não sobe não pode calar o som — sem
        # ele a ponte sobe como subia antes do GOVERNADOR-DO-RADIO-01.
        if self.governador is None:
            try:
                if self._governador_injetado is not None:
                    self.governador = self._governador_injetado
                else:
                    from hefesto_dualsense4unix.daemon.subsystems.governador_do_radio import (
                        GovernadorDoRadio,
                    )

                    self.governador = GovernadorDoRadio.de_producao()
                self.governador.ao_autorizar = self._esquecer_a_espera
                self.governador.iniciar()
            except Exception:
                logger.warning("governador_do_radio_nao_subiu", exc_info=True)
                self.governador = None
        self._parar.clear()
        self._acordar.clear()
        self._ouvir_quem_entra_na_partida(self._acordar_a_volta)
        self._ouvinte = threading.Thread(
            target=self._ouvir_o_retrato, name="hefesto-som-fluxos", daemon=True
        )
        self._ouvinte.start()
        self._thread = threading.Thread(
            target=self._loop, name="hefesto-som-sup", daemon=True
        )
        self._thread.start()
        logger.info("som_subsystem_iniciado")

    def _ouvir_quem_entra_na_partida(self, aviso: Any) -> None:
        """Liga (ou desliga, com ``None``) o aviso do controle que entra na partida.

        O dono das marcas nasce aqui se ainda não existe
        (``quem_mexe.quem_mexe_de``): quem sabe da partida é esta volta. Um
        dublê de daemon que recusa atributo fica sem aviso, e a volta segue
        pelo relógio.
        """
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import (
            ATRIBUTO,
            QuemMexe,
            quem_mexe_de,
        )

        daemon = getattr(self, "_daemon", None)
        if aviso is None:
            # Desligar não cria o dono: sem marcas, não há aviso a tirar.
            marcas = getattr(daemon, ATRIBUTO, None)
            if isinstance(marcas, QuemMexe):
                marcas.ao_marcar = None
            return
        marcas = quem_mexe_de(daemon)
        if marcas is not None:
            marcas.ao_marcar = aviso

    async def stop(self) -> None:
        """Derruba as pontes, e SÓ ENTÃO os nós. Idempotente.

        O ``join`` e o ``descer`` saem do event loop por ``to_thread``: segurar
        o loop do daemon por uma varredura em curso, ou por um gravador que
        demora a morrer, atrasaria o shutdown inteiro.

        **A ORDEM É A CURA — SOM-TRAVA-NA-QUEDA-01, 13/09/2026.** Até esta data
        o ``gerenciador.parar()`` vinha PRIMEIRO: os nós saíam com o
        ``pw-record`` de cada ponte ainda vivo, lendo o monitor de um nó que
        acabava de sumir, e as pontes só desciam depois. É o mesmo estado que a
        queda deixava quando a sessão de som dela travou duas vezes no dia: o
        nó fora e o gravador vivo. Agora: parar a reconciliação, descer as
        pontes (que colhem os gravadores) e só então tirar os nós.
        """
        self._parar.set()
        self._ouvir_quem_entra_na_partida(None)
        # O laço dorme no `_acordar`, e o ouvinte no retrato do som: sem os
        # dois toques, cada um só veria a parada no fim da espera.
        from hefesto_dualsense4unix.integrations.retrato_do_som import RETRATO

        self._acordar.set()
        RETRATO.acordar()
        thread, ouvinte = self._thread, self._ouvinte
        self._thread = self._ouvinte = None
        for fio in (thread, ouvinte):
            if fio is not None:
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(fio.join, 2.0)
        # As pontes MORREM COM O SUBSYSTEM. Cada uma segura um fd de hidraw e
        # um `pw-record`; deixá-las de pé depois do `stop()` é vazar os dois
        # por controle, e o próximo `start()` abriria um segundo par. Descem
        # JUNTAS: o pior caso de uma é o prazo do `join` mais o do `kill`, e em
        # fila os quatro controles somariam os quatro.
        pontes = list(self._pontes.items())
        if pontes:
            await asyncio.gather(
                *(asyncio.to_thread(ponte.descer) for _uniq, ponte in pontes),
                return_exceptions=True,
            )
        for uniq, _ponte in pontes:
            self._pontes.pop(uniq, None)
        # OS TOCADORES DO RUMBLE MORREM COM O SUBSYSTEM, e antes dos laços que
        # os levam: cada um é um processo tocando num endpoint.
        tocadores = list(self._tocadores.values())
        self._tocadores = MappingProxyType({})
        self._rumble_vivo = MappingProxyType({})
        if tocadores:
            await asyncio.gather(
                *(asyncio.to_thread(t.parar) for t in tocadores), return_exceptions=True
            )
        # OS LAÇOS DO CABO MORREM COM O SUBSYSTEM, como as pontes: cada um é um
        # `pw-loopback` lendo o endpoint de um aparelho. O endpoint FICA (o
        # restart o adota), e o laço volta na primeira volta do próximo start.
        cabo = self._cabo
        if cabo is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(cabo.parar)
        # OS OUVIDOS DAS PLACAS MORREM COM O SUBSYSTEM: cada um é um gravador
        # lendo o monitor da placa de um controle no cabo.
        ouvidos = list(self._ouvidos_das_placas.values())
        self._ouvidos_das_placas = MappingProxyType({})
        if ouvidos:
            await asyncio.gather(
                *(asyncio.to_thread(o.descer) for o in ouvidos), return_exceptions=True
            )
        # O GANHO NÃO SOBREVIVE AO HEFESTO: os traseiros das placas voltam a 1,0.
        with contextlib.suppress(Exception):
            await asyncio.to_thread(GANHO.devolver_as_placas)
        # O governador para DEPOIS das pontes: elas devolvem a vaga ao descer.
        governador, self.governador = self.governador, None
        if governador is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(governador.parar)
        gerenciador = self._gerenciador
        if gerenciador is not None:
            with contextlib.suppress(Exception):
                gerenciador.parar()
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            registrar_dizedor_da_fonte,
        )

        self._gerenciador = None
        self._desinstalar_o_numerador()
        registrar_dizedor_da_fonte(self._dizedor_anterior)
        self._dizedor_anterior = None
        self._backend = None
        logger.info("som_subsystem_parado")

    # -- o número do assento, que é do rótulo e de mais nada --------------

    def _instalar_o_numerador(self) -> None:
        """Instala o numerador de assento **só se ninguém o estiver atendendo**.

        O registro é UM (``dualsense_bt_audio.registrar_numerador_de_assento``)
        e serve aos dois rótulos, porque a resposta tem de ser a mesma nos
        dois. Quem chega primeiro atende; quem chega depois não derruba o
        dono, e a prova de que havia dono é o valor devolvido pelo registro —
        não existe leitor, e inventar um seria API nova por conveniência.

        Sem isto, subir este subsystem depois do ``BtMicSubsystem`` trocaria o
        numerador dele pelo nosso no meio da sessão, com os dois respondendo o
        mesmo — troca sem efeito e com risco.
        """
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            registrar_numerador_de_assento,
        )

        anterior = registrar_numerador_de_assento(self.numero_do_assento)
        if anterior is not None:
            registrar_numerador_de_assento(anterior)
            self._numerador_anterior = Ellipsis
            return
        self._numerador_anterior = anterior

    def _desinstalar_o_numerador(self) -> None:
        """Devolve o numerador anterior — e só se tiver sido ELE a instalar."""
        if self._numerador_anterior is Ellipsis:
            return
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            registrar_numerador_de_assento,
        )

        with contextlib.suppress(Exception):
            registrar_numerador_de_assento(self._numerador_anterior)
        self._numerador_anterior = Ellipsis

    # -- laço -------------------------------------------------------------

    def _loop(self) -> None:
        gerenciador = self._gerenciador
        if gerenciador is None:
            return
        while not self._parar.is_set():
            try:
                self._reconciliar(gerenciador)
            except Exception as exc:  # nunca derruba a thread
                logger.debug("som_reconciliacao_falhou", err=str(exc))
            if self._esperar_a_mesa_do_som(gerenciador):
                return

    def _ouvir_o_retrato(self) -> None:
        """O ouvinte: o retrato do som mudou nas saídas ou nos fluxos, e o laço acorda.

        A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01. **O fluxo que nasce é
        avisado, e não caçado**: o retrato (O-SERVIDOR-DE-SOM-TEM-UM-LEITOR-
        SO-01) é mantido em dia pelo ``pactl subscribe``, e esta thread só
        dorme nele. Sem mudança, nenhuma pergunta ao servidor; quem decide se
        a mudança importa é :meth:`_a_mesa_do_som_mudou`, no laço.
        """
        from hefesto_dualsense4unix.integrations.retrato_do_som import RETRATO

        marca = RETRATO.marca(_O_QUE_A_VOLTA_OUVE)
        while not self._parar.is_set():
            nova = RETRATO.esperar(marca, RECONCILIA_S, _O_QUE_A_VOLTA_OUVE)
            if nova != marca:
                marca = nova
                self._acordar.set()

    def _esperar_a_mesa_do_som(self, gerenciador: Any) -> bool:
        """Espera até a próxima volta, e volta CEDO se o que a volta leu mudou. True = parar.

        A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01. Acorda por três
        motivos, e nenhum é um relógio curto: o ouvinte do retrato
        (:meth:`_ouvir_o_retrato`), quem pede a volta
        (:meth:`_acordar_a_volta`) e a parada. O pedido reconcilia sempre; a
        mudança do retrato só quando ela toca os nós dos controles do rádio.

        **NÃO DUPLICA A DECISÃO**: quem decide o modo de cada ponte continua
        sendo :meth:`_casar_as_pontes`. Esta espera só responde *"vale a pena
        reconciliar agora?"*, comparando ENTRADAS, e não resultados — uma
        tentativa que falhou não muda entrada nenhuma, e por isso não prende
        a volta num laço.

        O ``Event`` é limpo ANTES de olhar: um aviso que chegue enquanto se
        olha fica armado para a espera seguinte, e nenhum se perde.
        """
        fim = time.monotonic() + RECONCILIA_S
        acordar = self._acordar
        while True:
            falta = fim - time.monotonic()
            if falta <= 0:
                return False
            avisado = acordar.wait(falta)
            if self._parar.is_set() or gerenciador.dormir(0.0):
                return True
            if not avisado:
                return False  # o relógio: a volta vem, e ninguém olhou nada
            acordar.clear()
            if self._volta_pedida:
                self._volta_pedida = False
                return False
            if self._a_mesa_do_som_mudou():
                return False

    def _o_que_a_mesa_do_som_diz(self) -> frozenset[str] | None:
        """Quais nós dos controles do rádio têm fluxo agora. ``None`` = não sei.

        São as ENTRADAS da decisão da volta: o endpoint de háptica e o nó de
        som de cada controle no rádio. Uma passada só pelo retrato do som, sem
        ``pactl`` no daemon (``sinks_que_tocam``). Sem nó nenhum, nem se
        pergunta.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            nome_do_sink,
            sinks_que_tocam,
        )

        nomes = [str(getattr(ep, "nome", "") or "") for ep in self._endpoints.values()]
        nomes += [nome_do_sink(u) for u in self._no_radio]
        nomes = [n for n in nomes if n]
        if not nomes:
            return frozenset()
        try:
            tocando = sinks_que_tocam(nomes)
        except Exception as exc:  # nunca derruba a thread do som
            logger.debug("som_mesa_ilegivel_no_retrato", err=str(exc))
            return None
        return None if tocando is None else frozenset(tocando)

    def _a_mesa_do_som_mudou(self) -> bool:
        """Algum nó dos controles do rádio abriu ou fechou fluxo desde que a volta começou?

        **NA DÚVIDA, NÃO MEXE**: servidor mudo não é «ninguém toca», e a
        espera segue até o relógio.
        """
        agora = self._o_que_a_mesa_do_som_diz()
        if agora is None:
            return False
        if agora == self._o_que_a_volta_viu:
            return False
        logger.debug(
            "som_volta_acordada_pelo_fluxo",
            antes=len(self._o_que_a_volta_viu or ()),
            agora=len(agora),
        )
        return True

    def _reconciliar(self, gerenciador: Any) -> None:
        """Uma varredura: quem está na lista ganha nó, quem saiu perde.

        Passa os CONTROLES, não os ``uniq``: quem resolve a rota precisa do
        transporte ao lado, e ir buscá-lo depois seria uma segunda varredura de
        sysfs com a chance de discordar da primeira — que é o defeito que
        `bt_mic._conectados_da_mesa` já pagou.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import e_radio

        alvos = self.alvos(list(self._fonte()))
        # O QUE ESTA VOLTA LÊ, GUARDADO ANTES DE AGIR: se um fluxo nascer
        # enquanto ela age, a espera seguinte vê a diferença e volta na hora.
        self._no_radio = frozenset(
            str(getattr(c, "uniq", "") or "")
            for c in alvos
            if e_radio(str(getattr(c, "transporte", "") or ""))
        )
        self._o_que_a_volta_viu = self._o_que_a_mesa_do_som_diz()
        # A PONTE PRIMEIRO, O NÓ DEPOIS — e a ordem é medida, não estética.
        # `rota_do_no` pergunta à ponte se ela está de pé no momento em que o
        # nó nasce. Fiar na ordem inversa publicaria a rota do rádio como
        # recusada e só a corrigiria na varredura seguinte, 2 s depois: o jogo
        # que abrisse o nó nesse intervalo pegaria a rota errada.
        self._casar_as_pontes(alvos)
        gerenciador.reconciliar(alvos)


__all__ = [
    "RECONCILIA_S",
    "AltoFalanteSubsystem",
    "ControleNaLista",
    "GerenciadorDeNosDeSom",
    "controles_na_lista",
]
