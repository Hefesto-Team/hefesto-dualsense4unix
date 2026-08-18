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

# ---------------------------------------------------------------------------
# CARD-ÚNICO-01, entrega 3 — o rótulo vira marca d'água
# ---------------------------------------------------------------------------
#
# Pedido dela, literal, com o print anotado: *"L3 e R3 saem do X: e vão ficar
# no centro do desenho do analógico com transparência 70% e grande ao fundo"*.
#
# "Transparência 70%" é OPACIDADE 30% — é assim que ela descreve o efeito, e é
# o alpha que entra no `set_source_rgba`.
MARCA_DAGUA_ALPHA: float = 0.3

#: O corpo da letra, como FRAÇÃO do raio do círculo — nunca um literal em px.
#:
#: O card inteiro obedece `theme.escala_fonte()`, e o desenho do analógico
#: recebe seu tamanho do card (`STICK_SIZE_SINGLE`/`STICK_SIZE_COMPACT`, e o
#: card único é maior que o compacto). Um `set_font_size(28)` ficaria certo num
#: dos dois e errado no outro, e quebraria na primeira vez que ela mudasse a
#: escala. Derivando do raio ALOCADO, a marca acompanha os dois eixos de
#: variação de graça.
MARCA_DAGUA_FRACAO_DO_RAIO: float = 0.95


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

        def _desenhar_marca_dagua(
            self,
            ctx: object,
            cx: float,
            cy: float,
            raio: float,
            cor: tuple[float, float, float],
        ) -> None:
            """Pinta o rótulo ("L3"/"R3") grande e apagado, centrado.

            CARD-ÚNICO-01, entrega 3. O rótulo JÁ chegava aqui pelo
            construtor e não era desenhado — ele só existia para o `repr` e
            para o stub. Agora ele é o desenho de fundo, e a linha de valores
            do card perdeu o prefixo que o repetia.

            Centrar texto em Cairo não é `xalign`: mede-se o traçado com
            `text_extents` e desloca-se pela metade dele. Usar só a largura,
            ou ignorar o `x_bearing`, deixa a letra visivelmente fora do
            centro — e num desenho com uma cruz no meio, o erro salta.
            """
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
            # `show_text` deixa um PONTO CORRENTE no fim do glifo, na baseline.
            # O próximo `ctx.arc` da borda encontraria esse ponto e o Cairo o
            # LIGARIA ao início do arco com um segmento de reta — o `stroke`
            # seguinte pintava essa "barra quebrada" atravessando o círculo,
            # com a cor e a espessura do anel. Quem suja o caminho é quem
            # limpa: o estado do contexto sai daqui como entrou.
            ctx.new_path()  # type: ignore[attr-defined]

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

            # A marca d'água ("L3"/"R3"), grande e apagada, ATRÁS de tudo.
            #
            # A ordem de pintura é a entrega: ela é FUNDO. Desenhada depois da
            # cruz ou do ponto, cobriria justamente o que o widget existe para
            # mostrar — e num alpha de 0,3 o resultado não é "atrás", é "sujo".
            self._desenhar_marca_dagua(ctx, cx, cy, raio_externo, borda)

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
