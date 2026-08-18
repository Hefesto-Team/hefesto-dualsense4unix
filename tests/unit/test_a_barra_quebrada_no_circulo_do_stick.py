"""A "barra quebrada" que atravessava o círculo do L3/R3 na aba Status.

Ela viu, fotografou e reclamou: um traço reto saía do meio da marca d'água e
ia até a borda do anel, cortando o desenho do analógico.

A causa não estava no arco nem na cor — estava no **ponto corrente** do Cairo.
`ctx.show_text()` termina deixando o ponto corrente no fim do glifo, sobre a
baseline. Três linhas adiante, `ctx.arc(cx, cy, raio_externo, ...)` encontra
esse ponto corrente e o Cairo, por definição, LIGA o ponto ao início do arco
com um segmento de reta antes de traçar a curva. O `stroke()` seguinte pinta
esse segmento com a cor e a espessura do anel — daí um traço opaco, cinza e
grosso atravessando o miolo do círculo.

Isso explica o que JÁ funcionava: antes de a marca d'água existir
(CARD-ÚNICO-01, entrega 3), nada deixava ponto corrente antes do arco, e o
círculo saía limpo. O defeito nasceu junto com o rótulo desenhado, não com o
anel.

A cura é uma linha — `ctx.new_path()` logo após o `show_text`, DENTRO da
auxiliar que sujou o estado. Quem suja o caminho é quem limpa.

Como estes testes MORDEM: arranque o `ctx.new_path()` de
`_desenhar_marca_dagua` e os dois reprovam — o de pixel porque volta a haver
tinta opaca da borda no miolo, o de contrato porque a auxiliar devolve o
contexto com ponto corrente.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("barra quebrada no círculo do stick")

import math
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

# CI sem libcairo (não está nas deps do build): pula o módulo inteiro em vez de
# estourar na coleta.
pytest.importorskip("cairo")

import cairo
from gi.repository import Gtk

from hefesto_dualsense4unix.gui.widgets.stick_preview_gtk import (
    BORDA_COLOR,
    StickPreviewGtk,
)


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")

#: Janelas vivas até o fim do módulo: uma `OffscreenWindow` coletada no meio do
#: teste leva junto a alocação do widget, e widget sem alocação desenha 1x1.
_janelas_vivas: list[Any] = []

#: Três tamanhos porque o desenho tem dois no produto (card único e compacto) e
#: ainda responde à escala de fonte dela. O segmento espúrio muda de lugar com
#: o tamanho da letra; o defeito, não.
LADOS = (90, 120, 160)

#: Folga, em pixels, para não confundir o segmento com o próprio anel. O anel é
#: traçado no raio externo com espessura 2, então até `raio - 1` ainda é anel; a
#: margem cobre também o antialiasing da curva.
FOLGA_DO_ANEL = 6


def _pintar(label: str, lado: int) -> Any:
    """Renderiza o desenho do analógico numa superfície de verdade.

    É a única forma honesta de aferir um `DrawingArea`: o desenho é Cairo, e
    perguntar ao widget qualquer coisa sobre seu estado não prova o que foi
    PINTADO.
    """
    preview = StickPreviewGtk(label=label)
    preview.set_size_request(lado, lado)
    janela = Gtk.OffscreenWindow()
    janela.add(preview)
    janela.set_size_request(lado, lado)
    janela.show_all()
    _janelas_vivas.append(janela)
    while Gtk.events_pending():
        Gtk.main_iteration()

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, lado, lado)
    ctx = cairo.Context(surface)
    preview._on_draw(preview, ctx)
    surface.flush()
    return surface


def _tinta_opaca_da_borda_no_miolo(surface: Any, lado: int) -> list[tuple[int, int]]:
    """Pixels de cor de borda PURA e opaca dentro do miolo do círculo.

    O critério é o que separa o defeito de tudo o que é legítimo no desenho:

    - o **anel** também é cor de borda pura, mas mora no raio externo, e o
      miolo aqui exclui essa faixa (`FOLGA_DO_ANEL`);
    - a **cruz** do centro é a mesma cor com alpha 0,35, e a **marca d'água**
      com alpha 0,3 — ambas saem MISTURADAS com o fundo, nunca puras;
    - o **ponto do stick** é branco Drácula, outra cor.

    Sobra exatamente uma coisa capaz de pintar cor de borda opaca no miolo: o
    segmento de reta que o Cairo desenha do ponto corrente até o início do
    arco.
    """
    dados = bytes(surface.get_data())
    stride = surface.get_stride()
    alvo = tuple(round(canal * 255) for canal in BORDA_COLOR)
    cx = cy = lado / 2
    raio_do_miolo = lado / 2 - 4 - FOLGA_DO_ANEL

    achados: list[tuple[int, int]] = []
    for y in range(lado):
        for x in range(lado):
            if math.hypot(x - cx, y - cy) > raio_do_miolo:
                continue
            base = y * stride + x * 4
            # ARGB32 em little-endian: os bytes saem B, G, R, A.
            b, g, r, a = (
                dados[base],
                dados[base + 1],
                dados[base + 2],
                dados[base + 3],
            )
            if a == 255 and (r, g, b) == alvo:
                achados.append((x, y))
    return achados


@pytest.mark.parametrize("lado", LADOS)
def test_o_circulo_do_stick_nao_tem_barra_atravessando(lado: int) -> None:
    """O miolo do círculo não tem um só pixel opaco da cor do anel.

    Este é o defeito como ela o viu: uma barra da cor e da espessura da borda
    cortando o desenho.

    Mordida medida (10/08): com o `ctx.new_path()` arrancado, este teste acha
    8 pixels em 90x120, 12 em 120x120 e 23 em 160x160 — e com a cura no lugar,
    zero nos três.
    """
    achados = _tinta_opaca_da_borda_no_miolo(_pintar("L3", lado), lado)

    assert not achados, (
        f"o miolo do círculo {lado}x{lado} tem {len(achados)} pixels opacos da "
        f"cor da borda (ex.: {achados[:5]}): o ponto corrente deixado pelo "
        "`show_text` da marca d'água voltou a ser ligado ao início do arco"
    )


@pytest.mark.parametrize("lado", LADOS)
def test_sem_rotulo_o_circulo_ja_saia_limpo(lado: int) -> None:
    """A hipótese explica o que JÁ funcionava.

    Sem rótulo, `_desenhar_marca_dagua` volta na primeira linha e nada deixa
    ponto corrente antes do arco — era assim o desenho antes de a marca d'água
    existir, e é assim que ele tem de continuar. Se este teste reprovasse, a
    culpa não seria do `show_text` e a cura estaria no lugar errado.
    """
    achados = _tinta_opaca_da_borda_no_miolo(_pintar("", lado), lado)

    assert not achados, (
        f"sem rótulo o miolo {lado}x{lado} já sai sujo ({len(achados)} pixels): "
        "a barra não vem do `show_text`, e a hipótese está errada"
    )


def test_a_marca_dagua_devolve_o_contexto_sem_ponto_corrente() -> None:
    """O contrato da auxiliar: quem suja o caminho é quem limpa.

    O teste de pixel prova o sintoma; este prova a regra, e sobrevive a
    qualquer mudança de fonte, de tamanho ou de posição do rótulo. Uma
    auxiliar de desenho que devolve ponto corrente é uma armadilha armada
    para o PRÓXIMO `arc` que alguém escrever ali — hoje é a borda, amanhã
    pode ser outro traço.
    """
    lado = 120
    preview = StickPreviewGtk(label="R3")
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, lado, lado)
    ctx = cairo.Context(surface)

    preview._desenhar_marca_dagua(ctx, lado / 2, lado / 2, lado / 2 - 4, BORDA_COLOR)

    assert not ctx.has_current_point(), (
        "`_desenhar_marca_dagua` devolveu o contexto com ponto corrente: o "
        "próximo `ctx.arc` vai ligar esse ponto ao início do arco com um "
        "segmento de reta"
    )
