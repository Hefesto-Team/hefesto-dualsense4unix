"""Testes do SegmentedSelector (FEAT-DSX-COMBO-TO-SEGMENTED-01)."""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.widgets.segmented_selector import (
    SegmentedSelector,
    _SegmentedLogic,
)


class _FakeSeg(_SegmentedLogic):
    """Implementa os hooks de toolkit em Python puro (sem GTK)."""

    def __init__(self) -> None:
        self._init_logic(wrap=False)
        self.rebuilds: list[list[tuple[str, str]]] = []
        self.activations: list[int] = []
        self.changed_events: list[str | None] = []
        self._handlers: list[Any] = []

    def connect(self, signal: str, cb: Any) -> None:
        if signal == "changed":
            self._handlers.append(cb)

    def _create_buttons(self, items: list[tuple[str, str]]) -> None:
        self.rebuilds.append(list(items))

    def _activate_button(self, idx: int) -> None:
        self.activations.append(idx)

    def _emit_changed(self) -> None:
        self.changed_events.append(self.get_active_id())
        for cb in list(self._handlers):
            cb(self)


def test_index_of_encontra_e_falta() -> None:
    items = [("a", "A"), ("b", "B"), ("c", "C")]
    assert _SegmentedLogic._index_of(items, "b") == 1
    assert _SegmentedLogic._index_of(items, "z") is None
    assert _SegmentedLogic._index_of(items, None) is None


def test_set_items_constroi_sem_ativo() -> None:
    seg = _FakeSeg()
    seg.set_items([("any", "Qualquer"), ("game", "Jogo")])
    assert len(seg.rebuilds) == 1
    assert seg.get_active_id() is None


def test_set_items_idempotente_nao_reconstroi() -> None:
    seg = _FakeSeg()
    itens = [("a", "A"), ("b", "B")]
    seg.set_items(itens)
    seg.set_items(list(itens))
    assert len(seg.rebuilds) == 1


def test_set_items_preserva_ativo_se_existir() -> None:
    seg = _FakeSeg()
    seg.set_items([("a", "A"), ("b", "B"), ("c", "C")])
    seg.set_active_id("b")
    assert seg.get_active_id() == "b"
    seg.set_items([("a", "A"), ("b", "B")])
    assert seg.get_active_id() == "b"


def test_set_items_limpa_ativo_se_sumir() -> None:
    seg = _FakeSeg()
    seg.set_items([("a", "A"), ("b", "B")])
    seg.set_active_id("b")
    seg.set_items([("x", "X"), ("y", "Y")])
    assert seg.get_active_id() is None


def test_set_items_nao_emite_changed() -> None:
    seg = _FakeSeg()
    seg.set_items([("a", "A"), ("b", "B")])
    seg.set_active_id("a")
    seg.changed_events.clear()
    seg.set_items([("a", "A"), ("b", "B"), ("c", "C")])
    assert seg.changed_events == []


def test_set_active_id_emite_changed_uma_vez() -> None:
    seg = _FakeSeg()
    seg.set_items([("a", "A"), ("b", "B")])
    seg.set_active_id("b")
    assert seg.get_active_id() == "b"
    assert seg.changed_events == ["b"]
    assert seg.activations == [1]


def test_set_active_id_mesmo_id_nao_emite() -> None:
    seg = _FakeSeg()
    seg.set_items([("a", "A"), ("b", "B")])
    seg.set_active_id("b")
    seg.changed_events.clear()
    seg.set_active_id("b")
    assert seg.changed_events == []


def test_set_active_id_inexistente_noop() -> None:
    seg = _FakeSeg()
    seg.set_items([("a", "A"), ("b", "B")])
    seg.set_active_id("zzz")
    assert seg.get_active_id() is None
    assert seg.changed_events == []


def test_connect_handler_recebe_o_widget() -> None:
    seg = _FakeSeg()
    seg.set_items([("a", "A"), ("b", "B")])
    recebidos: list[Any] = []
    seg.connect("changed", lambda w: recebidos.append(w))
    seg.set_active_id("a")
    assert recebidos == [seg]
    assert recebidos[0].get_active_id() == "a"


def _gtk_pronto() -> bool:
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        return bool(Gtk.init_check()[0])
    except Exception:
        return False


@pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")
@pytest.mark.parametrize("wrap", [False, True])
def test_widget_real_smoke(wrap: bool) -> None:
    """Com display real: 1 botão ativo por vez, set_active_id emite "changed"."""
    ev: list[str | None] = []
    sel = SegmentedSelector(wrap=wrap)
    sel.connect("changed", lambda w: ev.append(w.get_active_id()))
    sel.set_items([("off", "Off"), ("rigid", "Rigid"), ("custom", "Custom")])
    assert sel.get_active_id() is None
    assert sum(b.get_active() for b in sel._buttons) == 0

    sel.set_active_id("custom")
    assert sel.get_active_id() == "custom"
    assert ev == ["custom"]
    assert sum(b.get_active() for b in sel._buttons) == 1

    sel.set_active_id("custom")
    sel.set_active_id("nao_existe")
    assert ev == ["custom"]

    sel._buttons[1].clicked()
    assert sel.get_active_id() == "rigid"
    assert ev == ["custom", "rigid"]
    assert sum(b.get_active() for b in sel._buttons) == 1


@pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")
def test_wrap_dispoe_em_grade_de_3_colunas_e_nao_empilha() -> None:
    """S3: o modo ``wrap`` não pode reportar a altura de tudo empilhado."""
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    itens = [(f"m{i}", f"Modo {i}") for i in range(19)]
    sel = SegmentedSelector(wrap=True)
    sel.set_items(itens)

    assert isinstance(sel._container, Gtk.Grid), (
        "o modo wrap precisa de um container que NÃO renegocie colunas pela "
        "largura recebida (era GtkFlowBox, que empilhava tudo)"
    )
    posicoes = {
        (
            sel._container.child_get_property(b, "left-attach"),
            sel._container.child_get_property(b, "top-attach"),
        )
        for b in sel._buttons
    }
    assert len(posicoes) == 19, "cada botão ocupa uma célula própria"
    assert max(c for c, _ in posicoes) == 2, "no máximo 3 colunas"
    assert max(r for _, r in posicoes) == 6, "19 itens em 3 colunas = 7 linhas"

    win = Gtk.OffscreenWindow()
    win.add(sel)
    win.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()

    _, altura = sel.get_preferred_height_for_width(480)
    assert altura < 300, (
        f"altura {altura}px: a grade de 7 linhas deve ficar MUITO abaixo dos "
        "606px que o FlowBox empilhado reportava"
    )
