"""O envelope da háptica por áudio do jogo, dito no barramento (``jogo.haptica``).

O-GATILHO-E-A-HAPTICA-DO-JOGO-VIRAM-EVENTOS-PARA-AS-EXTENSOES-01. O RMS dos canais 3-4 (os
motores), de 0 a 1, sai como ``{uniq, jogador, intensidade: [esq, dir], t}``; a senoide de fundo
de escala vale 1. Sem gravador novo: ``espiar_a_haptica`` lê o PCM do leitor que já existe. Nos
dois transportes é o que o controle recebe: a placa do cabo já traz o ganho e o portão, e no rádio
o envelope aplica os da ponte. Janelas de 20 ms, passo de 0,02, teto de 50 por segundo e batida
de 250 ms enquanto não é zero; o zero sempre chega, com a fonte seca ou com o jogo que sai.
"""
from __future__ import annotations

import functools
import math
import threading
import time
from array import array
from collections.abc import Callable
from operator import mul
from typing import Any

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Os motores são os canais 3 e 4 do endpoint (índices 2 e 3): o 1 e o 2 são o som da frente.
CANAL_ESQUERDO = 2
CANAL_DIREITO = 3
CANAIS_DO_ENDPOINT = 4

#: A janela do RMS: 20 ms, e por isso 50 intensidades por segundo no máximo.
JANELA_S = 0.02
#: O degrau: a intensidade só muda de nível em passos de 0,02.
PASSO = 0.02
#: O teto de eventos por controle: 50 por segundo.
INTERVALO_MINIMO_S = 1.0 / 50.0
#: A batida: de quanto em quanto o evento se repete enquanto a intensidade não é zero.
PERIODO_DA_BATIDA_S = 0.25
#: Sem PCM por tanto tempo, a fonte secou: o zero sai.
SILENCIO_S = 0.5

_ATRIBUTO = "_envelopes_da_haptica_vistos"
_TRAVA_DA_CRIACAO = threading.Lock()

Nivel = tuple[float, float]
ZERO: Nivel = (0.0, 0.0)


class EnvelopeDaHaptica:
    """O RMS dos motores de UM controle, por janelas; ``dizer(nivel, agora)`` recebe o que sai."""

    def __init__(
        self,
        dizer: Callable[[Nivel, float], None],
        *,
        taxa: int,
        canais: int = CANAIS_DO_ENDPOINT,
        relogio: Callable[[], float] | None = None,
    ) -> None:
        self._dizer = dizer
        self._canais = int(canais)
        self._relogio = relogio or time.monotonic
        self._janela = max(1, round(int(taxa) * JANELA_S))
        self._trava = threading.Lock()
        self._resto = b""
        self._n = 0
        self._soma = [0, 0]
        self.ultimo: Nivel = ZERO
        self._enviado_em = float("-inf")
        self._pendente: Nivel | None = None
        self.ultimo_pcm_em = self._relogio()

    def alimentar(self, pcm: bytes | bytearray | memoryview, ganho: float = 1.0) -> None:
        """Um pedaço do PCM do endpoint (s16 nativo, ``canais`` intercalados). Nunca levanta.

        ``ganho`` é o fator de amplitude que o controle leva por cima deste PCM (o do Hefesto
        no rádio; 1 no cabo, cuja placa já o traz).
        """
        agora = self._relogio()
        a_dizer: list[tuple[Nivel, float]] = []
        with self._trava:
            self.ultimo_pcm_em = agora
            quadro = 2 * self._canais
            dados = self._resto + bytes(pcm)
            inteiro = len(dados) - len(dados) % quadro
            self._resto = dados[inteiro:]
            amostras = array("h")
            amostras.frombytes(dados[:inteiro])
            esquerdo = amostras[CANAL_ESQUERDO::self._canais]
            direito = amostras[CANAL_DIREITO::self._canais]
            pos = 0
            while pos < len(esquerdo):
                tomar = min(self._janela - self._n, len(esquerdo) - pos)
                a, b = esquerdo[pos:pos + tomar], direito[pos:pos + tomar]
                self._soma[0] += sum(map(mul, a, a))
                self._soma[1] += sum(map(mul, b, b))
                self._n += tomar
                pos += tomar
                if self._n >= self._janela:
                    nivel = (
                        _nivel(self._soma[0], self._n, ganho),
                        _nivel(self._soma[1], self._n, ganho),
                    )
                    self._soma, self._n = [0, 0], 0
                    saiu = self._decidir(nivel, agora)
                    if saiu is not None:
                        a_dizer.append((saiu, agora))
        for nivel, quando in a_dizer:
            self._dizer(nivel, quando)

    def _decidir(self, nivel: Nivel, agora: float) -> Nivel | None:
        """O que sai agora (``None`` = nada, ou pendente para o tique). Dentro da trava."""
        repete = nivel != ZERO and agora - self._enviado_em >= PERIODO_DA_BATIDA_S
        if nivel == self.ultimo and not repete:
            self._pendente = None
            return None
        if agora - self._enviado_em < INTERVALO_MINIMO_S:
            self._pendente = nivel
            return None
        self.ultimo, self._enviado_em, self._pendente = nivel, agora, None
        return nivel

    def bater(self, agora: float | None = None) -> None:
        """O que o teto atrasou, a batida e o zero da fonte que secou. Nunca levanta."""
        agora = self._relogio() if agora is None else agora
        saiu: Nivel | None = None
        with self._trava:
            if self.ultimo != ZERO and agora - self.ultimo_pcm_em > SILENCIO_S:
                saiu = self._soltar(agora)
            elif self._pendente is not None:
                saiu = self._decidir(self._pendente, agora)
            elif self.ultimo != ZERO and agora - self._enviado_em >= PERIODO_DA_BATIDA_S:
                saiu = self._decidir(self.ultimo, agora)
        if saiu is not None:
            self._dizer(saiu, agora)

    def zerar(self, agora: float | None = None) -> None:
        """O fim da sessão: quem ainda tinha intensidade recebe o zero. Nunca levanta."""
        agora = self._relogio() if agora is None else agora
        with self._trava:
            saiu = self._soltar(agora) if self.ultimo != ZERO else None
        if saiu is not None:
            self._dizer(saiu, agora)

    def _soltar(self, agora: float) -> Nivel:
        self.ultimo, self._enviado_em, self._pendente = ZERO, agora, None
        self._resto, self._n, self._soma = b"", 0, [0, 0]
        return ZERO


def _nivel(soma_dos_quadrados: int, n: int, ganho: float = 1.0) -> float:
    """O RMS da janela de 0 a 1 (senoide de fundo de escala = 1), em degraus de ``PASSO``."""
    rms = math.sqrt(soma_dos_quadrados / n)
    bruto = min(1.0, max(0.0, ganho) * rms * math.sqrt(2.0) / 32768.0)
    return round(round(bruto / PASSO) * PASSO, 4)


class _Entrada:
    def __init__(self, envelope: EnvelopeDaHaptica, taxa: int) -> None:
        self.envelope = envelope
        self.taxa = taxa


def _entradas_de(daemon: Any, *, criar: bool) -> dict[str, _Entrada] | None:
    atual = getattr(daemon, _ATRIBUTO, None)
    if isinstance(atual, dict):
        return atual
    if not criar:
        return None
    with _TRAVA_DA_CRIACAO:
        atual = getattr(daemon, _ATRIBUTO, None)
        if isinstance(atual, dict):
            return atual
        atual = {}
        try:
            setattr(daemon, _ATRIBUTO, atual)
        except AttributeError as exc:  # um dublê sem lugar para a tabela: sem evento, sem erro
            logger.debug("jogo_haptica_sem_tabela", err=str(exc))
            return None
    return atual


def _publicar(daemon: Any, uniq: str, nivel: Nivel, agora: float) -> None:
    publicar = getattr(getattr(daemon, "bus", None), "publish", None)
    if not callable(publicar):
        return
    from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import _jogador_de

    try:
        publicar(
            EventTopic.JOGO_HAPTICA,
            {
                "uniq": uniq,
                "jogador": _jogador_de(daemon, uniq),
                "intensidade": list(nivel),
                "t": agora,
            },
        )
    except Exception as exc:
        logger.debug("jogo_haptica_nao_publicada", uniq=uniq, err=str(exc))


def espiar_a_haptica(
    daemon: Any,
    uniq: str,
    fonte: Callable[[int], bytes],
    *,
    taxa: int,
    canais: int = CANAIS_DO_ENDPOINT,
    ganho: Callable[[], float] | None = None,
    vai: Callable[[], bool] | None = None,
) -> Callable[[int], bytes]:
    """A mesma fonte de PCM, e cada bloco que ela entrega passa pelo envelope deste controle.

    ``ganho`` e ``vai`` são os da ponte do rádio, que lê o PCM antes deles: o envelope diz o
    que chega ao controle, como o do cabo. O bloco que não vai ao controle conta como zero, e
    a fonte que seca (o leitor recebe vazio) manda o zero na hora, sem esperar o tique.
    """
    entradas = _entradas_de(daemon, criar=True)
    if entradas is None or not uniq:
        return fonte
    entrada = entradas.get(uniq)
    if entrada is None or entrada.taxa != taxa:
        envelope = EnvelopeDaHaptica(
            lambda nivel, agora: _publicar(daemon, uniq, nivel, agora),
            taxa=taxa,
            canais=canais,
        )
        entrada = entradas[uniq] = _Entrada(envelope, taxa)
    envelope = entrada.envelope

    def _ler(quantos: int) -> bytes:
        pcm = fonte(quantos)
        try:
            if not pcm or (vai is not None and not vai()):
                envelope.zerar()
            else:
                envelope.alimentar(pcm, 1.0 if ganho is None else float(ganho()))
        except Exception as exc:  # o som do controle não espera por quem escuta
            logger.debug("jogo_haptica_envelope_falhou", uniq=uniq, err=str(exc))
        return pcm

    return _ler


def bater_o_envelope(daemon: Any, agora: float | None = None) -> None:
    """A batida, o que o teto atrasou e o zero da fonte seca: a cada tique. Nunca levanta."""
    entradas = _entradas_de(daemon, criar=False)
    if not entradas:
        return
    for entrada in list(entradas.values()):
        try:
            entrada.envelope.bater(agora)
        except Exception as exc:
            logger.debug("jogo_haptica_batida_falhou", err=str(exc))


def esquecer_o_envelope(
    daemon: Any, uniq: str | None = None, *, agora: float | None = None
) -> None:
    """O fim da sessão do pad (um controle) ou do jogo (todos): quem tinha intensidade zera."""
    entradas = _entradas_de(daemon, criar=False)
    if not entradas:
        return
    alvos = list(entradas.values()) if uniq is None else [
        e for u, e in list(entradas.items()) if u == uniq
    ]
    for entrada in alvos:
        try:
            entrada.envelope.zerar(agora)
        except Exception as exc:
            logger.debug("jogo_haptica_zero_falhou", err=str(exc))


_MODULO_DOS_OUVIDOS = "hefesto_dualsense4unix.integrations.alto_falante_bt"


@functools.cache
def _com_envelope(base: type) -> type:
    class OuvidoComEnvelope(base):  # type: ignore[misc]
        """O ouvido do cabo, com o envelope no mesmo bloco que ele já lê: sem gravador novo."""

        _daemon: Any = None

        def subir(self) -> bool:
            from hefesto_dualsense4unix.integrations import alto_falante_bt as afb

            if self.vivo:
                return True
            fonte, proc, motivo = afb.fonte_do_monitor_do_no(
                self.no, uniq=self.uniq, papel=self.papel, abrir=self._abrir,
                taxa=afb.TAXA_DO_OUVIDO_DA_PLACA, canais=self.canais,
                propriedades=afb.RECUO_PROIBIDO_DO_OUVIDO,
            )
            if fonte is None:
                self.motivo = motivo
                return False
            self._proc = proc
            self._parar = threading.Event()
            ouvir = espiar_a_haptica(
                self._daemon, self.uniq,
                afb.fonte_que_ouve(fonte, self.no, canais=self.canais),
                taxa=afb.TAXA_DO_OUVIDO_DA_PLACA, canais=self.canais,
            )
            tamanho = (afb.TAXA_DO_OUVIDO_DA_PLACA // 100) * 2 * self.canais
            parar = self._parar

            def _escutar() -> None:
                try:
                    while not parar.is_set():
                        if not ouvir(tamanho):
                            return
                except Exception:
                    logger.debug("som_ouvido_do_no_caiu", papel=self.papel, exc_info=True)

            self._fio = threading.Thread(
                target=_escutar, name=f"hefesto-ouvido-{self.papel}", daemon=True
            )
            self._fio.start()
            return True

    return OuvidoComEnvelope


def ouvido_da_placa(classe: Any, placa: str, uniq: str, daemon: Any) -> Any:
    """O ouvido da placa de um controle no cabo, que também diz o envelope da háptica dele.

    ``classe`` é o ``OuvidoDaPlaca`` que o chamador resolveu na hora: só a classe de verdade
    do produto ganha o envelope, e um dublê entra como veio.
    """
    if isinstance(classe, type) and classe.__module__ == _MODULO_DOS_OUVIDOS:
        ouvido = _com_envelope(classe)(placa=placa, uniq=uniq)
        ouvido._daemon = daemon
        return ouvido
    return classe(placa=placa, uniq=uniq)
