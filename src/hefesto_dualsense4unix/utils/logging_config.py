"""Configuração de logging do daemon com structlog."""
from __future__ import annotations

import logging
import os
import re
import sys
import threading
import traceback
from typing import TYPE_CHECKING, Any

import structlog

from hefesto_dualsense4unix.core import formas_do_endereco as _formas

if TYPE_CHECKING:
    from structlog.typing import Processor
else:
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
_COR_DO_TERMINAL = re.compile(r"(\x1b\[[0-9;]*m)")


def mascarar_a_linha(texto: str) -> str:
    """A linha do diário na máscara da casa. Nunca levanta."""
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
    """A linha de biblioteca (a que sai pelo ``logging``) pelo mesmo dono."""

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


def _escrever_no_stderr(texto: str) -> None:
    """O texto no stderr de agora, já pelo dono; sem stderr aberto, não há onde escrever.

    Se a escrita num stderr aberto falhar, o erro sobe ao interpretador, que é o
    dono da falha de um gancho, e ele tenta o mesmo stderr: nada sai cru por outra porta.
    """
    saida = sys.stderr
    if saida is None or getattr(saida, "closed", False):
        return
    saida.write(mascarar_a_linha(texto))
    saida.flush()


def _o_fio_que_cai(argumentos: threading.ExceptHookArgs) -> None:
    """O `Exception in thread <nome>:` do gancho padrão, com o nome e o traceback pelo dono."""
    if argumentos.exc_type is SystemExit:
        return
    fio = argumentos.thread
    nome = fio.name if fio is not None else str(threading.get_ident())
    corpo = "".join(
        traceback.format_exception(
            argumentos.exc_type, argumentos.exc_value, argumentos.exc_traceback
        )
    )
    _escrever_no_stderr(f"Exception in thread {nome}:\n{corpo}")


def _o_processo_que_cai(tipo: type[BaseException], valor: BaseException, rastro: Any) -> None:
    """O traceback que o interpretador escreve ao morrer, pelo dono."""
    _escrever_no_stderr("".join(traceback.format_exception(tipo, valor, rastro)))


def instalar_os_ganchos_do_fio_que_cai() -> None:
    """O fio e o processo que caem escrevem pelo dono: o nome do fio e o traceback saem crus
    pelo stderr, por fora do ``logging``, e o filtro do diário não os vê."""
    threading.excepthook = _o_fio_que_cai
    sys.excepthook = _o_processo_que_cai


def cadeia_do_diario(fmt: str = "console", stream: Any = None) -> list[Processor]:
    """Os processadores do structlog do produto, na ordem, com o dono no fim."""
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
    for manipulador in raiz.handlers:
        if manipulador not in antes:
            manipulador.addFilter(MascaraDoDiario())
    if any(manipulador not in antes for manipulador in raiz.handlers):
        # A mesma guarda do filtro: só quando o manipulador é do produto. Sob o pytest ou
        # dentro de outro programa o raiz já tinha manipulador, e o gancho global não é nosso.
        instalar_os_ganchos_do_fio_que_cai()

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
    "instalar_os_ganchos_do_fio_que_cai",
    "mascarar_a_linha",
    "reset_for_tests",
]
