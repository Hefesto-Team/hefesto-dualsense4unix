"""Testes unitários de RumbleActionsMixin (AUDIT-FINDING-COVERAGE-ACTIONS-ZERO-01).

Cobrem a lógica pura de:
  - Seleção de política via toggles (economia/balanceado/max/auto).
  - Sincronização slider de intensidade <-> política.
  - Aplicar/parar rumble persistindo valores no draft e chamando IPC.
  - Refresh do draft para widgets.

Usa padrão `_FakeMixin` (descriptor protocol `__get__`) e stubs de
`gi.repository.{Gtk,GLib}` para rodar sem PyGObject instalado no venv
(armadilha A-12). Mesmo cenário de `test_status_actions_reconnect.py`.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest


def _install_gi_stubs() -> None:
    # Reutiliza módulos stub existentes (se outros testes já injetaram) para
    # merge de atributos — caso contrário cria do zero.
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

    # Classes mínimas (idempotente).
    for cls_name in (
        "Builder", "Window", "Button", "ToggleButton", "ComboBoxText",
        "Switch", "TextView", "TextBuffer", "Scale", "Label", "Box",
    ):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))

    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import rumble_actions  # noqa: E402

# --- Fakes de widgets GTK ---------------------------------------------


class _FakeScale:
    def __init__(self, value: float = 0.0) -> None:
        self._value = float(value)

    def get_value(self) -> float:
        return self._value

    def set_value(self, v: float) -> None:
        self._value = float(v)


class _FakeToggleButton:
    def __init__(self, active: bool = False) -> None:
        self._active = active

    def get_active(self) -> bool:
        return self._active

    def set_active(self, v: bool) -> None:
        self._active = bool(v)


class _FakeLabel:
    def __init__(self) -> None:
        self._visible = False
        self._text = ""

    def set_visible(self, v: bool) -> None:
        self._visible = bool(v)

    def get_visible(self) -> bool:
        return self._visible

    def set_text(self, t: str) -> None:
        self._text = t


class _FakeStatusBar:
    def __init__(self) -> None:
        self.pushed: list[tuple[int, str]] = []
        self._ctx_counter = 0

    def get_context_id(self, key: str) -> int:
        self._ctx_counter += 1
        return self._ctx_counter

    def push(self, ctx_id: int, msg: str) -> None:
        self.pushed.append((ctx_id, msg))


# --- FakeMixin ---------------------------------------------------------


class _FakeRumbleMixin:
    """Composição mínima pra rodar RumbleActionsMixin sem GTK real."""

    def __init__(self) -> None:
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default()
        self._guard_refresh = False
        self._rumble_policy = "balanceado"

        self._widgets: dict[str, Any] = {
            "rumble_policy_economia": _FakeToggleButton(),
            "rumble_policy_balanceado": _FakeToggleButton(active=True),
            "rumble_policy_max": _FakeToggleButton(),
            "rumble_policy_auto": _FakeToggleButton(),
            "rumble_policy_slider": _FakeScale(70.0),
            "rumble_policy_auto_label": _FakeLabel(),
            "rumble_weak_scale": _FakeScale(0.0),
            "rumble_strong_scale": _FakeScale(0.0),
            "status_bar": _FakeStatusBar(),
        }

    def _get(self, key: str) -> Any:
        return self._widgets.get(key)


def _build_mixin(monkeypatch: pytest.MonkeyPatch) -> _FakeRumbleMixin:
    """Instancia o mixin via composição + neutraliza IPC real."""
    calls: dict[str, list[Any]] = {
        "rumble_set": [],
        "rumble_stop": [],
        "rumble_policy_set": [],
        "rumble_policy_custom": [],
        "call_async": [],
    }

    def fake_rumble_set(weak: int, strong: int) -> bool:
        calls["rumble_set"].append((weak, strong))
        return True

    def fake_rumble_stop() -> bool:
        calls["rumble_stop"].append(True)
        return True

    def fake_rumble_policy_set(policy: str) -> bool:
        calls["rumble_policy_set"].append(policy)
        return True

    def fake_rumble_policy_custom(mult: float) -> bool:
        calls["rumble_policy_custom"].append(mult)
        return True

    def fake_call_async(
        method: str, params: dict, on_success: Any = None, on_failure: Any = None
    ) -> None:
        calls["call_async"].append((method, params))

    monkeypatch.setattr(rumble_actions, "rumble_set", fake_rumble_set)
    monkeypatch.setattr(rumble_actions, "rumble_stop", fake_rumble_stop)
    monkeypatch.setattr(rumble_actions, "rumble_policy_set", fake_rumble_policy_set)
    monkeypatch.setattr(
        rumble_actions, "rumble_policy_custom", fake_rumble_policy_custom
    )
    monkeypatch.setattr(rumble_actions, "call_async", fake_call_async)

    instance = _FakeRumbleMixin()
    instance._ipc_calls = calls  # type: ignore[attr-defined]

    for name in (
        "install_rumble_tab",
        "_sync_policy_from_state",
        "_apply_policy_to_widgets",
        "on_rumble_policy_economia",
        "on_rumble_policy_balanceado",
        "on_rumble_policy_max",
        "on_rumble_policy_auto",
        "_set_policy",
        "on_rumble_policy_slider_changed",
        "_activate_policy_toggle",
        "on_rumble_apply",
        "on_rumble_test_500ms",
        "on_rumble_stop",
        "_refresh_rumble_from_draft",
        "_read_scales",
        "_set_scales",
        "_rumble_test_stop",
        "_toast_rumble",
    ):
        setattr(
            instance,
            name,
            rumble_actions.RumbleActionsMixin.__dict__[name].__get__(
                instance, type(instance)
            ),
        )
    return instance


# --- Testes: política (toggles) ---------------------------------------


def test_on_rumble_policy_economia_ativa_preset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    btn = mixin._widgets["rumble_policy_economia"]
    btn.set_active(True)
    mixin.on_rumble_policy_economia(btn)

    assert mixin._rumble_policy == "economia"
    assert mixin._ipc_calls["rumble_policy_set"] == ["economia"]
    # Slider move para 30% (0.3 mult).
    assert mixin._widgets["rumble_policy_slider"].get_value() == pytest.approx(30.0)


def test_on_rumble_policy_balanceado_ativa_preset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    btn = mixin._widgets["rumble_policy_balanceado"]
    btn.set_active(True)
    mixin.on_rumble_policy_balanceado(btn)

    assert mixin._rumble_policy == "balanceado"
    assert "balanceado" in mixin._ipc_calls["rumble_policy_set"]


def test_on_rumble_policy_auto_mostra_label(monkeypatch: pytest.MonkeyPatch) -> None:
    mixin = _build_mixin(monkeypatch)
    btn = mixin._widgets["rumble_policy_auto"]
    btn.set_active(True)
    mixin.on_rumble_policy_auto(btn)

    assert mixin._rumble_policy == "auto"
    assert mixin._widgets["rumble_policy_auto_label"].get_visible() is True


def test_on_rumble_policy_inativo_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Toggle inativo (get_active=False) não dispara IPC."""
    mixin = _build_mixin(monkeypatch)
    btn = mixin._widgets["rumble_policy_max"]
    btn.set_active(False)
    mixin.on_rumble_policy_max(btn)

    assert mixin._ipc_calls["rumble_policy_set"] == []


def test_on_rumble_policy_guard_refresh_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com _guard_refresh ativo, handler não dispara IPC."""
    mixin = _build_mixin(monkeypatch)
    mixin._guard_refresh = True
    btn = mixin._widgets["rumble_policy_max"]
    btn.set_active(True)
    mixin.on_rumble_policy_max(btn)

    assert mixin._ipc_calls["rumble_policy_set"] == []


# --- Testes: slider de intensidade ------------------------------------


def test_on_rumble_policy_slider_changed_preset_balanceado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Slider em 70% casa mult canônico de balanceado (0.7)."""
    mixin = _build_mixin(monkeypatch)
    mixin._rumble_policy = "economia"
    slider = mixin._widgets["rumble_policy_slider"]
    slider.set_value(70.0)
    mixin.on_rumble_policy_slider_changed(slider)

    assert mixin._rumble_policy == "balanceado"
    assert "balanceado" in mixin._ipc_calls["rumble_policy_set"]


def test_on_rumble_policy_slider_changed_custom(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Slider em valor não-canônico (ex.: 55%) vira política custom."""
    mixin = _build_mixin(monkeypatch)
    slider = mixin._widgets["rumble_policy_slider"]
    slider.set_value(55.0)
    mixin.on_rumble_policy_slider_changed(slider)

    assert mixin._rumble_policy == "custom"
    assert mixin._ipc_calls["rumble_policy_custom"] == [pytest.approx(0.55)]
    for pid in (
        "rumble_policy_economia",
        "rumble_policy_balanceado",
        "rumble_policy_max",
        "rumble_policy_auto",
    ):
        assert mixin._widgets[pid].get_active() is False


# --- Testes: apply / test / stop --------------------------------------


def test_on_rumble_apply_persiste_draft_e_chama_ipc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin._widgets["rumble_weak_scale"].set_value(120)
    mixin._widgets["rumble_strong_scale"].set_value(200)

    mixin.on_rumble_apply(None)

    assert mixin.draft.rumble.weak == 120
    assert mixin.draft.rumble.strong == 200
    assert mixin._ipc_calls["rumble_set"] == [(120, 200)]


def test_on_rumble_stop_zera_scales_e_chama_ipc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin._widgets["rumble_weak_scale"].set_value(160)
    mixin._widgets["rumble_strong_scale"].set_value(220)

    mixin.on_rumble_stop(None)

    assert mixin._widgets["rumble_weak_scale"].get_value() == 0
    assert mixin._widgets["rumble_strong_scale"].get_value() == 0
    assert mixin._ipc_calls["rumble_stop"] == [True]


def test_on_rumble_test_500ms_aplica_defaults_quando_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Teste com sliders em 0 dispara valor default (weak=160, strong=220)."""
    mixin = _build_mixin(monkeypatch)
    monkeypatch.setattr(
        rumble_actions.GLib, "timeout_add", lambda _ms, _fn: 1
    )

    mixin.on_rumble_test_500ms(None)

    assert mixin._ipc_calls["rumble_set"] == [(160, 220)]
    assert mixin._widgets["rumble_weak_scale"].get_value() == 160
    assert mixin._widgets["rumble_strong_scale"].get_value() == 220


# --- Testes: _apply_policy_to_widgets + refresh ----------------------


def test_apply_policy_to_widgets_ativa_toggle_correto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin._apply_policy_to_widgets("max", 1.0)

    assert mixin._widgets["rumble_policy_max"].get_active() is True
    assert mixin._widgets["rumble_policy_economia"].get_active() is False
    assert mixin._widgets["rumble_policy_slider"].get_value() == pytest.approx(100.0)


def test_apply_policy_to_widgets_custom_usa_custom_mult(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Policy=custom move slider para custom_mult*100."""
    mixin = _build_mixin(monkeypatch)
    mixin._apply_policy_to_widgets("custom", 0.42)

    assert mixin._widgets["rumble_policy_slider"].get_value() == pytest.approx(42.0)
    assert mixin._widgets["rumble_policy_auto_label"].get_visible() is False


def test_refresh_rumble_from_draft_popula_scales(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    new_rumble = mixin.draft.rumble.model_copy(update={"weak": 88, "strong": 177})
    mixin.draft = mixin.draft.model_copy(update={"rumble": new_rumble})

    mixin._refresh_rumble_from_draft()

    assert mixin._widgets["rumble_weak_scale"].get_value() == 88.0
    assert mixin._widgets["rumble_strong_scale"].get_value() == 177.0


def test_install_rumble_tab_chama_state_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_rumble_tab()
    assert any(c[0] == "daemon.state_full" for c in mixin._ipc_calls["call_async"])
