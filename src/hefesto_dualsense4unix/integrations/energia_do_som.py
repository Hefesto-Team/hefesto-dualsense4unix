"""A energia do som da máquina, para o efeito «Ao som» (A-LUZ-DANCA-COM-O-SOM-01).

Lê SÓ o monitor da saída padrão (``@DEFAULT_MONITOR@``): o que a máquina toca, nunca um microfone
(o único microfone de quem usa o Hefesto pode ser o do DualSense). ``abrir_fluxo`` recusa fonte que
não seja monitor. Cada bloco de 40 ms vira ``(nivel, agudos)``, de 0 a 1: a energia contra o pico
recente e a fração dela acima de ~2 kHz. A leitura só vive entre ``abrir`` e ``fechar``, e o
``parec`` morre com o pai.
"""

from __future__ import annotations

import array
import contextlib
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from typing import Any, Protocol

from hefesto_dualsense4unix.integrations.filho_de_som import (
    morrer_com_o_pai as _morrer_com_o_pai,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: A única fonte que este módulo abre: o monitor da saída padrão (a que o servidor aponta agora).
FONTE_DO_MONITOR = "@DEFAULT_MONITOR@"
SUFIXO_DE_MONITOR = ".monitor"

NOME_DO_FLUXO = "luz-ao-som"
APLICACAO_ID = "br.dev.hefesto.luz_ao_som"

#: Mono, 8 kHz: sobra para separar graves e agudos e custa pouco para ler em Python.
TAXA_HZ = 8000
LATENCIA_MS = 40
#: O bloco de análise: 40 ms.
AMOSTRAS_POR_BLOCO = TAXA_HZ * LATENCIA_MS // 1000
_TAM_AMOSTRA = 4

#: O filtro dos agudos: dois polos de um pólo a ~2 kHz, e o que sobra do sinal é agudo.
CORTE_DOS_AGUDOS_HZ = 2000.0
_ALFA_DOS_AGUDOS = 1.0 - math.exp(-2.0 * math.pi * CORTE_DOS_AGUDOS_HZ / TAXA_HZ)

#: Abaixo disto (RMS, escala cheia = 1) é silêncio: o nível é zero, e ruído de fundo não acende.
PISO_DE_SILENCIO = 0.002
#: O pico recente nunca cai abaixo disto, para o ruído não ser ampliado até o cheio.
PISO_DO_PICO = 0.01
#: O pico recente cai a esta fração a cada segundo de som mais fraco.
FRACAO_DO_PICO_POR_S = 0.85
#: O contraste do nível: ``(energia / pico) ** CONTRASTE``; a pancada se destaca do fundo.
CONTRASTE = 2.0
#: Sem bloco novo por tanto tempo, a leitura é «não sei» (o efeito deixa a luz descer).
MUDEZ_S = 1.0
ESPERA_APOS_FALHA_S = 2.0
#: Quanto esperar o ``parec`` sair e a thread de leitura voltar, ao fechar.
PRAZO_DO_FILHO_S = 2.0
PRAZO_DA_THREAD_S = 3.0
LEITURA_BYTES = 4096


class Fluxo(Protocol):
    """O mínimo que a leitura precisa de uma captura aberta."""

    def ler(self, n: int) -> bytes:
        """Bloqueia até haver bytes; ``b""`` quando o fluxo acabou."""

    def parar(self) -> None:
        """Fecha, sem levantar."""


def e_o_monitor(fonte: str) -> bool:
    """A fonte é o monitor de uma saída? Microfone e qualquer outra entrada dão ``False``."""
    return fonte == FONTE_DO_MONITOR or fonte.lower().endswith(SUFIXO_DE_MONITOR)


def argv_da_energia(fonte: str = FONTE_DO_MONITOR) -> list[str]:
    """O argv do ``parec`` que lê PCM do monitor. Recusa fonte que não seja monitor."""
    if not e_o_monitor(fonte):
        raise ValueError(f"o «Ao som» só lê o monitor da saída, nunca {fonte!r}")
    return [
        "parec",
        f"--device={fonte}",
        "--format=float32le",
        f"--rate={TAXA_HZ}",
        "--channels=1",
        f"--latency-msec={LATENCIA_MS}",
        f"--client-name=hefesto-{NOME_DO_FLUXO}",
        f"--stream-name={NOME_DO_FLUXO}",
        f"--property=application.id={APLICACAO_ID}",
        "--property=hefesto.papel=energia-do-som",
    ]


class _FluxoParec:
    """Um ``parec`` lendo PCM, visto como :class:`Fluxo`."""

    def __init__(self, proc: Any) -> None:
        self._proc = proc

    def ler(self, n: int) -> bytes:
        return os.read(self._proc.stdout.fileno(), n)

    def parar(self) -> None:
        with contextlib.suppress(OSError):
            self._proc.terminate()
        try:
            self._proc.wait(timeout=PRAZO_DO_FILHO_S)
        except Exception:
            with contextlib.suppress(OSError):
                self._proc.kill()
        with contextlib.suppress(OSError):
            if self._proc.stdout is not None:
                self._proc.stdout.close()


def abrir_fluxo(fonte: str = FONTE_DO_MONITOR) -> Fluxo | None:
    """Abre a captura do monitor; ``None`` quando não dá. Recusa (``None``) fonte de entrada."""
    if not e_o_monitor(fonte):
        logger.warning("energia_do_som_recusou_fonte", fonte=fonte)
        return None
    if shutil.which("parec") is None:
        logger.debug("energia_do_som_sem_parec")
        return None
    try:
        proc = subprocess.Popen(
            argv_da_energia(fonte),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
            bufsize=0,
            preexec_fn=_morrer_com_o_pai,
        )
    except (OSError, ValueError) as exc:
        logger.warning("energia_do_som_nao_abriu", err=str(exc))
        return None
    if proc.stdout is None:  # pragma: no cover - defensivo
        with contextlib.suppress(OSError):
            proc.kill()
        return None
    return _FluxoParec(proc)


class Medidor:
    """O PCM em float32 vira ``(nivel, agudos)`` a cada bloco de 40 ms. Puro: sem relógio nem I/O.

    ``alimentar`` recebe bytes de qualquer tamanho e devolve a última medida completa, ou ``None``
    se ainda não fechou um bloco. O pico recente é a referência do nível.
    """

    def __init__(self) -> None:
        self._resto = bytearray()
        self._m1 = 0.0
        self._m2 = 0.0
        self._pico = PISO_DO_PICO

    def alimentar(self, dados: bytes) -> tuple[float, float] | None:
        self._resto += dados
        tam = AMOSTRAS_POR_BLOCO * _TAM_AMOSTRA
        medida: tuple[float, float] | None = None
        while len(self._resto) >= tam:
            bloco = array.array("f")
            bloco.frombytes(bytes(self._resto[:tam]))
            if sys.byteorder == "big":  # pragma: no cover - o fluxo vem em little-endian
                bloco.byteswap()
            del self._resto[:tam]
            medida = self._bloco(bloco)
        return medida

    def _bloco(self, bloco: array.array[float]) -> tuple[float, float]:
        total = agudo = 0.0
        m1, m2 = self._m1, self._m2
        for x in bloco:
            if not math.isfinite(x):
                x = 0.0
            m1 += _ALFA_DOS_AGUDOS * (x - m1)
            m2 += _ALFA_DOS_AGUDOS * (m1 - m2)
            alto = x - m2
            total += x * x
            agudo += alto * alto
        self._m1, self._m2 = m1, m2
        n = len(bloco)
        rms = math.sqrt(total / n)
        duracao_s = n / TAXA_HZ
        self._pico = max(rms, PISO_DO_PICO, self._pico * FRACAO_DO_PICO_POR_S ** duracao_s)
        if rms < PISO_DE_SILENCIO:
            return 0.0, 0.0
        nivel = min(1.0, rms / self._pico) ** CONTRASTE
        agudos = min(1.0, math.sqrt(agudo / n) / rms)
        return nivel, agudos


class EnergiaDoSom:
    """A leitura viva: abre o monitor numa thread e guarda a última medida.

    ``abrir`` e ``fechar`` são idempotentes. ``nivel`` devolve ``(nivel, agudos)`` ou ``None``
    (fechado, sem fluxo ou mudo há mais de ``MUDEZ_S``): ``None`` nunca vira silêncio inventado.
    """

    def __init__(
        self,
        *,
        abrir: Callable[[str], Fluxo | None] = abrir_fluxo,
        agora: Callable[[], float] = time.monotonic,
        espera_apos_falha_s: float = ESPERA_APOS_FALHA_S,
    ) -> None:
        self._abrir_fluxo = abrir
        self._agora = agora
        self._espera = espera_apos_falha_s
        self._lock = threading.Lock()
        self._medida: tuple[float, float] | None = None
        self._medida_em = float("-inf")
        self._fluxo: Fluxo | None = None
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def aberto(self) -> bool:
        return self._thread is not None

    def abrir(self) -> None:
        with self._lock:
            if self._thread is not None:
                return
            self._parar = threading.Event()
            self._medida = None
            self._thread = threading.Thread(
                target=self._rodar, args=(self._parar,), name="energia_do_som", daemon=True)
            thread = self._thread
        thread.start()

    def fechar(self) -> None:
        with self._lock:
            thread, self._thread = self._thread, None
            fluxo, self._fluxo = self._fluxo, None
            self._parar.set()
            self._medida = None
        if fluxo is not None:
            fluxo.parar()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=PRAZO_DA_THREAD_S)

    def nivel(self) -> tuple[float, float] | None:
        with self._lock:
            if self._medida is None or self._agora() - self._medida_em >= MUDEZ_S:
                return None
            return self._medida

    def _rodar(self, parar: threading.Event) -> None:
        while not parar.is_set():
            try:
                fluxo = self._abrir_fluxo(FONTE_DO_MONITOR)
            except Exception as exc:
                logger.warning("energia_do_som_abrir_falhou", err=str(exc))
                fluxo = None
            if fluxo is None:
                parar.wait(self._espera)
                continue
            with self._lock:
                if parar.is_set():
                    fluxo.parar()
                    return
                self._fluxo = fluxo
            self._ler(fluxo, parar)
            fluxo.parar()
            with self._lock:
                if self._fluxo is fluxo:
                    self._fluxo = None
            parar.wait(self._espera)

    def _ler(self, fluxo: Fluxo, parar: threading.Event) -> None:
        analise = Medidor()
        while not parar.is_set():
            try:
                dados = fluxo.ler(LEITURA_BYTES)
            except (OSError, ValueError) as exc:
                logger.debug("energia_do_som_leitura_fechou", err=str(exc))
                return
            if not dados:
                return
            medida = analise.alimentar(dados)
            if medida is not None:
                with self._lock:
                    self._medida, self._medida_em = medida, self._agora()


__all__ = [
    "FONTE_DO_MONITOR",
    "EnergiaDoSom",
    "Fluxo",
    "Medidor",
    "abrir_fluxo",
    "argv_da_energia",
    "e_o_monitor",
]
