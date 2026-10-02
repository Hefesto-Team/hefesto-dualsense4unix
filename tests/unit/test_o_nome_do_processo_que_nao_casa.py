"""PROCESSO-CEGO-01 — o campo `process_name` que a tela mandava preencher e o"""

from __future__ import annotations

import os
import sys
import types
from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("aviso do nome do processo no editor de perfis")


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

    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = lambda *_a, **_kw: None  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    glib_mod = types.ModuleType("gi.repository.GLib")
    gobject_mod = types.ModuleType("gi.repository.GObject")
    for nome in (
        "Builder", "Window", "Button", "CheckButton", "ComboBoxText", "Switch",
        "TreeView", "TreeViewColumn", "CellRendererText", "ListStore",
        "TreeSelection", "TreePath", "Box", "Label", "Frame", "Entry",
        "RadioButton", "Scale", "Stack", "MessageDialog", "MessageType",
        "ButtonsType", "ResponseType",
    ):
        setattr(gtk_mod, nome, object)
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

from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.integrations.window_backends import (
    wayland_portal,
    cosmic_toplevel,
    wlr_toplevel,
    xlib,
)
from hefesto_dualsense4unix.integrations.window_detect import (
    BACKENDS_CEGOS_AO_PROCESSO,
    BACKENDS_QUE_VEEM_O_PROCESSO,
    backend_ve_nome_do_processo,
)
from hefesto_dualsense4unix.profiles.schema import MatchCriteria


class TestATabelaBateComOsBackends:
    """A tabela não é crença: é conferida contra o que cada arquivo devolve."""

    def test_o_portal_devolve_exe_vazio_mesmo_tendo_o_pid(self) -> None:
        """O portal RECEBE o pid e ainda assim não resolve o executável."""
        info = wayland_portal._parse_portal_result(
            {"app-id": "steam_app_3357650", "title": "PRAGMATA", "pid": os.getpid()}
        )
        assert info is not None
        assert info.pid == os.getpid()
        assert info.exe_basename == ""
        assert info.as_dict()["exe_basename"] == ""
        nome = wayland_portal.WaylandPortalBackend.backend_name
        assert backend_ve_nome_do_processo(nome) is False

    def test_o_wlrctl_devolve_exe_vazio(self, monkeypatch: Any) -> None:
        """Mesmo com o `wlrctl` respondendo um toplevel inteiro, o campo é vazio."""

        class _Resposta:
            returncode = 0
            stdout = '[{"app_id": "steam_app_3357650", "title": "PRAGMATA"}]'
            stderr = ""

        monkeypatch.setattr(wlr_toplevel.shutil, "which", lambda _b: "/usr/bin/wlrctl")
        monkeypatch.setattr(
            wlr_toplevel.subprocess, "run", lambda *_a, **_kw: _Resposta()
        )
        info = wlr_toplevel.WlrctlBackend().get_active_window_info()
        assert info is not None
        assert info.wm_class == "steam_app_3357650"
        assert info.exe_basename == ""
        nome = wlr_toplevel.WlrctlBackend.backend_name
        assert backend_ve_nome_do_processo(nome) is False

    def test_o_cosmic_devolve_exe_vazio_e_pid_zero(self) -> None:
        """O `zcosmic_toplevel_info_v1` não manda PID — nem na versão 3."""
        janela = cosmic_toplevel._Janela()
        janela.app_id = "com.system76.CosmicTerm"
        janela.titulo = "Terminal"
        janela.ativada = True
        backend = cosmic_toplevel.CosmicToplevelBackend()
        backend._janelas = {1: janela}
        backend._soquete = object()  # type: ignore[assignment]
        backend._esvaziar = lambda: True  # type: ignore[method-assign]
        info = backend.get_active_window_info()
        assert info is not None
        assert info.wm_class == "com.system76.CosmicTerm"
        assert info.pid == 0
        assert info.exe_basename == ""
        nome = cosmic_toplevel.CosmicToplevelBackend.backend_name
        assert backend_ve_nome_do_processo(nome) is False

    def test_o_xlib_resolve_o_executavel_de_verdade(self) -> None:
        """O X11 é o único que lê `/proc/<pid>/exe` — provado com o pid deste teste."""
        assert xlib._exe_basename_from_pid(os.getpid()) != ""
        assert backend_ve_nome_do_processo(xlib.XlibBackend.backend_name) is True

    def test_as_duas_tabelas_nao_se_cruzam(self) -> None:
        """Um backend não pode estar nas duas listas — o predicado responderia pela ordem."""
        assert not (BACKENDS_QUE_VEEM_O_PROCESSO & BACKENDS_CEGOS_AO_PROCESSO)

    def test_backend_desconhecido_ou_ausente_nao_afirma_nada(self) -> None:
        """"Não sei" e "não casa" mandam caçar em lugares opostos."""
        assert backend_ve_nome_do_processo(None) is None
        assert backend_ve_nome_do_processo("") is None
        assert backend_ve_nome_do_processo("backend_de_terceiro") is None


class TestOCampoDerrubaOPerfilInteiro:
    def test_com_a_window_class_certa_o_perfil_ainda_nao_entra(self) -> None:
        """A afirmação forte do aviso, medida: *"nem com o window_class certo"*."""
        janela_wayland = {
            "wm_class": "steam_app_3357650",
            "wm_name": "PRAGMATA",
            "exe_basename": "",
        }
        so_a_classe = MatchCriteria(window_class=["steam_app_3357650"])
        com_o_processo = MatchCriteria(
            window_class=["steam_app_3357650"], process_name=["PRAGMATA.exe"]
        )

        assert so_a_classe.matches(janela_wayland) is True
        assert com_o_processo.matches(janela_wayland) is False


class _FakeLabel:
    def __init__(self) -> None:
        self.markup: str | None = None
        self.visivel = False

    def set_markup(self, markup: str) -> None:
        self.markup = markup

    def set_visible(self, visivel: bool) -> None:
        self.visivel = bool(visivel)


class _FakeSwitch:
    def __init__(self) -> None:
        self.active = False

    def set_active(self, active: bool) -> None:
        self.active = active


class _FakeStack:
    def __init__(self) -> None:
        self.visible_child = ""

    def set_visible_child_name(self, name: str) -> None:
        self.visible_child = name


class _FakeEntry:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text


class _Editor(pa.ProfilesActionsMixin):
    """Editor fake: métodos REAIS do mixin sobre widgets fake."""

    def __init__(self) -> None:
        self.aviso = _FakeLabel()
        self._widgets: dict[str, Any] = {
            "profile_process_name_aviso": self.aviso,
            "profile_editor_stack": _FakeStack(),
            "profile_advanced_switch": _FakeSwitch(),
            "profile_name_entry": _FakeEntry(""),
            "profile_window_class_entry": _FakeEntry(""),
            "profile_title_regex_entry": _FakeEntry(""),
            "profile_process_name_entry": _FakeEntry(""),
        }
        self._mode_advanced = False
        self._suppress_advanced_toggle = False
        self._profiles_cache: list[Any] = []

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _mostrar_a_regra_nos_campos_crus(self) -> None:
        return None


def _responder_state(monkeypatch: Any, state: dict[str, Any]) -> None:
    """Faz o `call_async` responder NA HORA, com o estado dado."""

    def _falso_call_async(**kwargs: Any) -> None:
        kwargs["on_success"](state)

    monkeypatch.setattr(pa, "call_async", _falso_call_async)
    monkeypatch.setattr(pa, "set_pref", lambda *_a, **_kw: None)


class TestOWlrctlNaoPrecisaDeCompositorNoTeste:
    """Cinto do próprio instrumento: o dublê do `wlrctl` não pode virar produto."""

    def test_sem_o_binario_o_backend_nem_tenta(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(wlr_toplevel.shutil, "which", lambda _b: None)

        def _explode(*_a: Any, **_kw: Any) -> Any:  # pragma: no cover
            raise AssertionError("não deveria chamar o wlrctl sem o binário")

        monkeypatch.setattr(wlr_toplevel.subprocess, "run", _explode)
        assert wlr_toplevel.WlrctlBackend().get_active_window_info() is None
