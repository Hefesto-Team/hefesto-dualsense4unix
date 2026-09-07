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

1. **o nó vive só enquanto há controle.** Um nó permanente impediria o jogo de
   perder a saída na troca de transporte, e seria ruído na lista de som quando
   não há controle nenhum ligado. Ela escolheu o segundo lado: sem controle,
   sem nó. É por isso que :meth:`AltoFalanteSubsystem._reconciliar` derruba o
   nó de quem sumiu, e o teste que morde é o de tirar um controle da lista;
2. **no cabo ele não vira saída padrão.** ``priority.session`` baixa
   (``integrations.alto_falante_bt.PRIORIDADE_SESSAO_DO_SOM``). Publicar o nó
   é uma coisa; mandar o som do sistema para ele é outra, e a segunda é dela;
3. **a escolha entre ``0x32`` e ``0x39`` só depois do D5**, com o número de
   banda na mesa. Este subsystem **não escreve no rádio** e por isso não
   escolhe degrau nenhum.

O QUE ELE NÃO FAZ, E É METADE DO VALOR DE LER ISTO
---------------------------------------------------
* **não escreve um byte no aparelho.** Ele publica e derruba nós do PipeWire,
  e mais nada. Quem escreve no rádio é o ensaio de bancada
  (``scripts/ensaios/o_som_que_sai.py``), com a orelha dela do outro lado —
  e o mapa proíbe, com todas as letras, concluir daí que a ponte funciona —
  a forma de erro tem nome e é a **FALÁCIA DO CANAL QUE RESPONDE**: concluir
  que, porque um canal responde, ele FAZ o que a gente esperava dele. O
  honesto é o par: *o canal responde, e o conteúdo vai pelos dois arranjos
  candidatos*;
* **não liga o monitor ao sink USB do controle no cabo.** O link exige
  ``module-loopback`` e o casamento por dispositivo USB
  (``integrations.fontes_de_captura.escolher_sink``, ``integrations.usb_pai``),
  que estão fora da posse desta sprint. Ver a entrega;
* **não é registrado no daemon.** ``daemon/subsystems/__init__.py`` e
  ``daemon/lifecycle.py`` — os dois lugares que ligam um subsystem, e os dois
  fora da posse. **Este subsystem nasce órfão de propósito e declarado**, que é
  o oposto do defeito que o ``__init__.py`` do registry nomeia (o
  ``BtMicSubsystem`` nasceu órfão em 25/07 sem ninguém saber).
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)

#: Cadência da varredura de hotplug (sysfs). Não é polling de áudio: é só
#: *"apareceu/sumiu controle?"*. O mesmo número da metade de entrada.
RECONCILIA_S = 5.0


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

    ``reconciliar()`` é idempotente e barato, e é ele que faz o *"vive só
    enquanto há controle"* da decisão dela: um controle que sai da lista tem o
    nó derrubado, e os outros ficam de pé.
    """

    def __init__(self, *, fabrica: Any = None) -> None:
        self._fabrica = fabrica
        self._nos: dict[str, Any] = {}
        self._acordar = threading.Event()

    @property
    def nos(self) -> dict[str, Any]:
        return dict(self._nos)

    def _construir(self, uniq: str) -> Any:
        if self._fabrica is not None:
            return self._fabrica(uniq)
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            SinkVirtualPipeWire,
        )

        return SinkVirtualPipeWire(uniq=uniq)

    def reconciliar(self, uniqs: list[str] | None = None) -> None:
        """Casa os nós vivos com a lista de controles recebida.

        **Tirar um controle da lista DERRUBA o nó dele e deixa os outros de
        pé.** Sem isso, um controle sumir derrubaria o som dos quatro — que é
        exatamente o defeito de "a rota some debaixo do jogo", só que causado
        por nós.
        """
        alvos = [u for u in (uniqs or []) if u]
        for uniq in list(self._nos):
            if uniq not in alvos:
                self._derrubar(uniq)
        for uniq in alvos:
            if uniq in self._nos:
                continue
            no = self._construir(uniq)
            try:
                subiu = bool(no.iniciar())
            except Exception as exc:  # nunca derruba a varredura
                logger.debug("som_no_falhou", uniq=uniq, err=str(exc))
                continue
            if subiu:
                self._nos[uniq] = no
            else:
                logger.info("som_no_nao_subiu", uniq=uniq)

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

    def __init__(
        self,
        *,
        gerenciador: Any = None,
        fonte_de_controles: Any = None,
    ) -> None:
        self._gerenciador_injetado = gerenciador
        self._gerenciador: Any = None
        self._fonte = fonte_de_controles or controles_na_lista
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()

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

    def alvos(self, controles: list[Any]) -> list[str]:
        """Os ``uniq`` que ganham nó — os que têm identidade legível.

        Um controle sem ``HID_UNIQ`` NUNCA entra: sem endereço não há de quem
        seja o nó, e dois anônimos disputariam o mesmo nome. Ausência é
        resposta.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

        vistos: list[str] = []
        for controle in controles:
            uniq = str(getattr(controle, "uniq", "") or "")
            if not nome_do_sink(uniq) or uniq in vistos:
                continue
            vistos.append(uniq)
        return vistos

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

    async def start(self, ctx: DaemonContext) -> None:
        """Sobe a thread de reconciliação. Idempotente.

        Nada de bloquear o event loop: a varredura do sysfs e o ``pactl`` do
        ``load-module`` rodam na thread.
        """
        del ctx
        if self._thread is not None and self._thread.is_alive():
            return
        self._gerenciador = self._gerenciador_injetado or GerenciadorDeNosDeSom()
        self._parar.clear()
        self._thread = threading.Thread(
            target=self._loop, name="hefesto-som-sup", daemon=True
        )
        self._thread.start()
        logger.info("som_subsystem_iniciado")

    async def stop(self) -> None:
        """Derruba os nós. Idempotente.

        O ``join`` sai do event loop por ``to_thread``: segurar o loop do
        daemon por uma varredura em curso atrasaria o shutdown inteiro.
        """
        self._parar.set()
        gerenciador = self._gerenciador
        if gerenciador is not None:
            with contextlib.suppress(Exception):
                gerenciador.parar()
        thread = self._thread
        self._thread = None
        if thread is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(thread.join, 2.0)
        self._gerenciador = None
        logger.info("som_subsystem_parado")

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
            if self._parar.wait(RECONCILIA_S) or gerenciador.dormir(0.0):
                return

    def _reconciliar(self, gerenciador: Any) -> None:
        gerenciador.reconciliar(self.alvos(list(self._fonte())))


__all__ = [
    "RECONCILIA_S",
    "AltoFalanteSubsystem",
    "ControleNaLista",
    "GerenciadorDeNosDeSom",
    "controles_na_lista",
]
