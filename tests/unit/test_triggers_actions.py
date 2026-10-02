"""Testes unitários de TriggersActionsMixin (AUDIT-FINDING-COVERAGE-ACTIONS-ZERO-01).

Cobrem:
  - Seleção de preset via dropdown de modo (Off, Rigid, Pulse, MultiPos*).
  - Aplicar trigger persistindo no draft e chamando IPC.
  - Reset para Off.
  - Mudança de preset posicional (MultiPositionFeedback/Vibration).
  - Collect de valores de sliders para payload IPC.

Padrão `_FakeMixin` + stubs de `gi` (armadilha A-12).
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("triggers_actions: os gatilhos na janela")

import sys
import types
from typing import Any

import pytest


class _Orientation:
    HORIZONTAL = 0
    VERTICAL = 1


class _PositionType:
    LEFT = 0
    RIGHT = 1


class _Adjustment:
    def __init__(
        self,
        value: float = 0,
        lower: float = 0,
        upper: float = 100,
        step_increment: float = 1,
        page_increment: float = 10,
    ) -> None:
        self.value = value


class _StyleContext:
    """Guarda as classes CSS aplicadas, para os testes poderem afirmá-las."""

    def __init__(self) -> None:
        self.classes: set[str] = set()

    def add_class(self, nome: str) -> None:
        self.classes.add(nome)


class _Box:
    def __init__(self, *_a: Any, **_kw: Any) -> None:
        self._children: list[Any] = []
        self._style = _StyleContext()

    def pack_start(self, child: Any, *_a: Any, **_kw: Any) -> None:
        self._children.append(child)

    def get_children(self) -> list[Any]:
        return list(self._children)

    def remove(self, child: Any) -> None:
        self._children.remove(child)

    def show_all(self) -> None:
        pass

    def set_homogeneous(self, _v: bool) -> None:
        pass

    def get_style_context(self) -> _StyleContext:
        return self._style

    def set_visible(self, _v: bool) -> None:
        pass


class _Scale:
    def __init__(self, *_a: Any, **kw: Any) -> None:
        adjust = kw.get("adjustment")
        self._value: float = float(adjust.value) if adjust else 0.0

    def set_digits(self, _n: int) -> None:
        pass

    def set_value_pos(self, _p: int) -> None:
        pass

    def set_hexpand(self, _v: bool) -> None:
        pass

    def set_value(self, v: float) -> None:
        self._value = float(v)

    def get_value(self) -> float:
        return self._value

    def queue_draw(self) -> None:
        pass

    def connect(self, _signal: str, _cb: Any) -> None:
        pass


class _Label:
    def __init__(self, *_a: Any, **kw: Any) -> None:
        self._text = kw.get("label", "")
        self.line_wrap: bool | None = None
        self.ellipsize: Any = None
        self.tooltip: str | None = None

    def set_xalign(self, _x: float) -> None:
        pass

    def set_size_request(self, _w: int, _h: int) -> None:
        pass

    def set_line_wrap(self, wrap: bool) -> None:
        self.line_wrap = wrap

    def set_ellipsize(self, mode: Any) -> None:
        self.ellipsize = mode

    def set_tooltip_text(self, texto: str) -> None:
        self.tooltip = texto

    def set_text(self, t: str) -> None:
        self._text = t

    def set_markup(self, m: str) -> None:
        self._text = m


def _install_gi_stubs() -> None:
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import GLib, Gtk, Pango  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
            pass

    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")
    gi_mod.require_version = lambda _n, _v: None  # type: ignore[attr-defined]
    repo_mod = sys.modules.get("gi.repository") or types.ModuleType(
        "gi.repository"
    )
    gtk_mod = sys.modules.get("gi.repository.Gtk") or types.ModuleType(
        "gi.repository.Gtk"
    )
    glib_mod = sys.modules.get("gi.repository.GLib") or types.ModuleType(
        "gi.repository.GLib"
    )

    for cls_name in (
        "Builder", "Window", "Button", "ToggleButton", "ComboBoxText",
        "Switch", "TextView", "TextBuffer",
    ):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))
    gtk_mod.Orientation = _Orientation  # type: ignore[attr-defined]
    gtk_mod.PositionType = _PositionType  # type: ignore[attr-defined]
    gtk_mod.Adjustment = _Adjustment  # type: ignore[attr-defined]
    gtk_mod.Box = _Box  # type: ignore[attr-defined]
    gtk_mod.Scale = _Scale  # type: ignore[attr-defined]
    gtk_mod.Label = _Label  # type: ignore[attr-defined]

    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]
    glib_mod.source_remove = lambda *_a, **_kw: None  # type: ignore[attr-defined]

    pango_mod = sys.modules.get("gi.repository.Pango") or types.ModuleType(
        "gi.repository.Pango"
    )
    if not hasattr(pango_mod, "EllipsizeMode"):
        pango_mod.EllipsizeMode = type(  # type: ignore[attr-defined]
            "EllipsizeMode", (), {"NONE": 0, "START": 1, "MIDDLE": 2, "END": 3}
        )

    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    repo_mod.Pango = pango_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod
    sys.modules["gi.repository.Pango"] = pango_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import triggers_actions


class _FakeSegmentedSelector:
    """Stub do SegmentedSelector (FEAT-DSX-COMBO-TO-SEGMENTED-01)."""

    def __init__(self, wrap: bool = False) -> None:
        self.wrap = wrap
        self._items: list[tuple[str, str]] = []
        self._active_id: str | None = None
        self._visible = True
        self.handlers: list[tuple[str, Any]] = []
        self.dicas: dict[str, str] = {}

    def set_items(self, items: list[tuple[str, str]]) -> None:
        self._items = list(items)

    def set_tooltips(self, dicas: dict[str, str]) -> None:
        """Dica por BOTÃO — a T8 passa uma por modo (`{id: description}`)."""
        self.dicas = dict(dicas)

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        if the_id == self._active_id:
            return
        if all(iid != the_id for iid, _label in self._items):
            return
        self._active_id = the_id
        for sinal, cb in list(self.handlers):
            if sinal == "changed":
                cb(self)

    def connect(self, signal: str, cb: Any) -> None:
        self.handlers.append((signal, cb))

    def show_all(self) -> None:
        pass

    def get_visible(self) -> bool:
        return self._visible

    def set_visible(self, v: bool) -> None:
        self._visible = bool(v)


class _Relogio:
    """O ``GLib.timeout_add`` que GUARDA o callback em vez de engoli-lo."""

    def __init__(self) -> None:
        self.pendentes: dict[int, tuple[Any, tuple[Any, ...]]] = {}
        self._ultimo = 0

    def timeout_add(self, _ms: int, cb: Any, *args: Any) -> int:
        self._ultimo += 1
        self.pendentes[self._ultimo] = (cb, args)
        return self._ultimo

    def source_remove(self, ident: int) -> None:
        self.pendentes.pop(ident, None)

    def disparar_pendentes(self) -> int:
        """Faz o tempo passar. Devolve quantos callbacks dispararam."""
        pendentes = list(self.pendentes.items())
        self.pendentes.clear()
        for _ident, (cb, args) in pendentes:
            cb(*args)
        return len(pendentes)


class _FakeStatusBar:
    def __init__(self) -> None:
        self.pushed: list[tuple[int, str]] = []
        self._ctr = 0

    def get_context_id(self, _k: str) -> int:
        self._ctr += 1
        return self._ctr

    def push(self, ctx: int, msg: str) -> None:
        self.pushed.append((ctx, msg))


def _mk_widgets() -> dict[str, Any]:
    widgets: dict[str, Any] = {}
    for side in ("left", "right"):
        widgets[f"trigger_{side}_mode_slot"] = _Box()
        widgets[f"trigger_{side}_desc"] = _Label()
        widgets[f"trigger_{side}_params_box"] = _Box()
        widgets[f"trigger_{side}_preset_slot"] = _Box()
        widgets[f"trigger_{side}_preset_row"] = _Box()
    widgets["status_bar"] = _FakeStatusBar()
    return widgets


_CORPO_APLICADO: dict[str, Any] = {"status": "ok", "aplicado_em": ["02:fe:00:00:00:33"]}


def _espiar_ordem(
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    """Registra a ORDEM real entre `trigger.set` e `trigger.reset`.

    As duas listas do `_build_mixin` são separadas, então "quem saiu antes"
    não dá para ler nelas. Aqui embrulhamos os dois dublês já instalados —
    o que se mede é a sequência que o daemon veria no socket.
    """
    ordem: list[str] = []
    set_instalado = triggers_actions.trigger_set_detalhado
    reset_instalado = triggers_actions.trigger_reset_detalhado

    def espia_set(*a: Any, **kw: Any) -> Any:
        ordem.append("set")
        return set_instalado(*a, **kw)

    def espia_reset(*a: Any, **kw: Any) -> Any:
        ordem.append("reset")
        return reset_instalado(*a, **kw)

    monkeypatch.setattr(triggers_actions, "trigger_set_detalhado", espia_set)
    monkeypatch.setattr(triggers_actions, "trigger_reset_detalhado", espia_reset)
    return ordem


def _mensagem_real_do_daemon(mode: str, params: list[int]) -> str:
    """Mensagem que o daemon devolve ao recusar `params` (CODE_INVALID_PARAMS)."""
    from hefesto_dualsense4unix.core.trigger_effects import build_from_name

    with pytest.raises(ValueError) as exc:
        build_from_name(mode, params)
    return str(exc.value)


def test_humanizar_erro_de_ordem_usa_os_rotulos_dos_sliders() -> None:
    from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec

    motivo = _mensagem_real_do_daemon("Bow", [5, 3, 4, 4])
    texto = triggers_actions.humanizar_erro_gatilho(motivo, get_spec("Bow"))

    assert texto == "Fim (3) precisa ser maior que Início (5)"


def test_humanizar_erro_de_faixa_usa_os_rotulos_dos_sliders() -> None:
    from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec

    motivo = _mensagem_real_do_daemon("Rigid", [5, 300])
    texto = triggers_actions.humanizar_erro_gatilho(motivo, get_spec("Rigid"))

    assert texto == "Força precisa estar entre 0 e 255 (você pediu 300)"


def test_humanizar_mensagem_desconhecida_devolve_none() -> None:
    assert triggers_actions.humanizar_erro_gatilho("pane geral", None) is None


