"""O segfault da suíte diz onde morreu (VERDE-NAO-E-PROVA-01, passo 4).

Em 26/09/2026 uma parte da suíte morreu com `rc=139` (o WebKit no lote) e
nenhum log tinha a pilha. A Python vem do `faulthandler` (o pytest o liga, e o
`tests/conftest.py` põe `PYTHONFAULTHANDLER=1` para os filhos); a nativa, de
`scripts/pilha_nativa.c`, que o `scripts/rodar-a-suite.sh` carrega em todo
pytest; e cada arquivo do WebKit roda em processo próprio. O processo que
morre de propósito se declara não despejável antes do sinal: o apport dorme.

AS MORDIDAS: tire o `PYTHONFAULTHANDLER` do conftest, e a régua do filho
reprova; troque a `saida` da `pilha_nativa.c` pelo `STDERR_FILENO`, e as duas
da pilha reprovam (a captura do pytest engole o texto); tire o `LD_PRELOAD` ou
o processo próprio do `rodar-a-suite.sh`, e a da suíte de brinquedo reprova.
"""
from __future__ import annotations

import faulthandler
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "scripts" / "pilha_nativa.c"
SUITE = RAIZ / "scripts" / "rodar-a-suite.sh"

#: O processo que morre de propósito: não despejável, sem apport.
_MORRE = (
    "import ctypes, os, signal\n"
    "ctypes.CDLL(None).prctl(4, 0, 0, 0, 0)\n"
    "os.kill(os.getpid(), signal.SIGSEGV)\n"
)


def _ambiente(**mais: str) -> dict[str, str]:
    """O ambiente do filho, sem as opções e o `LD_PRELOAD` de quem chama."""
    fora = {"PYTEST_ADDOPTS", "SUITE_PYTEST_ARGS", "LD_PRELOAD"}
    env = {k: v for k, v in os.environ.items() if k not in fora and not k.startswith("COV_")}
    env.update({"PY_COLORS": "0", **mais})
    return env


def _compilada(pasta: Path) -> Path:
    if shutil.which("cc") is None:
        pytest.skip("sem compilador C nesta máquina: a suíte sai só com a pilha Python")
    alvo = pasta / "pilha-nativa.so"
    feito = subprocess.run(
        ["cc", "-shared", "-fPIC", "-O1", "-o", str(alvo), str(FONTE), "-ldl"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert feito.returncode == 0, feito.stderr
    return alvo


def test_o_processo_da_suite_tem_o_faulthandler_ligado() -> None:
    assert faulthandler.is_enabled(), (
        "o pytest roda sem o faulthandler (alguém passou `-p no:faulthandler`?): "
        "um segfault na suíte volta a morrer sem pilha")


def test_o_python_filho_herda_o_faulthandler() -> None:
    filho = subprocess.run(
        [sys.executable, "-c", "import faulthandler; print(faulthandler.is_enabled())"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert filho.returncode == 0, filho.stderr
    assert filho.stdout.strip() == "True", (
        "o Python que a suíte dispara nasce sem o faulthandler: o conftest "
        "deixou de pôr `PYTHONFAULTHANDLER=1` no ambiente, e o próximo `rc=139` "
        "de um filho Python morre sem dizer onde")


def test_a_pilha_nativa_sai_mesmo_com_o_stderr_desviado(tmp_path: Path) -> None:
    """O pytest desvia o fd 2 durante o teste; a pilha sai no stderr de nascença."""
    biblioteca = _compilada(tmp_path)
    codigo = (
        "import os\n"
        "print('LD_PRELOAD=' + repr(os.environ.get('LD_PRELOAD')), flush=True)\n"
        "os.dup2(os.open(os.devnull, os.O_WRONLY), 2)\n" + _MORRE
    )
    filho = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, timeout=120,
        check=False, env=_ambiente(LD_PRELOAD=str(biblioteca)),
    )
    assert filho.returncode == -11, filho.stdout + filho.stderr
    assert "LD_PRELOAD=None" in filho.stdout, (
        "a biblioteca ficou no ambiente do processo: os filhos dele herdariam o "
        "tratador\n" + filho.stdout)
    assert "pilha nativa: sinal 11" in filho.stderr, filho.stderr
    assert "pilha nativa: a linha que recebeu o sinal" in filho.stderr, filho.stderr
    assert "libc.so" in filho.stderr, "a pilha saiu sem nenhum quadro:\n" + filho.stderr


def test_o_arquivo_do_webkit_morre_sozinho_e_diz_onde(tmp_path: Path) -> None:
    """A suíte de brinquedo: um arquivo comum, um do WebKit que morre, um que importa o piloto."""
    _compilada(tmp_path)
    raiz = tmp_path / "arvore"
    for pasta in ("scripts", "tests/unit", "src/pacote"):
        (raiz / pasta).mkdir(parents=True)
    shutil.copy(SUITE, raiz / "scripts" / SUITE.name)
    shutil.copy(FONTE, raiz / "scripts" / FONTE.name)
    (raiz / "src" / "pacote" / "piloto.py").write_text(
        'import gi\ngi.require_version("WebKit2", "4.1")\n', encoding="utf-8")
    (raiz / "tests" / "unit" / "test_a_comum.py").write_text(
        "def test_passa():\n    assert True\n", encoding="utf-8")
    (raiz / "tests" / "unit" / "test_b_morre.py").write_text(
        "# a régua do WebKit2 de mentira\n\n\ndef test_morre():\n"
        + "".join(f"    {linha}\n" for linha in _MORRE.splitlines()), encoding="utf-8")
    (raiz / "tests" / "unit" / "test_c_piloto.py").write_text(
        "def test_so_cita():\n    if False:\n        from pacote import piloto  # noqa: F401\n",
        encoding="utf-8")
    saida = tmp_path / "saida"

    feito = subprocess.run(
        ["bash", "scripts/rodar-a-suite.sh", "00"], cwd=raiz, capture_output=True, text=True,
        timeout=300, check=False,
        env=_ambiente(PY=sys.executable, PARTES="1", SAIDA=str(saida)),
    )
    texto = feito.stdout + feito.stderr

    assert feito.returncode == 1, texto
    linhas = {linha.strip().split(":", 1)[0]: linha for linha in feito.stdout.splitlines()}
    assert "1 passed" in linhas.get("parte-00 (3 arq)", ""), (
        "o arquivo comum não sobreviveu ao sinal do vizinho:\n" + texto)
    assert "MORREU PELO SINAL 11" in linhas.get("test_b_morre, em processo próprio", ""), texto
    assert "1 passed" in linhas.get("test_c_piloto, em processo próprio", ""), (
        "o arquivo que importa um módulo do WebKit não rodou sozinho:\n" + texto)
    log = (saida / "parte-00-test_b_morre.log").read_text(encoding="utf-8")
    assert "Fatal Python error: Segmentation fault" in log, log
    assert "pilha nativa: a linha que recebeu o sinal" in log, (
        "o log de quem morreu não tem a pilha nativa:\n" + log)
