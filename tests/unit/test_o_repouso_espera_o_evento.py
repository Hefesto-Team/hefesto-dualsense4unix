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


# ---------------------------------------------------------------------------
# Régua 4 — o adaptador pela geração do hidraw
# ---------------------------------------------------------------------------

#: Quatro controles no rádio (faixa forjada), dois adaptadores forjados.
_UNIQS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
_ADAPTADOR_A = "02:fe:00:00:00:0a"
_ADAPTADOR_B = "02:fe:00:00:00:0b"


def _uevent(uniq: str, phys: str) -> str:
    return (
        "DRIVER=playstation\n"
        "HID_ID=0005:0000054C:00000CE6\n"
        "HID_NAME=DualSense Wireless Controller\n"
        f"HID_PHYS={phys}\n"
        f"HID_UNIQ={uniq}\n"
    )


def _mesa_do_hidraw(sysfs: Path, dev: Path) -> None:
    """12 nós: os quatro físicos no rádio, os quatro vpads e quatro de fora."""
    nos: list[tuple[str, str]] = []
    for i, uniq in enumerate(_UNIQS):
        nos.append((uniq, _ADAPTADOR_A if i < 2 else _ADAPTADOR_B))
    for uniq in _UNIQS:
        nos.append((uniq, "hefesto-vpad"))
    for i in range(4):
        nos.append((f"aa:bb:cc:00:01:0{i}", f"usb-0000:0c:00.3-{i}/input3"))
    for n, (uniq, phys) in enumerate(nos):
        pasta = sysfs / f"hidraw{n}" / "device"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "uevent").write_text(_uevent(uniq, phys))
        (dev / f"hidraw{n}").write_text("")


class TestOAdaptadorPelaGeracaoDoHidraw:
    def test_sessenta_perguntas_leem_os_doze_uevent_uma_vez(self, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

        sysfs = tmp_path / "sys"
        dev = tmp_path / "dev"
        (dev / "input").mkdir(parents=True)
        _mesa_do_hidraw(sysfs, dev)
        dono = ode.DonoDoEvento(entradas=str(dev / "input"), nos=str(dev))
        assert dono.armar()
        try:
            rm._esquecer_o_mapa()
            with contando() as conta:
                respostas = [
                    rm.adaptador_por_uniq(_UNIQS, raiz=str(sysfs), dono=dono)
                    for _ in range(60)
                ]
            lidos = _sob(conta, sysfs, "open")
            assert len(lidos) == 12, f"{len(lidos)} uevent lidos em 60 perguntas"
            assert respostas[-1] == {
                _UNIQS[0]: _ADAPTADOR_A,
                _UNIQS[1]: _ADAPTADOR_A,
                _UNIQS[2]: _ADAPTADOR_B,
                _UNIQS[3]: _ADAPTADOR_B,
            }

            # O controle 1 sai do adaptador A e volta pelo B: o nó dele some e
            # nasce outro (o hidraw12), com o HID_PHYS novo.
            (dev / "hidraw0").unlink()
            (sysfs / "hidraw0" / "device" / "uevent").unlink()
            (sysfs / "hidraw0" / "device").rmdir()
            (sysfs / "hidraw0").rmdir()
            novo = sysfs / "hidraw12" / "device"
            novo.mkdir(parents=True)
            (novo / "uevent").write_text(_uevent(_UNIQS[0], _ADAPTADOR_B))
            (dev / "hidraw12").write_text("")
            assert rm.adaptador_por_uniq(_UNIQS, raiz=str(sysfs), dono=dono)[_UNIQS[0]] == (
                _ADAPTADOR_B
            )
        finally:
            dono.desarmar()
            rm._esquecer_o_mapa()

    def test_com_ler_injetado_e_sem_dono_le_como_hoje(self, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

        while ode.armado():
            ode.desarmar()
        sysfs = tmp_path / "sys"
        dev = tmp_path / "dev"
        dev.mkdir()
        _mesa_do_hidraw(sysfs, dev)
        lidos: list[str] = []

        def ler(caminho: str) -> str:
            lidos.append(caminho)
            return Path(caminho).read_text()

        for _ in range(60):
            rm.adaptador_por_uniq(_UNIQS, raiz=str(sysfs), ler=ler)
        assert len(lidos) == 720

    def test_a_raiz_de_mentira_da_suite_nao_herda_o_mapa(
        self, raizes: tuple[Path, Path], tmp_path: Path
    ) -> None:
        """Dono do processo armado, raiz que não é a de produção: como hoje."""
        from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

        sysfs = tmp_path / "sys"
        _entradas, dev = raizes
        _mesa_do_hidraw(sysfs, dev)
        with contando() as conta:
            for _ in range(5):
                rm.adaptador_por_uniq(_UNIQS, raiz=str(sysfs))
        assert len(_sob(conta, sysfs, "open")) == 60

    def test_o_listar_que_levanta_so_roda_quando_o_mapa_perde(self, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

        sysfs = tmp_path / "sys"
        dev = tmp_path / "dev"
        (dev / "input").mkdir(parents=True)
        _mesa_do_hidraw(sysfs, dev)
        chamadas: list[str] = []

        def listar(raiz: str) -> list[str]:
            chamadas.append(raiz)
            return os.listdir(raiz)

        dono = ode.DonoDoEvento(entradas=str(dev / "input"), nos=str(dev))
        assert dono.armar()
        try:
            rm._esquecer_o_mapa()
            for _ in range(10):
                rm.adaptador_por_uniq(_UNIQS[:1], raiz=str(sysfs), listar=listar, dono=dono)
            assert len(chamadas) == 1
        finally:
            dono.desarmar()
            rm._esquecer_o_mapa()


# ---------------------------------------------------------------------------
# Régua 3 — a descoberta pela geração, na origem
# ---------------------------------------------------------------------------

#: O bitmap `capabilities/key` do nó de gamepad (BTN_SOUTH..BTN_THUMBR).
_TECLAS_DE_GAMEPAD = "7fdb000000000000 0 0 0 0"
_EXTERNO = (0x2DC8, 0x6012)  # vendor/product forjados de um externo


class _MesaDeEntrada:
    """`/dev/input` e o sysfs de mentira, com o dono armado na pasta.

    Os quatro DualSense (dois no cabo, dois no rádio) têm o nó de gamepad
    fechado, como o `0600 root` do físico: a descoberta os classifica pelo
    sysfs, sem abrir. O externo abre pelo caminho, pelo dublê do
    `abrir_input_device`, que publica o que o real publica.
    """

    def __init__(self, raiz: Path, entradas: Path) -> None:
        from tests.unit.sysfs_de_entrada_de_mentira import publicar_no

        self._publicar = publicar_no
        self.sys = raiz / "sys-class-input"
        self.sys.mkdir()
        self.dev = entradas
        self.aberturas: list[str] = []
        self.listagens = 0
        self.falhar_uma_vez: set[str] = set()
        self.externos: dict[str, str] = {}
        numero = 9301
        for i, bus in enumerate((0x03, 0x03, 0x05, 0x05)):
            self.dualsense(f"event{numero}", f"aa:bb:cc:00:00:0{i + 1}", bus)
            numero += 1

    def dualsense(self, evento: str, uniq: str, bus: int) -> str:
        caminho = str(self.dev / evento)
        self._publicar(
            self.sys,
            caminho,
            nome="DualSense Wireless Controller",
            uniq=uniq,
            bus=bus,
            teclas=_TECLAS_DE_GAMEPAD,
        )
        Path(caminho).write_text("")
        os.chmod(caminho, 0o000)
        return caminho

    def externo(self, evento: str, uniq: str, *, modo: int = 0o644) -> str:
        caminho = str(self.dev / evento)
        self._publicar(
            self.sys,
            caminho,
            nome="8BitDo Pro 2",
            uniq=uniq,
            vendor=_EXTERNO[0],
            product=_EXTERNO[1],
            bus=0x03,
            teclas=_TECLAS_DE_GAMEPAD,
        )
        Path(caminho).write_text("")
        os.chmod(caminho, modo)
        self.externos[caminho] = uniq
        return caminho

    def listar(self, *_a: Any) -> list[str]:
        """O `list_devices` da biblioteca: só o nó que o processo abre."""
        self.listagens += 1
        return [
            str(c)
            for c in sorted(self.dev.glob("event*"))
            if os.access(c, os.R_OK | os.W_OK)
        ]

    def abrir(self, caminho: Any, **_kw: Any) -> Any:
        from evdev import ecodes

        caminho = str(caminho)
        self.aberturas.append(caminho)
        if caminho in self.falhar_uma_vez:
            self.falhar_uma_vez.discard(caminho)
            raise OSError(5, "Input/output error", caminho)
        uniq = self.externos[caminho]
        caps = {ecodes.EV_KEY: [ecodes.BTN_SOUTH, ecodes.BTN_EAST], ecodes.EV_ABS: []}
        return SimpleNamespace(
            info=SimpleNamespace(vendor=_EXTERNO[0], product=_EXTERNO[1], bustype=0x03),
            name="8BitDo Pro 2",
            uniq=uniq,
            path=caminho,
            capabilities=lambda **_kw: caps,
            close=lambda: None,
        )


@pytest.fixture
def mesa_de_entrada(
    raizes: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> _MesaDeEntrada:
    pytest.importorskip("evdev")
    if os.geteuid() == 0:  # pragma: no cover - como root o 0000 não fecha nada
        pytest.skip("como root todo nó abre")
    from hefesto_dualsense4unix.core import evdev_reader as er

    entradas, _nos = raizes
    mesa = _MesaDeEntrada(tmp_path, entradas)
    monkeypatch.setattr(er, "SYS_CLASS_INPUT", str(mesa.sys))
    monkeypatch.setattr(er, "DEV_INPUT_DIR", str(entradas))
    socket_do_broker = tmp_path / "broker.sock"
    socket_do_broker.write_text("")
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(socket_do_broker))
    monkeypatch.setattr("evdev.list_devices", mesa.listar)
    monkeypatch.setattr(er, "abrir_input_device", mesa.abrir)
    er._esquecer_o_inventario()
    return mesa


class TestADescobertaPelaGeracao:
    def test_trinta_chamadas_pelas_tres_portas_uma_volta_por_chave(
        self, mesa_de_entrada: _MesaDeEntrada
    ) -> None:
        from hefesto_dualsense4unix.core import evdev_reader as er

        mesa_de_entrada.externo("event9401", "aa:bb:cc:00:02:01")
        with contando() as conta:
            for _ in range(10):
                externos = er.discover_external_gamepads()
                dualsense = er.discover_dualsense_evdevs()
                primeiro = er.find_dualsense_evdev()
        # Duas chaves: (com_sysfs, externos) e (sem sysfs, as duas espécies).
        assert mesa_de_entrada.listagens == 2, (
            f"{mesa_de_entrada.listagens} descobertas em 30 chamadas sem evento"
        )
        assert len(mesa_de_entrada.aberturas) == 2  # o externo, uma vez por chave
        leituras_de_id = [c for c in _sob(conta, mesa_de_entrada.sys, "open") if "/id/" in c]
        assert leituras_de_id, "a primeira volta tem de ler o sysfs"
        assert [e["uniq"] for e in externos] == ["aa:bb:cc:00:02:01"]
        assert len(dualsense) == 4
        assert primeiro is not None

    def test_um_no_que_nasce_descobre_de_novo_e_acha(
        self, mesa_de_entrada: _MesaDeEntrada
    ) -> None:
        from hefesto_dualsense4unix.core import evdev_reader as er

        assert len(er.discover_dualsense_evdevs()) == 4
        mesa_de_entrada.dualsense("event9305", "aa:bb:cc:00:00:05", 0x05)
        assert len(er.discover_dualsense_evdevs()) == 5

    def test_um_no_que_ganha_permissao_sem_nascer_e_achado(
        self, mesa_de_entrada: _MesaDeEntrada
    ) -> None:
        """O udev põe a permissão DEPOIS de o nó nascer: o `IN_ATTRIB` conta."""
        from hefesto_dualsense4unix.core import evdev_reader as er

        caminho = mesa_de_entrada.externo("event9402", "aa:bb:cc:00:02:02", modo=0o000)
        assert er.discover_external_gamepads() == []
        os.chmod(caminho, 0o644)
        assert [e["uniq"] for e in er.discover_external_gamepads()] == ["aa:bb:cc:00:02:02"]

    def test_o_externo_que_falhou_ao_abrir_volta_na_chamada_seguinte(
        self, mesa_de_entrada: _MesaDeEntrada
    ) -> None:
        from hefesto_dualsense4unix.core import evdev_reader as er

        caminho = mesa_de_entrada.externo("event9403", "aa:bb:cc:00:02:03")
        mesa_de_entrada.falhar_uma_vez.add(caminho)
        assert er.discover_external_gamepads() == []
        assert [e["uniq"] for e in er.discover_external_gamepads()] == ["aa:bb:cc:00:02:03"], (
            "o externo que falhou uma vez sumiu até o próximo evento"
        )

    def test_quem_muda_o_inventario_nao_muda_o_seguinte(
        self, mesa_de_entrada: _MesaDeEntrada
    ) -> None:
        from hefesto_dualsense4unix.core import evdev_reader as er

        mesa_de_entrada.externo("event9404", "aa:bb:cc:00:02:04")
        primeira = er.discover_external_gamepads()
        primeira[0]["holders"] = ["steam"]
        primeira.clear()
        segunda = er.discover_external_gamepads()
        assert len(segunda) == 1 and "holders" not in segunda[0]

        er.discover_gamepads(com_sysfs=False)  # a volta que guarda
        gps = er.discover_gamepads(com_sysfs=False)  # a que devolve o guardado
        gps[0].eixos[0] = er.EixoAbsoluto(minimo=1, maximo=2)
        gps.clear()
        de_novo = er.discover_gamepads(com_sysfs=False)
        assert len(de_novo) == 5
        assert all(0 not in gp.eixos for gp in de_novo)

    def test_o_broker_que_volta_poe_o_fisico_fechado_na_volta(
        self, mesa_de_entrada: _MesaDeEntrada, tmp_path: Path
    ) -> None:
        """O socket do broker que some e volta não é evento de `/dev/input`."""
        from hefesto_dualsense4unix.core import evdev_reader as er

        socket_do_broker = tmp_path / "broker.sock"
        socket_do_broker.unlink()
        assert er.discover_dualsense_evdevs() == {}, "sem broker, o nó fechado não tem porta"
        socket_do_broker.write_text("")
        assert len(er.discover_dualsense_evdevs()) == 4, (
            "o broker voltou e o inventário guardado sem ele seguiu respondendo"
        )

    def test_desarmado_cada_chamada_descobre_como_hoje(
        self, mesa_de_entrada: _MesaDeEntrada
    ) -> None:
        from hefesto_dualsense4unix.core import evdev_reader as er

        while ode.armado():
            ode.desarmar()
        for _ in range(10):
            er.discover_dualsense_evdevs()
        assert mesa_de_entrada.listagens == 10


# ---------------------------------------------------------------------------
# Régua 7 — os arquivos da casa pela assinatura do stat
# ---------------------------------------------------------------------------


def _envelhecer(caminho: Path, segundos: float = 100.0) -> None:
    """O arquivo gravado há `segundos`: fora da janela do recém-gravado."""
    import time

    quando = time.time() - segundos
    os.utime(caminho, (quando, quando))


class TestALeituraPelaAssinatura:
    """As duas regras finas, com o relógio de parede injetado."""

    def _leitor(self, relogio: list[float]) -> Any:
        from hefesto_dualsense4unix.utils.leitura_pela_assinatura import (
            LeituraPelaAssinatura,
        )

        lidos: list[str] = []

        def decodificar(caminho: Path) -> str:
            lidos.append(str(caminho))
            return caminho.read_text()

        leitor = LeituraPelaAssinatura(decodificar, relogio=lambda: relogio[0])
        leitor.lidos = lidos  # type: ignore[attr-defined]
        return leitor

    def test_a_gravacao_no_mesmo_segundo_e_vista(self, tmp_path: Path) -> None:
        """O `mtime` em nanossegundos: a segunda gravação no mesmo segundo muda a assinatura."""
        base = 1_900_000_000
        relogio = [float(base + 100)]  # a leitura é bem depois: nada é recém-gravado
        arquivo = tmp_path / "perfil.json"
        leitor = self._leitor(relogio)
        arquivo.write_text("AAAA")
        os.utime(arquivo, ns=(base * 10**9 + 100_000_000, base * 10**9 + 100_000_000))
        assert leitor.ler(arquivo) == "AAAA"
        assert leitor.ler(arquivo) == "AAAA"
        assert len(leitor.lidos) == 1
        with arquivo.open("r+") as fh:  # no lugar: o mesmo inode
            fh.write("BBBB")
        os.utime(arquivo, ns=(base * 10**9 + 500_000_000, base * 10**9 + 500_000_000))
        assert leitor.ler(arquivo) == "BBBB", "a gravação no mesmo segundo não foi vista"

    def test_o_arquivo_recem_gravado_se_rele_ate_envelhecer(self, tmp_path: Path) -> None:
        """Duas gravações do mesmo tamanho com o MESMO `mtime_ns`: a regra do «racy»."""
        base = 1_900_000_000
        mtime = base * 10**9
        relogio = [float(base) + 0.5]  # lida meio segundo depois de gravada
        arquivo = tmp_path / "last_run"
        leitor = self._leitor(relogio)
        arquivo.write_text("appid=1\n")
        os.utime(arquivo, ns=(mtime, mtime))
        assert leitor.ler(arquivo) == "appid=1\n"
        with arquivo.open("r+") as fh:
            fh.write("appid=2\n")
        os.utime(arquivo, ns=(mtime, mtime))  # a mesma assinatura, byte a byte
        assert leitor.ler(arquivo) == "appid=2\n", "a segunda gravação do mesmo tamanho sumiu"
        relogio[0] = float(base) + 10.0
        leitor.ler(arquivo)  # esta leitura já é confiável
        antes = len(leitor.lidos)
        for _ in range(10):
            assert leitor.ler(arquivo) == "appid=2\n"
        assert len(leitor.lidos) == antes

    def test_a_gravacao_durante_a_leitura_nao_se_guarda(self, tmp_path: Path) -> None:
        """O wrapper grava o marker sem trava: a troca no meio da leitura não gruda."""
        from hefesto_dualsense4unix.utils.leitura_pela_assinatura import (
            LeituraPelaAssinatura,
        )

        arquivo = tmp_path / "last_run"
        arquivo.write_text("appid=1\n")
        _envelhecer(arquivo)
        trocar = [True]

        def decodificar(caminho: Path) -> str:
            texto = caminho.read_text()
            if trocar[0]:  # o lançamento regrava o marker logo depois da leitura
                trocar[0] = False
                novo = tmp_path / "last_run.novo"
                novo.write_text("appid=2\n")
                _envelhecer(novo)
                os.replace(novo, caminho)
            return texto

        leitor = LeituraPelaAssinatura(decodificar)
        assert leitor.ler(arquivo) == "appid=1\n"
        assert leitor.ler(arquivo) == "appid=2\n", "a leitura de antes grudou na assinatura nova"

    def test_o_ausente_guarda_ausente_ate_o_stat_achar(self, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.utils.leitura_pela_assinatura import (
            LeituraPelaAssinatura,
        )

        arquivo = tmp_path / "nao-ha.json"
        leituras: list[int] = []

        def decodificar(caminho: Path) -> str:
            leituras.append(1)
            try:
                return caminho.read_text()
            except FileNotFoundError:
                return ""

        leitor = LeituraPelaAssinatura(decodificar)
        for _ in range(10):
            assert leitor.ler(arquivo) == ""
        assert len(leituras) == 1
        arquivo.write_text("x")
        assert leitor.ler(arquivo) == "x"


@pytest.fixture
def perfis(
    raizes: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Doze perfis gravados há 100 s, numa pasta de mentira, com o dono armado."""
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

    pasta = tmp_path / "profiles"
    pasta.mkdir()
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: pasta)
    monkeypatch.setenv(loader.SEED_SKIP_ENV_VAR, "1")
    loader._PERFIS_PELA_ASSINATURA.esquecer()
    for i in range(12):
        loader.save_profile(
            Profile(name=f"perfil{i:02d}", match=MatchCriteria(window_class=[f"jogo{i:02d}"]))
        )
    for arquivo in pasta.glob("*.json"):
        _envelhecer(arquivo)
    return pasta


def _classes(perfil: Any) -> list[str]:
    """As classes de janela do `match` do perfil (o de mentira é sempre `MatchCriteria`)."""
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria

    assert isinstance(perfil.match, MatchCriteria)
    return perfil.match.window_class


def _jsons(conta: list[tuple[str, str]], pasta: Path) -> list[str]:
    return [c for c in _sob(conta, pasta, "open") if c.endswith(".json")]


class TestOsArquivosDaCasa:
    def test_dez_cargas_sem_mudanca_leem_os_perfis_uma_vez(self, perfis: Path) -> None:
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles

        with contando() as conta:
            cargas = [load_all_profiles() for _ in range(10)]
        assert len(_jsons(conta, perfis)) == 12, "os perfis foram relidos sem mudar"
        travas = [c for c in _sob(conta, perfis, "open") if c.endswith(".lock")]
        assert len(travas) == 12, "o FileLock abriu sem haver leitura"
        assert len(_sob(conta, perfis, "os.scandir", "os.listdir")) == 10  # uma por carga
        assert all([p.name for p in c] == [p.name for p in cargas[0]] for c in cargas)

    def test_so_os_perfis_gravados_sao_relidos(self, perfis: Path) -> None:
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles, save_profile

        antes = {p.name: p for p in load_all_profiles()}
        mudado = antes["perfil03"].model_copy(update={"priority": 7})
        save_profile(mudado)  # a gravação atômica, `os.replace`
        no_lugar = perfis / "perfil07.json"
        texto = no_lugar.read_text().replace('"jogo07"', '"jogo77"')
        no_lugar.write_text(texto)  # a gravação no lugar, mesmo inode
        with contando() as conta:
            depois = {p.name: p for p in load_all_profiles()}
        relidos = sorted(Path(c).name for c in _jsons(conta, perfis))
        assert relidos == ["perfil03.json", "perfil07.json"]
        assert depois["perfil03"].priority == 7
        assert _classes(depois["perfil07"]) == ["jogo77"]

    def test_quem_muda_o_perfil_devolvido_nao_muda_a_carga_seguinte(self, perfis: Path) -> None:
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles

        primeira = load_all_profiles()
        _classes(primeira[0]).append("intrusa")
        segunda = load_all_profiles()
        _classes(segunda[0]).append("outra")
        assert _classes(load_all_profiles()[0]) == ["jogo00"]

    def test_desarmado_cada_carga_le_tudo_como_hoje(self, perfis: Path) -> None:
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles

        while ode.armado():
            ode.desarmar()
        with contando() as conta:
            for _ in range(3):
                load_all_profiles()
        assert len(_jsons(conta, perfis)) == 36

    def test_a_lista_de_exclusao_ausente_nao_abre_depois_da_primeira(
        self, raizes: tuple[Path, Path], tmp_path: Path
    ) -> None:
        from hefesto_dualsense4unix.integrations import lista_de_exclusao as lde

        lde._LISTA_PELA_ASSINATURA.esquecer()
        casa = tmp_path / "config"
        with contando() as conta:
            for _ in range(20):
                assert lde.contem("steam_app_1", config_home=casa) is False
        assert len(_sob(conta, casa, "open")) == 1

    def test_o_marcador_do_lancamento_pela_assinatura(
        self, raizes: tuple[Path, Path], tmp_path: Path
    ) -> None:
        from hefesto_dualsense4unix.daemon import launch_env

        launch_env._MARCADORES_PELA_ASSINATURA.esquecer()
        marcador = tmp_path / "last_run"
        marcador.write_text("appid=1599660\nepoch=1900000000\npid=4242\n")
        _envelhecer(marcador)
        with contando() as conta:
            for _ in range(20):
                assert launch_env.read_last_run_marker(tmp_path) == (1599660, 1900000000)
                assert launch_env.read_last_run_pid(tmp_path) == 4242
        assert len(_sob(conta, marcador, "open")) == 1
        marcador.write_text("appid=2497900\nepoch=1900000100\npid=4343\n")
        assert launch_env.read_last_run_marker(tmp_path) == (2497900, 1900000100)


# ---------------------------------------------------------------------------
# Régua 5 — o negativo de /proc vale até o evento, só na pergunta de exibição
# ---------------------------------------------------------------------------

_REAPER = (
    "/home/quem/.steam/ubuntu12_32/reaper SteamLaunch AppId=1599660 -- "
    "/.../proton waitforexitandrun /.../Jogo.exe"
)


class _ProcDeMentira:
    """`/proc` de mentira: o mapa pid → cmdline, e a conta das varreduras."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.daemon import launch_env
        from hefesto_dualsense4unix.integrations import steam_launch_options as slo

        self.mapa: dict[str, str] = {"100": "cosmic-comp", "101": "pipewire"}
        self.varreduras = 0
        self.lancamento = tmp_path / "launch_env"
        self.lancamento.mkdir()
        listar_de_verdade = os.listdir

        def listar(caminho: Any = ".") -> list[str]:
            if str(caminho) == "/proc":
                self.varreduras += 1
                return [*self.mapa, "self", "cpuinfo"]
            return listar_de_verdade(caminho)

        monkeypatch.setattr(os, "listdir", listar)  # o `os` que o módulo usa
        monkeypatch.setattr(slo, "_cmdline_of", lambda pid: self.mapa.get(str(pid), ""))
        monkeypatch.setattr(launch_env, "launch_env_dir", lambda: self.lancamento)
        monkeypatch.setattr(slo, "_agora", lambda: _RELOGIO_DA_FOTO[0])
        launch_env._MARCADORES_PELA_ASSINATURA.esquecer()
        slo.invalidar_varredura_de_proc()

    def lancar(self, appid: int, pid: int) -> None:
        """O wrapper regrava o marker `last_run` (um lançamento novo)."""
        (self.lancamento / "last_run").write_text(
            f"appid={appid}\nepoch=1900000000\npid={pid}\n"
        )


@pytest.fixture
def proc_de_mentira(
    raizes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[_ProcDeMentira]:
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    proc = _ProcDeMentira(monkeypatch, tmp_path)
    yield proc
    slo.invalidar_varredura_de_proc()


_RELOGIO_DA_FOTO: list[float] = [0.0]


def _exibir(agora: float) -> int | None:
    """A pergunta de exibição do poll loop, no instante `agora` do relógio injetado."""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    _RELOGIO_DA_FOTO[0] = agora
    return slo.steam_game_running_appid()


def _recusar(agora: float) -> bool:
    """A pergunta de quem pensa em fechar a Steam, no instante `agora`."""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    _RELOGIO_DA_FOTO[0] = agora
    return slo.steam_game_running()


class TestONegativoDeProc:
    def test_trinta_perguntas_de_exibicao_em_59_s_uma_varredura(
        self, proc_de_mentira: _ProcDeMentira
    ) -> None:

        for t in range(0, 60, 2):
            assert _exibir(float(t)) is None
        assert proc_de_mentira.varreduras == 1

    def test_aos_60_s_varre(self, proc_de_mentira: _ProcDeMentira) -> None:

        _exibir(0.0)
        _exibir(59.0)
        assert proc_de_mentira.varreduras == 1
        _exibir(60.0)
        assert proc_de_mentira.varreduras == 2

    def test_o_marcador_que_muda_varre(self, proc_de_mentira: _ProcDeMentira) -> None:

        _exibir(0.0)
        _exibir(8.0)
        assert proc_de_mentira.varreduras == 1
        proc_de_mentira.lancar(1599660, 4242)
        _exibir(10.0)
        assert proc_de_mentira.varreduras == 2

    def test_invalidar_varre(self, proc_de_mentira: _ProcDeMentira) -> None:
        from hefesto_dualsense4unix.integrations import steam_launch_options as slo

        _exibir(0.0)
        slo.invalidar_varredura_de_proc()
        _exibir(8.0)
        assert proc_de_mentira.varreduras == 2

    def test_a_pergunta_de_recusa_segue_nos_cinco_segundos(
        self, proc_de_mentira: _ProcDeMentira
    ) -> None:
        """O jogo que nasce aos 10 s: a recusa o vê aos 16 s; a exibição, sozinha, no teto."""

        assert _exibir(0.0) is None
        proc_de_mentira.mapa["200"] = _REAPER  # o jogo nasce aos 10 s, fora do lançador
        assert _exibir(12.0) is None  # o preço declarado
        assert _recusar(16.0) is True, (
            "a pergunta de quem pensa em fechar a Steam leu o negativo longo"
        )

    def test_so_a_exibicao_ve_o_jogo_fora_do_lancador_no_teto(
        self, proc_de_mentira: _ProcDeMentira
    ) -> None:
        """O caso do item 4, dito em voz alta: backend cego e sem lançador, até 60 s."""

        assert _exibir(0.0) is None
        proc_de_mentira.mapa["200"] = _REAPER
        vistos = [_exibir(float(t)) for t in range(10, 60, 2)]
        assert vistos == [None] * len(vistos)
        assert _exibir(60.0) == 1599660

    def test_outra_janela_em_foco_invalida_o_negativo(
        self, proc_de_mentira: _ProcDeMentira
    ) -> None:
        from unittest.mock import MagicMock

        from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher

        # Pelo `_tick` do autoswitch, o caminho do produto, e não pela função
        # auxiliar: a régua que chama o auxiliar direto passa com o tique que
        # nunca o chama (medido na conferência).
        sw = AutoSwitcher(manager=MagicMock(), window_reader=lambda: {})
        sw._tick({"wm_class": "firefox", "pid": 10}, 0.0)
        _exibir(0.0)
        sw._tick({"wm_class": "firefox", "pid": 10}, 4.0)
        _exibir(4.0)
        sw._tick({"wm_class": "", "pid": 0}, 6.0)  # cega
        _exibir(6.0)
        assert proc_de_mentira.varreduras == 1
        proc_de_mentira.mapa["200"] = _REAPER
        sw._tick({"wm_class": "steam_app_1599660", "pid": 200}, 8.0)
        assert _exibir(8.0) == 1599660

    def test_desarmado_a_exibicao_segue_nos_cinco_segundos(
        self, proc_de_mentira: _ProcDeMentira
    ) -> None:

        while ode.armado():
            ode.desarmar()
        for t in range(0, 60, 2):
            _exibir(float(t))
        assert proc_de_mentira.varreduras == 10


# ---------------------------------------------------------------------------
# Régua 6 — a volta de 30 s pelo evento
# ---------------------------------------------------------------------------

_QUATRO = ("aabbcc000001", "aabbcc000002", "aabbcc000003", "aabbcc000004")


class _BrokerDeMentira:
    """Esconde com `chmod`, como o broker: cada rehide mexe na firma do nó."""

    def __init__(self) -> None:
        self.hides: list[str] = []

    def hide(self, no: str) -> None:
        import time

        time.sleep(0.02)  # passa do tique do relógio do sistema de arquivos
        os.chmod(no, 0o000)
        self.hides.append(no)


class _ControleDoRepouso:
    """Os quatro no rádio, sempre online; o `connect()` conta."""

    def __init__(self, dev: Path) -> None:
        self.connects = 0
        self.nos = {uniq: str(dev / f"hidraw{i}") for i, uniq in enumerate(_QUATRO)}

    def connect(self) -> None:
        self.connects += 1

    def is_connected(self) -> bool:
        return True

    def get_transport(self) -> str:
        return "bt"

    def nos_hidraw_por_uniq(self) -> dict[str, str]:
        return dict(self.nos)

    def hidraw_path(self, uniq: str | None = None) -> str | None:
        return self.nos.get(uniq or _QUATRO[0])


class _DaemonDoRepouso:
    """O que o `reconnect_loop` e o rehide real usam, com o broker de mentira."""

    def __init__(self, controller: _ControleDoRepouso, *, nativo: bool = False) -> None:
        from hefesto_dualsense4unix.core.events import EventBus

        self.controller = controller
        self.bus = EventBus()
        self.config = SimpleNamespace(
            reconnect_backoff_sec=0.01, auto_reconnect=True, gamepad_emulation_enabled=True
        )
        self._stop_event: asyncio.Event | None = None
        self._nativo = nativo
        self._gamepad_device = object()  # o vpad do P1, vivo
        self._coop_manager = SimpleNamespace(
            _players={u: SimpleNamespace(vpad=object()) for u in _QUATRO[1:]}
        )
        self._hidraw_broker_client = _BrokerDeMentira()

    def _is_stopping(self) -> bool:
        return self._stop_event is not None and self._stop_event.is_set()

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)

    def _arm_input_grace(self) -> None:
        pass

    def is_native_mode(self) -> bool:
        return self._nativo

    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()


class _VoltaDeMentira:
    """O relógio de mentira do laço: cada espera avança o relógio sem dormir.

    `agenda` são os eventos de fora, cada um no seu segundo; as voltas anotam o
    segundo de cada `connect()`, de cada rehide e de cada sonda forçada.
    """

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        daemon: _DaemonDoRepouso,
        *,
        ate: float,
        agenda: dict[float, Any] | None = None,
    ) -> None:
        import hefesto_dualsense4unix.daemon.connection as cx
        from hefesto_dualsense4unix.integrations import hidraw_broker_client

        self.daemon = daemon
        self.agora = 0.0
        self.ate = ate
        self.agenda = dict(sorted((agenda or {}).items()))
        self.sondas: list[float] = []
        self.connects: list[float] = []
        self.rehides: list[float] = []
        controle = daemon.controller
        connect_real = controle.connect

        def connect() -> None:
            self.connects.append(self.agora)
            connect_real()

        controle.connect = connect  # type: ignore[method-assign]
        broker = daemon._hidraw_broker_client
        hide_real = broker.hide

        def hide(no: str) -> None:
            if not self.rehides or self.rehides[-1] != self.agora:
                self.rehides.append(self.agora)
            hide_real(no)

        broker.hide = hide  # type: ignore[method-assign]

        async def esperar(_daemon: Any, segundos: float) -> None:
            self.agora += segundos
            while self.agenda and next(iter(self.agenda)) <= self.agora:
                quando = next(iter(self.agenda))
                self.agenda.pop(quando)()
            if self.agora >= self.ate:
                daemon.stop()
            await asyncio.sleep(0)

        async def sondar(_daemon: Any, *, forcar: bool) -> int:
            if forcar:
                self.sondas.append(self.agora)
            return 0

        async def nada(*_a: Any, **_kw: Any) -> int:
            return 0

        monkeypatch.setattr(cx, "_wait_or_stop", esperar)
        monkeypatch.setattr(cx, "vigiar_escritor_cru", sondar)
        monkeypatch.setattr(cx, "vigiar_o_sequestro", nada)
        monkeypatch.setattr(cx, "carimbar_o_nascimento", nada)
        monkeypatch.setattr(cx, "vigiar_o_cabo_em_espera", nada)
        monkeypatch.setattr(hidraw_broker_client, "broker_executor_for", lambda _d: None)

    def rodar(self) -> None:
        from hefesto_dualsense4unix.daemon.connection import reconnect_loop

        async def _rodar() -> None:
            self.daemon._stop_event = asyncio.Event()
            await asyncio.wait_for(reconnect_loop(self.daemon), timeout=60.0)  # type: ignore[arg-type]

        asyncio.run(_rodar())


@pytest.fixture
def mesa_do_rádio(raizes: tuple[Path, Path]) -> tuple[Path, Path]:
    """Os quatro `hidraw` do rádio, escondidos (0000), na `/dev` de mentira."""
    entradas, dev = raizes
    for i in range(len(_QUATRO)):
        no = dev / f"hidraw{i}"
        no.write_text("")
        os.chmod(no, 0o000)
    return entradas, dev


class TestAVoltaPeloEvento:
    def test_trezentos_segundos_sem_evento_uma_volta(
        self, mesa_do_rádio: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _entradas, dev = mesa_do_rádio
        daemon = _DaemonDoRepouso(_ControleDoRepouso(dev))
        volta = _VoltaDeMentira(monkeypatch, daemon, ate=299.0)
        volta.rodar()
        assert volta.connects == [0.0], f"voltas sem evento: {volta.connects}"
        assert volta.rehides == [0.0]
        assert volta.sondas == [0.0]
        assert len(daemon._hidraw_broker_client.hides) == 4, "o rehide é dos quatro"

    def test_no_teto_a_volta_roda(
        self, mesa_do_rádio: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import hefesto_dualsense4unix.daemon.connection as cx

        _entradas, dev = mesa_do_rádio
        daemon = _DaemonDoRepouso(_ControleDoRepouso(dev))
        volta = _VoltaDeMentira(monkeypatch, daemon, ate=cx.TETO_DA_VOLTA_PELO_EVENTO_SEC + 1)
        volta.rodar()
        assert volta.connects == [0.0, cx.TETO_DA_VOLTA_PELO_EVENTO_SEC]

    def test_um_no_que_nasce_acorda_a_volta_na_fatia_seguinte(
        self, mesa_do_rádio: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import hefesto_dualsense4unix.daemon.connection as cx

        entradas, dev = mesa_do_rádio
        daemon = _DaemonDoRepouso(_ControleDoRepouso(dev))
        volta = _VoltaDeMentira(
            monkeypatch,
            daemon,
            ate=100.0,
            agenda={21.0: lambda: (entradas / "event40").write_text("")},
        )
        volta.rodar()
        assert len(volta.connects) == 2
        segunda = volta.connects[1]
        assert 21.0 <= segunda <= 21.0 + cx.RECONNECT_HOTPLUG_POLL_INTERVAL_SEC
        assert volta.rehides == volta.connects
        assert volta.sondas == volta.connects

    def test_o_hidraw_que_nasce_em_dev_acorda_a_volta(
        self, mesa_do_rádio: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _entradas, dev = mesa_do_rádio
        daemon = _DaemonDoRepouso(_ControleDoRepouso(dev))
        volta = _VoltaDeMentira(
            monkeypatch, daemon, ate=100.0, agenda={31.0: lambda: (dev / "hidraw9").write_text("")}
        )
        volta.rodar()
        assert len(volta.connects) == 2 and 31.0 <= volta.connects[1] <= 33.0

    def test_a_firma_de_um_no_escondido_que_muda_roda_o_rehide(
        self, mesa_do_rádio: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ACL que o udev devolve ao físico: um `chmod` de fora, no nó."""
        _entradas, dev = mesa_do_rádio
        daemon = _DaemonDoRepouso(_ControleDoRepouso(dev))

        def devolver_a_acl() -> None:
            import time

            time.sleep(0.02)
            os.chmod(dev / "hidraw2", 0o000)

        volta = _VoltaDeMentira(monkeypatch, daemon, ate=100.0, agenda={41.0: devolver_a_acl})
        volta.rodar()
        assert len(volta.rehides) == 2 and 41.0 <= volta.rehides[1] <= 43.0

    def test_a_acl_devolvida_ao_no_de_entrada_roda_o_rehide(
        self, mesa_do_rádio: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O `udevadm trigger` de `input` devolve a ACL só aos nós de entrada.

        O rehide esconde o `hidraw` E os nós de entrada do físico (o
        `fechar_entradas` do broker), e a firma do `hidraw` não muda quando só o
        nó de entrada volta a abrir. É o `IN_ATTRIB` de `/dev/input` (a geração
        de permissões, anotada depois da rodada) que acorda a volta.
        """
        entradas, dev = mesa_do_rádio
        no_de_entrada = entradas / "event7"
        no_de_entrada.write_text("")
        os.chmod(no_de_entrada, 0o600)
        daemon = _DaemonDoRepouso(_ControleDoRepouso(dev))

        def devolver_a_acl() -> None:
            os.chmod(no_de_entrada, 0o660)

        volta = _VoltaDeMentira(monkeypatch, daemon, ate=100.0, agenda={41.0: devolver_a_acl})
        volta.rodar()
        assert len(volta.rehides) == 2 and 41.0 <= volta.rehides[1] <= 43.0, volta.rehides

    def test_o_barramento_hid_que_muda_roda_a_volta(
        self, mesa_do_rádio: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import hefesto_dualsense4unix.daemon.connection as cx

        _entradas, dev = mesa_do_rádio
        daemon = _DaemonDoRepouso(_ControleDoRepouso(dev))
        volta = _VoltaDeMentira(monkeypatch, daemon, ate=100.0)
        monkeypatch.setattr(cx, "_o_barramento_hid_mudou", lambda _d: volta.agora == 51.0 + 1.0)
        volta.rodar()
        assert volta.connects == [0.0, 52.0]

    def test_no_modo_nativo_nenhum_rehide(
        self, mesa_do_rádio: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _entradas, dev = mesa_do_rádio
        daemon = _DaemonDoRepouso(_ControleDoRepouso(dev), nativo=True)
        volta = _VoltaDeMentira(monkeypatch, daemon, ate=299.0)
        volta.rodar()
        assert volta.rehides == []
        assert volta.connects == [0.0]

    def test_desarmado_a_volta_de_trinta_segundos_de_sempre(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem `inotify` (o dono não arma): o relógio de 30 s de hoje."""
        while ode.armado():
            ode.desarmar()
        dev = tmp_path / "dev"
        (dev / "input").mkdir(parents=True)
        monkeypatch.setattr(ode, "RAIZ_DAS_ENTRADAS", str(dev / "input"))
        monkeypatch.setattr(ode, "RAIZ_DOS_NOS", str(dev))
        monkeypatch.setattr(ode, "_libc_do_processo", lambda: _LibcQueFalha())
        daemon = _DaemonDoRepouso(_ControleDoRepouso(dev))
        volta = _VoltaDeMentira(monkeypatch, daemon, ate=299.0)
        volta.rodar()
        assert len(volta.connects) == 10


# ---------------------------------------------------------------------------
# Régua 2 — o nó do vpad pela geração (a família 1, o `state_full`)
# ---------------------------------------------------------------------------

import time

from hefesto_dualsense4unix.daemon import ipc_handlers as ipc_mod
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.integrations import no_do_vpad as no_mod
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    VPAD_HID_PHYS,
    player_mac,
)
from hefesto_dualsense4unix.integrations.uinput_gamepad import XBOX360_NAME

#: A mesa de 29/09: 54 nós de entrada, quatro deles por vpad `uhid` (o
#: touchpad, os sensores, o gamepad e o «Headset Jack», com o mesmo `uniq`).
_NOS_NA_MESA = 54
_NOS_POR_VPAD = (" Touchpad", " Motion Sensors", "", " Headset Jack")


def _nome_do_vpad(jogador: int) -> str:
    return f"DualSense Wireless Controller (Hefesto P{jogador})"


class _MesaDoVpad:
    """`/sys/class/input` e `/dev` de mentira, no formato do kernel.

    `/sys/class/input/eventN/device` aponta para `<HID>/input/inputM`, e o
    `hidraw` do vpad mora em `<HID>/hidraw/`, com o nó em `/dev`. O `/dev` é
    o mesmo que o dono do evento olha (o fixture `raizes`).
    """

    def __init__(self, tmp_path: Path, entradas: Path, nos: Path) -> None:
        self.class_input = tmp_path / "sys" / "class" / "input"
        self.devices = tmp_path / "sys" / "devices"
        self.class_input.mkdir(parents=True)
        self.entradas = entradas
        self.nos = nos
        self._proximo = 0

    def _no(self, dir_pai: Path, nome: str, uniq: str, numero: int | None = None) -> str:
        if numero is None:
            numero = self._proximo
        self._proximo = max(self._proximo, numero + 1)
        dir_input = dir_pai / "input" / f"input{numero}"
        dir_input.mkdir(parents=True)
        (dir_input / "name").write_text(nome + "\n")
        (dir_input / "uniq").write_text(uniq + "\n")
        evento = f"event{numero}"
        (self.class_input / evento).mkdir()
        os.symlink(dir_input, self.class_input / evento / "device")
        (self.entradas / evento).write_text("")
        return evento

    def outro(self, rotulo: str) -> str:
        return self._no(self.devices / "platform" / rotulo, f"Teclado {rotulo}", "")

    def vpad(self, jogador: int, *, hidraw: str | None, primeiro: int | None = None) -> Path:
        dir_hid = self.devices / "virtual" / "misc" / "uhid" / f"0003:054C:0DF2.{jogador:04X}"
        dir_hid.mkdir(parents=True, exist_ok=True)
        (dir_hid / "uevent").write_text(
            f"HID_PHYS={VPAD_HID_PHYS}\nHID_UNIQ={player_mac(jogador)}\n"
        )
        for i, sufixo in enumerate(_NOS_POR_VPAD):
            self._no(
                dir_hid,
                _nome_do_vpad(jogador) + sufixo,
                player_mac(jogador),
                None if primeiro is None else primeiro + i,
            )
        if hidraw is not None:
            self.hidraw(dir_hid, hidraw)
        return dir_hid

    def uinput(self, nome: str) -> str:
        """Um pad `uinput` (o modo Xbox): evdev puro, sem `uniq` e sem hidraw."""
        return self._no(self.devices / "virtual", nome, "")

    def hidraw(self, dir_hid: Path, hidraw: str) -> None:
        (dir_hid / "hidraw" / hidraw).mkdir(parents=True)
        (self.nos / hidraw).write_text("")

    def tirar_o_vpad(self, jogador: int) -> None:
        for pasta in list(self.class_input.iterdir()):
            if player_mac(jogador) in (pasta / "device" / "uniq").read_text():
                (self.entradas / pasta.name).unlink()
                (pasta / "device").unlink()
                pasta.rmdir()

    def gamepad(self, jogador: int) -> str:
        for pasta in self.class_input.iterdir():
            if (pasta / "device" / "name").read_text().strip() == _nome_do_vpad(jogador):
                return str(self.entradas / pasta.name)
        raise AssertionError("o gamepad do vpad não está na mesa")


class _Relogio:
    """O `time` do `ipc_handlers` com o `monotonic` de mentira; o resto, o de verdade."""

    def __init__(self) -> None:
        self.agora = 1_000.0

    def monotonic(self) -> float:
        return self.agora

    def __getattr__(self, nome: str) -> Any:
        return getattr(time, nome)


class _SoOCache(IpcHandlersMixin):
    """O mixin com o cache do nó: `_no_do_vpad_cached` não pede mais nada."""

    def __init__(self) -> None:
        pass


@pytest.fixture
def mesa_do_vpad(
    tmp_path: Path, raizes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> _MesaDoVpad:
    """A mesa de 29/09 (quatro vpads, 54 nós), com o produto apontado para ela."""
    entradas, nos = raizes
    mesa = _MesaDoVpad(tmp_path, entradas, nos)
    for jogador in range(1, 5):
        mesa.vpad(jogador, hidraw=f"hidraw{jogador}")
    while mesa._proximo < _NOS_NA_MESA:
        mesa.outro(f"k{mesa._proximo}")
    monkeypatch.setattr(no_mod, "RAIZ_CLASS_INPUT", str(mesa.class_input))
    monkeypatch.setattr(no_mod, "RAIZ_DEV_INPUT", str(entradas))
    monkeypatch.setattr(no_mod, "RAIZ_DEV", str(nos))
    return mesa


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> _Relogio:
    r = _Relogio()
    monkeypatch.setattr(ipc_mod, "time", r)
    return r


def _a_bandeja_pergunta(h: _SoOCache, relogio: _Relogio, voltas: int) -> list[dict[str, Any]]:
    """`voltas` perguntas da bandeja (uma a cada 3 s), os quatro vpads em cada."""
    blocos: list[dict[str, Any]] = []
    for _ in range(voltas):
        for jogador in range(1, 5):
            blocos.append(h._no_do_vpad_cached(player_mac(jogador), _nome_do_vpad(jogador)))
        relogio.agora += 3.0
    return blocos


def _varreduras(conta: list[tuple[str, str]], mesa: _MesaDoVpad) -> int:
    """Uma varredura é uma listagem de `/sys/class/input` (o `_candidatos`)."""
    return sum(
        1 for evento, caminho in conta
        if evento == "os.listdir" and caminho == str(mesa.class_input)
    )


class TestONoDoVpadPelaGeracao:
    def test_quarenta_perguntas_em_120_s_varrem_uma_vez_por_vpad(
        self, mesa_do_vpad: _MesaDoVpad, relogio: _Relogio
    ) -> None:
        """A sonda de 29/09: 80 varreduras e 4.320 `uniq` por minuto, por relógio.

        MORDIDA: devolva o TTL de 2 s ao caminho armado, e as 40 perguntas dos
        quatro vpads fazem 160 varreduras.
        """
        h = _SoOCache()
        with contando() as conta:
            blocos = _a_bandeja_pergunta(h, relogio, 40)
        assert _varreduras(conta, mesa_do_vpad) == 4
        uniqs = _sob(conta, mesa_do_vpad.class_input, "open")
        assert sum(c.endswith("/uniq") for c in uniqs) == 4 * _NOS_NA_MESA
        assert blocos[-4]["evdev"] == mesa_do_vpad.gamepad(1)
        assert blocos[-4]["hidraw"] == str(mesa_do_vpad.nos / "hidraw1")

    def test_um_no_que_nasce_varre_de_novo(
        self, mesa_do_vpad: _MesaDoVpad, relogio: _Relogio
    ) -> None:
        h = _SoOCache()
        _a_bandeja_pergunta(h, relogio, 1)
        with contando() as conta:
            _a_bandeja_pergunta(h, relogio, 5)
        assert _varreduras(conta, mesa_do_vpad) == 0
        mesa_do_vpad.outro("novo")
        with contando() as conta:
            _a_bandeja_pergunta(h, relogio, 5)
        assert _varreduras(conta, mesa_do_vpad) == 4

    def test_o_vpad_recriado_com_outro_event_e_o_no_novo(
        self, mesa_do_vpad: _MesaDoVpad, relogio: _Relogio
    ) -> None:
        h = _SoOCache()
        antes = _a_bandeja_pergunta(h, relogio, 1)[0]
        mesa_do_vpad.tirar_o_vpad(1)
        mesa_do_vpad.vpad(1, hidraw=None, primeiro=200)
        depois = h._no_do_vpad_cached(player_mac(1), _nome_do_vpad(1))
        assert depois["evdev"] == str(mesa_do_vpad.entradas / "event202") != antes["evdev"]
        assert depois["ino"] == os.stat(mesa_do_vpad.entradas / "event202").st_ino

    def test_o_hidraw_que_nasce_depois_da_entrada_chega_na_pergunta_seguinte(
        self, mesa_do_vpad: _MesaDoVpad, relogio: _Relogio
    ) -> None:
        """O `hid_connect` registra a entrada antes do hidraw.

        MORDIDA: tire a geração dos `hidraw*` de `/dev` da ficha, e o vpad fica
        com `hidraw: None` até o próximo nó de entrada.
        """
        h = _SoOCache()
        _a_bandeja_pergunta(h, relogio, 1)
        dir_hid = mesa_do_vpad.vpad(5, hidraw=None)
        sem = h._no_do_vpad_cached(player_mac(5), _nome_do_vpad(5))
        assert sem["evdev"] is not None and sem["hidraw"] is None
        relogio.agora += 3.0
        mesa_do_vpad.hidraw(dir_hid, "hidraw5")
        com = h._no_do_vpad_cached(player_mac(5), _nome_do_vpad(5))
        assert com["hidraw"] == str(mesa_do_vpad.nos / "hidraw5")

    def test_o_dono_de_outra_raiz_nao_prende_o_no(
        self, mesa_do_vpad: _MesaDoVpad, relogio: _Relogio, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """O dono olha um `/dev`, e a varredura usa outro: nada se prende.

        MORDIDA: pergunte ao dono pelas raízes DELE (`dono.raiz_das_entradas`),
        e não pelas da varredura, e o vpad que nasce no `/dev` que o dono não
        olha fica «desconhecido» para sempre.
        """
        outro_dev = tmp_path / "outro" / "dev"
        (outro_dev / "input").mkdir(parents=True)
        outra = _MesaDoVpad(tmp_path / "outro", outro_dev / "input", outro_dev)
        monkeypatch.setattr(no_mod, "RAIZ_CLASS_INPUT", str(outra.class_input))
        monkeypatch.setattr(no_mod, "RAIZ_DEV_INPUT", str(outro_dev / "input"))
        monkeypatch.setattr(no_mod, "RAIZ_DEV", str(outro_dev))
        h = _SoOCache()
        assert h._no_do_vpad_cached(player_mac(1), _nome_do_vpad(1))["evdev"] is None
        outra.vpad(1, hidraw="hidraw1")
        relogio.agora += 3.0
        assert h._no_do_vpad_cached(player_mac(1), _nome_do_vpad(1))["evdev"] is not None

    def test_o_no_que_nasce_durante_a_varredura_chega_na_pergunta_seguinte(
        self, mesa_do_vpad: _MesaDoVpad, relogio: _Relogio,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A ficha se anota ANTES da varredura (`DonoDoEvento.ficha`).

        O hidraw do P5 nasce enquanto a primeira pergunta ainda varre (depois
        de ela ter lido a pasta `hidraw/`). Com a ficha de antes, o evento a
        muda, e a pergunta seguinte varre de novo e acha o nó.
        MORDIDA: anote a ficha DEPOIS do `resolver_no_do_vpad`, e o P5 fica com
        `hidraw: None` até o próximo nó nascer.
        """
        h = _SoOCache()
        dir_hid = mesa_do_vpad.vpad(5, hidraw=None)
        real = no_mod.resolver_no_do_vpad

        def varre_e_o_no_nasce(**kw: Any) -> dict[str, Any]:
            bloco = real(**kw)
            mesa_do_vpad.hidraw(dir_hid, "hidraw5")
            return bloco

        monkeypatch.setattr(ipc_mod, "resolver_no_do_vpad", varre_e_o_no_nasce)
        sem = h._no_do_vpad_cached(player_mac(5), _nome_do_vpad(5))
        assert sem["evdev"] is not None and sem["hidraw"] is None
        monkeypatch.setattr(ipc_mod, "resolver_no_do_vpad", real)
        relogio.agora += 3.0
        com = h._no_do_vpad_cached(player_mac(5), _nome_do_vpad(5))
        assert com["hidraw"] == str(mesa_do_vpad.nos / "hidraw5")

    def test_o_pad_do_xbox_casa_pelo_nome_e_o_segundo_desfaz_a_resposta(
        self, mesa_do_vpad: _MesaDoVpad, relogio: _Relogio
    ) -> None:
        """O modo Xbox: o pad `uinput` não tem `uniq`, e casa pelo nome.

        Uma varredura em 40 perguntas. Quando o pad do P2 nasce com o MESMO
        nome, a pergunta seguinte do P1 é «não sei» (nada diz qual nó é de
        quem), e não o nó guardado.
        MORDIDA: tire a geração de `/dev/input` da ficha, e o P1 segue com o nó
        guardado depois que o P2 nasceu.
        """
        h = _SoOCache()
        evento = mesa_do_vpad.uinput(XBOX360_NAME)
        blocos: list[dict[str, Any]] = []
        with contando() as conta:
            for _ in range(40):
                blocos.append(h._no_do_vpad_cached(None, XBOX360_NAME))
                relogio.agora += 3.0
        assert _varreduras(conta, mesa_do_vpad) == 1
        assert blocos[-1]["evdev"] == str(mesa_do_vpad.entradas / evento)
        assert blocos[-1]["hidraw"] is None
        mesa_do_vpad.uinput(XBOX360_NAME)
        assert h._no_do_vpad_cached(None, XBOX360_NAME) == no_mod.NO_DESCONHECIDO

    def test_desarmado_o_ttl_de_sempre(
        self, mesa_do_vpad: _MesaDoVpad, relogio: _Relogio
    ) -> None:
        """Sem o dono (a janela, a CLI): cada pergunta a 3 s varre, como antes."""
        while ode.armado():
            ode.desarmar()
        h = _SoOCache()
        with contando() as conta:
            _a_bandeja_pergunta(h, relogio, 40)
        assert _varreduras(conta, mesa_do_vpad) == 4 * 40


class _VpadDoStateFull:
    """O que o `per_vpad` do `state_full` lê de um vpad `uhid`."""

    def __init__(self, jogador: int) -> None:
        self.backend = "uhid"
        self.player = jogador
        self.mac = player_mac(jogador)
        self.name = _nome_do_vpad(jogador)
        self.game_open = False


class _HandlersDoStateFull(IpcHandlersMixin):
    def __init__(self, daemon: Any) -> None:
        self.daemon = daemon
        self.store = daemon.store
        self.controller = daemon.controller


async def test_o_state_full_da_bandeja_nao_varre_a_cada_pergunta(
    mesa_do_vpad: _MesaDoVpad, relogio: _Relogio, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O caminho de verdade: a bandeja pede o `state_full` a cada 3 s.

    Dois jogadores (o P1 pelo `_gamepad_device`, o P2 pelo co-op), vinte
    `state_full` em 60 s de relógio de mentira: duas varreduras, na primeira.
    MORDIDA: a mesma do TTL (40 varreduras).
    """
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
    from hefesto_dualsense4unix.testing import FakeController
    from hefesto_dualsense4unix.utils import session

    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    daemon = Daemon(controller=FakeController(transport="usb"))
    daemon.config.coop_enabled = True
    daemon._gamepad_device = _VpadDoStateFull(1)
    mgr = CoopManager(daemon)
    mgr._players["aabbcc000002"] = _SecondaryPlayer(
        identity="aabbcc000002",
        evdev_path="/dev/input/event99",
        reader=SimpleNamespace(grab_state="held"),  # type: ignore[arg-type]
        player_index=2,
        vpad=_VpadDoStateFull(2),  # type: ignore[arg-type]
    )
    daemon._coop_manager = mgr
    h = _HandlersDoStateFull(daemon)
    with contando() as conta:
        for _ in range(20):
            cheio = await h._handle_daemon_state_full({})
            relogio.agora += 3.0
    assert _varreduras(conta, mesa_do_vpad) == 2
    blocos = {b["player"]: b for b in cheio["rumble_ff"]["per_vpad"]}
    assert blocos[1]["evdev"] == mesa_do_vpad.gamepad(1)
    assert blocos[2]["evdev"] == mesa_do_vpad.gamepad(2)
