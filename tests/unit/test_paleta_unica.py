"""Toda cor da interface sai da paleta Drácula — inclusive as inline no Python.

O redesign 1.0.0 deu UM papel a cada cor. A disciplina é fácil de furar sem
querer: o CSS e o glade são revisados, mas markup Pango escrito no meio de um
`.py` (`<span foreground="#2d8">`) passa despercebido — eram 41 usos de sete
cores fora da paleta espalhados por sete arquivos, todos "quase" iguais às
oficiais e sutilmente diferentes entre si.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
GUI = RAIZ / "gui"
APP = RAIZ / "app"

#: As 11 do Drácula + os 7 tokens de superfície do guia de identidade.
PALETA = {
    "#282a36", "#44475a", "#f8f8f2", "#6272a4", "#8be9fd", "#50fa7b",
    "#ffb86c", "#ff79c6", "#bd93f9", "#ff5555", "#f1fa8c",
    "#21222c", "#2b2d3a", "#343746", "#c8ccda", "#8b8fa8",
    "#403b55", "#4a4363",
}

#: Exceções conscientes, cada uma com motivo.
PERMITIDAS = {
    # Bloco HighContrast (FEAT-A11Y-HIGH-CONTRAST-01): preto/branco/amarelo
    # puros dão 21:1 de contraste — WCAG AAA. Sair da paleta ali é o objetivo.
    "#000", "#fff", "#ff0",
    # Variações de hover dos botões preenchidos (verde mais claro/escuro e os
    # fundos tingidos de laranja), derivadas das cores da paleta.
    "#6ffb90", "#3ee066", "#3d3630", "#4a4136", "#2c3a32", "#35473b",
}

#: Hex de cor. O `(?<![\w&])` descarta dois vizinhos que se parecem com cor:
#: entidades numéricas do Pango (`&#9679;` é o glifo  do indicador de conexão)
#: e números de issue citados em comentários (`cosmic-epoch#2497`). Cor de
#: verdade sempre vem depois de aspas, espaço ou início de linha.
_HEX = re.compile(r"(?<![\w&])#[0-9a-fA-F]{3,8}\b")


def _cores_de(texto: str) -> set[str]:
    return {c.lower() for c in _HEX.findall(texto)}


def _fora_da_paleta(cores: set[str]) -> set[str]:
    return cores - PALETA - PERMITIDAS


def test_cores_do_python_da_gui_saem_da_paleta() -> None:
    """QUALQUER hex nos módulos da GUI, não só `foreground="..."`.

    A primeira versão deste teste casava apenas o atributo de markup — e três
    cores continuaram escondidas num dicionário (`{"[ OK ]": "#2d8", ...}`) e em
    argumentos posicionais, exatamente onde uma revisão de olho também não
    olharia. O critério passou a ser o hex, venha de onde vier.
    """
    intrusas: dict[str, set[str]] = {}
    for arquivo in APP.rglob("*.py"):
        fora = _fora_da_paleta(_cores_de(arquivo.read_text(encoding="utf-8")))
        if fora:
            intrusas[arquivo.name] = fora

    assert not intrusas, (
        "cores fora da paleta nos módulos da GUI: "
        + "; ".join(f"{k}: {sorted(v)}" for k, v in sorted(intrusas.items()))
    )


def test_glade_usa_a_paleta() -> None:
    achadas = {
        m.group(1).lower()
        for m in re.finditer(
            r'(?:foreground|background)="(#[0-9a-fA-F]{3,8})"',
            (GUI / "main.glade").read_text(encoding="utf-8"),
        )
    }

    assert not _fora_da_paleta(achadas), (
        f"cores fora da paleta no glade: {sorted(_fora_da_paleta(achadas))}"
    )


def test_css_usa_a_paleta() -> None:
    """No CSS as cores viram tokens `@define-color`; só elas podem ser hex."""
    css = (GUI / "theme.css").read_text(encoding="utf-8")
    # Comentários saem primeiro: eles citam issues como `cosmic-epoch#2497`, que
    # o regex de hex leria como cor.
    sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    # Fora das definições de token, o CSS deve referenciar `@token`.
    sem_tokens = re.sub(
        r"@define-color\s+\w+\s+#[0-9a-fA-F]{3,8}\s*;", "", sem_comentarios
    )

    assert not _fora_da_paleta(_cores_de(sem_tokens)), (
        "cores fora da paleta no theme.css: "
        f"{sorted(_fora_da_paleta(_cores_de(sem_tokens)))}"
    )


def test_a_paleta_do_teste_bate_com_os_tokens_do_css() -> None:
    """Se o CSS ganhar um token novo, esta lista tem de saber — senão o teste
    passa a reprovar uma cor que virou oficial."""
    css = (GUI / "theme.css").read_text(encoding="utf-8")
    tokens = {
        m.group(1).lower()
        for m in re.finditer(
            r"@define-color\s+\w+\s+(#[0-9a-fA-F]{3,8})\s*;", css
        )
    }

    assert tokens <= PALETA, (
        f"tokens do CSS ausentes da paleta deste teste: {sorted(tokens - PALETA)}"
    )
