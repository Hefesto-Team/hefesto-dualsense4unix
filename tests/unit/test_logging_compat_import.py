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

    import hefesto_dualsense4unix.utils.logging_config as mod

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
    original_logging_config = sys.modules.pop("hefesto_dualsense4unix.utils.logging_config", None)

    try:
        monkeypatch.setitem(sys.modules, "structlog.typing", None)
        with pytest.raises(ImportError):
            import structlog.typing  # noqa: F401

        monkeypatch.setitem(sys.modules, "structlog.typing", None)
        import hefesto_dualsense4unix.utils.logging_config as mod

        assert hasattr(mod, "Processor"), (
            "Fallback para structlog.types deveria expor Processor"
        )
    finally:
        sys.modules.pop("structlog.typing", None)
        if original_typing is not None:
            sys.modules["structlog.typing"] = original_typing
        sys.modules.pop("hefesto_dualsense4unix.utils.logging_config", None)
        if original_logging_config is not None:
            sys.modules["hefesto_dualsense4unix.utils.logging_config"] = original_logging_config
        else:
            importlib.import_module("hefesto_dualsense4unix.utils.logging_config")


def test_structlog_types_tem_processor() -> None:
    """Garante que structlog.types existe e expõe Processor (pré-22.1 e pós)."""
    from structlog.types import Processor  # type: ignore[attr-defined]

    assert Processor is not None


def test_cascata_tripla_fallback_callable_quando_nem_typing_nem_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """structlog 20.x (Jammy apt default) não tem typing NEM types.

    Valida que o 3º nível da cascata (Callable alias) é acionado quando
    ambos os submódulos de tipo estão ausentes. Simula o cenário bloqueando
    ambos os imports via sys.modules=None.
    """
    original_typing = sys.modules.pop("structlog.typing", None)
    original_types = sys.modules.pop("structlog.types", None)
    original_logging_config = sys.modules.pop("hefesto_dualsense4unix.utils.logging_config", None)

    try:
        monkeypatch.setitem(sys.modules, "structlog.typing", None)
        monkeypatch.setitem(sys.modules, "structlog.types", None)

        import hefesto_dualsense4unix.utils.logging_config as mod

        assert hasattr(mod, "Processor"), (
            "Cascata deveria cair no Callable alias quando typing E types faltam"
        )
    finally:
        sys.modules.pop("structlog.typing", None)
        sys.modules.pop("structlog.types", None)
        sys.modules.pop("hefesto_dualsense4unix.utils.logging_config", None)
        if original_typing is not None:
            sys.modules["structlog.typing"] = original_typing
        if original_types is not None:
            sys.modules["structlog.types"] = original_types
        if original_logging_config is not None:
            sys.modules["hefesto_dualsense4unix.utils.logging_config"] = original_logging_config
        else:
            importlib.import_module("hefesto_dualsense4unix.utils.logging_config")
