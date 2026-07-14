"""M5 (auditoria) — o gate do PS-solo suprime a ação de sistema DURANTE o jogo
(vpad ativo E Steam rodando), mas NÃO no desktop com a Steam fechada.

Antes o gate pulava a ação pela MERA existência do vpad, matando o "abre a Steam"
no desktop (onde o BTN_MODE não tem quem receba).
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import steam_launcher


def _daemon(*, gamepad: bool, native: bool = False, action: str = "steam") -> Any:
    return SimpleNamespace(
        config=SimpleNamespace(ps_button_action=action, ps_button_command=""),
        _gamepad_device=object() if gamepad else None,
        store=SimpleNamespace(native_mode_active=native),
    )


def test_ps_solo_abre_steam_no_desktop_com_steam_fechada(monkeypatch):
    """vpad ativo, Steam FECHADA → a ação roda (abre a Steam)."""
    opened = []
    monkeypatch.setattr(steam_launcher, "is_steam_running", lambda: False)
    monkeypatch.setattr(
        steam_launcher, "open_or_focus_steam", lambda: opened.append(True) or True
    )
    cb = hotkey.build_ps_solo_callback(_daemon(gamepad=True))
    cb()
    assert opened == [True], "com a Steam fechada o PS-solo deve abrir a Steam"


def test_ps_solo_suprimido_em_jogo_com_steam_rodando(monkeypatch):
    """vpad ativo, Steam JÁ rodando (em jogo) → suprime (não rouba foco)."""
    opened = []
    monkeypatch.setattr(steam_launcher, "is_steam_running", lambda: True)
    monkeypatch.setattr(
        steam_launcher, "open_or_focus_steam", lambda: opened.append(True) or True
    )
    cb = hotkey.build_ps_solo_callback(_daemon(gamepad=True))
    cb()
    assert opened == [], "com a Steam rodando e vpad ativo, o PS-solo é suprimido"


def test_ps_solo_suprimido_no_modo_nativo(monkeypatch):
    opened = []
    monkeypatch.setattr(steam_launcher, "is_steam_running", lambda: False)
    monkeypatch.setattr(
        steam_launcher, "open_or_focus_steam", lambda: opened.append(True) or True
    )
    cb = hotkey.build_ps_solo_callback(_daemon(gamepad=False, native=True))
    cb()
    assert opened == [], "no Modo Nativo o controle é do jogo — PS-solo suprimido"


def test_ps_solo_sem_vpad_abre_steam(monkeypatch):
    """Sem vpad (desktop puro) → ação roda normalmente."""
    opened = []
    monkeypatch.setattr(steam_launcher, "is_steam_running", lambda: False)
    monkeypatch.setattr(
        steam_launcher, "open_or_focus_steam", lambda: opened.append(True) or True
    )
    cb = hotkey.build_ps_solo_callback(_daemon(gamepad=False))
    cb()
    assert opened == [True]
