"""O-EM-TODOS-DO-GATILHO-CHEGA-A-CADA-CONTROLE-DA-MESA-01 — «Todos» é cada controle.

O botão «Em todos» da aba Gatilhos mandava o par pela rota sem endereço do
daemon. Essa rota segue o destino da aba Conexões (com o seletor no P2, ela
escreve só no P2) e grava pelo `_record_desired_locked(None, …)`, que não solta o
bloco cru do jogo. A tela lembrava o efeito nas quatro colunas e o recado dizia
que ele foi para os controles ligados.

O backend e o servidor IPC são os do produto; os quatro handles são instâncias
do `_PinnedPyDualSense` sem hidraw, e o `common[10]` lido é o que o
`_build_common` montaria para o fio. A mesa tem P1 e P2 no cabo, P3 e P4 no
rádio.
"""
from __future__ import annotations

import pathlib
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

MACS = (
    "AA:BB:CC:00:00:01",
    "AA:BB:CC:00:00:02",
    "AA:BB:CC:00:00:03",
    "AA:BB:CC:00:00:04",
)
UNIQS = tuple(m.replace(":", "").lower() for m in MACS)
TRANSPORTES = (ConnectionType.USB, ConnectionType.USB, ConnectionType.BT, ConnectionType.BT)
BLOCO_DO_JOGO = bytes([0x21, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
RIGIDO = {"side": "right", "mode": "Rigid", "params": [5, 200]}


class _Daemon:
    def is_native_mode(self) -> bool:
        return False


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


def _mesa(tmp_path: Path) -> tuple[IpcServer, bp.PyDualSenseController]:
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    backend = bp.PyDualSenseController(evdev_reader=reader)
    backend._handles = {
        mac: _handle(t) for mac, t in zip(MACS, TRANSPORTES, strict=True)
    }
    backend._primary_key = MACS[0]
    store = StateStore()
    store.update_controller_state(
        ControllerState(battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb")
    )
    server = IpcServer(
        controller=backend,
        store=store,
        profile_manager=ProfileManager(controller=backend, store=store),
        socket_path=tmp_path / "em_todos.sock",
        daemon=_Daemon(),
    )
    return server, backend


def _o_que_sai(backend: bp.PyDualSenseController) -> list[int]:
    """O `common[10]` (modo do R2) que cada handle mandaria agora."""
    return [
        int(backend._handles[mac]._build_common(rumble_asserted=False)[10])
        for mac in MACS
    ]


def _modo_do_rigido() -> int:
    efeito = build_from_name(str(RIGIDO["mode"]), list(RIGIDO["params"]))
    modo: Any = bp.PyDualSenseController._coerce_mode(efeito.mode)
    return int(modo.value)


@pytest.mark.asyncio
async def test_com_o_destino_no_p2_o_em_todos_chega_aos_quatro(tmp_path: Path) -> None:
    server, backend = _mesa(tmp_path)
    backend.set_output_target(1)

    resposta = await server._handle_trigger_set({**RIGIDO, "todos": True})

    assert _o_que_sai(backend) == [_modo_do_rigido()] * 4, (
        "o «Em todos» seguiu o destino da aba Conexões"
    )
    assert sorted(resposta["aplicado_em"]) == sorted(UNIQS)
    assert resposta["guardado_em"] == []
    assert backend._desired_default.trigger_right is not None, (
        "o padrão que um controle novo herda não foi gravado"
    )


@pytest.mark.asyncio
async def test_sem_todos_a_rota_sem_endereco_continua_no_destino(tmp_path: Path) -> None:
    """A rota clássica (CLI, seletor global) não muda: segue a Conexões."""
    server, backend = _mesa(tmp_path)
    backend.set_output_target(1)

    resposta = await server._handle_trigger_set(dict(RIGIDO))

    sai = _o_que_sai(backend)
    assert sai[1] == _modo_do_rigido()
    assert sai[0] == sai[2] == sai[3] != _modo_do_rigido()
    assert resposta["aplicado_em"] == [UNIQS[1]]


@pytest.mark.asyncio
async def test_o_em_todos_vence_o_bloco_que_o_jogo_pendurou(tmp_path: Path) -> None:
    server, backend = _mesa(tmp_path)
    assert backend.set_game_trigger_for(MACS[2], "right", BLOCO_DO_JOGO) is True
    assert _o_que_sai(backend)[2] == BLOCO_DO_JOGO[0]

    await server._handle_trigger_set({**RIGIDO, "todos": True})

    assert _o_que_sai(backend) == [_modo_do_rigido()] * 4, (
        "o bloco do jogo continuou saindo no P3 depois do «Em todos»"
    )
    assert UNIQS[2] not in backend._game_triggers_by_uniq


@pytest.mark.asyncio
async def test_o_desligar_em_todos_tambem_chega_aos_quatro(tmp_path: Path) -> None:
    server, backend = _mesa(tmp_path)
    await server._handle_trigger_set({**RIGIDO, "todos": True})
    backend.set_output_target(1)
    backend.set_game_trigger_for(MACS[3], "right", BLOCO_DO_JOGO)

    resposta = await server._handle_trigger_reset({"side": "right", "todos": True})

    modo: Any = bp.PyDualSenseController._coerce_mode(build_from_name("Off", []).mode)
    desligado = int(modo.value)
    assert _o_que_sai(backend) == [desligado] * 4
    assert sorted(resposta["aplicado_em"]) == sorted(UNIQS)


# A ponta da janela: a aba Gatilhos, com a ponte dublada.

class _Ponte:
    """O daemon que responde em quem pegou, e anota o que recebeu."""

    def __init__(self, aplicado_em: list[str]) -> None:
        self.aplicado_em = aplicado_em
        self.enviados: list[dict[str, Any]] = []

    def _corpo(self) -> tuple[bool, None, dict[str, Any]]:
        return True, None, {"status": "ok", "aplicado_em": list(self.aplicado_em),
                            "guardado_em": []}

    def trigger_set_detalhado(self, lado: str, modo: str, params: list[int],
                              uniq: str | None = None, todos: bool = False) -> Any:
        self.enviados.append({"lado": lado, "modo": modo, "uniq": uniq, "todos": todos})
        return self._corpo()

    def trigger_reset_detalhado(self, lado: str, uniq: str | None = None,
                                todos: bool = False) -> Any:
        self.enviados.append({"lado": lado, "modo": "Off", "uniq": uniq, "todos": todos})
        return self._corpo()

    def chamar(self, metodo: str, **_: Any) -> bool:
        return True


PERFIL = "Em todos"


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

    estado: dict[str, Any] = {PERFIL: Profile(name=PERFIL, match=MatchManual())}

    def _grava(prof: Any, **_: Any) -> None:
        estado[prof.name] = prof

    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n], raising=False)
    monkeypatch.setattr(loader, "save_profile", _grava, raising=False)
    return estado


@pytest.fixture(autouse=True)
def rascunho_limpo() -> Iterator[None]:
    from pacotes.a03_gatilhos import esquecer_o_rascunho

    esquecer_o_rascunho()
    yield
    esquecer_o_rascunho()


def _clique_em_todos(ctx: Any, ponte: _Ponte) -> Any:
    import pacotes
    from pacotes.a03_gatilhos import GESTO_DE_TODOS

    gesto = pacotes.gesto_da_pagina("03-gatilhos.html", GESTO_DE_TODOS)
    assert gesto is not None
    return gesto(ctx, {"uniq": UNIQS[0], "controle": "p1",
                       "forma": {"modo-chave-d": "Pulse"}}, ponte)


def _ctx() -> Any:
    import pacotes

    mesa = [{"uniq": u, "transport": "usb" if i < 2 else "bt", "connected": True,
             "player": i + 1} for i, u in enumerate(UNIQS)]
    return pacotes.Contexto(state={"active_profile": PERFIL, "controllers": mesa},
                            mesa=[], conectados=mesa, estados={})


def test_o_pedido_vai_com_todos(disco: dict[str, Any]) -> None:
    ponte = _Ponte(list(UNIQS))

    _clique_em_todos(_ctx(), ponte)

    assert ponte.enviados == [
        {"lado": "right", "modo": "Pulse", "uniq": "", "todos": True}
    ], "o «Em todos» voltou à rota sem endereço, que segue a aba Conexões"


def test_so_quem_recebeu_lembra_o_rascunho(disco: dict[str, Any]) -> None:
    from pacotes.a03_gatilhos import _do_rascunho

    ponte = _Ponte(list(UNIQS[:3]))

    r = _clique_em_todos(_ctx(), ponte)

    lembram = [u for u in UNIQS if (_do_rascunho(u, "right") or {}).get("mode") == "Pulse"]
    assert lembram == list(UNIQS[:3]), (
        "a coluna do P4, que não recebeu, ficou com o efeito na tela"
    )
    recado = r["recado"]
    for jogador in (1, 2, 3):
        assert f"Controle {jogador}" in recado
    assert "Controle 4" not in recado
