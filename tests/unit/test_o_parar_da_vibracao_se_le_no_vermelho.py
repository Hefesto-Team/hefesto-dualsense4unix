"""O «Parar» da Vibração se lê no vermelho: a variante de 20/10/2026, à espera da escolha.

A sprint O-PARAR-DA-VIBRACAO-SE-LE-NO-VERMELHO-01 mediu a letra branca sobre o `--red` (#ff5555)
com 3,14 para 1, abaixo dos 4,5 que a letra de 11,5 px pede. A variante troca só o fundo do
«Parar»; a página de hoje fica como está até a escolha.

MORDIDA (executada): com o `var(--red)` de volta na variante, `test_a_variante_passa_da_regua`
reprova.
"""

from __future__ import annotations

import difflib
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[2]
BASE = RAIZ / "mockup" / "05-vibracao.html"
VARIANTE = RAIZ / "mockup" / "variantes" / "05-parar-A-vermelho-mais-fundo.html"
REGRA = re.compile(r"\.acoes-col \.btn\.vermelho,\.acoes-col \.btn\.vermelho:hover\{\s*([^}]*)\}")
TOKEN = re.compile(r"--red:\s*(#[0-9a-fA-F]{6})")


def _luz(hexa: str) -> float:
    canais = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contraste(a: str, b: str) -> float:
    x, y = sorted((_luz(a), _luz(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def _fundo_e_letra(html: str) -> tuple[str, str]:
    regra = REGRA.search(html)
    assert regra, "a regra do «Parar» sumiu da folha"
    corpo = regra.group(1)
    fundo = re.search(r"background:\s*([^;]+);", corpo).group(1).strip()
    letra = re.search(r"(?:^|;)\s*color:\s*([^;]+);", corpo).group(1).strip()
    if fundo == "var(--red)":
        fundo = TOKEN.search(html).group(1)
    return fundo, {"#fff": "#ffffff"}.get(letra, letra)


def test_a_variante_passa_da_regua() -> None:
    fundo, letra = _fundo_e_letra(VARIANTE.read_text(encoding="utf-8"))
    assert letra == "#ffffff", "o pedido de 06/10 é letra branca"
    assert _contraste(fundo, letra) >= 4.5


def test_a_pagina_de_hoje_e_a_que_a_sprint_mediu() -> None:
    fundo, letra = _fundo_e_letra(BASE.read_text(encoding="utf-8"))
    assert round(_contraste(fundo, letra), 2) == 3.14


def test_a_variante_so_muda_a_regra_do_parar() -> None:
    base = BASE.read_text(encoding="utf-8").splitlines()
    variante = VARIANTE.read_text(encoding="utf-8").splitlines()
    mudou = [d for d in difflib.unified_diff(base, variante, lineterm="", n=0)
             if d[:1] in "+-" and not d.startswith(("+++", "---"))]
    assert len(mudou) == 2, mudou
    assert all("background:" in d and "border-color:" in d for d in mudou)
