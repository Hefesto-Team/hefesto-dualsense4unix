"""Os arquivos da casa pela assinatura do ``stat`` — O-REPOUSO-ESPERA-O-EVENTO-01.

Família 6 da sprint (29/09/2026). A sonda S.4 da bancada de 29/09 (60 s, os
quatro controles no rádio, parados, sem jogo) contou 4.194 ``open`` por minuto
nos arquivos da casa: os perfis (dois ``open`` por perfil a cada carga, o
``FileLock`` e a leitura), o marcador do lançamento relido a 2 Hz e a lista de
exclusão lida a 2 Hz sem existir. Nenhum deles tinha mudado.

Um :class:`LeituraPelaAssinatura` guarda o conteúdo DECODIFICADO de cada
arquivo e só o relê quando a assinatura ``(st_ino, st_mtime_ns, st_size)``
muda: um ``stat``, nenhum ``open``. As regras, cada uma com o seu porquê:

- **arquivo ausente guarda «ausente»** até o ``stat`` achar o arquivo;
- **o arquivo recém-gravado não se guarda**: enquanto o ``mtime`` dele estiver a
  menos de :data:`JANELA_DO_RECEM_GRAVADO_S` do relógio de parede no instante
  da leitura, a leitura se repete a cada pergunta. Duas gravações do mesmo
  tamanho dentro do mesmo tique do relógio do sistema de arquivos dão a mesma
  assinatura — o mesmo cuidado do índice do git com o arquivo «racy»;
- **a assinatura guardada é a do ``stat`` feito DEPOIS da leitura**, sob a trava
  do dono do arquivo quando ele usa uma (o ``FileLock`` dos perfis); e quando
  ela difere da do ``stat`` de antes, alguém gravou durante a leitura (o
  wrapper grava o marker sem trava nenhuma): a leitura não se guarda, e a
  pergunta seguinte relê;
- **quem chama recebe uma cópia** (``copiar``): quem muda o objeto devolvido
  não muda a leitura seguinte;
- **leitura que falha não se guarda**: a exceção sobe para quem chama, como
  antes.

Serve para a gravação atômica (``os.replace``, inode novo) e para a que escreve
no lugar (``write_text``, ``mtime`` e tamanho novos): a assinatura muda nas duas.

Quem usa, e só com o dono do evento armado (``core/o_dono_do_evento.py``; sem
ele, a leitura de sempre): o ``load_all_profiles``, os marcadores do lançamento
(``daemon/launch_env.py``) e o ``lista_de_exclusao.contem``. Desarmar o dono
esquece tudo o que se guardou aqui.
"""

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

#: ``(st_ino, st_mtime_ns, st_size)``; None = o arquivo não existe.
Assinatura = tuple[int, int, int]

#: Quanto o ``mtime`` tem de estar atrás do relógio de parede, no instante da
#: leitura, para a leitura valer até a assinatura mudar. Folga larga sobre o
#: tique do relógio dos sistemas de arquivos (de nanossegundos a um segundo).
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
    #: False quando o arquivo foi lido recém-gravado: não vale até mudar.
    confiavel: bool


def _sem_trava() -> AbstractContextManager[object]:
    return contextlib.nullcontext()


class LeituraPelaAssinatura(Generic[T]):
    """O conteúdo decodificado de cada arquivo, relido só quando a assinatura muda.

    ``decodificar`` recebe o caminho e devolve o valor (e decide o que é o valor
    de um arquivo ausente, se não levantar); ``copiar`` faz a cópia que quem
    chama recebe; ``relogio`` é o relógio de PAREDE (``time.time``), costura de
    teste.
    """

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
