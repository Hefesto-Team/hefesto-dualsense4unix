"""O-LIMIAR-DO-GATILHO-DO-DSX-VALE-PARA-CADA-JOGADOR-01 — o corte é de cada jogador.

O `TriggerThreshold` do DSX guardava UM par no store, e só o pad do P1
(`dispatch_gamepad`) o lia: o co-op entregava o `l2` cru ao pad de P2 a P4.

Agora o limiar é guardado por MAC, para cada destino do pedido, e um dono só
(`gamepad.cortar_pelo_limiar`) corta no pad do P1 e no de cada jogador do
co-op. A mesa tem quatro controles no backend do produto (dois no cabo, dois
no rádio, sem hidraw), e o que se lê é o `ABS_Z` que o jogo veria no pad
virtual de cada um, nas máscaras DualSense e Xbox.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, cast

import pytest
from evdev import ecodes
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.daemon.udp_server import UdpHandler
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

MACS = tuple(f"AA:BB:CC:00:00:0{n}" for n in range(1, 5))
UNIQS = tuple(m.replace(":", "").lower() for m in MACS)
TRANSPORTES = (ConnectionType.USB, ConnectionType.BT, ConnectionType.USB, ConnectionType.BT)
MASCARAS = ("dualsense", "xbox")
LIMIAR = 100
ABAIXO = 60
ACIMA = 150
LIMIAR_SEM_INDICE = {"type": "TriggerThreshold", "parameters": ["left", LIMIAR]}
RESET = {"type": "ResetToUserSettings", "parameters": []}


def _handle(transporte: ConnectionType) -> Any:
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.leftMotor = 0
    inst.rightMotor = 0
    inst.light = DSLight()
    inst.audio = DSAudio()
    inst.triggerL = DSTrigger()
    inst.triggerR = DSTrigger()
    inst.conType = transporte
    inst._suppress_leds = True
    inst._rumble_active = False
    inst._rumble_stop_pending = False
    inst._bt_seq = 0
    inst._raw_trigger_right = None
    inst._raw_trigger_left = None
    inst.connected = True
    return inst


class _No:
    """O nó do uinput de mentira: guarda o último `ABS_Z` (o L2) que o jogo leria."""

    def __init__(self) -> None:
        self.l2: int | None = None

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        if tipo == ecodes.EV_ABS and codigo == ecodes.ABS_Z:
            self.l2 = valor

    def syn(self) -> None:
        pass


def _pad(mascara: str) -> tuple[UinputGamepad, _No]:
    no = _No()
    pad = UinputGamepad(flavor=mascara)
    pad._device = no
    pad._ecodes = ecodes
    return pad, no


class _Leitor:
    """O leitor do co-op: devolve o L2 que o teste põe na mão do jogador."""

    grab_state = "held"

    def __init__(self) -> None:
        self.l2 = 0

    def snapshot(self) -> Any:
        return SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=self.l2, r2_raw=0,
            buttons_pressed=frozenset(),
        )


class _Mesa:
    """P1 no `dispatch_gamepad`, P2 a P4 no `forward_all`, um store e um DSX só."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, mascara: str) -> None:
        monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
        monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
        reader = EvdevReader(device_path=None)
        reader._device_path = None
        self.backend = bp.PyDualSenseController(evdev_reader=reader)
        self.backend._handles = {
            mac: _handle(t) for mac, t in zip(MACS, TRANSPORTES, strict=True)
        }
        self.backend._primary_key = MACS[0]
        self.store = StateStore()
        self.dsx = UdpHandler(controller=self.backend, store=self.store)
        pads = [_pad(mascara) for _ in UNIQS]
        self.pads = [pad for pad, _ in pads]
        self.nos = [no for _, no in pads]
        self.daemon = SimpleNamespace(
            store=self.store,
            controller=SimpleNamespace(primary_uniq=UNIQS[0]),
            config=SimpleNamespace(coop_enabled=True, gamepad_flavor=mascara),
            identity_registry=None,
            _gamepad_device=self.pads[0],
            _coop_manager=None,
            _hotkey_manager=None,
        )
        self.coop = CoopManager(self.daemon)
        self.leitores = [_Leitor() for _ in UNIQS[1:]]
        for n, (uniq, leitor) in enumerate(zip(UNIQS[1:], self.leitores, strict=True), 2):
            self.coop._players[uniq] = _SecondaryPlayer(
                identity=uniq,
                evdev_path=f"/dev/input/event{n + 10}",
                reader=cast(Any, leitor),
                player_index=n,
                vpad=self.pads[n - 1],
            )

    def mandar(self, *instrucoes: dict[str, Any]) -> None:
        pacote = json.dumps({"instructions": list(instrucoes)}).encode("utf-8")
        self.dsx.handle_datagram(pacote, ("127.0.0.1", 40000))

    def apertar_l2(self, valor: int) -> list[int | None]:
        """Os quatro apertam o L2 em `valor`; devolve o `ABS_Z` de cada pad."""
        estado = SimpleNamespace(
            raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=valor, r2_raw=0
        )
        gp.dispatch_gamepad(self.daemon, estado, frozenset())
        for leitor in self.leitores:
            leitor.l2 = valor
        self.coop.forward_all()
        return [no.l2 for no in self.nos]


@pytest.mark.parametrize("mascara", MASCARAS)
def test_o_limiar_do_jogador_3_corta_so_no_pad_do_p3(
    monkeypatch: pytest.MonkeyPatch, mascara: str
) -> None:
    mesa = _Mesa(monkeypatch, mascara)
    mesa.backend.set_output_target(2)

    mesa.mandar(LIMIAR_SEM_INDICE)

    assert mesa.apertar_l2(ABAIXO) == [ABAIXO, ABAIXO, 0, ABAIXO]
    assert mesa.apertar_l2(ACIMA) == [ACIMA] * 4
    assert mesa.store.udp_trigger_thresholds_por_controle == {UNIQS[2]: (LIMIAR, 0)}


@pytest.mark.parametrize("mascara", MASCARAS)
def test_o_pedido_para_todos_corta_nos_quatro(
    monkeypatch: pytest.MonkeyPatch, mascara: str
) -> None:
    mesa = _Mesa(monkeypatch, mascara)
    mesa.backend.set_output_target(None)

    mesa.mandar(LIMIAR_SEM_INDICE)

    assert mesa.apertar_l2(ABAIXO) == [0] * 4
    assert mesa.apertar_l2(ACIMA) == [ACIMA] * 4


@pytest.mark.parametrize("mascara", MASCARAS)
def test_o_reset_devolve_os_quatro_a_zero(
    monkeypatch: pytest.MonkeyPatch, mascara: str
) -> None:
    mesa = _Mesa(monkeypatch, mascara)
    mesa.backend.set_output_target(None)
    mesa.mandar(LIMIAR_SEM_INDICE)
    assert mesa.apertar_l2(ABAIXO) == [0] * 4

    mesa.mandar(RESET)

    assert mesa.apertar_l2(ABAIXO) == [ABAIXO] * 4
    assert all(mesa.store.udp_trigger_threshold_de(u) == (0, 0) for u in UNIQS)


def test_sem_destino_o_pedido_falha_alto_e_ninguem_corta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mesa sem controle: o limiar não fica guardado para ninguém, e o erro conta."""
    mesa = _Mesa(monkeypatch, "dualsense")
    mesa.backend._handles = {}

    mesa.mandar(LIMIAR_SEM_INDICE)

    assert mesa.store.counter("udp.error.TriggerThreshold") == 1
    assert mesa.store.udp_trigger_thresholds_por_controle == {}
