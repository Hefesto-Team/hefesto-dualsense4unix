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
  ``integrations.alto_falante_bt.rota_do_no``, e ele é o MESMO que a janela
  chama por ``app/audio_saida`` — uma pergunta, um dono;
* **não escolhe o número do rótulo.** O «Controle N» de «Alto-falante do
  Controle N» é a conta DA CASA, e este subsystem só a alcança — ver
  :meth:`AltoFalanteSubsystem.numero_do_assento` e
  ``daemon/subsystems/base.numero_do_assento_na_mesa``.

O ÓRFÃO GANHOU A ROTA, E DEPOIS GANHOU AS TRÊS LINHAS DO REGISTRO
------------------------------------------------------------------
**As duas razões de 07/09 para não o ligar caíram em 09/09**, e as duas eram
razões de verdade:

* *"sem o ``module-loopback``, o nó publicado é um sumidouro"* — agora
  :class:`~integrations.alto_falante_bt.SinkVirtualPipeWire` sobe o loopback
  junto, e a pergunta *"onde este nó entrega?"* passou a ter **um** dono
  (``integrations.alto_falante_bt.rota_do_no``), que é o mesmo que a janela
  chama por ``app/audio_saida``. Eram duas respostas escritas; ficou uma;
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
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.daemon.subsystems.base import numero_do_assento_na_mesa
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)

#: Cadência da varredura de hotplug (sysfs). Não é polling de áudio: é só
#: *"apareceu/sumiu controle?"*. O mesmo número da metade de entrada.
RECONCILIA_S = 5.0

#: Cadência do VIGIA DO MODO — HAPTICA-RADIO-INICIO-01, 19/09/2026.
#:
#: O QUE ELE CURA, medido com três DualSense no rádio em 18/09: a vibração do
#: jogo começou **2, 4 e 5 s** depois de o jogo começar a tocar. A causa estava
#: escrita no próprio laço — a troca para o modo háptica só acontece quando
#: `sink_esta_tocando` responde sim, e a pergunta era feita **uma vez por
#: volta**, a cada :data:`RECONCILIA_S`. Um pulso de 1,5 s podia nunca vibrar.
#:
#: E ELE NÃO MULTIPLICA AS CHAMADAS AO SERVIDOR DE SOM, que é a ressalva
#: escrita na sprint. O vigia usa `sinks_que_tocam`, que responde por TODOS os
#: endpoints numa passada de dois `pactl` (2,9 ms + 2,6 ms, medidos nesta
#: máquina). Com quatro controles, a volta inteira gasta OITO subprocessos e o
#: vigia gasta DOIS — 5,5 ms a cada 0,4 s é 1,4% de um núcleo, e o custo deixa
#: de crescer com o número de controles.
#:
#: 0,4 s e não menos: a prova de pronto da sprint é *"a vibração ligando em
#: menos de 0,5 s"*, e o vigia tem de caber dentro dela com folga para a
#: passada do `pactl`.
VIGIA_DO_MODO_S = 0.4

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
        # SEM ROTA, SEM NÓ — e a razão está na invariante 4 de
        # `app/audio_saida.py`: *"um `module-null-sink` sozinho seria
        # exatamente o sink que aceita o áudio e o joga fora"*. Publicar
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
    """`mtime_ns` do arquivo daquele perfil — `None` quando não dá para saber.

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

        return Path(_profile_path(nome)).stat().st_mtime_ns
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

        perfil = load_profile(nome)
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

    #: Quem o jogo estava LENDO na última volta — lembrado para o vigia do
    #: modo poder adivinhar o que a volta decidiria sem varrer `/proc` a cada
    #: :data:`VIGIA_DO_MODO_S`. Fica velho por até uma volta, e o preço de
    #: estar velho é UMA reconciliação a mais, nunca uma ponte errada.
    #:
    #: **MORA NO CORPO DA CLASSE, e não no `__init__`** — e o motivo é uma
    #: armadilha desta casa: dublê montado por `object.__new__` não roda o
    #: `__init__`, e estado novo que só nasce lá deixa o dublê mais POBRE que
    #: o produto. `frozenset` e não `set`: um mutável no corpo da classe seria
    #: compartilhado por todas as instâncias.
    _jogando: frozenset[str] = frozenset()

    #: O GOVERNADOR DO RÁDIO (GOVERNADOR-DO-RADIO-01, 23/09/2026): quem dá a
    #: vaga de cada ponte, por adaptador, e manda ceder na fonte quando o
    #: adaptador não escoa. Nasce no ``start()``; ``None`` num dublê montado
    #: por ``__new__`` ou antes de subir, e aí a ponte sobe como sempre subiu.
    #: O ``state_full`` lê a amostra de ar DELE — um medidor só no daemon.
    governador: Any = None
    #: ``(uniq, modo)`` de quem tem som esperando uma vaga que o governador
    #: ainda não deu (o adaptador cheio, à espera da resposta dela; ou o
    #: adaptador parado). Refeito a cada volta. O vigia do modo o lê como o
    #: modo ATUAL daquele controle — sem isso, a mesma pergunta acordaria a
    #: volta a cada 0,4 s enquanto ela não responde.
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
        #: O endpoint de mentira por controle no rádio — o alto-falante de
        #: quatro canais que o JOGO enxerga. Ele não é o `hefesto_som_<hex6>`:
        #: aquele é a saída da MÁQUINA para o controle, e a pessoa o escolhe.
        self._endpoints: dict[str, Any] = {}
        #: "som" ou "haptica": qual arranjo a ponte daquele controle está
        #: mandando AGORA. O escritor é um só, e trocar de arranjo exige
        #: derrubar e subir — é por isso que o modo é lembrado.
        self._modo_da_ponte: dict[str, str] = {}
        #: `uniq -> quando o `subir()` falhou` — ver :data:`RECUSA_DA_PONTE_S`.
        self._ponte_recusada: dict[str, float] = {}
        #: Quantos controles no rádio ficaram sem âncora USB na última volta —
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

    def _avisar_ancoras_que_faltam(self, faltam: int, controles: int) -> None:
        """O controle no rádio sem âncora USB fica sem vibração — e diz isso.

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
            logger.warning("haptica_sem_ancora", faltam=faltam, controles=controles)
        else:
            logger.info("haptica_ancoras_bastam", controles=controles)
        self._faltam_ancoras = faltam

    def _quem_o_jogo_le(self, controles: list[Any]) -> set[str]:
        """Os ``uniq`` que algum JOGO está lendo agora — em minúsculas.

        QUEM-JOGA-E-QUEM-VIBRA-01. Devolve conjunto VAZIO quando não há jogo,
        quando `/proc` não se lê, ou quando o que o jogo abriu não se traduz em
        controle nenhum. **O vazio é o lado seguro**: um controle que não vibra
        é uma falta; um que vibra sozinho na mão de alguém é o defeito que ela
        reportou em 20/09.

        A lista de físicos vem de TODOS os controles da mesa, e não só dos do
        rádio: com máscara, o jogo abre o vpad, e traduzir o vpad exige poder
        derivá-lo de qualquer aparelho — inclusive o do cabo, que é quem
        costuma estar jogando.
        """
        from hefesto_dualsense4unix.integrations.quem_o_jogo_le import (
            dono_do_vpad_pela_forja,
            quem_o_jogo_le,
        )

        fisicos = [
            str(getattr(c, "uniq", "") or "") for c in controles
        ]
        fisicos = [u for u in fisicos if u]
        if not fisicos:
            return set()
        try:
            return quem_o_jogo_le(
                fisicos=fisicos,
                dono_do_vpad=lambda v: dono_do_vpad_pela_forja(v, fisicos),
            )
        except Exception as erro:
            # AUSÊNCIA É RESPOSTA, e ela é registrada: um erro aqui cala a
            # háptica da mesa inteira, e calar sem dizer por quê é o defeito
            # que esta casa mais persegue.
            logger.info("haptica_nao_sei_quem_joga", motivo=str(erro))
            return set()

    def _casar_as_pontes(self, controles: list[Any]) -> None:
        """Sobe uma ponte por controle NO RÁDIO, e derruba a de quem saiu.

        Roda na thread de reconciliação, junto com os nós — as duas coisas
        respondem à mesma lista, e separá-las abriria a janela em que o nó
        existe e a ponte não (ou o contrário).
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            ARRANJO_HAPTICA_032,
            CANAIS_DA_HAPTICA,
            PonteDeSomPorRadio,
            e_radio,
            fonte_do_monitor_do_no,
            garantir_motores_audiveis,
            nome_do_sink,
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
        # O ENDPOINT DA HÁPTICA CAI DEPOIS DA PONTE, nunca antes: a ponte lê o
        # monitor dele, e derrubar o nó primeiro deixaria a leitura pendurada.
        for uniq in [u for u in self._endpoints if u not in vivos]:
            endpoint = self._endpoints.pop(uniq, None)
            if endpoint is not None:
                endpoint.parar()
        # O QUE O PROCESSO ANTERIOR DEIXOU — 18/09/2026, e ele não é teórico:
        # na mesa dela havia VINTE E DOIS `module-null-sink` onde deviam existir
        # quatro. O laço acima só alcança o que ESTE processo criou; o servidor
        # de som é outro processo e sobrevive ao restart do daemon. Sem esta
        # varredura, cada reinício somava mais um nó com o mesmo nome à lista de
        # saídas de som dela. É a mesma classe — e a mesma cura — do canal órfão
        # do microfone (`bt_mic.VarredorDeCanaisOrfaos`).
        #
        # UMA pergunta ao servidor por volta, e ela serve às duas coisas: à
        # varredura e à semente das âncoras logo abaixo.
        de_pe: dict[str, list[tuple[str, str]]] | None = None
        with contextlib.suppress(Exception):
            de_pe = endpoints_de_pe()
        with contextlib.suppress(Exception):
            varrer_endpoints_orfaos(vivos, de_pe=de_pe)

        # O ENDPOINT DA HÁPTICA — um por controle no rádio, e ele VIVE ENQUANTO
        # O CONTROLE EXISTIR. É a mesma decisão dela de 08/09 para o nó do som
        # ("nó que some quebra o jogo que o escolheu"), e aqui ela pesa mais: se
        # o nó cair no meio da partida, o endpoint da háptica morre com o jogo
        # aberto. Cada controle ganha uma âncora PRÓPRIA — âncoras iguais são
        # ContainerIds iguais, e aí a háptica do jogador 2 iria para o device do
        # jogador 1. A distribuição respeita a POSSE — a memória deste processo
        # e o que o servidor já tem de pé — e só as livres vão para quem chega:
        # por ordem pura, o controle que chegava depois com o `uniq` menor
        # herdava a âncora de quem já estava (INSTALL-UNIVERSAL, 18/09/2026).
        postas = distribuir_ancoras(
            vivos, ancoras(), de_pe,
            ja_postas={u: e.ancora for u, e in self._endpoints.items()},
        )
        for uniq in vivos:
            posta = postas.get(uniq)
            atual = self._endpoints.get(uniq)
            if atual is not None:
                if posta is None or posta.syspath == atual.ancora.syspath:
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
                if (
                    uniq in self._pontes and self._modo_da_ponte.get(uniq) == "haptica"
                ) or sink_esta_tocando(atual.nome, na_duvida=True):
                    continue
                self._endpoints.pop(uniq, None)
                atual.parar()
                logger.info("haptica_endpoint_reancorado", uniq=uniq, ancora=posta.syspath)
            if posta is None:
                continue
            endpoint = EndpointDeHaptica(uniq=uniq, ancora=posta)
            if endpoint.iniciar():
                self._endpoints[uniq] = endpoint
        self._avisar_ancoras_que_faltam(
            sum(1 for u in vivos if u not in self._endpoints and u not in postas),
            len(vivos),
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
        with contextlib.suppress(Exception):
            for sink_com_motor in sinks_com_motores():
                garantir_motores_audiveis(sink_com_motor)

        # QUEM O JOGO ESTÁ LENDO — QUEM-JOGA-E-QUEM-VIBRA-01, 20/09/2026.
        # Correção dela, e ela derrubou a premissa da sprint anterior: *"é um
        # jogo de um player e o erro era que o player 3 tava recebendo a
        # vibração de forma espelhada"*. Antes desta linha, o modo háptica
        # entrava em TODO controle cujo endpoint tivesse stream — e num jogo de
        # um jogador isso não é ninguém além de quem segura o controle.
        #
        # É calculado UMA VEZ por volta, e não por controle: são duas varreduras
        # de `/proc`, e repeti-las por peça multiplicaria o custo pela mesa.
        jogando = self._quem_o_jogo_le(controles)
        self._jogando = frozenset(jogando)

        governador = self.governador
        esperando: set[tuple[str, str]] = set()
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
            endpoint = self._endpoints.get(uniq)
            # O GATE TEM DOIS LADOS, e os dois precisam ser verdade: o jogo
            # abriu o canal DAQUELE endpoint (o sinal de sempre) E o jogo está
            # LENDO aquele controle (o sinal novo). Só o primeiro deixava três
            # controles vibrarem num jogo de um jogador.
            o_jogo_le_este = uniq.lower() in jogando
            modo = (
                "haptica"
                if (endpoint and o_jogo_le_este and sink_esta_tocando(endpoint.nome))
                else "som"
            )
            # A PONTE DO SOM SÓ EXISTE ENQUANTO HÁ SOM — RADIO-AFOGADO-01,
            # 22/09/2026, e é o defeito que tirou três dos quatro controles
            # dela da mesa. Ela escrevia 93,75 reports de 334 B por segundo
            # por controle, tocasse alguém ou não; o teto medido desta mesa é
            # DUAS pontes, e a terceira derrubou os quatro em 11 a 89
            # segundos. Os números, a corrente até o `EAGAIN` do bluetoothd e
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
            if uniq in self._pontes:
                if self._modo_da_ponte.get(uniq) == modo:
                    continue
                anterior = self._pontes.pop(uniq)
                anterior.descer()
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
            # com ele em ZERO e o repetia 93,75 vezes por segundo, desligando
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
            )
            if ponte.subir():
                self._pontes[uniq] = ponte
                self._modo_da_ponte[uniq] = modo
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

    def _esquecer_a_espera(self, uniq: str) -> None:
        """Ela respondeu «Ligar aqui»: quem esperava vaga deixa de esperar.

        Com o controle fora de :attr:`_esperando_vaga`, o vigia do modo vê som
        sem ponte e acorda a volta em até :data:`VIGIA_DO_MODO_S` — a ponte
        sobe logo, e não na volta seguinte, cinco segundos depois.
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
        self._thread = threading.Thread(
            target=self._loop, name="hefesto-som-sup", daemon=True
        )
        self._thread.start()
        logger.info("som_subsystem_iniciado")

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
        thread = self._thread
        self._thread = None
        if thread is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(thread.join, 2.0)
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
            if self._esperar_de_olho_no_modo(gerenciador):
                return

    def _esperar_de_olho_no_modo(self, gerenciador: Any) -> bool:
        """Espera até a próxima volta, mas volta CEDO se o modo mudou. True = parar.

        HAPTICA-RADIO-INICIO-01, 19/09/2026.

        **NÃO DUPLICA A DECISÃO.** Quem troca de modo continua sendo
        `_reconciliar` — descer e subir a ponte é ato de um escritor só, e ter
        dois lugares mexendo no fio é o defeito que o «escritor é UM SÓ» desta
        casa existe para impedir. O vigia só responde *"vale a pena reconciliar
        agora?"*, e encurta a espera quando vale.

        **NA DÚVIDA, NÃO MEXE.** `sinks_que_tocam` devolve ``None`` quando o
        servidor de som não respondeu, e aí a espera segue como antes — um
        `pactl` que falhou não pode derrubar a ponte de um jogo aberto, que é a
        decisão dela de 08/09.
        """
        fatias = max(1, int(RECONCILIA_S / VIGIA_DO_MODO_S))
        for _ in range(fatias):
            if self._parar.wait(VIGIA_DO_MODO_S) or gerenciador.dormir(0.0):
                return True
            if self._o_modo_de_alguem_mudou():
                return False
        return False

    def _o_modo_de_alguem_mudou(self) -> bool:
        """Alguém passou a tocar (ou parou) desde a última volta?

        Uma passada de `pactl` para todos os nós — ver :data:`VIGIA_DO_MODO_S`.
        Sem endpoint não há o que vigiar, e a pergunta nem é feita.

        **O VIGIA OLHA OS DOIS NÓS DE CADA CONTROLE — RADIO-AFOGADO-01,
        22/09/2026.** Até esta data ele via só o endpoint da háptica, porque a
        ponte do som estava sempre de pé e não havia partida a esperar. Agora
        ela só sobe com som tocando, e um vigia cego ao `hefesto_som_<hex6>`
        deixaria o primeiro som dela esperar a volta inteira —
        :data:`RECONCILIA_S`, cinco segundos. A pergunta é a MESMA: os dois
        nomes vão na mesma passada, e `sinks_que_tocam` não cobra por nome.

        **NÃO DUPLICA A DECISÃO**, e por isso o palpite é grosseiro: quem
        decide o modo continua sendo `_casar_as_pontes`, que também pergunta
        quem o jogo LÊ. O vigia reusa a última resposta (`self._jogando`) só
        para não acordar a volta à toa; estar velha custa uma reconciliação a
        mais, nunca uma ponte errada.
        """
        nomes = {uniq: ep.nome for uniq, ep in self._endpoints.items() if ep.nome}
        if not nomes:
            return False
        try:
            # Import local pela mesma razão do `_reconciliar`: o módulo de som
            # puxa o PipeWire, e a importação no topo arrastaria isso para todo
            # processo que só quer o subsystem.
            from hefesto_dualsense4unix.integrations.alto_falante_bt import (
                nome_do_sink,
                sinks_que_tocam,
            )

            alto_falantes = {uniq: nome_do_sink(uniq) for uniq in nomes}
            tocando = sinks_que_tocam(
                [*nomes.values(), *(n for n in alto_falantes.values() if n)]
            )
        except Exception as exc:  # nunca derruba a thread do som
            logger.debug("vigia_do_modo_falhou", err=str(exc))
            return False
        if tocando is None:
            return False  # servidor mudo não é "ninguém toca"
        esperando = dict(self._esperando_vaga)
        for uniq, nome in nomes.items():
            if nome in tocando and uniq.lower() in self._jogando:
                agora: str | None = "haptica"
            elif alto_falantes.get(uniq, "") in tocando:
                agora = "som"
            else:
                agora = None
            # Quem espera vaga do governador já foi decidido nesta volta: a
            # pergunta está com ela. Acordar a volta não muda a resposta.
            if (self._modo_da_ponte.get(uniq) or esperando.get(uniq)) != agora:
                logger.info(
                    "vigia_do_modo_acordou_a_volta", uniq=uniq, modo=agora or "nenhuma"
                )
                return True
        return False

    def _reconciliar(self, gerenciador: Any) -> None:
        """Uma varredura: quem está na lista ganha nó, quem saiu perde.

        Passa os CONTROLES, não os ``uniq``: quem resolve a rota precisa do
        transporte ao lado, e ir buscá-lo depois seria uma segunda varredura de
        sysfs com a chance de discordar da primeira — que é o defeito que
        `bt_mic._conectados_da_mesa` já pagou.
        """
        alvos = self.alvos(list(self._fonte()))
        # A PONTE PRIMEIRO, O NÓ DEPOIS — e a ordem é medida, não estética.
        # `rota_do_no` pergunta à ponte se ela está de pé no momento em que o
        # nó nasce. Fiar na ordem inversa publicaria a rota do rádio como
        # recusada e só a corrigiria na varredura seguinte, 2 s depois: o jogo
        # que abrisse o nó nesse intervalo pegaria a rota errada.
        self._casar_as_pontes(alvos)
        gerenciador.reconciliar(alvos)


__all__ = [
    "RECONCILIA_S",
    "VIGIA_DO_MODO_S",
    "AltoFalanteSubsystem",
    "ControleNaLista",
    "GerenciadorDeNosDeSom",
    "controles_na_lista",
]
