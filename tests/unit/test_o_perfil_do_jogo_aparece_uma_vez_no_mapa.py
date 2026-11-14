"""O perfil do jogo aparece uma vez no seletor do Mapa, e as âncoras apontam o lugar dele.

O-PERFIL-DO-JOGO-APARECE-UMA-VEZ-NO-MAPA-01 (14/11/2026): com o jogo ativo, o nome dele saía no topo
(a chave `nav`, o perfil que vale) e de novo em «Meus perfis», e o `#trocar` escolhia a segunda.

MORDIDA: tirar o filtro de «Meus perfis» (`_chave_no_seletor` no `_opcoes_do_perfil`) reprova o caso
do jogo; devolver o `_chave_das_trocas` a `PERFIL + nome` reprova o caso da âncora.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o pacote do mapa do controle carrega o GTK")

import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a06_navegacao as a06
from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13
from hefesto_dualsense4unix.profiles import loader

JOGO = "Thicc Magic"
OUTRO = "Corrida"
FREESTYLE = loader.NOME_DO_PADRAO
MESAS = {
    "p1-cabo": [("p1", "USB")],
    "p1-radio": [("p1", "BT")],
    "p1-a-p4-mista": [("p1", "USB"), ("p2", "BT"), ("p3", "USB"), ("p4", "BT")],
}


def _ctx(ativo: str, mesa: list[tuple[str, str]]) -> Contexto:
    linhas = [{"pref": pref, "uniq": f"aa:bb:cc:00:00:0{n}", "nome": "Cosmic Red", "via": via,
               "jogador": n, "cor": "cosmic-red"} for n, (pref, via) in enumerate(mesa, 1)]
    return Contexto(state={"active_profile": ativo}, mesa=linhas,
                    conectados=[{"uniq": x["uniq"], "inputs": {"buttons": ["cross"]}}
                                for x in linhas])


@pytest.fixture(autouse=True)
def _disco(monkeypatch: pytest.MonkeyPatch) -> None:
    perfis: dict[str, dict[str, Any]] = {
        nome: {"name": nome, "remapeamento": {"triangle": "cross"}}
        for nome in (JOGO, OUTRO, FREESTYLE)}
    monkeypatch.setattr(a13.perfil, "lista", lambda: [{"nome": n} for n in perfis])
    monkeypatch.setattr(a13.perfil, "ativo", lambda nome=None: dict(perfis.get(str(nome), {})))
    monkeypatch.setattr(a06, "_o_point_and_click_de_hoje", lambda: f"perfil:{JOGO}")
    a13._largar()


def _opcoes(ctx: Contexto) -> list[tuple[str, str]]:
    return re.findall(r'<option value="([^"]*)">([^<]*)</option>', a13._opcoes_do_perfil(ctx))


@pytest.mark.parametrize("mesa", MESAS, ids=list(MESAS))
def test_com_o_jogo_ativo_o_nome_dele_aparece_uma_vez(mesa: str) -> None:
    ctx = _ctx(JOGO, MESAS[mesa])
    opcoes = _opcoes(ctx)
    assert [t for _v, t in opcoes].count(JOGO) == 1, opcoes
    assert opcoes[0] == (a13.NAV, JOGO), "o perfil do jogo mora no topo"
    assert (f"perfil:{OUTRO}", OUTRO) in opcoes, "os outros perfis seguem em «Meus perfis»"


@pytest.mark.parametrize("mesa", MESAS, ids=list(MESAS))
def test_as_ancoras_apontam_uma_opcao_que_existe_no_seletor(mesa: str) -> None:
    for ativo in (JOGO, OUTRO, FREESTYLE):
        ctx = _ctx(ativo, MESAS[mesa])
        valores = {v for v, _t in _opcoes(ctx)}
        mesa_da_edicao = a13._mesa_da_edicao(ctx)
        for campo in ("ancora-trocar", "ancora-pac"):
            assert mesa_da_edicao[campo] in valores, (ativo, campo, mesa_da_edicao[campo], valores)


def test_o_trocar_abre_o_perfil_do_jogo_com_as_trocas_dele() -> None:
    ctx = _ctx(JOGO, MESAS["p1-a-p4-mista"])
    chave = a13._mesa_da_edicao(ctx)["ancora-trocar"]
    assert chave == a13.NAV
    a13.mapa_perfil(ctx, {"valor": chave}, None)
    aberto = a13._mesa_da_edicao(ctx)
    assert (aberto["nome"], aberto["mc-tipo"]) == (JOGO, "troca"), aberto


def test_o_gesto_com_a_chave_do_disco_do_jogo_cai_no_topo() -> None:
    ctx = _ctx(JOGO, MESAS["p1-cabo"])
    a13.mapa_perfil(ctx, {"valor": f"perfil:{JOGO}"}, None)
    assert a13._mesa_da_edicao(ctx)["perfil"] == a13.NAV


def test_fora_do_jogo_o_freestyle_com_botao_proprio_segue_em_meus_perfis() -> None:
    ctx = _ctx(FREESTYLE, MESAS["p1-radio"])
    opcoes = _opcoes(ctx)
    assert opcoes[0][0] == a13.NAV and opcoes[0][1] != FREESTYLE, opcoes
    assert (f"perfil:{FREESTYLE}", FREESTYLE) in opcoes
    assert a13._mesa_da_edicao(ctx)["ancora-trocar"] == f"perfil:{FREESTYLE}"
