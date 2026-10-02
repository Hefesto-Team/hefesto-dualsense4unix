"""O Check-up da aba Conexões mostra TODO achado, e não inventa nenhum."""
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
def tela():
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
            pg.add_style_tag(content=FOLHA_DA_CASA)
            pg.evaluate(
                "window.webkit={messageHandlers:{hefesto:{postMessage:function(){}}}};")
            pg.evaluate(_bootstrap())
            yield pg
        finally:
            navegador.close()


def _linhas(pg, n: int) -> list[dict]:
    """Pinta `n` achados — TRÊS tiques — e devolve o que está na tela."""
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
    """Bloco do desenho sem item some — NUNCA vira uma linha de travessão."""
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
    """Doze achados e depois três: os nove clones SAEM do DOM."""
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
    """A rede de `60vh` — a resposta à pergunta dela sobre a resolução da tela."""
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
