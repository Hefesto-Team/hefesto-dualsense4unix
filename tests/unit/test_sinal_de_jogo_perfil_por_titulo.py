"""SINAL-DE-JOGO-01 — a evidência nº 2 do sinal de jogo volta a existir."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.game_signal import classify
from hefesto_dualsense4unix.testing import FakeController

TITULO_COOP = "Sackboy: A Big Adventure"
TITULO_FPS = "Cyberpunk 2077 (c) CD PROJEKT RED"
EXE_FPS = "Cyberpunk2077.exe"


def _daemon() -> Daemon:
    return Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )


def _sem_marcador(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Aponta o diretório do wrapper para um tmp VAZIO."""
    import hefesto_dualsense4unix.daemon.launch_env as le_mod

    monkeypatch.setattr(
        le_mod, "launch_env_dir", lambda ensure=False: tmp_path / "launch_env"
    )


def _perfis(monkeypatch: pytest.MonkeyPatch, perfis: list[Any]) -> None:
    from hefesto_dualsense4unix.profiles import manager as manager_module

    monkeypatch.setattr(manager_module, "load_all_profiles", lambda: list(perfis))


def _perfil_coop_local() -> Any:
    """O formato exato do `coop_local` dela: só título, `mode: gamepad`."""
    from hefesto_dualsense4unix.profiles.schema import (
        MatchCriteria,
        Profile,
        ProfileModeConfig,
    )

    return Profile(
        name="coop_local",
        priority=75,
        match=MatchCriteria(
            window_title_regex=r".*(Sackboy|Overcooked|It Takes Two|Cuphead|Portal 2).*"
        ),
        mode=ProfileModeConfig(kind="gamepad"),
    )


def _perfil_fps() -> Any:
    """O formato exato do `fps.json` dela: título E `process_name`."""
    from hefesto_dualsense4unix.profiles.schema import (
        MatchCriteria,
        Profile,
        ProfileModeConfig,
    )

    return Profile(
        name="FPS",
        priority=60,
        match=MatchCriteria(
            window_title_regex=r".*(Cyberpunk 2077|Doom|Control).*",
            process_name=[EXE_FPS, "Doom.exe"],
        ),
        mode=ProfileModeConfig(kind="gamepad"),
    )


def test_perfil_so_por_titulo_segura_a_autoridade_em_game(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O cenário medido: janela do jogo em foco, marcador ausente, e a única"""
    _sem_marcador(monkeypatch, tmp_path)
    _perfis(monkeypatch, [_perfil_coop_local()])

    daemon = _daemon()
    daemon.store.set_window_detect_backend("xlib", healthy=True)
    daemon.store.record_window_detect_read(
        "xlib", "unknown", wm_name=TITULO_COOP, exe_basename="sackboy"
    )

    inputs = daemon._gather_game_signal_inputs()

    assert inputs["marker"] is None, "o marcador do wrapper tem de estar ausente"
    assert inputs["window_seen_age"] is None, "a evidência nº 1 tem de estar apagada"
    assert inputs["window_healthy"] is True
    assert inputs["profile_rule_match"] is True
    assert classify(**inputs) == "game"


def test_perfil_com_titulo_e_processo_exige_os_dois_campos(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A cura pela metade — passar só o título — não pode passar aqui."""
    _sem_marcador(monkeypatch, tmp_path)
    _perfis(monkeypatch, [_perfil_fps()])

    daemon = _daemon()

    assert daemon._profile_rule_matches_game("unknown", TITULO_FPS) is False
    assert daemon._profile_rule_matches_game("unknown", None, EXE_FPS) is False
    assert daemon._profile_rule_matches_game("unknown", TITULO_FPS, EXE_FPS) is True

    daemon.store.set_window_detect_backend("xlib", healthy=True)
    daemon.store.record_window_detect_read(
        "xlib", "unknown", wm_name=TITULO_FPS, exe_basename=EXE_FPS
    )
    assert classify(**daemon._gather_game_signal_inputs()) == "game"


def test_janela_com_titulo_de_outro_app_nao_vira_jogo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O contrapeso: sem este teste, uma cura que sempre devolvesse True"""
    _sem_marcador(monkeypatch, tmp_path)
    _perfis(monkeypatch, [_perfil_coop_local(), _perfil_fps()])

    daemon = _daemon()
    daemon.store.set_window_detect_backend("xlib", healthy=True)
    daemon.store.record_window_detect_read(
        "xlib", "firefox", wm_name="Ache aqui — Navegador", exe_basename="firefox"
    )

    inputs = daemon._gather_game_signal_inputs()

    assert inputs["profile_rule_match"] is False
    assert classify(**inputs) == "daemon"


def test_catch_all_com_modo_gamepad_continua_vetado_com_a_janela_inteira(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O veto do `MatchAny` não pode afrouxar por causa dos campos novos."""
    from hefesto_dualsense4unix.profiles.schema import (
        MatchAny,
        Profile,
        ProfileModeConfig,
    )

    _sem_marcador(monkeypatch, tmp_path)
    _perfis(
        monkeypatch,
        [
            Profile(
                name="vitoria",
                priority=0,
                match=MatchAny(),
                mode=ProfileModeConfig(kind="gamepad"),
            )
        ],
    )

    daemon = _daemon()

    assert (
        daemon._profile_rule_matches_game("unknown", TITULO_COOP, "sackboy") is False
    )


def test_janela_sem_nenhum_dos_tres_campos_nao_consulta_perfil(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem classe, sem título e sem processo não há pergunta a fazer — e o"""
    _perfis(monkeypatch, [_perfil_coop_local()])

    daemon = _daemon()

    assert daemon._profile_rule_matches_game(None) is False
    assert daemon._profile_rule_matches_game("") is False
    assert daemon._profile_rule_matches_game(None, None, None) is False
    assert daemon._profile_rule_matches_game("", "", "") is False


class _ControladorComReplay(FakeController):
    """FakeController com os dois callbacks que a transição de autoridade usa."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.defend_calls = 0
        self.replay_calls = 0

    def set_game_authority_provider(self, fn: Any) -> None:
        self.provider = fn

    def defend_display(self) -> None:
        self.defend_calls += 1

    def replay_retained_game_outputs(self) -> None:
        self.replay_calls += 1


async def test_aba_de_navegador_com_titulo_de_jogo_sobe_a_autoridade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O PREÇO desta cura, medido no disco dela e fixado aqui de propósito."""
    _sem_marcador(monkeypatch, tmp_path)
    _perfis(monkeypatch, [_perfil_coop_local()])

    ctrl = _ControladorComReplay(transport="usb")
    daemon = Daemon(
        controller=ctrl,
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    daemon._executor = ThreadPoolExecutor(max_workers=1)
    daemon._wire_game_signal()
    daemon.store.set_window_detect_backend("xlib", healthy=True)
    daemon.store.record_window_detect_read("xlib", "firefox")

    await daemon._sync_game_signal()
    assert daemon.display_authority == "daemon"
    assert ctrl.replay_calls == 0

    daemon.store.record_window_detect_read(
        "xlib", "firefox", wm_name="Portal 2 — YouTube", exe_basename="firefox"
    )
    await daemon._sync_game_signal()

    assert daemon.display_authority == "game"
    assert ctrl.replay_calls == 1


def test_store_guarda_titulo_e_executavel_da_leitura() -> None:
    store = StateStore()
    store.set_window_detect_backend("xlib", healthy=True)

    store.record_window_detect_read(
        "xlib", "steam_app_1599660", wm_name=TITULO_COOP, exe_basename="Sackboy.exe"
    )

    assert store.window_detect_current_name == TITULO_COOP
    assert store.window_detect_current_exe == "Sackboy.exe"


def test_titulo_e_executavel_decaem_como_a_classe_crua() -> None:
    """Os campos novos NÃO podem virar sticky."""
    store = StateStore()
    store.set_window_detect_backend("xlib", healthy=True)
    store.record_window_detect_read(
        "xlib", "steam_app_1599660", wm_name=TITULO_COOP, exe_basename="Sackboy.exe"
    )

    store.record_window_detect_read("xlib", "unknown")

    assert store.window_detect_current_name is None
    assert store.window_detect_current_exe is None
    assert store.window_detect_last_class == "steam_app_1599660"


def test_novo_episodio_do_detector_zera_titulo_e_executavel() -> None:
    store = StateStore()
    store.record_window_detect_read(
        "xlib", "steam_app_1599660", wm_name=TITULO_COOP, exe_basename="Sackboy.exe"
    )

    store.set_window_detect_backend("xlib", healthy=True)

    assert store.window_detect_current_name is None
    assert store.window_detect_current_exe is None


def test_campos_vazios_do_backend_wayland_viram_none() -> None:
    """Os backends Wayland preenchem `exe_basename=""` (não têm `/proc/PID`)."""
    store = StateStore()

    store.record_window_detect_read("portal", "org.gnome.Nautilus", wm_name="", exe_basename="")

    assert store.window_detect_current_name is None
    assert store.window_detect_current_exe is None
