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
* :class:`Recorte` e :class:`TocadorDoEstalo` (O-SOM-DO-TIRO-SAI-TAMBEM-NO-CONTROLE-01):
  o detector recorta o estalo (de 30 a 80 ms, fim em silêncio) e o tocador o
  leva ao nó de som do controle de quem atirou, calado quando o jogo toca nele.

O gravador NÃO é o :func:`alto_falante_bt.argv_do_gravador`: aquele lê o
monitor de um SINK (o alvo dele sai de ``pactl list sinks``), e o fluxo do
jogo não é sink. Os programas e o formato são os mesmos (``pw-record`` ou
``parec``, s16, a mesma latência), mirando o fluxo; e o nó nasce com o
``RECUO_PROIBIDO_DO_OUVIDO`` da ponte, porque o alvo de reserva de um gravador
é o microfone.
"""
from __future__ import annotations

import contextlib
import fcntl
import math
import operator
import os
import select
import shutil
import subprocess
import threading
import time
from array import array
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    LATENCIA_DO_GRAVADOR_MS,
    RECUO_PROIBIDO_DO_OUVIDO,
    OrigemDoGravador,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TAXA = 48_000
CANAIS = 2
JANELA_S = 0.005
QUADROS_POR_JANELA = int(TAXA * JANELA_S)
BYTES_POR_JANELA = QUADROS_POR_JANELA * CANAIS * 2
ESCALA = 32768.0

TAU_DA_MEDIA_S = 0.1
TAU_DO_DESVIO_S = 0.5
SALTO = 3.0
DESVIOS = 4.0
REARMA_SALTO = 1.5
PISO = 0.02
REFRATARIO_S = 0.04
AQUECIMENTO_S = 0.1
CENTRO = 0.25
ENERGIA_CHEIA = 0.5

RECORTE_MINIMO_S = 0.03
RECORTE_MAXIMO_S = 0.08
QUEDA_DO_RECORTE = 0.25

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


JANELAS_DO_MINIMO = round(RECORTE_MINIMO_S / JANELA_S)
JANELAS_DO_MAXIMO = round(RECORTE_MAXIMO_S / JANELA_S)


def _apagar_no_fim(janela: bytes) -> bytes:
    """A janela com o volume caindo em linha até zero: o último quadro é silêncio."""
    amostras = array("h", janela)
    quadros = len(amostras) // CANAIS
    if quadros < 2:
        return bytes(len(janela))
    for q in range(quadros):
        fator = (quadros - 1 - q) / (quadros - 1)
        for c in range(CANAIS):
            amostras[q * CANAIS + c] = int(amostras[q * CANAIS + c] * fator)
    return amostras.tobytes()


class Recorte:
    """O estalo recortado do som do jogo. Nasce no disparo e se completa depois."""

    def __init__(self, instante: float) -> None:
        self.instante = instante
        self._janelas: list[bytes] = []
        self._pico = 0.0
        self._pronto = threading.Event()
        self.pcm = b""

    @property
    def janelas(self) -> int:
        return len(self._janelas)

    @property
    def pronto(self) -> bool:
        return self._pronto.is_set()

    @property
    def duracao_s(self) -> float:
        return len(self.pcm) / (TAXA * CANAIS * 2)

    def acrescentar(self, janela: bytes, nivel: float) -> bool:
        """Mais uma janela do estalo. ``True`` quando o recorte fechou."""
        if self.pronto:
            return True
        self._janelas.append(bytes(janela))
        self._pico = max(self._pico, nivel)
        quantas = len(self._janelas)
        if quantas >= JANELAS_DO_MAXIMO or (
            quantas >= JANELAS_DO_MINIMO and nivel < QUEDA_DO_RECORTE * self._pico
        ):
            self.fechar()
            return True
        return False

    def fechar(self) -> None:
        """Fecha com a última janela apagando até o silêncio. Idempotente."""
        if self.pronto:
            return
        if self._janelas:
            self._janelas[-1] = _apagar_no_fim(self._janelas[-1])
        self.pcm = b"".join(self._janelas)
        self._janelas = []
        self._pronto.set()


@dataclass(frozen=True)
class Transiente:
    """Um estalo do som do jogo: quando, de que lado e com que força (0 a 1)."""

    instante: float
    lado: str
    energia: float
    recorte: Recorte | None = field(default=None, compare=False)


class DetectorDeTransiente:
    """O limiar que se adapta ao fundo, com histerese e refratário. Sem relógio próprio."""

    def __init__(
        self,
        *,
        refratario_s: float = REFRATARIO_S,
        salto: float = SALTO,
        desvios: float = DESVIOS,
        adapta: bool = True,
        recortar: bool = False,
    ) -> None:
        self.refratario_s = refratario_s
        self.salto = salto
        self.desvios = desvios
        self.adapta = adapta
        self.recortar = recortar
        self._aberto: Recorte | None = None
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
            instante = agora - (inteiras - 1 - i) * JANELA_S
            achado = self._janela(esquerda, direita, instante)
            if achado is not None:
                achados.append(achado)
            if self.recortar:
                self._recortar(achado, janela.tobytes(), max(esquerda, direita))
        return achados

    def _recortar(self, achado: Transiente | None, janela: bytes, nivel: float) -> None:
        """O estalo novo abre um recorte (fechando o anterior); os outros o completam."""
        if achado is not None and achado.recorte is not None:
            self.fechar_o_recorte()
            self._aberto = achado.recorte
        aberto = self._aberto
        if aberto is not None and aberto.acrescentar(janela, nivel):
            self._aberto = None

    def fechar_o_recorte(self) -> None:
        """O recorte em curso fecha onde está: o fluxo acabou, ele não fica preso."""
        aberto, self._aberto = self._aberto, None
        if aberto is not None:
            aberto.fechar()

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
                    Recorte(instante) if self.recortar else None,
                )
        elif nivel <= REARMA_SALTO * media or nivel < PISO:
            self._armado = True
        self._media += self._alfa_media * (nivel - self._media)
        self._desvio += self._alfa_desvio * (abs(nivel - self._media) - self._desvio)
        return achado


ROTULO_DO_OUVIDO = "hefesto-tato-ouvido-do-jogo"


@dataclass(frozen=True)
class FluxoDoJogo:
    """O fluxo que o jogo toca: o índice do servidor, o serial do nó e o nome dele.

    A identidade é o ``serial`` (o ``object.serial``) e o ``ident`` (o ``object.id``,
    o id do grafo). O ``nome`` é o que o ``pactl`` entregou, e o do jogo com ™, ® ou
    acento chega vazio (``nome_perdido``): ele serve ao diário, nunca à conferência.
    """

    indice: int
    serial: int | None
    nome: str
    pid: int
    ident: int | None = None
    nome_perdido: bool = False


def _inteiro_da_propriedade(propriedades: Mapping[str, str], chave: str) -> int | None:
    bruto = str(propriedades.get(chave, "")).strip()
    return int(bruto) if bruto.isdigit() else None


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
        perdidos: frozenset[str] = getattr(fluxo, "perdidos", frozenset()) or frozenset()
        candidatos.append((
            bool(getattr(fluxo, "corked", False)),
            FluxoDoJogo(
                indice=int(getattr(fluxo, "indice", -1)),
                serial=_inteiro_da_propriedade(propriedades, "object.serial"),
                nome=nome,
                pid=pid,
                ident=_inteiro_da_propriedade(propriedades, "object.id"),
                nome_perdido="node.name" in perdidos,
            ),
        ))
    if not candidatos:
        return None
    candidatos.sort(key=lambda par: par[0])
    return candidatos[0][1]


def e_o_fluxo_pedido(origem: OrigemDoGravador | str | None, fluxo: FluxoDoJogo) -> bool | None:
    """O gravador se ligou ao fluxo pedido? ``None`` = não sei.

    O-NOME-DO-JOGO-COM-ACENTO-NAO-SE-PERDE-NO-PACTL-01 (24/10/2026): compara a
    IDENTIDADE do nó, o serial e depois o id do grafo. O nome do fluxo vem do
    ``pactl``, que entrega ``(null)`` no lugar de todo texto fora do ASCII (o ™ do
    Sackboy™), e o da origem vem do ``pw-dump``, inteiro: comparar os dois calava o
    ouvido a cada volta. O nome só decide quando nenhum dos lados tem identidade e o
    do fluxo não se perdeu. Uma origem que é só um texto é uma origem sem identidade.
    """
    if origem is None:
        return None
    if isinstance(origem, str):
        serial, ident, nome = None, None, origem
    else:
        serial, ident, nome = origem.serial, origem.ident, origem.nome
    if serial is not None and fluxo.serial is not None:
        return bool(serial == fluxo.serial)
    if ident is not None and fluxo.ident is not None:
        return bool(ident == fluxo.ident)
    if nome and fluxo.nome and not fluxo.nome_perdido:
        return nome == fluxo.nome
    return None


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


PROCURA_S = 5.0
VIVO_S = 1.0
PRAZO_DA_VOLTA_DO_OUVIDO_S = 1.5
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
        conferir_o_alvo: Callable[[str], OrigemDoGravador | str | None] | None = None,
        relogio: Callable[[], float] = time.monotonic,
        procura_s: float = PROCURA_S,
        recortar: Callable[[], bool] | None = None,
        ao_pcm: Callable[[bytes], object] | None = None,
    ) -> None:
        self._querer = querer
        self._ao_pcm = ao_pcm
        self._recortar = recortar or (lambda: False)
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
        self.detector.recortar = bool(self._recortar())
        if self._proc is not None and not self._gravando():
            self._calar()
        if self._proc is None:
            self._ligar()
            return
        if not self._conferido and self._fluxo is not None:
            origem = self._conferir_o_alvo(ROTULO_DO_OUVIDO)
            certo = e_o_fluxo_pedido(origem, self._fluxo)
            if certo is None:
                return
            if not certo:
                self.contadores["alvo_errado"] += 1
                identidade = origem if isinstance(origem, OrigemDoGravador) else None
                logger.warning(
                    "tato_ouvido_alvo_errado",
                    alvo=identidade.nome if identidade is not None else origem,
                    alvo_serial=identidade.serial if identidade is not None else None,
                    fluxo=self._fluxo.nome, serial=self._fluxo.serial,
                )
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
        self.detector = DetectorDeTransiente(recortar=bool(self._recortar()))
        self._fluxo = fluxo
        self._conferido = False
        self._proc = proc
        self.contadores["gravacoes"] += 1
        self._leitor = threading.Thread(
            target=self._ler, args=(saida,), name="tato-ouvido-leitor", daemon=True
        )
        self._leitor.start()
        logger.info("tato_ouvido_ligado", fluxo=fluxo.nome, serial=fluxo.serial, pid=fluxo.pid)

    def _ler(self, saida: Any) -> None:
        while True:
            try:
                pedaco = saida.read(LEITURA)
            except (OSError, ValueError):
                logger.debug("tato_ouvido_leitura_fechou", exc_info=True)
                return
            if not pedaco:
                return
            agora = self._relogio()
            self._ultimo_pcm = agora
            if self._ao_pcm is not None:
                try:
                    self._ao_pcm(pedaco)
                except Exception:
                    logger.debug("tato_ouvido_ao_pcm_falhou", exc_info=True)
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
        self.detector.fechar_o_recorte()
        with self._trava:
            self._fila.clear()

    def parar(self) -> None:
        self._parar.set()
        volta = self._volta
        if volta is not None and volta is not threading.current_thread():
            volta.join(timeout=PRAZO_DA_VOLTA_DO_OUVIDO_S)
        self._calar()

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


def conferir_o_alvo_do_ouvido(rotulo: str) -> OrigemDoGravador | None:
    """A origem do gravador do ouvido, com a identidade do nó. ``None`` = não sei."""
    from hefesto_dualsense4unix.integrations.alto_falante_bt import origem_do_gravador

    return origem_do_gravador(rotulo)


MARCA_DO_ESTALO = "hefesto-tato-estalo-"
QUADROS_DO_BLOCO = 480
BYTES_DO_BLOCO = QUADROS_DO_BLOCO * CANAIS * 2
_BLOCO_MUDO = bytes(BYTES_DO_BLOCO)
FOLGA_DO_ESTALO_S = 3.0
LATENCIA_DO_ESTALO_MS = 20
CANO_DO_ESTALO = 4096
PRAZO_DO_RECORTE_S = 0.2
VALIDADE_DA_GUARDA_S = 1.0
RECUSA_DO_ESTALO_S = 60.0
PRAZO_DA_ESCRITA_S = 1.0
PRAZO_DO_FIO_DO_ESTALO_S = 2.0
VIGIA_DO_ESTALO_S = 1.0
PRAZO_DA_MORTE_DO_ESTALO_S = 2.0
ESPERAS_DA_CONFERENCIA_S: tuple[float, ...] = (0.3, 0.7, 1.0)
RECUO_PROIBIDO_DO_ESTALO: tuple[str, ...] = (
    *RECUO_PROIBIDO_DO_OUVIDO,
    "state.restore-target=false",
    "state.restore-props=false",
)


def rotulo_do_estalo(sink: str) -> str:
    """O ``node.name`` do tocador do estalo deste nó de som. Sem endereço: o nó não tem."""
    return f"{MARCA_DO_ESTALO}{str(sink).lower()}"


def argv_do_estalo(
    sink: str,
    rotulo: str,
    *,
    serial: int | None,
    achar: Callable[[str], str | None] = shutil.which,
) -> list[str]:
    """O comando que toca o estalo (PCM s16 estéreo) no nó ``sink``. ``[]`` = não há como."""
    if not sink or not rotulo:
        return []
    if serial is not None and achar("pw-cat") is not None:
        return [
            "pw-cat", "--playback", "--raw", f"--target={serial}",
            f"--rate={TAXA}", f"--channels={CANAIS}", "--format=s16",
            f"--latency={LATENCIA_DO_ESTALO_MS}ms", "--volume=1.0",
            "-P", " ".join((f"node.name={rotulo}", f"media.name={rotulo}",
                            *RECUO_PROIBIDO_DO_ESTALO)),
            "-",
        ]
    if achar("pacat") is not None:
        return [
            "pacat", "--playback", "--raw", f"--device={sink}",
            f"--rate={TAXA}", f"--channels={CANAIS}", "--format=s16le",
            f"--latency-msec={LATENCIA_DO_ESTALO_MS}", "--volume=65536",
            f"--client-name={rotulo}", f"--stream-name={rotulo}",
            f"--property=node.name={rotulo}",
            *(f"--property={p}" for p in RECUO_PROIBIDO_DO_ESTALO),
        ]
    return []


def outro_fluxo_no_no(nos: Iterable[Any], fluxos: Iterable[Any], sink: str, rotulo: str) -> bool:
    """Há no nó ``sink`` um fluxo que não é o do estalo? É o jogo (ou o sistema) tocando nele."""
    indices = {str(getattr(no, "indice", "")) for no in nos if getattr(no, "nome", "") == sink}
    if not indices:
        return False
    for fluxo in fluxos:
        if str(getattr(fluxo, "alvo", "")) not in indices:
            continue
        propriedades: Mapping[str, str] = getattr(fluxo, "propriedades", {}) or {}
        if rotulo in (propriedades.get("node.name"), propriedades.get("media.name")):
            continue
        return True
    return False


def o_jogo_toca_no_no(sink: str, rotulo: str) -> bool | None:
    """Pergunta ao servidor de som. ``None`` = não sei, e quem chama cala."""
    from hefesto_dualsense4unix.integrations.alto_falante_bt import rodar_pactl
    from hefesto_dualsense4unix.integrations.porta_do_som import ler_fluxos, ler_nos

    nos = ler_nos("sinks", rodar_pactl)
    if nos is None:
        return None
    fluxos = ler_fluxos("sink-inputs", rodar_pactl)
    if fluxos is None:
        return None
    return outro_fluxo_no_no(nos, fluxos, sink, rotulo)


def montar_o_argv_do_estalo(sink: str, rotulo: str) -> list[str]:
    from hefesto_dualsense4unix.integrations.alto_falante_bt import (
        o_servidor_e_o_pipewire,
        serial_do_no,
    )

    serial = serial_do_no(sink) if o_servidor_e_o_pipewire() else None
    return argv_do_estalo(sink, rotulo, serial=serial)


def conferir_o_destino_do_estalo(rotulo: str) -> str | None:
    from hefesto_dualsense4unix.integrations.endpoint_de_haptica import (
        conferir_o_destino_do_tocador,
    )

    return conferir_o_destino_do_tocador(rotulo)


class TocadorDoEstalo:
    """O estalo do tiro no nó de som de UM controle. Nunca espera, nunca levanta."""

    def __init__(
        self,
        sink: str,
        *,
        o_jogo_toca: Callable[[str, str], bool | None] | None = None,
        argv_de: Callable[[str, str], list[str]] | None = None,
        lancar: Callable[..., Any] | None = None,
        conferir: Callable[[str], str | None] | None = None,
        ao_mudar: Callable[[], object] | None = None,
        folga_s: float = FOLGA_DO_ESTALO_S,
        prazo_do_recorte_s: float = PRAZO_DO_RECORTE_S,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.sink = str(sink)
        self.rotulo = rotulo_do_estalo(self.sink)
        self._o_jogo_toca = o_jogo_toca or o_jogo_toca_no_no
        self._argv_de = argv_de or montar_o_argv_do_estalo
        self._lancar: Callable[..., Any] = lancar or subprocess.Popen
        self._conferir = conferir or conferir_o_destino_do_estalo
        self._ao_mudar = ao_mudar
        self._folga_s = float(folga_s)
        self._prazo_do_recorte_s = float(prazo_do_recorte_s)
        self._relogio = relogio
        self._trava = threading.Lock()
        self._acordar = threading.Event()
        self._fim = threading.Event()
        self._fio: threading.Thread | None = None
        self._proc: Any = None
        self._vivo = False
        self._recusado_ate = float("-inf")
        self._pendente: tuple[Recorte, float] | None = None
        self._tocando = b""
        self._guarda: tuple[float, bool | None] | None = None
        self.contadores = {"pedidos": 0, "tocados": 0, "calados_pelo_jogo": 0, "atrasados": 0}

    @property
    def vivo(self) -> bool:
        proc = self._proc
        return bool(self._vivo and proc is not None and proc.poll() is None)

    def tocar(self, recorte: Recorte) -> None:
        """Põe o estalo na vez: o novo toma o lugar do que ainda não acabou."""
        with self._trava:
            self.contadores["pedidos"] += 1
            self._pendente = (recorte, self._relogio())
            if not self._fim.is_set() and (self._fio is None or not self._fio.is_alive()):
                self._fio = threading.Thread(
                    target=self._correr, name=f"hefesto-{self.rotulo}", daemon=True
                )
                self._fio.start()
        self._acordar.set()

    def parar(self) -> None:
        """Derruba o processo e o fio. Idempotente."""
        self._fim.set()
        self._acordar.set()
        self._matar(self._proc)
        fio = self._fio
        if fio is not None and fio is not threading.current_thread():
            fio.join(timeout=PRAZO_DO_FIO_DO_ESTALO_S)

    def _o_jogo_toca_agora(self) -> bool:
        """O jogo toca no nó do controle? Na dúvida, sim: o jogo manda."""
        agora = self._relogio()
        guarda = self._guarda
        if guarda is None or agora - guarda[0] >= VALIDADE_DA_GUARDA_S:
            try:
                resposta = self._o_jogo_toca(self.sink, self.rotulo)
            except Exception:
                resposta = None
            guarda = self._guarda = (agora, resposta)
        return guarda[1] is not False

    def proximo_bloco(self) -> bytes:
        """O trecho do estalo em curso, ou silêncio. Decide o pendente que ficou pronto."""
        with self._trava:
            pendente = self._pendente
        if pendente is not None:
            recorte, pedido_em = pendente
            if recorte.pronto:
                with self._trava:
                    if self._pendente is pendente:
                        self._pendente = None
                if self._o_jogo_toca_agora():
                    self.contadores["calados_pelo_jogo"] += 1
                else:
                    self.contadores["tocados"] += 1
                    with self._trava:
                        self._tocando = recorte.pcm
            elif self._relogio() - pedido_em > self._prazo_do_recorte_s:
                with self._trava:
                    if self._pendente is pendente:
                        self._pendente = None
                self.contadores["atrasados"] += 1
        with self._trava:
            trecho, self._tocando = (
                self._tocando[:BYTES_DO_BLOCO], self._tocando[BYTES_DO_BLOCO:]
            )
        if len(trecho) < BYTES_DO_BLOCO:
            trecho += _BLOCO_MUDO[len(trecho):]
        return trecho

    @property
    def em_curso(self) -> bool:
        return self._pendente is not None or bool(self._tocando)

    def _avisar(self) -> None:
        aviso = self._ao_mudar
        if aviso is not None:
            with contextlib.suppress(Exception):
                aviso()

    def _recusar(self, motivo: str) -> None:
        self._recusado_ate = self._relogio() + RECUSA_DO_ESTALO_S
        logger.info("tato_estalo_recusado", no=self.sink, motivo=motivo)

    def _correr(self) -> None:
        while not self._fim.is_set():
            self._acordar.wait(timeout=VIGIA_DO_ESTALO_S)
            self._acordar.clear()
            if self._fim.is_set():
                return
            if not self.em_curso:
                continue
            if self._relogio() < self._recusado_ate:
                with self._trava:
                    self._pendente, self._tocando = None, b""
                continue
            self._tocar()

    def _tocar(self) -> None:
        argv = self._argv_de(self.sink, self.rotulo)
        if not argv:
            self._recusar("sem_tocador")
            return
        try:
            proc = self._lancar(
                argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("tato_estalo_nao_subiu", no=self.sink, err=str(exc))
            self._recusar("nao_subiu")
            return
        self._proc = proc
        motivo = "silencio"
        try:
            fd = proc.stdin.fileno()
            with contextlib.suppress(OSError):
                fcntl.fcntl(fd, getattr(fcntl, "F_SETPIPE_SZ", 1031), CANO_DO_ESTALO)
            os.set_blocking(fd, False)
            motivo = self._escrever_enquanto_toca(proc, fd)
        except Exception as exc:
            logger.debug("tato_estalo_falhou", no=self.sink, err=str(exc))
            motivo = "falhou"
        finally:
            estava_vivo = self._vivo
            self._vivo = False
            self._matar(proc)
            self._proc = None
            if motivo not in ("silencio", "parado"):
                self._recusar(motivo)
            logger.info("tato_estalo_saiu", no=self.sink, motivo=motivo)
            if estava_vivo:
                self._avisar()

    def _escrever_enquanto_toca(self, proc: Any, fd: int) -> str:
        silencio_desde: float | None = None
        while not self._fim.is_set():
            if proc.poll() is not None:
                return "morreu"
            agora = self._relogio()
            if self.em_curso:
                silencio_desde = None
            elif silencio_desde is None:
                silencio_desde = agora
            elif agora - silencio_desde >= self._folga_s:
                return "silencio"
            if not self._escrever(fd, self.proximo_bloco()):
                return "parou_de_ler"
            if not self._vivo:
                self._vivo = True
                logger.info("tato_estalo_de_pe", no=self.sink)
                threading.Thread(
                    target=self._conferir_o_destino, args=(proc,), daemon=True,
                    name=f"hefesto-{self.rotulo}-conferencia",
                ).start()
                self._avisar()
        return "parado"

    def _escrever(self, fd: int, dados: bytes) -> bool:
        """Escreve o bloco inteiro; ``False`` = o tocador parou de ler ou morreu."""
        vista = memoryview(dados)
        espera = select.poll()
        espera.register(fd, select.POLLOUT)
        parado_desde: float | None = None
        while vista and not self._fim.is_set():
            try:
                prontos = espera.poll(100)
            except (OSError, ValueError):
                return False
            if any(ev & (select.POLLERR | select.POLLHUP | select.POLLNVAL) for _, ev in prontos):
                return False
            if not prontos:
                agora = self._relogio()
                parado_desde = agora if parado_desde is None else parado_desde
                if agora - parado_desde >= PRAZO_DA_ESCRITA_S:
                    return False
                continue
            parado_desde = None
            try:
                escritos = os.write(fd, vista)
            except BlockingIOError:
                escritos = 0
            except OSError:
                return False
            vista = vista[escritos:]
        return not vista

    def _conferir_o_destino(self, proc: Any) -> None:
        """Ligado a outro nó que não o do controle, o tocador morre: nunca na caixa."""
        for espera in ESPERAS_DA_CONFERENCIA_S:
            if self._fim.wait(espera) or proc.poll() is not None:
                return
            try:
                destino = self._conferir(self.rotulo)
            except Exception:
                destino = None
            if destino is None:
                continue
            if destino == self.sink:
                return
            logger.warning("tato_estalo_ligado_a_outro_no", no=self.sink)
            self._recusado_ate = self._relogio() + RECUSA_DO_ESTALO_S
            self._matar(proc)
            return

    @staticmethod
    def _matar(proc: Any) -> None:
        if proc is None:
            return
        with contextlib.suppress(Exception):
            proc.stdin.close()
        with contextlib.suppress(Exception):
            proc.kill()
        with contextlib.suppress(Exception):
            proc.wait(timeout=PRAZO_DA_MORTE_DO_ESTALO_S)


__all__ = [
    "GRAVADORES_DO_FLUXO",
    "MARCA_DO_ESTALO",
    "ROTULO_DO_OUVIDO",
    "DetectorDeTransiente",
    "FluxoDoJogo",
    "OuvidoDoJogo",
    "Recorte",
    "TocadorDoEstalo",
    "Transiente",
    "achar_o_fluxo_do_jogo",
    "argv_do_estalo",
    "argv_do_ouvido",
    "conferir_o_alvo_do_ouvido",
    "e_o_fluxo_pedido",
    "fluxo_do_jogo",
    "lado_da_razao",
    "montar_o_argv_do_ouvido",
    "o_jogo_toca_no_no",
    "outro_fluxo_no_no",
    "rotulo_do_estalo",
]
