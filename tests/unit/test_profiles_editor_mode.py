"""Editor de perfis — seção "Modo" (FEAT-PROFILE-MODE-GUI-01).

Cobre o contrato editor→Profile da seção ``mode``:

1. Cada kind do seletor ("desktop"/"gamepad"/"native") vira a seção certa no
   Profile salvo; "none" (sem opinião) salva SEM a seção (mode=None).
2. "none" também REMOVE a seção de um perfil existente que a tinha.
3. Round-trip: perfil com mode carregado no editor → salvo sem perder nada.
4. Máscara/co-op só valem com kind == "gamepad" (nos demais: None/False).
5. Sem a seção montada (glade antigo), o mode do perfil-base sobrevive por
   herança — comportamento anterior preservado.
6. Visibilidade das opções de gamepad segue o kind; populate programático não
   dispara preview (guard anti-loop).

Hermético: stubs de ``gi.repository`` quando o PyGObject real não está
disponível (padrão replicado de ``test_profiles_gui_sync.py``) e widgets fake
com a mesma API por-ID do SegmentedSelector — nenhum GTK real é construído.
"""
from __future__ import annotations

import sys
import types
from typing import Any


def _install_gi_stubs() -> None:
    """Instala stubs mínimos de ``gi.repository`` se o módulo real faltar.

    Réplica do helper de ``test_profiles_gui_sync.py`` (armadilha A-12: o
    ``.venv`` de CI pode não ter PyGObject).
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

    gtk_mod.Builder = object  # type: ignore[attr-defined]
    gtk_mod.Window = object  # type: ignore[attr-defined]
    gtk_mod.Button = object  # type: ignore[attr-defined]
    gtk_mod.CheckButton = object  # type: ignore[attr-defined]
    gtk_mod.ComboBoxText = object  # type: ignore[attr-defined]
    gtk_mod.Switch = object  # type: ignore[attr-defined]
    gtk_mod.TreeView = object  # type: ignore[attr-defined]
    gtk_mod.TreeViewColumn = object  # type: ignore[attr-defined]
    gtk_mod.CellRendererText = object  # type: ignore[attr-defined]
    gtk_mod.ListStore = object  # type: ignore[attr-defined]
    gtk_mod.TreeSelection = object  # type: ignore[attr-defined]
    gtk_mod.TreePath = object  # type: ignore[attr-defined]
    gtk_mod.Box = object  # type: ignore[attr-defined]
    gtk_mod.Label = object  # type: ignore[attr-defined]
    gtk_mod.Frame = object  # type: ignore[attr-defined]
    gtk_mod.Entry = object  # type: ignore[attr-defined]
    gtk_mod.RadioButton = object  # type: ignore[attr-defined]
    gtk_mod.Scale = object  # type: ignore[attr-defined]
    gtk_mod.Stack = object  # type: ignore[attr-defined]
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

from hefesto_dualsense4unix.app.actions.profiles_actions import (  # noqa: E402
    ProfilesActionsMixin,
)
from hefesto_dualsense4unix.profiles.schema import Profile  # noqa: E402

# ---------------------------------------------------------------------------
# Widgets fake (mesma API por-ID do SegmentedSelector; sem GTK real)
# ---------------------------------------------------------------------------


class _FakeEntry:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text


class _FakeScale:
    def __init__(self, value: float = 0.0) -> None:
        self._value = value

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        self._value = value


class _FakeStack:
    def __init__(self) -> None:
        self.visible_child = ""

    def set_visible_child_name(self, name: str) -> None:
        self.visible_child = name


class _FakeSwitch:
    def __init__(self) -> None:
        self.active = False

    def set_active(self, active: bool) -> None:
        self.active = active


class _FakeSelector:
    """Stub do SegmentedSelector: API por-ID + "changed" emitido no set_active_id.

    Espelha a semântica do widget real: só emite quando o id efetivamente muda
    e o handler recebe apenas o seletor (sinal SEM argumentos —
    BUG-HOME-SEGMENTED-SIGNATURE-01).
    """

    def __init__(self, active: str | None = None) -> None:
        self._active_id = active
        self._handlers: list[Any] = []

    def connect(self, signal: str, handler: Any) -> None:
        if signal == "changed":
            self._handlers.append(handler)

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        if the_id == self._active_id:
            return
        self._active_id = the_id
        for handler in list(self._handlers):
            handler(self)


class _FakeCheck:
    def __init__(self, active: bool = False) -> None:
        self._active = active

    def get_active(self) -> bool:
        return self._active

    def set_active(self, active: bool) -> None:
        self._active = active


class _FakeBox:
    """Linha de opções do gamepad: registra visibilidade/sensibilidade."""

    def __init__(self) -> None:
        self.visible = True
        self.no_show_all = False
        self.sensitive = True

    def set_visible(self, visible: bool) -> None:
        self.visible = visible

    def set_no_show_all(self, flag: bool) -> None:
        self.no_show_all = flag

    def set_sensitive(self, sensitive: bool) -> None:
        self.sensitive = sensitive


# ---------------------------------------------------------------------------
# Stub do editor: mixin real + widgets fake resolvidos por _get
# ---------------------------------------------------------------------------


class _EditorStub(ProfilesActionsMixin):
    """Editor fake: métodos REAIS do mixin sobre widgets fake (sem GTK)."""

    def __init__(self, name: str = "perfil_teste", priority: int = 10) -> None:
        self._widgets: dict[str, Any] = {
            "profile_name_entry": _FakeEntry(name),
            "profile_priority_scale": _FakeScale(priority),
            "profile_simple_custom_name": _FakeEntry(""),
            "profile_editor_stack": _FakeStack(),
            "profile_advanced_switch": _FakeSwitch(),
        }
        self._profiles_cache = []
        self._duplicate_source = None
        self._mode_advanced = False
        self._aplica_a = _FakeSelector("any")
        self.preview_calls = 0

    def _get(self, widget_id: str) -> Any:  # sem Gtk.Builder nos testes
        return self._widgets.get(widget_id)

    def _refresh_preview(self) -> None:  # conta chamadas (testa o guard)
        self.preview_calls += 1

    def com_secao_mode(self) -> _EditorStub:
        """Equivale ao _install_mode_section: widgets fake + handlers ligados."""
        self._mode_kind_selector = _FakeSelector("none")
        self._mode_flavor_selector = _FakeSelector("dualsense")
        self._mode_coop_check = _FakeCheck(False)
        self._mode_gamepad_opts = _FakeBox()
        self._mode_kind_selector.connect("changed", self._on_mode_kind_changed)
        self._mode_flavor_selector.connect("changed", self._on_mode_flavor_changed)
        self._sync_mode_options_visibility("none")
        return self


def _profile_com_mode(name: str, mode: dict[str, Any] | None) -> Profile:
    data: dict[str, Any] = {
        "name": name,
        "version": 1,
        "match": {"type": "any"},
        "priority": 10,
    }
    if mode is not None:
        data["mode"] = mode
    return Profile.model_validate(data)


# ---------------------------------------------------------------------------
# editor → Profile: cada kind do seletor
# ---------------------------------------------------------------------------


class TestBuildProfileMode:
    def test_kind_none_salva_sem_secao(self) -> None:
        """"Sem opinião" → perfil salvo NÃO tem a seção mode."""
        stub = _EditorStub().com_secao_mode()

        profile = stub._build_profile_from_editor()

        assert profile.mode is None

    def test_kind_desktop(self) -> None:
        stub = _EditorStub().com_secao_mode()
        stub._mode_kind_selector.set_active_id("desktop")

        profile = stub._build_profile_from_editor()

        assert profile.mode is not None
        assert profile.mode.kind == "desktop"
        assert profile.mode.gamepad_flavor is None
        assert profile.mode.coop is False

    def test_kind_native(self) -> None:
        stub = _EditorStub().com_secao_mode()
        stub._mode_kind_selector.set_active_id("native")

        profile = stub._build_profile_from_editor()

        assert profile.mode is not None
        assert profile.mode.kind == "native"
        assert profile.mode.gamepad_flavor is None
        assert profile.mode.coop is False

    def test_kind_gamepad_com_flavor_e_coop(self) -> None:
        stub = _EditorStub().com_secao_mode()
        stub._mode_kind_selector.set_active_id("gamepad")
        stub._mode_flavor_selector.set_active_id("xbox")
        stub._mode_coop_check.set_active(True)

        profile = stub._build_profile_from_editor()

        assert profile.mode is not None
        assert profile.mode.kind == "gamepad"
        assert profile.mode.gamepad_flavor == "xbox"
        assert profile.mode.coop is True

    def test_flavor_e_coop_so_valem_com_gamepad(self) -> None:
        """Máscara/co-op marcados mas kind != gamepad → gravados limpos."""
        stub = _EditorStub().com_secao_mode()
        stub._mode_flavor_selector.set_active_id("xbox")
        stub._mode_coop_check.set_active(True)
        stub._mode_kind_selector.set_active_id("native")

        profile = stub._build_profile_from_editor()

        assert profile.mode is not None
        assert profile.mode.gamepad_flavor is None
        assert profile.mode.coop is False

    def test_none_remove_secao_de_perfil_existente(self) -> None:
        """Perfil que TINHA mode + editor em "none" → seção removida ao salvar."""
        existente = _profile_com_mode(
            "meu_jogo", {"kind": "gamepad", "gamepad_flavor": "xbox", "coop": True}
        )
        stub = _EditorStub(name="meu_jogo").com_secao_mode()
        stub._profiles_cache = [existente]

        profile = stub._build_profile_from_editor()

        assert profile.name == "meu_jogo"
        assert profile.mode is None

    def test_sem_secao_montada_preserva_heranca(self) -> None:
        """Glade antigo (slot ausente) → mode do perfil-base sobrevive intacto."""
        existente = _profile_com_mode("nativo_sony", {"kind": "native"})
        stub = _EditorStub(name="nativo_sony")  # SEM com_secao_mode()
        stub._profiles_cache = [existente]

        profile = stub._build_profile_from_editor()

        assert profile.mode is not None
        assert profile.mode.kind == "native"


# ---------------------------------------------------------------------------
# Round-trip: carregar no editor → salvar sem perder a seção
# ---------------------------------------------------------------------------


class TestRoundTripMode:
    def test_round_trip_gamepad_coop(self) -> None:
        original = _profile_com_mode(
            "coop_local",
            {"kind": "gamepad", "gamepad_flavor": "dualsense", "coop": True},
        )
        stub = _EditorStub(name="coop_local").com_secao_mode()
        stub._profiles_cache = [original]

        stub._populate_editor(original)
        assert stub._mode_kind_selector.get_active_id() == "gamepad"
        assert stub._mode_flavor_selector.get_active_id() == "dualsense"
        assert stub._mode_coop_check.get_active() is True

        rebuilt = stub._build_profile_from_editor()
        assert rebuilt.mode == original.mode

    def test_round_trip_native(self) -> None:
        original = _profile_com_mode("sackboy", {"kind": "native"})
        stub = _EditorStub(name="sackboy").com_secao_mode()
        stub._profiles_cache = [original]

        stub._populate_editor(original)
        assert stub._mode_kind_selector.get_active_id() == "native"

        rebuilt = stub._build_profile_from_editor()
        assert rebuilt.mode == original.mode

    def test_round_trip_sem_mode(self) -> None:
        """Perfil sem opinião entra e sai sem ganhar a seção por acidente."""
        original = _profile_com_mode("navegador", None)
        stub = _EditorStub(name="navegador").com_secao_mode()
        # Editor sujo de um perfil anterior COM mode: o populate deve limpar.
        stub._mode_kind_selector.set_active_id("gamepad")
        stub._mode_coop_check.set_active(True)
        stub._profiles_cache = [original]

        stub._populate_editor(original)
        assert stub._mode_kind_selector.get_active_id() == "none"

        rebuilt = stub._build_profile_from_editor()
        assert rebuilt.mode is None


# ---------------------------------------------------------------------------
# Visibilidade das opções de gamepad + guard anti-loop do populate
# ---------------------------------------------------------------------------


class TestModeOptionsVisibility:
    def test_gamepad_mostra_e_habilita_opcoes(self) -> None:
        stub = _EditorStub().com_secao_mode()

        stub._mode_kind_selector.set_active_id("gamepad")  # clique da usuária

        opts = stub._mode_gamepad_opts
        assert opts.visible is True
        assert opts.sensitive is True
        assert opts.no_show_all is False

    def test_none_esconde_e_desabilita_opcoes(self) -> None:
        stub = _EditorStub().com_secao_mode()
        stub._mode_kind_selector.set_active_id("gamepad")

        stub._mode_kind_selector.set_active_id("none")

        opts = stub._mode_gamepad_opts
        assert opts.visible is False
        assert opts.sensitive is False
        assert opts.no_show_all is True

    def test_clique_da_usuaria_atualiza_preview(self) -> None:
        stub = _EditorStub().com_secao_mode()

        stub._mode_kind_selector.set_active_id("desktop")

        assert stub.preview_calls == 1

    def test_populate_programatico_nao_dispara_preview(self) -> None:
        """Guard anti-loop: _set_mode_editor preenche sem refresh em cascata."""
        original = _profile_com_mode(
            "meu_jogo", {"kind": "gamepad", "gamepad_flavor": "xbox", "coop": True}
        )
        stub = _EditorStub().com_secao_mode()

        stub._set_mode_editor(original.mode)

        assert stub.preview_calls == 0
        # Mas a visibilidade das opções foi sincronizada mesmo sob guard.
        assert stub._mode_gamepad_opts.visible is True
