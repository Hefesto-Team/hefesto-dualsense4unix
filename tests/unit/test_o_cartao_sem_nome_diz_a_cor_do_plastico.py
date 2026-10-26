#!/usr/bin/env python3
"""O cartão do controle sem nome diz a cor do plástico, nunca o número repetido.

A régua é a D-2610-O-CONTROLE-SEM-NOME-SE-CHAMA-PELA-COR: na 08, que já mostra o «P N» ao lado,
o campo do dono de um controle sem nome diz a cor que a mesa leu («P1 · Cosmic Red»); sem cor
conhecida, o modelo. De P1 a P4, no cabo e no rádio. A 02 e a Calibrar, que já dizem a cor na
mesma linha, continuam com o «P N» no lugar do nome.
"""
from __future__ import annotations

import itertools
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _pasta in ("src", "src/hefesto_dualsense4unix/interface"):
    if str(RAIZ / _pasta) not in sys.path:
        sys.path.insert(0, str(RAIZ / _pasta))

from hefesto_dualsense4unix.integrations.cor_do_plastico import MODELO_GENERICO, cor_do_nome
from hefesto_dualsense4unix.interface import mesa_viva, monta
from hefesto_dualsense4unix.interface.pacotes import Contexto, a08_conexoes, nome_do_jogador

UNIQS = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]
CORES = {UNIQS[0]: "Cosmic Red", UNIQS[1]: "Starlight Blue", UNIQS[2]: "Galactic Purple"}
TRANSPORTES = [*sorted(set(itertools.permutations(("usb", "bt", "usb", "bt"))))[:3],
               ("usb",) * 4, ("bt",) * 4]


def _estado(transportes: tuple[str, ...]) -> dict[str, Any]:
    return {"controllers": [
        {"uniq": u, "connected": True, "player": n, "player_slot": n, "transport": t,
         "battery_pct": 80, "is_primary": n == 1, "inputs": {}}
        for n, (u, t) in enumerate(zip(UNIQS, transportes, strict=True), start=1)]}


def _colunas(transportes: tuple[str, ...], nomes: dict[str, str],
             monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(nome_do_jogador, "nomes_dos_donos", lambda: nomes)
    estado = _estado(transportes)
    cores = {u: cor_do_nome(nome) for u, nome in CORES.items()}
    mesa = mesa_viva.mesa_do_estado(estado, cores, declaracao=object())
    ctx = Contexto(state=estado, mesa=mesa, conectados=estado["controllers"], estados={})
    return dict(a08_conexoes.pacote(ctx)["colunas"])


@pytest.mark.parametrize("transportes", TRANSPORTES, ids="-".join)
def test_sem_nome_a_08_diz_a_cor_e_sem_cor_o_modelo(
        transportes: tuple[str, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    colunas = _colunas(transportes, {}, monkeypatch)
    for n, uniq in enumerate(UNIQS, start=1):
        dono = colunas[uniq]["dono"]
        assert dono == CORES.get(uniq, MODELO_GENERICO), (n, transportes[n - 1], dono)
        assert dono != f"P{n}", f"P{n} no {transportes[n - 1]}: o número repetido no lugar do nome"


def test_com_nome_o_nome_vence_a_cor(monkeypatch: pytest.MonkeyPatch) -> None:
    colunas = _colunas(("usb", "bt", "usb", "bt"),
                       {nome_do_jogador.mac(UNIQS[1]): "Vitória"}, monkeypatch)
    assert colunas[UNIQS[1]]["dono"] == "Vitória"
    assert colunas[UNIQS[0]]["dono"] == "Cosmic Red"


@pytest.mark.parametrize("plastico, esperado", [
    ("Cosmic Red", "Cosmic Red"), ("White", "White"), ("", MODELO_GENERICO),
    (mesa_viva.COR_DESCONHECIDA, MODELO_GENERICO), ("  ", MODELO_GENERICO)])
def test_o_dono_sem_nome_e_a_cor_ou_o_modelo(plastico: str, esperado: str) -> None:
    for n in range(1, 5):
        assert monta.dono_na_linha({}, UNIQS[n - 1], n, plastico=plastico) == esperado
        assert monta.dono_na_linha({}, UNIQS[n - 1], n, plastico=plastico, em_html=True) == esperado


def test_a_cor_sai_escapada_no_html() -> None:
    assert monta.dono_na_linha({}, UNIQS[0], 1, plastico="<b>", em_html=True) == "&lt;b&gt;"


def test_a_linha_que_ja_diz_a_cor_segue_com_o_numero() -> None:
    assert monta.dono_na_linha({}, UNIQS[0], 2) == "P2"
    assert monta.quem_joga_com_o_numero({}, UNIQS[0], 3).endswith("3</span>")


@pytest.mark.parametrize("digitado, gravado", [
    ("Cosmic Red", ""), ("DualSense", "DualSense"), ("P1", ""), ("Ana", "Ana")])
def test_a_cor_no_campo_do_dono_nao_vira_nome_gravado(
        digitado: str, gravado: str, monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[tuple[str, str]] = []

    class _Escrita:
        feita = True

    def _alias(endereco: str, nome: str) -> _Escrita:
        chamadas.append((endereco, nome))
        return _Escrita()

    monkeypatch.setattr(a08_conexoes, "_alias_do_aparelho", _alias)
    monkeypatch.setattr(nome_do_jogador, "nomes_dos_donos",
                        lambda: {nome_do_jogador.mac(UNIQS[0]): "Antigo"})
    estado = _estado(("usb", "bt", "usb", "bt"))
    mesa = mesa_viva.mesa_do_estado(estado, {UNIQS[0]: cor_do_nome("Cosmic Red")},
                                    declaracao=object())
    ctx = Contexto(state=estado, mesa=mesa, conectados=estado["controllers"], estados={})
    a08_conexoes.dono_renomear(ctx, {"uniq": UNIQS[0], "valor": digitado}, None)
    assert chamadas == [(UNIQS[0].upper(), gravado)]
