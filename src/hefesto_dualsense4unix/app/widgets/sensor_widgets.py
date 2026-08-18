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
#: o medidor inteiro e ficaria idêntico a "não tenho microfone" — que é o
#: estado em que o módulo SOME. Com o piso, silêncio é uma linha baixa e
#: contínua: dá para ver que o medidor está vivo e não tem nada entrando.
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

#: A régua de volume do alto-falante mora em `core/speaker_scale.py`, e não
#: aqui. Ela é falada por TRÊS superfícies — a barra de leitura, o controle
#: deslizante e o comando `speaker volume` da linha de comando — e enquanto
#: viveu neste arquivo a linha de comando tinha uma cópia linear dela: os 60 %
#: da janela e o `speaker volume 60` mandavam valores diferentes para o mesmo
#: registrador. `app/widgets/` puxa GTK no import do pacote, então importá-la
#: daqui fazia um comando de terminal carregar a interface inteira.
#:
#: Reexportado com os mesmos nomes para o código de tela continuar lendo como
#: sempre leu. A curva medida, o método e as ressalvas estão lá.
from hefesto_dualsense4unix.core.speaker_scale import (  # noqa: E402
    fracao_do_volume,
    percentual_do_volume,
    volume_do_percentual,
)


def texto_volume(volume: int, muted: bool | None) -> str:
    """Rótulo do alto-falante: "Mudo" ou a porcentagem do volume.

    ``muted`` None = o daemon mandou volume mas não mandou mute; o rótulo
    mostra só a porcentagem em vez de cravar que o som está saindo.
    """
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

    class DesenhoElastico(Gtk.DrawingArea):  # type: ignore[misc]
        """`DrawingArea` com largura NATURAL maior que a mínima.

        CARD-OCUPA-01 — *"tem muito espaço vazio aqui, dava pra aumentar a
        largura do touchpad e lightbar e do microfone e alto falante pra
        ocuparem os espaços laterais vazios"*.

        Um `DrawingArea` nu tem natural IGUAL ao mínimo (o chain-up devolve
        ``(0, 0)`` e quem vira piso dos dois é o `set_size_request`), então ele
        fica parado no piso enquanto o card cresce até
        `LARGURA_CARD_ELASTICA` — era isso que sobrava como vão lateral na
        faixa. Aqui o mínimo continua exatamente o do `set_size_request` (o
        piso de largura do card não sobe um pixel) e só o NATURAL cresce.

        Quem faz o resto é a estrutura que a faixa já tem: os três blocos
        entram com ``expand=True, fill=False``, e nessa combinação o GtkBox
        aloca ``min(natural, fatia)``. Medido na bancada com três filhos de
        mínimo 180 e natural 360: 1400px de caixa dá 360 a cada um, 900px dá
        311, 800px dá 261 e 620px devolve os 180 do piso — o encolhimento é
        contínuo e nunca transborda, que é o que permite subir o natural sem
        tocar no mínimo da janela.
        """

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
            # ALINHA-DUAS-LINHAS-01 (01/08): o VALOR mudou de lado — ele agora
            # fica logo depois da letra do eixo, e a barra ocupa todo o resto.
            #
            # Por quê: com o desenho esticando até a metade direita da faixa
            # (640px na tela dela, contra 420 de antes), um valor ancorado na
            # BORDA DIREITA ficaria a mais de meio card do "X" que o nomeia —
            # a mesma queixa que `test_o_numero_do_giroscopio_fica_perto_do_
            # nome_do_eixo` levantou quando a barra era larga demais. Aquele
            # teste resolvia estreitando o desenho; isso deixou de ser opção
            # quando ela pediu o desenho esticado, e a resposta certa era mover
            # o número, não encolher a barra.
            #
            # Ganho de quebra: o par letra+número agora é uma coluna fixa à
            # esquerda, então os três valores ficam alinhados entre si em
            # qualquer largura — antes eles dançavam com o fim da barra.
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
                ctx.move_to(inicio_valor, centro_y + 3)
                ctx.show_text(texto_eixo(self._valores[indice]))
            return False

    class MicMeter(DesenhoElastico):
        """Onda de amplitude do microfone: 14 amostras deslizantes (mockup).

        A versão anterior era uma ESCADA FIXA: as barras tinham sempre as
        mesmas alturas e o nível só decidia QUANTAS acendiam — a forma nunca
        mudava e o verde de pico, que dependia de uma barra ultrapassar 60%,
        não aparecia nunca. Agora cada barra É uma amostra: a altura conta o
        que entrou naquele instante e a cor sai de :func:`cor_da_barra_do_mic`.
        """

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

    class TouchpadView(DesenhoElastico):
        """Retângulo do touchpad com o ponto de toque (guia §4).

        Alargar não mente a posição do dedo: o toque é normalizado por FRAÇÃO
        (``px = 2 + fx * (largura - 4)``), então o ponto continua no lugar
        relativo certo em qualquer largura — o que muda é a proporção do
        retângulo.
        """

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
    "ESCALA_GYRO_GRAUS_S",
    "MIC_AMOSTRAS",
    "DesenhoElastico",
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
    "percentual_do_volume",
    "posicao_normalizada",
    "selo_mic",
    "texto_eixo",
    "texto_toques",
    "texto_volume",
    "volume_do_percentual",
]
