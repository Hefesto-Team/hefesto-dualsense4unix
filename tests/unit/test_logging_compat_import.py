"""Cobertura do fallback de import em logging_config."""
from __future__ import annotations

import importlib
import sys

import pytest


def test_logging_config_importa_com_structlog_typing_presente() -> None:
    """Caminho feliz: structlog moderno (>= 22.1) expõe .typing. Deve funcionar."""
    import structlog.typing  # noqa: F401

    import hefesto_dualsense4unix.utils.logging_config as mod

    configurado_antes = mod._configured
    try:
        importlib.reload(mod)
        assert hasattr(mod, "Processor")
    finally:
        mod._configured = configurado_antes


def test_logging_config_fallback_quando_typing_ausente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove structlog.typing e força reload; o fallback de types deve resolver."""
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
    """structlog 20.x (Jammy apt default) não tem typing NEM types."""
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
