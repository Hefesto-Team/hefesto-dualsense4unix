"""Testes opt-in com Gtk REAL (AUDIT-FINDING-COVERAGE-ACTIONS-ZERO-01).

Complementam `test_input_actions.py` (que usa `_FakeListStore` para rodar
sem PyGObject) exercitando o `InputActionsMixin` contra `Gtk.ListStore`
real. Skipados quando PyGObject está indisponível ou
`Gtk.require_version('3.0')` falha (armadilha A-12).

Razão: `_FakeListStore` pode mascarar bugs onde o mixin assume detalhes
do `Gtk.ListStore` real (ex.: tipo de coluna, iteração, get_iter por path).
Estes testes validam a integração no ambiente que tem PyGObject habilitado
(dev local com `--with-tray`, CI com `python3-gi` no runner).
"""
from __future__ import annotations

from typing import Any

import pytest

# Probe não-fatal: se `gi`/Gtk indisponíveis, pytest skipa o módulo inteiro.
# Também detecta stubs ModuleType (outros testes desta suite injetam stubs
# em sys.modules["gi.repository.Gtk"] — são `ModuleType`, não o pacote real).
GTK_AVAILABLE = False
try:
    import types as _types_probe

    import gi as _gi_probe

    _gi_probe.require_version("Gtk", "3.0")
    from gi.repository import Gtk as _GtkReal

    # Stubs dos demais testes são `types.ModuleType` puros sem `ListStore`.
    # O PyGObject real expõe `Gtk.ListStore`, `Gtk.TreeView`, `Gtk.Template`.
    if (
        not isinstance(_GtkReal, _types_probe.ModuleType)
        or hasattr(_GtkReal, "ListStore")
    ) and hasattr(_GtkReal, "ListStore"):
        GTK_AVAILABLE = True
except Exception:  # pragma: no cover — sem PyGObject
    GTK_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not GTK_AVAILABLE,
    reason="PyGObject/Gtk3 ausente — opt-in de dev (armadilha A-12)",
)


def _build_mixin_with_real_store() -> Any:
    """Composição leve com `Gtk.ListStore` real (2 colunas: button, key_combo)."""
    from gi.repository import Gtk

    from hefesto_dualsense4unix.app.actions.input_actions import InputActionsMixin
    from hefesto_dualsense4unix.app.draft_config import DraftConfig

    class _RealStoreMixin:
        def __init__(self) -> None:
            self.draft = DraftConfig.default()
            self._key_bindings_store = Gtk.ListStore(str, str)
            self._toasts: list[str] = []

        def _get(self, _key: str) -> Any:
            return None

        def _toast_input(self, msg: str) -> None:
            self._toasts.append(msg)

    instance = _RealStoreMixin()
    for name in (
        "_resolve_effective_bindings",
        "_refresh_key_bindings_from_draft",
        "on_key_binding_add",
        "on_key_binding_remove",
        "on_key_binding_restore_defaults",
        "_persist_key_bindings_to_draft",
        "_on_key_binding_cell_edited",
    ):
        setattr(
            instance,
            name,
            InputActionsMixin.__dict__[name].__get__(instance, type(instance)),
        )
    return instance


def test_gtk_real_add_e_persiste_no_draft() -> None:
    """Add via mixin contra ListStore real propaga ao draft."""
    mixin = _build_mixin_with_real_store()
    mixin.on_key_binding_add(None)
    mixin._persist_key_bindings_to_draft()

    assert mixin.draft.key_bindings is not None
    assert "cross" in mixin.draft.key_bindings


def test_gtk_real_restore_defaults_zera_draft() -> None:
    """Restore com store real esvazia o draft (None = herda defaults)."""
    mixin = _build_mixin_with_real_store()
    mixin.draft = mixin.draft.model_copy(
        update={"key_bindings": {"triangle": ["KEY_C"]}}
    )
    mixin.on_key_binding_restore_defaults(None)

    assert mixin.draft.key_bindings is None


def test_gtk_real_resolve_efetivo_combina_defaults_e_overrides() -> None:
    """ListStore real: resolve aplica overrides e descarta defaults."""
    mixin = _build_mixin_with_real_store()
    mixin.draft = mixin.draft.model_copy(
        update={"key_bindings": {"triangle": ["KEY_C"]}}
    )
    resolved = mixin._resolve_effective_bindings()

    assert resolved == {"triangle": ("KEY_C",)}
