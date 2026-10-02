"""O lixo do WebKit se recolhe no fio do GTK, depois de cada teste (02/10/2026).

MEDIDO em 01 e 02/10/2026, num lote de 42 arquivos vizinhos da aba Conexões,
três vezes em três: o processo morria com `Fatal Python error: Aborted`, e a
pilha dizia «Garbage-collecting» num fio da central do rádio. O objeto do
`WebKit2` que um teste deixava num ciclo de referências só saía na coleta, e a
coleta rodava no fio que estivesse alocando — fora do fio do GTK, onde o WebKit
aborta ao soltar o objeto. A cura é a borda do `tests/conftest.py`
(`pytest_runtest_teardown_do_webkit`): depois de todo teste de arquivo que diz
`WebKit2`, e na troca de arquivo com o WebKit carregado, a coleta roda no fio
principal.

Esta régua não precisa do WebKit: o ciclo é de Python, e o que se prova é que a
borda o recolhe no teardown, e só onde deve.

AS MORDIDAS: tire o `gc.collect()` de `_recolher_no_fio_do_gtk`, e a primeira
reprova (o ciclo sobrevive ao teardown); faça `_e_arquivo_do_webkit` dizer
sempre «não», e a primeira reprova também; tire o `@pytest.hookimpl` da borda,
e o pytest recusa o conftest (um `pytest_*` que não é gancho conhecido) antes
de coletar; trocado o nome, a terceira reprova.
"""
from __future__ import annotations

import contextlib
import gc
import weakref
from pathlib import Path
from typing import Any

import pytest

from tests import conftest


class _Sentinela:
    """O objeto que faz o papel da vista: só morre se alguém recolher o ciclo."""


class _Item:
    def __init__(self, path: Path) -> None:
        self.path = path


def _ciclo_que_guarda_a_sentinela() -> weakref.ref[_Sentinela]:
    sentinela = _Sentinela()
    no: dict[str, Any] = {"vista": sentinela}
    no["eu"] = no  # o ciclo: só a coleta o solta
    return weakref.ref(sentinela)


def _rodar_a_borda(item: _Item, proximo: _Item | None) -> None:
    gerador = conftest.pytest_runtest_teardown_do_webkit(item, proximo)
    next(gerador)
    with contextlib.suppress(StopIteration):
        gerador.send(None)


def _arquivo(tmp_path: Path, nome: str, texto: str) -> Path:
    caminho = tmp_path / nome
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def test_o_teardown_de_um_arquivo_do_webkit_recolhe_o_ciclo(tmp_path: Path) -> None:
    do_webkit = _arquivo(tmp_path, "test_vista.py", "gi.require_version('WebKit2', '4.1')\n")
    gc.disable()
    try:
        vista = _ciclo_que_guarda_a_sentinela()
        assert vista() is not None, "o ciclo morreu sozinho: a régua não mede nada"
        _rodar_a_borda(_Item(do_webkit), _Item(do_webkit))
        assert vista() is None, (
            "o teardown de um teste do WebKit deixou o ciclo vivo: a coleta vai "
            "rodar no fio que estiver alocando, e o WebKit aborta fora do fio do GTK")
    finally:
        gc.enable()


def test_o_teardown_de_um_arquivo_sem_webkit_nao_paga_a_coleta(tmp_path: Path) -> None:
    """No meio de um arquivo sem WebKit, a borda não coleta: a suíte não paga por teste."""
    comum = _arquivo(tmp_path, "test_comum.py", "def test_x():\n    pass\n")
    gc.disable()
    try:
        vista = _ciclo_que_guarda_a_sentinela()
        _rodar_a_borda(_Item(comum), _Item(comum))
        assert vista() is not None, (
            "a borda coletou no meio de um arquivo sem WebKit: cada teste da "
            "suíte pagaria uma coleta inteira")
    finally:
        gc.enable()
        gc.collect()


def test_a_borda_e_um_teardown_do_pytest(request: pytest.FixtureRequest) -> None:
    gancho = request.config.pluginmanager.hook.pytest_runtest_teardown
    nomes = {impl.function.__name__ for impl in gancho.get_hookimpls()}
    assert "pytest_runtest_teardown_do_webkit" in nomes, (
        "a borda que recolhe o lixo do WebKit não está registrada no pytest: "
        "o lote de vizinhos volta a morrer com «Garbage-collecting» num fio")
