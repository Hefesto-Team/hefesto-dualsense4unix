#!/usr/bin/env python3
"""A RÉGUA DA LARGURA: o desenho acompanha a janela, até um teto.

DECISÃO DELA, 08/09/2026, com o produto instalado e os quatro DualSense na mesa.
O que ela disse foi o sintoma: *"o background fica completamente preto"*.

MEDIDO, NÃO ERA FALTA DE FUNDO. O `body` do `topo.html` já pinta `#11121a`; o
que ela via era a cor da casa, só que MUITA — a `.janela` parava em 1180px
enquanto a janela maximizada tem ~1900, deixando ~360px de casa de cada lado. A
recomendação foi levada a ela e ela aprovou: *"eu confio em vc, manda ver"*.

O QUE ESTA RÉGUA GUARDA, e o que ela deliberadamente NÃO guarda
----------------------------------------------------------------
Ela guarda a DECISÃO: **estica, com teto**. As três metades disso são
mensuráveis e estão aqui — cresce com a janela, para num teto, e continua
encolhendo até o piso.

Ela NÃO crava o 1600 como dogma. O número é hipótese com razão escrita, e a
razão está no `topo.html`: as dez páginas foram medidas em 1180, 1400, 1600 e
1900, nada quebrou em nenhuma, a coluna por jogador da Gatilhos ganhou **46%**
(228 -> 333px) e o preço de leitura dobrou em vez de triplicar. Quem remedir e
achar melhor troca o número **e** a razão; o que esta régua reprova é o dia em
que a largura voltar a ser FIXA, ou crescer sem limite.

O PISO NÃO MUDOU, e é a parte que se lê errado
-----------------------------------------------
`gui/ponte_da_tela.LARGURA_DO_DESENHO` continua 1212 (`16+1180+16`), e continua
certo: 1180 é o ponto abaixo do qual as colunas em px do miolo não têm para onde
encolher. O que mudou é que **o CSS não escreve mais esse número** — quem segura
o piso agora é só o `set_size_request` da janela GTK. Esta régua mede isso de
propósito, para que apagar aquela linha deixe de ser barato.

A MORDIDA
---------
Troque `width:min(100%,1600px)` por `width:1180px` no `interface/topo.html`,
regere e publique. Cai o primeiro caso, com o desenho parado em 1180 numa janela
de 1600 — que é a sobra que ela fotografou. Troque por `width:100%` e cai o
segundo, o do teto.
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
PUBLICADO = INTERFACE / "paginas"  # (noqa-acento) nome de PASTA; caminho não leva acento

#: As larguras de JANELA em que a página é medida, e o que cada uma pergunta:
#:
#:   1212  o PISO — o que `ponte_da_tela.LARGURA_DO_DESENHO` pede à janela
#:   1450  a janela crescendo, ainda BEM abaixo do teto: aqui se vê se ela segue
#:   1932  MAIOR que o teto — a TV dela, maximizada: aqui se vê se ela para
#:
#: O `body{padding:16px}` come 32 de cada uma, e é por isso que 1212 devolve
#: 1180 — a largura exata do desenho que ela aprovou.
#:
#: **O 1450 NÃO PODE SER 1632.** A primeira volta desta régua usou 1632, que é
#: `1600 + 32`, e ela media o TETO duas vezes  (noqa-acento: verbo medir)
#: em vez de medir o crescimento uma
#: vez: naquela largura o desenho para pelo teto, e um `width:1600px` FIXO
#: passaria pelos dois casos. Uma medida no meio do caminho é o que separa
#: "acompanha a janela" de "é grande".
PISO, MEIO, ACIMA_DO_TETO = 1212, 1450, 1932
RESPIRO = 32  # o `body{padding:16px}` dos dois lados

O_QUE_O_MOTOR_DESENHA = """() => {
  const j = document.querySelector('.janela');
  if (!j) return {erro: 'a página não tem `.janela`'};
  const d = document.documentElement;
  return {
    largura: Math.round(j.getBoundingClientRect().width),
    rolagem_lateral: d.scrollWidth > d.clientWidth,
    // nenhuma caixa pode sair da moldura em largura nenhuma
    fora_da_moldura: [...j.querySelectorAll('*')].filter(e => {
      const s = getComputedStyle(e);
      if (s.display === 'none' || s.visibility === 'hidden') return false;
      const r = e.getBoundingClientRect(), m = j.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && (r.right > m.right + 1 || r.left < m.left - 1);
    }).length,
  };
}"""


def _abas() -> list[pathlib.Path]:
    return sorted(PUBLICADO.glob("[0-9][0-9]-*.html"))


@pytest.fixture(scope="module")
def medido() -> dict:
    """Cada aba publicada, nas três larguras. Uma abertura de Chrome para todas."""
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    paginas = _abas()
    assert len(paginas) >= 10, (
        f"achei {len(paginas)} abas em {PUBLICADO} — o caminho mudou? "
        f"Uma régua de largura que mede zero página passa sobre tudo.")

    from playwright.sync_api import sync_playwright

    from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos

    # O QUE O PRODUTO ESCONDE VEM DA FOLHA, e não deste arquivo. Sem isto a
    # `.nota` — a legenda do mockup, que o piloto apaga — deixa a página mais
    # alta que o viewport, o Chrome pinta a barra de rolagem vertical, e ela come
    # **15px da largura**: a primeira volta desta régua mediu 1165 onde o desenho
    # tem 1180 e reprovou a cura por causa de uma barra que o produto não mostra.
    # É a mesma cura que o `interface/olhar.py` já tinha, e pela mesma razão.
    esconde = "".join(f"{s}{{display:none}}" for s in seletores_escondidos())

    fora: dict = {}
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"],
                                 ignore_default_args=["--hide-scrollbars"])
        try:
            for larg in (PISO, MEIO, ACIMA_DO_TETO):
                pg = nav.new_page(viewport={"width": larg, "height": 1000})
                for p in paginas:
                    pg.goto(p.as_uri())
                    pg.wait_for_load_state("networkidle")
                    pg.add_style_tag(content=esconde)
                    fora.setdefault(p.name, {})[larg] = pg.evaluate(O_QUE_O_MOTOR_DESENHA)
                pg.close()
        finally:
            nav.close()
    return fora


#: A aba 07 é de OUTRA leva, e por isso ela fica fora dos casos de largura.
#: **Isto é declaração, não silêncio:** ela não foi regerada nesta frente (a
#: posse dela é de outra frente em voo), então a página publicada dela ainda
#: carrega o `topo.html` de ontem e continua parada em 1180. Quem integrar roda
#: os dez geradores no fim, e ela entra sozinha. Se ela sair desta lista sem que
#: alguém regere, os casos abaixo reprovam — que é o que se quer.
DE_OUTRA_LEVA = {"07-lancadores.html"}


def _nossas(medido: dict) -> dict:
    return {n: r for n, r in medido.items() if n not in DE_OUTRA_LEVA}


def test_o_desenho_acompanha_a_janela(medido: dict) -> None:
    """Numa janela maior que o piso, o desenho cresce junto — não sobra casa."""
    parados = {n: r[MEIO]["largura"] for n, r in _nossas(medido).items()
               if r[MEIO]["largura"] != MEIO - RESPIRO}
    assert not parados, (
        f"numa janela de {MEIO}px o desenho destas abas parou antes da borda: "
        f"{parados}. É a sobra que ela fotografou — *'o background fica "
        f"completamente preto'* —, e o preto é a cor da casa aparecendo demais.")


def test_o_desenho_para_no_teto(medido: dict) -> None:
    """E ele PARA: esticar sem limite alonga a linha até ela deixar de se ler.

    O teto é o que separa a decisão dela de um `width:100%`. Sem ele, o registro
    da Sistema chega a 294 caracteres por linha na TV dela — medido em 08/09,
    contra os 157 do desenho que ela aprovou.
    """
    sem_teto = {n: r[ACIMA_DO_TETO]["largura"] for n, r in _nossas(medido).items()
                if r[ACIMA_DO_TETO]["largura"] > ACIMA_DO_TETO - RESPIRO - 1}
    assert not sem_teto, (
        f"numa janela de {ACIMA_DO_TETO}px estas abas foram até a borda: "
        f"{sem_teto}. A decisão dela é esticar COM TETO.")
    # e o teto é o mesmo nas nossas — uma aba com teto próprio é divergência calada
    tetos = {r[ACIMA_DO_TETO]["largura"] for r in _nossas(medido).values()}
    assert len(tetos) == 1, (
        f"as abas pararam em larguras diferentes: {sorted(tetos)}. O teto mora "
        f"numa linha só, no `interface/topo.html`.")


def test_no_piso_a_janela_entrega_o_desenho_inteiro(medido: dict) -> None:
    """No piso de `ponte_da_tela.LARGURA_DO_DESENHO`, o desenho cabe inteiro.

    O 1212 é `16+1180+16`, e o 1180 é a largura do desenho que ela aprovou.
    Este caso é o que faz o piso continuar sendo um número com razão, agora que
    o CSS não o escreve mais.
    """
    from hefesto_dualsense4unix.gui.ponte_da_tela import LARGURA_DO_DESENHO

    assert LARGURA_DO_DESENHO == PISO, (
        f"o piso da janela virou {LARGURA_DO_DESENHO} e esta régua mede {PISO}")
    curtas = {n: r[PISO]["largura"] for n, r in _nossas(medido).items()
              if r[PISO]["largura"] != PISO - RESPIRO}
    assert not curtas, (
        f"no piso de {PISO}px o desenho não ficou com os {PISO - RESPIRO}px que "
        f"ela aprovou: {curtas}")


def test_nenhuma_aba_rola_de_lado_nem_perde_caixa(medido: dict) -> None:
    """Nas três larguras, nas DEZ: zero rolagem lateral e zero caixa fora da moldura.

    A aba 07 entra AQUI de propósito, e é a diferença entre este caso e os de
    cima: ela não foi regerada, logo a largura dela não pode ser cobrada — mas a
    integridade pode, e ela vale para o esqueleto velho tanto quanto para o novo.
    """
    ruins = []
    for nome, por_larg in medido.items():
        for larg, r in por_larg.items():
            if r["rolagem_lateral"]:
                ruins.append(f"{nome} @ {larg}px: a página rola de lado")
            if r["fora_da_moldura"]:
                ruins.append(f"{nome} @ {larg}px: {r['fora_da_moldura']} caixa(s) "
                             f"fora da moldura")
    assert not ruins, "\n  ".join(["a grade não aguentou a largura:", *ruins])
