#!/usr/bin/env python3
"""O DESENHO da intensidade da vibração e do gatilho.

Sprint: A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-COMO-NO-PS5-01.

Só o desenho: a 05 tem o trilho de 0 a 200% e a 03 ganha o mesmo trilho para o gatilho. O produto
(o byte do firmware até 100% e o multiplicador acima) é a segunda passagem e não é medido aqui.

MORDIDAS: volte o `TETO_DA_FORCA` da 05 a 100, ponha botões de degrau na «Força», tire a linha da
03 do desenho, troque o `data-hef` do trilho da 03 por `data-papel` (gesto sem dono), ponha uma
palavra de firmware na dica, ou aumente o respiro da grade da 03 — cada uma reprova uma asserção.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

CHROME = pathlib.Path("/usr/bin/google-chrome")
VISTAS = [(940, 809), (1272, 860), (1512, 860), (1900, 1000)]
JARGAO = ("firmware", "byte", "nibble", "multiplicador", "software", "atenuação", "bit", "pwm")


def _html(nome: str) -> str:
    arq = RAIZ / "mockup" / nome
    assert arq.exists(), f"o desenho não tem {nome} — rode o gerador da aba"
    return arq.read_text(encoding="utf-8")


def _trilhos(doc: str, campo_ou_papel: str) -> list[str]:
    todos = re.findall(r'<input class="trilho arrasta"[^>]*>', doc)
    return [t for t in todos if campo_ou_papel in t]


@pytest.fixture(scope="module")
def d03() -> str:
    return _html("03-gatilhos.html")


@pytest.fixture(scope="module")
def d05() -> str:
    return _html("05-vibracao.html")


def test_a_forca_da_vibracao_vai_de_0_a_200_sem_degraus(d05: str) -> None:
    from hefesto_dualsense4unix.interface import aba05
    from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX

    assert aba05.TETO_DA_FORCA == round(RUMBLE_CUSTOM_MULT_MAX * 100) == 200
    assert "data-forca=" not in d05 and 'class="seg"' not in d05
    trilhos = _trilhos(d05, 'data-papel="intensidade"')
    assert len(trilhos) == len(aba05.MESA)
    assert all('min="0"' in t and 'max="200"' in t and 'step="5"' in t for t in trilhos), trilhos


def test_o_gatilho_ganha_o_trilho_de_0_a_200_por_controle(d03: str) -> None:
    # D-1810-O-GATILHO-E-A-VIBRACAO-TEM-O-TRILHO-DE-0-A-200
    from hefesto_dualsense4unix.interface import aba03, aba05

    trilhos = _trilhos(d03, f'data-campo="{aba03.CAMPO_DA_INTENSIDADE}"')
    assert len(trilhos) == len(aba03.MESA), f"um trilho por lugar, e há {len(trilhos)}"
    for t in trilhos:
        assert 'min="0"' in t and 'max="200"' in t and 'step="5"' in t, t
        assert 'data-hef-alvo="valor"' in t, "o piloto não pinta o trilho"
    assert (aba03.TETO_DA_INTENSIDADE, aba03.PASSO_DA_INTENSIDADE) == (
        aba05.TETO_DA_FORCA, aba05.PASSO_DA_FORCA), "os dois trilhos têm de ter o mesmo alcance"
    assert "Intensidade do gatilho" in d03
    # o mesmo formato da 05: ícone do controle, trilho, número e `%`
    assert d03.count('class="teto">%</span>') >= len(aba03.MESA)
    assert aba03.GLIFO_DA_INTENSIDADE == aba05.GLIFO_DO_CONTROLE


def test_o_lugar_sem_controle_mostra_o_travessao_e_nao_um_numero(d03: str) -> None:
    from hefesto_dualsense4unix.interface import aba03

    vazios = [c for c in aba03.MESA if not c.get("conectado", True)]
    assert vazios, "a cena deve ter vagas sem controle"
    celulas = re.findall(r'<div class="g2-int[^"]*"[^>]*>', d03)
    assert len(celulas) == len(aba03.MESA)
    for c in vazios:
        cel = next(x for x in celulas if f'data-controle="{c["pref"]}"' in x)
        assert 'data-conectado="nao"' in cel and " off" in cel, cel
        molde = rf'<div class="g2-int[^"]*" data-controle="{c["pref"]}".*?</div>'
        achada = re.search(molde, d03, re.S)
        assert achada and f">{aba03.TRAVESSAO}</span>" in achada.group(0), "a vaga afirma um número"


def test_a_linha_da_03_fica_antes_do_l2_e_o_estilo_continua_escolhendo_o_efeito(d03: str) -> None:
    from hefesto_dualsense4unix.interface import aba03

    assert aba03.ONDE_ENTRA_A_INTENSIDADE == "acima"
    primeiro_trilho = d03.index(f'data-campo="{aba03.CAMPO_DA_INTENSIDADE}"')
    primeiro_modo = d03.index('data-gesto="modo"')
    assert primeiro_trilho < primeiro_modo, "a intensidade entra sob o chip, antes do L2"
    # o L2/R2 do estilo (r3b-03-15) fica como está: dois campos de cada por controle
    n = len(aba03.MESA)
    assert d03.count('data-gesto="modo"') == 2 * n and d03.count('data-gesto="imersao"') == 2 * n


def test_o_trilho_novo_nao_cria_gesto_sem_dono(d03: str) -> None:
    """Gesto sem dono reprova `test_os_sem_dono_so_diminuem`: o trilho só pinta (`data-hef`)."""
    from hefesto_dualsense4unix.interface import aba03

    g = aba03.GESTO_DA_INTENSIDADE_QUE_ESPERA_O_PRODUTO
    assert f'data-hef="{g}"' in d03
    assert f'data-papel="{g}"' not in d03 and f'data-gesto="{g}"' not in d03, (
        "o gesto novo ganhou endereço antes de ter atendente e camada")


def test_a_dica_de_cada_trilho_e_uma_frase_curta_sem_jargao() -> None:
    from hefesto_dualsense4unix.interface import aba03, aba05

    for dica in (aba03.DICA_DA_INTENSIDADE, aba05.DICA_DA_FORCA):
        baixa = dica.lower()
        assert not any(p in baixa for p in JARGAO), f"jargão na dica: {dica!r}"
        assert len(dica) <= 120 and dica.count(".") == 0, f"a dica é uma frase curta: {dica!r}"
        assert "100%" in dica and ("mais fraco" in dica or "mais fraca" in dica)


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome do sistema: a régua não tem motor")
def test_a_03_e_a_05_nao_rolam_na_vertical_nas_quatro_vistas() -> None:
    """Nem o documento, nem o `.miolo` (a rolagem interna que `passa_da_dobra` não vê)."""
    from playwright.sync_api import sync_playwright

    medir = """() => {
      const rola = [];
      for (const e of document.querySelectorAll('*')) {
        const s = getComputedStyle(e);
        if ((s.overflowY === 'auto' || s.overflowY === 'scroll')
            && e.scrollHeight > e.clientHeight + 1) {
          rola.push((e.className || e.tagName) + ':' + (e.scrollHeight - e.clientHeight));
        }
      }
      const d = document.documentElement;
      const sobra = d.scrollHeight - window.innerHeight;
      if (sobra > 1) rola.push('doc:' + sobra);
      return {rola, lateral: d.scrollWidth > d.clientWidth + 1};
    }"""
    achados = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        for pagina in ("03-gatilhos.html", "05-vibracao.html"):
            for larg, alt in VISTAS:
                pg = nav.new_page(viewport={"width": larg, "height": alt})
                pg.goto((RAIZ / "mockup" / pagina).as_uri())
                pg.wait_for_load_state("networkidle")
                pg.wait_for_timeout(300)
                m = pg.evaluate(medir)
                if m["rola"] or m["lateral"]:
                    achados.append((pagina, larg, alt, m))
                pg.close()
        nav.close()
    assert not achados, f"há rolagem: {achados}"


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome do sistema: a régua não tem motor")
def test_a_linha_da_03_tem_a_altura_e_as_colunas_da_linha_da_forca_da_05() -> None:
    """O pedido é «no mesmo formato, altura e colunas» do trilho da 05: mede-se a geometria.

    MORDIDA: troque, no `aba03.CSS`, o `grid-template-columns` da `.g2-int` (o 44px do número
    por 60px) ou a altura de 36 por 30, regere o desenho, e esta régua reprova.
    """
    from playwright.sync_api import sync_playwright

    medir = """s => {
      const t = document.querySelector(s), l = t.parentElement, cs = getComputedStyle(l);
      const cols = cs.gridTemplateColumns.split(' ');
      return {altura: Math.round(l.getBoundingClientRect().height),
              fixas: [cols[0], cols[2], cols[3]], vao: cs.columnGap,
              trilho: Math.round(t.getBoundingClientRect().height)};
    }"""
    medidas = {}
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        for pagina, seletor in (("03-gatilhos.html", '.g2-int:not(.off) input.trilho'),
                                ("05-vibracao.html", 'input.trilho[data-papel="intensidade"]')):
            pg = nav.new_page(viewport={"width": 1272, "height": 860})
            pg.goto((RAIZ / "mockup" / pagina).as_uri())
            pg.wait_for_load_state("networkidle")
            medidas[pagina] = pg.evaluate(medir, seletor)
            pg.close()
        nav.close()
    m03, m05 = medidas["03-gatilhos.html"], medidas["05-vibracao.html"]
    assert m03 == m05, f"a linha da 03 não tem o formato da Força da 05: {m03} ≠ {m05}"
    assert m03["altura"] == 36 and m03["fixas"] == ["36px", "44px", "8px"], m03
