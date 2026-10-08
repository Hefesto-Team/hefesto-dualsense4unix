"""O resumo da suíte lê só os logs que ESTA execução escreveu (O-VERMELHO-DA-SUITE-01).

No fecho da 1.6.5 a suíte listou 6 vermelhos quando a corrida tinha 1: o `falhas.txt` vinha de
`grep … "$SAIDA"/parte-*.log`, que lê todo log do diretório, inclusive o de outra parte (o
`fecho-suite.sh` chama `rodar-a-suite.sh <parte>` uma vez por parte, no mesmo `SAIDA`) e o de uma
corrida velha de mais partes. O laço das partes também varria o glob `parte-*`, e o
`parte-NN` velho de um `PARTES` maior voltava a rodar.

A prova é numa árvore de mentira com o script de verdade, e nada se apaga: o log velho continua
no disco, só não entra na conta.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SUITE = RAIZ / "scripts" / "rodar-a-suite.sh"

VELHO = "FAILED tests/unit/test_de_outra_corrida.py::test_velho - AssertionError\n"
ARQUIVOS = [f"test_a{i:02d}.py" for i in range(6)]


def _ambiente(**mais: str) -> dict[str, str]:
    fora = {
        "PYTEST_ADDOPTS",
        "SUITE_PYTEST_ARGS",
        "LD_PRELOAD",
        "PARTES_EM_PARALELO",
        "VEZ_DO_PYTEST",
        "PARTIDO",
        "A_SECO",
        "CSV_DOS_TEMPOS",
        "PARTES",
        "SAIDA",
    }
    env = {k: v for k, v in os.environ.items() if k not in fora and not k.startswith("COV_")}
    env.update({"PY_COLORS": "0", "PY": sys.executable, **mais})
    return env


def _arvore(raiz: Path, reprova: str | None = None) -> None:
    (raiz / "scripts").mkdir(parents=True)
    shutil.copy2(SUITE, raiz / "scripts" / "rodar-a-suite.sh")
    (raiz / "tests" / "unit").mkdir(parents=True)
    for nome in ARQUIVOS:
        corpo = "def test_passa():\n    assert True\n"
        if nome == reprova:
            corpo = "def test_cai():\n    assert False\n"
        (raiz / "tests" / "unit" / nome).write_text(corpo, encoding="utf-8")


def _rodar(raiz: Path, saida: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/rodar-a-suite.sh", *args],
        cwd=raiz,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        env=_ambiente(SAIDA=str(saida), **env),
    )


def _deixar_corrida_velha(saida: Path, de: range) -> None:
    """O que uma corrida anterior (de mais partes, ou de outra parte) deixou no SAIDA."""
    saida.mkdir(parents=True)
    for k in de:
        (saida / f"parte-{k:02d}").write_text("tests/unit/test_a00.py\n", encoding="utf-8")
        (saida / f"parte-{k:02d}.log").write_text(VELHO, encoding="utf-8")
        (saida / f"parte-{k:02d}-test_de_webkit.log").write_text(VELHO, encoding="utf-8")


def _linha(feito: subprocess.CompletedProcess[str], inicio: str) -> str:
    return next(x for x in feito.stdout.splitlines() if x.startswith(inicio))


def test_uma_parte_so_nao_traz_o_vermelho_do_log_de_outra_parte(tmp_path: Path) -> None:
    raiz, saida = tmp_path / "arvore", tmp_path / "saida"
    _arvore(raiz)
    _deixar_corrida_velha(saida, range(3, 4))
    feito = _rodar(raiz, saida, "01", PARTES="6")
    assert feito.returncode == 0, feito.stdout
    assert "testes vermelhos: 0" in feito.stdout, feito.stdout
    assert (saida / "falhas.txt").read_text(encoding="utf-8") == ""
    # nada se apaga: o log da outra corrida continua onde estava, para quem tria
    assert (saida / "parte-03.log").read_text(encoding="utf-8") == VELHO
    assert (saida / "parte-03-test_de_webkit.log").read_text(encoding="utf-8") == VELHO


def test_a_corrida_de_menos_partes_nao_conta_os_logs_nem_roda_as_partes_da_de_mais(
    tmp_path: Path,
) -> None:
    raiz, saida = tmp_path / "arvore", tmp_path / "saida"
    _arvore(raiz)
    _deixar_corrida_velha(saida, range(4, 8))
    feito = _rodar(raiz, saida, PARTES="4")
    assert feito.returncode == 0, feito.stdout
    assert "partes verdes: 4 · partes com vermelho: 0 · testes vermelhos: 0" in feito.stdout, (
        feito.stdout
    )
    for k in range(4, 8):
        assert f"parte-{k:02d} (" not in feito.stdout, feito.stdout
        assert (saida / f"parte-{k:02d}.log").read_text(encoding="utf-8") == VELHO


def test_o_vermelho_desta_corrida_continua_na_lista_e_so_ele(tmp_path: Path) -> None:
    raiz, saida = tmp_path / "arvore", tmp_path / "saida"
    _arvore(raiz, reprova="test_a02.py")
    _deixar_corrida_velha(saida, range(5, 8))
    feito = _rodar(raiz, saida, PARTES="5")
    assert feito.returncode == 1, feito.stdout
    assert "testes vermelhos: 1" in feito.stdout, feito.stdout
    falhas = (saida / "falhas.txt").read_text(encoding="utf-8").split("\n")
    assert [x for x in falhas if x] == ["FAILED tests/unit/test_a02.py::test_cai"]
    assert "test_de_outra_corrida" not in feito.stdout


def test_com_a_chave_ligada_o_resumo_tambem_le_so_a_corrida_dele(tmp_path: Path) -> None:
    raiz, saida = tmp_path / "arvore", tmp_path / "saida"
    _arvore(raiz, reprova="test_a04.py")
    _deixar_corrida_velha(saida, range(4, 8))
    feito = _rodar(
        raiz, saida, PARTES="4", PARTES_EM_PARALELO="2", VEZ_DO_PYTEST="nenhum"
    )
    assert feito.returncode == 1, feito.stdout
    assert "testes vermelhos: 1" in feito.stdout, feito.stdout
    falhas = (saida / "falhas.txt").read_text(encoding="utf-8").split("\n")
    assert [x for x in falhas if x] == ["FAILED tests/unit/test_a04.py::test_cai"]
    assert "test_de_outra_corrida" not in feito.stdout
    assert (saida / "parte-05.log").read_text(encoding="utf-8") == VELHO


def test_pedir_uma_parte_que_a_divisao_nao_tem_e_erro_e_nao_verde(tmp_path: Path) -> None:
    raiz, saida = tmp_path / "arvore", tmp_path / "saida"
    _arvore(raiz)
    _deixar_corrida_velha(saida, range(5, 6))
    feito = _rodar(raiz, saida, "05", PARTES="3")
    assert feito.returncode != 0, feito.stdout
    assert "05" in feito.stdout, feito.stdout
