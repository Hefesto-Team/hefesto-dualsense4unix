"""O-DSX-ACENDE-O-JOGADOR-QUE-O-MOD-PEDE-01 — o índice do mod é o jogador.

O `UdpHandler` descartava o `controllerIndex` do DSX e chamava `controller.set_*`
sem destino: com quatro controles e o seletor em «Todos», o que o mod pedia para
um jogador ia aos quatro, inclusive o índice 0, que quase todo mod manda.

Agora o índice 0 é o jogador 1 e o 3 é o jogador 4, e a instrução escreve só no
MAC dele. Índice sem jogador na mesa é descartado e contado, nunca vira «todos».
O dialeto do Hefesto, sem índice, segue o seletor.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import OutputSpec, ResultadoDeSaida
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.udp import start_udp
from hefesto_dualsense4unix.daemon.udp_server import UdpHandler
from hefesto_dualsense4unix.testing import FakeController

UNIQS = tuple(f"aabbcc00000{n}" for n in range(1, 5))
JOGADORES = {uniq: n for n, uniq in enumerate(UNIQS, 1)}
ENDERECO = ("127.0.0.1", 40000)


class _QuatroControles(FakeController):
    """Quatro DualSense na mesa, com a escrita por MAC que o backend real tem."""

    def __init__(self) -> None:
        super().__init__(transport="usb")
        self.por_mac: list[tuple[str, str, Any]] = []

    def uniqs_do_destino(self) -> list[str]:
        return list(UNIQS)

    def set_game_trigger_for(self, uniq: str, side: str, bloco: bytes) -> bool:
        self.por_mac.append((uniq, f"gatilho.{side}", bytes(bloco)))
        return True

    def soltar_o_gatilho_do_jogo_for(self, uniq: str, side: str, bloco: bytes) -> bool:
        self.por_mac.append((uniq, f"solta.{side}", bytes(bloco)))
        return True

    def apply_output_for(self, uniq: str, spec: OutputSpec) -> ResultadoDeSaida:
        self.por_mac.append((uniq, "saida", spec))
        return "escreveu"

    def set_trigger(self, side: Any, effect: Any) -> None:
        self.por_mac.append(("todos", f"set_trigger.{side}", effect))

    def donos_de(self, tipo: str) -> list[str]:
        return [uniq for uniq, que, _ in self.por_mac if que == tipo]


def _mesa(
    jogadores: dict[str, int] | None = None,
) -> tuple[UdpHandler, _QuatroControles, StateStore]:
    fc = _QuatroControles()
    store = StateStore()
    numeros = dict(JOGADORES if jogadores is None else jogadores)
    return UdpHandler(controller=fc, store=store, jogadores=lambda: numeros), fc, store


def _mandar(handler: UdpHandler, *instrucoes: dict[str, Any]) -> None:
    pacote = json.dumps({"instructions": list(instrucoes)}).encode("utf-8")
    handler.handle_datagram(pacote, ENDERECO)


# `TriggerUpdate` no layout do DSX: [indice, lado, modo, ...]; lado 2 = R2, modo 21 = Feedback.
def _gatilho(indice: int) -> dict[str, Any]:
    return {"type": 1, "parameters": [indice, 2, 21, 3, 8]}


def _cor(indice: int) -> dict[str, Any]:
    return {"type": 2, "parameters": [indice, 10, 20, 30]}


def test_o_trigger_update_do_indice_1_muda_so_o_gatilho_do_jogador_2() -> None:
    handler, fc, store = _mesa()

    _mandar(handler, _gatilho(1))

    assert fc.donos_de("gatilho.right") == [UNIQS[1]]
    assert fc.donos_de("set_trigger.right") == []
    assert store.counter("udp.applied.TriggerUpdate") == 1


@pytest.mark.parametrize("indice", [0, 3])
def test_o_rgb_update_acende_so_a_barra_do_jogador_pedido(indice: int) -> None:
    handler, fc, store = _mesa()

    _mandar(handler, _cor(indice))

    assert fc.por_mac == [(UNIQS[indice], "saida", OutputSpec(led=(10, 20, 30)))]
    assert [c for c in fc.commands if c.kind == "set_led"] == []
    assert store.counter("udp.applied.RGBUpdate") == 1


def test_o_indice_sem_jogador_nao_muda_ninguem_e_conta() -> None:
    handler, fc, store = _mesa()

    _mandar(
        handler,
        _gatilho(7),
        _cor(7),
        {"type": 3, "parameters": [7, 1, 0, 0, 0, 0]},
        {"type": 5, "parameters": [7, 0]},
        {"type": 4, "parameters": [7, 1, 90]},
        {"type": 7, "parameters": [7]},
    )

    assert fc.por_mac == []
    assert fc.commands == []
    assert store.counter("udp.indice_sem_jogador") == 6
    assert store.counter("udp.error.RGBUpdate") == 0
    assert store.counter("udp.applied.RGBUpdate") == 0
    assert store.udp_trigger_thresholds_por_controle == {}


def test_o_controle_sem_mac_ainda_e_o_jogador_1_do_indice_0() -> None:
    """Um DualSense só, por cabo sem serial (ou antes de o MAC resolver): a fila vem vazia.

    O co-op deixa fora quem não tem MAC (`_alvos_de_numeracao`), então
    `numeros_de_jogador` é `{}` com o controle na mesa. O índice 0, que quase
    todo mod manda, é ele, pela rota sem endereço; o índice 1 não tem jogador.
    """
    fc = _QuatroControles()
    fc.connect()
    store = StateStore()
    handler = UdpHandler(controller=fc, store=store, jogadores=dict)

    _mandar(handler, _cor(0), _cor(1))

    assert [c.kind for c in fc.commands if c.kind == "set_led"] == ["set_led"]
    assert fc.por_mac == []
    assert store.counter("udp.applied.RGBUpdate") == 1
    assert store.counter("udp.indice_sem_jogador") == 1


def test_a_mesa_vazia_descarta_o_indice_0() -> None:
    """Sem controle nenhum, o índice 0 não tem jogador: nada se grava para depois."""
    handler = UdpHandler(controller=_QuatroControles(), store=StateStore(), jogadores=dict)

    _mandar(handler, _cor(0))

    assert handler.controller.commands == []
    assert handler.store.counter("udp.indice_sem_jogador") == 1


def test_o_dialeto_do_hefesto_sem_indice_segue_o_seletor() -> None:
    handler, fc, store = _mesa()

    _mandar(handler, {"type": "TriggerUpdate", "parameters": ["right", "Rigid", 5, 200]})
    _mandar(handler, {"type": "TriggerThreshold", "parameters": ["left", 100]})

    assert fc.donos_de("gatilho.right") == list(UNIQS)
    assert set(store.udp_trigger_thresholds_por_controle) == set(UNIQS)
    assert store.counter("udp.indice_sem_jogador") == 0


def test_o_indice_vale_o_numero_do_jogador_e_nao_a_posicao() -> None:
    """O jogador 1 da mesa pode ser o terceiro handle: o número vem da fila de chegada."""
    invertido = {UNIQS[2]: 1, UNIQS[0]: 2, UNIQS[3]: 3, UNIQS[1]: 4}
    handler, fc, _ = _mesa(invertido)

    _mandar(handler, _cor(0), _cor(1))

    assert fc.donos_de("saida") == [UNIQS[2], UNIQS[0]]


def test_o_player_led_e_o_mic_led_vao_so_ao_controle_do_indice() -> None:
    handler, fc, _ = _mesa()

    _mandar(
        handler,
        {"type": 3, "parameters": [2, 1, 0, 1, 0, 1]},
        {"type": 5, "parameters": [3, 2]},
    )

    assert fc.por_mac == [
        (UNIQS[2], "saida", OutputSpec(player_leds=(True, False, True, False, True))),
        (UNIQS[3], "saida", OutputSpec(mic_led=False)),
    ]
    assert [c for c in fc.commands if c.kind in ("set_player_leds", "set_mic_led")] == []


def test_o_mic_led_sem_indice_segue_o_seletor() -> None:
    handler, fc, _ = _mesa()

    _mandar(handler, {"type": 5, "parameters": [1]})

    assert [c.kind for c in fc.commands if c.kind == "set_mic_led"] == ["set_mic_led"]
    assert fc.por_mac == []


def test_o_limiar_e_o_reset_do_indice_so_mexem_no_jogador_dele() -> None:
    handler, fc, store = _mesa()
    _mandar(handler, {"type": 4, "parameters": [1, 1, 90]}, {"type": 4, "parameters": [2, 1, 70]})
    _mandar(handler, _gatilho(1), _gatilho(2))
    assert store.udp_trigger_thresholds_por_controle == {
        UNIQS[1]: (90, 0),
        UNIQS[2]: (70, 0),
    }

    _mandar(handler, {"type": 7, "parameters": [1]})

    assert fc.donos_de("solta.right") == [UNIQS[1]]
    assert store.udp_trigger_threshold_de(UNIQS[1]) == (0, 0)
    assert store.udp_trigger_threshold_de(UNIQS[2]) == (70, 0)


def test_o_reset_sem_indice_solta_todos() -> None:
    handler, fc, store = _mesa()
    _mandar(handler, _gatilho(0), _gatilho(3), {"type": 4, "parameters": [0, 1, 90]})

    _mandar(handler, {"type": 7, "parameters": []})

    assert sorted(fc.donos_de("solta.right")) == [UNIQS[0], UNIQS[3]]
    assert store.udp_trigger_thresholds_por_controle == {}


def _handle() -> Any:
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.leftMotor = 0
    inst.rightMotor = 0
    inst.light = DSLight()
    inst.audio = DSAudio()
    inst.triggerL = DSTrigger()
    inst.triggerR = DSTrigger()
    inst.conType = ConnectionType.USB
    inst._suppress_leds = True
    inst._rumble_active = False
    inst._rumble_stop_pending = False
    inst._bt_seq = 0
    inst._raw_trigger_right = None
    inst._raw_trigger_left = None
    inst.connected = True
    return inst


def test_no_backend_do_produto_a_cor_do_indice_3_fica_so_no_quarto_controle() -> None:
    """O backend real, sem `jogadores`: o número vem da posição em `describe_controllers`."""
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    backend = bp.PyDualSenseController(evdev_reader=reader)
    macs = [f"AA:BB:CC:00:00:0{n}" for n in range(1, 5)]
    backend._handles = {mac: _handle() for mac in macs}
    backend._primary_key = macs[0]
    handler = UdpHandler(controller=backend, store=StateStore())

    _mandar(handler, _cor(3))

    com_cor = {u for u, o in backend._desired_by_uniq.items() if o.led is not None}
    assert com_cor == {UNIQS[3]}
    assert backend._desired_by_uniq[UNIQS[3]].led == (10, 20, 30)


@pytest.mark.asyncio
async def test_o_start_udp_entrega_ao_servidor_a_fonte_dos_jogadores() -> None:
    """A fiação: o daemon passa a pergunta «quem é cada jogador» ao `UdpServer`."""
    coop = SimpleNamespace(numeros_de_jogador=lambda: dict(JOGADORES))
    daemon = SimpleNamespace(
        controller=FakeController(transport="usb"),
        store=StateStore(),
        config=SimpleNamespace(udp_host="127.0.0.1", udp_port=0),
        _coop_manager=coop,
        _udp_server=None,
    )

    await start_udp(daemon)
    try:
        assert daemon._udp_server is not None
        assert daemon._udp_server.jogadores is not None
        assert dict(daemon._udp_server.jogadores()) == JOGADORES
    finally:
        await daemon._udp_server.stop()
