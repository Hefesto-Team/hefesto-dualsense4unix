"""O dono único da falha de passo em todo laço do serviço.

Cada laço isola os passos por um :class:`PassosDoLaco` com o nome do laço: a falha soma
``<laço>.erro.<passo>`` no store e o ``warning`` com o traceback sai UMA vez por episódio; o
aviso volta só depois de um acerto do mesmo passo. O estado do episódio anda sob trava, porque
há laço em fio próprio. O laço sem store à mão conta no store do processo, o que o daemon
registra ao subir (:func:`registrar_o_store_do_processo`); sem daemon, num store próprio.
"""
from __future__ import annotations

import contextlib
import threading
from collections.abc import Awaitable, Callable, Iterator
from typing import Any, Final

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

FALHOU: Final = object()
LACO_DO_POLL: Final = "poll"
_ATRIBUTO_NO_DAEMON: Final = "_passos_dos_lacos"

_trava_do_processo = threading.Lock()
_store_do_processo: Any = None


def registrar_o_store_do_processo(store: Any) -> None:
    """O store em que os laços sem store próprio contam a falha (o do daemon que subiu)."""
    global _store_do_processo
    with _trava_do_processo:
        _store_do_processo = store


def store_do_processo() -> Any:
    """O store registrado pelo daemon; sem registro, um store próprio do processo."""
    global _store_do_processo
    with _trava_do_processo:
        if _store_do_processo is None:
            from hefesto_dualsense4unix.daemon.state_store import StateStore

            _store_do_processo = StateStore()
        return _store_do_processo


class PassosDoLaco:
    """O embrulho dos passos de UM laço: uma falha não derruba o laço nem some.

    ``store`` ``None`` conta no :func:`store_do_processo` da hora da falha.
    """

    __slots__ = ("_em_erro", "_laco", "_store", "_trava")

    def __init__(self, store: Any = None, laco: str = LACO_DO_POLL) -> None:
        self._store = store
        self._laco = laco
        self._em_erro: set[str] = set()
        self._trava = threading.Lock()

    @property
    def laco(self) -> str:
        return self._laco

    def falhou(self, nome: str, exc: BaseException) -> bool:
        """Conta a falha de ``nome``; ``True`` se a falha abre um episódio novo."""
        store = self._store if self._store is not None else store_do_processo()
        store.bump(f"{self._laco}.erro.{nome}")
        with self._trava:
            if nome in self._em_erro:
                return False
            self._em_erro.add(nome)
        logger.warning(
            "passo_do_laco_falhou", laco=self._laco, passo=nome, err=str(exc), exc_info=exc)
        return True

    def deu_certo(self, nome: str) -> None:
        with self._trava:
            self._em_erro.discard(nome)

    @contextlib.contextmanager
    def isolado(self, nome: str) -> Iterator[None]:
        """O bloco que levanta conta como falha de ``nome``, e o laço segue depois do bloco."""
        try:
            yield
        except Exception as exc:
            self.falhou(nome, exc)
            return
        self.deu_certo(nome)

    def passo(self, nome: str, fn: Callable[[], Any]) -> Any:
        """Roda ``fn``; devolve o resultado de ``fn``, ou :data:`FALHOU`."""
        try:
            resultado = fn()
        except Exception as exc:
            self.falhou(nome, exc)
            return FALHOU
        self.deu_certo(nome)
        return resultado

    async def passo_async(self, nome: str, fn: Callable[[], Awaitable[Any]]) -> Any:
        """O mesmo de :meth:`passo` para uma corrotina."""
        try:
            resultado = await fn()
        except Exception as exc:
            self.falhou(nome, exc)
            return FALHOU
        self.deu_certo(nome)
        return resultado


def passos_do_daemon(daemon: Any, laco: str) -> PassosDoLaco:
    """O :class:`PassosDoLaco` do laço ``laco`` deste daemon, sobre o store do daemon."""
    with _trava_do_processo:
        por_laco = getattr(daemon, _ATRIBUTO_NO_DAEMON, None)
        if not isinstance(por_laco, dict):
            por_laco = {}
            with contextlib.suppress(AttributeError, TypeError):
                setattr(daemon, _ATRIBUTO_NO_DAEMON, por_laco)
        passos = por_laco.get(laco)
        if not isinstance(passos, PassosDoLaco):
            passos = PassosDoLaco(getattr(daemon, "store", None), laco)
            por_laco[laco] = passos
        return passos


__all__ = [
    "FALHOU",
    "LACO_DO_POLL",
    "PassosDoLaco",
    "passos_do_daemon",
    "registrar_o_store_do_processo",
    "store_do_processo",
]
