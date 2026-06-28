"""FEAT-DSX-COOP-LOCAL-01 — CoopManager: jogadores secundários do co-op local.

Cobre a reconciliação (sync) com fakes de EvdevReader/UinputGamepad: cria um
jogador por controle físico ALÉM do primário (cada um com reader+grab+vpad
próprios), repassa o input ao vpad certo (forward_all), e desmonta no hotplug-out
/ ao desligar o co-op / sem gamepad virtual. Sem hardware real.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager


class _FakeReader:
    def __init__(self, device_path: Any = None) -> None:
        self.device_path = device_path
        self.started = False
        self.grabbed: bool | None = None
        self.stopped = False
        self.snap = SimpleNamespace(
            lx=200, ly=50, rx=128, ry=128, l2_raw=10, r2_raw=20,
            buttons_pressed=frozenset({"cross"}),
        )

    def start(self) -> bool:
        self.started = True
        return True

    def set_grab(self, grab: bool) -> None:
        self.grabbed = grab

    def stop(self) -> None:
        self.stopped = True

    def snapshot(self) -> Any:
        return self.snap


class _FakeVpad:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.flavor = ""
        self.analog: list[dict[str, int]] = []
        self.buttons: list[frozenset[str]] = []

    @classmethod
    def for_flavor(cls, flavor: str) -> _FakeVpad:
        inst = cls()
        inst.flavor = flavor
        return inst

    def start(self) -> bool:
        self.started = True
        return True

    def stop(self) -> None:
        self.stopped = True

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons.append(pressed)


def _make_daemon(
    *, coop: bool = True, gamepad: bool = True, primary: str = "/dev/input/event5"
) -> Any:
    return SimpleNamespace(
        config=SimpleNamespace(coop_enabled=coop, gamepad_flavor="dualsense"),
        _gamepad_device=object() if gamepad else None,
        controller=SimpleNamespace(_evdev=SimpleNamespace(_device_path=Path(primary))),
        _coop_manager=None,
    )


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _FakeReader
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.uinput_gamepad.UinputGamepad", _FakeVpad
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.uinput_gamepad.normalize_flavor",
        lambda f: f or "dualsense",
    )


def _set_evdevs(monkeypatch: pytest.MonkeyPatch, paths: list[str]) -> None:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.find_all_dualsense_evdevs",
        lambda: [Path(p) for p in paths],
    )


def test_sync_cria_secundario_excluindo_o_primario(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_evdevs(monkeypatch, ["/dev/input/event5", "/dev/input/event7"])
    mgr = CoopManager(_make_daemon(primary="/dev/input/event5"))
    mgr.sync()

    assert mgr.player_count() == 2  # P1 (primário) + 1 secundário
    assert list(mgr._players) == ["/dev/input/event7"]  # event5 (primário) excluído
    player = mgr._players["/dev/input/event7"]
    assert player.reader.started is True
    assert player.reader.grabbed is True  # grab: jogo vê só o vpad, não o cru
    assert player.vpad.started is True


def test_forward_all_repassa_snapshot_ao_vpad(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_evdevs(monkeypatch, ["/dev/input/event5", "/dev/input/event7"])
    mgr = CoopManager(_make_daemon())
    mgr.sync()
    mgr.forward_all()

    vpad = mgr._players["/dev/input/event7"].vpad
    assert vpad.analog[-1] == {"lx": 200, "ly": 50, "rx": 128, "ry": 128, "l2": 10, "r2": 20}
    assert vpad.buttons[-1] == frozenset({"cross"})


def test_sync_remove_no_hotplug_out(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_evdevs(monkeypatch, ["/dev/input/event5", "/dev/input/event7"])
    mgr = CoopManager(_make_daemon())
    mgr.sync()
    player = mgr._players["/dev/input/event7"]

    # Secundário desconectou: só o primário sobrou.
    _set_evdevs(monkeypatch, ["/dev/input/event5"])
    mgr.sync()

    assert mgr.player_count() == 1
    assert player.reader.grabbed is False  # soltou o grab
    assert player.reader.stopped is True
    assert player.vpad.stopped is True


def test_desligar_coop_desmonta_tudo(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_evdevs(monkeypatch, ["/dev/input/event5", "/dev/input/event7"])
    daemon = _make_daemon(coop=True)
    mgr = CoopManager(daemon)
    mgr.sync()
    assert mgr.player_count() == 2

    daemon.config.coop_enabled = False
    mgr.sync()  # should_be_active=False → desmonta
    assert mgr.player_count() == 1
    assert mgr._players == {}


def test_should_be_active_gates(patched: None) -> None:
    assert CoopManager(_make_daemon(coop=True, gamepad=True)).should_be_active() is True
    assert CoopManager(_make_daemon(coop=False, gamepad=True)).should_be_active() is False
    assert CoopManager(_make_daemon(coop=True, gamepad=False)).should_be_active() is False


def test_sync_sem_gamepad_nao_cria(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_evdevs(monkeypatch, ["/dev/input/event5", "/dev/input/event7"])
    mgr = CoopManager(_make_daemon(gamepad=False))
    mgr.sync()
    assert mgr.player_count() == 1  # gamepad virtual desligado → co-op inativo
