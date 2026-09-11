#!/usr/bin/env python3
"""O portão da maiúscula decorativa MORDE — e as duas metades mordem sozinhas.

`scripts/check_a_maiuscula_decorativa.py` nasceu de uma ordem dela de
11/09/2026: *"Esse tipo de coisa não pode se repetir na interface."*

**A RAZÃO DE ESTE ARQUIVO EXISTIR é que a régua tem duas peneiras e cada uma
sozinha daria verde sobre o defeito da outra.** O `CABO` que ela fotografou
**não estava escrito em lugar nenhum**: o HTML dizia `cabo` e quem gritava era
uma linha de folha de estilo. Uma régua de texto passaria; uma régua de folha
passaria sobre uma palavra digitada em caixa alta no documento.

Cada função aqui diz a própria MORDIDA.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: A RÉGUA É CARREGADA PELO CAMINHO, não por `import`: `scripts/` não é pacote,
#: e um `sys.path.insert` naquela pasta traria vinte e tantos `check_*` para o
#: espaço de nomes desta suíte.
_SPEC = importlib.util.spec_from_file_location(
    "_regua_da_maiuscula", RAIZ / "scripts" / "check_a_maiuscula_decorativa.py")
assert _SPEC and _SPEC.loader
regua = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(regua)


def _pagina(cabeca: str = "", corpo: str = "") -> str:
    return (f"<!doctype html>\n<html>\n<head>\n<title>Hefesto — aba TESTE</title>\n"
            f"<style>\n{cabeca}\n</style>\n</head>\n<body>\n{corpo}\n</body>\n</html>")


# ---------------------------------------------------------------------------
# §1 — A FOLHA
# ---------------------------------------------------------------------------
def test_a_folha_que_sobe_a_caixa_e_acusada_com_o_seletor():
    """A regra que sobe a caixa aparece com linha e seletor.

    **A MORDIDA:** tire `uppercase` de :data:`regua.SOBE_A_CAIXA` e esta linha
    reprova — a peneira deixa de ver a única forma que o defeito dela teve.
    """
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
    """Abaixar não inventa maiúscula nenhuma — e `none` é a CURA de várias abas.

    **A MORDIDA:** ponha `none` em :data:`regua.SOBE_A_CAIXA` e a régua passa a
    reprovar as próprias curas que as dez páginas já escrevem.
    """
    assert not regua._folha(_pagina(cabeca=".a{text-transform:none}"))
    assert not regua._folha(_pagina(cabeca=".b{text-transform:lowercase}"))


def test_o_comentario_que_cita_a_regra_nao_e_a_regra():
    """A armadilha de prosa desta casa, e ela já custou seis levas.

    Um comentário escrito para AVISAR que a regra não pode voltar viraria a
    primeira ocorrência dela, e a régua reprovaria o aviso.

    **A MORDIDA:** tire o apagador de comentário de :func:`regua._folha` e esta
    linha reprova.
    """
    folha = ("/* aqui morava uma regra que subia a caixa:\n"
             "   .fita .chip .via{text-transform:uppercase} — e ela saiu */\n"
             ".fita .chip .via{color:red}")

    assert not regua._folha(_pagina(cabeca=folha)), (
        "o comentário que descreve a regra proibida foi lido como a regra")


def test_o_apagador_de_comentario_nao_move_a_linha():
    """O comentário some, o número da linha fica — o endereço é a entrega.

    **A MORDIDA:** troque o apagador por uma remoção (`sub("")`) e a linha
    acusada passa a ser a de antes do comentário.
    """
    folha = "/* um\ncomentário\nde três linhas */\n.x{text-transform:uppercase}"
    (linha, _, _), = regua._folha(_pagina(cabeca=folha))

    #: `<style>` abre na linha 5 do molde; o comentário ocupa 5, 6 e 7.
    assert linha == 9, f"a linha andou: {linha}"


# ---------------------------------------------------------------------------
# §2 — O TEXTO
# ---------------------------------------------------------------------------
def test_a_palavra_em_caixa_alta_no_corpo_e_vista():
    """A ênfase decorativa em prosa aparece, com o trecho em volta.

    **A MORDIDA:** faça :func:`regua._palavras` devolver só as palavras sem o
    contexto e a mensagem de falha deixa de dizer ONDE.
    """
    achadas = regua._palavras(_pagina(corpo="<p>Ignora ESTE conselho.</p>"))

    assert "ESTE" in achadas
    (_, trecho), = achadas["ESTE"]
    assert "conselho" in trecho


def test_a_palavra_dentro_do_title_do_elemento_conta():
    """A dica É tela: uma pessoa a lê, ainda que dentro de um atributo."""
    corpo = '<button title="Põe em TODOS os jogos">Pôr</button>'

    assert "TODOS" in regua._palavras(_pagina(corpo=corpo))


def test_o_titulo_do_documento_nao_conta():
    """`<title>Hefesto — aba TESTE</title>`: nesta janela ninguém o lê.

    **A MORDIDA:** tire o recorte do `<body>` de :func:`regua._so_a_tela` e as
    dez páginas passam a acusar o nome da própria aba.
    """
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
    """Ordem da sprint: *"Os selos são desenho e ficam."*

    **A MORDIDA:** tire `selo` de :data:`regua.SELO` e `CERTO`, `MUDO` e
    `NÃO SEI` viram vermelho — reprovando o desenho que ela aprovou.
    """
    corpo = ('<span class="selo ok"><span data-campo="selo">CERTO</span></span>'
             '<span class="lanc-selo nao_sei">NÃO SEI</span>')
    achadas = regua._palavras(_pagina(corpo=corpo))

    assert "CERTO" not in achadas and "SEI" not in achadas, achadas


def test_a_palavra_decorativa_ao_lado_do_selo_continua_pega():
    """O selo cobre o que está DENTRO dele, e nada além.

    É a diferença entre a peneira estrutural e uma lista de palavras: quem
    escrever ênfase colada num selo não se salva por vizinhança.

    **A MORDIDA:** faça :func:`regua._sem_os_selos` apagar até o fim da linha
    em vez de até o fechamento equilibrado e esta linha reprova.
    """
    corpo = '<p><span class="selo ok">CERTO</span> — vale para ESTE controle.</p>'

    assert "ESTE" in regua._palavras(_pagina(corpo=corpo))


def test_o_span_de_selo_citado_no_style_nao_apaga_a_pagina():
    """A CICATRIZ DESTA RÉGUA, e ela é do próprio dia em que nasceu.

    Um comentário do `<style>` que CITA ``<span class="lanc-selo …">`` — havia
    um, escrito para explicar por que a folha não conhecia a classe nova — era
    lido como abertura de selo de verdade. O varredor saía dali procurando o
    fechamento, atravessava o ``</style>`` e o apagava junto: a folha inteira
    virava "texto visível" e a régua acusava **306** caixas altas, quase todas
    prosa de comentário de CSS.

    *O comentário que descreve o padrão vira a primeira ocorrência dele* — pela
    sétima vez nesta casa, e desta vez dentro do instrumento feito para medi-la.

    **A MORDIDA:** tire o `<style>` de :data:`regua._FORA_DA_TELA` e esta linha
    reprova com dezenas de palavras de comentário.
    """
    folha = '/* o gerador emitia <span class="lanc-selo localizado">, e nada casava */'
    achadas = regua._palavras(_pagina(cabeca=folha, corpo="<p>oi</p>"))

    assert not achadas, f"a folha de estilo vazou para o texto visível: {achadas}"


def test_a_sigla_e_o_modelo_nao_reprovam():
    """A caixa alta é a grafia PRÓPRIA delas — escrevê-las de outro jeito é erro.

    **A MORDIDA:** esvazie :data:`regua.SIGLA` e o contador de controles
    (`1 USB · 1 BT`) vira vermelho nas dez páginas.
    """
    assert regua._legitima("USB") and regua._legitima("BT")
    assert regua._legitima("AX211"), "modelo de aparelho não é palavra"
    assert not regua._legitima("INTEIRO")


def test_a_cor_e_o_endereco_saem_pela_forma_inteira():
    """Cor em hexa e endereço de rádio somem ANTES de virarem palavras.

    **E O PEDAÇO NÃO SERVE — medido em 11/09/2026, por este arquivo.** A
    primeira versão da régua tratava qualquer par `[0-9A-F]{2}` como código,
    para cobrir os octetos de `AA:BB:CC:…`, e com isso o `DA` de «BOTÕES DA
    FACE» saía calado: uma preposição do português perdida porque as duas
    letras dela também são dígitos hexadecimais.

    **A MORDIDA:** volte a aceitar o par solto e a última asserção reprova.
    """
    corpo = '<p>#FF5555 e AA:BB:CC:00:00:01 — vale para ESTE controle.</p>'
    achadas = regua._palavras(_pagina(corpo=corpo))

    assert "FF" not in achadas and "AA" not in achadas, achadas
    assert "ESTE" in achadas, "a régua apagou mais do que o valor de máquina"
    assert not regua._legitima("DA"), (
        "«DA» voltou a passar por código de máquina — é preposição, e ela "
        "aparece em «BOTÕES DA FACE», que é dívida declarada")


def test_a_divida_esta_declarada_e_nao_reprova():
    """A dívida sai IMPRESSA com o dono, e não some.

    Nenhuma das palavras de :data:`regua.DIVIDA` mora num arquivo da
    ESQUELETO-C2: reprovar de saída seria um portão desligado na segunda-feira.
    O que ela impede é a dívida CRESCER calada.

    **A MORDIDA:** apague uma linha de :data:`regua.DIVIDA` e a régua reprova —
    a palavra continua na tela e deixou de estar declarada.
    """
    assert regua.DIVIDA, "a dívida sumiu sem ninguém curá-la"
    for palavra, (oque, dono) in regua.DIVIDA.items():
        assert palavra == palavra.upper(), palavra
        assert oque and dono, f"{palavra} sem o que é ou sem dono"
        assert not regua._legitima(palavra), (
            f"{palavra} está na dívida E na lista de legítimas — duas respostas "
            f"para a mesma palavra")


# ---------------------------------------------------------------------------
# O produto de hoje
# ---------------------------------------------------------------------------
def test_as_dez_paginas_publicadas_estao_verdes(capsys):
    """O portão fecha na árvore de hoje — a cura de 11/09 está publicada.

    **A MORDIDA:** devolva ao `topo.html` a regra que subia a caixa da via,
    regere e publique — esta linha reprova dez vezes, uma por página.
    """
    assert regua.main([]) == 0, capsys.readouterr().err


def test_a_regua_recusa_pasta_sem_as_dez(monkeypatch, tmp_path):
    """Régua que acha ZERO não é régua verde.

    **A MORDIDA:** troque o `!= 10` por um `for` sobre o que houver e a régua
    passa a dizer OK sobre nenhuma página.
    """
    monkeypatch.setattr(regua, "PUBLICADO", tmp_path)

    assert regua.main([]) == 2
