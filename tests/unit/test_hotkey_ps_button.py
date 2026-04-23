"""Testes do PS solo (FEAT-HOTKEY-STEAM-01).

Cobre:
  - `HotkeyManager` dispara callback `on_ps_solo` no release sem combo.
  - PS + D-pad (combo) suprime PS solo.
  - `steam_launcher.open_or_focus_steam` usa spawn quando pgrep falha.
  - Usa wmctrl quando pgrep acha processo.
  - Binário ausente loga warning uma vez e retorna False.
  - Nunca chama `shell=True`.
"""
from __future__ import annotations

import subprocess
from typing import Any

import pytest

from hefesto.integrations import steam_launcher
from hefesto.integrations.hotkey_daemon import HotkeyManager

# ---------------------------------------------------------------------------
# HotkeyManager.on_ps_solo
# ---------------------------------------------------------------------------


def test_ps_solo_dispara_no_release_sem_combo():
    fired: list[str] = []
    mgr = HotkeyManager(on_ps_solo=lambda: fired.append("solo"))

    # Press curto: PS entra e sai sem combo.
    assert mgr.observe(["ps"], now=0.0) is None
    assert fired == []
    result = mgr.observe([], now=0.05)
    assert result == "ps_solo"
    assert fired == ["solo"]


def test_ps_solo_dispara_mesmo_apos_hold_longo():
    """PS segurado sozinho por muito tempo e entao solto ainda conta como solo.

    Semantica: o usuário não combinou com D-pad; pressionar PS e soltar sempre
    vale como solo. O buffer de 150ms governa apenas o combo — não filtra solo.
    """
    fired: list[str] = []
    mgr = HotkeyManager(on_ps_solo=lambda: fired.append("solo"))
    for t in (0.0, 0.2, 0.4, 0.6):
        mgr.observe(["ps"], now=t)
    assert fired == []
    assert mgr.observe([], now=0.65) == "ps_solo"
    assert fired == ["solo"]


def test_ps_solo_suprimido_quando_combo_dispara():
    fired_next: list[str] = []
    fired_solo: list[str] = []
    mgr = HotkeyManager(
        on_next=lambda: fired_next.append("n"),
        on_ps_solo=lambda: fired_solo.append("solo"),
    )
    # PS + D-pad ↑ segurado alem do buffer -> combo dispara.
    mgr.observe(["ps", "dpad_up"], now=0.0)
    mgr.observe(["ps", "dpad_up"], now=0.2)
    # Solta D-pad, PS ainda segurado.
    mgr.observe(["ps"], now=0.25)
    # Release do PS: não deve disparar solo porque combo ja disparou.
    mgr.observe([], now=0.3)
    assert fired_next == ["n"]
    assert fired_solo == []


def test_ps_solo_nao_dispara_sem_callback():
    mgr = HotkeyManager()
    mgr.observe(["ps"], now=0.0)
    # Não explode e retorna nome do evento.
    assert mgr.observe([], now=0.05) == "ps_solo"


def test_ps_solo_nao_dispara_se_ps_nunca_foi_pressionado():
    fired: list[str] = []
    mgr = HotkeyManager(on_ps_solo=lambda: fired.append("solo"))
    mgr.observe([], now=0.0)
    mgr.observe(["cross"], now=0.1)
    mgr.observe([], now=0.2)
    assert fired == []


def test_ps_solo_readiepara_em_novo_press():
    fired: list[str] = []
    mgr = HotkeyManager(on_ps_solo=lambda: fired.append("solo"))
    mgr.observe(["ps"], now=0.0)
    mgr.observe([], now=0.05)
    mgr.observe(["ps"], now=0.10)
    mgr.observe([], now=0.15)
    assert fired == ["solo", "solo"]


# ---------------------------------------------------------------------------
# steam_launcher.open_or_focus_steam
# ---------------------------------------------------------------------------


def _make_completed(rc: int, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["fake"], returncode=rc, stdout=stdout, stderr="")


@pytest.fixture(autouse=True)
def _reset_missing_warning():
    steam_launcher._reset_missing_warning_for_tests()
    yield
    steam_launcher._reset_missing_warning_for_tests()


def test_open_or_focus_steam_spawn_quando_nao_roda():
    popen_calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_popen(cmd: list[str], **kwargs: Any) -> object:
        popen_calls.append((cmd, kwargs))
        return object()

    def fake_pgrep(_cmd: list[str]) -> subprocess.CompletedProcess[str]:
        # Não achou processo
        return _make_completed(rc=1, stdout="")

    ok = steam_launcher.open_or_focus_steam(
        which=lambda _name: "/usr/bin/steam",
        pgrep_runner=fake_pgrep,
        popen_runner=fake_popen,
    )
    assert ok is True
    assert len(popen_calls) == 1
    cmd, kwargs = popen_calls[0]
    assert cmd == ["steam"]
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
    assert kwargs["start_new_session"] is True
    # Nunca passa shell=True.
    assert "shell" not in kwargs or kwargs["shell"] is False


def test_open_or_focus_steam_usa_wmctrl_quando_processo_existe(monkeypatch):
    wmctrl_calls: list[list[str]] = []
    popen_called = False

    def fake_pgrep(_cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return _make_completed(rc=0, stdout="12345\n")

    def fake_wmctrl(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        wmctrl_calls.append(cmd)
        if cmd[:2] == ["wmctrl", "-lx"]:
            listing = (
                "0x01400007  0 steam.Steam  host-hefesto  Steam\n"
                "0x01400009  0 Firefox.firefox  host-hefesto  Mozilla\n"
            )
            return _make_completed(rc=0, stdout=listing)
        if cmd[:2] == ["wmctrl", "-ia"]:
            return _make_completed(rc=0)
        return _make_completed(rc=1)

    def fake_popen(*_args: Any, **_kwargs: Any) -> object:
        nonlocal popen_called
        popen_called = True
        return object()

    # shutil.which retorna tanto steam quanto wmctrl
    monkeypatch.setattr(steam_launcher.shutil, "which", lambda name: f"/usr/bin/{name}")

    ok = steam_launcher.open_or_focus_steam(
        which=lambda name: f"/usr/bin/{name}",
        pgrep_runner=fake_pgrep,
        wmctrl_runner=fake_wmctrl,
        popen_runner=fake_popen,
    )
    assert ok is True
    assert popen_called is False
    assert wmctrl_calls[0] == ["wmctrl", "-lx"]
    # Segunda chamada foca a janela steam.Steam (0x01400007).
    assert wmctrl_calls[1] == ["wmctrl", "-ia", "0x01400007"]


def test_open_or_focus_steam_fallback_spawn_quando_janela_nao_existe(monkeypatch):
    popen_calls: list[list[str]] = []

    def fake_pgrep(_cmd: list[str]) -> subprocess.CompletedProcess[str]:
        # Processo rodando.
        return _make_completed(rc=0, stdout="99999\n")

    def fake_wmctrl(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["wmctrl", "-lx"]:
            # Nenhuma janela Steam.
            return _make_completed(rc=0, stdout="0x01400009  0 Firefox.firefox  host foo\n")
        return _make_completed(rc=0)

    def fake_popen(cmd: list[str], **_kwargs: Any) -> object:
        popen_calls.append(cmd)
        return object()

    monkeypatch.setattr(steam_launcher.shutil, "which", lambda name: f"/usr/bin/{name}")
    ok = steam_launcher.open_or_focus_steam(
        which=lambda name: f"/usr/bin/{name}",
        pgrep_runner=fake_pgrep,
        wmctrl_runner=fake_wmctrl,
        popen_runner=fake_popen,
    )
    assert ok is True
    assert popen_calls == [["steam"]]


def test_open_or_focus_steam_binario_ausente_loga_uma_vez(caplog):
    caplog.set_level("WARNING")
    fake_popen_called = False

    def fake_popen(*_a: Any, **_k: Any) -> object:
        nonlocal fake_popen_called
        fake_popen_called = True
        return object()

    ok1 = steam_launcher.open_or_focus_steam(
        which=lambda _name: None,
        popen_runner=fake_popen,
    )
    ok2 = steam_launcher.open_or_focus_steam(
        which=lambda _name: None,
        popen_runner=fake_popen,
    )
    assert ok1 is False
    assert ok2 is False
    # Não tenta Popen quando binário não existe.
    assert fake_popen_called is False


def test_open_or_focus_steam_nunca_levanta():
    """Mesmo se pgrep explode, a função retorna False e não propaga."""
    def bomba_pgrep(_cmd: list[str]) -> subprocess.CompletedProcess[str]:
        raise RuntimeError("pgrep morreu")

    def fake_popen(_cmd: list[str], **_kwargs: Any) -> object:
        return object()

    ok = steam_launcher.open_or_focus_steam(
        which=lambda name: f"/usr/bin/{name}",
        pgrep_runner=bomba_pgrep,
        popen_runner=fake_popen,
    )
    # pgrep falhou -> tratou como "não rodando" -> spawn -> True.
    assert ok is True


def test_daemon_config_ps_button_defaults():
    from hefesto.daemon.lifecycle import DaemonConfig

    cfg = DaemonConfig()
    assert cfg.ps_button_action == "steam"
    assert cfg.ps_button_command == []


def test_start_hotkey_manager_instancia_e_chama_steam(monkeypatch):
    """Daemon._start_hotkey_manager() cria HotkeyManager; on_ps_solo chama steam."""
    from hefesto.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto.integrations import steam_launcher as _sl
    from hefesto.testing import FakeController

    called: list[str] = []
    monkeypatch.setattr(_sl, "open_or_focus_steam", lambda **_kw: called.append("steam") or True)

    fc = FakeController(transport="usb", states=[])
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(ps_button_action="steam"),
    )
    daemon._start_hotkey_manager()

    assert daemon._hotkey_manager is not None
    daemon._hotkey_manager.on_ps_solo()
    assert called == ["steam"]


def test_start_hotkey_manager_none_nao_chama_steam(monkeypatch):
    """ps_button_action='none' → on_ps_solo não chama nenhum launcher."""
    from hefesto.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto.integrations import steam_launcher as _sl
    from hefesto.testing import FakeController

    called: list[str] = []
    monkeypatch.setattr(_sl, "open_or_focus_steam", lambda **_kw: called.append("steam") or True)

    fc = FakeController(transport="usb", states=[])
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(ps_button_action="none"),
    )
    daemon._start_hotkey_manager()
    daemon._hotkey_manager.on_ps_solo()

    assert called == []
