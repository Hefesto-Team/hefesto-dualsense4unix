"""O dono do evento — O-REPOUSO-ESPERA-O-EVENTO-01 (29/09/2026).

O que se mediu (sonda S.4 da bancada de 29/09, 60 s, os quatro no rádio, parados,
sem jogo): o daemon fazia 491 ``open`` por segundo em repouso, quase todos de
varreduras que rodavam por RELÓGIO (validade de 1, 2 e 5 s; tique de 1, 2 e 30 s)
para responder perguntas cuja resposta só muda num EVENTO: um nó que nasce, some
ou muda de dono. Cada módulo inventou a sua validade, e o que mais se aproximava
de um dono do evento (o ``InputDirWatch``) era um ``listdir`` por consumidor.

Este módulo é o dono: **um ``inotify`` só por processo**, pela ``libc`` via
``ctypes`` (sem dependência nova), olhando duas raízes, a das entradas
(``/dev/input``) e a dos nós (``/dev``, onde só contam os nomes ``hidraw*``).
Para cada raiz ele responde três gerações, números que só sobem:

- ``NOMES``: um nome nasceu, sumiu ou mudou de lugar;
- ``CRIACOES``: um nome nasceu (é o ``nasceu`` do ``InputDirWatch``);
- ``PERMISSOES``: um nome mudou de permissão (``IN_ATTRIB``). Fica numa geração
  própria porque o próprio produto a provoca (o broker faz ``chmod`` ao
  esconder), e quem só depende de nomes não acorda com isso. Entra de propósito:
  a permissão que o udev põe no nó que acabou de nascer e a ACL que um
  ``udevadm trigger`` devolve ao físico escondido chegam como evento.

Um ``IN_Q_OVERFLOW`` sobe todas as gerações: evento perdido é «tudo mudou»,
nunca «nada mudou». A raiz cujo olhar morre (``IN_IGNORED``) deixa de ser
olhada, e quem pergunta por ela volta ao comportamento de antes.

**Ler uma geração é drenar um fd não bloqueante**, sob uma trava (o poll loop, os
handlers de IPC, o ``reconnect_loop`` e os executores perguntam de fios
diferentes): nenhum ``open``, nenhuma listagem.

**O dono se ARMA, e só o daemon arma** (o ``reconnect_loop``, no caminho de
produção, com o desarme no ``finally``). Sem armar, e sem ``inotify`` (a chamada
falha), nenhuma resposta sai daqui, e toda função que pergunta a ele se
comporta como antes: a janela, a CLI e os instrumentos não ganham cache que
ninguém invalida. Desarmar chama as limpezas registradas em
:func:`ao_desarmar`, que zeram os caches presos a ele.

O ``sysfs`` não emite ``inotify`` para o que o kernel cria, e por isso ele não
é olhado aqui: o ``InputDirWatch`` de outra raiz (o do barramento HID) segue no
``listdir`` de sempre.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import struct
import threading
from collections.abc import Callable
from typing import Any

#: A raiz das entradas: os nós ``eventN``/``jsN`` que a descoberta percorre.
RAIZ_DAS_ENTRADAS = "/dev/input"
#: A raiz dos nós ``hidraw*``. Os outros nomes de ``/dev`` não contam.
RAIZ_DOS_NOS = "/dev"
PREFIXO_DOS_NOS = "hidraw"

NOMES = "nomes"
CRIACOES = "criações"
PERMISSOES = "permissões"
_TIPOS: tuple[str, ...] = (NOMES, CRIACOES, PERMISSOES)

# linux/inotify.h
IN_ATTRIB = 0x00000004
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_DELETE_SELF = 0x00000400
IN_MOVE_SELF = 0x00000800
IN_Q_OVERFLOW = 0x00004000
IN_IGNORED = 0x00008000
IN_ONLYDIR = 0x01000000

#: O que cada raiz pede ao kernel. O ``IN_ATTRIB`` é o que a régua da permissão
#: tardia arranca para morder.
MASCARA_DO_OLHAR = (
    IN_CREATE
    | IN_DELETE
    | IN_MOVED_FROM
    | IN_MOVED_TO
    | IN_ATTRIB
    | IN_DELETE_SELF
    | IN_MOVE_SELF
    | IN_ONLYDIR
)

#: ``struct inotify_event``: ``int wd; uint32 mask; uint32 cookie; uint32 len``.
_CABECALHO = struct.Struct("iIII")
_TAMANHO_DA_LEITURA = 64 * 1024

#: A época é global e só sobe: a ficha de um dono re-armado, ou de outro dono,
#: nunca casa com a de antes.
_EPOCA = 0
_EPOCA_TRAVA = threading.Lock()


def _nova_epoca() -> int:
    global _EPOCA
    with _EPOCA_TRAVA:
        _EPOCA += 1
        return _EPOCA


def _normal(raiz: str) -> str:
    return os.path.normpath(str(raiz))


def _libc_do_processo() -> Any:
    """A ``libc`` já carregada no processo (``dlopen(NULL)``, sem procurar arquivo)."""
    return ctypes.CDLL(None, use_errno=True)


class DonoDoEvento:
    """O ``inotify`` das duas raízes, e as gerações de cada uma.

    ``libc`` e ``ler`` são costuras de teste: o primeiro troca o
    ``inotify_init1``/``inotify_add_watch`` (o dublê que falha), o segundo a
    leitura do fd (o dublê que entrega um ``IN_Q_OVERFLOW``).
    """

    def __init__(
        self,
        *,
        entradas: str = RAIZ_DAS_ENTRADAS,
        nos: str = RAIZ_DOS_NOS,
        prefixo_dos_nos: str = PREFIXO_DOS_NOS,
        libc: Any = None,
        ler: Callable[[int, int], bytes] | None = None,
    ) -> None:
        self.raiz_das_entradas = _normal(entradas)
        self.raiz_dos_nos = _normal(nos)
        self._prefixos = {self.raiz_das_entradas: "", self.raiz_dos_nos: prefixo_dos_nos}
        self._libc = libc
        self._ler = ler if ler is not None else os.read
        self._trava = threading.Lock()
        self._fd = -1
        self._armes = 0
        self._epoca = 0
        self._raiz_do_wd: dict[int, str] = {}
        self._vivas: set[str] = set()
        self._geracoes: dict[str, dict[str, int]] = {
            raiz: dict.fromkeys(_TIPOS, 0) for raiz in self._prefixos
        }

    # -- armar e desarmar ---------------------------------------------------

    @property
    def armado(self) -> bool:
        return self._armes > 0

    @property
    def epoca(self) -> int:
        return self._epoca

    def armar(self) -> bool:
        """Liga o ``inotify``. False = não ligou, e nada aqui responde."""
        with self._trava:
            if self._armes > 0:
                self._armes += 1
                return True
            libc = self._libc if self._libc is not None else _libc_do_processo()
            try:
                fd = int(libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC))
            except Exception:
                return False
            if fd < 0:
                return False
            raiz_do_wd: dict[int, str] = {}
            for raiz in self._prefixos:
                try:
                    wd = int(libc.inotify_add_watch(fd, os.fsencode(raiz), MASCARA_DO_OLHAR))
                except Exception:
                    wd = -1
                if wd >= 0:
                    raiz_do_wd[wd] = raiz
            if not raiz_do_wd:
                with contextlib.suppress(OSError):
                    os.close(fd)
                return False
            self._fd = fd
            self._raiz_do_wd = raiz_do_wd
            self._vivas = set(raiz_do_wd.values())
            self._armes = 1
            self._epoca = _nova_epoca()
            return True

    def desarmar(self) -> None:
        """Desfaz um ``armar``; no último, fecha o fd e zera os caches presos a ele."""
        with self._trava:
            if self._armes == 0:
                return
            self._armes -= 1
            if self._armes > 0:
                return
            fd, self._fd = self._fd, -1
            self._raiz_do_wd = {}
            self._vivas = set()
            with contextlib.suppress(OSError):
                os.close(fd)
        _limpar_os_caches()

    # -- as perguntas -------------------------------------------------------

    def olha(self, raiz: str) -> bool:
        """Esta raiz está sob o olhar agora? (armado, e o olhar dela vivo)."""
        with self._trava:
            if self._armes == 0:
                return False
            self._drenar()
            return _normal(raiz) in self._vivas

    def geracao(self, raiz: str, tipo: str = NOMES) -> int | None:
        """A geração ``tipo`` da ``raiz``; None = não se olha (e não se guarda nada)."""
        ficha = self.ficha((raiz, tipo))
        return None if ficha is None else ficha[1]

    def ficha(self, *pedidos: tuple[str, str]) -> tuple[int, ...] | None:
        """``(época, geração, …)`` dos pedidos, ou None se algum não se olha.

        É a chave com que um cache se prende ao evento: ficha igual, resposta
        igual. Quem guarda anota a ficha ANTES de calcular a resposta; o evento
        que chega durante o cálculo muda a ficha, e a pergunta seguinte refaz.
        """
        with self._trava:
            if self._armes == 0:
                return None
            self._drenar()
            valores: list[int] = [self._epoca]
            for raiz, tipo in pedidos:
                chave = _normal(raiz)
                if chave not in self._vivas:
                    return None
                valores.append(self._geracoes[chave][tipo])
            return tuple(valores)

    # -- o fd ---------------------------------------------------------------

    def _drenar(self) -> None:
        """Lê tudo o que o kernel enfileirou. Chamado sob a trava."""
        while self._fd >= 0:
            try:
                dados = self._ler(self._fd, _TAMANHO_DA_LEITURA)
            except BlockingIOError:
                return
            except OSError:
                # O fd quebrou: «tudo mudou», e daqui em diante nada se olha.
                self._subir_tudo()
                self._vivas = set()
                return
            if not dados:
                return
            self._consumir(dados)

    def _consumir(self, dados: bytes) -> None:
        pos = 0
        while pos + _CABECALHO.size <= len(dados):
            wd, mascara, _cookie, tamanho = _CABECALHO.unpack_from(dados, pos)
            bruto = dados[pos + _CABECALHO.size : pos + _CABECALHO.size + tamanho]
            pos += _CABECALHO.size + tamanho
            if mascara & IN_Q_OVERFLOW:
                self._subir_tudo()
                continue
            raiz = self._raiz_do_wd.get(wd)
            if raiz is None:
                continue
            if mascara & (IN_IGNORED | IN_DELETE_SELF | IN_MOVE_SELF):
                self._subir(raiz, *_TIPOS)
                self._vivas.discard(raiz)
                continue
            nome = bruto.split(b"\0", 1)[0].decode("utf-8", "replace")
            if not nome or not nome.startswith(self._prefixos[raiz]):
                continue
            if mascara & (IN_CREATE | IN_MOVED_TO):
                self._subir(raiz, NOMES, CRIACOES)
            if mascara & (IN_DELETE | IN_MOVED_FROM):
                self._subir(raiz, NOMES)
            if mascara & IN_ATTRIB:
                self._subir(raiz, PERMISSOES)

    def _subir(self, raiz: str, *tipos: str) -> None:
        for tipo in tipos:
            self._geracoes[raiz][tipo] += 1

    def _subir_tudo(self) -> None:
        for raiz in self._geracoes:
            self._subir(raiz, *_TIPOS)


# ---------------------------------------------------------------------------
# O dono do processo
# ---------------------------------------------------------------------------

_DONO: DonoDoEvento | None = None
_DONO_TRAVA = threading.Lock()
_LIMPEZAS: list[Callable[[], None]] = []


def ao_desarmar(limpeza: Callable[[], None]) -> None:
    """Registra quem zerar quando o dono desarma (uma vez por função)."""
    with _DONO_TRAVA:
        if limpeza not in _LIMPEZAS:
            _LIMPEZAS.append(limpeza)


def _limpar_os_caches() -> None:
    with _DONO_TRAVA:
        limpezas = list(_LIMPEZAS)
    for limpeza in limpezas:
        with contextlib.suppress(Exception):
            limpeza()


def armar(
    *,
    entradas: str | None = None,
    nos: str | None = None,
    libc: Any = None,
    ler: Callable[[int, int], bytes] | None = None,
) -> bool:
    """Arma o dono do PROCESSO. Devolve se ele ficou armado.

    Já armado, só conta mais um ``armar`` (as raízes pedidas não mudam nada).
    Desarmado, nasce de novo com as raízes pedidas: as padrão no daemon, as de
    mentira na suíte.
    """
    global _DONO
    with _DONO_TRAVA:
        dono = _DONO
        if dono is None or not dono.armado:
            dono = DonoDoEvento(
                entradas=entradas or RAIZ_DAS_ENTRADAS,
                nos=nos or RAIZ_DOS_NOS,
                libc=libc,
                ler=ler,
            )
            _DONO = dono
    return dono.armar()


def desarmar() -> None:
    """Desfaz um :func:`armar` do dono do processo."""
    dono = _DONO
    if dono is not None:
        dono.desarmar()


def dono_armado() -> DonoDoEvento | None:
    """O dono do processo, se armado; None, e quem pergunta faz como antes."""
    dono = _DONO
    if dono is None or not dono.armado:
        return None
    return dono


def armado() -> bool:
    return dono_armado() is not None


__all__ = [
    "CRIACOES",
    "IN_ATTRIB",
    "IN_CREATE",
    "IN_DELETE",
    "IN_IGNORED",
    "IN_Q_OVERFLOW",
    "MASCARA_DO_OLHAR",
    "NOMES",
    "PERMISSOES",
    "PREFIXO_DOS_NOS",
    "RAIZ_DAS_ENTRADAS",
    "RAIZ_DOS_NOS",
    "DonoDoEvento",
    "ao_desarmar",
    "armado",
    "armar",
    "desarmar",
    "dono_armado",
]
