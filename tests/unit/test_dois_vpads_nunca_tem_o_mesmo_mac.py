"""O-VPAD-DO-P1-NAO-REPETE-O-MAC-01 — dois vpads vivos nunca vestem o mesmo MAC.

**O defeito, medido na conferência da O-ASSENTO-GUARDADO-NAO-ANDA-03 (24/09):**
o vpad do posto que renasce com a identidade do P1 (troca de máscara, de
caminho, ``_reerguer_o_p1``) e o vpad secundário do P1 que volta DEPOIS do
prazo, com o jogo aberto, saíam com o MESMO MAC — os dois pediam
``vpad_mac(P1)``. O ``hid_playstation`` recusa o segundo com ``-EEXIST``
(``ps_devices_list_add``, ``assets/dkms/hid-playstation/hid-playstation.c``), e
o P1 caía no vpad ``uinput`` degradado: sem vibração, sem giroscópio, sem
gatilho, sem luz.

**A régua é a classe REAL contra um kernel de mentira que recusa como o de
verdade.** :class:`KernelDoHidPlaystation` é o ``/dev/uhid`` com o probe do
``hid_playstation`` na ordem que o fonte faz — ``START``, ``OPEN``, o
``GET_REPORT`` do 0x09 (o MAC), o do 0x20, o ``ps_devices_list_add`` e, se o
MAC já está na lista, ``CLOSE`` e ``STOP`` com ``Duplicate device found for MAC
address``. Ele entra no lugar do ``os`` do ``uhid_gamepad`` SÓ para aquele
módulo: nenhum nó ``/dev/uhid`` ou ``/dev/uinput`` de verdade nasce aqui, e o
resto do processo segue com o ``os`` de sempre.

**O caso geral é a régua**, e não só o posto contra o P1 que volta: todo par
de nascimentos que o produto faz (o mesmo aparelho duas vezes, as duas grafias
do mesmo plástico, os sem endereço no mesmo número), a mesa cheia, a
reconexão de cada lugar (o MAC volta o mesmo), as faixas dos MACs seguintes e
as três saídas do dono (o ``start`` que falha, a ordem do ``stop``, dois fios
ao mesmo tempo). A matriz de transportes (USB, BT e a mesa mista) e os lugares
que o posto carrega estão na bancada honesta da volta tardia
(``test_o_buraco_de_quem_saiu_se_fecha_no_jogo.py``).

AS MORDIDAS (24/09/2026, cada uma devolvida com o md5 conferido):

- no dublê: sem a checagem da lista do driver reprovam 2; sem o ``ps_remove``, 8
  (os dois do dublê, a mesa cheia e as cinco reconexões: o driver seguiria
  guardando o MAC de quem já saiu);
- ``vestir`` vestindo o pedido sem olhar quem veste: 20;
- a propriedade ``mac`` ignorando o vestido (o 0x09 leva o pedido): 19;
- ``despir`` que não devolve: 7;
- o ``start`` que falha sem ``despir``: 1; o ``stop`` que devolve antes do
  ``UHID_DESTROY``: 1; o ``vestir`` sem o lock: 1.

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados;
os ``02:fe:`` são os que o produto forja.
"""
from __future__ import annotations

import errno
import itertools
import os
import struct
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import uhid_gamepad, uinput_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    DUALSENSE_VENDOR,
    UHID_CLOSE,
    UHID_CREATE2,
    UHID_DESTROY,
    UHID_GET_REPORT,
    UHID_GET_REPORT_REPLY,
    UHID_INPUT2,
    UHID_NODE,
    UHID_OPEN,
    UHID_SET_REPORT_REPLY,
    UHID_START,
    UHID_STOP,
)

#: Os ids de produto em que o ``hid_playstation`` faz bind no DualSense — o
#: físico (0x0CE6) e o Edge (0x0DF2, o que o vpad apresenta).
_PIDS_DUALSENSE = (0x0CE6, 0x0DF2)

#: Os três feature reports do probe do DualSense e o tamanho que o
#: ``__ps_get_report`` exige (``DS_FEATURE_REPORT_*_SIZE`` no fonte).
_PAREAMENTO, _PAREAMENTO_TAMANHO = 0x09, 20
_FIRMWARE, _FIRMWARE_TAMANHO = 0x20, 64
_CALIBRACAO, _CALIBRACAO_TAMANHO = 0x05, 41

#: ``UHID_FEATURE_REPORT`` do ``linux/uhid.h``.
_UHID_FEATURE_REPORT = 0

#: Onde começam os fds de mentira — longe de qualquer fd real do processo.
_PRIMEIRO_FD = 40_000


def mac_impresso(mac_no_report: bytes) -> str:
    """Os seis bytes como o kernel os imprime (``%pMR``: a ordem inversa)."""
    return ":".join(f"{b:02x}" for b in reversed(mac_no_report))


def mac_no_report(mac: str) -> bytes:
    """``aa:bb:…`` na ordem do report 0x09 — a que a lista do driver compara."""
    return bytes(reversed(bytes.fromhex(mac.replace(":", ""))))


@dataclass
class _Device:
    """Um fd aberto em ``/dev/uhid``: o device HID e o probe do driver nele."""

    fila: list[bytes] = field(default_factory=list)
    criado: bool = False
    nome: str = ""
    uniq: str = ""
    mac: bytes | None = None
    na_lista: bool = False
    recusado: bool = False
    pedidos: dict[int, int] = field(default_factory=dict)
    inputs: int = 0


class KernelDoHidPlaystation:
    """O ``/dev/uhid`` e o probe do ``hid_playstation``, de mentira — e a recusa, de verdade.

    O que ele faz é o que o fonte do driver faz (``ps_probe`` →
    ``dualsense_create``), na mesma ordem:

    1. ``CREATE2`` com VID Sony e PID de DualSense → ``START`` e ``OPEN``, e o
       ``GET_REPORT`` do 0x09;
    2. a resposta do 0x09 dá o MAC (bytes 1..6, a ordem do report) e pede o 0x20;
    3. a resposta do 0x20 leva ao ``ps_devices_list_add``: **MAC que já está na
       lista é recusado** — ``Duplicate device found for MAC address``,
       ``probe failed -17`` — e o device recebe ``CLOSE`` e ``STOP``;
    4. senão o MAC entra na lista, e a resposta do 0x05 fecha o probe;
    5. ``DESTROY`` (ou fechar o fd) tira o device da lista — o ``ps_remove``.

    Resposta curta, com o id errado ou com ``err`` levanta o mesmo ``CLOSE`` e
    ``STOP`` que o driver levanta (``Invalid byte count``, ``Invalid
    reportID``): um dublê que aceitasse qualquer resposta seria mais frouxo que
    o real. A lista nasce com os controles FÍSICOS da mesa (``fisicos``), como
    no kernel — um vpad que vestisse o MAC de um físico seria recusado também.
    """

    def __init__(self, fisicos: tuple[str, ...] = ()) -> None:
        self.devices: dict[int, _Device] = {}
        #: A ``ps_devices_list``: MAC na ordem do report → fd do dono (None = físico).
        self.lista: dict[bytes, int | None] = {mac_no_report(f): None for f in fisicos}
        #: Cada recusa por MAC repetido, com a frase do ``hid_err`` do driver.
        self.recusas: list[str] = []
        #: Toda linha que o driver escreveria no diário do kernel.
        self.diario: list[str] = []
        #: Quantas aberturas de ``/dev/uhid`` recusar com ``EACCES`` (a ACL que o
        #: logind ainda não aplicou no primeiro boot depois do install).
        self.recusar_aberturas = 0
        self._proximo_fd = _PRIMEIRO_FD
        self._proximo_pedido = 1

    # -- o que o userspace chama -------------------------------------------

    def abrir(self, caminho: str) -> int:
        if caminho != UHID_NODE:
            raise PermissionError(errno.EACCES, f"o kernel de mentira só tem {UHID_NODE}")
        if self.recusar_aberturas:
            self.recusar_aberturas -= 1
            raise PermissionError(errno.EACCES, "sem ACL no /dev/uhid")
        fd = self._proximo_fd
        self._proximo_fd += 1
        self.devices[fd] = _Device()
        return fd

    def escrever(self, fd: int, dados: bytes) -> int:
        device = self._device(fd)
        tipo = struct.unpack("<I", dados[:4])[0]
        if tipo == UHID_CREATE2:
            self._criar(device, dados)
        elif tipo == UHID_GET_REPORT_REPLY:
            self._resposta(fd, device, dados)
        elif tipo == UHID_INPUT2:
            if not device.criado:
                raise OSError(errno.EINVAL, "INPUT2 antes do CREATE2")
            device.inputs += 1
        elif tipo == UHID_DESTROY:
            self._destruir(fd, device)
        elif tipo != UHID_SET_REPORT_REPLY:
            raise OSError(errno.EINVAL, f"evento uhid {tipo} que o kernel de mentira não conhece")
        return len(dados)

    def ler(self, fd: int, _tamanho: int) -> bytes:
        device = self._device(fd)
        if not device.fila:
            raise BlockingIOError(errno.EAGAIN, "nada na fila")
        return device.fila.pop(0)

    def fechar(self, fd: int) -> None:
        device = self.devices.pop(fd, None)
        if device is not None:
            self._destruir(fd, device)

    # -- o probe --------------------------------------------------------------

    def _device(self, fd: int) -> _Device:
        device = self.devices.get(fd)
        if device is None:
            raise OSError(errno.EBADF, f"fd {fd} não é do /dev/uhid de mentira")
        return device

    def _criar(self, device: _Device, dados: bytes) -> None:
        device.criado = True
        device.nome = dados[4:132].split(b"\0", 1)[0].decode("utf-8", "replace")
        device.uniq = dados[196:260].split(b"\0", 1)[0].decode("ascii", "replace")
        vendor, product = struct.unpack("<II", dados[264:272])
        if vendor != DUALSENSE_VENDOR or product not in _PIDS_DUALSENSE:
            return  # sem driver: nenhum probe, nenhum START
        device.fila.append(struct.pack("<IQ", UHID_START, 0))
        device.fila.append(struct.pack("<I", UHID_OPEN))
        self._pedir(device, _PAREAMENTO)

    def _pedir(self, device: _Device, report: int) -> None:
        pedido = self._proximo_pedido
        self._proximo_pedido += 1
        device.pedidos[pedido] = report
        device.fila.append(
            struct.pack("<IIBB", UHID_GET_REPORT, pedido, report, _UHID_FEATURE_REPORT)
        )

    def _desistir(self, device: _Device, motivo: str) -> None:
        """O caminho de erro do ``ps_probe``: ``hid_hw_close`` e ``hid_hw_stop``."""
        self.diario.append(motivo)
        self.diario.append(f"{device.nome}: Failed to create dualsense.")
        device.fila.append(struct.pack("<I", UHID_CLOSE))
        device.fila.append(struct.pack("<I", UHID_STOP))

    def _resposta(self, fd: int, device: _Device, dados: bytes) -> None:
        pedido, err, tamanho = struct.unpack("<IHH", dados[4:12])
        report = device.pedidos.pop(pedido, None)
        if report is None:
            return  # resposta atrasada de pedido que o kernel já largou
        corpo = dados[12 : 12 + tamanho]
        esperado = {
            _PAREAMENTO: _PAREAMENTO_TAMANHO,
            _FIRMWARE: _FIRMWARE_TAMANHO,
            _CALIBRACAO: _CALIBRACAO_TAMANHO,
        }[report]
        if err:
            self._desistir(device, f"Failed to retrieve feature with reportID {report}: -5")
            return
        if len(corpo) < esperado:
            self._desistir(
                device,
                f"Invalid byte count transferred, expected {esperado} got {len(corpo)}",
            )
            return
        if corpo[0] != report:
            self._desistir(
                device, f"Invalid reportID received, expected {report} got {corpo[0]}"
            )
            return
        if report == _PAREAMENTO:
            device.mac = bytes(corpo[1:7])
            self._pedir(device, _FIRMWARE)
        elif report == _FIRMWARE:
            assert device.mac is not None
            if device.mac in self.lista:
                recusa = f"Duplicate device found for MAC address {mac_impresso(device.mac)}."
                self.recusas.append(recusa)
                device.recusado = True
                self._desistir(device, recusa)
                self.diario.append(f"{device.nome}: probe failed with error -17")
                return
            self.lista[device.mac] = fd
            device.na_lista = True
            self._pedir(device, _CALIBRACAO)

    def _destruir(self, fd: int, device: _Device) -> None:
        """``ps_remove``: o MAC sai da lista junto com o device."""
        if device.na_lista and device.mac is not None and self.lista.get(device.mac) == fd:
            del self.lista[device.mac]
        device.na_lista = False
        device.criado = False
        device.fila.clear()

    # -- a leitura da régua ---------------------------------------------------

    def macs_na_lista(self) -> list[str]:
        """Os MACs dos vpads vivos que o driver registrou (sem os físicos)."""
        return sorted(mac_impresso(m) for m, dono in self.lista.items() if dono is not None)

    def instalar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Põe este kernel no lugar do ``os`` do ``uhid_gamepad`` — e só dele.

        E o vpad ``uinput`` do recuo nasce sobre um device de mentira: o
        ``UinputGamepad.start`` roda inteiro, mas o ``UInput`` do python-evdev
        (o ``/dev/uinput`` de verdade) nunca é chamado.

        Um kernel novo é uma máquina nova: o dono dos MACs vestidos também
        nasce vazio. Sem isto, os vpads das bancadas de testes anteriores (que
        ninguém para, e que os ciclos de referência mantêm vivos até o coletor
        passar) seguiriam vestindo os MACs deste teste.
        """
        monkeypatch.setattr(
            uhid_gamepad, "_MACS_DOS_VPADS_VIVOS", uhid_gamepad._MacsDosVpadsVivos()
        )
        monkeypatch.setattr(uhid_gamepad, "os", _OsDoKernel(self))
        monkeypatch.setattr(
            uinput_gamepad.UinputGamepad,
            "_create_device",
            lambda _self, *, with_ff: _UinputDeMentira(),
        )


class _OsDoKernel:
    """O ``os`` que o ``uhid_gamepad`` enxerga: ``/dev/uhid`` é o kernel de mentira.

    Tudo o que não é ``/dev/uhid`` segue para o ``os`` de verdade, menos o que
    escreveria num fd: um fd que não é do kernel de mentira é recusado em voz
    alta, em vez de chegar a um fd real do processo.
    """

    def __init__(self, kernel: KernelDoHidPlaystation) -> None:
        self._kernel = kernel

    def open(self, caminho: str, _flags: int, *_a: Any, **_k: Any) -> int:
        return self._kernel.abrir(caminho)

    def write(self, fd: int, dados: bytes) -> int:
        return self._kernel.escrever(fd, bytes(dados))

    def read(self, fd: int, tamanho: int) -> bytes:
        return self._kernel.ler(fd, tamanho)

    def close(self, fd: int) -> None:
        self._kernel.fechar(fd)

    def set_blocking(self, fd: int, _bloqueante: bool) -> None:
        self._kernel._device(fd)

    def access(self, caminho: str, modo: int) -> bool:
        return True if caminho == UHID_NODE else os.access(caminho, modo)

    def __getattr__(self, nome: str) -> Any:
        return getattr(os, nome)


class _UinputDeMentira:
    """O ``UInput`` que o recuo ``uinput`` abriria: aceita tudo e não toca nada."""

    def write(self, *_a: Any) -> None:
        pass

    def syn(self) -> None:
        pass

    def close(self) -> None:
        pass

    def read_one(self) -> None:
        return None


#: Os cinco controles FÍSICOS das bancadas desta casa (faixa forjada): o kernel
#: de mentira nasce com eles na lista do driver, como o de verdade nasce com os
#: DualSense que estão na mesa.
FISICOS_DAS_BANCADAS = tuple(f"aa:bb:cc:00:00:0{n}" for n in range(1, 6))


@contextmanager
def kernel_de_mentira(monkeypatch: pytest.MonkeyPatch) -> Iterator[KernelDoHidPlaystation]:
    """O kernel de mentira no lugar do ``/dev/uhid``, com o registro de máscaras zerado.

    Um gerenciador de contexto, e não só a fixture: a régua da volta tardia
    (``test_o_buraco_de_quem_saiu_se_fecha_no_jogo.py``) monta a fixture dela
    com ele, sem importar o nome ``kernel`` (que ela sombrearia).
    """
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
        _zerar_registro_de_mascaras,
    )

    _zerar_registro_de_mascaras()
    k = KernelDoHidPlaystation(fisicos=FISICOS_DAS_BANCADAS)
    k.instalar(monkeypatch)
    try:
        yield k
    finally:
        _zerar_registro_de_mascaras()


@pytest.fixture
def kernel(monkeypatch: pytest.MonkeyPatch) -> Iterator[KernelDoHidPlaystation]:
    with kernel_de_mentira(monkeypatch) as k:
        yield k


# ---------------------------------------------------------------------------
# O dublê recusa como o real — senão a régua mede um kernel mais frouxo
# ---------------------------------------------------------------------------

#: Os três controles de mentira da mesa (octetos 4 e 5 zerados).
_FISICOS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03")


def _criar_na_mao(kernel: KernelDoHidPlaystation, mac: str, *, pid: int = 0x0DF2) -> int:
    """Um device de ``mac`` pelo protocolo cru, sem a classe do produto: o probe inteiro."""
    fd = kernel.abrir(UHID_NODE)
    evento = struct.pack("<I", UHID_CREATE2)
    evento += b"vpad".ljust(128, b"\0") + b"".ljust(64, b"\0") + mac.encode().ljust(64, b"\0")
    evento += struct.pack("<HH", 1, 0x03) + struct.pack("<IIII", DUALSENSE_VENDOR, pid, 0, 0)
    evento += b"\0" * 4096
    kernel.escrever(fd, evento)
    respostas = {
        _PAREAMENTO: bytes([_PAREAMENTO]) + mac_no_report(mac) + bytes(13),
        _FIRMWARE: bytes([_FIRMWARE]) + bytes(63),
        _CALIBRACAO: bytes([_CALIBRACAO]) + bytes(40),
    }
    while True:
        try:
            evento = kernel.ler(fd, 4096)
        except BlockingIOError:
            return fd
        if struct.unpack("<I", evento[:4])[0] != UHID_GET_REPORT:
            continue
        pedido, report = struct.unpack("<IB", evento[4:9])
        corpo = respostas[report]
        kernel.escrever(
            fd,
            struct.pack("<IIHH", UHID_GET_REPORT_REPLY, pedido, 0, len(corpo))
            + corpo.ljust(4096, b"\0"),
        )


class TestODubleDoKernel:
    """As recusas do driver, uma a uma: o dublê não pode ser mais frouxo que o real."""

    def test_o_mac_repetido_e_recusado_com_eexist(self) -> None:
        """MORDIDA do dublê: tirar a checagem da lista deixa os dois de pé."""
        kernel = KernelDoHidPlaystation()
        primeiro = _criar_na_mao(kernel, "02:fe:00:00:00:01")
        segundo = _criar_na_mao(kernel, "02:fe:00:00:00:01")

        assert kernel.devices[primeiro].na_lista
        assert kernel.devices[segundo].recusado and not kernel.devices[segundo].na_lista
        assert kernel.recusas == [
            "Duplicate device found for MAC address 02:fe:00:00:00:01."
        ]
        assert "probe failed with error -17" in kernel.diario[-1]

    def test_macs_diferentes_ficam_de_pe(self) -> None:
        kernel = KernelDoHidPlaystation()
        _criar_na_mao(kernel, "02:fe:00:00:00:01")
        _criar_na_mao(kernel, "02:fe:00:00:00:02")
        assert kernel.recusas == []
        assert kernel.macs_na_lista() == ["02:fe:00:00:00:01", "02:fe:00:00:00:02"]

    def test_o_destroy_devolve_o_mac_a_lista(self) -> None:
        """O ``ps_remove``: depois do ``DESTROY`` o mesmo MAC volta a ser aceito."""
        kernel = KernelDoHidPlaystation()
        fd = _criar_na_mao(kernel, "02:fe:00:00:00:01")
        kernel.escrever(fd, struct.pack("<I", UHID_DESTROY))
        _criar_na_mao(kernel, "02:fe:00:00:00:01")
        assert kernel.recusas == []

    def test_fechar_o_fd_tambem_devolve(self) -> None:
        kernel = KernelDoHidPlaystation()
        fd = _criar_na_mao(kernel, "02:fe:00:00:00:01")
        kernel.fechar(fd)
        _criar_na_mao(kernel, "02:fe:00:00:00:01")
        assert kernel.recusas == []

    def test_o_mac_de_um_fisico_da_mesa_tambem_e_recusado(self) -> None:
        """Os físicos estão na mesma lista do driver que os vpads."""
        kernel = KernelDoHidPlaystation(fisicos=_FISICOS)
        _criar_na_mao(kernel, _FISICOS[1])
        assert kernel.recusas == [f"Duplicate device found for MAC address {_FISICOS[1]}."]

    def test_resposta_curta_derruba_o_probe(self) -> None:
        """O ``__ps_get_report`` exige o tamanho exato: ``Invalid byte count``."""
        kernel = KernelDoHidPlaystation()
        fd = kernel.abrir(UHID_NODE)
        evento = struct.pack("<I", UHID_CREATE2) + bytes(256)
        evento += struct.pack("<HH", 1, 0x03) + struct.pack("<IIII", DUALSENSE_VENDOR, 0x0DF2, 0, 0)
        kernel.escrever(fd, evento + bytes(4096))
        fila = [struct.unpack("<I", kernel.ler(fd, 4096)[:4])[0] for _ in range(3)]
        assert fila == [UHID_START, UHID_OPEN, UHID_GET_REPORT]
        kernel.escrever(fd, struct.pack("<IIHH", UHID_GET_REPORT_REPLY, 1, 0, 7) + bytes(7))
        fila = [struct.unpack("<I", kernel.ler(fd, 4096)[:4])[0] for _ in range(2)]
        assert fila == [UHID_CLOSE, UHID_STOP]
        assert "Invalid byte count" in kernel.diario[0]

    def test_pid_que_nao_e_dualsense_nao_tem_probe(self) -> None:
        kernel = KernelDoHidPlaystation()
        fd = kernel.abrir(UHID_NODE)
        evento = struct.pack("<I", UHID_CREATE2) + bytes(256)
        evento += struct.pack("<HH", 1, 0x03) + struct.pack("<IIII", 0x045E, 0x028E, 0, 0)
        kernel.escrever(fd, evento + bytes(4096))
        with pytest.raises(BlockingIOError):
            kernel.ler(fd, 4096)

    def test_o_kernel_de_mentira_so_abre_o_uhid(self) -> None:
        with pytest.raises(PermissionError):
            KernelDoHidPlaystation().abrir("/dev/uinput")


# ---------------------------------------------------------------------------
# A régua do caso geral: dois vpads vivos QUAISQUER
# ---------------------------------------------------------------------------

#: Os quatro plásticos da mesa, na grafia colada que o co-op e o backend usam.
P1, P2, P3, P4 = (f"aabbcc00000{n}" for n in range(1, 5))

#: Os nascimentos que o produto faz, com a identidade e o número que a fábrica
#: recebe. O do posto e o do P1 que volta são IGUAIS de propósito: é o defeito.
NASCIMENTOS = {
    "posto-com-o-p1": (P1, 1),
    "o-p1-que-volta": (P1, 1),
    "o-p1-com-dois-pontos": ("aa:bb:cc:00:00:01", 3),
    "o-p2": (P2, 2),
    "clone-sem-endereco": ("dev:0003:054C:0CE6.0008", 1),
    "no-sem-endereco": ("path:/dev/input/event30", 1),
    "posto-do-boot": (None, 1),
}


def nascer(identity: str | None, player: int) -> Any:
    """Um vpad pela fábrica REAL — o mesmo caminho do posto e do co-op."""
    from hefesto_dualsense4unix.integrations.virtual_pad import make_virtual_pad

    return make_virtual_pad("dualsense", identity=identity, player=player, allow_uhid=True)


def de_pe_no_driver(kernel: KernelDoHidPlaystation, *vpads: Any) -> None:
    """Cada vpad é ``uhid``, está ligado, e o driver guarda exatamente os MACs deles."""
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import vpad_vivo

    for vpad in vpads:
        assert getattr(vpad, "backend", None) == "uhid", (
            f"caiu no uinput: {getattr(vpad, 'fallback_motivo', None)}"
        )
        assert vpad_vivo(vpad) and vpad.is_bound
    macs = [v.mac for v in vpads]
    assert len(set(macs)) == len(macs), f"dois vpads vivos com o mesmo MAC: {macs}"
    assert kernel.recusas == [], kernel.recusas
    assert kernel.macs_na_lista() == sorted(macs)


class TestDoisVpadsVivosQuaisquer:
    """O caso geral que a sprint pede: não é só o posto contra o P1 que volta."""

    @pytest.mark.parametrize(
        ("primeiro", "segundo"),
        list(itertools.combinations_with_replacement(NASCIMENTOS, 2)),
    )
    def test_nenhum_par_repete_o_mac(
        self, kernel: KernelDoHidPlaystation, primeiro: str, segundo: str
    ) -> None:
        """Todo par de nascimentos, inclusive dois com a MESMA identidade e o mesmo número.

        MORDIDA: ``vestir`` vestindo o pedido sem olhar quem veste reprova todo
        par que pede o mesmo MAC — o do posto com o P1 que volta, as duas
        grafias do mesmo plástico, e os três sem endereço no número 1.
        """
        a = nascer(*NASCIMENTOS[primeiro])
        b = nascer(*NASCIMENTOS[segundo])
        de_pe_no_driver(kernel, a, b)

    def test_a_mesa_cheia_com_quem_volta_e_os_sem_endereco(
        self, kernel: KernelDoHidPlaystation
    ) -> None:
        """O dia inteiro de uma mesa: o boot, a troca de máscara, os quatro, a volta tardia."""
        boot = nascer(None, 1)
        boot.stop()  # a troca de máscara: o posto renasce com o primário
        posto = nascer(P1, 1)
        secundarios = [nascer(P2, 2), nascer(P3, 3), nascer(P4, 4)]
        volta = nascer(P1, 1)
        clones = [nascer("dev:0003:054C:0CE6.0009", 2), nascer(None, 3)]
        de_pe_no_driver(kernel, posto, *secundarios, volta, *clones)


class TestOMacDeCadaLugarEEstavel:
    """O MAC de cada lugar é o mesmo a cada reconexão: o Steam Input e o jogo lembram dele."""

    def test_sem_colisao_cada_um_veste_o_mac_do_aparelho(
        self, kernel: KernelDoHidPlaystation
    ) -> None:
        """O caso de sempre não muda um byte: o MAC do aparelho.

        É o que a E3 prometeu: o jogo e o Steam Input reconhecem cada controle
        pelo MAC dele. (Quem VIBRA não sai daqui: o co-op diz quem alimenta
        cada vpad — A-HAPTICA-SEGUE-QUEM-ALIMENTA-O-VPAD-01.)
        """
        from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac

        mesa = {P1: 1, P2: 2, P3: 3, P4: 4}
        vpads = {uniq: nascer(uniq, n) for uniq, n in mesa.items()}
        de_pe_no_driver(kernel, *vpads.values())
        for uniq, vpad in vpads.items():
            assert vpad.mac == vpad_mac(uniq, mesa[uniq])
            assert vpad.mac == vpad_mac(uniq, 1), "o MAC do aparelho não depende do número"

    @pytest.mark.parametrize(
        "quem", ["posto-com-o-p1", "o-p2", "o-p3", "o-p4", "o-p1-que-volta"]
    )
    def test_a_reconexao_de_cada_lugar_volta_ao_mesmo_mac(
        self, kernel: KernelDoHidPlaystation, quem: str
    ) -> None:
        """Os quatro lugares e o P1 que voltou tarde: sai, volta, e veste o mesmo.

        Inclusive quem veste o MAC SEGUINTE — a mesma mesa o devolve do mesmo
        jeito. MORDIDA: ``despir`` que não devolve faz quem volta vestir o
        seguinte do seguinte.
        """
        entradas = {
            "posto-com-o-p1": (P1, 1),
            "o-p2": (P2, 2),
            "o-p3": (P3, 3),
            "o-p4": (P4, 4),
            "o-p1-que-volta": (P1, 1),
        }
        vpads = {nome: nascer(*e) for nome, e in entradas.items()}
        antes = {nome: v.mac for nome, v in vpads.items()}

        vpads[quem].stop()
        assert kernel.macs_na_lista() == sorted(m for n, m in antes.items() if n != quem)
        vpads[quem] = nascer(*entradas[quem])

        de_pe_no_driver(kernel, *vpads.values())
        assert {nome: v.mac for nome, v in vpads.items()} == antes

    def test_a_mesma_mesa_noutro_boot_veste_os_mesmos_macs(self) -> None:
        """O seguinte do mesmo aparelho não depende do processo — ``blake2b``, não ``hash()``.

        Dois interpretadores com sementes de hash diferentes, a mesma mesa (o
        posto com o P1 e o P1 que volta): os mesmos dois MACs.
        """
        codigo = (
            "import itertools;"
            "from hefesto_dualsense4unix.integrations.uhid_gamepad import "
            "vpad_macs_do_aparelho as v;"
            f"print(list(itertools.islice(v({P1!r}, 1), 3)))"
        )
        respostas = set()
        for semente in ("0", "1", "12345"):
            saida = subprocess.run(
                [sys.executable, "-c", codigo],
                capture_output=True,
                text=True,
                check=True,
                env=dict(os.environ, PYTHONHASHSEED=semente),
            )
            respostas.add(saida.stdout.strip())
        assert len(respostas) == 1, respostas


class TestAsFaixasDoMac:
    """Os MACs seguintes ficam na faixa do vpad e não invadem nenhum outro espaço."""

    def test_o_primeiro_e_sempre_o_da_e3(self) -> None:
        from hefesto_dualsense4unix.integrations.uhid_gamepad import (
            vpad_mac,
            vpad_macs_do_aparelho,
        )

        for identidade, numero in NASCIMENTOS.values():
            assert next(vpad_macs_do_aparelho(identidade, numero)) == vpad_mac(
                identidade, numero
            )

    @pytest.mark.parametrize("identidade", [P1, P2, P3, P4])
    def test_os_do_aparelho_ficam_no_espaco_derivado(self, identidade: str) -> None:
        from hefesto_dualsense4unix.integrations.uhid_gamepad import (
            player_mac,
            vpad_macs_do_aparelho,
        )

        macs = list(vpad_macs_do_aparelho(identidade, 2))
        assert len(set(macs)) == len(macs) == 64
        pisos = {player_mac(n) for n in range(1, 9)}
        for mac in macs:
            assert mac.startswith("02:fe:") and mac not in pisos, mac
            assert int(mac.split(":")[2], 16) & 0x80, mac

    @pytest.mark.parametrize("identidade", [None, "dev:0003:054C:0CE6.0008", "path:/x"])
    def test_os_sem_endereco_ficam_fora_do_piso_e_do_derivado(
        self, identidade: str | None
    ) -> None:
        from hefesto_dualsense4unix.integrations.uhid_gamepad import (
            player_mac,
            vpad_macs_do_aparelho,
        )

        primeiro, *seguintes = vpad_macs_do_aparelho(identidade, 3)
        assert primeiro == player_mac(3)
        pisos = {player_mac(n) for n in range(1, 9)}
        for mac in seguintes:
            octetos = mac.split(":")
            assert octetos[:4] == ["02", "fe", "00", "00"] and octetos[4] != "00", mac
            assert octetos[5] == "03" and mac not in pisos, mac


class TestODonoDevolve:
    """O MAC vestido volta ao dono em toda saída — senão o próximo muda de MAC."""

    def test_o_start_que_falha_nao_segura_o_mac(
        self, kernel: KernelDoHidPlaystation, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem ACL no ``/dev/uhid``, o vpad cai no uinput — e o MAC não fica preso.

        O vpad que não nasceu fica VIVO de propósito (a régua guarda cada um que
        a fábrica cria): solto, a referência fraca do dono morreria com ele e
        esconderia a falta do ``despir``. No daemon, quem o segura é qualquer
        ciclo de referência até o coletor passar.

        MORDIDA: tirar o ``despir`` do caminho de falha do ``start`` faz o
        próximo vpad do mesmo aparelho vestir o seguinte.
        """
        from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense, vpad_mac

        criados: list[UhidDualSense] = []
        fabricar = UhidDualSense.for_flavor.__func__  # type: ignore[attr-defined]

        def _guardando(cls: type[UhidDualSense], *a: Any, **k: Any) -> UhidDualSense | None:
            pad = fabricar(cls, *a, **k)
            if pad is not None:
                criados.append(pad)
            return pad

        monkeypatch.setattr(UhidDualSense, "for_flavor", classmethod(_guardando))
        kernel.recusar_aberturas = 1
        degradado = nascer(P1, 1)
        assert degradado.backend == "uinput"
        assert degradado.fallback_motivo == "uhid_start_falhou"

        de_novo = nascer(P1, 1)
        de_pe_no_driver(kernel, de_novo)
        assert de_novo.mac == vpad_mac(P1, 1)
        assert len(criados) == 2 and criados[0] is not de_novo

    def test_o_stop_devolve_so_depois_do_destroy(
        self, kernel: KernelDoHidPlaystation, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ordem do ``ps_remove``: no ``UHID_DESTROY`` o MAC ainda é deste vpad.

        MORDIDA: devolver antes de destruir (``despir`` antes do
        ``_destruir_o_device``) deixaria um vpad de outro fio vestir o MAC que
        o driver ainda guarda — e esta régua vê o MAC já solto no DESTROY.
        """
        vpad = nascer(P1, 1)
        vestidos_no_destroy: list[str | None] = []
        destruir = kernel._destruir

        def _espiar(fd: int, device: _Device) -> None:
            vestidos_no_destroy.append(uhid_gamepad._MACS_DOS_VPADS_VIVOS.vestido_por(vpad))
            destruir(fd, device)

        monkeypatch.setattr(kernel, "_destruir", _espiar)
        mac = vpad.mac
        vpad.stop()
        # Duas passagens: o `UHID_DESTROY` e o `close` do fd, e nas duas o MAC
        # ainda é dele.
        assert vestidos_no_destroy and set(vestidos_no_destroy) == {mac}, vestidos_no_destroy
        assert uhid_gamepad._MACS_DOS_VPADS_VIVOS.vestido_por(vpad) is None

    def test_dois_fios_nunca_vestem_o_mesmo(
        self, kernel: KernelDoHidPlaystation, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O posto renasce pelo fio do IPC e o co-op nasce pelo do laço — ao mesmo tempo.

        A pergunta «quem veste este MAC?» demora de propósito, e responde o que
        viu ANTES de demorar: sem o lock do dono, os dois fios ouvem «ninguém»
        juntos e vestem o mesmo. MORDIDA: tirar o ``with self._lock`` do
        ``vestir``.
        """
        from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

        class _PerguntaQueDemora(dict):  # type: ignore[type-arg]
            def get(self, chave: Any, padrao: Any = None) -> Any:
                visto = super().get(chave, padrao)
                time.sleep(0.05)
                return visto

        monkeypatch.setattr(
            uhid_gamepad._MACS_DOS_VPADS_VIVOS, "_vestido_por", _PerguntaQueDemora()
        )
        pads = [UhidDualSense(player=1, identity=P1) for _ in range(2)]
        vestidos: list[str] = []
        fios = [
            threading.Thread(
                target=lambda p=p: vestidos.append(uhid_gamepad._MACS_DOS_VPADS_VIVOS.vestir(p))
            )
            for p in pads
        ]
        for fio in fios:
            fio.start()
        for fio in fios:
            fio.join(timeout=5)
        assert len(vestidos) == 2 and len(set(vestidos)) == 2, vestidos
        for pad in pads:
            uhid_gamepad._MACS_DOS_VPADS_VIVOS.despir(pad)
