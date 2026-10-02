"""SINAL-DE-JOGO-01/E4 — o jogo VIVO é evidência, e a árvore da Steam não é."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.launch_env import (
    WRAPPER_MARKER_WINDOW_SEC,
    wrapper_game_running,
)
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems.game_signal import GameSignal, classify
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.testing import FakeController

APPID = 1599660
REAPER_COM_JOGO = (
    "/home/vitoriamaria/.steam/debian-installation/ubuntu12_32/reaper "
    f"SteamLaunch AppId={APPID} -- /.../proton waitforexitandrun /.../Launcher.exe"
)

PROC_STEAM_SEM_JOGO = {
    "1000": "/usr/bin/steam",
    "1001": "/home/vitoriamaria/.steam/.../steamwebhelper --type=utility",
    "1002": "/home/vitoriamaria/.steam/.../reaper",
}


@pytest.fixture(autouse=True)
def _sem_foto_herdada() -> Any:
    """A varredura tem memória de 5 s (BG-03) e ela sobrevive ao teste."""
    slo.invalidar_varredura_de_proc()
    yield
    slo.invalidar_varredura_de_proc()


def _proc_falso(monkeypatch: pytest.MonkeyPatch, mapa: dict[str, str]) -> None:
    """Instala um `/proc` sintético para a varredura da casa (mesma costura"""
    monkeypatch.setattr(slo, "_cmdline_of", lambda pid: mapa.get(str(pid), ""))
    monkeypatch.setattr(slo.os, "listdir", lambda path: [*mapa, "self", "cpuinfo"])


def _launch_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Aponta o diretório do wrapper para um tmp — sem isto o teste leria"""
    import hefesto_dualsense4unix.daemon.launch_env as le_mod

    destino = tmp_path / "launch_env"
    destino.mkdir(exist_ok=True)
    monkeypatch.setattr(le_mod, "launch_env_dir", lambda ensure=False: destino)
    return destino


def _sem_perfis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apaga a evidência nº 2: nenhum perfil no disco casa coisa nenhuma."""
    from hefesto_dualsense4unix.profiles import manager as manager_module

    monkeypatch.setattr(manager_module, "load_all_profiles", lambda: [])


def _daemon_no_desktop() -> Daemon:
    """Daemon com o detector de janela SÃO e olhando o desktop."""
    daemon = Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    daemon.store.set_window_detect_backend("xlib", healthy=True)
    daemon.store.record_window_detect_read(
        "xlib", "firefox", wm_name="Ache aqui — Navegador", exe_basename="firefox"
    )
    return daemon


def test_jogo_vivo_sem_wrapper_e_evidencia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Marker VENCIDO, pid do jogo vivo: a autoridade não cai."""
    destino = _launch_env(monkeypatch, tmp_path)
    _sem_perfis(monkeypatch)

    meu_pid = os.getpid()
    agora = int(time.time())
    vencido_ha = int(WRAPPER_MARKER_WINDOW_SEC) + 900
    (destino / "last_run").write_text(
        f"appid={APPID}\nepoch={agora - vencido_ha}\npid={meu_pid}\n",
        encoding="utf-8",
    )
    _proc_falso(monkeypatch, {str(meu_pid): REAPER_COM_JOGO, "1": "/sbin/init"})

    daemon = _daemon_no_desktop()
    inputs = daemon._gather_game_signal_inputs()

    assert inputs["marker"] == (APPID, agora - vencido_ha)
    assert inputs["marker_pid_alive"] is True
    assert inputs["window_seen_age"] is None
    assert inputs["profile_rule_match"] is False
    assert (
        wrapper_game_running(
            marker=inputs["marker"],
            exit_marker=inputs["exit_marker"],
            pid_alive=inputs["marker_pid_alive"],
            marker_pid=inputs["marker_pid"],
            exit_pid=inputs["exit_pid"],
            now=inputs["now"],
        )
        is False
    ), "o teto de frescor tinha de ter vencido — senão este teste mede outra coisa"

    assert inputs["appid_de_jogo_vivo"] == APPID
    assert classify(**inputs) == "game", (
        "jogo vivo com marker vencido tem de continuar sendo evidência — "
        f"appid_de_jogo_vivo={inputs['appid_de_jogo_vivo']!r}"
    )

    sinal = GameSignal()
    sinal.evaluate("game", session_open=True)
    assert sinal.evaluate(classify(**inputs), session_open=True) == "game"


def test_steam_viva_nao_e_jogo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Vivos só `steam`, `steamwebhelper` e `reaper`: a autoridade não sobe."""
    _launch_env(monkeypatch, tmp_path)
    _sem_perfis(monkeypatch)
    _proc_falso(monkeypatch, dict(PROC_STEAM_SEM_JOGO))

    daemon = _daemon_no_desktop()
    inputs = daemon._gather_game_signal_inputs()

    assert inputs["marker"] is None
    assert inputs["profile_rule_match"] is False
    assert inputs["window_seen_age"] is None

    aceito = slo._steam_launch_cmdline()
    processos = sorted(PROC_STEAM_SEM_JOGO.values())
    assert inputs["appid_de_jogo_vivo"] is None, (
        "a árvore da Steam SEM jogo virou evidência de jogo "
        f"(appid_de_jogo_vivo={inputs['appid_de_jogo_vivo']!r}). "
        f"A varredura canônica aceitou a cmdline {aceito!r}; o /proc deste "
        f"teste só tinha estes processos, e nenhum deles é jogo: {processos}"
    )
    assert classify(**inputs) == "daemon", (
        "sem jogo nenhum vivo o veredito tem de ser `daemon` — "
        f"appid_de_jogo_vivo={inputs['appid_de_jogo_vivo']!r}, "
        f"cmdline aceita pela varredura canônica: {aceito!r}, "
        f"processos do /proc do teste: {processos}"
    )


def test_jogo_vivo_sem_marker_nenhum_e_evidencia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O caso dela, medido em 31/07: **o jogo não passa pelo wrapper**."""
    _launch_env(monkeypatch, tmp_path)
    _sem_perfis(monkeypatch)
    _proc_falso(
        monkeypatch,
        {"1": "/sbin/init", "4242": REAPER_COM_JOGO, **PROC_STEAM_SEM_JOGO},
    )

    daemon = _daemon_no_desktop()
    inputs = daemon._gather_game_signal_inputs()

    assert inputs["marker"] is None
    assert inputs["marker_pid_alive"] is False
    assert inputs["appid_de_jogo_vivo"] == APPID
    assert classify(**inputs) == "game"


def test_appid_zero_nao_e_jogo() -> None:
    """`AppId=0` não identifica jogo nenhum, e a agulha `SteamLaunch AppId=\\d`"""
    base = dict(
        window_healthy=True,
        window_class_current="firefox",
        window_seen_age=None,
        profile_rule_match=False,
        marker=None,
        marker_pid_alive=False,
        exit_marker=None,
        session_open=False,
        now=time.time(),
    )
    assert classify(**base, appid_de_jogo_vivo=0) == "daemon"
    assert classify(**base, appid_de_jogo_vivo=None) == "daemon"
    assert classify(**base, appid_de_jogo_vivo=APPID) == "game"
