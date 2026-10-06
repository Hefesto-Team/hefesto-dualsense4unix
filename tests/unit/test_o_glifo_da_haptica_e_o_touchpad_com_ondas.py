"""A háptica tem glifo PRÓPRIO: a área do touchpad com ondinhas na borda de cima.

Ela, 03/10/2026 (A-VIBRACAO-E-A-HAPTICA-DE-CADA-CONTROLE-SAO-INDEPENDENTES-01):
*«precisamos de um svg específico pro hático»* e, sobre o desenho, a área do touchpad com ondas
na parte superior. Até aqui a linha «Sensor Háptico» usava o desenho do
motor esquerdo.

AS MORDIDAS:

* volte `glifo(ESQ["glifo"], …)` na `_linha_da_haptica` → o botão da háptica
  volta a trazer o título do motor e `test_o_botao_da_haptica_usa_o_glifo_proprio`
  reprova;
* tire as ondas do `haptica.svg` → `test_o_glifo_e_o_touchpad_com_ondas_em_cima`
  reprova;
* apague o `haptica_active.svg` → `test_os_dois_estados_existem_e_so_trocam_a_cor`.
"""
from __future__ import annotations

import pathlib
import re
import xml.etree.ElementTree as ET

RAIZ = pathlib.Path(__file__).resolve().parents[2]
GLIFOS = RAIZ / "assets" / "glyphs"
MOCKUP = RAIZ / "mockup" / "05-vibracao.html"
NS = {"s": "http://www.w3.org/2000/svg"}


def _raiz(nome: str) -> ET.Element:
    return ET.parse(GLIFOS / nome).getroot()


def test_o_glifo_e_o_touchpad_com_ondas_em_cima() -> None:
    touch = _raiz("touchpad.svg").find("s:rect", NS)
    haptica = _raiz("haptica.svg")
    area = haptica.find("s:rect", NS)
    assert touch is not None and area is not None
    for atributo in ("x", "width", "rx"):
        assert area.get(atributo) == touch.get(atributo), (
            f"a área do glifo não é a do touchpad no atributo {atributo}"
        )
    topo = float(area.get("y", "0"))
    ondas = haptica.findall("s:path", NS)
    assert len(ondas) >= 2, "faltam as ondinhas"
    for onda in ondas:
        ys = [float(n) for n in re.findall(r"[Mm]\s*-?[\d.]+\s+(-?[\d.]+)", onda.get("d", ""))]
        assert ys and max(ys) < topo, (
            "uma onda desce para dentro do retângulo: elas saem da borda de cima"
        )


def test_os_dois_estados_existem_e_so_trocam_a_cor() -> None:
    comum = (GLIFOS / "haptica.svg").read_text(encoding="utf-8")
    acesa = (GLIFOS / "haptica_active.svg").read_text(encoding="utf-8")
    assert comum.replace("#f8f8f2", "#bd93f9") == acesa


def test_o_botao_da_haptica_usa_o_glifo_proprio() -> None:
    html = MOCKUP.read_text(encoding="utf-8")
    botoes = re.findall(
        r'<button class="haptica-lado[^>]*>(.*?)</button>', html, flags=re.S)
    assert botoes, "a página perdeu o botão da háptica"
    for botao in botoes:
        assert "<title>Háptica</title>" in botao, (
            "o botão da háptica não traz o glifo próprio"
        )
        assert "Motor de vibração" not in botao, (
            "o botão da háptica voltou ao desenho do motor"
        )
