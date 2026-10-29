"""SPRINT-HARMONIA-01 — o modo do sistema tem UM dono só."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("mode_transition: a troca de modo tem um dono")

import sys
import types
from typing import Any

import pytest


def _install_gi_stubs() -> None:
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover
            pass

    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")
    gi_mod.require_version = lambda _n, _v: None  # type: ignore[attr-defined]
    repo_mod = sys.modules.get("gi.repository") or types.ModuleType("gi.repository")
    gtk_mod = sys.modules.get("gi.repository.Gtk") or types.ModuleType(
        "gi.repository.Gtk"
    )
    glib_mod = sys.modules.get("gi.repository.GLib") or types.ModuleType(
        "gi.repository.GLib"
    )
    gobject_mod = sys.modules.get("gi.repository.GObject") or types.ModuleType(
        "gi.repository.GObject"
    )
    for cls_name in ("Builder", "Window", "Button", "Label", "Box"):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))
    if not hasattr(glib_mod, "idle_add"):
        glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    repo_mod.GObject = gobject_mod  # type: ignore[attr-defined]
    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod
    sys.modules["gi.repository.GObject"] = gobject_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import (
    home_actions,
    mode_transition,
)


Call = tuple[str, dict[str, Any], float]


@pytest.fixture()
def ipc(monkeypatch: pytest.MonkeyPatch) -> list[Call]:
    """Grava (método, params, timeout) de todo IPC despachado pela transição."""
    calls: list[Call] = []

    def _fake(
        method: str,
        params: dict[str, Any] | None,
        _ok: Any = None,
        _err: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        calls.append((method, dict(params or {}), timeout_s))

    monkeypatch.setattr(mode_transition, "call_async", _fake)
    monkeypatch.setattr(home_actions, "call_async", _fake)
    return calls


def _methods(calls: list[Call]) -> list[tuple[str, dict[str, Any]]]:
    return [(m, p) for m, p, _t in calls]


def test_plano_do_gamepad_sai_do_nativo_antes_de_ligar_o_vpad() -> None:
    """Ordem FIFO do worker: na ordem inversa o vpad nasce com o físico grabado."""
    assert mode_transition.plan_mode_transition("gamepad", "xbox") == [
        ("native.mode.set", {"enabled": False, "origin": "manual"}),
        ("gamepad.emulation.set", {"enabled": True, "flavor": "xbox", "origin": "manual"}),
    ]


def test_plano_do_desktop_desliga_nativo_e_gamepad_e_carrega_o_perfil() -> None:
    """HARM-06: "Controlar o PC" é um modo, não só o desligar dos outros dois.

    O terceiro passo vem por último: ligar o mouse antes de o gamepad sair faria
    a exclusão mútua do daemon derrubar o mouse recém-ligado.

    POINT-AND-CLICK-01 (17/09/2026): ele trocou de FONTE e não de posição. Era
    `mouse.emulation.restore`, que lê a flag de sessão da máquina; é
    `desktop.arranjo.apply`, que lê o PERFIL ATIVO — mouse, teclas, botões,
    `teclado_emulado` e a queda da supressão.
    """
    assert mode_transition.plan_mode_transition("desktop") == [
        ("native.mode.set", {"enabled": False, "origin": "manual"}),
        ("gamepad.emulation.set", {"enabled": False, "origin": "manual"}),
        ("desktop.arranjo.apply", {"origin": "manual"}),
    ]


def test_plano_do_nativo_so_liga_o_nativo() -> None:
    assert mode_transition.plan_mode_transition("native") == [
        ("native.mode.set", {"enabled": True, "origin": "manual"})
    ]


def test_plano_sem_flavor_nao_escolhe_mascara_nenhuma() -> None:
    """AUTO-01.3: sem escolha do usuário, quem decide a máscara é o DAEMON."""
    plan = mode_transition.plan_mode_transition("gamepad", None)
    assert plan[-1] == ("gamepad.emulation.set", {"enabled": True, "origin": "manual"})
    assert "flavor" not in plan[-1][1]


def test_plano_com_flavor_explicito_manda_o_campo() -> None:
    """A escolha do usuário no seletor de máscara continua chegando intacta."""
    plan = mode_transition.plan_mode_transition("gamepad", "dualsense")

    assert plan[-1] == (
        "gamepad.emulation.set",
        {"enabled": True, "flavor": "dualsense", "origin": "manual"},
    )


def test_modo_desconhecido_falha_alto() -> None:
    """Um modo novo passa por aqui em vez de virar um terceiro dono."""
    with pytest.raises(ValueError):
        mode_transition.plan_mode_transition("turbo")


def test_mode_of_state_nativo_vence_o_gamepad() -> None:
    """Com os dois ligados é o físico grabado que manda — as abas não discordam."""
    state = {"native_mode": True, "gamepad_emulation": {"enabled": True}}
    assert mode_transition.mode_of_state(state) == "native"


def test_mode_of_state_offline_e_none() -> None:
    assert mode_transition.mode_of_state(None) is None


def test_mode_of_state_desktop_sem_nada_ligado() -> None:
    assert mode_transition.mode_of_state({"gamepad_emulation": {}}) == "desktop"

