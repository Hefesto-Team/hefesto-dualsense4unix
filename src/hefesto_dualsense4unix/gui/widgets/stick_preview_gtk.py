"""stick_preview_gtk.py — widget GTK3 que exibe o estado de um stick analógico."""
from __future__ import annotations

import math
from collections.abc import Sequence

from hefesto_dualsense4unix.utils.color_contrast import ensure_min_contrast

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    _GTK_DISPONIVEL = True
except (ImportError, ValueError):
    _GTK_DISPONIVEL = False

MAX_ANALOG = 255
CENTER_STICK = 128
L3_COLOR = (0.741, 0.576, 0.976)
BORDA_COLOR = (0.6, 0.6, 0.6)
FUNDO_COLOR = (0.157, 0.165, 0.212)
PONTO_NORMAL = (0.973, 0.973, 0.898)

MARCA_DAGUA_ALPHA: float = 0.3

MARCA_DAGUA_FRACAO_DO_RAIO: float = 0.95


if _GTK_DISPONIVEL:

    class StickPreviewGtk(Gtk.DrawingArea):  # type: ignore[misc]
        """Widget GTK3 de preview de stick analógico 120x120."""

        def __init__(self, label: str = "L") -> None:
            super().__init__()
            self._label = label
            self._x = CENTER_STICK
            self._y = CENTER_STICK
            self._l3_pressed = False
            self._accent: tuple[float, float, float] | None = None
            self.set_size_request(120, 120)
            self.connect("draw", self._on_draw)


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

        def set_accent(self, rgb: Sequence[int] | None) -> None:
            """Pinta os traços (borda/cruz/ponto) com a cor do controle."""
            novo: tuple[float, float, float] | None
            if rgb is None:
                novo = None
            else:
                ar, ag, ab = ensure_min_contrast(rgb)
                novo = (ar / 255, ag / 255, ab / 255)
            if novo != self._accent:
                self._accent = novo
                self.queue_draw()


        def _desenhar_marca_dagua(
            self,
            ctx: object,
            cx: float,
            cy: float,
            raio: float,
            cor: tuple[float, float, float],
        ) -> None:
            """Pinta o rótulo ("L3"/"R3") grande e apagado, centrado."""
            if not self._label:
                return
            ctx.select_font_face("sans")  # type: ignore[attr-defined]
            ctx.set_font_size(raio * MARCA_DAGUA_FRACAO_DO_RAIO)  # type: ignore[attr-defined]
            ext = ctx.text_extents(self._label)  # type: ignore[attr-defined]
            ctx.set_source_rgba(*cor, MARCA_DAGUA_ALPHA)  # type: ignore[attr-defined]
            ctx.move_to(  # type: ignore[attr-defined]
                cx - ext.width / 2 - ext.x_bearing,
                cy - ext.height / 2 - ext.y_bearing,
            )
            ctx.show_text(self._label)  # type: ignore[attr-defined]
            ctx.new_path()  # type: ignore[attr-defined]

        def _on_draw(self, _widget: Gtk.DrawingArea, ctx: object) -> bool:
            """Callback de desenho cairo."""
            w = self.get_allocated_width()
            h = self.get_allocated_height()
            cx = w / 2
            cy = h / 2
            raio_externo = min(w, h) / 2 - 4

            ctx.set_source_rgb(*FUNDO_COLOR)  # type: ignore[attr-defined]
            ctx.paint()  # type: ignore[attr-defined]

            if self._accent is None:
                borda = L3_COLOR if self._l3_pressed else BORDA_COLOR
                cor_ponto = L3_COLOR if self._l3_pressed else PONTO_NORMAL
            else:
                borda = PONTO_NORMAL if self._l3_pressed else self._accent
                cor_ponto = borda

            self._desenhar_marca_dagua(ctx, cx, cy, raio_externo, borda)

            ctx.set_source_rgb(*borda)  # type: ignore[attr-defined]
            ctx.arc(cx, cy, raio_externo, 0, 2 * math.pi)  # type: ignore[attr-defined]
            ctx.set_line_width(2)  # type: ignore[attr-defined]
            ctx.stroke()  # type: ignore[attr-defined]

            ctx.set_source_rgba(*borda, 0.35)  # type: ignore[attr-defined]
            ctx.set_line_width(1)  # type: ignore[attr-defined]
            ctx.move_to(cx - raio_externo * 0.7, cy)  # type: ignore[attr-defined]
            ctx.line_to(cx + raio_externo * 0.7, cy)  # type: ignore[attr-defined]
            ctx.stroke()  # type: ignore[attr-defined]
            ctx.move_to(cx, cy - raio_externo * 0.7)  # type: ignore[attr-defined]
            ctx.line_to(cx, cy + raio_externo * 0.7)  # type: ignore[attr-defined]
            ctx.stroke()  # type: ignore[attr-defined]

            fator_x = (self._x - CENTER_STICK) / CENTER_STICK
            fator_y = (self._y - CENTER_STICK) / CENTER_STICK
            px = cx + fator_x * raio_externo * 0.85
            py = cy + fator_y * raio_externo * 0.85

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
            self._accent: tuple[float, float, float] | None = None

        def set_size_request(self, *_args: object) -> None:
            """No-op no stub."""

        def update(self, x: int, y: int) -> None:
            """Atualiza posição (no-op no stub)."""
            self._x = x
            self._y = y

        def set_l3_pressed(self, pressed: bool) -> None:
            """Define pressionamento (no-op no stub)."""
            self._l3_pressed = pressed

        def set_accent(self, rgb: Sequence[int] | None) -> None:
            """Define o accent dos traços (mesma normalização do widget real)."""
            if rgb is None:
                self._accent = None
            else:
                ar, ag, ab = ensure_min_contrast(rgb)
                self._accent = (ar / 255, ag / 255, ab / 255)

        def queue_draw(self) -> None:
            """No-op no stub."""

        def show(self) -> None:
            """No-op no stub."""
