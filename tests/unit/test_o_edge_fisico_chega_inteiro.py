"""O Edge físico entrega as traseiras e os Fn ao pad do Hefesto, de P1 a P4, no cabo e no rádio.

O relatório é forjado e lido pela `pydualsense` instalada; o pad é o `UhidDualSense` de verdade
com o fd no `/dev/null`. O kernel não mapeia os bits 4 a 7 do `buttons[2]` no evdev
(`assets/dkms/hid-playstation/hid-playstation.c:191-193`), então eles só chegam pelo hidraw.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSBattery, DSState, pydualsense

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.evdev_reader import (
    BOTOES_DO_EDGE,
    EvdevReader,
    EvdevSnapshot,
)
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

FN_ESQUERDO, FN_DIREITO, TRASEIRA_ESQUERDA, TRASEIRA_DIREITA = 0x10, 0x20, 0x40, 0x80
TODOS = FN_ESQUERDO | FN_DIREITO | TRASEIRA_ESQUERDA | TRASEIRA_DIREITA
NOMES = {
    FN_ESQUERDO: "fn_esquerdo",
    FN_DIREITO: "fn_direito",
    TRASEIRA_ESQUERDA: "traseira_esquerda",
    TRASEIRA_DIREITA: "traseira_direita",
}
MASCARAS = (FN_ESQUERDO, FN_DIREITO, TRASEIRA_ESQUERDA, TRASEIRA_DIREITA, TODOS)
P2 = "aabbcc000002"


def _nomes(mascara: int) -> frozenset[str]:
    return frozenset(nome for bit, nome in NOMES.items() if mascara & bit)


def _edge(mascara: int, *, radio: bool, edge: bool = True) -> pydualsense:
    """Um Edge da `pydualsense` instalada que acabou de ler um relatório forjado."""
    ds = pydualsense()
    ds.state = DSState()
    ds.battery = DSBattery()
    ds.is_edge = edge
    ds.connected = True
    ds.conType = ConnectionType.BT if radio else ConnectionType.USB
    relatorio = [0] * (78 if radio else 64)
    relatorio[0] = 0x31 if radio else 0x01
    base = 1 if radio else 0
    for i in range(1, 5):
        relatorio[base + i] = 0x80
    relatorio[base + 8] = 0x08
    relatorio[base + 10] = mascara
    ds.readInput(relatorio)
    return ds


class _SemEvdev:
    def is_available(self) -> bool:
        return False


class _EvdevSoDaCruz(EvdevReader):
    def __init__(self) -> None:
        super().__init__(device_path=None)

    def is_available(self) -> bool:
        return True

    def snapshot(self) -> EvdevSnapshot:
        return EvdevSnapshot(l2_raw=0, r2_raw=0, buttons_pressed=frozenset({"cross"}))


def _backend(ds: pydualsense, *, evdev: bool) -> PyDualSenseController:
    leitor: Any = _EvdevSoDaCruz() if evdev else _SemEvdev()
    backend = PyDualSenseController(evdev_reader=leitor)
    backend._ds = ds
    return backend


@pytest.fixture
def fazer_uhid() -> Iterator[Callable[[int], tuple[UhidDualSense, list[bytes]]]]:
    abertos: list[UhidDualSense] = []

    def fazer(n: int) -> tuple[UhidDualSense, list[bytes]]:
        pad = UhidDualSense(player=n, blueprint=None)
        pad._fd = os.open(os.devnull, os.O_WRONLY)
        reports: list[bytes] = []
        enviar = pad.send_report

        def gravar(report: bytes) -> bool:
            reports.append(bytes(report))
            return enviar(report)

        pad.send_report = gravar  # type: ignore[method-assign]
        abertos.append(pad)
        return pad, reports

    yield fazer
    for pad in abertos:
        fd, pad._fd = pad._fd, None
        if fd is not None:
            os.close(fd)


@pytest.fixture(autouse=True)
def _so_o_caminho_do_botao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)


def _bits_do_pad(reports: list[bytes]) -> int:
    assert reports, "o pad não emitiu relatório"
    return reports[-1][10] & TODOS


def test_os_nomes_do_edge_sao_os_do_estado_da_pydualsense() -> None:
    assert BOTOES_DO_EDGE == {
        "L4": "fn_esquerdo",
        "R4": "fn_direito",
        "L5": "traseira_esquerda",
        "R5": "traseira_direita",
    }


@pytest.mark.parametrize("radio", [False, True], ids=["cabo", "radio"])
@pytest.mark.parametrize("evdev", [True, False], ids=["com-evdev", "sem-evdev"])
@pytest.mark.parametrize("mascara", MASCARAS)
def test_o_relatorio_do_edge_chega_ao_estado_do_controle(
    mascara: int, evdev: bool, radio: bool
) -> None:
    estado = _backend(_edge(mascara, radio=radio), evdev=evdev).read_state()
    assert estado.buttons_pressed & frozenset(NOMES.values()) == _nomes(mascara)
    if evdev:
        assert "cross" in estado.buttons_pressed


@pytest.mark.parametrize("radio", [False, True], ids=["cabo", "radio"])
def test_o_dualsense_comum_nao_ganha_traseira(radio: bool) -> None:
    ds = _edge(TODOS, radio=radio)
    ds.is_edge = False
    estado = _backend(ds, evdev=True).read_state()
    assert not estado.buttons_pressed & frozenset(NOMES.values())


@pytest.mark.parametrize("mascara", MASCARAS)
def test_o_pad_do_hefesto_repete_o_byte_do_fisico(
    mascara: int, fazer_uhid: Callable[[int], tuple[UhidDualSense, list[bytes]]]
) -> None:
    pad, reports = fazer_uhid(1)
    pad.forward_buttons(_nomes(mascara))
    assert _bits_do_pad(reports) == mascara
    pad.forward_buttons(frozenset())
    assert _bits_do_pad(reports) == 0


def _daemon_do_p1(pad: Any, controle: Any) -> SimpleNamespace:
    controle._evdev = EvdevReader(device_path=Path("/nao/existe/event-do-p1"))
    return SimpleNamespace(
        controller=controle,
        store=SimpleNamespace(udp_trigger_thresholds=(0, 0)),
        _gamepad_device=pad,
        _mouse_device=None,
        _input_ready_at=0.0,
    )


@pytest.mark.parametrize("radio", [False, True], ids=["cabo", "radio"])
@pytest.mark.parametrize("mascara", MASCARAS)
def test_o_p1_edge_entrega_as_traseiras_e_os_fn_ao_jogo(
    mascara: int,
    radio: bool,
    fazer_uhid: Callable[[int], tuple[UhidDualSense, list[bytes]]],
) -> None:
    pad, reports = fazer_uhid(1)
    backend = _backend(_edge(mascara, radio=radio), evdev=False)
    estado = backend.read_state()
    gp.dispatch_gamepad(cast(Any, _daemon_do_p1(pad, backend)), estado, frozenset())
    assert _bits_do_pad(reports) == mascara


@pytest.mark.parametrize("radio", [False, True], ids=["cabo", "radio"])
@pytest.mark.parametrize("mascara", MASCARAS)
def test_o_edge_do_p2_ao_p4_entrega_as_traseiras_e_os_fn_ao_jogo(
    mascara: int,
    radio: bool,
    fazer_uhid: Callable[[int], tuple[UhidDualSense, list[bytes]]],
) -> None:
    pad, reports = fazer_uhid(2)
    backend = _backend(_edge(0, radio=radio), evdev=False)
    backend._handles[P2] = _edge(mascara, radio=radio)
    gerente = co.CoopManager.__new__(co.CoopManager)
    gerente._daemon = SimpleNamespace(
        controller=backend,
        store=SimpleNamespace(udp_trigger_thresholds=(0, 0)),
        _gamepad_device=None,
        _mouse_device=None,
        _input_ready_at=0.0,
    )
    gerente._players = {
        P2: co._SecondaryPlayer(
            identity=P2,
            evdev_path="/dev/input/event-do-p2",
            reader=EvdevReader(device_path=Path("/nao/existe/event-do-p2")),
            player_index=2,
            vpad=cast(Any, pad),
        )
    }
    gerente.forward_all()
    assert _bits_do_pad(reports) == mascara


def test_o_controle_de_fora_nao_pergunta_pelo_edge() -> None:
    perguntas: list[str | None] = []

    def ler(uniq: str | None) -> set[str]:
        perguntas.append(uniq)
        return {"fn_esquerdo"}

    gerente = co.CoopManager.__new__(co.CoopManager)
    gerente._daemon = SimpleNamespace(controller=SimpleNamespace(botoes_do_edge=ler))
    de_fora = co._SecondaryPlayer(
        identity="aabbcc0000fe",
        evdev_path="/dev/input/event-do-pro",
        reader=cast(Any, None),
        player_index=2,
        externo=True,
    )
    assert gerente._botoes_do_edge(de_fora) == frozenset()
    assert perguntas == []
