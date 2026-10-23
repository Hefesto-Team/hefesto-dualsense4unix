"""Os alvos e a letra crescem, e a interface ganha tamanho (20/10/2026).

O piso é dela (13/10: alvo de 24 px, o WCAG 2.2 critério 2.5.8, e nenhuma letra abaixo de 12 px).
A régua mede o que os GERADORES escrevem nas dez abas, não o publicado de ontem, com o Chrome do
sistema: todo elemento que age, todo título ou rótulo que abre uma dica (o `?` de 17 px é um deles),
todo texto visível, em quatro vistas e nos estados do acordeão da 02.

* **02 e 09 chegam a zero**, em toda vista: a escolha de 20/10 («Controles: A», «Sistema: A»).
* **As outras oito abas têm teto declarado** (`TETO_DAS_OUTRAS`): quanto cada uma ainda fica abaixo
  do piso HOJE. O teto só desce; tela que nasce pequena reprova. Zerar uma delas é o desenho dela,
  que a sprint seguinte pede (a escolha de 20/10 cobriu só a 02 e a 09).
* **O tamanho da interface** (`interface_escala`, escrito pela 09) é lido pela janela, que põe o
  zoom no WebView ao abrir e quando o arquivo muda (filho sob `xvfb-run`: a janela do pytest
  nasceria no compositor de quem roda).

MORDIDAS (todas executadas aqui, sobre cópias do HTML gerado):

* um «?» de 17 px focável na 02 -> `test_a_regua_morde_o_ponto_de_interrogacao_de_17_px`;
* a folha do piso arrancada da 02 e da 09 -> `test_a_regua_morde_a_folha_do_piso_arrancada`;
* uma letra de 11 px na 09 -> `test_a_regua_morde_a_letra_pequena`;
* um alvo pequeno a mais numa aba de teto -> `test_a_regua_morde_o_teto`;
* a vaga com os traços de volta -> `test_a_vaga_diz_so_player_n_desconectado`;
* a janela ignorando `interface_escala` -> `test_a_janela_le_o_tamanho_da_interface`;
* o 150 % que não cede na vista de 840 -> `test_a_regua_morde_o_tamanho_que_nao_cede` e o modo
  `nao-cede` de `test_a_janela_le_o_tamanho_da_interface`.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import pytest

from tests.conftest import skip_sem_gi_real

if TYPE_CHECKING:
    from playwright.sync_api import Browser

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup"
CHROME = pathlib.Path("/usr/bin/google-chrome")
#: as três vistas da casa e uma abaixo do desenho (1280x720), onde o piso de 24 e 12 px também vale
VISTAS = ((1212, 809), (1918, 840), (1212, 740), (1280, 720))
ESTADOS_02 = ("c-p1", "c-p2", "c-p3", "c-todos")
ABAS = (
    "01-jogar", "02-controles", "03-gatilhos", "04-iluminacao", "05-vibracao",
    "06-navegacao", "07-lancadores", "08-conexoes", "09-sistema", "10-perfis",
)
NO_PISO = ("02-controles", "09-sistema")
#: Quanto cada aba que a escolha de 20/10 não cobriu ainda fica abaixo do piso (vista 1212x809):
#: (alvos que agem, títulos que abrem dica, textos abaixo de 12 px). SÓ DESCE: quem zera tira
#: a linha daqui e põe a aba em NO_PISO; quem faz nascer um alvo pequeno reprova.
TETO_DAS_OUTRAS: dict[str, tuple[int, int, int]] = {
    "01-jogar": (0, 6, 43),
    "03-gatilhos": (2, 7, 22),
    "04-iluminacao": (2, 4, 47),
    "05-vibracao": (8, 3, 39),
    "06-navegacao": (0, 2, 20),
    "07-lancadores": (2, 2, 2),
    "08-conexoes": (4, 3, 29),
    "10-perfis": (0, 18, 76),
}
ID_DA_FOLHA = "piso-dos-alvos"

_MEDIDA = r"""() => {
 const corta = (e, r) => { let p = e.parentElement, x0 = r.left, y0 = r.top, x1 = r.right, y1 = r.bottom;
  while (p && p !== document.documentElement) { const c = getComputedStyle(p);
   if (c.display === 'none' || c.visibility === 'hidden') return false;
   if (['hidden', 'auto', 'scroll', 'clip'].includes(c.overflowX)
       || ['hidden', 'auto', 'scroll', 'clip'].includes(c.overflowY)) { const q = p.getBoundingClientRect();
    x0 = Math.max(x0, q.left); y0 = Math.max(y0, q.top); x1 = Math.min(x1, q.right); y1 = Math.min(y1, q.bottom);
    if (x1 - x0 < 1 || y1 - y0 < 1) return false; }
   p = p.parentElement; } return true; };
 const visivel = e => { const r = e.getBoundingClientRect(), c = getComputedStyle(e);
  if (r.width === 0 || r.height === 0 || c.visibility === 'hidden' || c.display === 'none') return false;
  if (parseFloat(c.opacity) === 0) return false; return corta(e, r); };
 const ACAO = 'button,a[href],input:not([type=hidden]),select,textarea,summary,[role=button],[role=switch],'
  + '[role=checkbox],[role=radio],[role=tab],[data-gesto],label[for]';
 const alvos = [], dicas = [], vistos = new Set();
 document.querySelectorAll(ACAO + ',[tabindex]:not([tabindex="-1"])').forEach(e => {
  if (vistos.has(e)) return; vistos.add(e);
  if (e.matches('input.radio-mesa')) return;
  if (!visivel(e)) return;
  const r = e.getBoundingClientRect();
  if (r.width < 24 || r.height < 24) {
   const o = (e.tagName + '.' + e.className + ' ' + (e.innerText || '').trim().slice(0, 20)
              + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
   (e.matches(ACAO) ? alvos : dicas).push(o); } });
 const letras = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
 while ((n = w.nextNode())) { const t = n.textContent.trim(); if (!t) continue; const e = n.parentElement;
  if (!e || ['SCRIPT', 'STYLE', 'OPTION', 'OPTGROUP'].includes(e.tagName) || !visivel(e)) continue;
  let fs = parseFloat(getComputedStyle(e).fontSize); const svg = e.closest('svg');
  if (svg && e.getScreenCTM) { const m = e.getScreenCTM(); if (m) fs = fs * Math.abs(m.a); }
  if (Math.round(fs * 100) / 100 < 12) letras.push(e.tagName + '.' + e.className + ' ' + t.slice(0, 20) + ' ' + fs); }
 const d = document.documentElement;
 return {alvos, dicas, letras, sobra: d.scrollHeight - d.clientHeight,
         lateral: d.scrollWidth > d.clientWidth + 1}; }"""  # noqa: E501

_ABRE = """(id) => { const e = document.getElementById(id);
  if (e) { e.checked = true; e.dispatchEvent(new Event('change', {bubbles: true})); } }"""


def _so_o_arquivo(rota: Any) -> None:
    """Fonte e imagem de fora não entram: a régua mede a página, e a rede não é do usuário."""
    if rota.request.url.startswith("file:"):
        rota.continue_()
    else:
        rota.abort()


@pytest.fixture(scope="module")
def geradas(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """As dez abas como os geradores as escrevem hoje, numa bancada de mentira."""
    bancada = tmp_path_factory.mktemp("bancada")
    for pagina in MOCKUP.glob("*.html"):
        shutil.copy(pagina, bancada / pagina.name)
    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ / "src"), HEFESTO_BANCADA=str(bancada))
    for aba in ABAS:
        numero = aba[:2]
        feito = subprocess.run(
            [sys.executable, "-m", f"hefesto_dualsense4unix.interface.aba{numero}"],
            env=ambiente, capture_output=True, text=True, timeout=300, check=False,
        )
        assert feito.returncode == 0, (aba, feito.stdout[-400:], feito.stderr[-800:])
    return bancada


@pytest.fixture(scope="module")
def navegador() -> Iterator[Browser]:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        yield nav
        nav.close()


def _medir(navegador: Browser, arquivo: pathlib.Path, vista: tuple[int, int] = VISTAS[0],
           estado: str = "") -> dict[str, Any]:
    pg = navegador.new_page(viewport={"width": vista[0], "height": vista[1]})
    try:
        # fonte e imagem de fora não entram: a régua mede a página, e a rede não é do usuário
        pg.route("**/*", _so_o_arquivo)
        pg.goto(arquivo.as_uri())
        pg.wait_for_timeout(300)
        if estado:
            pg.evaluate(_ABRE, estado)
            pg.wait_for_timeout(200)
        medida: dict[str, Any] = pg.evaluate(_MEDIDA)
        return medida
    finally:
        pg.close()


def _problemas(medida: dict[str, Any]) -> list[str]:
    """O que reprova o piso de uma aba que está nele: zero de tudo, e nenhuma rolagem lateral."""
    falta: list[str] = []
    if medida["alvos"]:
        falta.append(f"alvos abaixo de 24 px: {medida['alvos'][:3]}")
    if medida["dicas"]:
        falta.append(f"título ou rótulo que abre dica abaixo de 24 px: {medida['dicas'][:3]}")
    if medida["letras"]:
        falta.append(f"letra abaixo de 12 px: {medida['letras'][:3]}")
    if medida["lateral"]:
        falta.append("rolagem lateral")
    return falta


def _acima_do_teto(aba: str, medida: dict[str, Any]) -> list[str]:
    teto = TETO_DAS_OUTRAS[aba]
    visto = (len(medida["alvos"]), len(medida["dicas"]), len(medida["letras"]))
    falta: list[str] = []
    for nome, v, t in zip(("alvos", "dicas", "letras"), visto, teto, strict=True):
        if v > t:
            falta.append(f"{aba}: {v} {nome} abaixo do piso, e o teto é {t}")
    return falta


def _casos_do_piso() -> list[tuple[str, tuple[int, int], str]]:
    casos: list[tuple[str, tuple[int, int], str]] = []
    for aba in NO_PISO:
        for vista in VISTAS:
            for estado in (ESTADOS_02 if aba.startswith("02") else ("",)):
                casos.append((aba, vista, estado))
    return casos


@pytest.mark.parametrize(("aba", "vista", "estado"), _casos_do_piso())
def test_a_02_e_a_09_estao_no_piso_em_toda_vista(
    navegador: Browser, geradas: pathlib.Path, aba: str, vista: tuple[int, int], estado: str
) -> None:
    """Zero alvo abaixo de 24 px (a dica inclusive) e zero letra abaixo de 12 px.

    A prova da D-2010-O-PISO-DE-24-PX-E-12-PX-VALE-NAS-ABAS-02-E-09.
    """
    medida = _medir(navegador, geradas / f"{aba}.html", vista, estado)
    assert _problemas(medida) == [], (aba, vista, estado)


@pytest.mark.parametrize("aba", sorted(TETO_DAS_OUTRAS))
def test_as_outras_abas_nao_passam_do_teto(
    navegador: Browser, geradas: pathlib.Path, aba: str
) -> None:
    """Aba que a escolha de 20/10 não cobriu: o que está abaixo do piso hoje não cresce."""
    assert aba not in NO_PISO
    assert _acima_do_teto(aba, _medir(navegador, geradas / f"{aba}.html")) == []


def test_o_teto_so_cobre_as_abas_fora_do_piso() -> None:
    assert set(TETO_DAS_OUTRAS) | set(NO_PISO) == set(ABAS)
    assert not set(TETO_DAS_OUTRAS) & set(NO_PISO)


@pytest.mark.parametrize("aba", NO_PISO)
def test_o_mockup_e_o_que_o_gerador_escreve(geradas: pathlib.Path, aba: str) -> None:
    """O desenho aprovado mora no gerador: regerar não muda um byte do `mockup/`."""
    assert (geradas / f"{aba}.html").read_bytes() == (MOCKUP / f"{aba}.html").read_bytes(), aba


def test_o_piso_e_uma_folha_so() -> None:
    """24 px e 12 px moram em `folha_da_casa.py`; nenhuma aba carrega número próprio."""
    from hefesto_dualsense4unix.interface import folha_da_casa as fc

    assert (fc.ALVO_MINIMO_PX, fc.LETRA_MINIMA_PX) == (24, 12)
    assert set(fc.PISO_POR_PAGINA) == set(NO_PISO)
    for aba in NO_PISO:
        doc = (MOCKUP / f"{aba}.html").read_text(encoding="utf-8")
        assert doc.count(f'<style id="{ID_DA_FOLHA}">') == 1, aba
        assert doc.index(ID_DA_FOLHA) < doc.index("</head>"), f"a folha da {aba} está no corpo"
        assert fc.PISO_POR_PAGINA[aba] in doc, aba
        assert "variante-alvos" not in doc, f"a folha da variante da {aba} ficou no desenho"
    for gerador in ("aba02.py", "aba09.py"):
        fonte = (RAIZ / "src/hefesto_dualsense4unix/interface" / gerador).read_text("utf-8")
        assert "com_o_piso(" in fonte, gerador
        assert not re.search(r"min-(height|width):\s*24px", fonte), (
            f"{gerador} guarda o piso por conta própria"
        )


# ---------------------------------------------------------------------------------------------
# O tamanho cede onde não cabe (O-TAMANHO-DE-150-NAO-CABE-NA-VISTA-DE-840-PX-01)
# ---------------------------------------------------------------------------------------------

#: As vistas da janela em pixels da tela (a de quem usa e a menor) e os tamanhos acima de 100.
VISTAS_DA_JANELA = ((1918, 840), (1212, 809))
TAMANHOS_GRANDES = (125, 150)

_ROLAGENS = r"""() => { const fora = [];
 document.querySelectorAll('body *').forEach(e => { const c = getComputedStyle(e);
  if (c.display === 'none' || c.visibility === 'hidden') return;
  const r = e.getBoundingClientRect(); if (r.width === 0 || r.height === 0) return;
  const y = ['auto', 'scroll'].includes(c.overflowY) && e.scrollHeight > e.clientHeight + 1;
  const x = ['auto', 'scroll'].includes(c.overflowX) && e.scrollWidth > e.clientWidth + 1;
  const quem = e.tagName + '.' + String(e.className).split(' ')[0];
  if (y) fora.push('rola por dentro: ' + quem);
  if (x) fora.push('rola de lado por dentro: ' + quem); });
 const d = document.documentElement;
 return {sobra: d.scrollHeight - d.clientHeight, lateral: d.scrollWidth > d.clientWidth + 1, fora}; }"""  # noqa: E501


def _vista_em_css(vista: tuple[int, int], escolhido: int,
                  cede: Any = None) -> tuple[int, int]:
    """O que o WebKit vê com o zoom em uso: a vista da janela dividida pelo tamanho que a janela
    aplica (`folha_da_casa.tamanho_que_cabe`, o mesmo que a `janela.JanelaDaAba` chama)."""
    from hefesto_dualsense4unix.interface import folha_da_casa as fc

    em_uso = (cede or fc.tamanho_que_cabe)(escolhido, *vista)
    return vista[0] * 100 // em_uso, vista[1] * 100 // em_uso


def _rolagens(navegador: Browser, arquivo: pathlib.Path, vista: tuple[int, int],
              estado: str = "") -> set[str]:
    """O que rola ou corta com a folha da casa por cima, como no produto: o documento (para baixo
    ou de lado) e todo painel que rola por dentro."""
    from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA

    pg = navegador.new_page(viewport={"width": vista[0], "height": vista[1]})
    try:
        pg.route("**/*", _so_o_arquivo)
        pg.goto(arquivo.as_uri())
        pg.add_style_tag(content=FOLHA_DA_CASA)
        pg.wait_for_timeout(300)
        if estado:
            pg.evaluate(_ABRE, estado)
            pg.wait_for_timeout(200)
        medida: dict[str, Any] = pg.evaluate(_ROLAGENS)
    finally:
        pg.close()
    achado = set(medida["fora"])
    if medida["sobra"] > 0:
        achado.add("o documento rola")
    if medida["lateral"]:
        achado.add("o documento rola de lado")
    return achado


def _casos_do_zoom() -> list[tuple[str, tuple[int, int], int, str]]:
    return [(aba, vista, escolhido, estado)
            for aba in ABAS for vista in VISTAS_DA_JANELA for escolhido in TAMANHOS_GRANDES
            for estado in (("", "c-todos") if aba.startswith("02") else ("",))]


@pytest.mark.parametrize(("aba", "vista", "escolhido", "estado"), _casos_do_zoom())
def test_o_tamanho_grande_cabe_na_janela(
    navegador: Browser, geradas: pathlib.Path, aba: str, vista: tuple[int, int],
    escolhido: int, estado: str,
) -> None:
    """125 % e 150 % na vista de quem usa (1918x840) e na menor (1212x809): nada rola nem corta
    além do que já rola a 100 % na mesma janela (a 100 %, só a 02 com os quatro abertos rola, no
    quadro, por desenho; o documento não rola em aba nenhuma).

    A escolha de 23/10/2026, «Cede onde não cabe»: a janela aplica o menor entre o escolhido e o
    que a vista comporta. A 150 % sem ceder, a vista de 840 vira 560 px em CSS, e a 04 rolava 72.
    """
    arquivo = geradas / f"{aba}.html"
    a_cem = _rolagens(navegador, arquivo, vista, estado)
    assert not {"o documento rola", "o documento rola de lado"} & a_cem, (aba, vista, estado)
    grande = _rolagens(navegador, arquivo, _vista_em_css(vista, escolhido), estado)
    assert grande - a_cem == set(), (aba, vista, escolhido, estado)


def test_o_que_cabe_e_o_menor_entre_o_escolhido_e_a_vista() -> None:
    """A conta da janela: 840 px de altura comportam 103 %; a vista alta, o escolhido; e nunca
    abaixo de 100, que é o tamanho de hoje."""
    from hefesto_dualsense4unix.interface.folha_da_casa import VISTA_DO_DESENHO, tamanho_que_cabe
    from hefesto_dualsense4unix.interface.janela import LARGURA_DO_DESENHO, PISO_DA_VISTA

    assert VISTA_DO_DESENHO == (LARGURA_DO_DESENHO, PISO_DA_VISTA) == (1212, 809)
    assert tamanho_que_cabe(150, 1918, 840) == 103
    assert tamanho_que_cabe(125, 1918, 840) == 103
    assert tamanho_que_cabe(150, 1212, 809) == 100
    assert tamanho_que_cabe(150, 1918, 1300) == 150
    assert tamanho_que_cabe(150, 1918, 1041) == 128
    assert tamanho_que_cabe(100, 1918, 1300) == 100
    assert tamanho_que_cabe(150, 940, 600) == 100
    for vista in ((1918, 840), (1212, 809), (1918, 1041), (1600, 900)):
        largura, altura = _vista_em_css(vista, 150)
        assert largura >= 1212 and altura >= 809, vista


def test_a_regua_morde_o_tamanho_que_nao_cede(
    navegador: Browser, geradas: pathlib.Path
) -> None:
    """MORDIDA: a 150 % sem ceder, a vista de 1918x840 é 1278x560 em CSS, e a 04 rola."""
    sem_ceder = _vista_em_css((1918, 840), 150, cede=lambda escolhido, _l, _a: escolhido)
    assert sem_ceder == (1278, 560)
    achado = _rolagens(navegador, geradas / "04-iluminacao.html", sem_ceder)
    assert "o documento rola" in achado, achado


# ---------------------------------------------------------------------------------------------
# A vaga: só o nome e «Desconectado»
# ---------------------------------------------------------------------------------------------

def _texto_da_vaga(navegador: Browser, arquivo: pathlib.Path, numero: int) -> str:
    pg = navegador.new_page(viewport={"width": VISTAS[0][0], "height": VISTAS[0][1]})
    try:
        pg.route("**/*", _so_o_arquivo)
        pg.goto(arquivo.as_uri())
        pg.wait_for_timeout(300)
        pg.evaluate(_ABRE, f"c-p{numero}")
        texto: str = pg.evaluate(
            f"() => document.querySelector('label.faixa[for=c-p{numero}]').innerText"
        )
        return re.sub(r"\s+", " ", texto).strip()
    finally:
        pg.close()


@pytest.mark.parametrize("numero", (3, 4))
def test_a_vaga_diz_so_player_n_desconectado(
    navegador: Browser, geradas: pathlib.Path, tmp_path: pathlib.Path, numero: int
) -> None:
    """r4-02-18: o lugar sem controle mostra «Player N • Desconectado» e mais nada.

    MORDIDA: sem a regra que esconde o resto, a vaga volta a mostrar máscara, microfone e bateria.
    """
    doc = (geradas / "02-controles.html").read_text(encoding="utf-8")
    esperado = f"Player {numero} • Desconectado"
    assert _texto_da_vaga(navegador, geradas / "02-controles.html", numero) == esperado
    mordido = doc.replace(".ctl.off > .faixa > :not(.card-nome){display:none !important}", "", 1)
    assert mordido != doc
    alvo = tmp_path / "vaga-com-traco.html"
    alvo.write_text(mordido, encoding="utf-8")
    assert _texto_da_vaga(navegador, alvo, numero) != esperado


# ---------------------------------------------------------------------------------------------
# As mordidas da régua
# ---------------------------------------------------------------------------------------------

def _escreve(tmp_path: pathlib.Path, nome: str, doc: str) -> pathlib.Path:
    arquivo = tmp_path / f"{nome}.html"
    arquivo.write_text(doc, encoding="utf-8")
    return arquivo


def _com_no_corpo(doc: str, html: str) -> str:
    assert doc.count("</body>") == 1
    return doc.replace("</body>", html + "</body>", 1)


def test_a_regua_morde_o_ponto_de_interrogacao_de_17_px(
    navegador: Browser, geradas: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """O `?` de 17x17 que abre a dica, em toda aba antes de 20/10: um só basta para reprovar."""
    doc = (geradas / "02-controles.html").read_text(encoding="utf-8")
    assert _problemas(_medir(navegador, _escreve(tmp_path, "limpa", doc))) == []
    ponto = ('<span class="ajuda" tabindex="0" style="display:inline-block;width:17px;height:17px;'
             'font-size:12px">?</span>')
    medida = _medir(navegador, _escreve(tmp_path, "com-ponto", _com_no_corpo(doc, ponto)))
    assert any("abre dica" in f for f in _problemas(medida)), medida["dicas"]


def test_a_regua_morde_a_folha_do_piso_arrancada(
    navegador: Browser, geradas: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    for aba in NO_PISO:
        doc = (geradas / f"{aba}.html").read_text(encoding="utf-8")
        sem = re.sub(rf'<style id="{ID_DA_FOLHA}">.*?</style>\n?', "", doc, count=1, flags=re.S)
        assert sem != doc, aba
        medida = _medir(navegador, _escreve(tmp_path, f"sem-{aba}", sem), VISTAS[0], "c-p1"
                        if aba.startswith("02") else "")
        assert _problemas(medida), f"sem a folha do piso a {aba} passou"


def test_a_regua_morde_a_letra_pequena(
    navegador: Browser, geradas: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    doc = (geradas / "09-sistema.html").read_text(encoding="utf-8")
    mordido = doc.replace("body .log{font-size:12px", "body .log{font-size:11px", 1)
    assert mordido != doc
    medida = _medir(navegador, _escreve(tmp_path, "letra", mordido))
    assert any("letra abaixo" in f for f in _problemas(medida)), medida["letras"]


def test_a_regua_morde_o_teto(
    navegador: Browser, geradas: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Um alvo de 20 px a mais na 08 passa do teto; e o teto não pode estar folgado."""
    doc = (geradas / "08-conexoes.html").read_text(encoding="utf-8")
    assert _acima_do_teto("08-conexoes", _medir(navegador, _escreve(tmp_path, "oito", doc))) == []
    botao = '<button style="width:20px;height:20px;font-size:12px">x</button>'
    medida = _medir(navegador, _escreve(tmp_path, "oito-mais", _com_no_corpo(doc, botao)))
    assert _acima_do_teto("08-conexoes", medida) != []


# ---------------------------------------------------------------------------------------------
# A janela lê o tamanho da interface
# ---------------------------------------------------------------------------------------------

_FILHO = textwrap.dedent(
    """
    import json, pathlib, sys, time
    from gi.repository import GLib
    from hefesto_dualsense4unix.interface import janela as jn
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    modo, arq = sys.argv[1], pathlib.Path(sys.argv[2])
    a09.guardar_o_tamanho(150)
    if modo == "ignora":
        jn.tamanho_da_interface = lambda: 100  # a janela que não pergunta ao arquivo
    if modo == "nao-cede":
        jn.tamanho_que_cabe = lambda escolhido, _l, _a: escolhido  # o zoom sem olhar a vista
    carregou = []
    # a vista alta (1300 px) comporta o 150 %; a de 840 px, a de quem usa, só 103 %
    tela = jn.JanelaDaAba(arquivo=arq, titulo_esperado="Prova do zoom", tamanho=(1918, 1300),
                          ao_carregar=lambda: carregou.append(1), oculta=True)

    def bombear(ate, prazo=8.0):
        contexto = GLib.MainContext.default()
        fim = time.monotonic() + prazo
        while not ate() and time.monotonic() < fim:
            while contexto.pending():
                contexto.iteration(False)
            time.sleep(0.004)
        return ate()

    def dicas():
        lido = {}
        tela.ponte.perguntar(
            "JSON.stringify([...document.querySelectorAll('button[data-v]')]"
            ".map(b => [b.dataset.v, b.dataset.dica]))",
            lambda v, e: lido.setdefault("v", v if e is None else repr(e)))
        bombear(lambda: "v" in lido)
        return dict(json.loads(lido["v"]))

    def zoom(alvo):
        bombear(lambda: abs(tela.view.get_zoom_level() - alvo) < 1e-6, 3.0)
        return tela.view.get_zoom_level()

    bombear(lambda: bool(carregou))
    print("ao-abrir", json.dumps([zoom(1.5), dicas()]), flush=True)
    a09.guardar_o_tamanho(125)
    print("ao-gravar", json.dumps([zoom(1.25), dicas()]), flush=True)
    tela.janela.set_default_size(1918, 840)  # a janela oculta muda pelo tamanho padrão
    print("na-vista-baixa", json.dumps([zoom(1.03), dicas()]), flush=True)
    # a página nova (trocar de aba e voltar) nasce com a dica do desenho, e o em uso volta a ela
    vezes = len(carregou)
    tela.view.reload()
    bombear(lambda: len(carregou) > vezes)
    print("recarregada", json.dumps([zoom(1.03), dicas()]), flush=True)
    tela.janela.set_default_size(1918, 1300)
    print("de-volta", json.dumps([zoom(1.25), dicas()]), flush=True)
    """
)

_PROVA_DO_ZOOM = (
    "<!doctype html><html><head><meta charset=\"utf-8\"><title>Prova do zoom</title></head><body>"
    '<div data-id="tamanho-da-interface">'
    '<button data-v="100" data-dica="O tamanho de hoje">Padrão</button>'
    '<button data-v="125" data-dica="Letras e botões maiores">Confortável</button>'
    '<button data-v="150" data-dica="Letras e botões maiores ainda">Espaçoso</button>'
    "</div></body></html>"
)
_DICAS = {"100": "O tamanho de hoje", "125": "Letras e botões maiores",
          "150": "Letras e botões maiores ainda"}
_LEITURAS = ("ao-abrir", "ao-gravar", "na-vista-baixa", "recarregada", "de-volta")


def _roda_o_filho(modo: str, tmp_path: pathlib.Path) -> dict[str, tuple[float, dict[str, str]]]:
    if shutil.which("xvfb-run") is None:  # pragma: no cover - máquina sem xvfb
        pytest.skip("sem `xvfb-run` a janela nasceria na tela de quem roda")
    html = tmp_path / "zoom.html"
    html.write_text(_PROVA_DO_ZOOM, encoding="utf-8")
    script = tmp_path / "filho_do_zoom.py"
    script.write_text(_FILHO, encoding="utf-8")
    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ / "src"), GDK_BACKEND="x11",
                    XDG_CONFIG_HOME=str(tmp_path / "config"))
    for nome in ("WAYLAND_DISPLAY", "DISPLAY", "HEFESTO_NA_TELA"):
        ambiente.pop(nome, None)
    feito = subprocess.run(
        ["xvfb-run", "-a", sys.executable, str(script), modo, str(html)],
        env=ambiente, capture_output=True, text=True, timeout=120, check=False,
    )
    assert feito.returncode == 0, (feito.stdout[-400:], feito.stderr[-800:])
    achado: dict[str, tuple[float, dict[str, str]]] = {}
    for linha in feito.stdout.splitlines():
        nome, _, resto = linha.partition(" ")
        if nome in _LEITURAS:
            zoom, dicas = json.loads(resto)
            achado[nome] = (float(zoom), dicas)
    assert set(achado) == set(_LEITURAS), (feito.stdout[-400:], feito.stderr[-800:])
    return achado


# O filho importa o `gi` e abre a janela: sem o PyGObject real (o job leve do CI) não mede nada.
@skip_sem_gi_real
def test_a_janela_le_o_tamanho_da_interface(tmp_path: pathlib.Path) -> None:
    """150 % guardado: a janela alta abre com zoom 1,5; a 09 grava 125: o zoom vai a 1,25.

    E o tamanho cede onde não cabe (O-TAMANHO-DE-150-NAO-CABE-NA-VISTA-DE-840-PX-01, «Cede onde
    não cabe», 23/10/2026): a janela baixada a 840 px de altura fica em 1,03, o que põe a vista do
    desenho (1212x809 em CSS) dentro dela, e a dica do botão escolhido diz o tamanho em uso, de
    novo na página recarregada; de volta à vista alta, o 1,25 e a dica do desenho voltam.

    MORDIDAS: `ignora` (a janela que não pergunta ao arquivo fica em 1,0) e `nao-cede` (o zoom
    que não olha a vista fica em 1,25 a 840 px, e a dica não diz nada). Arrancar o recomeço da
    dica na página nova (`_dizer_o_tamanho_em_uso(pagina_nova=True)` sem zerar `_dica_cedida`)
    reprova a leitura `recarregada` (conferência de 23/10/2026).
    """
    certo = _roda_o_filho("le", tmp_path)
    assert {k: v[0] for k, v in certo.items()} == {
        "ao-abrir": pytest.approx(1.5), "ao-gravar": pytest.approx(1.25),
        "na-vista-baixa": pytest.approx(1.03), "recarregada": pytest.approx(1.03),
        "de-volta": pytest.approx(1.25)}
    for leitura in ("ao-abrir", "ao-gravar", "de-volta"):
        assert certo[leitura][1] == _DICAS, leitura
    baixa = certo["na-vista-baixa"][1]
    em_uso = "Letras e botões maiores. Em uso: 103 %, o que cabe na janela"
    assert baixa == {**_DICAS, "125": em_uso}
    assert certo["recarregada"][1] == baixa, "a página nova perdeu o tamanho em uso"
    (tmp_path / "surdo").mkdir()
    surdo = _roda_o_filho("ignora", tmp_path / "surdo")
    assert [v[0] for v in surdo.values()] == [pytest.approx(1.0)] * len(_LEITURAS)
    (tmp_path / "teimoso").mkdir()
    teimoso = _roda_o_filho("nao-cede", tmp_path / "teimoso")
    assert teimoso["na-vista-baixa"][0] == pytest.approx(1.25)
    assert teimoso["na-vista-baixa"][1] == _DICAS
