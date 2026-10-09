"""O transiente do som do jogo: o estalo do tiro e o lado de onde ele vem.

O-TIRO-VEM-DO-LADO-CERTO-01 (08/10/2026). O motor do tato vivo só sabia «houve
um tiro»; o lado (esquerdo, direito) mora no som posicional do jogo, que chega
mais forte num canal do que no outro. Este módulo tem três peças:

* :class:`DetectorDeTransiente` (pura): PCM estéreo s16 em janelas de 5 ms, o
  envelope de cada canal, um limiar que se adapta ao fundo (a média recente
  mais um múltiplo do desvio, e um salto mínimo sobre a média), histerese e
  refratário. Sai ``(instante, lado, energia)``; o lado é a razão
  ``(R - L) / (R + L)`` do envelope na janela do estalo, e perto de zero é
  «centro».
* :func:`fluxo_do_jogo` (pura): entre os fluxos que tocam, o do processo de
  JOGO (os pids de :func:`quem_o_jogo_le.pids_de_jogo`), nunca o som do
  sistema inteiro.
* :class:`OuvidoDoJogo`: um gravador só para a máquina, que mira o fluxo do
  jogo e entrega os transientes numa fila. Só sobe quando quem o liga quer
  (a receita pede o lado do som e há jogo); sem fluxo de jogo, fica calado.

O gravador NÃO é o :func:`alto_falante_bt.argv_do_gravador`: aquele lê o
monitor de um SINK (o alvo dele sai de ``pactl list sinks``), e o fluxo do
jogo não é sink. Os programas e o formato são os mesmos (``pw-record`` ou
``parec``, s16, a mesma latência), mirando o fluxo; e o nó nasce com o
``RECUO_PROIBIDO_DO_OUVIDO`` da ponte, porque o alvo de reserva de um gravador
é o microfone.
"""
from __future__ import annotations

import contextlib
import math
import operator
import shutil
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    LATENCIA_DO_GRAVADOR_MS,
    RECUO_PROIBIDO_DO_OUVIDO,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TAXA = 48_000
CANAIS = 2
JANELA_S = 0.005
QUADROS_POR_JANELA = int(TAXA * JANELA_S)
BYTES_POR_JANELA = QUADROS_POR_JANELA * CANAIS * 2
ESCALA = 32768.0

#: a média do fundo segue o som em ~0,1 s; o desvio, em ~0,5 s.
TAU_DA_MEDIA_S = 0.1
TAU_DO_DESVIO_S = 0.5
#: o estalo tem de saltar sobre o fundo: N vezes a média E a média mais K desvios.
SALTO = 3.0
DESVIOS = 4.0
#: a histerese: rearma quando o envelope volta para perto do fundo.
REARMA_SALTO = 1.5
#: abaixo disto (-34 dBFS) é silêncio, e silêncio não dispara.
PISO = 0.02
#: um tiro é um evento: o eco e o rabo do mesmo estalo não disparam de novo.
REFRATARIO_S = 0.04
#: o começo do fluxo só ensina o fundo.
AQUECIMENTO_S = 0.1
#: |razão| abaixo disto é «centro».
CENTRO = 0.25
#: o envelope (RMS) que vale o toque inteiro (-6 dBFS).
ENERGIA_CHEIA = 0.5

LADO_ESQUERDO = "esquerdo"
LADO_DIREITO = "direito"
LADO_CENTRO = "centro"

_SOMA_DOS_PRODUTOS: Callable[[Any, Any], float] | None = getattr(math, "sumprod", None)


def _energia(amostras: Sequence[int]) -> float:
    """O RMS de um canal, em fração da escala cheia."""
    if not amostras:
        return 0.0
    if _SOMA_DOS_PRODUTOS is not None:
        soma = _SOMA_DOS_PRODUTOS(amostras, amostras)
    else:
        soma = sum(map(operator.mul, amostras, amostras))
    return math.sqrt(soma / len(amostras)) / ESCALA


def lado_da_razao(esquerda: float, direita: float) -> str:
    """O lado pela razão ``(R - L) / (R + L)``; perto de zero, «centro»."""
    total = esquerda + direita
    if total <= 0.0:
        return LADO_CENTRO
    razao = (direita - esquerda) / total
    if razao >= CENTRO:
        return LADO_DIREITO
    if razao <= -CENTRO:
        return LADO_ESQUERDO
    return LADO_CENTRO


@dataclass(frozen=True)
class Transiente:
    """Um estalo do som do jogo: quando, de que lado e com que força (0 a 1)."""

    instante: float
    lado: str
    energia: float


class DetectorDeTransiente:
    """O limiar que se adapta ao fundo, com histerese e refratário. Sem relógio próprio."""

    def __init__(
        self,
        *,
        refratario_s: float = REFRATARIO_S,
        salto: float = SALTO,
        desvios: float = DESVIOS,
        adapta: bool = True,
    ) -> None:
        self.refratario_s = refratario_s
        self.salto = salto
        self.desvios = desvios
        self.adapta = adapta
        self._alfa_media = JANELA_S / TAU_DA_MEDIA_S
        self._alfa_desvio = JANELA_S / TAU_DO_DESVIO_S
        self._sobra = b""
        self._media: float | None = None
        self._desvio = 0.0
        self._ouvido_s = 0.0
        self._armado = True
        self._ultimo: float | None = None
        self.janelas = 0

    def ouvir(self, pcm: bytes, agora: float) -> list[Transiente]:
        """Os transientes do pedaço ``pcm``, que acabou de chegar em ``agora``."""
        dados = self._sobra + pcm
        inteiras = len(dados) // BYTES_POR_JANELA
        self._sobra = dados[inteiras * BYTES_POR_JANELA:]
        if not inteiras:
            return []
        amostras = memoryview(dados[: inteiras * BYTES_POR_JANELA]).cast("h")
        achados: list[Transiente] = []
        por_janela = QUADROS_POR_JANELA * CANAIS
        for i in range(inteiras):
            janela = amostras[i * por_janela:(i + 1) * por_janela]
            esquerda = _energia(janela[0::2])
            direita = _energia(janela[1::2])
            # A janela i acabou (inteiras - 1 - i) janelas antes do fim do pedaço.
            instante = agora - (inteiras - 1 - i) * JANELA_S
            achado = self._janela(esquerda, direita, instante)
            if achado is not None:
                achados.append(achado)
        return achados

    def _janela(self, esquerda: float, direita: float, instante: float) -> Transiente | None:
        self.janelas += 1
        nivel = max(esquerda, direita)
        if self._media is None:
            self._media = nivel
        media, desvio = self._media, self._desvio
        self._ouvido_s += JANELA_S
        if not self.adapta:
            media, desvio = PISO, 0.0
        achado: Transiente | None = None
        if self._armado:
            dispara = (
                self._ouvido_s > AQUECIMENTO_S
                and nivel >= PISO
                and nivel >= self.salto * media
                and nivel >= media + self.desvios * desvio
                and (self._ultimo is None or instante - self._ultimo >= self.refratario_s)
            )
            if dispara:
                self._armado = False
                self._ultimo = instante
                achado = Transiente(
                    instante, lado_da_razao(esquerda, direita),
                    min(1.0, nivel / ENERGIA_CHEIA),
                )
        elif nivel <= REARMA_SALTO * media or nivel < PISO:
            self._armado = True
        # O fundo aprende depois da decisão: o estalo não sobe o próprio limiar.
        self._media += self._alfa_media * (nivel - self._media)
        self._desvio += self._alfa_desvio * (abs(nivel - self._media) - self._desvio)
        return achado


# --- O fluxo do jogo -------------------------------------------------------

#: o nome do NOSSO nó de gravação: único na máquina, e é o que a conferência procura.
ROTULO_DO_OUVIDO = "hefesto-tato-ouvido-do-jogo"


@dataclass(frozen=True)
class FluxoDoJogo:
    """O fluxo que o jogo toca: o índice do servidor, o serial do nó e o nome dele."""

    indice: int
    serial: int | None
    nome: str
    pid: int


def _pid_do_fluxo(propriedades: Mapping[str, str]) -> int | None:
    bruto = str(propriedades.get("application.process.id", "")).strip()
    return int(bruto) if bruto.isdigit() else None


def fluxo_do_jogo(fluxos: Iterable[Any], pids: Iterable[int]) -> FluxoDoJogo | None:
    """O fluxo tocado por um processo de jogo; o que não está pausado vem antes."""
    dos_jogos = set(pids)
    if not dos_jogos:
        return None
    candidatos: list[tuple[bool, FluxoDoJogo]] = []
    for fluxo in fluxos:
        propriedades: Mapping[str, str] = getattr(fluxo, "propriedades", {}) or {}
        pid = _pid_do_fluxo(propriedades)
        nome = str(propriedades.get("node.name", "") or "")
        if pid is None or pid not in dos_jogos or nome.startswith("hefesto"):
            continue
        serial_cru = str(propriedades.get("object.serial", "")).strip()
        candidatos.append((
            bool(getattr(fluxo, "corked", False)),
            FluxoDoJogo(
                indice=int(getattr(fluxo, "indice", -1)),
                serial=int(serial_cru) if serial_cru.isdigit() else None,
                nome=nome,
                pid=pid,
            ),
        ))
    if not candidatos:
        return None
    candidatos.sort(key=lambda par: par[0])
    return candidatos[0][1]


#: os dois gravadores, na ordem da ponte do rádio; o alvo é o FLUXO do jogo.
GRAVADORES_DO_FLUXO: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "pw-record",
        ("--raw", "--target={serial}", f"--rate={TAXA}", f"--channels={CANAIS}",
         "--format=s16", "--latency={latencia_ms}ms", "-P",
         "node.name={rotulo}",
         "-"),
    ),
    (
        "parec",
        ("--monitor-stream={indice}", f"--rate={TAXA}", f"--channels={CANAIS}",
         "--format=s16le", "--raw", "--latency-msec={latencia_ms}",
         "--client-name={rotulo}"),
    ),
)


def argv_do_ouvido(
    fluxo: FluxoDoJogo,
    *,
    pipewire: bool,
    latencia_ms: int = LATENCIA_DO_GRAVADOR_MS,
    rotulo: str = ROTULO_DO_OUVIDO,
    propriedades: Sequence[str] = RECUO_PROIBIDO_DO_OUVIDO,
    achar: Callable[[str], str | None] = shutil.which,
) -> list[str]:
    """O comando que lê o PCM do fluxo do jogo. ``[]`` se não há como."""
    for binario, modelo in GRAVADORES_DO_FLUXO:
        if achar(binario) is None:
            continue
        if binario == "pw-record" and (not pipewire or fluxo.serial is None):
            continue
        argv = [binario, *(m.format(serial=fluxo.serial, indice=fluxo.indice,
                                    latencia_ms=latencia_ms, rotulo=rotulo)
                           for m in modelo)]
        if binario == "pw-record":
            indice = argv.index(f"node.name={rotulo}")
            argv[indice] = " ".join((argv[indice], *propriedades))
            return argv
        return [*argv, *(f"--property={p}" for p in propriedades)]
    return []


# --- O ouvido: um gravador só para a máquina ---------------------------------

PROCURA_S = 5.0
#: o ouvido está vivo enquanto o PCM chega; sem PCM há mais disto, o jogo calou.
VIVO_S = 1.0
LEITURA = BYTES_POR_JANELA * 4


class OuvidoDoJogo:
    """Acha o fluxo do jogo, grava, detecta e enfileira. Calado sem jogo ou sem pedido."""

    def __init__(
        self,
        querer: Callable[[], bool],
        *,
        achar_o_fluxo: Callable[[], FluxoDoJogo | None] | None = None,
        montar_argv: Callable[[FluxoDoJogo], list[str]] | None = None,
        abrir: Callable[[list[str]], Any] | None = None,
        derrubar: Callable[..., Any] | None = None,
        conferir_o_alvo: Callable[[str], str | None] | None = None,
        relogio: Callable[[], float] = time.monotonic,
        procura_s: float = PROCURA_S,
    ) -> None:
        self._querer = querer
        self._achar_o_fluxo = achar_o_fluxo or achar_o_fluxo_do_jogo
        self._montar_argv = montar_argv or montar_o_argv_do_ouvido
        self._abrir = abrir
        self._derrubar = derrubar
        self._conferir_o_alvo = conferir_o_alvo or conferir_o_alvo_do_ouvido
        self._relogio = relogio
        self.procura_s = procura_s
        self._fila: deque[Transiente] = deque(maxlen=256)
        self._trava = threading.Lock()
        self._parar = threading.Event()
        self._volta: threading.Thread | None = None
        self._proc: Any = None
        self._leitor: threading.Thread | None = None
        self._fluxo: FluxoDoJogo | None = None
        self._conferido = False
        self._ultimo_pcm = float("-inf")
        self.detector = DetectorDeTransiente()
        self.contadores = {"gravacoes": 0, "transientes": 0, "alvo_errado": 0}

    # A volta de procura -------------------------------------------------

    def comecar(self) -> None:
        """Sobe a volta de procura (idempotente). Ela dorme enquanto ninguém quer."""
        if self._volta is not None and self._volta.is_alive():
            return
        self._parar.clear()
        self._volta = threading.Thread(
            target=self._rodar, name="tato-ouvido-do-jogo", daemon=True
        )
        self._volta.start()

    def _rodar(self) -> None:
        while not self._parar.is_set():
            try:
                self.uma_volta()
            except Exception:
                logger.debug("tato_ouvido_volta_falhou", exc_info=True)
            self._parar.wait(self.procura_s)
        self._calar()

    def uma_volta(self) -> None:
        """Uma passada: cala sem pedido; sem gravador, procura; com ele, confere o alvo."""
        if not self._querer():
            self._calar()
            return
        if self._proc is not None and not self._gravando():
            self._calar()
        if self._proc is None:
            self._ligar()
            return
        if not self._conferido and self._fluxo is not None:
            alvo = self._conferir_o_alvo(ROTULO_DO_OUVIDO)
            if alvo is None:
                return  # «não sei» não derruba; pergunta de novo na próxima volta
            if alvo != self._fluxo.nome:
                self.contadores["alvo_errado"] += 1
                logger.warning("tato_ouvido_alvo_errado", alvo=alvo, fluxo=self._fluxo.nome)
                self._calar()
                return
            self._conferido = True

    def _gravando(self) -> bool:
        poll = getattr(self._proc, "poll", None)
        return self._proc is not None and (not callable(poll) or poll() is None)

    def _ligar(self) -> None:
        fluxo = self._achar_o_fluxo()
        if fluxo is None:
            return
        argv = self._montar_argv(fluxo)
        if not argv:
            return
        abrir = self._abrir
        if abrir is None:
            from hefesto_dualsense4unix.integrations.filho_de_som import lancar_leitor

            abrir = lancar_leitor
        proc = abrir(argv)
        saida = getattr(proc, "stdout", None)
        if saida is None:
            self._derrubar_o(proc, None)
            return
        self.detector = DetectorDeTransiente()
        self._fluxo = fluxo
        self._conferido = False
        self._proc = proc
        self.contadores["gravacoes"] += 1
        self._leitor = threading.Thread(
            target=self._ler, args=(saida,), name="tato-ouvido-leitor", daemon=True
        )
        self._leitor.start()
        logger.info("tato_ouvido_ligado", fluxo=fluxo.nome, pid=fluxo.pid)

    def _ler(self, saida: Any) -> None:
        while True:
            try:
                pedaco = saida.read(LEITURA)
            except (OSError, ValueError):
                return
            if not pedaco:
                return
            agora = self._relogio()
            self._ultimo_pcm = agora
            achados = self.detector.ouvir(pedaco, agora)
            if achados:
                with self._trava:
                    self._fila.extend(achados)
                    self.contadores["transientes"] += len(achados)

    def _derrubar_o(self, proc: Any, leitor: threading.Thread | None) -> None:
        derrubar = self._derrubar
        if derrubar is None:
            from hefesto_dualsense4unix.integrations.filho_de_som import (
                derrubar_leitor_de_pipe,
            )

            derrubar = derrubar_leitor_de_pipe
        with contextlib.suppress(Exception):
            derrubar(proc, leitor=leitor, junta_s=0.5, espera_s=0.5)

    def _calar(self) -> None:
        proc, leitor = self._proc, self._leitor
        self._proc = self._leitor = self._fluxo = None
        self._ultimo_pcm = float("-inf")
        if proc is not None:
            self._derrubar_o(proc, leitor)
            logger.info("tato_ouvido_calado")
        with self._trava:
            self._fila.clear()

    def parar(self) -> None:
        self._parar.set()
        volta = self._volta
        if volta is not None and volta is not threading.current_thread():
            volta.join(timeout=1.5)
        self._calar()

    # O que o motor lê ------------------------------------------------------

    @property
    def ouvindo(self) -> bool:
        """O PCM do jogo está chegando agora."""
        return self._proc is not None and self._relogio() - self._ultimo_pcm < VIVO_S

    def tirar(self) -> list[Transiente]:
        with self._trava:
            achados = list(self._fila)
            self._fila.clear()
        return achados


def achar_o_fluxo_do_jogo() -> FluxoDoJogo | None:
    """O fluxo do jogo nesta máquina, perguntado ao servidor de som e ao ``/proc``."""
    from hefesto_dualsense4unix.integrations.alto_falante_bt import rodar_pactl
    from hefesto_dualsense4unix.integrations.porta_do_som import ler_fluxos
    from hefesto_dualsense4unix.integrations.quem_o_jogo_le import pids_de_jogo

    fluxos = ler_fluxos("sink-inputs", rodar_pactl)
    if not fluxos:
        return None
    return fluxo_do_jogo(fluxos, pids_de_jogo())


def montar_o_argv_do_ouvido(fluxo: FluxoDoJogo) -> list[str]:
    from hefesto_dualsense4unix.integrations.alto_falante_bt import o_servidor_e_o_pipewire

    return argv_do_ouvido(fluxo, pipewire=o_servidor_e_o_pipewire())


def conferir_o_alvo_do_ouvido(rotulo: str) -> str | None:
    from hefesto_dualsense4unix.integrations.alto_falante_bt import (
        conferir_o_alvo_do_gravador,
    )

    return conferir_o_alvo_do_gravador(rotulo)


__all__ = [
    "GRAVADORES_DO_FLUXO",
    "ROTULO_DO_OUVIDO",
    "DetectorDeTransiente",
    "FluxoDoJogo",
    "OuvidoDoJogo",
    "Transiente",
    "achar_o_fluxo_do_jogo",
    "argv_do_ouvido",
    "conferir_o_alvo_do_ouvido",
    "fluxo_do_jogo",
    "lado_da_razao",
    "montar_o_argv_do_ouvido",
]
