"""NUMA-01 — a fiação do lifecycle que ATIVA o gate NUMA-02/03 dormente."""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing import FakeController


class _AuthorityController(FakeController):
    """FakeController + os 3 pontos de contato do NUMA-01/02/03."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.provider: Any = None
        self.defend_calls = 0
        self.replay_calls = 0

    def set_game_authority_provider(self, fn: Any) -> None:
        self.provider = fn

    def defend_display(self) -> None:
        self.defend_calls += 1

    def replay_retained_game_outputs(self) -> None:
        self.replay_calls += 1


def _daemon(controller: Any) -> Daemon:
    return Daemon(
        controller=controller,
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )


def test_display_authority_e_unknown_antes_de_qualquer_fiacao() -> None:
    daemon = _daemon(FakeController(transport="usb"))
    assert daemon.display_authority == "unknown"


def test_wire_game_signal_sempre_nasce_mesmo_com_fake_controller() -> None:
    """Diferente de `_wire_identity_registry`/`_wire_external_registry`: o"""
    daemon = _daemon(FakeController(transport="usb"))
    daemon._wire_game_signal()
    assert daemon._game_signal is not None
    assert daemon.display_authority == "unknown"
    assert not hasattr(daemon.controller, "set_game_authority_provider")


def test_wire_game_signal_injeta_o_provider_quando_o_backend_suporta() -> None:
    ctrl = _AuthorityController(transport="usb")
    daemon = _daemon(ctrl)
    daemon._wire_game_signal()
    assert callable(ctrl.provider)
    assert ctrl.provider() == daemon.display_authority == "unknown"


def test_provider_reflete_mudancas_de_autoridade_em_tempo_real() -> None:
    """O provider é uma leitura viva (`lambda: self._game_signal.authority`)"""
    ctrl = _AuthorityController(transport="usb")
    daemon = _daemon(ctrl)
    daemon._wire_game_signal()
    daemon._game_signal.evaluate("game", session_open=True)
    assert ctrl.provider() == "game"


async def test_sync_game_signal_e_noop_sem_wire() -> None:
    """Sem `_wire_game_signal` (nunca chamado) — precisa ser no-op"""
    daemon = _daemon(FakeController(transport="usb"))
    await daemon._sync_game_signal()
    assert daemon.display_authority == "unknown"


async def test_sync_game_signal_sem_evidencia_e_detector_sao_vira_daemon() -> None:
    ctrl = _AuthorityController(transport="usb")
    daemon = _daemon(ctrl)
    daemon._executor = ThreadPoolExecutor(max_workers=1)
    daemon._wire_game_signal()
    daemon.store.set_window_detect_backend("xlib", healthy=True)

    await daemon._sync_game_signal()

    assert daemon.display_authority == "daemon"
    assert ctrl.defend_calls == 1
    assert ctrl.replay_calls == 0


async def test_sync_game_signal_dispara_defend_display_na_transicao_para_daemon() -> (
    None
):
    ctrl = _AuthorityController(transport="usb")
    daemon = _daemon(ctrl)
    daemon._executor = ThreadPoolExecutor(max_workers=1)
    daemon._wire_game_signal()
    daemon.store.set_window_detect_backend("xlib", healthy=False)

    await daemon._sync_game_signal()
    assert daemon.display_authority == "unknown"
    assert ctrl.defend_calls == 0

    daemon.store.set_window_detect_backend("xlib", healthy=True)
    await daemon._sync_game_signal()
    assert daemon.display_authority == "daemon"
    assert ctrl.defend_calls == 1


async def test_sync_game_signal_dispara_replay_na_volta_de_daemon_para_game() -> None:
    ctrl = _AuthorityController(transport="usb")
    daemon = _daemon(ctrl)
    daemon._executor = ThreadPoolExecutor(max_workers=1)
    daemon._wire_game_signal()
    daemon.store.set_window_detect_backend("xlib", healthy=True)

    await daemon._sync_game_signal()
    assert daemon.display_authority == "daemon"

    daemon.store.record_window_detect_read("xlib", "steam_app_1599660")
    await daemon._sync_game_signal()

    assert daemon.display_authority == "game"
    assert ctrl.replay_calls == 1


async def test_sync_game_signal_callback_ausente_no_controller_e_no_op() -> None:
    """Backend sem `defend_display`/`replay_retained_game_outputs`"""
    daemon = _daemon(FakeController(transport="usb"))
    daemon._executor = ThreadPoolExecutor(max_workers=1)
    daemon._wire_game_signal()
    daemon.store.set_window_detect_backend("xlib", healthy=True)

    await daemon._sync_game_signal()

    assert daemon.display_authority == "daemon"


async def test_gather_falhando_degrada_para_unknown_sem_derrubar_o_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctrl = _AuthorityController(transport="usb")
    daemon = _daemon(ctrl)
    daemon._executor = ThreadPoolExecutor(max_workers=1)
    daemon._wire_game_signal()
    daemon._game_signal.evaluate("daemon", session_open=False)

    def _explode() -> dict[str, Any]:
        raise OSError("disco cheio")

    monkeypatch.setattr(daemon, "_gather_game_signal_inputs", _explode)

    await daemon._sync_game_signal()

    assert daemon.display_authority == "unknown"
    assert ctrl.replay_calls == 1


def test_gather_game_signal_inputs_correlaciona_last_exit_por_pid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Integração pós-auditoria da Onda N: `_gather_game_signal_inputs` lê"""
    import hefesto_dualsense4unix.daemon.launch_env as le_mod
    from hefesto_dualsense4unix.daemon.subsystems.game_signal import classify

    launch_dir = tmp_path / "launch_env"
    launch_dir.mkdir()
    monkeypatch.setattr(le_mod, "launch_env_dir", lambda ensure=False: launch_dir)

    meu_pid = os.getpid()
    outro_pid = meu_pid + 1
    agora = int(time.time())
    (launch_dir / "last_run").write_text(
        f"appid=1599660\nepoch={agora - 10}\npid={meu_pid}\n", encoding="utf-8"
    )
    (launch_dir / "last_exit").write_text(
        f"epoch={agora - 5}\npid={outro_pid}\n", encoding="utf-8"
    )

    daemon = _daemon(FakeController(transport="usb"))

    inputs = daemon._gather_game_signal_inputs()

    assert inputs["marker_pid"] == meu_pid
    assert inputs["exit_pid"] == outro_pid
    assert inputs["marker_pid_alive"] is True
    assert classify(**inputs) == "game"


def test_gather_game_signal_inputs_sem_markers_nao_quebra(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sem `last_run`/`last_exit` no disco: `marker_pid`/`exit_pid` vêm"""
    import hefesto_dualsense4unix.daemon.launch_env as le_mod

    launch_dir = tmp_path / "launch_env"
    monkeypatch.setattr(le_mod, "launch_env_dir", lambda ensure=False: launch_dir)

    daemon = _daemon(FakeController(transport="usb"))

    inputs = daemon._gather_game_signal_inputs()

    assert inputs["marker"] is None
    assert inputs["marker_pid"] is None
    assert inputs["exit_pid"] is None


def test_any_game_session_open_false_sem_vpad() -> None:
    daemon = _daemon(FakeController(transport="usb"))
    assert daemon._any_game_session_open() is False


def test_any_game_session_open_true_com_o_vpad_primario() -> None:
    from types import SimpleNamespace

    daemon = _daemon(FakeController(transport="usb"))
    daemon._gamepad_device = SimpleNamespace(game_open=True)
    assert daemon._any_game_session_open() is True


def test_any_game_session_open_true_com_vpad_do_coop() -> None:
    from types import SimpleNamespace

    daemon = _daemon(FakeController(transport="usb"))
    daemon._gamepad_device = SimpleNamespace(game_open=False)
    daemon._coop_manager = SimpleNamespace(
        _players={
            "p2": SimpleNamespace(vpad=SimpleNamespace(game_open=True)),
        }
    )
    assert daemon._any_game_session_open() is True


def test_profile_rule_matches_game_false_sem_wm_class() -> None:
    daemon = _daemon(FakeController(transport="usb"))
    assert daemon._profile_rule_matches_game(None) is False
    assert daemon._profile_rule_matches_game("") is False


def test_profile_rule_matches_game_ignora_matchany_catchall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O perfil fallback (`MatchAny`) SEMPRE casa — não pode virar evidência"""
    from hefesto_dualsense4unix.profiles import manager as manager_module
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    fallback = Profile(name="fallback", match=MatchAny())
    monkeypatch.setattr(manager_module, "load_all_profiles", lambda: [fallback])

    daemon = _daemon(FakeController(transport="usb"))
    assert daemon._profile_rule_matches_game("qualquer_coisa") is False


def test_profile_rule_matches_game_true_com_regra_especifica_gamepad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.profiles import manager as manager_module
    from hefesto_dualsense4unix.profiles.schema import (
        MatchCriteria,
        Profile,
        ProfileModeConfig,
    )

    jogo = Profile(
        name="heroic_jogo",
        match=MatchCriteria(window_class=["heroic-game"]),
        mode=ProfileModeConfig(kind="gamepad"),
    )
    monkeypatch.setattr(manager_module, "load_all_profiles", lambda: [jogo])

    daemon = _daemon(FakeController(transport="usb"))
    assert daemon._profile_rule_matches_game("heroic-game") is True
    assert daemon._profile_rule_matches_game("outra-janela") is False


def test_profile_rule_matches_game_false_para_kind_nativo_ou_desktop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.profiles import manager as manager_module
    from hefesto_dualsense4unix.profiles.schema import (
        MatchCriteria,
        Profile,
        ProfileModeConfig,
    )

    nativo = Profile(
        name="nativo",
        match=MatchCriteria(window_class=["algum-jogo"]),
        mode=ProfileModeConfig(kind="native"),
    )
    monkeypatch.setattr(manager_module, "load_all_profiles", lambda: [nativo])

    daemon = _daemon(FakeController(transport="usb"))
    assert daemon._profile_rule_matches_game("algum-jogo") is False
