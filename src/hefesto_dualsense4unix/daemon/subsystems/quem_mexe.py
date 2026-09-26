"""Quem joga: o controle físico que MEXEU desde que o jogo abriu.

A-HAPTICA-QUEM-JOGA-01, 26/09/2026 — decisão ``D-2609-QUEM-JOGA-E-QUEM-MEXE``.

O DEFEITO
=========
O portão da háptica pelo rádio (``alto_falante._casar_as_pontes``) só deixa
entrar em modo háptica o controle que o JOGO está lendo, e quem respondia era
``quem_o_jogo_le``, contando os ``eventN`` que um processo de jogo segura. O
winebus do GE-Proton **nunca mantém aberto o evdev de um DualSense** — nem o
físico nem o vpad ``0df2`` —, só o ``hidraw``. Com máscara DualSense a resposta
saía vazia por construção, e nenhum controle vibrava pelo rádio.

E o ``hidraw`` não separa quem joga: o ``winedevice`` segura o de TODOS os
vpads. Contá-lo devolveria o espelhado de 20/09 (o P3 vibrando num jogo de um
jogador). O report de saída que o jogo escreve no vpad também não separa: o
jogo escreveu gatilho em três vpads em 21/09, e a Steam escreve LED nos vpads
antes de o jogo abrir.

O SINAL QUE SOBRA, E O DAEMON JÁ O TEM
======================================
**Quem joga é o físico que teve entrada — botão, gatilho ou eixo fora da zona
morta — desde que o jogo abriu.** O daemon lê a entrada de cada controle a
cada tique para mandá-la ao vpad: o laço lê o do posto, e o
``CoopManager.forward_all`` lê cada secundário. A marca reusa essa leitura, sem
snapshot a mais, e custa uma comparação por controle e tique — e, com o jogo
fechado, um ``getattr``.

A PARTIDA É A JANELA
====================
A marca vale da abertura do jogo até ele fechar, e ZERA nas duas pontas. Quem
diz que o jogo abriu é a volta do portão, com o MESMO predicado com que ela já
decide se há jogo (``quem_o_jogo_le.pids_de_jogo``) e na MESMA varredura de
``/proc``: o jogo abre quando a volta vê processo de jogo e a anterior não via,
ou via um conjunto sem nenhum pid em comum (é outro jogo); fecha quando não vê
nenhum.

Não «os últimos N segundos»: numa cena parada (cutscene, menu, a pessoa lendo)
a háptica cairia no meio da cena que vibra. Quem pegou o controle nesta
partida está jogando nela.

O RISCO ACEITO, E O LIMITE
==========================
Um controle que alguém mexe, num jogo que não o lê, entra em háptica se o
endpoint dele tiver stream — aceito na decisão. E no Modo Nativo com mais de um
controle o daemon só lê o físico do posto (o co-op desmonta): os secundários
não são vistos por aqui.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable
from typing import Any

from hefesto_dualsense4unix.daemon.battery_journal import mascarar_endereco
from hefesto_dualsense4unix.integrations.quem_o_jogo_le import _digitos
from hefesto_dualsense4unix.integrations.uinput_mouse import MOVE_DEADZONE, STICK_CENTER
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O atributo do daemon onde mora o dono único das marcas.
ATRIBUTO = "_quem_mexe"

#: A zona morta do eixo e do gatilho, em 0..255. É o MESMO número com que a
#: casa já diz «o analógico se mexeu de propósito» — a zona do cursor
#: (``uinput_mouse.MOVE_DEADZONE``). O repouso de um DualSense fica a poucas
#: unidades do centro; um controle parado na mesa não marca.
ZONA_MORTA = MOVE_DEADZONE

_CRIACAO = threading.Lock()


def teve_entrada(
    *,
    botoes: Iterable[str],
    lx: int,
    ly: int,
    rx: int,
    ry: int,
    l2: int,
    r2: int,
) -> bool:
    """A mão está no controle neste tique? Botão, gatilho ou eixo fora da zona."""
    if botoes:
        return True
    if l2 > ZONA_MORTA or r2 > ZONA_MORTA:
        return True
    return any(abs(eixo - STICK_CENTER) > ZONA_MORTA for eixo in (lx, ly, rx, ry))


class QuemMexe:
    """As marcas da partida: ``{12 dígitos do físico: instante da primeira entrada}``.

    Escrito pelo laço do daemon (o tique) e lido pela volta e pelo vigia do
    alto-falante, que moram noutra thread — daí a trava. Fora da partida, a
    marca nem nasce: ``anotar`` devolve na primeira comparação.
    """

    def __init__(self, *, relogio: Callable[[], float] = time.monotonic) -> None:
        self._relogio = relogio
        self._trava = threading.Lock()
        self._marcas: dict[str, float] = {}
        #: Quando a partida começou (o relógio de ``relogio``); None = sem jogo.
        self._aberto_em: float | None = None
        #: Os pids de jogo que a última volta viu — para reconhecer outro jogo.
        self._pids: frozenset[int] = frozenset()

    # -- a partida (a volta do alto-falante) ------------------------------

    @property
    def jogo_aberto(self) -> bool:
        return self._aberto_em is not None

    def acompanhar_o_jogo(self, pids: Iterable[int]) -> None:
        """A volta diz quais processos de jogo viu; a partida abre, segue ou fecha.

        Abrir e fechar ZERAM as marcas: a entrada de antes da partida não é
        desta partida, e a de um jogo fechado não é do próximo.
        """
        agora = frozenset(pids)
        with self._trava:
            antes, aberto = self._pids, self._aberto_em
            self._pids = agora
            if not agora:
                if aberto is None:
                    return
                marcados = len(self._marcas)
                self._aberto_em = None
                self._marcas = {}
            elif aberto is None or agora.isdisjoint(antes):
                marcados = len(self._marcas)
                self._aberto_em = self._relogio()
                self._marcas = {}
            else:
                return
        if agora:
            logger.info("haptica_partida_aberta", processos=len(agora), zerou=marcados)
        else:
            logger.info("haptica_partida_fechada", quem_jogou=marcados)

    def quem_joga(self) -> frozenset[str]:
        """Os doze dígitos de quem mexeu nesta partida (vazio sem jogo)."""
        with self._trava:
            return frozenset(self._marcas) if self._aberto_em is not None else frozenset()

    def joga(self, uniq: object) -> bool:
        """``uniq`` (em qualquer grafia) mexeu nesta partida? O(1)."""
        chave = _digitos(uniq)
        return bool(chave) and self._aberto_em is not None and chave in self._marcas

    # -- o tique (o laço do daemon) ----------------------------------------

    def anotar(
        self,
        uniq: object,
        *,
        botoes: Iterable[str],
        lx: int,
        ly: int,
        rx: int,
        ry: int,
        l2: int,
        r2: int,
    ) -> None:
        """Marca ``uniq`` se a mão dele está no controle neste tique — O(1)."""
        if self._aberto_em is None:
            return
        if teve_entrada(botoes=botoes, lx=lx, ly=ly, rx=rx, ry=ry, l2=l2, r2=r2):
            self.marcar(uniq)

    def marcar(self, uniq: object) -> None:
        """``uniq`` teve entrada agora. Só a PRIMEIRA da partida escreve.

        As seguintes são uma pertinência num dicionário, sem trava. A primeira
        vai ao diário, uma vez por controle e partida — é a linha que diz, no
        gesto dela, quando o daemon passou a contar aquele controle.
        """
        chave = _digitos(uniq)
        if not chave or chave in self._marcas or self._aberto_em is None:
            return
        with self._trava:
            aberto = self._aberto_em
            if aberto is None or chave in self._marcas:
                return
            agora = self._relogio()
            # Troca o dicionário inteiro, nunca o muda no lugar: quem lê noutra
            # thread (a volta, o vigia) segura sempre um dicionário acabado.
            self._marcas = {**self._marcas, chave: agora}
        logger.info(
            "haptica_quem_joga",
            uniq=mascarar_endereco(chave),
            desde_a_abertura_s=round(agora - aberto, 1),
        )


def quem_mexe_de(daemon: Any) -> QuemMexe | None:
    """O dono único das marcas daquele daemon — criado na primeira pergunta.

    Quem cria é a volta do alto-falante (a única que sabe se há jogo); o laço
    só lê, por :func:`marcas_da_partida`. ``None`` sem daemon, ou num dublê que
    recusa atributo. A classe é conferida: num ``MagicMock`` o ``getattr``
    devolveria um mock, e um mock responde «sim» a toda pergunta.
    """
    if daemon is None:
        return None
    atual = getattr(daemon, ATRIBUTO, None)
    if isinstance(atual, QuemMexe):
        return atual
    with _CRIACAO:
        atual = getattr(daemon, ATRIBUTO, None)
        if isinstance(atual, QuemMexe):
            return atual
        novo = QuemMexe()
        try:
            setattr(daemon, ATRIBUTO, novo)
        except Exception:  # dublê que recusa atributo: sem marca, e sem exceção
            return None
        return novo


def marcas_da_partida(daemon: Any) -> QuemMexe | None:
    """As marcas, SÓ com a partida aberta — a pergunta do tique. Nunca cria.

    Com o jogo fechado, o custo por tique é este ``getattr`` e uma comparação.
    """
    marcas = getattr(daemon, ATRIBUTO, None)
    if isinstance(marcas, QuemMexe) and marcas.jogo_aberto:
        return marcas
    return None


def anotar_o_primario(daemon: Any, state: Any, botoes: Iterable[str]) -> None:
    """O laço marca o controle do posto com o que ele JÁ leu neste tique.

    ``state`` é o ``read_state()`` do tique (eixos e gatilhos do evdev do
    primário) e ``botoes`` o ``_evdev_buttons_once()`` — nenhum snapshot a mais.
    O ``primary_uniq`` só é perguntado quando há entrada. Nunca levanta: o
    laço do daemon não cai por uma marca.
    """
    marcas = marcas_da_partida(daemon)
    if marcas is None:
        return
    try:
        if not teve_entrada(
            botoes=botoes,
            lx=int(state.raw_lx),
            ly=int(state.raw_ly),
            rx=int(state.raw_rx),
            ry=int(state.raw_ry),
            l2=int(state.l2_raw),
            r2=int(state.r2_raw),
        ):
            return
        marcas.marcar(getattr(getattr(daemon, "controller", None), "primary_uniq", None))
    except Exception as exc:  # nunca derruba o laço
        logger.debug("haptica_marca_do_primario_falhou", err=str(exc))


__all__ = [
    "ATRIBUTO",
    "ZONA_MORTA",
    "QuemMexe",
    "anotar_o_primario",
    "marcas_da_partida",
    "quem_mexe_de",
    "teve_entrada",
]
