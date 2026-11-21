"""O texto que descreve o `constraints.txt` o chama de piso, nunca de trava de igualdade.

OS-TEXTOS-DO-PISO-NAO-FALAM-EM-IGUALDADE-01 (D-2011-O-REGISTRO-DO-ATUALIZADOR-E-PISO): o arquivo
virou o piso da primeira instalação e o que o atualizador provou vale por cima. A página das
versões validadas, o roteiro da máquina limpa e o `LEIA.md` dele diziam que o arquivo «manda» ou
que o instalador «as usa».

A MORDIDA: devolva «o constraints.txt manda» ao roteiro ou «e o instalador as usa» à página, e a
régua reprova.
"""
from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PAGINA = RAIZ / "docs" / "usage" / "versoes-validadas.md"
ROTEIRO = RAIZ / "scripts" / "maquina-limpa" / "p3-conteiner.sh"
LEIA = RAIZ / "scripts" / "maquina-limpa" / "LEIA.md"

VELHAS = (
    "o constraints.txt manda",
    "o instalador as usa",
    "versões do\n`constraints.txt` no `pip list`",
)


@pytest.mark.parametrize("arquivo", [PAGINA, ROTEIRO, LEIA], ids=lambda p: p.name)
def test_nenhum_texto_chama_o_constraints_de_trava_de_igualdade(arquivo: Path) -> None:
    """MORDIDA: devolva a frase velha ao arquivo e a régua reprova."""
    texto = arquivo.read_text(encoding="utf-8")
    achadas = [v for v in VELHAS if v in texto]
    assert not achadas, f"{arquivo.name} ainda descreve o `constraints.txt` como trava: {achadas}"


@pytest.mark.parametrize("arquivo", [PAGINA, ROTEIRO, LEIA], ids=lambda p: p.name)
def test_o_texto_diz_que_o_constraints_e_o_piso(arquivo: Path) -> None:
    texto = arquivo.read_text(encoding="utf-8")
    assert "piso" in texto


def test_o_piso_do_arquivo_e_de_desigualdade() -> None:
    linhas = [
        ln for ln in (RAIZ / "constraints.txt").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    assert linhas
    assert all(">=" in ln and "==" not in ln for ln in linhas), linhas
