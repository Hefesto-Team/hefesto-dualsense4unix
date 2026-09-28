"""O segfault da suíte diz onde morreu (VERDE-NAO-E-PROVA-01, passo 4).

Em 26/09/2026 uma parte da suíte morreu com `rc=139` (segfault, com o WebKit
no lote) e nenhum log tinha a pilha. O `catchsegv` saiu da glibc na 2.35, e
nesta máquina o `core_pattern` vai para o apport, sem `coredumpctl`. A pilha
em Python vem do `faulthandler`: o pytest o liga no próprio processo, e o
`tests/conftest.py` põe `PYTHONFAULTHANDLER=1` no ambiente para os filhos.

Nenhum dos dois testes derruba processo: medir o `faulthandler` ligado basta,
e um segfault de verdade acordaria o apport da máquina.

A MORDIDA: tire o `os.environ.setdefault("PYTHONFAULTHANDLER", "1")` do
conftest e `test_o_python_filho_herda_o_faulthandler` reprova.
"""
from __future__ import annotations

import faulthandler
import subprocess
import sys


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
        "de um filho (o WebKit sob Xvfb) morre sem dizer onde")
