"""Os intermitentes do CI: o teste vermelho numa perna e verde noutra da corrida entra na tabela."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _carregar(rel: str, nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, RAIZ / rel)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


INT = _carregar("scripts/ci/intermitentes.py", "_os_intermitentes_do_ci")

OSCILA = "tests/unit/test_a.py::test_oscila"
FIRME = "tests/unit/test_b.py::test_quebrado"
PASSOS_LINT = {"Pytest unit": "failure", "Pytest core": "skipped"}
PASSOS_VERDES = {"Pytest unit": "success", "Pytest core": "success"}


def _job(nome: str, conclusao: str, ident: int,
         passos: dict[str, str] | None = None) -> dict[str, Any]:
    quais = passos or (PASSOS_VERDES if conclusao == "success" else PASSOS_LINT)
    return {"name": nome, "conclusion": conclusao, "databaseId": ident,
            "steps": [{"name": n, "conclusion": c} for n, c in quais.items()]}


def _log(*vermelhos: str) -> str:
    return "".join(f"2026-11-01T10:00:00.000Z FAILED {t}\n" for t in vermelhos)


def _corrida(ident: str, sha: str, conclusao: str, jobs: list[dict[str, Any]],
             logs: dict[int, str], data: str = "2026-11-01") -> Any:
    c = INT.Corrida(ident, sha, "dev", data, conclusao)
    c.pernas = INT.pernas_da_corrida(jobs, logs.get)
    return c


def _tres_pythons(vermelho_em: dict[str, tuple[str, ...]]) -> Any:
    """Uma corrida com as três pernas do lint-test; ``vermelho_em`` diz os vermelhos de cada."""
    jobs, logs = [], {}
    for i, py in enumerate(("3.10", "3.11", "3.12")):
        testes = vermelho_em.get(py, ())
        jobs.append(_job(f"lint-test ({py})", "failure" if testes else "success", i))
        if testes:
            logs[i] = _log(*testes)
    return _corrida("100", "aaaa", "failure", jobs, logs)


def test_o_teste_vermelho_so_numa_perna_entra_e_o_vermelho_em_todas_nao() -> None:
    corrida = _tres_pythons({"3.10": (OSCILA, FIRME), "3.11": (FIRME,), "3.12": (FIRME,)})
    linhas = INT.cruzar([corrida])
    assert [ln.funcao for ln in linhas] == [OSCILA], "só o que passou em outra perna oscila"
    assert linhas[0].oscilou == [("100", "2026-11-01")]


def test_mordida_sem_o_cruzamento_o_vermelho_em_todas_entra_na_tabela(
        monkeypatch: pytest.MonkeyPatch) -> None:
    corrida = _tres_pythons({"3.10": (OSCILA, FIRME), "3.11": (FIRME,), "3.12": (FIRME,)})
    assert [ln.funcao for ln in INT.cruzar([corrida])] == [OSCILA]
    monkeypatch.setattr(INT, "oscila", lambda _pernas, _teste: True)
    assert {ln.funcao for ln in INT.cruzar([corrida])} == {OSCILA, FIRME}, (
        "a mordida não mordeu: sem o cruzamento o vermelho nas três entra")


def test_os_parametros_se_juntam_na_funcao_e_a_corrida_conta_uma_vez() -> None:
    corrida = _tres_pythons({"3.10": (OSCILA + "[a]", OSCILA + "[b]")})
    linhas = INT.cruzar([corrida])
    assert [ln.funcao for ln in linhas] == [OSCILA] and len(linhas[0].oscilou) == 1


def test_a_perna_vermelha_sem_log_ou_sem_o_passo_da_suite_nao_prova_o_verde() -> None:
    jobs = [_job("lint-test (3.10)", "failure", 0), _job("lint-test (3.11)", "failure", 1)]
    sem_log = _corrida("1", "a", "failure", jobs, {0: _log(OSCILA)})
    assert INT.cruzar([sem_log]) == [], "a perna sem log pode ter reprovado o mesmo teste"
    parou_antes = {"Pytest unit": "skipped", "Pytest core": "skipped"}
    jobs = [_job("lint-test (3.10)", "failure", 0),
            _job("lint-test (3.11)", "failure", 1, parou_antes)]
    cedo = _corrida("2", "a", "failure", jobs, {0: _log(OSCILA), 1: _log()})
    assert INT.cruzar([cedo]) == [], "a perna que parou antes da suíte não rodou o teste"


def test_a_perna_vermelha_com_log_sem_o_teste_prova_o_verde() -> None:
    jobs = [_job("lint-test (3.10)", "failure", 0), _job("lint-test (3.11)", "failure", 1)]
    corrida = _corrida("1", "a", "failure", jobs, {0: _log(OSCILA), 1: _log(FIRME)})
    assert {ln.funcao for ln in INT.cruzar([corrida])} == {OSCILA, FIRME}


def test_a_faixa_decide_quem_prova_o_verde_de_quem() -> None:
    estreita, larga = "lint-test (py3.12), partes 00-03", "Interface com GTK REAL (x), partes 00-05"
    jobs = [_job(estreita, "failure", 0), _job(larga, "success", 1)]
    corrida = _corrida("1", "a", "failure", jobs, {0: _log(OSCILA)})
    assert [ln.funcao for ln in INT.cruzar([corrida])] == [OSCILA]
    jobs = [_job(estreita, "success", 0), _job(larga, "failure", 1)]
    assert INT.cruzar([_corrida("2", "a", "failure", jobs, {1: _log(OSCILA)})]) == [], (
        "o teste da faixa larga pode estar nas partes 04-05, que a estreita não roda")


def test_a_perna_do_lote_sem_numero_nao_prova_o_verde_das_faixas() -> None:
    faixa = "Interface com GTK REAL (ubuntu-24.04), partes 04-07"
    lote = "Interface com GTK REAL (ubuntu-26.04), partes janela-e-bandeja"
    passos_do_lote = {"A suíte inteira sob Xvfb, com o GTK real": "success"}
    jobs = [_job(faixa, "failure", 0), _job(lote, "success", 1, passos_do_lote)]
    assert INT.cruzar([_corrida("1", "a", "failure", jobs, {0: _log(OSCILA)})]) == [], (
        "o lote janela-e-bandeja roda poucos arquivos e não prova o verde de um teste da faixa")
    jobs = [_job(lote, "failure", 0, {"A suíte inteira sob Xvfb, com o GTK real": "failure"}),
            _job("lint-test (py3.12), partes 00-03", "success", 1),
            _job("lint-test (3.10)", "success", 2)]
    linhas = INT.cruzar([_corrida("2", "a", "failure", jobs, {0: _log(OSCILA)})])
    assert [ln.funcao for ln in linhas] == [OSCILA], "só a perna das 24 partes cobre o lote"
    assert INT.faixa_do_job(lote) is None and INT.faixa_do_job("lint-test (3.10)") == (0, 23)


def test_a_perna_que_morreu_sem_sumario_nao_prova_o_verde() -> None:
    jobs = [_job("lint-test (3.10)", "failure", 0), _job("lint-test (3.11)", "failure", 1)]
    morreu = "  parte-03 (90 arq): SEM SUMÁRIO — o processo morreu no meio\n"
    corrida = _corrida("1", "a", "failure", jobs, {0: _log(OSCILA), 1: morreu})
    assert INT.cruzar([corrida]) == [], "o processo morto no meio pode não ter chegado ao teste"
    passou = morreu + f"2026-11-01T10:00:00.000Z {OSCILA} PASSED [ 1%]\n"
    corrida = _corrida("2", "a", "failure", jobs, {0: _log(OSCILA), 1: passou})
    assert [ln.funcao for ln in INT.cruzar([corrida])] == [OSCILA], "o PASSED escrito prova"


def test_a_chave_da_lista_casa_o_arquivo_ou_a_funcao_inteira() -> None:
    assert INT.chave_casa("test_a.py", OSCILA)
    assert INT.chave_casa("test_a.py::test_oscila", OSCILA)
    assert not INT.chave_casa("a.py", OSCILA), "a chave é o nome inteiro do arquivo"
    assert not INT.chave_casa("test_a.py::test_osc", OSCILA), "a chave é o nome inteiro da função"
    linhas = [INT.Linha("tests/unit/test_a.py::test_oscila_mais"),
              INT.Linha("tests/unit/test_xa.py::test_y")]
    INT.aplicar_razoes(linhas, {"test_a.py::test_oscila": "razão de outra função",
                                "a.py": "outro arquivo"})
    assert [ln.razao for ln in linhas] == [INT.SEM_RAZAO, INT.SEM_RAZAO], (
        "a razão de outro teste não cala a linha no --exigir-razao")


def test_os_testes_do_core_pedem_o_passo_do_core() -> None:
    jobs = [_job("lint-test (3.10)", "failure", 0),
            _job("lint-test (3.11)", "failure", 1, PASSOS_LINT)]
    nucleo = "tests/core/test_n.py::test_n"
    corrida = _corrida("1", "a", "failure", jobs, {0: _log(nucleo, OSCILA), 1: _log(OSCILA)})
    assert [ln.funcao for ln in INT.cruzar([corrida])] == []


def test_a_ordem_poe_primeiro_o_que_oscilou_com_o_mesmo_sha_verde() -> None:
    a = _tres_pythons({"3.10": (OSCILA,)})
    a.sha, a.id = "s1", "1"
    b = _tres_pythons({"3.10": (FIRME,)})
    b.sha, b.id = "s2", "2"
    verde = INT.Corrida("3", "s2", "dev", "2026-11-02", "success")
    linhas = INT.cruzar([a, b, verde])
    assert [(ln.funcao, ln.mesmo_sha_verde) for ln in linhas] == [(FIRME, 1), (OSCILA, 0)]


def test_os_shas_com_verde_e_vermelho_saem_do_mais_novo_ao_mais_velho() -> None:
    corridas = [
        INT.Corrida("1", "velho", "dev", "2026-10-01", "failure"),
        INT.Corrida("2", "velho", "dev", "2026-10-01", "success"),
        INT.Corrida("3", "novo", "dev", "2026-11-01", "success"),
        INT.Corrida("4", "novo", "main", "2026-11-02", "failure"),
        INT.Corrida("5", "so-verde", "dev", "2026-11-03", "success"),
        INT.Corrida("6", "cancelado", "dev", "2026-11-03", "cancelled"),
        INT.Corrida("7", "cancelado", "dev", "2026-11-03", "success"),
    ]
    esperado = [("novo", ["3"], ["4"]), ("velho", ["2"], ["1"])]
    assert INT.shas_com_verde_e_vermelho(corridas) == esperado


def test_a_lista_conhecida_da_a_razao_e_a_linha_sem_razao_se_acusa(tmp_path: Path) -> None:
    lista = tmp_path / "lista.md"
    lista.write_text(
        "| teste | medida | sprint ou razão |\n| --- | --- | --- |\n"
        f"| `{OSCILA}` | 3 de 9 | O-TESTE-ESPERA-O-EVENTO-01 |\n| texto solto | 1 | nada |\n",
        encoding="utf-8")
    linhas = INT.cruzar([_tres_pythons({"3.10": (OSCILA, FIRME), "3.11": (), "3.12": ()})])
    INT.aplicar_razoes(linhas, INT.razoes_da_lista(lista))
    assert {ln.funcao: ln.razao for ln in linhas} == {
        OSCILA: "O-TESTE-ESPERA-O-EVENTO-01", FIRME: INT.SEM_RAZAO}


def _pasta_de_mentira(tmp_path: Path) -> Path:
    pasta = tmp_path / "casa"
    (pasta / "jobs").mkdir(parents=True)
    (pasta / "logs").mkdir()
    runs = [
        {"databaseId": 100, "conclusion": "failure", "createdAt": "2026-11-01T10:00:00Z",
         "headSha": "aaaaaaaaaa", "headBranch": "dev"},
        {"databaseId": 101, "conclusion": "success", "createdAt": "2026-11-01T11:00:00Z",
         "headSha": "aaaaaaaaaa", "headBranch": "dev"},
        {"databaseId": 102, "conclusion": "success", "createdAt": "2025-01-01T11:00:00Z",
         "headSha": "fora", "headBranch": "dev"},
    ]
    (pasta / "corridas.json").write_text(json.dumps(runs), encoding="utf-8")
    jobs = [_job("lint-test (3.10)", "failure", 7), _job("lint-test (3.11)", "success", 8)]
    (pasta / "jobs" / "100.json").write_text(json.dumps({"jobs": jobs}), encoding="utf-8")
    (pasta / "logs" / "job-7.log").write_text(_log(OSCILA), encoding="utf-8")
    return pasta


def test_a_pasta_baixada_vira_a_tabela_sem_chamar_o_gh(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    def _proibido(*_args: str) -> str:
        raise AssertionError("o --sem-gh chamou o gh")

    monkeypatch.setattr(INT, "_gh", _proibido)
    pasta = _pasta_de_mentira(tmp_path)
    rc = INT.main(["--desde", "2026-10-01", "--ate", "2026-11-30", "--pasta", str(pasta),
                   "--sem-gh"])
    saida = capsys.readouterr().out
    assert rc == 0
    assert "2 corrida(s) lidas" in saida and f"`{OSCILA}` | 1 | 1 | 0 | 2026-11-01" in saida, saida
    assert "| aaaaaaaaa | 101 | 100 |" in saida, saida


def test_exigir_a_razao_reprova_a_linha_sem_sprint_nem_razao(
        tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pasta = _pasta_de_mentira(tmp_path)
    base = ["--desde", "2026-10-01", "--ate", "2026-11-30", "--pasta", str(pasta), "--sem-gh"]
    vazia = tmp_path / "vazia.md"
    vazia.write_text("sem tabela\n", encoding="utf-8")
    assert INT.main([*base, "--razoes", str(vazia), "--exigir-razao"]) == 1
    assert INT.SEM_RAZAO in capsys.readouterr().out
    lista = tmp_path / "lista.md"
    lista.write_text(f"| `{OSCILA}` | 1 de 2 | O-TESTE-ESPERA-O-EVENTO-01 |\n", encoding="utf-8")
    assert INT.main([*base, "--razoes", str(lista), "--exigir-razao"]) == 0


def test_o_periodo_sem_corrida_recusa(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pasta = _pasta_de_mentira(tmp_path)
    rc = INT.main(["--desde", "2020-01-01", "--ate", "2020-01-02", "--pasta", str(pasta),
                   "--sem-gh"])
    assert rc == 2 and "RECUSADO" in capsys.readouterr().err
