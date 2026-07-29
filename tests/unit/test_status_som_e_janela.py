"""SOM-01 — os três pedidos que ela fez olhando a v2, medidos na geometria.

*"dava pra colocar o auto falante abaixo do microfone"*, *"aumentar e espaçar
mais os botões do controle tipo x quadrado bola e triângulo e afins"* e
*"permitir a expansão da janela"*.

Como em `test_status_faixa_blocos.py`, tudo é medido com o card MONTADO numa
`Gtk.OffscreenWindow` da largura da tela dela (1920 maximizada, 1870 para a
área de conteúdo): widget sem alocação devolve 1x1 em tudo, e um teste de
geometria sobre ele passaria com qualquer layout.

Cada teste diz no docstring qual é a MORDIDA — o que arrancar do
`controller_card.py` para vê-lo em vermelho.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira
# no CI headless, em vez de pular.
exigir_gi_real("status som e janela")

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

# CI headless sem libcairo cai no stub do card (sem sub-widgets de desenho).
pytest.importorskip("cairo")

from gi.repository import Gtk

from hefesto_dualsense4unix.app.mic_monitor import LeituraMic
from hefesto_dualsense4unix.app.widgets.controller_card import (

    GLYPH_ESPACO_COMPACTO,
    GLYPH_ESPACO_UNICO,
    LARGURA_CARD_ELASTICA,
    LARGURA_CARD_UNICO,
    ControllerCard,
    glyph_size,
    glyph_size_unico,
)

#: A largura que a aba Status recebe na tela dela, maximizada em 1920x1080.
LARGURA_DA_TELA_DELA = 1870

_INPUTS: dict[str, Any] = {
    "lx": 60,
    "ly": 200,
    "rx": 180,
    "ry": 90,
    "l2_raw": 200,
    "r2_raw": 40,
    "buttons": ["cross"],
    "gyro": {"x": 143.2, "y": -412.0, "z": 22.8},
    "touchpad": {
        "touching": True,
        "x": 1440,
        "y": 270,
        "width": 1920,
        "height": 1080,
    },
}
_ENTRY: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "uniq": "aa:bb:cc:00:00:01",
    "battery_pct": 80,
    "player": None,
    "player_slot": 1,
    "lightbar_rgb": [97, 53, 131],
    "lightbar_on": True,
    "lightbar_source": "sysfs",
    "inputs": _INPUTS,
    "vpad_backend": "uhid",
    "vpad_motivo": None,
    "speaker": {"volume": 180, "muted": False},
}
_ESTADO: dict[str, Any] = {"native_mode": False}

#: As janelas ficam vivas numa lista de módulo: o Python coleta a referência
#: local assim que a função retorna, e um card sem toplevel volta a reportar
#: 1x1 no meio da asserção.
_janelas_vivas: list[Any] = []


def _card(
    *, compact: bool = False, largura: int = LARGURA_DA_TELA_DELA
) -> Any:
    """Card montado e alocado numa janela da largura pedida."""
    card = ControllerCard(compact=compact)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.set_size_request(largura, 900)
    janela.show_all()
    _janelas_vivas.append(janela)
    card.update(_ENTRY, _ESTADO, LeituraMic(nivel=0.6, muted=False))
    janela.resize(largura, 900)
    while Gtk.events_pending():
        Gtk.main_iteration()
    return card


# ---------------------------------------------------------------------------
# Pedido 1 — "dava pra colocar o auto falante abaixo do microfone"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("compact", [False, True])
def test_o_alto_falante_fica_logo_abaixo_do_microfone(compact: bool) -> None:
    """O pedido ao pé da letra: ABAIXO, e na MESMA coluna.

    Na v2 o alto-falante estava na coluna da esquerda, embaixo da lightbar, e
    o microfone à direita dos analógicos — os dois lados opostos da faixa,
    para o mesmo assunto (o áudio do controle). Medido na captura dela: o
    alto-falante em x=468 e o microfone em x=986, com 518px entre eles.

    Duas asserções, e as duas precisam valer: o alto-falante COMEÇA na mesma
    coluna do microfone (mesmo x, mesma largura — é o que faz os dois lerem
    como um bloco só) e fica ABAIXO dele (y maior, e sem sobreposição).

    Vale nos dois cards: com 2+ controles a faixa é a mesma, e deixar o
    compacto para trás faria a tela dela mudar de desenho quando o segundo
    controle entrasse.

    A mordida: devolver o `_montar_speaker()` para o `_montar_coluna_sensores`
    faz o x do alto-falante voltar para o da coluna da esquerda e este teste
    cai nas duas parametrizações.
    """
    card = _card(compact=compact)

    mic = card._mic_box.get_allocation()
    alto = card._speaker_box.get_allocation()

    assert alto.x == mic.x, (
        f"o alto-falante começa em x={alto.x} e o microfone em x={mic.x}: "
        "eles não estão na mesma coluna"
    )
    assert alto.width == mic.width, (
        f"o alto-falante mede {alto.width}px e o microfone {mic.width}px: a "
        "coluna do som ficou desalinhada"
    )
    assert alto.y >= mic.y + mic.height, (
        f"o alto-falante começa em y={alto.y} e o microfone só termina em "
        f"y={mic.y + mic.height}: ele não está ABAIXO do microfone"
    )
    # E é uma coluna de verdade, não dois blocos que calharam de se alinhar.
    assert card._speaker_box.get_parent() is card._coluna_audio
    assert card._mic_box.get_parent() is card._coluna_audio


def test_a_coluna_da_esquerda_nao_fica_orfa_de_altura() -> None:
    """O alto-falante saiu da coluna da esquerda — ela não pode ter afundado.

    Tirar um bloco de uma coluna vertical mexe em duas coisas: a altura que
    ela pede e o alinhamento dos que ficaram. Touchpad e lightbar continuam
    ancorados no TOPO da faixa, na mesma linha em que começam os analógicos e
    a coluna do som — é assim que os títulos das molduras se leem lado a lado.

    A mordida: trocar o `valign=START` da coluna de sensores por `CENTER` faz
    o touchpad descer ~35px em relação ao microfone e este teste cai.
    """
    card = _card()

    touch = card._touch_box.get_allocation()
    mic = card._mic_box.get_allocation()
    sticks = card._stick_left.get_allocation()

    assert touch.y == mic.y, (
        f"o touchpad começa em y={touch.y} e o microfone em y={mic.y}: a "
        "coluna da esquerda saiu do topo da faixa"
    )
    assert touch.y <= sticks.y, "os sensores abrem a faixa, no alto"
    # A coluna continua com os dois blocos que sobraram, e nesta ordem.
    assert card._lightbar_box.get_allocation().y > touch.y
    assert card._speaker_box.get_parent() is not card._coluna_sensores


# ---------------------------------------------------------------------------
# Pedido 2 — "aumentar e espaçar mais os botões do controle"
# ---------------------------------------------------------------------------


def test_o_glifo_do_card_de_um_controle_e_maior_que_o_do_compacto() -> None:
    """*"aumentar (...) os botões tipo x quadrado bola e triângulo"*.

    Medido na tela dela antes da leva: cada glifo ocupava 36x36px e o grid 4x4
    inteiro, 150x150px no canto direito de um card de 960. Depois: 58x58 e
    262x262.

    A medida é do glifo ALOCADO no card montado, não da constante: é o que
    prova que o número novo chegou ao widget. E o compacto entra como
    contraprova — a decisão desta leva é que o glifo cresce onde há largura
    para pagá-lo, e o card de 2+ controles não tem.

    A mordida: fazer `_montar_glyphs` chamar `glyph_size()` nos dois cards (o
    que valia antes) empata as duas medidas e este teste cai.
    """
    unico = _card()
    compacto = _card(compact=True, largura=600)

    glifo_unico = unico._glyphs["triangle"].get_allocated_width()
    glifo_compacto = compacto._glyphs["triangle"].get_allocated_width()

    assert glifo_unico > glifo_compacto, (
        f"o glifo do card de um controle mede {glifo_unico}px e o do compacto "
        f"{glifo_compacto}px: ele parou de crescer onde havia largura"
    )
    assert glifo_unico == glyph_size_unico()
    assert glifo_compacto == glyph_size()
    # O grid inteiro cresce junto — é ele que ela vê como "os botões".
    assert unico._glyph_grid.get_allocated_width() > (
        compacto._glyph_grid.get_allocated_width()
    )


def test_os_glifos_do_card_de_um_controle_tem_respiro_entre_eles() -> None:
    """*"e espaçar mais"* — a segunda metade do pedido.

    Com 2px de respiro os 16 desenhos liam como um bloco só; a distância entre
    dois vizinhos é medida aqui na GEOMETRIA (fim de um até o começo do
    outro), e não no `row-spacing`, porque é a distância que ela vê.

    A mordida: devolver o `set_row_spacing(2)`/`set_column_spacing(2)` do card
    de um controle derruba as duas asserções de baixo.
    """
    card = _card()

    cruz = card._glyphs["cross"].get_allocation()
    circulo = card._glyphs["circle"].get_allocation()
    cima = card._glyphs["dpad_up"].get_allocation()

    horizontal = circulo.x - (cruz.x + cruz.width)
    vertical = cima.y - (cruz.y + cruz.height)

    assert horizontal >= GLYPH_ESPACO_UNICO, (
        f"a cruz e a bola estão a {horizontal}px uma da outra (esperado ao "
        f"menos {GLYPH_ESPACO_UNICO}px): os botões voltaram a ficar colados"
    )
    assert vertical >= GLYPH_ESPACO_UNICO, (
        f"as duas fileiras estão a {vertical}px uma da outra (esperado ao "
        f"menos {GLYPH_ESPACO_UNICO}px)"
    )
    assert GLYPH_ESPACO_UNICO > GLYPH_ESPACO_COMPACTO


def test_o_card_compacto_mantem_o_glifo_de_hoje() -> None:
    """A contrapartida MEDIDA da decisão: no compacto o glifo não cresce.

    Não é esquecimento e não é preferência — é o mesmo orçamento que decidiu a
    moldura dos blocos em `_bloco`: com 2+ controles os cards vão lado a lado,
    a rolagem horizontal da aba é `never` e a largura de cada card sobe somada
    até a janela. A folga da aba inteira com dois cards é de 128px
    (`test_dois_cards_lado_a_lado_cabem_na_largura_da_janela`), e o grid maior
    custa 112px por card — 224px nos dois.

    Este teste existe para que a diferença entre os dois cards continue sendo
    uma decisão escrita, e não uma que alguém desfaz sem medir o preço.
    """
    compacto = _card(compact=True, largura=600)

    assert compacto._glyph_size == glyph_size()
    assert compacto._glyph_grid.get_row_spacing() == GLYPH_ESPACO_COMPACTO
    assert compacto._glyph_grid.get_column_spacing() == GLYPH_ESPACO_COMPACTO


def test_o_glifo_maior_continua_derivando_da_escala_de_fonte() -> None:
    """O tamanho novo não pode ser px cru: ele tem de crescer com a fonte dela.

    Foi o defeito que a STATUS-SIMETRIA-01 curou (o glifo era o único tamanho
    da interface fora do alcance do ajuste de fonte), e multiplicar um número
    fixo o traria de volta pela porta dos fundos.

    A mordida: trocar o corpo de `glyph_size_unico` por um `return 58` faz as
    duas escalas empatarem e este teste cai.
    """
    assert glyph_size_unico(0) < glyph_size_unico(3)
    assert glyph_size_unico(0) > glyph_size(0)


# ---------------------------------------------------------------------------
# Pedido 3 — "permitir a expansão da janela"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("largura_da_janela", "esperado"),
    [
        (1180, 1180),
        (1400, 1400),
        (LARGURA_DA_TELA_DELA, LARGURA_CARD_ELASTICA),
    ],
)
def test_o_card_acompanha_a_janela_ate_o_teto_elastico(
    largura_da_janela: int, esperado: int
) -> None:
    """A curva inteira do teto elástico, e não só as pontas.

    O card acompanha a janela enquanto ela cresce e para no teto: é isso que
    separa "a janela expande" (o pedido) de "o card estica pela tela toda" (o
    defeito que a rodada anterior curou, com dois vãos de 673px dentro da
    faixa).

    A mordida: sem o corte do `do_size_allocate` o último caso vira 1870;
    com o `halign=CENTER` e o `set_size_request` da rodada anterior, os três
    casos viram 1040.
    """
    card = _card(largura=largura_da_janela)

    assert card.get_allocated_width() == esperado


def test_o_piso_do_card_e_o_que_o_conteudo_pede() -> None:
    """O piso não pode ser decorativo.

    :data:`LARGURA_CARD_UNICO` é repetido no `frame_status_estado` do glade e
    travado por `test_status_faixa_blocos`. Se o conteúdo do card passar a
    pedir MAIS que ele, o número vira enfeite: o card ignora o piso, o frame
    Estado não, e a aba volta a ter duas larguras — que é exatamente o que a
    rodada anterior tinha curado.

    A mordida: crescer qualquer desenho do card (o analógico, o touchpad, o
    grid de botões) além do que o piso paga derruba este teste antes de a
    tela dela mostrar o desalinhamento.
    """
    card = ControllerCard(compact=False)
    card.show_all()

    minimo, _natural = card.get_preferred_width()

    assert minimo <= LARGURA_CARD_UNICO, (
        f"o conteúdo do card pede {minimo}px e o piso compartilhado com o "
        f"frame Estado é de {LARGURA_CARD_UNICO}px: o piso virou enfeite"
    )
    assert LARGURA_CARD_UNICO < LARGURA_CARD_ELASTICA


def test_o_card_compacto_nao_ganha_teto_elastico() -> None:
    """O corte é só do card de UM controle.

    Com 2+ controles quem manda na largura é o `status_players_slot`, que os
    põe em colunas homogêneas: um corte por card ali deixaria buraco ENTRE as
    colunas, que é o defeito de origem desta série de sprints.

    A mordida: tirar o `not self._compact` do `do_size_allocate` faz o card
    compacto parar de preencher a coluna e este teste cai.
    """
    card = _card(compact=True, largura=LARGURA_DA_TELA_DELA)

    assert card.get_allocated_width() == LARGURA_DA_TELA_DELA
