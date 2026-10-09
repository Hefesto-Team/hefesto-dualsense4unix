"""A chave «Também no jogo» e a Função do teclado «Só dentro do jogo» na aba 06.

O-GATILHO-VIRA-CLIQUE-SEM-LIGAR-O-CURSOR-01 (opção b) e
O-TECLADO-SO-DENTRO-DO-JOGO-TEM-DONO-01 (opção a): o desenho aprovado é o que o
gerador publica, e o pacote pinta pelos MESMOS endereços.

Os leitores são o HTML do desenho (`mockup/`, sem `--publicar`, que é da costura)
e o `mesa` que o pacote devolve — nunca as constantes que a cura usa.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo


def _desenho() -> str:
    import onde

    return onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")


def _topo_das_definicoes() -> str:
    doc = _desenho()
    ini = doc.index('id="definicoes-mouse"')
    topo = doc.index('<div class="tn-topo">', ini)
    return doc[topo:doc.index('<div class="tn-corpo">', topo)]


def test_a_chave_mora_no_topo_das_definicoes_entre_o_ajuda_e_o_x():
    """Dentro do `.tn-topo`, depois do título e do `?` e antes do botão de fechar."""
    topo = _topo_das_definicoes()
    assert topo.index("tn-tit") < topo.index("chave-jogo") < topo.index('class="tn-x"'), (
        "a chave saiu do lugar do desenho: título, `?` do título, chave, botão de fechar")
    assert topo.count('data-gesto="tabela-no-jogo"') == 1, (
        "o gesto tem de estar no interruptor e só nele — no `?` ele ligaria a chave por engano")
    assert "Também no jogo" in topo


def test_a_chave_tem_os_tres_enderecos_e_nasce_desligada():
    topo = _topo_das_definicoes()
    assert topo.count('data-campo="tabela-no-jogo"') == 2, (
        "o interruptor perdeu a classe `ligado` ou a palavra Sim/Não")
    assert topo.count('data-campo="tabela-no-jogo-fora"') == 1, (
        "sem o endereço do Nativo a chave não fica apagada")
    assert ">Não</span>" in topo, "a chave nasce DESLIGADA: ligada, o Cruz clicaria em todo jogo"


def test_o_ponto_de_interrogacao_da_chave_diz_o_porque_do_nativo():
    topo = _topo_das_definicoes()
    assert "modo nativo" in topo and "apagada" in topo
    assert "P1" in topo, "a dica tem de dizer que o cursor e a rolagem só andam pelo P1"


def test_a_dica_do_teclado_explica_as_duas_palavras_de_jogo():
    doc = _desenho()
    assert ("<b>Só dentro do jogo</b>: digita só com um jogo aberto. "
            "<b>Só fora do jogo</b>: digita só sem jogo aberto.") in doc


@pytest.mark.parametrize("perfil,esperado", [
    ({"tabela_no_jogo": True}, "Sim"),
    ({"tabela_no_jogo": False}, "Não"),
    ({}, "Não"),
])
def test_a_chave_pinta_o_que_o_perfil_diz(monkeypatch, perfil, esperado):
    """MORDIDA: inverter o `if` do `pacote()` troca o Sim pelo Não e reprova os três."""
    import pacotes
    from pacotes import a06_navegacao as mod
    from pacotes import perfil as pp

    monkeypatch.setattr(pp, "ativo_que_vale", lambda nome: {"name": "x", **perfil})
    mesa = mod.pacote(pacotes.Contexto(state={"active_profile": "x"}))["mesa"]
    assert mesa["tabela-no-jogo"] == esperado


@pytest.mark.parametrize("nativo,esperado", [(True, "NATIVO"), (False, "")])
def test_no_nativo_a_chave_fica_apagada(monkeypatch, nativo, esperado):
    import pacotes
    from pacotes import a06_navegacao as mod
    from pacotes import perfil as pp

    monkeypatch.setattr(pp, "ativo_que_vale", lambda nome: {"name": "x"})
    estado = {"active_profile": "x", "native_mode": nativo}
    mesa = mod.pacote(pacotes.Contexto(state=estado))["mesa"]
    assert mesa["tabela-no-jogo-fora"] == esperado


@pytest.mark.parametrize("so_dentro,ligado,esperada", [
    (True, True, "Só dentro do jogo"),
    (False, True, "Só fora do jogo"),
    (True, False, "Desativado"),
])
def test_a_lista_do_teclado_pinta_so_dentro_quando_o_perfil_diz(
        monkeypatch, so_dentro, ligado, esperada):
    """MORDIDA: tirar o `so_dentro` da pintura deixa «Só fora do jogo» no lugar."""
    import pacotes
    from pacotes import a06_navegacao as mod
    from pacotes import perfil as pp

    monkeypatch.setattr(pp, "ativo_que_vale",
                        lambda nome: {"name": "x", "teclado_so_no_jogo": so_dentro})
    monkeypatch.setattr(mod, "_o_que_a_pagina_oferece",
                        lambda: frozenset({"Só dentro do jogo", "Só fora do jogo", "Desativado"}))
    estado = {"active_profile": "x", "keyboard_emulation": {"enabled": ligado}}
    mesa = mod.pacote(pacotes.Contexto(state=estado))["mesa"]
    assert mesa["teclado-estado"] == esperada


def test_o_css_da_chave_nao_usa_opacidade_nem_vermelho():
    """Cinza de verdade no Nativo (cor explícita) e nunca vermelho."""
    doc = _desenho()
    bloco = re.search(r"\.chave-jogo\.apagada[^}]*}", doc)
    assert bloco, "o cinza do Nativo da chave sumiu do desenho"
    assert "opacity" not in bloco.group(0) and "red" not in bloco.group(0)
