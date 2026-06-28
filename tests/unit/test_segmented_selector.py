"""Testes do SegmentedSelector (FEAT-DSX-COMBO-TO-SEGMENTED-01).

O widget substitui o GtkComboBox na COSMIC (popup fechado no clique pelo
cosmic-comp). A lógica por-ID vive em ``_SegmentedLogic`` (puro Python, sem GTK)
e é testada via uma subclasse com hooks fake — sem display, sem GtkRadioButton
real (a "mock de display" que o spec pede). Um smoke opcional exercita o widget
real quando há GTK + display utilizável (``Gtk.init_check``).

Semânticas cobertas (espelham o GtkComboBoxText):
  - set_items: idempotente; preserva o id ativo se ainda existir, senão limpa.
  - set_active_id: ativa o botão e EMITE "changed" — só quando o id muda.
  - get_active_id: reflete o ativo (ou None).
"""
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


# ---------------------------------------------------------------------------
# _index_of (lógica pura)
# ---------------------------------------------------------------------------


def test_index_of_encontra_e_falta() -> None:
    items = [("a", "A"), ("b", "B"), ("c", "C")]
    assert _SegmentedLogic._index_of(items, "b") == 1
    assert _SegmentedLogic._index_of(items, "z") is None
    assert _SegmentedLogic._index_of(items, None) is None


# ---------------------------------------------------------------------------
# set_items
# ---------------------------------------------------------------------------


def test_set_items_constroi_sem_ativo() -> None:
    seg = _FakeSeg()
    seg.set_items([("any", "Qualquer"), ("game", "Jogo")])
    assert len(seg.rebuilds) == 1
    assert seg.get_active_id() is None


def test_set_items_idempotente_nao_reconstroi() -> None:
    seg = _FakeSeg()
    itens = [("a", "A"), ("b", "B")]
    seg.set_items(itens)
    seg.set_items(list(itens))  # iguais → no-op
    assert len(seg.rebuilds) == 1


def test_set_items_preserva_ativo_se_existir() -> None:
    seg = _FakeSeg()
    seg.set_items([("a", "A"), ("b", "B"), ("c", "C")])
    seg.set_active_id("b")
    assert seg.get_active_id() == "b"
    # Nova lista que ainda contém "b" → ativo preservado.
    seg.set_items([("a", "A"), ("b", "B")])
    assert seg.get_active_id() == "b"


def test_set_items_limpa_ativo_se_sumir() -> None:
    seg = _FakeSeg()
    seg.set_items([("a", "A"), ("b", "B")])
    seg.set_active_id("b")
    seg.set_items([("x", "X"), ("y", "Y")])  # "b" sumiu
    assert seg.get_active_id() is None


def test_set_items_nao_emite_changed() -> None:
    seg = _FakeSeg()
    seg.set_items([("a", "A"), ("b", "B")])
    seg.set_active_id("a")
    seg.changed_events.clear()
    # Trocar itens preservando o ativo NÃO deve emitir "changed".
    seg.set_items([("a", "A"), ("b", "B"), ("c", "C")])
    assert seg.changed_events == []


# ---------------------------------------------------------------------------
# set_active_id / get_active_id / changed
# ---------------------------------------------------------------------------


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
    seg.set_active_id("b")  # já é o ativo → no-op (como o GtkComboBox)
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


# ---------------------------------------------------------------------------
# Smoke do widget REAL (precisa de GTK + display utilizável)
# ---------------------------------------------------------------------------


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
    # FIX #4 (None-state visual): NENHUM botão visível ativo — o founder oculto
    # do grupo segura o estado inicial, casando o visual com get_active_id()==None.
    # Sem isto, o 1º botão nasceria ativo e o item default ficaria inalcançável
    # por clique (clicar um rádio já-ativo não dispara "toggled").
    assert sum(b.get_active() for b in sel._buttons) == 0

    sel.set_active_id("custom")
    assert sel.get_active_id() == "custom"
    assert ev == ["custom"]
    # Exatamente um GtkRadioButton ativo.
    assert sum(b.get_active() for b in sel._buttons) == 1

    # id repetido/inexistente não reemite.
    sel.set_active_id("custom")
    sel.set_active_id("nao_existe")
    assert ev == ["custom"]

    # Clique do usuário (imune ao bug do cosmic-comp) emite "changed".
    sel._buttons[1].clicked()  # "rigid"
    assert sel.get_active_id() == "rigid"
    assert ev == ["custom", "rigid"]
    assert sum(b.get_active() for b in sel._buttons) == 1
