"""A `.janela` nunca é mais alta que a vista — o rodapé não sai pela borda."""

from __future__ import annotations

import pathlib
import re

import pytest

from hefesto_dualsense4unix.interface import onde

VISTAS = (900, 809, 790, 760, 700)

_RECUO = re.compile(r"--recuo-do-corpo:\s*(\d+)px")


def _folha() -> str:
    return (pathlib.Path(__file__).resolve().parents[2]
            / "src/hefesto_dualsense4unix/interface/topo.html").read_text(encoding="utf-8")


def test_a_folha_ainda_declara_o_recuo() -> None:
    """A premissa da conta. Sem ela, o resto mede o próprio palpite."""
    assert _RECUO.search(_folha()), (
        "`--recuo-do-corpo` sumiu da folha comum — a conta da altura da janela "
        "mudou de forma, e esta régua está medindo o mundo de ontem")


def test_a_janela_tem_teto_de_vista() -> None:
    """O `max-height` existe e é calculado a partir da vista, não fixo."""
    folha = _folha()
    assert re.search(
        r"\.janela\{[^}]*max-height:\s*calc\(\s*100dvh\s*-\s*var\(--recuo-do-corpo\)\s*\*\s*2\s*\)",
        folha, re.S), (
        "a `.janela` perdeu o teto de vista: sem ele, toda vista abaixo de 809 px "
        "empurra o rodapé para fora da tela, e os quatro botões de ação ficam "
        "inalcançáveis sem rolar")


@pytest.mark.parametrize("aba", [p.name for p in onde.paginas()])
def test_toda_aba_carrega_o_teto(aba: str) -> None:
    """As DEZ, e não só a que se olhou."""
    doc = onde.pagina(aba).read_text(encoding="utf-8")
    if 'class="janela"' not in doc:
        pytest.skip(f"{aba} não usa a `.janela` — tela auxiliar")
    assert "max-height:calc(100dvh - var(--recuo-do-corpo) * 2)" in doc, (
        f"{aba} está com a folha VELHA — rode o gerador dela. Sem o teto, a "
        f"janela estreita corta o rodapé desta aba")
