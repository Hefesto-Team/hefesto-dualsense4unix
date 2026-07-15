"""FEAT-NATIVE-MODE-01 — Modo Nativo ("release total" do controle).

Cobre o setter do daemon (neutraliza saída + gate + pause + flag), a
idempotência, a restauração ao desligar, o gate do autoswitch e a rota IPC.
"""
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
    # Evita uinput real: os setters de emulação viram no-op que registram.
    d.set_mouse_emulation = MagicMock(return_value=False)  # type: ignore[method-assign]
    d.set_gamepad_emulation = MagicMock(return_value=True)  # type: ignore[method-assign]
    return d


def test_native_on_neutraliza_e_gate(daemon: Daemon, tmp_config: Any) -> None:
    daemon.config.rumble_active = (100, 100)
    assert daemon.set_native_mode(True) is True
    assert daemon.is_native_mode() is True
    assert daemon.store.native_mode_active is True
    # Rumble em passthrough (o hefesto não re-asserta).
    assert daemon.config.rumble_active is None
    # Emulação desligada (libera grab/uinput) com origin="profile": NÃO carimba o
    # lock manual de 30s — senão o restore ao desligar seria bloqueado.
    daemon.set_mouse_emulation.assert_called_with(False, origin="profile")  # type: ignore[attr-defined]
    daemon.set_gamepad_emulation.assert_called_with(False, origin="profile")  # type: ignore[attr-defined]
    # Flag persistido (JSON com o stash).
    assert (tmp_config / "native_mode.flag").exists()


def test_native_nao_usa_pause(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    """BUG-NATIVE-RESUME-CLOBBERS-PAUSE-01 (design): o Modo Nativo gateia o
    dispatch pelo próprio flag, NÃO por pause(). Então não pisa num pause manual
    anterior e `daemon.resume` não "des-solta" o controle."""
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    # Pause manual anterior.
    daemon._paused = True
    daemon.set_native_mode(True)
    assert daemon.is_paused() is True  # native não mexeu no pause
    # resume() durante native: o gate é o _native_mode, que continua ativo.
    daemon.resume()
    assert daemon.is_native_mode() is True  # continua solto para o jogo
    daemon.set_native_mode(False)
    # Off não força pause nem resume — respeita o estado de pause pós-resume.


def test_native_off_restaura_e_limpa(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch, tmp_config: Any
) -> None:
    daemon.set_native_mode(True)
    reapplied: list[str] = []
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: reapplied.append("x"))
    assert daemon.set_native_mode(False) is False
    assert daemon.is_native_mode() is False
    assert daemon.store.native_mode_active is False
    assert reapplied == ["x"]  # re-aplicou o último perfil
    assert not (tmp_config / "native_mode.flag").exists()


def test_native_restaura_gamepad_do_stash(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch, tmp_config: Any
) -> None:
    """BUG-NATIVE-DESTROYS-GAMEPAD-01: o gamepad virtual ligado ANTES do Modo
    Nativo é restaurado ao desligar (o release apaga o flag; o stash preserva)."""
    from hefesto_dualsense4unix.utils import session as session_mod

    # Sessão anterior: gamepad ligado (flavor xbox).
    session_mod.save_gamepad_emulation(True, "xbox")
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    daemon.set_native_mode(True)
    # O stash capturou o gamepad ligado.
    assert daemon._native_emu_stash["gamepad"] == [True, "xbox"]
    daemon.set_gamepad_emulation.reset_mock()  # type: ignore[attr-defined]
    daemon.set_native_mode(False)
    # Restaurou o gamepad (precedência sobre mouse).
    daemon.set_gamepad_emulation.assert_called_with(True, "xbox", origin="profile")  # type: ignore[attr-defined]


def test_native_flag_stash_roundtrip_e_legado(tmp_config: Any) -> None:
    """O flag guarda o stash (JSON) e o load o devolve; conteúdo legado "1" ok."""
    from hefesto_dualsense4unix.utils.session import load_native_mode, save_native_mode

    save_native_mode(True, emu_stash={"gamepad": [True, "xbox"], "mouse": [False, 6, 1]})
    active, stash = load_native_mode()
    assert active is True
    assert stash["gamepad"] == [True, "xbox"]
    # Legado "1\n" → ativo com stash vazio (sem crash).
    (tmp_config / "native_mode.flag").write_text("1\n", encoding="utf-8")
    active2, stash2 = load_native_mode()
    assert active2 is True and stash2 == {}
    # Ausente → (False, {}).
    (tmp_config / "native_mode.flag").unlink()
    assert load_native_mode() == (False, {})


def test_native_idempotente(daemon: Daemon) -> None:
    daemon.set_native_mode(True)
    daemon.set_mouse_emulation.reset_mock()  # type: ignore[attr-defined]
    # Ligar de novo é no-op (não re-neutraliza).
    assert daemon.set_native_mode(True) is True
    daemon.set_mouse_emulation.assert_not_called()  # type: ignore[attr-defined]


def test_autoswitch_gateado_por_native_mode() -> None:
    store = StateStore()
    store.set_native_mode_active(True)
    manager = MagicMock()
    sw = AutoSwitcher(manager=manager, window_reader=lambda: {}, store=store)
    sw._activate("qualquer", {"wm_class": "Sackboy"})
    manager.activate.assert_not_called()  # não ativa perfil em modo nativo


def test_state_full_inclui_native_mode(daemon: Daemon) -> None:
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    server = IpcServer(
        controller=daemon.controller,
        store=daemon.store,
        profile_manager=MagicMock(),
        daemon=daemon,
    )
    daemon.set_native_mode(True)
    import asyncio

    state = asyncio.run(server._handle_daemon_state_full({}))
    assert state["native_mode"] is True


async def test_boot_em_modo_nativo_nao_restaura_emulacao(
    tmp_config: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auditoria #4: boot com native_mode.flag — sobe SOLTO (native_mode ativo,
    dispatch gateado) e NÃO restaura emulação de mouse/gamepad persistida (o
    controle fica com o jogo)."""
    from hefesto_dualsense4unix.utils import session as session_mod

    # Sessão anterior: gamepad ligado E Modo Nativo ligado.
    session_mod.save_gamepad_emulation(True, "xbox")
    session_mod.save_native_mode(True, emu_stash={"gamepad": [True, "xbox"]})
    # Não criar uinput real.
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
    # Emulação NÃO restaurada (gate `and not self._native_mode` no boot).
    assert d.config.gamepad_emulation_enabled is False
    assert d.config.mouse_emulation_enabled is False
    # O stash foi carregado (para um native off futuro restaurar).
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

    # Sem 'enabled' → toggle (off→on).
    r1 = asyncio.run(server._handle_native_mode_set({}))
    assert r1 == {"status": "ok", "native_mode": True}
    # Toggle de novo (on→off) — restore chamará _reapply; stub para não tocar disco.
    daemon._reapply_last_profile = lambda: None  # type: ignore[method-assign]
    r2 = asyncio.run(server._handle_native_mode_set({}))
    assert r2 == {"status": "ok", "native_mode": False}


# --- HARM-16: sair de um modo zera os motores --------------------------


def _rumbles(controller: FakeController) -> list[tuple[int, int]]:
    return [c.payload for c in controller.commands if c.kind == "set_rumble"]


def test_native_off_zera_os_motores(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HARM-16: no Modo Nativo quem vibra o controle é o JOGO (hidraw direto,
    com o nosso output mutado). Ao sair, `rumble_active` está em passthrough —
    o reassert do poll loop é no-op — e ninguém zerava o hardware: o controle
    vibrava para sempre e o jogo perdia a vibração."""
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    daemon.set_native_mode(True)
    controller: FakeController = daemon.controller  # type: ignore[assignment]
    controller.commands.clear()

    daemon.set_native_mode(False)

    assert (0, 0) in _rumbles(controller)


def test_native_off_zera_depois_de_desmutar(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ordem importa: mutado, o report_thread não escreve NADA — zerar antes
    do unmute deixaria o motor ligado até a próxima mudança de output."""
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    ordem: list[str] = []
    daemon.controller.set_output_mute = lambda muted: ordem.append(  # type: ignore[attr-defined]
        f"mute={muted}"
    )
    daemon.controller.set_rumble = lambda weak, strong: ordem.append(  # type: ignore[method-assign]
        f"rumble={weak},{strong}"
    )
    daemon.set_native_mode(True)
    ordem.clear()

    daemon.set_native_mode(False)

    assert ordem[:2] == ["mute=False", "rumble=0,0"]


def test_gamepad_off_zera_os_motores(tmp_config: Any) -> None:
    """HARM-16 (mesmo mal, outro modo): o vpad morre no meio de um FF do jogo e
    o motor fica ligado — em passthrough ninguém re-afirma o silêncio."""
    d = Daemon(controller=FakeController())
    d.config.rumble_active = None
    controller: FakeController = d.controller  # type: ignore[assignment]
    controller.commands.clear()

    d.set_gamepad_emulation(False)

    assert (0, 0) in _rumbles(controller)


def test_saida_de_modo_nao_desfaz_rumble_fixado_pela_usuaria(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com rumble FIXADO (aba Rumble), o dono é a usuária: o reassert re-afirma
    o valor de qualquer jeito e zerar seria desfazer o gesto dela."""
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    daemon.set_native_mode(True)
    daemon.config.rumble_active = (120, 200)
    controller: FakeController = daemon.controller  # type: ignore[assignment]
    controller.commands.clear()

    daemon.set_native_mode(False)

    assert _rumbles(controller) == []
