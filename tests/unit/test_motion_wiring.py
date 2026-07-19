"""Fiação do espelho de motion (GYRO-01): spawn, teardown e retarget.

Prova, sem hardware:

- `start_gamepad_emulation` lê o 0x05 do primário, o repassa à factory do vpad
  e sobe o `PhysicalReportReader` do P1 (só no backend uhid); o reader é
  registrado no backend (`attach_motion_reader`) para o retarget de primário.
- `stop_gamepad_emulation` para o reader ANTES do `device.stop()` (o reader
  escreve no /dev/uhid do vpad — a ordem inversa seria write em fd morto).
- Co-op: jogador DualSense (hidraw por-uniq resolve) ganha reader próprio;
  externo (sem handle no backend) e identidade sem MAC ficam SEM espelho por
  design (gyro nativo deles passa direto ao jogo). Teardown na mesma ordem.
- `_recompute_primary` do backend cutuca o reader (request_reopen) junto do
  retarget do evdev.
"""
from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.utils import session

_CALIB = bytes([0x05]) + bytes([0xAB]) * 40


class _FakeReader:
    """Dublê do PhysicalReportReader: grava ciclo de vida na ordem global."""

    def __init__(
        self, path_provider: Any, vpad: Any, **_kw: Any
    ) -> None:
        self.path_provider = path_provider
        self.vpad = vpad
        self.started = False
        self.stopped = False
        self.eventos: list[str] = getattr(vpad, "eventos", [])

    def start(self) -> bool:
        self.started = True
        self.eventos.append("reader.start")
        return True

    def stop(self) -> None:
        self.stopped = True
        self.eventos.append("reader.stop")


class _FakeVpad:
    def __init__(self, backend: str = "uhid") -> None:
        self.flavor = "dualsense"
        self.backend = backend
        self.eventos: list[str] = []
        self.stopped = False

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        self.stopped = True
        self.eventos.append("device.stop")

    def forward_analog(self, **_kw: int) -> None: ...

    def forward_buttons(self, _p: frozenset[str]) -> None: ...

    def pump_ff(self) -> None: ...


class _FakeController:
    """Backend com a superfície que o GYRO-01 usa (hidraw/calibração/attach)."""

    def __init__(self) -> None:
        self._evdev = SimpleNamespace(set_grab=lambda _g: True, grab_state="held")
        self.attached: list[Any] = []
        self.calib_pedidos = 0

    def hidraw_path(self, uniq: str | None = None) -> str | None:
        return "/dev/hidraw9"

    def read_calibration(self, uniq: str | None = None) -> bytes | None:
        self.calib_pedidos += 1
        return _CALIB

    def attach_motion_reader(self, reader: Any | None) -> None:
        self.attached.append(reader)


class _FakeDaemon:
    def __init__(self) -> None:
        self._gamepad_device = None
        self._motion_reader = None
        self._mouse_device = None
        self.config = DaemonConfig()
        self.controller = _FakeController()


@pytest.fixture()
def wired(monkeypatch: pytest.MonkeyPatch) -> tuple[_FakeDaemon, dict[str, Any]]:
    """Daemon falso + factory de vpad patchada devolvendo um uhid falso."""
    monkeypatch.setattr(session, "save_gamepad_emulation", lambda *a, **k: None)
    monkeypatch.setattr(session, "save_mouse_emulation_enabled", lambda *a, **k: None)
    monkeypatch.setattr(prr, "PhysicalReportReader", _FakeReader)
    capturado: dict[str, Any] = {}

    def _fake_make(flavor: Any, **kwargs: Any) -> _FakeVpad:
        capturado.update(kwargs)
        return _FakeVpad(backend="uhid")

    monkeypatch.setattr(vp, "make_virtual_pad", _fake_make)
    return _FakeDaemon(), capturado


class TestP1:
    def test_start_sobe_o_reader_e_carimba_a_calibracao(
        self, wired: tuple[_FakeDaemon, dict[str, Any]]
    ) -> None:
        daemon, capturado = wired
        assert gp.start_gamepad_emulation(daemon, flavor="dualsense") is True
        # A calibração do PRIMÁRIO viajou até a factory do vpad.
        assert capturado["calibration_0x05"] == _CALIB
        reader = daemon._motion_reader
        assert isinstance(reader, _FakeReader)
        assert reader.started is True
        # O provider resolve o hidraw do primário NA HORA (retarget barato).
        assert reader.path_provider() == "/dev/hidraw9"
        # Registrado no backend para o retarget de `_recompute_primary`.
        assert daemon.controller.attached == [reader]

    def test_stop_para_o_reader_antes_do_device(
        self, wired: tuple[_FakeDaemon, dict[str, Any]]
    ) -> None:
        daemon, _ = wired
        gp.start_gamepad_emulation(daemon, flavor="dualsense")
        device = daemon._gamepad_device
        gp.stop_gamepad_emulation(daemon)
        assert daemon._motion_reader is None
        # A ordem é a alma do teardown: reader morre ANTES do fd do uhid.
        eventos = device.eventos
        assert eventos.index("reader.stop") < eventos.index("device.stop")
        # E o backend foi desregistrado (attach(None) depois do attach(reader)).
        assert daemon.controller.attached[-1] is None

    def test_fallback_uinput_nao_ganha_reader(
        self, monkeypatch: pytest.MonkeyPatch, wired: tuple[_FakeDaemon, dict[str, Any]]
    ) -> None:
        daemon, _ = wired
        monkeypatch.setattr(
            vp, "make_virtual_pad", lambda *_a, **_k: _FakeVpad(backend="uinput")
        )
        gp.start_gamepad_emulation(daemon, flavor="dualsense")
        assert daemon._motion_reader is None

    def test_backend_sem_hidraw_nao_ganha_reader(
        self, wired: tuple[_FakeDaemon, dict[str, Any]]
    ) -> None:
        daemon, _ = wired
        del daemon.controller.__class__.hidraw_path
        try:
            gp.start_gamepad_emulation(daemon, flavor="dualsense")
            assert daemon._motion_reader is None
        finally:
            _FakeController.hidraw_path = lambda self, uniq=None: "/dev/hidraw9"  # type: ignore[method-assign]

    def test_read_primary_calibration_e_fail_safe(self) -> None:
        daemon = _FakeDaemon()
        daemon.controller.read_calibration = lambda uniq=None: (_ for _ in ()).throw(  # type: ignore[method-assign]
            OSError("EIO")
        )
        assert gp.read_primary_calibration(daemon) is None
        # Backend SEM o método (FakeController do smoke): None sem explodir.
        daemon.controller = SimpleNamespace()
        assert gp.read_primary_calibration(daemon) is None


class TestCoop:
    def _manager(self, controller: Any) -> Any:
        from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager

        daemon = _FakeDaemon()
        daemon.controller = controller
        return CoopManager(daemon)

    def _player(self, identity: str, vpad: _FakeVpad | None = None) -> Any:
        from hefesto_dualsense4unix.daemon.subsystems.coop import _SecondaryPlayer

        reader = SimpleNamespace(
            set_grab=lambda _g: True, stop=lambda: None, grab_state="held"
        )
        return _SecondaryPlayer(
            identity=identity,
            evdev_path="/dev/input/event99",
            reader=reader,
            player_index=2,
            vpad=vpad if vpad is not None else _FakeVpad(),
        )

    def test_jogador_dualsense_ganha_reader_proprio(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(prr, "PhysicalReportReader", _FakeReader)
        manager = self._manager(_FakeController())
        player = self._player("aabbccddee02")
        manager._start_player_motion_reader(player)
        assert isinstance(player.motion_reader, _FakeReader)
        assert player.motion_reader.started is True
        assert player.motion_reader.path_provider() == "/dev/hidraw9"

    def test_externo_sem_handle_fica_sem_espelho(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 8BitDo/Nintendo: `hidraw_path(uniq)` do backend devolve None — o gyro
        # deles é NATIVO (passam direto ao jogo); espelhar seria reverter o
        # design 8BIT-02.
        monkeypatch.setattr(prr, "PhysicalReportReader", _FakeReader)
        controller = _FakeController()
        controller.hidraw_path = lambda uniq=None: None  # type: ignore[method-assign]
        manager = self._manager(controller)
        player = self._player("aabbcc000042")
        manager._start_player_motion_reader(player)
        assert player.motion_reader is None

    def test_identidade_sem_mac_fica_sem_espelho(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(prr, "PhysicalReportReader", _FakeReader)
        manager = self._manager(_FakeController())
        player = self._player("path:/dev/input/event99")
        manager._start_player_motion_reader(player)
        assert player.motion_reader is None

    def test_vpad_uinput_fica_sem_espelho(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(prr, "PhysicalReportReader", _FakeReader)
        manager = self._manager(_FakeController())
        player = self._player("aabbccddee02", vpad=_FakeVpad(backend="uinput"))
        manager._start_player_motion_reader(player)
        assert player.motion_reader is None

    def test_calibracao_por_jogador_e_fail_safe(self) -> None:
        manager = self._manager(_FakeController())
        assert manager._read_player_calibration("aabbccddee02") == _CALIB
        assert manager._read_player_calibration("path:/dev/input/event9") is None

    def test_teardown_para_o_reader_antes_do_vpad(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(prr, "PhysicalReportReader", _FakeReader)
        manager = self._manager(_FakeController())
        player = self._player("aabbccddee02")
        manager._start_player_motion_reader(player)
        manager._players[player.identity] = player
        with contextlib.suppress(Exception):
            manager._teardown_player(player.identity)
        assert player.motion_reader is None
        eventos = player.vpad.eventos
        assert eventos.index("reader.stop") < eventos.index("device.stop")


class TestRetargetNoBackend:
    def test_recompute_primary_cutuca_o_reader(self) -> None:
        from hefesto_dualsense4unix.core.backend_pydualsense import (
            PyDualSenseController,
        )

        inst = PyDualSenseController.__new__(PyDualSenseController)
        PyDualSenseController.__init__(
            inst,
            evdev_reader=SimpleNamespace(  # type: ignore[arg-type]
                retarget=lambda _u: None,
                refresh_device=lambda: True,
                is_available=lambda: False,
            ),
        )
        pedidos: list[str] = []
        inst.attach_motion_reader(
            SimpleNamespace(request_reopen=lambda reason: pedidos.append(reason))
        )
        handle = SimpleNamespace(conType=SimpleNamespace(name="USB"))
        inst._handles = {"aabbccddee01": handle}
        inst._primary_key = None
        inst._recompute_primary()  # elege o primário novo
        assert pedidos == ["primary_changed"]

    def test_attach_none_desregistra(self) -> None:
        from hefesto_dualsense4unix.core.backend_pydualsense import (
            PyDualSenseController,
        )

        inst = PyDualSenseController.__new__(PyDualSenseController)
        PyDualSenseController.__init__(inst, evdev_reader=SimpleNamespace())  # type: ignore[arg-type]
        inst.attach_motion_reader(SimpleNamespace())
        inst.attach_motion_reader(None)
        assert inst._motion_reader is None
