"""O CONTROLE NO USB DIZ «USB» NA LINHA DO RÁDIO — A-GESTAO-DOS-CONTROLES-NO-PRODUTO-01.

O item novo da sprint (26/09/2026): a linha de um controle que tem chave BT
num adaptador e está no USB agora diz «USB», não «Desligado» — as palavras do
transporte da tela são USB e BT (decisão dela de 21/09). O X continua: a chave
BT daquele adaptador existe, e esquecê-la é dela.

A conferência achou o item entregue sem régua. Esta é a régua, com o rádio de
mentira de três adaptadores e o roxo com chave em dois deles:

* com o roxo no cabo, as DUAS linhas dele dizem «USB», com o X de cada
  adaptador, e nenhuma diz «Desligado» — em qualquer grafia do ``uniq`` que o
  daemon publique;
* com o roxo em lugar nenhum, as duas voltam a dizer «Desligado»;
* um OUTRO controle no cabo não muda a linha do roxo.

MORDIDA: tire o ``no_usb`` da chamada de ``_os_desligados`` em
``cena_do_radio`` — as linhas voltam a dizer «Desligado» com o roxo no cabo, e
a primeira régua reprova.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, ROXO, SALA, VARANDA
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    Bancada,
    id_da_tela,
    preparar_a_tela,
    preparar_o_diario,
)
from tests.unit.test_o_pareamento_que_nao_chega_devolve_os_botoes import (
    _linhas,
    _mesa_das_chaves,
)


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    return preparar_a_tela(monkeypatch)


def _com_no_cabo(bancada: Bancada, monkeypatch: pytest.MonkeyPatch, uniq: str) -> None:
    """O ``state_full`` com mais um controle no USB — como o daemon o publica."""
    real = bancada.estado

    def estado() -> dict[str, Any]:
        st = real()
        st["controllers"] = [*st["controllers"],
                             {"uniq": uniq, "transport": "usb", "connected": True}]
        return st

    monkeypatch.setattr(bancada, "estado", estado)


def _o_x(lugar: str) -> str:
    return (f'data-gesto="esquecer-aparelho" data-alvo="{id_da_tela(ROXO)}" '
            f'data-lugar="{id_da_tela(lugar)}"')


@pytest.mark.parametrize("grafia", [ROXO, ROXO.upper(), rm.uniq(ROXO)],
                         ids=["com-dois-pontos", "maiusculas", "so-hex"])
def test_o_controle_no_cabo_diz_usb_nas_linhas_de_cada_adaptador(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, grafia: str,
) -> None:
    mundo, relogio = _mesa_das_chaves(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    _com_no_cabo(bancada, monkeypatch, grafia)
    try:
        sala = bancada.tique()["radio-sala"]
        cena = dict(a08._CENA_NA_TELA)
        for lugar in (VARANDA, SALA):
            (linha,) = _linhas(cena, lugar, desligado=True)
            assert linha["usb"] is True, (lugar, linha)
            assert _o_x(lugar) in sala, f"o X da linha no {lugar} sumiu com o controle no cabo"
        assert not _linhas(cena, QUARTO, desligado=True)
        assert sala.count(f">{a08.USB}</span>") == 2, sala
        assert "Desligado</span>" not in sala, "o controle no cabo foi dito «Desligado»"
    finally:
        bancada.fechar()


def test_fora_do_cabo_a_linha_volta_a_dizer_desligado(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outro controle no cabo (o azul, sem chave nestes adaptadores) não muda o roxo."""
    mundo, relogio = _mesa_das_chaves(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    _com_no_cabo(bancada, monkeypatch, AZUL)
    try:
        sala = bancada.tique()["radio-sala"]
        cena = dict(a08._CENA_NA_TELA)
        for lugar in (VARANDA, SALA):
            (linha,) = _linhas(cena, lugar, desligado=True)
            assert linha["usb"] is False, (lugar, linha)
            assert _o_x(lugar) in sala
        assert sala.count("Desligado</span>") == 2, sala
        assert f">{a08.USB}</span>" not in sala
    finally:
        bancada.fechar()
