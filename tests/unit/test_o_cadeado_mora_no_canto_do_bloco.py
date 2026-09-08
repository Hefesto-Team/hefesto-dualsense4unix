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
vêm em par: um mede onde a caixa está, o outro mede que o `data-gesto`, o
`data-campo`, o alvo de pintura e a dica continuam os mesmos — e que ela nasce
DESMARCADA, porque marcá-la no desenho afirmaria uma escolha dela que ela não
fez.

A MORDIDA
---------
Mova o `<label class="cadeado">` de volta para depois das duas seções
`hef-modo`, regere e publique. Caem os casos de posição — a caixa aparece abaixo
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
  const caixa = cad.querySelector('input[type=checkbox]');
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
    linhas_de_texto: Math.round(cx.height / parseFloat(getComputedStyle(cad).lineHeight)),
    // O GESTO — a metade que a mudança de posição não pode ter mexido
    gesto: cad.querySelector('[data-gesto]')
      ? cad.querySelector('[data-gesto]').dataset.gesto : null,
    campo: caixa ? caixa.dataset.campo : null,
    alvo: caixa ? caixa.dataset.hefAlvo : null,
    marcado_de_nascenca: caixa ? caixa.checked : null,
    tem_dica: (cad.getAttribute('title') || '').length > 0,
    rotulo: (cad.textContent || '').trim(),
  };
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
    CHEGA (o alvo `marcado` é o único que escreve `el.checked`) e `data-gesto` é
    por onde o dedo dela SAI. Um sem o outro é uma caixa que mostra e não deixa
    mudar, ou que deixa mudar e não mostra o que o daemon guardou.
    """
    assert medido["gesto"] == "cadeado", (
        f"o endereço do clique virou {medido['gesto']!r} — a caixa mudaria de "
        f"marca e não mudaria nada no produto")
    assert medido["campo"] == "cadeado", (
        f"o endereço da pintura virou {medido['campo']!r} — a caixa deixaria de "
        f"dizer o que o daemon guardou")
    assert medido["alvo"] == "marcado", (
        f"o alvo de pintura virou {medido['alvo']!r}; só `marcado` escreve "
        f"`el.checked`, e os outros nove poriam a string 'on' no `value`")


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


def test_o_cadeado_nasce_desmarcado(medido: dict) -> None:
    """Destravado é o padrão do produto; marcá-lo afirmaria uma escolha dela."""
    assert medido["marcado_de_nascenca"] is False, (
        "o cadeado nasce marcado — o desenho afirmaria uma escolha que ela não fez")


def test_o_cadeado_responde_ao_clique_no_rotulo() -> None:
    """CLICAR NO TEXTO marca a caixa — e é a metade que a foto não prova.

    Um botão que se move e nunca se clica não está entregue. O que este caso
    guarda é a associação `<label>`/`<input>`: ela é o que faz o texto inteiro
    ser área de clique, e é frágil justamente numa mudança de lugar — basta o
    `<input>` sair de dentro do `<label>` para o rótulo virar enfeite, sem
    nenhum sinal na tela e sem quebrar nenhum dos casos de geometria acima.

    O CLIQUE É NO RÓTULO, não na caixinha: clicar na caixinha funcionaria mesmo
    com a associação quebrada, e a régua daria verde sobre o defeito. A caixinha
    tem 13px; o rótulo tem o texto inteiro, e é onde o dedo dela cai.

    A PÁGINA ESTÁTICA NÃO TEM PILOTO, e por isso o que se mede aqui é a resposta
    do MOTOR — o estado da caixa antes e depois. Quem prova que o gesto chega ao
    daemon é a régua do endereço, logo acima: as duas juntas cobrem o caminho.
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
            antes = pg.eval_on_selector(".cadeado input", "e => e.checked")
            # o clique no TEXTO, pelo centro do <span> do rótulo
            pg.click(".cadeado span")
            depois = pg.eval_on_selector(".cadeado input", "e => e.checked")
            pg.click(".cadeado span")
            de_volta = pg.eval_on_selector(".cadeado input", "e => e.checked")
        finally:
            nav.close()

    assert antes is False, f"a caixa não nasceu desmarcada: {antes}"
    assert depois is True, (
        "clicar no RÓTULO do cadeado não marcou a caixa — o `<input>` saiu de "
        "dentro do `<label>` e o texto virou enfeite")
    assert de_volta is False, (
        "o segundo clique não desmarcou — a caixa responde uma vez só")
