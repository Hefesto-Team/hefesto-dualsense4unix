"""O `parec` do medidor MORRE COM O PAI — e o teste mata com SIGKILL."""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_FILHO = """
import sys, time
sys.path.insert(0, {raiz!r} + "/src")
from hefesto_dualsense4unix.integrations import nivel_do_microfone as m
m.argv_do_medidor = lambda fonte, uniq="": ["sleep", "300"]
fluxo = m.abrir_fluxo("fonte-de-mentira", "aabbcc000001")
if fluxo is None:
    print("0", flush=True)
    raise SystemExit(1)
print(fluxo.proc.pid, flush=True)
time.sleep(300)
"""


def _vivo(pid: int) -> bool:
    return os.path.exists(f"/proc/{pid}")


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="PR_SET_PDEATHSIG é do Linux")
def test_o_filho_morre_quando_o_pai_leva_sigkill() -> None:
    """ESTE É O TESTE QUE MORDE."""
    pai = subprocess.Popen(
        [sys.executable, "-c", _FILHO.format(raiz=RAIZ)],
        stdout=subprocess.PIPE, text=True,
    )
    try:
        assert pai.stdout is not None
        neto = int(pai.stdout.readline().strip())
        assert neto, "`abrir_fluxo` devolveu None — sem `parec`? O teste não mediu nada"
        time.sleep(0.5)
        assert _vivo(neto), "o filho nem chegou a nascer — o teste não mede nada"

        pai.kill()
        pai.wait(timeout=5)

        for _ in range(20):
            if not _vivo(neto):
                break
            time.sleep(0.05)

        assert not _vivo(neto), (
            f"o parec (pid {neto}) SOBREVIVEU ao SIGKILL do pai — é o órfão que "
            f"segura o microfone dela aberto. O `preexec_fn=_morrer_com_o_pai` "
            f"caiu do `Popen` de `integrations/nivel_do_microfone.py`?"
        )
    finally:
        with __import__("contextlib").suppress(Exception):
            pai.kill()


def test_a_funcao_da_cura_nao_derruba_quem_a_chama() -> None:
    """Chamá-la no processo do teste não pode matar o pytest."""
    from hefesto_dualsense4unix.integrations import nivel_do_microfone as m

    m._morrer_com_o_pai()
    assert True
