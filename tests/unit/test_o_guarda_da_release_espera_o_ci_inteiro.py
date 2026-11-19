"""A release espera o CI da tag inteiro, não repete a suíte, e o pacote se constrói antes da tag."""

from __future__ import annotations

import copy
import os
import re
import shutil
import stat
import subprocess
from functools import cache
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / ".github" / "workflows" / "ci.yml"
RELEASE = RAIZ / ".github" / "workflows" / "release.yml"
PECA = RAIZ / "assets" / "gdk-runtime"

PADRAO_DO_GITHUB = 360
FOLGA = 10
REPETE_O_CI = ("rodar-a-suite.sh", "ruff check", "mypy ")


def _jobs(arquivo: Path) -> dict[str, Any]:
    jobs: dict[str, Any] = yaml.safe_load(arquivo.read_text(encoding="utf-8"))["jobs"]
    return jobs


def _needs(job: dict[str, Any]) -> list[str]:
    precisa = job.get("needs", [])
    return [precisa] if isinstance(precisa, str) else list(precisa)


def caminho_mais_longo(jobs: dict[str, Any]) -> int:
    @cache
    def ate(nome: str) -> int:
        job = jobs[nome]
        antes = max((ate(n) for n in _needs(job)), default=0)
        return antes + int(job.get("timeout-minutes", PADRAO_DO_GITHUB))

    return max(ate(nome) for nome in jobs)


def _passo_que_espera(guarda: dict[str, Any]) -> dict[str, Any]:
    passos = [p for p in guarda.get("steps", []) if "ci.yml/runs" in str(p.get("run", ""))]
    assert len(passos) == 1, f"esperava um passo que consulta o ci.yml, achei {len(passos)}"
    passo: dict[str, Any] = passos[0]
    return passo


def teto_do_guarda(guarda: dict[str, Any]) -> int:
    passo = _passo_que_espera(guarda)
    tetos = [int(guarda.get("timeout-minutes", PADRAO_DO_GITHUB))]
    if "timeout-minutes" in passo:
        tetos.append(int(passo["timeout-minutes"]))
    tetos += [int(s) // 60 for s in re.findall(r"LIMITE_SEG=(\d+)", str(passo.get("run", "")))]
    return min(tetos)


def faltas(ci: dict[str, Any], release: dict[str, Any]) -> list[str]:
    achados: list[str] = []
    guarda = release["guarda-ci"]
    precisa = caminho_mais_longo(ci) + FOLGA
    teto = teto_do_guarda(guarda)
    if teto < precisa:
        achados.append(
            f"guarda-ci: desiste aos {teto} min, e o ci.yml pode levar {precisa - FOLGA}"
        )
    if not re.search(
        r"gh run watch .*--exit-status", str(_passo_que_espera(guarda).get("run", ""))
    ):
        achados.append("guarda-ci: não espera o fim do run do ci.yml (gh run watch --exit-status)")
    corpo = "\n".join(str(p.get("run", "")) for p in release["build"].get("steps", []))
    achados += [
        f"build: repete o que o ci.yml já cobra ({m.strip()})" for m in REPETE_O_CI if m in corpo
    ]
    if int(release["build"].get("timeout-minutes", PADRAO_DO_GITHUB)) > 15:
        achados.append("build: sem teto de 15 minutos")
    corpo_do_ci = "\n".join(str(p.get("run", "")) for j in ci.values() for p in j.get("steps", []))
    for comando in ("scripts/build_appimage.sh", "construir.sh dist/peca-gdk --conferir"):
        if comando not in corpo_do_ci:
            achados.append(f"ci.yml: nenhum job roda `{comando}` antes da tag")
    return achados


def test_a_release_espera_o_ci_inteiro_e_nao_repete_a_suite() -> None:
    assert faltas(_jobs(CI), _jobs(RELEASE)) == []


def test_a_regua_le_o_caminho_do_ci() -> None:
    ci = _jobs(CI)
    assert caminho_mais_longo(ci) >= max(int(j["timeout-minutes"]) for j in ci.values())


def test_mordida_o_teto_de_45_minutos_volta() -> None:
    release = copy.deepcopy(_jobs(RELEASE))
    passo = _passo_que_espera(release["guarda-ci"])
    passo["run"] = "LIMITE_SEG=2700\n" + str(passo["run"])
    assert any("desiste aos 45 min" in f for f in faltas(_jobs(CI), release))


def test_mordida_o_build_volta_a_rodar_a_suite() -> None:
    release = copy.deepcopy(_jobs(RELEASE))
    release["build"]["steps"].append({"run": "bash scripts/rodar-a-suite.sh"})
    assert "build: repete o que o ci.yml já cobra (rodar-a-suite.sh)" in faltas(_jobs(CI), release)


def _versoes_do_pino() -> dict[str, str]:
    linha = next(
        x
        for x in (PECA / "pino.txt").read_text(encoding="utf-8").splitlines()
        if x.startswith("mingw=")
    )
    return dict(p.split("=", 1) for p in linha.removeprefix("mingw=").split())


def _construir(tmp_path: Path, versoes: dict[str, str]) -> subprocess.CompletedProcess[str]:
    copia = tmp_path / "gdk-runtime"
    copia.mkdir()
    for nome in ("construir.sh", "pino.txt"):
        shutil.copy(PECA / nome, copia / nome)
    casos = "".join(f"  {p}) printf '%s' '{v}' ;;\n" for p, v in versoes.items())
    marca = tmp_path / "compilou"
    for nome, corpo in (
        ("dpkg-query", f'for a; do p="$a"; done\ncase "$p" in\n{casos}  *) exit 1 ;;\nesac\n'),
        ("cc", f"touch '{marca}'\nexit 1\n"),
    ):
        falso = tmp_path / nome
        falso.write_text(f"#!/bin/sh\n{corpo}", encoding="utf-8")
        falso.chmod(falso.stat().st_mode | stat.S_IXUSR)
    ambiente = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "CC": str(tmp_path / "cc"),
    }
    return subprocess.run(
        ["bash", str(copia / "construir.sh"), str(tmp_path / "saida"), "--conferir"],
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=60,
        check=False,
    )


def test_o_pino_diz_a_versao_de_cada_pacote_do_mingw() -> None:
    versoes = _versoes_do_pino()
    assert "gcc-mingw-w64-x86-64-posix" in versoes
    assert all(versoes.values())


def test_o_construir_com_o_mingw_do_pino_passa_a_conferencia_e_compila(tmp_path: Path) -> None:
    feito = _construir(tmp_path, _versoes_do_pino())
    assert "o compilador mudou" not in feito.stderr
    assert (tmp_path / "compilou").exists()


def test_o_construir_diz_que_o_compilador_mudou_antes_de_compilar(tmp_path: Path) -> None:
    versoes = {**_versoes_do_pino(), "gcc-mingw-w64-x86-64-posix": "14.2.0-1ubuntu1"}
    feito = _construir(tmp_path, versoes)
    assert feito.returncode == 1
    assert "o compilador mudou" in feito.stderr
    assert not (tmp_path / "compilou").exists()
