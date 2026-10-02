"""As ondas sonoras da aba 02 — o que ENTRA e o que SAI, medido de verdade.

Pedido dela, 05/09/2026: *"ondas sonoras do auto falante e do microfone devem
ser reais na aba controle. sobre o audio que entra e o que sai"*.

Até aqui as catorze barrinhas de cada medidor eram DESENHO — quatorze alturas
digitadas no gerador (``aba02.CARDS[...]["mic_v"]``), iguais em todo tique, com
a dica do ``?`` prometendo ao lado *"a barra mostra o som entrando agora"*. A
tela afirmava uma medição que ninguém fazia.

## O QUE ESTE MÓDULO É, e o que ele NÃO refaz

Ele **não** inventa um segundo jeito de medir pico. Quem sabe abrir um fluxo de
pico nesta casa é a PEÇA B da luz do mic
(:mod:`hefesto_dualsense4unix.integrations.nivel_do_microfone`), e as duas
funções que importam vêm de lá inteiras:

* :func:`~...nivel_do_microfone.argv_do_medidor` — o ``parec`` com
  ``resample.peaks=true`` e ``--latency-msec=100``, as duas flags que aquela
  medição tornou obrigatórias;
* :func:`~...nivel_do_microfone.abrir_fluxo` — que ainda pendura o
  ``PR_SET_PDEATHSIG`` no filho, a cura do ``parec`` órfão que segurava o
  microfone dela aberto.

O que este módulo acrescenta é UMA coisa: **o pico bruto não se perde**. A PEÇA
B consome cada amostra na histerese e devolve um ``bool`` — a pergunta dela é
*"está entrando som?"*. A pergunta desta é *"quanto, nos últimos 560 ms?"*, e a
resposta é uma fila de catorze alturas.

## POR QUE UM SEGUNDO MEDIDOR NÃO ATRAPALHA O PRIMEIRO

Os dois abrem fluxo na mesma fonte, e isso foi medido antes de ser escrito: o
cabeçalho da PEÇA B relata 20 s com DOIS fluxos simultâneos na mesma fonte do
DualSense, com os picos casando em 0,01 dB.

E o fluxo daqui **não acende a luz do microfone por engano**, que era o risco
real: a PEÇA A (``quem_ouve_o_microfone``) desconta todo ``source-output`` com
``resample.peaks``, *"seja nosso ou de estranho"* — e o argv que usamos é o
mesmo, com as mesmas três marcas. Um fluxo em modo de pico recebe ``max|x|``
por bloco, não áudio: ele não consegue ouvir ninguém.

## OS DOIS LADOS, e o de SAÍDA é o que não existia

=========  ==================================================  ===============
lado       o nó                                                quem dá o nome
=========  ==================================================  ===============
entra      a source do microfone                               o daemon, em
                                                               ``audio.canal_fonte``
sai        o ``.monitor`` do sink do controle                   ``audio_saida.
                                                               RotaDasDuasCamadas.
                                                               sink_do_controle``
=========  ==================================================  ===============

Os dois endereços já estavam na mão de quem pinta a aba 02, e nenhum custa uma
leitura nova: o primeiro vem no ``state_full`` e o segundo já está no cache que
``a02_controles._camada_1`` renova a cada dois segundos.

**O monitor de um sink é uma source como outra qualquer** — o mesmo ``parec``, o
mesmo modo de pico. Medido em 05/09/2026 nesta máquina, com um tom de amplitude
conhecida tocado num sink de teste: pedido 0,500 → lido 0,499969; pedido 0,120 →
lido 0,119995. O medidor devolve a amplitude que entrou, não uma aproximação.

**E ABRIR O MONITOR NÃO ACORDA O APARELHO.** Era a objeção séria — segurar o
isócrono USB da saída do DualSense o dia inteiro custaria bateria dela. Medido
no mesmo dia, lendo ``pactl list sinks short`` antes, durante (duas vezes) e
depois de um fluxo de monitor no sink do DualSense dela: ``IDLE`` nas quatro
leituras. O fluxo de monitor não muda o estado do sink.

## O CUSTO, e por que ele não entra no tique

O trabalho todo vive na thread deste módulo, num ``selectors`` só — quatro nós
são quatro descritores no MESMO ``epoll``, não quatro threads. Quem pinta a aba
só copia uma fila de catorze inteiros, que é a razão de o custo do tique não se
mexer (medido: mediana 1,73 ms antes, 1,80 ms depois).

A taxa é a da PEÇA B, 25 Hz — **100 bytes por segundo por nó**, já mastigados
pelo servidor. As catorze barras são 560 ms de história.

## ELE NASCE DESLIGADO, e isso é a trava da suíte

:func:`ligar` é chamada pelo piloto (``hefesto_vivo.main``), e por mais ninguém.
Sem ela, :meth:`OndasDeSom.seguir` não abre processo nenhum e
:meth:`OndasDeSom.alturas` responde ``None`` — *não sei*.

A razão é medida e é da casa: a suíte chama ``a02_controles.pacote()`` centenas
de vezes, e um medidor que abrisse ``parec`` a cada chamada seguraria o
microfone DELA aberto durante a suíte inteira. O ``_camada_1`` desta mesma aba
já tolera um ``pactl`` na thread; um fluxo de captura persistente é outra ordem
de grandeza, e a trava é explícita em vez de torcida.

## ``None`` NUNCA VIRA ZERO — é a regra que a PEÇA B escreveu e vale aqui

``None`` quer dizer *não há leitura*: controle no rádio (que não publica canal
nenhum), máquina sem ``parec``, fluxo recém-aberto que ainda não entregou
amostra, fluxo que morreu. Devolver zero afirmaria silêncio medido, e a barra no
piso é exatamente o que o desenho mostra quando o microfone está mudo — os dois
estados ficariam iguais na tela.

Quem pinta traduz esse ``None`` numa marca própria (a classe ``sem-leitura`` da
aba 02), e não no travessão: ``style.height = '—%'`` é CSS inválido, que o
CSSOM **descarta calado** e deixa o pixel do desenho no lugar. É o defeito que
a aba 02 já pagou uma vez, na barra de bateria do lugar vazio.
"""

from __future__ import annotations

import contextlib
import os
import selectors
import struct
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from hefesto_dualsense4unix.integrations.nivel_do_microfone import (
    MUDEZ_S,
    Fluxo,
    abrir_fluxo,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

BARRAS = 14

PISO_PCT = 16

PICO_CHEIO = 0.5

_TAM_AMOSTRA = 4

_LOTE_BYTES = 4096

_ESPERA_DO_SELETOR_S = 0.2

_ESPERA_APOS_MORTE_S = 2.0

_LIGADO = [False]


def ligar(ligado: bool = True) -> None:
    """Autoriza este módulo a abrir fluxo. Só o piloto chama."""
    _LIGADO[0] = bool(ligado)
    if not _LIGADO[0]:
        parar_o_de_sempre()


@dataclass
class _Canal:
    """Um nó sendo medido: o fluxo aberto, a fila de picos e o que sobrou."""

    no: str
    fluxo: Fluxo
    picos: list[float] = field(default_factory=list)
    resto: bytearray = field(default_factory=bytearray)
    ultimo_dado: float = 0.0


class OndasDeSom:
    """Mede o pico de cada nó pedido e guarda os últimos :data:`BARRAS`."""

    def __init__(
        self,
        *,
        abrir: Callable[[str, str], Fluxo | None] = abrir_fluxo,
        agora: Callable[[], float] = time.monotonic,
        barras: int = BARRAS,
        piso_pct: int = PISO_PCT,
        pico_cheio: float = PICO_CHEIO,
        mudez_s: float = MUDEZ_S,
        automatico: bool = True,
    ) -> None:
        self._abrir = abrir
        self._agora = agora
        self._barras = max(1, int(barras))
        self._piso = max(0, min(100, int(piso_pct)))
        self._cheio = pico_cheio if pico_cheio > 0 else PICO_CHEIO
        self._mudez_s = mudez_s
        self._automatico = automatico
        self._lock = threading.RLock()
        self._desejado: dict[str, str] = {}
        self._canais: dict[str, _Canal] = {}
        self._proxima_tentativa: dict[str, float] = {}
        self._seletor = selectors.DefaultSelector()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None


    def seguir(self, alvos: Mapping[str, str]) -> None:
        """Passa a medir exatamente estes nós — nem mais, nem menos."""
        with self._lock:
            self._desejado = {k: v for k, v in alvos.items() if k}
        if self._automatico and _LIGADO[0]:
            self._garantir_thread()

    def alturas(self, no: str) -> tuple[int, ...] | None:
        """As :data:`BARRAS` últimas alturas em por cento, ou ``None``."""
        agora = self._agora()
        with self._lock:
            canal = self._canais.get(no)
            if canal is None or not canal.picos:
                return None
            if (agora - canal.ultimo_dado) >= self._mudez_s:
                return None
            picos = list(canal.picos)
        faltam = self._barras - len(picos)
        if faltam > 0:
            return tuple([self._piso] * faltam + [self._pct(p) for p in picos])
        return tuple(self._pct(p) for p in picos[-self._barras:])

    def parar(self) -> None:
        """Fecha tudo. Idempotente, e não levanta."""
        self._parar.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        self._thread = None
        with self._lock:
            self._desejado = {}
            for no in list(self._canais):
                self._fechar(no)

    def __enter__(self) -> OndasDeSom:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.parar()


    def _pct(self, pico: float) -> int:
        """Pico linear -> altura de barra, entre :data:`PISO_PCT` e 100."""
        if pico != pico or pico < 0.0:
            pico = 0.0
        fatia = min(1.0, pico / self._cheio)
        return round(self._piso + fatia * (100 - self._piso))


    def bombear(self, timeout_s: float = _ESPERA_DO_SELETOR_S) -> None:
        """Uma volta: reconcilia os fluxos e come o que chegou."""
        self._reconciliar()
        for chave, _mascara in self._seletor.select(timeout=timeout_s):
            self._comer(str(chave.data), self._agora())

    def _rodar(self) -> None:  # pragma: no cover - exercitado só com thread
        while not self._parar.is_set():
            try:
                self.bombear()
            except Exception as exc:
                logger.warning("ondas_de_som_volta_falhou", err=str(exc))
                time.sleep(_ESPERA_DO_SELETOR_S)

    def _garantir_thread(self) -> None:
        with self._lock:
            if self._thread is not None or self._parar.is_set():
                return
            self._thread = threading.Thread(
                target=self._rodar, name="hefesto-ondas-de-som", daemon=True
            )
        self._thread.start()


    def _reconciliar(self) -> None:
        agora = self._agora()
        with self._lock:
            desejado = dict(self._desejado)
            for no, canal in list(self._canais.items()):
                if no not in desejado or not canal.fluxo.vivo():
                    self._fechar(no)
            faltam = [
                (n, u) for n, u in desejado.items() if n not in self._canais
            ]
        if not _LIGADO[0]:
            return
        for no, uniq in faltam:
            if agora < self._proxima_tentativa.get(no, 0.0):
                continue
            self._abrir_canal(no, uniq, agora)

    def _abrir_canal(self, no: str, uniq: str, agora: float) -> None:
        fluxo = self._abrir(no, uniq)
        if fluxo is None:
            self._proxima_tentativa[no] = agora + _ESPERA_APOS_MORTE_S
            return
        canal = _Canal(no=no, fluxo=fluxo, ultimo_dado=agora)
        try:
            self._seletor.register(fluxo.fd, selectors.EVENT_READ, no)
        except (KeyError, ValueError, OSError) as exc:  # pragma: no cover
            logger.warning("ondas_de_som_seletor_recusou", no=no, err=str(exc))
            fluxo.parar()
            self._proxima_tentativa[no] = agora + _ESPERA_APOS_MORTE_S
            return
        with self._lock:
            self._canais[no] = canal
        self._proxima_tentativa.pop(no, None)
        logger.info("ondas_de_som_abriu", no=no, uniq=uniq)

    def _fechar(self, no: str) -> None:
        """Chamado SEMPRE com o lock tomado."""
        canal = self._canais.pop(no, None)
        if canal is None:
            return
        with contextlib.suppress(KeyError, ValueError, OSError):
            self._seletor.unregister(canal.fluxo.fd)
        canal.fluxo.parar()
        logger.info("ondas_de_som_fechou", no=no)

    def _comer(self, no: str, agora: float) -> None:
        with self._lock:
            canal = self._canais.get(no)
        if canal is None:
            return
        try:
            dados = os.read(canal.fluxo.fd, _LOTE_BYTES)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            dados = b""
        if not dados:
            with self._lock:
                self._fechar(no)
            self._proxima_tentativa[no] = agora + _ESPERA_APOS_MORTE_S
            logger.info("ondas_de_som_fluxo_morreu", no=no)
            return
        canal.resto += dados
        inteiras = len(canal.resto) // _TAM_AMOSTRA
        if not inteiras:
            return
        with self._lock:
            for i in range(inteiras):
                canal.picos.append(
                    struct.unpack_from("<f", canal.resto, i * _TAM_AMOSTRA)[0]
                )
            del canal.resto[: inteiras * _TAM_AMOSTRA]
            if len(canal.picos) > self._barras * 2:
                del canal.picos[: len(canal.picos) - self._barras * 2]
            canal.ultimo_dado = agora


_DE_SEMPRE: list[OndasDeSom | None] = [None]


def o_de_sempre() -> OndasDeSom:
    """O medidor único deste processo, construído na primeira chamada."""
    atual = _DE_SEMPRE[0]
    if atual is None:
        atual = OndasDeSom()
        _DE_SEMPRE[0] = atual
    return atual


def parar_o_de_sempre() -> None:
    """Fecha o medidor único, se houver. Idempotente."""
    atual = _DE_SEMPRE[0]
    if atual is not None:
        atual.parar()


__all__ = [
    "BARRAS",
    "PICO_CHEIO",
    "PISO_PCT",
    "OndasDeSom",
    "ligar",
    "o_de_sempre",
    "parar_o_de_sempre",
]
