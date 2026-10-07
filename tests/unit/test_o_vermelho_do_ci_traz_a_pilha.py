"""O vermelho da suíte no CI traz a pilha, em vez de só o nome de quem reprovou.

O `scripts/rodar-a-suite.sh` grava cada parte em `$SAIDA/parte-NN.log` e imprime
só o NOME do teste vermelho (a saída crua não vai ao terminal da mantenedora).
No runner o `/tmp` morre com o job: um vermelho intermitente (07/10/2026, o
`test_o_pacote_leva_a_familia_ao_endereco_do_card`, parte-02 do `gtk-real`)
chegou sem pilha nenhuma, e a causa não pôde ser decidida.

Todo job cujo passo roda a suíte inteira tem de: (1) fixar o `SAIDA`; (2) ter,
depois, um passo `if: failure()` que imprime as `FAILURES` dos logs; (3) ter,
depois, um passo `if: failure()` que sobe os logs como artefato.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / ".github" / "workflows" / "ci.yml"
SCRIPT = RAIZ / "scripts" / "rodar-a-suite.sh"
RODA_A_SUITE = "scripts/rodar-a-suite.sh"


def _jobs() -> dict[str, Any]:
    jobs: dict[str, Any] = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]
    return jobs


def _passos_que_rodam_a_suite(job: dict[str, Any]) -> list[int]:
    return [
        i for i, p in enumerate(job.get("steps", []))
        if RODA_A_SUITE in str(p.get("run", ""))
    ]


def _com_falha(passo: dict[str, Any]) -> bool:
    return str(passo.get("if", "")).replace(" ", "") == "failure()"


def faltas_do_job(nome: str, job: dict[str, Any]) -> list[str]:
    """O que falta, no job, para o vermelho da suíte trazer a pilha."""
    faltas: list[str] = []
    passos = job.get("steps", [])
    donos = _passos_que_rodam_a_suite(job)
    if not donos:
        return faltas
    for i in donos:
        saida = str((passos[i].get("env") or {}).get("SAIDA", ""))
        if not saida.startswith("/"):
            faltas.append(f"{nome}: o passo da suíte não fixa o SAIDA (caminho absoluto no env)")
            continue
        depois = passos[i + 1:]
        imprime = [
            p for p in depois
            if _com_falha(p) and "FAILURES" in str(p.get("run", ""))
            and saida in str(p.get("run", ""))
        ]
        if not imprime:
            faltas.append(
                f"{nome}: nenhum passo posterior, com `if: failure()`, imprime as "
                f"FAILURES dos logs de {saida}"
            )
        sobe = [
            p for p in depois
            if _com_falha(p) and str(p.get("uses", "")).startswith("actions/upload-artifact")
            and str((p.get("with") or {}).get("path", "")).startswith(saida)
        ]
        if not sobe:
            faltas.append(
                f"{nome}: nenhum passo posterior, com `if: failure()`, sobe {saida} "
                f"com actions/upload-artifact"
            )
    return faltas


def test_existe_job_que_roda_a_suite_inteira() -> None:
    """Sem job a medir, a régua passaria calada."""
    assert [n for n, j in _jobs().items() if _passos_que_rodam_a_suite(j)], (
        f"nenhum job do ci.yml roda {RODA_A_SUITE}"
    )


def test_todo_job_da_suite_fixa_imprime_e_sobe_a_saida() -> None:
    faltas: list[str] = []
    for nome, job in _jobs().items():
        faltas += faltas_do_job(nome, job)
    assert not faltas, "\n".join(faltas)


def test_o_script_ainda_grava_o_log_que_o_ci_le() -> None:
    """Se a parte mudar de nome, o passo do CI leria uma pasta vazia, calado."""
    texto = SCRIPT.read_text(encoding="utf-8")
    assert '"$SAIDA/parte-$n.log"' in texto, (
        "o rodar-a-suite.sh não grava mais em \"$SAIDA/parte-$n.log\""
    )
    assert "SAIDA=\"${SAIDA:-" in texto, "o SAIDA deixou de poder ser fixado pelo ambiente"


def _passo_que_imprime() -> dict[str, Any]:
    for job in _jobs().values():
        for p in job.get("steps", []):
            if _com_falha(p) and "FAILURES" in str(p.get("run", "")):
                passo: dict[str, Any] = p
                return passo
    pytest.fail("nenhum passo `if: failure()` imprime as FAILURES")


def test_o_passo_imprime_so_a_parte_vermelha(tmp_path: Path) -> None:
    """Num SAIDA de brinquedo, a parte vermelha sai com o assert e a verde não."""
    passo = _passo_que_imprime()
    saida = next(
        str((p.get("env") or {}).get("SAIDA"))
        for j in _jobs().values() for p in j.get("steps", [])
        if RODA_A_SUITE in str(p.get("run", ""))
    )
    (tmp_path / "parte-01.log").write_text(
        "......F\n"
        "=================================== FAILURES ===================================\n"
        "_ test_o_pacote_leva_a_familia_ao_endereco_do_card _\n"
        "    assert familia == 'xbox'\n"
        "E   AssertionError: assert '' == 'xbox'\n"
        "=========================== short test summary info ============================\n"
        "FAILED tests/unit/test_x.py::test_o_pacote_leva_a_familia_ao_endereco_do_card\n"
        "1 failed, 5 passed in 1.23s\n",
        encoding="utf-8",
    )
    (tmp_path / "parte-02.log").write_text("........\n8 passed in 1.00s\n", encoding="utf-8")
    script = str(passo["run"]).replace(saida, str(tmp_path))
    r = subprocess.run(
        ["bash", "-e", "-c", script], capture_output=True, text=True, check=False, timeout=60
    )
    assert r.returncode == 0, r.stderr
    assert "E   AssertionError: assert '' == 'xbox'" in r.stdout
    assert "assert familia == 'xbox'" in r.stdout
    assert "parte-01.log" in r.stdout
    assert "parte-02.log" not in r.stdout


def _job_de_brinquedo(**mudancas: Any) -> dict[str, Any]:
    job = {
        "steps": [
            {"run": "bash scripts/rodar-a-suite.sh", "env": {"SAIDA": "/tmp/suite-ci"}},
            {"if": "failure()", "run": "sed -n '/FAILURES/,/x/p' /tmp/suite-ci/parte-01.log"},
            {
                "if": "failure()",
                "uses": "actions/upload-artifact@v4",
                "with": {"path": "/tmp/suite-ci/*.log"},
            },
        ]
    }
    job.update(mudancas)
    return job


def test_a_regua_morde_em_cada_falta() -> None:
    """Cada uma das três curas, arrancada, reprova; o brinquedo inteiro passa."""
    assert faltas_do_job("j", _job_de_brinquedo()) == []

    sem_saida = _job_de_brinquedo()
    del sem_saida["steps"][0]["env"]
    assert any("SAIDA" in f for f in faltas_do_job("j", sem_saida))

    sem_impressao = _job_de_brinquedo()
    del sem_impressao["steps"][1]
    assert any("FAILURES" in f for f in faltas_do_job("j", sem_impressao))

    sem_artefato = _job_de_brinquedo()
    del sem_artefato["steps"][2]
    assert any("upload-artifact" in f for f in faltas_do_job("j", sem_artefato))

    sem_condicao = _job_de_brinquedo()
    del sem_condicao["steps"][2]["if"]
    assert any("upload-artifact" in f for f in faltas_do_job("j", sem_condicao))
