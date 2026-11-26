"""OS-PADS-VIRTUAIS-SOBREVIVEM-A-QUEDA-DO-SERVICO-01 — os controles virtuais sobrevivem à queda.

D-2511-O-DEPOSITO-DOS-NOS-VALE-NA-QUEDA-E-NO-REINICIO-E-SAI-NO-STOP. O uhid e o uinput morriam
com o descritor do serviço, e o gadget descia no EOF da conexão com o broker: na queda ou no
«Reiniciar» com jogo aberto, o jogo via todos os controles saírem e voltarem em nós novos. Agora o
nó de cada controle se guarda no depósito do systemd (``FDSTORE``), o serviço que volta o readota
pelo nome em vez de criar outro, o herdado sem controle presente se fecha, e o broker segura o
gadget numa graça curta para o mesmo serial.

O systemd é de mentira: um soquete de datagrama que recebe o ``FDSTORE`` com o fd anexado. O
``/dev/uhid`` é um par de soquetes (o lado do kernel fica com o teste), e o broker usa o kernel de
mentira das réguas do pad em USB. Nada toca o uhid, o uinput ou o systemd de verdade.

MORDIDAS: sem o ``guardar_descritor`` no ``_criar_o_device``, o serviço que volta recria o device
(``UHID_CREATE2`` de novo); sem a graça no EOF do broker, o gadget desce na hora; sem o pedido
do gadget da graça antes da espera pelo endereço, o serviço que volta veste outro serial; sem o
report largado, o nó que fica no depósito segue com o botão apertado; sem o herdado no uinput, o
modo Xbox recria o nó.
"""

from __future__ import annotations

import array
import contextlib
import fcntl
import os
import socket
import struct
from collections.abc import Iterator
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense
from hefesto_dualsense4unix.utils import sd_notify

_PRIMEIRO_LIVRE = 900
_IDENTIDADES = {1: "aa:bb:cc:00:00:01", 2: "aa:bb:cc:00:00:02", 3: "aa:bb:cc:00:00:03",
                4: "aa:bb:cc:00:00:04"}


class _Systemd:
    """O ``NOTIFY_SOCKET`` de mentira: guarda cada aviso e cada fd que chega com ele."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        nome = f"hefesto-deposito-{os.getpid()}-{id(self)}"
        self.soquete = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.soquete.bind("\0" + nome)
        self.soquete.setblocking(False)
        monkeypatch.setattr(sd_notify, "_guardadas", {"NOTIFY_SOCKET": "@" + nome})
        monkeypatch.setattr(sd_notify, "_herdados", {})
        monkeypatch.setattr(sd_notify, "_no_deposito", set())
        monkeypatch.setattr(sd_notify, "_estado", {"parando": False})
        monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
        self.deposito: dict[str, list[int]] = {}
        self.avisos: list[str] = []

    def receber(self) -> None:
        while True:
            fds = array.array("i")
            try:
                dados, anc, _flags, _addr = self.soquete.recvmsg(
                    4096, socket.CMSG_SPACE(16 * fds.itemsize)
                )
            except BlockingIOError:
                return
            for nivel, tipo, bruto in anc:
                if nivel == socket.SOL_SOCKET and tipo == socket.SCM_RIGHTS:
                    fds.frombytes(bruto[: len(bruto) - (len(bruto) % fds.itemsize)])
            aviso = dados.decode()
            self.avisos.append(aviso)
            campos = dict(linha.split("=", 1) for linha in aviso.splitlines() if "=" in linha)
            nome = campos.get("FDNAME", "")
            if campos.get("FDSTORE") == "1":
                self.deposito.setdefault(nome, []).extend(fds)
            elif campos.get("FDSTOREREMOVE") == "1":
                for fd in self.deposito.pop(nome, []):
                    with contextlib.suppress(OSError):
                        os.close(fd)

    def entregar(self) -> dict[str, int]:
        """O reinício: o que está no depósito chega ao serviço novo pelo ``LISTEN_FDS``.

        Os fds vão a números seguidos (como o systemd os põe a partir do 3), e o
        ``ler_os_herdados`` do produto os lê.
        """
        self.receber()
        nomes: list[str] = []
        for i, (nome, fds) in enumerate(sorted(self.deposito.items())):
            os.dup2(fds[0], _PRIMEIRO_LIVRE + i)
            nomes.append(nome)
        ambiente = {
            "LISTEN_PID": str(os.getpid()),
            "LISTEN_FDS": str(len(nomes)),
            "LISTEN_FDNAMES": ":".join(nomes),
        }
        herdados = sd_notify.ler_os_herdados(ambiente, primeiro=_PRIMEIRO_LIVRE)
        sd_notify._herdados.update(herdados)
        sd_notify._no_deposito.update(herdados)
        return herdados

    def fechar(self) -> None:
        for fds in self.deposito.values():
            for fd in fds:
                with contextlib.suppress(OSError):
                    os.close(fd)
        self.soquete.close()


class _Uhid:
    """O ``/dev/uhid``: cada abertura é um par de soquetes; o lado do kernel fica aqui."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.aberturas = 0
        self.kernel: list[socket.socket] = []
        self.servico: list[socket.socket] = []
        real = os.open

        def abrir(caminho: Any, *args: Any, **kwargs: Any) -> int:
            if caminho != uhid.UHID_NODE:
                return real(caminho, *args, **kwargs)
            self.aberturas += 1
            kernel, servico = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            kernel.setblocking(False)
            self.kernel.append(kernel)
            self.servico.append(servico)
            return servico.detach()

        monkeypatch.setattr(os, "open", abrir)

    def eventos(self, kernel: socket.socket) -> list[int]:
        tipos: list[int] = []
        with contextlib.suppress(BlockingIOError):
            while True:
                dado = kernel.recv(8192)
                if not dado:
                    break
                tipos.append(struct.unpack("<I", dado[:4])[0])
        return tipos

    def fechar(self) -> None:
        for lado in self.kernel:
            lado.close()


@pytest.fixture
def systemd(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Systemd]:
    falso = _Systemd(monkeypatch)
    yield falso
    falso.fechar()


@pytest.fixture
def no_uhid(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Uhid]:
    falso = _Uhid(monkeypatch)
    yield falso
    falso.fechar()


def _pad(player: int) -> UhidDualSense:
    pad = UhidDualSense(player=player, blueprint=_blueprint())
    pad.identity = _IDENTIDADES[player]
    pad._sem_gadget = True
    return pad


def _blueprint() -> dict[str, Any]:
    return {
        "descriptor": bytes([0x05, 0x01, 0x09, 0x05, 0xA1, 0x01]),
        "features": {
            0x05: bytes([0x05]) + bytes(40),
            0x09: bytes([0x09]) + bytes(19),
            0x20: bytes([0x20]) + bytes(63),
        },
    }


def _cair(pad: UhidDualSense) -> None:
    """O serviço que morre: o kernel fecha o fd dele, sem `UHID_DESTROY` e sem pedir nada."""
    pad._parar_o_fio_do_uhid()
    fd = pad._fd
    pad._fd = None
    if fd is not None:
        os.close(fd)
    uhid._MACS_DOS_VPADS_VIVOS.despir(pad)


def _fechado(fd: int) -> bool:
    try:
        os.fstat(fd)
    except OSError:
        return True
    return False


def test_o_servico_que_volta_readota_os_quatro_nos_sem_criar_de_novo(
    systemd: _Systemd, no_uhid: _Uhid
) -> None:
    """P1 a P4 nascem e se guardam; o serviço cai; o que volta recebe os quatro e não abre o
    ``/dev/uhid`` nem manda ``UHID_CREATE2``: o report novo sai no MESMO canal do kernel."""
    antes = {n: _pad(n) for n in (1, 2, 3, 4)}
    for pad in antes.values():
        assert pad.start() is True
    assert no_uhid.aberturas == 4
    for kernel in no_uhid.kernel:
        assert no_uhid.eventos(kernel)[:1] == [uhid.UHID_CREATE2]
    systemd.receber()
    assert len(systemd.deposito) == 4, systemd.avisos
    for pad in antes.values():
        _cair(pad)

    herdados = systemd.entregar()
    assert len(herdados) == 4
    depois = {n: _pad(n) for n in (1, 2, 3, 4)}
    try:
        for pad in depois.values():
            assert pad.start() is True
        assert no_uhid.aberturas == 4, "o serviço que voltou recriou o device"
        for n, pad in depois.items():
            assert pad._started and pad._fd == herdados[uhid._nome_do_uhid_no_deposito(pad)]
            pad.forward_buttons(frozenset({"cross"}))
            assert uhid.UHID_INPUT2 in no_uhid.eventos(no_uhid.kernel[n - 1]), (
                f"P{n}: o report não chegou ao nó que o jogo já tinha")
            assert uhid.UHID_CREATE2 not in no_uhid.eventos(no_uhid.kernel[n - 1])
    finally:
        for pad in depois.values():
            pad.stop()


def test_o_herdado_de_um_controle_que_nao_voltou_se_fecha(
    systemd: _Systemd, no_uhid: _Uhid
) -> None:
    """P3 não volta: o herdado dele se fecha e sai do depósito; o de P1 vira o pad de P1."""
    antes = {n: _pad(n) for n in (1, 3)}
    for pad in antes.values():
        assert pad.start() is True
    nome_p3 = uhid._nome_do_uhid_no_deposito(antes[3])
    for pad in antes.values():
        _cair(pad)
    herdados = systemd.entregar()
    p1 = _pad(1)
    try:
        assert p1.start() is True
        assert no_uhid.aberturas == 2
        fechados = sd_notify.fechar_os_herdados_que_sobraram()
        assert fechados == [nome_p3]
        assert _fechado(herdados[nome_p3])
        systemd.receber()
        assert nome_p3 not in systemd.deposito
        assert not _fechado(herdados[uhid._nome_do_uhid_no_deposito(p1)])
    finally:
        p1.stop()


def test_o_controle_que_sai_com_o_servico_de_pe_tira_o_no_do_deposito(
    systemd: _Systemd, no_uhid: _Uhid
) -> None:
    """O controle que sai de verdade: `UHID_DESTROY`, e o nó sai do depósito (não volta)."""
    pad = _pad(2)
    assert pad.start() is True
    nome = uhid._nome_do_uhid_no_deposito(pad)
    no_uhid.eventos(no_uhid.kernel[0])
    pad.stop()
    uhid.esperar_as_descidas(5.0)
    assert uhid.UHID_DESTROY in no_uhid.eventos(no_uhid.kernel[0])
    systemd.receber()
    assert nome not in systemd.deposito
    assert f"FDSTOREREMOVE=1\nFDNAME={nome}" in systemd.avisos


def test_o_servico_que_para_deixa_o_no_ao_systemd(systemd: _Systemd, no_uhid: _Uhid) -> None:
    """Com o desligamento começado (``STOPPING=1``), o pad fecha só o fd dele: sem
    `UHID_DESTROY`, e o nó segue no depósito para o reinício (o `stop` o fecha no systemd)."""
    pad = _pad(4)
    assert pad.start() is True
    nome = uhid._nome_do_uhid_no_deposito(pad)
    no_uhid.eventos(no_uhid.kernel[0])
    assert sd_notify.parando() is True
    pad.stop()
    uhid.esperar_as_descidas(5.0)
    assert uhid.UHID_DESTROY not in no_uhid.eventos(no_uhid.kernel[0])
    systemd.receber()
    assert nome in systemd.deposito


def test_os_herdados_so_valem_para_este_processo_e_nao_vazam_aos_filhos() -> None:
    """``LISTEN_PID`` de outro processo não entrega nada; o fd entregue ganha ``FD_CLOEXEC``."""
    leitura, escrita = os.pipe()
    try:
        os.dup2(leitura, _PRIMEIRO_LIVRE)
        flags = fcntl.fcntl(_PRIMEIRO_LIVRE, fcntl.F_GETFD)
        fcntl.fcntl(_PRIMEIRO_LIVRE, fcntl.F_SETFD, flags & ~fcntl.FD_CLOEXEC)
        alheio = {"LISTEN_PID": "1", "LISTEN_FDS": "1", "LISTEN_FDNAMES": "x"}
        assert sd_notify.ler_os_herdados(alheio, primeiro=_PRIMEIRO_LIVRE) == {}
        meu = {"LISTEN_PID": str(os.getpid()), "LISTEN_FDS": "1", "LISTEN_FDNAMES": "x"}
        assert sd_notify.ler_os_herdados(meu, primeiro=_PRIMEIRO_LIVRE) == {"x": _PRIMEIRO_LIVRE}
        assert fcntl.fcntl(_PRIMEIRO_LIVRE, fcntl.F_GETFD) & fcntl.FD_CLOEXEC
    finally:
        for fd in (leitura, escrita, _PRIMEIRO_LIVRE):
            with contextlib.suppress(OSError):
                os.close(fd)


def test_a_unit_guarda_o_deposito_na_queda_e_no_reinicio_e_o_solta_no_stop() -> None:
    """A unit tem depósito para os quatro uhid e os quatro uinput, e ``restart`` (não ``yes``)."""
    from pathlib import Path

    unit = (Path(__file__).resolve().parents[2] / "assets" / "hefesto-dualsense4unix.service")
    linhas = {
        chave.strip(): valor.strip()
        for chave, _, valor in (
            linha.partition("=") for linha in unit.read_text(encoding="utf-8").splitlines()
            if linha and not linha.startswith("#") and "=" in linha
        )
    }
    assert int(linhas["FileDescriptorStoreMax"]) >= 8
    assert linhas["FileDescriptorStorePreserve"] == "restart"


class TestOBrokerSeguraOGadgetNaGraca:
    """O EOF da conexão do serviço não desce o gadget dentro da graça; o mesmo serial o herda."""

    @pytest.fixture
    def kernel(self, tmp_path: Any) -> Any:
        from tests.unit.test_o_pad_nasce_no_mesmo_usb_do_som import KernelDeMentira

        return KernelDeMentira(tmp_path)

    def _pedido(self) -> bytes:
        from tests.unit.test_o_pad_nasce_no_mesmo_usb_do_som import _pedido

        return _pedido()

    def test_dentro_da_graca_o_mesmo_serial_herda_o_gadget(self, kernel: Any) -> None:
        from hefesto_dualsense4unix.broker import hidraw_broker as broker

        agora = [1000.0]
        estado = broker.BrokerState(
            allowed_uid=1000, pad_ops=kernel.ops(), log=lambda *_a, **_k: None,
            relogio=lambda: agora[0],
        )
        resposta, fd = estado.handle_line(7, 1000, self._pedido())
        assert resposta["ok"] is True and fd is not None
        os.close(fd)
        gadget = resposta["gadget"]
        estado.on_conn_closed(7)
        agora[0] += broker.GRACA_DO_PAD_USB_S - 1.0
        estado.vencer_a_graca_dos_pads()
        assert os.listdir(kernel.raizes.configfs) == [gadget], "o gadget desceu dentro da graça"
        herdou, fd = estado.handle_line(8, 1000, self._pedido())
        assert herdou["ok"] is True and herdou.get("herdado") is True, herdou
        assert herdou["gadget"] == gadget and fd is not None
        os.close(fd)
        estado.on_conn_closed(8)
        agora[0] += broker.GRACA_DO_PAD_USB_S + 1.0
        estado.vencer_a_graca_dos_pads()
        assert os.listdir(kernel.raizes.configfs) == []

    def test_vencida_a_graca_o_gadget_desce(self, kernel: Any) -> None:
        from hefesto_dualsense4unix.broker import hidraw_broker as broker

        agora = [1000.0]
        estado = broker.BrokerState(
            allowed_uid=1000, pad_ops=kernel.ops(), log=lambda *_a, **_k: None,
            relogio=lambda: agora[0],
        )
        _resposta, fd = estado.handle_line(7, 1000, self._pedido())
        assert fd is not None
        os.close(fd)
        estado.on_conn_closed(7)
        agora[0] += broker.GRACA_DO_PAD_USB_S + 0.1
        estado.vencer_a_graca_dos_pads()
        assert os.listdir(kernel.raizes.configfs) == []
        novo, fd = estado.handle_line(8, 1000, self._pedido())
        assert novo["ok"] is True and novo.get("herdado") is None
        if fd is not None:
            os.close(fd)


def _ultimo_input_do_uhid(kernel: socket.socket) -> bytes | None:
    """O report do último `UHID_INPUT2` que chegou ao lado do kernel."""
    ultimo: bytes | None = None
    with contextlib.suppress(BlockingIOError):
        while True:
            dado = kernel.recv(8192)
            if not dado:
                break
            if len(dado) < 6:
                continue
            tipo, tamanho = struct.unpack("<IH", dado[:6])
            if tipo == uhid.UHID_INPUT2:
                ultimo = dado[6:6 + tamanho]
    return ultimo


def _largado(report: bytes) -> bool:
    """O report 0x01 de um controle largado: eixos no centro, nada apertado."""
    return (
        report[0] == 0x01
        and report[1:7] == bytes(uhid._AXES_NEUTRAL)
        and report[1 + uhid._BUTTONS0_OFFSET] == uhid._DPAD_NEUTRAL
    )


def test_o_no_que_fica_no_deposito_fica_largado(systemd: _Systemd, no_uhid: _Uhid) -> None:
    """O serviço que para com o botão apertado: o nó que fica para o reinício recebe o report
    largado antes do `close`, e o jogo não segue com o botão apertado até o serviço voltar."""
    pad = _pad(1)
    assert pad.start() is True
    pad.forward_buttons(frozenset({"cross"}))
    apertado = _ultimo_input_do_uhid(no_uhid.kernel[0])
    assert apertado is not None and not _largado(apertado)
    assert sd_notify.parando() is True
    pad.stop()
    uhid.esperar_as_descidas(5.0)
    ultimo = _ultimo_input_do_uhid(no_uhid.kernel[0])
    assert ultimo is not None and _largado(ultimo), "o nó ficou no depósito com o botão apertado"


def test_o_gadget_do_servico_que_volta_e_o_mesmo_serial_da_graca(
    systemd: _Systemd, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Máscara DualSense pelo gadget: o serviço para com o jogo aberto, o broker segura o
    gadget na graça, e o endereço dele segue no kernel. O serviço que volta pede o MESMO
    serial na hora, sem esperar o endereço sair nem vestir o próximo (outro serial seria
    outro controle no jogo); e o gadget que fica recebe o report largado."""
    from tests.unit.test_o_pad_nasce_no_mesmo_usb_do_som import EnsaioDoGadget

    ensaio = EnsaioDoGadget(monkeypatch, tmp_path)
    no_kernel: set[str] = set()
    monkeypatch.setattr(uhid, "_enderecos_no_kernel", lambda: frozenset(no_kernel))
    antes = ensaio.pad(player=1)
    assert antes.start() is True and antes._gadget is not None
    serial = ensaio.pedidos[0][0]
    marca = uhid._nome_do_gadget_no_deposito(serial)
    systemd.receber()
    assert marca in systemd.deposito, systemd.avisos
    jogo = ensaio.jogo
    assert jogo is not None
    no_kernel.add(antes.mac.lower())
    assert sd_notify.parando() is True
    antes.stop()
    uhid.esperar_as_descidas(5.0)
    jogo.setblocking(False)
    reports: list[bytes] = []
    with contextlib.suppress(BlockingIOError):
        while True:
            dado = jogo.recv(8192)
            if not dado:
                break
            reports.append(dado)
    assert reports and _largado(reports[-1]), "o gadget ficou na graça sem o report largado"
    assert ensaio.clientes[0].desmontados == [], "o serviço que para desceu o gadget"
    systemd.receber()
    assert marca in systemd.deposito

    sd_notify._estado["parando"] = False
    systemd.entregar()
    depois = ensaio.pad(player=1)
    try:
        assert depois.start() is True
        assert len(ensaio.pedidos) == 2
        assert ensaio.pedidos[1][0] == serial, (
            "o serviço que voltou vestiu outro endereço e pediu outro gadget")
        assert depois._gadget is not None
    finally:
        depois.stop()
        uhid.esperar_as_descidas(5.0)


def _a_classe_do_uinput() -> type:
    """A classe `UInput` do python-evdev, que a vigia da suíte troca por uma fábrica que
    recusa: o herdado só a aloca em volta do fd (``__new__``), sem `UI_DEV_CREATE`."""
    from evdev.eventio import EventIO

    pilha: list[type] = [EventIO]
    while pilha:
        classe = pilha.pop()
        if classe.__name__ == "UInput":
            return classe
        pilha.extend(classe.__subclasses__())
    raise AssertionError("o python-evdev não tem a classe UInput")


class _NoDoUinput:
    """O `UInput` de mentira: um fd de verdade (para o ``SCM_RIGHTS``) e cada escrita anotada."""

    def __init__(self) -> None:
        self.fd = os.open(os.devnull, os.O_RDWR)
        self.escritas: list[tuple[int, int, int]] = []
        self.destruido = False

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        self.escritas.append((tipo, codigo, valor))

    def syn(self) -> None:
        self.escritas.append((0, 0, 0))

    def close(self) -> None:
        self.destruido = True
        with contextlib.suppress(OSError):
            os.close(self.fd)
        self.fd = -1


def test_o_pad_uinput_volta_no_mesmo_no_e_fica_largado(
    systemd: _Systemd, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Máscara Xbox (uinput): o nó se guarda, o serviço que para o deixa largado no depósito
    sem `UI_DEV_DESTROY`, e o serviço que volta o readota sem criar outro."""
    import evdev
    from evdev import ecodes

    from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

    criados: list[_NoDoUinput] = []

    def criar(self: UinputGamepad, *, with_ff: bool) -> _NoDoUinput | None:
        if with_ff:
            return None
        no = _NoDoUinput()
        criados.append(no)
        return no

    monkeypatch.setattr(UinputGamepad, "_create_device", criar)
    antes = UinputGamepad.for_flavor("xbox")
    antes.identidade = _IDENTIDADES[2]
    assert antes.start() is True and len(criados) == 1
    systemd.receber()
    nome = antes._nome_no_deposito(False)
    assert nome in systemd.deposito, systemd.avisos
    antes.forward_buttons(frozenset({"cross"}))
    codigo = antes._resolve_evdev("cross", ecodes)
    assert (ecodes.EV_KEY, codigo, 1) in criados[0].escritas
    assert sd_notify.parando() is True
    antes.stop()
    no = criados[0]
    assert not no.destruido, "o serviço que para destruiu o nó guardado"
    assert no.escritas[-1] == (0, 0, 0)
    assert (ecodes.EV_KEY, codigo, 0) in no.escritas and (ecodes.EV_ABS, ecodes.ABS_X, 128) in (
        no.escritas), "o nó ficou no depósito com o botão apertado"
    systemd.receber()
    assert nome in systemd.deposito

    sd_notify._estado["parando"] = False
    herdados = systemd.entregar()
    monkeypatch.setattr(evdev, "UInput", _a_classe_do_uinput())
    depois = UinputGamepad.for_flavor("xbox")
    depois.identidade = _IDENTIDADES[2]
    try:
        assert depois.start() is True
        assert len(criados) == 1, "o serviço que voltou recriou o nó"
        assert depois._device.fd == herdados[nome]
    finally:
        depois.stop()
        with contextlib.suppress(OSError):
            os.close(herdados[nome])
