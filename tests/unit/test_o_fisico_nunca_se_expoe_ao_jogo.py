"""O físico nunca se expõe ao jogo (O-FISICO-NUNCA-SE-EXPOE-AO-JOGO-QUE-VESTE-O-COMUM-01).

A causa, provada no aparelho em 23/10/2026 (sessão G2, MMJ aberto): o handle de controle do daemon
abria o físico por caminho, dentro de um ``with exposicao(no)``. A ACL do usuário no nó do ``/dev``
por milissegundos é um ``IN_ATTRIB``, o ``winebus`` do Proton refaz o ``maybe_add_devnode`` e abre o
``hidraw``, e o fd dele sobrevive ao ``desexpor``.

A cura: o broker abre o nó (ele é root) e passa o fd por ``SCM_RIGHTS``; o handle lê e escreve
nesse fd. O nó do ``/dev`` nunca ganha permissão de usuário.

As réguas rodam o broker DE VERDADE (``BrokerState`` e ``Broker`` sobre um socket), o cliente DE
VERDADE, o abridor que o lifecycle injeta e o ``_PinnedPyDualSense`` de verdade. Só o fs é dublê:
o ``restore`` que ele grava é a ACL do usuário no nó, e o «hidraw» é um ``SOCK_SEQPACKET``, que
guarda a fronteira de cada report como o hidraw guarda. O ``hidapi.Device`` vira um dublê que
recusa: nenhuma régua abre nó de verdade.
"""
from __future__ import annotations

import contextlib
import os
import socket
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.broker.hidraw_broker import Broker, BrokerState
from hefesto_dualsense4unix.core import backend_pydualsense as backend
from hefesto_dualsense4unix.integrations import hidraw_broker_client as cli

#: Nós que não existem nesta máquina: o caminho por ``hidapi`` nunca acharia um aparelho do usuário.
NOS = ("/dev/hidraw90", "/dev/hidraw91", "/dev/hidraw92", "/dev/hidraw93")

#: O primeiro report de cada transporte: o ``determineConnectionType`` decide pelo tamanho.
REPORT_DO_CABO = bytes([0x01, 0x80, 0x80, 0x80, 0x80, 0, 0, 0, 0x08]) + bytes(55)
REPORT_DO_RADIO = bytes([0x31, 0x00, 0x80, 0x80, 0x80, 0x80, 0, 0, 0, 0x08]) + bytes(68)


class FsQueGrava:
    """O fs do broker: grava todo ato e serve, no ``open_node``, a ponta «física» do nó."""

    def __init__(self) -> None:
        self.atos: list[tuple[str, str]] = []
        self.pontas: dict[str, socket.socket] = {}
        self.aparelhos: dict[str, socket.socket] = {}

    def ligar(self, no: str) -> socket.socket:
        fisico, aparelho = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        aparelho.settimeout(3.0)
        self.pontas[no] = fisico
        self.aparelhos[no] = aparelho
        return aparelho

    def hide(self, node: str, base: str) -> None:
        self.atos.append(("hide", node))

    def restore(self, node: str, base: str, uid: int) -> None:
        self.atos.append(("restore", node))

    def is_exposed_to(self, node: str, uid: int) -> bool:
        return any(ato == ("restore", node) for ato in self.atos)

    def open_node(self, node: str, base: str) -> int:
        self.atos.append(("open_node", node))
        return os.dup(self.pontas[node].fileno())

    def soltar_as_pontas(self) -> None:
        """A régua não segura a ponta física: o fd do handle fica sendo o único."""
        for ponta in self.pontas.values():
            ponta.close()

    def fechar(self) -> None:
        for sock in (*self.pontas.values(), *self.aparelhos.values()):
            with contextlib.suppress(OSError):
                sock.close()

    def atos_de_acl(self) -> list[tuple[str, str]]:
        """Os atos que mexem na permissão do nó do ``/dev``: cada um é um ``IN_ATTRIB``."""
        return [ato for ato in self.atos if ato[0] != "open_node"]


class DaemonDeMentira:
    """O que o abridor pergunta ao daemon: só o cliente do broker."""

    def __init__(self, cliente: Any) -> None:
        self._hidraw_broker_client = cliente


@contextlib.contextmanager
def broker_no_ar(tmp_path: Path) -> Iterator[tuple[BrokerState, FsQueGrava, Any]]:
    """O broker real, numa thread, e um cliente real ligado a ele."""
    fs = FsQueGrava()
    estado = BrokerState(
        allowed_uid=os.getuid(),
        ops=fs,
        validator=lambda no: no.rsplit("/", 1)[-1] if no in NOS else None,
        dev_root="/dev",
        sys_class_hidraw=str(tmp_path / "sys-class-hidraw"),
        sys_class_bluetooth=str(tmp_path / "sys-class-bluetooth"),
        log=lambda *a, **k: None,
        sleep_fn=lambda _s: None,
        no_nasce_fechado=True,
    )
    broker = Broker(estado, None, log=lambda *a, **k: None)
    lado_do_broker, lado_do_daemon = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    assert broker.register_client(lado_do_broker) is not None
    parar = threading.Event()

    def _girar() -> None:
        while not parar.is_set():
            broker.step(timeout=0.02)

    girador = threading.Thread(target=_girar, daemon=True, name="broker-de-teste")
    girador.start()
    cliente = cli.HidrawBrokerClient(socket_path=str(tmp_path / "nao-existe.sock"))
    lado_do_daemon.settimeout(3.0)
    cliente._sock = lado_do_daemon
    try:
        yield estado, fs, cliente
    finally:
        parar.set()
        girador.join(timeout=2.0)
        with contextlib.suppress(OSError):
            lado_do_daemon.close()
        fs.fechar()


@pytest.fixture
def caminho_proibido(monkeypatch: pytest.MonkeyPatch) -> list[bytes]:
    """O ``hidapi.Device(path=…)`` grava e recusa: nenhum nó de verdade se abre aqui."""
    import hidapi

    abertos: list[bytes] = []

    def _recusa(*_a: Any, path: bytes | None = None, **_k: Any) -> Any:
        abertos.append(path or b"")
        raise OSError("Could not open connection to device.")

    monkeypatch.setattr(hidapi, "Device", _recusa)
    return abertos


def controle_com_o_abridor(daemon: Any) -> backend.PyDualSenseController:
    """O backend com o abridor que o lifecycle injeta (``_wire_abridor_do_handle``)."""
    ctl = backend.PyDualSenseController.__new__(backend.PyDualSenseController)
    ctl._io_lock = threading.RLock()
    ctl.set_abridor_do_handle(cli.make_abridor_do_handle(daemon))
    return ctl


def abrir(ctl: backend.PyDualSenseController, no: str) -> Any:
    return ctl._open_one(no.encode(), is_edge=False)


class TestOFisicoAbrePeloFdDoBroker:
    @pytest.mark.parametrize(
        ("report", "tamanho", "id_da_saida"),
        [(REPORT_DO_CABO, 64, 0x02), (REPORT_DO_RADIO, 78, 0x31)],
        ids=["cabo", "radio"],
    )
    def test_o_handle_abre_sem_nenhum_ato_de_acl_no_no(
        self,
        tmp_path: Path,
        caminho_proibido: list[bytes],
        report: bytes,
        tamanho: int,
        id_da_saida: int,
    ) -> None:
        """A régua da sprint: nenhum ``expose`` chega ao fs do nó, e o handle vive pelo fd."""
        # D-2310-O-HANDLE-ABRE-O-FISICO-PELO-FD-DO-BROKER
        with broker_no_ar(tmp_path) as (estado, fs, cliente):
            no = NOS[0]
            aparelho = fs.ligar(no)
            aparelho.send(report)
            ctl = controle_com_o_abridor(DaemonDeMentira(cliente))
            handle = abrir(ctl, no)
            fs.soltar_as_pontas()
            try:
                assert handle is not None, "o handle não abriu pelo fd do broker"
                assert fs.atos_de_acl() == [], (
                    f"o nó do /dev ganhou permissão de usuário: {fs.atos_de_acl()}"
                )
                assert fs.atos == [("open_node", no)]
                assert estado.expostos == {}
                assert caminho_proibido == [], "o handle abriu o nó por caminho"
                assert handle.input_report_length == tamanho
                saida = aparelho.recv(512)
                assert len(saida) == tamanho and saida[0] == id_da_saida
            finally:
                if handle is not None:
                    backend._fechar_os_handles_juntos([handle])
            # No cabo a abertura escreve a soltura do motor preso antes do primeiro report;
            # o que sobra na fila é saída do mesmo id, e o fim dela (EOF) prova o fd fechado.
            while (resto := aparelho.recv(512)) != b"":
                assert resto[0] == id_da_saida, "o fd do handle ficou aberto depois do close"

    def test_os_quatro_controles_abrem_sem_acl_cabo_e_radio(
        self, tmp_path: Path, caminho_proibido: list[bytes]
    ) -> None:
        """Um a quatro jogadores, cabo e rádio misturados: nenhum nó se expõe."""
        with broker_no_ar(tmp_path) as (_estado, fs, cliente):
            ctl = controle_com_o_abridor(DaemonDeMentira(cliente))
            handles = []
            try:
                for indice, no in enumerate(NOS):
                    aparelho = fs.ligar(no)
                    aparelho.send(REPORT_DO_CABO if indice % 2 == 0 else REPORT_DO_RADIO)
                    handles.append(abrir(ctl, no))
                fs.soltar_as_pontas()
                assert all(handle is not None for handle in handles)
                assert fs.atos_de_acl() == []
                assert [ato for ato in fs.atos] == [("open_node", no) for no in NOS]
                assert caminho_proibido == []
                assert [h.input_report_length for h in handles] == [64, 78, 64, 78]
            finally:
                backend._fechar_os_handles_juntos([h for h in handles if h is not None])

    def test_o_modo_nativo_segue_exposto_depois_do_handle_abrir(
        self, tmp_path: Path, caminho_proibido: list[bytes]
    ) -> None:
        """O Modo Nativo abre o nó ao jogo de propósito; o handle não mexe nessa lease."""
        with broker_no_ar(tmp_path) as (estado, fs, cliente):
            no = NOS[1]
            aparelho = fs.ligar(no)
            assert cliente.expor(no, entradas=True) is True
            atos_do_nativo = list(fs.atos)
            aparelho.send(REPORT_DO_RADIO)
            ctl = controle_com_o_abridor(DaemonDeMentira(cliente))
            handle = abrir(ctl, no)
            fs.soltar_as_pontas()
            try:
                assert handle is not None
                assert fs.atos == [*atos_do_nativo, ("open_node", no)]
                assert no in estado.expostos and estado.expostos[no].refcount == 1
                assert caminho_proibido == []
            finally:
                if handle is not None:
                    backend._fechar_os_handles_juntos([handle])


    def test_o_init_espera_o_primeiro_report_que_chega_depois_do_open(
        self, tmp_path: Path, caminho_proibido: list[bytes]
    ) -> None:
        """O hidraw nasce de fila vazia a cada open: o ``init`` espera o primeiro report."""
        with broker_no_ar(tmp_path) as (_estado, fs, cliente):
            no = NOS[3]
            aparelho = fs.ligar(no)
            atraso = threading.Timer(0.3, aparelho.send, args=(REPORT_DO_RADIO,))
            atraso.start()
            ctl = controle_com_o_abridor(DaemonDeMentira(cliente))
            try:
                handle = abrir(ctl, no)
            finally:
                atraso.join()
            fs.soltar_as_pontas()
            try:
                assert handle is not None
                assert handle.input_report_length == 78
                assert caminho_proibido == []
            finally:
                if handle is not None:
                    backend._fechar_os_handles_juntos([handle])

    def test_o_init_que_falha_fecha_o_fd_do_broker(
        self, tmp_path: Path, caminho_proibido: list[bytes]
    ) -> None:
        """Um primeiro report sem transporte derruba o ``init``: o fd do broker fecha na hora."""
        with broker_no_ar(tmp_path) as (_estado, fs, cliente):
            no = NOS[2]
            aparelho = fs.ligar(no)
            aparelho.send(bytes(10))
            ctl = controle_com_o_abridor(DaemonDeMentira(cliente))
            with pytest.raises(Exception, match="connection type") as falha:
                abrir(ctl, no)
            fs.soltar_as_pontas()
            # ``falha`` segura a pilha (e o handle nela): o ``__del__`` não fecha por acaso.
            assert falha.value is not None
            assert aparelho.recv(512) == b"", "o fd do broker vazou com o init que falhou"
            assert fs.atos_de_acl() == []
            assert caminho_proibido == []


class TestSemOFdDoBroker:
    def test_broker_ausente_abre_por_caminho_sem_pedir_exposicao(
        self, tmp_path: Path, caminho_proibido: list[bytes]
    ) -> None:
        """Máquina sem a cura (o nó já nasce do usuário): abre por caminho, como sempre."""
        cliente = cli.HidrawBrokerClient(socket_path=str(tmp_path / "nao-existe.sock"))
        ctl = controle_com_o_abridor(DaemonDeMentira(cliente))
        with pytest.raises(OSError):
            abrir(ctl, NOS[2])
        assert caminho_proibido == [NOS[2].encode()]

    def test_broker_que_recusa_o_no_nao_expoe_nada(
        self, tmp_path: Path, caminho_proibido: list[bytes]
    ) -> None:
        """O broker recusa o que não é DualSense físico; a recusa não vira exposição."""
        with broker_no_ar(tmp_path) as (estado, fs, cliente):
            ctl = controle_com_o_abridor(DaemonDeMentira(cliente))
            with pytest.raises(OSError):
                abrir(ctl, "/dev/hidraw89")
            assert fs.atos == []
            assert estado.expostos == {}
            assert caminho_proibido == [b"/dev/hidraw89"]

    def test_sem_fabrica_abre_por_caminho(self, caminho_proibido: list[bytes]) -> None:
        """Sem broker injetado (a CLI, o dublê) nada muda: o caminho de sempre."""
        ctl = backend.PyDualSenseController.__new__(backend.PyDualSenseController)
        with pytest.raises(OSError):
            abrir(ctl, NOS[3])
        assert caminho_proibido == [NOS[3].encode()]


class TestODispositivoPorFd:
    """O leitor/escritor do fd faz o que o backend hidraw do hidapi faz com o dele."""

    def test_le_um_report_por_vez_e_none_sem_espera(self) -> None:
        fisico, aparelho = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        dispositivo = backend._DispositivoPorFd(os.dup(fisico.fileno()))
        fisico.close()
        try:
            aparelho.send(REPORT_DO_CABO)
            aparelho.send(REPORT_DO_RADIO)
            assert dispositivo.read(100) == REPORT_DO_CABO
            backend._ler_sem_espera(dispositivo)
            assert dispositivo.read(100) == REPORT_DO_RADIO
            assert dispositivo.read(100) is None
            assert dispositivo.write(b"\x02" + bytes(63)) == 64
            assert aparelho.recv(512) == b"\x02" + bytes(63)
        finally:
            dispositivo.close()
            aparelho.close()

    def test_o_aparelho_que_sai_vira_oserror(self) -> None:
        fisico, aparelho = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        dispositivo = backend._DispositivoPorFd(os.dup(fisico.fileno()))
        fisico.close()
        backend._ler_sem_espera(dispositivo)
        aparelho.close()
        try:
            with pytest.raises(OSError):
                dispositivo.read(100)
        finally:
            dispositivo.close()

    def test_fechado_recusa_como_o_hidapi(self) -> None:
        fisico, aparelho = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        dispositivo = backend._DispositivoPorFd(os.dup(fisico.fileno()))
        fisico.close()
        dispositivo.close()
        aparelho.close()
        for gesto in (
            lambda: dispositivo.read(100),
            lambda: dispositivo.write(b"\x02"),
            dispositivo.close,
            lambda: backend._ler_sem_espera(dispositivo),
        ):
            with pytest.raises(OSError):
                gesto()
