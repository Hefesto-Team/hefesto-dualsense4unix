"""O exame fica com 46% da largura, e a Sugestão de Conexão nunca some."""

from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
GERADOR = RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py"
PAGINA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html"
EXAME = RAIZ / "src/hefesto_dualsense4unix/integrations/exame_da_mesa.py"

#: (noqa-acento: citação literal dela)
TETO_DA_FRASE = 70

REGRAS = (
    ".duas-colunas:has(.col-exame){grid-template-columns:minmax(0,46%) minmax(0,1fr);",
    ".lado-d .sugestao .col-ordem > .ordem{align-items:stretch}",
    ".sugestao .nada-a-mudar{",
)

AS_QUE_ESCONDIAM = (
    ".duas-colunas:has(.col-exame){grid-template-columns:1.7fr 1fr}",
    ".duas-colunas:has(.col-exame):has(.col-ordem:empty)",
    ".duas-colunas:has(.col-exame):has(.col-ordem > .nada:only-child)",
)

CHROME = pathlib.Path("/usr/bin/google-chrome")


@pytest.mark.parametrize("regra", REGRAS)
def test_o_gerador_traz_as_tres_regras(regra: str) -> None:
    assert regra in GERADOR.read_text(encoding="utf-8"), (
        "sem esta regra a coluna do exame volta à metade exata, e o achado "
        "mais longo quebra em duas linhas a partir de 1200 px"
    )


@pytest.mark.parametrize("regra", REGRAS)
def test_a_pagina_publicada_traz_as_tres(regra: str) -> None:
    """Curar o gerador e não publicar deixa a tela dela igual."""
    if not PAGINA.exists():  # pragma: no cover — árvore sem a página publicada
        pytest.skip(f"{PAGINA.name} não está publicada nesta árvore")
    assert regra in PAGINA.read_text(encoding="utf-8"), (
        "falta `check_o_desenho_aprovado.py --publicar 08`"
    )


@pytest.mark.parametrize("regra", AS_QUE_ESCONDIAM)
def test_nenhuma_regra_que_escondia_a_caixa_voltou(regra: str) -> None:
    """A caixa não some mais (26/09): nenhuma regra de 19/09 volta à página."""
    for pagina in (PAGINA, RAIZ / "mockup/08-conexoes.html"):
        assert regra not in pagina.read_text(encoding="utf-8"), (
            f"{pagina.name} voltou a trazer `{regra}` — a Sugestão de Conexão "
            "sumiria na tela sem ajuste, a foto de *«pq sumiu a parte da caixinha»*")


def frases_do_exame() -> list[str]:
    fonte = EXAME.read_text(encoding="utf-8")
    achadas = []
    for bloco in re.finditer(r'porque=\(?\s*((?:f?"[^"]*"\s*)+)\)?', fonte):
        achadas.append("".join(re.findall(r'"([^"]*)"', bloco.group(1))))
    return achadas


def test_ha_frases_para_medir() -> None:
    """Conjunto vazio não é verde — é a régua medindo o nada."""
    assert len(frases_do_exame()) >= 15, "o extrator perdeu as frases do exame"


def test_nenhuma_frase_do_exame_passa_do_teto() -> None:
    """*"resume mais pra ter uma linha só"* — a ordem dela, virada número."""
    longas = [f for f in frases_do_exame() if len(f) > TETO_DA_FRASE]
    assert not longas, "\n".join(
        f"  {len(f)} caracteres: {f}" for f in longas
    ) + (
        f"\n\n{len(longas)} frase(s) acima de {TETO_DA_FRASE} — elas quebram a "
        "linha do achado, que é o que a CHECKUP-VAO-01 veio fechar"
    )


def _bootstrap() -> str:
    """O `BOOTSTRAP` do piloto, lido do fonte SEM importar `gi`."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto — a régua ficaria verde sobre nada"
    return m.group(1)


@pytest.fixture(scope="module")
def tela():
    """A `08-conexoes` publicada, num Chrome, com o piloto e a folha da casa."""
    if not CHROME.exists():  # pragma: no cover — CI sem o Chrome do sistema
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    from playwright.sync_api import sync_playwright

    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 780})
            pg.goto(onde.pagina("08-conexoes.html", publicado=True).as_uri())
            pg.add_style_tag(content=FOLHA_DA_CASA)
            pg.evaluate(
                "window.webkit={messageHandlers:{hefesto:{postMessage:function(){}}}};")
            pg.evaluate(_bootstrap())
            yield pg
        finally:
            navegador.close()


def _larguras(pg, ordem: str, achados: int = 8) -> dict:
    """Pinta um tique com essa coluna da direita e mede os dois blocos."""
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_ATENCAO

    pg.evaluate("p => window.__hef.pintar(p)", {"mesa": {
        "achado": [f"achado {i + 1}" for i in range(achados)],
        "achado-explica": ["<b>x</b>"] * achados,
        "selo-estado": [ESTADO_ATENCAO] * achados,
        "exame-calada": [""] * achados,
        "ignorar-dica": [""] * achados,
        "ordem": ordem,
    }})
    return pg.evaluate("""() => {
        const e = document.querySelector('.lado-e').getBoundingClientRect();
        const d = document.querySelector('.lado-d');
        const s = document.querySelector('.sugestao');
        const r = s.getBoundingClientRect();
        const nada = s.querySelector('.nada-a-mudar');
        const quadro = document.querySelector('.duas-colunas').getBoundingClientRect();
        return {esquerda: Math.round(e.width),
                direita: d.offsetHeight > 0 ? Math.round(r.width) : 0,
                quadro: Math.round(quadro.width),
                vao: Math.round(r.left - e.right),
                altura_e: Math.round(e.height), altura_d: Math.round(r.height),
                titulo: (s.querySelector('.ordem-tit') || {}).textContent || '',
                nada: nada && nada.offsetHeight > 0 ? nada.textContent : ''}}""")


def _a08():
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _os_dois_blocos_se_encostam(r: dict) -> None:
    assert r["direita"] > 300, (
        f"a Sugestão de Conexão ficou com {r['direita']}px — a caixa sumiu, que é "
        "a foto de *«pq sumiu a parte da caixinha no canto superior direito?»*")
    assert r["titulo"] == _a08().TITULO_DA_ORDEM, r
    assert r["vao"] == 10, f"a Sugestão não encosta no exame (vão de {r['vao']}px)"
    assert abs(r["altura_e"] - r["altura_d"]) <= 1, (
        f"os dois blocos não têm a mesma altura ({r['altura_e']} e {r['altura_d']} px)")
    assert r["esquerda"] <= round(r["quadro"] * 0.46) + 1, (
        f"o exame passou dos 46% ({r['esquerda']} de {r['quadro']}px)")


def test_sem_ajuste_a_caixa_fica_e_diz_que_nao_ha_o_que_mudar(tela) -> None:
    """O CASO DELA de 26/09: a aba sem ajuste — a caixa fica, com a frase."""
    a08 = _a08()
    r = _larguras(tela, a08._html_da_ordem([], None))
    _os_dois_blocos_se_encostam(r)
    assert r["nada"] == a08.NADA_A_MUDAR, r


def test_o_nada_a_dizer_do_piloto_tambem_nao_esconde_a_caixa(tela) -> None:
    """O filho invisível de 19/09 (`monta.NADA_A_DIZER`) não esconde mais nada."""
    import sys

    from hefesto_dualsense4unix.interface import onde as _onde

    sys.modules.setdefault("onde", _onde)
    from hefesto_dualsense4unix.interface.monta import NADA_A_DIZER

    _os_dois_blocos_se_encostam(_larguras(tela, NADA_A_DIZER))


def test_com_card_de_verdade_a_coluna_fica(tela) -> None:
    """Com um de→para a mostrar, a caixa fica, do mesmo tamanho do exame."""
    card = ('<div class="ordem"><div class="faca"><span class="n">1</span>Mova o '
            'adaptador</div><div class="receita">'
            '<span class="caixa">Entrada 3</span><span class="seta">→</span>'
            '<span class="caixa alvo">Entrada 9</span></div></div>')
    r = _larguras(tela, card)
    _os_dois_blocos_se_encostam(r)
    assert r["nada"] == "", r
