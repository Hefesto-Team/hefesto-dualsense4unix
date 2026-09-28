"""Configuração de logging do daemon com structlog.

Formato padrão: key=value legível no terminal (dev) ou JSON (prod). Controlado
pela env `HEFESTO_DUALSENSE4UNIX_LOG_FORMAT=json|console` (default `console`).

Nível controlado por `HEFESTO_DUALSENSE4UNIX_LOG_LEVEL` (default `INFO`). Valores aceitos:
DEBUG, INFO, WARNING, ERROR, CRITICAL.

Uso:
    from hefesto_dualsense4unix.utils.logging_config import configure_logging, get_logger
    configure_logging()
    logger = get_logger(__name__)
    logger.info("daemon_start", transport="usb", profile="shooter")

O DIÁRIO NASCE MASCARADO (O-REGISTRO-COPIADO-NAO-ENTREGA-O-ENDERECO-01,
28/09/2026). O journal é o que se copia num relato de defeito, e até aqui ele
guardava o endereço dos controles cru. O dono da máscara
(``core/formas_do_endereco.mascarar``) é o último passo da cadeia do structlog,
sobre o texto JÁ RENDERIZADO — mascarar valor a valor deixaria de fora a lista
``nos=[…]`` e os dicionários aninhados —, e um ``logging.Filter`` no
manipulador do ``basicConfig`` faz o mesmo com a linha de biblioteca, que não
passa pela cadeia. Um defeito no dono não derruba o log: a linha sai com o
nome do erro no lugar do texto (:func:`mascarar_a_linha`).
"""
from __future__ import annotations

import logging
import os
import re
import sys
from typing import TYPE_CHECKING, Any

import structlog

from hefesto_dualsense4unix.core import formas_do_endereco as _formas

if TYPE_CHECKING:
    from structlog.typing import Processor
else:
    # Cascata empírica (L-21-7 — apt-cache policy confirmado 2026-04-24):
    #   structlog 22.1+  → expõe .typing
    #   structlog 21.x   → só .types
    #   structlog 20.x (Ubuntu 22.04 Jammy apt default) → nenhum dos dois.
    # BUG-DEB-SMOKE-STRUCTLOG-TYPING-02. Processor é Callable no core, então
    # o último fallback aliases Processor como Callable[..., Any] para que
    # o restante do módulo funcione sem quebrar em versões antigas.
    try:
        from structlog.typing import Processor
    except ImportError:
        try:
            from structlog.types import Processor
        except ImportError:
            from collections.abc import Callable

            Processor = Callable[..., Any]  # type: ignore[misc,assignment]

_configured = False

#: As cores do terminal que o ``ConsoleRenderer`` põe em volta de cada valor.
#: O dono lê a borda de uma forma pelo vizinho (a colada exige um vizinho que
#: não seja letra nem algarismo), e o ``m`` que fecha a cor encosta no valor:
#: a linha colorida se mascara pedaço a pedaço, entre as cores.
_COR_DO_TERMINAL = re.compile(r"(\x1b\[[0-9;]*m)")


def mascarar_a_linha(texto: str) -> str:
    """A linha do diário na máscara da casa. Nunca levanta.

    Se o dono levantar, a linha sai com o nome do erro e o tamanho do texto no
    lugar dele: o log não cai (uma exceção aqui subiria até quem chamou
    ``logger.info``) e o endereço não sai cru — um endereço vazado não se
    apaga, e a linha perdida se reconta pelo erro.
    """
    try:
        if "\x1b[" not in texto:
            return _formas.mascarar(texto)
        partes = _COR_DO_TERMINAL.split(texto)
        return "".join(
            parte if i % 2 else _formas.mascarar(parte) for i, parte in enumerate(partes)
        )
    except Exception as erro:
        return f"mascara_do_diario_falhou erro={type(erro).__name__} caracteres={len(texto)}"


def _mascarar_o_renderizado(_logger: Any, _metodo: str, renderizado: Any) -> Any:
    """O último processador da cadeia: o texto já renderizado, pelo dono."""
    if isinstance(renderizado, str):
        return mascarar_a_linha(renderizado)
    return renderizado


class MascaraDoDiario(logging.Filter):
    """A linha de biblioteca (a que sai pelo ``logging``) pelo mesmo dono.

    Ela não passa pela cadeia do structlog. O filtro troca a mensagem já
    formatada pela mascarada, e mascara também o traceback e a pilha, que o
    formatador emenda depois. Nunca levanta e nunca descarta a linha.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            texto = record.getMessage()
        except Exception as erro:
            texto = f"mensagem_ilegivel erro={type(erro).__name__}"
        record.msg, record.args = mascarar_a_linha(texto), None
        if record.exc_info and not record.exc_text:
            try:
                record.exc_text = logging.Formatter().formatException(record.exc_info)
            except Exception as erro:
                record.exc_text = f"traceback_ilegivel erro={type(erro).__name__}"
        if record.exc_text:
            record.exc_text = mascarar_a_linha(record.exc_text)
        if record.stack_info:
            record.stack_info = mascarar_a_linha(record.stack_info)
        return True


def cadeia_do_diario(fmt: str = "console", stream: Any = None) -> list[Processor]:
    """Os processadores do structlog do produto, na ordem, com o dono no fim.

    Uma função, e não uma lista escrita dentro de :func:`configure_logging`: a
    régua mede a cadeia do produto num logger próprio, sem reconfigurar o
    structlog global (trocar a lista global desliga o ``capture_logs`` dos
    outros testes, que a mexe no lugar).
    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso", utc=False),
    ]

    if fmt == "json":
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        colors = stream.isatty() if hasattr(stream, "isatty") else False
        renderer = structlog.dev.ConsoleRenderer(colors=colors)

    return [*shared_processors, renderer, _mascarar_o_renderizado]


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

    level_name = (level or os.getenv("HEFESTO_DUALSENSE4UNIX_LOG_LEVEL") or "INFO").upper()
    log_fmt = (fmt or os.getenv("HEFESTO_DUALSENSE4UNIX_LOG_FORMAT") or "console").lower()
    stream = stream or sys.stderr

    log_level = getattr(logging, level_name, logging.INFO)
    raiz = logging.getLogger()
    antes = list(raiz.handlers)
    logging.basicConfig(
        format="%(message)s",
        stream=stream,
        level=log_level,
    )
    # SÓ o manipulador que o `basicConfig` criou ganha o filtro: se a raiz já
    # tinha dono (o `caplog` de uma régua), o `basicConfig` não faz nada, e o
    # filtro não entra num manipulador que não é do produto.
    for manipulador in raiz.handlers:
        if manipulador not in antes:
            manipulador.addFilter(MascaraDoDiario())

    structlog.configure(
        processors=cadeia_do_diario(log_fmt, stream),
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


__all__ = [
    "MascaraDoDiario",
    "cadeia_do_diario",
    "configure_logging",
    "get_logger",
    "mascarar_a_linha",
    "reset_for_tests",
]
