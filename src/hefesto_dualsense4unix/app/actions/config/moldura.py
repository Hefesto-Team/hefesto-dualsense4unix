"""A moldura de uma seção da aba Configurações — o molde único das cinco."""
from __future__ import annotations

import contextlib
import weakref
from collections.abc import Iterator
from typing import Any

from hefesto_dualsense4unix.utils.i18n import _

CLASSE_TEM_DICA = "hefesto-tem-dica"

CLASSE_AJUDA = "hefesto-ajuda"

GLIFO_DE_AJUDA = "?"

_JA_LIGADOS: weakref.WeakSet[Any] = weakref.WeakSet()

MARGEM_VERTICAL = 10
MARGEM_HORIZONTAL = 12
ESPACAMENTO = 8


def _descer(widget: Any) -> Iterator[Any]:
    """Todo widget da subárvore, o topo incluído."""
    from gi.repository import Gtk

    yield widget
    if isinstance(widget, Gtk.Container):
        for filho in widget.get_children():
            yield from _descer(filho)


def merece_sublinhado(widget: Any) -> bool:
    """Se este widget é um rótulo que esconde explicação e não se anuncia."""
    from gi.repository import Gtk

    if not isinstance(widget, Gtk.Label):
        return False
    if not (widget.get_tooltip_text() or "").strip():
        return False
    if widget.get_ancestor(Gtk.Button) is not None:
        return False
    if _e_glifo_de_ajuda(widget):
        return False
    return not _tem_ajuda_ao_lado(widget)


def _tem_ajuda_ao_lado(widget: Any) -> bool:
    """Se algum irmão deste widget é o `?` de ajuda."""
    pai = widget.get_parent()
    if pai is None:
        return False
    return any(
        irmao is not widget and _e_glifo_de_ajuda(irmao)
        for irmao in pai.get_children()
    )


def marcar_afordancias(raiz: Any) -> int:
    """Dá a marca visual a todo ponto de dica da subárvore. Devolve quantos.

    POR QUE ISTO É UMA VARREDURA, E NÃO UMA LINHA EM CADA SEÇÃO.

    Os pontos de dica nascem espalhados por cinco módulos de seção, e vários
    deles nascem DEPOIS da montagem: o exame reescreve as cinco linhas quando o
    worker responde, e a mesa redesenha medidores e rádios a cada releitura.
    Uma chamada por ponto teria de ser escrita em cada um desses lugares e
    lembrada em cada ponto novo — e o defeito que esta função cura é exatamente
    o de dica que ninguém lembrou de anunciar. A varredura não tem como
    esquecer: quem põe `set_tooltip_text` ganha a marca sem saber que ela
    existe.

    É idempotente — `add_class` numa classe que já está não faz nada.
    """
    marcados = 0
    for widget in _descer(raiz):
        with contextlib.suppress(Exception):
            if _e_glifo_de_ajuda(widget):
                widget.get_style_context().add_class(CLASSE_AJUDA)
                marcados += 1
            elif merece_sublinhado(widget):
                widget.get_style_context().add_class(CLASSE_TEM_DICA)
                marcados += 1
        _ligar_o_add(widget)
    return marcados


def _e_glifo_de_ajuda(widget: Any) -> bool:
    """O `?` de ajuda: rótulo cujo texto é só `?` e que carrega uma dica."""
    from gi.repository import Gtk

    if not isinstance(widget, Gtk.Label):
        return False
    if (widget.get_text() or "").strip() != GLIFO_DE_AJUDA:
        return False
    return bool((widget.get_tooltip_text() or "").strip())


def _ligar_o_add(widget: Any) -> None:
    """Reagenda a varredura quando algo novo entra neste container."""
    from gi.repository import GLib, Gtk

    if not isinstance(widget, Gtk.Container) or widget in _JA_LIGADOS:
        return
    _JA_LIGADOS.add(widget)

    def _ao_adicionar(container: Any, _filho: Any) -> None:
        ref = weakref.ref(container)

        def _revarrer() -> bool:
            vivo = ref()
            if vivo is not None:
                with contextlib.suppress(Exception):
                    marcar_afordancias(vivo)
            return False

        GLib.idle_add(_revarrer)

    with contextlib.suppress(Exception):
        widget.connect("add", _ao_adicionar)


def moldura_de_secao(titulo: str, dica: str | None = None) -> tuple[Any, Any]:
    """Devolve ``(frame, caixa)`` — a moldura e a caixa onde a seção monta."""
    from gi.repository import Gtk

    frame = Gtk.Frame()
    rotulo = Gtk.Label(label=_(titulo))
    with contextlib.suppress(Exception):
        rotulo.get_style_context().add_class("hefesto-titulo-secao")
    if dica is not None:
        rotulo.set_tooltip_text(_(dica))
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class(CLASSE_TEM_DICA)
    rotulo.show()
    frame.set_label_widget(rotulo)

    with contextlib.suppress(Exception):
        frame.connect("map", lambda w: marcar_afordancias(w))

    frame.set_vexpand(False)

    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACAMENTO)
    caixa.set_margin_top(MARGEM_VERTICAL)
    caixa.set_margin_bottom(MARGEM_VERTICAL)
    caixa.set_margin_start(MARGEM_HORIZONTAL)
    caixa.set_margin_end(MARGEM_HORIZONTAL)
    frame.add(caixa)
    return frame, caixa


def rotulo_de_apoio(texto: str, *, largura_max: int = 92) -> Any:
    """Rótulo explicativo no padrão da casa: alinhado à esquerda e com quebra."""
    from gi.repository import Gtk

    rotulo = Gtk.Label(label=_(texto))
    rotulo.set_xalign(0.0)
    rotulo.set_halign(Gtk.Align.START)
    rotulo.set_line_wrap(True)
    rotulo.set_max_width_chars(largura_max)
    with contextlib.suppress(Exception):
        rotulo.get_style_context().add_class("dim-label")
    return rotulo
