"""Cobertura do fallback de import em logging_config.

BUG-DEB-SMOKE-STRUCTLOG-TYPING-02: em Ubuntu 22.04 (Jammy) o python3-structlog
do apt é versão 21.x, anterior à introdução de `structlog.typing`. O fallback
para `structlog.types` mantém compatibilidade sem exigir pip install extra.
"""
from __future__ import annotations

import importlib
import sys

import pytest


def test_logging_config_importa_com_structlog_typing_presente() -> None:
    """Caminho feliz: structlog moderno (>= 22.1) expõe .typing. Deve funcionar."""
    import structlog.typing  # noqa: F401

    import hefesto.utils.logging_config as mod

    importlib.reload(mod)
    assert hasattr(mod, "Processor")


def test_logging_config_fallback_quando_typing_ausente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove structlog.typing e força reload; o fallback de types deve resolver.

    Reproduz o cenário do Jammy sem precisar rodar o apt: mascara o módulo
    filho e força a re-importação do logging_config.
    """
    original_typing = sys.modules.pop("structlog.typing", None)
    original_logging_config = sys.modules.pop("hefesto.utils.logging_config", None)

    try:
        monkeypatch.setitem(sys.modules, "structlog.typing", None)
        with pytest.raises(ImportError):
            import structlog.typing  # noqa: F401

        monkeypatch.setitem(sys.modules, "structlog.typing", None)
        import hefesto.utils.logging_config as mod

        assert hasattr(mod, "Processor"), (
            "Fallback para structlog.types deveria expor Processor"
        )
    finally:
        sys.modules.pop("structlog.typing", None)
        if original_typing is not None:
            sys.modules["structlog.typing"] = original_typing
        sys.modules.pop("hefesto.utils.logging_config", None)
        if original_logging_config is not None:
            sys.modules["hefesto.utils.logging_config"] = original_logging_config
        else:
            importlib.import_module("hefesto.utils.logging_config")


def test_structlog_types_tem_processor() -> None:
    """Garante que structlog.types existe e expõe Processor (pré-22.1 e pós)."""
    from structlog.types import Processor  # type: ignore[attr-defined]

    assert Processor is not None
