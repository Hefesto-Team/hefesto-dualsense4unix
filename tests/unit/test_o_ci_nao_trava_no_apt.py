"""O CI não trava no apt nem espera seis horas (O-CI-NAO-TRAVA-NO-APT-NEM-ESPERA-SEIS-HORAS-01).

O apt do runner espera o espelho sem prazo e sem nova tentativa, e um job sem
``timeout-minutes`` espera o padrão do GitHub, 360 minutos. A régua lê o
``.github/workflows/ci.yml`` e reprova, pelo NOME do job:

* job sem ``timeout-minutes``;
* job que toca o apt (``apt-get`` num passo, o ``install_cmd`` da matriz ou um
  script ``.sh`` do repositório que chama o ``apt-get``) sem um passo ANTES que grave
  ``/etc/apt/apt.conf.d/80-prazo`` com ``Acquire::Retries`` e
  ``Acquire::http::Timeout``;
* o prazo de um passo maior que o do job que o contém (o job cortaria o passo).
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / ".github" / "workflows" / "ci.yml"

MARCAS_DO_PRAZO = ("80-prazo", "Acquire::Retries", "Acquire::http::Timeout")

# O passo que chama um script do repositório toca o apt se o script o chama.
SCRIPT_CHAMADO = re.compile(r"(?:\bbash\s+|\./)([\w./-]+\.sh)\b")


def _carregar(texto: str | None = None) -> dict[str, Any]:
    dado = yaml.safe_load(CI.read_text(encoding="utf-8") if texto is None else texto)
    assert isinstance(dado, dict) and isinstance(dado.get("jobs"), dict)
    jobs: dict[str, Any] = dado["jobs"]
    return jobs


def _grava_o_prazo(passo: dict[str, Any]) -> bool:
    corpo = str(passo.get("run", ""))
    return all(marca in corpo for marca in MARCAS_DO_PRAZO)


def _o_script_chama_o_apt(caminho: str) -> bool:
    script = RAIZ / caminho
    return script.is_file() and "apt-get" in script.read_text(encoding="utf-8")


def _toca_o_apt(passo: dict[str, Any], job: dict[str, Any]) -> bool:
    corpo = str(passo.get("run", ""))
    if "apt-get" in corpo or any(_o_script_chama_o_apt(c) for c in SCRIPT_CHAMADO.findall(corpo)):
        return True
    if "matrix.install_cmd" in corpo:
        matriz = (job.get("strategy") or {}).get("matrix") or {}
        return any("apt-get" in str(e.get("install_cmd", "")) for e in matriz.get("include", []))
    return False


def lacunas(jobs: dict[str, Any]) -> list[str]:
    """Cada falta, com o nome do job. Função pura: a mordida a chama com cópias."""
    achados: list[str] = []
    for nome, job in jobs.items():
        prazo_do_job = job.get("timeout-minutes")
        if not isinstance(prazo_do_job, int) or prazo_do_job <= 0:
            achados.append(f"{nome}: sem timeout-minutes no job")
        passos = job.get("steps") or []
        primeiro = next((i for i, p in enumerate(passos) if _toca_o_apt(p, job)), None)
        if primeiro is not None and not any(_grava_o_prazo(p) for p in passos[:primeiro]):
            achados.append(f"{nome}: toca o apt no passo {primeiro + 1} sem o passo do prazo antes")
        if isinstance(prazo_do_job, int):
            for p in passos:
                dentro = p.get("timeout-minutes")
                if isinstance(dentro, int) and dentro >= prazo_do_job:
                    achados.append(
                        f"{nome}: o passo «{p.get('name', '?')}» ({dentro} min) "
                        f"não cabe no job ({prazo_do_job} min)"
                    )
    return achados


def test_o_ci_nao_trava_no_apt_nem_espera_seis_horas() -> None:
    assert lacunas(_carregar()) == []


def test_o_ci_tem_jobs_e_apt_para_a_regua_medir() -> None:
    jobs = _carregar()
    com_apt = [n for n, j in jobs.items() if any(_toca_o_apt(p, j) for p in j.get("steps") or [])]
    assert len(jobs) >= 15, "a régua leu poucos jobs: o arquivo mudou de forma"
    assert {
        "lint-test",
        "gtk-real",
        "anonymity",
        "smoke-multi-distro",
        "banco-de-prova-sonda",
    } <= set(com_apt)


JOBS_COM_APT = [
    "anonymity",
    "lint-test",
    "gtk-real",
    "smoke-multi-distro",
    "install-multi-distro",
    "banco-de-prova-sonda",
]


@pytest.mark.parametrize("job", JOBS_COM_APT)
def test_tirar_o_passo_do_prazo_reprova_aquele_job(job: str) -> None:
    jobs = copy.deepcopy(_carregar())
    jobs[job]["steps"] = [p for p in jobs[job]["steps"] if not _grava_o_prazo(p)]
    achados = lacunas(jobs)
    assert [a for a in achados if a.startswith(f"{job}: toca o apt")], achados
    assert all(a.startswith(f"{job}:") for a in achados), achados


@pytest.mark.parametrize("job", ["glifos", "lint-test", "gtk-real"])
def test_tirar_o_timeout_do_job_reprova_aquele_job(job: str) -> None:
    jobs = copy.deepcopy(_carregar())
    del jobs[job]["timeout-minutes"]
    assert lacunas(jobs) == [f"{job}: sem timeout-minutes no job"]


def test_o_prazo_do_job_cobre_o_passo_mais_longo() -> None:
    jobs = copy.deepcopy(_carregar())
    jobs["gtk-real"]["timeout-minutes"] = 90
    assert any("não cabe no job" in a and a.startswith("gtk-real:") for a in lacunas(jobs))


def test_o_apt_depois_do_prazo_e_o_prazo_depois_do_apt() -> None:
    """A ordem importa: o passo do prazo DEPOIS do primeiro apt não vale."""
    jobs = copy.deepcopy(_carregar())
    passos = jobs["icones"]["steps"]
    posicao = next(i for i, p in enumerate(passos) if _grava_o_prazo(p))
    passos.append(passos.pop(posicao))
    assert any(a.startswith("icones: toca o apt") for a in lacunas(jobs))


def test_o_apt_em_comentario_nao_conta() -> None:
    texto = (
        "jobs:\n  so-comentario:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n"
        "    steps:\n      # sudo apt-get install -y nada\n      - run: echo ok\n"
    )
    assert lacunas(_carregar(texto)) == []


def test_o_apt_dentro_do_script_chamado_conta() -> None:
    """A sonda não escreve ``apt-get`` no passo: o ``sonda.sh`` é quem chama."""
    jobs = copy.deepcopy(_carregar())
    passos = jobs["banco-de-prova-sonda"]["steps"]
    assert not any("apt-get" in str(p.get("run", "")) for p in passos)
    jobs["banco-de-prova-sonda"]["steps"] = [p for p in passos if not _grava_o_prazo(p)]
    assert lacunas(jobs) == [
        "banco-de-prova-sonda: toca o apt no passo 2 sem o passo do prazo antes"
    ]
