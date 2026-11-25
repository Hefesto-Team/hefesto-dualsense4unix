"""Quem pede o `start`, o `stop` ou o `restart` do serviço deixa o nome ANTES de pedir ao systemd.

Dono único da anotação: uma linha (``instante<TAB>verbo<TAB>quem<TAB>pid<TAB>motivo``) no runtime
do produto, sobrescrita inteira. O serviço, ao parar, a lê e escreve o nome no diário; sem
anotação de até 30 s a parada diz `fora-do-produto` (o `systemctl` na mão não deixa nome). Os
scripts de shell gravam a mesma linha no mesmo formato e este módulo lê as duas. :func:`anotar`
nunca levanta: o pedido ao systemd não falha por causa da anotação.
"""
from __future__ import annotations

import contextlib
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

logger = get_logger(__name__)

NOME_DO_ARQUIVO = "pedido-ao-servico"
FORA_DO_PRODUTO = "fora-do-produto"
VERBOS = ("start", "stop", "restart", "try-restart")
VERBOS_QUE_SOBEM = ("start", "restart", "try-restart")
TETO_DA_PARADA_S = 30.0
TETO_DA_SUBIDA_S = 120.0
_LIMITE_DO_CAMPO = 120
_INSTANTE = re.compile(r"\d+(\.\d+)?")
_PID = re.compile(r"\d+")


@dataclass(frozen=True)
class Pedido:
    """O que a anotação diz: quando, o quê, quem, de qual processo e por quê."""

    instante: float
    verbo: str
    quem: str
    pid: int
    motivo: str


def arquivo() -> Path:
    """Onde mora a anotação: o runtime da sessão, que o logout limpa."""
    return runtime_dir() / NOME_DO_ARQUIVO


def _campo(texto: object) -> str:
    """Uma palavra de linha só: sem tabulação nem quebra, com teto."""
    limpo = " ".join(str(texto).replace("\t", " ").split())
    return limpo[:_LIMITE_DO_CAMPO]


def anotar(verbo: str, quem: str, motivo: str = "") -> bool:
    """Grava a anotação (instante, verbo, quem, pid, motivo); devolve se gravou, nunca levanta."""
    try:
        alvo = arquivo()
        alvo.parent.mkdir(parents=True, exist_ok=True)
        linha = "\t".join(
            (f"{time.time():.3f}", _campo(verbo), _campo(quem) or FORA_DO_PRODUTO,
             str(os.getpid()), _campo(motivo))
        )
        temporario = alvo.with_name(f"{NOME_DO_ARQUIVO}.{os.getpid()}.tmp")
        try:
            temporario.write_text(linha + "\n", encoding="utf-8")
            os.replace(temporario, alvo)
        finally:
            with contextlib.suppress(OSError):
                temporario.unlink()
    except Exception:
        return False
    return True


def ler(teto_s: float, agora: float | None = None) -> Pedido | None:
    """A anotação com menos de `teto_s` segundos; None se falta, é ilegível ou é velha."""
    try:
        alvo = arquivo()
        if not alvo.is_file():
            return None
        texto = alvo.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as erro:
        logger.warning("pedido_ao_servico_ilegivel", erro=str(erro))
        return None
    partes = texto.strip("\n").split("\t", 4)
    if len(partes) < 4 or not _INSTANTE.fullmatch(partes[0]) or not _PID.fullmatch(partes[3]):
        return None
    instante = float(partes[0])
    pid = int(partes[3])
    idade = (time.time() if agora is None else agora) - instante
    if idade < -1.0 or idade > teto_s:
        return None
    return Pedido(instante=instante, verbo=partes[1], quem=partes[2] or FORA_DO_PRODUTO,
                  pid=pid, motivo=partes[4] if len(partes) > 4 else "")


def a_parada_pedida(agora: float | None = None) -> Pedido | None:
    """Quem pediu a parada que chega agora: a anotação de até 30 s."""
    return ler(TETO_DA_PARADA_S, agora)


def a_subida_pedida(agora: float | None = None) -> Pedido | None:
    """Quem pediu a subida que acontece agora (`start`, `restart`): a anotação de até 120 s."""
    pedido = ler(TETO_DA_SUBIDA_S, agora)
    if pedido is None or pedido.verbo not in VERBOS_QUE_SOBEM:
        return None
    return pedido


def _dizer_quem_pediu_a_parada(logger: Any) -> None:
    pedido = a_parada_pedida()
    if pedido is None:
        logger.info("daemon_stop_requested", quem=FORA_DO_PRODUTO)
        return
    logger.info("daemon_stop_requested", quem=pedido.quem, motivo=pedido.motivo or "-",
                verbo=pedido.verbo)


def _dizer_de_quem_foi_a_subida(logger: Any) -> None:
    pedido = a_subida_pedida()
    if pedido is None:
        return
    logger.info("daemon_subiu_depois_de", quem=pedido.quem, motivo=pedido.motivo or "-",
                verbo=pedido.verbo)


def dizer_quem_pediu_a_parada(logger: Any) -> threading.Thread:
    """Escreve `daemon_stop_requested quem=...` fora do fio de quem chamou: a parada não espera."""
    fio = threading.Thread(target=_dizer_quem_pediu_a_parada, args=(logger,),
                           name="quem-pediu-a-parada", daemon=True)
    fio.start()
    return fio


def dizer_de_quem_foi_a_subida(logger: Any) -> threading.Thread:
    """Escreve `daemon_subiu_depois_de quem=...` fora do fio de quem chamou: a subida não espera."""
    fio = threading.Thread(target=_dizer_de_quem_foi_a_subida, args=(logger,),
                           name="de-quem-foi-a-subida", daemon=True)
    fio.start()
    return fio


__all__ = [
    "FORA_DO_PRODUTO",
    "NOME_DO_ARQUIVO",
    "Pedido",
    "a_parada_pedida",
    "a_subida_pedida",
    "anotar",
    "arquivo",
    "dizer_de_quem_foi_a_subida",
    "dizer_quem_pediu_a_parada",
    "ler",
]
