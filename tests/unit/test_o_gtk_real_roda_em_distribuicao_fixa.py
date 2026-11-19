"""O GTK real do CI roda em distribuição fixa, e todo classificador tem célula que o rode."""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Any

import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / ".github" / "workflows" / "ci.yml"
PYPROJECT = RAIZ / "pyproject.toml"

PYTHON_DA_DISTRO = {"ubuntu-24.04": "3.12", "ubuntu-26.04": "3.14"}
CELULA_QUE_DECIDE = "ubuntu-24.04"
CLASSIFICADOR = re.compile(r"Programming Language :: Python :: (3\.\d+)$")


def _jobs() -> dict[str, Any]:
    jobs: dict[str, Any] = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]
    return jobs


def _classificadores() -> list[str]:
    dados = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return [m[1] for c in dados["project"]["classifiers"] if (m := CLASSIFICADOR.match(c))]


def _usa_o_python_do_sistema(job: dict[str, Any]) -> bool:
    return "container" not in job and not any(
        str(p.get("uses", "")).startswith("actions/setup-python") for p in job.get("steps", [])
    )


def _distros(job: dict[str, Any]) -> list[str]:
    matriz = job.get("strategy", {}).get("matrix", {})
    return [str(d) for d in matriz.get("os", [])] + [
        str(c["os"]) for c in matriz.get("include", []) if "os" in c
    ]


def faltas(jobs: dict[str, Any], classificadores: list[str]) -> list[str]:
    achados = [
        f"{nome}: usa o Python do sistema em «ubuntu-latest», que muda de distribuição sem commit"
        for nome, job in jobs.items()
        if job.get("runs-on") == "ubuntu-latest" and _usa_o_python_do_sistema(job)
    ]
    gtk = jobs.get("gtk-real", {})
    distros = _distros(gtk)
    if gtk.get("runs-on") != "${{ matrix.os }}":
        achados.append("gtk-real: o runs-on não é a distribuição da matriz")
    if CELULA_QUE_DECIDE not in gtk.get("strategy", {}).get("matrix", {}).get("os", []):
        achados.append(f"gtk-real: a célula que decide ({CELULA_QUE_DECIDE}) não roda as faixas")
    achados += [f"gtk-real: «{d}» sem Python medido" for d in distros if d not in PYTHON_DA_DISTRO]
    pernas = jobs.get("lint-test", {}).get("strategy", {}).get("matrix", {}).get("python", [])
    provadas = {str(v) for v in pernas}
    provadas |= {PYTHON_DA_DISTRO[d] for d in distros if d in PYTHON_DA_DISTRO}
    achados += [
        f"pyproject: o classificador {v} não tem célula que o rode"
        for v in classificadores
        if v not in provadas
    ]
    return achados


def test_o_gtk_real_roda_em_distribuicao_fixa_e_prova_os_classificadores() -> None:
    assert faltas(_jobs(), _classificadores()) == []


def test_mordida_o_gtk_real_de_volta_ao_ubuntu_latest() -> None:
    jobs = copy.deepcopy(_jobs())
    jobs["gtk-real"]["runs-on"] = "ubuntu-latest"
    assert any("gtk-real: usa o Python do sistema" in f for f in faltas(jobs, _classificadores()))


def test_mordida_classificador_sem_celula() -> None:
    assert faltas(_jobs(), [*_classificadores(), "3.13"]) == [
        "pyproject: o classificador 3.13 não tem célula que o rode"
    ]


def test_mordida_a_celula_de_3_14_sai() -> None:
    jobs = copy.deepcopy(_jobs())
    jobs["gtk-real"]["strategy"]["matrix"].pop("include")
    sem_celula = "pyproject: o classificador 3.14 não tem célula que o rode"
    assert sem_celula in faltas(jobs, _classificadores())
