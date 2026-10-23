"""O-BASICO-MEDIDO-01 (C10): o estado completo diz a camada da usuária de cada controle.

O ``led.set``, o ``trigger.*`` e o ``led.player_set`` com ``uniq`` entram na camada
``usuaria`` do backend, que sobrevive a hotplug e vence todo perfil automático. Sem o
campo ``controllers[].camada_da_usuaria`` a volta de um ajuste pelo IPC era invisível: o
protocolo do básico (``scripts/o_basico.py``) não tinha com que conferi-la.

O dono é o ``PyDualSenseController`` (``camada_da_usuaria_de``), o mesmo mapa de procedência
que o merge lê; o ``describe_controllers`` o publica e o ``daemon.state_full`` o leva. Backend
REAL com handles de mentira, MAC na faixa forjada ``aa:bb:cc``.
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from tests.unit.test_backend_multi_controller import (
    KEY_1,
    KEY_2,
    UNIQ_1,
    UNIQ_2,
    _FakeHandle,
    _null_evdev,
)

RAIZ = Path(__file__).resolve().parents[2]


def _backend() -> PyDualSenseController:
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    inst._handles = {KEY_1: _FakeHandle(), KEY_2: _FakeHandle()}
    inst._primary_key = KEY_1
    return inst


def _camadas(inst: PyDualSenseController) -> dict[str, Any]:
    return {str(c["uniq"]): c["camada_da_usuaria"] for c in inst.describe_controllers()}


def test_o_controle_sem_ajuste_dela_diz_lista_vazia() -> None:
    assert _camadas(_backend()) == {UNIQ_1: [], UNIQ_2: []}


def test_o_ajuste_com_uniq_entra_so_no_controle_dele() -> None:
    inst = _backend()
    inst.apply_output_for(UNIQ_2, OutputSpec(led=(0, 255, 0)))
    assert _camadas(inst) == {UNIQ_1: [], UNIQ_2: ["led"]}


def test_os_campos_vem_na_ordem_do_contrato_e_o_gatilho_conta() -> None:
    from hefesto_dualsense4unix.core.controller import TriggerEffect

    inst = _backend()
    inst.apply_output_for(
        UNIQ_1,
        OutputSpec(
            led=(1, 2, 3),
            trigger_right=TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0)),
        ),
    )
    assert _camadas(inst)[UNIQ_1] == ["trigger_right", "led"]


def test_soltar_a_camada_devolve_a_lista_vazia() -> None:
    inst = _backend()
    inst.apply_output_for(UNIQ_1, OutputSpec(led=(0, 255, 0)))
    inst.clear_user_output_overrides()
    assert _camadas(inst) == {UNIQ_1: [], UNIQ_2: []}


def test_o_que_e_do_perfil_nao_e_da_usuaria() -> None:
    """Só a procedência `usuaria` conta: o campo do perfil não é ajuste dela."""
    inst = _backend()
    inst.apply_output_for(UNIQ_1, OutputSpec(led=(0, 255, 0)))
    inst._desired_owner_by_uniq[UNIQ_1]["led"] = bp._LAYER_PROFILE
    assert _camadas(inst)[UNIQ_1] == []


def test_o_dono_vazio_nao_inventa_camada() -> None:
    """Dono carimbado sem valor no override (rastro velho) não conta como ajuste."""
    inst = _backend()
    inst.apply_output_for(UNIQ_1, OutputSpec(led=(0, 255, 0)))
    inst._desired_by_uniq[UNIQ_1].led = None
    assert _camadas(inst)[UNIQ_1] == []


def test_a_chave_sem_endereco_nao_tem_camada() -> None:
    assert _backend().camada_da_usuaria_de("/dev/hidraw3") == []


async def _estado_completo(inst: PyDualSenseController, tmp: Path) -> dict[str, Any]:
    server = IpcServer(
        controller=inst,
        store=StateStore(),
        profile_manager=ProfileManager(controller=inst, store=StateStore()),
        socket_path=tmp / "h.sock",
        daemon=None,
    )
    chamada = getattr(server, "_handle_daemon_" + "state" + "_full")
    resposta = await chamada({})
    assert isinstance(resposta, dict)
    return resposta


def test_o_estado_completo_do_daemon_leva_a_camada_de_cada_controle(tmp_path: Path) -> None:
    inst = _backend()
    inst.apply_output_for(UNIQ_2, OutputSpec(led=(0, 255, 0)))
    resposta = asyncio.run(_estado_completo(inst, tmp_path))
    por_uniq = {c["uniq"]: c.get("camada_da_usuaria") for c in resposta["controllers"]}
    assert por_uniq == {UNIQ_1: [], UNIQ_2: ["led"]}


def _o_basico() -> ModuleType:
    spec = importlib.util.spec_from_file_location("o_basico_camada", RAIZ / "scripts/o_basico.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def test_a_volta_do_protocolo_ve_a_camada_que_ficou() -> None:
    """O protocolo do básico confere o campo: o ajuste que sobra é diferença da volta."""
    ob = _o_basico()
    antes = {"controllers": [{"player": 1, "uniq": UNIQ_1, "camada_da_usuaria": []}]}
    depois = {"controllers": [{"player": 1, "uniq": UNIQ_1, "camada_da_usuaria": ["led"]}]}
    a, d = ob.campos_da_volta(antes), ob.campos_da_volta(depois)
    assert a["P1.camada_da_usuaria"] == [] and d["P1.camada_da_usuaria"] == ["led"]
    assert a != d


@pytest.mark.parametrize("campo", ["camada_da_usuaria"])
def test_o_campo_esta_nos_campos_da_volta(campo: str) -> None:
    assert f"controllers[].{campo}" in _o_basico().CAMPOS_DA_VOLTA


def test_o_pedido_pelo_ipc_vai_e_volta_nos_quatro_e_nos_dois_transportes(tmp_path: Path) -> None:
    """Os comandos de saída com `uniq` (cabo e rádio, de P1 a P4) e a volta, lidos no estado."""
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    chaves = [f"AA:BB:CC:00:00:0{n}" for n in range(1, 5)]
    inst._handles = {
        k: _FakeHandle(transport_name="USB" if n % 2 else "BT") for n, k in enumerate(chaves)
    }
    inst._primary_key = chaves[0]
    server = IpcServer(
        controller=inst,
        store=StateStore(),
        profile_manager=ProfileManager(controller=inst, store=StateStore()),
        socket_path=tmp_path / "h.sock",
        daemon=None,
    )
    u1, u2, u3, u4 = (k.replace(":", "").lower() for k in chaves)

    async def roteiro() -> list[dict[str, Any]]:
        await server._handle_led_set({"rgb": [0, 255, 0], "uniq": u2})
        await server._handle_trigger_set(
            {"side": "left", "mode": "Rigid", "params": [0, 255], "uniq": u3}
        )
        await server._handle_led_player_set({"bits": [True] * 5, "uniq": u4})
        ida = await _estado_completo(inst, tmp_path)
        inst.clear_user_output_overrides()
        volta = await _estado_completo(inst, tmp_path)
        return [ida, volta]

    ida, volta = asyncio.run(roteiro())

    def por_uniq(r: dict[str, Any]) -> dict[str, Any]:
        return {c["uniq"]: c.get("camada_da_usuaria") for c in r["controllers"]}

    assert por_uniq(ida) == {u1: [], u2: ["led"], u3: ["trigger_left"], u4: ["player_leds"]}
    assert por_uniq(volta) == {u1: [], u2: [], u3: [], u4: []}
