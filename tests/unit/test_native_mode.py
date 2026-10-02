"""FEAT-NATIVE-MODE-01 — Modo Nativo ("release total" do controle)."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
def tmp_config(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Isola o config_dir (flags de sessão) num tmp."""
    from hefesto_dualsense4unix.utils import session as session_mod

    monkeypatch.setattr(session_mod, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


@pytest.fixture
def daemon(tmp_config: Any, monkeypatch: pytest.MonkeyPatch) -> Daemon:
    d = Daemon(controller=FakeController())
    d.set_mouse_emulation = MagicMock(return_value=False)  # type: ignore[method-assign]
    d.set_gamepad_emulation = MagicMock(return_value=True)  # type: ignore[method-assign]
    return d


def test_native_on_neutraliza_e_gate(daemon: Daemon, tmp_config: Any) -> None:
    daemon.config.rumble_active = (100, 100)
    assert daemon.set_native_mode(True, origin="manual") is True
    assert daemon.is_native_mode() is True
    assert daemon.store.native_mode_active is True
    assert daemon.config.rumble_active is None
    daemon.set_mouse_emulation.assert_called_with(False, origin="profile")  # type: ignore[attr-defined]
    daemon.set_gamepad_emulation.assert_called_with(False, origin="profile")  # type: ignore[attr-defined]
    assert (tmp_config / "native_mode.flag").exists()


def test_native_nao_usa_pause(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    """BUG-NATIVE-RESUME-CLOBBERS-PAUSE-01 (design): o Modo Nativo gateia o"""
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    daemon._paused = True
    daemon.set_native_mode(True, origin="manual")
    assert daemon.is_paused() is True
    daemon.resume()
    assert daemon.is_native_mode() is True
    daemon.set_native_mode(False, origin="manual")


def test_native_off_restaura_e_limpa(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch, tmp_config: Any
) -> None:
    daemon.set_native_mode(True, origin="manual")
    reapplied: list[str] = []
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: reapplied.append("x"))
    assert daemon.set_native_mode(False, origin="manual") is False
    assert daemon.is_native_mode() is False
    assert daemon.store.native_mode_active is False
    assert reapplied == ["x"]
    assert not (tmp_config / "native_mode.flag").exists()


def test_native_restaura_gamepad_do_stash(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch, tmp_config: Any
) -> None:
    """BUG-NATIVE-DESTROYS-GAMEPAD-01: o gamepad virtual ligado ANTES do Modo"""
    from hefesto_dualsense4unix.utils import session as session_mod

    session_mod.save_gamepad_emulation(True, "xbox")
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    daemon.set_native_mode(True, origin="manual")
    assert daemon._native_emu_stash["gamepad"] == [True, "xbox"]
    daemon.set_gamepad_emulation.reset_mock()  # type: ignore[attr-defined]
    daemon.set_native_mode(False, origin="manual")
    daemon.set_gamepad_emulation.assert_called_with(  # type: ignore[attr-defined]
        True, "xbox", origin="profile", caminho=None
    )


def test_native_flag_stash_roundtrip_e_legado(tmp_config: Any) -> None:
    """O flag guarda o stash (JSON) e o load o devolve; conteúdo legado "1" ok."""
    from hefesto_dualsense4unix.utils.session import load_native_mode, save_native_mode

    save_native_mode(True, emu_stash={"gamepad": [True, "xbox"], "mouse": [False, 6, 1]})
    active, stash = load_native_mode()
    assert active is True
    assert stash["gamepad"] == [True, "xbox"]
    (tmp_config / "native_mode.flag").write_text("1\n", encoding="utf-8")
    active2, stash2 = load_native_mode()
    assert active2 is True and stash2 == {}
    (tmp_config / "native_mode.flag").unlink()
    assert load_native_mode() == (False, {})


def test_native_idempotente(daemon: Daemon) -> None:
    daemon.set_native_mode(True, origin="manual")
    daemon.set_mouse_emulation.reset_mock()  # type: ignore[attr-defined]
    assert daemon.set_native_mode(True, origin="manual") is True
    daemon.set_mouse_emulation.assert_not_called()  # type: ignore[attr-defined]


def test_autoswitch_gateado_por_native_mode() -> None:
    store = StateStore()
    store.set_native_mode_active(True)
    manager = MagicMock()
    sw = AutoSwitcher(manager=manager, window_reader=lambda: {}, store=store)
    sw._activate("qualquer", {"wm_class": "Sackboy"})
    manager.activate.assert_not_called()


def test_state_full_inclui_native_mode(daemon: Daemon) -> None:
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    server = IpcServer(
        controller=daemon.controller,
        store=daemon.store,
        profile_manager=MagicMock(),
        daemon=daemon,
    )
    daemon.set_native_mode(True, origin="manual")
    import asyncio

    state = asyncio.run(server._handle_daemon_state_full({}))
    assert state["native_mode"] is True


async def test_boot_em_modo_nativo_nao_restaura_emulacao(
    tmp_config: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auditoria #4: boot com native_mode.flag — sobe SOLTO (native_mode ativo,"""
    from hefesto_dualsense4unix.utils import session as session_mod

    session_mod.save_gamepad_emulation(True, "xbox")
    session_mod.save_native_mode(True, emu_stash={"gamepad": [True, "xbox"]})
    monkeypatch.setattr(Daemon, "_start_mouse_emulation", lambda self: True)

    cfg = DaemonConfig(
        poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
        autoswitch_enabled=False, keyboard_emulation_enabled=False,
        ps_button_action="none", mic_button_toggles_system=False,
    )
    d = Daemon(controller=FakeController(transport="usb"), config=cfg)
    run_task = asyncio.create_task(d.run())
    await asyncio.sleep(0.05)
    d.stop()
    await run_task

    assert d.is_native_mode() is True
    assert d.store.native_mode_active is True
    assert d.config.gamepad_emulation_enabled is False
    assert d.config.mouse_emulation_enabled is False
    assert d._native_emu_stash.get("gamepad") == [True, "xbox"]


def test_ipc_native_mode_set_toggle(daemon: Daemon) -> None:
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    server = IpcServer(
        controller=daemon.controller,
        store=daemon.store,
        profile_manager=MagicMock(),
        daemon=daemon,
    )
    import asyncio

    r1 = asyncio.run(server._handle_native_mode_set({}))
    assert r1 == {"status": "ok", "native_mode": True}
    daemon._reapply_last_profile = lambda: None  # type: ignore[method-assign]
    r2 = asyncio.run(server._handle_native_mode_set({}))
    assert r2 == {"status": "ok", "native_mode": False}


class _FakeVpad:
    """Gamepad virtual dublado — o suficiente para ser parado (sem uinput/uhid)."""

    flavor = "xbox"

    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


def _daemon_com_vpad(monkeypatch: pytest.MonkeyPatch) -> Daemon:
    """Daemon real com o vpad dublado — sem uinput/uhid de verdade."""
    from hefesto_dualsense4unix.integrations import virtual_pad

    monkeypatch.setattr(virtual_pad, "make_virtual_pad", lambda *_a, **_k: _FakeVpad())
    d = Daemon(
        controller=FakeController(),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    monkeypatch.setattr(d, "_reapply_last_profile", lambda: None)
    return d


def test_gamepad_on_com_nativo_ligado_sai_do_nativo(
    tmp_config: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Aceite do item: `gamepad on` com o nativo ligado não deixa os dois juntos."""
    d = _daemon_com_vpad(monkeypatch)
    d.set_native_mode(True, origin="manual")
    assert d.is_native_mode() is True

    d.set_gamepad_emulation(True, flavor="xbox", origin="manual")

    assert d.is_native_mode() is False
    assert d.config.gamepad_emulation_enabled is True
    assert d._gamepad_device is not None


def test_native_on_com_gamepad_ligado_derruba_o_vpad(
    tmp_config: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caminho inverso, com o daemon de verdade (sem os mocks do fixture)."""
    d = _daemon_com_vpad(monkeypatch)
    d.set_gamepad_emulation(True, flavor="xbox", origin="manual")
    assert d.config.gamepad_emulation_enabled is True

    d.set_native_mode(True, origin="manual")

    assert d.is_native_mode() is True
    assert d.config.gamepad_emulation_enabled is False
    assert d._gamepad_device is None


def test_gamepad_on_sem_nativo_nao_mexe_no_modo(
    tmp_config: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A saída do nativo é condicional: sem nativo ligado, nada de efeito extra"""
    d = _daemon_com_vpad(monkeypatch)
    chamadas: list[Any] = []
    monkeypatch.setattr(
        d, "_restore_emulation_from_stash", lambda: chamadas.append("restore")
    )

    d.set_gamepad_emulation(True, flavor="xbox", origin="manual")

    assert chamadas == []
    assert d.config.gamepad_emulation_enabled is True


def _rumbles(controller: FakeController) -> list[tuple[int, int]]:
    return [c.payload for c in controller.commands if c.kind == "set_rumble"]


def test_native_off_zera_os_motores(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HARM-16: no Modo Nativo quem vibra o controle é o JOGO (hidraw direto,"""
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    daemon.set_native_mode(True, origin="manual")
    controller: FakeController = daemon.controller  # type: ignore[assignment]
    controller.commands.clear()

    daemon.set_native_mode(False, origin="manual")

    assert (0, 0) in _rumbles(controller)


def test_native_off_zera_depois_de_desmutar(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ordem importa: mutado, o report_thread não escreve NADA — zerar antes"""
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    ordem: list[str] = []
    daemon.controller.set_output_mute = lambda muted: ordem.append(  # type: ignore[attr-defined]
        f"mute={muted}"
    )
    daemon.controller.set_rumble = lambda weak, strong: ordem.append(  # type: ignore[method-assign]
        f"rumble={weak},{strong}"
    )
    daemon.set_native_mode(True, origin="manual")
    ordem.clear()

    daemon.set_native_mode(False, origin="manual")

    assert ordem[:2] == ["mute=False", "rumble=0,0"]


def test_gamepad_off_zera_os_motores(tmp_config: Any) -> None:
    """HARM-16 (mesmo mal, outro modo): o vpad morre no meio de um FF do jogo e"""
    d = Daemon(controller=FakeController())
    d.config.rumble_active = None
    controller: FakeController = d.controller  # type: ignore[assignment]
    controller.commands.clear()

    d.set_gamepad_emulation(False, origin="manual")

    assert (0, 0) in _rumbles(controller)


def test_ligar_o_mouse_derruba_o_vpad_e_zera_os_motores(
    tmp_config: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O terceiro caminho de saída, que o HARM-16 não cobria."""
    d = Daemon(controller=FakeController())
    d.config.rumble_active = None
    d._gamepad_device = _FakeVpad()
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.mouse.start_mouse_emulation",
        lambda _t: True,
    )
    controller: FakeController = d.controller  # type: ignore[assignment]
    controller.commands.clear()

    d.set_mouse_emulation(True, origin="manual")

    assert d._gamepad_device is None
    assert (0, 0) in _rumbles(controller)


def test_zerar_e_consequencia_de_parar_o_vpad(tmp_config: Any) -> None:
    """A garantia mora no `stop`, não na memória de cada caller (HARM-16)."""
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import stop_gamepad_emulation

    d = Daemon(controller=FakeController())
    d.config.rumble_active = None
    d._gamepad_device = _FakeVpad()
    controller: FakeController = d.controller  # type: ignore[assignment]
    controller.commands.clear()

    stop_gamepad_emulation(d, persist=False, release_grab=False)

    assert (0, 0) in _rumbles(controller)


def test_saida_de_modo_nao_desfaz_rumble_fixado_pela_usuaria(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com rumble FIXADO (aba Rumble), o dono é a usuária: o reassert re-afirma"""
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    daemon.set_native_mode(True, origin="manual")
    daemon.config.rumble_active = (120, 200)
    controller: FakeController = daemon.controller  # type: ignore[assignment]
    controller.commands.clear()

    daemon.set_native_mode(False, origin="manual")

    assert _rumbles(controller) == []
