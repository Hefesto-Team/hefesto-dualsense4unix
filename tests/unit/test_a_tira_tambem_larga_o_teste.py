"""O clique na tira também larga o teste da aba Vibração."""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa o piloto, que carrega o GTK")

import gi

gi.require_version("WebKit2", "4.1")
from gi.repository import WebKit2

from hefesto_dualsense4unix.interface import hefesto_vivo, onde
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

UNIQ = "aa:bb:cc:00:00:02"


class _PonteQueAnota:
    """A ponte de mentira: guarda o que as largadas pediram, na ordem."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def haptica_testar(self, *a: Any) -> tuple[bool, dict[str, Any]]:
        self.chamadas.append(("haptica_testar", a))
        return True, {"status": "ok"}

    def rumble_stop(self, *a: Any) -> tuple[bool, dict[str, Any]]:
        self.chamadas.append(("rumble_stop", a))
        return True, {"status": "ok"}

    def rumble_passthrough(self, *a: Any) -> tuple[bool, dict[str, Any]]:
        self.chamadas.append(("rumble_passthrough", a))
        return True, {"status": "ok"}


class _View:
    def __init__(self, pagina: str) -> None:
        self._uri = onde.pagina(pagina, publicado=True).as_uri()

    def get_uri(self) -> str:
        return self._uri


class _Piloto:
    """Só o que o `_carregou` lê, com a instalação contada e não feita."""

    def __init__(self, de: str, para: str, *, pronto: bool = True) -> None:
        self.view = _View(para)
        self.pagina = de
        self.pronto = pronto
        self.visitadas: list[str] = [de]
        self.instalou = 0

    def _antes_de_instalar(self) -> None:
        self.instalou += 1

    def _a_mesma_recarregou(self, _nova: str) -> None:
        pass


@pytest.fixture(autouse=True)
def _mesa_limpa():
    """Nenhum teste herda a marca do anterior: eles rodam no MESMO processo."""
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()
    yield
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()


@pytest.fixture
def ponte(monkeypatch: pytest.MonkeyPatch) -> _PonteQueAnota:
    falsa = _PonteQueAnota()
    monkeypatch.setattr(hefesto_vivo, "ponte", falsa)
    return falsa


def _carregar(piloto: _Piloto) -> None:
    hefesto_vivo.Piloto._carregou(piloto, None, WebKit2.LoadEvent.FINISHED)


def test_o_clique_na_tira_cala_o_teste_da_haptica(ponte: _PonteQueAnota) -> None:
    a05._EM_TESTE_DA_HAPTICA[0] = UNIQ
    piloto = _Piloto("05-vibracao.html", "03-gatilhos.html")
    _carregar(piloto)
    assert ("haptica_testar", (UNIQ, False)) in ponte.chamadas, (
        "a página trocou pela tira e o teste da háptica seguiu ligado: o coração "
        "rebate na aba nova, e o controle vibra até ela voltar à Vibração")
    assert a05.em_teste_da_haptica() == ""
    assert piloto.instalou == 1 and piloto.pagina == "03-gatilhos.html"


def test_o_clique_na_tira_devolve_os_motores_do_teste_da_vibracao(
    ponte: _PonteQueAnota,
) -> None:
    a05._EM_TESTE[0] = UNIQ
    _carregar(_Piloto("05-vibracao.html", "02-controles.html"))
    nomes = [n for n, _ in ponte.chamadas]
    assert nomes == ["rumble_stop", "rumble_passthrough"], (
        f"a tira trocou a página e os motores ficaram com o teste: {nomes}")
    assert ponte.chamadas[1] == ("rumble_passthrough", (True,))
    assert a05.em_teste() == ""


def test_a_mesma_pagina_e_a_primeira_carga_nao_largam(ponte: _PonteQueAnota) -> None:
    a05._EM_TESTE_DA_HAPTICA[0] = UNIQ
    _carregar(_Piloto("05-vibracao.html", "05-vibracao.html", pronto=True))
    _carregar(_Piloto("05-vibracao.html", "05-vibracao.html", pronto=False))
    assert ponte.chamadas == []
    assert a05.em_teste_da_haptica() == UNIQ
