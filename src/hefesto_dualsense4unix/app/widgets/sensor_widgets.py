"""sensor_widgets.py — giroscópio, microfone, touchpad, lightbar e alto-falante."""
from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any, Final

RGB = tuple[float, float, float]


COR_GYRO_X: Final[str] = "#ff5555"
COR_GYRO_Y: Final[str] = "#50fa7b"
COR_GYRO_Z: Final[str] = "#8be9fd"
COR_CONTORNO: Final[str] = "#44475a"
COR_TOQUE: Final[str] = "#8be9fd"
COR_TEXTO_FRACO: Final[str] = "#c8ccda"
COR_TRILHA: Final[str] = "#2b2d3a"
COR_SELO_ATIVO_FUNDO: Final[str] = "#50fa7b"
COR_SELO_ATIVO_TEXTO: Final[str] = "#21222c"
COR_SELO_MUDO_FUNDO: Final[str] = "#2b2d3a"
COR_SELO_MUDO_TEXTO: Final[str] = "#c8ccda"

COR_MIC_PICO: Final[str] = "#50fa7b"
COR_MIC_FALA: Final[str] = "#8be9fd"
COR_MIC_SILENCIO: Final[str] = "#44475a"

COR_RADIO_ENTRADA: Final[str] = "#bd93f9"
COR_RADIO_AUDIO: Final[str] = "#8be9fd"


def hex_para_rgb(valor: str) -> RGB:
    """``"#8be9fd"`` -> ``(0.545, 0.913, 0.992)`` para o cairo."""
    texto = valor.lstrip("#")
    return tuple(int(texto[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


#: Fundo de escala das barras de giroscópio, em graus/s. O DualSense reporta
ESCALA_GYRO_GRAUS_S: Final[float] = 500.0


def fracao_do_eixo(graus_por_s: float, escala: float = ESCALA_GYRO_GRAUS_S) -> float:
    """Valor em graus/s -> fração -1.0..+1.0 da barra bidirecional."""
    if escala <= 0:
        return 0.0
    return max(-1.0, min(1.0, graus_por_s / escala))


def texto_eixo(graus_por_s: float) -> str:
    """Rótulo numérico de um eixo, em largura FIXA."""
    return f"{graus_por_s:>+7.1f}"


#: `ESCALA_GYRO_GRAUS_S`, e o mesmo raciocínio: o sensor vai a ±4 g
ESCALA_ACCEL_G: Final[float] = 2.0


def texto_eixo_g(g: float) -> str:
    """Rótulo numérico de um eixo de acelerômetro, em largura FIXA."""
    return f"{g:>+7.2f}"


def selo_mic(muted: bool | None) -> tuple[str, str, str] | None:
    """``(texto, fundo, cor_do_texto)`` do selo do microfone; None = sem selo."""
    if muted is None:
        return None
    if muted:
        return ("MUDO", COR_SELO_MUDO_FUNDO, COR_SELO_MUDO_TEXTO)
    return ("ATIVO", COR_SELO_ATIVO_FUNDO, COR_SELO_ATIVO_TEXTO)


def fatias_da_barra(fracao_entrada: float, fracao_audio: float) -> tuple[float, float]:
    """As duas fatias do medidor de rádio, prontas para pintar."""
    entrada = max(0.0, min(1.0, float(fracao_entrada)))
    audio = max(0.0, min(1.0 - entrada, float(fracao_audio)))
    return entrada, audio


MIC_AMOSTRAS: Final[int] = 14

MIC_PISO_BARRA: Final[float] = 0.08


def cor_da_barra_do_mic(amplitude: float) -> str:
    """Cor de UMA barra do medidor, pela amplitude DAQUELA amostra."""
    if amplitude > 0.60:
        return COR_MIC_PICO
    if amplitude > 0.30:
        return COR_MIC_FALA
    return COR_MIC_SILENCIO


def historico_deslizante(
    historico: tuple[float, ...], amostra: float, tamanho: int = MIC_AMOSTRAS
) -> tuple[float, ...]:
    """Empurra ``amostra`` na direita e descarta a mais velha da esquerda."""
    if tamanho <= 0:
        return ()
    valor = max(0.0, min(1.0, float(amostra)))
    janela = list(historico)[-(tamanho - 1) :] if tamanho > 1 else []
    faltam = (tamanho - 1) - len(janela)
    return tuple([0.0] * faltam + janela + [valor])

from hefesto_dualsense4unix.core.speaker_scale import (  # noqa: E402
    fracao_do_volume,
    percentual_do_volume,
    volume_do_percentual,
)


def texto_volume(volume: int, muted: bool | None) -> str:
    """Rótulo do alto-falante: "Mudo" ou a porcentagem do volume."""
    if muted:
        return "Mudo"
    return f"{percentual_do_volume(volume)} %"


def texto_toques(quantidade: int) -> str:
    """Rótulo do touchpad: "Sem toque" ou "N toque"/"N toques"."""
    if quantidade <= 0:
        return "Sem toque"
    if quantidade == 1:
        return "1 toque"
    return f"{quantidade} toques"


def posicao_normalizada(
    x: int, y: int, largura: int, altura: int
) -> tuple[float, float]:
    """Coordenada absoluta do kernel -> fração 0.0..1.0 do retângulo."""
    fx = x / largura if largura > 0 else 0.0
    fy = y / altura if altura > 0 else 0.0
    return (max(0.0, min(1.0, fx)), max(0.0, min(1.0, fy)))


try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    _GTK_DISPONIVEL = all(
        hasattr(Gtk, attr) for attr in ("DrawingArea", "Align")
    )
except (ImportError, ValueError):
    _GTK_DISPONIVEL = False


_LINHA_GYRO_PX: Final[int] = 12
_ROTULO_GYRO_PX: Final[int] = 12
_VALOR_GYRO_PX: Final[int] = 54
_FONTE_GYRO_PX: Final[int] = 11
_LARGURA_POR_PX_DE_ESCALA: Final[int] = 5
_TOUCHPAD_PX: Final[tuple[int, int]] = (76, 42)
_MIC_PX: Final[tuple[int, int]] = (72, 26)
#: "faixa fina" da barra de LED do DualSense.
_LIGHTBAR_PX: Final[tuple[int, int]] = (60, 12)
_SPEAKER_PX: Final[tuple[int, int]] = (60, 12)
_RADIO_PX: Final[tuple[int, int]] = (120, 10)


if _GTK_DISPONIVEL:
    from hefesto_dualsense4unix.app.theme import escala_fonte

    class DesenhoElastico(Gtk.DrawingArea):  # type: ignore[misc]
        """`DrawingArea` com largura NATURAL maior que a mínima."""

        def __init__(self) -> None:
            super().__init__()
            self._largura_natural: int | None = None

        def definir_largura_natural(self, px: int | None) -> None:
            """Teto de crescimento em px; ``None`` volta ao natural = mínimo."""
            if px == self._largura_natural:
                return
            self._largura_natural = px
            self.queue_resize()

        def largura_natural(self) -> int | None:
            """O teto declarado (o que o card mandou), para medição e teste."""
            return self._largura_natural

        def do_get_preferred_width(self) -> tuple[int, int]:
            minimo, natural = Gtk.DrawingArea.do_get_preferred_width(self)
            if self._largura_natural is None:
                return (minimo, natural)
            return (minimo, max(natural, self._largura_natural))

    class GyroBars(Gtk.DrawingArea):  # type: ignore[misc]
        """Três barras horizontais bidirecionais (X/Y/Z) com origem no centro.

        ``set_valores(x, y, z)``; ``limpar()`` volta ao repouso. Redesenha só
        quando algum eixo muda de verdade — a 10 Hz, repintar três barras
        iguais seria trabalho puro de GPU.

        **Serve os DOIS sensores do node de motion** (ONDA-CONTROLES-04): sem
        argumento é o giroscópio de sempre, em graus/s; com
        ``escala=ESCALA_ACCEL_G, texto=texto_eixo_g`` é o acelerômetro, em g.
        O desenho é o mesmo porque o DADO é o mesmo — três eixos com sinal,
        origem no centro —, e o que muda entre eles é só o fundo de escala e o
        formato do número. Um segundo widget copiado seria a mesma pintura
        mantida em dois lugares.

        Os defaults deixam ``GyroBars()`` idêntico ao que era: nenhum dos
        chamadores do giro precisou mudar de linha.
        """

        def __init__(
            self,
            *,
            escala: float = ESCALA_GYRO_GRAUS_S,
            texto: Callable[[float], str] = texto_eixo,
        ) -> None:
            super().__init__()
            self._valores: tuple[float, float, float] = (0.0, 0.0, 0.0)
            self._escala = escala
            self._texto = texto
            delta = escala_fonte()
            self._fonte_px = _FONTE_GYRO_PX + delta
            self._linha_px = _LINHA_GYRO_PX + delta
            self._valor_px = _VALOR_GYRO_PX + delta * _LARGURA_POR_PX_DE_ESCALA
            self.set_size_request(-1, self._linha_px * 3 + 4)
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
            ctx.set_font_size(self._fonte_px)
            cores = (COR_GYRO_X, COR_GYRO_Y, COR_GYRO_Z)
            trilha = hex_para_rgb(COR_TRILHA)
            contorno = hex_para_rgb(COR_CONTORNO)
            fraco = hex_para_rgb(COR_TEXTO_FRACO)
            inicio_valor = _ROTULO_GYRO_PX
            inicio_barra = inicio_valor + self._valor_px
            fim_barra = max(inicio_barra + 10, largura)
            meio = (inicio_barra + fim_barra) / 2
            metade = (fim_barra - inicio_barra) / 2

            for indice, (letra, cor_hex) in enumerate(zip("XYZ", cores, strict=True)):
                topo = indice * self._linha_px + 2
                centro_y = topo + self._linha_px / 2 - 1

                ctx.set_source_rgb(*fraco)
                ctx.move_to(0, centro_y + 3)
                ctx.show_text(letra)

                ctx.set_source_rgb(*trilha)
                ctx.rectangle(inicio_barra, topo + 2, fim_barra - inicio_barra, 7)
                ctx.fill()
                ctx.set_source_rgb(*contorno)
                ctx.set_line_width(1)
                ctx.move_to(meio + 0.5, topo + 1)
                ctx.line_to(meio + 0.5, topo + 10)
                ctx.stroke()

                fracao = fracao_do_eixo(self._valores[indice], self._escala)
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
                ctx.move_to(inicio_valor, centro_y + 3)
                ctx.show_text(self._texto(self._valores[indice]))
            return False

    class MicMeter(DesenhoElastico):
        """Onda de amplitude do microfone: 14 amostras deslizantes (mockup)."""

        def __init__(self) -> None:
            super().__init__()
            self._nivel = 0.0
            self._historico: tuple[float, ...] = (0.0,) * MIC_AMOSTRAS
            self.set_size_request(*_MIC_PX)
            self.connect("draw", self._on_draw)

        def set_nivel(self, nivel: float) -> None:
            """Empurra mais uma amostra na onda (a mais velha cai fora)."""
            valor = max(0.0, min(1.0, float(nivel)))
            self._nivel = valor
            self._historico = historico_deslizante(self._historico, valor)
            self.queue_draw()

        def limpar(self) -> None:
            """Zera a onda — o mic sumiu e o traço dele não pode ficar na tela."""
            if any(self._historico) or self._nivel:
                self._nivel = 0.0
                self._historico = (0.0,) * MIC_AMOSTRAS
                self.queue_draw()

        def _on_draw(self, _widget: Any, ctx: Any) -> bool:
            largura = self.get_allocated_width()
            altura = self.get_allocated_height()
            passo = largura / MIC_AMOSTRAS
            for indice, amostra in enumerate(self._historico):
                fracao = max(MIC_PISO_BARRA, amostra)
                h = altura * fracao
                ctx.set_source_rgb(*hex_para_rgb(cor_da_barra_do_mic(amostra)))
                ctx.rectangle(indice * passo, altura - h, max(1.0, passo - 2), h)
                ctx.fill()
            return False

    class LightbarBar(Gtk.DrawingArea):  # type: ignore[misc]
        """Faixa horizontal com a cor CRUA da lightbar daquele controle."""

        def __init__(self) -> None:
            super().__init__()
            self._rgb: tuple[int, int, int] | None = None
            self.set_size_request(*_LIGHTBAR_PX)
            self.connect("draw", self._on_draw)

        def set_cor(self, rgb: tuple[int, int, int] | None) -> None:
            if rgb != self._rgb:
                self._rgb = rgb
                self.queue_draw()

        def _on_draw(self, _widget: Any, ctx: Any) -> bool:
            largura = self.get_allocated_width()
            altura = self.get_allocated_height()
            ctx.set_source_rgb(*hex_para_rgb(COR_TRILHA))
            ctx.rectangle(0, 0, largura, altura)
            ctx.fill()
            if self._rgb is not None:
                ctx.set_source_rgb(*(canal / 255 for canal in self._rgb))
                ctx.rectangle(1, 1, largura - 2, altura - 2)
                ctx.fill()
            ctx.set_source_rgb(*hex_para_rgb(COR_CONTORNO))
            ctx.set_line_width(1)
            ctx.rectangle(0.5, 0.5, largura - 1, altura - 1)
            ctx.stroke()
            return False

    class SpeakerBar(Gtk.DrawingArea):  # type: ignore[misc]
        """Barra de volume do alto-falante do controle (0-255 -> fração)."""

        def __init__(self) -> None:
            super().__init__()
            self._fracao = 0.0
            self._muted = False
            self.set_size_request(*_SPEAKER_PX)
            self.connect("draw", self._on_draw)

        def set_volume(self, fracao: float, muted: bool | None) -> None:
            valor = max(0.0, min(1.0, float(fracao)))
            mudo = bool(muted)
            if (valor, mudo) != (self._fracao, self._muted):
                self._fracao = valor
                self._muted = mudo
                self.queue_draw()

        def _on_draw(self, _widget: Any, ctx: Any) -> bool:
            largura = self.get_allocated_width()
            altura = self.get_allocated_height()
            ctx.set_source_rgb(*hex_para_rgb(COR_TRILHA))
            ctx.rectangle(0, 0, largura, altura)
            ctx.fill()
            if self._fracao > 0:
                cor = COR_CONTORNO if self._muted else COR_TOQUE
                ctx.set_source_rgb(*hex_para_rgb(cor))
                ctx.rectangle(1, 1, max(0.0, (largura - 2) * self._fracao), altura - 2)
                ctx.fill()
            ctx.set_source_rgb(*hex_para_rgb(COR_CONTORNO))
            ctx.set_line_width(1)
            ctx.rectangle(0.5, 0.5, largura - 1, altura - 1)
            ctx.stroke()
            return False

    class MedidorDeRadio(Gtk.DrawingArea):  # type: ignore[misc]
        """Barra de ocupação do rádio de UM adaptador Bluetooth — duas fatias."""

        def __init__(self) -> None:
            super().__init__()
            self._entrada = 0.0
            self._audio = 0.0
            self.set_size_request(*_RADIO_PX)
            self.connect("draw", self._on_draw)

        def set_ocupacao(self, fracao_entrada: float, fracao_audio: float) -> None:
            """Guarda as duas frações e repinta SÓ quando alguma mudou."""
            fatias = fatias_da_barra(fracao_entrada, fracao_audio)
            if fatias != (self._entrada, self._audio):
                self._entrada, self._audio = fatias
                self.queue_draw()

        def _on_draw(self, _widget: Any, ctx: Any) -> bool:
            largura = self.get_allocated_width()
            altura = self.get_allocated_height()
            ctx.set_source_rgb(*hex_para_rgb(COR_TRILHA))
            ctx.rectangle(0, 0, largura, altura)
            ctx.fill()
            util = max(0.0, largura - 2)
            fim_da_entrada = util * self._entrada
            if self._entrada > 0:
                ctx.set_source_rgb(*hex_para_rgb(COR_RADIO_ENTRADA))
                ctx.rectangle(1, 1, fim_da_entrada, altura - 2)
                ctx.fill()
            if self._audio > 0:
                ctx.set_source_rgb(*hex_para_rgb(COR_RADIO_AUDIO))
                ctx.rectangle(1 + fim_da_entrada, 1, util * self._audio, altura - 2)
                ctx.fill()
            ctx.set_source_rgb(*hex_para_rgb(COR_CONTORNO))
            ctx.set_line_width(1)
            ctx.rectangle(0.5, 0.5, largura - 1, altura - 1)
            ctx.stroke()
            return False

    class TouchpadView(DesenhoElastico):
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
            ctx.set_source_rgba(*cor, 0.28)
            ctx.arc(px, py, 7, 0, 2 * math.pi)
            ctx.fill()
            ctx.set_source_rgb(*cor)
            ctx.arc(px, py, 3.5, 0, 2 * math.pi)
            ctx.fill()
            return False

else:

    class DesenhoElastico:  # type: ignore[no-redef]
        """Stub sem GTK: guarda o teto de largura declarado pelo card."""

        def __init__(self) -> None:
            self._largura_natural: int | None = None

        def definir_largura_natural(self, px: int | None) -> None:
            self._largura_natural = px

        def largura_natural(self) -> int | None:
            return self._largura_natural

    class GyroBars:  # type: ignore[no-redef]
        """Stub sem GTK: guarda os valores para as asserções de contrato."""

        def __init__(
            self,
            *,
            escala: float = ESCALA_GYRO_GRAUS_S,
            texto: Callable[[float], str] = texto_eixo,
        ) -> None:
            self._valores: tuple[float, float, float] = (0.0, 0.0, 0.0)
            self._escala = escala
            self._texto = texto

        def set_valores(self, x: float, y: float, z: float) -> None:
            self._valores = (float(x), float(y), float(z))

        def limpar(self) -> None:
            self.set_valores(0.0, 0.0, 0.0)

        def set_size_request(self, *_args: object) -> None:
            """No-op no stub."""

        def show(self) -> None:
            """No-op no stub."""

    class MicMeter(DesenhoElastico):  # type: ignore[no-redef]
        """Stub sem GTK do medidor de nível (guarda a onda deslizante)."""

        def __init__(self) -> None:
            super().__init__()
            self._nivel = 0.0
            self._historico: tuple[float, ...] = (0.0,) * MIC_AMOSTRAS

        def set_nivel(self, nivel: float) -> None:
            self._nivel = max(0.0, min(1.0, float(nivel)))
            self._historico = historico_deslizante(self._historico, self._nivel)

        def limpar(self) -> None:
            self._nivel = 0.0
            self._historico = (0.0,) * MIC_AMOSTRAS

        def set_size_request(self, *_args: object) -> None:
            """No-op no stub."""

        def show(self) -> None:
            """No-op no stub."""

    class LightbarBar:  # type: ignore[no-redef]
        """Stub sem GTK da faixa da lightbar."""

        def __init__(self) -> None:
            self._rgb: tuple[int, int, int] | None = None

        def set_cor(self, rgb: tuple[int, int, int] | None) -> None:
            self._rgb = rgb

        def set_size_request(self, *_args: object) -> None:
            """No-op no stub."""

        def show(self) -> None:
            """No-op no stub."""

    class SpeakerBar:  # type: ignore[no-redef]
        """Stub sem GTK da barra de volume do alto-falante."""

        def __init__(self) -> None:
            self._fracao = 0.0
            self._muted = False

        def set_volume(self, fracao: float, muted: bool | None) -> None:
            self._fracao = max(0.0, min(1.0, float(fracao)))
            self._muted = bool(muted)

        def set_size_request(self, *_args: object) -> None:
            """No-op no stub."""

        def show(self) -> None:
            """No-op no stub."""

    class MedidorDeRadio:  # type: ignore[no-redef]
        """Stub sem GTK do medidor de ocupação do rádio."""

        def __init__(self) -> None:
            self._entrada = 0.0
            self._audio = 0.0

        def set_ocupacao(self, fracao_entrada: float, fracao_audio: float) -> None:
            self._entrada, self._audio = fatias_da_barra(fracao_entrada, fracao_audio)

        def set_size_request(self, *_args: object) -> None:
            """No-op no stub."""

        def set_hexpand(self, *_args: object) -> None:
            """No-op no stub."""

        def show(self) -> None:
            """No-op no stub."""

    class TouchpadView(DesenhoElastico):  # type: ignore[no-redef]
        """Stub sem GTK do painel de touchpad."""

        def __init__(self) -> None:
            super().__init__()
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
    "COR_MIC_FALA",
    "COR_MIC_PICO",
    "COR_MIC_SILENCIO",
    "COR_RADIO_AUDIO",
    "COR_RADIO_ENTRADA",
    "ESCALA_ACCEL_G",
    "ESCALA_GYRO_GRAUS_S",
    "MIC_AMOSTRAS",
    "DesenhoElastico",
    "GyroBars",
    "LightbarBar",
    "MedidorDeRadio",
    "MicMeter",
    "SpeakerBar",
    "TouchpadView",
    "cor_da_barra_do_mic",
    "fatias_da_barra",
    "fracao_do_eixo",
    "fracao_do_volume",
    "hex_para_rgb",
    "historico_deslizante",
    "percentual_do_volume",
    "posicao_normalizada",
    "selo_mic",
    "texto_eixo",
    "texto_eixo_g",
    "texto_toques",
    "texto_volume",
    "volume_do_percentual",
]
