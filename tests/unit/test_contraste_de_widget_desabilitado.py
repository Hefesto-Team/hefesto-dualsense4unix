"""BUG-GUI-SWITCH-APAGADO-INVISIVEL-01 — o interruptor que não mostrava estado."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tests.conftest import exigir_gi_real

exigir_gi_real("contraste de widget desabilitado")

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.utils.color_contrast import razao_contraste

CSS = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "gui"
    / "theme.css"
)

TOLERANCIA_PCT = 3

PISO_FRACAO_DIFERENTE = 0.10

PISO_RAZAO_DO_MIOLO = 1.8

PISO_RAZAO_DA_MARCA = 3.0


def _drenar() -> None:
    """Assenta o laço. Widget sem alocação mede 1x1 e aprova qualquer desenho."""
    for _ in range(6):
        while Gtk.events_pending():
            Gtk.main_iteration()


def _render(fabrica: Callable[[], Gtk.Widget], *, sensivel: bool, com_o_css: bool):
    """Um widget desenhado numa `Gtk.OffscreenWindow`, devolvido como pixbuf."""
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class("hefesto-dualsense4unix-window")

    widget = fabrica()
    widget.set_sensitive(sensivel)
    widget.set_halign(Gtk.Align.CENTER)
    widget.set_valign(Gtk.Align.CENTER)
    for lado in ("start", "end", "top", "bottom"):
        getattr(widget, f"set_margin_{lado}")(8)
    janela.add(widget)

    provedor = None
    if com_o_css:
        provedor = Gtk.CssProvider()
        provedor.load_from_path(str(CSS))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provedor, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    janela.show_all()
    _drenar()
    pixbuf = janela.get_pixbuf()

    if provedor is not None:
        Gtk.StyleContext.remove_provider_for_screen(Gdk.Screen.get_default(), provedor)
    janela.destroy()
    return pixbuf


def _celulas(pixbuf) -> tuple[list[tuple[int, int, int]], int, int]:
    """O pixbuf como lista de (r, g, b), na ordem de leitura, mais as medidas."""
    dados = pixbuf.get_pixels()
    canais = pixbuf.get_n_channels()
    passo = pixbuf.get_rowstride()
    largura, altura = pixbuf.get_width(), pixbuf.get_height()
    saida: list[tuple[int, int, int]] = []
    for y in range(altura):
        base = y * passo
        for x in range(largura):
            i = base + x * canais
            saida.append((dados[i], dados[i + 1], dados[i + 2]))
    return saida, largura, altura


def distancia_ao_desabilitar(
    fabrica: Callable[[], Gtk.Widget],
    *,
    com_o_css: bool = True,
    tolerancia_pct: int = TOLERANCIA_PCT,
) -> tuple[int, int, float]:
    """Quanto o desenho de um widget MUDA quando ele fica insensível."""
    aceso = _render(fabrica, sensivel=True, com_o_css=com_o_css)
    apagado = _render(fabrica, sensivel=False, com_o_css=com_o_css)

    a, largura, altura = _celulas(aceso)
    b, _, _ = _celulas(apagado)
    total = largura * altura
    corte = tolerancia_pct * 255 / 100.0
    diferentes = sum(
        1
        for pa, pb in zip(a, b, strict=True)
        if max(abs(pa[0] - pb[0]), abs(pa[1] - pb[1]), abs(pa[2] - pb[2])) > corte
    )
    return diferentes, total, diferentes / total


def _cor_do_miolo(pixbuf, ligado: bool) -> tuple[int, int, int]:
    """Cor no centro do SLIDER — o miolo que anda, não o trilho."""
    celulas, largura, altura = _celulas(pixbuf)
    x = int(largura * (0.72 if ligado else 0.28))
    return celulas[(altura // 2) * largura + x]


def _cor_da_borda(pixbuf) -> tuple[int, int, int]:
    """Cor da BORDA no topo do widget, descendo pela coluna central."""
    celulas, largura, altura = _celulas(pixbuf)
    x = largura // 2
    fundo = celulas[x]
    for y in range(altura):
        p = celulas[y * largura + x]
        if max(abs(p[i] - fundo[i]) for i in range(3)) > 12:
            return p
    return fundo


def _interruptor(ligado: bool) -> Callable[[], Gtk.Widget]:
    def fabrica() -> Gtk.Widget:
        sw = Gtk.Switch()
        sw.set_active(ligado)
        sw.set_state(ligado)
        return sw

    return fabrica


def _botao() -> Gtk.Widget:
    return Gtk.Button(label="Aplicar")


ADORMECIDOS: list[tuple[str, Callable[[], Gtk.Widget]]] = [
    ("switch desligado", _interruptor(False)),
    ("switch ligado", _interruptor(True)),
    ("button", _botao),
]


@pytest.mark.parametrize("nome,fabrica", ADORMECIDOS, ids=[n for n, _ in ADORMECIDOS])
def test_widget_insensivel_desenha_diferente_de_um_sensivel(
    nome: str, fabrica: Callable[[], Gtk.Widget]
) -> None:
    """A mordida: sem `switch:disabled` no theme.css, os dois `switch` reprovam."""
    diferentes, total, fracao = distancia_ao_desabilitar(fabrica)

    assert fracao >= PISO_FRACAO_DIFERENTE, (
        f"`{nome}` insensível desenha praticamente igual ao sensível: só "
        f"{diferentes} de {total} px ({fracao:.2%}) mudam acima de "
        f"{TOLERANCIA_PCT}% de tolerância, e o piso é {PISO_FRACAO_DIFERENTE:.0%}. "
        "Ela não consegue ver que o controle está indisponível. Falta variante "
        "`:disabled` no theme.css para este widget, ou ela deixou de casar."
    )


@pytest.mark.parametrize("ligado", [False, True], ids=["desligado", "ligado"])
def test_o_miolo_do_interruptor_escurece_ao_ficar_indisponivel(ligado: bool) -> None:
    """O critério qualitativo: o botão que anda tem de APAGAR, não só a moldura."""
    aceso = _cor_do_miolo(_render(_interruptor(ligado), sensivel=True, com_o_css=True), ligado)
    apagado = _cor_do_miolo(
        _render(_interruptor(ligado), sensivel=False, com_o_css=True), ligado
    )

    razao = razao_contraste(aceso, apagado)

    assert razao >= PISO_RAZAO_DO_MIOLO, (
        f"o miolo do interruptor (ligado={ligado}) vai de "
        f"#{aceso[0]:02X}{aceso[1]:02X}{aceso[2]:02X} para "
        f"#{apagado[0]:02X}{apagado[1]:02X}{apagado[2]:02X} ao ficar insensível "
        f"— razão de {razao:.2f}:1, abaixo do piso de {PISO_RAZAO_DO_MIOLO}:1. "
        "Falta `switch:disabled slider` (e o `:checked:disabled slider`) no "
        "theme.css. O GTK stock entrega 2,90:1 de graça nesta mesma máquina."
    )


def test_o_gtk_stock_ja_entregava_a_distincao_que_o_tema_apagou() -> None:
    """Ancora a premissa: a régua é possível, e o defeito era NOSSO."""
    _, _, fracao = distancia_ao_desabilitar(_interruptor(False), com_o_css=False)

    if fracao < PISO_FRACAO_DIFERENTE:
        pytest.skip(
            "o tema GTK deste ambiente não rebaixa `switch` insensível sozinho "
            f"(só {fracao:.2%} do render muda): não há o que ancorar aqui. A "
            "cura continua coberta pelos testes que carregam o theme.css."
        )

    assert fracao >= PISO_FRACAO_DIFERENTE


def test_o_interruptor_indisponivel_continua_dizendo_se_esta_ligado() -> None:
    """O SEGUNDO eixo: rebaixar não pode custar a leitura de LIGADO x desligado."""
    borda_ligado = _cor_da_borda(_render(_interruptor(True), sensivel=False, com_o_css=True))
    borda_desligado = _cor_da_borda(
        _render(_interruptor(False), sensivel=False, com_o_css=True)
    )

    razao = razao_contraste(borda_ligado, borda_desligado)

    assert razao >= PISO_RAZAO_DA_MARCA, (
        "um interruptor INDISPONÍVEL não diz mais se está ligado: o anel do "
        f"ligado é #{borda_ligado[0]:02X}{borda_ligado[1]:02X}{borda_ligado[2]:02X} "
        f"e o do desligado é "
        f"#{borda_desligado[0]:02X}{borda_desligado[1]:02X}{borda_desligado[2]:02X} "
        f"— razão de {razao:.2f}:1, abaixo do piso de {PISO_RAZAO_DA_MARCA}:1. "
        "Provavelmente saiu o bloco `switch:checked:disabled` do theme.css, e o "
        "`switch:disabled` genérico passou a pintar o anel dos dois estados de "
        "@border_soft."
    )
