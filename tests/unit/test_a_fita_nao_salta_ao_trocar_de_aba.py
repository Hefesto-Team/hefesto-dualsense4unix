#!/usr/bin/env python3
"""A LINHA DO ALVO MEDE O MESMO NAS DEZ ABAS, e em qualquer estado da fita.

O DEFEITO, medido em 11/09/2026 (`AS-DEZ-ABAS-MAXIMIZADAS`, §3.6) e remedido em
13/09/2026 depois de a faixa de cabeçalho sair: a altura da linha do alvo é a do
filho mais alto dela. O chip da fita tinha 28 px com borda de 1 e 30 com borda
de 2. Nas três abas que escolhem controle o chip do plástico tem 2 e a linha
dava **52**; nas sete de fita inerte ele tem 1 e a linha dava **51**. A barra
de abas e o quadro desciam 1 px a cada troca de aba.

POR QUE A RÉGUA MEDE QUATRO ESTADOS, e não só a página publicada
------------------------------------------------------------------
A cura escrita na sprint (2 px na borda do chip inerte) igualava as páginas
publicadas — menos a 07, cuja fita nasce só com o «Todos» — e quebrava a regra
de 08/09 («cinza como os demais», `test_a_fita_inerte_nao_acende_ninguem.py`).
E a página publicada é só o instante antes do primeiro tique. O piloto repinta
a fita com o que o daemon diz, e a classe do plástico só entra quando a cor foi
LIDA — pelo rádio ela nunca é. Medido com CSS injetado nas dez, sem tocar
arquivo:

    hoje            publicado 51/52 · cor lida 51/52 · sem cor 51 · só «Todos» 51
    cura da sprint  publicado 51 (07) / 52 · e seis fitas inertes com duas caras
    cura na causa   52 nas dez, nos quatro estados

Então a régua simula os quatro estados que o produto pinta, e cobra UMA altura:
entre as dez abas E entre os estados. **Nenhum número está digitado aqui** — as
abas são comparadas entre si.

A MORDIDA
---------
Arranque do ``interface/topo.html`` a regra ``.fita .chip{padding-top:…;
padding-bottom:…}``, regere as dez e publique. Caem os três primeiros casos,
com a 01, a 02 e a 08 em 52 e as outras sete em 51.
"""
from __future__ import annotations

import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
PUBLICADO = INTERFACE / "paginas"  # (noqa-acento) nome de PASTA; caminho não leva acento

#: O MESMO MOTOR DAS OUTRAS RÉGUAS DE TELA desta casa, headless: nenhuma janela
#: nasce na tela dela.
CHROME = pathlib.Path("/usr/bin/google-chrome")

#: A VISTA DA JANELA MAXIMIZADA DELA (`scripts/ensaios/a_janela_cabe_no_que_ela_ve.py`).
VISTA = {"width": 1918, "height": 840}

#: OS ESTADOS QUE O PRODUTO PINTA NA FITA, cada um com o que o provoca.
ESTADOS = {
    # o arquivo, antes do primeiro tique — é o que aparece a cada troca de aba
    "como-publicado": "",
    # o rádio: `monta.fita` e `a09_sistema._um_chip` só põem a classe do
    # plástico quando a cor foi lida, e pelo rádio ela não é
    "sem-cor-lida": "document.querySelectorAll('.fita .chip.plastico')"
                    ".forEach(c => c.classList.remove('plastico'));",
    # a fita com um chip só: é assim que a 07 está no arquivo publicado, antes
    # do primeiro tique
    "so-todos": "document.querySelectorAll('.fita .chip')"
                ".forEach(c => { if ((c.textContent || '').trim() !== 'Todos') c.remove(); });",
    # o cabo: todo controle com a cor lida ganha a classe do plástico
    "com-cor-lida": "document.querySelectorAll('.fita .chip')"
                    ".forEach(c => { if ((c.textContent || '').trim() !== 'Todos')"
                    " c.classList.add('plastico'); });",
}

O_QUE_O_MOTOR_DESENHA = """() => {
  const linha = document.querySelector('.fita-linha');
  const miolo = document.querySelector('.miolo');
  const fita = document.querySelector('.fita');
  if (!linha || !miolo || !fita) return {erro: 'a página não tem linha do alvo, fita ou miolo'};
  const chips = [...fita.querySelectorAll('.chip')].map(c => ({
    texto: (c.textContent || '').trim(),
    altura: c.getBoundingClientRect().height,
    borda: getComputedStyle(c).borderTopWidth,
  }));
  return {
    linha: linha.getBoundingClientRect().height,
    miolo: miolo.getBoundingClientRect().y,
    inerte: fita.classList.contains('inerte'),
    chips,
  };
}"""


def _abas_publicadas() -> list[pathlib.Path]:
    return sorted(PUBLICADO.glob("[0-9][0-9]-*.html"))


@pytest.fixture(scope="module")
def medido() -> dict[str, dict[str, dict]]:
    """``{estado: {página: medida}}`` — as dez abas nos quatro estados, no Chrome.

    **RÉGUA QUE ACHA ZERO NÃO É RÉGUA VERDE.** Menos de dez páginas reprova, e
    uma fita sem chip nenhum também: comparar alturas de nada dá igualdade.
    """
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    paginas = _abas_publicadas()
    assert len(paginas) >= 10, (
        f"achei {len(paginas)} abas publicadas em {PUBLICADO} — o caminho mudou? "
        f"Uma régua de tela que mede zero página passa sobre tudo.")

    from playwright.sync_api import sync_playwright

    fora: dict[str, dict[str, dict]] = {e: {} for e in ESTADOS}
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = nav.new_page(viewport=VISTA)
            for estado, js in ESTADOS.items():
                for p in paginas:
                    pg.goto(p.as_uri())
                    pg.wait_for_load_state("networkidle")
                    if js:
                        pg.evaluate("() => {" + js + "}")
                    r = pg.evaluate(O_QUE_O_MOTOR_DESENHA)
                    assert "erro" not in r, f"{p.name}: {r['erro']}"
                    assert r["chips"], f"{p.name} ({estado}): a fita saiu sem chip nenhum"
                    fora[estado][p.name] = r
        finally:
            nav.close()
    return fora


def _por_valor(medidas: dict[str, dict], chave: str) -> dict[float, list[str]]:
    grupos: dict[float, list[str]] = {}
    for nome, r in medidas.items():
        grupos.setdefault(round(r[chave], 2), []).append(nome[:2])
    return grupos


# ---------------------------------------------------------------------------
# 1. A CAUSA — o chip da fita mede o mesmo com borda de 1 ou de 2
# ---------------------------------------------------------------------------
def test_todo_chip_da_fita_tem_a_mesma_altura(medido: dict) -> None:
    """A espessura da borda não muda a altura do chip, em estado nenhum.

    É a causa medida: a linha segue o filho mais alto, e o chip de borda 2
    passava 2 px o de borda 1. Com a causa fechada, os outros dois casos são
    consequência — e este diz ONDE mexer quando não forem.
    """
    ruins = []
    for estado, medidas in medido.items():
        alturas: dict[float, list[str]] = {}
        for nome, r in medidas.items():
            for c in r["chips"]:
                alturas.setdefault(round(c["altura"], 2), []).append(
                    f"{nome[:2]}:{c['texto']!r}:{c['borda']}")
        if len(alturas) > 1:
            ruins.append(f"{estado}: " + " · ".join(
                f"{h} px ← {sorted(set(q))[:4]}" for h, q in sorted(alturas.items())))
    assert not ruins, (
        "o chip da fita muda de altura com a espessura da borda — a linha do alvo "
        "segue o filho mais alto e salta junto:\n  " + "\n  ".join(ruins))


# ---------------------------------------------------------------------------
# 2. A QUEIXA — a linha e o miolo não saem do lugar ao trocar de aba
# ---------------------------------------------------------------------------
def test_a_linha_do_alvo_mede_o_mesmo_nas_dez(medido: dict) -> None:
    """Em cada estado, as dez abas têm a mesma linha do alvo e o miolo no mesmo `y`."""
    ruins = []
    for estado, medidas in medido.items():
        for chave in ("linha", "miolo"):
            grupos = _por_valor(medidas, chave)
            if len(grupos) > 1:
                ruins.append(f"{estado} · {chave}: {grupos}")
    assert not ruins, (
        "trocar de aba move a barra de abas e o quadro:\n  " + "\n  ".join(ruins))


def test_a_pintura_nao_move_a_linha_do_alvo(medido: dict) -> None:
    """Entre o arquivo e o que o tique pinta, a mesma aba não muda de altura.

    A página publicada é só o instante antes do primeiro tique; depois dele a
    fita tem a cor que o aparelho deu ou não deu. Uma altura por estado seria
    um salto a cada visita — no instante em que a pintura chega.
    """
    alturas = {round(r["linha"], 2) for medidas in medido.values() for r in medidas.values()}
    assert len(alturas) == 1, (
        f"a linha do alvo mede {sorted(alturas)} conforme o estado da fita: "
        + "; ".join(f"{e}={sorted(_por_valor(m, 'linha'))}" for e, m in medido.items()))


# ---------------------------------------------------------------------------
# 3. O QUE A CURA NÃO PODE DESFAZER — a fita inerte segue sem espessura própria
# ---------------------------------------------------------------------------
def test_a_fita_inerte_segue_com_uma_espessura_so(medido: dict) -> None:
    """Com a cor lida, o chip do plástico na fita inerte tem a borda dos irmãos.

    É a cura que a sprint escrevia, e ela caiu: 2 px no chip inerte devolve a
    espessura que ela mandou tirar em 08/09 — *"conseguimos deixar ele cinza
    como os demais?"* (a régua dela é `test_a_fita_inerte_nao_acende_ninguem.py`,
    que mede a página como publicada; este caso mede o estado do cabo).
    """
    ruins = []
    for nome, r in medido["com-cor-lida"].items():
        if not r["inerte"]:
            continue
        bordas = {c["borda"] for c in r["chips"]}
        if len(bordas) > 1:
            ruins.append(f"{nome}: {[(c['texto'], c['borda']) for c in r['chips']]}")
    assert not ruins, (
        "numa fita que não escolhe nada, o chip do plástico voltou a ter borda "
        "própria:\n  " + "\n  ".join(ruins))
