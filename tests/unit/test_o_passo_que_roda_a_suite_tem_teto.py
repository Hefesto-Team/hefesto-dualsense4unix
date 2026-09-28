"""O passo do CI que roda a suíte tem teto, e o teto reprova em vez de cancelar.

O-CI-DA-DEV-VOLTA-A-VERDE-01 (28/09/2026). Sem `timeout-minutes` vale o teto do
GitHub, 360 minutos: quatro corridas do `dev` no 3.10, de 25 a 27/09, ficaram
seis horas presas num `Daemon.run()` cujo `shutdown` não voltava, e saíram
«cancelled», que ninguém lê como defeito.

O teto mora no PASSO, e não no job: o do job CANCELA, o do passo REPROVA. E o
do job, quando existe, fica acima do do passo: o relógio do job corre desde a
instalação, e um teto de job que estoura antes do passo devolve o «cancelled».

Vale para todo passo que espera um `Daemon.run()` voltar: a suíte (a pasta
inteira de unidade e as 24 partes) e o smoke do `run.sh`, que sobe o daemon de
verdade e espera o `stop()`.

A MORDIDA: arranque o `timeout-minutes` do `Pytest unit` do lint-test e
`test_o_passo_que_roda_a_suite_tem_teto` reprova nomeando o job e o passo; ponha
no job do lint-test um teto de 60 e ele reprova pelo teto do job.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / ".github" / "workflows" / "ci.yml"

#: O teto do próprio GitHub. Um `timeout-minutes` igual ou acima dele não
#: muda nada, e é o teto de todo job que não declara o seu.
TETO_DO_GITHUB = 360

#: Quanto o teto do job fica, no mínimo, acima do teto do passo. Nas corridas
#: do `dev` de 25 a 27/09, o que vem antes do passo levou de 0,9 a 1,9 minuto.
FOLGA_DO_JOB = 10

#: O que marca um passo que espera um `Daemon.run()` voltar: o `pytest` da
#: pasta inteira de unidade (e não de um arquivo dela, que é o que os portões
#: rodam), o script das 24 partes e o smoke do `run.sh`.
MARCA_DO_PASSO = re.compile(
    r"pytest tests/unit(?![/\w])|rodar-a-suite\.sh|run\.sh --smoke")

#: Os jobs que têm esse passo hoje. Sem eles na lista achada, a régua passaria
#: sobre nada — um passo renomeado ou um `run` reescrito tira o passo da
#: busca calado.
JOBS_COM_O_PASSO = {"lint-test", "gtk-real", "runtime-smoke"}


def _teto(valor: Any) -> int | None:
    # `bool` é `int` em Python: `timeout-minutes: true` não é teto.
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor


def _passos_marcados() -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    dados = yaml.safe_load(CI.read_text(encoding="utf-8"))
    achados: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for nome_do_job, job in dados["jobs"].items():
        for passo in job.get("steps", []):
            corpo = str(passo.get("run", ""))
            if MARCA_DO_PASSO.search(corpo):
                achados.append((nome_do_job, job, passo))
    return achados


def test_a_busca_acha_os_passos_da_suite() -> None:
    jobs = {nome for nome, _, _ in _passos_marcados()}
    assert jobs >= JOBS_COM_O_PASSO, (
        f"a busca não achou o passo em {sorted(JOBS_COM_O_PASSO - jobs)}: "
        f"a régua de baixo passaria sobre nada")


def test_o_passo_que_roda_a_suite_tem_teto() -> None:
    sem_teto = []
    for nome_do_job, job, passo in _passos_marcados():
        rotulo = f"{nome_do_job} / {passo.get('name')}"
        teto = _teto(passo.get("timeout-minutes"))
        if teto is None or not 0 < teto < TETO_DO_GITHUB:
            sem_teto.append(f"{rotulo}: {passo.get('timeout-minutes')!r}")
            continue
        teto_do_job = _teto(job.get("timeout-minutes", TETO_DO_GITHUB))
        if teto_do_job is None or teto_do_job < teto + FOLGA_DO_JOB:
            sem_teto.append(
                f"{rotulo}: o job tem teto {job.get('timeout-minutes')!r}, "
                f"que não fica {FOLGA_DO_JOB} minutos acima dos {teto} do "
                f"passo; o job cancela antes de o passo reprovar")
    assert not sem_teto, (
        "passo que espera o daemon sem teto no PASSO (o do job cancela, o do "
        "passo reprova), com teto que não fica abaixo dos 360 do GitHub, ou "
        "com o teto do job por baixo:\n  "
        + "\n  ".join(sem_teto))
