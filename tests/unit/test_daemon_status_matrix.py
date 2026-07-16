"""Testes da matriz de estados do daemon (BUG-DAEMON-STATUS-MISMATCH-01).

Cobre `_daemon_status()` com monkeypatch das 3 fontes:
  1. `_systemctl_oneline` — retorna is-active e is-enabled.
  2. `_read_daemon_pid` — retorna o pid lido do arquivo.
  3. `is_alive` via single_instance — retorna se o pid esta vivo.

As 4 combinacoes principais da matriz:
  A. systemd active + processo vivo   → online_systemd
  B. systemd inactive + processo vivo → online_avulso
  C. systemd active + processo morto  → iniciando
  D. systemd inactive + processo morto → offline

Adicionalmente verifica o estado `online_systemd` com enabled=enabled
e que `_set_daemon_status_markup` pinta o label correto.

Usa stubs gi para rodar em CI sem display GTK.
"""
from __future__ import annotations

import sys
import types
from typing import Any


def _install_gi_stubs() -> None:
    """Instala stubs minimos de gi.repository para rodar sem GTK real."""
    # GATE-SKIP-MASK-01: com o PyGObject real disponível, NÃO instala stubs —
    # poluir sys.modules["gi"] na coleta fazia testes de GUI pularem como
    # "ambiente sem GTK" mesmo com o GTK real presente.
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

    class _FakeLabel:
        def __init__(self) -> None:
            self._markup: str = ""
            self._tooltip: str = ""

        def set_markup(self, markup: str) -> None:
            self._markup = markup

        def set_tooltip_text(self, tooltip: str) -> None:
            self._tooltip = tooltip

        def set_visible(self, _v: bool) -> None:
            pass

    class _FakeSwitch:
        def set_active(self, _v: bool) -> None:
            pass

    class _FakeButton:
        def set_sensitive(self, _v: bool) -> None:
            pass

        def set_tooltip_text(self, _t: str) -> None:
            pass

        def set_visible(self, _v: bool) -> None:
            pass

    class _FakeTextView:
        def get_buffer(self) -> _FakeBuffer:
            return _FakeBuffer()

        def scroll_to_mark(self, *_a: Any, **_kw: Any) -> None:
            pass

        def scroll_to_iter(self, *_a: Any, **_kw: Any) -> None:
            pass

    class _FakeBuffer:
        def set_text(self, _t: str) -> None:
            pass

        def get_end_iter(self) -> None:
            return None  # type: ignore[return-value]

        def create_mark(self, *_a: Any) -> None:
            return None  # type: ignore[return-value]

        def delete_mark(self, _m: Any) -> None:
            pass

    class _FakeWindow:
        pass

    gtk_mod.Builder = object  # type: ignore[attr-defined]
    gtk_mod.Window = _FakeWindow  # type: ignore[attr-defined]
    gtk_mod.Button = _FakeButton  # type: ignore[attr-defined]
    gtk_mod.Switch = _FakeSwitch  # type: ignore[attr-defined]
    gtk_mod.Label = _FakeLabel  # type: ignore[attr-defined]
    gtk_mod.TextView = _FakeTextView  # type: ignore[attr-defined]
    gtk_mod.TextBuffer = _FakeBuffer  # type: ignore[attr-defined]
    gtk_mod.MessageDialog = object  # type: ignore[attr-defined]
    gtk_mod.MessageType = object  # type: ignore[attr-defined]
    gtk_mod.ButtonsType = object  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
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
# Host mínimo para exercitar _daemon_status sem Builder real
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

    # UI-DAEMON-LOG-AUTOSCROLL-01: autoscroll do log usa scroll_to_iter.
    def scroll_to_iter(self, *_a: Any, **_kw: Any) -> None:
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
    def set_active(self, _v: bool) -> None:
        pass


class _FakeButtonObj:
    def __init__(self) -> None:
        self.visible: bool = False

    def set_visible(self, v: bool) -> None:
        self.visible = v


class _Host(DaemonActionsMixin):
    """Host mínimo que permite monkeypatch de _systemctl_oneline e _read_daemon_pid."""

    def __init__(self) -> None:
        self._daemon_autostart_guard = False
        self._daemon_autostart_attempts = 0
        # Widgets fake para _set_daemon_status_markup e _refresh_daemon_view.
        self._label = _FakeLabelObj()
        self._sw = _FakeSwitchObj()
        self._btn_migrate = _FakeButtonObj()

    def _get(self, widget_id: str) -> Any:
        if widget_id == "daemon_status_label":
            return self._label
        if widget_id == "daemon_autostart_switch":
            return self._sw
        if widget_id == "btn_migrate_to_systemd":
            return self._btn_migrate
        if widget_id == "daemon_status_text":
            return _FakeTextViewObj()
        return None

    # Stub de _systemctl_status_text para não chamar subprocess real.
    def _systemctl_status_text(self, _unit: str) -> str:
        return "(stub)"


# ---------------------------------------------------------------------------
# Testes da matriz de estados
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "systemd_active, process_alive, expected_status",
    [
        (True, True, "online_systemd"),    # A: systemd + processo vivo
        (False, True, "online_avulso"),    # B: avulso
        (True, False, "iniciando"),        # C: systemd active, processo ausente
        (False, False, "offline"),         # D: tudo morto
    ],
)
def test_daemon_status_matriz(
    monkeypatch: pytest.MonkeyPatch,
    systemd_active: bool,
    process_alive: bool,
    expected_status: str,
) -> None:
    """_daemon_status() retorna o estado correto para cada combinacao da matriz."""
    host = _Host()

    def _fake_oneline(args: list[str]) -> str:
        if "is-active" in args:
            return "active" if systemd_active else "inactive"
        if "is-enabled" in args:
            return "enabled"
        return ""

    monkeypatch.setattr(host, "_systemctl_oneline", _fake_oneline)

    pid_val: int | None = 12345 if process_alive else None
    monkeypatch.setattr(host, "_read_daemon_pid", lambda: pid_val)
    monkeypatch.setattr(si_mod, "is_alive", lambda pid: process_alive)

    result = host._daemon_status()
    assert result == expected_status


def test_online_systemd_com_enabled_diz_que_liga_sozinho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verde + a informação de que o Hefesto sobe junto com o computador.

    LEIGO-03: o texto dizia "Online (systemd + auto-start)". O fato exibido é o
    mesmo (`is-enabled` == enabled), então o teste continua sendo sobre ELE — só
    parou de exigir a palavra do systemd.
    """
    host = _Host()

    def _fake_oneline(args: list[str]) -> str:
        if "is-active" in args:
            return "active"
        if "is-enabled" in args:
            return "enabled"
        return ""

    monkeypatch.setattr(host, "_systemctl_oneline", _fake_oneline)
    monkeypatch.setattr(host, "_read_daemon_pid", lambda: 99)
    monkeypatch.setattr(si_mod, "is_alive", lambda _pid: True)

    host._set_daemon_status_markup("online_systemd", "enabled")

    assert "#2d8" in host._label.markup
    assert "Funcionando" in host._label.markup
    assert "liga sozinho" in host._label.markup


def test_online_systemd_sem_enabled_nao_promete_ligar_sozinho() -> None:
    """Com `is-enabled` != enabled o label NÃO pode prometer o autostart."""
    host = _Host()
    host._set_daemon_status_markup("online_systemd", "disabled")

    assert "#2d8" in host._label.markup
    assert "Funcionando" in host._label.markup
    assert "liga sozinho" not in host._label.markup


def test_offline_label_vermelho(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado desligado: vermelho + a palavra que a usuária entende."""
    host = _Host()
    host._set_daemon_status_markup("offline", "disabled")

    assert "#d33" in host._label.markup
    assert "Desligado" in host._label.markup


def test_online_avulso_label_amarelo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avulso: amarelo + o aviso de que está funcionando "no improviso"."""
    host = _Host()
    host._set_daemon_status_markup("online_avulso", "disabled")

    assert "#ca0" in host._label.markup
    assert "improvisado" in host._label.markup


def test_nenhum_estado_vaza_jargao_na_tela(monkeypatch: pytest.MonkeyPatch) -> None:
    """LEIGO-03: systemd/unit/rc=/.service/Online não aparecem no label.

    O acoplamento a texto de UI é o que quebrou os testes acima quando a aba foi
    reescrita; este aqui é o oposto — trava a REGRA do sprint (nada de jargão),
    não uma frase específica.
    """
    proibidas = ("systemd", "unit", "rc=", ".service", "Online", "Offline",
                 "daemon", "avulso", "pid")
    for status in ("online_systemd", "online_avulso", "iniciando", "offline"):
        for enabled in ("enabled", "disabled"):
            host = _Host()
            host._set_daemon_status_markup(status, enabled)  # type: ignore[arg-type]
            visivel = host._label.markup
            for palavra in proibidas:
                assert palavra not in visivel, (
                    f"{status}/{enabled} mostra {palavra!r} na tela: {visivel!r}"
                )


def test_botao_migrate_visivel_apenas_em_avulso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """btn_migrate_to_systemd fica visivel apenas no estado online_avulso."""
    host = _Host()

    # Estado online_avulso: botao deve ficar visivel.
    def _fake_oneline_avulso(args: list[str]) -> str:
        if "is-active" in args:
            return "inactive"
        if "is-enabled" in args:
            return "disabled"
        return ""

    monkeypatch.setattr(host, "_systemctl_oneline", _fake_oneline_avulso)
    monkeypatch.setattr(host, "_read_daemon_pid", lambda: 777)
    monkeypatch.setattr(si_mod, "is_alive", lambda _pid: True)

    host._refresh_daemon_view()

    assert host._btn_migrate.visible is True

    # Estado offline: botao deve ficar oculto.
    monkeypatch.setattr(host, "_read_daemon_pid", lambda: None)
    monkeypatch.setattr(si_mod, "is_alive", lambda _pid: False)

    host._refresh_daemon_view()

    assert host._btn_migrate.visible is False
