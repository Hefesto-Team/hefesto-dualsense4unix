"""Testes unitários de RumbleActionsMixin (AUDIT-FINDING-COVERAGE-ACTIONS-ZERO-01)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("rumble_actions: a vibração na janela")

import sys
import types
from typing import Any

import pytest


def _install_gi_stubs() -> None:
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
            pass

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

    for cls_name in (
        "Builder", "Window", "Button", "ToggleButton", "ComboBoxText",
        "Switch", "TextView", "TextBuffer", "Scale", "Label", "Box",
    ):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))

    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.source_remove = lambda *_a, **_kw: None  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

_PCT = {nome: mult * 100 for nome, mult in RUMBLE_POLICY_MULT.items()}


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

    def set_markup(self, t: str) -> None:
        self._text = t


class _FakeStatusBar:
    def __init__(self) -> None:
        self.pushed: list[tuple[int, str]] = []
        self._ctx_counter = 0

    def get_context_id(self, key: str) -> int:
        self._ctx_counter += 1
        return self._ctx_counter

    def pop(self, ctx_id: int) -> None:
        if self.pushed:
            self.pushed.pop()

    def push(self, ctx_id: int, msg: str) -> None:
        self.pushed.append((ctx_id, msg))


class _FakeRumbleMixin:
    """Composição mínima pra rodar RumbleActionsMixin sem GTK real."""

    def __init__(self) -> None:
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default()
        self._edit_target_uniq = None
        self._rumble_guard_refresh = False
        self._rumble_policy = "balanceado"
        self._rumble_test_source: int | None = None

        self._widgets: dict[str, Any] = {
            "rumble_policy_economia": _FakeToggleButton(),
            "rumble_policy_balanceado": _FakeToggleButton(active=True),
            "rumble_policy_max": _FakeToggleButton(),
            "rumble_policy_auto": _FakeToggleButton(),
            "rumble_policy_slider": _FakeScale(70.0),
            "rumble_policy_auto_label": _FakeLabel(),
            "rumble_weak_scale": _FakeScale(0.0),
            "rumble_strong_scale": _FakeScale(0.0),
            "rumble_state_label": _FakeLabel(),
            "status_bar": _FakeStatusBar(),
        }

    def _get(self, key: str) -> Any:
        return self._widgets.get(key)


def test_o_trilho_da_intensidade_vai_ate_o_teto_do_schema() -> None:
    """O trilho oferece a faixa INTEIRA que o schema aceita (`mult * 100`)."""
    from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX

    import re
    from pathlib import Path

    pagina = (
        Path(__file__).resolve().parents[2]
        / "src" / "hefesto_dualsense4unix"
        / "interface" / "paginas" / "05-vibracao.html"  # noqa-acento (pasta)
    ).read_text(encoding="utf-8")
    trilho = re.search(
        r'<input[^>]*type="range"[^>]*data-campo="mult-pos"[^>]*>', pagina
    )
    assert trilho is not None, (
        "o trilho `mult-pos` sumiu de `05-vibracao.html` — a coluna "
        "Intensidade perdeu o ajuste livre, ou a régua ficou cega"
    )
    atributos = dict(re.findall(r'([a-z-]+)="([^"]*)"', trilho.group(0)))
    assert float(atributos["max"]) == RUMBLE_CUSTOM_MULT_MAX * 100
    assert float(atributos["min"]) == 0.0


def test_faixa_do_trilho_cabe_no_que_o_handler_do_daemon_aceita() -> None:
    """A faixa da tela é subconjunto do que `rumble.policy_custom` aceita."""
    import asyncio
    from types import SimpleNamespace

    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    import re
    from pathlib import Path

    pagina = (
        Path(__file__).resolve().parents[2]
        / "src" / "hefesto_dualsense4unix"
        / "interface" / "paginas" / "05-vibracao.html"  # noqa-acento (pasta)
    ).read_text(encoding="utf-8")
    trilho = re.search(
        r'<input[^>]*type="range"[^>]*data-campo="mult-pos"[^>]*>', pagina
    )
    assert trilho is not None, (
        "o trilho `mult-pos` sumiu de `05-vibracao.html` — a coluna "
        "Intensidade perdeu o ajuste livre, ou a régua ficou cega"
    )
    atributos = dict(re.findall(r'([a-z-]+)="([^"]*)"', trilho.group(0)))
    topo = float(atributos["max"]) / 100.0

    class _Handlers(IpcHandlersMixin):
        def __init__(self) -> None:
            self.daemon = SimpleNamespace(
                config=SimpleNamespace(
                    rumble_policy="balanceado", rumble_policy_custom_mult=0.7
                )
            )

        def _mark_rumble_policy_manual(self) -> None:
            pass

    handlers = _Handlers()
    result = asyncio.run(handlers._handle_rumble_policy_custom({"mult": topo}))
    assert result["status"] == "ok"
    assert handlers.daemon.config.rumble_policy_custom_mult == pytest.approx(topo)


