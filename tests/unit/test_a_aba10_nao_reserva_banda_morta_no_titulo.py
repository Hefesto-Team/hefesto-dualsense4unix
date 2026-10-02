#!/usr/bin/env python3
"""A tira do desfecho não ocupa espaço quando não há recado — medido em PIXELS."""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.interface import onde

CHROME = pathlib.Path("/usr/bin/google-chrome")
pytestmark = pytest.mark.skipif(
    not CHROME.exists(), reason="sem o Chrome do sistema — a régua não tem motor")

ABAS = sorted(p.name for p in onde.paginas(publicado=True)
              if p.name[:2].isdigit())

FRASE_LONGA = (
    "Perfil “Mortal Kombat 1” ativado — a carona da Steam foi reposta na Opção "
    "de Inicialização do jogo, e sem ela, no Bluetooth, o jogo tende a não "
    "enxergar controle nenhum. São 33 perfis no disco.")

O_VAO = """
() => {
  const topo = document.querySelector('.quadro-topo');
  const corpo = document.querySelector('.quadro-corpo');
  if (!topo || !corpo) return null;
  return corpo.getBoundingClientRect().top
       - topo.getBoundingClientRect().bottom;
}
"""

A_TIRA = """
(frase) => {
  const cx = document.querySelector('.desfecho');
  if (!cx) return null;
  const topo = document.querySelector('.quadro-topo');
  const corpo = document.querySelector('.quadro-corpo');
  const vao = () => corpo.getBoundingClientRect().top
                  - topo.getBoundingClientRect().bottom;
  const medir = () => {
    const cs = getComputedStyle(cx);
    return {altura: cx.getBoundingClientRect().height,
            folga: parseFloat(cs.marginTop) || 0,
            visivel: cs.visibility,
            linhas: cs.webkitLineClamp,
            vao: vao(),
            transbordou: cx.scrollHeight > cx.clientHeight + 1};
  };
  const vazia = medir();
  cx.querySelector('span').textContent = frase;
  cx.classList.add('on');
  const acesa = medir();
  return {vazia, acesa};
}
"""


def _no_chrome(pagina: pathlib.Path, script: str, *args: object) -> object:
    """Abre a página publicada no Chrome do sistema e devolve o que ela mediu."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1280, "height": 900})
            pg.goto(pagina.as_uri())
            return pg.evaluate(script, *args)
        finally:
            navegador.close()


@pytest.fixture(scope="module")
def tira() -> dict:
    """A tira da aba 10, vazia e acesa — uma abertura para todos os casos."""
    medido = _no_chrome(
        onde.pagina("10-perfis.html", publicado=True), A_TIRA, FRASE_LONGA)
    assert medido, (
        "a `.desfecho` sumiu da página publicada — sem ela o canal do desfecho "
        "não existe, e esta régua ficaria verde por ausência")
    return dict(medido)


def test_a_tira_vazia_nao_ocupa_um_pixel(tira: dict) -> None:
    """Zero de altura e zero de folga — é a queixa dela, em números."""
    vazia = tira["vazia"]
    assert vazia["altura"] == 0 and vazia["folga"] == 0, (
        f"a tira do desfecho VAZIA mede {vazia['altura']}px de altura e "
        f"{vazia['folga']}px de folga — são "
        f"{vazia['altura'] + vazia['folga']}px de banda morta debaixo do título "
        f"'Perfis', em toda tela sem recado")
    assert vazia["visivel"] == "hidden", (
        "a tira vazia ficou VISÍVEL — ela apareceria como uma faixa em branco "
        "em toda tela sem recado")


def test_a_aba10_nao_e_mais_a_unica_com_vao_entre_o_titulo_e_o_corpo() -> None:
    """As dez abas medidas juntas: nenhuma reserva espaço que não usa."""
    vaos = {aba: _no_chrome(onde.pagina(aba, publicado=True), O_VAO)
            for aba in ABAS}
    medidos = {a: v for a, v in vaos.items() if v is not None}
    assert medidos, "nenhuma das dez páginas tem `.quadro-topo` e `.quadro-corpo`"
    piso = min(medidos.values())
    fora = {a: v for a, v in medidos.items() if v > piso}
    assert not fora, (
        f"a(s) aba(s) {fora} reservam espaço entre o título do quadro e o corpo "
        f"que as outras não reservam (o piso das dez é {piso}px). Ela chamou "
        f"isso de 'espaço vertical bizarro desnecessário no título' em 05/09.")


def test_a_tira_acesa_volta_as_duas_linhas_de_antes(tira: dict) -> None:
    """30px, 7px de folga, e as duas linhas: o recado chega igual ao de antes."""
    acesa = tira["acesa"]
    assert acesa["visivel"] == "visible", (
        "a tira com recado continuou invisível — o desfecho de todo gesto que "
        "escreve no disco dela voltaria ao silêncio")
    assert acesa["altura"] == 30 and acesa["folga"] == 7, (
        f"a tira acesa mede {acesa['altura']}px de altura e {acesa['folga']}px "
        f"de folga; eram 30 e 7 antes de a banda vazia sair. A cura da banda "
        f"morta não pode encolher a tira que TEM recado.")
    assert acesa["vao"] == 37, (
        f"o vão entre o título e o corpo com recado é {acesa['vao']}px — eram "
        f"37, que é o que a tira ocupava o tempo todo antes de 05/09")


def test_a_frase_longa_para_na_segunda_linha_e_nao_vaza(tira: dict) -> None:
    """O `-webkit-line-clamp:2` sobreviveu à cura — decisão [05] do PO."""
    acesa = tira["acesa"]
    assert acesa["linhas"] == "2", (
        f"a tira perdeu o `-webkit-line-clamp:2` (diz `{acesa['linhas']}`) — a "
        f"frase longa volta a ser cortada com reticências numa linha só")
    assert not acesa["transbordou"], (
        "a frase longa vazou para fora da caixa de duas linhas — o clamp existe "
        "e não está segurando")
