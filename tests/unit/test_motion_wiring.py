"""Fiação do espelho de motion (GYRO-01): spawn, teardown e retarget.

Prova, sem hardware:

- `start_gamepad_emulation` lê o 0x05 do primário, o repassa à factory do vpad
  e sobe o `PhysicalReportReader` do P1 (só no backend uhid); o reader é
  registrado no backend (`attach_motion_reader`) para o retarget de primário.
- `stop_gamepad_emulation` para o reader ANTES do `device.stop()` (o reader
  escreve no /dev/uhid do vpad — a ordem inversa seria write em fd morto).
- Co-op: jogador DualSense ganha reader próprio — inclusive quando o handle do
  backend ainda NÃO abriu (ESPELHO-QUE-NAO-NASCEU-01, 15/08/2026: quem esperava
  o handle na promoção perdia a corrida do hotplug e ficava sem espelho para
  sempre; quem espera é o `path_provider` do reader). Identidade sem MAC fica
  SEM espelho, e externo (8BitDo/Nintendo) nem chega a `_players` — a garantia
  do 8BIT-02 é da descoberta, fechada em vendor/PID. Teardown na mesma ordem.
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
        assert gp.start_gamepad_emulation(daemon, flavor="dualsense", origin="manual") is True
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
        gp.start_gamepad_emulation(daemon, flavor="dualsense", origin="manual")
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
        gp.start_gamepad_emulation(daemon, flavor="dualsense", origin="manual")
        assert daemon._motion_reader is None

    def test_backend_sem_hidraw_nao_ganha_reader(
        self, wired: tuple[_FakeDaemon, dict[str, Any]]
    ) -> None:
        daemon, _ = wired
        del daemon.controller.__class__.hidraw_path
        try:
            gp.start_gamepad_emulation(daemon, flavor="dualsense", origin="manual")
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

    def test_espelho_nasce_com_o_handle_ainda_fechado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ESPELHO-QUE-NAO-NASCEU-01: perder a corrida não é ficar sem espelho.

        A promoção roda no tick do hotplug, e o `_open_one` do backend para
        aquele MAC pode ainda estar no ar (até `INIT_TIMEOUT_SEC` = 5 s; o BT
        chega a estourar o teto). Enquanto ele não abre, `hidraw_path(identity)`
        devolve None. O reader TEM de nascer assim mesmo: quem espera é ele, no
        `path_provider`, na thread dele — como o espelho do P1 sempre fez.

        Medido na mesa de quatro em 15/08/2026: o vpad do jogador que perdeu
        essa corrida entregava ~0,4 Hz ao jogo contra 165-196 Hz dos outros.
        """
        monkeypatch.setattr(prr, "PhysicalReportReader", _FakeReader)
        controller = _FakeController()
        # O handle ainda não abriu: o backend não sabe o hidraw deste MAC.
        aberto = False

        def _hidraw(uniq: str | None = None) -> str | None:
            return "/dev/hidraw11" if aberto else None

        controller.hidraw_path = _hidraw  # type: ignore[method-assign]
        manager = self._manager(controller)
        player = self._player("aabbccddee02")
        manager._start_player_motion_reader(player)

        assert isinstance(player.motion_reader, _FakeReader)
        assert player.motion_reader.started is True
        # Enquanto o handle não abre, o provider devolve None e o reader espera.
        assert player.motion_reader.path_provider() is None
        # Quando o backend termina de abrir, o MESMO reader acha o nó sozinho —
        # sem que ninguém precise reexecutar a promoção.
        aberto = True
        assert player.motion_reader.path_provider() == "/dev/hidraw11"

    def test_externo_nunca_chega_a_pedir_espelho(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """8BIT-02 segue de pé — pela descoberta, não por olhar o handle.

        A decisão da mantenedora (estudo 2026-07-19) não mudou: 8BitDo/Nintendo
        passam direto ao jogo com o gyro NATIVO deles, sem espelho. O que mudou
        em 15/08/2026 é onde ela é garantida. Antes, `_start_player_motion_reader`
        a inferia de `hidraw_path(uniq) is None` — sinal que um DualSense
        legítimo também emite enquanto o backend não abriu o handle dele
        (ESPELHO-QUE-NAO-NASCEU-01). A garantia real é estrutural e anterior:
        `discover_dualsense_evdevs`, única fonte dos secundários, é fechada em
        `DUALSENSE_VENDOR`/`DUALSENSE_PIDS`, então um externo nunca entra em
        `_players` — e um DualSense sem MAC legível para no gate `path:`.
        """
        from hefesto_dualsense4unix.core import evdev_reader as er

        def _descoberto(especie: str, identidade: str, node: str) -> Any:
            return er.GamepadDescoberto(
                especie=especie,
                identidade=identidade,
                evdev_path=node,
                name="dublê",
                vid="054c",
                pid="0ce6",
                bus="0003",
                uniq=None,
                driver=None,
                hidraw=None,
            )

        mesa = [
            _descoberto(er.ESPECIE_DUALSENSE, "aabbccddee02", "/dev/input/event1"),
            _descoberto("8bitdo", "aabbcc000042", "/dev/input/event2"),
            _descoberto("nintendo", "aabbcc000043", "/dev/input/event3"),
        ]
        monkeypatch.setattr(er, "discover_gamepads", lambda **_kw: mesa)

        achados = er.discover_dualsense_evdevs()

        # Só o DualSense vira chave — e é de `achados` que `_players` nasce.
        assert set(achados) == {"aabbccddee02"}
        assert "aabbcc000042" not in achados
        assert "aabbcc000043" not in achados
        # A lista fechada que sustenta a garantia continua fechada.
        assert er.DUALSENSE_VENDOR == 0x054C
        assert sorted(er.DUALSENSE_PIDS) == [0x0CE6, 0x0DF2]

    def test_identidade_sem_mac_e_o_gate_do_externo_sem_driver(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DualSense sem MAC legível para no `path:` — mesmo com handle nenhum."""
        monkeypatch.setattr(prr, "PhysicalReportReader", _FakeReader)
        controller = _FakeController()
        controller.hidraw_path = lambda uniq=None: None  # type: ignore[method-assign]
        manager = self._manager(controller)
        player = self._player("path:/dev/input/event42")
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
