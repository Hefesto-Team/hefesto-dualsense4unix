"""OS-INTERRUPTORES-QUE-NINGUEM-LIGA-01 — os plugins ligam por um verbo do CLI.

Plugin de terceiro roda com os privilégios do daemon. O padrão é desligado, e
a única mão que os liga é ``hefesto-dualsense4unix plugin ligar``, que grava
``plugins.flag`` na pasta de configuração; o daemon lê a escolha na subida. A
variável de ambiente que os forçava, e que nada escrevia, saiu em 02/10/2026.

A MORDIDA: devolva o ``env_force`` em ``PluginsSubsystem.is_enabled`` e o
terceiro teste reprova; tire o ``plugins_enabled=`` do ``DaemonConfig`` em
``daemon/main.py`` e o último reprova.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.cmd_plugin import app
from hefesto_dualsense4unix.daemon.subsystems.plugins import PluginsSubsystem
from hefesto_dualsense4unix.utils import session

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


def test_sem_escolha_gravada_os_plugins_ficam_desligados(casa: Path) -> None:
    assert not (casa / "plugins.flag").exists()
    assert session.load_plugins_enabled() is False


def test_ligar_e_desligar_gravam_a_escolha(casa: Path) -> None:
    runner = CliRunner()
    ligou = runner.invoke(app, ["ligar"])
    assert ligou.exit_code == 0, ligou.output
    assert json.loads((casa / "plugins.flag").read_text("utf-8")) == {"enabled": True}
    assert session.load_plugins_enabled() is True
    assert "subir de novo" in ligou.output

    desligou = runner.invoke(app, ["desligar"])
    assert desligou.exit_code == 0, desligou.output
    assert session.load_plugins_enabled() is False


def test_a_variavel_de_ambiente_nao_liga_mais(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_PLUGINS_ENABLED", "1")
    ps = PluginsSubsystem()
    assert ps.is_enabled(SimpleNamespace(plugins_enabled=False)) is False
    assert ps.is_enabled(SimpleNamespace(plugins_enabled=True)) is True


def test_arquivo_estragado_conta_como_desligado(casa: Path) -> None:
    (casa / "plugins.flag").write_text("{nao é json", encoding="utf-8")
    assert session.load_plugins_enabled() is False


def test_a_subida_do_daemon_le_a_escolha() -> None:
    fonte = (RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "main.py").read_text(
        encoding="utf-8"
    )
    chamadas = [
        no
        for no in ast.walk(ast.parse(fonte))
        if isinstance(no, ast.Call) and getattr(no.func, "id", None) == "DaemonConfig"
    ]
    assert len(chamadas) == 1, "a subida do daemon monta o DaemonConfig num lugar só"
    valores = {kw.arg: ast.unparse(kw.value) for kw in chamadas[0].keywords}
    assert valores.get("plugins_enabled") == "session.load_plugins_enabled()", valores
