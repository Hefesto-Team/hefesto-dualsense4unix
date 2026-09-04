#!/usr/bin/env python3
"""A POSIÇÃO DO PONTINHO — a queixa dela, e a régua que ela deixa.

A QUEIXA É DELA, 04/09/2026, com dois DualSense na mesa (um no cabo, um no
rádio, os dois validados): *"não funciona o touch, analogicos"*.

E ela estava certa nos dois. O DADO CHEGAVA INTEIRO — `daemon/sensor_hub.py`
publica o bloco `touchpad` com as cinco chaves juntas (`touching`, `x`, `y`,
`width`, `height`) e o `inputs` com `lx`/`ly`/`rx`/`ry`;
`docs/data/mapa-controles.csv` diz `toque.touchpad = sim` nos DOIS transportes.
O que o produto fazia com ele:

    onde o dado morria                       o que a tela mostrava
    `toque_do_controle` lia só `lido[0]`     o pontinho ACENDIA e APAGAVA certo,
                                             parado em `left:62%;top:44%`
    os dois `<span class="p">` dos           as bolinhas dos polegares paradas
    analógicos não tinham endereço           onde o mockup as cravou

**ACENDER NO LUGAR ERRADO É A FAMÍLIA DE DEFEITO QUE ESTA ABA JÁ PAGOU DUAS
VEZES**: ter dono não é dizer a verdade. O `touch-ponto` tinha dono desde 02/09
— e o dono só sabia dizer *se* havia um dedo, nunca *onde*.

POR QUE NÃO ERA ALCANÇÁVEL, e é a razão de a cura ser uma FOLHA e não um campo:
`left`/`top` moravam num `style=` de LINHA, que vence qualquer folha de estilo,
e o `escrever()` do piloto não tem alvo que escreva `style` — o alvo `atributo`
o RECUSA por nome (`hefesto_vivo.atributo_escrevivel` exige `data-`/`aria-` ou
`title`). A cura é a mesma da cor do plástico, de 03/09: a posição sai do
`style=` e vira REGRA numa folha endereçada que o produto TROCA INTEIRA
(`data-campo="posicao-css"`, alvo `html`).

O QUE ESTA RÉGUA MEDE, e o que cada teste MORDE está escrito no teste. As duas
metades:

1. **o dado chega à folha** — com touchpad e analógicos sintéticos, a regra do
   assento sai com a posição lida, e não com a do desenho;
2. **a página não tem mais posição cravada** — nenhum `style="left:…%;top:…%"`
   sobrou, e a folha endereçada existe, é UMA e nomeia os três pontinhos de cada
   controle conectado.

O QUE ELA NÃO MEDE, declarado para não virar verde por vacuidade: ela não abre
o `WebView` nem confere o que o WebKit calcula. A prova de que a regra VENCE o
desenho é de especificidade, e está contada em `PISO_DAS_POSICOES`; a prova de
que ela chega à tela é a foto, que é obrigatória nesta casa e não cabe num teste
de unidade.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: MAC da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"

#: O TOUCHPAD COMO O DAEMON O PUBLICA, com o dedo em três quartos da largura e
#: um quarto da altura. Os limites são os que o payload declara — 1920x1080 é o
#: que os dois DualSense dela publicam, e `posicao_normalizada` os LÊ em vez de
#: cravá-los.
DEDO = {"touching": True, "x": 1440, "y": 270, "width": 1920, "height": 1080}
#: A posição do `DEDO` em por cento: 1440/1920 e 270/1080.
DEDO_EM_POR_CENTO = (75.0, 25.0)

#: OS DOIS POLEGARES, e o esquerdo está no TALO — `lx=0` é o extremo à
#: esquerda, não o centro. É o defeito que `mesa_viva._eixo_do_analogico` mediu
#: e curou em 29/08/2026 (`int(inputs.get(nome) or 128)` fazia `0` virar `128`).
POLEGARES = {"lx": 0, "ly": 255, "rx": 128, "ry": 128}


@pytest.fixture(scope="module")
def pac():
    import pacotes

    return pacotes


@pytest.fixture(scope="module")
def a02():
    from pacotes import a02_controles

    return a02_controles


@pytest.fixture(scope="module")
def pagina() -> str:
    """A página da BANCADA — o desenho de hoje, que é o que ela olha.

    A bancada, e não o publicado, de propósito: apontar uma régua para o
    publicado a faria dar **verde sobre a página congelada**, que é a armadilha
    mais cara do `docs/process/COMO-OLHAR-A-TELA.md` e a razão de
    `onde.pagina()` ter a bancada por padrão.
    """
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina("02-controles.html").read_text(encoding="utf-8")


BASE: dict[str, Any] = {
    "uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
    "battery_pct": 95, "is_primary": True, "inputs": {}, "audio": {},
}
#: O assento na mesa. O `pref` é o endereço do desenho (`data-controle="p1"`), e
#: é ele — não o `uniq` do daemon — que nomeia o seletor.
MESA = [{"uniq": UNIQ, "pref": "p1", "nome": "White", "via": "USB", "cor": "white"}]


def _folha(pac, a02, entrada: dict, monkeypatch) -> str:
    """A folha `posicao-css` que o pacote emite para UM controle na mesa.

    O `_ENDERECOS` É FORÇADO, e a razão é de calendário: `_so_se_a_pagina_tiver`
    pergunta à página **publicada**, e o `posicao-css` nasce hoje na BANCADA —
    o publicado só o recebe no dia em que ela mandar publicar a aba. Sem este
    desvio esta régua mediria a data da publicação, e não a cura.
    """
    monkeypatch.setattr(
        a02, "_ENDERECOS", frozenset({"posicao-css", "plastico-css"}), raising=False)
    ctx = pac.Contexto(state={}, mesa=MESA, conectados=[entrada], estados={})
    return str(a02.pacote(ctx)["mesa"]["posicao-css"])


# --------------------------------------------------------------------------
# 1. O DADO CHEGA À FOLHA
# --------------------------------------------------------------------------
def test_a_posicao_do_dedo_chega_a_folha(pac, a02, monkeypatch):
    """Com o dedo em 75%/25% do pad, a regra do P1 diz 75%/25%.

    Ela é a metade `touch` da queixa dela. O `fx`/`fy` já vinham prontos de
    `controller_card.touchpad_do_inputs` — *"já normalizados 0..1 pelos limites
    que o PRÓPRIO payload declara"* — e `toque_do_controle` os jogava fora.

    MORDE: voltar `toque_do_controle` a devolver o par (só `palavra` e `ponto`,
    sem a posição) rebenta a desempacotação em `pacote()`; devolver `None` no
    terceiro item — a forma silenciosa do mesmo estrago — apaga a regra e
    reprova aqui, porque a folha volta a ter só o piso.
    """
    folha = _folha(pac, a02, {**BASE, "inputs": {"touchpad": DEDO}}, monkeypatch)
    x, y = DEDO_EM_POR_CENTO
    assert f'.ctl[data-controle="p1"] .touch .ponto{{left:{x}%;top:{y}%}}' in folha, (
        f"a posição do dedo não chegou à folha:\n{folha}")
    assert "62%" not in folha, (
        "a folha carrega o `left:62%` que o mockup cravou — o pontinho continua "
        "aceso no lugar do desenho")


def test_a_posicao_dos_polegares_chega_a_folha(pac, a02, monkeypatch):
    """Os dois analógicos, e o esquerdo no TALO: `lx=0` é 0%, não o centro.

    A metade `analogicos` da queixa dela. Os dois `<span class="p">` não tinham
    endereço NENHUM — o `left`/`top` deles era o que o mockup cravou, e nenhuma
    linha de código os movia.

    MORDE DUAS VEZES:
    * apagar as duas entradas de `posicoes_do_controle` reprova na primeira
      asserção (a folha fica só com o piso);
    * ler o eixo com `inputs.get("lx") or 128` — o defeito de 29/08, em que o
      zero vira o centro — reprova na segunda, que é o talo.
    """
    folha = _folha(pac, a02, {**BASE, "inputs": dict(POLEGARES)}, monkeypatch)
    assert '.ctl[data-controle="p1"] .stick[data-stick="l"] .p{left:0.0%;top:100.0%}' \
        in folha, f"o polegar esquerdo não chegou à folha:\n{folha}"
    assert '.ctl[data-controle="p1"] .stick[data-stick="r"] .p{left:50.2%;top:50.2%}' \
        in folha, f"o polegar direito não chegou à folha:\n{folha}"
    # O TALO NÃO PODE TER VIRADO O CENTRO. Esta é a linha que pega o `or 128`.
    esquerdo = next(ln for ln in folha.split("\n") if 'data-stick="l"' in ln)
    assert "left:0.0%" in esquerdo, (
        f"`lx=0` — o extremo à esquerda — virou outra coisa: {esquerdo}")


def test_sem_leitura_a_folha_e_so_o_piso(pac, a02, monkeypatch):
    """O controle sem `inputs` não ganha regra nenhuma — e o piso o recolhe.

    É o card do P2 da mesa dela: o daemon só publica `inputs` para o
    `is_primary`, e o outro vem `None` (`daemon/ipc_handlers.py:3513-3516`).
    Escrever o repouso como se fosse leitura seria a mesma mentira que o card do
    P2 já contou com os números do P1.

    MORDE: emitir a posição mesmo sem leitor (trocar o `if tem_leitor` por
    `True` em `posicoes_do_controle`) põe duas regras a mais aqui e reprova.
    """
    folha = _folha(pac, a02, {**BASE, "inputs": None}, monkeypatch)
    assert folha == a02.PISO_DAS_POSICOES, (
        f"um controle sem leitura ganhou regra de posição:\n{folha}")


def test_o_piso_vem_primeiro_e_recolhe_o_assento_sem_dono(a02):
    """A folha é trocada INTEIRA, então ela precisa de um piso.

    Sem ele, o assento que a mesa viva não nomeia ficaria sem `left`/`top` — e o
    pontinho cairia na posição estática do elemento, que não é lugar nenhum. O
    neutro é o REPOUSO (128 nos dois eixos), o mesmo que o `xy-l`/`xy-r` ao lado
    já dizem quando não há leitura.

    MORDE: apagar `PISO_DAS_POSICOES` da lista de `folha_das_posicoes` reprova
    na primeira linha.
    """
    folha = a02.folha_das_posicoes({"p1": {"touch": (10.0, 20.0)}})
    assert folha.split("\n")[0] == a02.PISO_DAS_POSICOES
    assert a02.PISO_DAS_POSICOES.endswith("{left:50.2%;top:50.2%}"), (
        "o piso deixou de ser o repouso do analógico")


def test_o_assento_sem_pref_nao_vira_seletor(a02):
    """Sem `pref` não há endereço — e um seletor vazio pegaria TODOS os cards.

    `.ctl[data-controle=""] …` não casa nada, mas a regra entraria na folha e o
    dia em que alguém a afrouxasse ela vestiria a mesa inteira com a posição de
    um controle só.

    MORDE: tirar o `if pref` de `folha_das_posicoes` põe a regra aqui.
    """
    folha = a02.folha_das_posicoes({"": {"touch": (10.0, 20.0)}})
    assert folha == a02.PISO_DAS_POSICOES


# --------------------------------------------------------------------------
# 2. A PÁGINA NÃO TEM MAIS POSIÇÃO CRAVADA
# --------------------------------------------------------------------------
def test_a_pagina_nao_tem_mais_posicao_no_style_de_linha(pagina):
    """Nenhum `style="left:…%;top:…%"` sobrou — era o que travava tudo.

    Estilo de LINHA vence folha de estilo. Enquanto um só desses sobrar, o
    pontinho daquele card fica onde o desenho o pôs, faça o produto o que fizer.

    MORDE: devolver o `style=` ao `bloco()` (ou tirar a chamada de
    `posicao_por_regra` do `__main__` do gerador) reprova aqui — e reprova antes
    disso, no próprio gerador, que já para com a âncora.
    """
    achados = re.findall(r'style="left:[0-9.]+%;top:[0-9.]+%"', pagina)
    assert not achados, (
        f"{len(achados)} posição(ões) ainda cravada(s) no `style=`: {achados[:3]}")


def test_a_pagina_tem_a_folha_enderecada_e_ela_e_uma_so(pagina):
    """A folha existe, é UMA e o alvo é `html`.

    Sem o `data-hef-alvo="html"` o piloto escreveria a folha como TEXTO por cima
    da página. Duas folhas deixariam o assento que a segunda não nomeia com a
    posição do desenho — o buraco medido em 03/09 com o `--plastico`.

    MORDE: trocar o alvo, ou emitir a folha duas vezes, reprova.
    """
    assert '<style data-campo="posicao-css" data-hef-alvo="html">' in pagina
    assert pagina.count('data-campo="posicao-css"') == 1


def test_a_folha_da_pagina_nomeia_os_tres_pontinhos_de_cada_controle(pagina, a02):
    """Três regras por controle conectado: o dedo e os dois polegares.

    E o SELETOR É PEDIDO AO DONO (`seletor_da_posicao`), nunca redigitado: o
    gerador e o produto escrevem a mesma folha, e duas gramáticas divergiriam
    sem ninguém ver — foi a lição do `seletor_do_plastico`.

    MORDE: mudar a gramática do seletor num dos dois lados reprova aqui.
    """
    prefs = sorted(set(re.findall(r'<div class="ctl card" data-controle="([^"]+)">',
                                  pagina)))
    assert prefs, "a régua não achou um card sequer — régua que acha zero é ERRO"
    faltam = [f"{p}/{alvo}" for p in prefs for alvo in a02.ALVOS_DA_POSICAO
              if f"{a02.seletor_da_posicao(p, alvo)}{{left:" not in pagina]
    assert not faltam, f"a folha da página não nomeia {faltam}"


def test_o_piso_da_pagina_e_o_do_produto(pagina, a02):
    """O piso da página é o MESMO objeto de texto que o produto emite.

    Se os dois divergirem, o primeiro tique troca a folha e move todo pontinho
    que a mesa viva não nomear — um salto visível na tela dela, sem causa.

    MORDE: redigitar o piso no gerador reprova.
    """
    assert a02.PISO_DAS_POSICOES in pagina
