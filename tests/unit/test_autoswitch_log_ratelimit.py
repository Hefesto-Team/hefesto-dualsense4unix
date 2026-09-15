"""FEAT-POINT-AND-CLICK-01 — rate-limit dos logs de supressão do autoswitch.

O tick de 0,5s repetia `autoswitch_suppressed_by_manual_override` enquanto o
override durasse (~1074 linhas em 2h no journal). Agora loga 1x por
(motivo, candidato); re-loga quando o candidato ou o motivo muda, ou quando a
supressão termina e um novo episódio começa. Estado por instância do
AutoSwitcher (nada global).

O VEÍCULO MUDOU EM 14/09/2026, e o que este arquivo mede não. Ele produzia a
supressão com `store.mark_manual_trigger_active()` — a trava manual por
categoria —, e ela saiu inteira por decisão dela
(`D-1409-A-TRAVA-MANUAL-SAI-O-PERFIL-APLICA-TUDO`; a razão está em
`tests/unit/test_a_trava_que_ninguem_solta_01.py`). O rate-limit é sobre o LOG,
não sobre qual motivo suprime: o motivo que restou é o lock de perfil manual
(`MANUAL_PROFILE_LOCK_SEC`, 30 s), e é com ele que os testes abaixo produzem
episódio de supressão.

O QUE SE PERDEU, e está dito em vez de escondido: `test_motivo_diferente_reloga`
provava que a chave de dedup inclui o MOTIVO — ela trocava trava por lock e
cobrava um log de cada. Com um motivo só, não há segundo motivo para trocar, e um
teste que fingisse dois estaria medindo um produto que não existe. A metade do
contrato que sobrevive — *re-loga quando o CANDIDATO muda* — continua coberta por
`test_candidato_novo_reloga`.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import autoswitch as autoswitch_mod
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher

#: O evento que o lock de perfil manual emite ao suprimir. Era
#: `autoswitch_suppressed_by_manual_override` (o da trava) até 14/09/2026.
EVENTO = "autoswitch_suppressed_by_manual_profile_lock"

#: Um instante futuro qualquer para o lock: os testes congelam o relógio em 0,0,
#: então qualquer valor positivo mantém o lock de pé pela corrida inteira.
LOCK_DE_PE = 10_000.0


@pytest.fixture
def log_spy(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    spy = MagicMock()
    monkeypatch.setattr(autoswitch_mod, "logger", spy)
    return spy


@pytest.fixture
def relogio_parado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Congela o `monotonic` que o gate do lock consulta.

    Sem ele o lock venceria (ou não) conforme o relógio da máquina, e um teste de
    DEDUP DE LOG mediria o relógio junto — que é a diferença entre uma régua e
    uma régua intermitente.
    """
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
    for _ in range(5):  # 5 ticks de poll suprimidos
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

    # Supressão termina: `_activate` roda sem lock e zera a chave.
    store.mark_manual_profile_lock(until=0.0)
    sw._activate("jogo", {"wm_class": "Doom"})

    # Novo episódio de supressão, mesmo candidato → loga de novo.
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
    """BUG-AUTOSWITCH-LOG-KEY-STUCK-01 (via run() REAL): quando o episódio de
    supressão termina com o candidato estável == perfil corrente (volta ao jogo),
    `_activate` NÃO roda — mas o run-loop reabre a chave, então o próximo episódio
    de supressão volta a logar. Sem o fix (reset só em `_activate`), ficava preso
    em 1 log. Roteiro coordena janela + lock manual; manager mock (sem disco).

    ELE NÃO CONGELA O RELÓGIO, ao contrário dos irmãos acima, e é de propósito: o
    run-loop de verdade dorme entre tiques, e um `monotonic` parado faria o lock
    valer para sempre — o roteiro não conseguiria desligá-lo no passo 3. O lock é
    armado e desarmado pelo próprio roteiro, com `until` no futuro e no passado.
    """
    store = StateStore()
    jogo = SimpleNamespace(name="jogo")
    fallback = SimpleNamespace(name="fallback")

    # (window_class, lock_manual_armado)
    script = [
        ("Doom", False),      # ativa jogo (current=jogo)
        ("firefox", True),    # alt-tab p/ desktop + lock → fallback suprimido → log 1
        ("Doom", False),      # volta ao jogo (candidato==current) + reset → run-loop zera a chave
        ("firefox", True),    # alt-tab + lock de novo → fallback suprimido → log 2
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
    await asyncio.sleep(0.1)  # ~20 ticks >> 4 passos; dedup impede logs extras
    sw.stop()
    await sw._task  # type: ignore[union-attr]

    assert len(_eventos(log_spy)) == 2
