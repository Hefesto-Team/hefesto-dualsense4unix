#!/usr/bin/env python3
"""A BORDA DA ABA 02 VESTE O CONTROLE DELE — no WebKit, e não só em Python.

A LEI É DELA, 03/09/2026:

    *"imagina que cada pessoa tenha um dualsense diferente. eu mapeei as cores,
    glifos, controles, id e tudo mais. é pro projeto usar esse meu trabalho.
    nada hardcoded. eu quero que cada user ao usar seu controle se toque disso
    que o app se adaptou ao controle dele"*

O TESTE QUE PROVA A LEI não é "os dois controles dela pintam certo" — os dois
estão no desenho, e uma cura falsa passaria neles. É **um modelo que o desenho
NÃO tem**: Nova Pink, Astro Bot, Sterling Silver. Se só os quatro do mockup
funcionarem, trocou-se um cravado por outro.

POR QUE NUM WEBKIT DE VERDADE, e não medindo a folha em Python: o que decide a
cor é a CASCATA, e a cascata é do motor. A página tem uma folha principal cheia
de `var(--plastico)` e a folha viva endereçada logo depois; reimplementar a
resolução em Python seria testar a reimplementação — *"medir contra a biblioteca
errada produz alarme convincente e falso"*. Aqui a pergunta é feita ao
`getComputedStyle` do mesmo WebKitGTK que a janela dela usa.

A JANELA É `Gtk.OffscreenWindow` por duas razões, e as duas estão escritas nesta
casa: sob Xvfb não há gerenciador de janelas e uma `Gtk.Window` fica 1x1 para
sempre; e ela tem UMA tela — janela de teste não nasce na frente dela.

O QUE MUDOU DO LADO DO PRODUTO, e é o que este arquivo guarda: até 03/09/2026
`a02_controles.cor_da_borda` recebia o NOME de tela e o procurava em
`integrations/cor_do_plastico.NOMES_DE_FABRICA` (21 linhas) para chegar a `TONS`
(21 hexas, **vinte deles aproximados**). Agora ela recebe o SLUG — o `id` da
linha dela em `docs/data/cores-do-dualsense.csv` — e pergunta ao mesmo dono que
pinta o chip da fita, `monta.cor_da_zona`.

E A MORDIDA RODA — :func:`test_a_mordida_com_a_tabela_velha_a_tela_erra_a_cor`
monta a folha pela regra ANTIGA e mede a mesma tela: o Nova Pink sai
`rgb(238, 126, 166)` em vez do `rgb(227, 91, 140)` do mapa dela, e o
Marvel's Spider-Man 2 perde a borda inteira. Régua que passa com a cura arrancada
não mede nada.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"

#: A BANCADA, e não o publicado. É onde o desenho de HOJE está — o publicado
#: ainda tem a cura de duas folhas de 03/09 às 01h31, e apontar para ele daria
#: verde sobre página congelada, que é a armadilha mais cara do
#: `COMO-OLHAR-A-TELA.md`.
BANCADA = RAIZ / "mockup/02-controles.html"

#: OS TRÊS QUE O DESENHO NÃO TEM. O mockup traz Cosmic Red (`p1`) e Starlight
#: Blue (`p2`); estes três não aparecem em lugar nenhum da página, então uma cor
#: certa na tela só pode ter vindo do mapa dela.
#:
#: O `rgb(…)` é o que o WebKit devolve; o hexa ao lado é o `casca_esq` do
#: `docs/data/cores-do-dualsense.csv`, que é o que ela amostrou.
FORA_DO_DESENHO = {
    "nova-pink": ("#e35b8c", "rgb(227, 91, 140)"),
    "astro-bot": ("#e8e4dc", "rgb(232, 228, 220)"),
    "sterling-silver": ("#c5c8cc", "rgb(197, 200, 204)"),
}

#: O que o desenho crava, e nenhum destes pode sobreviver a um aparelho outro.
DO_DESENHO = ("rgb(174, 51, 90)", "rgb(126, 184, 212)")

ROTEIRO = """
(function(){
  const fora = {};
  const p1 = document.querySelector('.ctl[data-controle="p1"]');
  const p2 = document.querySelector('.ctl[data-controle="p2"]');
  const chip = document.querySelector('.fita .chip[for="c-p1"]');
  fora.virgem_p1 = getComputedStyle(p1).borderTopColor;
  fora.virgem_p2 = getComputedStyle(p2).borderTopColor;
  fora.medidas = {};
  for(const [nome, css] of Object.entries(FOLHAS_AQUI)){
    window.__hef.pintar({mesa: {'plastico-css': css}});
    fora.medidas[nome] = {
      p1: getComputedStyle(p1).borderTopColor,
      p2: getComputedStyle(p2).borderTopColor,
      chip: chip ? getComputedStyle(chip).borderTopColor : ''
    };
  }
  return JSON.stringify(fora);
})()
"""


def _bootstrap() -> str:
    """O BOOTSTRAP lido do FONTE do piloto, e não importado.

    Importar `hefesto_vivo` arrastaria a janela GTK inteira para dentro do
    teste. É como os outros testes do pintor fazem, e pela mesma razão.
    """
    import re

    achou = re.search(r'^BOOTSTRAP = r"""(.*?)"""$',
                      PILOTO.read_text(encoding="utf-8"), re.S | re.M)
    assert achou, "o piloto perdeu o BOOTSTRAP — não há o que testar"
    return achou.group(1)


def _rodar_no_webkit(folhas: dict[str, str]) -> dict:
    """Abre a bancada num WebKit offscreen, instala o pintor e mede a borda."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    roteiro = ROTEIRO.replace("FOLHAS_AQUI", json.dumps(folhas))
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def guardou(v: object, res: object) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def instalou(v: object, res: object) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:  # pragma: no cover — só quando o bootstrap quebra
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v: object, evento: object) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(_bootstrap(), -1, None, None, None, instalou)

    view.connect("load-changed", carregou)
    view.load_uri(BANCADA.as_uri())
    GLib.timeout_add(30000, Gtk.main_quit)
    Gtk.main()
    janela.destroy()
    assert saiu, "o WebKit não respondeu em 30 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return dict(json.loads(saiu[0]))


def _folha_velha(mesa: list[dict[str, str]]) -> str:
    """A folha pela REGRA ANTIGA — nome de tela → `NOMES_DE_FABRICA` → `TONS`.

    É a cura ARRANCADA, escrita aqui para que a mordida rode em vez de morar num
    comentário. Ela repete a antiga de propósito: o que se mede é a TELA que
    aquela regra produzia.
    """
    from hefesto_dualsense4unix.integrations.cor_do_plastico import (
        cor_do_nome,
        tom_para_a_borda,
    )
    from pacotes import a02_controles as a02

    regras = [a02.PISO_DA_FOLHA]
    for c in mesa:
        achada = cor_do_nome(c.get("nome") or "")
        cor = tom_para_a_borda(achada.tom if achada else "") or a02.BORDA_SEM_COR
        regras.append(f'.ctl[data-controle="{c["pref"]}"],'
                      f'.fita .chip[for="c-{c["pref"]}"]{{--plastico:{cor}}}')
    return "\n".join(regras)


@pytest.fixture(scope="module")
def medido() -> dict:
    from pacotes import a02_controles as a02

    folhas = {
        slug: a02.folha_do_plastico([{"pref": "p1", "cor": slug}])
        for slug in FORA_DO_DESENHO
    }
    # A MESA DELA DE HOJE, com os dois: P1 White no cabo, P2 Galactic Purple no
    # rádio. Ela entra aqui porque é a única mesa que ELA vê, e porque é a que
    # prova que o assento 2 também obedece.
    folhas["mesa-dela"] = a02.folha_do_plastico([
        {"pref": "p1", "cor": "white"},
        {"pref": "p2", "cor": "galactic-purple"},
    ])
    # A MORDIDA, pela regra velha, na mesma ida ao motor.
    folhas["mordida-nova-pink"] = _folha_velha([{"pref": "p1", "nome": "Nova Pink"}])
    folhas["mordida-spider"] = _folha_velha(
        [{"pref": "p1", "nome": "Marvel's Spider-Man 2"}])
    return _rodar_no_webkit(folhas)


# ---------------------------------------------------------------------------
# 1. A BANCADA nasce com o desenho — sem isto o resto não prova nada
# ---------------------------------------------------------------------------
def test_a_pagina_virgem_mostra_o_desenho_que_ela_aprovou(medido: dict) -> None:
    """Se a página já nascesse neutra, qualquer cor depois pareceria cura."""
    assert medido["virgem_p1"] == DO_DESENHO[0], (
        f"o `p1` da bancada devia nascer Cosmic Red e nasceu {medido['virgem_p1']}")
    assert medido["virgem_p2"] == DO_DESENHO[1]


# ---------------------------------------------------------------------------
# 2. A LEI — um modelo que o desenho NÃO tem chega à tela na cor dela
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("slug", sorted(FORA_DO_DESENHO))
def test_um_modelo_fora_do_desenho_pinta_a_borda(medido: dict, slug: str) -> None:
    """Nova Pink, Astro Bot, Sterling Silver: nenhum aparece na página."""
    _hexa, esperado = FORA_DO_DESENHO[slug]
    visto = medido["medidas"][slug]["p1"]
    assert visto == esperado, (
        f"com um {slug} na mesa a borda do card ficou {visto}, e o mapa dela diz "
        f"{esperado}. Se veio um dos do desenho, a cor não é do aparelho")
    assert visto not in DO_DESENHO


def test_o_assento_sem_controle_nao_fica_com_a_cor_do_desenho(medido: dict) -> None:
    """Com um controle só, o `p2` tem de cair no neutro — não no Starlight Blue."""
    for slug in FORA_DO_DESENHO:
        assert medido["medidas"][slug]["p2"] not in DO_DESENHO, (
            f"com um {slug} sozinho na mesa, o assento vazio continuou "
            f"{medido['medidas'][slug]['p2']}, que é a cor do mockup")


def test_a_mesa_dela_de_hoje_chega_certa_aos_dois_assentos(medido: dict) -> None:
    """P1 White (`#e4e0d8`) e P2 Galactic Purple (`#74588e`), do mapa dela.

    O White aqui NÃO é `#edeef0`: aquele é o da tabela aproximada que saiu do
    caminho em 03/09. O `#e4e0d8` é o `casca_esq` que ela amostrou, e é o mesmo
    que o chip da fita mostra três centímetros acima.
    """
    assert medido["medidas"]["mesa-dela"]["p1"] == "rgb(228, 224, 216)"
    assert medido["medidas"]["mesa-dela"]["p2"] == "rgb(116, 88, 142)"


# ---------------------------------------------------------------------------
# 3. AS MORDIDAS — a cura arrancada, medida na mesma tela
# ---------------------------------------------------------------------------
def test_a_mordida_com_a_tabela_velha_a_tela_erra_a_cor(medido: dict) -> None:
    """A regra antiga pinta o Nova Pink em `rgb(238, 126, 166)`, que não é dela.

    Não é "um tom parecido": é a tabela `TONS`, cujo próprio cabeçalho diz que
    vinte das vinte e uma linhas são aproximadas. O chip da fita ao lado
    continuaria em `rgb(227, 91, 140)` — dois valores da mesma cor, na mesma
    tela, que é o defeito que ELA reportou.
    """
    _hexa, certo = FORA_DO_DESENHO["nova-pink"]
    velho = medido["medidas"]["mordida-nova-pink"]["p1"]
    assert velho != certo, (
        "a mordida NÃO mordeu: a regra velha devolveu a mesma cor da nova, "
        "então este arquivo não está medindo o que diz medir")
    assert velho == "rgb(238, 126, 166)", (
        f"a regra velha mudou de resposta ({velho}) — releia a mordida antes de "
        "acreditar no verde acima")


def test_a_mordida_da_grafia_a_borda_some_no_spider_man(medido: dict) -> None:
    """`Marvel's Spider-Man 2` é o nome que a MESA entrega, do CSV dela.

    `NOMES_DE_FABRICA` escreve `Spider-Man 2`, sem o `Marvel's`. Pela regra
    velha os dois não casavam e a borda caía no neutro — o card perdia a única
    marca que diz de quem ele é. São TRÊS modelos assim; ver
    `GRAFIA_DIVERGENTE`, em `test_aba02_a_cor_do_plastico_vem_do_aparelho.py`.
    """
    from pacotes import a02_controles as a02

    velho = medido["medidas"]["mordida-spider"]["p1"]
    assert velho == "rgb(68, 71, 90)", (
        f"a mordida da grafia mudou de resposta: {velho}. Ela existia para "
        "mostrar a borda SUMINDO no neutro `--border-forte`")
    assert a02.cor_da_borda("spider-man-2") == "#5f5f60", (
        "e pelo slug ela tem cor — que é a cura desta sprint")
