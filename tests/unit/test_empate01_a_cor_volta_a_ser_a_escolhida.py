"""A cor volta a ser dela — a aba Perfis para de rebaixar o que ela consertou.

Três entregas da fila crítica dos perfis, todas com evidência datada:

**SALVAR-NAO-REBAIXA-01.** `_build_profile_from_editor` terminava com um
`base.update({name, priority, match})` que sobrescrevia SEMPRE, com o que
estivesse nos widgets. Medido no disco do usuário: `Pragmata` era regra de jogo com
prioridade 100 em 26/07 às 23h40 e amanheceu catch-all em 27/07 às 23h04;
`vitoria.json` caiu de prioridade 100 para 0. Salvar a cor pela aba Perfis
gravava de volta a leitura empobrecida da tela.

**PERFIL-NASCE-CERTO-01.** O perfil novo nascia `match:any` e prioridade 0 —
que é a combinação que garante que ele NUNCA vale num jogo (a R-21 nega
autoridade a catch-all em janela de jogo) e perde para o catch-all dela em
todo o resto. E o teto da escala era 100, com o catch-all dela exatamente em
100: não existia número escolhível pela janela que desempatasse.

**EMPATE-01/E-1.** O `fallback` semeado pelo repositório trazia
`lightbar: [40, 40, 40]` — a olho nu, um controle apagado — e ganhava, pelo
alfabeto, de quem tinha opinião melhor.

Hermético: stubs de `gi.repository` quando falta PyGObject, widgets falsos com
a mesma API por-ID que a aba usa. Nenhum GTK real, nenhum daemon, nenhuma
escrita no ~/.config dela.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("empate01 a cor volta a ser dela")

import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest


pytest.importorskip("gi")


def _install_gi_stubs() -> None:
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover - ambientes sem GTK
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
from hefesto_dualsense4unix.profiles.schema import (
    MatchCriteria,
    Profile,
)

APPID = "3357650"
WM_JOGO = f"steam_app_{APPID}"

RAIZ = Path(__file__).resolve().parents[2]
FALLBACK_JSON = RAIZ / "assets" / "estilos_de_jogo" / "fallback.json"


class _FakeEntry:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text

    def set_placeholder_text(self, text: str) -> None:
        return None

    def set_tooltip_text(self, text: str) -> None:
        return None


class _FakeScale:
    """Escala com TETO, como o `profile_priority_adj` do glade."""

    def __init__(self, value: float = 0.0, teto: float | None = None) -> None:
        self._teto = float(pa.PRIORIDADE_MAXIMA if teto is None else teto)
        self._value = 0.0
        self._handlers: list[Any] = []
        self.set_value(value)

    def connect(self, sinal: str, handler: Any) -> None:
        if sinal == "value-changed":
            self._handlers.append(handler)

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        """Emite `value-changed` como o GtkScale de verdade — inclusive quando o"""
        self._value = max(0.0, min(self._teto, float(value)))
        for handler in self._handlers:
            handler(self)


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


class _FakeBox:
    """Dublê da linha "Nome do jogo:" com a doutrina de visibilidade do GTK."""

    def __init__(self) -> None:
        self.visivel = False
        self.no_show_all = True
        self.filhos_visiveis = False

    def show(self) -> None:
        self.visivel = True

    def show_all(self) -> None:
        if self.no_show_all:
            return
        self.visivel = True
        self.filhos_visiveis = True

    def set_no_show_all(self, valor: bool) -> None:
        self.no_show_all = bool(valor)

    def hide(self) -> None:
        self.visivel = False


class _FakeSelector:
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


class _Editor(pa.ProfilesActionsMixin):

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _selected_profile_name(self, selection: Any = None) -> str | None:
        return None

    def _refresh_preview(self) -> None:
        return None

    def _prefill_steam_appid(self) -> None:
        return None

    def _reload_profiles_store(self, **_kw: Any) -> None:
        return None

    def _notify_launch_env_refresh(self) -> None:
        return None

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)


def _perfil_do_pragmata() -> Profile:
    """O perfil como ele ficou depois do conserto à mão de 26/07."""
    return Profile(
        name="Pragmata",
        match=MatchCriteria(window_class=[WM_JOGO], window_title_regex="Pragmata"),
        priority=110,
    )


class TestTetoDaEscalaSobeParaDuzentos:
    def test_a_constante_do_codigo(self) -> None:
        assert pa.PRIORIDADE_MAXIMA == 200


class TestSementeSemOpiniaoSobreCor:
    """EMPATE-01/E-1: o `fallback` do repositório para de apagar o controle."""

    def test_o_fallback_semeado_nao_manda_na_cor(self) -> None:
        """Com a cura arrancada, o campo volta e o teste reprova."""
        bruto = json.loads(FALLBACK_JSON.read_text(encoding="utf-8"))
        leds = bruto.get("leds") or {}

        assert "lightbar" not in leds, (
            "o fallback voltou a ter opinião sobre a cor — e ele vence, pelo "
            "alfabeto, o perfil que tem opinião melhor"
        )

    def test_o_desenho_do_numero_do_jogador_fica(self) -> None:
        """Só uma das duas metades estava errada: acender a luz central é o"""
        bruto = json.loads(FALLBACK_JSON.read_text(encoding="utf-8"))
        leds = bruto.get("leds") or {}

        assert leds.get("player_leds") == [False, False, True, False, False]
