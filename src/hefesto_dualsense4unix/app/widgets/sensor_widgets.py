"""sensor_widgets.py — giroscópio, microfone, touchpad, lightbar e alto-falante.

Os módulos de sensor que o guia de identidade pediu para a aba Status, cada
um com a mesma anatomia do resto da casa: as REGRAS moram em funções puras
(testáveis sem toolkit) e o desenho, num `Gtk.DrawingArea` que só pinta o que
a função pura decidiu. Ambiente sem GTK cai num stub que guarda o mesmo
estado — é o que deixa a suíte rodar em CI sem display.

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
#: LEGIBILIDADE-01 — estes dois eram `#6272a4` (@comment), que é cor de BORDA:
#: como TEXTO ele reprova o WCAG AA sobre qualquer fundo da interface. Aqui
#: doía duas vezes, porque nenhum dos dois passa pelo CSS (um é desenhado em
#: Cairo, o outro é markup de Pango) e o teste de contraste do tema não os
#: enxerga: os números do giroscópio davam 3,03:1 sobre o card e o selo MUDO,
#: 2,85:1 sobre a trilha — o pior par da interface inteira, na palavra que diz
#: se o microfone está aberto. `@text_soft` dá 8,89:1 e 8,51:1.
COR_TEXTO_FRACO: Final[str] = "#c8ccda"
COR_TRILHA: Final[str] = "#2b2d3a"
COR_SELO_ATIVO_FUNDO: Final[str] = "#50fa7b"
COR_SELO_ATIVO_TEXTO: Final[str] = "#21222c"
COR_SELO_MUDO_FUNDO: Final[str] = "#2b2d3a"
COR_SELO_MUDO_TEXTO: Final[str] = "#c8ccda"

#: Faixas de amplitude do medidor de microfone (mockup `Telas Hefesto.dc.html`,
#: `micBars`): pico em verde, fala em ciano, silêncio no cinza do contorno.
COR_MIC_PICO: Final[str] = "#50fa7b"
COR_MIC_FALA: Final[str] = "#8be9fd"
COR_MIC_SILENCIO: Final[str] = "#44475a"


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


#: Quantas amostras o medidor de microfone mostra ao mesmo tempo (mockup).
MIC_AMOSTRAS: Final[int] = 14

#: Piso da altura de uma barra do medidor. Sem ele, silêncio absoluto apagaria
#: o medidor inteiro e ficaria idêntico a "não estou medindo" — que agora é um
#: estado DESENHADO (`MicMeter.set_inativo`), e não mais o sumiço do módulo.
#: Com o piso, silêncio é uma linha baixa e contínua: dá para ver que o
#: medidor está vivo e não tem nada entrando.
MIC_PISO_BARRA: Final[float] = 0.08


def cor_da_barra_do_mic(amplitude: float) -> str:
    """Cor de UMA barra do medidor, pela amplitude DAQUELA amostra.

    Três faixas (mockup `micBars`): acima de 60% é pico (verde), acima de 30%
    é fala (ciano), o resto é o cinza de silêncio. A cor acompanha a barra,
    não o nível global — é o que faz o pico aparecer no instante em que
    acontece, em vez de nunca (a escada fixa antiga só acendia mais barras da
    MESMA cor).
    """
    if amplitude > 0.60:
        return COR_MIC_PICO
    if amplitude > 0.30:
        return COR_MIC_FALA
    return COR_MIC_SILENCIO


def historico_deslizante(
    historico: tuple[float, ...], amostra: float, tamanho: int = MIC_AMOSTRAS
) -> tuple[float, ...]:
    """Empurra ``amostra`` na direita e descarta a mais velha da esquerda.

    O medidor é uma janela do PASSADO RECENTE: a altura de cada barra é uma
    amostra de amplitude, e o conjunto forma a onda que anda para a esquerda.
    Histórico curto demais (ou longo demais) não é problema: a função sempre
    devolve exatamente ``tamanho`` amostras, completando com zeros à esquerda.
    """
    if tamanho <= 0:
        return ()
    valor = max(0.0, min(1.0, float(amostra)))
    janela = list(historico)[-(tamanho - 1) :] if tamanho > 1 else []
    faltam = (tamanho - 1) - len(janela)
    return tuple([0.0] * faltam + janela + [valor])


def fracao_do_volume(volume: int) -> float:
    """Volume bruto 0-255 do alto-falante -> fração 0.0-1.0 da barra."""
    return max(0.0, min(1.0, volume / 255))


def texto_volume(volume: int, muted: bool | None) -> str:
    """Rótulo do alto-falante: "mudo" ou a porcentagem do volume.

    ``muted`` None = o daemon mandou volume mas não mandou mute; o rótulo
    mostra só a porcentagem em vez de cravar que o som está saindo.
    """
    if muted:
        return "mudo"
    return f"{round(fracao_do_volume(volume) * 100)} %"


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
_LINHA_GYRO_PX: Final[int] = 12
#: Largura reservada à letra do eixo e ao número (campo fixo — sem reflow).
_ROTULO_GYRO_PX: Final[int] = 12
_VALOR_GYRO_PX: Final[int] = 54
#: Corpo dos rótulos do giroscópio (a letra do eixo e o número), em px.
#:
#: LEGIBILIDADE-01 — era o MENOR texto da interface: 9,0px, e fora do alcance
#: de qualquer ajuste de tema, porque quem desenha é o Cairo, que não passa
#: nem pelo CSS nem pelo Pango. O degrau subiu para o piso da escala (11px) e
#: passou a acompanhar a escala global, somando o mesmo delta que o CSS.
#: A LINHA e a largura reservada ao número crescem junto: fonte maior numa
#: linha de altura fixa faria um eixo escrever por cima do outro.
_FONTE_GYRO_PX: Final[int] = 11
#: Quanto a largura reservada ao número cresce por px de escala. O campo tem 7
#: caracteres em mono ("+412.0"), e mono cresce ~0,6px de avanço por px de
#: corpo — 7 x 0,6 arredondado para cima.
_LARGURA_POR_PX_DE_ESCALA: Final[int] = 5
#: Tamanho do painel do touchpad (proporção 16:9 do sensor real). Encolheu de
#: 88x50 quando os cinco blocos passaram a dividir UMA linha só.
_TOUCHPAD_PX: Final[tuple[int, int]] = (76, 42)
#: Medidor do mic: 14 barras verticais de amplitude (mockup).
_MIC_PX: Final[tuple[int, int]] = (72, 26)
#: Barra da lightbar e barra de volume do alto-falante — a mesma pegada de
#: "faixa fina" da barra de LED do DualSense.
_LIGHTBAR_PX: Final[tuple[int, int]] = (60, 12)
_SPEAKER_PX: Final[tuple[int, int]] = (60, 12)


if _GTK_DISPONIVEL:
    # A escala de fonte da sessão. Mora em `app.theme`, o dono único do tema —
    # importado aqui dentro porque este ramo já exige GTK e o stub abaixo não
    # pode depender dele.
    from hefesto_dualsense4unix.app.theme import escala_fonte

    class GyroBars(Gtk.DrawingArea):  # type: ignore[misc]
        """Três barras horizontais bidirecionais (X/Y/Z) com origem no centro.

        ``set_valores(x, y, z)`` em graus/s; ``limpar()`` volta ao repouso.
        Redesenha só quando algum eixo muda de verdade — a 10 Hz, repintar
        três barras iguais seria trabalho puro de GPU.
        """

        def __init__(self) -> None:
            super().__init__()
            self._valores: tuple[float, float, float] = (0.0, 0.0, 0.0)
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
            inicio_barra = _ROTULO_GYRO_PX
            fim_barra = max(inicio_barra + 10, largura - self._valor_px)
            meio = (inicio_barra + fim_barra) / 2
            metade = (fim_barra - inicio_barra) / 2

            for indice, (letra, cor_hex) in enumerate(zip("XYZ", cores, strict=True)):
                topo = indice * self._linha_px + 2
                centro_y = topo + self._linha_px / 2 - 1

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
        """Onda de amplitude do microfone: 14 amostras deslizantes (mockup).

        A versão anterior era uma ESCADA FIXA: as barras tinham sempre as
        mesmas alturas e o nível só decidia QUANTAS acendiam — a forma nunca
        mudava e o verde de pico, que dependia de uma barra ultrapassar 60%,
        não aparecia nunca. Agora cada barra É uma amostra: a altura conta o
        que entrou naquele instante e a cor sai de :func:`cor_da_barra_do_mic`.

        Dois estados de desenho, e a diferença entre eles é o contrato desta
        casa (MIC-FAIXA-01):

        * **medindo** — as 14 barras, com o piso de :data:`MIC_PISO_BARRA`
          que faz o silêncio virar uma linha baixa e CONTÍNUA (dá para ver
          que o medidor está vivo e nada entrando);
        * **inativo** — só a trilha vazia e o contorno. Nasce assim. Sem
          medição, aquelas mesmas barras no piso diriam "silêncio" onde a
          verdade é "não estou medindo" — e é justamente o que a faixa do
          rodapé escreve por extenso ao lado.
        """

        def __init__(self) -> None:
            super().__init__()
            self._nivel = 0.0
            self._historico: tuple[float, ...] = (0.0,) * MIC_AMOSTRAS
            # Nasce INATIVO: nada foi medido ainda, e barras no piso antes da
            # primeira amostra seriam silêncio afirmado sem prova.
            self._inativo = True
            self.set_size_request(*_MIC_PX)
            self.connect("draw", self._on_draw)

        def set_nivel(self, nivel: float) -> None:
            """Empurra mais uma amostra na onda (a mais velha cai fora)."""
            valor = max(0.0, min(1.0, float(nivel)))
            self._nivel = valor
            self._historico = historico_deslizante(self._historico, valor)
            self._inativo = False
            self.queue_draw()

        def set_inativo(self) -> None:
            """Sem medição: a área continua na tela, vazia — e a onda vai junto.

            O widget NÃO é escondido: a faixa do microfone é permanente. O que
            some é o dado, porque não existe.
            """
            if not self._inativo or any(self._historico) or self._nivel:
                self._nivel = 0.0
                self._historico = (0.0,) * MIC_AMOSTRAS
                self._inativo = True
                self.queue_draw()

        def limpar(self) -> None:
            """Alias histórico de :meth:`set_inativo` (o mic sumiu)."""
            self.set_inativo()

        def _on_draw(self, _widget: Any, ctx: Any) -> bool:
            largura = self.get_allocated_width()
            altura = self.get_allocated_height()
            if self._inativo:
                # Trilha + contorno: o espaço do medidor fica desenhado como
                # espaço, sem uma única barra que possa ser lida como nível.
                ctx.set_source_rgb(*hex_para_rgb(COR_TRILHA))
                ctx.rectangle(0, 0, largura, altura)
                ctx.fill()
                ctx.set_source_rgb(*hex_para_rgb(COR_CONTORNO))
                ctx.set_line_width(1)
                ctx.rectangle(0.5, 0.5, largura - 1, altura - 1)
                ctx.stroke()
                return False
            passo = largura / MIC_AMOSTRAS
            for indice, amostra in enumerate(self._historico):
                fracao = max(MIC_PISO_BARRA, amostra)
                h = altura * fracao
                ctx.set_source_rgb(*hex_para_rgb(cor_da_barra_do_mic(amostra)))
                ctx.rectangle(indice * passo, altura - h, max(1.0, passo - 2), h)
                ctx.fill()
            return False

    class LightbarBar(Gtk.DrawingArea):  # type: ignore[misc]
        """Faixa horizontal com a cor CRUA da lightbar daquele controle.

        Cor crua de propósito (mesma decisão D8 do swatch do título): quem
        precisa de contraste é o TRAÇO da interface, não a amostra da cor —
        ajustar aqui mostraria uma cor que o controle não está emitindo.
        """

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
            # Trilha embaixo: com a lightbar apagada, a faixa continua
            # visível como faixa (apagada é um estado, não um sumiço).
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
                # Mudo mantém o DESENHO do volume (o valor não some ao mutar),
                # só troca a cor para o cinza de "não está saindo som".
                cor = COR_CONTORNO if self._muted else COR_TOQUE
                ctx.set_source_rgb(*hex_para_rgb(cor))
                ctx.rectangle(1, 1, max(0.0, (largura - 2) * self._fracao), altura - 2)
                ctx.fill()
            ctx.set_source_rgb(*hex_para_rgb(COR_CONTORNO))
            ctx.set_line_width(1)
            ctx.rectangle(0.5, 0.5, largura - 1, altura - 1)
            ctx.stroke()
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
        """Stub sem GTK do medidor de nível (guarda a onda deslizante)."""

        def __init__(self) -> None:
            self._nivel = 0.0
            self._historico: tuple[float, ...] = (0.0,) * MIC_AMOSTRAS
            self._inativo = True

        def set_nivel(self, nivel: float) -> None:
            self._nivel = max(0.0, min(1.0, float(nivel)))
            self._historico = historico_deslizante(self._historico, self._nivel)
            self._inativo = False

        def set_inativo(self) -> None:
            self._nivel = 0.0
            self._historico = (0.0,) * MIC_AMOSTRAS
            self._inativo = True

        def limpar(self) -> None:
            self.set_inativo()

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
    "COR_MIC_FALA",
    "COR_MIC_PICO",
    "COR_MIC_SILENCIO",
    "ESCALA_GYRO_GRAUS_S",
    "MIC_AMOSTRAS",
    "GyroBars",
    "LightbarBar",
    "MicMeter",
    "SpeakerBar",
    "TouchpadView",
    "cor_da_barra_do_mic",
    "fracao_do_eixo",
    "fracao_do_volume",
    "hex_para_rgb",
    "historico_deslizante",
    "posicao_normalizada",
    "selo_mic",
    "texto_eixo",
    "texto_toques",
    "texto_volume",
]
