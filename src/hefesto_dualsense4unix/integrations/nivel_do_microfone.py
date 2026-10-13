"""Está entrando som NESTE microfone agora? O medidor da luz do mic (LUZ-DO-MIC-01, peça B).

Responde por controle ``True`` (medi, há som), ``False`` (medi, não há) ou ``None`` (não sei, e
``None`` NUNCA vira ``False``). O pico vem do servidor de som (``parec`` com ``resample.peaks=true``
e ``--latency-msec=100``); a histerese tem TRÊS degraus (``LIMIAR_ENTRA``, ``ENTRA_S``,
``LIMIAR_SAI``/``SEGURA_S``). O fluxo é aberto com ``stdout=subprocess.PIPE`` e mais nada, e o que
emudece é fechado (``MUDEZ_S``): um ``parec`` vazado prende o microfone do usuário. As medições:
``docs/research/o-porque-dos-modulos.md``, seção «nivel_do_microfone».
"""

from __future__ import annotations

import contextlib
import math
import os
import selectors
import shutil
import struct
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from hefesto_dualsense4unix.integrations.filho_de_som import (
    morrer_com_o_pai as _morrer_com_o_pai,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


NOME_DO_MEDIDOR = "hefesto-medidor-de-nivel"

NOME_DO_FLUXO = "luz-do-mic"

APLICACAO_ID = "br.dev.hefesto.luz_do_mic"

CHAVE_DO_PAPEL = "hefesto.papel"
PAPEL_DO_MEDIDOR = "medidor-de-nivel"

CHAVE_DO_UNIQ = "hefesto.uniq"

CHAVE_DO_PICO = "resample.peaks"
VALOR_DO_PICO = "true"


def propriedades_do_medidor(uniq: str = "") -> dict[str, str]:
    """As propriedades que o nosso fluxo publica no servidor de som."""
    props = {
        CHAVE_DO_PICO: VALOR_DO_PICO,
        "application.id": APLICACAO_ID,
        CHAVE_DO_PAPEL: PAPEL_DO_MEDIDOR,
    }
    if uniq:
        props[CHAVE_DO_UNIQ] = uniq
    return props



TAXA_HZ = 25

LIMIAR_ENTRA = 0.0631

ENTRA_S = 0.12

LIMIAR_SAI = 0.0316

SEGURA_S = 0.6

MUDEZ_S = 3.0

_FOLGA_S = 1e-6

_TAM_AMOSTRA = 4
_LOTE_BYTES = 4096
_ESPERA_DO_SELETOR_S = 0.2
_ESPERA_APOS_MORTE_S = 2.0

_ESPERA_APOS_MUDEZ_S = 10.0


@dataclass
class Histerese:
    """A régua de TRÊS degraus: amplitude, duração para entrar, tempo para sair."""

    limiar_entra: float = LIMIAR_ENTRA
    limiar_sai: float = LIMIAR_SAI
    segura_s: float = SEGURA_S
    entra_s: float = ENTRA_S
    _captando: bool = field(default=False, init=False)
    _ultimo_alto: float = field(default=0.0, init=False)
    _acima_desde: float | None = field(default=None, init=False)
    _viu: bool = field(default=False, init=False)

    def aplicar(self, pico: float, agora: float) -> bool | None:
        """Come uma amostra e devolve o estado. Amostra suja é ignorada."""
        if not math.isfinite(pico):
            return self.estado(agora)
        valor = abs(pico)
        self._viu = True
        if valor >= self.limiar_sai:
            self._ultimo_alto = agora
        if not self._captando:
            if valor < self.limiar_entra:
                self._acima_desde = None
            else:
                if self._acima_desde is None:
                    self._acima_desde = agora
                if (agora - self._acima_desde) >= self.entra_s - _FOLGA_S:
                    self._captando = True
                    self._ultimo_alto = agora
        return self.estado(agora)

    def estado(self, agora: float) -> bool | None:
        """O estado AGORA — e é aqui que o tempo apaga, não só a amostra."""
        if not self._viu:
            return None
        if self._captando and (agora - self._ultimo_alto) >= self.segura_s - _FOLGA_S:
            self._captando = False
            self._acima_desde = None
        return self._captando


class Fluxo(Protocol):
    """O mínimo que o medidor precisa de uma captura aberta."""

    @property
    def fd(self) -> int:
        """Descritor de onde saem os float32 do pico."""

    def vivo(self) -> bool:
        """Ainda está de pé?"""

    def parar(self) -> None:
        """Fecha, sem levantar."""


def argv_do_medidor(fonte: str, uniq: str = "") -> list[str]:
    """O argv do ``parec`` que mede o pico desta fonte."""
    argv = [
        "parec",
        f"--device={fonte}",
        "--format=float32le",
        f"--rate={TAXA_HZ}",
        "--channels=1",
        "--latency-msec=100",
        "--client-name=" + NOME_DO_MEDIDOR,
        "--stream-name=" + NOME_DO_FLUXO,
    ]
    argv += [f"--property={k}={v}" for k, v in propriedades_do_medidor(uniq).items()]
    return argv


def _ambiente_c() -> dict[str, str]:
    """`LC_ALL=C`: a saída das ferramentas de som é TRADUZIDA nesta máquina."""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return env


@dataclass
class _FluxoParec:
    """Um ``parec`` em modo de pico, visto como :class:`Fluxo`."""

    proc: Any

    @property
    def fd(self) -> int:
        return int(self.proc.stdout.fileno())

    def vivo(self) -> bool:
        return self.proc.poll() is None

    def parar(self) -> None:
        with contextlib.suppress(OSError):  # pragma: no cover - defensivo
            self.proc.terminate()
        try:
            self.proc.wait(timeout=2.0)
        except Exception:  # pragma: no cover - defensivo
            with contextlib.suppress(OSError):
                self.proc.kill()
        with contextlib.suppress(OSError):  # pragma: no cover - defensivo
            if self.proc.stdout is not None:
                self.proc.stdout.close()


def abrir_fluxo(fonte: str, uniq: str = "") -> Fluxo | None:
    """Abre a captura de pico desta fonte — ``None`` quando não dá."""
    if shutil.which("parec") is None:
        logger.debug("nivel_do_mic_sem_parec", fonte=fonte)
        return None
    try:
        proc = subprocess.Popen(
            argv_do_medidor(fonte, uniq),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=_ambiente_c(),
            bufsize=0,
            preexec_fn=_morrer_com_o_pai,
        )
    except (OSError, ValueError) as exc:
        logger.warning("nivel_do_mic_nao_abriu", fonte=fonte, err=str(exc))
        return None
    if proc.stdout is None:  # pragma: no cover - defensivo
        with contextlib.suppress(OSError):
            proc.kill()
        return None
    return _FluxoParec(proc=proc)


@dataclass
class _Canal:
    """Um controle sendo medido: o fluxo aberto, a régua e o que sobrou."""

    uniq: str
    fonte: str
    fluxo: Fluxo
    hist: Histerese
    resto: bytearray = field(default_factory=bytearray)
    ultimo_dado: float = 0.0


class NivelDoMicrofone:
    """Mede o pico de cada canal pedido e responde com histerese."""

    def __init__(
        self,
        *,
        abrir: Callable[[str, str], Fluxo | None] = abrir_fluxo,
        agora: Callable[[], float] = time.monotonic,
        limiar_entra: float = LIMIAR_ENTRA,
        limiar_sai: float = LIMIAR_SAI,
        segura_s: float = SEGURA_S,
        entra_s: float = ENTRA_S,
        mudez_s: float = MUDEZ_S,
        automatico: bool = True,
    ) -> None:
        self._abrir = abrir
        self._agora = agora
        self._limiar_entra = limiar_entra
        self._limiar_sai = limiar_sai
        self._segura_s = segura_s
        self._entra_s = entra_s
        self._mudez_s = mudez_s
        self._automatico = automatico
        self._lock = threading.RLock()
        self._desejado: dict[str, str | None] = {}
        self._canais: dict[str, _Canal] = {}
        self._proxima_tentativa: dict[str, float] = {}
        self._seletor = selectors.DefaultSelector()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None


    def seguir(self, alvos: Mapping[str, str | None]) -> None:
        """Passa a medir exatamente estes controles — nem mais, nem menos."""
        with self._lock:
            self._desejado = dict(alvos)
        if self._automatico:
            self._garantir_thread()

    def captando(self) -> dict[str, bool | None]:
        """``{uniq: True|False|None}`` para tudo que :meth:`seguir` recebeu."""
        agora = self._agora()
        with self._lock:
            return {u: self._resposta(u, agora) for u in self._desejado}

    def captando_em(self, uniq: str) -> bool | None:
        """A resposta de UM controle. ``None`` também para quem nem é seguido."""
        agora = self._agora()
        with self._lock:
            if uniq not in self._desejado:
                return None
            return self._resposta(uniq, agora)

    def parar(self) -> None:
        """Fecha tudo. Idempotente, e não levanta."""
        self._parar.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        self._thread = None
        with self._lock:
            self._desejado = {}
            for uniq in list(self._canais):
                self._fechar(uniq)
        with contextlib.suppress(OSError):  # pragma: no cover - defensivo
            self._seletor.close()

    def __enter__(self) -> NivelDoMicrofone:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.parar()


    def bombear(self, timeout_s: float = _ESPERA_DO_SELETOR_S) -> None:
        """Uma volta: reconcilia os fluxos e come o que chegou."""
        self._reconciliar()
        eventos = self._seletor.select(timeout=timeout_s)
        agora = self._agora()
        for chave, _mascara in eventos:
            self._comer(str(chave.data), agora)

    def _rodar(self) -> None:  # pragma: no cover - exercitado só com thread
        while not self._parar.is_set():
            try:
                self.bombear()
            except Exception as exc:
                logger.warning("nivel_do_mic_volta_falhou", err=str(exc))
                time.sleep(_ESPERA_DO_SELETOR_S)

    def _garantir_thread(self) -> None:
        with self._lock:
            if self._thread is not None or self._parar.is_set():
                return
            self._thread = threading.Thread(
                target=self._rodar, name="nivel_do_microfone", daemon=True
            )
        self._thread.start()


    def _resposta(self, uniq: str, agora: float) -> bool | None:
        """Chamado SEMPRE com o lock tomado."""
        canal = self._canais.get(uniq)
        if canal is None:
            return None
        if (agora - canal.ultimo_dado) >= self._mudez_s:
            return None
        return canal.hist.estado(agora)

    def _reconciliar(self) -> None:
        agora = self._agora()
        with self._lock:
            desejado = dict(self._desejado)
            for uniq, canal in list(self._canais.items()):
                if desejado.get(uniq) != canal.fonte or not canal.fluxo.vivo():
                    self._fechar(uniq)
                elif (agora - canal.ultimo_dado) >= self._mudez_s:
                    self._fechar(uniq)
                    self._proxima_tentativa[uniq] = agora + _ESPERA_APOS_MUDEZ_S
                    logger.warning(
                        "nivel_do_mic_fluxo_emudeceu",
                        uniq=uniq,
                        mudo_ha_s=round(agora - canal.ultimo_dado, 2),
                    )
            faltam = [
                (u, f)
                for u, f in desejado.items()
                if f and u not in self._canais
            ]
        for uniq, fonte in faltam:
            if agora < self._proxima_tentativa.get(uniq, 0.0):
                continue
            self._abrir_canal(uniq, str(fonte), agora)

    def _abrir_canal(self, uniq: str, fonte: str, agora: float) -> None:
        fluxo = self._abrir(fonte, uniq)
        if fluxo is None:
            self._proxima_tentativa[uniq] = agora + _ESPERA_APOS_MORTE_S
            return
        canal = _Canal(
            uniq=uniq,
            fonte=fonte,
            fluxo=fluxo,
            hist=Histerese(
                limiar_entra=self._limiar_entra,
                limiar_sai=self._limiar_sai,
                segura_s=self._segura_s,
                entra_s=self._entra_s,
            ),
            ultimo_dado=agora,
        )
        try:
            self._seletor.register(fluxo.fd, selectors.EVENT_READ, uniq)
        except (KeyError, ValueError, OSError) as exc:  # pragma: no cover
            logger.warning("nivel_do_mic_seletor_recusou", uniq=uniq, err=str(exc))
            fluxo.parar()
            self._proxima_tentativa[uniq] = agora + _ESPERA_APOS_MORTE_S
            return
        with self._lock:
            self._canais[uniq] = canal
        self._proxima_tentativa.pop(uniq, None)
        logger.info("nivel_do_mic_abriu", uniq=uniq, fonte=fonte)

    def _fechar(self, uniq: str) -> None:
        """Chamado SEMPRE com o lock tomado."""
        canal = self._canais.pop(uniq, None)
        if canal is None:
            return
        with contextlib.suppress(  # pragma: no cover - defensivo
            KeyError, ValueError, OSError
        ):
            self._seletor.unregister(canal.fluxo.fd)
        canal.fluxo.parar()
        logger.info("nivel_do_mic_fechou", uniq=uniq, fonte=canal.fonte)

    def _comer(self, uniq: str, agora: float) -> None:
        with self._lock:
            canal = self._canais.get(uniq)
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
                self._fechar(uniq)
            self._proxima_tentativa[uniq] = agora + _ESPERA_APOS_MORTE_S
            logger.info("nivel_do_mic_fluxo_morreu", uniq=uniq)
            return
        canal.resto += dados
        inteiras = len(canal.resto) // _TAM_AMOSTRA
        if not inteiras:
            return
        with self._lock:
            inicio = canal.ultimo_dado
            passo = (agora - inicio) / inteiras
            for i in range(inteiras):
                pico = struct.unpack_from("<f", canal.resto, i * _TAM_AMOSTRA)[0]
                canal.hist.aplicar(pico, inicio + passo * (i + 1))
            del canal.resto[: inteiras * _TAM_AMOSTRA]
            canal.ultimo_dado = agora


__all__ = [
    "APLICACAO_ID",
    "CHAVE_DO_PAPEL",
    "CHAVE_DO_PICO",
    "CHAVE_DO_UNIQ",
    "ENTRA_S",
    "LIMIAR_ENTRA",
    "LIMIAR_SAI",
    "MUDEZ_S",
    "NOME_DO_FLUXO",
    "NOME_DO_MEDIDOR",
    "PAPEL_DO_MEDIDOR",
    "SEGURA_S",
    "TAXA_HZ",
    "VALOR_DO_PICO",
    "Fluxo",
    "Histerese",
    "NivelDoMicrofone",
    "abrir_fluxo",
    "argv_do_medidor",
    "propriedades_do_medidor",
]
