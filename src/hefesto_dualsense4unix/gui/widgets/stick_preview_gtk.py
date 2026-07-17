"""stick_preview_gtk.py — widget GTK3 que exibe o estado de um stick analógico.

Desenha um circulo externo (borda) com um ponto interno que se move
proporcionalmente aos valores X/Y do stick (0-255, centro=128).

Tamanho recomendado: 120x120 pixels (via set_size_request).

STATUS-03 (tinting por controle): ``set_accent(rgb)`` pinta os traços
(borda, cruz e ponto) com a cor do lightbar do controle, ajustada por
``ensure_min_contrast`` — o comportamento clássico (roxo Drácula no L3)
fica intacto enquanto ``set_accent`` nunca for chamado.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from hefesto_dualsense4unix.utils.color_contrast import ensure_min_contrast

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
            self._accent: tuple[float, float, float] | None = None
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

        def set_accent(self, rgb: Sequence[int] | None) -> None:
            """Pinta os traços (borda/cruz/ponto) com a cor do controle.

            A cor é AJUSTADA por ``ensure_min_contrast`` (decisão D8: o
            swatch do card mostra a cor crua; os traços recebem a ajustada)
            — passar uma cor já legível é idempotente. Com accent ativo, o
            estado pressionado (L3/R3) realça em branco Drácula, que segue
            distinguível de qualquer accent. ``None`` restaura a paleta
            padrão (comportamento pré-STATUS-03). Aceita ``[r, g, b]`` do
            IPC ou tuple.
            """
            novo: tuple[float, float, float] | None
            if rgb is None:
                novo = None
            else:
                ar, ag, ab = ensure_min_contrast(rgb)
                novo = (ar / 255, ag / 255, ab / 255)
            if novo != self._accent:
                self._accent = novo
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

            # Cores efetivas dos traços: paleta clássica OU accent por
            # controle (STATUS-03). Com accent, o pressionado realça em
            # branco Drácula (distinguível de qualquer accent).
            if self._accent is None:
                borda = L3_COLOR if self._l3_pressed else BORDA_COLOR
                cor_ponto = L3_COLOR if self._l3_pressed else PONTO_NORMAL
            else:
                borda = PONTO_NORMAL if self._l3_pressed else self._accent
                cor_ponto = borda

            # Circulo externo (borda)
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
