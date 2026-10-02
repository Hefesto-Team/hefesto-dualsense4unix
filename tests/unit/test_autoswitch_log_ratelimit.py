"""FEAT-POINT-AND-CLICK-01 — rate-limit dos logs de supressão do autoswitch."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import autoswitch as autoswitch_mod
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher

EVENTO = "autoswitch_suppressed_by_manual_profile_lock"

LOCK_DE_PE = 10_000.0


@pytest.fixture
def log_spy(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    spy = MagicMock()
    monkeypatch.setattr(autoswitch_mod, "logger", spy)
    return spy


@pytest.fixture
def relogio_parado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Congela o `monotonic` que o gate do lock consulta."""
    monkeypatch.setattr(autoswitch_mod.time, "monotonic", lambda: 0.0)


def _eventos(log_spy: MagicMock, evento: str = EVENTO) -> list:
    return [c for c in log_spy.info.call_args_list if c[0][0] == evento]


def _store_suprimindo() -> StateStore:
    store = StateStore()
    store.mark_manual_profile_lock(until=LOCK_DE_PE)
    return store


def _switcher(store: StateStore) -> AutoSwitcher:
    return AutoSwitcher(manager=MagicMock(), window_reader=lambda: {}, store=store)


def test_mesmo_candidato_loga_uma_vez(log_spy: MagicMock, relogio_parado: None) -> None:
    sw = _switcher(_store_suprimindo())
    for _ in range(5):
        sw._activate("jogo", {"wm_class": "Doom"})
    assert len(_eventos(log_spy)) == 1


def test_candidato_novo_reloga(log_spy: MagicMock, relogio_parado: None) -> None:
    sw = _switcher(_store_suprimindo())
    sw._activate("jogo", {"wm_class": "Doom"})
    sw._activate("jogo", {"wm_class": "Doom"})
    sw._activate("navegacao", {"wm_class": "firefox"})
    eventos = _eventos(log_spy)
    assert len(eventos) == 2
    assert eventos[0].kwargs["candidate"] == "jogo"
    assert eventos[1].kwargs["candidate"] == "navegacao"


def test_fim_da_supressao_reabre_o_log(
    log_spy: MagicMock, relogio_parado: None
) -> None:
    """Episódio novo (mesmo candidato) volta a logar após a supressão acabar."""
    store = _store_suprimindo()
    sw = _switcher(store)
    sw._activate("jogo", {"wm_class": "Doom"})
    sw._activate("jogo", {"wm_class": "Doom"})

    store.mark_manual_profile_lock(until=0.0)
    sw._activate("jogo", {"wm_class": "Doom"})

    store.mark_manual_profile_lock(until=LOCK_DE_PE)
    sw._activate("jogo", {"wm_class": "Doom"})
    assert len(_eventos(log_spy)) == 2


def test_estado_por_instancia_nao_global(
    log_spy: MagicMock, relogio_parado: None
) -> None:
    """Dois switchers não compartilham a deduplicação."""
    store = _store_suprimindo()
    sw1 = _switcher(store)
    sw2 = _switcher(store)
    sw1._activate("jogo", {"wm_class": "Doom"})
    sw2._activate("jogo", {"wm_class": "Doom"})
    assert len(_eventos(log_spy)) == 2


async def test_run_reabre_log_com_candidato_estavel_igual_ao_corrente(
    log_spy: MagicMock,
) -> None:
    """BUG-AUTOSWITCH-LOG-KEY-STUCK-01 (via run() REAL): quando o episódio de"""
    store = StateStore()
    jogo = SimpleNamespace(name="jogo")
    fallback = SimpleNamespace(name="fallback")

    script = [
        ("Doom", False),
        ("firefox", True),
        ("Doom", False),
        ("firefox", True),
    ]
    step = {"i": 0}

    def reader() -> dict:
        import time as _t

        i = min(step["i"], len(script) - 1)
        window, travado = script[i]
        store.mark_manual_profile_lock(
            until=(_t.monotonic() + 60.0) if travado else 0.0
        )
        step["i"] += 1
        return {"wm_class": window}

    manager = MagicMock()
    manager.select_for_window.side_effect = lambda info: (
        jogo if info.get("wm_class") == "Doom" else fallback
    )
    sw = AutoSwitcher(
        manager=manager,
        window_reader=reader,
        store=store,
        poll_interval_sec=0.005,
        debounce_sec=0.0,
    )
    sw.start()
    await asyncio.sleep(0.1)
    sw.stop()
    await sw._task  # type: ignore[union-attr]

    assert len(_eventos(log_spy)) == 2
