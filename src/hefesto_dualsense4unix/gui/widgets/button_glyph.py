"""button_glyph.py — widget GTK3 que exibe um glyph SVG de botao do DualSense.

Cada glyph possui duas variantes carregadas em memoria na inicialização:
  - padrão:  assets/glyphs/<nome>.svg      (tracos brancos #f8f8f2)
  - ativo:   assets/glyphs/<nome>_active.svg  (tracos roxos #bd93f9)

O widget alterna entre elas via `set_pressed(bool)`, acionando `queue_draw`.

Caminho dos assets resolvido por ordem de preferência:
  1. ~/.local/share/hefesto-dualsense4unix/glyphs/   (instalação via install.sh)
  2. assets/glyphs/                   (diretório do repo — ambiente dev)
"""
from __future__ import annotations

import pathlib
from typing import Any

# ---------------------------------------------------------------------------
# Mapa PT-BR — consumido por UI-STATUS-STICKS-REDESIGN-01
# ---------------------------------------------------------------------------
BUTTON_GLYPH_LABELS: dict[str, str] = {
    "cross": "Cruz",
    "circle": "Circulo",
    "square": "Quadrado",
    "triangle": "Triangulo",
    "dpad_up": "D-pad Cima",
    "dpad_down": "D-pad Baixo",
    "dpad_left": "D-pad Esquerda",
    "dpad_right": "D-pad Direita",
    "l1": "L1",
    "r1": "R1",
    "l2": "L2",
    "r2": "R2",
    "l3": "L3",
    "r3": "R3",
    "share": "Share",
    "options": "Options",
    "ps": "PS",
    "touchpad": "Touchpad",
    "mic": "Microfone",
    "stick_l": "Analogico Esquerdo",
    "stick_r": "Analogico Direito",
}

# ---------------------------------------------------------------------------
# Resolucao de caminho dos glyphs
# ---------------------------------------------------------------------------


def _resolver_dir_glyphs() -> pathlib.Path:
    """Retorna o diretório de glyphs disponivel."""
    instalado = pathlib.Path.home() / ".local" / "share" / "hefesto-dualsense4unix" / "glyphs"
    if instalado.is_dir():
        return instalado
    # Dev: caminho relativo ao pacote (src/hefesto_dualsense4unix/gui/widgets/ -> raiz/assets/glyphs/)  # noqa: E501
    repo_root = pathlib.Path(__file__).parent.parent.parent.parent.parent
    dev = repo_root / "assets" / "glyphs"
    if dev.is_dir():
        return dev
    raise FileNotFoundError(
        f"Diretório de glyphs não encontrado em '{instalado}' nem em '{dev}'."
    )


GLYPHS_DIR: pathlib.Path | None
try:
    GLYPHS_DIR = _resolver_dir_glyphs()
except FileNotFoundError:
    GLYPHS_DIR = None


# ---------------------------------------------------------------------------
# ButtonGlyph
# ---------------------------------------------------------------------------

try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import Gdk, GdkPixbuf, Gtk

    _GTK_DISPONIVEL = True
except (ImportError, ValueError):
    _GTK_DISPONIVEL = False


if _GTK_DISPONIVEL:

    class ButtonGlyph(Gtk.DrawingArea):  # type: ignore[misc]
        """Exibe um glyph SVG de botao do DualSense com estado pressionado.

        Uso::

            g = ButtonGlyph("cross", size=24)
            g.set_pressed(True)   # troca para variante ativa (roxo Dracula)

        Parametros
        ----------
        name:
            Nome do glyph sem extensão (ex: "cross", "circle", "l1").
        size:
            Dimensão quadrada em pixels logicos. Default: 24.
        tooltip_pt_br:
            Texto do tooltip em PT-BR. Se None, usa BUTTON_GLYPH_LABELS.
        """

        def __init__(
            self,
            name: str,
            size: int = 24,
            tooltip_pt_br: str | None = None,
        ) -> None:
            super().__init__()
            self._name = name
            self._size = size
            self._pressed = False
            self._pb_normal: GdkPixbuf.Pixbuf | None = None
            self._pb_active: GdkPixbuf.Pixbuf | None = None
            self._load_pixbuf_pair()
            self.set_size_request(size, size)
            self.connect("draw", self._on_draw)
            label = tooltip_pt_br or BUTTON_GLYPH_LABELS.get(name, name)
            self.set_tooltip_text(label)

        # ------------------------------------------------------------------
        # API publica
        # ------------------------------------------------------------------

        def set_pressed(self, pressed: bool) -> None:
            """Altera o estado pressionado e agenda redesenho."""
            if pressed != self._pressed:
                self._pressed = pressed
                self.queue_draw()

        @property
        def is_pressed(self) -> bool:
            """Retorna True se o glyph esta no estado pressionado."""
            return self._pressed

        # ------------------------------------------------------------------
        # Internos
        # ------------------------------------------------------------------

        def _load_pixbuf_pair(self) -> None:
            """Carrega os dois pixbufs (normal e ativo) do disco."""
            if GLYPHS_DIR is None:
                return
            self._pb_normal = self._carregar(f"{self._name}.svg")
            self._pb_active = self._carregar(f"{self._name}_active.svg")

        def _carregar(self, nome_arquivo: str) -> GdkPixbuf.Pixbuf | None:
            """Carrega um pixbuf SVG em escala 1:1 (size x size)."""
            if GLYPHS_DIR is None:
                return None
            caminho = str(GLYPHS_DIR / nome_arquivo)
            try:
                return GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    caminho, self._size, self._size, True
                )
            except Exception:
                return None

        def _on_draw(
            self,
            _widget: Gtk.DrawingArea,
            ctx: Any,  # cairo.Context — sem stubs oficiais
        ) -> bool:
            """Callback de desenho do widget."""
            pb = self._pb_active if self._pressed else self._pb_normal
            if pb is None:
                return False
            x_off = (self.get_allocated_width() - pb.get_width()) / 2
            y_off = (self.get_allocated_height() - pb.get_height()) / 2
            Gdk.cairo_set_source_pixbuf(ctx, pb, x_off, y_off)
            ctx.paint()
            return False

else:
    # Stub mínimo para ambientes sem GTK (testes, CI sem display).
    class ButtonGlyph:  # type: ignore[no-redef]
        """Stub de ButtonGlyph para ambientes sem GTK3."""

        def __init__(
            self,
            name: str,
            size: int = 24,
            tooltip_pt_br: str | None = None,
        ) -> None:
            self._name = name
            self._size = size
            self._pressed = False

        def set_pressed(self, pressed: bool) -> None:
            """Altera o estado pressionado."""
            if pressed != self._pressed:
                self._pressed = pressed
                self.queue_draw()

        @property
        def is_pressed(self) -> bool:
            """Retorna True se pressionado."""
            return self._pressed

        def queue_draw(self) -> None:
            """Solicita redesenho (no-op no stub)."""

        def set_size_request(self, *_args: object) -> None:
            """No-op no stub."""

        def set_tooltip_text(self, *_args: object) -> None:
            """No-op no stub."""
