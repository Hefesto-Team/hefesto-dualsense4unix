"""stick_preview_gtk.py — widget GTK3 que exibe o estado de um stick analógico.

Desenha um circulo externo (borda) com um ponto interno que se move
proporcionalmente aos valores X/Y do stick (0-255, centro=128).

Tamanho recomendado: 120x120 pixels (via set_size_request).
"""
from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Resolução condicional de GTK
# ---------------------------------------------------------------------------

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    _GTK_DISPONIVEL = True
except (ImportError, ValueError):
    _GTK_DISPONIVEL = False

MAX_ANALOG = 255
CENTER_STICK = 128
L3_COLOR = (0.741, 0.576, 0.976)   # roxo Drácula #bd93f9
BORDA_COLOR = (0.6, 0.6, 0.6)      # cinza claro
FUNDO_COLOR = (0.157, 0.165, 0.212)  # fundo Drácula #282a36
PONTO_NORMAL = (0.973, 0.973, 0.898)  # branco Drácula #f8f8e5


if _GTK_DISPONIVEL:

    class StickPreviewGtk(Gtk.DrawingArea):  # type: ignore[misc]
        """Widget GTK3 de preview de stick analógico 120x120.

        Uso::

            sp = StickPreviewGtk(label="L3")
            sp.set_size_request(120, 120)
            sp.update(x=200, y=80)        # move o ponto
            sp.set_l3_pressed(True)       # cor do ponto vira roxo Drácula
        """

        def __init__(self, label: str = "L") -> None:
            super().__init__()
            self._label = label
            self._x = CENTER_STICK
            self._y = CENTER_STICK
            self._l3_pressed = False
            self.set_size_request(120, 120)
            self.connect("draw", self._on_draw)

        # ------------------------------------------------------------------
        # API pública
        # ------------------------------------------------------------------

        def update(self, x: int, y: int) -> None:
            """Atualiza posição do stick e agenda redesenho."""
            x = max(0, min(MAX_ANALOG, x))
            y = max(0, min(MAX_ANALOG, y))
            if x != self._x or y != self._y:
                self._x = x
                self._y = y
                self.queue_draw()

        def set_l3_pressed(self, pressed: bool) -> None:
            """Define se o stick está sendo pressionado (L3/R3)."""
            if pressed != self._l3_pressed:
                self._l3_pressed = pressed
                self.queue_draw()

        # ------------------------------------------------------------------
        # Interno
        # ------------------------------------------------------------------

        def _on_draw(self, _widget: Gtk.DrawingArea, ctx: object) -> bool:
            """Callback de desenho cairo."""
            w = self.get_allocated_width()
            h = self.get_allocated_height()
            cx = w / 2
            cy = h / 2
            raio_externo = min(w, h) / 2 - 4

            # Fundo
            ctx.set_source_rgb(*FUNDO_COLOR)  # type: ignore[attr-defined]
            ctx.paint()  # type: ignore[attr-defined]

            # Circulo externo (borda)
            borda = L3_COLOR if self._l3_pressed else BORDA_COLOR
            ctx.set_source_rgb(*borda)  # type: ignore[attr-defined]
            ctx.arc(cx, cy, raio_externo, 0, 2 * math.pi)  # type: ignore[attr-defined]
            ctx.set_line_width(2)  # type: ignore[attr-defined]
            ctx.stroke()  # type: ignore[attr-defined]

            # Linhas de cruz no centro
            ctx.set_source_rgba(*borda, 0.35)  # type: ignore[attr-defined]
            ctx.set_line_width(1)  # type: ignore[attr-defined]
            ctx.move_to(cx - raio_externo * 0.7, cy)  # type: ignore[attr-defined]
            ctx.line_to(cx + raio_externo * 0.7, cy)  # type: ignore[attr-defined]
            ctx.stroke()  # type: ignore[attr-defined]
            ctx.move_to(cx, cy - raio_externo * 0.7)  # type: ignore[attr-defined]
            ctx.line_to(cx, cy + raio_externo * 0.7)  # type: ignore[attr-defined]
            ctx.stroke()  # type: ignore[attr-defined]

            # Ponto do stick
            fator_x = (self._x - CENTER_STICK) / CENTER_STICK
            fator_y = (self._y - CENTER_STICK) / CENTER_STICK
            px = cx + fator_x * raio_externo * 0.85
            py = cy + fator_y * raio_externo * 0.85

            cor_ponto = L3_COLOR if self._l3_pressed else PONTO_NORMAL
            ctx.set_source_rgb(*cor_ponto)  # type: ignore[attr-defined]
            ctx.arc(px, py, 6, 0, 2 * math.pi)  # type: ignore[attr-defined]
            ctx.fill()  # type: ignore[attr-defined]

            return False

else:

    class StickPreviewGtk:  # type: ignore[no-redef]
        """Stub para ambientes sem GTK3 (testes, CI sem display)."""

        def __init__(self, label: str = "L") -> None:
            self._label = label
            self._x = CENTER_STICK
            self._y = CENTER_STICK
            self._l3_pressed = False

        def set_size_request(self, *_args: object) -> None:
            """No-op no stub."""

        def update(self, x: int, y: int) -> None:
            """Atualiza posição (no-op no stub)."""
            self._x = x
            self._y = y

        def set_l3_pressed(self, pressed: bool) -> None:
            """Define pressionamento (no-op no stub)."""
            self._l3_pressed = pressed

        def queue_draw(self) -> None:
            """No-op no stub."""

        def show(self) -> None:
            """No-op no stub."""
