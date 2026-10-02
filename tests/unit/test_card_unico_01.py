"""CARD-ÚNICO-01 — o frame "Estado" apaga e o que sobra dele entra no card."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("card único 01")

import math
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

pytest.importorskip("cairo")

import cairo
from gi.repository import Gtk

from hefesto_dualsense4unix.app.widgets.controller_card import (
    TEXTO_SPEAKER_SEM_DADO,
    TITULO_SPEAKER,
    ControllerCard,
)
from hefesto_dualsense4unix.gui.widgets.stick_preview_gtk import (
    BORDA_COLOR,
    FUNDO_COLOR,
    StickPreviewGtk,
)
from tests.unit.test_status_faixa_blocos import _ENTRY, _ESTADO


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")

_janelas_vivas: list[Any] = []


LARGURA_DA_TELA_DELA = 1920


def _card(*, compact: bool = False, largura: int = LARGURA_DA_TELA_DELA) -> Any:
    """Card montado e ALOCADO na largura da tela dela, com dados completos."""
    from hefesto_dualsense4unix.app.mic_monitor import LeituraMic

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


def test_o_card_unico_mostra_perfil_e_daemon_e_o_compacto_nao() -> None:
    """As duas linhas novas, e por que elas não entram no card compacto."""
    unico = _card()
    dois = _card(compact=True)

    assert unico._linha_estado_global is not None
    assert unico._perfil_ativo_label is not None
    assert unico._daemon_label is not None

    unico.definir_estado_global("ação", "Ligado")
    assert unico._perfil_ativo_label.get_text() == "ação"
    assert unico._daemon_label.get_text() == "Ligado"

    assert dois._linha_estado_global is None, (
        "perfil ativo e daemon são fatos GLOBAIS: num card por controle eles "
        "apareceriam repetidos na mesma tela"
    )
    dois.definir_estado_global("ação", "Ligado")


def test_a_bateria_do_card_unico_nao_desenha_o_proprio_texto() -> None:
    """O número sai da barra e vira rótulo ao lado dela."""
    unico = _card()

    assert unico._battery_bar.get_show_text() is False
    assert unico._battery_pct_label is not None
    assert unico._battery_pct_label.get_text() == unico._battery_bar.get_text()
    assert unico._battery_pct_label.get_text() == "80 %"


def test_a_bateria_fica_a_direita_e_o_giroscopio_a_esquerda_na_mesma_linha() -> None:
    """*"a bateria fica ao lado do hertz do giroscópio"* — na mesma linha."""
    unico = _card()
    faixa = unico._faixa_gyro_bateria
    largura_da_faixa = faixa.get_allocated_width()
    bateria = unico._battery_row.get_allocation()

    assert largura_da_faixa > 1, "faixa sem alocação: a medida não vale nada"
    assert bateria.x > largura_da_faixa / 2, (
        f"a bateria começa em x={bateria.x} numa faixa de {largura_da_faixa}px "
        "— ela devia estar na metade DIREITA, com o giroscópio à esquerda"
    )


def test_o_titulo_do_alto_falante_nao_diz_nao_ajustado() -> None:
    """*"remover o não ajustado"*."""
    unico = _card()

    unico._escrever_valor_do_speaker(TEXTO_SPEAKER_SEM_DADO)
    assert unico._speaker_titulo.get_text() == TITULO_SPEAKER
    assert TEXTO_SPEAKER_SEM_DADO not in unico._speaker_titulo.get_text()
    assert unico._speaker_label.get_text() == TEXTO_SPEAKER_SEM_DADO

    unico._escrever_valor_do_speaker("71 %")
    assert unico._speaker_titulo.get_text() == f"{TITULO_SPEAKER} · 71 %"


def _pintar(label: str, lado: int = 120) -> Any:
    """Renderiza o desenho do analógico numa superfície de verdade."""
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


def _tinta_fora_do_fundo(surface: Any, lado: int) -> int:
    """Quantos pixels do MIOLO não são a cor de fundo."""
    dados = bytes(surface.get_data())
    stride = surface.get_stride()
    fundo = tuple(round(c * 255) for c in FUNDO_COLOR)
    inicio, fim = lado // 3, 2 * lado // 3
    tinta = 0
    for y in range(inicio, fim):
        for x in range(inicio, fim):
            base = y * stride + x * 4
            b, g, r = dados[base], dados[base + 1], dados[base + 2]
            if (r, g, b) != fundo:
                tinta += 1
    return tinta


def test_a_marca_dagua_e_realmente_pintada_dentro_do_circulo() -> None:
    """*"L3 e R3 (...) no centro do desenho do analógico (...) ao fundo"*."""
    lado = 120
    com = _tinta_fora_do_fundo(_pintar("L3", lado), lado)
    sem = _tinta_fora_do_fundo(_pintar("", lado), lado)

    assert com > sem, (
        f"o miolo do desenho tem {com} pixels de tinta com rótulo e {sem} sem "
        "ele: a marca d'água não está sendo pintada"
    )


def test_a_marca_dagua_e_fundo_e_nao_cobre_a_cruz() -> None:
    """A ordem de pintura é a entrega: ela vem ANTES da cruz e do ponto."""
    import inspect

    fonte = inspect.getsource(StickPreviewGtk._on_draw)
    pos_marca = fonte.index("_desenhar_marca_dagua")
    pos_borda = fonte.index("ctx.arc(cx, cy, raio_externo")
    pos_ponto = fonte.index("ctx.arc(px, py")

    assert pos_marca < pos_borda < pos_ponto, (
        "a marca d'água é FUNDO: ela tem de ser pintada antes da borda, da "
        "cruz e do ponto"
    )


def test_o_tamanho_da_marca_dagua_acompanha_o_desenho() -> None:
    """Nada de literal em px: o card inteiro obedece à escala de fonte dela."""
    grande = _tinta_fora_do_fundo(_pintar("L3", 180), 180)
    pequeno = _tinta_fora_do_fundo(_pintar("L3", 90), 90)

    assert grande > pequeno * 2, (
        f"a marca d'água rendeu {grande} pixels no desenho grande e "
        f"{pequeno} no pequeno: ela não está acompanhando o tamanho"
    )


ANEL_DA_BARRA = (0.55, 0.93)

TOLERANCIA_DO_TRACO = 20


def _tinta_opaca_da_borda_no_anel(surface: Any, lado: int) -> int:
    """Quantos pixels do ANEL estão pintados com a borda OPACA."""
    dados = bytes(surface.get_data())
    stride = surface.get_stride()
    cx = cy = lado / 2
    raio = lado / 2 - 4
    dentro, fora = (f * raio for f in ANEL_DA_BARRA)
    alvo = tuple(round(c * 255) for c in BORDA_COLOR)
    tinta = 0
    for y in range(lado):
        for x in range(lado):
            dist = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            if not dentro <= dist <= fora:
                continue
            base = y * stride + x * 4
            b, g, r = dados[base], dados[base + 1], dados[base + 2]
            canais = zip((r, g, b), alvo, strict=True)
            if all(abs(c - a) <= TOLERANCIA_DO_TRACO for c, a in canais):
                tinta += 1
    return tinta


@pytest.mark.parametrize("label", ["L3", "R3"])
@pytest.mark.parametrize("lado", [90, 120, 180])
def test_a_marca_dagua_nao_deixa_barra_atravessando_o_circulo(
    label: str, lado: int
) -> None:
    """Ela viu e fotografou: uma barra riscando o círculo do L3 e do R3."""
    barra = _tinta_opaca_da_borda_no_anel(_pintar(label, lado), lado)

    assert barra == 0, (
        f"{barra} pixels da cor OPACA da borda no anel do desenho {lado}x{lado} "
        f"de {label!r}: há um traço atravessando o círculo — o ponto corrente "
        "deixado por `show_text` está sendo ligado ao início do arco da borda"
    )


def test_o_card_compacto_tambem_para_de_esticar_pela_tela_toda() -> None:
    """Empilhado, cada card recebe a janela inteira — e precisa do teto."""
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        LARGURA_CARD_ELASTICA,
    )

    assert LARGURA_DA_TELA_DELA > LARGURA_CARD_ELASTICA, (
        "a bancada precisa de uma tela MAIOR que o teto: numa janela do "
        "tamanho do teto, este teste passaria com ou sem o corte"
    )
    card = _card(compact=True)
    assert card.get_allocated_width() == LARGURA_CARD_ELASTICA


def test_a_bateria_do_card_compacto_tambem_nao_desenha_o_proprio_texto() -> None:
    """O empilhamento trouxe de volta o número flutuando no vazio."""
    compacto = _card(compact=True)

    assert compacto._battery_bar.get_show_text() is False
    assert compacto._battery_pct_label is not None
    assert compacto._battery_pct_label.get_text() == compacto._battery_bar.get_text()
