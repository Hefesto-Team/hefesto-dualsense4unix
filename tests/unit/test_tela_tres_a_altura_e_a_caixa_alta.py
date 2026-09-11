#!/usr/bin/env python3
"""TELA-TRES-01 — a altura dos dois quadros da Sistema, e CABO/RÁDIO na fita.

**Duas coisas que ela pediu em 08/09/2026, e as duas se medem no navegador —
não no CSS.** Uma régua que procura a string `flex:1` na folha dá verde sobre
um `flex` que a cascata anulou três regras adiante; o que decide é a geometria
computada.

## §1 — "em sistema aumentar a altura do detalhes técnicos pra ficar igual ao
bloco à esquerda"

**Medido no Chrome, na página publicada, em 09/09/2026, ANTES da cura:**

    .avancado .lista   136px   base 700
    .avancado .log     110px   base 674

Vinte e seis pixels, e a lista das identidades de fábrica rolava enquanto
sobrava espaço embaixo dela. Com QUATRO controles na mesa são quatro linhas —
o caso dela.

A causa era `height:110px` cravado, calibrado num dia em que a lista tinha
TRÊS botões; o quarto entrou em 06/09 e levou os 26px.

## §2 — "cabo e rádio coloca maiúsculo" — REVOGADO EM 11/09/2026

**A CAIXA ALTA DA VIA SAIU.** O pedido de 08/09 foi lido como caixa alta, e três
dias depois ela leu na MESMA tela `CABO` na fita e `cabo` no cartão logo abaixo:
*"Esse tipo de coisa não pode se repetir na interface."* A regra dela sobre
maiúscula é de 30/08 e é sobre a PRIMEIRA letra; a palavra inteira nunca foi o
que esse padrão diz. A revogação mora no `topo.html` (ESQUELETO-C2), com a foto.

**O que esta função guarda agora é o inverso, e o `<span class="via">` fica:**
ele é o ENDEREÇO da via no rótulo do chip. Quem vigia a caixa alta nas dez
páginas é `scripts/check_a_maiuscula_decorativa.py`.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CHROME = pathlib.Path("/usr/bin/google-chrome")

pytestmark = pytest.mark.skipif(
    not CHROME.exists(), reason="sem o Chrome do sistema não há geometria a medir")


def _no_chrome(pagina: pathlib.Path, js: str, largura: int = 1600):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = nav.new_page(viewport={"width": largura, "height": 900})
            pg.goto(pagina.as_uri())
            pg.wait_for_timeout(250)
            return pg.evaluate(js)
        finally:
            nav.close()


def test_os_dois_quadros_da_sistema_fecham_na_mesma_linha():
    """§1 — a caixa acompanha o irmão, medida no navegador.

    **A MORDIDA:** devolva `height:110px` ao `.log` de `aba09.py`, rode o
    gerador e publique — esta linha reprova com os dois números em pixel.
    """
    import onde

    r = _no_chrome(onde.pagina("09-sistema.html", publicado=True), """() => {
      const q = s => { const e = document.querySelector(s);
        if (!e) return null;
        const b = e.getBoundingClientRect();
        return {h: Math.round(b.height), base: Math.round(b.bottom)}; };
      return {lista: q('.avancado .lista'), log: q('.avancado .log')};
    }""")

    assert r["lista"] and r["log"], (
        "a faixa «Avançado» perdeu a lista ou a caixa de detalhes técnicos")
    assert r["lista"]["base"] == r["log"]["base"], (
        f"os dois quadros da Sistema não fecham na mesma linha: a lista "
        f"termina em {r['lista']['base']}px e a caixa em {r['log']['base']}px "
        f"— {abs(r['lista']['base'] - r['log']['base'])}px de diferença")
    assert r["log"]["h"] >= 110, (
        f"a caixa encolheu abaixo do piso de 110px (está em {r['log']['h']}px) "
        f"— quatro linhas de identidade não cabem mais")


def test_a_via_do_chip_nao_sobe_de_caixa_no_navegador():
    """§2 — REVOGADO em 11/09/2026: a via do chip NÃO sobe mais de caixa.

    **ESTA FUNÇÃO MEDIA O CONTRÁRIO, e a decisão que ela guardava caiu.** O
    §2 da TELA-TRES-01 nasceu de um pedido dela de 08/09 (*"cabo e rádio coloca
    maiúsculo"*) e foi lido como CAIXA ALTA. Três dias depois ela leu, na mesma
    tela, `CABO` na fita e `cabo` no cartão logo abaixo:

        *"Leia o cabo e acordado (ambos minusculo sem   (noqa-acento: citação dela)
        iniciar de forma capitular). Esse tipo de coisa
        não pode se repetir na interface."*

    A regra da casa sobre maiúscula é dela e é de 30/08 — *"a maiúscula a
    regra é sobre a primeira letra a ser capitalizada, é o padrão do
    projeto"* —, e a caixa alta da via saiu do `topo.html` (ESQUELETO-C2).

    **O SPAN FICOU, e é o que esta função ainda guarda:** ele é o ENDEREÇO da
    via no rótulo do chip, não um gancho de estilo.

    **A MORDIDA:** devolva ao `topo.html` a regra que subia a caixa da via,
    regere e publique — a primeira asserção reprova. Tire o
    `<span class="via">` de `monta.rotulo_do_chip` e reprova a que os conta.
    """
    import onde

    r = _no_chrome(onde.pagina("04-iluminacao.html", publicado=True), """() => {
      const vias = [...document.querySelectorAll('.fita .chip .via')];
      const chips = [...document.querySelectorAll('.fita .chip')];
      return {
        quantas: vias.length,
        chips: chips.length,
        caixa: vias.map(e => getComputedStyle(e).textTransform),
        caixa_do_chip: chips.map(e => getComputedStyle(e).textTransform),
        texto: vias.map(e => e.textContent),
      };
    }""")

    assert r["quantas"] >= 1, (
        "nenhum chip da fita tem o span da via — o endereço da via sumiu do "
        "rótulo, e com ele a régua da maiúscula perde onde olhar")
    assert set(r["caixa"]) <= {"none"}, (
        f"a via do chip voltou a subir de caixa: {r['caixa']} — na tela viva "
        f"isso escreve «CABO» na fita com «cabo» no cartão logo abaixo, que é "
        f"exatamente o que ela mandou não repetir em 11/09/2026")
    assert set(r["caixa_do_chip"]) <= {"none"}, (
        f"o chip INTEIRO subiu de caixa e o nome do plástico foi junto: "
        f"{r['caixa_do_chip']}")
    #: **O TEXTO DO DESENHO É `USB`/`BT`, e não `cabo`/`rádio`** — medido em
    #: 09/09/2026. A `MESA` do mockup ainda escreve a via na língua antiga, de
    #: propósito: seis geradores a leem direto, e trocá-la mudaria o desenho
    #: aprovado sem sprint que responda por isso (é a `A-PALAVRA-MESA-SAI-01`).
    #: Na tela VIVA a mesma casa traz `cabo`/`rádio`, pelo
    #: `palavra_do_transporte` — e é por isso que a caixa alta aqui era
    #: invisível no desenho parado e gritava no produto dela.
    assert all(t.strip() for t in r["texto"]), (
        f"um chip ficou com a via vazia: {r['texto']}")


def test_o_dono_do_texto_continua_sendo_rotulo():
    """`rotulo_do_chip` MARCA o que `rotulo` devolveu — não remonta.

    Remontar o rótulo aqui seria a sexta gramática do nome de um controle
    nesta janela; as cinco que havia estão contadas na docstring do dono.

    **A MORDIDA:** faça `rotulo_do_chip` montar o texto por conta própria e a
    comparação com `rotulo(c, "curta")` reprova na primeira mudança de ordem.
    """
    import monta

    c = {"jogador": 2, "nome": "Galactic Purple", "via": "rádio", "pref": "p2"}
    marcado = monta.rotulo_do_chip(c)

    assert '<span class="via">rádio</span>' in marcado
    #: SEM A MARCA DA VIA, é byte a byte o que o dono devolve. A remoção é do
    #: PAR exato — o rótulo tem outros `</span>`, os dos separadores, e um
    #: `replace("</span>", "")` cego os comeria e a régua passaria por acaso.
    assert marcado.replace('<span class="via">rádio</span>', "rádio") == \
        monta.rotulo(c, "curta")


def test_sem_via_o_rotulo_volta_como_veio():
    """Queda silenciosa: marcar por posição fixa quebraria na ordem nova.

    **A MORDIDA:** troque o `endswith` por uma fatia de tamanho fixo e um
    controle sem transporte perde o fim do nome.
    """
    import monta

    c = {"jogador": 3, "nome": "White", "via": "", "pref": "p3"}

    assert monta.rotulo_do_chip(c) == monta.rotulo(c, "curta")
    #: `class="via"` E NÃO `<span`: o rótulo tem os spans dos separadores, e
    #: procurar a tag genérica mediria a pontuação em vez da marca.
    assert 'class="via"' not in monta.rotulo_do_chip(c)
