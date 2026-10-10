"""O ``plugin.reload`` recarrega os plugins do disco sem perder nenhum.

O-PLUGIN-RECARREGA-SEM-PERDER-OS-PLUGINS-01 e
O-RECARREGAR-DOS-PLUGINS-NAO-APAGA-OS-PLUGINS-01 (09/10/2026). O ``reload``
descarregava todos e embrulhava o ``start`` num laço próprio, e o único
chamador, o manipulador do IPC, roda dentro do laço do daemon: o
``run_until_complete`` levantava ``RuntimeError`` e o daemon ficava sem
plugins até reiniciar.

A MORDIDA: devolva o ``asyncio.new_event_loop().run_until_complete`` e o
primeiro teste reprova com o erro interno e a lista vazia; tire o ``clear()``
e o segundo reprova com o plugin duplicado.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.plugins import PluginsSubsystem
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

PLUGIN = '''
import os
from pathlib import Path

from hefesto_dualsense4unix.plugin_api.plugin import Plugin


def _marca(evento):
    with Path(os.environ["HEFESTO_REGUA_CONTADOR"]).open("a") as f:
        f.write(evento + "\\n")


class Um(Plugin):
    name = "um"

    def on_load(self, ctx):
        _marca("load")

    def on_unload(self):
        _marca("unload")
'''


@pytest.fixture
def contador(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / "plugins"
    pasta.mkdir()
    (pasta / "um.py").write_text(PLUGIN, encoding="utf-8")
    arquivo = tmp_path / "contador.txt"
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_PLUGINS_DIR", str(pasta))
    monkeypatch.setenv("HEFESTO_REGUA_CONTADOR", str(arquivo))
    return arquivo


def _eventos(arquivo: Path) -> list[str]:
    return arquivo.read_text(encoding="utf-8").split() if arquivo.exists() else []


async def _servico(tmp_path: Path) -> tuple[IpcServer, PluginsSubsystem]:
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    daemon = MagicMock()
    ps = PluginsSubsystem()
    daemon._plugins_subsystem = ps
    servidor = IpcServer(controller=fc, store=store,
                         profile_manager=ProfileManager(controller=fc, store=store),
                         socket_path=tmp_path / "hefesto-dualsense4unix.sock",
                         daemon=daemon)
    await ps.start(MagicMock(controller=fc, bus=MagicMock(), store=store))
    return servidor, ps


async def _chamar(servidor: IpcServer, metodo: str, n: int) -> Any:
    pedido = json.dumps({"jsonrpc": "2.0", "id": n, "method": metodo, "params": {}})
    resposta = await servidor._dispatch(pedido.encode("utf-8"))
    assert resposta is not None
    corpo = json.loads(resposta)
    assert "error" not in corpo, corpo
    return corpo["result"]


@pytest.mark.asyncio
async def test_o_reload_pelo_ipc_mantem_o_plugin(tmp_path: Path, contador: Path) -> None:
    servidor, _ps = await _servico(tmp_path)
    assert [p["name"] for p in await _chamar(servidor, "plugin.list", 1)] == ["um"]

    assert await _chamar(servidor, "plugin.reload", 2) == {"status": "ok", "total": 1}

    assert [p["name"] for p in await _chamar(servidor, "plugin.list", 3)] == ["um"]


@pytest.mark.asyncio
async def test_dois_reloads_deixam_um_plugin_so(tmp_path: Path, contador: Path) -> None:
    servidor, ps = await _servico(tmp_path)
    for n in (1, 2):
        assert await _chamar(servidor, "plugin.reload", n) == {"status": "ok", "total": 1}
    assert [p["name"] for p in ps.list_plugins()] == ["um"]
    eventos = _eventos(contador)
    assert eventos.count("load") == 3, eventos
    assert eventos.count("unload") == 2, eventos
