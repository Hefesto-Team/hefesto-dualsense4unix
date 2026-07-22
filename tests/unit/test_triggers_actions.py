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

# --- Fakes headless de widgets Gtk usados pela aba Triggers ------------
# Módulo-level para servirem tanto ao stub de CI (_install_gi_stubs)
# quanto ao patch hermético dos bindings do módulo em _build_mixin.


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


def _install_gi_stubs() -> None:
    # Se PyGObject real está disponível, não fazemos nada (integração real).
    # GATE-SKIP-MASK-01: a checagem antiga só valia se "gi" JÁ estivesse em
    # sys.modules — na coleta a fio frio o stub entrava mesmo com GTK real
    # instalado e envenenava o processo inteiro.
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
            pass

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
    glib_mod.source_remove = lambda *_a, **_kw: None  # type: ignore[attr-defined]

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


class _FakeSegmentedSelector:
    """Stub do SegmentedSelector (FEAT-DSX-COMBO-TO-SEGMENTED-01).

    Espelha o subconjunto da API por-ID usado pela aba Triggers. Não dispara o
    handler "changed" em set_active_id (os testes invocam os handlers à mão,
    como faziam com o _FakeComboBox) — a semântica de emissão é coberta nos
    testes do próprio SegmentedSelector.
    """

    def __init__(self, wrap: bool = False) -> None:
        self.wrap = wrap
        self._items: list[tuple[str, str]] = []
        self._active_id: str | None = None
        self._visible = True
        self.handlers: list[tuple[str, Any]] = []

    def set_items(self, items: list[tuple[str, str]]) -> None:
        self._items = list(items)

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        self._active_id = the_id

    def connect(self, signal: str, cb: Any) -> None:
        self.handlers.append((signal, cb))

    def show_all(self) -> None:
        pass

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
    # GATE-SKIP-MASK-01: fakes headless direto (nada de gi/sys.modules) —
    # um Gtk.Box REAL rejeitaria o _FakeSegmentedSelector no pack_start.
    widgets: dict[str, Any] = {}
    for side in ("left", "right"):
        # FEAT-DSX-COMBO-TO-SEGMENTED-01: o combo de modo virou um slot (GtkBox)
        # onde install_triggers_tab empacota o SegmentedSelector.
        widgets[f"trigger_{side}_mode_slot"] = _Box()
        widgets[f"trigger_{side}_desc"] = _Label()
        widgets[f"trigger_{side}_params_box"] = _Box()
        widgets[f"trigger_{side}_preset_combo"] = _FakeComboBox()
        widgets[f"trigger_{side}_preset_row"] = _Box()
    widgets["status_bar"] = _FakeStatusBar()
    return widgets


class _FakeTriggersMixin:
    # Herdado do mixin real (atributo de classe frozenset).
    _MODES_COM_PRESET = triggers_actions.TriggersActionsMixin._MODES_COM_PRESET

    def __init__(self) -> None:
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default()
        # M1: guard renomeado por mixin (era _guard_refresh compartilhado).
        self._triggers_guard_refresh = False
        self._trigger_preset_applying = False
        self._trigger_param_widgets = {"left": {}, "right": {}}
        self._widgets = _mk_widgets()

    def _get(self, key: str) -> Any:
        return self._widgets.get(key)


def _build_mixin(monkeypatch: pytest.MonkeyPatch) -> _FakeTriggersMixin:
    calls: list[tuple[str, str, list[int]]] = []

    def fake_trigger_set(
        side: str, mode: str, params: list[int], uniq: str | None = None
    ) -> tuple[bool, str | None]:
        calls.append((side, mode, list(params)))
        return True, None

    monkeypatch.setattr(triggers_actions, "trigger_set_checked", fake_trigger_set)
    # FEAT-DSX-COMBO-TO-SEGMENTED-01: install_triggers_tab instancia o
    # SegmentedSelector real (precisa de display). Troca pelo stub headless.
    monkeypatch.setattr(
        triggers_actions, "SegmentedSelector", _FakeSegmentedSelector
    )
    # GATE-SKIP-MASK-01: em vez de envenenar sys.modules["gi"], trocamos os
    # bindings Gtk/GLib DO MÓDULO em teste pelos fakes headless. O
    # monkeypatch desfaz tudo no teardown — os demais testes do processo
    # seguem vendo o PyGObject real.
    monkeypatch.setattr(
        triggers_actions,
        "Gtk",
        types.SimpleNamespace(
            Orientation=_Orientation,
            PositionType=_PositionType,
            Adjustment=_Adjustment,
            Box=_Box,
            Scale=_Scale,
            Label=_Label,
        ),
    )
    monkeypatch.setattr(
        triggers_actions,
        "GLib",
        types.SimpleNamespace(
            timeout_add=lambda *_a, **_kw: 0,
            idle_add=lambda fn, *a, **kw: fn(*a, **kw),
            source_remove=lambda *_a, **_kw: None,
        ),
    )

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
        "_on_param_slider_changed",
        "_update_preset_to_custom",
        "_persist_params_to_draft",
        "_rebuild_params",
        "_build_param_row",
        "_collect_values",
        "_apply_trigger",
        "_send_trigger_named",
        "_reset_trigger",
        "_toast_trigger",
        "_schedule_live_preview",
        "_fire_live_preview",
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

    combo_left = mixin._trigger_mode["left"]
    assert combo_left.get_active_id() == "Off"
    assert len(combo_left._items) == len(PRESETS)
    # O handler "changed" foi conectado no código (não mais via Glade).
    assert any(sig == "changed" for sig, _cb in combo_left.handlers)


def test_on_trigger_mode_changed_atualiza_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")

    mixin.on_trigger_left_mode_changed(combo)

    assert mixin.draft.triggers.left.mode == "Rigid"
    # BUG-TRIGGERS-DRAFT-STALE-01: o draft já nasce com os defaults dos
    # sliders (antes gravava () — "Salvar Perfil" antes do live-preview
    # persistia o gatilho zerado). Rigid: position=5, force=200.
    assert mixin.draft.triggers.left.params == (5, 200)


def test_on_trigger_mode_changed_guard_refresh_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    mixin._triggers_guard_refresh = True
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Pulse")

    mixin.on_trigger_left_mode_changed(combo)

    # Draft não mudou porque guard estava ativo.
    assert mixin.draft.triggers.left.mode == "Off"


def test_apply_trigger_rigid_persiste_draft_e_chama_ipc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
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
    combo = mixin._trigger_mode["right"]
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
    # BUG-TRIGGER-FLAT-MULTIPOS-01: o draft TAMBÉM precisa guardar a lista plana
    # (antes gravava () -> perda silenciosa ao salvar/aplicar perfil).
    assert mixin.draft.triggers.right.mode == "MultiPositionFeedback"
    assert mixin.draft.triggers.right.params == (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)


def test_reset_trigger_envia_off(monkeypatch: pytest.MonkeyPatch) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
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

    mode_combo = mixin._trigger_mode["left"]
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
    mode_combo = mixin._trigger_mode["left"]
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
    mode_combo = mixin._trigger_mode["left"]
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

    combo = mixin._trigger_mode["left"]
    assert combo.get_active_id() == "Rigid"
    widgets = mixin._trigger_param_widgets["left"]
    assert widgets["position"].get_value() == 4
    assert widgets["force"].get_value() == 180


def test_apply_trigger_custom_envia_mode_e_forces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["right"]
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


# ---------------------------------------------------------------------------
# UI-TRIGGERS-LIVE-PREVIEW-01 — debounce + apply imediato no combobox change
# ---------------------------------------------------------------------------


def test_on_mode_changed_agenda_live_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trocar o combobox de modo agenda `_apply_trigger` via debounce 300ms."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    agendados: list[tuple[int, Any, str]] = []

    def fake_timeout_add(
        interval: int, fn: Any, *args: Any, **_kw: Any
    ) -> int:
        agendados.append((interval, fn, args[0] if args else ""))
        return 42  # handle fictício

    monkeypatch.setattr(triggers_actions.GLib, "timeout_add", fake_timeout_add)

    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Pulse")
    mixin.on_trigger_left_mode_changed(combo)

    assert agendados, "live preview não agendou GLib.timeout_add"
    interval, fn, side = agendados[0]
    assert interval == 300
    assert side == "left"
    assert callable(fn)


def test_schedule_live_preview_cancela_pendente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trocas rápidas devem cancelar o timer anterior antes de agendar novo."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    removidos: list[int] = []

    def fake_remove(handle: int) -> None:
        removidos.append(handle)

    monkeypatch.setattr(triggers_actions.GLib, "source_remove", fake_remove)
    monkeypatch.setattr(
        triggers_actions.GLib,
        "timeout_add",
        lambda *_a, **_kw: 99,
    )

    # Primeira agendagem grava handle 99.
    mixin._schedule_live_preview("left")
    assert mixin._trigger_live_preview_timer["left"] == 99
    # Segunda agendagem deve cancelar o handle anterior (99).
    mixin._schedule_live_preview("left")
    assert 99 in removidos


def test_fire_live_preview_aplica_e_zera_timer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_fire_live_preview` chama `_apply_trigger` e zera o handle."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    mixin._trigger_live_preview_timer["right"] = 77

    combo = mixin._trigger_mode["right"]
    combo.set_active_id("Rigid")
    mixin.on_trigger_right_mode_changed(combo)
    # _on_mode_changed dispara _schedule_live_preview que zera handle local
    # ao agendar; o teste foca o _fire_live_preview standalone.
    mixin._trigger_live_preview_timer["right"] = 77
    mixin._fire_live_preview("right")

    assert mixin._trigger_live_preview_timer["right"] == 0
    assert any(call[0] == "right" for call in mixin._trigger_set_calls)


# ---------------------------------------------------------------------------
# BUG-TRIGGERS-PRESET-DUP-01 — seletor de preset sem "Personalizar" duplicado
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode_id", ["MultiPositionFeedback", "MultiPositionVibration"])
def test_populate_preset_combo_sem_duplicar_personalizar(
    monkeypatch: pytest.MonkeyPatch, mode_id: str
) -> None:
    """Os dicts de labels JÁ trazem "custom"; o combo não pode duplicá-lo."""
    from hefesto_dualsense4unix.profiles.trigger_presets import (
        FEEDBACK_POSITION_LABELS,
        VIBRATION_POSITION_LABELS,
    )

    labels = (
        FEEDBACK_POSITION_LABELS
        if mode_id == "MultiPositionFeedback"
        else VIBRATION_POSITION_LABELS
    )
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    mixin._populate_preset_combo("left", mode_id)

    items = mixin._trigger_preset["left"]._items
    ids = [key for key, _label in items]
    # Exatamente uma entrada "custom", sempre por último (UX: Personalizar no fim).
    assert ids.count("custom") == 1
    assert ids[-1] == "custom"
    assert len(items) == len(labels)


# ---------------------------------------------------------------------------
# BUG-TRIGGERS-DRAFT-STALE-01 — slider/preset atualizam o draft (rodapé salva
# o que a usuária vê/sente) + agendam o live-preview
# ---------------------------------------------------------------------------


def test_slider_atualiza_draft_e_agenda_live_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mexer num slider grava os params correntes no draft e agenda o preview."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    agendados: list[tuple[int, str]] = []
    monkeypatch.setattr(
        triggers_actions.GLib,
        "timeout_add",
        lambda interval, _fn, *args, **_kw: (
            agendados.append((interval, args[0] if args else "")) or 7
        ),
    )

    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")
    mixin.on_trigger_left_mode_changed(combo)
    agendados.clear()  # descarta o preview do mode-changed; foco é o do slider

    widgets = mixin._trigger_param_widgets["left"]
    widgets["position"].set_value(7)
    # O stub de Gtk.Scale não emite "value-changed"; invoca o handler à mão
    # (é o que o sinal real dispara via _rebuild_params).
    mixin._on_param_slider_changed("left")

    assert mixin.draft.triggers.left.mode == "Rigid"
    assert mixin.draft.triggers.left.params == (7, 200)
    assert agendados == [(300, "left")]


def test_slider_durante_refresh_nao_grava_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refresh programático (guard ativo) não pode reescrever o draft."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")
    mixin.on_trigger_left_mode_changed(combo)
    draft_antes = mixin.draft

    mixin._triggers_guard_refresh = True
    try:
        mixin._trigger_param_widgets["left"]["position"].set_value(9)
        mixin._on_param_slider_changed("left")
    finally:
        mixin._triggers_guard_refresh = False

    assert mixin.draft is draft_antes


def test_preset_changed_atualiza_draft_e_agenda_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escolher um preset posicional persiste os valores no draft + preview."""
    from hefesto_dualsense4unix.profiles.trigger_presets import (
        FEEDBACK_POSITION_PRESETS,
    )

    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    agendados: list[tuple[int, str]] = []
    monkeypatch.setattr(
        triggers_actions.GLib,
        "timeout_add",
        lambda interval, _fn, *args, **_kw: (
            agendados.append((interval, args[0] if args else "")) or 7
        ),
    )

    mode_combo = mixin._trigger_mode["left"]
    mode_combo.set_active_id("MultiPositionFeedback")
    mixin.on_trigger_left_mode_changed(mode_combo)
    agendados.clear()

    preset_combo = mixin._widgets["trigger_left_preset_combo"]
    preset_combo.set_active_id("rampa_crescente")
    mixin.on_trigger_left_preset_changed(preset_combo)

    esperado = tuple(FEEDBACK_POSITION_PRESETS["rampa_crescente"])
    assert mixin.draft.triggers.left.mode == "MultiPositionFeedback"
    assert mixin.draft.triggers.left.params == esperado
    assert (300, "left") in agendados


# --- HARM-19: erro de validação explica o erro, não acusa o daemon ------


def _mensagem_real_do_daemon(mode: str, params: list[int]) -> str:
    """Mensagem que o daemon devolve ao recusar `params` (CODE_INVALID_PARAMS).

    Vem do `build_from_name` de verdade — é o que o `_handle_trigger_set` chama
    e o `ipc_server` converte em erro JSON-RPC. Assim o teste prova a
    COEXISTÊNCIA (o texto do daemon casa com o tradutor da aba), não a fantasia
    do teste sobre esse texto.
    """
    from hefesto_dualsense4unix.core.trigger_effects import build_from_name

    with pytest.raises(ValueError) as exc:
        build_from_name(mode, params)
    return str(exc.value)


def test_humanizar_erro_de_ordem_usa_os_rotulos_dos_sliders() -> None:
    from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec

    motivo = _mensagem_real_do_daemon("Bow", [5, 3, 4, 4])
    texto = triggers_actions.humanizar_erro_gatilho(motivo, get_spec("Bow"))

    assert texto == "Fim (3) precisa ser maior que Início (5)"


def test_humanizar_erro_de_faixa_usa_os_rotulos_dos_sliders() -> None:
    from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec

    motivo = _mensagem_real_do_daemon("Rigid", [5, 300])
    texto = triggers_actions.humanizar_erro_gatilho(motivo, get_spec("Rigid"))

    assert texto == "Força precisa estar entre 0 e 255 (você pediu 300)"


def test_humanizar_mensagem_desconhecida_devolve_none() -> None:
    assert triggers_actions.humanizar_erro_gatilho("pane geral", None) is None


def test_toast_de_validacao_explica_e_nao_culpa_o_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HARM-19: com o daemon VIVO recusando (Fim <= Início), o toast dizia
    "falhou (daemon offline?)" — mandava a usuária caçar o problema no lugar
    errado."""
    mixin = _build_mixin(monkeypatch)
    motivo = _mensagem_real_do_daemon("Bow", [5, 3, 4, 4])
    monkeypatch.setattr(
        triggers_actions,
        "trigger_set_checked",
        lambda *_a, **_kw: (False, motivo),
    )
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Bow")
    mixin.on_trigger_left_mode_changed(combo)
    widgets = mixin._trigger_param_widgets["left"]
    widgets["start"].set_value(5)
    widgets["end"].set_value(3)

    mixin.on_trigger_left_apply(None)

    _ctx, msg = mixin._widgets["status_bar"].pushed[-1]
    assert msg == (
        "Gatilho esquerdo (L2): Bow não aplicado — "
        "Fim (3) precisa ser maior que Início (5)"
    )
    assert "daemon" not in msg


def test_toast_de_daemon_offline_aponta_para_a_aba_sistema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem motivo = ninguém respondeu; JARG-01: em vez de "daemon offline?",
    o leigo é mandado ligar o Hefesto na aba Sistema."""
    mixin = _build_mixin(monkeypatch)
    monkeypatch.setattr(
        triggers_actions, "trigger_set_checked", lambda *_a, **_kw: (False, None)
    )
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")
    mixin.on_trigger_left_mode_changed(combo)

    mixin.on_trigger_left_apply(None)

    _ctx, msg = mixin._widgets["status_bar"].pushed[-1]
    assert msg == (
        "Gatilho esquerdo (L2): não consegui aplicar Rigid — o Hefesto pode "
        "estar desligado (ligue na aba Sistema)"
    )


def test_toast_de_motivo_desconhecido_mostra_o_texto_cru(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Texto cru do daemon ainda diz mais que "offline?" — nunca cair no ramo
    errado por não reconhecer o formato."""
    mixin = _build_mixin(monkeypatch)
    monkeypatch.setattr(
        triggers_actions,
        "trigger_set_checked",
        lambda *_a, **_kw: (False, "formato novo de recusa"),
    )
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")
    mixin.on_trigger_left_mode_changed(combo)

    mixin.on_trigger_left_apply(None)

    _ctx, msg = mixin._widgets["status_bar"].pushed[-1]
    assert msg == "Gatilho esquerdo (L2): Rigid não aplicado — formato novo de recusa"
