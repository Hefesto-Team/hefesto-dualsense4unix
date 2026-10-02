"""Sincronia da seleção da aba Perfis com perfil ativo (FEAT-GUI-LOAD-LAST-PROFILE-01)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("a janela sincroniza os perfis com o daemon")

import sys
import types
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock


def _install_gi_stubs() -> None:
    """Instala stubs mínimos de ``gi.repository`` se o módulo real não estiver disponível."""
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
            pass

    gi_mod = types.ModuleType("gi")

    def _require_version(_name: str, _ver: str) -> None:
        return None

    gi_mod.require_version = _require_version  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    glib_mod = types.ModuleType("gi.repository.GLib")
    gobject_mod = types.ModuleType("gi.repository.GObject")

    class _FakeStack:
        def set_visible_child_name(self, _name: str) -> None:  # pragma: no cover
            pass

    gtk_mod.Builder = object  # type: ignore[attr-defined]
    gtk_mod.Window = object  # type: ignore[attr-defined]
    gtk_mod.Button = object  # type: ignore[attr-defined]
    gtk_mod.ComboBoxText = object  # type: ignore[attr-defined]
    gtk_mod.Switch = object  # type: ignore[attr-defined]
    gtk_mod.TextView = object  # type: ignore[attr-defined]
    gtk_mod.TextBuffer = object  # type: ignore[attr-defined]
    gtk_mod.TreeView = object  # type: ignore[attr-defined]
    gtk_mod.TreeViewColumn = object  # type: ignore[attr-defined]
    gtk_mod.CellRendererText = object  # type: ignore[attr-defined]
    gtk_mod.ListStore = object  # type: ignore[attr-defined]
    gtk_mod.TreeSelection = object  # type: ignore[attr-defined]
    gtk_mod.TreePath = object  # type: ignore[attr-defined]
    gtk_mod.Box = object  # type: ignore[attr-defined]
    gtk_mod.Entry = object  # type: ignore[attr-defined]
    gtk_mod.RadioButton = object  # type: ignore[attr-defined]
    gtk_mod.Scale = object  # type: ignore[attr-defined]
    gtk_mod.Stack = _FakeStack  # type: ignore[attr-defined]
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    gobject_mod.TYPE_STRING = "str"  # type: ignore[attr-defined]
    gobject_mod.TYPE_INT = "int"  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    repo_mod.GObject = gobject_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod
    sys.modules["gi.repository.GObject"] = gobject_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin


def _make_store(rows: list[tuple[str, int, str]]):
    """Cria stub de ``Gtk.ListStore`` compatível com ``_select_profile_by_name``."""
    store = MagicMock()

    def get_iter_first():
        return 0 if rows else None

    def iter_next(it):
        nxt = it + 1
        return nxt if nxt < len(rows) else None

    def get_value(it, col):
        return rows[it][col]

    def get_path(it):
        return f"path:{it}"

    store.get_iter_first.side_effect = get_iter_first
    store.iter_next.side_effect = iter_next
    store.get_value.side_effect = get_value
    store.get_path.side_effect = get_path
    return store


def _make_tree():
    """Stub de ``Gtk.TreeView`` que registra qual iter foi selecionado."""
    selection = MagicMock()
    tree = MagicMock()
    tree.get_selection.return_value = selection
    return tree, selection


def _stub_with(rows, tree) -> Any:
    """Monta stub com ``_profiles_store``, ``_get`` e ``_select_profile_by_name`` bound."""
    store = _make_store(rows)
    stub = SimpleNamespace(_profiles_store=store)

    def _get(widget_id):
        if widget_id == "profiles_tree":
            return tree
        raise KeyError(f"widget desconhecido no stub: {widget_id}")

    stub._get = _get  # type: ignore[attr-defined]
    stub._select_profile_by_name = lambda name: (  # type: ignore[attr-defined]
        ProfilesActionsMixin._select_profile_by_name(stub, name)
    )
    stub._selecao_programatica = False  # type: ignore[attr-defined]
    stub._alvo_do_salvar = None  # type: ignore[attr-defined]
    stub._ha_trabalho_no_editor = lambda: (  # type: ignore[attr-defined]
        ProfilesActionsMixin._ha_trabalho_no_editor(stub)
    )
    stub._selecao_pode_se_mover_sozinha = lambda destino: (  # type: ignore[attr-defined]
        ProfilesActionsMixin._selecao_pode_se_mover_sozinha(stub, destino)
    )
    stub._mover_selecao_sem_gesto = lambda linha: (  # type: ignore[attr-defined]
        ProfilesActionsMixin._mover_selecao_sem_gesto(stub, linha)
    )
    stub._mark_active_profile_row = lambda active: setattr(  # type: ignore[attr-defined]
        stub, "_active_profile_hint", active
    )
    return stub


class TestSelectProfileByName:
    def test_encontra_e_seleciona_perfil_ativo(self):
        tree, selection = _make_tree()
        rows = [
            ("André", 10, "criteria"),
            ("fallback", -1000, "any"),
            ("meu_perfil", 50, "criteria"),
        ]
        stub = _stub_with(rows, tree)

        ok = ProfilesActionsMixin._select_profile_by_name(stub, "meu_perfil")

        assert ok is True
        selection.select_iter.assert_called_once_with(2)
        tree.scroll_to_cell.assert_called_once()

    def test_perfil_inexistente_retorna_false(self):
        tree, selection = _make_tree()
        rows = [("André", 10, "criteria"), ("fallback", -1000, "any")]
        stub = _stub_with(rows, tree)

        ok = ProfilesActionsMixin._select_profile_by_name(stub, "perfil_deletado")

        assert ok is False
        selection.select_iter.assert_not_called()

    def test_store_vazio_retorna_false(self):
        tree, selection = _make_tree()
        stub = _stub_with([], tree)

        ok = ProfilesActionsMixin._select_profile_by_name(stub, "qualquer")

        assert ok is False
        selection.select_iter.assert_not_called()


class TestOnDaemonStatusForSync:
    def test_cenario_1_perfil_explicito_ativo_seleciona(self):
        """Daemon respondeu com ``meu_perfil`` ativo → seleção muda."""
        tree, selection = _make_tree()
        rows = [("André", 10, "criteria"), ("meu_perfil", 50, "criteria")]
        stub = _stub_with(rows, tree)

        result = ProfilesActionsMixin._on_daemon_status_for_sync(
            stub, {"active_profile": "meu_perfil", "connected": True}
        )

        assert result is False
        selection.select_iter.assert_called_once_with(1)

    def test_cenario_2_daemon_offline_fallback_preservado(self):
        """``_on_daemon_status_sync_failed`` roda quando daemon offline; no-op."""
        tree, selection = _make_tree()
        rows = [("André", 10, "criteria"), ("meu_perfil", 50, "criteria")]
        stub = _stub_with(rows, tree)

        result = ProfilesActionsMixin._on_daemon_status_sync_failed(
            stub, ConnectionRefusedError("daemon offline")
        )

        assert result is False
        selection.select_iter.assert_not_called()

    def test_cenario_3_active_profile_none_noop(self):
        """Startup fresh sem perfil ativo → result traz ``None``; no-op."""
        tree, selection = _make_tree()
        rows = [("André", 10, "criteria"), ("meu_perfil", 50, "criteria")]
        stub = _stub_with(rows, tree)

        result = ProfilesActionsMixin._on_daemon_status_for_sync(
            stub, {"active_profile": None, "connected": True}
        )

        assert result is False
        selection.select_iter.assert_not_called()

    def test_active_profile_string_vazia_noop(self):
        tree, selection = _make_tree()
        rows = [("André", 10, "criteria")]
        stub = _stub_with(rows, tree)

        result = ProfilesActionsMixin._on_daemon_status_for_sync(
            stub, {"active_profile": "", "connected": True}
        )

        assert result is False
        selection.select_iter.assert_not_called()

    def test_resultado_nao_dict_noop(self):
        tree, selection = _make_tree()
        rows = [("André", 10, "criteria")]
        stub = _stub_with(rows, tree)

        result = ProfilesActionsMixin._on_daemon_status_for_sync(
            stub, "resposta_bizarra"
        )

        assert result is False
        selection.select_iter.assert_not_called()

    def test_active_profile_nao_existe_no_store_noop(self):
        """Daemon reporta ``perfil_x`` mas store só tem outros → no-op silencioso."""
        tree, selection = _make_tree()
        rows = [("André", 10, "criteria"), ("fallback", -1000, "any")]
        stub = _stub_with(rows, tree)

        result = ProfilesActionsMixin._on_daemon_status_for_sync(
            stub, {"active_profile": "perfil_deletado_recente"}
        )

        assert result is False
        selection.select_iter.assert_not_called()


class _FakeCombo:
    """Stub mínimo de GtkComboBoxText para testar helpers sem GTK."""

    def __init__(self, initial_id: str = "any") -> None:
        self._active_id = initial_id
        self.connected: list[tuple[str, Any]] = []

    def get_active_id(self) -> str:
        return self._active_id

    def set_active_id(self, new_id: str) -> bool:
        self._active_id = new_id
        return True

    def connect(self, signal: str, handler: Any) -> None:
        self.connected.append((signal, handler))


class _FakeBox:
    """Dublê da linha "Nome do jogo:" com a doutrina de visibilidade do GTK."""

    def __init__(self) -> None:
        self.visible = True
        self.no_show_all = True
        self.filhos_visiveis = False

    def show(self) -> None:
        self.visible = True

    def show_all(self) -> None:
        if self.no_show_all:
            return
        self.visible = True
        self.filhos_visiveis = True

    def set_no_show_all(self, valor: bool) -> None:
        self.no_show_all = bool(valor)

    def hide(self) -> None:
        self.visible = False


def _stub_with_combo(combo: _FakeCombo, box: _FakeBox | None = None) -> SimpleNamespace:
    """Stub com _get + ref do seletor "Aplica a:", para testes sem GTK."""
    stub = SimpleNamespace()
    widgets: dict[str, Any] = {}
    if box is not None:
        widgets["profile_game_entry_box"] = box

    def _get(widget_id: str) -> Any:
        return widgets.get(widget_id)

    stub._get = _get  # type: ignore[attr-defined]
    stub._aplica_a = combo  # type: ignore[attr-defined]
    from types import MethodType

    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        ProfilesActionsMixin,
    )

    stub._mostrar_caixa_do_steam_input = MethodType(  # type: ignore[attr-defined]
        ProfilesActionsMixin._mostrar_caixa_do_steam_input, stub
    )
    stub._atualizar_frase_do_jogo = MethodType(  # type: ignore[attr-defined]
        ProfilesActionsMixin._atualizar_frase_do_jogo, stub
    )
    return stub


class TestProfilesCacheNonBlocking:

    def test_find_cached_profile_cache_ausente_retorna_none(self):
        _install_gi_stubs()
        from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin

        stub = SimpleNamespace()
        assert ProfilesActionsMixin._find_cached_profile(stub, "x") is None


