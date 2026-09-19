"""O Check-up da aba Conexões mostra TODO achado, e não inventa nenhum.

DECISÃO DELA, 19/09/2026: *"A lista rola, sem teto — todo achado aparece."*

O QUE ESTA RÉGUA MEDE, e são DUAS pontas do mesmo defeito, as duas medidas na
página PUBLICADA antes de existir cura:

* **a lista que SOBRA sumia.** O desenho tem cinco blocos e o exame da bancada
  dela devolve sete: dois achados não chegavam à tela, e a tira ficava com
  cinco CERTO — a tela dizendo "está tudo bem" com dois achados abertos;
* **a lista que FALTA mentia.** Com três achados (uma máquina sem a bancada
  dela — e o produto é para qualquer computador), os dois blocos que sobravam
  ficavam com o travessão de `escrever(el, '')`. A tela INVENTAVA duas linhas.

UM TETO MAIOR NÃO CURARIA NENHUMA DAS DUAS: as conferências do exame devolvem
LISTAS (`a08_conexoes._conferencias`), uma porta problemática por item, e o
número de achados não tem máximo.

ELA DIRIGE A PÁGINA PUBLICADA NUM CHROME DE VERDADE, com o `BOOTSTRAP` lido do
fonte do piloto — é o mesmo instrumento de `test_a_tela_entrega_as_vinte_e_uma_
linhas`. Medir o HTML do gerador não serviria: quem clona é o piloto, e o
defeito só existe depois que a mesa chega.
"""
from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
CHROME = pathlib.Path("/usr/bin/google-chrome")
pytestmark = pytest.mark.skipif(
    not CHROME.exists(), reason="sem o Chrome do sistema — a régua não tem motor")


def _bootstrap() -> str:
    """O `BOOTSTRAP` do piloto, lido do fonte SEM importar `gi`."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto — a régua ficaria verde sobre nada"
    return m.group(1)


def _mesa(n: int) -> dict:
    """A carga de um tique com `n` achados — as cinco listas que o pacote emite."""
    return {"mesa": {
        "achado": [f"achado numero {i + 1}" for i in range(n)],
        "achado-explica": [f"<b>a dica {i + 1}</b>" for i in range(n)],
        "selo-estado": ["certo"] * n,
        "exame-calada": [""] * n,
        "ignorar-dica": [""] * n,
    }}


@pytest.fixture(scope="module")
def tela():  # o tipo é o `Page` do playwright, importado lá dentro
    """A `08-conexoes` publicada, com o piloto e a folha da casa no ar."""
    from playwright.sync_api import sync_playwright

    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA

    pagina = onde.pagina("08-conexoes.html", publicado=True)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 780})
            pg.goto(pagina.as_uri())
            # A FOLHA DA CASA entra à mão porque quem a injeta é o piloto GTK
            # (`hefesto_vivo`), não a página. Sem ela o `.hef-sem-item` seria
            # uma classe sem lâmpada, e a régua veria o bloco vazio aceso.
            pg.add_style_tag(content=FOLHA_DA_CASA)
            pg.evaluate(
                "window.webkit={messageHandlers:{hefesto:{postMessage:function(){}}}};")
            pg.evaluate(_bootstrap())
            yield pg
        finally:
            navegador.close()


def _linhas(pg, n: int) -> list[dict]:
    """Pinta `n` achados — TRÊS tiques — e devolve o que está na tela."""
    # TRÊS TIQUES E NÃO UM: a peça do molde tem de ser IDEMPOTENTE. Sem a marca
    # `data-hef-clone` o tique seguinte leria os clones como originais e a lista
    # dobraria a cada volta — o defeito que esta linha existe para pegar.
    for _ in range(3):
        pg.evaluate("p => window.__hef.pintar(p)", _mesa(n))
    return pg.evaluate("""() => Array.from(
        document.querySelectorAll('.col-exame .exame'))
        .filter(el => el.offsetHeight > 0)
        .map(el => ({texto: ((el.querySelector('[data-campo=achado]') || {})
                              .textContent || '').trim(),
                     clone: el.hasAttribute('data-hef-clone')}))""")


@pytest.mark.parametrize("quantos", [7, 12, 16])
def test_todo_achado_chega_a_tela_mesmo_passando_do_desenho(tela, quantos: int) -> None:
    """A lista maior que os cinco blocos do desenho NÃO perde nenhum item."""
    linhas = _linhas(tela, quantos)
    assert len(linhas) == quantos, (
        f"{quantos} achados na mesa e {len(linhas)} na tela. O molde parou de "
        f"clonar (`hefesto_vivo.BOOTSTRAP`, `data-hef-molde`) ou a "
        f"`.col-exame` perdeu o `data-hef-molde-conta`. Achado que não chega à "
        f"tela é a aba dizendo 'está tudo bem' sobre um problema aberto.")
    assert [x["texto"] for x in linhas] == [
        f"achado numero {i + 1}" for i in range(quantos)], (
        f"os achados chegaram fora de ordem ou repetidos: {linhas}")


@pytest.mark.parametrize("quantos", [1, 2, 3])
def test_a_tela_nao_inventa_achado_quando_a_lista_e_menor(tela, quantos: int) -> None:
    """Bloco do desenho sem item some — NUNCA vira uma linha de travessão.

    ESTE É O LADO QUE NINGUÉM TINHA VISTO, e ele é universal: a bancada dela
    devolve sete achados e enche os cinco blocos, mas o produto é para qualquer
    computador. Numa máquina sem controle no cabo o exame devolve TRÊS — medido
    em 19/09 com o `HOME` desviado — e as duas linhas que sobravam mostravam
    `—`. Uma tela que inventa achado é pior que uma que esconde: ela pede
    conferência de um problema que não existe.
    """
    linhas = _linhas(tela, quantos)
    assert len(linhas) == quantos, (
        f"{quantos} achados na mesa e {len(linhas)} linhas visíveis. "
        f"As que sobram deviam ter a classe `hef-sem-item` "
        f"(`folha_da_casa.FOLHA_DA_CASA`): {linhas}")
    tracos = [x for x in linhas if x["texto"] in ("—", "-", "")]
    assert not tracos, (
        f"a tela inventou {len(tracos)} achado(s) de travessão: {linhas}. O "
        f"`escrever(el, '')` do piloto troca vazio por `—` antes de olhar o "
        f"alvo — quem cura é esconder o bloco, não mandar vazio.")


def test_a_lista_que_encolhe_devolve_os_clones(tela) -> None:
    """Doze achados e depois três: os nove clones SAEM do DOM.

    Sem isto a aba acumularia um nó por achado que já houve, para sempre — e a
    próxima lista de doze encontraria vinte e um blocos.
    """
    _linhas(tela, 12)
    depois = tela.evaluate(
        "() => document.querySelectorAll('.col-exame .exame[data-hef-clone]').length")
    assert depois == 7, f"doze achados deviam deixar 7 clones, e deixaram {depois}"
    _linhas(tela, 3)
    sobraram = tela.evaluate(
        "() => document.querySelectorAll('.col-exame .exame[data-hef-clone]').length")
    assert sobraram == 0, (
        f"a lista encolheu para três e {sobraram} clone(s) ficaram no DOM. O "
        f"laço que remove o excedente parou de rodar.")


def test_a_coluna_rola_em_vez_de_empurrar_quando_a_tela_e_pequena(tela) -> None:
    """A rede de `60vh` — a resposta à pergunta dela sobre a resolução da tela.

    NUMA JANELA GRANDE ISTO NUNCA DISPARA, e é de propósito: medido a 1180x780,
    dezesseis achados terminam em y=527 com 250px de sobra. Rolagem dentro de
    tela vazia é pior que crescer. O que a régua exige é que o teto EXISTA e
    acompanhe a tela, para a coluna não empurrar o resto da aba para fora numa
    janela baixa.
    """
    teto = tela.evaluate(
        "() => getComputedStyle(document.querySelector('.col-exame')).maxHeight")
    assert teto.endswith("px") and float(teto[:-2]) > 0, (
        f"a `.col-exame` está sem `max-height` ({teto!r}): numa janela baixa "
        f"ela empurra os botões do Check-up para fora da tela.")
    janela = tela.evaluate("() => window.innerHeight")
    assert abs(float(teto[:-2]) - janela * 0.6) < 2, (
        f"o teto é {teto} numa janela de {janela}px — ele deixou de ser `60vh` "
        f"e virou um número cravado, que não acompanha a tela de quem usa.")
    rola = tela.evaluate(
        "() => getComputedStyle(document.querySelector('.col-exame')).overflowY")
    assert rola in ("auto", "scroll"), (
        f"a `.col-exame` tem `overflow-y:{rola}` — com o teto acima, o que "
        f"passar dele seria CORTADO em vez de rolar.")
