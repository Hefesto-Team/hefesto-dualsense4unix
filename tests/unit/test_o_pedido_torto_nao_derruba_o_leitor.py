"""O pedido torto da extensão recebe uma recusa e o leitor, pai do jogo, segue atendendo.

O valor da varredura se confere contra o tipo e a faixa do ``buildid`` contra a forma, na
entrada; o que ainda escapar do pedido vira recusa com uma linha no diário.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import leitor_do_estado as leitor
from tests.unit.test_a_porta_le_o_estado_que_a_receita_declara import (  # noqa: F401
    VALOR,
    filho,
)

JOGO = "steam_app_1"


def _servico(pid: int, pasta: Path) -> leitor.ServicoDoLeitor:
    chaves = leitor.ChavesDaMemoria(pasta / "chaves.json")
    chaves.gravar(JOGO, True)
    return leitor.ServicoDoLeitor(pid, JOGO, chaves, buildid="100")


def _ler(endereco: float, faixa: Any = None) -> dict[str, Any]:
    pedido: dict[str, Any] = {"verbo": "ler", "entradas": [
        {"nome": "vida", "cadeia_de_ponteiros": [endereco], "tipo": "i32", "hz": 30}]}
    if faixa is not None:
        pedido["faixa"] = faixa
    return pedido


@pytest.mark.parametrize(("pedido", "frase"), [
    ({"verbo": "varrer", "tipo": "i32", "valor": 1.5}, "não cabe no tipo «i32»"),
    ({"verbo": "varrer", "tipo": "u8", "valor": 300}, "não cabe no tipo «u8»"),
    ({"verbo": "varrer", "tipo": "u8", "valor": "3"}, "não é um número"),
])
def test_o_valor_fora_do_tipo_recusa_e_o_pedido_seguinte_e_atendido(
        filho, tmp_path, pedido, frase) -> None:  # noqa: F811
    """D-1911-O-PEDIDO-TORTO-VIRA-RECUSA: valor fora do tipo recusa; o próximo se atende."""
    proc, valor, _ = filho
    servico = _servico(proc.pid, tmp_path)
    assert frase in servico.atender(pedido)["recusa"]
    assert servico.atender(_ler(valor))["valores"]["vida"] == VALOR


def test_a_faixa_que_nao_e_numero_recusa_e_o_pedido_seguinte_e_atendido(
        filho, tmp_path) -> None:  # noqa: F811
    proc, valor, _ = filho
    servico = _servico(proc.pid, tmp_path)
    assert "faixa de versões" in servico.atender(_ler(valor, {"min": "abc"}))["recusa"]
    assert servico.atender(_ler(valor, {"min": 50}))["valores"]["vida"] == VALOR


def test_o_refino_fora_do_tipo_recusa_e_a_varredura_segue(
        filho, tmp_path) -> None:  # noqa: F811
    proc, _, _ = filho
    servico = _servico(proc.pid, tmp_path)
    token = servico.atender({"verbo": "varrer", "tipo": "i32", "valor": VALOR})["token"]
    refino = {"verbo": "refinar", "token": token, "comparacao": "igual", "valor": 1.5}
    assert "não cabe no tipo «i32»" in servico.atender(refino)["recusa"]
    assert servico.atender({**refino, "valor": VALOR})["contagem"] >= 1


def test_a_cadeia_infinita_recusa_e_o_pedido_seguinte_e_atendido(
        filho, tmp_path) -> None:  # noqa: F811
    proc, valor, _ = filho
    servico = _servico(proc.pid, tmp_path)
    assert "linha da receita" in servico.atender(_ler(float("inf")))["recusa"]
    assert servico.atender(_ler(valor))["valores"]["vida"] == VALOR


def test_o_fracionario_cabe_so_nos_tipos_de_ponto_flutuante() -> None:
    assert leitor.valor_do_tipo("f32", 1.5) == 1.5
    assert leitor.valor_do_tipo("i8", -128) == -128
    for tipo, valor in (("i8", 128), ("u64", -1), ("f32", 1e300), ("i32", True)):
        with pytest.raises(leitor.LeituraRecusadaError):
            leitor.valor_do_tipo(tipo, valor)


def test_o_erro_que_escapa_do_pedido_vira_recusa_com_linha_no_diario(
        filho, tmp_path, monkeypatch, caplog) -> None:  # noqa: F811
    proc, valor, _ = filho
    servico = _servico(proc.pid, tmp_path)
    original = leitor.processo_do_jogo
    monkeypatch.setattr(leitor, "processo_do_jogo", lambda *a: 1 / 0)
    with caplog.at_level(logging.WARNING, logger=leitor.logger.name):
        assert "recusa" in servico.atender({"verbo": "varrer", "tipo": "i32", "valor": 7})
    assert [r.exc_info[0] for r in caplog.records if r.exc_info] == [ZeroDivisionError]
    monkeypatch.setattr(leitor, "processo_do_jogo", original)
    assert servico.atender(_ler(valor))["valores"]["vida"] == VALOR
