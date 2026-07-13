"""Cards de controle da aba Início com bateria + fim do MAC (FEAT-STATE-PER-CONTROLLER-01).

Duas camadas, ambas herméticas (sem GTK real):

1. Funções puras de formatação (`_format_controller_subtitle` e
   `_format_controller_uniq_suffix`) — o contrato de texto dos cards.
2. `_render_home_controllers` com um Gtk fake injetado em ``sys.modules``
   (o método importa ``gi.repository`` dentro da função, então o
   ``monkeypatch.setitem`` cobre com ou sem PyGObject instalado — A-12).

Os handlers do SegmentedSelector (BUG-HOME-SEGMENTED-SIGNATURE-01) NÃO são
tocados aqui — seguem cobertos por ``test_home_actions_handlers.py``.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.home_actions import (
    HomeActionsMixin,
    _format_controller_subtitle,
    _format_controller_uniq_suffix,
)

# ---------------------------------------------------------------------------
# 1. Funções puras de formatação
# ---------------------------------------------------------------------------


class TestFormatSubtitle:
    def test_com_bateria_e_primario(self) -> None:
        assert (
            _format_controller_subtitle("usb", is_primary=True, battery_pct=87)
            == "USB  ·  primário  ·  87%"
        )

    def test_sem_bateria_omite_percentual(self) -> None:
        assert (
            _format_controller_subtitle("bt", is_primary=False, battery_pct=None)
            == "BT"
        )

    def test_bateria_zero_e_mostrada(self) -> None:
        """0% é dado REAL (bateria morta) — diferente de None (sem dado)."""
        assert (
            _format_controller_subtitle("bt", is_primary=False, battery_pct=0)
            == "BT  ·  0%"
        )

    def test_bool_nao_vira_bateria(self) -> None:
        """bool é subclasse de int — payload malformado não vira "True%"."""
        assert (
            _format_controller_subtitle("usb", is_primary=False, battery_pct=True)
            == "USB"
        )

    def test_transport_ausente_vira_interrogacao(self) -> None:
        assert (
            _format_controller_subtitle(None, is_primary=False, battery_pct=None)
            == "?"
        )


class TestFormatUniqSuffix:
    def test_mac_normalizado_vira_sufixo_de_6_hex(self) -> None:
        assert _format_controller_uniq_suffix("a0ab51c311f0") == "…c311f0"

    def test_none_e_vazio_omitem(self) -> None:
        assert _format_controller_uniq_suffix(None) is None
        assert _format_controller_uniq_suffix("") is None

    def test_nao_string_omite(self) -> None:
        assert _format_controller_uniq_suffix(123456) is None

    def test_uniq_curto_nao_estoura(self) -> None:
        assert _format_controller_uniq_suffix("f0") == "…f0"


# ---------------------------------------------------------------------------
# 2. Render dos cards com Gtk fake
# ---------------------------------------------------------------------------


class _StyleCtx:
    def __init__(self) -> None:
        self.classes: list[str] = []

    def add_class(self, name: str) -> None:
        self.classes.append(name)


class _FakeWidget:
    """Cobre o subconjunto de Gtk.Label/Gtk.Box usado pelo render dos cards."""

    def __init__(
        self,
        label: str | None = None,
        orientation: object = None,
        spacing: int | None = None,
    ) -> None:
        self.label = label
        self.children: list[_FakeWidget] = []
        self.style = _StyleCtx()

    def get_style_context(self) -> _StyleCtx:
        return self.style

    def set_xalign(self, value: float) -> None:
        pass

    def set_margin_end(self, value: int) -> None:
        pass

    def set_markup(self, markup: str) -> None:
        self.label = markup

    def pack_start(self, child: _FakeWidget, *args: object) -> None:
        self.children.append(child)

    def get_children(self) -> list[_FakeWidget]:
        return list(self.children)

    def remove(self, child: _FakeWidget) -> None:
        self.children.remove(child)

    def show_all(self) -> None:
        pass


class _Host:
    """Instância mínima com o que `_render_home_controllers` toca."""

    _render_home_controllers = HomeActionsMixin._render_home_controllers

    def __init__(self) -> None:
        self._home_controllers_box = _FakeWidget()


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gtk fake em ``sys.modules`` — o import local do render cai nele."""
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_FakeWidget,
        Box=_FakeWidget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


def _card_texts(card: _FakeWidget) -> list[str]:
    return [str(child.label) for child in card.children]


def test_render_mostra_bateria_e_fim_do_mac(fake_gtk: None) -> None:
    host = _Host()
    controllers: list[dict[str, Any]] = [
        {
            "index": 0,
            "connected": True,
            "transport": "usb",
            "is_primary": True,
            "uniq": "a0ab51c311f0",
            "battery_pct": 87,
        },
        {
            "index": 1,
            "connected": True,
            "transport": "bt",
            "is_primary": False,
            "uniq": None,
            "battery_pct": None,
        },
    ]

    host._render_home_controllers(controllers)

    cards = host._home_controllers_box.get_children()
    assert len(cards) == 2

    texts_p1 = _card_texts(cards[0])
    assert "USB  ·  primário  ·  87%" in texts_p1
    assert "…c311f0" in texts_p1
    # O identificador é discreto: classe dim-label no widget do MAC.
    uniq_widget = next(c for c in cards[0].children if c.label == "…c311f0")
    assert "dim-label" in uniq_widget.style.classes

    texts_p2 = _card_texts(cards[1])
    assert "BT" in texts_p2
    # Sem uniq/bateria: nada de "…" nem "%" no segundo card.
    assert not any("…" in t or "%" in t for t in texts_p2)


def test_render_sem_campos_novos_nao_regride(fake_gtk: None) -> None:
    """Payload antigo (daemon velho, sem uniq/battery_pct) segue renderizando."""
    host = _Host()
    host._render_home_controllers(
        [{"index": 0, "connected": True, "transport": "usb", "is_primary": True}]
    )

    (card,) = host._home_controllers_box.get_children()
    assert "USB  ·  primário" in _card_texts(card)


def test_render_lista_vazia_mostra_placeholder(fake_gtk: None) -> None:
    host = _Host()
    host._render_home_controllers([])

    (placeholder,) = host._home_controllers_box.get_children()
    assert placeholder.label == "Nenhum controle conectado."
