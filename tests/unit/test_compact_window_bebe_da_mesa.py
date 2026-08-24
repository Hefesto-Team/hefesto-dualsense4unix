"""ONDA0-Z5/T7 — a janela compacta bebe da mesma fonte (`app.mesa`).

[COSMÉTICA]: com a derivação certa, o texto não muda quando topo e mesa
concordam (é o caso de todo dia) — muda de onde ele vem. A prova é o dublê da
T6: topo mentindo `connected: true`/`bt` com a mesa (`controllers`) vazia, o
estado exato medido em 23/08 (ONDA0-Z5 §2.2).
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("T7: a janela compacta bebe da mesma fonte")

from hefesto_dualsense4unix.app.compact_window import CompactWindow


class _FakeLabel:
    def __init__(self) -> None:
        self.markup: str | None = None

    def set_markup(self, markup: str) -> None:
        self.markup = markup

    def set_xalign(self, _v: float) -> None:
        pass


def _mk_window() -> CompactWindow:
    cw = CompactWindow(
        on_show_window=lambda: None,
        on_quit=lambda: None,
        on_list_profiles=lambda: [],
        on_switch_profile=lambda _name: True,
        on_state=lambda: None,
    )
    cw._status_label = _FakeLabel()  # type: ignore[assignment]
    cw._battery_label = _FakeLabel()  # type: ignore[assignment]
    return cw


def test_topo_mentindo_conectado_com_mesa_vazia_mostra_desconectado() -> None:
    cw = _mk_window()
    cw._render_state(
        {
            "connected": True,
            "transport": "bt",
            "battery_pct": 75,
            "active_profile": "vitoria",
            "controllers": [],  # a mesa medida em 23/08: ZERO controles
        }
    )
    assert cw._status_label is not None
    markup = cw._status_label.markup or ""
    assert "desconectado" in markup.lower(), (
        f"janela compacta mentiu 'conectado' com mesa vazia: {markup!r}"
    )
    assert "#ff5555" in markup


def test_mesa_com_um_controle_manda_mesmo_com_topo_divergindo() -> None:
    cw = _mk_window()
    cw._render_state(
        {
            "connected": True,
            "transport": "bt",  # topo diz bt
            "battery_pct": 80,
            "active_profile": "vitoria",
            "controllers": [
                {"connected": True, "is_primary": True, "transport": "usb"}
            ],  # a mesa diz usb — a mesa manda
        }
    )
    assert cw._status_label is not None
    markup = cw._status_label.markup or ""
    assert "USB" in markup
    assert "#50fa7b" in markup
