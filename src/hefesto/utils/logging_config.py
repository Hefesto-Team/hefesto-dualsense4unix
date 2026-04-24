"""Configuração de logging do daemon com structlog.

Formato padrão: key=value legível no terminal (dev) ou JSON (prod). Controlado
pela env `HEFESTO_LOG_FORMAT=json|console` (default `console`).

Nível controlado por `HEFESTO_LOG_LEVEL` (default `INFO`). Valores aceitos:
DEBUG, INFO, WARNING, ERROR, CRITICAL.

Uso:
    from hefesto.utils.logging_config import configure_logging, get_logger
    configure_logging()
    logger = get_logger(__name__)
    logger.info("daemon_start", transport="usb", profile="shooter")
"""
from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from structlog.typing import Processor
else:
    # structlog 22.1+ expõe .typing; Ubuntu 22.04 apt empacota 21.x com só
    # .types (BUG-DEB-SMOKE-STRUCTLOG-TYPING-02). Fallback runtime preserva
    # compatibilidade sem exigir pip install user.
    try:
        from structlog.typing import Processor
    except ImportError:
        from structlog.types import Processor

_configured = False


def configure_logging(
    *,
    level: str | None = None,
    fmt: str | None = None,
    stream: Any = None,
) -> None:
    """Configura logging stdlib + structlog. Idempotente."""
    global _configured
    if _configured:
        return

    level_name = (level or os.getenv("HEFESTO_LOG_LEVEL") or "INFO").upper()
    log_fmt = (fmt or os.getenv("HEFESTO_LOG_FORMAT") or "console").lower()
    stream = stream or sys.stderr

    log_level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=stream,
        level=log_level,
    )

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso", utc=False),
    ]

    if log_fmt == "json":
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        colors = stream.isatty() if hasattr(stream, "isatty") else False
        renderer = structlog.dev.ConsoleRenderer(colors=colors)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str | None = None) -> Any:
    """Retorna um logger structlog. Configura automaticamente se preciso."""
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)


def reset_for_tests() -> None:
    """Reseta o estado interno — uso exclusivo em testes."""
    global _configured
    _configured = False
    structlog.reset_defaults()


__all__ = ["configure_logging", "get_logger", "reset_for_tests"]
