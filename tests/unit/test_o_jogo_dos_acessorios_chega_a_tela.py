"""A aba Vibração sem «Meus toques», e a janela genérica da extensão na 07, sem rolar.

No desenho do todo, aprovado em 12/10/2026 (`todo-05`, «Meus toques sai daqui; vai para a 07»), os
toques do jogador deixaram a aba Vibração. A janela dos acessórios que os recebia saiu da 07 em
19/10/2026, com o adulto: o que ela fazia é da extensão `intiface`, que desenha a dela pelo
manifesto, na janela genérica «Configurar · <extensão>».

Só o desenho (`mockup/05-vibracao.html` e `mockup/07-lancadores.html`). Rótulos com só a primeira
letra maiúscula (fora nomes próprios) e nem a 05 nem a janela da extensão rolam na vertical a
1212x809, a 1918x840 e a 1212x740.

MORDIDAS (executadas aqui): uma maiúscula no meio da janela e outra numa dica reprovam a régua; a
05 com «Meus toques» de volta também.
"""

from __future__ import annotations

import html
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
M05 = RAIZ / "mockup" / "05-vibracao.html"
M07 = RAIZ / "mockup" / "07-lancadores.html"
CHROME = pathlib.Path("/usr/bin/google-chrome")
LARGURAS = ((1212, 809), (1918, 840), (1212, 740))
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "src"))
import check_so_a_primeira_letra as regua



def _doc(caminho: pathlib.Path, texto: str | None = None) -> str:
    bruto = texto if texto is not None else caminho.read_text(encoding="utf-8")
    sem = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", bruto, flags=re.S)
    return re.sub(r"<!--.*?-->", "", sem, flags=re.S)


def _maiusculas_a_mais(doc: str, so_o_que_se_le: bool = False) -> list[str]:
    """Palavra com maiúscula no meio da frase, pela régua da casa (`check_so_a_primeira_letra`).

    O nome próprio e a marca são os que a régua declara: a lista tem um dono só. Além do que a
    régua lê, aqui entram as dicas (`data-dica`) das janelas da 07; `so_o_que_se_le` as deixa de
    fora, porque nas dicas da 05 o nome de um botão («Parar», «Sem efeito») vai citado.
    """
    nomes = regua.licencas([M05, M07])
    lidas = [frase for _, frase in regua.frases(doc)]
    if not so_o_que_se_le:
        lidas += [html.unescape(d) for d in re.findall(r'data-dica="([^"]+)"', doc)]
    return sorted({p for frase in lidas for p in regua.maiusculas_no_meio(frase, nomes)})


def _janela(doc: str, ident: str) -> str:
    inicio = doc.index(f'id="{ident}"')
    fim = doc.find('<div class="tela-nova"', inicio + 1)
    return doc[inicio:] if fim < 0 else doc[inicio:fim]


def test_a_aba_vibracao_nao_tem_mais_os_meus_toques() -> None:
    """A seção saiu da 05 (todo-05, 12/10/2026), e a 07 também não a tem: é da extensão."""
    assert "Meus toques" not in _doc(M05)
    assert "Meus toques" not in _doc(M07)


def test_a_regua_morde_os_meus_toques_que_voltam_a_05() -> None:
    assert "Meus toques" in _doc(M05, M05.read_text(encoding="utf-8").replace(
        "</body>", "<div class=\"pc-sub\">Meus toques</div></body>"))


def test_so_a_primeira_letra_e_maiuscula_na_05_e_nas_janelas_da_07() -> None:
    assert _maiusculas_a_mais(_doc(M05), so_o_que_se_le=True) == []
    assert _maiusculas_a_mais(_doc(M07)) == []


def test_a_regua_morde_a_maiuscula_no_meio_da_janela_e_da_dica() -> None:
    doc = _doc(M07).replace("Brilho da luz", "Brilho da Luz")
    assert "Luz" in _maiusculas_a_mais(doc)
    doc = _doc(M07).replace("Uma extensão com opções em três grupos",
                            "Uma extensão com Opções em três grupos")
    assert "Opções" in _maiusculas_a_mais(doc)


@pytest.fixture(scope="module")
def navegador():
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        yield nav
        nav.close()


@pytest.mark.parametrize(("larg", "alt"), LARGURAS)
def test_a_05_e_a_janela_da_extensao_nao_rolam_na_vertical(navegador, larg, alt) -> None:
    pg = navegador.new_page(viewport={"width": larg, "height": alt})
    try:
        pg.goto(M05.as_uri())
        m = pg.evaluate("""() => { const d = document.documentElement;
          return {alto: d.scrollHeight, cabe: d.clientHeight,
                  largo: d.scrollWidth > d.clientWidth + 1}; }""")
        assert m["alto"] <= m["cabe"] + 1 and not m["largo"], ("05", m)
        for ancora in ("modificacao",):  # (noqa-acento: âncora do HTML)
            pg.goto(f"{M07.as_uri()}#{ancora}")
            dentro = pg.evaluate("""(a) => { const r = document.getElementById(a);
              const cx = r.querySelector('.tn-cx').getBoundingClientRect();
              const roladores = [r, ...r.querySelectorAll('*')].filter(e =>
                e.scrollHeight > e.clientHeight + 1 && e.clientHeight > 0 &&
                ['auto', 'scroll'].includes(getComputedStyle(e).overflowY)).length;
              return {topo: cx.top, fundo: cx.bottom, alto: innerHeight, roladores}; }""", ancora)
            assert dentro["topo"] >= 0 and dentro["fundo"] <= dentro["alto"] + 1, (ancora, dentro)
            assert dentro["roladores"] == 0, (ancora, dentro)
    finally:
        pg.close()
