"""O logger dos módulos que rodam como script no Python do sistema, só com a biblioteca padrão.

A unidade do vigia da Steam, o ``disable_steam_input.sh``, o ``doctor.sh``, o ``install.sh`` e
``scripts/lib`` chamam módulos de ``integrations`` por ``python3``, sem ``structlog`` nem o pacote.
``get_logger(nome)`` tem a forma de chamada do dono do log (evento nomeado e campos) e escolhe pelo
**modo**, nunca pela presença da biblioteca: dentro do pacote entrega o logger de
``utils/logging_config``; no avulso entrega um adaptador do ``logging`` padrão, sem tentar o dono.
"""

from __future__ import annotations

import logging
from typing import Any

_NIVEIS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


class LoggerDoAvulso:
    """Aceita ``logger.debug("evento", campo=valor)`` e entrega ao ``logging`` padrão."""

    __slots__ = ("_log",)

    def __init__(self, nome: str | None) -> None:
        self._log = logging.getLogger(nome)

    def _emitir(self, nivel: int, evento: str, campos: dict[str, Any]) -> None:
        if not self._log.isEnabledFor(nivel):
            return
        exc_info = campos.pop("exc_info", None)
        detalhe = " ".join(f"{chave}={valor!r}" for chave, valor in campos.items())
        self._log.log(nivel, f"{evento} {detalhe}" if detalhe else evento, exc_info=exc_info)

    def debug(self, evento: str, **campos: Any) -> None:
        self._emitir(_NIVEIS["debug"], evento, campos)

    def info(self, evento: str, **campos: Any) -> None:
        self._emitir(_NIVEIS["info"], evento, campos)

    def warning(self, evento: str, **campos: Any) -> None:
        self._emitir(_NIVEIS["warning"], evento, campos)

    def error(self, evento: str, **campos: Any) -> None:
        self._emitir(_NIVEIS["error"], evento, campos)

    def exception(self, evento: str, **campos: Any) -> None:
        campos.setdefault("exc_info", True)
        self._emitir(_NIVEIS["error"], evento, campos)

    def critical(self, evento: str, **campos: Any) -> None:
        self._emitir(_NIVEIS["critical"], evento, campos)


if __package__:
    from ..utils.logging_config import get_logger as _do_dono

    def get_logger(nome: str | None = None) -> Any:
        """Dentro do pacote: o logger do dono do log."""
        return _do_dono(nome)

else:

    def get_logger(nome: str | None = None) -> Any:
        """No avulso: o adaptador do ``logging`` padrão."""
        return LoggerDoAvulso(nome)
