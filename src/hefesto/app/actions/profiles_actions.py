"""Aba Perfis: lista + editor de matcher com persistência em disco.

Dois modos de editor:
- simples   (default): radios "Aplica a" + slider Prioridade humanamente legíveis.
- avancado  (toggle):  campos crus window_class / title_regex / process_name.

A preferência de modo persiste em ~/.config/hefesto/gui_preferences.json via
gui_prefs.load_gui_prefs / gui_prefs.set_pref.
"""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi
from pydantic import ValidationError

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk

from hefesto.app.actions.base import WidgetAccessMixin
from hefesto.app.gui_prefs import load_gui_prefs, set_pref
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
from hefesto.profiles.simple_match import (
    detect_simple_preset,
    from_simple_choice,
)

# Mapeamento radio-id -> chave de preset
_RADIO_IDS = ("any", "steam", "browser", "terminal", "editor", "game")


class ProfilesActionsMixin(WidgetAccessMixin):
    """Controla a aba Perfis."""

    _profiles_store: Gtk.ListStore
    _mode_advanced: bool = False  # True = editor avançado ativo; default seguro sem GTK

    def install_profiles_tab(self) -> None:
        """Inicializa a aba Perfis: lista, colunas, handlers e estado inicial do toggle."""
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

        # Conecta handler de toggle para todos os radios
        for radio_id in _RADIO_IDS:
            radio: Gtk.RadioButton = self._get(f"profile_radio_{radio_id}")
            radio.connect("toggled", self._on_radio_toggled)

        # Estado inicial do toggle a partir das preferências persistidas
        prefs = load_gui_prefs()
        self._mode_advanced = bool(prefs.get("advanced_editor", False))
        switch: Gtk.Switch = self._get("profile_advanced_switch")
        switch.set_active(self._mode_advanced)
        self._apply_editor_mode()

        self._reload_profiles_store()

    # --- handlers de toggle e radio ---

    def on_profile_advanced_toggle(
        self,
        switch: Gtk.Switch,
        state: bool,
    ) -> bool:
        """Alterna entre modo simples e avançado; persiste preferência."""
        self._mode_advanced = state
        self._apply_editor_mode()
        set_pref("advanced_editor", state)
        return False  # retorno False = deixa o GTK atualizar o estado visual

    def _on_radio_toggled(self, radio: Gtk.RadioButton) -> None:
        """Mostra entry "Jogo específico" só quando o radio game está ativo."""
        game_active = self._get("profile_radio_game").get_active()
        box: Gtk.Box = self._get("profile_game_entry_box")
        if game_active:
            box.show()
        else:
            box.hide()

    # --- handlers da lista ---

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
        self._get("profile_priority_scale").set_value(0)
        self._get("profile_radio_any").set_active(True)
        self._get("profile_window_class_entry").set_text("")
        self._get("profile_title_regex_entry").set_text("")
        self._get("profile_process_name_entry").set_text("")
        self._get("profile_simple_custom_name").set_text("")
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

    # --- helpers internos ---

    def _apply_editor_mode(self) -> None:
        """Aplica a página correta da stack conforme _mode_advanced."""
        stack: Gtk.Stack = self._get("profile_editor_stack")
        page = "avancado" if self._mode_advanced else "simples"
        stack.set_visible_child_name(page)

    def _selected_simple_choice(self) -> str:
        """Retorna a chave do radio ativo na página simples."""
        for radio_id in _RADIO_IDS:
            radio: Gtk.RadioButton = self._get(f"profile_radio_{radio_id}")
            if radio.get_active():
                return radio_id
        return "any"

    def _select_radio(self, choice: str) -> None:
        """Seleciona o radio correspondente à chave fornecida."""
        widget_id = f"profile_radio_{choice}" if choice in _RADIO_IDS else "profile_radio_any"
        self._get(widget_id).set_active(True)

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
        """Preenche o editor com os dados do perfil.

        Detecta automaticamente se o match bate com um preset simples:
        - bate → modo simples, seleciona radio correspondente.
        - não bate → força modo avançado para não perder informação.
        """
        self._get("profile_name_entry").set_text(profile.name)
        prio = max(0, min(100, profile.priority))
        self._get("profile_priority_scale").set_value(prio)

        match = profile.match
        preset_key = detect_simple_preset(match)

        if preset_key is not None:
            # Match reconhecido como preset simples — usa modo simples
            self._select_radio(preset_key)
            # Se for "game", preenche o entry com o process_name
            if preset_key == "game" and isinstance(match, MatchCriteria):
                custom = match.process_name[0] if match.process_name else ""
                self._get("profile_simple_custom_name").set_text(custom)
            else:
                self._get("profile_simple_custom_name").set_text("")
            # Vai para página simples sem alterar a preferência persistida
            stack: Gtk.Stack = self._get("profile_editor_stack")
            stack.set_visible_child_name("simples")
            switch: Gtk.Switch = self._get("profile_advanced_switch")
            # Suprime o signal para não disparar on_profile_advanced_toggle
            with switch.handler_block(switch.connect("state-set", lambda *_: None)):
                switch.set_active(False)
            self._mode_advanced = False
        else:
            # Match complexo — força modo avançado
            if isinstance(match, MatchCriteria):
                self._get("profile_window_class_entry").set_text(
                    ",".join(match.window_class)
                )
                self._get("profile_title_regex_entry").set_text(
                    match.window_title_regex or ""
                )
                self._get("profile_process_name_entry").set_text(
                    ",".join(match.process_name)
                )
            else:
                self._get("profile_window_class_entry").set_text("")
                self._get("profile_title_regex_entry").set_text("")
                self._get("profile_process_name_entry").set_text("")
            stack = self._get("profile_editor_stack")
            stack.set_visible_child_name("avancado")
            switch = self._get("profile_advanced_switch")
            with switch.handler_block(switch.connect("state-set", lambda *_: None)):
                switch.set_active(True)
            self._mode_advanced = True

    def _build_profile_from_editor(self) -> Profile:
        """Constrói Profile a partir do editor (modo simples ou avançado)."""
        name = self._get("profile_name_entry").get_text().strip()
        priority = int(self._get("profile_priority_scale").get_value())

        match: MatchAny | MatchCriteria
        if self._mode_advanced:
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
        else:
            choice = self._selected_simple_choice()
            custom = self._get("profile_simple_custom_name").get_text().strip() or None
            match = from_simple_choice(choice=choice, custom_name=custom)

        existing = next(
            (p for p in load_all_profiles() if p.name == name),
            None,
        )
        base: dict[str, Any] = (
            existing.model_dump(mode="python") if existing else {}
        )

        # Lê brightness pendente do slider (FEAT-LED-BRIGHTNESS-03).
        pending_brightness: float = getattr(self, "_pending_brightness", 1.0)

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
