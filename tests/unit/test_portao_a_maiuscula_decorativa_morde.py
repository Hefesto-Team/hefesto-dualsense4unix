#!/usr/bin/env python3
"""O portão da maiúscula decorativa MORDE — e as duas metades mordem sozinhas."""
from __future__ import annotations

import importlib.util
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SPEC = importlib.util.spec_from_file_location(
    "_regua_da_maiuscula", RAIZ / "scripts" / "check_a_maiuscula_decorativa.py")
assert _SPEC and _SPEC.loader
regua = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(regua)


def _pagina(cabeca: str = "", corpo: str = "") -> str:
    return (f"<!doctype html>\n<html>\n<head>\n<title>Hefesto — aba TESTE</title>\n"
            f"<style>\n{cabeca}\n</style>\n</head>\n<body>\n{corpo}\n</body>\n</html>")


def test_a_folha_que_sobe_a_caixa_e_acusada_com_o_seletor():
    """A regra que sobe a caixa aparece com linha e seletor."""
    achado = regua._folha(_pagina(cabeca=".fita .chip .via{text-transform:uppercase}"))

    assert len(achado) == 1, f"a folha que sobe a caixa passou: {achado}"
    _, valor, seletor = achado[0]
    assert valor == "uppercase"
    assert ".fita .chip .via" in seletor, (
        f"a régua acusou sem dizer QUEM: {seletor!r} — o endereço do defeito é "
        f"a entrega de uma régua, não o número dele")


def test_o_capitalize_tambem_sobe():
    """`capitalize` também inventa maiúscula que o documento não tem."""
    assert regua._folha(_pagina(cabeca=".x{text-transform:capitalize}"))


def test_o_none_e_o_lowercase_nao_sao_defeito():
    """Abaixar não inventa maiúscula nenhuma — e `none` é a CURA de várias abas."""
    assert not regua._folha(_pagina(cabeca=".a{text-transform:none}"))
    assert not regua._folha(_pagina(cabeca=".b{text-transform:lowercase}"))


def test_o_comentario_que_cita_a_regra_nao_e_a_regra():
    """A armadilha de prosa desta casa, e ela já custou seis levas."""
    folha = ("/* aqui morava uma regra que subia a caixa:\n"
             "   .fita .chip .via{text-transform:uppercase} — e ela saiu */\n"
             ".fita .chip .via{color:red}")

    assert not regua._folha(_pagina(cabeca=folha)), (
        "o comentário que descreve a regra proibida foi lido como a regra")


def test_o_apagador_de_comentario_nao_move_a_linha():
    """O comentário some, o número da linha fica — o endereço é a entrega."""
    folha = "/* um\ncomentário\nde três linhas */\n.x{text-transform:uppercase}"
    (linha, _, _), = regua._folha(_pagina(cabeca=folha))

    assert linha == 9, f"a linha andou: {linha}"


def test_a_palavra_em_caixa_alta_no_corpo_e_vista():
    """A ênfase decorativa em prosa aparece, com o trecho em volta."""
    achadas = regua._palavras(_pagina(corpo="<p>Ignora ESTE conselho.</p>"))

    assert "ESTE" in achadas
    (_, trecho), = achadas["ESTE"]
    assert "conselho" in trecho


def test_a_palavra_dentro_do_title_do_elemento_conta():
    """A dica É tela: uma pessoa a lê, ainda que dentro de um atributo."""
    corpo = '<button title="Põe em TODOS os jogos">Pôr</button>'

    assert "TODOS" in regua._palavras(_pagina(corpo=corpo))


def test_o_titulo_do_documento_nao_conta():
    """`<title>Hefesto — aba TESTE</title>`: nesta janela ninguém o lê."""
    assert "TESTE" not in regua._palavras(_pagina())


def test_o_title_do_svg_conta():
    """O `<title>` de um grupo do desenho É o nome daquele pedaço, e se lê.

    **A MORDIDA:** apague TODO `<title>` em vez de só o do documento e os
    catorze rótulos de grupo do DualSense somem do inventário sem que ninguém
    os tenha curado.
    """
    corpo = '<svg><g><title>CHASSI</title><path d="M0 0"/></g></svg>'

    assert "CHASSI" in regua._palavras(_pagina(corpo=corpo))


def test_o_selo_e_desenho_e_nao_entra():
    """Ordem da sprint: *"Os selos são desenho e ficam."*"""
    corpo = ('<span class="selo ok"><span data-campo="selo">CERTO</span></span>'
             '<span class="lanc-selo nao_sei">NÃO SEI</span>')
    achadas = regua._palavras(_pagina(corpo=corpo))

    assert "CERTO" not in achadas and "SEI" not in achadas, achadas


def test_a_palavra_decorativa_ao_lado_do_selo_continua_pega():
    """O selo cobre o que está DENTRO dele, e nada além."""
    corpo = '<p><span class="selo ok">CERTO</span> — vale para ESTE controle.</p>'

    assert "ESTE" in regua._palavras(_pagina(corpo=corpo))


def test_o_span_de_selo_citado_no_style_nao_apaga_a_pagina():
    """A CICATRIZ DESTA RÉGUA, e ela é do próprio dia em que nasceu."""
    folha = '/* o gerador emitia <span class="lanc-selo localizado">, e nada casava */'
    achadas = regua._palavras(_pagina(cabeca=folha, corpo="<p>oi</p>"))

    assert not achadas, f"a folha de estilo vazou para o texto visível: {achadas}"


def test_a_sigla_e_o_modelo_nao_reprovam():
    """A caixa alta é a grafia PRÓPRIA delas — escrevê-las de outro jeito é erro."""
    assert regua._legitima("USB") and regua._legitima("BT")
    assert regua._legitima("AX211"), "modelo de aparelho não é palavra"
    assert not regua._legitima("INTEIRO")


def test_a_cor_e_o_endereco_saem_pela_forma_inteira():
    """Cor em hexa e endereço de rádio somem ANTES de virarem palavras."""
    corpo = '<p>#FF5555 e AA:BB:CC:00:00:01 — vale para ESTE controle.</p>'
    achadas = regua._palavras(_pagina(corpo=corpo))

    assert "FF" not in achadas and "AA" not in achadas, achadas
    assert "ESTE" in achadas, "a régua apagou mais do que o valor de máquina"
    assert not regua._legitima("DA"), (
        "«DA» voltou a passar por código de máquina — é preposição, e ela "
        "aparece em «BOTÕES DA FACE», que é dívida declarada")


def test_a_divida_esta_declarada_e_nao_reprova():
    """A dívida sai IMPRESSA com o dono, e não some."""
    assert regua.DIVIDA, "a dívida sumiu sem ninguém curá-la"
    for palavra, (oque, dono) in regua.DIVIDA.items():
        assert palavra == palavra.upper(), palavra
        assert oque and dono, f"{palavra} sem o que é ou sem dono"
        assert not regua._legitima(palavra), (
            f"{palavra} está na dívida E na lista de legítimas — duas respostas "
            f"para a mesma palavra")


def test_as_dez_paginas_publicadas_estao_verdes(capsys):
    """O portão fecha na árvore de hoje — a cura de 11/09 está publicada."""
    assert regua.main([]) == 0, capsys.readouterr().err


def test_a_regua_recusa_pasta_sem_as_dez(monkeypatch, tmp_path):
    """Régua que acha ZERO não é régua verde."""
    monkeypatch.setattr(regua, "PUBLICADO", tmp_path)

    assert regua.main([]) == 2
