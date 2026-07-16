"""Testes do AutoSwitcher."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
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


def _mk_profile(name: str, **kw) -> Profile:
    defaults = {
        "match": MatchCriteria(window_class=[f"{name}_class"]),
        "priority": 10,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Rigid", params=[0, 100]),
        ),
        "leds": LedsConfig(lightbar=(10, 20, 30)),
    }
    defaults.update(kw)
    return Profile(name=name, **defaults)


@pytest.mark.asyncio
async def test_disabled_via_env(monkeypatch: pytest.MonkeyPatch, isolated_profiles_dir: Path):
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT", "1")
    save_profile(_mk_profile("shooter"))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)

    reads: list[dict] = []
    switcher = AutoSwitcher(
        manager=manager, window_reader=lambda: reads.append({}) or {}
    )
    assert switcher.disabled() is True
    await switcher.run()  # deve sair imediatamente sem erro
    assert reads == []


@pytest.mark.asyncio
async def test_aplica_apos_debounce(isolated_profiles_dir: Path):
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)

    sequence = [
        {"wm_class": "Inkscape"},
        {"wm_class": "Doom"},
        {"wm_class": "Doom"},
        {"wm_class": "Doom"},
        {"wm_class": "Doom"},
        {"wm_class": "Doom"},
    ]
    idx = {"i": 0}

    def reader() -> dict:
        i = idx["i"]
        idx["i"] = min(i + 1, len(sequence) - 1)
        return sequence[i]

    switcher = AutoSwitcher(
        manager=manager,
        window_reader=reader,
        poll_interval_sec=0.02,
        debounce_sec=0.05,
    )
    switcher.start()
    await asyncio.sleep(0.25)
    switcher.stop()
    await switcher._task  # type: ignore[union-attr]

    assert switcher._current_profile == "shooter"
    # Também marcou no store via manager
    assert manager.store.active_profile == "shooter"


@pytest.mark.asyncio
async def test_nao_reaplica_mesmo_perfil(isolated_profiles_dir: Path):
    save_profile(_mk_profile("driving", match=MatchCriteria(window_class=["Forza"])))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)

    def reader() -> dict:
        return {"wm_class": "Forza"}

    switcher = AutoSwitcher(
        manager=manager,
        window_reader=reader,
        poll_interval_sec=0.02,
        debounce_sec=0.02,
    )
    switcher.start()
    await asyncio.sleep(0.2)
    switcher.stop()
    await switcher._task  # type: ignore[union-attr]

    # Manager.activate foi chamado só 1x → bump de contador igual a 1
    assert manager.store.counter("profile.activated") == 1


@pytest.mark.asyncio
async def test_flicker_alt_tab_suprimido(isolated_profiles_dir: Path):
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))
    save_profile(_mk_profile("driving", match=MatchCriteria(window_class=["Forza"])))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)

    alternating = [
        {"wm_class": "Doom"},
        {"wm_class": "Forza"},
        {"wm_class": "Doom"},
        {"wm_class": "Forza"},
    ]
    idx = {"i": 0}

    def reader() -> dict:
        v = alternating[idx["i"] % len(alternating)]
        idx["i"] += 1
        return v

    switcher = AutoSwitcher(
        manager=manager,
        window_reader=reader,
        poll_interval_sec=0.02,
        debounce_sec=0.2,  # debounce maior que o alt-tab
    )
    switcher.start()
    await asyncio.sleep(0.3)
    switcher.stop()
    await switcher._task  # type: ignore[union-attr]

    # Nenhum dos dois se estabilizou por 200ms -> nenhum ativo.
    assert switcher._current_profile is None


@pytest.mark.asyncio
async def test_erro_no_window_reader_nao_derruba(isolated_profiles_dir: Path):
    save_profile(_mk_profile("x"))
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)

    def reader() -> dict:
        raise RuntimeError("xlib broke")

    switcher = AutoSwitcher(
        manager=manager,
        window_reader=reader,
        poll_interval_sec=0.02,
        debounce_sec=0.02,
    )
    switcher.start()
    await asyncio.sleep(0.1)
    switcher.stop()
    # Terminou limpo, sem exception propagada
    await switcher._task  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# UX-01 (SPRINT-UX-AUTOSWITCH-01) — histerese: leitura sem informação não
# troca perfil. Os testes dirigem `_tick(info, now)` com relógio controlado
# porque o debounce é wall-time (o buraco-do-debounce só é testável assim).
# ---------------------------------------------------------------------------


def _mk_switcher(
    manager: ProfileManager, *, debounce_sec: float = 0.5
) -> AutoSwitcher:
    return AutoSwitcher(
        manager=manager, window_reader=lambda: {}, debounce_sec=debounce_sec
    )


def test_cenario_medido_sackboy_nativo_unknown_nao_cai_para_vitoria(
    isolated_profiles_dir: Path,
):
    """O episódio do journal 2026-07-16 13:07:18 vira teste: perfil de jogo
    ativo + leituras `wm_class=unknown wm_name=` (backend cego no COSMIC) NÃO
    caem para o fallback MatchAny `vitoria` — o perfil corrente fica retido."""
    save_profile(
        _mk_profile(
            "sackboy_nativo",
            match=MatchCriteria(window_class=["steam_app_1599660"]),
        )
    )
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    sw._tick({"wm_class": "steam_app_1599660"}, 0.0)
    sw._tick({"wm_class": "steam_app_1599660"}, 0.6)
    assert sw._current_profile == "sackboy_nativo"

    # O glitch medido ao vivo: minutos de unknown/vazio no meio do jogo.
    for t in (1.0, 1.5, 6.1, 60.0, 300.0):
        sw._tick({"wm_class": "unknown", "wm_name": ""}, t)

    assert sw._current_profile == "sackboy_nativo"
    assert manager.store.counter("profile.activated") == 1


def test_matchany_nunca_ativado_por_leitura_vazia_ou_unknown(
    isolated_profiles_dir: Path,
):
    """Critério 2: com perfil MatchAny salvo, reads `{}` ou unknown NUNCA o
    ativam — por mais estáveis que fiquem (sem TTL, por design)."""
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    leituras_cegas: list[dict] = [
        {},
        {"wm_class": "unknown"},
        {"wm_class": ""},
        {"wm_class": "unknown", "wm_name": "", "exe_basename": ""},
    ]
    for i, info in enumerate(leituras_cegas * 5):
        sw._tick(info, float(i))

    assert sw._current_profile is None
    assert manager.store.counter("profile.activated") == 0


def test_fresh_install_desktop_wayland_puro_nao_ativa_matchany(
    isolated_profiles_dir: Path,
):
    """Critério 5: fresh-install em desktop Wayland puro (backend cego desde o
    primeiro tick, sem last_profile salvo) — o MatchAny não ativa sozinho via
    unknown. Intencional: o boot é coberto pelo restore_last_profile
    (FEAT-PERSIST-SESSION-01), não pelo autoswitch."""
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    for t in range(20):
        sw._tick(
            {"wm_class": "unknown", "wm_name": "", "pid": 0, "exe_basename": ""},
            float(t),
        )

    assert sw._current_profile is None
    assert manager.store.counter("profile.activated") == 0


def test_unknown_com_exe_basename_ainda_entra_no_select(
    isolated_profiles_dir: Path,
):
    """Critério 3: wm_class 'unknown' mas exe_basename preenchido é evidência
    positiva — preserva perfis por process_name."""
    save_profile(
        _mk_profile("shooter", match=MatchCriteria(process_name=["doom-bin"]))
    )

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    sw._tick({"wm_class": "unknown", "exe_basename": "doom-bin"}, 0.0)
    sw._tick({"wm_class": "unknown", "exe_basename": "doom-bin"}, 0.6)

    assert sw._current_profile == "shooter"


def test_unknown_com_titulo_ativa_fallback_apos_debounce(
    isolated_profiles_dir: Path,
):
    """Tradeoff residual aceito (armadilha 3 da UX-01, coberto de propósito):
    janela X sem WM_CLASS mas com TÍTULO ainda entra no select e ativa o
    fallback MatchAny depois do debounce."""
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    sw._tick({"wm_class": "unknown", "wm_name": "Splash sem classe"}, 0.0)
    sw._tick({"wm_class": "unknown", "wm_name": "Splash sem classe"}, 0.6)

    assert sw._current_profile == "vitoria"


def test_buraco_do_debounce_glitch_apos_gap_nao_ativa_na_hora(
    isolated_profiles_dir: Path,
):
    """Critério 4 (armadilha 1): o debounce é wall-time. Glitch útil → gap
    longo de skips → glitch útil idêntico NÃO ativa na hora: a primeira
    leitura útil pós-gap reinicia o relógio do debounce (o tempo pulado não
    conta como estabilidade)."""
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    sw._tick({"wm_class": "Doom"}, 0.0)  # glitch útil (1 tick só)
    for t in (0.4, 1.0, 100.0, 399.5):  # gap longo sem informação
        sw._tick({"wm_class": "unknown"}, t)

    sw._tick({"wm_class": "Doom"}, 400.0)  # glitch idêntico pós-gap
    assert sw._current_profile is None  # NÃO ativou na hora

    sw._tick({"wm_class": "Doom"}, 400.6)  # estabilidade REAL >= debounce
    assert sw._current_profile == "shooter"


def test_skip_nao_pula_reset_da_suppress_log_key(isolated_profiles_dir: Path):
    """Armadilha 2 da UX-01 (regressão do BUG-AUTOSWITCH-LOG-KEY-STUCK-01):
    o tick pulado AINDA reabre o log de supressão quando a supressão cessou."""
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)  # store=None → supressão nunca ativa

    sw._suppress_log_key = ("autoswitch_suppressed_by_manual_override", "jogo")
    sw._tick({"wm_class": "unknown"}, 0.0)
    assert sw._suppress_log_key is None


def test_log_info_unavailable_uma_vez_por_episodio(
    isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """Critério 6: journal sem flood — `autoswitch_window_info_unavailable` sai
    1x por episódio; leitura útil fecha o episódio e reabre o log."""
    from unittest.mock import MagicMock

    from hefesto_dualsense4unix.profiles import autoswitch as autoswitch_mod

    spy = MagicMock()
    monkeypatch.setattr(autoswitch_mod, "logger", spy)

    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    # Episódio 1: 3 skips → 1 log.
    for t in (0.0, 0.5, 1.0):
        sw._tick({"wm_class": "unknown"}, t)
    # Leitura útil encerra o episódio.
    sw._tick({"wm_class": "Doom"}, 1.5)
    # Episódio 2: 2 skips → mais 1 log.
    for t in (2.0, 2.5):
        sw._tick({}, t)

    eventos = [
        c
        for c in spy.info.call_args_list
        if c[0][0] == "autoswitch_window_info_unavailable"
    ]
    assert len(eventos) == 2


@pytest.mark.asyncio
async def test_histerese_no_run_loop_mantem_perfil(isolated_profiles_dir: Path):
    """Critério 1 pelo run() REAL: Doom estável → N ticks unknown → mantém
    shooter e counter('profile.activated') == 1 (o fallback MatchAny salvo
    nunca rouba o lugar)."""
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)

    sequence = [{"wm_class": "Doom"}] * 5 + [{"wm_class": "unknown", "wm_name": ""}]
    idx = {"i": 0}

    def reader() -> dict:
        i = idx["i"]
        idx["i"] = min(i + 1, len(sequence) - 1)
        return sequence[i]

    switcher = AutoSwitcher(
        manager=manager,
        window_reader=reader,
        poll_interval_sec=0.02,
        debounce_sec=0.05,
    )
    switcher.start()
    await asyncio.sleep(0.4)
    switcher.stop()
    await switcher._task  # type: ignore[union-attr]

    assert switcher._current_profile == "shooter"
    assert manager.store.counter("profile.activated") == 1
