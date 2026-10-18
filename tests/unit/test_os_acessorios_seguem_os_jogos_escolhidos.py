"""Os acessórios seguem os jogos escolhidos, com a força no deslizante: o DESENHO da janela.

Na aba interna «O que seguem» da janela dos acessórios (Lovense), a moldura «Os jogos que os
acessórios seguem» tem uma caixa por jogo, e a lista NASCE DESMARCADA («nenhum marcado: os
acessórios ficam parados»); a moldura «Força de cada canal» tem, para cada aparelho, um deslizante
de 0 a 20 por canal (vibração, gatilho e háptica), com o número ao lado.

Só o desenho (`mockup/07-lancadores.html`); o evento, o autoswitch e o manifesto ficam para a
segunda passagem. Nenhum «P1» a «P4» e nenhum nome de controle cravado.

MORDIDAS (executadas aqui): um deslizante a menos, um limite de 0 a 30, uma caixa já marcada de
fábrica ou um «P1» na janela reprovam a régua; o deslizante que não muda o número reprova no Chrome.
"""

from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "07-lancadores.html"
CHROME = pathlib.Path("/usr/bin/google-chrome")
APARELHOS = ["Lovense Nora", "Lovense Domi", "Lovense Ferri"]
CANAIS = ["Vibração", "Gatilho", "Háptica"]


def _janela(texto: str | None = None) -> str:
    bruto = texto if texto is not None else MOCKUP.read_text(encoding="utf-8")
    sem = re.sub(r"<style\b[^>]*>.*?</style>", "", bruto, flags=re.S)
    inicio = sem.index('id="acessorios"')
    return sem[inicio:sem.find('<div class="tela-nova"', inicio + 1) if sem.find(
        '<div class="tela-nova"', inicio + 1) > 0 else None]


def _problemas(janela: str) -> list[str]:
    falta: list[str] = []
    forca = re.search(r'<div class="moldura t2-forca">(.*?)</div>\s*</div>', janela, flags=re.S)
    if not forca:
        return ["sem a moldura «Força de cada canal»"]
    cabecas = re.findall(r'<span class="fz-cab"[^>]*>([^<]+)</span>', forca.group(1))
    if cabecas != CANAIS:
        falta.append(f"canais {cabecas}")
    aparelhos = re.findall(r'<span class="fz-ap">([^<]+)</span>', forca.group(1))
    if aparelhos != APARELHOS:
        falta.append(f"aparelhos {aparelhos}")
    deslizantes = re.findall(
        r'<input type="range" min="(\d+)" max="(\d+)"[^>]*aria-label="([^"]+)"', forca.group(1))
    esperados = {f"{c} de {a}" for a in APARELHOS for c in CANAIS}
    if {r for _, _, r in deslizantes} != esperados or len(deslizantes) != 9:
        falta.append(f"{len(deslizantes)} deslizantes, e são nove: três por aparelho")
    if any((lo, hi) != ("0", "20") for lo, hi, _ in deslizantes):
        falta.append("um deslizante não vai de 0 a 20")
    lista = re.search(r'<div class="jg-lista">(.*?)</div>\s*</div>', janela, flags=re.S)
    caixas = re.findall(r'<input type="checkbox"([^>]*)>', lista.group(1)) if lista else []
    if not caixas:
        falta.append("sem a lista de jogos com caixa")
    if any("checked" in c for c in caixas):
        falta.append("uma caixa nasce marcada; a lista nasce desmarcada")
    if re.search(r"\bP[1-4]\b", janela):
        falta.append("um P1 a P4 na janela; a cor do plástico é do produto")
    return falta


def test_nove_deslizantes_de_zero_a_vinte_e_a_lista_nasce_desmarcada() -> None:
    assert _problemas(_janela()) == []


def test_ha_uma_caixa_por_jogo_com_perfil_e_o_nome_dele() -> None:
    lista = re.search(r'<div class="jg-lista">(.*?)</div>\s*</div>', _janela(), flags=re.S).group(1)
    caixas = re.findall(
        r'<input type="checkbox" data-jogo="([^"]+)"><span class="jg-n">([^<]+)</span>', lista)
    assert len(caixas) >= 7 and all(a == b for a, b in caixas), caixas


def test_a_regua_morde_o_limite_a_caixa_marcada_o_deslizante_a_menos_e_o_p1() -> None:
    doc = MOCKUP.read_text(encoding="utf-8")
    assert any("0 a 20" in p for p in _problemas(_janela(doc.replace(
        'max="20" step="1" value="10" aria-label="Vibração de Lovense Nora"',
        'max="30" step="1" value="10" aria-label="Vibração de Lovense Nora"', 1))))
    assert any("marcada" in p for p in _problemas(_janela(doc.replace(
        '<input type="checkbox" data-jogo="Elden Ring">',
        '<input type="checkbox" checked data-jogo="Elden Ring">', 1))))
    assert any("deslizantes" in p for p in _problemas(_janela(doc.replace(
        'aria-label="Háptica de Lovense Ferri"', 'aria-label="x"', 1))))
    assert any("P1" in p for p in _problemas(_janela(doc.replace(
        "Força de cada canal</span>", "Força de cada canal P1</span>", 1))))


@pytest.fixture(scope="module")
def pagina():
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        pg = nav.new_page(viewport={"width": 1212, "height": 809})
        yield pg
        nav.close()


def test_o_deslizante_muda_o_numero_ao_lado_e_a_lista_abre_desmarcada(pagina) -> None:
    pagina.goto(f"{MOCKUP.as_uri()}?aba=t2#acessorios")
    assert pagina.evaluate("[...document.querySelectorAll('.jg-l input')].every(c => !c.checked)")
    pagina.evaluate("""() => {
      const r = document.querySelector('[aria-label="Gatilho de Lovense Domi"]');
      r.value = 17; r.dispatchEvent(new Event('input', {bubbles: true})); }""")
    assert pagina.evaluate("""document.querySelector(
      '[aria-label="Gatilho de Lovense Domi"]').nextElementSibling.textContent""") == "17"
    pagina.click(".jg-l:nth-child(2) input")
    assert pagina.evaluate("document.querySelectorAll('.jg-l input:checked').length") == 1
