"""As traseiras e os Fn do Edge chegam em toda máscara, no cabo e no rádio, de P1 e de P2.

O Edge forjado é lido pela `pydualsense` instalada, no cabo e no rádio, e entregue pelo
caminho de P1 (`dispatch_gamepad`) e de P2 (`CoopManager.forward_all`) a cada roupa: o Edge e o
comum no `UhidDualSense` com o fd no `/dev/null`, o Xbox, o Nintendo e o DualSense do uinput num
nó de mentira que só anota o que se escreve. Nenhum nó de verdade nasce.
"""
from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSBattery, DSState, pydualsense

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.evdev_reader import BOTOES_DO_EDGE, EvdevReader
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import uinput_gamepad as ug
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

ecodes = pytest.importorskip("evdev").ecodes

BITS = {
    "fn_esquerdo": 0x10, "fn_direito": 0x20, "traseira_esquerda": 0x40, "traseira_direita": 0x80,
}
TODOS = 0xF0
APERTOS = (*BITS.values(), TODOS)
P2 = "aabbcc000002"

DECLARADO: dict[str, dict[str, str] | None] = {
    "edge": None,
    "comum": None,
    "xbox": {
        "traseira_direita": "BTN_TRIGGER_HAPPY5",
        "fn_direito": "BTN_TRIGGER_HAPPY6",
        "traseira_esquerda": "BTN_TRIGGER_HAPPY7",
        "fn_esquerdo": "BTN_TRIGGER_HAPPY8",
    },
    "nintendo": {
        "fn_esquerdo": "BTN_TRIGGER_HAPPY1",
        "fn_direito": "BTN_TRIGGER_HAPPY2",
        "traseira_esquerda": "BTN_TRIGGER_HAPPY3",
        "traseira_direita": "BTN_TRIGGER_HAPPY4",
    },
    "dualsense-uinput": {
        "fn_esquerdo": "BTN_TRIGGER_HAPPY1",
        "fn_direito": "BTN_TRIGGER_HAPPY2",
        "traseira_esquerda": "BTN_TRIGGER_HAPPY3",
        "traseira_direita": "BTN_TRIGGER_HAPPY4",
    },
    "xbox-vestido": {
        "traseira_direita": "BTN_TRIGGER_HAPPY5",
        "fn_direito": "BTN_TRIGGER_HAPPY6",
        "traseira_esquerda": "BTN_TRIGGER_HAPPY7",
        "fn_esquerdo": "BTN_TRIGGER_HAPPY8",
    },
}
ROUPAS = tuple(DECLARADO)


def _nomes(aperto: int) -> frozenset[str]:
    return frozenset(nome for nome, bit in BITS.items() if aperto & bit)


def _edge(aperto: int, *, radio: bool) -> pydualsense:
    ds = pydualsense()
    ds.state = DSState()
    ds.battery = DSBattery()
    ds.is_edge = True
    ds.connected = True
    ds.conType = ConnectionType.BT if radio else ConnectionType.USB
    relatorio = [0] * (78 if radio else 64)
    relatorio[0] = 0x31 if radio else 0x01
    base = 1 if radio else 0
    for i in range(1, 5):
        relatorio[base + i] = 0x80
    relatorio[base + 8] = 0x08
    relatorio[base + 10] = aperto
    ds.readInput(relatorio)
    return ds


class _SemEvdev:
    def is_available(self) -> bool:
        return False


def _backend(ds: pydualsense) -> PyDualSenseController:
    backend = PyDualSenseController(evdev_reader=cast(Any, _SemEvdev()))
    backend._ds = ds
    return backend


class _NoDeMentira:
    """O nó do uinput sem kernel: guarda o último valor de cada tecla escrita.

    Como o kernel, descarta a tecla que o nó não declarou ao nascer: o repasse para um código fora
    das capacidades não chega ao jogo.
    """

    def __init__(self, declaradas: list[int]) -> None:
        self.declaradas = frozenset(declaradas)
        self.teclas: dict[int, int] = {}

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        if tipo == ecodes.EV_KEY and codigo in self.declaradas:
            self.teclas[codigo] = valor

    def syn(self) -> None:
        return None


class _Pad:
    """Uma roupa de pé e o jeito de ler o que chegou das quatro ao nó da roupa."""

    def __init__(self, roupa: str, jogador: int, abertos: list[int]) -> None:
        self.roupa = roupa
        if roupa in ("edge", "comum"):
            produto = 0x0DF2 if roupa == "edge" else 0x0CE6
            pad = UhidDualSense(player=jogador, blueprint=None, product=produto)
            pad._fd = os.open(os.devnull, os.O_WRONLY)
            abertos.append(pad._fd)
            self.reports: list[bytes] = []
            enviar = pad.send_report

            def gravar(report: bytes) -> bool:
                self.reports.append(bytes(report))
                return enviar(report)

            pad.send_report = gravar  # type: ignore[method-assign]
            self.pad: Any = pad
            return
        sabor = {"dualsense-uinput": "dualsense", "xbox-vestido": "dualsense"}.get(roupa, roupa)
        uinput = ug.UinputGamepad.for_flavor(sabor)
        if roupa == "xbox-vestido":
            uinput.vestir("xbox")
        caps = ug._build_capabilities(with_ff=False, flavor=uinput.mascara_no_jogo)
        self.no = _NoDeMentira(caps[ecodes.EV_KEY])
        uinput._device = self.no
        uinput._ecodes = ecodes
        self.pad = uinput

    def chegou(self) -> int:
        """Os bits das quatro que o jogo vê agora, no formato do relatório do Edge.

        No pad Sony, quem lê o relatório é o `hid-playstation`, que só lê os quatro no 0DF2
        (`test_o_driver_so_le_os_quatro_no_edge`): no 0CE6 eles não chegam ao jogo.
        """
        if hasattr(self, "reports"):
            assert self.reports, "o pad não emitiu relatório"
            return self.reports[-1][10] & TODOS if self.pad.product == 0x0DF2 else 0
        tabela = DECLARADO[self.roupa]
        assert tabela is not None
        return sum(
            BITS[nome]
            for nome, tecla in tabela.items()
            if self.no.teclas.get(getattr(ecodes, tecla)) == 1
        )


def _esperado(roupa: str, aperto: int) -> int:
    return 0 if roupa == "comum" else aperto


@pytest.fixture
def fazer_pad() -> Iterator[Callable[[str, int], _Pad]]:
    abertos: list[int] = []
    yield lambda roupa, jogador: _Pad(roupa, jogador, abertos)
    for fd in abertos:
        os.close(fd)


@pytest.fixture(autouse=True)
def _so_o_caminho_do_botao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)


def _daemon(backend: PyDualSenseController, pad: Any) -> SimpleNamespace:
    return SimpleNamespace(
        controller=backend,
        store=SimpleNamespace(udp_trigger_thresholds=(0, 0)),
        _gamepad_device=pad,
        _mouse_device=None,
        _input_ready_at=0.0,
    )


def _entregar_ao_p1(pad: _Pad, aperto: int, radio: bool) -> None:
    backend = _backend(_edge(aperto, radio=radio))
    backend._evdev = EvdevReader(device_path=Path("/nao/existe/event-do-p1"))
    gp.dispatch_gamepad(cast(Any, _daemon(backend, pad.pad)), backend.read_state(), frozenset())


def _entregar_ao_p2(pad: _Pad, aperto: int, radio: bool) -> None:
    backend = _backend(_edge(0, radio=radio))
    backend._handles[P2] = _edge(aperto, radio=radio)
    gerente = co.CoopManager.__new__(co.CoopManager)
    gerente._daemon = _daemon(backend, None)
    gerente._players = {
        P2: co._SecondaryPlayer(
            identity=P2,
            evdev_path="/dev/input/event-do-p2",
            reader=EvdevReader(device_path=Path("/nao/existe/event-do-p2")),
            player_index=2,
            vpad=pad.pad,
        )
    }
    gerente.forward_all()


@pytest.mark.parametrize("jogador", [1, 2], ids=["P1", "P2"])
@pytest.mark.parametrize("radio", [False, True], ids=["cabo", "radio"])
@pytest.mark.parametrize("aperto", APERTOS, ids=lambda a: f"{a:#04x}")
@pytest.mark.parametrize("roupa", ROUPAS)
def test_cada_uma_das_quatro_chega_ao_botao_declarado_da_roupa(
    roupa: str, aperto: int, radio: bool, jogador: int,
    fazer_pad: Callable[[str, int], _Pad],
) -> None:
    """MORDIDA: tirar o repasse de uma roupa (a tabela sem os quatro) reprova os casos da roupa."""
    pad = fazer_pad(roupa, jogador)
    entregar = _entregar_ao_p1 if jogador == 1 else _entregar_ao_p2

    entregar(pad, aperto, radio)
    assert pad.chegou() == _esperado(roupa, aperto)

    entregar(pad, 0, radio)
    assert pad.chegou() == 0


@pytest.mark.parametrize("mascara", sorted(ug.FLAVORS))
def test_os_quatro_nascem_declarados_depois_de_todo_botao_da_mascara(mascara: str) -> None:
    """O nó declara os quatro, e nenhum `bN` que o SDL conta por posição se desloca."""
    base = list(ug.CAPACIDADES_POR_FLAVOR[mascara](with_ff=False)[ecodes.EV_KEY])
    caps = ug._build_capabilities(with_ff=False, flavor=mascara)[ecodes.EV_KEY]
    extras = [getattr(ecodes, t) for t in ug.TRASEIRAS_POR_FLAVOR[mascara].values()]

    assert caps[: len(base)] == base
    assert sorted(caps[len(base):]) == sorted(extras)
    assert min(extras) > max(base)
    assert set(ug.TRASEIRAS_POR_FLAVOR[mascara]) == set(BOTOES_DO_EDGE.values())


def _o_driver_do_7_2() -> str:
    return (
        Path(__file__).resolve().parents[2]
        / "assets/dkms/hid-playstation/fonte-por-kernel/7.2.6-76070206/hid-playstation.c"
    ).read_text(encoding="utf-8")


def test_o_driver_so_le_os_quatro_no_edge() -> None:
    """O `is_edge` nasce só no PID do Edge, e só com ele o driver escreve os quatro."""
    fonte = _o_driver_do_7_2()
    ramo = re.search(
        r"\} else if \(hdev->product == USB_DEVICE_ID_SONY_PS5_CONTROLLER_2\) \{\n"
        r"(?:\t\t[^\n]*\n)*?\t\tds->is_edge = true;",
        fonte,
    )
    assert ramo is not None
    assert fonte.count("ds->is_edge = true;") == 1
    assert "\tif (ds->is_edge) {\n\t\tinput_report_key(ds->gamepad, BTN_TRIGGER_HAPPY1," in fonte


def test_as_mascaras_de_tabela_sony_seguem_o_hid_playstation_do_edge() -> None:
    """O par bit -> tecla do `hid-playstation` do 7.2, lido no fonte que a casa guarda."""
    fonte = _o_driver_do_7_2()
    pares = {
        "DS_EDGE_BUTTONS_FN1": ("BTN_TRIGGER_HAPPY1", "fn_esquerdo"),
        "DS_EDGE_BUTTONS_FN2": ("BTN_TRIGGER_HAPPY2", "fn_direito"),
        "DS_EDGE_BUTTONS_LEFT_PADDLE": ("BTN_TRIGGER_HAPPY3", "traseira_esquerda"),
        "DS_EDGE_BUTTONS_RIGHT_PADDLE": ("BTN_TRIGGER_HAPPY4", "traseira_direita"),
    }
    for bit, (tecla, nome) in pares.items():
        assert f"{tecla},\n\t\t\t\t ds_report->buttons[2] & {bit}" in fonte, bit
        assert ug.TRASEIRAS_POR_FLAVOR["dualsense"][nome] == tecla
        assert ug.TRASEIRAS_POR_FLAVOR["nintendo"][nome] == tecla
