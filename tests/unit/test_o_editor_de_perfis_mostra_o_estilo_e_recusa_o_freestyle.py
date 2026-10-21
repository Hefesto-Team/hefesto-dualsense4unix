"""O editor de Perfis mostra o estilo do perfil aberto, recusa o Freestyle e renomeia pela linha.

O-EDITOR-DE-PERFIS-MOSTRA-O-ESTILO-RECUSA-O-FREESTYLE-E-PERDE-O-QUE-O-DESENHO-TIROU-01, com o
desenho escolhido em 19/10/2026: o ponto laranja com a frase na dica (Freestyle, A) e o duplo
clique na célula do nome renomeia (sem campo Nome no editor).

MORDIDAS:
  * devolva `editor.estilo` a `a10_perfis.NAO_PINTAVEIS`: o estilo do Pragmata some do pacote;
  * tire o `e_o_freestyle` do `editor_jogo`: «Freestyle» grava no perfil;
  * troque o `hefPerfil` do `perfis_renomear` pelo perfil do editor: a linha errada muda de nome.
"""
from __future__ import annotations

from typing import Any

import pytest


from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import estilos_de_jogo, loader
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

PRAGMATA = "Pragmata"
ELDEN = "Elden Ring"


class PonteDeMentira:
    """O daemon calado que confirma: nada do aparelho entra na régua."""

    def profile_switch(self, nome: str) -> bool:
        return True

    def profile_reaplicar(self, nome: str, *, prender: bool = False) -> bool:
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return {}


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome, valor in (("_ESCOLHIDO", ""), ("_ARMADO", None), ("_PROCURA", ""),
                        ("_PINTADO_PARA", ""), ("_ULTIMO_TIQUE", 0.0),
                        ("_RECUSA_DO_JOGO", ("", ""))):
        monkeypatch.setattr(a10_perfis, nome, valor, raising=False)


def _adulto() -> Any:
    return estilos_de_jogo.POR_CHAVE["adulto"]


def _o_disco() -> None:
    """O Pragmata com o estilo Adulto e o Elden Ring sem estilo."""
    loader.save_profile(Profile(name=PRAGMATA, match=MatchCriteria(window_class=["pragmata"]),
                                estilo=_adulto().chave), origem="régua")
    loader.save_profile(Profile(name=ELDEN, match=MatchCriteria(window_class=["eldenring"])),
                        origem="régua")


def _ctx() -> Contexto:
    return Contexto(state={"active_profile": PRAGMATA}, mesa=[], conectados=[], estados={})


def _abrir(nome: str) -> dict[str, Any]:
    a10_perfis.selecionar(_ctx(), {"hefPerfil": nome}, PonteDeMentira())
    return a10_perfis.pacote(_ctx())


def _pintado(pacote: dict[str, Any], chave: str) -> Any:
    return (pacote.get("mesa") or pacote).get(chave)


def test_cada_perfil_mostra_o_proprio_estilo() -> None:
    """Pragmata diz Adulto; Elden Ring volta ao travessão; Pragmata de novo repinta Adulto."""
    _o_disco()
    assert _pintado(_abrir(PRAGMATA), "editor.estilo") == _adulto().rotulo
    assert _pintado(_abrir(ELDEN), "editor.estilo") in (None, "", "—"), (
        "o Elden Ring não tem estilo e a tela afirmou um")
    assert _pintado(_abrir(PRAGMATA), "editor.estilo") == _adulto().rotulo


def test_o_tique_sobre_o_mesmo_perfil_nao_repinta_o_estilo() -> None:
    """Pintar a cada tique apagaria a escolha feita agora (e o select reaplicaria a receita)."""
    _o_disco()
    _abrir(PRAGMATA)
    assert "editor.estilo" not in (a10_perfis.pacote(_ctx()).get("mesa") or {})


@pytest.mark.parametrize("digitado", ["Freestyle", "freestyle ", "FREESTYLE"])
def test_o_nome_do_jogo_recusa_o_freestyle(digitado: str) -> None:
    """O nome do botão não grava, e o ponto laranja acende com a frase na dica, até o tique."""
    _o_disco()
    _abrir(ELDEN)
    antes = loader.load_profile(ELDEN).model_dump()
    fora = a10_perfis.editor_jogo(_ctx(), {"valor": digitado, "evento": "change"},
                                  PonteDeMentira())
    assert loader.load_profile(ELDEN).model_dump() == antes, f"«{digitado}» gravou no perfil"
    assert _pintado(fora, "editor.jogo.exige") == "sim"
    assert _pintado(fora, "editor.jogo.exigencia") == a10_perfis.FRASE_DO_FREESTYLE
    tique = a10_perfis.pacote(_ctx())
    assert _pintado(tique, "editor.jogo.exige") == "sim", "o tique apagou o ponto laranja"
    assert _pintado(_abrir(PRAGMATA), "editor.jogo.exige") != "sim", (
        "a recusa do Elden Ring acendeu no Pragmata")


def test_um_jogo_comum_grava_e_apaga_a_recusa() -> None:
    _o_disco()
    _abrir(ELDEN)
    a10_perfis.editor_jogo(_ctx(), {"valor": "Freestyle", "evento": "change"}, PonteDeMentira())
    a10_perfis.editor_jogo(_ctx(), {"valor": "eldenring.exe", "evento": "change"},
                           PonteDeMentira())
    assert "eldenring.exe" in loader.load_profile(ELDEN).model_dump_json()
    assert a10_perfis._RECUSA_DO_JOGO == ("", "")


def test_o_duplo_clique_renomeia_a_linha_e_nao_o_editor() -> None:
    """O campo nasce na célula do nome: o perfil é o da linha, mesmo com outro no editor."""
    _o_disco()
    _abrir(PRAGMATA)
    a10_perfis.perfis_renomear(_ctx(), {"hefPerfil": ELDEN, "valor": "Elden Ring NG+",
                                        "evento": "change"}, PonteDeMentira())
    nomes = {p.name for p in loader.load_all_profiles()}
    assert "Elden Ring NG+" in nomes and ELDEN not in nomes
    assert PRAGMATA in nomes, "o perfil do editor mudou de nome"
    assert a10_perfis._ESCOLHIDO in ("", PRAGMATA), "o editor pulou para a linha renomeada"


@pytest.mark.parametrize("novo", ["Freestyle", " freestyle"])
def test_o_renomear_recusa_o_freestyle(novo: str) -> None:
    _o_disco()
    with pytest.raises(RuntimeError, match="Freestyle"):
        a10_perfis.perfis_renomear(_ctx(), {"hefPerfil": ELDEN, "valor": novo,
                                            "evento": "change"}, PonteDeMentira())
    assert ELDEN in {p.name for p in loader.load_all_profiles()}


def test_o_clique_no_campo_do_renomear_nao_grava() -> None:
    """O clique que põe o cursor no campo chega como gesto; só o `change` grava."""
    _o_disco()
    assert a10_perfis.perfis_renomear(_ctx(), {"hefPerfil": ELDEN, "valor": "X",
                                               "evento": "click"}, PonteDeMentira()) is None
    assert ELDEN in {p.name for p in loader.load_all_profiles()}


def test_a_pagina_renomeia_pelo_duplo_clique_no_nome() -> None:
    """O roteiro da página abre o campo na célula do nome com o gesto e o perfil da linha."""
    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("10-perfis.html").read_text(encoding="utf-8")
    assert 'closest(\'td[data-hef="perfis.linha.nome"]\')' in html
    assert "campo.dataset.hefGesto = 'perfis.renomear'" in html
    assert "campo.dataset.hefPerfil = era" in html
    assert 'data-hef-gesto="editor.nome"' not in html
