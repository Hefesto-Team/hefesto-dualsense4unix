"""PluginsSubsystem — carregamento e despacho de plugins Python.

Carrega plugins de ~/.config/hefesto/plugins/ (ou HEFESTO_PLUGINS_DIR),
chama os hooks no poll loop e subscreve eventos do bus.

Ciclo de vida:
  start(ctx):
    - load_plugins_from_dir() carrega todos os *.py do diretório.
    - on_load(ctx) e chamado em cada plugin com um PluginContext dedicado.
    - Subscreve BUTTON_DOWN e BATTERY_CHANGE para despacho síncrono via
      método tick() chamado pelo poll loop.

  tick(state, active_profile):
    - Chamado pelo _poll_loop() em lifecycle.py a cada tick.
    - Despacha on_tick(state) para plugins com profile_match vazio ou que
      contenham o perfil ativo.
    - Watchdog: cada hook tem time.monotonic antes/depois; se > 5 ms loga
      warning; 3x seguido desativa o plugin (flag local).

  stop():
    - Chama on_unload() em cada plugin ativo.

Configuração:
  - plugins_enabled (DaemonConfig): False por padrao. Opt-in explícito.
  - HEFESTO_PLUGINS_DIR: env var sobrescreve o diretório padrao.
  - HEFESTO_PLUGINS_ENABLED: "1" forca ativação (util em smoke/dev).

Aviso de seguranca:
    Plugins rodam com os mesmos privilegios do daemon. O usuário e
    responsavel pelo código instalado em ~/.config/hefesto/plugins/.
    Ver ADR-017.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto.core.controller import ControllerState
    from hefesto.daemon.context import DaemonContext
    from hefesto.daemon.lifecycle import DaemonConfig
    from hefesto.plugin_api.plugin import Plugin

logger = get_logger(__name__)

# Tempo máximo por hook antes de emitir warning (segundos).
_HOOK_WARN_MS = 5.0 / 1000.0

# Quantas vezes consecutivas acima do limite antes de desativar.
_HOOK_DISABLE_THRESH = 3


def _default_plugins_dir() -> Path:
    """Retorna o diretório padrão de plugins (~/.config/hefesto/plugins/)."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg_config) if xdg_config else Path.home() / ".config"
    return base / "hefesto" / "plugins"


class _PluginEntry:
    """Envolve um Plugin com estado de watchdog."""

    def __init__(self, plugin: Plugin) -> None:
        self.plugin = plugin
        self.disabled = False
        self._slow_ticks: int = 0

    def _call_hook(self, hook_name: str, *args: Any) -> None:
        """Chama um hook com watchdog de tempo."""
        if self.disabled:
            return
        hook = getattr(self.plugin, hook_name, None)
        if hook is None:
            return
        t0 = time.monotonic()
        try:
            hook(*args)
        except Exception as exc:
            logger.warning(
                "plugin_hook_excecao",
                plugin=self.plugin.name,
                hook=hook_name,
                erro=str(exc),
                exc_info=True,
            )
        elapsed = time.monotonic() - t0
        if elapsed > _HOOK_WARN_MS:
            self._slow_ticks += 1
            logger.warning(
                "plugin_hook_lento",
                plugin=self.plugin.name,
                hook=hook_name,
                elapsed_ms=round(elapsed * 1000, 2),
                slow_ticks=self._slow_ticks,
            )
            if self._slow_ticks >= _HOOK_DISABLE_THRESH:
                logger.error(
                    "plugin_desativado_por_lentidao",
                    plugin=self.plugin.name,
                    hook=hook_name,
                    slow_ticks=self._slow_ticks,
                )
                self.disabled = True
        else:
            self._slow_ticks = 0

    def call_on_tick(self, state: ControllerState) -> None:
        self._call_hook("on_tick", state)

    def call_on_button_down(self, name: str) -> None:
        self._call_hook("on_button_down", name)

    def call_on_battery_change(self, pct: int) -> None:
        self._call_hook("on_battery_change", pct)

    def call_on_profile_change(self, from_name: str | None, to_name: str) -> None:
        self._call_hook("on_profile_change", from_name, to_name)

    def call_on_unload(self) -> None:
        self._call_hook("on_unload")


class PluginsSubsystem:
    """Subsystem que gerencia o ciclo de vida dos plugins.

    Wire-up canônico (A-07):
      1. Slot no dataclass Daemon: _plugins_subsystem
      2. _start_plugins() chamado em Daemon.run() (após connect, antes de
         _stop_event.wait())
      3. tick() chamado no _poll_loop() apos cada read_state bem-sucedido
      4. stop() chamado no shutdown
    """

    name = "plugins"

    def __init__(self) -> None:
        self._entries: list[_PluginEntry] = []
        self._ctx: DaemonContext | None = None
        self._last_profile: str | None = None

    # ------------------------------------------------------------------
    # Subsystem Protocol
    # ------------------------------------------------------------------

    async def start(self, ctx: DaemonContext) -> None:
        """Carrega plugins do diretório configurado e chama on_load()."""
        from hefesto.plugin_api.context import make_plugin_context
        from hefesto.plugin_api.loader import load_plugins_from_dir

        self._ctx = ctx

        env_dir = os.environ.get("HEFESTO_PLUGINS_DIR", "")
        plugins_dir = Path(env_dir) if env_dir else _default_plugins_dir()

        logger.info("plugins_subsystem_starting", diretório=str(plugins_dir))

        plugins = load_plugins_from_dir(plugins_dir)
        for plugin in plugins:
            pctx = make_plugin_context(
                plugin_name=plugin.name,
                controller=ctx.controller,
                bus=ctx.bus,
                store=ctx.store,
            )
            entry = _PluginEntry(plugin)
            try:
                plugin.on_load(pctx)
                self._entries.append(entry)
                logger.info("plugin_on_load_ok", plugin=plugin.name)
            except Exception as exc:
                logger.warning(
                    "plugin_on_load_falhou",
                    plugin=plugin.name,
                    erro=str(exc),
                    exc_info=True,
                )

        logger.info("plugins_subsystem_started", total=len(self._entries))

    async def stop(self) -> None:
        """Chama on_unload() em todos os plugins ativos."""
        for entry in self._entries:
            entry.call_on_unload()
        logger.info("plugins_subsystem_stopped", total=len(self._entries))
        self._entries.clear()

    def is_enabled(self, config: DaemonConfig) -> bool:
        """Habilitado se plugins_enabled=True ou HEFESTO_PLUGINS_ENABLED=1."""
        env_force = os.environ.get("HEFESTO_PLUGINS_ENABLED", "0") == "1"
        cfg_enabled = bool(getattr(config, "plugins_enabled", False))
        return cfg_enabled or env_force

    # ------------------------------------------------------------------
    # Método de tick (chamado pelo poll loop)
    # ------------------------------------------------------------------

    def tick(self, state: ControllerState, active_profile: str | None = None) -> None:
        """Despacha on_tick() para plugins que correspondem ao perfil ativo.

        Deve ser chamado uma vez por iteração do poll loop, apos
        read_state() bem-sucedido.

        Args:
            state: snapshot imutavel do controle.
            active_profile: slug do perfil ativo (None se nenhum).
        """
        # Verificar mudanca de perfil
        if active_profile != self._last_profile:
            for entry in self._entries:
                if not entry.disabled:
                    entry.call_on_profile_change(self._last_profile, active_profile or "")
            self._last_profile = active_profile

        for entry in self._entries:
            if entry.disabled:
                continue
            pm = entry.plugin.profile_match
            if not pm or (active_profile and active_profile in pm):
                entry.call_on_tick(state)

    def dispatch_button_down(self, button_name: str) -> None:
        """Propaga BUTTON_DOWN para todos os plugins ativos."""
        for entry in self._entries:
            if not entry.disabled:
                entry.call_on_button_down(button_name)

    def dispatch_battery_change(self, pct: int) -> None:
        """Propaga BATTERY_CHANGE para todos os plugins ativos."""
        for entry in self._entries:
            if not entry.disabled:
                entry.call_on_battery_change(pct)

    # ------------------------------------------------------------------
    # Introspeccao (CLI)
    # ------------------------------------------------------------------

    def list_plugins(self) -> list[dict[str, Any]]:
        """Retorna lista de dicts descrevendo cada plugin carregado."""
        return [
            {
                "name": e.plugin.name,
                "profile_match": list(e.plugin.profile_match),
                "disabled": e.disabled,
                "classe": type(e.plugin).__name__,
            }
            for e in self._entries
        ]

    def reload(self, ctx: DaemonContext | None = None) -> int:
        """Descarrega todos os plugins e recarrega do disco.

        Returns:
            Numero de plugins carregados apos o reload.
        """
        import asyncio

        ctx_real = ctx or self._ctx
        if ctx_real is None:
            logger.warning("plugins_reload_sem_ctx")
            return 0

        # Unload sincrono
        for entry in self._entries:
            entry.call_on_unload()
        self._entries.clear()

        # Re-start sincrono (sem await — chamado do CLI)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.start(ctx_real))
        finally:
            loop.close()

        return len(self._entries)


__all__ = ["PluginsSubsystem"]
