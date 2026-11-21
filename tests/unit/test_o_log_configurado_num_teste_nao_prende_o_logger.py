"""O log configurado num teste não prende o logger de módulo dos testes seguintes.

Em 09/11/2026 a parte 02 da suíte deu 6 vermelhos no ``test_profile_loader``: o logger do
loader, usado com o log configurado, guardou a montagem daquela configuração
(``cache_logger_on_first_use``), e o ``reset_for_tests`` trocava a lista de processadores por
outra, que o ``capture_logs`` esvazia sem alcançar o logger guardado. O serviço continua
guardando a montagem no primeiro uso.
"""
from __future__ import annotations

import ast
import io
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog

from hefesto_dualsense4unix.utils import logging_config as lc


@pytest.fixture(autouse=True)
def _limpo() -> Iterator[None]:
    lc.reset_for_tests()
    yield
    lc.reset_for_tests()


def test_o_servico_guarda_a_montagem_no_primeiro_uso() -> None:
    lc.configure_logging(stream=io.StringIO())
    logger = lc.get_logger("modulo_do_servico")
    logger.warning("primeiro_uso")
    guardado = vars(logger).get("bind")
    assert guardado is not None
    logger.warning("segundo_uso")
    assert vars(logger).get("bind") is guardado


def test_o_capture_logs_depois_do_reset_ve_o_logger_ja_usado() -> None:
    """D-0911-O-LOG-DE-UM-TESTE-NAO-PRENDE-O-DOS-OUTROS: o logger usado com o log configurado
    aparece no ``capture_logs`` depois do reset."""
    lc.configure_logging(stream=io.StringIO())
    logger = lc.get_logger("modulo_do_loader")
    logger.warning("usado_com_o_log_configurado")
    lc.reset_for_tests()
    with structlog.testing.capture_logs() as capturado:
        logger.warning("depois_do_reset", campo=1)
    assert [e["event"] for e in capturado] == ["depois_do_reset"]


def test_o_destino_novo_recebe_o_logger_ja_usado() -> None:
    primeiro, segundo = io.StringIO(), io.StringIO()
    lc.configure_logging(stream=primeiro)
    logger = lc.get_logger("modulo_do_destino")
    logger.warning("no_primeiro")
    lc.reset_for_tests()
    lc.configure_logging(stream=segundo)
    logger.warning("no_segundo")
    assert "no_segundo" in segundo.getvalue()
    assert "no_segundo" not in primeiro.getvalue()


def test_o_get_logger_dentro_do_capture_logs_depois_do_reset_nao_reconfigura() -> None:
    lc.configure_logging(stream=io.StringIO())
    lc.reset_for_tests()
    with structlog.testing.capture_logs() as capturado:
        lc.get_logger("modulo_que_chega_depois").warning("dentro_do_capture")
    assert [e["event"] for e in capturado] == ["dentro_do_capture"]


def test_o_reload_do_modulo_nao_perde_os_entregues() -> None:
    import importlib

    entregues = lc._ENTREGUES
    configurado = lc._configured
    try:
        importlib.reload(lc)
        assert lc._ENTREGUES is entregues
    finally:
        lc._configured = configurado


_SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
_DONO_DO_LOG = _SRC / "utils" / "logging_config.py"


def _quem_pega_o_logger_do_structlog(arvore: ast.AST) -> list[int]:
    """As linhas que chamam `structlog.get_logger` ou importam `get_logger` do structlog."""
    linhas: list[int] = []
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Attribute)
            and no.attr in {"get_logger", "getLogger"}
            and isinstance(no.value, ast.Name)
            and no.value.id == "structlog"
        ):
            linhas.append(no.lineno)
        if (
            isinstance(no, ast.ImportFrom)
            and no.module == "structlog"
            and any(a.name in {"get_logger", "getLogger"} for a in no.names)
        ):
            linhas.append(no.lineno)
    return linhas


def test_so_o_dono_do_log_pega_o_logger_do_structlog() -> None:
    """D-2011-TODO-LOGGER-PASSA-PELO-DONO-DO-LOG: o reset só alcança o logger da casa."""
    fora_do_dono: dict[str, list[int]] = {}
    for arquivo in sorted(_SRC.rglob("*.py")):
        if arquivo == _DONO_DO_LOG:
            continue
        linhas = _quem_pega_o_logger_do_structlog(ast.parse(arquivo.read_text(encoding="utf-8")))
        if linhas:
            fora_do_dono[str(arquivo.relative_to(_SRC))] = linhas
    assert fora_do_dono == {}


def test_a_regua_do_logger_enxerga_as_duas_formas() -> None:
    direta = ast.parse("import structlog\nlogger = structlog.get_logger(__name__)\n")
    importada = ast.parse("from structlog import get_logger\n")
    da_casa = ast.parse("from hefesto_dualsense4unix.utils.logging_config import get_logger\n")
    assert _quem_pega_o_logger_do_structlog(direta) == [2]
    assert _quem_pega_o_logger_do_structlog(importada) == [1]
    assert _quem_pega_o_logger_do_structlog(da_casa) == []
