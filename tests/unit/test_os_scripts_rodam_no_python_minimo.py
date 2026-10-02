"""Todo script versionado tem de compilar no Python MÍNIMO que o projeto declara."""
from __future__ import annotations

import ast
import re
import shutil
import sys
from pathlib import Path

import pytest

from tests.conftest import binario_do_venv

RAIZ = Path(__file__).resolve().parents[2]

TERRITORIOS = ("src", "scripts", "tests")


def _minimo_declarado() -> tuple[int, int]:
    """O Python mínimo, lido do `pyproject.toml` — nunca digitado aqui."""
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    achado = re.search(r'requires-python\s*=\s*"[><=~^]*(\d+)\.(\d+)', texto)
    assert achado, "não achei `requires-python` no pyproject.toml"
    return int(achado.group(1)), int(achado.group(2))


def _fontes() -> list[Path]:
    achadas: list[Path] = []
    for territorio in TERRITORIOS:
        for f in (RAIZ / territorio).rglob("*.py"):
            if any(p in {"__pycache__", ".venv", "venv"} for p in f.parts):
                continue
            achadas.append(f)
    return sorted(achadas)


def test_a_regua_sabe_reprovar() -> None:
    """Valide o instrumento antes de acreditar nele — a disciplina da casa."""
    minimo = _minimo_declarado()
    if minimo >= (3, 12):
        pytest.skip("o mínimo declarado já é 3.12+; a régua não teria o que pegar")

    with pytest.raises(SyntaxError):
        ast.parse("type X = int", feature_version=minimo)


def test_todo_script_compila_no_minimo_declarado() -> None:
    """MORDE: escrever sintaxe de 3.12 em qualquer script versionado."""
    minimo = _minimo_declarado()
    quebrados: list[str] = []

    for f in _fontes():
        fonte = f.read_text(encoding="utf-8", errors="replace")
        try:
            ast.parse(fonte, feature_version=minimo)
        except SyntaxError as erro:
            quebrados.append(
                f"{f.relative_to(RAIZ)}:{erro.lineno} — {erro.msg}"
            )

    versao = ".".join(map(str, minimo))
    assert not quebrados, (
        f"estes arquivos NÃO compilam no Python {versao}, que é o mínimo que o "
        f"`pyproject.toml` declara suportar (esta bancada roda "
        f"{'.'.join(map(str, sys.version_info[:2]))}, e por isso não acusa):\n  "
        + "\n  ".join(quebrados)
    )


def test_o_ruff_cobre_scripts_tambem() -> None:
    """O buraco que deixou o defeito passar: o CI não roda `ruff` em `scripts/`."""
    import subprocess

    ruff = binario_do_venv("ruff") or shutil.which("ruff")
    if ruff is None:
        pytest.skip(
            "não há `ruff` no venv desta árvore, no da árvore principal, nem "
            "no PATH — sem ele não há o que medir em `scripts/`"
        )

    p = subprocess.run(
        [str(ruff), "check", "scripts/", "--output-format", "concise"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=300,
    )

    quebras = [
        linha for linha in p.stdout.splitlines() if "invalid-syntax" in linha
    ]

    assert not quebras, (
        "há sintaxe nova demais para o `target-version` do projeto em "
        "`scripts/` — o CI roda `ruff check src/ tests/` e não olha essa "
        "pasta, então este teste é o único portão:\n  "
        + "\n  ".join(quebras)
    )
