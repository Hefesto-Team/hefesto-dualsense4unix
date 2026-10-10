"""O controle e o vpad dele se casam pelo endereço, nunca pelo número do jogador.

O-CONTROLE-E-O-VPAD-DELE-SE-CASAM-PELO-ENDERECO-01 (09/10/2026). Fora do co-op
todos os conectados vêm como jogador 1, e o vpad do P1 serve só o primário: o
mapa do controle acendia os dois motores do segundo controle, que não vibrava.
O serviço publica em cada item de `rumble_ff.per_vpad` o `uniq` do controle
físico que aquele vpad serve, e a interface tem UM leitor que casa por ele.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa o pacote da aba do mapa do controle, que carrega o GTK")

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.interface import cartao_do_controle as cartao
from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

U1, U2, U3, U4 = (f"aabbcc00000{n}" for n in range(1, 5))
INTERFACE = Path(cartao.__file__).resolve().parent


def _vpad(uniq: str, jogador: int, **campos: Any) -> dict[str, Any]:
    return {"player": jogador, "uniq": uniq, "rumble_no_fisico": [200, 90],
            "rumble_no_fisico_ha_s": 0.1, "motion_streaming": True,
            "motion_hz": 250.0, **campos}


def test_fora_do_coop_so_o_primario_mostra_motores_e_giroscopio() -> None:
    """Dois controles com `player: 1`; o vpad do P1 serve só o primário."""
    estado = {"rumble_ff": {"per_vpad": [_vpad(U1, 1)]}}
    primario = {"uniq": U1, "player": 1, "is_primary": True}
    segundo = {"uniq": U2, "player": 1, "is_primary": False}

    assert a13._motores(estado, primario) == (True, True)
    assert a13._motores(estado, segundo) == (False, False)
    assert cartao._item_do_vpad(primario, estado) is not None
    assert cartao._item_do_vpad(segundo, estado) is None
    assert cartao.texto_motion(primario, estado) == (
        "Giroscópio: fluindo para o jogo (~250 Hz)")
    assert cartao.texto_motion(segundo, estado) is None


def test_no_coop_renumerado_cada_controle_acha_o_vpad_dele() -> None:
    """P1 a P4 com o número fora da posição na lista: o endereço decide."""
    numeros = {U1: 3, U2: 1, U3: 4, U4: 2}
    estado = {"rumble_ff": {"per_vpad": [
        _vpad(u, n, motion_hz=100.0 + n, rumble_no_fisico=[n, 0])
        for u, n in sorted(numeros.items(), key=lambda par: -par[1])
    ]}}
    for posicao, (uniq, numero) in enumerate(numeros.items()):
        entrada = {"uniq": uniq, "player": numero, "is_primary": posicao == 0}
        item = cartao._item_do_vpad(entrada, estado)
        assert item is not None and item["uniq"] == uniq
        assert item["player"] == numero
        assert cartao.texto_motion(entrada, estado) == (
            f"Giroscópio: fluindo para o jogo (~{100 + numero} Hz)")
        assert a13._motores(estado, entrada) == (False, True)


def test_controle_sem_endereco_nao_casa_com_vpad_nenhum() -> None:
    estado = {"rumble_ff": {"per_vpad": [_vpad(U1, 1)]}}
    assert cartao._item_do_vpad({"player": 1, "is_primary": True}, estado) is None
    assert a13._motores(estado, {"player": 1, "is_primary": True}) == (False, False)


# O serviço: o handler de verdade publica o endereço em cada item.


def _vpad_ns() -> SimpleNamespace:
    return SimpleNamespace(backend="uhid", flavor="dualsense", ff_supported=True,
                           ff_play_count=0, output_count=0, trigger_replicas=0,
                           lightbar_replicas=0, player_led_replicas=0,
                           ff_last_sent=(0, 0), motion_streaming=False)


@pytest.fixture
def _perfis_isolados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    alvo = tmp_path / "profiles"
    alvo.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: alvo)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_perfis_isolados")
async def test_o_servico_publica_o_endereco_do_fisico_em_cada_vpad(
    tmp_path: Path,
) -> None:
    """O primário e dois do co-op, renumerados: cada item leva o `uniq` dele."""
    fc = FakeController(transport="usb")
    fc.connect()
    fc.primary_uniq = U1  # type: ignore[attr-defined]
    store = StateStore()
    daemon = MagicMock()
    daemon._last_state = None
    daemon.config = MagicMock(coop_enabled=True, mouse_emulation_enabled=False,
                              rumble_policy="balanceado", rumble_active=None)
    daemon._gamepad_device = _vpad_ns()
    daemon._motion_reader = SimpleNamespace(emit_hz=0.0)
    daemon._coop_manager = SimpleNamespace(
        _players={
            U2: SimpleNamespace(player_index=2, vpad=_vpad_ns(), motion_reader=None),
            U3: SimpleNamespace(player_index=3, vpad=_vpad_ns(), motion_reader=None),
        },
        player_indexes=lambda: {U1: 2, U2: 3, U3: 1},
        player_count=lambda: 3,
    )
    sock = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(controller=fc, store=store,
                       profile_manager=ProfileManager(controller=fc, store=store),
                       socket_path=sock, daemon=daemon)
    await server.start()
    try:
        async with IpcClient.connect(sock) as client:
            resultado = await client.call("daemon.state_full")
    finally:
        await server.stop()
    per_vpad = resultado["rumble_ff"]["per_vpad"]
    assert {item["uniq"]: item["player"] for item in per_vpad} == {
        U1: 2, U2: 3, U3: 1}


# A fonte: um leitor só de `per_vpad` na interface.


def _quem_le_per_vpad(caminho: Path) -> set[str]:
    """As funções que LEEM `per_vpad` (`.get("per_vpad")` ou `[...]`)."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    leitores: set[str] = set()
    for funcao in ast.walk(arvore):
        if not isinstance(funcao, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for no in ast.walk(funcao):
            alvo: ast.AST | None = None
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) \
                    and no.func.attr == "get" and no.args:
                alvo = no.args[0]
            elif isinstance(no, ast.Subscript):
                alvo = no.slice
            if isinstance(alvo, ast.Constant) and alvo.value == "per_vpad":
                leitores.add(f"{caminho.relative_to(INTERFACE)}:{funcao.name}")
    return leitores


def test_a_interface_tem_um_leitor_so_do_per_vpad() -> None:
    leitores: set[str] = set()
    for caminho in sorted(INTERFACE.rglob("*.py")):
        leitores |= _quem_le_per_vpad(caminho)
    assert leitores == {"cartao_do_controle.py:_item_do_vpad"}, (
        "o casamento controle→vpad tem um dono: chame `_item_do_vpad`")
