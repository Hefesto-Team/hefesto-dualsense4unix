"""O filho de som do daemon: quem sobe um processo derruba o processo.

SOM-TRAVA-NA-QUEDA-01 (13/09/2026). Um dono só para as duas coisas que os três
leitores de som do daemon precisam e que cada um fazia do seu jeito: nascer
preso ao pai (``PR_SET_PDEATHSIG``) e morrer quando a casa manda, mesmo com o
cano cheio.

O DEFEITO, MEDIDO NO ESTUDO DA SPRINT
-------------------------------------
Na queda do controle no rádio, o laço da ponte de som para de ler o
``pw-record`` do monitor do nó (a escrita no hidraw é recusada), o cano de
64 KiB enche em cerca de 0,34 s, e a única thread do gravador fica parada no
``write``. O SIGTERM do ``descer()`` chega por ``signalfd`` e fica PENDENTE para
sempre (``ShdPnd 0x4000``, ``wchan anon_pipe_write``). O gravador sobrevive à
ponte, e todo cliente que tenta mudar um parâmetro do nó dele fica esperando
por ele — e na máquina dela a sessão de som parou duas vezes no mesmo dia, com
a Steam sem janela.

O que derruba, medido: **fechar a ponta de leitura** (o ``write`` pendente toma
SIGPIPE, 1,1 ms) ou SIGKILL. E nos dois casos o ``wait`` é obrigatório, senão
sobra zumbi.

A ORDEM, e cada passo tem a razão ao lado
-----------------------------------------
:func:`derrubar_leitor_de_pipe` faz, nesta ordem:

1. ``terminate`` — o gravador são sai por aqui em 1 ms, e quem lê vê o fim;
2. ``join`` da thread que lê, com prazo — quando há thread;
3. **só se quem lê já parou**, fechar o ``stdout``. Com a thread ainda viva o
   fd seria reaproveitado pelo kernel debaixo do ``read`` dela, o mesmo
   cuidado que ``PonteDeSomPorRadio.descer`` já registra para o hidraw;
4. ``wait`` com prazo;
5. ``kill`` e ``wait`` de novo, se o prazo passou (o teimoso: TERM bloqueado e
   SIGPIPE ignorado caem só aqui);
6. ``join`` de novo — o KILL dá o fim do cano a quem lia;
7. só então fechar o ``stdout``.

E devolve :class:`ComoMorreu` — código de saída, milissegundos e se precisou
insistir — para o diário. Não é frase de tela: o defeito é do daemon.

O PDEATHSIG É DA THREAD, NÃO DO PROCESSO — medido nesta sprint
--------------------------------------------------------------
O kernel manda o sinal quando morre a THREAD que lançou o filho, e não só
quando morre o processo: um dublê lançado de uma thread curta, com o
``prctl``, morreu com SIGKILL no instante em que a thread terminou; sem o
``prctl`` ficou vivo. Por isso só se lança leitor de som de uma thread que
vive tanto quanto ele — a de reconciliação do subsystem, que é de onde os dois
filhos de vida longa nascem hoje. Lançar de uma thread de trabalho curta
mataria o filho logo depois de nascer.
"""

from __future__ import annotations

import contextlib
import ctypes
import signal
import subprocess
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

#: Quanto se espera o processo morrer antes de insistir com o KILL. Medido no
#: estudo: o teimoso cai por KILL em 1001 ms com este prazo, e o gravador preso
#: cai por SIGPIPE muito antes de ele vencer.
ESPERA_PELO_FIM_S = 1.0

#: O número do ``prctl`` que arma o sinal de morte do pai. O nome é do kernel.
_PR_SET_PDEATHSIG = 1


def _carregar_o_prctl() -> Any:
    """O ``prctl`` da libc, resolvido UMA vez no processo pai. ``None`` fora do Linux.

    Resolver aqui, e não dentro de :func:`morrer_com_o_pai`, tira o ``dlopen``
    do intervalo entre o ``fork`` e o ``exec``: ali o filho herda os locks do
    pai no estado em que estavam, e alocar memória é o que pode travar.
    """
    try:
        return ctypes.CDLL("libc.so.6", use_errno=True).prctl
    except (OSError, AttributeError):
        return None


_PRCTL = _carregar_o_prctl()


def morrer_com_o_pai() -> None:
    """Pede ao kernel um SIGKILL neste filho quando o pai morrer. Nunca levanta.

    É ``preexec_fn``: roda no FILHO, entre o ``fork`` e o ``exec``. O
    ``terminate()`` de quem lançou só alcança a morte ORDEIRA do daemon; morte
    por SIGKILL, OOM ou queda da sessão não roda ``finally`` nenhum, e é
    justamente quando o filho vira órfão com ``ppid 1``.

    O ``start_new_session=True`` seria o OPOSTO: ele desliga o filho do grupo
    do pai, que é como o processo sobrevive ao terminal.

    O aviso do ruff (PLW1509) é sobre ``preexec_fn`` em programa com threads.
    Aqui a chamada é um único ``prctl`` já resolvido no pai, sem importar nada
    e sem abrir biblioteca no filho.

    Fora do Linux não faz nada, e o processo nasce igual: degradar em silêncio
    é melhor que recusar o som inteiro num sistema que não é Linux.

    O NOME ANTIGO CONTINUA VALENDO: ``nivel_do_microfone._morrer_com_o_pai`` é
    esta função, reexportada, porque a régua do medidor a chama por lá.
    """
    prctl = _PRCTL
    if prctl is None:
        return
    with contextlib.suppress(Exception):
        prctl(_PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)


def lancar_leitor(argv: Sequence[str]) -> subprocess.Popen[bytes]:
    """O ``Popen`` de um leitor de som: cano no ``stdout``, e preso ao pai.

    ``stdout=PIPE`` é a outra trava de morte: com o cano, o filho que escreve
    morre por SIGPIPE quando a ponta de leitura fecha; com ``/dev/null`` ele
    sobreviveria. ``stderr`` vai para ``/dev/null`` porque ninguém o lê, e um
    segundo cano sem leitor seria outro jeito de o filho parar num ``write``.

    Sem ``shell=True``, que é invariante desta casa: o argv é uma lista.
    """
    return subprocess.Popen(  # argv fixo, sem shell
        list(argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        preexec_fn=morrer_com_o_pai,
    )


@dataclass(frozen=True)
class ComoMorreu:
    """Como o filho morreu — para o diário, nunca para a tela.

    O primeiro campo é o ``returncode``: negativo é o sinal que o derrubou
    (``-13`` é SIGPIPE, ``-9`` é SIGKILL), ``None`` é que ele NÃO foi colhido.
    """

    codigo: int | None
    ms: float
    insistiu: bool = False

    @property
    def por(self) -> str:
        """O nome do fim: ``SIGPIPE``, ``SIGKILL``, ``saiu`` ou ``vivo``."""
        if self.codigo is None:
            return "vivo"
        if self.codigo >= 0:
            return "saiu"
        try:
            return signal.Signals(-self.codigo).name
        except ValueError:
            return f"sinal {-self.codigo}"


def _terminar(proc: Any) -> None:
    terminar = getattr(proc, "terminate", None)
    if terminar is None:
        return
    with contextlib.suppress(Exception):
        terminar()


def _fechar_a_saida(proc: Any) -> None:
    saida = getattr(proc, "stdout", None)
    if saida is None:
        return
    with contextlib.suppress(Exception):
        saida.close()


def _esperar(proc: Any, prazo_s: float) -> int | None:
    """O código de saída, ou ``None`` se o processo não morreu no prazo."""
    esperar = getattr(proc, "wait", None)
    if esperar is None:
        return None
    try:
        codigo = esperar(timeout=prazo_s)
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
    codigo = getattr(proc, "returncode", codigo)
    return int(codigo) if codigo is not None else None


def derrubar_leitor_de_pipe(
    proc: Any,
    *,
    leitor: threading.Thread | None = None,
    junta_s: float = ESPERA_PELO_FIM_S,
    espera_s: float = ESPERA_PELO_FIM_S,
) -> ComoMorreu:
    """Derruba e COLHE um processo cujo ``stdout`` é lido por nós. Idempotente.

    ``leitor`` é a thread que lê o cano, quando existe. A ordem dos sete passos
    e a razão de cada um estão no cabeçalho deste módulo; a regra que não pode
    cair é a do passo 3: o ``stdout`` só fecha com quem lê já parado.

    Nunca levanta, e aceita dublê: quem não tem ``terminate``, ``wait`` ou
    ``stdout`` só pula aquele passo.
    """
    comeco = time.monotonic()
    if proc is None:
        return ComoMorreu(codigo=None, ms=0.0)
    _terminar(proc)
    if leitor is not None and leitor.is_alive():
        leitor.join(timeout=junta_s)
    parado = leitor is None or not leitor.is_alive()
    if parado:
        _fechar_a_saida(proc)
    insistiu = False
    codigo = _esperar(proc, espera_s)
    if codigo is None:
        matar = getattr(proc, "kill", None)
        if matar is not None:
            insistiu = True
            with contextlib.suppress(Exception):
                matar()
            codigo = _esperar(proc, espera_s)
    if not parado and leitor is not None:
        leitor.join(timeout=junta_s)
    if leitor is None or not leitor.is_alive():
        _fechar_a_saida(proc)
    return ComoMorreu(
        codigo=codigo,
        ms=round((time.monotonic() - comeco) * 1000.0, 1),
        insistiu=insistiu,
    )


__all__ = [
    "ESPERA_PELO_FIM_S",
    "ComoMorreu",
    "derrubar_leitor_de_pipe",
    "lancar_leitor",
    "morrer_com_o_pai",
]
