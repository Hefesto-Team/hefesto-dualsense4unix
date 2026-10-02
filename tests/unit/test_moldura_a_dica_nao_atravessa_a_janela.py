"""MOLDURA — nenhum rótulo de apoio da aba Configurações atravessa a janela."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("largura dos rótulos de apoio da aba Configurações")

from collections.abc import Iterator
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
_gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app.actions.config.mixin import ConfigActionsMixin
from hefesto_dualsense4unix.app.constants import GUI_DIR
from tests.unit.aba_config_sem_a_janela import aba_config_montada
from hefesto_dualsense4unix.app.theme import (
    ESCALA_PADRAO,
    escalar_css,
    escalar_nome_da_fonte,
)

LARGURA_DA_MEDIDA = 1868

TETO_DO_ROTULO = 1100


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")


@pytest.fixture(autouse=True, scope="module")
def _tema_na_escala_que_sai() -> Iterator[None]:
    """Aplica o tema pelos dois canais de `apply_theme`, e desfaz."""

    delta = ESCALA_PADRAO
    tela = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    bruto = (GUI_DIR / "theme.css").read_text(encoding="utf-8")
    provider.load_from_data(escalar_css(bruto, delta).encode("utf-8"))
    if tela is not None:
        Gtk.StyleContext.add_provider_for_screen(
            tela, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    settings = Gtk.Settings.get_default()
    anterior = None
    if settings is not None and delta:
        anterior = settings.get_property("gtk-font-name")
        settings.set_property(
            "gtk-font-name", escalar_nome_da_fonte(anterior or "", delta)
        )
    yield
    if settings is not None and anterior is not None:
        settings.set_property("gtk-font-name", anterior)
    if tela is not None:
        Gtk.StyleContext.remove_provider_for_screen(tela, provider)


class _HospedeiroDaAba(ConfigActionsMixin):
    def __init__(self, builder: Gtk.Builder) -> None:
        self.builder = builder


def _descer(widget: Any) -> Iterator[Any]:
    yield widget
    if isinstance(widget, Gtk.Container):
        for filho in widget.get_children():
            yield from _descer(filho)


def _e_rotulo_de_apoio(widget: Any) -> bool:
    """A assinatura do que `rotulo_de_apoio` produz, sem perguntar pelo halign."""
    return (
        isinstance(widget, Gtk.Label)
        and widget.get_line_wrap()
        and widget.get_max_width_chars() > 0
        and "dim-label" in widget.get_style_context().list_classes()
    )


@pytest.fixture(scope="module")
def aba_montada() -> Any:
    """A aba de VERDADE, montada pelo mixin, numa janela da largura da medida."""
    caixa = aba_config_montada()
    pagina = Gtk.ScrolledWindow()
    pagina.add(caixa)
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class("hefesto-dualsense4unix-window")
    janela.add(pagina)
    janela.set_size_request(LARGURA_DA_MEDIDA, 1000)
    janela.show_all()
    for _ in range(3000):
        if not Gtk.events_pending():
            break
        Gtk.main_iteration()
    return pagina


def _rotulos_de_apoio(pagina: Any) -> list[Any]:
    achados = [w for w in _descer(pagina) if _e_rotulo_de_apoio(w) and w.get_mapped()]
    piso = 3
    assert len(achados) >= piso, (
        f"a bancada achou {len(achados)} rótulos de apoio mapeados na aba, e o "
        f"piso é {piso}. Menos que isso é sinal de que a assinatura de "
        "`_e_rotulo_de_apoio` deixou de casar com o que `rotulo_de_apoio` "
        "produz — e um teste que não acha o alvo passa sempre."
    )
    return achados


def test_nenhum_rotulo_de_apoio_atravessa_a_janela(aba_montada: Any) -> None:
    """Com a janela em 1868px, nenhuma dica passa de 1100px."""
    largos = [
        (w.get_allocation().width, w.get_text()[:60])
        for w in _rotulos_de_apoio(aba_montada)
        if w.get_allocation().width > TETO_DO_ROTULO
    ]
    assert not largos, (
        f"{len(largos)} rótulo(s) de apoio passaram do teto de "
        f"{TETO_DO_ROTULO}px numa janela de {LARGURA_DA_MEDIDA}px: {largos}. "
        "O `max_width_chars` só limita a largura NATURAL pedida — sem o "
        "`set_halign(Gtk.Align.START)` o pai entrega a largura toda ao rótulo e "
        "a frase sai numa linha só, de borda a borda."
    )


def test_o_rotulo_de_apoio_para_no_natural_e_nao_no_pai(aba_montada: Any) -> None:
    """A mesma cura, medida sem depender de nenhum número em pixels."""
    esticados = []
    for rotulo in _rotulos_de_apoio(aba_montada):
        natural = rotulo.get_preferred_width()[1]
        alocada = rotulo.get_allocation().width
        if alocada > natural + 1:
            esticados.append((alocada, natural, rotulo.get_text()[:60]))
    assert not esticados, (
        "rótulo(s) de apoio receberam mais que a própria largura natural "
        f"(alocada, natural, texto): {esticados}. O pai esticou o rótulo, que é "
        "o que o `set_halign(Gtk.Align.START)` existe para impedir."
    )
