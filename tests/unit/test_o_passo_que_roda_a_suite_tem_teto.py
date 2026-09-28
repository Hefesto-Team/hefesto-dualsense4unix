"""O passo do CI que roda a suíte tem teto, e o teto reprova em vez de cancelar.

O-CI-DA-DEV-VOLTA-A-VERDE-01 (28/09/2026). Sem `timeout-minutes` vale o teto do
GitHub, 360 minutos: quatro corridas do `dev` no 3.10, de 25 a 27/09, ficaram
seis horas presas num `Daemon.run()` cujo `shutdown` não voltava, e saíram
«cancelled», que ninguém lê como defeito.

O teto mora no PASSO, e não no job: o do job CANCELA, o do passo REPROVA.

A MORDIDA: arranque o `timeout-minutes` do `Pytest unit` do lint-test e
`test_o_passo_que_roda_a_suite_tem_teto` reprova nomeando o job e o passo.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / ".github" / "workflows" / "ci.yml"

#: O teto do próprio GitHub. Um `timeout-minutes` igual ou acima dele não
#: muda nada.
TETO_DO_GITHUB = 360

#: O que marca um passo que roda a suíte: o `pytest` da pasta inteira de
#: unidade (e não de um arquivo dela, que é o que os portões rodam) e o script
#: das 24 partes.
MARCA_DA_SUITE = re.compile(r"pytest tests/unit(?![/\w])|rodar-a-suite\.sh")

#: Os jobs que rodam a suíte hoje. Sem eles na lista achada, a régua passaria
#: sobre nada — um passo renomeado ou um `run` reescrito tira o passo da
#: busca calado.
JOBS_QUE_RODAM_A_SUITE = {"lint-test", "gtk-real"}


def _passos_da_suite() -> list[tuple[str, dict[str, Any]]]:
    dados = yaml.safe_load(CI.read_text(encoding="utf-8"))
    achados: list[tuple[str, dict[str, Any]]] = []
    for nome_do_job, job in dados["jobs"].items():
        for passo in job.get("steps", []):
            corpo = str(passo.get("run", ""))
            if MARCA_DA_SUITE.search(corpo):
                achados.append((nome_do_job, passo))
    return achados


def test_a_busca_acha_os_passos_da_suite() -> None:
    jobs = {nome for nome, _ in _passos_da_suite()}
    assert jobs >= JOBS_QUE_RODAM_A_SUITE, (
        f"a busca não achou o passo da suíte em {sorted(JOBS_QUE_RODAM_A_SUITE - jobs)}: "
        f"a régua de baixo passaria sobre nada")


def test_o_passo_que_roda_a_suite_tem_teto() -> None:
    sem_teto = []
    for nome_do_job, passo in _passos_da_suite():
        teto = passo.get("timeout-minutes")
        if not isinstance(teto, int) or not 0 < teto < TETO_DO_GITHUB:
            sem_teto.append(f"{nome_do_job} / {passo.get('name')}: {teto!r}")
    assert not sem_teto, (
        "passo que roda a suíte sem teto no PASSO (o do job cancela, o do passo "
        "reprova), ou com teto que não fica abaixo dos 360 do GitHub:\n  "
        + "\n  ".join(sem_teto))
