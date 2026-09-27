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
