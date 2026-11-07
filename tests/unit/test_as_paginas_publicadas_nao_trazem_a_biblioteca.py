"""Nenhuma página nem gerador traz adaptador ou id de uma biblioteca real de exemplo.

Os títulos de jogo moram na régua `scripts/check_a_biblioteca_pessoal_fica_fora.py`.

A interface é a mesma em qualquer computador: o exemplo do desenho é fictício, e o dado de verdade
vem do pacote da aba. A publicada entra na régua quando sai de `mockup/DIVERGENCIAS.md`.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.interface import onde

NOMES = re.compile(
    r"TP-Link|UB500|UH700|AX211|Archer T3U|Logitech|C920|USB-BT500|Xiaomi|0e8d:0608"
    r"|\b(?:1971870|1245620|1358160|2380050)\b"
)

GERADORES = sorted([
    *INTERFACE.glob("aba[01][0-9].py"),
    INTERFACE / "desenho_da_experimental.py",
    INTERFACE / "pagina_do_mapa.py",
])


def _do_trecho_da_origem(arvore: ast.AST) -> set[int]:
    """O `antes=` de uma edição do mapa casa com a origem congelada e nunca chega à página."""
    return {id(sub) for no in ast.walk(arvore) if isinstance(no, ast.Call)
            for arg in no.keywords if arg.arg == "antes" for sub in ast.walk(arg.value)}


def _constantes(arquivo: pathlib.Path) -> list[tuple[int, str]]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    fora = _do_trecho_da_origem(arvore)
    return [(no.lineno, no.value) for no in ast.walk(arvore)
            if isinstance(no, ast.Constant) and isinstance(no.value, str) and id(no) not in fora]


def test_ha_geradores_para_varrer() -> None:
    assert {"aba08.py", "aba09.py", "aba10.py", "desenho_da_experimental.py",
            "pagina_do_mapa.py"} <= {p.name for p in GERADORES}


@pytest.mark.parametrize("arquivo", GERADORES, ids=lambda p: p.name)
def test_nenhum_gerador_traz_exemplo_real(arquivo: pathlib.Path) -> None:
    """MORDE: devolva `UB500` ao `modelo` do adaptador em `aba08.py` e reprova."""
    achados = [f"{arquivo.name}:{n}: {t[:90]!r}"
               for n, t in _constantes(arquivo) if NOMES.search(t)]
    assert not achados, "\n".join(achados)


def _em_trabalho() -> set[str]:
    corpo = (onde.ENSAIO / "DIVERGENCIAS.md").read_text(encoding="utf-8").partition("\n---\n")[2]
    return set(re.findall(r"^##\s+(\S+\.html)\s*$", corpo, re.M))


def _publicadas() -> list[pathlib.Path]:
    return sorted(p for p in onde.PUBLICADO.glob("*.html") if p.name not in _em_trabalho())


@pytest.mark.parametrize("desenho", [*sorted(onde.ENSAIO.glob("*.html")), *_publicadas()],
                         ids=lambda p: f"{p.parent.name}/{p.name}")
def test_nenhuma_pagina_traz_exemplo_real(desenho: pathlib.Path) -> None:
    """MORDE: apague as seções de `mockup/DIVERGENCIAS.md` antes do `--publicar` e reprova."""
    linhas = desenho.read_text(encoding="utf-8").splitlines()
    achados = [f"{desenho.name}:{n}: {nome}"
               for n, t in enumerate(linhas, 1) for nome in NOMES.findall(t)]
    assert not achados, "\n".join(achados)
