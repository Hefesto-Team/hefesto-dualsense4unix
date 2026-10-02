"""Testes unitários de InputActionsMixin (FEAT-KEYBOARD-UI-01, sprint 59.3)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("input actions")

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS


class _FakeListStore:
    """Stand-in para `Gtk.ListStore` suportando operações mínimas."""

    def __init__(self) -> None:
        self.rows: list[list[str]] = []

    def append(self, row: list[str]) -> None:
        self.rows.append(list(row))

    def clear(self) -> None:
        self.rows.clear()

    def remove(self, treeiter: int) -> None:
        del self.rows[treeiter]

    def get_iter(self, path: str) -> int:
        return int(path)

    def set_value(self, treeiter: int, col: int, value: str) -> None:
        self.rows[treeiter][col] = value

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.rows)


class _FakeMixin:
    """Aproveita apenas a parte testável de `InputActionsMixin` sem GTK."""

    def __init__(self) -> None:
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default()
        self._key_bindings_store = _FakeListStore()
        self._toasts: list[str] = []

    def _get(self, _key: str) -> Any:
        return None

    def _toast_input(self, msg: str) -> None:
        self._toasts.append(msg)


class TestHumanizacaoTeclado:
    """KBD-01: exibição amigável  tokens crus (round-trip)."""

    def test_humanize_button(self) -> None:
        from hefesto_dualsense4unix.app.actions.input_actions import humanize_button

        assert humanize_button("l1") == "L1"
        assert humanize_button("create") == "Share / Create"
        assert humanize_button("touchpad_left_press") == "Touchpad — lado esquerdo"
        assert humanize_button("xpto") == "xpto"

    def test_humanize_binding(self) -> None:
        from hefesto_dualsense4unix.app.actions.input_actions import humanize_binding

        assert humanize_binding("KEY_LEFTALT+KEY_TAB") == "Alt + Tab"
        assert humanize_binding("KEY_SYSRQ") == "PrintScreen"
        assert humanize_binding("__OPEN_OSK__") == "Abrir teclado na tela"
        assert humanize_binding("KEY_C") == "C"

    def test_dehumanize_binding(self) -> None:
        from hefesto_dualsense4unix.app.actions.input_actions import dehumanize_binding

        assert dehumanize_binding("Alt + Tab") == "KEY_LEFTALT+KEY_TAB"
        assert dehumanize_binding("PrintScreen") == "KEY_SYSRQ"
        assert dehumanize_binding("Abrir teclado na tela") == "__OPEN_OSK__"
        assert dehumanize_binding("KEY_LEFTALT+KEY_TAB") == "KEY_LEFTALT+KEY_TAB"

    def test_round_trip_dos_defaults(self) -> None:
        """Todo binding default humanizado e de volta reproduz o token cru."""
        from hefesto_dualsense4unix.app.actions.input_actions import (
            dehumanize_binding,
            humanize_binding,
        )

        for tokens in DEFAULT_BUTTON_BINDINGS.values():
            cru = "+".join(tokens)
            assert dehumanize_binding(humanize_binding(cru)) == cru
