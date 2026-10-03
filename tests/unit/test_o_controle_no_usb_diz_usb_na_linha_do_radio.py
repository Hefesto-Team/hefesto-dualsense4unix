"""O CONTROLE NO USB DIZ «USB» NA LINHA DO RÁDIO — A-GESTAO-DOS-CONTROLES-NO-PRODUTO-01."""

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


def _o_menu(lugar: str) -> str:
    return (f'data-gesto="aparelho-menu" data-alvo="{id_da_tela(ROXO)}" '
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
            assert _o_menu(lugar) in sala, (
                f"o «⋮» da linha no {lugar} sumiu com o controle no cabo")
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
            assert _o_menu(lugar) in sala
        assert sala.count("Desligado</span>") == 2, sala
        assert f">{a08.USB}</span>" not in sala
    finally:
        bancada.fechar()
