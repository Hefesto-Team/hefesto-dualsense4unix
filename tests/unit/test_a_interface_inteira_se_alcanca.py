"""A interface inteira se alcança pelo controle e pelo teclado.

Três contratos, medidos no Chrome sobre os DESENHOS (`mockup/`), em todas as páginas:

1. TUDO O QUE O MOUSE ALCANÇA TEM PARADA NO TAB. Todo `data-gesto`, `data-hef-gesto`, link e
   botão visível tem `tabIndex >= 0`: o chip da fita, o grau da régua, a alça de uma coluna.
2. A NAVEGAÇÃO INTERNA ENXERGA O MESMO QUE O MOUSE. O seletor dela (`NAV_INSTALAR`) pega todo
   link e botão visível (a barra das abas, o «Voltar» da calibração), e uma tela fechada não
   conta como janela aberta: nenhuma página nasce com `popup` sem caixa dentro, que suprimia o
   R1 e o L1 e deixava a página inteira fora do alcance do controle.
3. A TELA POR CIMA É UM DIÁLOGO. Aberta por âncora, o foco entra nela, nenhuma caixa da
   Navegação fica atrás dela, o Tab fica dentro e o Esc fecha.
4. O TECLADO ACIONA. Enter e Espaço clicam o gesto que não é botão, e o Esc devolve o foco a
   quem abriu a tela.

MORDIDAS (cada uma tira UMA cura de uma cópia da página e a régua tem de reprovar): sem o
contrato do alcance; sem o `tabindex` posto; sem `a[href],button` no seletor; sem o
`presente(d)` do `aberta()`; sem o `el.click()` do Enter; sem o `quemAbriu.focus()`.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from collections.abc import Callable, Iterator
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(RAIZ / "scripts")):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import chrome_sem_rede  # o ponto comum dos portões de página, sem a rede

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.interface import hefesto_vivo

CHROME = pathlib.Path("/usr/bin/google-chrome")
MOCKUP = RAIZ / "mockup"
LARGURA, ALTURA = 1212, 809
MARCA_DO_CONTRATO = "/* O alcance pelo teclado e pelo controle ("


def _paginas() -> list[pathlib.Path]:
    return sorted(
        p for p in MOCKUP.glob("*.html")
        if 'id="base-comum"' in p.read_text(encoding="utf-8"))


def _seletor_da_navegacao(nav_js: str) -> str:
    """O `SEL` do JS da navegação, como expressão: a régua usa o seletor DE VERDADE."""
    achado = re.search(r"const SEL = (.*?);\n", nav_js, flags=re.S)
    assert achado, "a navegação perdeu o seletor"
    return achado.group(1)


_JS_DA_MEDIDA = """() => {
  const SEL = __SELETOR__;
  const visivel = el => {
    if (el.closest('[aria-hidden="true"],[inert],[hidden]') || el.disabled) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
  };
  const nome = el => el.tagName + '.' + (typeof el.className === 'string' ? el.className : '') +
    '[' + (el.dataset.gesto || el.dataset.hefGesto || el.getAttribute('href') || el.id || '') + ']';
  const mouse = Array.from(document.querySelectorAll(
    SEL + ',[data-gesto],[data-hef-gesto],a[href],button')).filter(visivel);
  const semParada = mouse.filter(el => el.tabIndex < 0).map(nome);
  const foraDoSel = mouse.filter(el => !el.matches(SEL)).map(nome);
  return {mouse: mouse.length, semParada, foraDoSel};
}"""


def _js_da_medida(seletor: str) -> str:
    """O que o mouse alcança e o Tab tem de alcançar também, medido sobre o que se VÊ."""
    return _JS_DA_MEDIDA.replace("__SELETOR__", seletor)


_JS_DA_TELA = """(id) => {
  const tela = document.getElementById(id);
  const caixa = tela && (tela.querySelector('.tn-cx') || tela.firstElementChild);
  return {
    alvo: !!tela && tela === document.querySelector('.tela-nova:target'),
    foco: !!tela && tela.contains(document.activeElement),
    papel: caixa ? caixa.getAttribute('role') : null,
  };
}"""

_JS_DAS_CAIXAS_ATRAS = """(id) => {
  const tela = document.getElementById(id);
  const lei = JSON.parse(window.__hefNav.ler());
  const atras = [];
  for (const c of lei.caixas) {
    const x = c.x + c.w / 2, y = c.y + c.h / 2;
    if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
    const topo = document.elementFromPoint(x, y);
    if (!topo || !tela.contains(topo)) atras.push(c.endereco);
  }
  return {popup: lei.popup, caixas: lei.caixas.length, atras};
}"""

_JS_DAS_PARADAS = """(id) => {
  const t = document.getElementById(id);
  const q = 'a[href],button:not([disabled]),input:not([type=hidden]):not([disabled]),'
    + 'select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
  return Array.from(t.querySelectorAll(q)).filter(e => e.getClientRects().length > 0).length;
}"""

_JS_DENTRO = """(id) => {
  const t = document.getElementById(id);
  return !!t && t.contains(document.activeElement);
}"""


def _abrir(navegador: Any, arquivo: pathlib.Path, ancora: str = "") -> Any:
    destino = arquivo.as_uri() + (f"#{ancora}" if ancora else "")
    pg, _ = chrome_sem_rede.abrir_sem_rede(navegador, destino, largura=LARGURA, altura=ALTURA)
    return pg


def medir_pagina(navegador: Any, arquivo: pathlib.Path, nav_js: str) -> dict[str, Any]:
    """Tudo o que a régua precisa de UMA página: a parada, o seletor, o popup e cada tela."""
    seletor = _seletor_da_navegacao(nav_js)
    pg = _abrir(navegador, arquivo)
    try:
        pg.evaluate(nav_js)
        parado = pg.evaluate(_js_da_medida(seletor))
        lei = json.loads(pg.evaluate("window.__hefNav.ler()"))
        telas = pg.evaluate(
            "() => Array.from(document.querySelectorAll('.tela-nova'))"
            ".map(t => t.id).filter(Boolean)")
    finally:
        pg.close()
    # Janela «aberta» sem nenhuma caixa dentro é o defeito: a página fica fora do alcance.
    saida: dict[str, Any] = {
        "parado": parado, "popup_parado": lei["popup"] and not lei["caixas"], "telas": {}}
    for tela in telas:
        saida["telas"][tela] = _medir_tela(navegador, arquivo, nav_js, seletor, tela)
    return saida


def _medir_tela(
    navegador: Any, arquivo: pathlib.Path, nav_js: str, seletor: str, tela: str
) -> dict[str, Any]:
    pg = _abrir(navegador, arquivo, tela)
    try:
        pg.evaluate(nav_js)
        pg.wait_for_timeout(50)
        aberta = pg.evaluate(_JS_DA_TELA, tela)
        atras = pg.evaluate(_JS_DAS_CAIXAS_ATRAS, tela)
        dentro = pg.evaluate(_js_da_medida(seletor))
        paradas = pg.evaluate(_JS_DAS_PARADAS, tela)
        fugiu = []
        for passo in range(paradas + 3):
            pg.keyboard.press("Tab")
            if not pg.evaluate(_JS_DENTRO, tela):
                fugiu.append(passo)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(50)
        fechou = pg.evaluate("() => !document.querySelector('.tela-nova:target')")
    finally:
        pg.close()
    return {"aberta": aberta, "atras": atras, "paradas": paradas, "fugiu": fugiu,
            "fechou": fechou, "dentro": dentro}


@pytest.fixture(scope="module")
def navegador() -> Iterator[Any]:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            yield nav
        finally:
            nav.close()


@pytest.fixture(scope="module")
def medidas(navegador: Any) -> dict[str, dict[str, Any]]:
    return {p.name: medir_pagina(navegador, p, hefesto_vivo.NAV_INSTALAR) for p in _paginas()}


def _problemas(medidas: dict[str, dict[str, Any]]) -> list[str]:
    """Toda reprovação da régua, uma por linha — a mesma lista serve ao teste e às mordidas."""
    achados: list[str] = []
    for pagina, m in medidas.items():
        p = m["parado"]
        if p["semParada"]:
            achados.append(f"{pagina}: sem parada no Tab: {p['semParada'][:6]}")
        if p["foraDoSel"]:
            achados.append(f"{pagina}: a navegação não enxerga: {p['foraDoSel'][:6]}")
        if m["popup_parado"]:
            achados.append(f"{pagina}: nasce com janela aberta (popup) sem uma caixa dentro")
        for tela, t in m["telas"].items():
            aqui = f"{pagina}#{tela}"
            if not t["aberta"]["alvo"]:
                achados.append(f"{aqui}: a âncora não abriu a tela")
                continue
            if t["aberta"]["papel"] != "dialog":
                achados.append(f"{aqui}: a caixa não é um diálogo (role={t['aberta']['papel']})")
            if not t["aberta"]["foco"]:
                achados.append(f"{aqui}: o foco não entrou na tela")
            if not t["atras"]["popup"]:
                achados.append(f"{aqui}: a navegação não vê a tela como janela aberta")
            if t["atras"]["atras"]:
                achados.append(f"{aqui}: caixas da navegação atrás: {t['atras']['atras'][:4]}")
            if t["fugiu"]:
                achados.append(f"{aqui}: o Tab saiu da tela nos passos {t['fugiu']}")
            if not t["fechou"]:
                achados.append(f"{aqui}: o Esc não fechou a tela")
            d = t["dentro"]
            if d["semParada"] or d["foraDoSel"]:
                achados.append(
                    f"{aqui}: dentro da tela: sem parada {d['semParada'][:4]},"
                    f" fora do seletor {d['foraDoSel'][:4]}")
    return achados


def test_as_paginas_do_desenho_estao_todas_na_medida(medidas: dict[str, dict[str, Any]]) -> None:
    """A régua mede as dez abas, a calibração e os mapas: uma lista vazia não é verde."""
    nomes = set(medidas)
    for esperado in ("01-jogar.html", "06-navegacao.html", "08-conexoes.html",
                     "10-perfis.html", "calibrar-sensores.html", "mapa-do-controle.html"):
        assert esperado in nomes, esperado
    assert len(nomes) >= 13, sorted(nomes)
    assert sum(m["parado"]["mouse"] for m in medidas.values()) > 300
    telas = sum(len(m["telas"]) for m in medidas.values())
    assert telas >= 5, "sem tela por âncora, a régua não mede o diálogo"


def test_a_interface_inteira_se_alcanca(medidas: dict[str, dict[str, Any]]) -> None:
    achados = _problemas(medidas)
    assert not achados, "\n".join(achados)


def test_a_06_e_a_08_nao_nascem_com_janela_aberta(medidas: dict[str, dict[str, Any]]) -> None:
    """A causa de 16/10: o `aberta()` pegava o diálogo escondido e o R1/L1 morria nas duas."""
    for pagina in ("06-navegacao.html", "08-conexoes.html"):
        assert medidas[pagina]["popup_parado"] is False, pagina


def test_a_barra_das_abas_e_a_calibracao_entram_na_navegacao(navegador: Any) -> None:
    """O que o seletor velho não tinha: as abas 06 a 10 e o «Voltar» da calibração."""
    seletor = _seletor_da_navegacao(hefesto_vivo.NAV_INSTALAR)
    assert "a[href]" in seletor and "button" in seletor
    pedidos = (("06-navegacao.html", "a.aba"), ("calibrar-sensores.html", "a.voltar,a.btn"))
    for pagina, quem in pedidos:
        pg = _abrir(navegador, MOCKUP / pagina)
        try:
            pg.evaluate(hefesto_vivo.NAV_INSTALAR)
            lei = json.loads(pg.evaluate("window.__hefNav.ler()"))
            visiveis = pg.evaluate(
                "(q) => Array.from(document.querySelectorAll(q)).filter(e => !e.disabled &&"
                " e.getBoundingClientRect().width > 0 && !e.closest('.tela-nova')).map(e =>"
                " e.getAttribute('href') || e.textContent.trim().slice(0, 24))", quem)
        finally:
            pg.close()
        enderecos = " ".join(c["endereco"] for c in lei["caixas"])
        faltam = [v for v in visiveis if v and v not in enderecos]
        assert visiveis and not faltam, f"{pagina}: a navegação não enxerga {faltam[:5]}"


# ---- as mordidas: tirar UMA cura de uma cópia e ver a régua reprovar ----------------------


def _sem_o_contrato(texto: str) -> str:
    """A página sem o IIFE do alcance (do marcador até o fim do `<script id="base-comum">`)."""
    ini = texto.index(MARCA_DO_CONTRATO)
    fim = texto.index("</script>", ini)
    return texto[:ini] + texto[fim:]


def _sem_o_tabindex(texto: str) -> str:
    assert texto.count("el.setAttribute('tabindex', '0')") == 1
    return texto.replace("el.setAttribute('tabindex', '0')", "void 0")


def _mordida(
    navegador: Any,
    tmp_path: pathlib.Path,
    pagina: str,
    mexe_no_html: Callable[[str], str] | None = None,
    nav_js: str | None = None,
) -> list[str]:
    texto = (MOCKUP / pagina).read_text(encoding="utf-8")
    if mexe_no_html:
        texto = mexe_no_html(texto)
    copia = tmp_path / pagina
    copia.write_text(texto, encoding="utf-8")
    medida = medir_pagina(navegador, copia, nav_js or hefesto_vivo.NAV_INSTALAR)
    return _problemas({pagina: medida})


def test_morde_sem_o_contrato_do_alcance(navegador: Any, tmp_path: pathlib.Path) -> None:
    # 06: tem a tela por âncora (sem o diálogo e o Tab preso a régua reprova); 01: tem a fita.
    assert _mordida(navegador, tmp_path, "06-navegacao.html", _sem_o_contrato)
    assert _mordida(navegador, tmp_path, "01-jogar.html", _sem_o_contrato)


def test_morde_sem_o_tabindex_posto(navegador: Any, tmp_path: pathlib.Path) -> None:
    achados = _mordida(navegador, tmp_path, "01-jogar.html", _sem_o_tabindex)
    assert any("sem parada no Tab" in a for a in achados), achados


def test_morde_sem_link_e_botao_no_seletor(navegador: Any, tmp_path: pathlib.Path) -> None:
    velho = hefesto_vivo.NAV_INSTALAR
    assert velho.count(",a[href],button'") == 1
    achados = _mordida(navegador, tmp_path, "calibrar-sensores.html",
                       nav_js=velho.replace(",a[href],button'", "'"))
    assert any("a navegação não enxerga" in a for a in achados), achados


def test_morde_sem_o_presente_do_aberta(navegador: Any, tmp_path: pathlib.Path) -> None:
    velho = hefesto_vivo.NAV_INSTALAR
    assert velho.count(" && presente(d)") == 1
    achados = _mordida(navegador, tmp_path, "06-navegacao.html",
                       nav_js=velho.replace(" && presente(d)", ""))
    assert any("nasce com janela aberta" in a for a in achados), achados


# ---- o teclado aciona e o foco volta: Enter e Espaço clicam, e o Esc devolve o foco -----------

_JS_DO_GESTO = """() => {
  const NATIVO = 'a[href],button,input,select,textarea,summary';
  const el = Array.from(document.querySelectorAll('[data-gesto],[data-hef-gesto]')).find(e =>
    !e.matches(NATIVO) && !e.closest('.tela-nova') && e.getBoundingClientRect().width > 0);
  if (!el) return null;
  window.__cliques = 0;
  el.addEventListener('click', ev => {
    window.__cliques++; ev.preventDefault(); ev.stopImmediatePropagation();
  }, true);
  el.focus();
  return document.activeElement === el ? (el.dataset.gesto || el.dataset.hefGesto) : null;
}"""


def medir_o_teclado(
    navegador: Any, arquivo: pathlib.Path, volta: pathlib.Path, abre: str
) -> dict[str, Any]:
    """Enter e Espaço num gesto que não é botão (`arquivo`), e o foco de volta a quem abriu a
    tela `abre` (`volta`)."""
    pg = _abrir(navegador, arquivo)
    try:
        gesto = pg.evaluate(_JS_DO_GESTO)
        pg.keyboard.press("Enter")
        pg.keyboard.press(" ")
        cliques = pg.evaluate("() => window.__cliques")
    finally:
        pg.close()
    pg = _abrir(navegador, volta)
    try:
        pg.focus(f'a[href="#{abre}"]')
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(50)
        dentro = pg.evaluate(_JS_DENTRO, abre)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(50)
        voltou = pg.evaluate(
            "(id) => document.activeElement && document.activeElement.matches"
            "(`a[href=\"#${id}\"]`) && !document.querySelector('.tela-nova:target')", abre)
    finally:
        pg.close()
    return {"gesto": gesto, "cliques": cliques, "dentro": dentro, "voltou": voltou}


def test_enter_e_espaco_clicam_o_gesto_e_o_esc_devolve_o_foco(navegador: Any) -> None:
    m = medir_o_teclado(
        navegador, MOCKUP / "01-jogar.html", MOCKUP / "06-navegacao.html", "acessibilidade")
    assert m["gesto"], "a 01 perdeu o gesto que não é botão: a régua não mede o Enter"
    assert m["cliques"] == 2, f"Enter e Espaço não clicaram o gesto {m['gesto']}: {m}"
    assert m["dentro"], "o Enter no link não pôs o foco dentro da tela"
    assert m["voltou"], "o Esc fechou e o foco não voltou ao link que abriu a tela"


def test_morde_sem_o_clique_do_enter_e_sem_o_foco_que_volta(
    navegador: Any, tmp_path: pathlib.Path,
) -> None:
    for cura, chave in (("    el.click();\n", "cliques"), ("quemAbriu.focus(); ", "voltou")):
        copias = []
        for pagina in ("01-jogar.html", "06-navegacao.html"):
            texto = (MOCKUP / pagina).read_text(encoding="utf-8")
            assert texto.count(cura) == 1, (pagina, cura)
            copia = tmp_path / f"sem-{chave}-{pagina}"
            copia.write_text(texto.replace(cura, ""), encoding="utf-8")
            copias.append(copia)
        m = medir_o_teclado(navegador, copias[0], copias[1], "acessibilidade")
        assert m["gesto"] and m[chave] in (0, False), (
            f"sem {cura.strip()!r} a régua não reprovou: {m}")
