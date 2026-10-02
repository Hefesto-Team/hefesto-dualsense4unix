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
from hefesto_dualsense4unix.utils import session as _session


def _a_escolha_dela(nome: str) -> None:
    """O último perfil que ela ativou à mão, no `session.json` do lar isolado."""
    _session.save_last_profile(nome)


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
    await switcher.run()
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
        debounce_sec=0.2,
    )
    switcher.start()
    await asyncio.sleep(0.3)
    switcher.stop()
    await switcher._task  # type: ignore[union-attr]

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
    await switcher._task  # type: ignore[union-attr]


def _mk_switcher(
    manager: ProfileManager, *, debounce_sec: float = 0.5
) -> AutoSwitcher:
    return AutoSwitcher(
        manager=manager, window_reader=lambda: {}, debounce_sec=debounce_sec
    )


def test_cenario_medido_sackboy_nativo_unknown_nao_cai_para_vitoria(
    isolated_profiles_dir: Path,
):
    """O episódio do journal 2026-07-16 13:07:18 vira teste: perfil de jogo"""
    save_profile(
        _mk_profile(
            "sackboy_nativo",
            match=MatchCriteria(window_class=["steam_app_1599660"]),
        )
    )
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
    _a_escolha_dela("vitoria")

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    sw._tick({"wm_class": "steam_app_1599660"}, 0.0)
    sw._tick({"wm_class": "steam_app_1599660"}, 0.6)
    assert sw._current_profile == "sackboy_nativo"

    for t in (1.0, 1.5, 6.1, 60.0, 300.0):
        sw._tick({"wm_class": "unknown", "wm_name": ""}, t)

    assert sw._current_profile == "sackboy_nativo"
    assert manager.store.counter("profile.activated") == 1


def test_matchany_nunca_ativado_por_leitura_vazia_ou_unknown(
    isolated_profiles_dir: Path,
):
    """Critério 2: com perfil MatchAny salvo, reads `{}` ou unknown NUNCA o"""
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
    _a_escolha_dela("vitoria")

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
    """Critério 5: fresh-install em desktop Wayland puro (backend cego desde o"""
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
    """Critério 3: wm_class 'unknown' mas exe_basename preenchido é evidência"""
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
    """Tradeoff residual aceito (armadilha 3 da UX-01, coberto de propósito):"""
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
    _a_escolha_dela("vitoria")

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
    """Critério 4 (armadilha 1): o debounce é wall-time. Glitch útil → gap"""
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    sw._tick({"wm_class": "Doom"}, 0.0)
    for t in (0.4, 1.0, 100.0, 399.5):
        sw._tick({"wm_class": "unknown"}, t)

    sw._tick({"wm_class": "Doom"}, 400.0)
    assert sw._current_profile is None

    sw._tick({"wm_class": "Doom"}, 400.6)
    assert sw._current_profile == "shooter"


def test_skip_nao_pula_reset_da_suppress_log_key(isolated_profiles_dir: Path):
    """Armadilha 2 da UX-01 (regressão do BUG-AUTOSWITCH-LOG-KEY-STUCK-01):"""
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    sw._suppress_log_key = ("autoswitch_suppressed_by_manual_override", "jogo")
    sw._tick({"wm_class": "unknown"}, 0.0)
    assert sw._suppress_log_key is None


def test_log_info_unavailable_uma_vez_por_episodio(
    isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """Critério 6: journal sem flood — `autoswitch_window_info_unavailable` sai"""
    from unittest.mock import MagicMock

    from hefesto_dualsense4unix.profiles import autoswitch as autoswitch_mod

    spy = MagicMock()
    monkeypatch.setattr(autoswitch_mod, "logger", spy)

    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    for t in (0.0, 0.5, 1.0):
        sw._tick({"wm_class": "unknown"}, t)
    sw._tick({"wm_class": "Doom"}, 1.5)
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
    """Critério 1 pelo run() REAL: Doom estável → N ticks unknown → mantém"""
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
    _a_escolha_dela("vitoria")

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


def test_autoswitch_ativa_sem_gravar_last_profile_manual(
    isolated_profiles_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """PERFIL-03: a troca automática ativa o perfil (aplica + marca ativo) mas"""
    config = tmp_path / "config"
    config.mkdir()

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            config.mkdir(parents=True, exist_ok=True)
        return config

    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.config_dir", fake_config_dir
    )
    from hefesto_dualsense4unix.utils import xdg_paths

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)

    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    sw._tick({"wm_class": "Doom"}, 0.0)
    sw._tick({"wm_class": "Doom"}, 0.6)

    assert sw._current_profile == "shooter"
    assert manager.store.active_profile == "shooter"
    from hefesto_dualsense4unix.utils.session import (
        load_last_profile,
        read_active_marker,
    )

    assert load_last_profile() is None
    assert read_active_marker() is None


def test_gui_propria_em_foco_nao_flipa_perfil(isolated_profiles_dir: Path):
    """Cenário do journal: sackboy_nativo ativo + foco na própria GUI"""
    save_profile(
        _mk_profile(
            "sackboy_nativo",
            match=MatchCriteria(window_class=["steam_app_1599660"]),
        )
    )
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
    _a_escolha_dela("vitoria")

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    sw._tick({"wm_class": "steam_app_1599660"}, 0.0)
    sw._tick({"wm_class": "steam_app_1599660"}, 0.6)
    assert sw._current_profile == "sackboy_nativo"

    for t, wm in (
        (1.0, "Main.py"),
        (1.5, "Hefesto-Dualsense4Unix"),
        (30.0, "hefesto-dualsense4unix"),
        (60.0, "hefesto-dualsense4unix-gui"),
        (120.0, "com.vitoriamaria.HefestoDualsense4Unix"),
    ):
        sw._tick({"wm_class": wm, "wm_name": "Hefesto DualSense4Unix"}, t)

    assert sw._current_profile == "sackboy_nativo"
    assert manager.store.counter("profile.activated") == 1


def test_gui_propria_nunca_ativa_fallback_sem_perfil_corrente(
    isolated_profiles_dir: Path,
):
    """Sem perfil corrente, encarar a GUI por minutos não ativa o MatchAny —"""
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
    _a_escolha_dela("vitoria")

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    for t in range(10):
        sw._tick(
            {"wm_class": "Main.py", "wm_name": "Hefesto DualSense4Unix"},
            float(t) * 30.0,
        )

    assert sw._current_profile is None
    assert manager.store.counter("profile.activated") == 0


def test_pos_gui_debounce_reinicia(isolated_profiles_dir: Path):
    """Voltar da GUI reinicia o relógio do debounce (armadilha 1 da UX-01):"""
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    sw._tick({"wm_class": "Doom"}, 0.0)
    for t in (0.4, 10.0, 100.0):
        sw._tick({"wm_class": "Main.py"}, t)

    sw._tick({"wm_class": "Doom"}, 100.5)
    assert sw._current_profile is None

    sw._tick({"wm_class": "Doom"}, 101.1)
    assert sw._current_profile == "shooter"


def test_log_janela_propria_uma_vez_por_episodio(
    isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """Journal sem flood: `autoswitch_janela_propria_ignorada` sai 1x por"""
    from unittest.mock import MagicMock

    from hefesto_dualsense4unix.profiles import autoswitch as autoswitch_mod

    spy = MagicMock()
    monkeypatch.setattr(autoswitch_mod, "logger", spy)

    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _mk_switcher(manager)

    for t in (0.0, 0.5, 1.0):
        sw._tick({"wm_class": "Main.py"}, t)
    sw._tick({"wm_class": "Doom"}, 1.5)
    for t in (2.0, 2.5):
        sw._tick({"wm_class": "Hefesto-Dualsense4Unix"}, t)

    eventos = [
        c
        for c in spy.info.call_args_list
        if c[0][0] == "autoswitch_janela_propria_ignorada"
    ]
    assert len(eventos) == 2


def test_janela_propria_matcher():
    """Matcher unitário: wm_class nossos (case-insensitive, com espaços) são"""
    proprias = [
        "Main.py",
        "main.py",
        "Hefesto-Dualsense4Unix",
        "hefesto-dualsense4unix",
        "  hefesto-dualsense4unix-gui ",
        "com.vitoriamaria.HefestoDualsense4Unix",
    ]
    for wm in proprias:
        assert AutoSwitcher._janela_propria({"wm_class": wm}), wm

    alheias = [
        {"wm_class": "steam_app_1599660"},
        {"wm_class": "Doom"},
        {"wm_class": "unknown"},
        {"wm_class": ""},
        {},
    ]
    for info in alheias:
        assert not AutoSwitcher._janela_propria(info), info


def _sw_assimetrico(manager: ProfileManager) -> AutoSwitcher:
    return AutoSwitcher(
        manager=manager,
        window_reader=lambda: {},
        debounce_sec=0.5,
        debounce_saida_sec=12.0,
    )


def test_entrar_no_perfil_do_jogo_continua_rapido(isolated_profiles_dir: Path):
    save_profile(
        _mk_profile(
            "madjack", match=MatchCriteria(window_class=["steam_app_2111190"])
        )
    )
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
    _a_escolha_dela("vitoria")

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _sw_assimetrico(manager)

    sw._tick({"wm_class": "firefox"}, 0.0)
    sw._tick({"wm_class": "firefox"}, 0.6)
    assert sw._current_profile == "vitoria"

    sw._tick({"wm_class": "steam_app_2111190"}, 1.0)
    sw._tick({"wm_class": "steam_app_2111190"}, 1.6)
    assert sw._current_profile == "madjack"


def test_sair_do_perfil_de_jogo_para_a_escolha_exige_o_debounce_longo(
    isolated_profiles_dir: Path,
):
    """O cenário exato do journal: alt-tab do jogo para uma janela que regra"""
    save_profile(
        _mk_profile(
            "madjack", match=MatchCriteria(window_class=["steam_app_2111190"])
        )
    )
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
    _a_escolha_dela("vitoria")

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _sw_assimetrico(manager)

    sw._tick({"wm_class": "steam_app_2111190"}, 0.0)
    sw._tick({"wm_class": "steam_app_2111190"}, 0.6)
    assert sw._current_profile == "madjack"

    for t in (10.0, 10.5, 11.0, 11.4):
        sw._tick({"wm_class": "firefox"}, t)
    assert sw._current_profile == "madjack"

    sw._tick({"wm_class": "firefox"}, 22.1)
    assert sw._current_profile == "vitoria"


def test_alt_tab_curto_no_meio_do_jogo_nao_flipa(isolated_profiles_dir: Path):
    """Ping-pong de 18-28 s do journal, reproduzido: com o debounce de saída,"""
    save_profile(
        _mk_profile(
            "madjack", match=MatchCriteria(window_class=["steam_app_2111190"])
        )
    )
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
    _a_escolha_dela("vitoria")

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _sw_assimetrico(manager)

    sw._tick({"wm_class": "steam_app_2111190"}, 0.0)
    sw._tick({"wm_class": "steam_app_2111190"}, 0.6)

    t = 1.0
    for _ in range(6):
        for _ in range(4):
            sw._tick({"wm_class": "firefox"}, t)
            t += 0.5
        for _ in range(4):
            sw._tick({"wm_class": "steam_app_2111190"}, t)
            t += 0.5

    assert sw._current_profile == "madjack"
    assert manager.store.counter("profile.activated") == 1


def test_troca_entre_dois_perfis_especificos_segue_no_debounce_curto(
    isolated_profiles_dir: Path,
):
    """A assimetria é só para a VOLTA ao genérico — trocar de um jogo para"""
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))
    save_profile(_mk_profile("driving", match=MatchCriteria(window_class=["Forza"])))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _sw_assimetrico(manager)

    sw._tick({"wm_class": "Doom"}, 0.0)
    sw._tick({"wm_class": "Doom"}, 0.6)
    assert sw._current_profile == "shooter"

    sw._tick({"wm_class": "Forza"}, 1.0)
    sw._tick({"wm_class": "Forza"}, 1.6)
    assert sw._current_profile == "driving"


def test_saida_de_catch_all_para_catch_all_nao_paga_o_debounce_longo(
    isolated_profiles_dir: Path,
):
    """Só perfil ESPECÍFICO arma o lado lento: quem já está no genérico não tem"""
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
    _a_escolha_dela("vitoria")
    save_profile(
        _mk_profile("leitura", priority=50, match=MatchCriteria(window_class=["zathura"]))
    )

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    sw = _sw_assimetrico(manager)

    sw._tick({"wm_class": "firefox"}, 0.0)
    sw._tick({"wm_class": "firefox"}, 0.6)
    assert sw._current_profile == "vitoria"
    assert sw._current_especifico is False

    sw._tick({"wm_class": "zathura"}, 1.0)
    sw._tick({"wm_class": "zathura"}, 1.6)
    assert sw._current_profile == "leitura"
    assert sw._current_especifico is True
