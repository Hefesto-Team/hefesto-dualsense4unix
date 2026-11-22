"""O controle abre sem esperar o primeiro report — O-CONTROLE-ABRE-SEM-ESPERAR-O-PRIMEIRO-REPORT-01.

O hidraw de mentira é um fd de verdade (`socketpair`) que nunca entrega report: o rádio calado.
O transporte vem do `HID_ID` do uevent, e a abertura não lê o aparelho.
"""

from __future__ import annotations

import contextlib
import os
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydualsense.enums import ConnectionType

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

LIMITE_DA_ABERTURA_SEC = 0.100
GUARDA_DE_TESTE_SEC = 0.6
AVISO_DE_SILENCIO_SEC = 0.15

CABO = "0003"
RADIO = "0005"


class _Diario:
    def __init__(self) -> None:
        self.linhas: list[tuple[str, dict[str, Any]]] = []

    def _guardar(self, evento: str, **campos: Any) -> None:
        self.linhas.append((evento, campos))

    debug = info = warning = error = _guardar

    def eventos(self, nome: str) -> list[dict[str, Any]]:
        return [campos for evento, campos in self.linhas if evento == nome]


class _Mesa:
    """Os hidraw de mentira: um nó no `/sys` e um fd mudo por controle."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.pares: dict[int, tuple[socket.socket, socket.socket]] = {}
        self.abertos: list[Any] = []

    def no(self, numero: int, barramento: str) -> bytes:
        pasta = self.raiz / f"hidraw{numero}" / "device"
        pasta.mkdir(parents=True)
        (pasta / "uevent").write_text(
            f"HID_ID={barramento}:0000054C:00000CE6\nHID_UNIQ=aa:bb:cc:00:00:{numero:02x}\n",
            encoding="utf-8",
        )
        return f"/dev/hidraw{numero}".encode()

    def dispositivo(self, numero: int) -> bp._DispositivoPorFd:
        dentro, fora = socket.socketpair()
        self.pares[numero] = (dentro, fora)
        fd = os.dup(dentro.fileno())
        dentro.close()
        return bp._DispositivoPorFd(fd)

    def falar(self, numero: int, report: bytes) -> None:
        self.pares[numero][1].send(report)

    def soltar(self) -> None:
        for h in self.abertos:
            with contextlib.suppress(Exception):
                h.close()
        for dentro, fora in self.pares.values():
            for ponta in (dentro, fora):
                with contextlib.suppress(OSError):
                    ponta.close()


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Mesa]:
    raiz = tmp_path / "hidraw"
    raiz.mkdir()
    monkeypatch.setattr(bp, "RAIZ_CLASS_HIDRAW", str(raiz))
    monkeypatch.setattr(bp, "INIT_TIMEOUT_SEC", GUARDA_DE_TESTE_SEC)
    monkeypatch.setattr(bp, "LEITURA_VAZIA_AVISO_SEC", AVISO_DE_SILENCIO_SEC)
    m = _Mesa(raiz)
    yield m
    m.soltar()


@pytest.fixture
def controlador() -> PyDualSenseController:
    leitor = EvdevReader(device_path=None)
    leitor._device_path = None
    return PyDualSenseController(evdev_reader=leitor)


def _abrir(
    controlador: PyDualSenseController, mesa: _Mesa, numero: int, caminho: bytes
) -> tuple[Any, float]:
    inicio = time.monotonic()
    handle = controlador._abrir_handle_pinado(
        caminho, is_edge=False, dispositivo=mesa.dispositivo(numero)
    )
    gasto = time.monotonic() - inicio
    if handle is not None:
        mesa.abertos.append(handle)
    return handle, gasto


def _report_do_radio() -> bytes:
    corpo = bytearray(prr.INPUT_REPORT_BT_SIZE)
    corpo[0] = prr.INPUT_REPORT_BT
    crc = prr.bt_crc32(bytes(corpo[:-4]), seed=prr.BT_INPUT_CRC_SEED)
    corpo[-4:] = crc.to_bytes(4, "little")
    return bytes(corpo)


def _report_do_cabo() -> bytes:
    corpo = bytearray(64)
    corpo[0] = prr.INPUT_REPORT_USB
    return bytes(corpo)


def _fios_de_abertura() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name == "hefesto-ds-init" and t.is_alive()]


def _fds_abertos() -> int:
    return len(os.listdir("/proc/self/fd"))


def test_os_quatro_abrem_sem_report_com_o_transporte_certo(
    mesa: _Mesa, controlador: PyDualSenseController
) -> None:
    """D-2211-O-CONTROLE-ABRE-SEM-ESPERAR-O-PRIMEIRO-REPORT: dois cabo e dois rádio, nenhum fd
    entrega report, e a abertura não espera."""
    plano = [(0, CABO, ConnectionType.USB, 64), (1, RADIO, ConnectionType.BT, 78),
             (2, CABO, ConnectionType.USB, 64), (3, RADIO, ConnectionType.BT, 78)]
    for numero, barramento, tipo, comprimento in plano:
        caminho = mesa.no(numero, barramento)
        handle, gasto = _abrir(controlador, mesa, numero, caminho)
        assert handle is not None, "a abertura esperou o report e o guarda desistiu"
        assert gasto < LIMITE_DA_ABERTURA_SEC, (
            f"a abertura esperou o report: hidraw{numero} levou {gasto:.3f}s"
        )
        assert handle.conType is tipo
        assert handle.input_report_length == comprimento
        assert handle.output_report_length == comprimento
    assert _fios_de_abertura() == [], "um fio de abertura ficou parado num read"


def test_nenhum_fio_fica_parado_num_read_bloqueante(
    mesa: _Mesa, controlador: PyDualSenseController
) -> None:
    """A volta de cada controle lê sem espera: nenhum fd fica em `read` bloqueante."""
    handles = []
    for numero, barramento in ((0, CABO), (1, RADIO)):
        caminho = mesa.no(numero, barramento)
        handle, _ = _abrir(controlador, mesa, numero, caminho)
        handles.append(handle)
    time.sleep(0.2)
    assert all(h.device._bloqueante is False for h in handles), (
        "o fd de um controle calado ficou em leitura bloqueante"
    )
    assert all(h.report_thread.is_alive() for h in handles)


def test_o_calado_aparece_como_entrada_muda_e_volta_com_o_report(
    mesa: _Mesa, controlador: PyDualSenseController, monkeypatch: pytest.MonkeyPatch
) -> None:
    diario = _Diario()
    monkeypatch.setattr(bp, "logger", diario)
    caminho = mesa.no(4, RADIO)
    handle, _ = _abrir(controlador, mesa, 4, caminho)
    assert handle is not None
    limite = time.monotonic() + 3.0
    while not diario.eventos("report_thread_entrada_muda") and time.monotonic() < limite:
        time.sleep(0.02)
    assert diario.eventos("report_thread_entrada_muda"), "o silêncio do controle não foi medido"
    mesa.falar(4, _report_do_radio())
    limite = time.monotonic() + 3.0
    while not diario.eventos("report_thread_entrada_voltou") and time.monotonic() < limite:
        time.sleep(0.02)
    assert diario.eventos("report_thread_entrada_voltou"), "o report que veio não fechou o silêncio"


def test_o_cabo_calado_tambem_abre_e_volta(
    mesa: _Mesa, controlador: PyDualSenseController, monkeypatch: pytest.MonkeyPatch
) -> None:
    diario = _Diario()
    monkeypatch.setattr(bp, "logger", diario)
    caminho = mesa.no(5, CABO)
    handle, gasto = _abrir(controlador, mesa, 5, caminho)
    assert handle is not None and gasto < LIMITE_DA_ABERTURA_SEC
    mesa.falar(5, _report_do_cabo())
    limite = time.monotonic() + 3.0
    while handle._reports_aceitos == 0 and time.monotonic() < limite:
        time.sleep(0.02)
    assert handle._reports_aceitos >= 1


def test_sete_voltas_com_o_calado_nao_acumulam_fios_nem_fds(
    mesa: _Mesa, controlador: PyDualSenseController
) -> None:
    """O guarda de 5 s deixava um fio e um fd novos a cada volta; agora não sobra nenhum."""
    caminho = mesa.no(6, RADIO)
    fios_antes = threading.active_count()
    fds_antes = _fds_abertos()
    for _ in range(7):
        handle, gasto = _abrir(controlador, mesa, 6, caminho)
        assert handle is not None, "a abertura esperou o report"
        assert gasto < LIMITE_DA_ABERTURA_SEC
        handle.close()
        mesa.abertos.remove(handle)
        for ponta in mesa.pares[6]:
            ponta.close()
    assert _fios_de_abertura() == []
    assert threading.active_count() <= fios_antes, "a volta deixou fio para trás"
    assert _fds_abertos() <= fds_antes, "a volta deixou fd para trás"


def test_no_sem_hid_id_cai_na_leitura_com_prazo(
    mesa: _Mesa, controlador: PyDualSenseController
) -> None:
    """Sem `HID_ID` legível a leitura de hoje fica, mas com prazo: o mudo não prende o fio."""
    caminho = b"/dev/hidraw77"
    inicio = time.monotonic()
    handle = None
    try:
        handle, _ = _abrir(controlador, mesa, 77, caminho)
    except Exception as exc:
        assert "connection type" in str(exc)
    assert time.monotonic() - inicio < GUARDA_DE_TESTE_SEC + 0.5
    assert handle is None or handle.conType is not ConnectionType.ERROR
    assert _fios_de_abertura() == [], "a leitura sem prazo segurou o fio"


def test_no_sem_hid_id_com_report_decide_pelo_tamanho(
    mesa: _Mesa, controlador: PyDualSenseController
) -> None:
    caminho = b"/dev/hidraw78"
    dispositivo = mesa.dispositivo(78)
    mesa.falar(78, _report_do_radio())
    ds = bp._PinnedPyDualSense(caminho, is_edge=False, dispositivo=dispositivo)
    ds.device = dispositivo
    assert ds.determineConnectionType() is ConnectionType.BT
    assert ds.input_report_length == 78
