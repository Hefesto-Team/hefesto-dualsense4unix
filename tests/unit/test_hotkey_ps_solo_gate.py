"""M5 (auditoria + review) — o gate do PS-solo suprime a ação de sistema quando o
controle está DEDICADO a um jogo (Modo Nativo ou modo jogo/_emulation_suppressed),
mas NÃO no desktop.

O gate usa flags EM MEMÓRIA (sem subprocess): o `is_steam_running`/pgrep anterior
bloqueava o poll loop até 2s (REVIEW-M5-PGREP-BLOCK-01) e deixava passar jogos
não-Steam (REVIEW-M5-NONSTEAM-FOCUS-01).
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import steam_launcher


def _daemon(*, suppressed: bool = False, native: bool = False, action: str = "steam") -> Any:
    return SimpleNamespace(
        config=SimpleNamespace(ps_button_action=action, ps_button_command=""),
        _emulation_suppressed=suppressed,
        store=SimpleNamespace(native_mode_active=native),
    )


def _patch_steam(monkeypatch) -> list[Any]:
    opened: list[Any] = []
    monkeypatch.setattr(
        steam_launcher, "open_or_focus_steam", lambda: opened.append(True) or True
    )
    # Guard-rail do review: o gate NÃO pode chamar subprocess (pgrep) no poll loop.
    def _boom(*_a, **_kw):  # pragma: no cover
        raise AssertionError("gate do PS-solo não pode rodar subprocess/pgrep")

    monkeypatch.setattr(steam_launcher, "_default_pgrep", _boom)
    return opened


def test_ps_solo_abre_steam_no_desktop(monkeypatch):
    """Sem modo jogo e sem nativo → a ação roda (abre a Steam)."""
    opened = _patch_steam(monkeypatch)
    hotkey.build_ps_solo_callback(_daemon())()
    assert opened == [True]


def test_ps_solo_suprimido_em_modo_jogo(monkeypatch):
    """Emulação suprimida (modo jogo — inclui jogos NÃO-Steam) → suprime."""
    opened = _patch_steam(monkeypatch)
    hotkey.build_ps_solo_callback(_daemon(suppressed=True))()
    assert opened == []


def test_ps_solo_suprimido_no_modo_nativo(monkeypatch):
    opened = _patch_steam(monkeypatch)
    hotkey.build_ps_solo_callback(_daemon(native=True))()
    assert opened == []


def test_ps_solo_none_nao_faz_nada(monkeypatch):
    opened = _patch_steam(monkeypatch)
    hotkey.build_ps_solo_callback(_daemon(action="none"))()
    assert opened == []
