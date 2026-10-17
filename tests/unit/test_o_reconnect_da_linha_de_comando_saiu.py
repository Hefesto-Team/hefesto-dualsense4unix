"""A opção `--reconnect/--no-reconnect` não fazia nada, e saiu com os dois campos que ninguém lia.

O DEFEITO (13/10/2026): `daemon start --no-reconnect` era aceita e o daemon reconectava
igual. O `auto_reconnect` e o `reconnect_backoff_sec` do `DaemonConfig` não tinham leitor
em `src/` desde que o `reconnect_loop` virou o dono único da reconexão. A opção mentia.

A CURA: a opção sai da ajuda, de `run_daemon` e do `DaemonConfig`. Quem ainda a passa (uma
unit, um script, um atalho) NÃO quebra: a linha de comando a aceita, avisa que foi ignorada e
sobe o daemon. E o `daemon.reload` com uma das duas chaves antigas responde `ok`, tira a
chave e deixa um aviso no diário; chave que nunca existiu continua sendo erro.

MORDIDAS (cada uma reprova a régua que a nomeia):
  - devolver o `typer.Option` visível reprova `test_a_ajuda_nao_fala_de_reconnect`;
  - devolver o campo ao `DaemonConfig` reprova `test_o_daemon_config_nao_tem_os_dois_campos`;
  - tirar o `CAMPOS_APOSENTADOS` reprova `test_o_reload_com_a_chave_aposentada_...`;
  - tirar a opção escondida reprova `test_a_opcao_velha_nao_derruba_o_daemon`.
"""
from __future__ import annotations

import dataclasses
import inspect
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import click
import pytest
from structlog.testing import capture_logs
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.app import app
from hefesto_dualsense4unix.daemon import ipc_handlers
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.main import run_daemon
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.testing import FakeController

runner = CliRunner()

APOSENTADOS = ("auto_reconnect", "reconnect_backoff_sec")
SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"


def _daemon() -> Daemon:
    return Daemon(
        controller=FakeController(transport="usb", states=[]),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False),
    )


def _ipc(daemon: Daemon) -> IpcServer:
    return IpcServer(
        controller=FakeController(transport="usb", states=[]),
        store=StateStore(),
        profile_manager=MagicMock(),
        daemon=daemon,
    )


@pytest.fixture
def run_daemon_de_mentira(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Troca o `run_daemon` por um registro: nada de daemon, de socket ou de aparelho."""
    chamadas: list[dict[str, Any]] = []

    def falso(**kwargs: Any) -> int:
        chamadas.append(kwargs)
        return 0

    monkeypatch.setattr("hefesto_dualsense4unix.daemon.main.run_daemon", falso)
    return chamadas


def test_a_ajuda_nao_fala_de_reconnect() -> None:
    # Sob `GITHUB_ACTIONS` o rich do Typer força o terminal e pinta `--poll-hz` em pedaços: a
    # régua lê o texto sem os códigos de cor, que é o que a pessoa lê.
    saida = click.unstyle(runner.invoke(app, ["daemon", "start", "--help"]).output)
    assert "--poll-hz" in saida, "a ajuda não saiu: o teste mediria o vazio"
    assert "reconnect" not in saida.lower()


def test_a_docstring_do_topo_nao_anuncia_a_opcao() -> None:
    import hefesto_dualsense4unix.cli.app as cli_app

    assert "reconnect" not in (cli_app.__doc__ or "").lower()


def test_o_daemon_config_nao_tem_os_dois_campos() -> None:
    campos = {f.name for f in dataclasses.fields(DaemonConfig)}
    assert not campos & set(APOSENTADOS)
    assert "auto_reconnect" not in inspect.signature(run_daemon).parameters


def test_nenhum_codigo_de_src_cita_os_dois_campos_fora_da_lista_do_reload() -> None:
    padrao = re.compile(r"auto_reconnect|reconnect_backoff")
    citam = sorted(
        str(arq.relative_to(SRC))
        for arq in SRC.rglob("*.py")
        if padrao.search(arq.read_text(encoding="utf-8"))
    )
    assert citam == ["daemon/ipc_handlers.py"], citam


@pytest.mark.parametrize("flag", ["--no-reconnect", "--reconnect"])
def test_a_opcao_velha_nao_derruba_o_daemon(
    flag: str, run_daemon_de_mentira: list[dict[str, Any]]
) -> None:
    # D-1610-A-OPCAO-RECONNECT-SAI-E-A-VELHA-SO-AVISA
    """Uma unit ou um script antigo com a opção sobe o daemon igual, com um aviso."""
    r = runner.invoke(app, ["daemon", "start", "--poll-hz", "30", flag])
    assert r.exit_code == 0, r.output
    assert run_daemon_de_mentira == [{"poll_hz": 30}]
    assert "ignorada" in r.output
    assert "sempre reconecta" in r.output


def test_sem_a_opcao_velha_nao_ha_aviso(run_daemon_de_mentira: list[dict[str, Any]]) -> None:
    r = runner.invoke(app, ["daemon", "start", "--poll-hz", "30"])
    assert r.exit_code == 0, r.output
    assert run_daemon_de_mentira == [{"poll_hz": 30}]
    assert "ignorada" not in r.output


@pytest.mark.asyncio
async def test_o_reload_com_a_chave_aposentada_responde_ok_aplica_o_resto_e_avisa() -> None:
    ipc_handlers._APOSENTADOS_AVISADOS.clear()
    daemon = _daemon()
    ipc = _ipc(daemon)

    with capture_logs() as diario:
        resposta = await ipc._handle_daemon_reload(
            {"config_overrides": {"auto_reconnect": False, "poll_hz": 30}}
        )

    assert resposta["status"] == "ok"
    assert resposta["config"]["poll_hz"] == 30
    assert daemon.config.poll_hz == 30
    assert not set(resposta["config"]) & set(APOSENTADOS)
    avisos = [e for e in diario if e.get("event") == "daemon.reload.campo_aposentado"]
    assert [e["campo"] for e in avisos] == ["auto_reconnect"]


@pytest.mark.asyncio
async def test_o_aviso_da_chave_aposentada_sai_uma_vez_por_chave() -> None:
    ipc_handlers._APOSENTADOS_AVISADOS.clear()
    ipc = _ipc(_daemon())
    pedido = {"config_overrides": {"auto_reconnect": True, "reconnect_backoff_sec": 1.0}}

    with capture_logs() as diario:
        await ipc._handle_daemon_reload(pedido)
        await ipc._handle_daemon_reload(pedido)

    avisos = sorted(
        e["campo"] for e in diario if e.get("event") == "daemon.reload.campo_aposentado"
    )
    assert avisos == sorted(APOSENTADOS)


@pytest.mark.asyncio
async def test_chave_que_nunca_existiu_continua_levantando_ao_lado_de_uma_aposentada() -> None:
    ipc = _ipc(_daemon())
    with pytest.raises(ValueError, match="campos desconhecidos") as erro:
        await ipc._handle_daemon_reload(
            {"config_overrides": {"auto_reconnect": False, "campo_que_nunca_existiu": 1}}
        )
    assert "campo_que_nunca_existiu" in str(erro.value)
    assert "auto_reconnect" not in str(erro.value)
