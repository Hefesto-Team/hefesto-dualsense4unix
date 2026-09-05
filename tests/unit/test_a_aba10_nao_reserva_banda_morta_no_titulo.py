#!/usr/bin/env python3
"""A tira do desfecho não ocupa espaço quando não há recado — medido em PIXELS.

QUEIXA DELA, 05/09/2026: *"a aba dez tem um espaço vertical bizarro
desnecessário no título"*.

O QUE ESTAVA LÁ, medido no Chrome sobre as DEZ páginas publicadas: um
``<div class="desfecho">`` vazio entre o ``.quadro-topo`` e o ``.quadro-corpo``,
com ``height:30px`` + ``margin-top:7px`` — **37px de banda morta logo abaixo do
título "Perfis"**, e a aba 10 era a ÚNICA das dez com vão entre topo e corpo
(as outras nove mediram ZERO). O espaço era reservado de propósito, para a lista
de 33 perfis não pular quando o desfecho de um gesto aparece; o custo era pago
em toda a vida da tela para poupar um pulo que acontece por clique.

**A CURA É COLAPSAR VAZIA E ABRIR CHEIA.** A altura e a folga saíram da regra de
repouso e foram para a ``.desfecho.on``: vazia a tira mede zero, acesa ela volta
aos MESMOS 30px de duas linhas mais os 7px. Nas outras nove abas o recado do
piloto (``.hef-recado``) já não paga nada — ele nasce quando há notícia.

POR QUE ESTA RÉGUA MEDE ALTURA, E NÃO A PRESENÇA DE UMA CLASSE
---------------------------------------------------------------
Porque foi uma régua de PRESENÇA que segurou o defeito: o ``monta()`` da aba
exigia ``height:30px`` na regra de repouso, com a mensagem *"a tira do desfecho
deixou de reservar o espaço"* — verde sobre os 37px que ela chamou de bizarros.
Uma régua que lê a folha de estilo não sabe quanto a folha vale em pixels; esta
pergunta ao motor.

A régua do ``monta()`` não foi apagada: ela se INVERTEU, e agora cobra que a
tira em repouso não tenha altura nem folga, e que as duas voltem na ``.on``.

O QUE ELA NÃO ALCANÇA: o WebKitGTK, que é o motor do produto. O Chrome aqui é da
mesma família (é a razão do prefixo ``-webkit-`` no ``line-clamp``), e a prova no
motor de verdade é a foto do ``hefesto_vivo.py --oculta``.

MORDIDA (provada em 05/09): devolva ``height:30px;margin-top:7px`` à regra
``.desfecho{…}`` de ``interface/aba10.py``, regere e publique — caem os dois
primeiros casos, dizendo *"a aba 10 reserva 37px de banda morta"*.
"""
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

#: AS DEZ ABAS PUBLICADAS. A lista é lida do disco, e não digitada: uma aba nova
#: entra na medição sozinha.
ABAS = sorted(p.name for p in onde.paginas(publicado=True)
              if p.name[:2].isdigit())

#: A FRASE MAIS LONGA QUE O DESFECHO CARREGA, e ela é o caso que decidiu as duas
#: linhas (decisão [05] do PO, 04/09): a ativação mais a carona da Steam passam
#: de 280 caracteres, e a linha de ~1.180px a 11px comporta ~200.
FRASE_LONGA = (
    "Perfil “Mortal Kombat 1” ativado — a carona da Steam foi reposta na Opção "
    "de Inicialização do jogo, e sem ela, no Bluetooth, o jogo tende a não "
    "enxergar controle nenhum. São 33 perfis no disco.")

#: O VÃO ENTRE O TÍTULO DO QUADRO E O CORPO DELE — é o que ela vê como "espaço
#: vertical no título". Medido do fundo do ``.quadro-topo`` ao topo do
#: ``.quadro-corpo``, que é onde a tira mora.
O_VAO = """
() => {
  const topo = document.querySelector('.quadro-topo');
  const corpo = document.querySelector('.quadro-corpo');
  if (!topo || !corpo) return null;
  return corpo.getBoundingClientRect().top
       - topo.getBoundingClientRect().bottom;
}
"""

#: A TIRA VAZIA E A TIRA ACESA, na mesma página e na mesma abertura. A acesa
#: recebe a frase longa pelo ``<span>`` de dentro, que é por onde o piloto a
#: escreve, e a classe ``on``, que é o que o alvo ``classe`` liga.
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


# ---------------------------------------------------------------------------
# 1. VAZIA, ELA NÃO OCUPA NADA
# ---------------------------------------------------------------------------
def test_a_tira_vazia_nao_ocupa_um_pixel(tira: dict) -> None:
    """Zero de altura e zero de folga — é a queixa dela, em números.

    Os 37px eram 30 de altura mais 7 de folga. A régua cobra os dois: cobrar só
    a altura deixaria a margem sozinha devolver metade do vão.
    """
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
    """As dez abas medidas juntas: nenhuma reserva espaço que não usa.

    A CONTA É CONTRA AS IRMÃS, e não contra um número digitado: foi assim que o
    defeito apareceu — a aba 10 marcava 37px e as outras nove marcavam 0. Se um
    dia o desenho decidir que TODO quadro tem um vão, esta régua acompanha
    sozinha, em vez de reprovar a decisão nova.
    """
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


# ---------------------------------------------------------------------------
# 2. ACESA, ELA VOLTA INTEIRA — a cura não pode ter custado o canal
# ---------------------------------------------------------------------------
def test_a_tira_acesa_volta_as_duas_linhas_de_antes(tira: dict) -> None:
    """30px, 7px de folga, e as duas linhas: o recado chega igual ao de antes.

    É a metade que a cura poderia ter comido em silêncio — uma tira que colapsa
    vazia e NÃO abre é o botão respondendo calado, que é o defeito que o
    desfecho nasceu para curar em 03/09.
    """
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
    """O `-webkit-line-clamp:2` sobreviveu à cura — decisão [05] do PO.

    Sem ele a frase de 280 caracteres vaza para fora da caixa; com ele ela para
    na segunda linha. O que a reticência come é o FIM da frase, e o fim é sempre
    a metade que avisa.
    """
    acesa = tira["acesa"]
    assert acesa["linhas"] == "2", (
        f"a tira perdeu o `-webkit-line-clamp:2` (diz `{acesa['linhas']}`) — a "
        f"frase longa volta a ser cortada com reticências numa linha só")
    assert not acesa["transbordou"], (
        "a frase longa vazou para fora da caixa de duas linhas — o clamp existe "
        "e não está segurando")
