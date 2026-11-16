"""O job `pre-commit` do CI pula só o gancho que outro job já roda igual.

Um id no `SKIP` só vale se o gancho roda sem lista de arquivos (`pass_filenames: false`), com
o comando de um portão do `scripts/portoes.sh` que algum job do `ci.yml` chama pelo `--so`. O
gancho que lê os arquivos que o framework passa, ou cujo comando difere, fica no job.
"""

from __future__ import annotations

import copy
import re
import shlex
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / ".github" / "workflows" / "ci.yml"
GANCHOS = RAIZ / ".pre-commit-config.yaml"
PORTOES = RAIZ / "scripts" / "portoes.sh"
INTERPRETES = {"python3", "python", "bash", "sh"}


def _sem_interprete(comando: str) -> tuple[str, ...]:
    partes = shlex.split(comando)
    while partes and partes[0] in INTERPRETES:
        partes = partes[1:]
    return tuple(partes)


def _jobs() -> dict[str, Any]:
    jobs: dict[str, Any] = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]
    return jobs


def _ganchos() -> dict[str, dict[str, Any]]:
    dados = yaml.safe_load(GANCHOS.read_text(encoding="utf-8"))
    return {g["id"]: g for repo in dados["repos"] for g in repo["hooks"]}


def _portoes() -> dict[tuple[str, ...], str]:
    tabela = {}
    for linha in PORTOES.read_text(encoding="utf-8").splitlines():
        campos = linha.split("|")
        if len(campos) >= 4 and campos[0] in {"rapido", "completo"}:
            tabela[_sem_interprete(campos[3])] = campos[1]
    return tabela


def _ids_chamados_no_ci(jobs: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for job in jobs.values():
        for passo in job.get("steps", []):
            for achado in re.finditer(r"portoes\.sh --so ([^\n]+)", str(passo.get("run", ""))):
                ids |= set(achado.group(1).split())
    return ids


def _skip(jobs: dict[str, Any]) -> list[str]:
    for passo in jobs["pre-commit"]["steps"]:
        if "pre-commit run" in str(passo.get("run", "")):
            valor = str((passo.get("env") or {}).get("SKIP", ""))
            return [i for i in valor.split(",") if i]
    raise AssertionError("o job pre-commit perdeu o passo que roda os ganchos")


def faltas_do_skip(jobs: dict[str, Any], ganchos: dict[str, dict[str, Any]]) -> list[str]:
    """Cada id do SKIP tem par: o mesmo comando, sem arquivos, num portão que o CI chama."""
    portoes, no_ci, faltas = _portoes(), _ids_chamados_no_ci(jobs), []
    for gid in _skip(jobs):
        gancho = ganchos.get(gid)
        if gancho is None:
            faltas.append(f"{gid}: não existe no .pre-commit-config.yaml")
            continue
        if gancho.get("pass_filenames", True):
            faltas.append(f"{gid}: o gancho lê os arquivos que o framework passa; o portão não")
            continue
        portao = portoes.get(_sem_interprete(gancho["entry"]))
        if portao is None:
            faltas.append(f"{gid}: nenhum portão roda «{gancho['entry']}»")
        elif portao not in no_ci:
            faltas.append(f"{gid}: o portão {portao} não roda em nenhum job do CI")
    return faltas


def test_cada_gancho_pulado_tem_o_portao_igual_num_job_do_ci() -> None:
    assert _skip(_jobs()), "o SKIP sumiu: o job volta a repetir os portões"
    assert faltas_do_skip(_jobs(), _ganchos()) == []


def test_o_texto_enxuto_e_os_ganchos_por_arquivo_seguem_no_job() -> None:
    pulados = set(_skip(_jobs()))
    ficam = {"texto-enxuto", "ruff-check", "acentuacao-strict", "glifos", "texto-sem-pessoa"}
    assert not pulados & ficam, pulados & ficam
    assert set(_ganchos()) - pulados >= ficam


def _com_skip(*ids: str) -> dict[str, Any]:
    jobs = copy.deepcopy(_jobs())
    for passo in jobs["pre-commit"]["steps"]:
        if "pre-commit run" in str(passo.get("run", "")):
            passo["env"]["SKIP"] = ",".join([*_skip(_jobs()), *ids])
    return jobs


def test_mordida_pular_o_texto_enxuto_reprova() -> None:
    faltas = faltas_do_skip(_com_skip("texto-enxuto"), _ganchos())
    assert any(f.startswith("texto-enxuto:") for f in faltas), faltas


def test_mordida_id_que_nao_existe_reprova() -> None:
    faltas = faltas_do_skip(_com_skip("gancho-inventado"), _ganchos())
    assert any("não existe" in f for f in faltas), faltas


def test_mordida_portao_que_o_ci_nao_chama_reprova() -> None:
    jobs = _com_skip()
    for job in jobs.values():
        for passo in job.get("steps", []):
            if "portoes.sh --so" in str(passo.get("run", "")):
                passo["run"] = str(passo["run"]).replace(" icones", "")
    faltas = faltas_do_skip(jobs, _ganchos())
    assert any(f.startswith("icones-refletem-o-svg:") for f in faltas), faltas


def test_mordida_comando_diferente_do_portao_reprova() -> None:
    ganchos = copy.deepcopy(_ganchos())
    ganchos["referencias-docs"]["entry"] = "python3 scripts/validar-referencias-docs.py"
    faltas = faltas_do_skip(_jobs(), ganchos)
    assert any(f.startswith("referencias-docs:") for f in faltas), faltas
