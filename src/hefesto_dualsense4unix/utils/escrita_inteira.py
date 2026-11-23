"""O dono da escrita de estado: o arquivo novo inteiro no lugar, ou o de antes intacto."""
from __future__ import annotations

import asyncio
import atexit
import os
import tempfile
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path


def escrever_inteiro(alvo: Path | str, dados: bytes | str) -> None:
    """Grava ``dados`` em ``alvo`` por troca atômica (o texto vai em UTF-8).

    Temporário na mesma pasta, escrita repetida até o último byte, ``fsync`` e
    ``os.replace``. Falha levanta ``OSError`` com o ``alvo`` de antes byte a byte
    igual e sem temporário na pasta; quem lê vê o arquivo velho ou o novo, nunca a metade.
    """
    alvo = Path(alvo)
    bruto = dados.encode("utf-8") if isinstance(dados, str) else dados
    alvo.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix=f".{alvo.name}.", suffix=".tmp", dir=alvo.parent)
    try:
        try:
            resto = memoryview(bruto)
            while resto:
                resto = resto[os.write(fd, resto):]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporario, alvo)
    except BaseException:
        Path(temporario).unlink(missing_ok=True)
        raise


def no_fio_do_laco() -> bool:
    """O fio de quem chama roda um laço do ``asyncio``? Quem espera o disco aqui para o laço."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


@dataclass
class _Pedido:
    trabalho: Callable[[], None]
    futuros: list[Future[None]] = field(default_factory=list)


class _Gravador:
    """A fila de gravações num fio só: na ordem de chegada, e a última da mesma chave vence."""

    def __init__(self) -> None:
        self._trava = threading.Condition()
        self._fila: dict[str, _Pedido] = {}
        self._em_curso: dict[str, _Pedido] = {}
        self._fio: threading.Thread | None = None

    def agendar(self, chave: str, trabalho: Callable[[], None]) -> Future[None]:
        futuro: Future[None] = Future()
        with self._trava:
            pedido = self._fila.get(chave)
            if pedido is None:
                pedido = self._fila[chave] = _Pedido(trabalho)
            else:
                pedido.trabalho = trabalho
            pedido.futuros.append(futuro)
            if self._fio is None or not self._fio.is_alive():
                self._fio = threading.Thread(
                    target=self._servir, name="gravador-do-estado", daemon=True
                )
                self._fio.start()
            self._trava.notify_all()
        return futuro

    def _servir(self) -> None:
        while True:
            with self._trava:
                if not self._fila:
                    self._fio = None
                    self._trava.notify_all()
                    return
                chave = next(iter(self._fila))
                pedido = self._fila.pop(chave)
                self._em_curso[chave] = pedido
            erro: BaseException | None = None
            try:
                pedido.trabalho()
            except BaseException as exc:
                erro = exc
            with self._trava:
                self._em_curso.pop(chave, None)
                self._trava.notify_all()
            for futuro in pedido.futuros:
                if erro is None:
                    futuro.set_result(None)
                else:
                    futuro.set_exception(erro)

    def esperar(self, prazo_s: float) -> bool:
        fim = time.monotonic() + prazo_s
        with self._trava:
            while self._fila or self._em_curso:
                restante = fim - time.monotonic()
                if restante <= 0:
                    return False
                self._trava.wait(restante)
        return True


_GRAVADOR = _Gravador()


def gravar_sem_parar_o_laco(
    chave: str, trabalho: Callable[[], None]
) -> Future[None] | None:
    """Roda ``trabalho`` (uma gravação) fora do fio do laço, ou aqui mesmo fora de um laço.

    No fio de um laço do ``asyncio`` o ``trabalho`` vai para o gravador e a chamada volta com o
    futuro dele: a falha chega por ele, nunca pelo laço. Duas gravações da mesma ``chave`` na
    fila viram a última. Fora de um laço o ``trabalho`` roda na hora, a falha levanta aqui e
    o retorno é ``None``.
    """
    if not no_fio_do_laco():
        trabalho()
        return None
    return _GRAVADOR.agendar(chave, trabalho)


def esperar_a_fila(prazo_s: float = 10.0) -> bool:
    """Espera o gravador esvaziar a fila (a parada do serviço); ``False`` se o prazo estourou."""
    return _GRAVADOR.esperar(prazo_s)


atexit.register(esperar_a_fila)
