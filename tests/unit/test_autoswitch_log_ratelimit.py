"""FEAT-POINT-AND-CLICK-01 — rate-limit dos logs de supressão do autoswitch.

O tick de 0,5s repetia `autoswitch_suppressed_by_manual_override` enquanto o
override durasse (~1074 linhas em 2h no journal). Agora loga 1x por
(motivo, candidato); re-loga quando o candidato ou o motivo muda, ou quando a
supressão termina e um novo episódio começa. Estado por instância do
AutoSwitcher (nada global).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import autoswitch as autoswitch_mod
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher


@pytest.fixture
def log_spy(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    spy = MagicMock()
    monkeypatch.setattr(autoswitch_mod, "logger", spy)
    return spy


def _eventos(log_spy: MagicMock, evento: str) -> list:
    return [c for c in log_spy.info.call_args_list if c[0][0] == evento]


def _switcher(store: StateStore) -> AutoSwitcher:
    return AutoSwitcher(manager=MagicMock(), window_reader=lambda: {}, store=store)


def test_mesmo_candidato_loga_uma_vez(log_spy: MagicMock) -> None:
    store = StateStore()
    store.mark_manual_trigger_active()
    sw = _switcher(store)
    for _ in range(5):  # 5 ticks de poll suprimidos
        sw._activate("jogo", {"wm_class": "Doom"})
    assert len(_eventos(log_spy, "autoswitch_suppressed_by_manual_override")) == 1


def test_candidato_novo_reloga(log_spy: MagicMock) -> None:
    store = StateStore()
    store.mark_manual_trigger_active()
    sw = _switcher(store)
    sw._activate("jogo", {"wm_class": "Doom"})
    sw._activate("jogo", {"wm_class": "Doom"})
    sw._activate("navegacao", {"wm_class": "firefox"})
    eventos = _eventos(log_spy, "autoswitch_suppressed_by_manual_override")
    assert len(eventos) == 2
    assert eventos[0].kwargs["candidate"] == "jogo"
    assert eventos[1].kwargs["candidate"] == "navegacao"


def test_motivo_diferente_reloga(log_spy: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Override de trigger → lock de perfil: motivos distintos, 1 log cada."""
    store = StateStore()
    store.mark_manual_trigger_active()
    sw = _switcher(store)
    sw._activate("jogo", {"wm_class": "Doom"})
    # Troca o motivo: limpa o trigger, arma o lock de perfil manual.
    store.clear_manual_trigger_active()
    store.mark_manual_profile_lock(until=10_000.0)
    monkeypatch.setattr(autoswitch_mod.time, "monotonic", lambda: 0.0)
    sw._activate("jogo", {"wm_class": "Doom"})
    sw._activate("jogo", {"wm_class": "Doom"})
    assert len(_eventos(log_spy, "autoswitch_suppressed_by_manual_override")) == 1
    assert (
        len(_eventos(log_spy, "autoswitch_suppressed_by_manual_profile_lock")) == 1
    )


def test_fim_da_supressao_reabre_o_log(log_spy: MagicMock) -> None:
    """Episódio novo (mesmo candidato) volta a logar após a supressão acabar."""
    store = StateStore()
    store.mark_manual_trigger_active()
    sw = _switcher(store)
    sw._activate("jogo", {"wm_class": "Doom"})
    sw._activate("jogo", {"wm_class": "Doom"})

    # Supressão termina: _activate roda sem override e zera a chave.
    store.clear_manual_trigger_active()
    sw._activate("jogo", {"wm_class": "Doom"})

    # Novo episódio de supressão, mesmo candidato → loga de novo.
    store.mark_manual_trigger_active()
    sw._activate("jogo", {"wm_class": "Doom"})
    assert len(_eventos(log_spy, "autoswitch_suppressed_by_manual_override")) == 2


def test_estado_por_instancia_nao_global(log_spy: MagicMock) -> None:
    """Dois switchers não compartilham a deduplicação."""
    store = StateStore()
    store.mark_manual_trigger_active()
    sw1 = _switcher(store)
    sw2 = _switcher(store)
    sw1._activate("jogo", {"wm_class": "Doom"})
    sw2._activate("jogo", {"wm_class": "Doom"})
    assert len(_eventos(log_spy, "autoswitch_suppressed_by_manual_override")) == 2


async def test_run_reabre_log_com_candidato_estavel_igual_ao_corrente(
    log_spy: MagicMock,
) -> None:
    """BUG-AUTOSWITCH-LOG-KEY-STUCK-01 (via run() REAL): quando o episódio de
    supressão termina com o candidato estável == perfil corrente (volta ao jogo),
    `_activate` NÃO roda — mas o run-loop reabre a chave, então o próximo episódio
    de supressão volta a logar. Sem o fix (reset só em `_activate`), ficava preso
    em 1 log. Roteiro coordena janela + trigger manual; manager mock (sem disco)."""
    store = StateStore()
    jogo = SimpleNamespace(name="jogo")
    fallback = SimpleNamespace(name="fallback")

    # (window_class, trigger_manual_ativo)
    script = [
        ("Doom", False),      # ativa jogo (current=jogo)
        ("firefox", True),    # alt-tab p/ desktop + trigger → fallback suprimido → log 1
        ("Doom", False),      # volta ao jogo (candidato==current) + reset → run-loop zera a chave
        ("firefox", True),    # alt-tab + trigger de novo → fallback suprimido → log 2
    ]
    step = {"i": 0}

    def reader() -> dict:
        i = min(step["i"], len(script) - 1)
        window, trig = script[i]
        if trig:
            store.mark_manual_trigger_active()
        else:
            store.clear_manual_trigger_active()
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
    await asyncio.sleep(0.1)  # ~20 ticks >> 4 passos; dedup impede logs extras
    sw.stop()
    await sw._task  # type: ignore[union-attr]

    assert len(_eventos(log_spy, "autoswitch_suppressed_by_manual_override")) == 2
