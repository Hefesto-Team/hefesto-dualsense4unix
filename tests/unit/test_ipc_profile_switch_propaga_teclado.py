"""Wiring REAL do fix A-06/A8 (FEAT-POINT-AND-CLICK-01).

O teste antigo deste arquivo injetava `keyboard_device` direto no
`ProfileManager` — mascarava o bug A8: no boot real, `start_ipc` e
`start_autoswitch` criavam o manager ANTES de o keyboard subir
(`lifecycle.py` sobe IPC/autoswitch primeiro) e capturavam `None` para
sempre; `profile.switch` (IPC) e o autoswitch nunca propagavam
`key_bindings` ao teclado vivo.

Aqui exercitamos o caminho de boot verdadeiro: `start_ipc(daemon)` /
`start_autoswitch(daemon)` com `_keyboard_device=None`, o device sobe
DEPOIS, e a ativação de perfil TEM que chegar ao `set_bindings` — o
provider lazy resolve o device a cada ativação (imune também ao device
anulado/recriado em disconnect/reload).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _mk_profile(name: str, **kw: object) -> Profile:
    defaults: dict[str, object] = {
        "match": MatchCriteria(window_class=[f"{name}_class"]),
        "priority": 10,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Off"),
        ),
        "leds": LedsConfig(lightbar=(0, 0, 0), player_leds=[False] * 5),
    }
    defaults.update(kw)
    return Profile(name=name, **defaults)  # type: ignore[arg-type]


class _FakeDaemon:
    """Mínimo que start_ipc/start_autoswitch e os handlers exigem.

    Espelha o estado do boot real: `_keyboard_device=None` (o keyboard sobe
    DEPOIS de IPC/autoswitch). `apply_profile_mouse` e
    `apply_profile_suppression` registram chamadas (são os appliers injetados
    no ProfileManager pelos callsites — BUG-PROFILE-MOUSE-KILLS-GAMEPAD-01: o
    mouse_applier passou de `set_mouse_emulation` cru para o guardado
    `apply_profile_mouse`).
    """

    def __init__(self) -> None:
        self.controller = FakeController()
        self.store = StateStore()
        self._ipc_server: Any = None
        self._autoswitch: Any = None
        self._keyboard_device: Any = None
        self.mouse_calls: list[tuple[bool, int, int]] = []
        self.suppression_calls: list[bool] = []

    def apply_profile_mouse(
        self, enabled: bool, speed: int, scroll_speed: int
    ) -> None:
        self.mouse_calls.append((enabled, int(speed), int(scroll_speed)))

    def apply_profile_suppression(
        self, desired: bool, *, profile: Any = None
    ) -> None:
        # R-02: o applier recebe QUEM mandou (o dublê só registra o valor).
        self.suppression_calls.append(desired)

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)


async def _start_ipc_sem_socket(
    daemon: _FakeDaemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Roda start_ipc real, pulando só o listen do socket unix.

    O wiring do ProfileManager — o que está sob teste — permanece 100% real.
    """
    from hefesto_dualsense4unix.daemon import ipc_server as ipc_server_mod
    from hefesto_dualsense4unix.daemon.subsystems.ipc import start_ipc

    async def _noop_start(self: Any) -> None:
        return None

    monkeypatch.setattr(ipc_server_mod.IpcServer, "start", _noop_start)
    await start_ipc(daemon)  # type: ignore[arg-type]


# --- IPC: boot real, keyboard sobe depois -----------------------------------


async def test_boot_real_ipc_switch_propaga_teclado(
    isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A8: start_ipc ANTES do keyboard; profile.switch ainda propaga bindings."""
    save_profile(_mk_profile("kbdprof", key_bindings={"triangle": ["KEY_V"]}))
    daemon = _FakeDaemon()
    daemon.controller.connect()

    # lifecycle.py: IPC sobe primeiro (keyboard ainda None)…
    await _start_ipc_sem_socket(daemon, monkeypatch)
    # …keyboard sobe DEPOIS.
    kbd = MagicMock()
    daemon._keyboard_device = kbd

    result = await daemon._ipc_server._handle_profile_switch({"name": "kbdprof"})

    assert result == {"active_profile": "kbdprof"}
    kbd.set_bindings.assert_called_once()
    assert kbd.set_bindings.call_args[0][0] == {"triangle": ("KEY_V",)}


async def test_boot_real_ipc_switch_sobrevive_device_recriado(
    isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disconnect anula e reload recria o device — o provider resolve o NOVO."""
    save_profile(_mk_profile("kbdprof", key_bindings={"triangle": ["KEY_V"]}))
    daemon = _FakeDaemon()
    daemon.controller.connect()
    await _start_ipc_sem_socket(daemon, monkeypatch)

    kbd_antigo = MagicMock()
    daemon._keyboard_device = kbd_antigo
    await daemon._ipc_server._handle_profile_switch({"name": "kbdprof"})
    kbd_antigo.set_bindings.assert_called_once()

    # connection.py:233-236 anula no disconnect; reload recria outro device.
    daemon._keyboard_device = None
    kbd_novo = MagicMock()
    daemon._keyboard_device = kbd_novo
    await daemon._ipc_server._handle_profile_switch({"name": "kbdprof"})

    kbd_novo.set_bindings.assert_called_once()
    # O device antigo NÃO recebe a segunda ativação.
    kbd_antigo.set_bindings.assert_called_once()


async def test_boot_real_ipc_switch_aplica_secao_mouse(
    isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FEAT-POINT-AND-CLICK-01: profile.switch liga o mouse do perfil."""
    save_profile(
        _mk_profile(
            "mouseprof",
            mouse={"enabled": True, "speed": 8, "scroll_speed": 2},
        )
    )
    daemon = _FakeDaemon()
    daemon.controller.connect()
    await _start_ipc_sem_socket(daemon, monkeypatch)

    await daemon._ipc_server._handle_profile_switch({"name": "mouseprof"})

    assert daemon.mouse_calls == [(True, 8, 2)]
    # suppression_applier é chamado SEMPRE (com o default False aqui).
    assert daemon.suppression_calls == [False]


async def test_boot_restore_nao_aplica_secao_mouse(
    isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BUG-BOOT-RESTORE-FLIPS-EMULATION-01: o restore do boot NÃO reaplica a
    seção mouse do perfil (mouse_applier=None) — os flags persistidos governam a
    emulação. Antes, restaurar um last_profile com mouse.enabled matava o gamepad
    recém-restaurado, apagava gamepad_emulation.flag e invertia a escolha da
    usuária a CADA boot. A supressão AINDA é restaurada (applier presente)."""
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile

    # RESTORE-ESCOPO-01 (22/07): o default do helper é MatchCriteria por
    # janela — e perfil de janela agora NÃO volta no restore de boot. O
    # assunto DESTE teste é a seção mouse, então o perfil vira MatchAny
    # (perfil "sempre", que o restore continua reativando).
    save_profile(
        _mk_profile(
            "mouseprof",
            match=MatchAny(),
            mouse={"enabled": True, "speed": 8, "scroll_speed": 2},
        )
    )
    daemon = _FakeDaemon()
    daemon.controller.connect()
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_last_profile",
        lambda: "mouseprof",
    )
    # PERFIL-03: o restore agora consulta também o marker manual
    # (`resolve_boot_profile`) — anula-o para o teste não ler o
    # active_profile.txt REAL da máquina (hermeticidade).
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.read_active_marker",
        lambda: None,
    )

    await restore_last_profile(daemon)  # type: ignore[arg-type]

    # A seção mouse do perfil NÃO foi aplicada no restore (governado pelos flags).
    assert daemon.mouse_calls == []
    # A supressão do perfil ainda é aplicada (com o default False aqui).
    assert daemon.suppression_calls == [False]


# --- Autoswitch: boot real, keyboard sobe depois ------------------------------


async def test_boot_real_autoswitch_propaga_teclado(
    isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A8 (caso análogo): start_autoswitch antes do keyboard; _activate propaga."""
    from hefesto_dualsense4unix.daemon.subsystems import autoswitch as sub_autoswitch

    save_profile(_mk_profile("kbdprof", key_bindings={"l1": ["KEY_LEFTSHIFT"]}))
    daemon = _FakeDaemon()
    daemon.controller.connect()

    # Hermético: sem probe de systemctl nem backend de compositor real.
    monkeypatch.setattr(sub_autoswitch, "_ensure_display_env", lambda: None)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.window_detect.build_window_reader",
        lambda: (lambda: {}),
    )
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT", "1")

    await sub_autoswitch.start_autoswitch(daemon)  # type: ignore[arg-type]
    kbd = MagicMock()
    daemon._keyboard_device = kbd

    daemon._autoswitch._activate("kbdprof", {"wm_class": "kbdprof_class"})

    kbd.set_bindings.assert_called_once()
    assert kbd.set_bindings.call_args[0][0] == {"l1": ("KEY_LEFTSHIFT",)}


async def test_boot_real_autoswitch_aplica_mouse_e_supressao(
    isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Autoswitch ativa perfil com mouse+supressão via appliers do daemon."""
    from hefesto_dualsense4unix.daemon.subsystems import autoswitch as sub_autoswitch

    save_profile(
        _mk_profile(
            "gameprof",
            mouse={"enabled": True, "speed": 8, "scroll_speed": 1},
            suppress_desktop_emulation=True,
        )
    )
    daemon = _FakeDaemon()
    daemon.controller.connect()
    monkeypatch.setattr(sub_autoswitch, "_ensure_display_env", lambda: None)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.window_detect.build_window_reader",
        lambda: (lambda: {}),
    )
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT", "1")

    await sub_autoswitch.start_autoswitch(daemon)  # type: ignore[arg-type]
    daemon._autoswitch._activate("gameprof", {"wm_class": "gameprof_class"})

    assert daemon.mouse_calls == [(True, 8, 1)]
    assert daemon.suppression_calls == [True]


# --- Complemento: nível do manager (caminho direto, sem daemon) ---------------


async def test_manager_direto_com_keyboard_device_legado(
    isolated_profiles_dir: Path,
) -> None:
    """Backcompat: `keyboard_device` eager (sem provider) continua funcionando."""
    save_profile(_mk_profile("overwatch_kbd", key_bindings={"triangle": ["KEY_V"]}))
    fc = FakeController()
    fc.connect()
    kbd_mock = MagicMock()
    manager = ProfileManager(
        controller=fc, store=StateStore(), keyboard_device=kbd_mock
    )

    manager.activate("overwatch_kbd")

    kbd_mock.set_bindings.assert_called_once()
    assert kbd_mock.set_bindings.call_args[0][0] == {"triangle": ("KEY_V",)}


async def test_manager_provider_tem_precedencia_sobre_device_eager(
    isolated_profiles_dir: Path,
) -> None:
    """Com provider E device eager, o provider vence (fonte viva)."""
    save_profile(_mk_profile("prof", key_bindings={"r1": ["KEY_DOT"]}))
    fc = FakeController()
    fc.connect()
    eager = MagicMock()
    vivo = MagicMock()
    manager = ProfileManager(
        controller=fc,
        store=StateStore(),
        keyboard_device=eager,
        keyboard_device_provider=lambda: vivo,
    )

    manager.activate("prof")

    vivo.set_bindings.assert_called_once()
    eager.set_bindings.assert_not_called()
