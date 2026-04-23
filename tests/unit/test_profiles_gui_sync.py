"""Sincronia da seleção da aba Perfis com perfil ativo (FEAT-GUI-LOAD-LAST-PROFILE-01).

Testa os 3 cenários do spec:

1. Daemon rodando com perfil explícito (``meu_perfil``) ativo → GUI seleciona ``meu_perfil``.
2. Daemon offline → callback de falha dispara; seleção fallback preservada.
3. Daemon rodando mas ``active_profile`` é ``None`` (startup sem switch explícito
   nem last_profile persistido) → no-op; fallback preservado.

Abordagem: evita subir GTK via stubs de ``gi.repository`` (padrão replicado de
``test_status_actions_reconnect.py``). Assim o teste roda no ``.venv`` mesmo sem
PyGObject instalado (armadilha A-12 do BRIEF).
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock


def _install_gi_stubs() -> None:
    """Instala stubs mínimos de ``gi.repository`` se o módulo real não estiver disponível.

    Réplica do helper de ``test_status_actions_reconnect.py`` para evitar requerer
    GTK/PyGObject em CI e no ``.venv`` sem ``--with-tray`` (A-12).
    """
    if "gi" in sys.modules and hasattr(sys.modules["gi"], "require_version"):
        try:
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

from hefesto.app.actions.profiles_actions import ProfilesActionsMixin  # noqa: E402

# ---------------------------------------------------------------------------
# Stubs de Gtk.ListStore / Gtk.TreeView para iteração de linhas.
# ---------------------------------------------------------------------------


def _make_store(rows: list[tuple[str, int, str]]):
    """Cria stub de ``Gtk.ListStore`` compatível com ``_select_profile_by_name``.

    Cada ``iter`` é o próprio índice (``int``); ``None`` sinaliza fim da lista.
    """
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
    """Monta stub com ``_profiles_store``, ``_get`` e ``_select_profile_by_name`` bound.

    ``_on_daemon_status_for_sync`` (método do mixin) chama ``self._select_profile_by_name``
    — precisamos bindar o método do mixin ao stub para a chamada resolver.
    """
    store = _make_store(rows)
    stub = SimpleNamespace(_profiles_store=store)

    def _get(widget_id):
        if widget_id == "profiles_tree":
            return tree
        raise KeyError(f"widget desconhecido no stub: {widget_id}")

    stub._get = _get  # type: ignore[attr-defined]
    # Binda o método do mixin ao stub preservando ``self`` como o próprio stub.
    stub._select_profile_by_name = lambda name: (  # type: ignore[attr-defined]
        ProfilesActionsMixin._select_profile_by_name(stub, name)
    )
    return stub


# ---------------------------------------------------------------------------
# _select_profile_by_name
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _on_daemon_status_for_sync / _on_daemon_status_sync_failed
# ---------------------------------------------------------------------------


class TestOnDaemonStatusForSync:
    def test_cenario_1_perfil_explicito_ativo_seleciona(self):
        """Daemon respondeu com ``meu_perfil`` ativo → seleção muda."""
        tree, selection = _make_tree()
        rows = [("André", 10, "criteria"), ("meu_perfil", 50, "criteria")]
        stub = _stub_with(rows, tree)

        result = ProfilesActionsMixin._on_daemon_status_for_sync(
            stub, {"active_profile": "meu_perfil", "connected": True}
        )

        assert result is False  # convenção GLib.idle_add
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


# ---------------------------------------------------------------------------
# _sync_selection_with_active_profile — dispara call_async com parâmetros certos
# ---------------------------------------------------------------------------


class TestSyncSelectionWithActiveProfile:
    def test_sync_chama_call_async_com_daemon_status(self, monkeypatch):
        import hefesto.app.actions.profiles_actions as mod

        captured: dict = {}

        def fake_call_async(method, params, on_success, on_failure=None, timeout_s=0.25):
            captured["method"] = method
            captured["params"] = params
            captured["on_success"] = on_success
            captured["on_failure"] = on_failure
            captured["timeout_s"] = timeout_s

        monkeypatch.setattr(mod, "call_async", fake_call_async)

        # Stub precisa expor os callbacks bound via referência direta aos métodos
        # do mixin (compat com ``self._on_daemon_status_for_sync``).
        stub = SimpleNamespace()
        stub._on_daemon_status_for_sync = lambda _r: False  # type: ignore[attr-defined]
        stub._on_daemon_status_sync_failed = lambda _e: False  # type: ignore[attr-defined]

        ProfilesActionsMixin._sync_selection_with_active_profile(stub)

        assert captured["method"] == "daemon.status"
        assert captured["params"] is None
        # Timeout generoso para GUI (spec permite até 500ms).
        assert captured["timeout_s"] == 0.5
        assert captured["on_success"] is not None
        assert captured["on_failure"] is not None
