"""O-PACOTE-DE-TODA-ABA-SE-MONTA-FORA-DO-FIO-DO-GTK-01: o tique só pinta a carga pronta.

O `Piloto._tique` de verdade, num piloto sem WebView, com a chave do processo da janela
ligada e um pacote de mentira que dorme 2 s: o tique volta em menos de 100 ms, a carga
se monta no fio `hefesto-pacote` e pinta num tique seguinte. O gesto que chega enquanto a
carga se monta a descarta. Fora do processo da janela (as réguas e o `olhar.py`) o tique
monta na hora, como sempre.

Mordida: devolver a montagem ao tique (`_a_carga_na_hora` no lugar de
`_a_carga_montada_no_fundo` em `Piloto._tique`) faz o primeiro tique durar 2 s.
"""
from __future__ import annotations

import threading
import time
import types
from collections.abc import Iterator
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.interface import hefesto_vivo, mesa_viva
from hefesto_dualsense4unix.interface import pacotes as pac
from hefesto_dualsense4unix.interface.pacotes import fios

PAGINA = "01-jogar.html"
SONO_S = 2.0
TETO_DO_TIQUE_S = 0.1


class _PonteQueGuarda:
    """A ponte do piloto sem WebView: guarda a pintura e devolve a contagem."""

    def __init__(self) -> None:
        self.pinturas: list[str] = []

    def perguntar(self, js: str, volta: Any) -> None:
        self.pinturas.append(js)
        volta("1", None)

    def rodar(self, js: str) -> None:
        self.pinturas.append(js)


class _PacoteQueDorme:
    """O pacote de mentira: dorme, anota o fio e devolve a marca da vez."""

    def __init__(self) -> None:
        self.fios: list[str] = []
        self.vez = 0
        self.sono_s = SONO_S

    def __call__(self, pagina: str, ctx: Any) -> dict[str, Any]:
        self.vez += 1
        marca = f"v{self.vez}"
        self.fios.append(threading.current_thread().name)
        time.sleep(self.sono_s)
        return {"mesa": {"hef-marca": marca}}


@pytest.fixture
def na_janela() -> Iterator[None]:
    fios.ligar_a_janela()
    try:
        yield
    finally:
        fios.ligar_a_janela(False)


def _piloto(monkeypatch: pytest.MonkeyPatch, pacote: _PacoteQueDorme) -> Any:
    monkeypatch.setattr(pac, "bater_os_coracoes", lambda *_a, **_k: None)
    monkeypatch.setattr(pac, "pacote_da_pagina", pacote)
    st = {"connected": True, "controllers": []}

    def contexto(st: dict[str, Any]) -> tuple[Any, dict[str, str]]:
        mesa = mesa_viva.mesa_do_estado(st, {})
        return pac.Contexto(state=st, mesa=mesa, conectados=[], estados={}), {}

    piloto: Any = types.SimpleNamespace(
        pronto=True, _pintura_no_ar=False, _pular=0, _pulados_por_voo=0,
        _pulados_por_custo=0, pagina=PAGINA, ponte=_PonteQueGuarda(),
        args=types.SimpleNamespace(prova_de_mockup=False, conta_mutacoes=0),
        _estado_do_tique=lambda: st, _contexto=contexto,
        trocas={}, tiques={}, pinturas={}, voltas=0, custos=[], custo_do_ipc=[],
        _contar_mutacoes=lambda: None)
    for metodo in ("_o_que_mandar", "_esperando_o_estado_novo", "_moldes_da_pagina",
                   "_navegar"):
        setattr(piloto, metodo, types.MethodType(getattr(hefesto_vivo.Piloto, metodo), piloto))
    vars(piloto).update(
        _escondida=False, _geracao_na_volta=None, _pintada=None, _ate_a_inteira=0,
        _com_molduras=False, _moldes={},
        TIQUES_ENTRE_CARGAS_INTEIRAS=hefesto_vivo.Piloto.TIQUES_ENTRE_CARGAS_INTEIRAS)
    return piloto


def _tique(piloto: Any) -> float:
    t0 = time.perf_counter()
    assert hefesto_vivo.Piloto._tique(piloto) is True
    return time.perf_counter() - t0


def _esperar_a_montagem(piloto: Any, prazo_s: float = 10.0) -> None:
    fim = time.monotonic() + prazo_s
    montagem = getattr(piloto, "_montagem", None)
    while time.monotonic() < fim:
        if montagem is not None and not montagem.no_ar():
            return
        time.sleep(0.02)
        montagem = getattr(piloto, "_montagem", None)
    raise AssertionError("a montagem não voltou no prazo")


def _marcas(piloto: Any) -> list[str]:
    return [js for js in piloto.ponte.pinturas if "hef-marca" in js]


def test_o_tique_volta_na_hora_e_a_pintura_chega_depois(
        na_janela: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Com o pacote dormindo 2 s, o tique volta em menos de 100 ms e pinta depois."""
    pacote = _PacoteQueDorme()
    piloto = _piloto(monkeypatch, pacote)
    primeiro = _tique(piloto)
    assert primeiro < TETO_DO_TIQUE_S, (
        f"o tique esperou o pacote no fio do GTK: {primeiro * 1000:.0f} ms")
    assert not _marcas(piloto), "o tique pintou antes de a carga ficar pronta"
    _esperar_a_montagem(piloto)
    assert pacote.fios and threading.main_thread().name not in pacote.fios, pacote.fios
    assert set(pacote.fios) == {"hefesto-pacote"}, pacote.fios
    segundo = _tique(piloto)
    assert segundo < TETO_DO_TIQUE_S, f"o segundo tique esperou: {segundo * 1000:.0f} ms"
    pintadas = _marcas(piloto)
    assert len(pintadas) == 1 and "v1" in pintadas[0], pintadas
    assert piloto._carga_de_agora["mesa"]["hef-marca"] == "v1"
    _esperar_a_montagem(piloto)


def test_o_gesto_no_meio_descarta_a_carga_velha(
        na_janela: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A carga montada antes do gesto não pinta por cima do que o gesto mudou."""
    pacote = _PacoteQueDorme()
    pacote.sono_s = 0.3
    piloto = _piloto(monkeypatch, pacote)
    _tique(piloto)
    hefesto_vivo._esquecer_a_pintura(piloto)
    _esperar_a_montagem(piloto)
    _tique(piloto)
    assert not _marcas(piloto), "a carga de antes do gesto pintou por cima dele"
    _esperar_a_montagem(piloto)
    _tique(piloto)
    pintadas = _marcas(piloto)
    assert len(pintadas) == 1 and "v2" in pintadas[0], pintadas


def test_a_carga_da_aba_que_saiu_nao_pinta_a_que_entrou(
        na_janela: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Trocar de aba com a montagem no ar descarta a carga da aba que saiu."""
    pacote = _PacoteQueDorme()
    pacote.sono_s = 0.3
    piloto = _piloto(monkeypatch, pacote)
    _tique(piloto)
    piloto.pagina = "02-controles.html"
    _esperar_a_montagem(piloto)
    _tique(piloto)
    assert not _marcas(piloto), "a carga da 01 pintou a 02"
    _esperar_a_montagem(piloto)


def test_fora_da_janela_o_tique_monta_na_hora(monkeypatch: pytest.MonkeyPatch) -> None:
    """As réguas e o `olhar.py` (sem a chave da janela) seguem pintando no mesmo tique."""
    pacote = _PacoteQueDorme()
    pacote.sono_s = 0.0
    piloto = _piloto(monkeypatch, pacote)
    _tique(piloto)
    assert pacote.fios == [threading.current_thread().name]
    assert len(_marcas(piloto)) == 1
