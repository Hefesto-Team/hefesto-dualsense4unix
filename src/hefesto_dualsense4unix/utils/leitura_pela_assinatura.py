"""Os arquivos da casa pela assinatura do ``stat`` — O-REPOUSO-ESPERA-O-EVENTO-01."""

from __future__ import annotations

import contextlib
import os
import threading
import time
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

T = TypeVar("T")

Assinatura = tuple[int, int, int]

JANELA_DO_RECEM_GRAVADO_S = 2.0


def assinatura(caminho: str | os.PathLike[str]) -> Assinatura | None:
    """A assinatura do arquivo por ``stat``, sem abrir nada; None = ausente."""
    try:
        st = os.stat(caminho)
    except OSError:
        return None
    return (int(st.st_ino), int(st.st_mtime_ns), int(st.st_size))


@dataclass(frozen=True)
class _Guardado(Generic[T]):
    assinatura: Assinatura | None
    valor: T
    confiavel: bool


def _sem_trava() -> AbstractContextManager[object]:
    return contextlib.nullcontext()


class LeituraPelaAssinatura(Generic[T]):
    """O conteúdo decodificado de cada arquivo, relido só quando a assinatura muda."""

    def __init__(
        self,
        decodificar: Callable[[Path], T],
        *,
        copiar: Callable[[T], T] | None = None,
        relogio: Callable[[], float] = time.time,
        recem_gravado_s: float = JANELA_DO_RECEM_GRAVADO_S,
    ) -> None:
        self._decodificar = decodificar
        self._copiar: Callable[[T], T] = copiar if copiar is not None else (lambda v: v)
        self._relogio = relogio
        self._recem_gravado_s = recem_gravado_s
        self._trava = threading.Lock()
        self._guardados: dict[str, _Guardado[T]] = {}

    def ler(
        self,
        caminho: str | os.PathLike[str],
        *,
        trava: Callable[[], AbstractContextManager[object]] | None = None,
    ) -> T:
        """O valor do arquivo: o guardado se a assinatura é a mesma, senão lê."""
        chave = os.fspath(caminho)
        agora = assinatura(chave)
        with self._trava:
            guardado = self._guardados.get(chave)
        if guardado is not None and guardado.confiavel and guardado.assinatura == agora:
            return self._copiar(guardado.valor)
        with (trava or _sem_trava)():
            valor = self._decodificar(Path(chave))
            depois = assinatura(chave)
        lido_em = self._relogio()
        confiavel = depois == agora and (
            depois is None or (lido_em - depois[1] / 1e9) >= self._recem_gravado_s
        )
        with self._trava:
            self._guardados[chave] = _Guardado(depois, valor, confiavel)
        return self._copiar(valor)

    def manter_so(self, caminhos: Iterable[str | os.PathLike[str]]) -> None:
        """Esquece os arquivos que não estão em ``caminhos`` (a pasta perdeu um)."""
        ficam = {os.fspath(c) for c in caminhos}
        with self._trava:
            for chave in [c for c in self._guardados if c not in ficam]:
                del self._guardados[chave]

    def esquecer(self) -> None:
        """Joga fora tudo o que se guardou."""
        with self._trava:
            self._guardados.clear()


__all__ = [
    "JANELA_DO_RECEM_GRAVADO_S",
    "Assinatura",
    "LeituraPelaAssinatura",
    "assinatura",
]
