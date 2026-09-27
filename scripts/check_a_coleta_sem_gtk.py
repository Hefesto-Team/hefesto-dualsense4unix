#!/usr/bin/env python3
"""A coleta sem GTK, em casa — o espelho do «Censo de coleta» do lint-test.

VERDE-NAO-E-PROVA-01 (27/09/2026). O CI do `dev` ficou vermelho em oito
corridas seguidas desde 26/09 14h27: cinco módulos de teste importavam a
interface sem `exigir_gi_real()` (`tests/conftest.py`), e o job do lint-test,
que não tem GTK, não conseguia coletá-los. O `portoes.sh` local dava verde,
porque esta máquina TEM o GTK: o defeito só existia sem ele.

Este portão roda a mesma coleta do CI (`pytest tests --collect-only -q
--continue-on-collection-errors`) com o `gi` e o `cairo` bloqueados no
`sys.meta_path`, que é como o passo do CI mediu o próprio ambiente
(PISO-DA-COLETA-02, no `ci.yml`), e reprova por qualquer `ERROR` de coleta.
O piso de encolhimento continua só no CI.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

_SEM_GTK = '''\
import sys


class _SemGtk:
    """O ambiente do lint-test: sem PyGObject e sem pycairo."""

    def find_spec(self, nome, caminho=None, alvo=None):
        if nome.split(".")[0] in ("gi", "cairo"):
            # No runner o pacote não existe: é ModuleNotFoundError, que é o
            # que o `pytest.importorskip` pula (um ImportError qualquer ele não pula).
            raise ModuleNotFoundError(f"No module named {nome!r}", name=nome)
        return None


sys.meta_path.insert(0, _SemGtk())
'''


def main() -> int:
    python = os.environ.get("HEFESTO_PY") or sys.executable
    with tempfile.TemporaryDirectory(prefix="coleta-sem-gtk-") as pasta:
        (Path(pasta) / "sitecustomize.py").write_text(_SEM_GTK, encoding="utf-8")
        ambiente = dict(os.environ)
        ambiente["PYTHONPATH"] = os.pathsep.join(
            p for p in (pasta, str(RAIZ / "src"), ambiente.get("PYTHONPATH", "")) if p
        )
        saida = subprocess.run(
            [
                python,
                "-m",
                "pytest",
                "tests",
                "--collect-only",
                "-q",
                "--continue-on-collection-errors",
                "-p",
                "no:cacheprovider",
            ],
            cwd=RAIZ,
            env=ambiente,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    linhas = saida.splitlines()
    total = sum(1 for linha in linhas if linha.startswith("tests/") and "::" in linha)
    erros = [linha for linha in linhas if linha.startswith("ERROR ")]
    if total == 0:
        print("FALHA: a coleta sem GTK não coletou nada; o pytest morreu antes.")
        print("\n".join(linhas[-15:]))
        return 1
    if erros:
        print(f"FALHA: {len(erros)} módulo(s) não coletam sem o GTK (o lint-test do CI reprova):")
        for linha in erros:
            print("  " + linha)
        print("\nMódulo de interface precisa de exigir_gi_real() (tests/conftest.py)")
        print("antes do primeiro import que carregue o GTK.")
        return 1
    print(f"OK: {total} testes coletados sem o GTK, nenhum erro de coleta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
