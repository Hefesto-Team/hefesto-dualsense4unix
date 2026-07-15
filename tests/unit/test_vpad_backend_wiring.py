"""Ligação do backend de vpad ao daemon (SPRINT-UHID-VPAD-01, UHID-02).

O módulo uhid estava provado no hardware mas não tinha call site: nada em `src/`
o importava. Aqui trava-se o que o daemon precisa ENTREGAR à factory para o vpad
uhid ser um DualSense de verdade em vez de um device mudo:

1. **o hidraw do controle FÍSICO** — é de lá que o vpad copia o report descriptor
   e os feature reports do probe. O daemon já sabe qual é (os handles do backend
   são "pinados" por path); sem repassar, todo vpad cai no uinput e a máscara
   DualSense volta a não vibrar.
2. **o índice do jogador** — no uhid ele vira o MAC do vpad. Todos nascendo
   `player=1` = MAC repetido = probe do P2 em diante morrendo com -EEXIST, ou
   seja, co-op de 4 reduzido a 1.

E o inverso: backend sem `hidraw_path` (FakeController) ou jogador sem MAC não
podem quebrar nada — caem no uinput, que é o comportamento de hoje.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gamepad_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
    resolve_hidraw_path,
    start_gamepad_emulation,
)

MAC_P1 = "a0fa9cc31100"
MAC_P2 = "a0fa9cc31122"


class _FakePad:
    flavor = "dualsense"

    def stop(self) -> None: ...


@pytest.fixture()
def chamadas(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Intercepta a factory: registra os kwargs de cada vpad pedido."""
    registro: list[dict[str, Any]] = []

    def _fake_factory(flavor: str | None, **kwargs: Any) -> Any:
        registro.append({"flavor": flavor, **kwargs})
        return _FakePad()

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
        _fake_factory,
    )
    return registro


class _FakeReader:
    """EvdevReader falso já com o grab confirmado."""

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
        self.grab_state = "off"

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        self.grab_state = "held" if grab else "off"
        return True

    def stop(self) -> None: ...

    def snapshot(self) -> Any:  # pragma: no cover - forward_all não roda aqui
        raise NotImplementedError


def _daemon(*, hidraw: dict[str | None, str] | None = None) -> Any:
    """Daemon falso cujo controller responde `hidraw_path` como o backend real."""
    calls: list[str | None] = []

    def _hidraw_path(uniq: str | None = None) -> str | None:
        calls.append(uniq)
        return (hidraw or {}).get(uniq)

    controller = SimpleNamespace(
        _evdev=SimpleNamespace(_device_path=Path("/dev/input/event5")),
        primary_uniq=MAC_P1,
        _desired=SimpleNamespace(player_leds=None),
        set_player_leds=lambda _bits: None,
        hidraw_path=_hidraw_path if hidraw is not None else None,
    )
    return SimpleNamespace(
        config=SimpleNamespace(
            coop_enabled=True,
            gamepad_flavor="dualsense",
            gamepad_emulation_enabled=False,
        ),
        _gamepad_device=None,
        _mouse_device=None,
        controller=controller,
        _coop_manager=None,
        hidraw_calls=calls,
    )


class TestResolveHidrawPath:
    def test_delega_ao_backend(self) -> None:
        daemon = _daemon(hidraw={None: "/dev/hidraw4", MAC_P2: "/dev/hidraw7"})

        assert resolve_hidraw_path(daemon, None) == "/dev/hidraw4"
        assert resolve_hidraw_path(daemon, MAC_P2) == "/dev/hidraw7"

    def test_backend_sem_hidraw_path_devolve_none(self) -> None:
        """FakeController/IController não têm o método — vpad cai no uinput."""
        assert resolve_hidraw_path(_daemon(), None) is None

    def test_backend_que_estoura_nao_derruba_o_vpad(self) -> None:
        def _boom(_uniq: str | None = None) -> str:
            raise OSError("hidraw sumiu no meio do hotplug")

        daemon = _daemon(hidraw={})
        daemon.controller.hidraw_path = _boom

        assert resolve_hidraw_path(daemon, None) is None

    def test_controle_desconhecido_devolve_none(self) -> None:
        daemon = _daemon(hidraw={None: "/dev/hidraw4"})

        assert resolve_hidraw_path(daemon, MAC_P2) is None


class TestGamepadPrimario:
    def test_p1_recebe_player_1_e_o_hidraw_do_primario(
        self, chamadas: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gamepad_mod, "_set_controller_grab", lambda *_a: None)
        daemon = _daemon(hidraw={None: "/dev/hidraw4"})

        assert start_gamepad_emulation(daemon, flavor="dualsense") is True
        assert chamadas == [
            {"flavor": "dualsense", "rumble_sink": chamadas[0]["rumble_sink"],
             "player": 1, "hidraw_path": "/dev/hidraw4"}
        ]
        assert daemon.hidraw_calls == [None]  # o primário é pedido por default

    def test_factory_sem_backend_falha_o_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gamepad_mod, "_set_controller_grab", lambda *_a: None)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
            lambda *_a, **_k: None,
        )
        daemon = _daemon(hidraw={None: "/dev/hidraw4"})

        assert start_gamepad_emulation(daemon, flavor="dualsense") is False
        assert daemon._gamepad_device is None
        assert daemon.config.gamepad_emulation_enabled is False


class TestCoopPorJogador:
    @pytest.fixture(autouse=True)
    def _sem_hardware(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _FakeReader
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll",
            lambda self: True,
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
            lambda: {MAC_P1: Path("/dev/input/event5"),
                     MAC_P2: Path("/dev/input/event7")},
        )
        monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})

    def test_secundario_recebe_o_seu_player_e_o_seu_hidraw(
        self, chamadas: list[dict[str, Any]]
    ) -> None:
        """MAC próprio por jogador: o vpad do P2 não pode nascer com `player=1`."""
        daemon = _daemon(hidraw={None: "/dev/hidraw4", MAC_P2: "/dev/hidraw7"})
        daemon._gamepad_device = _FakePad()
        CoopManager(daemon).sync()

        assert len(chamadas) == 1
        assert chamadas[0]["player"] == 2
        assert chamadas[0]["hidraw_path"] == "/dev/hidraw7"  # o DELE, não o do P1

    def test_jogador_sem_mac_nao_pede_hidraw(
        self, chamadas: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Identidade "path:" não casa handle nenhum — cai no uinput, sem chutar."""
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
            lambda: {MAC_P1: Path("/dev/input/event5"),
                     "path:/dev/input/event7": Path("/dev/input/event7")},
        )
        daemon = _daemon(hidraw={None: "/dev/hidraw4"})
        daemon._gamepad_device = _FakePad()
        CoopManager(daemon).sync()

        assert chamadas[0]["hidraw_path"] is None
        assert daemon.hidraw_calls == []  # nem chegou a perguntar ao backend

    def test_vpad_recusado_derruba_o_jogador_e_agenda_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
            lambda *_a, **_k: None,
        )
        daemon = _daemon(hidraw={None: "/dev/hidraw4", MAC_P2: "/dev/hidraw7"})
        daemon._gamepad_device = _FakePad()
        mgr = CoopManager(daemon)
        mgr.sync()

        assert mgr._players == {}
        assert mgr._retry_spawn is True

    def test_hidraw_for_ignora_identidade_por_path(self) -> None:
        daemon = _daemon(hidraw={None: "/dev/hidraw4"})

        assert CoopManager(daemon)._hidraw_for("path:/dev/input/event7") is None
        assert daemon.hidraw_calls == []


class TestCoopModuloNaoImportaBackendConcreto:
    def test_coop_fala_com_a_factory(self) -> None:
        """Regressão de arquitetura: quem escolhe o backend é a factory.

        O co-op voltar a construir `UinputGamepad` na mão desliga o uhid (e a
        vibração da máscara DualSense) sem que nenhum outro teste fique vermelho.
        """
        fonte = Path(coop_mod.__file__).read_text(encoding="utf-8")

        assert "make_virtual_pad" in fonte
        assert "UinputGamepad.for_flavor" not in fonte
