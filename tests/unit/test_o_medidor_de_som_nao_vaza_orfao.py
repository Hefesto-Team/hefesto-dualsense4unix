"""O `parec` do medidor MORRE COM O PAI — e o teste mata com SIGKILL.

O DEFEITO, medido na máquina dela em 03/09/2026
------------------------------------------------
Três gerações diferentes de `parec` sobreviveram aos processos que as lançaram.
A última tinha `PPID=1`, 42 segundos de vida e o `hefesto.uniq` no `cmdline` —
era nosso, estava órfão, e segurava a fonte de captura do controle em `RUNNING`.

Em português: **o microfone dela ficava aberto por um processo que ninguém
estava lendo.** Numa mesa de quatro controles, quatro medidores vazando é o
microfone dos quatro aberto para sempre.

POR QUE O `terminate()` NÃO BASTAVA, e é o ponto do teste
----------------------------------------------------------
O `_FluxoParec` já fecha o processo no `finally`. Isso cobre a morte ORDEIRA —
aquela em que o pai teve chance de rodar o seu código de saída. O vazamento
acontece justamente quando ele NÃO tem: `SIGKILL`, `OOM killer`, queda da
sessão gráfica. É por isso que este teste mata o pai com `SIGKILL`: qualquer
morte mais gentil deixaria o `finally` rodar e o teste passaria mesmo com a
cura arrancada — seria uma régua que mede a PALAVRA, não o ATO.

A CURA é o `PR_SET_PDEATHSIG` em `_morrer_com_o_pai`, o único mecanismo que não
depende de o pai colaborar: quem mata o filho é o kernel.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: O filho roda num processo SEPARADO de propósito: `PR_SET_PDEATHSIG` age na
#: morte do processo PAI, e o pai aqui tem de ser alguém que possamos matar sem
#: derrubar o pytest.
#:
#: E ele chama `abrir_fluxo` — O CAMINHO DO PRODUTO —, nunca a função da cura
#: diretamente. A primeira versão deste teste chamava
#: `Popen(..., preexec_fn=m._morrer_com_o_pai)` com as próprias mãos, e por isso
#: PASSAVA COM A CURA ARRANCADA: ela media se a FUNÇÃO funciona, não se o
#: produto A USA. É a família de defeito que esta casa mais paga — *a régua
#: confunde a PALAVRA com o ATO* —, e foi pega na própria mordida, em 03/09/2026.
#:
#: O `argv_do_medidor` é trocado por um `sleep` porque o alvo aqui é a MORTE do
#: processo, não a medição de áudio: um `parec` contra fonte inexistente sairia
#: em milissegundos e não haveria órfão para observar. Tudo o mais — o `Popen`,
#: o `preexec_fn`, o `env` — é o do produto, intocado.
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
    """ESTE É O TESTE QUE MORDE.

    Tire o `preexec_fn=_morrer_com_o_pai` do `Popen` de
    `integrations/nivel_do_microfone.py` e ele reprova na hora — medido em
    03/09/2026, com o processo de verdade: sem a cura o filho SOBREVIVE ao
    `SIGKILL` do pai, que é exatamente o órfão que se viu na mesa dela.
    """
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

        pai.kill()   # SIGKILL: a morte que o `finally` NÃO alcança
        pai.wait(timeout=5)

        # O kernel entrega o sinal na hora, mas o /proc leva um instante para
        # sumir. Meio segundo é folga larga; sem a cura ele sobrevive aos 300 s.
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
    """Chamá-la no processo do teste não pode matar o pytest.

    Ela é `preexec_fn`, logo roda no FILHO depois do `fork` — mas nada impede
    alguém de chamá-la por engano no processo principal, e nesse caso ela só
    arma um sinal que nunca chega (o pai do pytest continua vivo). O teste
    existe para que a função continue sendo inofensiva fora do lugar dela.
    """
    from hefesto_dualsense4unix.integrations import nivel_do_microfone as m

    m._morrer_com_o_pai()   # se isto matar o processo, o pytest não reporta nada
    assert True
