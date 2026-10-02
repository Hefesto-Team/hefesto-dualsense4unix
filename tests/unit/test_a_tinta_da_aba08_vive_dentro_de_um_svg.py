#!/usr/bin/env python3
"""A TABELA DOS 28 DA ABA 08 SÓ PINTA SE ELA VIVER DENTRO DE UM `<svg>`."""
from __future__ import annotations

import pathlib
import re
import sys
from html.parser import HTMLParser

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

BANCADA = RAIZ / "mockup/08-conexoes.html"

FOLHA = re.compile(r'<style id="([^"]*cores-do-dualsense-folha)">(.*?)</style>', re.S)

#: A tinta que a folha pede por referência: `fill:url(#hachura-sem-hex)`.
TINTA_POR_REFERENCIA = re.compile(r"url\(\s*['\"]?#([^)'\"\s]+)")

REGRA_DE_COLORWAY = re.compile(r'svg\[data-colorway="([^"]+)"\]')


class _OndeCadaIdNasceu(HTMLParser):
    """Guarda cada `id` da página e se ele nasceu DENTRO de um `<svg>`."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fundo = 0
        self.ids: dict[str, bool] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "svg":
            self.fundo += 1
        ident = dict(attrs).get("id")
        if ident:
            self.ids.setdefault(ident, self.fundo > 0)

    def handle_startendtag(self, tag: str,
                           attrs: list[tuple[str, str | None]]) -> None:
        dentro = self.fundo > 0 or tag == "svg"
        ident = dict(attrs).get("id")
        if ident:
            self.ids.setdefault(ident, dentro)

    def handle_endtag(self, tag: str) -> None:
        if tag == "svg" and self.fundo > 0:
            self.fundo -= 1


def _html() -> str:
    return BANCADA.read_text(encoding="utf-8")


def _folha() -> str:
    achado = FOLHA.search(_html())
    assert achado, (
        "a `08-conexoes` não publica folha de cores nenhuma — sem ela o alvo de "
        "atributo escreve um colorway que nada casa, e os 28 viram um cinza só")
    return achado.group(2)


def _onde_nasceram() -> dict[str, bool]:
    varredor = _OndeCadaIdNasceu()
    varredor.feed(_html())
    return varredor.ids


def test_a_folha_pede_tinta_por_referencia() -> None:
    """A régua tem sujeito: a folha da 08 cita `url(#…)`."""
    citados = set(TINTA_POR_REFERENCIA.findall(_folha()))
    assert citados, (
        "a folha da 08 não pinta nenhum modelo com `url(#…)`. Se o mapa dela "
        "deixou de usar hachura e gradiente, esta régua perdeu o alvo e as duas "
        "abaixo passaram a não medir nada — apague-as ou dê-lhes o alvo novo.")


def test_toda_tinta_citada_pela_folha_nasce_dentro_de_um_svg() -> None:
    """O `<defs>` das cores tem de viver num fragmento SVG, não solto no HTML."""
    nasceram = _onde_nasceram()
    citados = sorted(set(TINTA_POR_REFERENCIA.findall(_folha())))
    fora = [i for i in citados if not nasceram.get(i, False)]
    ausentes = [i for i in citados if i not in nasceram]
    assert not ausentes, (
        f"a folha da 08 pinta com `url(#{ausentes[0]})` e a página não define "
        f"esse `id` em lugar nenhum: {ausentes}")
    assert not fora, (
        f"a folha da 08 pinta com `url(#…)` apontando para {fora}, que a página "
        f"define FORA de um `<svg>`. Fora do `<svg>` não há espaço de nomes SVG: "
        f"`<pattern>` e `<linearGradient>` viram `HTMLUnknownElement` e o `fill` "
        f"fica sem tinta. A cura é o `<svg width=\"0\">` que envolve o "
        f"`<defs id=\"cores-do-dualsense\">` em `aba08.TABELA_DAS_CORES`.")


def test_nenhum_modelo_do_mapa_dela_pede_tinta_que_a_pagina_nao_resolve() -> None:
    """A conta que ela lê: QUAIS dos 28 a página sabe pintar de verdade."""
    folha = _folha()
    nasceram = _onde_nasceram()
    modelos = REGRA_DE_COLORWAY.findall(folha)
    assert len(set(modelos)) >= 28, (
        f"a folha da 08 traz {len(set(modelos))} modelos — ela mapeou 28, e uma "
        f"folha curta é a escolha cravada que a lei dela proíbe")
    perdidos = []
    for modelo in sorted(set(modelos)):
        bloco = "\n".join(
            linha for linha in folha.splitlines()
            if f'data-colorway="{modelo}"' in linha)
        for ident in sorted(set(TINTA_POR_REFERENCIA.findall(bloco))):
            if not nasceram.get(ident, False):
                perdidos.append(f"{modelo} (url(#{ident}))")
    assert not perdidos, (
        f"{len(perdidos)} modelos do mapa dela pedem tinta que a `08` não "
        f"resolve: {perdidos}. Quem tiver um deles vê o controle cru, que na "
        f"tela é indistinguível de 'não li a cor'.")
