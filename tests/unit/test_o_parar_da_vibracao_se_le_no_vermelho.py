"""O «Parar» da Vibração se lê no vermelho: a variante A, escolhida em 20/10/2026, no desenho da 05.

A sprint O-PARAR-DA-VIBRACAO-SE-LE-NO-VERMELHO-01 mediu a letra branca sobre o `--red` (#ff5555)
com 3,14 para 1, abaixo dos 4,5 que a letra de 11,5 px pede. A regra mora na folha do `aba05.py`
e sai no `mockup/05-vibracao.html` que ele gera; o publicado recebe pelo `--publicar 05`.

MORDIDA (executada em 21/10/2026): com o `var(--red)` de volta no `aba05.py` e a 05 gerada de
novo, `test_o_desenho_passa_da_regua` e `test_o_desenho_tem_a_regra_da_variante` reprovam.
"""

from __future__ import annotations

import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "mockup" / "05-vibracao.html"
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


def _corpo(html: str) -> str:
    regra = REGRA.search(html)
    assert regra, "a regra do «Parar» sumiu da folha"
    return regra.group(1)


def _fundo_e_letra(html: str) -> tuple[str, str]:
    corpo = _corpo(html)
    fundo = re.search(r"background:\s*([^;]+);", corpo).group(1).strip()
    letra = re.search(r"(?:^|;)\s*color:\s*([^;]+);", corpo).group(1).strip()
    if fundo == "var(--red)":
        fundo = TOKEN.search(html).group(1)
    return fundo, {"#fff": "#ffffff"}.get(letra, letra)


def test_o_desenho_passa_da_regua() -> None:
    fundo, letra = _fundo_e_letra(DESENHO.read_text(encoding="utf-8"))
    assert letra == "#ffffff", "o pedido de 06/10 é letra branca"
    assert _contraste(fundo, letra) >= 4.5, (fundo, round(_contraste(fundo, letra), 2))


def test_o_desenho_tem_a_regra_da_variante() -> None:
    assert _corpo(DESENHO.read_text(encoding="utf-8")) == _corpo(
        VARIANTE.read_text(encoding="utf-8"))


def test_o_red_do_tema_e_o_que_a_sprint_mediu() -> None:
    """O porquê de a regra não usar o token: a letra branca sobre o `--red` dá 3,14."""
    red = TOKEN.search(DESENHO.read_text(encoding="utf-8")).group(1)
    assert round(_contraste(red, "#ffffff"), 2) == 3.14
