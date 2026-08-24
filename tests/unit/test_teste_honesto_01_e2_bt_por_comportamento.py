"""TESTE-HONESTO-01/E2 — o transporte decide `native_bt_fragil`, medido por
comportamento, não por texto de fonte.

O `state_full` calcula `native_bt_fragil` em duas fases (ver
`daemon/ipc_handlers.py::_handle_daemon_state_full`, MESA-CHEIA-11/E1):
quando o backend sabe descrever a mesa inteira (`describe_controllers`), a
resposta vem POR CONTROLE via `controles_bt_frageis` — já coberta por
comportamento em `test_mesa_cheia_11_a_janela_conta_quatro.py`. Quando o
backend NÃO sabe descrever a mesa (o caso do `FakeController`, que não
implementa `describe_controllers` — o mesmo caso de `test_native_mode.py` e
da maioria dos testes desta suíte), o handler cai no par histórico:
``native_mode and transport == "bt"``.

Esse segundo ramo, o que a sprint TESTE-HONESTO-01/E2 mediu, só tinha prova de
TEXTO: `test_dedup_guard.py::test_state_full_publica_native_bt_fragil` confere
que a string `'result["native_bt_fragil"]'` existe no arquivo-fonte — o que
sobrevive a qualquer sabotagem que não apague essa string, inclusive trocar a
condição por outra (achado da própria sprint, seção E2).

Este arquivo prova o ramo de fallback por COMPORTAMENTO: liga o Modo Nativo,
varia só o transporte do `FakeController`, e exige o par diferencial — USB
nega, BT afirma. E prova o caso oposto: fora do Modo Nativo, BT não assusta,
porque o jogo nem vê o físico.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState, Transport
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController


class _FakeDaemonNativo:
    """Dublê mínimo do `Daemon` real — só o suficiente para o `state_full`
    não estourar (`is_paused`/`is_native_mode` são chamados incondicionalmente
    quando `self.daemon` não é `None`). Mesmo padrão de
    `test_state_full_game_signal.py::_FakeDaemon`.
    """

    def __init__(self, native: bool) -> None:
        self._native = native

    def is_paused(self) -> bool:
        return False

    def is_native_mode(self) -> bool:
        return self._native


def _server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transporte: Transport
) -> IpcServer:
    """IpcServer mínimo com um `FakeController` conectado no transporte dado,
    sem `describe_controllers` — o ramo que este arquivo mede."""
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    fc = FakeController(transport=transporte)
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=50,
            l2_raw=0,
            r2_raw=0,
            connected=True,
            transport=transporte,
        )
    )
    manager = ProfileManager(controller=fc, store=store)
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "hefesto-dualsense4unix.sock",
    )


@pytest.mark.parametrize(
    ("transporte", "esperado"),
    [("usb", False), ("bt", True)],
)
async def test_native_bt_fragil_por_transporte_com_native_ligado(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    transporte: Transport,
    esperado: bool,
) -> None:
    server = _server(tmp_path, monkeypatch, transporte)
    server.daemon = _FakeDaemonNativo(native=True)  # type: ignore[assignment]

    result = await server._handle_daemon_state_full({})

    assert result["transport"] == transporte
    assert result["native_bt_fragil"] is esperado, (
        f"transporte={transporte!r} com Modo Nativo ligado: esperava "
        f"native_bt_fragil={esperado}, veio {result['native_bt_fragil']!r}"
    )


async def test_native_bt_fragil_falso_com_native_desligado_mesmo_em_bt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fora do Modo Nativo não há fragilidade a avisar: o jogo vê o gamepad
    virtual, não o físico — então BT sozinho não deve acender o aviso."""
    server = _server(tmp_path, monkeypatch, "bt")
    server.daemon = _FakeDaemonNativo(native=False)  # type: ignore[assignment]

    result = await server._handle_daemon_state_full({})

    assert result["native_bt_fragil"] is False
