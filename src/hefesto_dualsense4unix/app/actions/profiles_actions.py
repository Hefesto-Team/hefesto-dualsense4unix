"""Aba Perfis: lista + editor de matcher com persistência em disco.

Dois modos de editor:
- simples   (default): radios "Aplica a" + slider Prioridade humanamente legíveis.
- avancado  (toggle):  campos crus window_class / title_regex / process_name.

A preferência de modo persiste em ~/.config/hefesto-dualsense4unix/gui_preferences.json via
gui_prefs.load_gui_prefs / gui_prefs.set_pref.
"""
# ruff: noqa: E402
from __future__ import annotations

import json
from typing import Any

import gi
from pydantic import ValidationError

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs, set_pref
from hefesto_dualsense4unix.app.ipc_bridge import call_async, run_in_thread
from hefesto_dualsense4unix.app.widgets import SegmentedSelector
from hefesto_dualsense4unix.profiles.loader import (
    delete_profile,
    load_all_profiles,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
)
from hefesto_dualsense4unix.profiles.simple_match import (
    detect_simple_preset,
    from_simple_choice,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# Mapeamento radio-id -> chave de preset
_RADIO_IDS = ("any", "steam", "browser", "terminal", "editor", "game")

# FEAT-DSX-COMBO-TO-SEGMENTED-01: itens do seletor "Aplica a:" (id, rótulo curto).
# Antes vinham do `<items>` do GtkComboBoxText no Glade; agora alimentam o
# SegmentedSelector no código. Rótulos curtos para caber na aba; o contexto
# completo fica no tooltip do seletor.
_APLICA_A_ITEMS: list[tuple[str, str]] = [
    ("any", "Qualquer"),
    ("steam", "Steam"),
    ("browser", "Navegador"),
    ("terminal", "Terminal"),
    ("editor", "Editor"),
    ("game", "Jogo"),
]


class ProfilesActionsMixin(WidgetAccessMixin):
    """Controla a aba Perfis."""

    _profiles_store: Gtk.ListStore
    _mode_advanced: bool = False  # True = editor avançado ativo; default seguro sem GTK
    # PERF-GUI-PROFILE-LOAD-NONBLOCKING-01: cache em memória dos perfis. Evita
    # load_all_profiles() síncrono na thread GTK a cada clique/tecla. Populado
    # por _reload_profiles_store (thread worker); lido por
    # on_profile_selection_changed e _build_profile_from_editor.
    _profiles_cache: list[Profile]
    # BUG-ADVANCED-TOGGLE-CLOBBER-01: guard para set_active() programático em
    # _populate_editor não disparar on_profile_advanced_toggle (que persistiria
    # 'advanced_editor' indevidamente). Substitui o handler_block dummy que vazava.
    _suppress_advanced_toggle: bool = False
    # BUG-DUPLICATE-NO-CONFIG-COPY-01: perfil-fonte de uma duplicação em curso;
    # usado como base em _build_profile_from_editor para copiar triggers/LEDs/etc.
    _duplicate_source: Profile | None = None
    # FEAT-DSX-COMBO-TO-SEGMENTED-01: seletor "Aplica a:" em botões segmentados
    # (substitui o GtkComboBoxText `profile_aplica_a_combo`, fechado no clique
    # pelo cosmic-comp). Mesma API por-ID do combo.
    _aplica_a: Any

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

        # UI-PROFILES-RADIO-GROUP-REDESIGN-01 + FEAT-DSX-COMBO-TO-SEGMENTED-01:
        # 6 radios viraram combo e agora viram botões segmentados (sem popup;
        # imune ao bug do cosmic-comp). Mesma API por-ID; "changed" é emitido por
        # set_active_id, então os handlers rodam igual ao combo antigo.
        sel = SegmentedSelector(wrap=True)
        sel.set_items(_APLICA_A_ITEMS)
        sel.set_tooltip_text("Contexto em que este perfil será aplicado")
        slot = self._get("profile_aplica_a_slot")
        if slot is not None:
            slot.pack_start(sel, False, False, 0)
            sel.show_all()
        self._aplica_a = sel
        sel.connect("changed", self._on_aplica_a_changed)
        sel.connect("changed", lambda _c: self._refresh_preview())
        sel.set_active_id("any")

        # UI-PROFILES-RIGHT-PANEL-REBALANCE-01: preview JSON atualiza em tempo real
        # conforme inputs do editor. Reutiliza _build_profile_from_editor.
        for entry_id, signal in (
            ("profile_name_entry", "changed"),
            ("profile_simple_custom_name", "changed"),
            ("profile_window_class_entry", "changed"),
            ("profile_title_regex_entry", "changed"),
            ("profile_process_name_entry", "changed"),
        ):
            widget = self._get(entry_id)
            if widget is not None:
                widget.connect(signal, lambda _w: self._refresh_preview())
        scale = self._get("profile_priority_scale")
        if scale is not None:
            scale.connect("value-changed", lambda _w: self._refresh_preview())

        # Estado inicial do toggle a partir das preferências persistidas
        prefs = load_gui_prefs()
        self._mode_advanced = bool(prefs.get("advanced_editor", False))
        switch: Gtk.Switch = self._get("profile_advanced_switch")
        # T7: set_active programático no boot dispara on_profile_advanced_toggle,
        # que persistiria a pref no disco na thread GTK. Guard igual ao usado em
        # _populate_editor / on_profile_new.
        self._suppress_advanced_toggle = True
        try:
            switch.set_active(self._mode_advanced)
        finally:
            self._suppress_advanced_toggle = False
        self._apply_editor_mode()

        self._profiles_cache = []
        self._reload_profiles_store(on_done=self._sync_selection_with_active_profile)

    def _sync_selection_with_active_profile(self) -> None:
        """Consulta o daemon e seleciona a linha do perfil ativo (FEAT-GUI-LOAD-LAST-PROFILE-01).

        Reusa o handler IPC canônico ``daemon.status`` (que já retorna
        ``active_profile``). Chama via ``call_async`` para não bloquear a thread
        GTK. Se o daemon estiver offline, se ``active_profile`` for ``None`` ou
        se o perfil citado não existir no store atual, a chamada é no-op e a
        seleção fallback (primeiro da lista) feita por ``_reload_profiles_store``
        é preservada.
        """
        call_async(
            method="daemon.status",
            params=None,
            on_success=self._on_daemon_status_for_sync,
            on_failure=self._on_daemon_status_sync_failed,
            timeout_s=0.5,
        )

    def _on_daemon_status_for_sync(self, result: Any) -> bool:
        """Callback GTK: recebe daemon.status e seleciona perfil ativo se casar."""
        try:
            if not isinstance(result, dict):
                return False
            active = result.get("active_profile")
            if not isinstance(active, str) or not active:
                return False
            self._select_profile_by_name(active)
        except Exception as exc:
            logger.warning("profile_sync_callback_falhou", err=str(exc))
        return False  # GLib.idle_add: não repetir

    def _on_daemon_status_sync_failed(self, exc: Exception) -> bool:
        """Callback GTK: falha silenciosa — mantém fallback (primeiro da lista)."""
        logger.debug("profile_sync_daemon_offline", err=str(exc))
        return False

    def _select_profile_by_name(self, name: str) -> bool:
        """Seleciona a linha do store cujo nome bate com ``name``.

        Retorna True se encontrou e selecionou; False caso contrário (perfil não
        existe no store — ex.: deletado entre refresh e resposta IPC).
        """
        store = self._profiles_store
        tree: Gtk.TreeView = self._get("profiles_tree")
        tree_iter = store.get_iter_first()
        while tree_iter is not None:
            if str(store.get_value(tree_iter, 0)) == name:
                tree.get_selection().select_iter(tree_iter)
                path = store.get_path(tree_iter)
                tree.scroll_to_cell(path, None, False, 0.0, 0.0)
                return True
            tree_iter = store.iter_next(tree_iter)
        return False

    # --- handlers de toggle e radio ---

    def on_profile_advanced_toggle(
        self,
        switch: Gtk.Switch,
        state: bool,
    ) -> bool:
        """Alterna entre modo simples e avançado; persiste preferência."""
        # BUG-ADVANCED-TOGGLE-CLOBBER-01: ignora chamadas programáticas (set_active
        # em _populate_editor) — só persiste quando o usuário move o switch.
        if self._suppress_advanced_toggle:
            return False
        self._mode_advanced = state
        self._apply_editor_mode()
        set_pref("advanced_editor", state)
        return False  # retorno False = deixa o GTK atualizar o estado visual

    def _on_aplica_a_changed(self, combo: Any) -> None:
        """Mostra entry "Jogo específico" só quando o seletor == "game".

        ``combo`` é o ``SegmentedSelector`` (FEAT-DSX-COMBO-TO-SEGMENTED-01);
        mantém a mesma API por-ID do GtkComboBoxText anterior.
        """
        active_id = combo.get_active_id() or "any"
        box: Gtk.Box = self._get("profile_game_entry_box")
        if box is None:
            return
        if active_id == "game":
            box.show()
        else:
            box.hide()

    # --- handlers da lista ---

    def on_profile_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        name = self._selected_profile_name(selection)
        if name is None:
            return
        # PERF-GUI-PROFILE-LOAD-NONBLOCKING-01: lê do cache em memória em vez de
        # reler todos os perfis do disco a cada clique (load_all_profiles travava
        # a thread GTK).
        profile = self._find_cached_profile(name)
        if profile is None:
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
        self._duplicate_source = None  # perfil novo parte de defaults, não de cópia
        self._get("profile_name_entry").set_text("novo_perfil")
        self._get("profile_priority_scale").set_value(0)
        self._select_radio("any")
        self._get("profile_window_class_entry").set_text("")
        self._get("profile_title_regex_entry").set_text("")
        self._get("profile_process_name_entry").set_text("")
        self._get("profile_simple_custom_name").set_text("")
        # BUG-PROFILE-NEW-STALE-MODE-01: se o usuário vinha de um perfil de match
        # COMPLEXO, o editor ficou em modo avançado (stack/switch/_mode_advanced).
        # Sem resetar, "Salvar" monta um MatchCriteria VAZIO (não casa com nada),
        # em vez do "Qualquer" que o radio passou a mostrar. Volta ao modo simples
        # espelhando o ramo simples de _populate_editor.
        self._mode_advanced = False
        stack: Gtk.Stack = self._get("profile_editor_stack")
        if stack is not None:
            stack.set_visible_child_name("simples")
        switch: Gtk.Switch = self._get("profile_advanced_switch")
        if switch is not None:
            self._suppress_advanced_toggle = True
            try:
                switch.set_active(False)
            finally:
                self._suppress_advanced_toggle = False
        self._toast_profile("Novo perfil: edite e clique Salvar")

    def on_profile_duplicate(self, _btn: Gtk.Button | None) -> None:
        name = self._selected_profile_name()
        if name is None:
            self._toast_profile("Selecione um perfil para duplicar")
            return
        # BUG-DUPLICATE-NO-CONFIG-COPY-01: guarda o perfil-fonte para que
        # _build_profile_from_editor copie triggers/lightbar/LEDs/etc — antes a
        # cópia só mudava o nome e o resto virava default (perda da config real).
        self._duplicate_source = self._find_cached_profile(name)
        current = self._get("profile_name_entry").get_text()
        self._get("profile_name_entry").set_text(f"{current}_copia")
        self._toast_profile("Editor preenchido com cópia completa; ajuste o nome e Salvar")

    def on_profile_remove(self, _btn: Gtk.Button | None) -> None:
        name = self._selected_profile_name()
        if name is None:
            self._toast_profile("Selecione um perfil para remover")
            return
        # BUG-DELETE-NO-CONFIRM-01: remoção é permanente — pedir confirmação
        # (espelha o padrão de confirm_restore_default do rodapé e do CLI).
        from hefesto_dualsense4unix.app import gui_dialogs

        window = self._get("main_window")
        if not gui_dialogs.confirm_delete_profile(parent=window, name=name):
            self._toast_profile("Remoção cancelada.")
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
        # T4: profile.switch é I/O do daemon (asyncio.run no _safe_call síncrono
        # travava a thread GTK até o timeout). call_async despacha ao worker e
        # devolve o toast/refresh via GLib.idle_add — mesmo padrão async da aba.
        call_async(
            method="profile.switch",
            params={"name": name},
            on_success=lambda _result: self._on_profile_switch_success(name),
            on_failure=self._on_profile_switch_failure,
        )

    def _on_profile_switch_success(self, name: str) -> bool:
        """Callback GTK do switch de perfil: toast + re-sincroniza a seleção."""
        self._toast_profile(f"Perfil ativado: {name}")
        # Preserva o comportamento visível: seleção acompanha o perfil ativo
        # reportado pelo daemon após o switch.
        self._sync_selection_with_active_profile()
        return False  # GLib.idle_add: não repetir

    def _on_profile_switch_failure(self, exc: Exception) -> bool:
        """Callback GTK de falha do switch (daemon offline / erro de transporte)."""
        logger.debug("profile_switch_falhou", err=str(exc))
        self._toast_profile("Falha (daemon offline?)")
        return False

    def on_profile_reload(self, _btn: Gtk.Button | None) -> None:
        self._reload_profiles_store()
        self._toast_profile("Lista recarregada")

    def on_profile_save(self, _btn: Gtk.Button | None) -> None:
        try:
            profile = self._build_profile_from_editor()
        except (ValueError, ValidationError) as exc:
            self._toast_profile(f"Inválido: {exc}")
            return
        # BUG-PROFILE-SAVE-SILENT-OVERWRITE-01: avisa ao gravar por cima de OUTRO
        # perfil existente (não no caso de edição in-place do próprio selecionado).
        selected = self._selected_profile_name()
        cache_names = {p.name for p in getattr(self, "_profiles_cache", [])}
        if profile.name in cache_names and profile.name != selected:
            from hefesto_dualsense4unix.app import gui_dialogs

            window = self._get("main_window")
            if not gui_dialogs.prompt_overwrite_existing(parent=window, name=profile.name):
                self._toast_profile("Operação cancelada.")
                return
        try:
            save_profile(profile)
        except OSError as exc:
            self._toast_profile(f"Falha ao salvar: {exc}")
            return
        self._duplicate_source = None  # duplicação concluída
        self._reload_profiles_store(select_name=profile.name)
        self._toast_profile(f"Perfil salvo: {profile.name}")

    # --- helpers internos ---

    def _apply_editor_mode(self) -> None:
        """Aplica a página correta da stack conforme _mode_advanced."""
        stack: Gtk.Stack = self._get("profile_editor_stack")
        page = "avancado" if self._mode_advanced else "simples"
        stack.set_visible_child_name(page)

    def _selected_simple_choice(self) -> str:
        """Retorna o id ativo do seletor "Aplica a:".

        UI-PROFILES-RADIO-GROUP-REDESIGN-01: antes iterava 6 GtkRadioButton.
        FEAT-DSX-COMBO-TO-SEGMENTED-01: agora lê `get_active_id()` do
        SegmentedSelector (`self._aplica_a`). Fallback "any" preserva o
        comportamento anterior quando o seletor ainda não foi populado.
        """
        combo = getattr(self, "_aplica_a", None)
        if combo is None:
            return "any"
        active_id = combo.get_active_id()
        if active_id in _RADIO_IDS:
            return str(active_id)
        return "any"

    def _select_radio(self, choice: str) -> None:
        """Seleciona o id correspondente no seletor "Aplica a:".

        Nome histórico preservado para facilitar grep pelo contexto antigo;
        a implementação usa `set_active_id()` do SegmentedSelector em vez de
        `set_active(True)` num radio específico.
        """
        combo = getattr(self, "_aplica_a", None)
        if combo is None:
            return
        target_id = choice if choice in _RADIO_IDS else "any"
        combo.set_active_id(target_id)

    def _refresh_preview(self) -> None:
        """Atualiza o preview JSON do perfil em tempo real.

        UI-PROFILES-RIGHT-PANEL-REBALANCE-01. Reutiliza
        `_build_profile_from_editor` como fonte de verdade. Falha graciosa:
        se o editor estiver parcialmente preenchido e `_build_profile_from_editor`
        levantar `ValidationError`, mostra mensagem em vez de crashar.
        """
        label = self._get("profile_preview_label")
        if label is None:
            return
        try:
            profile = self._build_profile_from_editor()
        except ValidationError as exc:
            # Resume primeira violação para evitar diálogo enorme.
            first = exc.errors()[0] if exc.errors() else {"msg": str(exc)}
            msg = first.get("msg", str(exc))
            label.set_text(f"<perfil inválido: {msg}>")
            return
        except Exception as exc:  # preview não pode crashar GUI
            logger.debug("preview_build_falhou", err=str(exc))
            label.set_text(f"<preview indisponível: {exc}>")
            return

        try:
            payload = profile.model_dump(mode="json", exclude_none=True)
            pretty = json.dumps(payload, indent=2, ensure_ascii=False)
        except Exception as exc:
            label.set_text(f"<erro serializando perfil: {exc}>")
            return
        label.set_text(pretty)

    def _selected_profile_name(
        self,
        selection: Gtk.TreeSelection | None = None,
    ) -> str | None:
        sel = selection or self._get("profiles_tree").get_selection()
        model, tree_iter = sel.get_selected()
        if tree_iter is None:
            return None
        return str(model.get_value(tree_iter, 0))

    def _reload_profiles_store(
        self,
        select_name: str | None = None,
        on_done: Any | None = None,
    ) -> None:
        """Recarrega a lista de perfis SEM bloquear a thread GTK.

        PERF-GUI-PROFILE-LOAD-NONBLOCKING-01: load_all_profiles() (glob + FileLock
        + parse Pydantic) roda em thread worker; o store e o cache em memória
        (`_profiles_cache`) são atualizados no callback, na thread GTK. `on_done`
        (opcional) roda após popular o store (ex.: sincronizar a seleção com o
        perfil ativo no boot).
        """
        def _load() -> list[Profile]:
            return list(load_all_profiles())

        def _on_loaded(profiles: Any) -> bool:
            self._profiles_cache = list(profiles)
            self._populate_profiles_store(profiles, select_name)
            if on_done is not None:
                on_done()
            return False  # GLib.idle_add: não repetir

        run_in_thread(_load, _on_loaded)

    def _populate_profiles_store(
        self, profiles: list[Profile], select_name: str | None
    ) -> None:
        """Popula o ListStore a partir da lista de perfis (thread GTK)."""
        store = self._profiles_store
        store.clear()
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

    def _find_cached_profile(self, name: str) -> Profile | None:
        """Retorna o perfil do cache em memória pelo nome, ou None."""
        cache: list[Profile] = getattr(self, "_profiles_cache", [])
        for profile in cache:
            if profile.name == name:
                return profile
        return None

    def _populate_editor(self, profile: Profile) -> None:
        """Preenche o editor com os dados do perfil.

        Detecta automaticamente se o match bate com um preset simples:
        - bate → modo simples, seleciona radio correspondente.
        - não bate → força modo avançado para não perder informação.
        """
        # Selecionar um perfil existente cancela qualquer duplicação em curso.
        self._duplicate_source = None
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
            # BUG-ADVANCED-TOGGLE-CLOBBER-01: guard flag em vez de bloquear um
            # handler dummy recém-conectado (que vazava e não bloqueava o real).
            self._suppress_advanced_toggle = True
            try:
                switch.set_active(False)
            finally:
                self._suppress_advanced_toggle = False
            self._mode_advanced = False
        else:
            # Match complexo — força modo avançado.
            # BUG-PROFILE-SIMPLE-STALE-01: zera o editor simples para não vazar
            # estado de um perfil simples anterior ('game' + nome). Sem isso, se o
            # usuário depois desligar o switch Avançado, a página simples reaparece
            # com o preset/nome herdados e salvar sobrescreveria este match complexo.
            self._select_radio("any")
            self._get("profile_simple_custom_name").set_text("")
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
            self._suppress_advanced_toggle = True
            try:
                switch.set_active(True)
            finally:
                self._suppress_advanced_toggle = False
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

        # PERF-GUI-PROFILE-LOAD-NONBLOCKING-01: usa o cache (este método roda no
        # _refresh_preview a cada tecla/slider; reler o disco aqui travava a UI).
        existing = self._find_cached_profile(name)
        # BUG-DUPLICATE-NO-CONFIG-COPY-01: numa duplicação o nome novo ainda não
        # existe no cache -> sem o perfil-fonte a config viraria default. Usa a
        # fonte guardada por on_profile_duplicate como base.
        source = existing or (self._duplicate_source if self._duplicate_source else None)
        base: dict[str, Any] = (
            source.model_dump(mode="python") if source else {}
        )

        # FEAT-LED-BRIGHTNESS-03: brightness pendente do slider só é aplicado
        # quando o perfil-base NÃO tem brilho próprio. BUG-PROFILE-BRIGHTNESS-OVERWRITE-01:
        # antes sobrescrevia incondicionalmente com o global (default 1.0),
        # apagando o brilho persistido do perfil ao salvar pela aba Perfis.
        pending_brightness: float = getattr(self, "_pending_brightness", 1.0)
        leds_base: dict[str, Any] = dict(base.get("leds") or {})
        leds_base.setdefault("lightbar_brightness", pending_brightness)
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
        self._status_toast("profiles", msg)
