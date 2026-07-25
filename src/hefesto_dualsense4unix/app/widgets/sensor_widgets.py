"""sensor_widgets.py — giroscópio, microfone e touchpad do card (S2).

Os três módulos de sensor que o guia de identidade pediu para a aba Status,
cada um com a mesma anatomia do resto da casa: as REGRAS moram em funções
puras (testáveis sem toolkit) e o desenho, num `Gtk.DrawingArea` que só
pinta o que a função pura decidiu. Ambiente sem GTK cai num stub que guarda
o mesmo estado — é o que deixa a suíte rodar em CI sem display.

Nenhum widget daqui agenda timer: quem os alimenta é o tick de 10 Hz que a
mixin de status JÁ tinha (o gate de timers do STATUS-02 continua valendo).

Cores conforme `novo-layout/GUIA_IMPLEMENTACAO.md` §4 — todas da paleta
Drácula, sem exceção (o `test_paleta_unica` reprova qualquer hex novo).
"""
from __future__ import annotations

import math
from typing import Any, Final

RGB = tuple[float, float, float]

# ---------------------------------------------------------------------------
# Paleta (guia §4). Hex para a documentação; float para o cairo.
# ---------------------------------------------------------------------------

COR_GYRO_X: Final[str] = "#ff5555"
COR_GYRO_Y: Final[str] = "#50fa7b"
COR_GYRO_Z: Final[str] = "#8be9fd"
COR_CONTORNO: Final[str] = "#44475a"
COR_TOQUE: Final[str] = "#8be9fd"
COR_TEXTO_FRACO: Final[str] = "#6272a4"
COR_TRILHA: Final[str] = "#2b2d3a"
COR_SELO_ATIVO_FUNDO: Final[str] = "#50fa7b"
COR_SELO_ATIVO_TEXTO: Final[str] = "#21222c"
COR_SELO_MUDO_FUNDO: Final[str] = "#2b2d3a"
COR_SELO_MUDO_TEXTO: Final[str] = "#6272a4"


def hex_para_rgb(valor: str) -> RGB:
    """``"#8be9fd"`` -> ``(0.545, 0.913, 0.992)`` para o cairo."""
    texto = valor.lstrip("#")
    return tuple(int(texto[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Regras puras
# ---------------------------------------------------------------------------

#: Fundo de escala das barras de giroscópio, em graus/s. O DualSense reporta
#: até ~2000°/s, mas girar o controle na mão fica bem abaixo de 500 — usar o
#: fundo de escala do sensor deixaria as barras praticamente imóveis. Valores
#: acima saturam a barra (é o que "no talo" significa), sem nunca vazar do
#: desenho.
ESCALA_GYRO_GRAUS_S: Final[float] = 500.0


def fracao_do_eixo(graus_por_s: float, escala: float = ESCALA_GYRO_GRAUS_S) -> float:
    """Valor em graus/s -> fração -1.0..+1.0 da barra bidirecional.

    O sinal é preservado (é ele que decide para que lado do centro a barra
    cresce) e o módulo satura em 1.0.
    """
    if escala <= 0:
        return 0.0
    return max(-1.0, min(1.0, graus_por_s / escala))


def texto_eixo(graus_por_s: float) -> str:
    """Rótulo numérico de um eixo, em largura FIXA.

    Campo fixo pelo mesmo motivo do `_XY_MARKUP` dos sticks
    (BUG-STATUS-LABEL-REFLOW-01): a 10 Hz, um texto que muda de largura ao
    cruzar dígitos faz o painel inteiro "respirar".
    """
    return f"{graus_por_s:>+7.1f}"


def selo_mic(muted: bool | None) -> tuple[str, str, str] | None:
    """``(texto, fundo, cor_do_texto)`` do selo do microfone; None = sem selo.

    ``None`` quando o estado de mute ainda não foi lido: o selo espera em
    vez de afirmar "ATIVO" para um microfone que pode estar mudo.
    """
    if muted is None:
        return None
    if muted:
        return ("MUDO", COR_SELO_MUDO_FUNDO, COR_SELO_MUDO_TEXTO)
    return ("ATIVO", COR_SELO_ATIVO_FUNDO, COR_SELO_ATIVO_TEXTO)


def texto_toques(quantidade: int) -> str:
    """Rótulo do touchpad: "sem toque" ou "N toque"/"N toques"."""
    if quantidade <= 0:
        return "sem toque"
    if quantidade == 1:
        return "1 toque"
    return f"{quantidade} toques"


def posicao_normalizada(
    x: int, y: int, largura: int, altura: int
) -> tuple[float, float]:
    """Coordenada absoluta do kernel -> fração 0.0..1.0 do retângulo.

    Largura/altura chegam do próprio payload (o kernel é quem declara os
    limites) — hardcodar 1920x1080 aqui mentiria no dia em que um modelo
    novo mudasse a resolução do touchpad.
    """
    fx = x / largura if largura > 0 else 0.0
    fy = y / altura if altura > 0 else 0.0
    return (max(0.0, min(1.0, fx)), max(0.0, min(1.0, fy)))


# ---------------------------------------------------------------------------
# Resolução condicional de GTK (padrão da casa: real + stub)
# ---------------------------------------------------------------------------

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    _GTK_DISPONIVEL = all(
        hasattr(Gtk, attr) for attr in ("DrawingArea", "Align")
    )
except (ImportError, ValueError):
    _GTK_DISPONIVEL = False


#: Altura de uma linha de eixo do giroscópio, em px.
_LINHA_GYRO_PX: Final[int] = 13
#: Largura reservada à letra do eixo e ao número (campo fixo — sem reflow).
_ROTULO_GYRO_PX: Final[int] = 12
_VALOR_GYRO_PX: Final[int] = 54
#: Tamanho do painel do touchpad (proporção 16:9 do sensor real).
_TOUCHPAD_PX: Final[tuple[int, int]] = (88, 50)
#: Medidor do mic: barras verticais, como o guia pediu.
_MIC_PX: Final[tuple[int, int]] = (78, 22)
_MIC_BARRAS: Final[int] = 13


if _GTK_DISPONIVEL:

    class GyroBars(Gtk.DrawingArea):  # type: ignore[misc]
        """Três barras horizontais bidirecionais (X/Y/Z) com origem no centro.

        ``set_valores(x, y, z)`` em graus/s; ``limpar()`` volta ao repouso.
        Redesenha só quando algum eixo muda de verdade — a 10 Hz, repintar
        três barras iguais seria trabalho puro de GPU.
        """

        def __init__(self) -> None:
            super().__init__()
            self._valores: tuple[float, float, float] = (0.0, 0.0, 0.0)
            self.set_size_request(-1, _LINHA_GYRO_PX * 3 + 4)
            self.connect("draw", self._on_draw)

        def set_valores(self, x: float, y: float, z: float) -> None:
            novos = (float(x), float(y), float(z))
            if novos != self._valores:
                self._valores = novos
                self.queue_draw()

        def limpar(self) -> None:
            self.set_valores(0.0, 0.0, 0.0)

        def _on_draw(self, _widget: Any, ctx: Any) -> bool:
            largura = self.get_allocated_width()
            ctx.select_font_face("monospace")
            ctx.set_font_size(9)
            cores = (COR_GYRO_X, COR_GYRO_Y, COR_GYRO_Z)
            trilha = hex_para_rgb(COR_TRILHA)
            contorno = hex_para_rgb(COR_CONTORNO)
            fraco = hex_para_rgb(COR_TEXTO_FRACO)
            inicio_barra = _ROTULO_GYRO_PX
            fim_barra = max(inicio_barra + 10, largura - _VALOR_GYRO_PX)
            meio = (inicio_barra + fim_barra) / 2
            metade = (fim_barra - inicio_barra) / 2

            for indice, (letra, cor_hex) in enumerate(zip("XYZ", cores, strict=True)):
                topo = indice * _LINHA_GYRO_PX + 2
                centro_y = topo + _LINHA_GYRO_PX / 2 - 1

                ctx.set_source_rgb(*fraco)
                ctx.move_to(0, centro_y + 3)
                ctx.show_text(letra)

                # Trilha + marca do zero: sem elas, uma barra vazia e uma
                # barra ausente ficariam idênticas na tela.
                ctx.set_source_rgb(*trilha)
                ctx.rectangle(inicio_barra, topo + 2, fim_barra - inicio_barra, 7)
                ctx.fill()
                ctx.set_source_rgb(*contorno)
                ctx.set_line_width(1)
                ctx.move_to(meio + 0.5, topo + 1)
                ctx.line_to(meio + 0.5, topo + 10)
                ctx.stroke()

                fracao = fracao_do_eixo(self._valores[indice])
                comprimento = metade * fracao
                if abs(comprimento) >= 1.0:
                    ctx.set_source_rgb(*hex_para_rgb(cor_hex))
                    ctx.rectangle(
                        meio if comprimento > 0 else meio + comprimento,
                        topo + 2,
                        abs(comprimento),
                        7,
                    )
                    ctx.fill()

                ctx.set_source_rgb(*fraco)
                ctx.move_to(fim_barra + 4, centro_y + 3)
                ctx.show_text(texto_eixo(self._valores[indice]))
            return False

    class MicMeter(Gtk.DrawingArea):  # type: ignore[misc]
        """Medidor de nível do microfone em barras verticais (guia §4)."""

        def __init__(self) -> None:
            super().__init__()
            self._nivel = 0.0
            self.set_size_request(*_MIC_PX)
            self.connect("draw", self._on_draw)

        def set_nivel(self, nivel: float) -> None:
            valor = max(0.0, min(1.0, float(nivel)))
            # Quantiza na resolução do próprio desenho: variação menor que
            # uma barra não muda um pixel, e repintar por ela seria puro
            # desperdício a 10 Hz.
            if round(valor * _MIC_BARRAS) != round(self._nivel * _MIC_BARRAS):
                self._nivel = valor
                self.queue_draw()

        def _on_draw(self, _widget: Any, ctx: Any) -> bool:
            largura = self.get_allocated_width()
            altura = self.get_allocated_height()
            passo = largura / _MIC_BARRAS
            acesas = round(self._nivel * _MIC_BARRAS)
            trilha = hex_para_rgb(COR_TRILHA)
            cheia = hex_para_rgb(COR_TOQUE)
            for indice in range(_MIC_BARRAS):
                # Barras crescem em altura da esquerda para a direita: dá
                # forma de medidor mesmo sem cor, para quem não distingue
                # aceso de apagado.
                fracao_altura = 0.35 + 0.65 * (indice / max(1, _MIC_BARRAS - 1))
                h = altura * fracao_altura
                ctx.set_source_rgb(*(cheia if indice < acesas else trilha))
                ctx.rectangle(indice * passo, altura - h, max(1.0, passo - 2), h)
                ctx.fill()
            return False

    class TouchpadView(Gtk.DrawingArea):  # type: ignore[misc]
        """Retângulo do touchpad com o ponto de toque (guia §4)."""

        def __init__(self) -> None:
            super().__init__()
            self._toque: tuple[float, float] | None = None
            self.set_size_request(*_TOUCHPAD_PX)
            self.connect("draw", self._on_draw)

        def set_toque(self, ponto: tuple[float, float] | None) -> None:
            if ponto != self._toque:
                self._toque = ponto
                self.queue_draw()

        def _on_draw(self, _widget: Any, ctx: Any) -> bool:
            largura = self.get_allocated_width()
            altura = self.get_allocated_height()
            ctx.set_source_rgb(*hex_para_rgb(COR_CONTORNO))
            ctx.set_line_width(1)
            ctx.rectangle(0.5, 0.5, largura - 1, altura - 1)
            ctx.stroke()
            if self._toque is None:
                return False
            fx, fy = self._toque
            px = 2 + fx * (largura - 4)
            py = 2 + fy * (altura - 4)
            cor = hex_para_rgb(COR_TOQUE)
            # Halo primeiro, ponto por cima: é o "círculo com brilho" do guia.
            ctx.set_source_rgba(*cor, 0.28)
            ctx.arc(px, py, 7, 0, 2 * math.pi)
            ctx.fill()
            ctx.set_source_rgb(*cor)
            ctx.arc(px, py, 3.5, 0, 2 * math.pi)
            ctx.fill()
            return False

else:

    class GyroBars:  # type: ignore[no-redef]
        """Stub sem GTK: guarda os valores para as asserções de contrato."""

        def __init__(self) -> None:
            self._valores: tuple[float, float, float] = (0.0, 0.0, 0.0)

        def set_valores(self, x: float, y: float, z: float) -> None:
            self._valores = (float(x), float(y), float(z))

        def limpar(self) -> None:
            self.set_valores(0.0, 0.0, 0.0)

        def set_size_request(self, *_args: object) -> None:
            """No-op no stub."""

        def show(self) -> None:
            """No-op no stub."""

    class MicMeter:  # type: ignore[no-redef]
        """Stub sem GTK do medidor de nível."""

        def __init__(self) -> None:
            self._nivel = 0.0

        def set_nivel(self, nivel: float) -> None:
            self._nivel = max(0.0, min(1.0, float(nivel)))

        def set_size_request(self, *_args: object) -> None:
            """No-op no stub."""

        def show(self) -> None:
            """No-op no stub."""

    class TouchpadView:  # type: ignore[no-redef]
        """Stub sem GTK do painel de touchpad."""

        def __init__(self) -> None:
            self._toque: tuple[float, float] | None = None

        def set_toque(self, ponto: tuple[float, float] | None) -> None:
            self._toque = ponto

        def set_size_request(self, *_args: object) -> None:
            """No-op no stub."""

        def show(self) -> None:
            """No-op no stub."""


__all__ = [
    "COR_GYRO_X",
    "COR_GYRO_Y",
    "COR_GYRO_Z",
    "ESCALA_GYRO_GRAUS_S",
    "GyroBars",
    "MicMeter",
    "TouchpadView",
    "fracao_do_eixo",
    "hex_para_rgb",
    "posicao_normalizada",
    "selo_mic",
    "texto_eixo",
    "texto_toques",
]
