"""OS-INTERRUPTORES-QUE-NINGUEM-LIGA-01 — as métricas ligam por um verbo do CLI.

As métricas são ferramenta de diagnóstico, desligadas por padrão. A única mão
que as liga é ``hefesto-dualsense4unix metrics ligar``, que grava ``metrics.flag``
na pasta de configuração; o daemon lê a escolha na subida. A variável de
ambiente que as forçava, e que nada escrevia, saiu em 03/10/2026.

A MORDIDA: devolva o ``env_force`` em ``MetricsSubsystem.is_enabled`` e o
terceiro teste reprova; tire o ``metrics_enabled=`` do ``DaemonConfig`` em
``daemon/main.py`` e o último reprova.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.cmd_metrics import app
from hefesto_dualsense4unix.daemon.subsystems.metrics import MetricsSubsystem
from hefesto_dualsense4unix.utils import session

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


def test_sem_escolha_gravada_as_metricas_ficam_desligadas(casa: Path) -> None:
    assert not (casa / "metrics.flag").exists()
    assert session.load_metrics_enabled() is False


def test_ligar_e_desligar_gravam_a_escolha(casa: Path) -> None:
    runner = CliRunner()
    ligou = runner.invoke(app, ["ligar"])
    assert ligou.exit_code == 0, ligou.output
    assert json.loads((casa / "metrics.flag").read_text("utf-8")) == {"enabled": True}
    assert session.load_metrics_enabled() is True
    assert "subir de novo" in ligou.output

    desligou = runner.invoke(app, ["desligar"])
    assert desligou.exit_code == 0, desligou.output
    assert session.load_metrics_enabled() is False


def test_a_variavel_de_ambiente_nao_liga_mais(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_METRICS_ENABLED", "1")
    ms = MetricsSubsystem()
    assert ms.is_enabled(SimpleNamespace(metrics_enabled=False)) is False
    assert ms.is_enabled(SimpleNamespace(metrics_enabled=True)) is True


def test_arquivo_estragado_conta_como_desligado(casa: Path) -> None:
    (casa / "metrics.flag").write_text("{nao é json", encoding="utf-8")
    assert session.load_metrics_enabled() is False


def test_o_verbo_esta_na_arvore_do_cli() -> None:
    from hefesto_dualsense4unix.cli.app import app as raiz

    saida = CliRunner().invoke(raiz, ["metrics", "--help"])
    assert saida.exit_code == 0, saida.output
    assert "ligar" in saida.output and "desligar" in saida.output


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
    assert valores.get("metrics_enabled") == "session.load_metrics_enabled()", valores
