"""O CI roda a suíte em partes, e as pernas juntas cobrem as 24 sem furo e sem repetição.

O run 39619656976 (21/10/2026) fechou `failure` nos dois jobs que rodam a suíte, pelo mesmo
defeito de forma: um processo só para trabalho demais. Os três `lint-test` rodavam
`pytest tests/unit` num processo e morreram calados aos 36%, sem sumário; o `gtk-real` rodava as
24 partes em série e estourou o prazo de 95 minutos na parte 19.

A cura é do desenho do YAML, e esta régua o confere:
1. o passo da suíte do `lint-test` é o `scripts/rodar-a-suite.sh` (nenhum job roda `tests/unit`
   inteiro num processo só);
2. as faixas do `gtk-real` cobrem as partes de 00 à última, sem furo e sem repetição;
3. cada perna escreve a cobertura e os logs num nome que só ela tem (dois nomes iguais num
   `upload-artifact` reprovam a segunda perna);
4. a cobertura de cada faixa é SOMADA antes de o piso cobrar (o piso de 70 é da suíte inteira).
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
SCRIPT = RAIZ / "scripts" / "rodar-a-suite.sh"

UM_PROCESSO_SO = re.compile(r"pytest\s+tests/unit(?![/\w])")


def _jobs() -> dict[str, Any]:
    jobs: dict[str, Any] = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]
    return jobs


def _partes_do_script() -> int:
    achado = re.search(r'^PARTES="\$\{PARTES:-(\d+)\}"', SCRIPT.read_text(encoding="utf-8"), re.M)
    assert achado, "o rodar-a-suite.sh não declara mais o PARTES padrão: a régua leu o lugar errado"
    return int(achado.group(1))


def _passo_da_suite(job: dict[str, Any]) -> dict[str, Any]:
    achados = [
        p for p in job.get("steps", []) if "scripts/rodar-a-suite.sh" in str(p.get("run", ""))
    ]
    assert len(achados) == 1, f"esperava um passo que roda a suíte, achei {len(achados)}"
    passo: dict[str, Any] = achados[0]
    return passo


def _faixas(job: dict[str, Any]) -> list[tuple[int, int]]:
    faixas = []
    for texto in job["strategy"]["matrix"]["faixa"]:
        achado = re.fullmatch(r"(\d\d)-(\d\d)", str(texto))
        assert achado, f"faixa «{texto}» não tem a forma NN-NN"
        faixas.append((int(achado[1]), int(achado[2])))
    return faixas


def faltas_das_faixas(job: dict[str, Any], partes: int) -> list[str]:
    """O que falta para as pernas do `gtk-real` cobrirem as partes. Função pura."""
    faltas: list[str] = []
    try:
        faixas = _faixas(job)
    except (KeyError, AssertionError) as erro:
        return [f"gtk-real: a matriz de faixas sumiu ou mudou de forma ({erro})"]
    dadas: list[int] = []
    for ini, fim in faixas:
        if ini > fim:
            faltas.append(f"a faixa {ini:02d}-{fim:02d} começa depois de acabar")
        dadas.extend(range(ini, fim + 1))
    repetidas = sorted({k for k in dadas if dadas.count(k) > 1})
    sem_dono = sorted(set(range(partes)) - set(dadas))
    de_fora = sorted(set(dadas) - set(range(partes)))
    if repetidas:
        faltas.append(f"partes em mais de uma faixa: {repetidas}")
    if sem_dono:
        faltas.append(f"partes que nenhuma faixa roda: {sem_dono}")
    if de_fora:
        faltas.append(f"faixa com parte que a suíte não tem (são {partes}): {de_fora}")
    return faltas


def faltas_do_gtk_real(jobs: dict[str, Any], partes: int) -> list[str]:
    """Faixas, nomes por perna e o passo que roda parte a parte."""
    job = jobs.get("gtk-real")
    if job is None:
        return ["gtk-real: o job sumiu"]
    faltas = faltas_das_faixas(job, partes)
    passo = _passo_da_suite(job)
    corpo = str(passo.get("run", ""))
    if "FAIXA" not in corpo or 'rodar-a-suite.sh "$' not in corpo:
        faltas.append(
            "gtk-real: o passo não chama o rodar-a-suite.sh com UMA parte por volta; "
            "sem o número ele roda a suíte inteira em cada perna"
        )
    if "matrix.faixa" not in str((passo.get("env") or {}).get("COVERAGE_FILE", "")):
        faltas.append("gtk-real: o COVERAGE_FILE não leva a faixa; as pernas pisam no arquivo")
    nomes = [
        str((p.get("with") or {}).get("name", ""))
        for p in job.get("steps", [])
        if str(p.get("uses", "")).startswith("actions/upload-artifact")
    ]
    if not nomes:
        faltas.append("gtk-real: nenhum upload-artifact (nem os logs, nem a cobertura)")
    faltas += [
        f"gtk-real: o artefato «{n}» não leva a faixa; a segunda perna reprova no upload"
        for n in nomes
        if "matrix.faixa" not in n
    ]
    if not any(n.startswith("cobertura-") for n in nomes):
        faltas.append("gtk-real: nenhuma perna sobe os dados de cobertura (cobertura-<faixa>)")
    return faltas


def faltas_da_cobertura(jobs: dict[str, Any]) -> list[str]:
    """A soma das faixas antes do piso."""
    job = jobs.get("cobertura")
    if job is None:
        return ["cobertura: o job que soma as faixas sumiu"]
    faltas: list[str] = []
    precisa = job.get("needs")
    precisa = [precisa] if isinstance(precisa, str) else list(precisa or [])
    if "gtk-real" not in precisa:
        faltas.append("cobertura: não espera o gtk-real; somaria dados que ainda não subiram")
    baixa = [
        p
        for p in job.get("steps", [])
        if str(p.get("uses", "")).startswith("actions/download-artifact")
    ]
    if not baixa or "cobertura-" not in str((baixa[0].get("with") or {}).get("pattern", "")):
        faltas.append("cobertura: não baixa os artefatos cobertura-*")
    corpo = "\n".join(str(p.get("run", "")) for p in job.get("steps", []))
    soma, piso = corpo.find("coverage combine"), corpo.find("coverage report --fail-under=70")
    if soma < 0:
        faltas.append("cobertura: não faz o `coverage combine`; o piso mediria só uma faixa")
    if piso < 0:
        faltas.append("cobertura: não cobra o piso de 70")
    if 0 <= piso < soma:
        faltas.append("cobertura: cobra o piso ANTES de somar")
    return faltas


def faltas_do_lint_test(jobs: dict[str, Any]) -> list[str]:
    """Nenhum job roda `tests/unit` inteiro num processo só; o lint-test usa o dono do comando."""
    faltas = []
    for nome, job in jobs.items():
        for p in job.get("steps", []):
            if UM_PROCESSO_SO.search(str(p.get("run", ""))):
                faltas.append(f"{nome} / {p.get('name')}: roda `tests/unit` num processo só")
    lint = jobs.get("lint-test", {})
    passos = lint.get("steps", [])
    if not any("scripts/rodar-a-suite.sh" in str(p.get("run", "")) for p in passos):
        faltas.append("lint-test: nenhum passo roda scripts/rodar-a-suite.sh")
    else:
        nome = str((_passo_da_suite(lint).get("env") or {}).get("SAIDA", ""))
        if not nome.startswith("/"):
            faltas.append("lint-test: o passo da suíte não fixa o SAIDA")
    nomes = [
        str((p.get("with") or {}).get("name", ""))
        for p in lint.get("steps", [])
        if str(p.get("uses", "")).startswith("actions/upload-artifact")
    ]
    faltas += [
        f"lint-test: o artefato «{n}» não leva o python; a segunda perna reprova no upload"
        for n in nomes
        if "matrix.python" not in n
    ]
    return faltas


def todas_as_faltas(jobs: dict[str, Any], partes: int) -> list[str]:
    return faltas_do_lint_test(jobs) + faltas_do_gtk_real(jobs, partes) + faltas_da_cobertura(jobs)


def test_o_ci_roda_a_suite_em_partes_e_as_pernas_cobrem_as_24() -> None:
    assert todas_as_faltas(_jobs(), _partes_do_script()) == []


def test_a_regua_le_as_24_partes_e_as_quatro_faixas() -> None:
    """Sem isto a régua de cima passaria sobre uma matriz que ela não leu."""
    assert _partes_do_script() == 24
    assert len(_faixas(_jobs()["gtk-real"])) == 4


# --- as mordidas: cada cura arrancada, numa cópia, tem de reprovar --------------------------------


def _copia() -> dict[str, Any]:
    return copy.deepcopy(_jobs())


def test_mordida_faixa_tirada_deixa_parte_sem_dono() -> None:
    jobs = _copia()
    jobs["gtk-real"]["strategy"]["matrix"]["faixa"].pop()
    faltas = todas_as_faltas(jobs, 24)
    assert any("nenhuma faixa roda: [18, 19, 20, 21, 22, 23]" in f for f in faltas)


def test_mordida_faixa_sobreposta_repete_parte() -> None:
    jobs = _copia()
    jobs["gtk-real"]["strategy"]["matrix"]["faixa"][1] = "05-11"
    assert any("mais de uma faixa: [5]" in f for f in todas_as_faltas(jobs, 24))


def test_mordida_faixa_alem_das_24() -> None:
    jobs = _copia()
    jobs["gtk-real"]["strategy"]["matrix"]["faixa"][3] = "18-24"
    assert any("que a suíte não tem" in f for f in todas_as_faltas(jobs, 24))


def test_mordida_a_suite_ganhar_partes_sem_a_matriz_reprova() -> None:
    assert any("nenhuma faixa roda" in f for f in todas_as_faltas(_jobs(), 30))


def test_mordida_passo_sem_o_numero_da_parte_roda_a_suite_em_cada_perna() -> None:
    jobs = _copia()
    passo = _passo_da_suite(jobs["gtk-real"])
    passo["run"] = "xvfb-run -a bash scripts/rodar-a-suite.sh"
    assert any("UMA parte por volta" in f for f in todas_as_faltas(jobs, 24))


def test_mordida_cobertura_igual_nas_pernas() -> None:
    jobs = _copia()
    _passo_da_suite(jobs["gtk-real"])["env"]["COVERAGE_FILE"] = "/tmp/cobertura/dados"
    assert any("COVERAGE_FILE" in f for f in todas_as_faltas(jobs, 24))


def test_mordida_artefato_sem_a_faixa_no_nome() -> None:
    jobs = _copia()
    for p in jobs["gtk-real"]["steps"]:
        if str(p.get("uses", "")).startswith("actions/upload-artifact"):
            p["with"]["name"] = "suite-gtk-real"
    assert any("não leva a faixa" in f for f in todas_as_faltas(jobs, 24))


def test_mordida_artefato_do_lint_test_sem_o_python_no_nome() -> None:
    jobs = _copia()
    for p in jobs["lint-test"]["steps"]:
        if str(p.get("uses", "")).startswith("actions/upload-artifact"):
            p["with"]["name"] = "suite-lint-test"
    assert any("não leva o python" in f for f in todas_as_faltas(jobs, 24))


def test_mordida_job_sem_a_soma_da_cobertura() -> None:
    jobs = _copia()
    del jobs["cobertura"]
    assert any("job que soma as faixas sumiu" in f for f in todas_as_faltas(jobs, 24))


@pytest.mark.parametrize(
    ("de", "para", "esperado"),
    [
        ("coverage combine", "coverage erase", "não faz o `coverage combine`"),
        ("coverage report --fail-under=70", "coverage report", "não cobra o piso de 70"),
    ],
)
def test_mordida_cobertura_sem_soma_ou_sem_piso(de: str, para: str, esperado: str) -> None:
    jobs = _copia()
    for p in jobs["cobertura"]["steps"]:
        if "run" in p:
            p["run"] = str(p["run"]).replace(de, para)
    assert any(esperado in f for f in todas_as_faltas(jobs, 24))


def test_mordida_piso_antes_da_soma() -> None:
    jobs = _copia()
    for p in jobs["cobertura"]["steps"]:
        if "coverage combine" in str(p.get("run", "")):
            linhas = str(p["run"]).splitlines()
            linhas.sort(key=lambda ln: "report" not in ln)
            p["run"] = "\n".join(linhas)
    assert any("ANTES de somar" in f for f in todas_as_faltas(jobs, 24))


def test_mordida_cobertura_sem_esperar_as_faixas() -> None:
    jobs = _copia()
    del jobs["cobertura"]["needs"]
    assert any("não espera o gtk-real" in f for f in todas_as_faltas(jobs, 24))


def test_mordida_lint_test_de_volta_ao_processo_unico() -> None:
    jobs = _copia()
    passo = _passo_da_suite(jobs["lint-test"])
    passo["run"] = "pytest tests/unit -v --continue-on-collection-errors"
    achados = todas_as_faltas(jobs, 24)
    assert any("num processo só" in f for f in achados)
    assert any("nenhum passo roda scripts/rodar-a-suite.sh" in f for f in achados)
