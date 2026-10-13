"""O-DSX-PINTA-COMO-JOGO-E-O-RESET-DEVOLVE-O-PERFIL-01 — o mod pinta como jogo.

O `TriggerUpdate` do servidor DSX terminava no `set_trigger`, que grava como
desejo da pessoa: com o destino num controle, carimbava `usuaria` por cima do
perfil dele; em «Todos», escrevia o padrão e zerava o gatilho do perfil de
cada controle. O `ResetToUserSettings` mandava Off pelo mesmo caminho, e o
perfil não voltava.

Agora o efeito do mod vai à camada do JOGO de cada MAC de destino, o reset
solta só o que o DSX pintou, e o gesto da pessoa vence o mod. O backend é o do
produto; os dois handles são `_PinnedPyDualSense` sem hidraw (um no cabo, um
no rádio), e o que se lê é o `common` que o `_build_common` mandaria ao fio.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import trigger_effects as te
from hefesto_dualsense4unix.core.controller import OutputSpec, TriggerEffect
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.udp_server import UdpHandler

MACS = ("AA:BB:CC:00:00:01", "AA:BB:CC:00:00:02")
UNIQS = tuple(m.replace(":", "").lower() for m in MACS)
TRANSPORTES = (ConnectionType.USB, ConnectionType.BT)
PERFIL_P1 = te.rigid(2, 100)
PERFIL_P2 = te.rigid(6, 250)
GESTO = te.weapon(3, 6, 8)
#: `TriggerUpdate` no layout canônico do DSX: índice 0, lado 2 (R2), modo 21
#: (Feedback, extensão do DualSenseY-v2) com posição 3 e força 8.
DSX_FEEDBACK = {"type": 1, "parameters": [0, 2, 21, 3, 8]}
DSX_RESET = {"type": 7, "parameters": [0]}
R2 = slice(10, 21)
L2 = slice(21, 32)


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


def _mesa(destino: int | None) -> tuple[bp.PyDualSenseController, UdpHandler]:
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    backend = bp.PyDualSenseController(evdev_reader=reader)
    backend._handles = {
        mac: _handle(t) for mac, t in zip(MACS, TRANSPORTES, strict=True)
    }
    backend._primary_key = MACS[0]
    backend.set_output_target(destino)
    backend.reset_profile_overrides(
        {
            UNIQS[0]: OutputSpec(trigger_right=PERFIL_P1),
            UNIQS[1]: OutputSpec(trigger_right=PERFIL_P2),
        }
    )
    return backend, UdpHandler(controller=backend, store=StateStore())


def _mandar(handler: UdpHandler, *instrucoes: dict[str, Any]) -> None:
    pacote = json.dumps({"instructions": list(instrucoes)}).encode("utf-8")
    handler.handle_datagram(pacote, ("127.0.0.1", 40000))


def _r2(backend: bp.PyDualSenseController, mac: str) -> bytes:
    return bytes(backend._handles[mac]._build_common(rumble_asserted=False)[R2])


def _gatilho_do_perfil(backend: bp.PyDualSenseController, uniq: str) -> TriggerEffect | None:
    override = backend._desired_by_uniq.get(uniq)
    return None if override is None else override.trigger_right


def _dono(backend: bp.PyDualSenseController, uniq: str) -> str | None:
    return backend._desired_owner_by_uniq.get(uniq, {}).get("trigger_right")


BLOCO_DSX = te.bloco_do_efeito(te.feedback(3, 8))


@pytest.mark.parametrize("destino", [0, None], ids=["destino-no-p1", "todos"])
def test_o_trigger_update_pinta_como_jogo_e_nao_apaga_o_perfil(destino: int | None) -> None:
    backend, handler = _mesa(destino)

    _mandar(handler, DSX_FEEDBACK)

    assert _r2(backend, MACS[0]) == BLOCO_DSX
    # O índice 0 do mod é o jogador 1: o seletor em «Todos» não o espalha.
    assert _r2(backend, MACS[1]) == te.bloco_do_efeito(PERFIL_P2)
    for uniq, perfil in zip(UNIQS, (PERFIL_P1, PERFIL_P2), strict=True):
        assert _gatilho_do_perfil(backend, uniq) == perfil, "o mod apagou o perfil"
        assert _dono(backend, uniq) == "perfil", "o mod virou gesto da pessoa"
    assert backend._desired_default.trigger_right is None
    assert handler.store.counter("udp.applied.TriggerUpdate") == 1


@pytest.mark.parametrize("destino", [0, None], ids=["destino-no-p1", "todos"])
def test_o_reset_devolve_o_rigido_do_perfil_de_cada_controle(destino: int | None) -> None:
    backend, handler = _mesa(destino)
    _mandar(handler, DSX_FEEDBACK)

    _mandar(handler, DSX_RESET)

    assert _r2(backend, MACS[0]) == te.bloco_do_efeito(PERFIL_P1)
    assert _r2(backend, MACS[1]) == te.bloco_do_efeito(PERFIL_P2)
    assert backend._game_triggers_by_uniq == {}
    assert all(
        getattr(h, "_raw_trigger_right", None) is None for h in backend._handles.values()
    )


def test_o_reset_nao_solta_o_que_o_jogo_repintou_por_cima() -> None:
    backend, handler = _mesa(0)
    _mandar(handler, DSX_FEEDBACK)
    do_jogo = bytes([0x26, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    assert backend.set_game_trigger_for(UNIQS[0], "right", do_jogo)

    _mandar(handler, DSX_RESET)

    assert _r2(backend, MACS[0]) == do_jogo


def test_o_gesto_da_pessoa_vence_o_mod_e_o_reset_nao_o_desfaz() -> None:
    backend, handler = _mesa(0)
    _mandar(handler, DSX_FEEDBACK)

    assert backend.apply_output_for(UNIQS[0], OutputSpec(trigger_right=GESTO)) == "escreveu"
    assert _r2(backend, MACS[0]) == te.bloco_do_efeito(GESTO)

    _mandar(handler, DSX_RESET)

    assert _r2(backend, MACS[0]) == te.bloco_do_efeito(GESTO)
    assert _gatilho_do_perfil(backend, UNIQS[0]) == GESTO


EFEITOS_OFICIAIS: dict[str, TriggerEffect] = {
    "off": te.off(),
    "rigid": te.rigid(4, 180),
    "feedback": te.feedback(3, 8),
    "weapon": te.weapon(2, 7, 6),
    "vibration": te.vibration(1, 5, 30),
    "bow": te.bow(1, 6, 7, 4),
    "galloping": te.galloping(0, 9, 6, 7, 10),
    "machine": te.machine(1, 8, 5, 40),
    "slope": te.slope_feedback(1, 8, 2, 7),
    "multi_feedback": te.multi_position_feedback([1, 2, 3, 4, 5, 6, 7, 0, 1, 2]),
    "multi_vibration": te.multi_position_vibration(30, [1, 2, 3, 4, 5, 6, 7, 0, 1, 2]),
    "custom": te.custom(0x25, (10, 200, 3, 4, 5, 6, 77)),
}


@pytest.mark.parametrize("nome", sorted(EFEITOS_OFICIAIS))
def test_o_bloco_do_dono_novo_e_o_do_build_common_byte_a_byte(nome: str) -> None:
    efeito = EFEITOS_OFICIAIS[nome]
    handle = _handle(ConnectionType.USB)
    bp.PyDualSenseController._apply_trigger(handle, "right", efeito)
    bp.PyDualSenseController._apply_trigger(handle, "left", efeito)

    common = handle._build_common(rumble_asserted=False)

    f = efeito.forces
    layout_do_fio = bytes([efeito.mode, f[0], f[1], f[2], f[3], f[4], f[5], 0, 0, f[6], 0])
    assert te.bloco_do_efeito(efeito) == layout_do_fio
    assert bytes(common[R2]) == layout_do_fio
    assert bytes(common[L2]) == layout_do_fio
