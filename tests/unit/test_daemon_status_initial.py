"""Testes do primeiro refresh do status do daemon no bootstrap da GUI.

BUG-GUI-DAEMON-STATUS-INITIAL-01 — a aba Daemon (e a aba Status) mostrava
"Offline" no primeiro frame mesmo com o daemon ativo, porque:

  1. O default do Glade em ``status_daemon`` era ``"Offline"``.
  2. O primeiro tick do polling só disparava após 100 ms / 500 ms.
  3. ``_refresh_daemon_view`` era chamado síncrono no bootstrap da aba,
     bloqueando a thread GTK por até 15 s de timeout em ``systemctl`` caso
     o systemd travasse — atrasando o primeiro frame.

Fix coberto por estes testes:

  - Cenário 1 (daemon ativo): após ``install_daemon_tab``, o label final
    mostra ``online_systemd`` (verde, "● Online").
  - Cenário 2 (daemon inativo): o label final mostra ``offline``
    (vermelho, "○ Offline") — nunca "Iniciando...".
  - Cenário 3 (systemctl não responde / falha): durante a janela em que o
    worker ainda está rodando, o label mostra "● Consultando..." cinza em
    vez do falso-negativo "Offline".

Usa stubs de ``gi`` idênticos aos de ``test_daemon_status_matrix.py``.
"""
from __future__ import annotations

import sys
import types
from typing import Any


def _install_gi_stubs() -> None:
    """Stubs mínimos de gi.repository para rodar sem GTK real."""
    if "gi" in sys.modules and hasattr(sys.modules["gi"], "require_version"):
        try:
            from gi.repository import Gtk  # noqa: F401
            return
        except Exception:
            pass

    gi_mod = types.ModuleType("gi")

    def _require_version(_name: str, _ver: str) -> None:
        return None

    gi_mod.require_version = _require_version  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    glib_mod = types.ModuleType("gi.repository.GLib")

    class _FakeWindow:
        pass

    gtk_mod.Builder = object  # type: ignore[attr-defined]
    gtk_mod.Window = _FakeWindow  # type: ignore[attr-defined]
    gtk_mod.Button = object  # type: ignore[attr-defined]
    gtk_mod.Switch = object  # type: ignore[attr-defined]
    gtk_mod.Label = object  # type: ignore[attr-defined]
    gtk_mod.TextView = object  # type: ignore[attr-defined]
    gtk_mod.TextBuffer = object  # type: ignore[attr-defined]
    gtk_mod.MessageDialog = object  # type: ignore[attr-defined]
    gtk_mod.MessageType = object  # type: ignore[attr-defined]
    gtk_mod.ButtonsType = object  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw) or 0  # type: ignore[attr-defined]
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

import pytest  # noqa: E402

import hefesto_dualsense4unix.utils.single_instance as si_mod  # noqa: E402
from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin  # noqa: E402

# ---------------------------------------------------------------------------
# Fakes mínimos (espelham test_daemon_status_matrix.py)
# ---------------------------------------------------------------------------


class _FakeBufferObj:
    def set_text(self, _t: str) -> None:
        pass

    def get_end_iter(self) -> None:
        return None  # type: ignore[return-value]

    def create_mark(self, *_a: Any) -> None:
        return None  # type: ignore[return-value]

    def delete_mark(self, _m: Any) -> None:
        pass


class _FakeTextViewObj:
    def get_buffer(self) -> _FakeBufferObj:
        return _FakeBufferObj()

    def scroll_to_mark(self, *_a: Any, **_kw: Any) -> None:
        pass


class _FakeLabelObj:
    def __init__(self) -> None:
        self.markup: str = ""
        self.tooltip: str = ""

    def set_markup(self, markup: str) -> None:
        self.markup = markup

    def set_tooltip_text(self, tooltip: str) -> None:
        self.tooltip = tooltip


class _FakeSwitchObj:
    def __init__(self) -> None:
        self.active: bool = False

    def set_active(self, v: bool) -> None:
        self.active = v


class _FakeButtonObj:
    def __init__(self) -> None:
        self.visible: bool = False
        self.sensitive: bool = True
        self.tooltip: str = ""

    def set_visible(self, v: bool) -> None:
        self.visible = v

    def set_sensitive(self, v: bool) -> None:
        self.sensitive = v

    def set_tooltip_text(self, t: str) -> None:
        self.tooltip = t


class _ImmediateExecutor:
    """Executor síncrono — roda o worker na mesma thread, imediatamente."""

    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> None:
        fn(*args, **kwargs)


class _Host(DaemonActionsMixin):
    """Host mínimo com widgets fake e executor síncrono."""

    def __init__(self) -> None:
        self._daemon_autostart_guard = False
        self._daemon_autostart_attempts = 0
        self._label = _FakeLabelObj()
        self._sw = _FakeSwitchObj()
        self._btn_migrate = _FakeButtonObj()
        self._btn_restart = _FakeButtonObj()

    def _get(self, widget_id: str) -> Any:
        if widget_id == "daemon_status_label":
            return self._label
        if widget_id == "daemon_autostart_switch":
            return self._sw
        if widget_id == "btn_migrate_to_systemd":
            return self._btn_migrate
        if widget_id == "btn_restart_daemon":
            return self._btn_restart
        if widget_id == "daemon_status_text":
            return _FakeTextViewObj()
        return None

    def _systemctl_status_text(self, _unit: str) -> str:
        return "(stub status text)"


def _patch_installer_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Faz `ServiceInstaller().detect_installed_unit()` retornar None.

    Evita que `_sync_restart_daemon_button_sensitivity` tente rodar systemctl
    real durante os testes — o sensitivity ramifica em `installed = None`
    (botão desabilitado).
    """
    from hefesto_dualsense4unix.daemon import service_install

    class _FakeInstaller:
        def detect_installed_unit(self) -> Any:
            return None

    monkeypatch.setattr(service_install, "ServiceInstaller", _FakeInstaller)


def _patch_executor_immediate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Faz `_get_executor()` devolver um executor síncrono.

    Necessário para que o worker do `_refresh_daemon_view_async` rode antes
    do teste terminar — em produção é `ThreadPoolExecutor`.

    Também força `GLib.idle_add` a executar a callback na hora: o stub global
    de `test_daemon_status_matrix.py` (instalado no carregamento do módulo)
    retorna 0 sem chamar a função, porque lá não precisava — aqui precisa.
    """
    from hefesto_dualsense4unix.app import ipc_bridge

    monkeypatch.setattr(ipc_bridge, "_get_executor", lambda: _ImmediateExecutor())
    from hefesto_dualsense4unix.app.actions import daemon_actions

    monkeypatch.setattr(daemon_actions, "_get_executor", lambda: _ImmediateExecutor())

    # Força `daemon_actions.GLib.idle_add` a executar a callback.
    def _eager_idle_add(fn: Any, *args: Any, **kwargs: Any) -> int:
        fn(*args, **kwargs)
        return 0

    monkeypatch.setattr(daemon_actions.GLib, "idle_add", _eager_idle_add)


# ---------------------------------------------------------------------------
# Testes do primeiro refresh no bootstrap
# ---------------------------------------------------------------------------


def test_install_daemon_tab_com_daemon_ativo_pinta_online(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cenário 1: daemon ativo (systemd + processo vivo).

    Após `install_daemon_tab`, o worker roda imediatamente (executor síncrono),
    o `GLib.idle_add` (stub) aplica o resultado e o label final mostra
    "● Online" verde — nunca passa por "Offline".
    """
    _patch_installer_none(monkeypatch)
    _patch_executor_immediate(monkeypatch)

    host = _Host()

    def _fake_oneline(args: list[str]) -> str:
        if "is-active" in args:
            return "active"
        if "is-enabled" in args:
            return "enabled"
        return ""

    monkeypatch.setattr(host, "_systemctl_oneline", _fake_oneline)
    monkeypatch.setattr(host, "_read_daemon_pid", lambda: 99999)
    monkeypatch.setattr(si_mod, "is_alive", lambda _pid: True)

    host.install_daemon_tab()

    assert "#2d8" in host._label.markup, (
        f"esperava cor verde (#2d8) para online_systemd; markup={host._label.markup!r}"
    )
    assert "Online" in host._label.markup
    assert "Offline" not in host._label.markup
    assert "Consultando" not in host._label.markup  # já foi sobrescrito pelo async
    assert host._sw.active is True  # enabled


def test_install_daemon_tab_com_daemon_inativo_pinta_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cenário 2: daemon inativo (systemd inactive + sem processo).

    Após `install_daemon_tab`, o label final é "○ Offline" vermelho — nunca
    fica preso em "Iniciando..." nem no estado "Consultando..." transitório.
    """
    _patch_installer_none(monkeypatch)
    _patch_executor_immediate(monkeypatch)

    host = _Host()

    def _fake_oneline(args: list[str]) -> str:
        if "is-active" in args:
            return "inactive"
        if "is-enabled" in args:
            return "disabled"
        return ""

    monkeypatch.setattr(host, "_systemctl_oneline", _fake_oneline)
    monkeypatch.setattr(host, "_read_daemon_pid", lambda: None)
    monkeypatch.setattr(si_mod, "is_alive", lambda _pid: False)

    host.install_daemon_tab()

    assert "#d33" in host._label.markup, (
        f"esperava cor vermelha (#d33) para offline; markup={host._label.markup!r}"
    )
    assert "Offline" in host._label.markup
    assert "Iniciando" not in host._label.markup
    assert "Consultando" not in host._label.markup
    assert host._sw.active is False


def test_consulting_placeholder_aparece_antes_do_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cenário 3: worker não responde — label permanece "Consultando...".

    Aqui o executor NÃO é substituído pelo síncrono: o `submit` do
    `ThreadPoolExecutor` real agenda o worker em outra thread e retorna
    imediatamente. Durante o primeiro frame da GUI (antes do worker terminar),
    o usuário precisa ver "Consultando..." cinza — nunca "Offline" cru.
    """
    _patch_installer_none(monkeypatch)

    host = _Host()

    # Captura o worker sem executar — simula thread que ainda está rodando.
    captured: dict[str, Any] = {}

    class _LazyExecutor:
        def submit(self, fn: Any, *args: Any, **kwargs: Any) -> None:
            captured["fn"] = fn
            captured["args"] = (args, kwargs)

    from hefesto_dualsense4unix.app.actions import daemon_actions

    monkeypatch.setattr(
        daemon_actions, "_get_executor", lambda: _LazyExecutor()
    )

    host.install_daemon_tab()

    # Worker foi agendado mas não executado — label deve mostrar o placeholder
    # "Consultando..." cinza (nem verde, nem vermelho, nem amarelo).
    assert "Consultando" in host._label.markup, (
        f"esperava placeholder 'Consultando...'; markup={host._label.markup!r}"
    )
    assert "#888" in host._label.markup, (
        f"esperava cor cinza (#888) no placeholder; markup={host._label.markup!r}"
    )
    assert "Offline" not in host._label.markup
    assert "Iniciando" not in host._label.markup
    assert "fn" in captured, "worker do _refresh_daemon_view_async não foi agendado"
