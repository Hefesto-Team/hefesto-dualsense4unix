"""D-2011-TODO-LOGGER-PASSA-PELO-DONO-DO-LOG: o logger das integrações vem do dono do log.

O ``logging.getLogger`` direto dava ao módulo um logger que o dono do log não entrega, não solta
no reset e não alcança no ``capture_logs``. Os módulos de ``integrations`` pegam o logger pelo
``get_logger`` de ``utils/logging_config``. O leitor do estado, que roda como arquivo avulso,
fica no ``logging``.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import logging_config as lc

_SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
_INTEGRACOES = _SRC / "integrations"

AINDA_COM_LOGGING_DIRETO = frozenset({"canal_do_microfone.py", "leitor_do_estado.py"})

OS_MIGRADOS = {
    "a_roupa_do_jogo": "logger",
    "impedimentos_da_steam": "_LOG",
    "microfone_filtrado": "logger",
    "api_de_entrada": "logger",
    "ficha_declarada": "logger",
}


def _quem_pega_o_logger_do_logging(arvore: ast.AST) -> list[int]:
    """As linhas que chamam `logging.getLogger` ou importam `getLogger` do `logging`."""
    linhas: list[int] = []
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Attribute)
            and no.attr == "getLogger"
            and isinstance(no.value, ast.Name)
            and no.value.id == "logging"
        ):
            linhas.append(no.lineno)
        if (
            isinstance(no, ast.ImportFrom)
            and no.module == "logging"
            and any(a.name == "getLogger" for a in no.names)
        ):
            linhas.append(no.lineno)
    return linhas


def test_nenhuma_integracao_pega_o_logger_do_logging() -> None:
    """MORDIDA: um ``logging.getLogger`` devolvido a uma integração reprova a régua."""
    fora_do_dono: dict[str, list[int]] = {}
    for arquivo in sorted(_INTEGRACOES.rglob("*.py")):
        if arquivo.name in AINDA_COM_LOGGING_DIRETO:
            continue
        linhas = _quem_pega_o_logger_do_logging(ast.parse(arquivo.read_text(encoding="utf-8")))
        if linhas:
            fora_do_dono[str(arquivo.relative_to(_SRC))] = linhas
    assert fora_do_dono == {}


def test_a_regua_enxerga_as_duas_formas() -> None:
    direta = ast.parse("import logging\nlogger = logging.getLogger(__name__)\n")
    importada = ast.parse("from logging import getLogger\n")
    da_casa = ast.parse("from hefesto_dualsense4unix.utils.logging_config import get_logger\n")
    assert _quem_pega_o_logger_do_logging(direta) == [2]
    assert _quem_pega_o_logger_do_logging(importada) == [1]
    assert _quem_pega_o_logger_do_logging(da_casa) == []


@pytest.mark.parametrize(("o_modulo_de_som", "nome"), sorted(OS_MIGRADOS.items()))
def test_o_logger_dos_migrados_e_o_que_o_dono_entrega(o_modulo_de_som: str, nome: str) -> None:
    """MORDIDA: o ``logging.getLogger`` de volta tira o logger do conjunto que o dono solta."""
    mod = importlib.import_module(f"hefesto_dualsense4unix.integrations.{o_modulo_de_som}")
    assert getattr(mod, nome) in lc._ENTREGUES


def _importa_o_pacote_no_topo(arvore: ast.Module) -> list[int]:
    linhas: list[int] = []
    for no in arvore.body:
        if isinstance(no, ast.Import):
            nomes = [a.name for a in no.names]
        elif isinstance(no, ast.ImportFrom) and no.level == 0:
            nomes = [no.module or ""]
        else:
            continue
        if any(n.split(".")[0] == "hefesto_dualsense4unix" for n in nomes):
            linhas.append(no.lineno)
    return linhas


def test_o_leitor_do_estado_roda_avulso_so_com_a_biblioteca_padrao() -> None:
    """MORDIDA: o leitor é copiado para o ``bin`` e roda em ``python3 -I`` sem o pacote.

    Por isso ele fica no ``logging`` da biblioteca padrão e não importa o ``get_logger`` do dono.
    """
    fonte = (_INTEGRACOES / "leitor_do_estado.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    assert _importa_o_pacote_no_topo(arvore) == []
    assert _quem_pega_o_logger_do_logging(arvore) != []
    assert _importa_o_pacote_no_topo(ast.parse("from hefesto_dualsense4unix.x import y\n")) == [1]
