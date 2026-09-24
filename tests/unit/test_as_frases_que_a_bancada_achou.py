"""AS-FRASES-QUE-A-BANCADA-ACHOU-01 — o que a tela dizia e o produto desmentia.

Em 24/09/2026 a preparação da sessão de validação reescreveu os gestos da mesa
de medição contra a tela de hoje, e o conferente achou frases do PRODUTO que
contradizem o que o produto faz. Gesto nenhum cura isso: a cura é na tela.

AS TRÊS FRASES, medidas antes de mexer:

* aba 05, o «?» do «Testar agora» prometia *"treme este controle por meio
  segundo"*. Desde 07/09 (pedido dela) o `a05_vibracao.testar` fica ligado até
  o «Parar» e o de outra coluna encerra o anterior — a §1 abaixo mede o gesto,
  e não só a frase;
* aba 08, a contagem da Gestão dizia *"4 controles • 2 no cabo • 2 no rádio"*;
* aba 08, a linha do Microfone dizia *"pelo cabo • Placa do controle"* /
  *"pelo rádio • Pela ponte"*.

As duas da 08 caíram com a decisão dela de 21/09/2026, que revogou a I9: a
palavra do transporte na tela é USB e BT. A razão que segurava a contagem —
*"2 cabo · 0 rádio" não é português* (D-05) — caiu junto.

AS RÉGUAS LEEM A PÁGINA GERADA (`mockup/`), nunca o texto do gerador, e a
PALAVRA DO TRANSPORTE SE PERGUNTA AO DONO (`home_actions.palavra_do_transporte`),
nunca se digita: a régua de 06/09 que negava `"USB"` teria reprovado a decisão
dela de 21/09. A exceção é o «Parar», que é RÓTULO do botão e decisão dela de
30/08 (*"se o user quiser parar vai clicar em Parar"*).

MORDIDAS (cada uma no docstring do seu caso): devolva a frase velha ao gerador
ou ao dono, regere a página, e o caso reprova nomeando a frase.
"""
from __future__ import annotations

import html
import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app.actions.home_actions import (
    palavra_do_transporte as palavra,
)
from hefesto_dualsense4unix.gui import aba_conexoes as gestao
from tests.unit.test_a05_a_vibracao_aplica_e_fala import PonteDeMentira

BANCADA = RAIZ / "mockup"

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"


def _pagina(nome: str) -> str:
    """A página gerada, SEM os comentários — o que chega ao olho.

    Os comentários desta casa contam a história da frase velha, e uma régua que
    os lesse reprovaria quem escreve o porquê (a régua confundindo a palavra
    com o ato).
    """
    bruto = (BANCADA / nome).read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", "", bruto, flags=re.S)


def _texto(trecho: str) -> str:
    """O texto visível de um pedaço de HTML: sem tags, com o espaço colapsado."""
    sem_tags = re.sub(r"<[^>]+>", "", trecho)
    return re.sub(r"\s+", " ", html.unescape(sem_tags)).strip()


# ---------------------------------------------------------------------------
# 1. A 05 — o «?» do «Testar agora» deixa de prometer meio segundo
# ---------------------------------------------------------------------------
def _dica_do_testar() -> str:
    """O primeiro parágrafo do `?` do «Testar agora», como a página o mostra."""
    x = _pagina("05-vibracao.html")
    m = re.search(r'<span class="sec-rot">Testar agora\s*<span class="ajuda"[^>]*>\?'
                  r'<span class="dica">(.*?)<br><br>', x, flags=re.S)
    assert m, "o `?` do «Testar agora» sumiu da 05 gerada — a régua ficou cega"
    return _texto(m.group(1))


def test_a_dica_do_testar_nao_promete_duracao() -> None:
    """O «?» diz que o teste vai até o «Parar», e não põe prazo nenhum.

    MORDIDA: devolva *"treme este controle por meio segundo"* ao `aba05.py`,
    regere a 05 — reprova citando a frase.
    """
    dica = _dica_do_testar()
    prazo = re.search(r"\b(segundos?|ms|milissegundos?)\b", dica, flags=re.I)
    assert not prazo, (
        f"o `?` do «Testar agora» voltou a prometer um prazo ({prazo.group(0)!r}) "
        f"— o Testar fica ligado até o Parar desde 07/09: {dica!r}")
    assert re.search(r"\baté o Parar\b", dica), (
        f"o `?` do «Testar agora» não diz mais quem termina o teste: {dica!r}")
    assert re.search(r"\boutro controle\b", dica), (
        f"o `?` do «Testar agora» não diz que o teste de outro controle "
        f"encerra este (um teste só, `_EM_TESTE`): {dica!r}")


@pytest.fixture
def pac() -> Any:
    import pacotes

    return pacotes


@pytest.fixture
def a05() -> Any:
    from pacotes import a05_vibracao

    a05_vibracao.parar_o_teste()
    yield a05_vibracao
    a05_vibracao.parar_o_teste()


def _ctx(pac: Any) -> Any:
    """A mesa com os dois controles, um no USB e um no BT."""
    return pac.Contexto(
        state={"active_profile": "Bancada", "rumble_policy": "max",
               "rumble_motor_pct_padrao": 100, "rumble_motores": {}},
        mesa=[
            {"pref": "p1", "jogador": 1, "uniq": P1, "nome": "Régua 1",
             "via": "USB", "cor": "starlight-blue"},
            {"pref": "p2", "jogador": 2, "uniq": P2, "nome": "Régua 2",
             "via": "BT", "cor": "midnight-black"},
        ],
        conectados=[
            {"uniq": P1, "connected": True, "transport": "usb", "index": 0, "player": 1},
            {"uniq": P2, "connected": True, "transport": "bluetooth", "index": 1,
             "player": 2},
        ],
        estados={})


def test_o_testar_fica_ligado_ate_o_parar_e_o_de_outro_controle_o_encerra(
        pac: Any, a05: Any) -> None:
    """O fato que a frase nova afirma, medido no gesto — não na prosa.

    Três tempos: o Testar do P1 não manda parada nenhuma e fica marcado; o do
    P2 toma a marca (o daemon cala o dono abandonado,
    `rumble.silenciar_dono_abandonado`); e só o «Parar» apaga a marca e devolve
    os motores ao jogo.

    MORDIDA: ponha um `p.rumble_stop()` no fim de `a05_vibracao.testar` (o
    pulso de antes de 07/09) — reprova no primeiro tempo.
    """
    testar = pac.gesto_da_pagina("05-vibracao.html", "testar")
    parar = pac.gesto_da_pagina("05-vibracao.html", "parar")
    assert testar is not None and parar is not None, "o par Testar/Parar perdeu o dono"
    ctx = _ctx(pac)

    p = PonteDeMentira()
    testar(ctx, {"uniq": P1, "controle": "p1"}, p)
    paradas = [n for n in p.nomes if n.startswith(("rumble_stop", "rumble_passthrough"))]
    assert not paradas, f"o Testar parou sozinho: {p.nomes}"
    assert "rumble_set_checked" in p.nomes, f"o Testar não mandou vibração: {p.nomes}"
    assert a05.em_teste() == P1, "o Testar do P1 não ficou ligado"

    testar(ctx, {"uniq": P2, "controle": "p2"}, PonteDeMentira())
    assert a05.em_teste() == P2, (
        "o Testar do P2 não encerrou o do P1 — um teste só, `_EM_TESTE`")

    fim = PonteDeMentira()
    parar(ctx, {"uniq": P2, "controle": "p2"}, fim)
    assert a05.em_teste() == "", "o Parar não apagou a marca do teste"
    assert "rumble_stop_checked" in fim.nomes and "rumble_passthrough" in fim.nomes, (
        f"o Parar não devolveu os motores ao jogo: {fim.nomes}")


# ---------------------------------------------------------------------------
# 2. A 08 — a contagem da Gestão fala USB e BT
# ---------------------------------------------------------------------------
def _cartoes_da_gestao() -> list[tuple[str, str]]:
    """`(nome, bloco)` de cada linha da Gestão de Controles na página gerada."""
    x = _pagina("08-conexoes.html")
    partes = re.split(r'(?=<div class="gc-item )', x)[1:]
    assert partes, "a Gestão de Controles sumiu da 08 gerada — a régua ficou cega"
    fora = []
    for bloco in partes:
        nome = re.search(r'<span class="gc-nome" data-campo="nome"[^>]*>(.*?)</span>\s*<',
                         bloco, flags=re.S)
        assert nome, "uma linha da Gestão perdeu o nome"
        fora.append((_texto(nome.group(1)), bloco))
    return fora


def _palavra_do_cartao(nome: str) -> str | None:
    """A palavra de transporte que a linha mostra no fim do nome, se mostrar."""
    ultima = nome.rsplit("•", 1)[-1].strip()
    return ultima if ultima in {palavra("usb"), palavra("bt")} else None


def test_a_contagem_da_gestao_na_pagina_usa_a_palavra_do_dono() -> None:
    """O canto da Gestão conta com a palavra que o dono dá, e bate com as linhas.

    MORDIDA: devolva *"{usb} no cabo • {radio} no rádio"* ao
    `gui.aba_conexoes.texto_da_contagem`, regere a 08 — reprova com as duas
    frases.
    """
    x = _pagina("08-conexoes.html")
    m = re.search(r'data-campo="conta-gestao"[^>]*>(.*?)</span>\s*</div>', x, flags=re.S)
    assert m, "a contagem da Gestão perdeu o endereço `conta-gestao`"
    na_tela = _texto(m.group(1))

    palavras = [_palavra_do_cartao(n) for n, _ in _cartoes_da_gestao()]
    usb = palavras.count(palavra("usb"))
    bt = palavras.count(palavra("bt"))
    n = usb + bt
    assert n, "nenhuma linha da Gestão termina numa palavra de transporte do dono"
    pedacos = [f"{n} {'controle' if n == 1 else 'controles'}"]
    if usb:
        pedacos.append(f"{usb} {palavra('usb')}")
    if bt:
        pedacos.append(f"{bt} {palavra('bt')}")
    assert na_tela == " • ".join(pedacos), (
        f"a contagem da Gestão diz {na_tela!r}, e as linhas dela pedem "
        f"{' • '.join(pedacos)!r}")


@pytest.mark.parametrize(("transportes", "esperada"), [
    (["bt"], "1 controle • 1 {bt}"),
    (["usb", "usb"], "2 controles • 2 {usb}"),
    (["usb", "usb", "bt", "bt"], "4 controles • 2 {usb} • 2 {bt}"),
    ([], "0 controles"),
])
def test_a_contagem_omite_o_transporte_vazio(transportes: list[str], esperada: str) -> None:
    """O transporte sem controle não aparece — a decisão dela de 17/09 no canto
    de cima (`mesa_viva.frase_dos_transportes`) vale para o canto da Gestão.

    MORDIDA: tire os dois `if` de `texto_da_contagem` — o caso de um controle
    só no BT reprova com o `0 USB` na frase.
    """
    controles = [gestao.Controle(uniq=f"c{i}", jogador=i + 1, via=t, bateria=None)
                 for i, t in enumerate(transportes)]
    frase = gestao.texto_da_contagem(controles)
    assert frase == esperada.format(usb=palavra("usb"), bt=palavra("bt"))


@pytest.mark.parametrize("cru", ["usb", "bt", "bluetooth"])
def test_a_tabela_da_gestao_diz_o_que_o_dono_diz(cru: str) -> None:
    """`NOME_DO_TRANSPORTE` é a segunda grafia da tabela do dono — e presa a ela.

    O módulo nasceu puro (o gerador da 08 roda sem o `structlog`) e não importa
    `home_actions`; é esta régua que impede as duas de divergirem.
    """
    assert gestao.NOME_DO_TRANSPORTE[cru] == palavra(cru)


# ---------------------------------------------------------------------------
# 3. A 08 — a linha do Microfone e as duas dicas dela
# ---------------------------------------------------------------------------
def test_a_linha_do_microfone_na_pagina_fala_o_transporte_da_linha() -> None:
    """Cada linha diz «pelo <a palavra do nome dela>», no texto e no `title`.

    MORDIDA: devolva `("pelo rádio", "Pela ponte")` ao
    `a08_conexoes._CAMINHO_DO_MIC`, regere a 08 — reprova na linha do BT.
    """
    vistas = 0
    for nome, bloco in _cartoes_da_gestao():
        via = _palavra_do_cartao(nome)
        if via is None:
            continue
        vistas += 1
        caminho = re.search(r'data-campo="mic-caminho"[^>]*>(.*?)</span></span>',
                            bloco, flags=re.S)
        assert caminho, f"a linha {nome!r} perdeu o `mic-caminho`"
        texto = _texto(caminho.group(1))
        assert texto.startswith(f"pelo {via} •"), (
            f"a linha {nome!r} termina em {via} e o microfone dela diz {texto!r}")
        dica = re.search(r'data-campo="mic-dica"[^>]*title="([^"]*)"', bloco)
        assert dica, f"a linha {nome!r} perdeu o `mic-dica`"
        assert f"<b>pelo {via}</b>" in html.unescape(dica.group(1)), (
            f"a dica do microfone da linha {nome!r} não diz «pelo {via}»: "
            f"{html.unescape(dica.group(1))[:120]!r}")
    assert vistas >= 2, "a cena da 08 perdeu o par USB/BT — a régua ficou cega"


def test_o_interruptor_do_microfone_nomeia_as_duas_palavras() -> None:
    """O `?` do Ligado/Desligado manda ler a linha ao lado — na língua dela.

    MORDIDA: devolva *"quem decide é o cabo ou o rádio"* ao
    `aba08.MIC_LIGADO_DICA`, regere a 08 — reprova.
    """
    x = _pagina("08-conexoes.html")
    dicas = [_texto(d) for d in re.findall(
        r'<span class="dica">(Liga o microfone deste controle\..*?)<br><br>', x, flags=re.S)]
    assert dicas, "o `?` do Ligado/Desligado do microfone sumiu da 08 gerada"
    for dica in dicas:
        assert f"o {palavra('usb')} ou o {palavra('bt')}" in dica, (
            f"o `?` do microfone não fala a palavra do transporte: {dica!r}")


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_o_pacote_e_a_gestao_dizem_a_mesma_frase_do_microfone(via: str) -> None:
    """A repintura (`a08_conexoes.caminho_do_microfone`) e a Gestão
    (`Controle.texto_do_microfone`) são duas escritoras da mesma frase.

    MORDIDA: mude só uma das duas — reprova com as duas frases.
    """
    from pacotes import a08_conexoes

    do_pacote = _texto(a08_conexoes.caminho_do_microfone(via))
    c = gestao.Controle(uniq="c1", jogador=1, via=via, bateria=None)
    assert c.texto_do_microfone == f"Ligado, {do_pacote}", (
        f"a Gestão diz {c.texto_do_microfone!r} e a repintura {do_pacote!r}")
    assert do_pacote.startswith(f"pelo {palavra(via)} •")
