"""L8 — os ~600 px mortos das duas colunas da aba Lightbar.

**O que foi medido (M10 da sprint LIGHTBAR-COR-DE-CADA-UM-01, 24/08/2026).** Na
foto de 23/08, em 1920x1080, o conteúdo da coluna esquerda terminava em y≈460 e
o da direita em y≈455 — e as duas molduras iam até y≈1065. Duas caixas com
borda desenhada em volta de meio metro de nada, na aba mais vazia do produto.

**A causa, e ela é de uma linha.** ``tab_lightbar_box`` é uma ``GtkBox``
horizontal, e numa box o ``valign`` padrão dos filhos é ``fill``: cada moldura
esticava até o fim da página porque ninguém lhe disse para parar. ``valign =
start`` nas duas resolve — mesma classe de conserto do teto elástico que a
LARGURA-01/E5 já aplicou na LARGURA desta aba.

**A régua, e por que ela é de GEOMETRIA e não de XML.** Cobrar
``get_valign() == START`` seria ler de volta a propriedade que acabei de
escrever: passaria com o layout quebrado por qualquer outro motivo, e
reprovaria se alguém obtivesse o mesmo resultado por outro caminho. O que
importa é a ALTURA ALOCADA contra a NATURAL, com a aba realmente montada e
realmente alocada.

Molde: ``test_layout_orcamento_altura.py`` — inclusive o laço de assentamento,
que é a cura da RÉGUA-QUE-NÃO-ASSENTA-01 (19/08/2026): sob a carga da suíte
inteira a alocação ainda não entrou na fila quando ``events_pending()`` responde
"não há evento agora", e a medida sai de uma janela não alocada. Um número que
não assentou não mede layout nenhum.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("lightbar vao vertical")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
_gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app.constants import MAIN_GLADE

#: A tela em que a foto de 23/08 foi medida. Números do M10 vieram daqui.
LARGURA, ALTURA = 1920, 1080

#: Quanto a moldura pode passar da própria altura natural antes de virar vão.
#:
#: Não é gosto: é a diferença entre "o GTK arredondou/deu uma margem" e "a
#: moldura foi esticada até o fim da página". Com o defeito de 23/08 a folga
#: medida era de ~600 px em cada coluna — vinte vezes este teto.
FOLGA_MAXIMA_PX = 32

#: Teto de voltas do bombeamento até a alocação assentar (mesmo número e mesmo
#: motivo do `test_layout_orcamento_altura`).
_TETO_DE_VOLTAS = 200

#: As duas molduras da aba, pelo rótulo — é o que a pessoa vê na tela. Elas não
#: têm id no glade, e dar um id a cada uma só para o teste seria fabricar
#: superfície nova para medir a antiga.
_ROTULOS_DAS_COLUNAS = ("Lightbar (barra de LED)", "Desenho das 5 luzes")


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)


def _molduras(caixa: Gtk.Widget) -> dict[str, Gtk.Frame]:
    achadas: dict[str, Gtk.Frame] = {}
    for filho in caixa.get_children():
        if isinstance(filho, Gtk.Frame):
            achadas[filho.get_label() or ""] = filho
    return achadas


def _montar() -> tuple[Gtk.OffscreenWindow, Gtk.Widget]:
    """A aba Lightbar sozinha, numa janela offscreen alocada em 1920x1080.

    ``Gtk.OffscreenWindow`` e não ``Gtk.Window``: sob Xvfb não há gerenciador
    de janelas, e uma ``Gtk.Window`` fica 1x1 para sempre (armadilha nº 2 do
    COMO-OLHAR-A-TELA).
    """
    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    caixa = builder.get_object("tab_lightbar_box")
    assert caixa is not None, "a aba Lightbar sumiu do glade"
    pai = caixa.get_parent()
    if pai is not None:
        pai.remove(caixa)
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class("hefesto-dualsense4unix-window")
    janela.add(caixa)
    janela.show_all()

    # A alocação é IMPOSTA, não esperada: numa OffscreenWindow não há
    # gerenciador de janelas para responder ao `resize()`.
    retangulo = Gdk.Rectangle()
    retangulo.x, retangulo.y = 0, 0
    retangulo.width, retangulo.height = LARGURA, ALTURA
    anterior, iguais = -1, 0
    for _ in range(_TETO_DE_VOLTAS):
        janela.size_allocate(retangulo)
        while Gtk.events_pending():
            Gtk.main_iteration()
        atual = caixa.get_allocated_height()
        iguais = iguais + 1 if atual == anterior else 0
        anterior = atual
        if iguais >= 2 and atual > 0:
            return janela, caixa
        janela.queue_resize()
    pytest.fail(
        f"instrumento inválido: a aba não assentou em {_TETO_DE_VOLTAS} "
        f"voltas (última leitura {anterior}px). Isto NÃO é veredito sobre o "
        "layout — é a régua avisando que não chegou a medir."
    )


def test_as_duas_colunas_param_na_altura_natural() -> None:
    """A MORDIDA do L8: arranque o ``valign`` e veja o número de 23/08 voltar.

    Sem ``valign = start`` cada moldura recebe a altura inteira da página
    (~1065 px em 1920x1080) enquanto pede pouco mais de 400 px — e a asserção
    reprova nomeando a coluna e a sobra em pixels.
    """
    janela, caixa = _montar()
    try:
        molduras = _molduras(caixa)
        faltando = [r for r in _ROTULOS_DAS_COLUNAS if r not in molduras]
        assert not faltando, f"moldura(s) não encontrada(s) na aba: {faltando}"

        for rotulo in _ROTULOS_DAS_COLUNAS:
            moldura = molduras[rotulo]
            largura = moldura.get_allocated_width()
            natural = moldura.get_preferred_height_for_width(largura)[1]
            alocada = moldura.get_allocated_height()
            sobra = alocada - natural
            assert sobra <= FOLGA_MAXIMA_PX, (
                f"a coluna “{rotulo}” pede {natural}px e recebeu {alocada}px "
                f"— {sobra}px de moldura desenhada em volta de nada. É o vão "
                "vertical da VAO-01: as colunas têm de parar na altura "
                "natural (`valign = start`), não esticar até o fim da página."
            )
    finally:
        janela.destroy()


def test_a_aba_inteira_nao_cresceu_com_o_conserto() -> None:
    """A recíproca: parar de esticar não pode ENCOLHER o que a aba mostra.

    Se o conserto tivesse sido feito com um teto de altura em pixels, a
    coluna que crescesse (o rótulo novo do L6, por exemplo) passaria a ser
    cortada em silêncio. Aqui a altura pedida pela aba continua sendo a soma
    do conteúdo — o que muda é só o que sobra depois dela.
    """
    janela, caixa = _montar()
    try:
        natural = caixa.get_preferred_height_for_width(LARGURA)[1]
        assert natural > 0
        for rotulo, moldura in _molduras(caixa).items():
            pedida = moldura.get_preferred_height_for_width(
                moldura.get_allocated_width()
            )[1]
            assert moldura.get_allocated_height() >= pedida, (
                f"a coluna “{rotulo}” está sendo CORTADA: pede {pedida}px e "
                f"recebeu {moldura.get_allocated_height()}px"
            )
    finally:
        janela.destroy()
