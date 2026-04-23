"""Testes unitarios do sistema de plugins (FEAT-PLUGIN-01).

Cobre:
  - load_plugins_from_dir: carregamento via diretório tmp_path.
  - on_load called com PluginContext valido.
  - on_tick chamado pelo PluginsSubsystem.tick().
  - Watchdog: hook lento acima de 3 vezes desativa plugin.
  - BUTTON_DOWN e BATTERY_CHANGE despachados corretamente.
  - Plugin com profile_match não recebe tick de perfil fora da lista.
  - Arquivo invalido (SyntaxError) não quebra o loader.
  - Plugin sem atributo name e ignorado.
  - PluginContext: ControllerProxy delega para IController mock.
  - PluginsSubsystem.list_plugins() retorna descrição correta.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest

from hefesto.core.controller import ControllerState
from hefesto.core.events import EventBus
from hefesto.daemon.state_store import StateStore
from hefesto.daemon.subsystems.plugins import PluginsSubsystem, _PluginEntry
from hefesto.plugin_api import Plugin, PluginContext
from hefesto.plugin_api.context import ControllerProxy, make_plugin_context
from hefesto.plugin_api.loader import load_plugins_from_dir

# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _mk_state(battery: int = 80, buttons: frozenset[str] | None = None) -> ControllerState:
    return ControllerState(
        battery_pct=battery,
        l2_raw=0,
        r2_raw=0,
        connected=True,
        transport="usb",
        buttons_pressed=buttons or frozenset(),
    )


def _mk_controller_mock() -> MagicMock:
    ctrl = MagicMock()
    ctrl.is_connected.return_value = True
    ctrl.get_battery.return_value = 85
    ctrl.get_transport.return_value = "usb"
    return ctrl


def _plugin_py_content(name: str = "plugin_teste", extra: str = "") -> str:
    return f"""
from hefesto.plugin_api import Plugin, PluginContext

class PluginTeste(Plugin):
    name = "{name}"
    profile_match = []
    chamadas_on_load = 0
    chamadas_on_tick = 0
    chamadas_on_button = []
    chamadas_on_battery = []

    def on_load(self, ctx: PluginContext) -> None:
        self.__class__.chamadas_on_load += 1
        self.ctx = ctx

    def on_tick(self, state) -> None:
        self.__class__.chamadas_on_tick += 1

    def on_button_down(self, name: str) -> None:
        self.__class__.chamadas_on_button.append(name)

    def on_battery_change(self, pct: int) -> None:
        self.__class__.chamadas_on_battery.append(pct)

{extra}
"""


# ---------------------------------------------------------------------------
# Testes de loader
# ---------------------------------------------------------------------------


def test_load_plugins_from_dir_carrega_plugin(tmp_path: Path) -> None:
    """load_plugins_from_dir deve retornar instancia do plugin."""
    (tmp_path / "meu_plugin.py").write_text(_plugin_py_content("meu_plugin"))
    plugins = load_plugins_from_dir(tmp_path)
    assert len(plugins) == 1
    assert plugins[0].name == "meu_plugin"


def test_load_plugins_skip_underscore(tmp_path: Path) -> None:
    """Arquivos com _ inicial sao ignorados."""
    (tmp_path / "_interno.py").write_text(_plugin_py_content("interno"))
    plugins = load_plugins_from_dir(tmp_path)
    assert plugins == []


def test_load_plugins_dir_inexistente(tmp_path: Path) -> None:
    """Diretório inexistente retorna lista vazia sem excecao."""
    plugins = load_plugins_from_dir(tmp_path / "nao_existe")
    assert plugins == []


def test_load_plugins_arquivo_invalido_skipped(tmp_path: Path) -> None:
    """Arquivo com SyntaxError eh ignorado; outros plugins seguem carregando."""
    (tmp_path / "invalido.py").write_text("def foo(")
    (tmp_path / "valido.py").write_text(_plugin_py_content("valido"))
    plugins = load_plugins_from_dir(tmp_path)
    assert len(plugins) == 1
    assert plugins[0].name == "valido"


def test_load_plugins_sem_name_skipped(tmp_path: Path) -> None:
    """Plugin sem atributo name eh ignorado."""
    (tmp_path / "sem_name.py").write_text("""
from hefesto.plugin_api import Plugin

class SemName(Plugin):
    name = ""
""")
    plugins = load_plugins_from_dir(tmp_path)
    assert plugins == []


def test_load_plugins_sem_subclasse_skipped(tmp_path: Path) -> None:
    """Arquivo sem subclasse de Plugin eh ignorado."""
    (tmp_path / "sem_plugin.py").write_text("x = 42\n")
    plugins = load_plugins_from_dir(tmp_path)
    assert plugins == []


# ---------------------------------------------------------------------------
# Testes de PluginContext / ControllerProxy
# ---------------------------------------------------------------------------


def test_controller_proxy_delega_set_led() -> None:
    """ControllerProxy.set_led deve chamar IController.set_led."""
    ctrl = _mk_controller_mock()
    proxy = ControllerProxy(ctrl)
    proxy.set_led((255, 0, 128))
    ctrl.set_led.assert_called_once_with((255, 0, 128))


def test_controller_proxy_is_connected() -> None:
    ctrl = _mk_controller_mock()
    proxy = ControllerProxy(ctrl)
    assert proxy.is_connected is True


def test_make_plugin_context_retorna_instancia() -> None:
    ctrl = _mk_controller_mock()
    bus = EventBus()
    store = StateStore()
    ctx = make_plugin_context("meu_plugin", ctrl, bus, store)
    assert isinstance(ctx, PluginContext)
    assert ctx.controller is not None
    assert ctx.bus is not None
    assert ctx.store is not None
    assert ctx.log is not None


# ---------------------------------------------------------------------------
# Testes de on_load
# ---------------------------------------------------------------------------


def test_on_load_chamado_com_ctx(tmp_path: Path) -> None:
    """on_load deve ser chamado com PluginContext valido."""
    (tmp_path / "p.py").write_text(_plugin_py_content("p_load"))
    plugins = load_plugins_from_dir(tmp_path)
    assert len(plugins) == 1
    plugin = plugins[0]

    ctrl = _mk_controller_mock()
    bus = EventBus()
    store = StateStore()
    ctx = make_plugin_context(plugin.name, ctrl, bus, store)
    plugin.on_load(ctx)

    # Verifica que on_load foi executado (classe rastreia contador)
    assert plugin.__class__.chamadas_on_load >= 1


# ---------------------------------------------------------------------------
# Testes de PluginsSubsystem
# ---------------------------------------------------------------------------


def _mk_subsystem_with_plugin(plugin: Plugin) -> PluginsSubsystem:
    """Cria PluginsSubsystem com plugin ja registrado (sem start())."""
    ps = PluginsSubsystem()
    entry = _PluginEntry(plugin)
    ps._entries.append(entry)
    return ps


class _SimplePlugin(Plugin):
    """Plugin concreto minimo para testes."""

    name = "simples"
    profile_match: ClassVar[list[str]] = []
    ticks: ClassVar[int] = 0
    buttons: ClassVar[list[str]] = []
    battery_events: ClassVar[list[int]] = []

    def on_tick(self, state: Any) -> None:
        self.__class__.ticks += 1

    def on_button_down(self, name: str) -> None:
        self.__class__.buttons.append(name)

    def on_battery_change(self, pct: int) -> None:
        self.__class__.battery_events.append(pct)


def _reset_simple_plugin() -> None:
    _SimplePlugin.ticks = 0
    _SimplePlugin.buttons = []
    _SimplePlugin.battery_events = []


def test_tick_chama_on_tick() -> None:
    """tick() deve chamar on_tick em plugin sem profile_match."""
    _reset_simple_plugin()
    plugin = _SimplePlugin()
    ps = _mk_subsystem_with_plugin(plugin)
    ps.tick(_mk_state(), active_profile=None)
    assert _SimplePlugin.ticks == 1


def test_tick_respeita_profile_match() -> None:
    """Plugin com profile_match não recebe tick de perfil fora da lista."""
    _reset_simple_plugin()

    class PluginFiltrado(Plugin):
        name = "filtrado"
        profile_match: ClassVar[list[str]] = ["eldenring"]
        ticks_filtrado: ClassVar[int] = 0

        def on_tick(self, state: Any) -> None:
            self.__class__.ticks_filtrado += 1

    PluginFiltrado.ticks_filtrado = 0
    plugin = PluginFiltrado()
    ps = _mk_subsystem_with_plugin(plugin)

    # Perfil ativo diferente: não deve receber tick.
    ps.tick(_mk_state(), active_profile="darksouls")
    assert PluginFiltrado.ticks_filtrado == 0

    # Perfil ativo compativel: deve receber tick.
    ps.tick(_mk_state(), active_profile="eldenring")
    assert PluginFiltrado.ticks_filtrado == 1


def test_dispatch_button_down() -> None:
    """dispatch_button_down deve propagar para on_button_down do plugin."""
    _reset_simple_plugin()
    plugin = _SimplePlugin()
    ps = _mk_subsystem_with_plugin(plugin)
    ps.dispatch_button_down("cross")
    ps.dispatch_button_down("l1")
    assert _SimplePlugin.buttons == ["cross", "l1"]


def test_dispatch_battery_change() -> None:
    """dispatch_battery_change deve propagar para on_battery_change."""
    _reset_simple_plugin()
    plugin = _SimplePlugin()
    ps = _mk_subsystem_with_plugin(plugin)
    ps.dispatch_battery_change(42)
    assert _SimplePlugin.battery_events == [42]


def test_watchdog_desativa_plugin_apos_3_ticks_lentos() -> None:
    """Plugin cujo on_tick excede 5 ms por 3 vezes consecutivas deve ser desativado."""

    class PluginLento(Plugin):
        name = "lento"
        chamadas: int = 0

        def on_tick(self, state: Any) -> None:
            self.__class__.chamadas += 1
            time.sleep(0.010)  # 10 ms > 5 ms limite

    PluginLento.chamadas = 0
    plugin = PluginLento()
    entry = _PluginEntry(plugin)

    for _ in range(3):
        entry.call_on_tick(_mk_state())

    assert entry.disabled is True
    # Tick adicional apos desativacao: não deve chamar on_tick.
    PluginLento.chamadas_antes = PluginLento.chamadas
    entry.call_on_tick(_mk_state())
    assert PluginLento.chamadas == PluginLento.chamadas_antes


def test_watchdog_reset_apos_tick_rapido() -> None:
    """Contador de ticks lentos zera quando o hook executa dentro do limite."""

    contagem = {"rapidos": 0}

    class PluginHibrid(Plugin):
        name = "hibrid"

        def on_tick(self, state: Any) -> None:
            contagem["rapidos"] += 1

    entry = _PluginEntry(PluginHibrid())
    # Simula 2 ticks lentos (não chega ao threshold de 3).
    entry._slow_ticks = 2
    # Tick rapido deve zerar contador.
    entry.call_on_tick(_mk_state())
    assert entry._slow_ticks == 0
    assert entry.disabled is False


def test_list_plugins_retorna_descricao() -> None:
    """list_plugins deve retornar lista de dicts descritivos."""
    _reset_simple_plugin()
    plugin = _SimplePlugin()
    ps = _mk_subsystem_with_plugin(plugin)
    lista = ps.list_plugins()
    assert len(lista) == 1
    assert lista[0]["name"] == "simples"
    assert lista[0]["disabled"] is False
    assert "profile_match" in lista[0]


def test_plugin_desativado_nao_recebe_tick() -> None:
    """Plugin com entry.disabled=True não deve receber nenhum hook."""
    _reset_simple_plugin()
    plugin = _SimplePlugin()
    ps = _mk_subsystem_with_plugin(plugin)
    ps._entries[0].disabled = True

    ps.tick(_mk_state(), active_profile=None)
    ps.dispatch_button_down("cross")
    ps.dispatch_battery_change(10)

    assert _SimplePlugin.ticks == 0
    assert _SimplePlugin.buttons == []
    assert _SimplePlugin.battery_events == []


# ---------------------------------------------------------------------------
# Testes de integracao via loader + subsystem
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_carrega_plugins_e_chama_on_load(tmp_path: Path) -> None:
    """PluginsSubsystem.start() deve carregar plugins e chamar on_load."""
    (tmp_path / "p_start.py").write_text(_plugin_py_content("p_start"))

    ctrl = _mk_controller_mock()
    bus = EventBus()
    store = StateStore()
    cfg = MagicMock()
    cfg.plugins_enabled = True

    from hefesto.daemon.context import DaemonContext
    ctx = DaemonContext(controller=ctrl, bus=bus, store=store, config=cfg)

    ps = PluginsSubsystem()
    env_patch = {"HEFESTO_PLUGINS_DIR": str(tmp_path), "HEFESTO_PLUGINS_ENABLED": "1"}
    with patch.dict("os.environ", env_patch):
        await ps.start(ctx)

    assert len(ps._entries) == 1
    assert ps._entries[0].plugin.name == "p_start"


@pytest.mark.asyncio
async def test_stop_chama_on_unload(tmp_path: Path) -> None:
    """PluginsSubsystem.stop() deve chamar on_unload em todos os plugins."""
    unloaded: list[str] = []

    class PluginUnload(Plugin):
        name = "unload_teste"

        def on_unload(self) -> None:
            unloaded.append(self.name)

    ps = PluginsSubsystem()
    entry = _PluginEntry(PluginUnload())
    ps._entries.append(entry)
    await ps.stop()
    assert unloaded == ["unload_teste"]
