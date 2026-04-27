"""plugin_api — API publica para plugins do Hefesto - Dualsense4Unix.

Exports canonicos:
  - Plugin: ABC base para todos os plugins.
  - PluginContext: container de dependências injetado em on_load().

Uso mínimo em um plugin:

    from hefesto_dualsense4unix.plugin_api import Plugin, PluginContext

    class MeuPlugin(Plugin):
        name = "meu_plugin"

        def on_load(self, ctx: PluginContext) -> None:
            self.ctx = ctx

        def on_tick(self, state) -> None:
            ...
"""
from __future__ import annotations

from hefesto_dualsense4unix.plugin_api.context import PluginContext
from hefesto_dualsense4unix.plugin_api.plugin import Plugin

__all__ = ["Plugin", "PluginContext"]
