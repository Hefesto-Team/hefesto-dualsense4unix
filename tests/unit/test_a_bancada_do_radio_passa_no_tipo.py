"""O ensaio do rádio passa no mypy.

Sprint A-SONDA-DO-BLUEZ-PERGUNTA-SO-AO-DONO-E-O-ENSAIO-PASSA-NO-TIPO-01. O portão ``mypy`` do
``portoes.sh`` mede só ``src/``; ``scripts/bancada_do_radio.py`` nunca foi medido.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "scripts" / "bancada_do_radio.py"


def _mypy() -> list[str] | None:
    achado = shutil.which("mypy")
    if achado:
        return [achado]
    irmao = Path(sys.executable).parent / "mypy"
    return [str(irmao)] if irmao.exists() else None


def _erros(arquivo: Path, tmp_path: Path) -> str:
    comando = _mypy()
    assert comando is not None
    fim = subprocess.run(
        [*comando, "--cache-dir", str(tmp_path / "mypy"), str(arquivo)],
        capture_output=True,
        text=True,
        check=False,
        cwd=RAIZ,
    )
    return fim.stdout


def test_a_bancada_do_radio_passa_no_mypy(tmp_path: Path) -> None:
    if _mypy() is None:
        pytest.skip("o mypy não existe nesta máquina")
    saida = _erros(BANCADA, tmp_path)
    assert "Success: no issues found" in saida, saida


def test_a_regua_morde_o_nome_solto_do_achado(tmp_path: Path) -> None:
    """MORDIDA embutida: o ``quem`` fora do par, como ``str | None``, reprova."""
    if _mypy() is None:
        pytest.skip("o mypy não existe nesta máquina")
    fonte = BANCADA.read_text(encoding="utf-8")
    velho = "    fio, quem = achado\n"
    assert velho in fonte
    quebrado = fonte.replace(
        velho, "    fio = achado[0]\n    quem: str | None = achado[1]\n", 1
    )
    copia = tmp_path / "bancada_quebrada.py"
    copia.write_text(quebrado, encoding="utf-8")
    assert "arg-type" in _erros(copia, tmp_path)
