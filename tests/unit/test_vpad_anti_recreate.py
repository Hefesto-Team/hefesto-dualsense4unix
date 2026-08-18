"""MISC-08 item 3 — vpads NÃO recriam quando a config efetiva não mudou.

Ao vivo (20:15 do estudo 2026-07-18) recriar os vpads mid-game invalidou os
handles SDL/wine do jogo — a Steam nunca reabriu o hidraw do vpad P1. O
`start_gamepad_emulation` já é idempotente por (flavor, backend); aqui
trava-se a camada de cima (`Daemon.set_gamepad_emulation`): um apply IDÊNTICO
mantém o MESMO device (nenhum teardown+respawn) e NÃO força o ciclo cheio do
co-op (que reescreve player-LEDs via sysfs a cada força). Mudança REAL de
flavor continua recriando e repropagando ao co-op.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing import FakeController


class _FakePad:
    backend = "uhid"

    def __init__(self, flavor: str) -> None:
        self.flavor = flavor
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _CoopEspiao:
    def __init__(self) -> None:
        self.syncs: list[bool] = []

    def sync(self, *, force: bool = False) -> None:
        self.syncs.append(force)

    def disable(self) -> None: ...

    def player_count(self) -> int:
        return 1


@pytest.fixture()
def daemon(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_gamepad_emulation",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_mouse_emulation",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env",
        lambda _daemon: None,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
        lambda flavor, **_kw: _FakePad(str(flavor)),
    )
    d = Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    d._coop_manager = _CoopEspiao()
    return d


def test_apply_identico_nao_recria_o_vpad_nem_forca_o_coop(daemon: Any) -> None:
    assert daemon.set_gamepad_emulation(True, "dualsense") is True
    device = daemon._gamepad_device
    assert device is not None
    assert daemon._coop_manager.syncs == [True], (
        "criação REAL do vpad repropaga ao co-op (force)"
    )

    # Apply idêntico (toggle repetido / perfil reaplicando o mesmo modo):
    assert daemon.set_gamepad_emulation(True, "dualsense") is True
    assert daemon._gamepad_device is device, (
        "apply idêntico recriou o vpad — invalida os handles do jogo mid-game"
    )
    assert device.stopped is False
    assert daemon._coop_manager.syncs == [True], (
        "apply idêntico não pode forçar o ciclo cheio do co-op"
    )


def test_mudanca_de_flavor_recria_e_repropaga(daemon: Any) -> None:
    assert daemon.set_gamepad_emulation(True, "dualsense") is True
    device = daemon._gamepad_device

    assert daemon.set_gamepad_emulation(True, "xbox") is True
    assert daemon._gamepad_device is not device, "flavor mudou: recria"
    assert device.stopped is True
    assert daemon._coop_manager.syncs == [True, True], (
        "mudança real repropaga a máscara aos vpads do co-op"
    )


def test_religar_depois_de_desligar_recria(daemon: Any) -> None:
    daemon.set_gamepad_emulation(True, "dualsense")
    device = daemon._gamepad_device
    daemon.set_gamepad_emulation(False)
    assert device.stopped is True
    daemon.set_gamepad_emulation(True, "dualsense")
    assert daemon._gamepad_device is not None
    assert daemon._gamepad_device is not device
    assert daemon._coop_manager.syncs == [True, True]
