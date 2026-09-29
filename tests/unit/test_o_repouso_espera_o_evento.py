"""O repouso espera o evento (O-REPOUSO-ESPERA-O-EVENTO-01, 29/09/2026).

A sonda S.4 da bancada de 29/09 contou 491 ``open`` por segundo no daemon
parado, com os quatro controles no rádio e sem jogo: varreduras que rodavam
por RELÓGIO para responder perguntas cuja resposta só muda num EVENTO. A cura
é um dono do evento (``core/o_dono_do_evento.py``) e o cache de cada resposta
preso a ele.

Todas as réguas contam o trabalho do PRODUTO com um ``sys.addaudithook`` nos
eventos ``open``, ``os.listdir`` e ``os.scandir`` da biblioteca padrão (o
``open`` sozinho não vê uma listagem, e a ``glob`` lista por ``os.scandir``),
numa pasta de mentira (``tmp_path``, onde o ``inotify`` funciona), com o dono
ARMADO nas raízes de mentira por um fixture que desarma no teardown. Nenhuma
conta a própria saída: a conta vem do gancho, e o relógio é injetado.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import struct
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import o_dono_do_evento as ode
from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch

# ---------------------------------------------------------------------------
# O gancho que conta o trabalho do produto
# ---------------------------------------------------------------------------

#: Enquanto não é None, o gancho anota ``(evento, caminho)`` de todo ``open``,
#: ``os.listdir`` e ``os.scandir`` do fio que ligou a conta.
_CONTA: list[tuple[str, str]] | None = None
_FIO_DA_CONTA: int | None = None
_EVENTOS_CONTADOS = frozenset({"open", "os.listdir", "os.scandir"})


def _gancho(evento: str, args: tuple[Any, ...]) -> None:
    conta = _CONTA
    if conta is None or evento not in _EVENTOS_CONTADOS:
        return
    if threading.get_ident() != _FIO_DA_CONTA:
        return
    alvo = args[0] if args else ""
    if isinstance(alvo, bytes):
        alvo = os.fsdecode(alvo)
    conta.append((evento, str(alvo)))


# Um gancho de auditoria não se remove: fica um só, barato, por processo.
if not getattr(sys, "_hefesto_gancho_do_repouso", False):
    sys.addaudithook(_gancho)
    sys._hefesto_gancho_do_repouso = True  # type: ignore[attr-defined]


@contextlib.contextmanager
def contando() -> Iterator[list[tuple[str, str]]]:
    """Liga a conta no fio de quem chama e a desliga na saída."""
    global _CONTA, _FIO_DA_CONTA
    conta: list[tuple[str, str]] = []
    _FIO_DA_CONTA = threading.get_ident()
    _CONTA = conta
    try:
        yield conta
    finally:
        _CONTA = None
        _FIO_DA_CONTA = None


def _sob(conta: list[tuple[str, str]], raiz: Path | str, *eventos: str) -> list[str]:
    """Os caminhos contados sob ``raiz`` (e só dos ``eventos`` pedidos)."""
    prefixo = str(raiz)
    return [
        caminho
        for evento, caminho in conta
        if caminho.startswith(prefixo) and (not eventos or evento in eventos)
    ]


# ---------------------------------------------------------------------------
# O dono armado nas raízes de mentira
# ---------------------------------------------------------------------------


@pytest.fixture
def raizes(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    """``(entradas, nós)`` de mentira, com o dono do processo armado nelas."""
    nos = tmp_path / "dev"
    entradas = nos / "input"
    entradas.mkdir(parents=True)
    while ode.armado():  # nada herdado de outro teste
        ode.desarmar()
    assert ode.armar(entradas=str(entradas), nos=str(nos)), "o inotify não armou"
    try:
        yield entradas, nos
    finally:
        while ode.armado():
            ode.desarmar()


class _LibcQueFalha:
    """A ``libc`` sem ``inotify``: o ``inotify_init1`` devolve -1."""

    def inotify_init1(self, _flags: int) -> int:
        return -1

    def inotify_add_watch(self, _fd: int, _raiz: bytes, _mascara: int) -> int:
        return -1


# ---------------------------------------------------------------------------
# Régua 1 — o dono do evento
# ---------------------------------------------------------------------------


class TestODonoDoEvento:
    def test_criar_e_apagar_sobe_os_nomes_e_o_chmod_so_as_permissoes(
        self, raizes: tuple[Path, Path]
    ) -> None:
        entradas, _nos = raizes
        dono = ode.dono_armado()
        assert dono is not None
        nomes_0 = dono.geracao(str(entradas), ode.NOMES)
        perm_0 = dono.geracao(str(entradas), ode.PERMISSOES)
        assert nomes_0 is not None and perm_0 is not None

        no = entradas / "event7"
        no.write_text("")
        nomes_1 = dono.geracao(str(entradas), ode.NOMES)
        assert nomes_1 is not None and nomes_1 > nomes_0

        perm_antes = dono.geracao(str(entradas), ode.PERMISSOES)
        os.chmod(no, 0o600)
        assert dono.geracao(str(entradas), ode.NOMES) == nomes_1, (
            "o chmod subiu a geração de NOMES: quem só depende de nomes "
            "acordaria com o próprio esconder do broker"
        )
        perm_depois = dono.geracao(str(entradas), ode.PERMISSOES)
        assert perm_depois is not None and perm_antes is not None
        assert perm_depois > perm_antes

        no.unlink()
        nomes_2 = dono.geracao(str(entradas), ode.NOMES)
        assert nomes_2 is not None and nomes_2 > nomes_1

    def test_em_dev_so_os_hidraw_contam(self, raizes: tuple[Path, Path]) -> None:
        _entradas, nos = raizes
        dono = ode.dono_armado()
        assert dono is not None
        antes = dono.geracao(str(nos), ode.NOMES)
        (nos / "tty9").write_text("")
        assert dono.geracao(str(nos), ode.NOMES) == antes
        (nos / "hidraw3").write_text("")
        depois = dono.geracao(str(nos), ode.NOMES)
        assert depois is not None and antes is not None and depois > antes

    def test_cem_perguntas_sem_evento_nao_abrem_nem_listam_nada(
        self, raizes: tuple[Path, Path]
    ) -> None:
        entradas, nos = raizes
        dono = ode.dono_armado()
        assert dono is not None
        primeira = dono.ficha((str(entradas), ode.NOMES), (str(nos), ode.NOMES))
        with contando() as conta:
            fichas = {
                dono.ficha((str(entradas), ode.NOMES), (str(nos), ode.NOMES))
                for _ in range(100)
            }
        assert fichas == {primeira}
        assert conta == [], f"a pergunta ao dono fez trabalho de disco: {conta[:5]}"

    def test_o_watch_de_dev_input_pergunta_ao_dono_e_nao_lista(
        self, raizes: tuple[Path, Path]
    ) -> None:
        entradas, _nos = raizes
        watch = InputDirWatch(root=str(entradas))
        assert watch.poll() is True  # a primeira é «mudou», como sempre foi
        with contando() as conta:
            mudou = [watch.poll() for _ in range(100)]
        assert not any(mudou)
        assert _sob(conta, entradas) == [], "o watch armado listou a pasta"

        (entradas / "event3").write_text("")
        assert watch.poll() is True
        assert watch.nasceu is True
        assert watch.poll() is False
        (entradas / "event3").unlink()
        assert watch.poll() is True
        assert watch.nasceu is False, "a pasta só perdeu: não há o que procurar"
        os.chmod(entradas, 0o755)
        assert watch.poll() is False, "permissão não é nome"

    def test_o_overflow_sobe_todas_as_geracoes(self, tmp_path: Path) -> None:
        nos = tmp_path / "dev"
        entradas = nos / "input"
        entradas.mkdir(parents=True)
        eventos: list[bytes] = [
            struct.pack("iIII", -1, ode.IN_Q_OVERFLOW, 0, 0),
        ]

        def ler(_fd: int, _n: int) -> bytes:
            if eventos:
                return eventos.pop()
            raise BlockingIOError

        dono = ode.DonoDoEvento(entradas=str(entradas), nos=str(nos), ler=ler)
        assert dono.armar(), "o inotify não armou"
        try:
            # A primeira ficha já drena o overflow: as duas raízes, os três tipos.
            ficha = dono.ficha(
                (str(entradas), ode.NOMES),
                (str(entradas), ode.PERMISSOES),
                (str(nos), ode.NOMES),
                (str(nos), ode.PERMISSOES),
            )
            assert ficha is not None
            assert ficha[1:] == (1, 1, 1, 1), (
                "evento perdido é «tudo mudou», nunca «nada mudou»"
            )
        finally:
            dono.desarmar()

    def test_sem_inotify_nada_se_guarda_e_o_watch_lista_como_antes(
        self, tmp_path: Path
    ) -> None:
        while ode.armado():
            ode.desarmar()
        entradas = tmp_path / "input"
        entradas.mkdir()
        assert ode.armar(entradas=str(entradas), nos=str(tmp_path), libc=_LibcQueFalha()) is False
        assert ode.dono_armado() is None
        watch = InputDirWatch(root=str(entradas))
        watch.poll()
        with contando() as conta:
            for _ in range(100):
                watch.poll()
        assert len(_sob(conta, entradas, "os.listdir")) == 100

    def test_desarmado_o_watch_lista_como_antes(self, tmp_path: Path) -> None:
        while ode.armado():
            ode.desarmar()
        watch = InputDirWatch(root=str(tmp_path))
        watch.poll()
        with contando() as conta:
            for _ in range(100):
                watch.poll()
        assert len(_sob(conta, tmp_path, "os.listdir")) == 100

    def test_desarmar_chama_as_limpezas_e_rearmar_e_outra_epoca(
        self, tmp_path: Path
    ) -> None:
        while ode.armado():
            ode.desarmar()
        entradas = tmp_path / "input"
        entradas.mkdir()
        limpas: list[int] = []

        def limpar() -> None:
            limpas.append(1)

        ode.ao_desarmar(limpar)
        assert ode.armar(entradas=str(entradas), nos=str(tmp_path))
        dono = ode.dono_armado()
        assert dono is not None
        ficha_1 = dono.ficha((str(entradas), ode.NOMES))
        ode.desarmar()
        assert limpas, "desarmar não zerou os caches presos ao dono"
        assert ode.dono_armado() is None
        assert ode.armar(entradas=str(entradas), nos=str(tmp_path))
        try:
            dono_2 = ode.dono_armado()
            assert dono_2 is not None
            assert dono_2.ficha((str(entradas), ode.NOMES)) != ficha_1, (
                "a ficha de um dono re-armado casou com a de antes"
            )
        finally:
            ode.desarmar()

    def test_o_reconnect_loop_de_producao_arma_e_desarma(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Só o caminho sem watch injetado arma; e o `finally` desarma."""
        while ode.armado():
            ode.desarmar()
        nos = tmp_path / "dev"
        (nos / "input").mkdir(parents=True)
        monkeypatch.setattr(ode, "RAIZ_DAS_ENTRADAS", str(nos / "input"))
        monkeypatch.setattr(ode, "RAIZ_DOS_NOS", str(nos))
        daemon = _DaemonDeBancada(_ControleQueContaOArme())
        asyncio.run(_rodar_uma_volta(daemon))
        assert daemon.controller.armado_no_connect == [True]
        assert ode.dono_armado() is None, "o reconnect_loop saiu e o dono ficou armado"

        daemon = _DaemonDeBancada(_ControleQueContaOArme())
        asyncio.run(_rodar_uma_volta(daemon, watch=InputDirWatch(root=str(nos / "input"))))
        assert daemon.controller.armado_no_connect == [False], (
            "o watch injetado é teste: ele não arma o dono do processo"
        )


# ---------------------------------------------------------------------------
# O daemon de bancada do reconnect_loop
# ---------------------------------------------------------------------------


class _ControleQueContaOArme:
    """Sempre online; anota se o dono estava armado a cada `connect()`."""

    def __init__(self) -> None:
        self.armado_no_connect: list[bool] = []
        self.parar: Any = None

    def connect(self) -> None:
        self.armado_no_connect.append(ode.armado())
        if self.parar is not None:
            self.parar()

    def is_connected(self) -> bool:
        return True

    def get_transport(self) -> str:
        return "usb"


class _DaemonDeBancada:
    """Superfície mínima do DaemonProtocol que o `reconnect_loop` toca."""

    def __init__(self, controller: Any) -> None:
        from hefesto_dualsense4unix.core.events import EventBus

        self.controller = controller
        self.bus = EventBus()
        self.config = SimpleNamespace(
            reconnect_backoff_sec=0.01,
            auto_reconnect=True,
            gamepad_emulation_enabled=False,
        )
        self._stop_event: asyncio.Event | None = None
        if hasattr(controller, "parar"):
            controller.parar = self.stop

    def _is_stopping(self) -> bool:
        return self._stop_event is not None and self._stop_event.is_set()

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)

    def _arm_input_grace(self) -> None:
        pass

    def is_native_mode(self) -> bool:
        return False

    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()


async def _rodar_uma_volta(daemon: _DaemonDeBancada, *, watch: Any = None) -> None:
    from hefesto_dualsense4unix.daemon.connection import reconnect_loop

    daemon._stop_event = asyncio.Event()
    await asyncio.wait_for(reconnect_loop(daemon, input_watch=watch), timeout=5.0)  # type: ignore[arg-type]
