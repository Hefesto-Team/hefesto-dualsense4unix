"""A RÉGUA DA AS-REGUAS-DAS-DEZ-ABAS-NAO-LEEM-O-DIARIO-DA-MAQUINA-01: a 09 não abre o registro."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests import conftest
from tests.conftest import DIARIO_DE_MENTIRA_DA_SUITE

NOME_DO_PACOTE = "hefesto_dualsense4unix.interface.pacotes.a09_sistema"
NOME_DA_PASTA = "pacotes.a09_sistema"


class _Espia:
    """O `subprocess.run` de mentira: anota quem pediu o registro da unit e devolve vazio."""

    def __init__(self) -> None:
        self.pedidos: list[list[str]] = []

    def __call__(self, argv: Any, *_a: Any, **_k: Any) -> subprocess.CompletedProcess[str]:
        if isinstance(argv, (list, tuple)) and argv and str(argv[0]) == "journalctl":
            self.pedidos.append([str(x) for x in argv])
        return subprocess.CompletedProcess(argv, 0, "", "")


@pytest.fixture
def espia(monkeypatch: pytest.MonkeyPatch) -> _Espia:
    espia = _Espia()
    monkeypatch.setattr(subprocess, "run", espia)
    return espia


def _a09(nome: str) -> Any:
    __import__(nome)
    return sys.modules[nome]


@pytest.mark.parametrize("nome", [NOME_DO_PACOTE, NOME_DA_PASTA])
def test_pintar_o_repouso_da_09_nao_abre_o_registro_da_maquina(espia: _Espia, nome: str) -> None:
    """O painel de repouso traz o `_diario`; o texto é o da suíte e o `journalctl` nunca roda."""
    if nome == NOME_DA_PASTA:
        sys.path.insert(0, str(_a09(NOME_DO_PACOTE).__file__).rsplit("/pacotes/", 1)[0])
    try:
        a09 = _a09(nome)
        texto = a09._repouso_do_painel(None)
    finally:
        if nome == NOME_DA_PASTA:
            sys.path.pop(0)
    assert DIARIO_DE_MENTIRA_DA_SUITE in texto, texto
    assert espia.pedidos == [], espia.pedidos


def test_a_aba_importada_depois_da_fixture_nasce_trocada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A régua importa a aba no corpo do teste: o achador troca o `_diario` do módulo que nasce."""
    pacote = tmp_path / "abafalsa_do_diario"
    pacote.mkdir()
    (pacote / "__init__.py").write_text("", encoding="utf-8")
    (pacote / "a09_falsa.py").write_text(
        "def _diario():\n    return 'o da máquina'\n", encoding="utf-8")
    nome = "abafalsa_do_diario.a09_falsa"
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(conftest, "_NOMES_DA_ABA_DO_DIARIO", (nome,))
    achador = conftest._AchadorDaAbaDoDiario(
        lambda modulo: setattr(modulo, "_diario", lambda: DIARIO_DE_MENTIRA_DA_SUITE))
    monkeypatch.setattr(sys, "meta_path", [achador, *sys.meta_path])
    monkeypatch.delitem(sys.modules, nome, raising=False)
    monkeypatch.delitem(sys.modules, "abafalsa_do_diario", raising=False)
    modulo = importlib.import_module(nome)
    assert modulo._diario() == DIARIO_DE_MENTIRA_DA_SUITE
    sys.modules.pop(nome, None)
    sys.modules.pop("abafalsa_do_diario", None)


def test_quem_troca_o_diario_a_mao_continua_valendo(
    espia: _Espia, monkeypatch: pytest.MonkeyPatch
) -> None:
    a09 = _a09(NOME_DO_PACOTE)
    monkeypatch.setattr(a09, "_diario", lambda: "texto da régua")
    assert "texto da régua" in a09._repouso_do_painel(None)
    assert espia.pedidos == []


@pytest.mark.o_diario_de_verdade
def test_quem_declara_a_marca_mede_o_diario_de_verdade(espia: _Espia) -> None:
    """A marca devolve o `_diario` do produto: o que ele pede ao `journalctl` se mede."""
    a09 = _a09(NOME_DO_PACOTE)
    assert a09._diario.__code__.co_name == "_diario"
    a09._diario()
    assert len(espia.pedidos) == 1 and espia.pedidos[0][0] == "journalctl", espia.pedidos
