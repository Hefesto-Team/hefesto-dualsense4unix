#!/usr/bin/env python3
"""A caixa da janela das abas e o «Voltar», para as páginas que abrem POR FORA delas."""
from __future__ import annotations

import pathlib
import re

TOPO = pathlib.Path(__file__).resolve().with_name("topo.html")

VARIAVEIS_DA_MOLDURA = ("--recuo-do-corpo", "--piso-da-vista", "--teto-da-vista",
                        "--alt-janela")

TAMANHO_DA_JANELA = ("width", "height", "max-width", "max-height")


def _folha_do_topo(topo: str) -> str:
    """O CSS do `<style>` do esqueleto das abas, sem os comentários."""
    estilo = topo.split("<style>", 1)[1].split("</style>", 1)[0]
    return re.sub(r"/\*.*?\*/", "", estilo, flags=re.S)


def _regra(css: str, seletor: str) -> dict[str, str]:
    """As declarações da ÚNICA regra `seletor{…}` da folha, por propriedade."""
    achadas = re.findall(rf"(?<=[}}\s]){re.escape(seletor)}\s*\{{([^{{}}]*)\}}", css)
    if len(achadas) != 1:
        raise SystemExit(f"ERRO: o topo.html tem {len(achadas)} regra(s) "
                         f"`{seletor}{{…}}`, e as páginas avulsas leem o tamanho "
                         f"das abas de UMA só.")
    declaracoes: dict[str, str] = {}
    for linha in achadas[0].split(";"):
        prop, sep, valor = linha.partition(":")
        if sep and prop.strip():
            declaracoes[prop.strip()] = " ".join(valor.split())
    return declaracoes


def moldura(topo: str | None = None, caixa: str = ".cx") -> str:
    """A folha que dá a ``caixa`` o recuo e o tamanho da `.janela` das dez abas."""
    css = _folha_do_topo(TOPO.read_text(encoding="utf-8") if topo is None else topo)
    variaveis: list[str] = []
    for nome in VARIAVEIS_DA_MOLDURA:
        achados = re.findall(rf"{re.escape(nome)}\s*:\s*([^;]+);", css)
        if len(achados) != 1:
            raise SystemExit(f"ERRO: o topo.html declara `{nome}` {len(achados)} "
                             f"vez(es) — as páginas avulsas leem o tamanho das "
                             f"abas de lá.")
        variaveis.append(f"{nome}:{' '.join(achados[0].split())}")
    janela = _regra(css, ".janela")
    corpo = _regra(css, "body")
    faltam = [p for p in TAMANHO_DA_JANELA if p not in janela]
    if faltam or "padding" not in corpo:
        raise SystemExit(f"ERRO: o topo.html não diz mais {faltam or ['padding']} "
                         f"— as páginas avulsas não sabem o tamanho das abas.")
    tamanho = ";".join(f"{p}:{janela[p]}" for p in TAMANHO_DA_JANELA)
    return (f"  :root{{{';'.join(variaveis)}}}\n"
            f"  body{{padding:{corpo['padding']}}}\n"
            f"  {caixa}{{{tamanho}}}\n")


def voltar(reserva: str) -> str:
    """O «← Voltar» das páginas avulsas: volta para a aba de onde ela veio."""
    return (f'<a class="voltar" href="{reserva}"'
            ' onclick="if (history.length > 1) { history.back(); return false }"'
            ' title="Volta para a aba anterior.">← Voltar</a>')
