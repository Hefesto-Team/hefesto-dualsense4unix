"""button_glyph.py — widget GTK3 que exibe um glyph SVG de botao do DualSense.

Cada glyph possui duas variantes carregadas em memoria na inicialização:
  - padrão:  assets/glyphs/<nome>.svg      (tracos brancos #f8f8f2)
  - ativo:   assets/glyphs/<nome>_active.svg  (tracos roxos #bd93f9)

O widget alterna entre elas via `set_pressed(bool)`, acionando `queue_draw`.

Caminho dos assets resolvido por ordem de preferência (BUG-DEB-GLYPHS-
PATH-RESOLVER-01: o .deb instala em /usr/share/, não em ~/.local/share/):
  1. ~/.local/share/hefesto-dualsense4unix/glyphs/    (install.sh nativo)
  2. <sys.prefix>/share/hefesto-dualsense4unix/glyphs/ (Flatpak: /app/share)
  3. /usr/share/hefesto-dualsense4unix/assets/glyphs/ (.deb / system-wide)
  4. assets/glyphs/                                   (diretório do repo)

STATUS-03 (tinting por controle): ``set_accent(rgb)`` troca a variante
ativa por uma tintada com a cor do lightbar do controle (ajustada por
``ensure_min_contrast``): o literal ``#bd93f9`` é substituído no TEXTO do
SVG (replace-all; há 1-4 ocorrências por arquivo) e o pixbuf é carregado
via ``GdkPixbuf.PixbufLoader`` com ``set_size``, lendo do ``GLYPHS_DIR``
resolvido — com CACHE por ``(nome, size, hex)``: trocar o accent nunca
recarrega por tick nem recria o widget.
"""
from __future__ import annotations

import contextlib
import pathlib
import sys
from collections.abc import Sequence
from typing import Any

from hefesto_dualsense4unix.utils.color_contrast import ensure_min_contrast, rgb_para_hex

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
    """Retorna o diretório de glyphs disponivel.

    Cobre 3 cenários de instalação. A ordem reflete preferência: usuário
    ganha de sistema (override pessoal); sistema ganha de dev fallback.
    """
    candidatos: list[pathlib.Path] = [
        # 1) install.sh nativo copia para ~/.local/share/
        pathlib.Path.home() / ".local" / "share" / "hefesto-dualsense4unix" / "glyphs",
        # 2) Flatpak: o manifesto instala em /app/share/...; sys.prefix=/app
        # dentro do sandbox. Nem ~/.local/share (home isolado) nem /usr/share
        # (runtime) resolvem lá — sem este candidato os glyphs somem no Flatpak.
        pathlib.Path(sys.prefix) / "share" / "hefesto-dualsense4unix" / "glyphs",
        # 3) .deb instala assets em /usr/share/hefesto-dualsense4unix/assets/
        pathlib.Path("/usr/share/hefesto-dualsense4unix/assets/glyphs"),
        # 4) Dev: caminho relativo ao pacote
        # (src/hefesto_dualsense4unix/gui/widgets/ -> raiz/assets/glyphs/)
        pathlib.Path(__file__).parent.parent.parent.parent.parent / "assets" / "glyphs",
    ]
    for cand in candidatos:
        if cand.is_dir():
            return cand
    raise FileNotFoundError(
        "Diretório de glyphs não encontrado em nenhum dos paths: "
        + ", ".join(str(p) for p in candidatos)
    )


GLYPHS_DIR: pathlib.Path | None
try:
    GLYPHS_DIR = _resolver_dir_glyphs()
except FileNotFoundError:
    GLYPHS_DIR = None


# ---------------------------------------------------------------------------
# Tinting da variante ativa (STATUS-03)
# ---------------------------------------------------------------------------

#: Literal presente nos 19 ``*_active.svg`` shipados (roxo Drácula).
_HEX_ATIVO_STOCK = "#bd93f9"

#: Cache de pixbufs tintados. A chave embute o caminho RESOLVIDO do SVG
#: (dir + nome — hermético quando GLYPHS_DIR muda em teste), o tamanho e o
#: hex ajustado: no máximo 1 carga de pixbuf por (nome, size, hex).
_PIXBUF_TINT_CACHE: dict[tuple[str, int, str], Any] = {}


def _tintar_svg(texto: str, hex_cor: str) -> str:
    """Substitui TODAS as ocorrências do literal stock pelo hex do accent."""
    return texto.replace(_HEX_ATIVO_STOCK, hex_cor).replace(
        _HEX_ATIVO_STOCK.upper(), hex_cor
    )


def limpar_cache_tinting() -> None:
    """Esvazia o cache de pixbufs tintados (higiene de testes)."""
    _PIXBUF_TINT_CACHE.clear()


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

    def _carregar_pixbuf_tintado(nome: str, size: int, hex_cor: str) -> Any:
        """Carrega a variante ativa tintada (caminho de MISS do cache).

        Lê SEMPRE do ``GLYPHS_DIR`` resolvido (módulo — funciona nos 4
        caminhos de resolução e é monkeypatchável em teste), tinta o texto
        do SVG e materializa via ``GdkPixbuf.PixbufLoader`` com
        ``set_size(size, size)``. Retorna None em qualquer falha (o widget
        cai na variante stock).
        """
        if GLYPHS_DIR is None:
            return None
        caminho = GLYPHS_DIR / f"{nome}_active.svg"
        try:
            texto = caminho.read_text(encoding="utf-8")
        except OSError:
            return None
        loader = None
        try:
            loader = GdkPixbuf.PixbufLoader()
            # set_size ANTES do write: pós size-prepared o pedido é ignorado.
            loader.set_size(size, size)
            loader.write(_tintar_svg(texto, hex_cor).encode("utf-8"))
            loader.close()
            return loader.get_pixbuf()
        except Exception:
            if loader is not None:
                with contextlib.suppress(Exception):
                    loader.close()
            return None

    def _pixbuf_tintado_cacheado(nome: str, size: int, hex_cor: str) -> Any:
        """Consulta o cache por (nome, size, hex); carrega só no MISS."""
        if GLYPHS_DIR is None:
            return None
        chave = (str(GLYPHS_DIR / f"{nome}_active.svg"), size, hex_cor)
        if chave in _PIXBUF_TINT_CACHE:
            return _PIXBUF_TINT_CACHE[chave]
        pixbuf = _carregar_pixbuf_tintado(nome, size, hex_cor)
        if pixbuf is not None:
            _PIXBUF_TINT_CACHE[chave] = pixbuf
        return pixbuf

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
            # STATUS-03: guarda a variante ativa stock (roxo Drácula) para
            # set_accent(None) restaurar sem reler o disco.
            self._pb_active_stock: GdkPixbuf.Pixbuf | None = self._pb_active
            self._accent_hex: str | None = None
            self.set_size_request(size, size)
            self.connect("draw", self._on_draw)
            # BUG-GLYPH-TOOLTIP-ORFAO-01: tooltip DESLIGADO de propósito. Sob
            # COSMIC+XWayland a janelinha de tooltip ficava PRESA na tela
            # (órfã, sobre o grid) após o hover — visto ao vivo em 2026-07-13.
            # O glyph é auto-evidente; o rótulo segue acessível ao leitor de
            # tela via accessible-name.
            label = tooltip_pt_br or BUTTON_GLYPH_LABELS.get(name, name)
            self.set_has_tooltip(False)
            with contextlib.suppress(Exception):
                self.get_accessible().set_name(label)

        # ------------------------------------------------------------------
        # API publica
        # ------------------------------------------------------------------

        def set_pressed(self, pressed: bool) -> None:
            """Altera o estado pressionado e agenda redesenho."""
            if pressed != self._pressed:
                self._pressed = pressed
                self.queue_draw()

        def set_accent(self, rgb: Sequence[int] | None) -> None:
            """Tinta a variante ativa com a cor do controle, sem recriar o widget.

            A cor é AJUSTADA por ``ensure_min_contrast`` (decisão D8: swatch
            cru, traços ajustados); o pixbuf tintado vem do cache por
            ``(nome, size, hex)`` — repetir cores NÃO relê SVG do disco.
            ``None`` restaura o roxo Drácula stock. Aceita ``[r, g, b]`` do
            IPC ou tuple.
            """
            hex_novo = (
                None if rgb is None else rgb_para_hex(ensure_min_contrast(rgb))
            )
            if hex_novo == self._accent_hex:
                return
            self._accent_hex = hex_novo
            if hex_novo is None:
                self._pb_active = self._pb_active_stock
            else:
                tintado = _pixbuf_tintado_cacheado(self._name, self._size, hex_novo)
                self._pb_active = (
                    tintado if tintado is not None else self._pb_active_stock
                )
            if self._pressed:
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
            self._accent_hex: str | None = None

        def set_pressed(self, pressed: bool) -> None:
            """Altera o estado pressionado."""
            if pressed != self._pressed:
                self._pressed = pressed
                self.queue_draw()

        def set_accent(self, rgb: Sequence[int] | None) -> None:
            """Registra o accent (mesma normalização do widget real)."""
            if rgb is None:
                self._accent_hex = None
            else:
                self._accent_hex = rgb_para_hex(ensure_min_contrast(rgb))

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
