"""O clique na tira também larga o teste da aba Vibração."""
from __future__ import annotations

import argparse
import pathlib
import sys
import threading
import time
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


LENTIDAO_S = 0.1


class _PonteQueAnota:
    """A ponte de mentira: guarda o que as largadas pediram, na ordem, e demora como o IPC."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def haptica_testar(self, *a: Any) -> tuple[bool, dict[str, Any]]:
        time.sleep(LENTIDAO_S)
        self.chamadas.append(("haptica_testar", a))
        return True, {"status": "ok"}

    def rumble_stop(self, *a: Any) -> tuple[bool, dict[str, Any]]:
        time.sleep(LENTIDAO_S)
        self.chamadas.append(("rumble_stop", a))
        return True, {"status": "ok"}

    def rumble_passthrough(self, *a: Any) -> tuple[bool, dict[str, Any]]:
        time.sleep(LENTIDAO_S)
        self.chamadas.append(("rumble_passthrough", a))
        return True, {"status": "ok"}


class _View:
    def __init__(self, pagina: str) -> None:
        self._uri = onde.pagina(pagina, publicado=True).as_uri()

    def get_uri(self) -> str:
        return self._uri


class _Piloto:
    """Só o que o `_carregou` lê, com a instalação contada e não feita.

    O `args` é o do piloto oculto, o modo em que a régua roda: a aba à vista só se anota no
    runtime com a janela na tela, e a régua não escreve lá.
    """

    def __init__(self, de: str, para: str, *, pronto: bool = True) -> None:
        self.args = argparse.Namespace(oculta=True)
        self.view = _View(para)
        self.pagina = de
        self.pronto = pronto
        self.visitadas: list[str] = [de]
        self.instalou = 0
        self._mesa_de_agora: list[dict[str, Any]] = [{"uniq": UNIQ}]

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


_LARGADAS: list[threading.Thread | None] = []


@pytest.fixture
def ponte(monkeypatch: pytest.MonkeyPatch) -> _PonteQueAnota:
    falsa = _PonteQueAnota()
    monkeypatch.setattr(hefesto_vivo, "ponte", falsa)
    original = hefesto_vivo.pacotes.largar_o_que_as_abas_seguram

    def espia(*a: Any, **k: Any) -> threading.Thread | None:
        fio = original(*a, **k)
        _LARGADAS.append(fio)
        return fio

    monkeypatch.setattr(hefesto_vivo.pacotes, "largar_o_que_as_abas_seguram", espia)
    _LARGADAS.clear()
    return falsa


def _carregar(piloto: _Piloto) -> None:
    hefesto_vivo.Piloto._carregou(piloto, None, WebKit2.LoadEvent.FINISHED)
    for fio in _LARGADAS:
        if fio is not None:
            fio.join(5)


def test_o_clique_na_tira_cala_o_teste_da_haptica(ponte: _PonteQueAnota) -> None:
    a05._EM_TESTE_DA_HAPTICA.add(UNIQ)
    piloto = _Piloto("05-vibracao.html", "03-gatilhos.html")
    _carregar(piloto)
    assert ("haptica_testar", (UNIQ, False)) in ponte.chamadas, (
        "a página trocou pela tira e o teste da háptica seguiu ligado: o coração "
        "rebate na aba nova, e o controle vibra até ela voltar à Vibração")
    assert a05.em_teste_da_haptica() == frozenset()
    assert piloto.instalou == 1 and piloto.pagina == "03-gatilhos.html"


def test_o_clique_na_tira_devolve_os_motores_do_teste_da_vibracao(
    ponte: _PonteQueAnota,
) -> None:
    a05._EM_TESTE.add(UNIQ)
    _carregar(_Piloto("05-vibracao.html", "02-controles.html"))
    nomes = [n for n, _ in ponte.chamadas]
    assert nomes == ["rumble_stop", "rumble_passthrough"], (
        f"a tira trocou a página e os motores ficaram com o teste: {nomes}")
    assert ponte.chamadas[1] == ("rumble_passthrough", (True, UNIQ))
    assert a05.em_teste() == frozenset()


def test_a_mesma_pagina_e_a_primeira_carga_nao_largam(ponte: _PonteQueAnota) -> None:
    a05._EM_TESTE_DA_HAPTICA.add(UNIQ)
    _carregar(_Piloto("05-vibracao.html", "05-vibracao.html", pronto=True))
    _carregar(_Piloto("05-vibracao.html", "05-vibracao.html", pronto=False))
    assert ponte.chamadas == []
    assert a05.em_teste_da_haptica() == {UNIQ}
