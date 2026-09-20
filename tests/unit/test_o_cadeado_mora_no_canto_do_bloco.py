#!/usr/bin/env python3
"""A RÉGUA DA POSIÇÃO: o cadeado do perfil mora no canto do bloco Modo.

PEDIDO DELA, 08/09/2026, olhando a aba Jogar: *"esse não trocar de perfil. Pode
colocar ele no canto superior direito do bloco tipo esse banco de provas na guia
navegação."*

Ele ficava solto LOGO ABAIXO da fileira de modos, dentro do bloco **Modo**, e
ali lia como um QUINTO modo: na coluna dos modos, no fluxo de leitura dos modos,
sem ser modo nenhum — é uma trava sobre o perfil.

O MODELO É O QUE ELA APONTOU: o *"Banco de provas: o mapa do controle ↗"* da
Navegação (`aba06.py`), no canto superior direito do bloco, na linha do título.
**A coisa que pertence ao bloco mas não é o miolo dele mora no canto.**

POR QUE GEOMETRIA, e não a ordem no fonte
------------------------------------------
A régua que o gerador tinha media a ORDEM no arquivo  (noqa-acento: verbo medir)
— *"o cadeado vem depois de
`so-desligado`"* — e por isso REPROVOU esta mudança como se fosse defeito. Ela
respondia sobre a ordem do fonte, não sobre o lugar na tela. Aqui a pergunta é
feita ao motor: *onde esta caixa está desenhada, em pixels, dentro do bloco?*

O GESTO NÃO PODE MUDAR, e é metade desta régua
-----------------------------------------------
Mudança de POSIÇÃO que muda comportamento é mudança escondida. Por isso os casos
vêm em par: um mede onde a trava está, o outro mede que o `data-gesto`, o
`data-campo`, o alvo de pintura e a dica continuam os mesmos — e que ela nasce
APAGADA, porque acendê-la no desenho afirmaria uma escolha dela que ela não fez.

A LÍNGUA MUDOU EM 19/09/2026 E ESTA RÉGUA FOI ATRÁS (`TRAVA-PILULA-01`)
-----------------------------------------------------------------------
A trava era `<label class="cadeado">` com um `<input type="checkbox">` dentro, e
virou `<button class="cadeado">` com a gramática do `.sw` da aba Controles — a
razão está escrita no dono, em `a01_jogar._cadeado`: *"um checkbox tem DOIS
estados e o produto tem três"*. O que esta régua mediu deixou de existir, e cada
medida foi reapontada para o que existe HOJE:

===========================  =======================  ==========================
o que ela mediu               o que virou              por quê
===========================  =======================  ==========================
`cad.querySelector(input)`    o próprio `.cadeado`     não há mais `<input>`
`caixa.dataset.hefAlvo`       `classe` (era `marcado`) o alvo trocou com a tag
`caixa.checked`               a classe `ligada`        a pílula acende, não marca
`input`/`label` associados    `closest('[data-gesto]')` é como o piloto resolve
`lineHeight` do rótulo        as caixas de um `Range`  `normal` num botão é `NaN`
===========================  =======================  ==========================

**O `NaN` ERA UM VERDE DISFARÇADO DE VERMELHO, e vale anotar:**
`parseFloat('normal')` é `NaN`, e `NaN == 1` é falso — a régua reprovava. Se a
comparação fosse `!= 2` ela teria PASSADO sobre uma medida que não existe. Medir
quebra de linha pelas caixas de um `Range` sobre o nó de texto responde a
pergunta de verdade, e em qualquer `display`.

A MORDIDA
---------
Mova o `<button class="cadeado">` de volta para depois das duas seções
`hef-modo`, regere e publique. Caem os casos de posição — a trava aparece abaixo
do título e à esquerda —, e os de gesto continuam passando, que é justamente o
que prova que eles medem coisas diferentes.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

CHROME = pathlib.Path("/usr/bin/google-chrome")
JOGAR = INTERFACE / "paginas" / "01-jogar.html"  # (noqa-acento) nome de PASTA

#: A pergunta ao motor. Tudo aqui é medida ou endereço; nenhuma coordenada
#: esperada está escrita — as comparações são entre elementos da MESMA página.
O_QUE_O_MOTOR_DESENHA = """() => {
  const cad = document.querySelector('.cadeado');
  if (!cad) return {erro: 'a página não tem `.cadeado`'};
  const topo = cad.closest('.quadro-topo');
  const bloco = cad.closest('.quadro');
  if (!bloco) return {erro: 'o cadeado não está dentro de nenhum `.quadro`'};
  const titulo = bloco.querySelector('.quadro-titulo');
  const corpo = bloco.querySelector('.quadro-corpo');
  const modos = [...bloco.querySelectorAll('.hef-modo')];
  const cx = cad.getBoundingClientRect();
  const bx = bloco.getBoundingClientRect();
  const tx = titulo.getBoundingClientRect();
  // QUEM RECEBE O CLIQUE é quem o piloto acha com `closest`, e não um filho:
  // desde 19/09 o `data-gesto` mora no PRÓPRIO `<button class="cadeado">`.
  const dono = cad.closest('[data-gesto]');
  // A QUEBRA DE LINHA, medida pelas caixas que o nó de TEXTO ocupa. O
  // `lineHeight` de um `<button>` é `normal`, e `parseFloat('normal')` é `NaN`.
  const texto = [...cad.childNodes].find(
    n => n.nodeType === 3 && n.textContent.trim());
  const range = document.createRange();
  if (texto) range.selectNodeContents(texto);
  return {
    // ONDE ELE ESTÁ
    na_linha_do_titulo: topo !== null,
    dentro_de_alguma_secao_do_interruptor:
      modos.some(m => m.contains(cad)),
    dentro_do_corpo: corpo ? corpo.contains(cad) : false,
    titulo_do_bloco: (titulo.textContent || '').trim(),
    // as distâncias que dizem "canto superior direito", medidas contra o BLOCO
    folga_a_direita: Math.round(bx.right - cx.right),
    folga_a_esquerda: Math.round(cx.left - bx.left),
    // o topo do cadeado contra o topo do título: mesma linha = mesma altura
    desvio_vertical_do_titulo: Math.round(
      (cx.top + cx.height / 2) - (tx.top + tx.height / 2)),
    altura_do_cadeado: Math.round(cx.height),
    altura_do_titulo: Math.round(tx.height),
    altura_do_topo: topo ? Math.round(topo.getBoundingClientRect().height) : null,
    linhas_de_texto: texto ? range.getClientRects().length : null,
    // O GESTO — a metade que a mudança de posição não pode ter mexido
    gesto: dono ? dono.dataset.gesto : null,
    o_dono_do_gesto_e_o_proprio: dono === cad,
    campo: cad.dataset.campo || null,
    alvo: cad.dataset.hefAlvo || null,
    classe_que_acende: cad.dataset.hefClasse || null,
    acende_quando: cad.dataset.hefQuando || null,
    aceso_de_nascenca: cad.classList.contains(cad.dataset.hefClasse || 'on'),
    tem_dica: (cad.getAttribute('title') || '').length > 0,
    rotulo: (cad.textContent || '').trim(),
  };
}"""

#: O ESPIÃO DO CLIQUE — ele usa **o mesmo `closest` do piloto**, e de propósito:
#: a régua não pode ter uma segunda maneira de achar o dono do gesto, senão
#: passa a medir a si mesma em vez do caminho que o produto percorre.
O_CAMINHO_DO_CLIQUE = """() => {
  window.__recados = [];
  const ouvir = (ev) => {
    const alvo = ev.target.closest('[data-gesto]');
    window.__recados.push({
      tipo: ev.type,
      gesto: alvo ? alvo.dataset.gesto : null,
      // `false` quer dizer que o clique caiu num FILHO, e que só o `closest` o
      // levou ao dono — é o que o pontinho tem de provar.
      no_proprio_cadeado: ev.target.classList.contains('cadeado'),
    });
  };
  document.addEventListener('click', ouvir, true);
  document.addEventListener('change', ouvir, true);
  const cx = document.querySelector('.cadeado').getBoundingClientRect();
  return {largura: cx.width, altura: cx.height};
}"""


@pytest.fixture(scope="module")
def medido() -> dict:
    """O que o Chrome desenha na aba Jogar PUBLICADA — a que o produto carrega."""
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    assert JOGAR.is_file(), (
        f"{JOGAR} não existe — a aba Jogar publicada é o alvo desta régua, e "
        f"sem ela todos os casos passariam por ausência")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = nav.new_page(viewport={"width": 1600, "height": 900})
            pg.goto(JOGAR.as_uri())
            pg.wait_for_load_state("networkidle")
            saida = pg.evaluate(O_QUE_O_MOTOR_DESENHA)
        finally:
            nav.close()
    assert "erro" not in saida, saida.get("erro")
    return dict(saida)


# ---------------------------------------------------------------------------
# 1. ONDE ELE ESTÁ — o pedido dela, em pixels
# ---------------------------------------------------------------------------
def test_o_cadeado_esta_no_bloco_modo(medido: dict) -> None:
    """É o bloco **Modo** — não outro que por acaso tenha um canto livre."""
    assert medido["titulo_do_bloco"].startswith("Modo"), (
        f"o cadeado está no bloco {medido['titulo_do_bloco']!r}. Ela pediu o "
        f"canto do bloco Modo, que é onde a trava de perfil pertence.")


def test_o_cadeado_esta_na_linha_do_titulo(medido: dict) -> None:
    """Na linha do título, e não no miolo — que é o que o tira de "quinto modo".

    Os dois lados da mesma medida: ele está DENTRO do `.quadro-topo` e FORA do
    `.quadro-corpo`. O primeiro sozinho passaria se alguém aninhasse um segundo
    `.quadro-topo` no meio do corpo.
    """
    assert medido["na_linha_do_titulo"], (
        "o cadeado não está no `.quadro-topo`. Embaixo dos modos ele lê como um "
        "quinto modo — foi o que ela viu.")
    assert not medido["dentro_do_corpo"], (
        "o cadeado está dentro do `.quadro-corpo`, isto é, no miolo do bloco.")


def test_o_cadeado_esta_encostado_na_direita(medido: dict) -> None:
    """*"canto superior DIREITO"* — e a medida é contra o bloco, não um número.

    A folga da direita é a do `padding` do `.quadro-topo`; a da esquerda é o
    vão inteiro que o `margin-left:auto` come. Comparar as duas responde "está
    à direita?" sem nenhuma coordenada digitada aqui, que envelheceria no dia em
    que a janela mudar de largura — e ela acabou de mudar.
    """
    assert medido["folga_a_esquerda"] > medido["folga_a_direita"] * 5, (
        f"o cadeado não está encostado na direita: sobra "
        f"{medido['folga_a_esquerda']}px à esquerda e "
        f"{medido['folga_a_direita']}px à direita.")


def test_o_cadeado_nao_empurrou_a_linha_do_titulo(medido: dict) -> None:
    """A altura do `.quadro-topo` continua sendo a do título — 17px.

    ESTE CASO TEM PREÇO MEDIDO, e não é meu: a `.porta` da Navegação nasceu com
    19px, dois a mais que o `.quadro-titulo`, e **663 das 733 caixas daquela aba
    desceram 2px**. O `.quadro-topo` é `align-items:center`, então a altura dele
    é a do filho mais alto: qualquer coisa mais alta que o título move o bloco
    inteiro, e as abas vizinhas não.

    A QUEBRA DE LINHA SE MEDE NO NÓ DE TEXTO, pelas caixas de um `Range` — a
    conta velha (`altura ÷ lineHeight`) devolvia `NaN` desde que a trava virou
    `<button>`, porque o `lineHeight` de um botão é `normal`.
    """
    assert medido["altura_do_cadeado"] <= medido["altura_do_titulo"], (
        f"o cadeado ({medido['altura_do_cadeado']}px) é mais alto que o título "
        f"({medido['altura_do_titulo']}px) e empurra a linha inteira para baixo.")
    assert medido["linhas_de_texto"] == 1, (
        f"o rótulo do cadeado quebrou em {medido['linhas_de_texto']} linhas — "
        f"duas linhas aqui estouram a altura do título e derrubam o bloco.")


def test_o_cadeado_fica_fora_das_duas_secoes_do_interruptor(medido: dict) -> None:
    """`so-ligado` e `so-desligado` trocam com o Hefesto; o cadeado vale nos dois.

    Dentro de uma delas a caixa sumiria justamente no Modo Nativo, onde a troca
    automática de perfil continua valendo — e sumiria em SILÊNCIO. Era o
    requisito que a régua velha do gerador defendia, e ele não mudou; o que
    mudou foi como se mede.
    """
    assert not medido["dentro_de_alguma_secao_do_interruptor"], (
        "o cadeado está dentro de uma seção `hef-modo` — ele sumiria da tela "
        "na outra posição do interruptor.")


# ---------------------------------------------------------------------------
# 2. O GESTO NÃO MUDOU — a outra metade, e sem ela a mudança é escondida
# ---------------------------------------------------------------------------
def test_o_gesto_do_cadeado_atravessou_a_mudanca(medido: dict) -> None:
    """Mudou o LUGAR e mais nada: o endereço do clique e o da pintura são os mesmos.

    OS DOIS LADOS, e são o par de sempre: `data-campo` é por onde a verdade
    CHEGA e `data-gesto` é por onde o dedo dela SAI. Um sem o outro é uma trava
    que mostra e não deixa mudar, ou que deixa mudar e não mostra o que o daemon
    guardou.

    E O ALVO É `classe` DESDE 19/09, com as DUAS metades que ele exige: sem o
    `data-hef-classe` o piloto acende `on`, que folha nenhuma pinta; sem o
    `data-hef-quando` o alvo vira BOOLEANO (`hefesto_vivo`: *"sem
    `data-hef-quando` o alvo é booleano"*) e a pílula acenderia com `DESLIGADO`
    e com o travessão, que é a tela afirmando o contrário do que leu. Por isso
    as três se medem juntas — e a palavra do `quando` sai do DONO
    (`a01_jogar.CADEADO_LIGADO`), nunca digitada aqui.
    """
    from hefesto_dualsense4unix.interface.pacotes.a01_jogar import CADEADO_LIGADO

    assert medido["gesto"] == "cadeado", (
        f"o endereço do clique virou {medido['gesto']!r} — a trava mudaria de "
        f"cor e não mudaria nada no produto")
    assert medido["o_dono_do_gesto_e_o_proprio"], (
        "o `data-gesto` saiu do `.cadeado` e foi parar num ancestral: o piloto "
        "acharia o elemento errado com o `closest`, e a piscada verde do recibo "
        "acenderia em cima de outra coisa")
    assert medido["campo"] == "cadeado", (
        f"o endereço da pintura virou {medido['campo']!r} — a trava deixaria de "
        f"dizer o que o daemon guardou")
    assert medido["alvo"] == "classe", (
        f"o alvo de pintura virou {medido['alvo']!r}; a trava é uma pílula "
        f"desde 19/09, e quem acende pílula é o alvo `classe`")
    assert medido["classe_que_acende"] == "ligada", (
        f"a classe da pintura virou {medido['classe_que_acende']!r}; sem ela o "
        f"piloto acende `on`, e a folha desta aba pinta `.cadeado.ligada`")
    assert medido["acende_quando"] == CADEADO_LIGADO, (
        f"a pílula acende com {medido['acende_quando']!r} e o dono emite "
        f"{CADEADO_LIGADO!r}. Vazio é pior: o alvo `classe` sem "
        f"`data-hef-quando` é BOOLEANO, e a trava acenderia também com "
        f"`DESLIGADO` e com o travessão")


def test_a_palavra_e_a_da_janela_antiga(medido: dict) -> None:
    """O rótulo e a dica continuam os que ela já leu — não se reescreve texto dela.

    O literal tem dono em `pacotes/a01_jogar`, e ele veio palavra por palavra do
    `Gtk.CheckButton` de `home_actions._build_home`. Texto NOVO de tela é decisão
    dela; texto que ela já leu, não.
    """
    from hefesto_dualsense4unix.interface.pacotes.a01_jogar import CADEADO_ROTULO

    assert medido["rotulo"] == CADEADO_ROTULO, (
        f"o rótulo na tela é {medido['rotulo']!r} e o dono diz "
        f"{CADEADO_ROTULO!r}")
    assert medido["tem_dica"], "o cadeado ficou sem a razão na dica"


def test_o_cadeado_nasce_apagado(medido: dict) -> None:
    """Destravado é o padrão do produto; acendê-lo afirmaria uma escolha dela.

    A PÍLULA NASCE SEM A CLASSE, que é o `el.checked === false` desta língua:
    quem acende é o piloto, a partir do `autoswitch_locked` do daemon. Um
    desenho que já trouxesse `class="cadeado ligada"` diria TRAVADO antes de
    qualquer tique — e continuaria dizendo sobre um estado que ninguém leu, que
    é o terceiro estado que a pílula nasceu para não mentir.
    """
    assert medido["aceso_de_nascenca"] is False, (
        "o cadeado nasce aceso — o desenho afirmaria uma escolha que ela não fez")


def test_o_clique_no_rotulo_chega_ao_dono_do_gesto() -> None:
    """CLICAR NO TEXTO e no pontinho chega ao `data-gesto` — e em `click`.

    Um botão que se move e nunca se clica não está entregue. O que este caso
    guardava era a associação `<label>`/`<input>`, e ela morreu com a caixa em
    19/09: o que faz o texto inteiro ser área de clique agora é o próprio
    `<button>`, e o que leva o clique do `<span class="p">` até o dono é o
    `ev.target.closest('[data-gesto]')` do piloto (`hefesto_vivo`, o ouvinte
    único). É esse caminho que se mede aqui, com o mesmo `closest`.

    E A METADE NOVA É O NOME DO EVENTO, que é o que custou caro: **um
    `<button>` NÃO emite `change`** — só `<input>`, `<select>` e `<textarea>`.
    O `a01_jogar.cadeado` filtra por `click` por causa disso, e deixá-lo em
    `change` faria o gesto voltar cedo em TODO clique: a tela pisca verde e o
    disco não muda. Esta régua reprova nos DOIS sentidos — se o `change`
    voltasse a sair da trava, o produto teria dois eventos por gesto de novo.

    A PÁGINA ESTÁTICA NÃO TEM PILOTO, e por isso o que se mede é o caminho do
    evento no MOTOR, não o efeito. Quem prova que o gesto chega ao daemon é a
    régua do endereço, logo acima: as duas juntas cobrem o caminho.

    A MORDIDA: tire o `data-gesto` do `<button>` e ponha num `<div>` em volta —
    os dois cliques passam a chegar com o gesto certo pelo `closest`, e é o
    `o_dono_do_gesto_e_o_proprio` da régua de cima que reprova. Troque o
    `<button>` por um `<input type="checkbox">` e é AQUI que reprova, com um
    `change` na lista.
    """
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = nav.new_page(viewport={"width": 1600, "height": 900})
            pg.goto(JOGAR.as_uri())
            pg.wait_for_load_state("networkidle")
            caixa = pg.evaluate(O_CAMINHO_DO_CLIQUE)
            # O CLIQUE NO TEXTO, encostado na borda direita da pílula — é lá que
            # o rótulo está, e é onde o dedo dela cai. Clicar no centro poderia
            # acertar o pontinho, que é o outro caso, logo abaixo.
            pg.click(".cadeado", position={"x": caixa["largura"] - 6,
                                           "y": caixa["altura"] / 2})
            # E O CLIQUE NO PONTINHO, que é o filho: sem o `closest` ele chegaria
            # ao piloto como um clique em nada. O teto é de 3s e não o padrão de
            # 30s de propósito: um pontinho que sumiu ou ficou invisível é
            # defeito, e defeito tem de reprovar depressa.
            pg.click(".cadeado .p", timeout=3000)
            recados = pg.evaluate("() => window.__recados")
        finally:
            nav.close()

    assert len(recados) == 2, (
        f"a régua esperava dois eventos (o texto e o pontinho) e viu "
        f"{len(recados)}: {recados!r}")
    assert [r["gesto"] for r in recados] == ["cadeado", "cadeado"], (
        f"um dos cliques não chegou ao dono do gesto: {recados!r}. O clique no "
        f"pontinho depende do `closest`; o do texto, de o `data-gesto` estar no "
        f"elemento que recebe o clique")
    assert [r["tipo"] for r in recados] == ["click", "click"], (
        f"a trava emitiu {[r['tipo'] for r in recados]!r}. O gesto "
        f"`a01_jogar.cadeado` filtra por `click` porque um `<button>` não emite "
        f"`change` — um `change` aqui quer dizer que a caixa voltou, e com ela "
        f"a dupla entrega do mesmo gesto")
    assert [r["no_proprio_cadeado"] for r in recados] == [True, False], (
        f"a régua está medindo a si mesma: {recados!r}. O primeiro clique tem "
        f"de cair no PRÓPRIO `.cadeado` (o texto) e o segundo num FILHO (o "
        f"pontinho) — se os dois caem no mesmo elemento, o `closest` nunca foi "
        f"exercitado e este caso daria verde sobre um pontinho que o piloto "
        f"não alcança")
