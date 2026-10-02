"""vigia_do_laco.py — o laço do serviço que para se denuncia (O-CONECTAR-ABRE-INTEIRO-TODA-VEZ-01).

O QUE SE MEDIU, 30/09/2026, na madrugada dela: o serviço respondia aos trancos
desde 01h08, parou de vez às 01h12:38 e ficou 3 min 30 s sem uma linha no
diário; a fila do soquete encheu (551 ``[Errno 11]`` na janela) e o SIGTERM do
install, que o laço asyncio atende (``lifecycle.py``, o
``add_signal_handler``), esperou 90 s até o SIGKILL. O laço estava parado, e
nada dizia ONDE. O que o parou não está provado: o serviço não deixou rastro.

A VIGIA TEM TRÊS PEÇAS, e a terceira é a que o indício pede (as linhas das
01h13 chegaram ao diário 0,3 a 0,9 s depois da hora que elas mesmas carimbam —
quem escrevia esperou, e esperar o GIL é um dos jeitos):

1. **a batida** — uma tarefa do laço que guarda a hora (``monotonic``) a cada
   ``passo_s``;
2. **o olho** — um fio de Python que olha a batida a cada ``passo_s`` e escreve
   ``laco_parado`` (uma vez por parada) e ``laco_voltou`` no diário do serviço;
3. **o relógio de C** — o ``faulthandler.dump_traceback_later``, rearmado a
   cada batida. Ele escreve a pilha de TODOS os fios no ``stderr`` (que é o
   ``journalctl``) sem precisar do GIL: pega o laço parado por um fio que
   segura o GIL, que o olho de Python não pegaria.

A pilha diz arquivo, linha e função, sem valor de variável: nenhum endereço de
aparelho vai ao diário. Nada de IPC, de aparelho ou de sudo. Ela não é um
subsistema do ``lifecycle``: mora em ``daemon/subsystems/`` só pela vizinhança,
e quem a liga é o ``run_daemon`` (``daemon/main.py``), em volta do
``daemon.run()``.

A CURA DO TRAVAMENTO EM SI é da sprint que a pilha apontar: na próxima vez que o
serviço parar, o ``journalctl`` diz onde, sem ninguém precisar estar olhando.
"""
from __future__ import annotations

import asyncio
import contextlib
import faulthandler
import sys
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any, TextIO, TypeVar

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Quanto a batida pode atrasar antes de o laço ser dado por parado.
LIMITE_S = 10.0
#: De quanto em quanto tempo a batida bate e o olho olha.
PASSO_S = 1.0

T = TypeVar("T")


def _no_diario(evento: str, **campos: Any) -> None:
    logger.warning(evento, **campos)


class VigiaDoLaco:
    """A batida no laço, o olho num fio, e o relógio de C do ``faulthandler``."""

    def __init__(
        self,
        *,
        limite_s: float = LIMITE_S,
        passo_s: float = PASSO_S,
        avisar: Callable[..., None] = _no_diario,
        saida: TextIO | None = None,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limite_s = float(limite_s)
        self.passo_s = float(passo_s)
        self._avisar = avisar
        self._saida = saida
        self._relogio = relogio
        self._batida = relogio()
        self._parado_desde: float | None = None
        self._parar = threading.Event()
        self._fio: threading.Thread | None = None
        self._tarefa: asyncio.Task[None] | None = None

    # -- o relógio de C ---------------------------------------------------------

    def _armar(self) -> None:
        """Rearma o relógio de C: a pilha sai se a próxima batida não vier no limite."""
        with contextlib.suppress(Exception):
            faulthandler.cancel_dump_traceback_later()
            faulthandler.dump_traceback_later(
                self.limite_s, repeat=False, file=self._saida or sys.stderr)

    # -- a batida ----------------------------------------------------------------

    async def _bater(self) -> None:
        while not self._parar.is_set():
            self._batida = self._relogio()
            self._armar()
            await asyncio.sleep(self.passo_s)

    # -- o olho ------------------------------------------------------------------

    def olhar(self) -> None:
        """UMA olhada na batida: diz a parada uma vez, e a volta quando ela vem."""
        idade = self._relogio() - self._batida
        if idade > self.limite_s:
            if self._parado_desde is None:
                self._parado_desde = self._batida
                self._avisar("laco_parado", segundos=round(idade))
            return
        if self._parado_desde is not None:
            parado = self._batida - self._parado_desde
            self._parado_desde = None
            self._avisar("laco_voltou", parado_s=round(parado, 1))

    def _olhar_sempre(self) -> None:
        while not self._parar.wait(self.passo_s):
            try:
                self.olhar()
            except Exception:  # o olho nunca derruba o serviço
                logger.warning("vigia_do_laco_levantou", exc_info=True)

    # -- ligar e desligar ----------------------------------------------------------

    def ligar(self) -> None:
        """Liga as três peças. Chamado DE DENTRO do laço que ela vigia."""
        self._batida = self._relogio()
        self._armar()
        self._tarefa = asyncio.get_running_loop().create_task(self._bater())
        self._fio = threading.Thread(target=self._olhar_sempre, name="hefesto-vigia-do-laco",
                                     daemon=True)
        self._fio.start()

    def desligar(self) -> None:
        """Desliga as três. Idempotente; nunca levanta."""
        self._parar.set()
        with contextlib.suppress(Exception):
            faulthandler.cancel_dump_traceback_later()
        if self._tarefa is not None:
            self._tarefa.cancel()
        if self._fio is not None and self._fio is not threading.current_thread():
            self._fio.join(timeout=self.passo_s * 2)


async def vigiado(corrotina: Awaitable[T], **ajustes: Any) -> T:
    """Roda ``corrotina`` com a vigia ligada em volta, e a desliga no fim."""
    vigia = VigiaDoLaco(**ajustes)
    vigia.ligar()
    try:
        return await corrotina
    finally:
        vigia.desligar()


__all__ = ["LIMITE_S", "PASSO_S", "VigiaDoLaco", "vigiado"]
