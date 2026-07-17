"""tests/unit/test_status_tinting_widgets.py — tinting dos widgets (STATUS-03).

Exercita com GTK REAL (a suíte roda com display; widgets são instanciados):

  * ButtonGlyph.set_accent: cache por (nome, size, hex) — trocar a cor N
    vezes gera NO MÁXIMO 1 carga de pixbuf por combinação (contador via
    monkeypatch no loader de MISS), lendo do GLYPHS_DIR resolvido
    (dir FAKE em tmp_path — não caminho fixo);
  * _tintar_svg: replace-all do literal #bd93f9 no texto do SVG;
  * StickPreviewGtk.set_accent: desenha num surface cairo offscreen sem
    erro, o accent muda o render e None restaura o comportamento clássico;
  * tintar_progressbar: CssProvider POR WIDGET alcança trough/progress
    (pixels amostrados de render offscreen), provider recriado SÓ quando a
    cor muda.
"""
# ruff: noqa: E402 — gi.require_version precisa vir antes dos imports de gi
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import pytest

# CI sem libcairo (não está nas deps do build): pula o módulo inteiro em vez de
# estourar ModuleNotFoundError na coleta — mesmo padrão de `importorskip("gi")`.
pytest.importorskip("cairo")

import cairo
from gi.repository import Gtk

from hefesto_dualsense4unix.gui.widgets import button_glyph as glyph_mod
from hefesto_dualsense4unix.gui.widgets.stick_preview_gtk import StickPreviewGtk
from hefesto_dualsense4unix.utils.color_contrast import (
    TROUGH_HEX,
    ensure_min_contrast,
    rgb_para_hex,
    tintar_progressbar,
)

# Cores de exercício: a real medida ao vivo + um vermelho bem distinto.
COR_A = (16, 32, 72)
COR_B = (255, 0, 0)

_SVG_ATIVO_FAKE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <rect x="0" y="0" width="32" height="32" fill="#bd93f9"/>
  <line x1="4" y1="4" x2="28" y2="28" stroke="#bd93f9" stroke-width="2"/>
</svg>
"""

_SVG_NORMAL_FAKE = _SVG_ATIVO_FAKE.replace("#bd93f9", "#f8f8f2")


def _drena_eventos() -> None:
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)


def _render_offscreen(
    janela: Gtk.OffscreenWindow, largura: int, altura: int
) -> tuple[bytes, int]:
    """Copia o surface da OffscreenWindow para um ImageSurface: (bytes, stride)."""
    _drena_eventos()
    origem = janela.get_surface()
    assert origem is not None
    img = cairo.ImageSurface(cairo.FORMAT_ARGB32, largura, altura)
    ctx = cairo.Context(img)
    ctx.set_source_surface(origem, 0, 0)
    ctx.paint()
    img.flush()
    return bytes(img.get_data()), img.get_stride()


def _pixel(dados: bytes, stride: int, x: int, y: int) -> tuple[int, int, int, int]:
    """Lê um pixel (r, g, b, a) de um buffer ARGB32 pré-multiplicado."""
    off = y * stride + x * 4
    b, g, r, a = dados[off], dados[off + 1], dados[off + 2], dados[off + 3]
    return (r, g, b, a)


def _hex_para_rgb(hex_cor: str) -> tuple[int, int, int]:
    return (
        int(hex_cor[1:3], 16),
        int(hex_cor[3:5], 16),
        int(hex_cor[5:7], 16),
    )


# ---------------------------------------------------------------------------
# ButtonGlyph — cache do tinting
# ---------------------------------------------------------------------------


@pytest.fixture
def glyphs_dir_fake(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Path]:
    """GLYPHS_DIR fake com um glyph mínimo contendo o literal #bd93f9."""
    (tmp_path / "fake.svg").write_text(_SVG_NORMAL_FAKE, encoding="utf-8")
    (tmp_path / "fake_active.svg").write_text(_SVG_ATIVO_FAKE, encoding="utf-8")
    monkeypatch.setattr(glyph_mod, "GLYPHS_DIR", tmp_path)
    glyph_mod.limpar_cache_tinting()
    yield tmp_path
    glyph_mod.limpar_cache_tinting()


def test_glyph_trocar_cor_n_vezes_carrega_1x_por_combinacao(
    monkeypatch: pytest.MonkeyPatch, glyphs_dir_fake: Path
) -> None:
    """5 idas-e-vindas entre 2 cores => exatamente 2 cargas de pixbuf."""
    contador = {"cargas": 0}
    original = glyph_mod._carregar_pixbuf_tintado

    def _contando(nome: str, size: int, hex_cor: str) -> object:
        contador["cargas"] += 1
        return original(nome, size, hex_cor)

    monkeypatch.setattr(glyph_mod, "_carregar_pixbuf_tintado", _contando)

    glyph = glyph_mod.ButtonGlyph("fake", size=24)
    assert glyph._pb_active is not None, "SVG fake devia carregar no init"
    stock = glyph._pb_active_stock

    for _ in range(5):
        glyph.set_accent(COR_A)
        glyph.set_accent(COR_B)

    assert contador["cargas"] == 2, (
        f"esperado 1 carga por (nome, size, hex) — 2 no total; "
        f"houve {contador['cargas']}"
    )
    # O pixbuf tintado respeita o set_size e NÃO é o stock.
    assert glyph._pb_active is not stock
    assert glyph._pb_active.get_width() == 24
    assert glyph._pb_active.get_height() == 24


def test_glyph_set_accent_none_restaura_stock_sem_recarga(
    monkeypatch: pytest.MonkeyPatch, glyphs_dir_fake: Path
) -> None:
    contador = {"cargas": 0}
    original = glyph_mod._carregar_pixbuf_tintado

    def _contando(nome: str, size: int, hex_cor: str) -> object:
        contador["cargas"] += 1
        return original(nome, size, hex_cor)

    monkeypatch.setattr(glyph_mod, "_carregar_pixbuf_tintado", _contando)

    glyph = glyph_mod.ButtonGlyph("fake", size=24)
    stock = glyph._pb_active_stock
    glyph.set_accent(COR_A)
    assert glyph._pb_active is not stock
    assert contador["cargas"] == 1
    glyph.set_accent(None)
    assert glyph._pb_active is stock
    # Voltar à MESMA cor pós-None é cache HIT (0 cargas novas); repetir idem.
    glyph.set_accent(COR_A)
    glyph.set_accent(COR_A)
    assert contador["cargas"] == 1


def test_glyph_pixbuf_tintado_contem_a_cor_ajustada(
    glyphs_dir_fake: Path,
) -> None:
    """O pixbuf tintado carrega a cor AJUSTADA (D8: traço recebe a ajustada)."""
    glyph = glyph_mod.ButtonGlyph("fake", size=24)
    glyph.set_accent(COR_A)
    ajustada = ensure_min_contrast(COR_A)
    pixels = bytes(glyph._pb_active.get_pixels())
    n_canais = glyph._pb_active.get_n_channels()
    assert n_canais >= 3
    alvo = bytes(ajustada)
    assert alvo in pixels, (
        f"pixbuf tintado devia conter a cor ajustada {ajustada}"
    )
    # E não contém mais o roxo stock puro (o rect inteiro foi substituído).
    assert bytes((0xBD, 0x93, 0xF9)) not in pixels


def test_tintar_svg_substitui_todas_as_ocorrencias() -> None:
    """Replace-all: as 2 ocorrências do literal saem; o hex novo entra 2x."""
    tintado = glyph_mod._tintar_svg(_SVG_ATIVO_FAKE, "#102048")
    assert "#bd93f9" not in tintado
    assert "#BD93F9" not in tintado
    assert tintado.count("#102048") == 2


def test_glyphs_reais_shipados_tem_o_literal_stock() -> None:
    """Todos os *_active.svg do GLYPHS_DIR real carregam o literal tintável."""
    real = glyph_mod._resolver_dir_glyphs()
    ativos = sorted(real.glob("*_active.svg"))
    assert len(ativos) == 19
    sem_literal = [
        p.name
        for p in ativos
        if "#bd93f9" not in p.read_text(encoding="utf-8").lower()
    ]
    assert not sem_literal, f"SVGs sem o literal #bd93f9: {sem_literal}"


# ---------------------------------------------------------------------------
# StickPreviewGtk.set_accent — desenho offscreen
# ---------------------------------------------------------------------------


def _render_stick(sp: StickPreviewGtk) -> bytes:
    """Desenha o widget num ImageSurface cairo próprio (determinístico)."""
    img = cairo.ImageSurface(cairo.FORMAT_ARGB32, 120, 120)
    ctx = cairo.Context(img)
    sp._on_draw(sp, ctx)
    img.flush()
    return bytes(img.get_data())


def test_stick_preview_set_accent_desenha_offscreen_sem_erro() -> None:
    sp = StickPreviewGtk(label="L3")
    off = Gtk.OffscreenWindow()
    off.add(sp)
    off.show_all()
    _drena_eventos()
    assert sp.get_allocated_width() >= 120

    render_padrao = _render_stick(sp)

    sp.set_accent(COR_A)
    assert sp._accent is not None
    ar, ag, ab = ensure_min_contrast(COR_A)
    assert sp._accent == (ar / 255, ag / 255, ab / 255)

    render_accent = _render_stick(sp)
    assert render_accent != render_padrao, "accent devia mudar o desenho"

    # Pressionado continua distinguível com accent ativo.
    sp.set_l3_pressed(True)
    render_accent_l3 = _render_stick(sp)
    assert render_accent_l3 != render_accent
    sp.set_l3_pressed(False)

    # None restaura EXATAMENTE o comportamento clássico.
    sp.set_accent(None)
    assert sp._accent is None
    assert _render_stick(sp) == render_padrao
    off.destroy()


def test_stick_preview_set_accent_aceita_lista_e_e_idempotente() -> None:
    sp = StickPreviewGtk(label="R3")
    sp.set_accent([16, 32, 72])
    accent_1 = sp._accent
    # Passar a cor JÁ ajustada dá no mesmo accent (idempotência do ensure).
    ajustada = ensure_min_contrast((16, 32, 72))
    sp.set_accent(ajustada)
    assert sp._accent == accent_1


# ---------------------------------------------------------------------------
# tintar_progressbar — CssProvider por widget
# ---------------------------------------------------------------------------


def test_tintar_progressbar_provider_por_widget_e_pixels() -> None:
    barra = Gtk.ProgressBar()
    barra.set_fraction(0.5)
    barra.set_size_request(200, 20)

    hex_aplicado = tintar_progressbar(barra, COR_A)
    assert hex_aplicado == rgb_para_hex(ensure_min_contrast(COR_A))

    off = Gtk.OffscreenWindow()
    off.add(barra)
    off.show_all()
    altura_img = 32
    dados, stride = _render_offscreen(off, 200, altura_img)

    esperado_fill = _hex_para_rgb(hex_aplicado)
    esperado_trough = _hex_para_rgb(TROUGH_HEX)

    # A geometria vertical do trough depende do tema (min-height, centragem):
    # varre a COLUNA inteira procurando a cor — hermético contra o tema.
    def _coluna_contem(x: int, esperado: tuple[int, int, int]) -> bool:
        for y in range(altura_img):
            r, g, b, a = _pixel(dados, stride, x, y)
            if a == 255 and all(
                abs(c - e) <= 2 for c, e in zip((r, g, b), esperado, strict=True)
            ):
                return True
        return False

    # fraction=0.5: x=20 cai no preenchimento; x=180 cai no trough.
    assert _coluna_contem(20, esperado_fill), (
        f"coluna x=20 devia conter o fill {esperado_fill}"
    )
    assert _coluna_contem(180, esperado_trough), (
        f"coluna x=180 devia conter o trough {esperado_trough}"
    )
    off.destroy()


def test_tintar_progressbar_atualiza_so_quando_a_cor_muda() -> None:
    barra = Gtk.ProgressBar()

    hex_1 = tintar_progressbar(barra, COR_A)
    provider_1 = barra._hefesto_tint_provider

    # Mesma cor => no-op total (provider intacto).
    hex_2 = tintar_progressbar(barra, COR_A)
    assert hex_2 == hex_1
    assert barra._hefesto_tint_provider is provider_1

    # Cor crua diferente com o MESMO hex ajustado => também no-op.
    hex_3 = tintar_progressbar(barra, ensure_min_contrast(COR_A))
    assert hex_3 == hex_1
    assert barra._hefesto_tint_provider is provider_1

    # Cor nova => provider substituído.
    hex_4 = tintar_progressbar(barra, COR_B)
    assert hex_4 != hex_1
    assert barra._hefesto_tint_provider is not provider_1
