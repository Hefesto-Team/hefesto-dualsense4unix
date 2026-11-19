"""O mypy mede com o Python que o roda, nunca com versão menor que a das bibliotecas."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

RAIZ = Path(__file__).resolve().parents[2]
PYPROJECT = RAIZ / "pyproject.toml"
CI = RAIZ / ".github" / "workflows" / "ci.yml"


def _versao(texto: str) -> tuple[int, int]:
    maior, menor = texto.split(".")[:2]
    return int(maior), int(menor)


def _config_do_mypy(texto: str | None = None) -> dict[str, Any]:
    dados = tomllib.loads(PYPROJECT.read_text(encoding="utf-8") if texto is None else texto)
    config: dict[str, Any] = dados["tool"]["mypy"]
    return config


def _pythons_do_typecheck() -> set[tuple[int, int]]:
    jobs = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]
    return {
        _versao(str(p["with"]["python-version"]))
        for p in jobs["typecheck"]["steps"]
        if str(p.get("uses", "")).startswith("actions/setup-python")
    }


def _pythons_que_rodam_o_mypy() -> set[tuple[int, int]]:
    return _pythons_do_typecheck() | {sys.version_info[:2]}


def faltas(config: dict[str, Any], pythons: set[tuple[int, int]]) -> list[str]:
    if "python_version" not in config:
        return []
    alvo = _versao(str(config["python_version"]))
    return [
        f"o mypy mede como {alvo[0]}.{alvo[1]} e roda no {p[0]}.{p[1]}: "
        "lê os tipos das bibliotecas instaladas para outra versão"
        for p in sorted(pythons)
        if alvo < p
    ]


def test_o_mypy_mede_com_o_python_que_o_roda() -> None:
    assert faltas(_config_do_mypy(), _pythons_que_rodam_o_mypy()) == []


def test_a_regua_le_o_python_do_typecheck() -> None:
    assert _pythons_do_typecheck() == {(3, 12)}


def test_mordida_a_versao_fixa_de_volta() -> None:
    mordida = PYPROJECT.read_text(encoding="utf-8").replace(
        "[tool.mypy]\n", '[tool.mypy]\npython_version = "3.10"\n'
    )
    assert faltas(_config_do_mypy(mordida), _pythons_que_rodam_o_mypy()) != []
