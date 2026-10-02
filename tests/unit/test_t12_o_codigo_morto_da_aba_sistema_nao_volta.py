"""T-12 (SISTEMA-O-VIGIA-VIVO-01) — o grep virado portão."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

APAGADOS_POR_FALTA_DE_CHAMADOR = {
    "_query_gamepad_state": "app/actions/daemon_actions.py (T-12, 25/08/2026)",
}


def _arquivos_python() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _ocorrencias(simbolo: str) -> dict[Path, list[str]]:
    """Todas as linhas de `src/` que citam o símbolo, por arquivo."""
    achados: dict[Path, list[str]] = {}
    for arquivo in _arquivos_python():
        linhas = [
            linha
            for linha in arquivo.read_text(encoding="utf-8").splitlines()
            if simbolo in linha
        ]
        if linhas:
            achados[arquivo] = linhas
    return achados


@pytest.mark.parametrize("simbolo", sorted(APAGADOS_POR_FALTA_DE_CHAMADOR))
def test_simbolo_morto_so_volta_com_chamador(simbolo: str) -> None:
    """Reapareceu em `src/`? Então tem de ser chamado por alguém."""
    achados = _ocorrencias(simbolo)
    if not achados:
        return

    definicoes: list[str] = []
    chamadas: list[str] = []
    for arquivo, linhas in achados.items():
        for linha in linhas:
            texto = linha.strip()
            if re.search(rf"\bdef\s+{re.escape(simbolo)}\b", texto):
                definicoes.append(f"{arquivo.relative_to(RAIZ)}: {texto}")
            elif re.search(rf"{re.escape(simbolo)}\s*\(", texto):
                chamadas.append(f"{arquivo.relative_to(RAIZ)}: {texto}")

    assert chamadas, (
        f"`{simbolo}` voltou a `src/` sem nenhum chamador.\n"
        f"Morreu em: {APAGADOS_POR_FALTA_DE_CHAMADOR[simbolo]}\n"
        f"Definições encontradas: {definicoes or 'nenhuma'}\n"
        "Código sem chamador é a família F2 desta casa: custa leitura a toda "
        "pessoa que passa e não entrega nada. Traga o chamador junto, ou "
        "não traga a função."
    )
