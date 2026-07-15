"""FEAT-MOUSE-PERSIST-01: o toggle de emulação de mouse persiste em
restart/reboot via flag-file no config_dir.

FEAT-MOUSE-CURSOR-FEEL-01 (A5): o flag ganhou conteúdo JSON com speed e
scroll_speed (padrão flag-com-conteúdo do gamepad); conteúdo legado "1\\n"
continua contando como ligado (velocidades None → defaults). O restore do
daemon no boot aplica as velocidades com clamp ao contrato (1-12 / 1-5).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session


@pytest.fixture()
def tmp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redireciona config_dir do session para tmp_path."""
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


def test_roundtrip_liga_desliga(tmp_config: Path) -> None:
    assert session.load_mouse_emulation_enabled() is False
    session.save_mouse_emulation_enabled(True)
    assert (tmp_config / "mouse_emulation.flag").exists()
    assert session.load_mouse_emulation_enabled() is True
    session.save_mouse_emulation_enabled(False)
    # HARM-06: o "off" agora é GRAVADO (era o apagar do arquivo). O que a
    # usuária desligou tem que ser distinguível do que ela nunca configurou —
    # senão "Controlar o PC" religa o mouse contra a vontade dela.
    assert (tmp_config / "mouse_emulation.flag").exists()
    assert session.load_mouse_emulation_enabled() is False


def test_load_false_sem_arquivo(tmp_config: Path) -> None:
    assert session.load_mouse_emulation_enabled() is False


def test_save_best_effort_nao_propaga_excecao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_a: object, **_k: object) -> Path:
        raise OSError("config dir indisponível")

    monkeypatch.setattr(session, "config_dir", _boom)
    # Não deve levantar (best-effort); e load também é tolerante.
    session.save_mouse_emulation_enabled(True)
    assert session.load_mouse_emulation_enabled() is False
    session.save_mouse_emulation(True, speed=9, scroll_speed=3)
    assert session.load_mouse_emulation() == (False, None, None)


# --- flag JSON com velocidades (FEAT-MOUSE-CURSOR-FEEL-01, A5) ---------------


def test_flag_json_roundtrip_com_velocidades(tmp_config: Path) -> None:
    session.save_mouse_emulation(True, speed=9, scroll_speed=3)
    assert session.load_mouse_emulation() == (True, 9, 3)
    # Conteúdo é JSON de verdade (contrato do flag-com-conteúdo).
    data = json.loads((tmp_config / "mouse_emulation.flag").read_text("utf-8"))
    assert data == {"enabled": True, "speed": 9, "scroll_speed": 3}
    # HARM-06: desligar GRAVA "off" (era apagar o arquivo) e PRESERVA as
    # velocidades — o desligar não passa velocidades e não pode zerar a escolha.
    session.save_mouse_emulation(False)
    assert json.loads((tmp_config / "mouse_emulation.flag").read_text("utf-8")) == {
        "enabled": False,
        "speed": 9,
        "scroll_speed": 3,
    }
    assert session.load_mouse_emulation() == (False, 9, 3)


def test_flag_json_sem_velocidades_devolve_none(tmp_config: Path) -> None:
    session.save_mouse_emulation(True)
    assert session.load_mouse_emulation() == (True, None, None)


def test_flag_legado_conteudo_1_conta_como_ligado(tmp_config: Path) -> None:
    """Flag gravado por versão anterior ("1\\n") → ligado, velocidades default."""
    (tmp_config / "mouse_emulation.flag").write_text("1\n", encoding="utf-8")
    assert session.load_mouse_emulation() == (True, None, None)
    assert session.load_mouse_emulation_enabled() is True


def test_flag_json_malformado_ou_tipos_errados_tolerado(tmp_config: Path) -> None:
    flag = tmp_config / "mouse_emulation.flag"
    flag.write_text('{"speed": "rapido", "scroll_speed": true}', encoding="utf-8")
    assert session.load_mouse_emulation() == (True, None, None)
    flag.write_text("{corrompido", encoding="utf-8")
    assert session.load_mouse_emulation() == (True, None, None)
    flag.write_text("", encoding="utf-8")
    assert session.load_mouse_emulation() == (True, None, None)


def test_wrappers_legados_continuam_funcionando(tmp_config: Path) -> None:
    """Os nomes antigos delegam ao flag novo (não tocar testes/callers legados)."""
    session.save_mouse_emulation_enabled(True)
    assert session.load_mouse_emulation_enabled() is True
    assert session.load_mouse_emulation() == (True, None, None)
    session.save_mouse_emulation_enabled(False)
    assert session.load_mouse_emulation_enabled() is False


# --- restore no boot do daemon (restart simulado) ----------------------------


def _boot_config() -> DaemonConfig:
    return DaemonConfig(
        poll_hz=200,
        auto_reconnect=False,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        keyboard_emulation_enabled=False,
        ps_button_action="none",
        mic_button_toggles_system=False,
    )


async def _boot_and_stop(daemon: Daemon) -> None:
    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.05)
    daemon.stop()
    await run_task


@pytest.mark.asyncio
async def test_daemon_restaura_velocidades_no_boot(
    tmp_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ligar com speed=9/scroll=3 → restart (simulado) → daemon restaura 9/3.

    O start real do device é substituído (não criar uinput de verdade no
    sistema); o alvo do teste é o restore da config a partir do flag JSON.
    """
    session.save_mouse_emulation(True, speed=9, scroll_speed=3)
    started: list[bool] = []
    monkeypatch.setattr(
        Daemon, "_start_mouse_emulation", lambda self: started.append(True) or True
    )
    daemon = Daemon(controller=FakeController(transport="usb"), config=_boot_config())
    await _boot_and_stop(daemon)

    assert daemon.config.mouse_emulation_enabled is True
    assert daemon.config.mouse_speed == 9
    assert daemon.config.mouse_scroll_speed == 3
    assert started  # o subsystem mouse foi acionado no boot


@pytest.mark.asyncio
async def test_daemon_clampa_velocidades_do_flag_no_boot(
    tmp_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Flag com valores fora do contrato → clamp 1-12 / 1-5 no restore."""
    (tmp_config / "mouse_emulation.flag").write_text(
        '{"speed": 99, "scroll_speed": 0}', encoding="utf-8"
    )
    monkeypatch.setattr(Daemon, "_start_mouse_emulation", lambda self: True)
    daemon = Daemon(controller=FakeController(transport="usb"), config=_boot_config())
    await _boot_and_stop(daemon)

    assert daemon.config.mouse_emulation_enabled is True
    assert daemon.config.mouse_speed == 12
    assert daemon.config.mouse_scroll_speed == 1
