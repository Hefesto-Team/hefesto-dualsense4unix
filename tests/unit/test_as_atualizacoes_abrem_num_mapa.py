"""A seção Atualizações da aba Sistema é só o botão do mapa, o «Atualizar sozinho» e o prazo.

AS-ATUALIZACOES-ABREM-NUM-MAPA-COMO-O-DAS-CONEXOES-01 (09/11/2026). A grade das peças saiu da aba:
as peças moram no mapa que o botão abre (``interface/atualizacoes.html_da_pergunta``).

A MORDIDA: a grade de volta na seção (uma linha de peça, ou a marca, ou as «Versões anteriores»)
reprova ``test_a_secao_e_so_o_botao`` nomeando o que sobrou; o próprio teste a prova com a grade
de antes enxertada (``test_a_regua_morde_a_grade_de_volta``).
"""
from __future__ import annotations

import re
from pathlib import Path

from hefesto_dualsense4unix.interface import aba09
from hefesto_dualsense4unix.interface import atualizacoes as tela

RAIZ = Path(__file__).resolve().parents[2]
GESTOS_DA_SECAO = {"atualizacoes-abrir", "atualizar-sozinho", "prazo-da-atualizacao"}
GRADE_DE_ANTES = ('<div class="at-grade"><div class="col-lista"><div class="saude">'
                  '<input type="checkbox" class="at-marca" data-gesto="peca-da-atualizacao" '
                  'data-v="proton"><span class="selo nova">NOVA</span><span class="txt">'
                  '<span>GE-Proton</span></span></div></div></div>')


def _secao(pagina: str) -> str:
    inicio = pagina.index('<div class="atualiza">')
    fim = pagina.index('<div class="sec-rot sr-log', inicio)
    return pagina[inicio:fim]


def o_que_sobra(pagina: str) -> list[str]:
    secao = _secao(pagina)
    sobra = sorted(set(re.findall(r'data-gesto="([^"]+)"', secao)) - GESTOS_DA_SECAO)
    abrir = secao.count('data-gesto="atualizacoes-abrir"')
    if abrir != 1:
        sobra.append(f"{abrir} botões do mapa")
    sobra += [classe for classe in ("saude", "at-grade", "at-marca", "selo")
              if re.search(rf'class="[^"]*\b{classe}\b', secao)]
    return sobra


def test_a_secao_e_so_o_botao() -> None:
    """D-0911-AS-ATUALIZACOES-ABREM-NUM-MAPA: a seção é o botão, o sozinho e o prazo."""
    for pagina in (aba09.MIOLO, (RAIZ / "mockup/09-sistema.html").read_text(encoding="utf-8")):
        assert o_que_sobra(pagina) == [], o_que_sobra(pagina)


def test_a_regua_morde_a_grade_de_volta() -> None:
    com_a_grade = aba09.MIOLO.replace(
        '<div class="sec-rot sr-log', GRADE_DE_ANTES + '<div class="sec-rot sr-log', 1)
    assert o_que_sobra(com_a_grade) == ["peca-da-atualizacao", "saude", "at-grade", "at-marca",
                                        "selo"]


def test_o_botao_leva_o_numero_do_que_ha_para_baixar() -> None:
    botao = re.search(r'<button class="btn at-mapa" data-gesto="atualizacoes-abrir">.*?</button>',
                      aba09.MIOLO, re.S)
    assert botao is not None
    assert "Atualizações" in botao.group(0) and 'data-campo="atualizacoes-novas"' in botao.group(0)
    assert aba09.NOVAS_DO_DESENHO == tela.quantas_novas(aba09.EXEMPLO_DAS_PECAS) == 3


def test_o_desenho_do_mapa_e_o_que_o_produto_pinta() -> None:
    desenho = (RAIZ / "mockup" / aba09.DESENHO_DO_MAPA).read_text(encoding="utf-8")
    corpo = tela.html_da_pergunta(aba09.EXEMPLO_DAS_PECAS, {"sozinho": False, "dias": 7},
                                  jogo_aberto=False)
    assert corpo in desenho
    assert '<span class="mp-v"><span class="nv">1.11.0</span></span>' in corpo


CHROME = Path("/usr/bin/google-chrome")
VISTAS = ((1212, 700), (1212, 809))
MESAS_CHEIAS = {
    "treze-novas": ["nova"] * 13,
    "tres-grupos": ["nova"] * 5 + ["em_dia"] * 5 + ["fixa"] * 3,
    "quatro-grupos": ["nova", "revisar", "em_dia"] + ["fixa"] * 10,
    "duas-de-revisar": ["revisar"] * 2 + ["nova"] * 4 + ["em_dia"] * 7,
}
MEDIR_O_MAPA = """() => {
  const cx = document.querySelector('#hef-atualizacoes .tn-cx.mapa');
  const corpo = cx.querySelector('.tn-corpo');
  const r = cx.getBoundingClientRect();
  return {rola: corpo.scrollHeight - corpo.clientHeight,
          fora: Math.max(0, r.bottom - innerHeight, -r.top),
          cortados: Array.from(cx.querySelectorAll('.mp-n, .mp-v, .mp-g, .btn, .cadeado'))
            .filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.textContent.trim()),
          letra: Math.min(...Array.from(cx.querySelectorAll('.mp-n, .mp-v, .mp-g, .btn, .btn .n'))
            .map(e => parseFloat(getComputedStyle(e).fontSize))),
          sem_a_nova: Array.from(cx.querySelectorAll('.mp-v')).filter(v => {
            const nv = v.querySelector('.nv'), a = v.getBoundingClientRect();
            if (!nv) return false;
            const b = nv.getBoundingClientRect();
            return b.top < a.top - 1 || b.bottom > a.bottom + 1 || b.right > a.right + 1
              || nv.scrollWidth > nv.clientWidth + 1;
          }).map(v => v.textContent),
          barras: Array.from(document.querySelectorAll('body *'))
            .filter(e => !e.closest('.hef-atualiza')
              && getComputedStyle(e).scrollbarWidth !== 'none')
            .map(e => e.className).slice(0, 5),
          lisas: Array.from(cx.querySelectorAll('.mp-c.fixa'))
            .filter(e => getComputedStyle(e).borderStyle !== 'dashed')
            .map(e => e.textContent.trim())};
}"""


PAR_LONGO = ("1.6.11 · 0.5.19", "1.6.12 · 0.5.19")


def _mesa(estados: list[str]) -> dict[str, object]:
    pecas = []
    for i, (ident, estado) in enumerate(zip(tela.ORDEM_NA_TELA, estados, strict=False)):
        exemplo = next(p for p in aba09.EXEMPLO_DAS_PECAS["pecas"] if p["id"] == ident)
        de, para = PAR_LONGO if ident == "som" else ("10.20.30", "10.20.31")
        pecas.append({**exemplo, "estado": estado, "volta": 1, "marcada": i % 2 == 0,
                      "de": de, "para": para, "rotulo": "",
                      "completa": "1:10.20.31~24.04+0~hefesto1"})
    return {"pecas": pecas}


def _paginas(pasta: Path) -> dict[str, Path]:
    base = (RAIZ / "mockup/09-sistema.html").read_text(encoding="utf-8").replace(
        "url('../assets/", f"url('{(RAIZ / 'assets').as_uri()}/")
    saida = {}
    for nome, estados in MESAS_CHEIAS.items():
        corpo = tela.html_da_pergunta(_mesa(estados), {"sozinho": True, "dias": 7},
                                      jogo_aberto=nome != "treze-novas",
                                      nome_do_jogo="Um jogo de nome longo")
        caixa = (f'<style>{tela.CSS}</style><div id="{tela.ID_DA_CAIXA}" '
                 f'class="hef-atualiza aberta">{corpo}</div>')
        arquivo = pasta / f"{nome}.html"
        arquivo.write_text(base.replace("</body>", caixa + "</body>", 1), encoding="utf-8")
        saida[nome] = arquivo
    return saida


def test_o_mapa_cheio_cabe_sem_rolar(tmp_path: Path) -> None:
    """D-0911-AS-ATUALIZACOES-ABREM-NUM-MAPA: três e quatro grupos cheios cabem em 1212x700.

    MORDIDA: com o cartão de 64 px e os espaços da primeira versão, a «quatro-grupos» rola 54 px;
    com a chave solta antes da regra das fixas, as fixas saem lisas («lisas»); com o número do
    «Atualizar» a 11,5 px, a «letra» fica abaixo de 12; com o par das versões numa linha que
    corta, a versão nova do «Som» sai com reticências («sem_a_nova»); sem esconder as barras de
    rolagem da página de baixo, a do registro da 09 se pinta por cima do «Atualizar» no WebKit
    («barras»).
    """
    import pytest

    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    falhas = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            for nome, arquivo in _paginas(tmp_path).items():
                for larg, alt in VISTAS:
                    pg = nav.new_page(viewport={"width": larg, "height": alt})
                    pg.goto(arquivo.as_uri())
                    pg.evaluate("() => document.fonts.ready")
                    medida = pg.evaluate(MEDIR_O_MAPA)
                    pg.close()
                    if medida["rola"] > 0 or medida["fora"] > 0 or medida["cortados"] \
                            or medida["letra"] < 12 or medida["lisas"] or medida["sem_a_nova"] \
                            or medida["barras"]:
                        falhas.append((nome, f"{larg}x{alt}", medida))
        finally:
            nav.close()
    assert not falhas, falhas


def test_o_cartao_le_o_estado_e_os_campos_do_motor_nos_dois_formatos() -> None:
    hoje = {"id": "bluetooth", "nome": "Bluetooth", "estado": "fixa", "volta": 2,
            "de": "5.87", "dica": "BlueZ"}
    volta_2 = [
        {"id": "bluetooth", "nome": "Bluetooth", "estado": "nova", "volta": 1, "marcada": True,
         "de": "5.88", "para": "5.89", "completa": "5.89-0ubuntu1~hefesto2", "dica": "BlueZ"},
        {"id": "som", "nome": "Som", "estado": "revisar", "volta": 1, "marcada": True,
         "de": "1.6.11 · 0.5.19", "para": "1.6.12 · 0.5.19",
         "dica": "a casa precisa revisar os patches"},
        {"id": "portal", "nome": "Portal do COSMIC", "estado": "em_dia", "volta": 1,
         "marcada": True, "de": "1.11.0", "para": "1.11.0",
         "completa": "1.11.0~1792525517~24.04~f448ddf+0~hefesto1"},
        {"id": "gdk", "nome": "GameInput", "estado": "fora", "volta": 1, "de": "1"}]
    antes = tela.html_do_mapa({"pecas": [hoje]})
    assert '<div class="mp-g fixa"><span>Com o Hefesto</span>' in antes
    assert "mp-m" not in antes
    mapa = tela.html_do_mapa({"pecas": volta_2})
    grupos = re.findall(r'<div class="mp-g ([a-z-]+)">', mapa)
    assert grupos == ["nova", "revisar", "em-dia"]
    assert "GameInput" not in mapa
    assert 'data-dica="BlueZ · 5.89-0ubuntu1~hefesto2"' in mapa
    assert ('<span class="par"><span class="de">5.88</span><span class="seta">→</span></span>'
            '<span class="nv">5.89</span>') in mapa
    revisar = re.search(r'<div class="mp-c revisar"[^>]*>.*?</div>', mapa, re.S).group(0)
    assert 'data-dica="a casa precisa revisar os patches · 1.6.11 · 0.5.19 → 1.6.12 · 0.5.19"' \
        in revisar
    assert '<span class="mp-s">!</span>' in revisar and "mp-m" not in revisar
    assert 'data-dica="1.11.0~1792525517~24.04~f448ddf+0~hefesto1"' in mapa
    assert re.search(r'<div class="mp-c em-dia"[^>]*>.*?<label class="mp-mx"><input[^>]*'
                     r'data-v="portal"', mapa)
    assert tela.ids_para_atualizar({"pecas": volta_2}) == ["bluetooth"]
    assert tela.quantas_novas({"pecas": volta_2}) == 1


def chaves_soltas(css: str) -> list[int]:
    """As linhas em que uma chave fecha sem ter aberto: a regra seguinte some no navegador."""
    nivel, soltas = 0, []
    for numero, linha in enumerate(css.splitlines(), 1):
        for letra in linha:
            nivel += {"{": 1, "}": -1}.get(letra, 0)
            if nivel < 0:
                soltas.append(numero)
                nivel = 0
    return soltas + ([-1] if nivel else [])


def test_o_css_do_mapa_fecha_cada_chave_que_abre() -> None:
    """D-0911-AS-ATUALIZACOES-ABREM-NUM-MAPA: nenhuma chave solta no CSS da caixa e da seção.

    MORDIDA: a chave solta depois do selo «!» da peça a revisar apagava a regra das fixas.
    """
    for nome, css in (("tela.CSS", tela.CSS), ("aba09", aba09.CSS_DAS_ATUALIZACOES)):
        assert chaves_soltas(css) == [], (nome, chaves_soltas(css))
    assert chaves_soltas(".a{x:1}\n}\n.b{y:2}") == [2]


def test_o_atualizar_se_apaga_sem_peca_marcada_tambem_com_o_jogo_aberto() -> None:
    """D-0911-AS-ATUALIZACOES-ABREM-NUM-MAPA: sem peça marcada, o «Atualizar» do rodapé se
    apaga com o jogo aberto ou fechado, em vez de recusar no clique."""
    nada = {"pecas": [{"id": "proton", "nome": "GE-Proton", "estado": "em_dia", "volta": 1,
                       "marcada": True, "de": "11-12", "para": "11-12"}]}
    for aberto in (False, True):
        corpo = tela.html_da_pergunta(nada, {"sozinho": False, "dias": 7}, jogo_aberto=aberto)
        assert re.search(r'class="btn principal apagado" data-gesto="atualizacoes-atualizar"',
                         corpo), aberto
