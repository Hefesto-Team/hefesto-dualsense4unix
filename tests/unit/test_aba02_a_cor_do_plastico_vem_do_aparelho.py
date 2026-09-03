#!/usr/bin/env python3
"""A COR DO PLÁSTICO DA ABA 02 É A DO APARELHO, EM TODOS OS ASSENTOS — 03/09/2026.

A LEI É DELA:

    *"imagina que cada pessoa tenha um dualsense diferente. eu mapeei as cores,
    glifos, controles, id e tudo mais. é pro projeto usar esse meu trabalho
    entende? nada hardcoded. (…) eu quero que cada user ao usar seu controle se
    toque disso que o app se adaptou ao controle dele"*

O DEFEITO QUE ESTE ARQUIVO FECHA NÃO É "a cor está cravada" — esse já tinha sido
curado em 03/09 às 01h31, e o teste irmão
(`test_aba02_a_identidade_vem_da_fita.py`) o guarda. **É o buraco que sobrou na
CURA**, e ele só aparece quando a mesa viva é menor que a mesa do desenho.

A CURA DE 01h31 pôs DUAS folhas no fim do `<head>`: a do desenho, com os dois
assentos que ela aprovou, e uma vazia por cima, endereçada, onde o produto
escrevia o que leu. Duas folhas só se sobrepõem no assento que a SEGUNDA nomeia.

MEDIDO NO WEBKITGTK DESTA MÁQUINA — o motor da janela dela —, com a página da
bancada carregada numa ``Gtk.OffscreenWindow`` e a folha endereçada recebendo o
que ``folha_do_plastico`` monta para **um** controle na mesa (P1 White):

    assento   antes da cura desta sprint     depois
    p1        rgb(237, 238, 240)  White      rgb(237, 238, 240)  White
    p2        rgb(126, 184, 212)  ← MOCKUP   rgb(68, 71, 90)     neutro
                Starlight Blue num assento
                onde não há controle nenhum

O p2 ficava **Starlight Blue** — a cor do desenho, num lugar vazio. Com um
controle no cabo e o outro desligado, é exatamente a mentira que a lei dela veio
matar, e ela sobrevivia a `check_identidade_vem_de_cima` (que não olha dentro de
`<style>`) e à régua do mockup (que não enumera folha de estilo).

A CURA É ESTRUTURAL, e é por isso que ela se testa sem abrir navegador: **uma
folha só**, endereçada, com `data-hef-alvo="html"`, que o produto TROCA INTEIRA.
O que a troca não escreve deixa de existir — não sobra para o desenho. E o
:data:`PISO` é a primeira regra dela, porque `.ctl{border:2px solid
var(--plastico)}` e uma `var()` sem valor **invalida a declaração inteira**: sem
o piso, o assento que a mesa viva não nomeia perderia a borda em vez de ficar
neutro (a lição está medida no comentário do `.ctl.off`, em `aba02.py`).

O RESOLVEDOR ABAIXO É HONESTO PORQUE A PÁGINA É SIMPLES: depois da cura há **uma
única** fonte de `--plastico` no documento, e dentro dela todas as regras têm a
mesma especificidade — `.ctl[data-controle]` e `.ctl[data-controle="p1"]` valem
as duas (0,2,0). Logo quem decide é a ORDEM, e "a última que casa" é a resposta
certa. `test_a_pagina_tem_uma_unica_fonte_de_plastico` é o que mantém essa
premissa verdadeira: se alguém puser uma segunda folha, ele reprova ANTES de o
resolvedor passar a mentir.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

BANCADA = RAIZ / "mockup/02-controles.html"

#: Os dois hexas que o DESENHO crava, e que nenhum assento pode mostrar quando o
#: aparelho é outro. Saem de `monta.MESA` — Cosmic Red e Starlight Blue.
DO_DESENHO = ("#ae335a", "#7eb8d4")

#: `--border-forte` do tema, resolvido. É o "nada" que a regra dela manda
#: mostrar, e o mesmo tom que o lugar VAZIO desta aba já usava.
NEUTRO = "#44475a"


@pytest.fixture(scope="module")
def a02():
    from pacotes import a02_controles

    return a02_controles


@pytest.fixture(scope="module")
def aba02():
    import aba02 as modulo

    return modulo


@pytest.fixture(scope="module")
def doc() -> str:
    return BANCADA.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# O RESOLVEDOR — a cascata desta página, e só dela
# ---------------------------------------------------------------------------
FOLHA = re.compile(r"<style([^>]*)>(.*?)</style>", re.S)
REGRA = re.compile(r"([^{}]+)\{([^{}]*)\}")
PLASTICO = re.compile(r"--plastico\s*:\s*([^;}]+)")
COMENTARIO = re.compile(r"/\*.*?\*/", re.S)


def _folhas_com_plastico(doc: str) -> list[tuple[str, str]]:
    """As folhas que DECLARAM `--plastico`, em ordem de documento: (atributos, css).

    DECLARAR, e não usar: a folha principal desta página está cheia de
    `var(--plastico)` — é ela que pinta a borda, o círculo do analógico e os
    glifos —, e contá-la aqui faria esta régua acusar a página curada. Comentário
    também sai: as duas folhas falam de `--plastico` em prosa.
    """
    return [(m.group(1), m.group(2)) for m in FOLHA.finditer(doc)
            if PLASTICO.search(COMENTARIO.sub(" ", m.group(2)))]


def _cor_do_assento(doc: str, pref: str, troca: str | None = None) -> str | None:
    """A cor que o assento `pref` acaba tendo — ``None`` se nenhuma regra o alcança.

    `troca` é o que o produto escreve na folha endereçada (o `innerHTML` que o
    alvo `html` do piloto substitui). Sem ele, mede-se a BANCADA.
    """
    valor = None
    for atributos, css in _folhas_com_plastico(doc):
        if troca is not None and 'data-campo="plastico-css"' in atributos:
            css = troca
        for regra in REGRA.finditer(COMENTARIO.sub(" ", css)):
            seletores = [s.strip() for s in regra.group(1).split(",")]
            alcanca = any(
                s in (".ctl[data-controle]", f'.ctl[data-controle="{pref}"]')
                for s in seletores)
            achado = PLASTICO.search(regra.group(2))
            if alcanca and achado:
                valor = achado.group(1).strip()
    return valor


# ---------------------------------------------------------------------------
# 1. A FORMA — uma folha só, endereçada, com o piso na frente
# ---------------------------------------------------------------------------
def test_a_pagina_tem_uma_unica_fonte_de_plastico(doc):
    """Duas folhas foi exatamente o que deixou o Starlight Blue de pé no p2."""
    folhas = _folhas_com_plastico(doc)
    assert len(folhas) == 1, (
        f"{len(folhas)} folhas declaram `--plastico`; com mais de uma, a que o "
        "produto NÃO troca sobrevive nos assentos que ele não nomeia")
    atributos = folhas[0][0]
    assert 'data-campo="plastico-css"' in atributos, (
        "a única folha do plástico não tem endereço — o produto não tem onde escrever")
    assert 'data-hef-alvo="html"' in atributos, (
        "sem `data-hef-alvo=html` o `escrever` cai no ramo padrão e escreve a "
        "folha como TEXTO na página, deixando o desenho mandando na cor")


def test_nenhuma_cor_de_plastico_sobrou_no_estilo_de_linha(doc):
    """Estilo de linha vence qualquer folha — ali o produto não alcança."""
    assert "--plastico:#" not in doc.split("</head>", 1)[-1]


def test_o_piso_e_a_primeira_regra_da_folha(doc, aba02):
    """Ele vem primeiro porque a especificidade empata e quem decide é a ordem."""
    css = COMENTARIO.sub(" ", _folhas_com_plastico(doc)[0][1])
    regras = [r.group(0).strip() for r in REGRA.finditer(css)]
    assert regras, "a folha do plástico está vazia"
    assert regras[0] == aba02.PISO_DO_PLASTICO, (
        f"a primeira regra da folha é `{regras[0]}`, e devia ser o piso")


def test_o_piso_nao_nomeia_assento(aba02):
    """Um piso que nomeasse um assento deixaria os outros sem cor nenhuma."""
    assert '="' not in aba02.PISO_DO_PLASTICO.split("{", 1)[0], (
        "o piso ficou preso a um assento — os demais perderiam a borda inteira")


def test_os_dois_pisos_gemeos_nao_divergiram(aba02, a02):
    """O gerador é dono da BANCADA e o pacote é dono do PRODUTO, e eles não se
    importam — importar um do outro arrastaria a bancada para o fecho de
    produção. Quem impede a divergência é esta linha."""
    assert aba02.PISO_DO_PLASTICO == a02.PISO_DA_FOLHA


def test_o_seletor_do_assento_e_o_mesmo_dos_dois_lados(aba02, a02):
    """Bancada e produto têm de escrever o MESMO seletor, ou a troca não cobre."""
    do_produto = a02.folha_do_plastico([{"pref": "p1", "nome": "White"}])
    seletor = do_produto.splitlines()[1].split("{", 1)[0]
    assert seletor == aba02.seletor_do_plastico("p1")


# ---------------------------------------------------------------------------
# 2. A CASCATA — o buraco que esta sprint fecha
# ---------------------------------------------------------------------------
def test_a_bancada_mostra_o_desenho_que_ela_aprovou(doc):
    """Sem daemon, a página é a bancada: a folha nasce com o que ela aprovou."""
    assert _cor_do_assento(doc, "p1") == DO_DESENHO[0]
    assert _cor_do_assento(doc, "p2") == DO_DESENHO[1]


def test_com_um_controle_so_o_assento_vazio_perde_a_cor_do_desenho(doc, a02):
    """O DEFEITO, medido: o p2 ficava Starlight Blue com o P1 sozinho na mesa."""
    troca = a02.folha_do_plastico([{"pref": "p1", "nome": "White"}])
    assert _cor_do_assento(doc, "p1", troca) == "#edeef0"
    assert _cor_do_assento(doc, "p2", troca) == a02.BORDA_SEM_COR


def test_nenhum_assento_fica_sem_cor_definida(doc, a02):
    """`var()` sem valor não deixa a borda cinza — ela SOME. Por isso o piso."""
    troca = a02.folha_do_plastico([{"pref": "p1", "nome": "White"}])
    for pref in ("p1", "p2", "p3", "p4"):
        assert _cor_do_assento(doc, pref, troca) is not None, (
            f"o assento {pref} ficou sem `--plastico`, e a borda dele deixa de existir")


def test_a_mesa_dela_de_hoje_chega_inteira_a_tela(doc, a02):
    """P1 White no cabo, P2 Galactic Purple no rádio — os dois aparelhos dela."""
    troca = a02.folha_do_plastico([
        {"pref": "p1", "nome": "White"},
        {"pref": "p2", "nome": "Galactic Purple"},
    ])
    assert _cor_do_assento(doc, "p1", troca) == a02.cor_da_borda("White")
    assert _cor_do_assento(doc, "p2", troca) == a02.cor_da_borda("Galactic Purple")
    for hexa in DO_DESENHO:
        assert hexa not in troca, f"o pacote emitiu `{hexa}`, que é do desenho"


def test_nenhum_hexa_do_desenho_sobrevive_a_troca(doc, a02):
    """A varredura final, e ela é sobre a TELA: em nenhum dos quatro assentos, em
    nenhuma das mesas plausíveis, pode restar a cor do mockup."""
    mesas = [
        [],
        [{"pref": "p1", "nome": "White"}],
        [{"pref": "p2", "nome": "Nova Pink"}],
        [{"pref": "p1", "nome": "Midnight Black"}, {"pref": "p2", "nome": "Não sei"}],
        [{"pref": f"p{n}", "nome": "Chroma Teal"} for n in range(1, 5)],
    ]
    for mesa in mesas:
        troca = a02.folha_do_plastico(mesa)
        for pref in ("p1", "p2", "p3", "p4"):
            cor = _cor_do_assento(doc, pref, troca)
            assert cor not in DO_DESENHO, (
                f"com a mesa {[c['nome'] for c in mesa]} o assento {pref} "
                f"continuou em `{cor}`, que é a cor do desenho")


# ---------------------------------------------------------------------------
# 3. O DADO VEM DO MAPA DELA — os 28 modelos, e os que o produto ainda não sabe
# ---------------------------------------------------------------------------
def _modelos_do_mapa() -> dict[str, str]:
    """`código de fábrica -> nome`, lido do CSV que é dono deles."""
    import csv

    caminho = RAIZ / "docs/data/cores-do-dualsense.csv"
    linhas = [linha for linha in caminho.read_text(encoding="utf-8").splitlines()
              if linha.strip() and not linha.lstrip().startswith("#")]
    return {x["codigo_da_cor"]: x["nome"] for x in csv.DictReader(linhas)
            if x.get("codigo_da_cor")}


def test_o_mapa_dela_tem_vinte_e_oito_modelos():
    """O número da lei dela. Se ele mudar, tudo abaixo tem de ser relido."""
    assert len(_modelos_do_mapa()) == 28


@pytest.mark.parametrize("codigo_de_fabrica", sorted(_modelos_do_mapa()))
def test_todo_modelo_que_o_produto_reconhece_vira_borda(a02, codigo_de_fabrica):
    """Os 21 códigos que o produto conhece viram hexa; os sete que não, viram neutro.

    O NOME PEDIDO É O DO PRODUTO, e a distinção importa: `cor_da_borda` recebe um
    NOME, e o nome que chega vivo sai de `NOMES_DE_FABRICA` — o aparelho publica
    um CÓDIGO, e quem o traduz é essa tabela. Perguntar com o nome do CSV mediria
    a grafia dos dois arquivos, que é outro fato e tem teste próprio logo abaixo.
    """
    from hefesto_dualsense4unix.integrations.cor_do_plastico import NOMES_DE_FABRICA

    if codigo_de_fabrica in NOMES_DE_FABRICA:
        borda = a02.cor_da_borda(NOMES_DE_FABRICA[codigo_de_fabrica])
        assert re.fullmatch(r"#[0-9a-fA-F]{6}", borda), (
            f"o código `{codigo_de_fabrica}` está no mapa do produto e não virou hexa")
    else:
        alheio = _modelos_do_mapa()[codigo_de_fabrica]
        assert a02.cor_da_borda(alheio) == a02.BORDA_SEM_COR


#: OS TRÊS QUE SÃO O MESMO MODELO ESCRITO DE DOIS JEITOS — medido em 03/09/2026.
#: ``código -> (nome no CSV dela, nome no mapa do produto)``.
#:
#: A TELA NÃO SOFRE COM ISSO HOJE, e é importante dizer por quê: o nome vivo sai
#: de `NOMES_DE_FABRICA` pelo CÓDIGO que o aparelho publica, então a borda sai
#: certa. O que quebra é quem for de NOME — e é o caminho que
#: `check_a_cor_vem_do_aparelho.colorways_do_mapa` e o `mapa-do-controle.html`
#: usam, porque leem o CSV.
GRAFIA_DIVERGENTE = {
    "Z1": ("God of War Ragnarök", "God of War Ragnarok"),
    "Z2": ("Marvel's Spider-Man 2", "Spider-Man 2"),
    "ZB": ("Icon Blue Special Edition", "Icon Blue Limited Edition"),
}


def test_as_grafias_divergentes_estao_declaradas():
    """Dois arquivos com o mesmo modelo escrito diferente é divergência silenciosa."""
    from hefesto_dualsense4unix.integrations.cor_do_plastico import NOMES_DE_FABRICA

    do_csv = _modelos_do_mapa()
    achadas = {
        c: (do_csv[c], NOMES_DE_FABRICA[c])
        for c in sorted(do_csv)
        if c in NOMES_DE_FABRICA and do_csv[c] != NOMES_DE_FABRICA[c]
    }
    assert achadas == GRAFIA_DIVERGENTE, (
        "a grafia dos modelos divergiu entre `cores-do-dualsense.csv` (o mapa "
        "dela) e `cor_do_plastico.NOMES_DE_FABRICA` (o que o produto sabe).\n"
        f"  hoje: {achadas}\n  declarado: {GRAFIA_DIVERGENTE}")


#: OS SETE QUE ELA MAPEOU E O PRODUTO AINDA NÃO SABE — medido em 03/09/2026.
#:
#: `docs/data/cores-do-dualsense.csv` cataloga 28 modelos com código de fábrica;
#: `integrations/cor_do_plastico.NOMES_DE_FABRICA` conhece 21. Quem tiver um
#: destes sete vê a borda NEUTRA: honesto (o produto não inventa cor), mas não é
#: *"o app se adaptou ao controle dele"*, que é o que ela pediu.
#:
#: NÃO É DEFEITO DESTA ABA, e por isso não se conserta aqui: o dono é
#: `integrations/cor_do_plastico.py`, e a cura é ele LER o CSV em vez de repetir
#: a lista. Esta constante é o marcador — no dia em que alguém fechar a lacuna,
#: este teste reprova dizendo exatamente isto, e o número aqui desce.
SEM_TOM_NO_PRODUTO = {
    "13": "HyperPop Techno Red",
    "14": "HyperPop Remix Green",
    "15": "HyperPop Rhythm Blue",
    "ZC": "Ghost of Yōtei Limited Edition",
    "ZD": "Marathon Limited Edition",
    "ZE": "Genshin Impact Limited Edition",
    "ZF": "007 First Light Limited Edition",
}


def test_a_lacuna_entre_o_mapa_dela_e_o_produto_esta_declarada():
    """Régua que acha zero é erro; esta acha SETE, e diz quais."""
    from hefesto_dualsense4unix.integrations.cor_do_plastico import NOMES_DE_FABRICA

    faltam = {c: n for c, n in _modelos_do_mapa().items() if c not in NOMES_DE_FABRICA}
    assert faltam == SEM_TOM_NO_PRODUTO, (
        "a lacuna entre `cores-do-dualsense.csv` (o mapa dela) e "
        "`cor_do_plastico.NOMES_DE_FABRICA` (o que o produto sabe) mudou.\n"
        f"  hoje faltam: {sorted(faltam)}\n"
        f"  declarado:   {sorted(SEM_TOM_NO_PRODUTO)}\n"
        "Se alguém fechou a lacuna, apague daqui os que entraram.")
