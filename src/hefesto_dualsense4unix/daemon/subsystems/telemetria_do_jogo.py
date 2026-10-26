"""A telemetria do jogo de corrida chega ao gatilho (A-TELEMETRIA-DA-CORRIDA-CHEGA-AO-GATILHO-01).

Escuta o «Data Out» por UDP **só no localhost**, só com a Corrida ou a Simulação no perfil ativo, e
fecha a porta quando o estilo sai; nada se injeta no jogo. Traduz, com o portão de parado e a ordem
de ``PRIORIDADE``: o L2 pulsa como o ABS com a roda travada sob freio, o R2 vibra com a patinação
sob acelerador (de leve na zebra), a marcha é um Toque, a batida é um Impacto e a luz segue a
rotação sem passar de três subidas por segundo. Onde o jogo escreve, o jogo decide (``decidir``).
O porquê, os valores de partida e a bancada: ``docs/protocol/telemetria-da-corrida.md``.
"""
from __future__ import annotations

import asyncio
import contextlib
import math
import socket
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as _tv
from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import (
    CANAL_GATILHO,
    CANAL_HAPTICA,
    CICLO_DO_GATILHO_S,
    LADO_CENTRO,
    LADO_DIREITO,
    LADO_ESQUERDO,
    TETO_DA_LUZ_POR_S,
    EstadoDoCanal,
    Receita,
    _bloco_do_efeito,
    _o_modo_cala_o_motor,
    decidir,
)
from hefesto_dualsense4unix.integrations.telemetria_de_corrida import (
    EstadoDaCorrida,
    ler_o_pacote,
)
from hefesto_dualsense4unix.profiles import formas_de_haptica
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import TatoVivo

logger = get_logger(__name__)

RGB = tuple[int, int, int]

ESTILOS_DA_TELEMETRIA = frozenset({"corrida", "simulacao"})
ENDERECO = "127.0.0.1"
PORTA_DE_PARTIDA = 5300
VALIDADE_DO_PACOTE_S = 0.5
PACOTES_POR_VOLTA = 64
INTERVALO_DO_LACO_S = 1.0 / 60.0

VELOCIDADE_DE_PARADO_M_S = 0.1
GIRO_DE_PARADO_RAD_S = 1.0
ADERENCIA_PERDIDA = 1.0
FREIO_MINIMO = 0.1
ACELERADOR_MINIMO = 0.2

EFEITO_ABS = "abs"
EFEITO_PATINACAO = "patinacao"
EFEITO_ZEBRA = "zebra"
PRIORIDADE = (
    "colisao", "marcha", EFEITO_ABS, EFEITO_PATINACAO,  # (noqa-acento)
    "resistencia", "superficie")  # (noqa-acento)

FREQUENCIA_DO_ABS_HZ = 15
AMPLITUDE_DO_ABS = 6
FREQUENCIA_DA_PATINACAO_HZ = 30
FREQUENCIA_DA_ZEBRA_HZ = 25
AMPLITUDE_DA_ZEBRA = 2
HISTERESE_DA_PATINACAO = 2

BATIDA_M_S2 = 30.0
BATIDA_CHEIA_M_S2 = 60.0
REFRATARIO_DA_BATIDA_S = 0.5
ENERGIA_DA_MARCHA = 0.5
DURACAO_DA_MARCHA_MS = 30
DURACAO_DA_BATIDA_MS = 60

CORES_DA_ROTACAO: tuple[RGB, ...] = (
    (0, 200, 60), (120, 220, 0), (255, 200, 0), (255, 110, 0), (255, 0, 0))
ROTACAO_DO_PRIMEIRO_DEGRAU = 0.5
ROTACAO_DO_CORTE = 0.95
SEGURA_DA_ROTACAO_S = 1.0 / TETO_DA_LUZ_POR_S
JANELA_DA_ROTACAO_S = 1.0

_LADO_DO_BACKEND = {LADO_ESQUERDO: "left", LADO_DIREITO: "right"}

CANAL_DA_TELEMETRIA = "telemetria_da_corrida"


def em_movimento(estado: EstadoDaCorrida) -> bool:
    """O portão de parado: o carro anda, ou alguma roda gira (a patinação sai do lugar)."""
    if estado.velocidade_do_carro > VELOCIDADE_DE_PARADO_M_S:
        return True
    return any(abs(giro) > GIRO_DE_PARADO_RAD_S for giro in estado.giro_das_rodas)


@dataclass(frozen=True)
class PedidoDosGatilhos:
    """O que a corrida pede de cada gatilho: ``(efeito, amplitude)``, ou ``None`` (o perfil)."""

    l2: tuple[str, int] | None = None
    r2: tuple[str, int] | None = None

    def do_lado(self, lado: str) -> tuple[str, int] | None:
        return self.l2 if lado == LADO_ESQUERDO else self.r2


SEM_PEDIDO = PedidoDosGatilhos()


def degrau_da_patinacao(patinacao: float) -> int:
    """A amplitude (1 a 8) da patinação acima da aderência perdida."""
    return max(1, min(8, math.ceil((abs(patinacao) - ADERENCIA_PERDIDA) * 4)))


def pedido_da_corrida(estado: EstadoDaCorrida) -> PedidoDosGatilhos:
    """O L2 e o R2 que este pacote pede. Sem corrida, parado ou sem pedais (o curto), nada."""
    if not estado.corrida_ligada or not em_movimento(estado):
        return SEM_PEDIDO
    l2: tuple[str, int] | None = None
    r2: tuple[str, int] | None = None
    if estado.tem_pedais:
        freio = estado.freio or 0.0
        acelerador = estado.acelerador or 0.0
        travada = max(abs(x) for x in estado.razao_de_patinacao)
        if freio >= FREIO_MINIMO and travada > ADERENCIA_PERDIDA:
            l2 = (EFEITO_ABS, AMPLITUDE_DO_ABS)
        patina = max(abs(x) for x in estado.patinacao_combinada)
        if acelerador >= ACELERADOR_MINIMO and patina > ADERENCIA_PERDIDA:
            r2 = (EFEITO_PATINACAO, degrau_da_patinacao(patina))
    if r2 is None and any(estado.na_zebra):
        r2 = (EFEITO_ZEBRA, AMPLITUDE_DA_ZEBRA)
    return PedidoDosGatilhos(l2, r2)


def bloco_do_pedido(efeito: str, amplitude: int) -> bytes:
    """O bloco cru do efeito da corrida: a vibração no curso inteiro, na frequência de cada um."""
    from hefesto_dualsense4unix.core.trigger_effects import vibration

    frequencia = {
        EFEITO_ABS: FREQUENCIA_DO_ABS_HZ,
        EFEITO_PATINACAO: FREQUENCIA_DA_PATINACAO_HZ,
        EFEITO_ZEBRA: FREQUENCIA_DA_ZEBRA_HZ,
    }[efeito]
    return _bloco_do_efeito(vibration(0, max(1, min(8, amplitude)), frequencia))


@dataclass(frozen=True)
class ToqueDaCorrida:
    """Um toque no corpo: a marcha (o Toque) ou a batida (o Impacto)."""

    tipo: str
    energia: float
    forma: str
    duracao_ms: int


class LeitorDosToques:
    """A marcha que trocou e a batida, pacote a pacote; um toque por pacote, a colisão primeiro."""

    def __init__(self) -> None:
        self._marcha: int | None = None
        self._acima = False
        self._batida_em = float("-inf")

    def esquecer(self) -> None:
        self._marcha = None
        self._acima = False

    def ver(self, estado: EstadoDaCorrida, agora: float) -> ToqueDaCorrida | None:
        horizontal = math.hypot(estado.aceleracao[0], estado.aceleracao[2])
        acima, self._acima = self._acima, horizontal >= BATIDA_M_S2
        marcha_antes, self._marcha = self._marcha, estado.marcha
        if not estado.corrida_ligada or not em_movimento(estado):
            return None
        if self._acima and not acima and agora - self._batida_em >= REFRATARIO_DA_BATIDA_S:
            self._batida_em = agora
            return ToqueDaCorrida(
                "colisao", min(1.0, horizontal / BATIDA_CHEIA_M_S2),  # (noqa-acento)
                formas_de_haptica.IMPACTO, DURACAO_DA_BATIDA_MS)
        if marcha_antes is not None and estado.marcha is not None and estado.marcha != marcha_antes:
            return ToqueDaCorrida("marcha", ENERGIA_DA_MARCHA, formas_de_haptica.TOQUE,
                                  DURACAO_DA_MARCHA_MS)
        return None


class LuzDaRotacao:
    """O degrau da cor pela rotação: sobe no máximo três vezes por segundo e só desce depois de
    segurar um terço de segundo (o limitador de giro no corte não vira pisca-pisca)."""

    def __init__(self) -> None:
        self.degrau: int | None = None
        self._mudou_em = float("-inf")
        self._subidas: deque[float] = deque()

    def esquecer(self) -> None:
        self.degrau = None
        self._subidas.clear()

    @staticmethod
    def degrau_da_fracao(fracao: float) -> int:
        if fracao <= ROTACAO_DO_PRIMEIRO_DEGRAU:
            return 0
        if fracao >= ROTACAO_DO_CORTE:
            return len(CORES_DA_ROTACAO) - 1
        faixa = (ROTACAO_DO_CORTE - ROTACAO_DO_PRIMEIRO_DEGRAU) / (len(CORES_DA_ROTACAO) - 1)
        return min(len(CORES_DA_ROTACAO) - 2,
                   int((fracao - ROTACAO_DO_PRIMEIRO_DEGRAU) / faixa))

    def andar(self, fracao: float, agora: float) -> int:
        quer = self.degrau_da_fracao(fracao)
        while self._subidas and agora - self._subidas[0] >= JANELA_DA_ROTACAO_S:
            self._subidas.popleft()
        if self.degrau is None:
            self.degrau, self._mudou_em = quer, agora
        elif quer > self.degrau and len(self._subidas) < TETO_DA_LUZ_POR_S:
            self.degrau, self._mudou_em = quer, agora
            self._subidas.append(agora)
        elif quer < self.degrau and agora - self._mudou_em >= SEGURA_DA_ROTACAO_S:
            self.degrau, self._mudou_em = quer, agora
        return self.degrau

    def cor(self, fracao: float, agora: float) -> RGB:
        return CORES_DA_ROTACAO[self.andar(fracao, agora)]


class TelemetriaDoJogo:
    """A porta UDP do localhost, o último estado da corrida e o que ele pede."""

    def __init__(self, porta: int = PORTA_DE_PARTIDA, endereco: str = ENDERECO) -> None:
        self.porta = porta
        self.endereco = endereco
        self._socket: socket.socket | None = None
        self.ultimo: EstadoDaCorrida | None = None
        self.recebido_em = float("-inf")
        self._toques = LeitorDosToques()
        self._a_tocar: list[tuple[float, ToqueDaCorrida]] = []
        self.luz = LuzDaRotacao()
        self.contadores: dict[str, int] = {"pacotes": 0, "ignorados": 0, "toques": 0}
        self._tamanhos_ditos: set[int] = set()
        self._formato_dito = False

    @property
    def aberta(self) -> bool:
        return self._socket is not None

    @property
    def endereco_escutado(self) -> tuple[str, int] | None:
        if self._socket is None:
            return None
        nome = self._socket.getsockname()
        return (str(nome[0]), int(nome[1]))

    def abrir(self) -> bool:
        """Abre a porta no localhost; ocupada, fica fechada e tenta de novo na próxima volta."""
        if self._socket is not None:
            return True
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setblocking(False)
            sock.bind((ENDERECO, self.porta))
        except OSError:
            sock.close()
            logger.debug("telemetria_porta_ocupada", porta=self.porta, exc_info=True)
            return False
        self._socket = sock
        logger.info("telemetria_aberta", porta=self.endereco_escutado)
        return True

    def fechar(self) -> None:
        if self._socket is None:
            return
        with contextlib.suppress(OSError):
            self._socket.close()
        self._socket = None
        self.ultimo = None
        self.recebido_em = float("-inf")
        self._toques.esquecer()
        self._a_tocar.clear()
        self.luz.esquecer()
        self._formato_dito = False
        logger.info("telemetria_fechada")

    def alimentar(self, dados: bytes, agora: float) -> bool:
        """Um pacote do jogo. ``False`` quando o tamanho não é de formato conhecido."""
        estado = ler_o_pacote(dados)
        if estado is None:
            self.contadores["ignorados"] += 1
            if len(dados) not in self._tamanhos_ditos:
                self._tamanhos_ditos.add(len(dados))
                logger.info("telemetria_tamanho_desconhecido", tamanho=len(dados))
            return False
        self.contadores["pacotes"] += 1
        if not self._formato_dito:
            self._formato_dito = True
            logger.info("telemetria_primeiro_pacote", formato=estado.formato, tamanho=len(dados))
        self.ultimo, self.recebido_em = estado, agora
        self._a_tocar = [(em, t) for em, t in self._a_tocar if agora - em <= VALIDADE_DO_PACOTE_S]
        toque = self._toques.ver(estado, agora)
        if toque is not None:
            self._a_tocar.append((agora, toque))
        return True

    def receber(self, agora: float) -> int:
        """Lê o que chegou desde a última volta, sem esperar."""
        if self._socket is None:
            return 0
        lidos = 0
        for _ in range(PACOTES_POR_VOLTA):
            try:
                dados = self._socket.recv(2048)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                logger.debug("telemetria_leitura_falhou", exc_info=True)
                break
            self.alimentar(dados, agora)
            lidos += 1
        return lidos

    def andar(self, agora: float, estilo: str | None) -> int:
        """A volta do laço: abre com o estilo da corrida, fecha sem ele, e lê o que chegou."""
        if estilo not in ESTILOS_DA_TELEMETRIA:
            self.fechar()
            return 0
        if not self.abrir():
            return 0
        return self.receber(agora)

    def vivo(self, agora: float) -> EstadoDaCorrida | None:
        """O último estado, se ele chegou há menos de meio segundo e a corrida está ligada."""
        estado = self.ultimo
        if estado is None or agora - self.recebido_em > VALIDADE_DO_PACOTE_S:
            return None
        return estado if estado.corrida_ligada else None

    def pedido(self, agora: float) -> PedidoDosGatilhos:
        estado = self.vivo(agora)
        return SEM_PEDIDO if estado is None else pedido_da_corrida(estado)

    def tirar_os_toques(self, agora: float) -> list[ToqueDaCorrida]:
        toques, self._a_tocar = self._a_tocar, []
        if self.vivo(agora) is None:
            return []
        return [toque for em, toque in toques if agora - em <= VALIDADE_DO_PACOTE_S]

    def cor_da_rotacao(self, agora: float) -> RGB | None:
        """A cor da barra pela rotação; ``None`` sem corrida viva ou sem o giro máximo do motor."""
        estado = self.vivo(agora)
        fracao = None if estado is None else estado.fracao_da_rotacao
        if fracao is None:
            self.luz.esquecer()
            return None
        return self.luz.cor(fracao, agora)

    def estado(self) -> dict[str, Any]:
        """Diagnóstico: a porta, o formato do último pacote e os contadores."""
        ultimo = self.ultimo
        return {
            "aberta": self.aberta,
            "porta": self.porta,
            "formato": None if ultimo is None else ultimo.formato,
            **self.contadores,
        }


def telemetria_do(daemon: Any) -> TelemetriaDoJogo | None:
    tel = getattr(daemon, "_telemetria_do_jogo", None)
    return tel if isinstance(tel, TelemetriaDoJogo) else None


class AtuadorDaTelemetria:
    """O pedido da corrida nos gatilhos e os toques no corpo, no relógio do motor do tato.

    Escreve o lado só enquanto a corrida pede, e só quando o efeito muda; o jogo que escreve o
    gatilho ou a háptica cala este canal, e a Bateria longa também. O momento da imersão cede o
    lado à corrida (``quer_o_lado``) e volta depois. Cada escrita passa pelo teto do motor.
    """

    canal = CANAL_DA_TELEMETRIA

    def __init__(
        self,
        fonte: Callable[[], TelemetriaDoJogo | None],
        escrever: Callable[[str, str, bytes], object],
        devolver: Callable[[str], bool],
        tocar: Callable[..., object],
        largar: Callable[[str], object] | None = None,
        soltar_lado: Callable[[str, str, bytes], object] | None = None,
        cede: Callable[[str, str], bool] | None = None,
        na_economia: Callable[[str], bool] | None = None,
    ) -> None:
        self._fonte = fonte
        self._escrever = escrever
        self._devolver = devolver
        self._tocar = tocar
        self._largar = largar
        self._soltar_lado = soltar_lado
        self._cede = cede or (lambda uniq, lado: False)
        self._na_economia = na_economia or (lambda uniq: False)
        self._escrito: dict[tuple[str, str], tuple[str, int]] = {}
        self._bloco: dict[tuple[str, str], bytes] = {}
        self._escreveu_em: dict[str, float] = {}

    def responde_a(self, evento: Any, receita: Receita) -> bool:
        return False

    def escrever(self, evento: Any, receita: Receita, agora: float) -> float | None:
        return None

    def segura(self, uniq: str) -> list[str]:
        return [lado for lado in _LADO_DO_BACKEND if (uniq, lado) in self._escrito]

    def quer_o_lado(self, uniq: str, lado: str, agora: float) -> bool:
        """A corrida escreve este lado deste controle agora (o momento da imersão cede a ela).

        A mesma conta do ``_gatilhos``: na Bateria longa a corrida não escreve, e o momento não
        cede o lado a quem não vai escrevê-lo.
        """
        if self._na_economia(uniq) or self._cede(uniq, lado):
            return False
        tel = self._fonte()
        return tel is not None and tel.pedido(agora).do_lado(lado) is not None

    def relogio(
        self,
        motor: TatoVivo,
        agora: float,
        uniqs: Sequence[str],
        estado_de: Callable[[str], EstadoDoCanal | None],
        receita: Receita,
    ) -> int:
        tel = self._fonte()
        pedido = SEM_PEDIDO if tel is None else tel.pedido(agora)
        toques = [] if tel is None else tel.tirar_os_toques(agora)
        for saiu in {u for u, _lado in self._escrito} - set(uniqs):
            self.soltar(saiu)
        escritas = 0
        for uniq in uniqs:
            estado = estado_de(uniq)
            if estado is None or not decidir(CANAL_GATILHO, estado):
                if self.segura(uniq):
                    if estado is not None and not _o_modo_cala_o_motor(estado):
                        motor.contadores["soltos_ao_jogo"] += 1
                        self.soltar(uniq)
                    else:
                        self.devolver(uniq, agora)
            else:
                escritas += self._gatilhos(motor, uniq, pedido, agora)
            escritas += self._toques(motor, uniq, estado, toques, agora)
        return escritas

    def _toques(
        self, motor: TatoVivo, uniq: str, estado: EstadoDoCanal | None,
        toques: Sequence[ToqueDaCorrida], agora: float,
    ) -> int:
        if not toques or estado is None or not decidir(CANAL_HAPTICA, estado):
            return 0
        if self._na_economia(uniq):
            return 0
        escritas = 0
        for toque in toques:
            if not motor.teto.cabe(uniq, agora):
                motor.contadores["recusas_do_teto"] += 1
                continue
            motor.teto.gastar(uniq, agora)
            self._tocar(uniq, toque.energia, LADO_CENTRO, toque.duracao_ms, toque.forma)
            escritas += 1
            motor.contadores["escritas"] += 1
        return escritas

    def _gatilhos(
        self, motor: TatoVivo, uniq: str, pedido: PedidoDosGatilhos, agora: float,
    ) -> int:
        economia = self._na_economia(uniq)
        a_voltar: list[str] = []
        escritas = 0
        for lado, disco in _LADO_DO_BACKEND.items():
            chave = (uniq, lado)
            quer = None if economia or self._cede(uniq, lado) else pedido.do_lado(lado)
            if quer is None:
                if chave in self._escrito:
                    a_voltar.append(lado)
                continue
            escrito = self._escrito.get(chave)
            if escrito is not None and escrito[0] == quer[0] and (
                    abs(escrito[1] - quer[1]) < HISTERESE_DA_PATINACAO):
                continue
            ultima = self._escreveu_em.get(uniq)
            if ultima is not None and agora - ultima < CICLO_DO_GATILHO_S:
                continue
            if not motor.teto.cabe(uniq, agora):
                motor.contadores["recusas_do_teto"] += 1
                continue
            motor.teto.gastar(uniq, agora)
            bloco = bloco_do_pedido(*quer)
            self._escrever(uniq, disco, bloco)
            self._escrito[chave] = quer
            self._bloco[chave] = bloco
            escritas += 1
            motor.contadores["escritas"] += 1
        if escritas:
            self._escreveu_em[uniq] = agora
        if a_voltar:
            self._voltar(uniq, a_voltar)
            motor.contadores["devolucoes"] += 1
        return escritas

    def _voltar(self, uniq: str, lados: Sequence[str]) -> None:
        """O lado volta ao perfil: pela sessão se nada mais a segura, senão só ele, à mão."""
        blocos: dict[str, bytes] = {}
        for lado in lados:
            self._escrito.pop((uniq, lado), None)
            bloco = self._bloco.pop((uniq, lado), None)
            if bloco is not None:
                blocos[_LADO_DO_BACKEND[lado]] = bloco
        if not self.segura(uniq):
            self._escreveu_em.pop(uniq, None)
            if self._devolver(uniq):
                return
        if self._soltar_lado is not None:
            for disco, bloco in blocos.items():
                self._soltar_lado(uniq, disco, bloco)

    def soltar(self, uniq: str) -> None:
        """O jogo tomou o gatilho (ou o controle saiu): o que a corrida escreveu deixou de valer."""
        for lado in _LADO_DO_BACKEND:
            self._escrito.pop((uniq, lado), None)
            self._bloco.pop((uniq, lado), None)
        self._escreveu_em.pop(uniq, None)
        if self._largar is not None:
            self._largar(uniq)

    def devolver(self, uniq: str, agora: float) -> None:
        if self.segura(uniq):
            self._voltar(uniq, self.segura(uniq))

    def devolver_tudo(self, agora: float) -> None:
        for uniq in {u for u, _lado in self._escrito}:
            self.devolver(uniq, agora)


async def telemetria_loop(daemon: Any, tel: TelemetriaDoJogo) -> None:
    try:
        while not daemon._is_stopping():
            await asyncio.sleep(INTERVALO_DO_LACO_S)
            tel.andar(time.monotonic(), _tv.estilo_ativo(daemon))
    finally:
        tel.fechar()


def start_telemetria_do_jogo(daemon: Any) -> None:
    """Sobe o laço. Sem a Corrida ou a Simulação no perfil, a porta fica fechada."""
    tel = TelemetriaDoJogo()
    daemon._telemetria_do_jogo = tel
    task = asyncio.create_task(telemetria_loop(daemon, tel), name="telemetria_do_jogo_loop")
    daemon._tasks.append(task)
    logger.info("telemetria_do_jogo_iniciada")


__all__ = [
    "CANAL_DA_TELEMETRIA",
    "CORES_DA_ROTACAO",
    "ENDERECO",
    "ESTILOS_DA_TELEMETRIA",
    "PORTA_DE_PARTIDA",
    "PRIORIDADE",
    "AtuadorDaTelemetria",
    "LeitorDosToques",
    "LuzDaRotacao",
    "PedidoDosGatilhos",
    "TelemetriaDoJogo",
    "ToqueDaCorrida",
    "bloco_do_pedido",
    "em_movimento",
    "pedido_da_corrida",
    "start_telemetria_do_jogo",
    "telemetria_do",
]
