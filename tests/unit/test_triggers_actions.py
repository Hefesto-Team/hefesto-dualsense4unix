"""Testes unitários de TriggersActionsMixin (AUDIT-FINDING-COVERAGE-ACTIONS-ZERO-01).

Cobrem:
  - Seleção de preset via dropdown de modo (Off, Rigid, Pulse, MultiPos*).
  - Aplicar trigger persistindo no draft e chamando IPC.
  - Reset para Off.
  - Mudança de preset posicional (MultiPositionFeedback/Vibration).
  - Collect de valores de sliders para payload IPC.

Padrão `_FakeMixin` + stubs de `gi` (armadilha A-12).
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest


def _install_gi_stubs() -> None:
    # Se PyGObject real está disponível, não fazemos nada (integração real).
    real_gi = False
    if "gi" in sys.modules and hasattr(sys.modules["gi"], "require_version"):
        try:
            from gi.repository import Gtk

            real_gi = getattr(Gtk, "__spec__", None) is not None and hasattr(
                Gtk, "Window"
            ) and "gi.repository" in str(getattr(Gtk, "__spec__", ""))
        except Exception:  # pragma: no cover
            real_gi = False
    if real_gi:
        return

    # Reutiliza módulos stub se já criados por testes anteriores (merge de atributos).
    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")
    gi_mod.require_version = lambda _n, _v: None  # type: ignore[attr-defined]
    repo_mod = sys.modules.get("gi.repository") or types.ModuleType(
        "gi.repository"
    )
    gtk_mod = sys.modules.get("gi.repository.Gtk") or types.ModuleType(
        "gi.repository.Gtk"
    )
    glib_mod = sys.modules.get("gi.repository.GLib") or types.ModuleType(
        "gi.repository.GLib"
    )

    class _Orientation:
        HORIZONTAL = 0
        VERTICAL = 1

    class _PositionType:
        LEFT = 0
        RIGHT = 1

    class _Adjustment:
        def __init__(
            self,
            value: float = 0,
            lower: float = 0,
            upper: float = 100,
            step_increment: float = 1,
            page_increment: float = 10,
        ) -> None:
            self.value = value

    class _Box:
        def __init__(self, *_a: Any, **_kw: Any) -> None:
            self._children: list[Any] = []

        def pack_start(self, child: Any, *_a: Any, **_kw: Any) -> None:
            self._children.append(child)

        def get_children(self) -> list[Any]:
            return list(self._children)

        def remove(self, child: Any) -> None:
            self._children.remove(child)

        def show_all(self) -> None:
            pass

        def set_homogeneous(self, _v: bool) -> None:
            pass

        def set_visible(self, _v: bool) -> None:
            pass

    class _Scale:
        def __init__(self, *_a: Any, **kw: Any) -> None:
            adjust = kw.get("adjustment")
            self._value: float = float(adjust.value) if adjust else 0.0

        def set_digits(self, _n: int) -> None:
            pass

        def set_value_pos(self, _p: int) -> None:
            pass

        def set_hexpand(self, _v: bool) -> None:
            pass

        def set_value(self, v: float) -> None:
            self._value = float(v)

        def get_value(self) -> float:
            return self._value

        def queue_draw(self) -> None:
            pass

        def connect(self, _signal: str, _cb: Any) -> None:
            pass

    class _Label:
        def __init__(self, *_a: Any, **kw: Any) -> None:
            self._text = kw.get("label", "")

        def set_xalign(self, _x: float) -> None:
            pass

        def set_size_request(self, _w: int, _h: int) -> None:
            pass

        def set_text(self, t: str) -> None:
            self._text = t

        def set_markup(self, m: str) -> None:
            self._text = m

    # Registrar classes mínimas adicionais (idempotente: só adiciona se ausente).
    for cls_name in (
        "Builder", "Window", "Button", "ToggleButton", "ComboBoxText",
        "Switch", "TextView", "TextBuffer",
    ):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))
    # Sempre sobrescrevemos estes com as fakes funcionais desta suite (não são placeholders).
    gtk_mod.Orientation = _Orientation  # type: ignore[attr-defined]
    gtk_mod.PositionType = _PositionType  # type: ignore[attr-defined]
    gtk_mod.Adjustment = _Adjustment  # type: ignore[attr-defined]
    gtk_mod.Box = _Box  # type: ignore[attr-defined]
    gtk_mod.Scale = _Scale  # type: ignore[attr-defined]
    gtk_mod.Label = _Label  # type: ignore[attr-defined]

    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]

    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import triggers_actions  # noqa: E402

# --- Fakes de widgets GTK ---------------------------------------------


class _FakeComboBox:
    def __init__(self, active_id: str | None = None) -> None:
        self._entries: list[tuple[str, str]] = []
        self._active_id: str | None = active_id
        self._visible = True

    def remove_all(self) -> None:
        self._entries.clear()

    def append(self, id_: str, label: str) -> None:
        self._entries.append((id_, label))

    def set_active_id(self, id_: str) -> None:
        self._active_id = id_

    def get_active_id(self) -> str | None:
        return self._active_id

    def get_visible(self) -> bool:
        return self._visible

    def set_visible(self, v: bool) -> None:
        self._visible = bool(v)


class _FakeStatusBar:
    def __init__(self) -> None:
        self.pushed: list[tuple[int, str]] = []
        self._ctr = 0

    def get_context_id(self, _k: str) -> int:
        self._ctr += 1
        return self._ctr

    def push(self, ctx: int, msg: str) -> None:
        self.pushed.append((ctx, msg))


def _mk_widgets() -> dict[str, Any]:
    from gi.repository import Gtk  # stubs instalados

    widgets: dict[str, Any] = {}
    for side in ("left", "right"):
        widgets[f"trigger_{side}_mode"] = _FakeComboBox()
        widgets[f"trigger_{side}_desc"] = Gtk.Label()
        widgets[f"trigger_{side}_params_box"] = Gtk.Box()
        widgets[f"trigger_{side}_preset_combo"] = _FakeComboBox()
        widgets[f"trigger_{side}_preset_row"] = Gtk.Box()
    widgets["status_bar"] = _FakeStatusBar()
    return widgets


class _FakeTriggersMixin:
    # Herdado do mixin real (atributo de classe frozenset).
    _MODES_COM_PRESET = triggers_actions.TriggersActionsMixin._MODES_COM_PRESET

    def __init__(self) -> None:
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default()
        self._guard_refresh = False
        self._trigger_preset_applying = False
        self._trigger_param_widgets = {"left": {}, "right": {}}
        self._widgets = _mk_widgets()

    def _get(self, key: str) -> Any:
        return self._widgets.get(key)


def _build_mixin(monkeypatch: pytest.MonkeyPatch) -> _FakeTriggersMixin:
    calls: list[tuple[str, str, list[int]]] = []

    def fake_trigger_set(side: str, mode: str, params: list[int]) -> bool:
        calls.append((side, mode, list(params)))
        return True

    monkeypatch.setattr(triggers_actions, "trigger_set", fake_trigger_set)

    inst = _FakeTriggersMixin()
    inst._trigger_set_calls = calls  # type: ignore[attr-defined]

    for name in (
        "install_triggers_tab",
        "_refresh_triggers_from_draft",
        "on_trigger_left_mode_changed",
        "on_trigger_right_mode_changed",
        "on_trigger_left_preset_changed",
        "on_trigger_right_preset_changed",
        "on_trigger_left_apply",
        "on_trigger_right_apply",
        "on_trigger_left_reset",
        "on_trigger_right_reset",
        "_on_mode_changed",
        "_on_preset_changed",
        "_update_preset_row_visibility",
        "_populate_preset_combo",
        "_update_preset_to_custom",
        "_rebuild_params",
        "_build_param_row",
        "_collect_values",
        "_apply_trigger",
        "_send_trigger_named",
        "_reset_trigger",
        "_toast_trigger",
    ):
        setattr(
            inst,
            name,
            triggers_actions.TriggersActionsMixin.__dict__[name].__get__(
                inst, type(inst)
            ),
        )
    return inst


# --- Testes -----------------------------------------------------------


def test_install_triggers_tab_popula_combo_de_modos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS

    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    combo_left = mixin._widgets["trigger_left_mode"]
    assert combo_left.get_active_id() == "Off"
    assert len(combo_left._entries) == len(PRESETS)


def test_on_trigger_mode_changed_atualiza_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._widgets["trigger_left_mode"]
    combo.set_active_id("Rigid")

    mixin.on_trigger_left_mode_changed(combo)

    assert mixin.draft.triggers.left.mode == "Rigid"
    assert mixin.draft.triggers.left.params == ()


def test_on_trigger_mode_changed_guard_refresh_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    mixin._guard_refresh = True
    combo = mixin._widgets["trigger_left_mode"]
    combo.set_active_id("Pulse")

    mixin.on_trigger_left_mode_changed(combo)

    # Draft não mudou porque guard estava ativo.
    assert mixin.draft.triggers.left.mode == "Off"


def test_apply_trigger_rigid_persiste_draft_e_chama_ipc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._widgets["trigger_left_mode"]
    combo.set_active_id("Rigid")
    mixin.on_trigger_left_mode_changed(combo)

    # Forçar valores de sliders via _trigger_param_widgets.
    widgets = mixin._trigger_param_widgets["left"]
    widgets["position"].set_value(5)
    widgets["force"].set_value(200)

    mixin.on_trigger_left_apply(None)

    assert mixin._trigger_set_calls == [("left", "Rigid", [5, 200])]
    assert mixin.draft.triggers.left.mode == "Rigid"
    assert mixin.draft.triggers.left.params == (5, 200)


def test_apply_trigger_multi_position_feedback_envia_strengths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._widgets["trigger_right_mode"]
    combo.set_active_id("MultiPositionFeedback")
    mixin.on_trigger_right_mode_changed(combo)

    widgets = mixin._trigger_param_widgets["right"]
    for i in range(10):
        widgets[f"pos_{i}"].set_value(i)

    mixin.on_trigger_right_apply(None)

    assert len(mixin._trigger_set_calls) == 1
    side, mode, params = mixin._trigger_set_calls[0]
    assert side == "right"
    assert mode == "MultiPositionFeedback"
    # Envia lista de 10 strengths (pos_0..pos_9).
    assert params == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_reset_trigger_envia_off(monkeypatch: pytest.MonkeyPatch) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._widgets["trigger_left_mode"]
    combo.set_active_id("Rigid")

    mixin.on_trigger_left_reset(None)

    assert combo.get_active_id() == "Off"
    assert mixin._trigger_set_calls == [("left", "Off", [])]


def test_on_preset_changed_feedback_popula_sliders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seleção de preset posicional preenche sliders com valores do preset."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    mode_combo = mixin._widgets["trigger_left_mode"]
    mode_combo.set_active_id("MultiPositionFeedback")
    mixin.on_trigger_left_mode_changed(mode_combo)

    preset_combo = mixin._widgets["trigger_left_preset_combo"]
    preset_combo.set_active_id("rampa_crescente")

    mixin.on_trigger_left_preset_changed(preset_combo)

    # Pelo menos um slider foi alterado (valor != 0 em pos_0).
    widgets = mixin._trigger_param_widgets["left"]
    assert any(widgets[f"pos_{i}"].get_value() > 0 for i in range(10))


def test_on_preset_changed_custom_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preset 'custom' não altera sliders."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    mode_combo = mixin._widgets["trigger_left_mode"]
    mode_combo.set_active_id("MultiPositionFeedback")
    mixin.on_trigger_left_mode_changed(mode_combo)

    widgets = mixin._trigger_param_widgets["left"]
    for i in range(10):
        widgets[f"pos_{i}"].set_value(0)

    preset_combo = mixin._widgets["trigger_left_preset_combo"]
    preset_combo.set_active_id("custom")
    mixin.on_trigger_left_preset_changed(preset_combo)

    # Todos continuam 0.
    for i in range(10):
        assert widgets[f"pos_{i}"].get_value() == 0


def test_collect_values_extrai_dict_de_sliders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    mode_combo = mixin._widgets["trigger_left_mode"]
    mode_combo.set_active_id("Rigid")
    mixin.on_trigger_left_mode_changed(mode_combo)

    widgets = mixin._trigger_param_widgets["left"]
    widgets["position"].set_value(3)
    widgets["force"].set_value(150)

    result = mixin._collect_values("left")
    assert result == {"position": 3, "force": 150}


def test_refresh_triggers_from_draft_sincroniza_widgets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Draft contendo modo Rigid propaga para combo + rebuild sliders."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    from hefesto_dualsense4unix.app.draft_config import TriggerDraft, TriggersDraft
    new_triggers = TriggersDraft(
        left=TriggerDraft(mode="Rigid", params=(4, 180)),
    )
    mixin.draft = mixin.draft.model_copy(update={"triggers": new_triggers})

    mixin._refresh_triggers_from_draft()

    combo = mixin._widgets["trigger_left_mode"]
    assert combo.get_active_id() == "Rigid"
    widgets = mixin._trigger_param_widgets["left"]
    assert widgets["position"].get_value() == 4
    assert widgets["force"].get_value() == 180


def test_apply_trigger_custom_envia_mode_e_forces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._widgets["trigger_right_mode"]
    combo.set_active_id("Custom")
    mixin.on_trigger_right_mode_changed(combo)

    widgets = mixin._trigger_param_widgets["right"]
    widgets["mode"].set_value(2)
    for i in range(7):
        widgets[f"force_{i}"].set_value(10 + i)

    mixin.on_trigger_right_apply(None)

    assert len(mixin._trigger_set_calls) == 1
    side, mode, params = mixin._trigger_set_calls[0]
    assert side == "right"
    assert mode == "Custom"
    # [mode, force_0..force_6] = [2, 10, 11, 12, 13, 14, 15, 16]
    assert params == [2, 10, 11, 12, 13, 14, 15, 16]
