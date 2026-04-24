"""Aba "Mouse e Teclado" — handlers CRUD de key_bindings por perfil.

FEAT-KEYBOARD-UI-01 (sprint 59.3). Herda `MouseActionsMixin` para reaproveitar
os handlers de mouse existentes e estende com:

- `install_input_tab()` — popula o TreeView com bindings efetivos do perfil
  ativo (DEFAULT_BUTTON_BINDINGS mesclado com `draft.profile.key_bindings`).
- Handlers `on_key_binding_add`, `on_key_binding_remove`,
  `on_key_binding_restore_defaults` — CRUD sobre o ListStore, delegando
  persistência ao `profile.save` via footer.

Rename físico para `input_actions.py` segue o spec, mas `mouse_actions.py`
permanece como submódulo compatibilidade (classe `MouseActionsMixin` não é
removida) para evitar ripple em callers externos e em `main.glade` onde os
handlers de mouse continuam amarrados pelos IDs originais.
"""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk

from hefesto.app.actions.mouse_actions import MouseActionsMixin
from hefesto.core.keyboard_mappings import (
    DEFAULT_BUTTON_BINDINGS,
    format_binding,
    parse_binding,
)

# Legenda do layout de bindings — exibida acima do TreeView como referência
# rápida dos tokens aceitos. Tokens `__*__` são virtuais (OSK); demais são
# KEY_* canônicos do evdev.ecodes.
BINDINGS_LEGEND = (
    "<b>Formato de tecla:</b> KEY_* (ex: KEY_C, KEY_ENTER) "
    "ou __OPEN_OSK__ / __CLOSE_OSK__ para teclado virtual.\n"
    "<b>Combos:</b> separar por '+' (ex: KEY_LEFTALT+KEY_TAB).\n"
    "<b>Default:</b> Options=Super, Share=PrintScreen, L1=Alt+Shift+Tab, "
    "R1=Alt+Tab, L3=abrir OSK, R3=fechar OSK."
)


# Ordem canônica de exibição dos botões no TreeView. Corresponde aos 17 botões
# canônicos do DualSense mais as 3 regiões de touchpad.
CANONICAL_BUTTONS: tuple[str, ...] = (
    "cross",
    "circle",
    "triangle",
    "square",
    "dpad_up",
    "dpad_down",
    "dpad_left",
    "dpad_right",
    "l1",
    "r1",
    "l2",
    "r2",
    "l3",
    "r3",
    "options",
    "create",
    "ps",
    "touchpad_left_press",
    "touchpad_middle_press",
    "touchpad_right_press",
)


class InputActionsMixin(MouseActionsMixin):
    """Mixin da aba "Mouse e Teclado": mouse handlers + key_bindings CRUD."""

    _key_bindings_store: Any = None

    def install_input_tab(self) -> None:
        """Setup inicial da aba. Reusa `install_mouse_tab` + popula TreeView."""
        self.install_mouse_tab()
        self._install_key_bindings_treeview()
        self._refresh_key_bindings_from_draft()

    # ------------------------------------------------------------------
    # TreeView setup + refresh
    # ------------------------------------------------------------------

    def _install_key_bindings_treeview(self) -> None:
        """Cria/configura colunas do `key_bindings_treeview`. Idempotente."""
        tree: Gtk.TreeView | None = self._get("key_bindings_treeview")
        if tree is None:
            return
        if tree.get_model() is not None:
            self._key_bindings_store = tree.get_model()
            return
        store = Gtk.ListStore(
            GObject.TYPE_STRING,  # botão canônico
            GObject.TYPE_STRING,  # binding serializado (KEY_A+KEY_B)
        )
        tree.set_model(store)
        self._key_bindings_store = store
        for idx, title in ((0, "Botão"), (1, "Tecla(s)")):
            renderer = Gtk.CellRendererText()
            if idx == 1:
                renderer.set_property("editable", True)
                renderer.connect(
                    "edited", self._on_key_binding_cell_edited
                )
            column = Gtk.TreeViewColumn(title, renderer, text=idx)
            tree.append_column(column)
        legend: Gtk.Label | None = self._get("key_bindings_legend")
        if legend is not None:
            legend.set_markup(BINDINGS_LEGEND)

    def _refresh_key_bindings_from_draft(self) -> None:
        """Popula o store com as bindings efetivas do draft central.

        Efetiva = DEFAULT_BUTTON_BINDINGS quando `draft.key_bindings is None`
        (herda); `{}` = vazio (teclado silencioso); dict parcial = override
        explícito.
        """
        store = self._key_bindings_store
        if store is None:
            return
        store.clear()
        bindings = self._resolve_effective_bindings()
        for button in CANONICAL_BUTTONS:
            binding = bindings.get(button)
            if binding is None:
                continue
            store.append([button, format_binding(binding)])

    def _resolve_effective_bindings(self) -> dict[str, tuple[str, ...]]:
        """Resolve o draft atual em mapping de botões → tupla de tokens."""
        draft = getattr(self, "draft", None)
        if draft is None:
            return dict(DEFAULT_BUTTON_BINDINGS)
        raw = draft.key_bindings
        if raw is None:
            return dict(DEFAULT_BUTTON_BINDINGS)
        if not raw:
            return {}
        return {k: tuple(v) for k, v in raw.items()}

    # ------------------------------------------------------------------
    # CRUD handlers
    # ------------------------------------------------------------------

    def on_key_binding_add(self, _button: Any) -> None:
        """Adiciona row vazia para o primeiro botão canônico ainda sem row."""
        store = self._key_bindings_store
        if store is None:
            return
        existing = {row[0] for row in store}
        for candidate in CANONICAL_BUTTONS:
            if candidate not in existing:
                store.append([candidate, "KEY_SPACE"])
                self._persist_key_bindings_to_draft()
                return
        self._toast_input("Todos os botões já têm binding — edite os existentes.")

    def on_key_binding_remove(self, _button: Any) -> None:
        """Remove a row selecionada no TreeView."""
        tree: Gtk.TreeView | None = self._get("key_bindings_treeview")
        store = self._key_bindings_store
        if tree is None or store is None:
            return
        selection = tree.get_selection()
        _, treeiter = selection.get_selected()
        if treeiter is None:
            self._toast_input("Selecione uma linha para remover.")
            return
        store.remove(treeiter)
        self._persist_key_bindings_to_draft()

    def on_key_binding_restore_defaults(self, _button: Any) -> None:
        """Restaura DEFAULT_BUTTON_BINDINGS (draft.key_bindings = None)."""
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        self.draft = draft.model_copy(update={"key_bindings": None})
        self._refresh_key_bindings_from_draft()
        self._toast_input("Bindings do teclado restaurados para o default.")

    def _on_key_binding_cell_edited(
        self,
        _renderer: Gtk.CellRendererText,
        path: str,
        new_text: str,
    ) -> None:
        """Editor inline da coluna 'Tecla(s)' — valida e persiste."""
        store = self._key_bindings_store
        if store is None:
            return
        text = new_text.strip()
        if not text:
            return
        try:
            parse_binding(text)
        except ValueError as exc:
            self._toast_input(f"Binding inválido: {exc}")
            return
        treeiter = store.get_iter(path)
        store.set_value(treeiter, 1, text)
        self._persist_key_bindings_to_draft()

    def _persist_key_bindings_to_draft(self) -> None:
        """Serializa o store em dict e grava em `draft.key_bindings`.

        Store vazia → None (herda defaults). Dict não vazio → override
        explícito (consumido por `DraftConfig.to_profile`).
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        store = self._key_bindings_store
        if store is None:
            return
        new_bindings: dict[str, list[str]] = {}
        for row in store:
            button = row[0]
            try:
                tokens = list(parse_binding(row[1]))
            except ValueError:
                continue
            new_bindings[button] = tokens
        self.draft = draft.model_copy(
            update={"key_bindings": new_bindings or None}
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _toast_input(self, msg: str) -> None:
        """Toast em `status_bar`. Reusa ctx id "input" pra não brigar com mouse."""
        bar: Any = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id("input")
        bar.push(ctx_id, msg)


__all__ = [
    "BINDINGS_LEGEND",
    "CANONICAL_BUTTONS",
    "InputActionsMixin",
]
