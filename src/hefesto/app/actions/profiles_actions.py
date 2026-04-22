"""Aba Perfis: lista + editor de matcher com persistência em disco."""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi
from pydantic import ValidationError

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk

from hefesto.app.actions.base import WidgetAccessMixin
from hefesto.app.ipc_bridge import profile_switch
from hefesto.profiles.loader import (
    delete_profile,
    load_all_profiles,
    save_profile,
)
from hefesto.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
)


class ProfilesActionsMixin(WidgetAccessMixin):
    """Controla a aba Perfis."""

    _profiles_store: Gtk.ListStore

    def install_profiles_tab(self) -> None:
        combo = self._get("profile_match_type_combo")
        combo.remove_all()
        combo.append("criteria", "criteria")
        combo.append("any", "any (fallback)")
        combo.set_active_id("criteria")

        tree: Gtk.TreeView = self._get("profiles_tree")
        store = Gtk.ListStore(
            GObject.TYPE_STRING,
            GObject.TYPE_INT,
            GObject.TYPE_STRING,
        )
        tree.set_model(store)
        self._profiles_store = store

        for idx, title in ((0, "Nome"), (1, "Prio"), (2, "Match")):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=idx)
            tree.append_column(column)

        tree.get_selection().connect(
            "changed", self.on_profile_selection_changed
        )
        self._reload_profiles_store()

    # --- handlers ---

    def on_profile_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        name = self._selected_profile_name(selection)
        if name is None:
            return
        try:
            profile = next(p for p in load_all_profiles() if p.name == name)
        except StopIteration:
            return
        self._populate_editor(profile)

    def on_profile_row_activated(
        self,
        _tree: Gtk.TreeView,
        _path: Gtk.TreePath,
        _column: Gtk.TreeViewColumn,
    ) -> None:
        self.on_profile_activate(None)

    def on_profile_new(self, _btn: Gtk.Button | None) -> None:
        self._get("profile_name_entry").set_text("novo_perfil")
        self._get("profile_priority_spin").set_value(0)
        self._get("profile_match_type_combo").set_active_id("criteria")
        self._get("profile_window_class_entry").set_text("")
        self._get("profile_title_regex_entry").set_text("")
        self._get("profile_process_name_entry").set_text("")
        self._toast_profile("Novo perfil: edite e clique Salvar")

    def on_profile_duplicate(self, _btn: Gtk.Button | None) -> None:
        name = self._selected_profile_name()
        if name is None:
            self._toast_profile("Selecione um perfil para duplicar")
            return
        current = self._get("profile_name_entry").get_text()
        self._get("profile_name_entry").set_text(f"{current}_copia")
        self._toast_profile("Editor preenchido com cópia; ajuste o nome e Salvar")

    def on_profile_remove(self, _btn: Gtk.Button | None) -> None:
        name = self._selected_profile_name()
        if name is None:
            self._toast_profile("Selecione um perfil para remover")
            return
        try:
            delete_profile(name)
        except (FileNotFoundError, OSError) as exc:
            self._toast_profile(f"Falha ao remover: {exc}")
            return
        self._reload_profiles_store()
        self._toast_profile(f"Perfil removido: {name}")

    def on_profile_activate(self, _btn: Gtk.Button | None) -> None:
        name = self._selected_profile_name()
        if name is None:
            self._toast_profile("Selecione um perfil para ativar")
            return
        ok = profile_switch(name)
        self._toast_profile(
            f"Perfil ativado: {name}" if ok else "Falha (daemon offline?)"
        )

    def on_profile_reload(self, _btn: Gtk.Button | None) -> None:
        self._reload_profiles_store()
        self._toast_profile("Lista recarregada")

    def on_profile_match_type_changed(self, combo: Gtk.ComboBoxText) -> None:
        is_any = combo.get_active_id() == "any"
        for wid in (
            "profile_window_class_entry",
            "profile_title_regex_entry",
            "profile_process_name_entry",
        ):
            self._get(wid).set_sensitive(not is_any)

    def on_profile_save(self, _btn: Gtk.Button | None) -> None:
        try:
            profile = self._build_profile_from_editor()
        except (ValueError, ValidationError) as exc:
            self._toast_profile(f"Inválido: {exc}")
            return
        try:
            save_profile(profile)
        except OSError as exc:
            self._toast_profile(f"Falha ao salvar: {exc}")
            return
        self._reload_profiles_store(select_name=profile.name)
        self._toast_profile(f"Perfil salvo: {profile.name}")

    # --- helpers ---

    def _selected_profile_name(
        self,
        selection: Gtk.TreeSelection | None = None,
    ) -> str | None:
        sel = selection or self._get("profiles_tree").get_selection()
        model, tree_iter = sel.get_selected()
        if tree_iter is None:
            return None
        return str(model.get_value(tree_iter, 0))

    def _reload_profiles_store(self, select_name: str | None = None) -> None:
        store = self._profiles_store
        store.clear()
        profiles = load_all_profiles()
        select_iter = None
        first_iter = None
        for profile in profiles:
            row_iter = store.append(
                [profile.name, profile.priority, profile.match.type]
            )
            if first_iter is None:
                first_iter = row_iter
            if profile.name == select_name:
                select_iter = row_iter
        target = select_iter if select_iter is not None else first_iter
        if target is not None:
            self._get("profiles_tree").get_selection().select_iter(target)

    def _populate_editor(self, profile: Profile) -> None:
        self._get("profile_name_entry").set_text(profile.name)
        self._get("profile_priority_spin").set_value(profile.priority)
        match = profile.match
        if isinstance(match, MatchAny):
            self._get("profile_match_type_combo").set_active_id("any")
            self._get("profile_window_class_entry").set_text("")
            self._get("profile_title_regex_entry").set_text("")
            self._get("profile_process_name_entry").set_text("")
        else:
            self._get("profile_match_type_combo").set_active_id("criteria")
            self._get("profile_window_class_entry").set_text(
                ",".join(match.window_class)
            )
            self._get("profile_title_regex_entry").set_text(
                match.window_title_regex or ""
            )
            self._get("profile_process_name_entry").set_text(
                ",".join(match.process_name)
            )

    def _build_profile_from_editor(self) -> Profile:
        name = self._get("profile_name_entry").get_text().strip()
        priority = int(self._get("profile_priority_spin").get_value())
        match_type = self._get("profile_match_type_combo").get_active_id()

        match: MatchAny | MatchCriteria
        if match_type == "any":
            match = MatchAny()
        else:
            wc = self._split_csv(
                self._get("profile_window_class_entry").get_text()
            )
            regex = self._get("profile_title_regex_entry").get_text().strip() or None
            pn = self._split_csv(
                self._get("profile_process_name_entry").get_text()
            )
            match = MatchCriteria(
                window_class=wc,
                window_title_regex=regex,
                process_name=pn,
            )

        existing = next(
            (p for p in load_all_profiles() if p.name == name),
            None,
        )
        base: dict[str, Any] = (
            existing.model_dump(mode="python") if existing else {}
        )

        # Lê brightness pendente do slider (FEAT-LED-BRIGHTNESS-03).
        # _pending_brightness vive em LightbarActionsMixin — acessado via
        # getattr para não criar dependência circular entre mixins.
        pending_brightness: float = getattr(self, "_pending_brightness", 1.0)

        # Garante que o sub-dict leds existe e inclui o brightness atual.
        leds_base: dict[str, Any] = dict(base.get("leds") or {})
        leds_base["lightbar_brightness"] = pending_brightness
        base["leds"] = leds_base

        base.update(
            {
                "name": name,
                "priority": priority,
                "match": match.model_dump(mode="python"),
            }
        )
        return Profile.model_validate(base)

    @staticmethod
    def _split_csv(raw: str) -> list[str]:
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _toast_profile(self, msg: str) -> None:
        bar: Any = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id("profiles")
        bar.push(ctx_id, msg)
