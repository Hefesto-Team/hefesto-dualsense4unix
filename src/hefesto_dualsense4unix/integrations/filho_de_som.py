"""O filho de som do daemon: quem sobe um processo derruba o processo."""

from __future__ import annotations

import contextlib
import ctypes
import signal
import subprocess
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

ESPERA_PELO_FIM_S = 1.0

_PR_SET_PDEATHSIG = 1


def _carregar_o_prctl() -> Any:
    """O ``prctl`` da libc, resolvido UMA vez no processo pai. ``None`` fora do Linux."""
    try:
        return ctypes.CDLL("libc.so.6", use_errno=True).prctl
    except (OSError, AttributeError):
        return None


_PRCTL = _carregar_o_prctl()


def morrer_com_o_pai() -> None:
    """Pede ao kernel um SIGKILL neste filho quando o pai morrer. Nunca levanta."""
    prctl = _PRCTL
    if prctl is None:
        return
    with contextlib.suppress(Exception):
        prctl(_PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)


def lancar_leitor(argv: Sequence[str]) -> subprocess.Popen[bytes]:
    """O ``Popen`` de um leitor de som: cano no ``stdout``, e preso ao pai."""
    return subprocess.Popen(
        list(argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        preexec_fn=morrer_com_o_pai,
    )


@dataclass(frozen=True)
class ComoMorreu:
    """Como o filho morreu — para o diário, nunca para a tela."""

    codigo: int | None
    ms: float
    insistiu: bool = False

    @property
    def por(self) -> str:
        """O nome do fim: ``SIGPIPE``, ``SIGKILL``, ``saiu`` ou ``vivo``."""
        if self.codigo is None:
            return "vivo"
        if self.codigo >= 0:
            return "saiu"
        try:
            return signal.Signals(-self.codigo).name
        except ValueError:
            return f"sinal {-self.codigo}"


def _terminar(proc: Any) -> None:
    terminar = getattr(proc, "terminate", None)
    if terminar is None:
        return
    with contextlib.suppress(Exception):
        terminar()


def _fechar_a_saida(proc: Any) -> None:
    saida = getattr(proc, "stdout", None)
    if saida is None:
        return
    with contextlib.suppress(Exception):
        saida.close()


def _esperar(proc: Any, prazo_s: float) -> int | None:
    """O código de saída, ou ``None`` se o processo não morreu no prazo."""
    esperar = getattr(proc, "wait", None)
    if esperar is None:
        return None
    try:
        codigo = esperar(timeout=prazo_s)
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
    codigo = getattr(proc, "returncode", codigo)
    return int(codigo) if codigo is not None else None


def derrubar_leitor_de_pipe(
    proc: Any,
    *,
    leitor: threading.Thread | None = None,
    junta_s: float = ESPERA_PELO_FIM_S,
    espera_s: float = ESPERA_PELO_FIM_S,
) -> ComoMorreu:
    """Derruba e COLHE um processo cujo ``stdout`` é lido por nós. Idempotente."""
    comeco = time.monotonic()
    if proc is None:
        return ComoMorreu(codigo=None, ms=0.0)
    _terminar(proc)
    if leitor is not None and leitor.is_alive():
        leitor.join(timeout=junta_s)
    parado = leitor is None or not leitor.is_alive()
    if parado:
        _fechar_a_saida(proc)
    insistiu = False
    codigo = _esperar(proc, espera_s)
    if codigo is None:
        matar = getattr(proc, "kill", None)
        if matar is not None:
            insistiu = True
            with contextlib.suppress(Exception):
                matar()
            codigo = _esperar(proc, espera_s)
    if not parado and leitor is not None:
        leitor.join(timeout=junta_s)
    if leitor is None or not leitor.is_alive():
        _fechar_a_saida(proc)
    return ComoMorreu(
        codigo=codigo,
        ms=round((time.monotonic() - comeco) * 1000.0, 1),
        insistiu=insistiu,
    )


__all__ = [
    "ESPERA_PELO_FIM_S",
    "ComoMorreu",
    "derrubar_leitor_de_pipe",
    "lancar_leitor",
    "morrer_com_o_pai",
]
