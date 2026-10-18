"""O Hefesto como servidor Buttplug do próprio DualSense: o DESENHO da janela de configurações.

A janela «DualSense como brinquedo» (alcançada pela terceira linha da janela da Lovense) conta o
caminho do app ao motor do controle em quatro cartões numerados: 1 · Servidor (só neste
computador, pedir licença a cada app novo), 2 · Controles (o que cada um mostra, a força e o teto),
3 · O que vibra (motor esquerdo, direito, sensor háptico e gatilhos) e 4 · Parar (L2 no fundo, ao
abrir um jogo, tempo máximo). Os controles aparecem pelo endereço, sem nome de cor cravado.

Só o desenho (`mockup/07-lancadores.html`); o servidor e o `plugin_api` ficam para a segunda
passagem.

MORDIDAS (executadas aqui): um cartão a menos, o «Só este computador» trocado por «Qualquer rede»
ou um nome de cor de plástico cravado reprovam a régua.
"""

from __future__ import annotations

import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "07-lancadores.html"
CARTOES = ["1 · Servidor", "2 · Controles", "3 · O que vibra", "4 · Parar"]
CORES = ("Starlight Blue", "Cosmic Red", "Galactic Purple", "Nova Pink", "Midnight Black",
         "Volcanic Red", "Chroma")


def _janela(texto: str | None = None) -> str:
    bruto = texto if texto is not None else MOCKUP.read_text(encoding="utf-8")
    sem = re.sub(r"<style\b[^>]*>.*?</style>", "", bruto, flags=re.S)
    inicio = sem.index('id="buttplug"')
    fim = sem.find('<div class="tela-nova"', inicio + 1)
    return sem[inicio:] if fim < 0 else sem[inicio:fim]


def _problemas(janela: str) -> list[str]:
    falta: list[str] = []
    if re.findall(r'<span class="ac-tit">([^<]+)</span>', janela) != CARTOES:
        falta.append("os quatro cartões numerados não estão todos, na ordem")
    if "Só este computador" not in janela:
        falta.append("o servidor não diz que atende só este computador")
    if "Qualquer rede" in janela:
        falta.append("a janela oferece atender qualquer rede")
    for rotulo in ("Motor esquerdo", "Motor direito", "Sensor háptico", "Gatilhos",
                   "L2 no fundo para tudo", "Parar quando um jogo abrir", "Tempo máximo sem pausa"):
        if rotulo not in janela:
            falta.append(f"sem «{rotulo}»")
    for cor in CORES:
        if cor in janela:
            falta.append(f"o nome de cor «{cor}» está cravado; a cor é do aparelho")
    if not re.search(r'data-campo="controle-1"', janela):
        falta.append("o primeiro controle perdeu o endereço")
    return falta


def test_a_janela_conta_o_caminho_em_quatro_cartoes() -> None:
    assert _problemas(_janela()) == []


def test_a_regua_morde_o_cartao_a_menos_a_rede_aberta_e_a_cor_cravada() -> None:
    doc = MOCKUP.read_text(encoding="utf-8")
    assert _problemas(_janela(doc.replace('<span class="ac-tit">4 · Parar</span>', "", 1)))
    assert any("qualquer rede" in p for p in _problemas(_janela(doc.replace(
        "Só este computador</option>",
        "Só este computador</option><option>Qualquer rede</option>", 1))))
    assert any("Cosmic Red" in p for p in _problemas(_janela(doc.replace(
        'data-campo="controle-2" data-hef-alvo="html">Segundo controle',
        'data-campo="controle-2" data-hef-alvo="html">Cosmic Red', 1))))


def test_a_janela_se_alcanca_pela_terceira_linha_da_lovense() -> None:
    doc = MOCKUP.read_text(encoding="utf-8")
    lovense = doc[doc.index('id="lovense"'):doc.index('id="impedimentos"')]
    assert 'data-modificacao="buttplug"' in lovense and 'href="#buttplug"' in lovense
