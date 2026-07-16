"""SPRINT-HARMONIA-01 — o modo do sistema tem UM dono só.

HARM-01: a aba Emulação chamava ``gamepad.emulation.set`` cru, sem sair do Modo
Nativo antes. Nativo + gamepad ligados juntos = controle físico grabado pelo
jogo + vpad congelado, ou seja JOGO SEM CONTROLE NENHUM — e a Início ainda
exibia "Jogar direto (Sony)" (o nativo vence no `_render_home`), escondendo o
estado real. Estes testes travam a paridade: as duas abas emitem exatamente a
mesma sequência de IPC, com a mesma folga de timeout.

HARM-03: "Modo jogo" (suspender mouse/teclado) não pode ser oferecido em
"Controlar o PC" — nesse modo o controle SÓ faz mouse/teclado, então
suspendê-los deixa o controle sem função nenhuma.

Herméticos: stubs de gi (armadilha A-12), sem GTK real e sem daemon.

O stub daqui é um SUPERSET do de test_emulation_actions_modo_jogo.py: expõe
também `GObject`. O stub original só publica Gtk/GLib, então quando ele roda
antes de um módulo que faz ``from gi.repository import GObject``
(profiles_actions) a coleção do outro teste morre com ImportError. Stub de
menos quebra uns; gi real quebra outros (test_triggers_actions.py depende do
gi stubado) — o superset é o que convive com os dois.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest


def _install_gi_stubs() -> None:
    # GATE-SKIP-MASK-01: com o PyGObject real disponível, NÃO instala stubs —
    # o merge abaixo mutaria o gi REAL (sobrescreve GLib.idle_add e
    # require_version) e fazia testes de GUI pularem como "ambiente sem GTK".
    # Um stub instalado por outro módulo de teste (__spec__ None) segue
    # sendo reaproveitado para merge de atributos.
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
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

from hefesto_dualsense4unix.app.actions import (  # noqa: E402
    emulation_actions,
    home_actions,
    mode_transition,
)

# --- captura de IPC ---------------------------------------------------------

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


# --- plano puro da transição ------------------------------------------------


def test_plano_do_gamepad_sai_do_nativo_antes_de_ligar_o_vpad() -> None:
    """Ordem FIFO do worker: na ordem inversa o vpad nasce com o físico grabado."""
    assert mode_transition.plan_mode_transition("gamepad", "xbox") == [
        ("native.mode.set", {"enabled": False}),
        ("gamepad.emulation.set", {"enabled": True, "flavor": "xbox"}),
    ]


def test_plano_do_desktop_desliga_nativo_e_gamepad_e_liga_o_mouse() -> None:
    """HARM-06: "Controlar o PC" é um modo, não só o desligar dos outros dois.

    O restore vem por último: ligar o mouse antes de o gamepad sair faria a
    exclusão mútua do daemon derrubar o mouse recém-ligado.
    """
    assert mode_transition.plan_mode_transition("desktop") == [
        ("native.mode.set", {"enabled": False}),
        ("gamepad.emulation.set", {"enabled": False}),
        ("mouse.emulation.restore", {}),
    ]


def test_plano_do_nativo_so_liga_o_nativo() -> None:
    assert mode_transition.plan_mode_transition("native") == [
        ("native.mode.set", {"enabled": True})
    ]


def test_plano_sem_flavor_usa_o_default_unico() -> None:
    """HARM-08: um único default de máscara — Xbox (vibra, não duplica)."""
    plan = mode_transition.plan_mode_transition("gamepad", None)
    assert plan[-1] == ("gamepad.emulation.set", {"enabled": True, "flavor": "xbox"})


def test_modo_desconhecido_falha_alto() -> None:
    """Um modo novo passa por aqui em vez de virar um terceiro dono."""
    with pytest.raises(ValueError):
        mode_transition.plan_mode_transition("turbo")


def test_apply_mode_da_folga_de_timeout_em_todos_os_passos(ipc: list[Call]) -> None:
    """Trocar de modo cria uinput + grab: não cabe nos 0.25s default."""
    mode_transition.apply_mode(
        "gamepad", flavor="xbox", on_done=lambda _r: False, on_fail=lambda _e: False
    )
    assert [t for _m, _p, t in ipc] == [2.0, 2.0]


# --- leitura do modo (uma regra só) -----------------------------------------


def test_mode_of_state_nativo_vence_o_gamepad() -> None:
    """Com os dois ligados é o físico grabado que manda — as abas não discordam."""
    state = {"native_mode": True, "gamepad_emulation": {"enabled": True}}
    assert mode_transition.mode_of_state(state) == "native"


def test_mode_of_state_offline_e_none() -> None:
    assert mode_transition.mode_of_state(None) is None


def test_mode_of_state_desktop_sem_nada_ligado() -> None:
    assert mode_transition.mode_of_state({"gamepad_emulation": {}}) == "desktop"


# --- HARM-01: a Emulação usa o MESMO caminho da Início ----------------------


class _EmulStub(emulation_actions.EmulationActionsMixin):
    """Instância mínima: `_get` devolve None (sem widgets) e refresh é contado."""

    def __init__(self) -> None:
        self.toasts: list[str] = []
        self.refreshed = 0

    def _get(self, _widget_id: str) -> Any:
        return None

    def _toast_emulation(self, msg: str) -> None:
        self.toasts.append(msg)

    def _refresh_gamepad_and_gamemode(self) -> None:
        self.refreshed += 1


def test_emulacao_xbox_sai_do_nativo_antes_de_ligar_o_vpad(ipc: list[Call]) -> None:
    """Regressão do JOGO SEM CONTROLE NENHUM: era um `gamepad.emulation.set` cru."""
    _EmulStub().on_emulation_gamepad_xbox(None)

    assert _methods(ipc) == [
        ("native.mode.set", {"enabled": False}),
        ("gamepad.emulation.set", {"enabled": True, "flavor": "xbox"}),
    ]


def test_emulacao_dualsense_sai_do_nativo_antes_de_ligar_o_vpad(
    ipc: list[Call],
) -> None:
    _EmulStub().on_emulation_gamepad_dualsense(None)

    assert _methods(ipc) == [
        ("native.mode.set", {"enabled": False}),
        ("gamepad.emulation.set", {"enabled": True, "flavor": "dualsense"}),
    ]


def test_emulacao_desligado_tambem_sai_do_nativo(ipc: list[Call]) -> None:
    """"Desligado" = "Controlar o PC": deixar o nativo de pé exibia o botão
    "Desligado" realçado com o jogo ainda dono do controle."""
    _EmulStub().on_emulation_gamepad_off(None)

    assert _methods(ipc) == [
        ("native.mode.set", {"enabled": False}),
        ("gamepad.emulation.set", {"enabled": False}),
        ("mouse.emulation.restore", {}),
    ]


def test_nenhum_caminho_da_emulacao_liga_o_vpad_sem_transicao(ipc: list[Call]) -> None:
    """Aceite do HARM-01: todo `gamepad.emulation.set` vem depois de um
    `native.mode.set`, com a folga de 2s — em QUALQUER botão da aba."""
    stub = _EmulStub()
    for handler in (
        stub.on_emulation_gamepad_off,
        stub.on_emulation_gamepad_dualsense,
        stub.on_emulation_gamepad_xbox,
    ):
        ipc.clear()
        handler(None)
        metodos = [m for m, _p, _t in ipc]
        # A ordem é o que importa: sair do nativo ANTES de tocar no vpad.
        assert metodos.index("native.mode.set") < metodos.index(
            "gamepad.emulation.set"
        )
        assert all(t == 2.0 for _m, _p, t in ipc)


class _FakeSelector:
    def __init__(self, active_id: str | None = None) -> None:
        self._active_id = active_id

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        self._active_id = the_id


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def set_text(self, text: str) -> None:
        self.text = text


class _HomeStub:
    _on_home_mode_changed = home_actions.HomeActionsMixin._on_home_mode_changed

    def __init__(self, flavor: str) -> None:
        self._home_guard = False
        self._home_mode_desc = _FakeLabel()
        self._home_mode_selector = _FakeSelector()
        self._home_flavor_selector = _FakeSelector(flavor)

    def _status_toast(self, _origin: str, _msg: str) -> None:
        pass

    def _refresh_home_tab(self) -> None:
        pass


@pytest.mark.parametrize(
    ("mode_id", "flavor", "emul_handler"),
    [
        ("gamepad", "xbox", "on_emulation_gamepad_xbox"),
        ("gamepad", "dualsense", "on_emulation_gamepad_dualsense"),
        ("desktop", "xbox", "on_emulation_gamepad_off"),
    ],
)
def test_inicio_e_emulacao_emitem_a_mesma_sequencia(
    ipc: list[Call], mode_id: str, flavor: str, emul_handler: str
) -> None:
    """Aceite do HARM-01: alternar Início<->Emulação nunca mostra estados
    diferentes porque as duas abas fazem literalmente a mesma coisa."""
    home = _HomeStub(flavor)
    home._home_mode_selector.set_active_id(mode_id)
    home._on_home_mode_changed(home._home_mode_selector)
    pela_inicio = list(ipc)

    ipc.clear()
    getattr(_EmulStub(), emul_handler)(None)

    assert pela_inicio == list(ipc)


# --- HARM-03: "Modo jogo" não é oferecido em "Controlar o PC" ---------------


class _FakeButton:
    def __init__(self) -> None:
        self.sensitive = True

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = value


class _GameModeStub(emulation_actions.EmulationActionsMixin):
    def __init__(self) -> None:
        self.pause_btn = _FakeButton()
        self.hint = _FakeLabel()

    def _get(self, widget_id: str) -> Any:
        if widget_id == "emulation_pause_button":
            return self.pause_btn
        if widget_id == "emulation_gamemode_hint_label":
            return self.hint
        return None


def test_modo_jogo_desabilitado_em_controlar_o_pc() -> None:
    """Ligá-lo em desktop deixava o controle sem função NENHUMA (só faz
    mouse/teclado nesse modo) e o tooltip afirmava o contrário."""
    stub = _GameModeStub()
    stub._sync_gamemode_button("desktop")

    assert stub.pause_btn.sensitive is False
    assert "sem função nenhuma" in stub.hint.text


@pytest.mark.parametrize("mode", ["gamepad", "native"])
def test_modo_jogo_disponivel_jogando_e_sem_explicacao_sobrando(mode: str) -> None:
    stub = _GameModeStub()
    stub._sync_gamemode_button("desktop")  # estado anterior: bloqueado
    stub._sync_gamemode_button(mode)

    assert stub.pause_btn.sensitive is True
    assert stub.hint.text == ""


def test_modo_jogo_desabilitado_com_daemon_offline() -> None:
    """Sem estado não dá para saber se faz sentido; não oferecer às cegas."""
    stub = _GameModeStub()
    stub._sync_gamemode_button(None)

    assert stub.pause_btn.sensitive is False
    assert stub.hint.text == ""


def test_sync_gamemode_sem_widgets_nao_estoura() -> None:
    """A aba é montada por Glade; `_get` devolve None antes do install."""
    _EmulStub()._sync_gamemode_button("desktop")
