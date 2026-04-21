"""Testes da TUI via Textual Pilot (headless)."""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto.profiles import loader as loader_module
from hefesto.profiles.loader import save_profile
from hefesto.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto.tui.app import DaemonSnapshot, HefestoApp, MainScreen, StatusBar


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


def _mk_profile(name: str, **kw) -> Profile:
    defaults = {
        "match": MatchCriteria(window_class=[name]),
        "priority": 5,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Off"),
        ),
        "leds": LedsConfig(lightbar=(0, 0, 0)),
    }
    defaults.update(kw)
    return Profile(name=name, **defaults)


def test_daemon_snapshot_default():
    snap = DaemonSnapshot()
    assert snap.online is False
    assert snap.connected is False
    assert snap.profiles == []


def test_status_bar_offline():
    bar = StatusBar()
    bar.snapshot = DaemonSnapshot(online=False)
    rendered = bar.render()
    assert "offline" in rendered


def test_status_bar_online_conectado():
    bar = StatusBar()
    bar.snapshot = DaemonSnapshot(
        online=True, connected=True, transport="usb",
        battery_pct=85, active_profile="shooter",
    )
    rendered = bar.render()
    assert "bateria 85%" in rendered
    assert "usb" in rendered
    assert "shooter" in rendered


def test_status_bar_bateria_baixa_vermelha():
    bar = StatusBar()
    bar.snapshot = DaemonSnapshot(
        online=True, connected=True, transport="bt", battery_pct=10
    )
    rendered = bar.render()
    assert "[red]" in rendered


def test_status_bar_bateria_media_amarela():
    bar = StatusBar()
    bar.snapshot = DaemonSnapshot(
        online=True, connected=True, transport="usb", battery_pct=25
    )
    rendered = bar.render()
    assert "[yellow]" in rendered


@pytest.mark.asyncio
async def test_app_mounta_main_screen(isolated_profiles_dir: Path):
    """Sanidade: app sobe, main screen tem o Header, Footer e DataTable."""
    save_profile(_mk_profile("shooter"))
    save_profile(_mk_profile("driving"))

    async with HefestoApp().run_test(headless=True) as pilot:
        await pilot.pause()
        app = pilot.app
        assert isinstance(app.screen, MainScreen)
        # Header existe
        assert any(
            type(w).__name__ == "Header" for w in app.screen.walk_children()
        )
        # Footer existe
        assert any(
            type(w).__name__ == "Footer" for w in app.screen.walk_children()
        )
        # DataTable com os perfis
        from textual.widgets import DataTable

        tables = [w for w in app.screen.walk_children() if isinstance(w, DataTable)]
        assert len(tables) == 1
        # Aguarda refresh assincrono carregar
        await pilot.pause()
        await pilot.pause()


@pytest.mark.asyncio
async def test_app_quit_com_q(isolated_profiles_dir: Path):
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    async with HefestoApp().run_test(headless=True) as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        # Após q, app deve estar saindo
        assert pilot.app._exit is not False or not pilot.app.is_running
