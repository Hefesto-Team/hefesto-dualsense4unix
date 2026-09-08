#!/usr/bin/env python3
"""AS TRÊS FRASES DO PÉ: elas não custam mais layout, e cabem onde foram parar.

ORDEM DELA, 07/09/2026, olhando a aba com os quatro DualSense na mesa:

    *"navegacao tem essas 3 frases aqui na parte de baixo que quebram o
    layout"*

As três — a ressalva da D3 (``ativacao-ressalva``), a razão do portão de modo
(``modo-portao``) e o teclado na tela desta máquina (``teclado-osk``) — saíram
do pé do quadro "As opções de ativação" e foram para o ``?`` do CAMPO de que
cada uma fala, VIVAS, escritas pelo mesmo pacote a cada tique.

**POR QUE ESTA RÉGUA PRECISOU EXISTIR, e são dois defeitos, não um:**

1. *tirar do pé* é fácil de medir lendo o HTML, e o ``_conferir`` do gerador já
   o faz. O que o HTML **não** responde é quanto a tela CRESCE quando as frases
   chegam — e era esse o defeito dela: o quadro ia de 215px a 300,25px, o miolo
   passava 66px da janela e a fileira dos quatro botões terminava **41,25px
   fora**, cortada pelo rodapé;
2. e *mudar de lugar* pode perder a frase por outro caminho. Medido nesta mesma
   frente, na primeira volta: com três blocos vivos, a dica da "Função do
   teclado" ia a **356px** e o ``overflow-y`` do ``.miolo`` cortava o último
   parágrafo. A frase que se mudou para não sumir sumia de novo.

**A CENA É A DELA**, e nenhuma frase é digitada aqui: as três saem dos donos
(``a06_navegacao.RESSALVA_DOS_GLOBAIS``, ``a06_navegacao.RAZAO_DO_PORTAO`` e
``input_actions.frase_do_teclado_na_tela``). Uma cena com texto inventado
mediria uma tela que o produto não pinta — e o comprimento da frase é
exatamente o que decide se ela cabe.

**A MORDIDA**, e são duas: devolva as três ao ``ESTADOS``/``MIOLO`` do
``aba06.py`` e o primeiro caso reprova com a sobra em pixels; devolva
``modo-portao`` ao ``vivas`` da ``D_TECLADO`` e o segundo reprova nomeando a
dica que passa do fim da janela.

**O CHROME NÃO É O WEBKIT DELA**, e esta régua não finge que é: aqui se mede o
LAYOUT (caixa, fluxo e ``overflow``), que é padronizado. A prova no motor do
produto é a foto do piloto, com o daemon vivo — e ela está no relatório da
frente.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

CHROME = pathlib.Path("/usr/bin/google-chrome")
pytestmark = pytest.mark.skipif(
    not CHROME.exists(), reason="sem o Chrome do sistema — a régua não tem motor")

PAGINA = "06-navegacao.html"

#: A largura da janela do produto mais a folga do fundo. O que decide é a
#: ALTURA, e ela é fixa em `--alt-janela`: a régua não escolhe nenhuma das duas.
VIEWPORT = {"width": 1212, "height": 900}


def _a_cena_dela() -> dict[str, str]:
    """As três frases como o PACOTE as escreve — nunca digitadas aqui."""
    from hefesto_dualsense4unix.app.actions.input_actions import (
        frase_do_teclado_na_tela,
    )
    from pacotes.a06_navegacao import RAZAO_DO_PORTAO, RESSALVA_DOS_GLOBAIS

    return {
        "modo-portao": f'<span class="laranja">{RAZAO_DO_PORTAO}</span>',
        "ativacao-ressalva": RESSALVA_DOS_GLOBAIS,
        # `True` é o estado DESTA máquina, e é o caso curto. O caso longo (sem
        # teclado na tela instalado) é medido no segundo teste, que é onde o
        # comprimento decide.
        "teclado-osk": frase_do_teclado_na_tela(True),
    }


_PINTAR = """
([cena]) => {
  for (const [k, v] of Object.entries(cena))
    for (const el of document.querySelectorAll('[data-campo="' + k + '"]'))
      el.innerHTML = v;
}
"""

_MEDIR_O_MIOLO = """
() => {
  const miolo = document.querySelector('.miolo');
  const fileira = document.querySelector('.moldura-acoes');
  const quadro = [...document.querySelectorAll('.quadro')].find(
      q => (q.querySelector('.quadro-titulo') || {}).textContent
           === 'As opções de ativação');
  return {
    sobra: miolo.scrollHeight - miolo.clientHeight,
    quadro: quadro.getBoundingClientRect().height,
    fora: fileira.getBoundingClientRect().bottom
          - miolo.getBoundingClientRect().bottom,
  };
}
"""

#: Abre TODA `.dica` do painel que carrega frase viva e devolve o quanto cada
#: uma passa do fim da janela. Uma de cada vez: duas abertas ao mesmo tempo não
#: é cena que exista, e mediria a soma de duas coisas que nunca se somam.
#: QUEM RECORTA É O `.miolo`, e não a `.janela`: ele tem `overflow-y:auto`, e o
#: recorte de um ancestral que rola vale também para o descendente
#: `position:absolute` — que é o que a `.dica` é. Medir contra a janela daria
#: uma folga de 213px que não existe (a altura do rodapé mais o vão).
_MEDIR_AS_DICAS = """
() => {
  const miolo = document.querySelector('.miolo').getBoundingClientRect();
  const fora = [];
  for (const dica of document.querySelectorAll('.dica')) {
    if (!dica.querySelector('.viva')) continue;
    const linha = dica.closest('.at-linha');
    if (!linha) continue;
    // O NOME É SÓ O RÓTULO. `textContent` do `.at-rot` traz a dica inteira
    // dentro — o `?` é filho dele —, e a mensagem de falha ficava com 400
    // caracteres de explicação no lugar do nome do campo.
    const nome = [...linha.querySelector('.at-rot').childNodes]
        .filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
    dica.style.display = 'block';
    dica.style.visibility = 'visible';
    dica.style.opacity = '1';
    const r = dica.getBoundingClientRect();
    fora.push({campo: nome, alt: r.height,
               passa_do_fim: Math.round((r.bottom - miolo.bottom) * 100) / 100,
               passa_do_topo: Math.round((miolo.top - r.top) * 100) / 100});
    dica.style.display = '';
    dica.style.visibility = '';
    dica.style.opacity = '';
  }
  return fora;
}
"""


@pytest.fixture(scope="module")
def pagina():
    """A página PUBLICADA — a que o piloto carrega e que está na frente dela."""
    from playwright.sync_api import sync_playwright

    import onde

    alvo = onde.pagina(PAGINA, publicado=True)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"],
            # Sem isto o Chrome headless não pinta barra de rolagem nenhuma e
            # `scrollHeight` continua certo, mas a largura do miolo muda 15px —
            # e a altura de uma frase depende da largura em que ela quebra.
            ignore_default_args=["--hide-scrollbars"])
        try:
            pg = navegador.new_page(viewport=VIEWPORT, device_scale_factor=1)
            pg.goto(alvo.as_uri())
            pg.wait_for_load_state("networkidle")
            pg.wait_for_timeout(250)
            yield pg
        finally:
            navegador.close()


def test_as_tres_frases_nao_empurram_mais_a_fileira_para_fora(pagina):
    """Pintadas, elas custam ZERO no fluxo do painel.

    O QUE ERA, medido em 07/09 na página que ela abriu: quadro 215 -> 300,25px,
    miolo com 66px de sobra e a fileira 41,25px FORA da janela.
    """
    antes = pagina.evaluate(_MEDIR_O_MIOLO)
    pagina.evaluate(_PINTAR, [_a_cena_dela()])
    pagina.wait_for_timeout(120)
    depois = pagina.evaluate(_MEDIR_O_MIOLO)

    assert depois["quadro"] == antes["quadro"], (
        f"o quadro das opções de ativação cresceu {depois['quadro'] - antes['quadro']:.2f}px "
        f"quando as três frases chegaram ({antes['quadro']:.0f} -> "
        f"{depois['quadro']:.2f}). Elas voltaram a ocupar linha no pé.")
    assert depois["sobra"] <= 0, (
        f"o miolo passou {depois['sobra']:.2f}px da janela com as três frases "
        "pintadas — é exatamente a queixa dela de 07/09.")
    assert depois["fora"] < 0, (
        f"a fileira dos quatro botões terminou {depois['fora']:.2f}px abaixo do "
        "fim do miolo: ela fica cortada pelo rodapé, que foi o que a foto dela "
        "mostrou.")


@pytest.mark.parametrize("osk", [True, False])
def test_toda_dica_com_frase_viva_cabe_dentro_da_janela(pagina, osk):
    """O `?` que recebeu a frase tem de mostrá-la INTEIRA.

    OS DOIS ESTADOS DO `teclado-osk`, e o segundo é o que mede: com teclado na
    tela instalado a frase tem uma linha; sem ele são QUATRO, porque manda
    instalar um dos dois pacotes pelo nome. Medir só o caso curto daria verde
    sobre a máquina de quem não tem nenhum — que é justamente quem precisa ler
    a frase.

    O `.miolo` TEM `overflow-y:auto`, e é ele que corta: uma `.dica` é
    `position:absolute` e nasce para fora da caixa de propósito, mas o recorte
    do ancestral que rola vale para ela também.
    """
    from hefesto_dualsense4unix.app.actions.input_actions import (
        frase_do_teclado_na_tela,
    )

    cena = dict(_a_cena_dela(), **{"teclado-osk": frase_do_teclado_na_tela(osk)})
    pagina.evaluate(_PINTAR, [cena])
    pagina.wait_for_timeout(120)
    medidas = pagina.evaluate(_MEDIR_AS_DICAS)

    assert medidas, (
        "nenhuma `.dica` do painel carrega frase viva — as três frases que ela "
        "mandou tirar do pé não chegaram a `?` nenhum, e sumiram da tela.")
    estouradas = [m for m in medidas
                  if m["passa_do_fim"] > 0 or m["passa_do_topo"] > 0]
    assert not estouradas, (
        f"com `osk_disponivel={osk}`, estas dicas não cabem na janela: "
        + " · ".join(f"{m['campo']} ({m['alt']:.0f}px, passa {m['passa_do_fim']:+.2f} "
                     f"do fim e {m['passa_do_topo']:+.2f} do topo)"
                     for m in estouradas)
        + ". A frase que mudou de lugar para não sumir sumiria de novo.")
