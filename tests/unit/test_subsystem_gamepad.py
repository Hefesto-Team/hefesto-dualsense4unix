"""Testes do subsystem Gamepad (FEAT-DSX-GAMEPAD-FLAVOR-01).

Prova: start cria o device com a máscara certa, faz grab do controle real e
desliga o mouse (mútua exclusão); stop libera o grab; dispatch repassa estado;
persistência é chamada. Sem hardware — uinput é mockado via for_flavor.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import uinput_gamepad as ug
from hefesto_dualsense4unix.utils import session


class _FakeEvdev:
    def __init__(self) -> None:
        self.grab_calls: list[bool] = []

    def set_grab(self, grab: bool) -> None:
        self.grab_calls.append(grab)


class _FakeController:
    def __init__(self) -> None:
        self._evdev = _FakeEvdev()


class _FakeDevice:
    def __init__(
        self,
        flavor: str | None = "dualsense",
        start_ok: bool = True,
        rumble_sink: object | None = None,
    ) -> None:
        self.flavor = ug.normalize_flavor(flavor)
        self._start_ok = start_ok
        self.started = False
        self.stopped = False
        self.analog: dict | None = None
        self.buttons: frozenset[str] | None = None
        # FEAT-VPAD-FF-PASSTHROUGH-01: sink injetado + contagem de pumps.
        self.rumble_sink = rumble_sink
        self.ff_pumps = 0

    def start(self) -> bool:
        self.started = True
        return self._start_ok

    def stop(self) -> None:
        self.stopped = True

    def forward_analog(self, **kw: int) -> None:
        self.analog = kw

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons = pressed

    def pump_ff(self) -> None:
        self.ff_pumps += 1


class _FakeDaemon:
    def __init__(self) -> None:
        self._gamepad_device = None
        self._mouse_device = None
        self.config = DaemonConfig()
        self.controller = _FakeController()


@pytest.fixture()
def no_persist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutraliza a escrita em disco das flags de sessão."""
    monkeypatch.setattr(session, "save_gamepad_emulation", lambda *a, **k: None)
    monkeypatch.setattr(session, "save_mouse_emulation_enabled", lambda *a, **k: None)


def _patch_for_flavor(monkeypatch: pytest.MonkeyPatch) -> list[_FakeDevice]:
    """Faz UinputGamepad.for_flavor devolver _FakeDevice e registra os criados."""
    created: list[_FakeDevice] = []

    def _fake_for_flavor(
        flavor: str | None = "dualsense", *, rumble_sink: object | None = None
    ) -> _FakeDevice:
        dev = _FakeDevice(flavor, rumble_sink=rumble_sink)
        created.append(dev)
        return dev

    monkeypatch.setattr(ug.UinputGamepad, "for_flavor", staticmethod(_fake_for_flavor))
    return created


class TestStartGamepad:
    def test_start_cria_device_com_flavor_e_grab(
        self, monkeypatch: pytest.MonkeyPatch, no_persist: None
    ) -> None:
        created = _patch_for_flavor(monkeypatch)
        daemon = _FakeDaemon()

        ok = gp.start_gamepad_emulation(daemon, flavor="xbox")

        assert ok is True
        assert daemon._gamepad_device is created[0]
        assert created[0].flavor == "xbox"
        assert created[0].started is True
        assert daemon.config.gamepad_emulation_enabled is True
        assert daemon.config.gamepad_flavor == "xbox"
        # Grab do controle físico ligado (evita input dobrado).
        assert daemon.controller._evdev.grab_calls == [True]
        # FEAT-VPAD-FF-PASSTHROUGH-01: o vpad nasce com sink de rumble → o FF
        # do jogo tem para onde voltar (motores do primário).
        assert created[0].rumble_sink is not None

    def test_start_desliga_mouse_mutua_exclusao(
        self, monkeypatch: pytest.MonkeyPatch, no_persist: None
    ) -> None:
        _patch_for_flavor(monkeypatch)
        daemon = _FakeDaemon()
        mouse = _FakeDevice()
        daemon._mouse_device = mouse
        daemon.config.mouse_emulation_enabled = True

        gp.start_gamepad_emulation(daemon, flavor="dualsense")

        assert mouse.stopped is True
        assert daemon._mouse_device is None
        assert daemon.config.mouse_emulation_enabled is False

    def test_start_idempotente_mesmo_flavor(
        self, monkeypatch: pytest.MonkeyPatch, no_persist: None
    ) -> None:
        created = _patch_for_flavor(monkeypatch)
        daemon = _FakeDaemon()
        gp.start_gamepad_emulation(daemon, flavor="dualsense")
        gp.start_gamepad_emulation(daemon, flavor="dualsense")
        assert len(created) == 1  # não recria

    def test_troca_de_flavor_recria(
        self, monkeypatch: pytest.MonkeyPatch, no_persist: None
    ) -> None:
        created = _patch_for_flavor(monkeypatch)
        daemon = _FakeDaemon()
        gp.start_gamepad_emulation(daemon, flavor="dualsense")
        gp.start_gamepad_emulation(daemon, flavor="xbox")
        assert len(created) == 2
        assert created[0].stopped is True
        assert daemon._gamepad_device is created[1]
        assert daemon.config.gamepad_flavor == "xbox"

    def test_start_falha_se_device_nao_inicia(
        self, monkeypatch: pytest.MonkeyPatch, no_persist: None
    ) -> None:
        def _fail(
            flavor: str | None = "dualsense", *, rumble_sink: object | None = None
        ) -> _FakeDevice:
            return _FakeDevice(flavor, start_ok=False, rumble_sink=rumble_sink)

        monkeypatch.setattr(ug.UinputGamepad, "for_flavor", staticmethod(_fail))
        daemon = _FakeDaemon()
        ok = gp.start_gamepad_emulation(daemon, flavor="dualsense")
        assert ok is False
        assert daemon._gamepad_device is None
        assert daemon.config.gamepad_emulation_enabled is False


class TestStopGamepad:
    def test_stop_libera_grab_e_descarta(
        self, monkeypatch: pytest.MonkeyPatch, no_persist: None
    ) -> None:
        _patch_for_flavor(monkeypatch)
        daemon = _FakeDaemon()
        gp.start_gamepad_emulation(daemon, flavor="dualsense")
        dev = daemon._gamepad_device

        gp.stop_gamepad_emulation(daemon)

        assert dev.stopped is True
        assert daemon._gamepad_device is None
        assert daemon.config.gamepad_emulation_enabled is False
        # grab: ligado no start, desligado no stop.
        assert daemon.controller._evdev.grab_calls == [True, False]

    def test_stop_idempotente_sem_device(self, no_persist: None) -> None:
        daemon = _FakeDaemon()
        gp.stop_gamepad_emulation(daemon)  # não deve lançar
        assert daemon.config.gamepad_emulation_enabled is False


class TestDispatchGamepad:
    def _state(self) -> object:
        class _S:
            raw_lx = raw_ly = raw_rx = raw_ry = 128
            l2_raw = r2_raw = 0

        return _S()

    def test_dispatch_repassa_analog_e_botoes(self) -> None:
        daemon = _FakeDaemon()
        dev = _FakeDevice()
        daemon._gamepad_device = dev
        buttons = frozenset({"cross", "l1"})

        gp.dispatch_gamepad(daemon, self._state(), buttons)

        assert dev.analog == {"lx": 128, "ly": 128, "rx": 128, "ry": 128, "l2": 0, "r2": 0}
        assert dev.buttons == buttons
        # FEAT-VPAD-FF-PASSTHROUGH-01: cada dispatch bombeia o FF do vpad.
        assert dev.ff_pumps == 1

    def test_dispatch_noop_sem_device(self) -> None:
        daemon = _FakeDaemon()
        gp.dispatch_gamepad(daemon, self._state(), frozenset())  # não deve lançar

    def test_dispatch_trata_excecao(self) -> None:
        daemon = _FakeDaemon()
        dev = _FakeDevice()

        def _boom(**_kw: int) -> None:
            raise RuntimeError("falha forward")

        dev.forward_analog = _boom  # type: ignore[method-assign]
        daemon._gamepad_device = dev
        gp.dispatch_gamepad(daemon, self._state(), frozenset())  # não deve lançar


class TestGamepadSubsystem:
    def test_is_enabled_segue_config(self) -> None:
        sub = gp.GamepadSubsystem()
        cfg = DaemonConfig()
        assert sub.is_enabled(cfg) is False
        cfg.gamepad_emulation_enabled = True
        assert sub.is_enabled(cfg) is True

    @pytest.mark.asyncio
    async def test_start_noop_quando_desligado(
        self, monkeypatch: pytest.MonkeyPatch, no_persist: None
    ) -> None:
        created = _patch_for_flavor(monkeypatch)
        sub = gp.GamepadSubsystem()
        daemon = _FakeDaemon()  # gamepad_emulation_enabled=False por default

        class _Ctx:
            config = daemon.config
            daemon_ref = daemon

        ctx = _Ctx()
        ctx.daemon = daemon  # type: ignore[attr-defined]
        await sub.start(ctx)
        assert created == []  # não criou device
