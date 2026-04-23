"""Plugin de exemplo — lightbar em ciclo HSV (arco-iris).

Cicla as cores da lightbar ao longo do espectro HSV a cada tick.
Util para verificar que o sistema de plugins esta funcionando e
que os métodos de output do ControllerProxy operam corretamente.

Instalação:
    cp examples/plugins/lightbar_rainbow.py ~/.config/hefesto/plugins/

Ativação (em ~/.config/hefesto/config.toml ou env var):
    HEFESTO_PLUGINS_ENABLED=1 HEFESTO_PLUGINS_DIR=examples/plugins
"""
from __future__ import annotations

import contextlib
import math
import time
from typing import ClassVar

from hefesto.plugin_api import Plugin, PluginContext


def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    """Converte HSV (0-1 cada) para RGB (0-255 cada).

    Implementação pura, sem dependências externas.
    """
    if s == 0.0:
        c = int(v * 255)
        return (c, c, c)
    i = int(h * 6.0)
    f = (h * 6.0) - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    i = i % 6
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    return (int(r * 255), int(g * 255), int(b * 255))


class LightbarRainbowPlugin(Plugin):
    """Cicla a lightbar pelas cores do espectro HSV.

    - profile_match vazio → ativo independente do perfil.
    - Velocidade: 1 ciclo completo a cada 6 segundos.
    """

    name = "lightbar_rainbow"
    profile_match: ClassVar[list[str]] = []

    # Duracao de um ciclo completo em segundos.
    CYCLE_SEC: float = 6.0

    def on_load(self, ctx: PluginContext) -> None:
        """Guarda contexto e registra inicio do ciclo."""
        self.ctx = ctx
        self._start = time.monotonic()
        ctx.log.info("lightbar_rainbow_carregado")

    def on_tick(self, state) -> None:
        """Aplica a cor HSV correspondente ao momento atual."""
        elapsed = time.monotonic() - self._start
        hue = math.fmod(elapsed / self.CYCLE_SEC, 1.0)
        r, g, b = _hsv_to_rgb(hue, 1.0, 0.6)
        self.ctx.controller.set_led((r, g, b))

    def on_unload(self) -> None:
        """Restaura lightbar para apagado ao descarregar o plugin."""
        with contextlib.suppress(Exception):
            self.ctx.controller.set_led((0, 0, 0))
        self.ctx.log.info("lightbar_rainbow_descarregado")
