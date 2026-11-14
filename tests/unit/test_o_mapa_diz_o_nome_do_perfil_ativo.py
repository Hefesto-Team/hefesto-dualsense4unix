"""O Mapa diz o nome e o modo do perfil que o daemon diz ativo, para qualquer controle da fila.

A chave `nav` do seletor é o perfil que vale agora. Com um perfil de jogo ativo, o seletor e o
campo do nome dizem o nome dele, e a etiqueta diz o modo dele (o estilo de clicar é «Point and
click», a troca de botão é «Trocar os botões»); fora do jogo (nenhum perfil, ou o Freestyle), a
Navegação. O perfil ativo é um para todos os controles: o nome não muda com o chip escolhido no
«Vale para», com o cabo ou o rádio, nem com a posição do jogador.

MORDIDAS: devolver o nome fixo «Navegar no computador» ao campo ou ao seletor reprova o nome do
jogo; devolver o `nav` fixo à etiqueta reprova o modo do jogo.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o pacote do mapa do controle carrega o GTK")

import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import Contexto, pacote_da_pagina, perfil
from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13

CLICAR = "Thicc Magic"
TROCAR = "Luta de Rua"
DISCO: dict[str, dict[str, Any]] = {
    CLICAR: {"name": CLICAR, "estilo": "point_and_click"},
    TROCAR: {"name": TROCAR, "remapeamento": {"cross": "circle"}},
    "freestyle": {"name": "freestyle"},
}

CORES = ("cosmic-red", "white", "starlight-blue", "galactic-purple")
MESAS = {
    "4 cabos": ("USB", "USB", "USB", "USB"),
    "3 cabos e 1 rádio": ("USB", "BT", "USB", "USB"),
    "2 e 2": ("BT", "USB", "USB", "BT"),
    "1 cabo e 3 rádios": ("BT", "BT", "USB", "BT"),
    "4 rádios": ("BT", "BT", "BT", "BT"),
    "1 rádio só": ("BT",),
}


def _mesa_de(vias: tuple[str, ...]) -> list[dict[str, Any]]:
    return [{"pref": f"p{i}", "uniq": f"aa:bb:cc:00:00:0{i}", "nome": CORES[i - 1].title(),
             "via": via, "jogador": i, "cor": CORES[i - 1]}
            for i, via in enumerate(vias, start=1)]


def _ctx(ativo: str | None, vias: tuple[str, ...], escolhido: str = "") -> Contexto:
    mesa = _mesa_de(vias)
    return Contexto(state={"active_profile": ativo}, mesa=mesa, escolhido=escolhido,
                    conectados=[{"uniq": m["uniq"], "inputs": {"buttons": []}} for m in mesa])


@pytest.fixture(autouse=True)
def _disco(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Os perfis do disco, sem tocar o disco do usuário; a edição limpa antes e depois."""
    monkeypatch.setattr(perfil, "lista", lambda: [{"nome": n} for n in DISCO])
    monkeypatch.setattr(perfil, "ativo", lambda nome=None: dict(DISCO.get(str(nome), {})))
    a13._largar()
    yield
    a13._largar()


def _tela(ctx: Contexto) -> tuple[dict[str, Any], str]:
    pacote = pacote_da_pagina(a13.PAGINA, ctx) or {}
    opcoes = pacote["blocos"][a13.BLOCO_DO_PERFIL]
    achado = re.search(rf'<option value="{a13.NAV}">([^<]*)</option>', opcoes)
    assert achado, opcoes
    return pacote["mesa"], achado.group(1)


def _escolhas(vias: tuple[str, ...]) -> list[str]:
    return [""] + [f"p{i}" for i in range(1, len(vias) + 1)]


@pytest.mark.parametrize("mesa", MESAS, ids=list(MESAS))
@pytest.mark.parametrize(("ativo", "tipo", "etiqueta"), [
    (CLICAR, "pac", "Point and click"),
    (TROCAR, "troca", "Trocar os botões"),
])
def test_com_o_perfil_do_jogo_ativo_o_mapa_diz_o_nome_e_o_modo_dele(
        mesa: str, ativo: str, tipo: str, etiqueta: str) -> None:
    vias = MESAS[mesa]
    for escolhido in _escolhas(vias):
        a13._largar()
        tela, opcao = _tela(_ctx(ativo, vias, escolhido))
        assert tela["perfil"] == a13.NAV
        assert tela["nome"] == ativo, (escolhido, tela["nome"])
        assert opcao == ativo, (escolhido, opcao)
        assert (tela["mc-tipo"], tela["etiqueta"]) == (tipo, etiqueta), escolhido
        assert a13.NOME_DA_NAVEGACAO not in (tela["nome"], opcao)


@pytest.mark.parametrize("mesa", MESAS, ids=list(MESAS))
def test_fora_do_jogo_o_mapa_diz_a_navegacao(mesa: str) -> None:
    vias = MESAS[mesa]
    for escolhido in _escolhas(vias):
        a13._largar()
        tela, opcao = _tela(_ctx("freestyle", vias, escolhido))
        assert (tela["nome"], opcao) == (a13.NOME_DA_NAVEGACAO, a13.NOME_DA_NAVEGACAO)
        assert (tela["mc-tipo"], tela["etiqueta"]) == ("nav", "Navegação")
        assert a13.FORA_DO_JOGO in tela["usar-em"]


def test_o_jogo_que_sai_devolve_a_navegacao_e_o_que_entra_devolve_o_nome() -> None:
    vias = MESAS["2 e 2"]
    ordem = [(CLICAR, CLICAR), ("freestyle", a13.NOME_DA_NAVEGACAO), (TROCAR, TROCAR),
             (CLICAR, CLICAR)]
    for ativo, esperado in ordem:
        tela, opcao = _tela(_ctx(ativo, vias, "p2"))
        assert (tela["nome"], opcao) == (esperado, esperado), ativo


def test_o_nome_do_jogo_vai_escapado_ao_seletor() -> None:
    DISCO["A & B <x>"] = {"name": "A & B <x>", "remapeamento": {"cross": "circle"}}
    try:
        _, opcao = _tela(_ctx("A & B <x>", MESAS["4 cabos"]))
        assert opcao == "A &amp; B &lt;x&gt;"
    finally:
        DISCO.pop("A & B <x>")
