"""O log configurado num teste não prende o logger de módulo dos testes seguintes.

Em 09/11/2026 a parte 02 da suíte deu 6 vermelhos no ``test_profile_loader``: o logger do
loader, usado com o log configurado, guardou a montagem daquela configuração
(``cache_logger_on_first_use``), e o ``reset_for_tests`` trocava a lista de processadores por
outra, que o ``capture_logs`` esvazia sem alcançar o logger guardado. O serviço continua
guardando a montagem no primeiro uso.
"""
from __future__ import annotations

import io
from collections.abc import Iterator

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
