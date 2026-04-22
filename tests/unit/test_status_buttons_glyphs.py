"""tests/unit/test_status_buttons_glyphs.py — testes do redesign UI-STATUS-STICKS-REDESIGN-01.

Verifica que `_render_live_state` / `_refresh_glyphs` atualizam os ButtonGlyphs
e os StickPreviewGtk corretamente sem acoplar a GTK3 real.

Cenários:
  (a) cross + dpad_up pressionados → set_pressed(True) exatamente nesses dois.
  (b) Nenhum botão pressionado → todos False.
  (c) L2/R2 analógicos: l2_raw > 30 ilumina glyph l2; ≤ 30 apaga.
  (d) l3 pressionado → stick_left.set_l3_pressed(True); título roxo.
  (e) r3 pressionado → stick_right.set_l3_pressed(True); título roxo.
  (f) Diff: estado igual ao anterior → set_pressed não chamado novamente.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Stubs de GTK para CI sem display
# ---------------------------------------------------------------------------

def _install_gi_stubs() -> None:
    if "gi" in sys.modules and hasattr(sys.modules["gi"], "require_version"):
        try:
            from gi.repository import Gtk  # noqa: F401
            return
        except Exception:
            pass

    gi_mod = types.ModuleType("gi")

    def _require_version(_n: str, _v: str) -> None:
        return None

    gi_mod.require_version = _require_version  # type: ignore[attr-defined]

    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    glib_mod = types.ModuleType("gi.repository.GLib")

    # Align enum stub
    class _FakeAlign:
        CENTER = "center"
        START = "start"

    class _FakeGrid:
        def __init__(self) -> None:
            self._children: list[Any] = []

        def set_row_spacing(self, *_a: object) -> None:
            pass

        def set_column_spacing(self, *_a: object) -> None:
            pass

        def set_halign(self, *_a: object) -> None:
            pass

        def set_valign(self, *_a: object) -> None:
            pass

        def attach(self, *_a: object) -> None:
            pass

        def show_all(self) -> None:
            pass

    class _FakeBox:
        def __init__(self, *_a: object, **_kw: object) -> None:
            self._children: list[Any] = []

        def pack_start(self, child: Any, *_a: object) -> None:
            self._children.append(child)

        def show(self) -> None:
            pass

    gtk_mod.Align = _FakeAlign  # type: ignore[attr-defined]
    gtk_mod.Grid = _FakeGrid  # type: ignore[attr-defined]
    gtk_mod.Box = _FakeBox  # type: ignore[attr-defined]
    gtk_mod.DrawingArea = object  # type: ignore[attr-defined]
    gtk_mod.Builder = object  # type: ignore[attr-defined]
    gtk_mod.Window = object  # type: ignore[attr-defined]
    gtk_mod.Button = object  # type: ignore[attr-defined]
    gtk_mod.ComboBoxText = object  # type: ignore[attr-defined]
    gtk_mod.Switch = object  # type: ignore[attr-defined]
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto.app.actions.status_actions import (  # noqa: E402
    ALL_BUTTONS,
    L2_R2_THRESHOLD,
    StatusActionsMixin,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeGlyph:
    """Stub de ButtonGlyph que rastreia chamadas a set_pressed."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._pressed = False
        self.chamadas: list[bool] = []

    def set_pressed(self, val: bool) -> None:
        self.chamadas.append(val)
        self._pressed = val

    @property
    def is_pressed(self) -> bool:
        return self._pressed


class _FakeStick:
    """Stub de StickPreviewGtk."""

    def __init__(self, label: str = "L") -> None:
        self._label = label
        self._x = 128
        self._y = 128
        self._l3_pressed = False

    def update(self, x: int, y: int) -> None:
        self._x = x
        self._y = y

    def set_l3_pressed(self, val: bool) -> None:
        self._l3_pressed = val

    def set_size_request(self, *_a: object) -> None:
        pass

    def show(self) -> None:
        pass


class _FakeLabel:
    def __init__(self) -> None:
        self.markup: str | None = None
        self.text: str | None = None

    def set_markup(self, mk: str) -> None:
        self.markup = mk

    def set_text(self, t: str) -> None:
        self.text = t

    def set_fraction(self, _f: float) -> None:
        pass


class _FakeBar(_FakeLabel):
    def set_fraction(self, _f: float) -> None:
        pass


class _FakeBuilder:
    """Builder mínimo que devolve fakes por ID."""

    def __init__(self) -> None:
        self._w: dict[str, Any] = {}

    def get_object(self, wid: str) -> Any:
        if wid not in self._w:
            if "bar" in wid:
                self._w[wid] = _FakeBar()
            else:
                self._w[wid] = _FakeLabel()
        return self._w[wid]


class _Host(StatusActionsMixin):
    """Host mínimo que injeta fakes nos atributos dinâmicos."""

    def __init__(self) -> None:
        self.builder = _FakeBuilder()
        self._reconnect_state = "online"
        self._consecutive_failures = 0
        self._last_buttons: frozenset[str] = frozenset()
        self._last_l2_lit = False
        self._last_r2_lit = False
        # Injeta glyphs fake para todos os botões do grid
        self._button_glyphs: dict[str, _FakeGlyph] = {  # type: ignore[assignment]
            nome: _FakeGlyph(nome) for nome in ALL_BUTTONS
        }
        # Injeta sticks fake
        self._stick_left: _FakeStick = _FakeStick("L3")  # type: ignore[assignment]
        self._stick_right: _FakeStick = _FakeStick("R3")  # type: ignore[assignment]


@pytest.fixture
def host() -> _Host:
    return _Host()


# ---------------------------------------------------------------------------
# (a) cross + dpad_up pressionados
# ---------------------------------------------------------------------------

def test_cross_e_dpad_up_pressionados(host: _Host) -> None:
    """cross e dpad_up recebem set_pressed(True); os demais recebem False."""
    state: dict[str, Any] = {
        "buttons": ["cross", "dpad_up"],
        "l2_raw": 0,
        "r2_raw": 0,
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
    }
    host._render_live_state(state)

    assert host._button_glyphs["cross"].is_pressed
    assert host._button_glyphs["dpad_up"].is_pressed

    for nome, glyph in host._button_glyphs.items():
        if nome not in ("cross", "dpad_up", "l2", "r2"):
            assert not glyph.is_pressed, f"{nome} devia estar False"


# ---------------------------------------------------------------------------
# (b) Nenhum botão pressionado
# ---------------------------------------------------------------------------

def test_nenhum_botao_pressionado(host: _Host) -> None:
    state: dict[str, Any] = {
        "buttons": [],
        "l2_raw": 0,
        "r2_raw": 0,
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
    }
    host._render_live_state(state)

    for nome, glyph in host._button_glyphs.items():
        assert not glyph.is_pressed, f"{nome} devia estar False"


# ---------------------------------------------------------------------------
# (c) L2/R2 analógicos por threshold
# ---------------------------------------------------------------------------

def test_l2_raw_acima_threshold_ilumina_glyph(host: _Host) -> None:
    state: dict[str, Any] = {
        "buttons": [],
        "l2_raw": L2_R2_THRESHOLD + 1,
        "r2_raw": 0,
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
    }
    host._render_live_state(state)
    assert host._button_glyphs["l2"].is_pressed
    assert not host._button_glyphs["r2"].is_pressed


def test_l2_raw_abaixo_threshold_apaga_glyph(host: _Host) -> None:
    # Primeiro acende
    state_on: dict[str, Any] = {
        "buttons": [],
        "l2_raw": L2_R2_THRESHOLD + 5,
        "r2_raw": 0,
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
    }
    host._render_live_state(state_on)
    assert host._button_glyphs["l2"].is_pressed

    # Depois apaga
    state_off: dict[str, Any] = {
        "buttons": [],
        "l2_raw": L2_R2_THRESHOLD,
        "r2_raw": 0,
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
    }
    host._render_live_state(state_off)
    assert not host._button_glyphs["l2"].is_pressed


def test_r2_raw_acima_threshold_ilumina_glyph(host: _Host) -> None:
    state: dict[str, Any] = {
        "buttons": [],
        "l2_raw": 0,
        "r2_raw": L2_R2_THRESHOLD + 10,
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
    }
    host._render_live_state(state)
    assert host._button_glyphs["r2"].is_pressed
    assert not host._button_glyphs["l2"].is_pressed


# ---------------------------------------------------------------------------
# (d) L3 pressionado — stick esquerdo roxo
# ---------------------------------------------------------------------------

def test_l3_pressionado_pinta_titulo_roxo(host: _Host) -> None:
    state: dict[str, Any] = {
        "buttons": ["l3"],
        "l2_raw": 0,
        "r2_raw": 0,
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
    }
    host._render_live_state(state)

    assert host._stick_left._l3_pressed
    assert not host._stick_right._l3_pressed

    titulo = host.builder.get_object("stick_left_title")
    assert titulo.markup is not None
    assert "#bd93f9" in titulo.markup

    titulo_dir = host.builder.get_object("stick_right_title")
    # Direito sem markup colorido
    assert titulo_dir.markup is not None
    assert "#bd93f9" not in titulo_dir.markup


# ---------------------------------------------------------------------------
# (e) R3 pressionado — stick direito roxo
# ---------------------------------------------------------------------------

def test_r3_pressionado_pinta_titulo_roxo(host: _Host) -> None:
    state: dict[str, Any] = {
        "buttons": ["r3"],
        "l2_raw": 0,
        "r2_raw": 0,
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
    }
    host._render_live_state(state)

    assert host._stick_right._l3_pressed
    assert not host._stick_left._l3_pressed

    titulo = host.builder.get_object("stick_right_title")
    assert titulo.markup is not None
    assert "#bd93f9" in titulo.markup


# ---------------------------------------------------------------------------
# (f) Diff: estado idêntico não dispara set_pressed novamente
# ---------------------------------------------------------------------------

def test_diff_estado_igual_nao_re_dispara_set_pressed(host: _Host) -> None:
    state: dict[str, Any] = {
        "buttons": ["circle"],
        "l2_raw": 0,
        "r2_raw": 0,
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
    }
    host._render_live_state(state)
    chamadas_apos_1 = {
        nome: len(g.chamadas) for nome, g in host._button_glyphs.items()
    }

    # Segundo tick com mesmo estado
    host._render_live_state(state)
    chamadas_apos_2 = {
        nome: len(g.chamadas) for nome, g in host._button_glyphs.items()
    }

    # Nenhum glyph deve ter recebido chamada adicional
    for nome in ALL_BUTTONS:
        assert chamadas_apos_1[nome] == chamadas_apos_2[nome], (
            f"set_pressed chamado novamente em '{nome}' sem mudança de estado"
        )


# ---------------------------------------------------------------------------
# (g) grid tem exatamente 16 entradas (ALL_BUTTONS)
# ---------------------------------------------------------------------------

def test_all_buttons_tem_16_entradas() -> None:
    assert len(ALL_BUTTONS) == 16, f"Esperado 16, obtido {len(ALL_BUTTONS)}"


# ---------------------------------------------------------------------------
# (h) reset_live_widgets apaga todos os glyphs
# ---------------------------------------------------------------------------

def test_reset_live_widgets_apaga_glyphs(host: _Host) -> None:
    # Primeiro acende alguns
    state: dict[str, Any] = {
        "buttons": ["cross", "triangle"],
        "l2_raw": 100,
        "r2_raw": 0,
        "lx": 200,
        "ly": 60,
        "rx": 128,
        "ry": 128,
    }
    host._render_live_state(state)
    assert host._button_glyphs["cross"].is_pressed

    # Reset
    host._reset_live_widgets()

    for nome, glyph in host._button_glyphs.items():
        assert not glyph.is_pressed, f"{nome} devia estar apagado após reset"
    assert not host._stick_left._l3_pressed
    assert not host._stick_right._l3_pressed
