"""A régua da aba 03: a cor do plástico vem do APARELHO, nos 28 modelos dela.

A LEI, de 03/09/2026::

    A cor do plástico, o desenho do DualSense, as bordas e a escolha de cada player vêm do
    controle identificado no canto superior, a partir do mapa de cores já catalogado,
    e não de valores cravados no desenho. Cada pessoa pode ter um modelo diferente.

O DEFEITO que esta régua fecha: o cabeçalho de cada coluna trazia
`style="--plastico:#ae335a"` — o Cosmic Red do DESENHO — num `<span>` cujo alvo
de pintura era `texto`. O produto não tinha como reescrevê-lo: os alvos do
`escrever()` escrevem texto, largura, fundo, valor, html, classe, cor e
atributo, e **nenhum deles escreve uma propriedade CSS de autor**. Quem tivesse
um Nova Pink via um Cosmic Red.

A CURA tem duas metades, e as duas estão aqui:

1. o `--plastico` subiu para o EMBRULHO (`.cabeca`), que tem `data-campo` e o
   alvo `plastico` — o único que escreve a variável — e fica FORA do
   `innerHTML` que o alvo `html` do miolo compara;
2. o pacote escreve nele o que leu do MAPA DO USUÁRIO, e não de uma tabela sua.

**O QUE SEPARA A CURA DA MAQUIAGEM, e é o que esta régua mede:** trocar o Cosmic
Red por outro hexadecimal escrito à mão seria trocar um cravado por outro. Por
isso o laço abaixo passa pelos **28 modelos do CSV dela**, um a um, e exige que
a coluna vista EXATAMENTE o que o mapa responde — inclusive os três que o
desenho da aba nunca mostrou: **Nova Pink, Astro Bot e Sterling Silver**.

A MORDIDA: devolva a cor para dentro de `chip_do_controle` (ou troque a leitura
do mapa por um hexadecimal digitado) e `test_o_modelo_que_o_desenho_nao_tem` e
`test_a_cor_sai_do_mapa_dela_nos_28` reprovam nomeando o modelo.
"""
from __future__ import annotations

import csv
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "03-gatilhos.html"
CORES_CSV = RAIZ / "docs" / "data" / "cores-do-dualsense.csv"

DO_DESENHO = ("cosmic-red", "starlight-blue")

DE_FORA = ("nova-pink", "astro-bot", "sterling-silver")

NO_CABO = {
    "uniq": "aa:bb:cc:00:00:01", "player": 1, "transport": "usb",
    "is_primary": True, "inputs": {"l2_raw": 0, "r2_raw": 0},
}


@pytest.fixture(scope="module")
def a03():
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos

    return a03_gatilhos


@pytest.fixture(scope="module")
def mapa():
    """`[(id, nome, tinta)]` — os 28 modelos, lidos do CSV que é dono deles."""
    from monta import cor_da_zona

    linhas = [
        linha for linha in CORES_CSV.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]
    fora, visto = [], set()
    for linha in csv.DictReader(linhas):
        slug = (linha.get("id") or "").strip()
        if slug and slug not in visto:
            visto.add(slug)
            fora.append((slug, (linha.get("nome") or "").strip(),
                         str(cor_da_zona(slug))))
    return fora


def _mesa_com(slug: str, nome: str):
    """A mesa de UM controle, do modelo pedido — como o daemon a entrega."""
    return [{"pref": "p1", "jogador": 1, "uniq": NO_CABO["uniq"], "nome": nome,
             "via": "USB", "cor": slug, "mascara": "DualSense", "alvo": True}]


def _cor_da_coluna(a03, slug: str, nome: str) -> str:
    """O que o PACOTE escreve no endereço da cor da coluna do P1."""
    from pacotes import Contexto, perfil

    guardado = perfil.ativo
    perfil.ativo = lambda _n: {"triggers": {}, "controllers": {}}  # type: ignore[assignment]
    try:
        r = a03.pacote(Contexto(state={"active_profile": "régua"},
                                mesa=_mesa_com(slug, nome),
                                conectados=[NO_CABO], estados={}))
    finally:
        perfil.ativo = guardado  # type: ignore[assignment]
    return str((r["colunas"][NO_CABO["uniq"]])[a03.CAMPO_DO_PLASTICO])


def test_o_mapa_dela_continua_com_os_28(mapa):
    """A régua declara o tamanho do mapa em vez de presumi-lo."""
    assert len(mapa) == 28, (
        f"o mapa dela tem {len(mapa)} modelos, e esta régua foi escrita sobre "
        f"28. Se ela mapeou mais, o número acompanha; se caiu, alguém apagou "
        f"trabalho dela.")
    ids = {slug for slug, _n, _t in mapa}
    for slug in DE_FORA + DO_DESENHO:
        assert slug in ids, (
            f"`{slug}` saiu do CSV dela. Esta régua o nomeia de propósito — sem "
            f"ele, ela passa calada exatamente sobre o caso que existe para "
            f"medir.")


def test_a_cor_sai_do_mapa_dela_nos_28(a03, mapa):
    """A coluna veste o que o MAPA responde, para os 28 — e nada além disso."""
    for slug, nome, tinta in mapa:
        escrito = _cor_da_coluna(a03, slug, nome)
        esperado = tinta if tinta.startswith("#") else ""
        assert escrito == esperado, (
            f"{nome} ({slug}): o mapa dela responde {tinta!r} e a coluna "
            f"recebeu {escrito!r}. A cor tem de sair do CSV dela, não de uma "
            f"tabela deste código.")


def test_o_modelo_que_o_desenho_nao_tem(a03, mapa):
    """Nova Pink, Astro Bot e Sterling Silver aparecem — e são DIFERENTES."""
    do_desenho = {t for s, _n, t in mapa if s in DO_DESENHO}
    vistas = {}
    for slug in DE_FORA:
        nome = next(n for s, n, _t in mapa if s == slug)
        vistas[slug] = _cor_da_coluna(a03, slug, nome)

    for slug, cor in vistas.items():
        assert cor.startswith("#"), (
            f"quem tem um {slug} não recebe cor nenhuma: {cor!r}. O mapa dela "
            f"responde um hexadecimal para este modelo.")
        assert cor not in do_desenho, (
            f"a coluna de um {slug} recebeu {cor!r}, que é uma cor do DESENHO. "
            f"O app tem de se adaptar ao controle de quem o usa.")

    assert len(set(vistas.values())) == len(vistas), (
        f"os três modelos de fora do desenho receberam a mesma cor: {vistas}. "
        f"Uma cor só para modelos diferentes é a tela afirmando o que não é.")


def test_a_cor_tem_endereco_e_alvo_que_a_alcanca(a03, mapa):
    """O cabeçalho declara o alvo `plastico`, o único que escreve a variável."""
    nome = next(n for s, n, _t in mapa if s == "nova-pink")
    cabeca = a03._cabeca_do_controle(1, nome, "USB", a03._cor_do_plastico("nova-pink"))
    assert f'data-campo="{a03.CAMPO_DO_PLASTICO}"' in cabeca, (
        f"o cabeçalho saiu sem o endereço da cor: {cabeca!r}")
    assert f'data-hef-alvo="{a03.ALVO_DO_PLASTICO}"' in cabeca, (
        f"o cabeçalho não diz o alvo que alcança a cor: {cabeca!r}")
    assert a03.ALVO_DO_PLASTICO == "plastico", (
        "o alvo mudou de nome. `hefesto_vivo.escrever` compara o alvo por "
        "IGUALDADE — um nome novo cai no ramo padrão, calado.")


def test_a_ponte_ate_o_publicar_nao_apaga_a_borda_dela(a03, mapa):
    """Enquanto a página publicada não tiver o endereço, a cor vai NO CHIP."""
    tinta = next(t for s, _n, t in mapa if s == "nova-pink")
    com_ponte = a03.chip_do_controle(1, "Nova Pink", "USB", tinta,
                                     cor_no_chip=True)
    assert f"--plastico:{tinta}" in com_ponte, (
        f"a ponte até o `--publicar 03` não leva a cor: {com_ponte!r}. A página "
        f"que ela vê hoje só recebe o chip inteiro — sem a cor aqui dentro, a "
        f"borda das colunas dela fica neutra.")

    sem_ponte = a03.chip_do_controle(1, "Nova Pink", "USB", tinta)
    assert "--plastico" not in sem_ponte, (
        f"o chip leva a cor por padrão: {sem_ponte!r}. É o DESENHO que chama "
        f"assim, e ali a cor tem de estar no embrulho endereçado — num arquivo "
        f"estático ninguém a reescreve.")

    assert a03.a_pagina_recebe_a_cor_por_endereco() == (
        a03.CAMPO_DO_PLASTICO in a03._enderecos_da_pagina()), (
        "a escolha da ponte deixou de sair da página publicada. Presumir aqui "
        "faria o pacote apagar a borda dela, ou mandar a cor duas vezes depois "
        "de publicar.")


def test_a_bancada_nao_crava_cor_que_o_produto_nao_alcance(a03):
    """Na página gerada, todo `--plastico` mora num elemento com o alvo certo.

    É a mesma pergunta que `scripts/check_a_cor_vem_do_aparelho.py` faz sobre as
    dez páginas, feita aqui sobre a desta aba — para que a resposta apareça no
    `pytest` e não só no portão. A fita do topo fica de fora: ela é do
    `monta.fita()`, o esqueleto das DEZ páginas, e o piloto a troca INTEIRA.
    """
    import re

    from hefesto_dualsense4unix.interface import onde

    doc = onde.pagina(PAGINA).read_text(encoding="utf-8")
    achou = re.search(r'<div class="fita(?: inerte)?"', doc)
    assert achou, "a fita do esqueleto sumiu da página"
    depois = doc.index("</div>", achou.start()) + len("</div>")

    for casa in re.finditer(r"--plastico\s*:", doc[depois:]):
        posicao = casa.start() + depois
        tag = doc[doc.rfind("<", 0, posicao):doc.find(">", posicao) + 1]
        assert f'data-hef-alvo="{a03.ALVO_DO_PLASTICO}"' in tag, (
            f"a bancada crava uma cor que o produto não alcança: {tag[:140]!r}. "
            f"Quem tiver outro modelo continua vendo este.")
