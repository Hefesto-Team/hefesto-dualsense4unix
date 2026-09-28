"""Sem o GTK real, o teste que precisa dele pula com o motivo; com a exigência, reprova.

A regra mora em `tests/conftest.py` (`pytest_runtest_makereport`). As réguas
rodam um pytest filho sobre um teste de uma linha que importa o `gi`, com o
`gi` bloqueado como no `lint-test` do CI.

Mordidas: tire o hook e o primeiro caso reprova em vez de pular; tire a guarda
do `EXIGE_GTK_REAL` e o segundo caso pula em vez de reprovar; tire a guarda do
`_falta_o_gtk` e o terceiro caso (um erro que não é do GTK) pula calado.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

_BLOQUEIO = '''
import sys
class _SemGtk:
    def find_spec(self, nome, caminho=None, alvo=None):
        if nome.split(".")[0] in ("gi", "cairo"):
            raise ModuleNotFoundError(f"No module named {nome!r}", name=nome)
        return None
sys.meta_path.insert(0, _SemGtk())
'''

_PRECISA_DO_GTK = '''
def test_precisa_do_gtk():
    import gi  # noqa: F401
'''

_OUTRO_ERRO = '''
def test_um_erro_que_nao_e_do_gtk():
    import modulo_que_nao_existe_em_lugar_nenhum  # noqa: F401
'''


def _rodar(tmp_path: Path, corpo: str, *, exige: bool) -> str:
    bloqueio = tmp_path / "bloqueio"
    bloqueio.mkdir()
    (bloqueio / "sitecustomize.py").write_text(_BLOQUEIO, encoding="utf-8")
    alvo = tmp_path / "test_alvo.py"
    alvo.write_text(corpo, encoding="utf-8")
    ambiente = dict(os.environ)
    ambiente["PYTHONPATH"] = os.pathsep.join([str(bloqueio), str(RAIZ / "src")])
    ambiente.pop("HEFESTO_EXIGE_GTK_REAL", None)
    if exige:
        ambiente["HEFESTO_EXIGE_GTK_REAL"] = "1"
    ambiente["PYTHONPATH"] += os.pathsep + str(RAIZ)
    # O alvo mora fora da árvore (a suíte paralela não o coleta), então o
    # conftest da casa entra como plugin.
    r = subprocess.run(
        [
            sys.executable, "-m", "pytest", str(alvo), "-q", "-rs",
            "-p", "no:cacheprovider", "-p", "tests.conftest",
        ],
        capture_output=True,
        text=True,
        cwd=RAIZ,
        env=ambiente,
        timeout=180,
    )
    return r.stdout + r.stderr


@pytest.mark.parametrize("exige", [False, True], ids=["sem-exigencia", "com-exigencia"])
def test_a_falta_do_gtk_pula_so_quando_ninguem_a_exige(tmp_path: Path, exige: bool) -> None:
    saida = _rodar(tmp_path, _PRECISA_DO_GTK, exige=exige)
    if exige:
        assert "1 failed" in saida, (
            "com HEFESTO_EXIGE_GTK_REAL=1 a falta do GTK tem de reprovar: é o job "
            f"com o GTK real, e lá o pulo esconde defeito de ambiente.\n{saida[-800:]}"
        )
    else:
        assert "1 skipped" in saida and "GUARDA-GI-REAL-01" in saida, (
            "sem o GTK real, o teste que precisa dele pula com o motivo: foi o "
            f"lint-test de 27/09 com dois mil vermelhos.\n{saida[-800:]}"
        )


def test_o_erro_que_nao_e_do_gtk_continua_reprovando(tmp_path: Path) -> None:
    saida = _rodar(tmp_path, _OUTRO_ERRO, exige=False)
    assert "1 failed" in saida, (
        f"só a falta do GTK vira pulo; qualquer outro import quebrado reprova.\n{saida[-800:]}"
    )


# ---------------------------------------------------------------------------
# O FILHO QUE MORRE PELA FALTA DO GTK (27/09/2026)
# ---------------------------------------------------------------------------
#: O gerador de uma aba, o `aba05.py` sem o glade e o visor rodam num processo
#: filho. O neto herda o bloqueio pelo `PYTHONPATH`, como o python do runner.
_FILHO_PRECISA_DO_GTK = '''
import subprocess
import sys

from tests.conftest import repassar_a_falta_do_gtk


def test_o_filho_precisa_do_gtk():
    filho = subprocess.run(
        [sys.executable, "-c", "import gi"], capture_output=True, text=True, check=False)
    repassar_a_falta_do_gtk(filho)
    assert filho.returncode == 0, filho.stderr
'''

_FILHO_COM_OUTRO_ERRO = '''
import subprocess
import sys

from tests.conftest import repassar_a_falta_do_gtk


def test_o_filho_morre_por_outro_motivo():
    filho = subprocess.run(
        [sys.executable, "-c", "import modulo_que_nao_existe_em_lugar_nenhum"],
        capture_output=True, text=True, check=False)
    repassar_a_falta_do_gtk(filho)
    assert filho.returncode == 0, filho.stderr
'''


@pytest.mark.parametrize("exige", [False, True], ids=["sem-exigencia", "com-exigencia"])
def test_o_filho_sem_o_gtk_pula_so_quando_ninguem_o_exige(tmp_path: Path, exige: bool) -> None:
    """A falta do GTK no processo FILHO segue a mesma regra da falta no pai.

    A mordida: faça `repassar_a_falta_do_gtk` voltar sem levantar e o caso
    sem exigência reprova — é o `lint-test` de 27/09 com os dez geradores, o
    `aba05.py` e o visor vermelhos por ambiente.
    """
    saida = _rodar(tmp_path, _FILHO_PRECISA_DO_GTK, exige=exige)
    if exige:
        assert "1 failed" in saida and "no processo filho" in saida, (
            "com HEFESTO_EXIGE_GTK_REAL=1 o filho sem o GTK tem de reprovar, e "
            f"dizendo que a falta foi no filho.\n{saida[-800:]}"
        )
    else:
        assert "1 skipped" in saida and "GUARDA-GI-REAL-01" in saida, (
            "sem o GTK real, a régua cujo processo filho morreu pela falta dele "
            f"pula com o motivo, como a do processo da suíte.\n{saida[-800:]}"
        )


def test_o_filho_que_morre_por_outro_motivo_continua_reprovando(tmp_path: Path) -> None:
    """Só a falta do GTK no filho vira pulo; o resto chega à asserção da régua.

    A mordida: faça o repasse dar ao `ModuleNotFoundError` o nome `"gi"` em
    vez do módulo que o filho não achou, e este caso pula calado.
    """
    saida = _rodar(tmp_path, _FILHO_COM_OUTRO_ERRO, exige=False)
    assert "1 failed" in saida and "modulo_que_nao_existe_em_lugar_nenhum" in saida, (
        "o filho que morre por outro import tem de reprovar a régua, com o "
        f"stderr dele na cara.\n{saida[-800:]}"
    )
