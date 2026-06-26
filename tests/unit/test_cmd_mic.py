"""Cobertura do `hefesto-dualsense4unix mic on|off|status` (FEAT-DUALSENSE-MIC-TOGGLE-01)."""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.cli import cmd_mic


def test_action_flag_mapping():
    """Cada ação mapeia para a flag certa do script do WirePlumber."""
    assert cmd_mic._ACTION_FLAG["on"] == "--enable-mic"
    assert cmd_mic._ACTION_FLAG["off"] == "--disable-source"
    assert cmd_mic._ACTION_FLAG["status"] == "--status"


def test_acao_invalida_sai_com_codigo_2():
    import typer

    with pytest.raises(typer.Exit) as exc:
        cmd_mic.mic_cmd("ligadex")
    assert exc.value.exit_code == 2


def test_run_chama_script_com_flag(monkeypatch, tmp_path):
    """`mic on` roda o script com --enable-mic; código do subprocess é propagado."""
    import typer

    fake = tmp_path / "fix_wireplumber_default_source.sh"
    fake.write_text("#!/usr/bin/env bash\nexit 0\n")
    monkeypatch.setattr(cmd_mic, "_find_script", lambda: fake)

    calls: list[list[str]] = []

    class _R:
        returncode = 0

    def _fake_run(args, check=False):
        calls.append(args)
        return _R()

    monkeypatch.setattr(cmd_mic.subprocess, "run", _fake_run)

    with pytest.raises(typer.Exit) as exc:
        cmd_mic.mic_cmd("on")
    assert exc.value.exit_code == 0
    assert calls == [["bash", str(fake), "--enable-mic"]]


def test_off_trata_rc2_como_sucesso(monkeypatch, tmp_path):
    """disable-source devolve 2 quando o DualSense é a única fonte — não é falha."""
    import typer

    fake = tmp_path / "fix_wireplumber_default_source.sh"
    fake.write_text("#!/usr/bin/env bash\nexit 2\n")
    monkeypatch.setattr(cmd_mic, "_find_script", lambda: fake)

    class _R:
        returncode = 2

    monkeypatch.setattr(cmd_mic.subprocess, "run", lambda *a, **k: _R())

    with pytest.raises(typer.Exit) as exc:
        cmd_mic.mic_cmd("off")
    assert exc.value.exit_code == 0
