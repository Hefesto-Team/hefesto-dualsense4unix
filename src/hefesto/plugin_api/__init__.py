"""plugin_api — API publica para plugins do Hefesto.

Exports canonicos:
  - Plugin: ABC base para todos os plugins.
  - PluginContext: container de dependencias injetado em on_load().

Uso minimo em um plugin:

    from hefesto.plugin_api import Plugin, PluginContext

    class MeuPlugin(Plugin):
        name = "meu_plugin"

        def on_load(self, ctx: PluginContext) -> None:
            self.ctx = ctx

        def on_tick(self, state) -> None:
            ...
"""
from __future__ import annotations

from hefesto.plugin_api.context import PluginContext
from hefesto.plugin_api.plugin import Plugin

__all__ = ["Plugin", "PluginContext"]
