"""SRC-DESTA-ARVORE-01 — o teste daqui mede o produto daqui, não o de outra cópia."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def test_o_produto_importado_e_o_desta_arvore() -> None:
    """A METADE QUE IMPORTA — e ela vale mesmo chamada pela venv de outra árvore."""
    import hefesto_dualsense4unix as produto

    achado = Path(produto.__file__ or "").resolve()
    esperado = (RAIZ / "src" / "hefesto_dualsense4unix").resolve()
    assert achado.parent == esperado, (
        f"a suíte está medindo OUTRA árvore:\n  produto: {achado}\n"
        f"  esperado sob: {esperado}\n"
        "É o defeito de 04/09/2026 — e ele não reprova nada, só faz símbolo "
        "novo virar ImportError."
    )


def test_a_cura_nao_depende_de_qual_python_chamou() -> None:
    """A MORDIDA: um python de OUTRA árvore, sem PYTHONPATH, e ainda assim daqui."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    r = subprocess.run(
        [
            sys.executable,
            "-c",
            "import tests.conftest, hefesto_dualsense4unix as p; print(p.__file__)",
        ],
        cwd=RAIZ, capture_output=True, text=True, env=env, timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert str(RAIZ / "src") in r.stdout, (
        "sem PYTHONPATH o conftest deixou o produto de outra árvore entrar:\n"
        + r.stdout + r.stderr
    )


def test_o_pythonpath_vai_junto_para_os_subprocessos() -> None:
    """A suíte dispara dezenas de subprocessos; eles herdam a mesma escolha."""
    assert str(RAIZ / "src") in os.environ.get("PYTHONPATH", "").split(os.pathsep)


def test_o_portao_resolve_o_pythonpath_em_vez_de_reclamar() -> None:
    """A outra metade: o `portoes.sh` declara o `src/` que vai medir."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    r = subprocess.run(
        ["bash", str(RAIZ / "scripts" / "portoes.sh"), "--interpretador"],
        cwd=RAIZ, capture_output=True, text=True, env=env, timeout=60,
    )
    linha = next(
        (ln for ln in r.stdout.splitlines() if "PYTHONPATH" in ln), ""
    )
    assert str(RAIZ / "src") in linha, (
        "o portão não resolveu o `src/` desta árvore:\n" + r.stdout
    )
    assert "(vazio)" not in linha and "ARMADILHA" not in r.stdout, (
        "o cabeçalho voltou a AVISAR em vez de curar — aviso é o que falhou "
        "em 04/09/2026.\n" + r.stdout
    )
