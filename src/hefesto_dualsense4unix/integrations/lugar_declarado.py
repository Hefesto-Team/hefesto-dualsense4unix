"""Grava o que ela declarou DIRETO NO DISCO — sem daemon, sem IPC."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import (
    ResultadoDaGravacao,
    gravar_maquina_com_descartes,
    gravar_rascunho_da_mesa,
)

logger = get_logger(__name__)

MOTIVO_VERSAO_ESTRANHA = "versao_estranha"

MOTIVO_SCHEMA_RECUSOU = "schema_recusou"

MOTIVO_DISCO = "disco"


@dataclass(frozen=True)
class Recibo:
    """O que a gravação fez. ``motivo`` é ``""`` exatamente quando ``gravou``."""

    gravou: bool
    motivo: str = ""
    descartados: tuple[str, ...] = field(default_factory=tuple)


def declarar_a_mesa(declaracao: Mapping[str, Any]) -> Recibo:
    """Funde a declaração na seção ``mesa`` do ``maquina.json``. **Nunca levanta.**"""
    return _gravar(
        lambda: ResultadoDaGravacao(gravar_rascunho_da_mesa(declaracao), ()),
        campos=sorted(declaracao),
    )


def declarar_a_maquina(declaracao: Mapping[str, Any]) -> Recibo:
    """Funde a declaração INTEIRA no ``maquina.json``. **Nunca levanta.**"""
    return _gravar(
        lambda: gravar_maquina_com_descartes(declaracao), campos=sorted(declaracao)
    )


def _gravar(fazer: Callable[[], ResultadoDaGravacao], *, campos: list[str]) -> Recibo:
    """As três respostas possíveis da gravação, viradas :class:`Recibo`."""
    try:
        resultado = fazer()
    except ValueError as exc:
        logger.warning("lugar_declarado_schema_recusou", err=str(exc), campos=campos)
        return Recibo(False, MOTIVO_SCHEMA_RECUSOU)
    except OSError as exc:
        logger.warning("lugar_declarado_disco_recusou", err=str(exc), campos=campos)
        return Recibo(False, MOTIVO_DISCO)
    if not resultado.gravou:
        logger.warning("lugar_declarado_versao_estranha", campos=campos)
        return Recibo(False, MOTIVO_VERSAO_ESTRANHA)
    logger.debug(
        "lugar_declarado_gravado",
        campos=campos,
        descartados=list(resultado.descartados),
    )
    return Recibo(True, descartados=tuple(resultado.descartados))


__all__ = [
    "MOTIVO_DISCO",
    "MOTIVO_SCHEMA_RECUSOU",
    "MOTIVO_VERSAO_ESTRANHA",
    "Recibo",
    "declarar_a_maquina",
    "declarar_a_mesa",
]
