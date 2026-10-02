"""Testes da matriz de estados do daemon (BUG-DAEMON-STATUS-MISMATCH-01)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("a matriz do estado do daemon na janela")

import sys
import types
from typing import Any


def _install_gi_stubs() -> None:
    """Instala stubs minimos de gi.repository para rodar sem GTK real."""
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

import pytest

import hefesto_dualsense4unix.utils.single_instance as si_mod
from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin


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
        self.sensitive: bool | None = None
        self.tooltip: str = ""

    def set_visible(self, v: bool) -> None:
        self.visible = v

    def set_sensitive(self, v: bool) -> None:
        self.sensitive = v

    def set_tooltip_text(self, t: str) -> None:
        self.tooltip = t


class _Host(DaemonActionsMixin):
    """Host mínimo que permite monkeypatch de _systemctl_oneline e _read_daemon_pid."""

    def __init__(self) -> None:
        self._daemon_autostart_guard = False
        self._daemon_autostart_attempts = 0
        self._label = _FakeLabelObj()
        self._sw = _FakeSwitchObj()
        self._btn_migrate = _FakeButtonObj()
        self._btn_start = _FakeButtonObj()
        self._btn_stop = _FakeButtonObj()

    def _get(self, widget_id: str) -> Any:
        if widget_id == "daemon_status_label":
            return self._label
        if widget_id == "daemon_autostart_switch":
            return self._sw
        if widget_id == "btn_migrate_to_systemd":
            return self._btn_migrate
        if widget_id == "daemon_start_button":
            return self._btn_start
        if widget_id == "daemon_stop_button":
            return self._btn_stop
        if widget_id == "daemon_status_text":
            return _FakeTextViewObj()
        return None

    def _systemctl_status_text(self, _unit: str) -> str:
        return "(stub)"


@pytest.mark.parametrize(
    "systemd_active, process_alive, expected_status",
    [
        (True, True, "online_systemd"),
        (False, True, "online_avulso"),
        (True, False, "iniciando"),
        (False, False, "offline"),
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
    """Verde + a informação de que o Hefesto sobe junto com o computador."""
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

    assert "#50fa7b" in host._label.markup
    assert "Funcionando" in host._label.markup
    assert "liga sozinho" in host._label.markup


def test_online_systemd_sem_enabled_nao_promete_ligar_sozinho() -> None:
    """Com `is-enabled` != enabled o label NÃO pode prometer o autostart."""
    host = _Host()
    host._set_daemon_status_markup("online_systemd", "disabled")

    assert "#50fa7b" in host._label.markup
    assert "Funcionando" in host._label.markup
    assert "liga sozinho" not in host._label.markup


def test_offline_label_vermelho(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado desligado: vermelho + a palavra que a usuária entende."""
    host = _Host()
    host._set_daemon_status_markup("offline", "disabled")

    assert "#ff5555" in host._label.markup
    assert "Desligado" in host._label.markup


def test_online_avulso_label_amarelo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avulso: amarelo + o aviso de que está funcionando "no improviso"."""
    host = _Host()
    host._set_daemon_status_markup("online_avulso", "disabled")

    assert "#ffb86c" in host._label.markup
    assert "improvisado" in host._label.markup


def test_nenhum_estado_vaza_jargao_na_tela(monkeypatch: pytest.MonkeyPatch) -> None:
    """LEIGO-03: systemd/unit/rc=/.service/Online não aparecem no label."""
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

    monkeypatch.setattr(host, "_read_daemon_pid", lambda: None)
    monkeypatch.setattr(si_mod, "is_alive", lambda _pid: False)

    host._refresh_daemon_view()

    assert host._btn_migrate.visible is False


@pytest.mark.parametrize(
    "status, ligar_sensivel, desligar_sensivel",
    [
        ("online_systemd", False, True),
        ("online_avulso", False, True),
        ("iniciando", False, True),
        ("offline", True, False),
    ],
)
def test_ligar_e_desligar_ficam_cinzas_conforme_o_estado(
    status: str, ligar_sensivel: bool, desligar_sensivel: bool
) -> None:
    """A matriz que faltava: o botão sem trabalho a fazer fica cinza."""
    host = _Host()

    host._apply_daemon_view(status, "disabled", "(texto)")  # type: ignore[arg-type]

    assert host._btn_start.sensitive is ligar_sensivel
    assert host._btn_stop.sensitive is desligar_sensivel


@pytest.mark.parametrize("status", ["online_systemd", "offline"])
def test_o_botao_cinza_diz_por_que_esta_cinza(status: str) -> None:
    """Botão cinza sem explicação manda procurar defeito onde não há."""
    host = _Host()

    host._apply_daemon_view(status, "disabled", "(texto)")  # type: ignore[arg-type]

    apagado = host._btn_start if status == "online_systemd" else host._btn_stop
    assert apagado.sensitive is False
    assert apagado.tooltip.strip(), "botão cinza precisa dizer por quê"
    assert "já está" in apagado.tooltip


def test_desligar_com_sucesso_arma_o_flag_que_impede_a_ressurreicao() -> None:
    """T-06(b): o "Desligar" desta aba passa a durar além do próximo F5."""
    host = _Host()
    host._toast_daemon = lambda *_a, **_kw: None  # type: ignore[assignment]
    host._refresh_daemon_view_async = lambda *_a, **_kw: None  # type: ignore[assignment]

    host._on_systemctl_done("stop", "unit", 0)

    assert host._user_stopped_daemon is True


def test_desligar_que_falhou_nao_arma_o_flag() -> None:
    """A lição da BUG-HOME-SHUTDOWN-FALSE-OK-01, agora dos dois lados."""
    host = _Host()
    host._toast_daemon = lambda *_a, **_kw: None  # type: ignore[assignment]
    host._refresh_daemon_view_async = lambda *_a, **_kw: None  # type: ignore[assignment]

    host._on_systemctl_done("stop", "unit", 1)

    assert getattr(host, "_user_stopped_daemon", False) is False


def test_ligar_com_sucesso_nao_arma_o_flag_de_desligamento() -> None:
    """Só o "stop" arma. Um "start" bem-sucedido não pode marcar desligamento."""
    host = _Host()
    host._toast_daemon = lambda *_a, **_kw: None  # type: ignore[assignment]
    host._refresh_daemon_view_async = lambda *_a, **_kw: None  # type: ignore[assignment]

    host._on_systemctl_done("start", "unit", 0)

    assert getattr(host, "_user_stopped_daemon", False) is False


class _TextViewQueGuarda:
    """Dublê de `daemon_status_text` que LEMBRA o que foi escrito."""

    def __init__(self) -> None:
        self.texto: str = ""

    def get_buffer(self) -> Any:
        return self

    def set_text(self, t: str) -> None:
        self.texto = t

    def get_end_iter(self) -> None:
        return None

    def create_mark(self, *_a: Any) -> None:
        return None

    def delete_mark(self, _m: Any) -> None:
        pass

    def scroll_to_mark(self, *_a: Any, **_kw: Any) -> None:
        pass

    def scroll_to_iter(self, *_a: Any, **_kw: Any) -> None:
        pass


class _HostComPainel(_Host):
    def __init__(self) -> None:
        super().__init__()
        self._painel = _TextViewQueGuarda()

    def _get(self, widget_id: str) -> Any:
        if widget_id == "daemon_status_text":
            return self._painel
        return super()._get(widget_id)


def test_o_detalhe_do_erro_aparece_no_painel() -> None:
    """A promessa que a frase faz, cumprida pela primeira vez."""
    host = _HostComPainel()

    host._set_daemon_text("(systemctl status do daemon)")
    host._detalhe_tecnico("Traceback: ValueError('vdf ilegível')", assunto="teste")

    assert "systemctl status do daemon" in host._painel.texto
    assert "vdf ilegível" in host._painel.texto
    assert "--- teste ---" in host._painel.texto


def test_o_detalhe_sobrevive_ao_refresh_que_vem_logo_depois() -> None:
    """A metade que faz a cura funcionar de verdade."""
    host = _HostComPainel()

    host._detalhe_tecnico("motivo que importa", assunto="falha")
    host._set_daemon_text("(status novo, vindo do refresh)")

    assert "status novo" in host._painel.texto
    assert "motivo que importa" in host._painel.texto


def test_limpar_tira_o_detalhe_e_mantem_o_corpo() -> None:
    host = _HostComPainel()
    host._set_daemon_text("(corpo)")
    host._detalhe_tecnico("erro velho")

    host._limpar_detalhe_tecnico()

    assert "(corpo)" in host._painel.texto
    assert "erro velho" not in host._painel.texto


def test_detalhe_vazio_nao_suja_o_painel_com_cabecalho_solto() -> None:
    """Régua que sabe RECUSAR: sem saída crua não há detalhe a mostrar."""
    host = _HostComPainel()
    host._set_daemon_text("(corpo)")

    assert host._detalhe_tecnico("   ") is False
    assert host._detalhe_tecnico(None) is False
    assert host._painel.texto == "(corpo)"


def test_o_painel_continua_sem_escapes_ansi() -> None:
    """O `systemctl status` vem colorido; o TextView não entende ANSI."""
    host = _HostComPainel()

    host._set_daemon_text("\x1b[32mativo\x1b[0m")
    host._detalhe_tecnico("\x1b[31mfalhou\x1b[0m")

    assert "\x1b[" not in host._painel.texto
    assert "ativo" in host._painel.texto
    assert "falhou" in host._painel.texto
