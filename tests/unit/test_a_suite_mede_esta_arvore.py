"""SRC-DESTA-ARVORE-01 — o teste daqui mede o produto daqui, não o de outra cópia.

O DEFEITO, medido em 04/09/2026 numa árvore de integração: **doze lotes de
suíte mediram o `src/` de OUTRA árvore**, e uma leva de portões junto.

O caminho é banal, e é por isso que passa: toda venv do projeto tem o pacote em
modo editável, e o `.pth` dela aponta para o `src/` da árvore onde a venv
nasceu. Chamar `<venv-de-lá>/bin/python -m pytest` aqui roda os TESTES daqui
contra o PRODUTO de lá.

E o sintoma engana de um jeito específico e caro: `ImportError: cannot import
name 'BYTE_SONS_DO_JOGO'` e `AttributeError: ... has no attribute '_ECO_DO_ATO'`
— exatamente o que se veria se o agente que criou esses símbolos não tivesse
terminado. Passei a diagnosticar trabalho entregue como trabalho faltando.

`CLAUDE.md` já descrevia o risco (§2, "o daemon vivo é da árvore DELA") e o
`portoes.sh` já AVISAVA. Nenhum dos dois curava: aviso no cabeçalho de um
comando que termina verde é aviso que ninguém lê.

As duas curas desta régua:

1. `tests/conftest.py` põe o `src/` da SUA árvore na frente do `sys.path` e do
   `PYTHONPATH` dos subprocessos — funciona com qualquer python que a chame.
2. `scripts/portoes.sh` RESOLVE o `PYTHONPATH` em vez de reclamar dele.
"""

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
    """A MORDIDA: um python de OUTRA árvore, sem PYTHONPATH, e ainda assim daqui.

    Arranque o bloco `SRC-DESTA-ARVORE-01` do `conftest.py` e este caso reprova
    na hora — é exatamente a chamada que produziu o defeito.
    """
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
    """A outra metade: o `portoes.sh` declara o `src/` que vai medir.

    A MORDIDA está no conteúdo: se alguém devolver o `else` com o texto
    "ARMADILHA", o cabeçalho volta a AVISAR — e o aviso é o que falhou.
    """
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
