"""Testes de `ensure_daemon_running` (BUG-DAEMON-AUTOSTART-01).

Cobre:
  - No-op quando `detect_installed_unit()` retorna None.
  - No-op quando o service já está `active`.
  - Dispara `systemctl --user start hefesto-dualsense4unix.service` quando inativo.
  - Respeita limite anti-loop de 2 tentativas por sessão.
  - Submete trabalho ao executor (não bloqueia a thread chamadora).

Usa stubs `gi` para rodar em CI sem display GTK.
"""
from __future__ import annotations

import subprocess
import sys
import types
from typing import Any, ClassVar


def _install_gi_stubs() -> None:
    # GATE-SKIP-MASK-01: com o PyGObject real disponível, NÃO instala stubs —
    # poluir sys.modules["gi"] na coleta fazia testes de GUI pularem como
    # "ambiente sem GTK" mesmo com o GTK real presente. Stub só entra quando
    # o import real falha de verdade (CI sem PyGObject).
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

    class _FakeButton:
        def set_sensitive(self, _v: bool) -> None:
            pass

        def set_tooltip_text(self, _t: str) -> None:
            pass

    gtk_mod.Builder = object  # type: ignore[attr-defined]
    gtk_mod.Window = object  # type: ignore[attr-defined]
    gtk_mod.Button = _FakeButton  # type: ignore[attr-defined]
    gtk_mod.ComboBoxText = object  # type: ignore[attr-defined]
    gtk_mod.Switch = object  # type: ignore[attr-defined]
    gtk_mod.TextView = object  # type: ignore[attr-defined]
    gtk_mod.TextBuffer = object  # type: ignore[attr-defined]
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

from hefesto_dualsense4unix.app.actions import daemon_actions as da  # noqa: E402
from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin  # noqa: E402


class _SyncExecutor:
    """Executor fake que roda o worker inline — sem threads de fato.

    Permite asserts síncronos depois de `ensure_daemon_running()`.
    """

    def __init__(self) -> None:
        self.submitted: list[Any] = []

    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> None:
        self.submitted.append(fn)
        fn(*args, **kwargs)


class _Host(DaemonActionsMixin):
    """Host mínimo para exercitar o helper sem Builder real."""

    def __init__(self) -> None:
        self._daemon_autostart_guard = False
        self._daemon_autostart_attempts = 0

    def _daemon_pid_alive(self) -> bool:
        """Isola o teste do pid file do sistema host (BUG-MULTI-INSTANCE-01).

        Teste só exercita o fluxo systemd; cenário do pid file tem sua
        própria suíte. Default False garante que os testes antigos continuem
        cobrindo o caso 'systemd inactive + nenhum processo avulso'.
        """
        return False


class _FakePopen:
    """Substituto hermético de `subprocess.Popen` para este arquivo.

    HERMETICIDADE (achado da onda SPRINT-UX-AUTOSWITCH-01): os testes daqui
    mockavam só `subprocess.run`; quando o systemctl fake "falhava"
    (`raise_on_start`/`start_rc!=0`), o `_start_service_blocking` caía no
    fallback de Popen REAL e spawnava um daemon `--foreground` DE VERDADE na
    máquina (órfão, `start_new_session=True`) a cada rodada da suíte — mesmo
    perigo do `test_quit_app` que já matou o daemon da usuária. O fake
    preserva o caminho de código (poll() vivo → rc 0) sem processo real.
    """

    spawned: ClassVar[list[list[str]]] = []

    def __init__(self, cmd: list[str], *args: Any, **kwargs: Any) -> None:
        type(self).spawned.append(list(cmd))
        self.pid = 424242
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return None


@pytest.fixture(autouse=True)
def _popen_hermetico(monkeypatch: pytest.MonkeyPatch) -> type[_FakePopen]:
    """Nenhum teste deste arquivo pode spawnar processo real (ver _FakePopen)."""
    _FakePopen.spawned = []
    monkeypatch.setattr(da.subprocess, "Popen", _FakePopen)
    return _FakePopen


@pytest.fixture
def sync_executor(monkeypatch: pytest.MonkeyPatch) -> _SyncExecutor:
    exe = _SyncExecutor()
    monkeypatch.setattr(da, "_get_executor", lambda: exe)
    return exe


@pytest.fixture
def host() -> _Host:
    return _Host()


def _fake_run_factory(
    is_active_stdout: str,
    start_rc: int = 0,
    raise_on_start: Exception | None = None,
) -> tuple[list[list[str]], Any]:
    """Produz um substituto de `subprocess.run` que distingue is-active vs start."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(list(cmd))
        if "is-active" in cmd:
            result = subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=is_active_stdout, stderr=""
            )
            return result
        if "start" in cmd:
            if raise_on_start is not None:
                raise raise_on_start
            return subprocess.CompletedProcess(
                args=cmd, returncode=start_rc, stdout="", stderr=""
            )
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="", stderr=""
        )

    return calls, fake_run


def test_noop_quando_unit_nao_instalada(
    host: _Host,
    sync_executor: _SyncExecutor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Se `detect_installed_unit()` retorna None, não dispara systemctl."""
    monkeypatch.setattr(
        da.ServiceInstaller, "detect_installed_unit", lambda self: None
    )
    calls, fake_run = _fake_run_factory(is_active_stdout="inactive\n")
    monkeypatch.setattr(da.subprocess, "run", fake_run)

    host.ensure_daemon_running()

    assert calls == []
    assert host._daemon_autostart_attempts == 0


def test_noop_quando_daemon_ja_ativo(
    host: _Host,
    sync_executor: _SyncExecutor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Se is-active retorna `active`, não dispara start."""
    monkeypatch.setattr(
        da.ServiceInstaller, "detect_installed_unit", lambda self: "hefesto-dualsense4unix"
    )
    calls, fake_run = _fake_run_factory(is_active_stdout="active\n")
    monkeypatch.setattr(da.subprocess, "run", fake_run)

    host.ensure_daemon_running()

    # Apenas a chamada is-active deve ter ocorrido — nenhuma start.
    assert any("is-active" in " ".join(c) for c in calls)
    # Nenhum cmd contém o argumento literal "start" (exceto dentro de "is-active" — filtrado).
    started = [c for c in calls if "start" in c and "is-active" not in c]
    assert started == []
    assert host._daemon_autostart_attempts == 0


def test_dispara_start_quando_inativo(
    host: _Host,
    sync_executor: _SyncExecutor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Se is-active != active, dispara systemctl start e incrementa contador."""
    monkeypatch.setattr(
        da.ServiceInstaller, "detect_installed_unit", lambda self: "hefesto-dualsense4unix"
    )
    calls, fake_run = _fake_run_factory(
        is_active_stdout="inactive\n", start_rc=0
    )
    monkeypatch.setattr(da.subprocess, "run", fake_run)

    host.ensure_daemon_running()

    started = [c for c in calls if "start" in c and "is-active" not in c]
    assert len(started) == 1
    assert "hefesto-dualsense4unix.service" in started[0]
    assert host._daemon_autostart_attempts == 1


def test_limite_anti_loop_duas_tentativas(
    host: _Host,
    sync_executor: _SyncExecutor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Após 2 tentativas, helper vira no-op até próxima sessão."""
    monkeypatch.setattr(
        da.ServiceInstaller, "detect_installed_unit", lambda self: "hefesto-dualsense4unix"
    )
    calls, fake_run = _fake_run_factory(
        is_active_stdout="inactive\n", start_rc=1
    )
    monkeypatch.setattr(da.subprocess, "run", fake_run)

    # Três chamadas consecutivas — só duas devem executar start.
    host.ensure_daemon_running()
    host.ensure_daemon_running()
    host.ensure_daemon_running()

    started = [c for c in calls if "start" in c and "is-active" not in c]
    assert len(started) == 2
    assert host._daemon_autostart_attempts == 2


def test_falha_silenciosa_em_timeout(
    host: _Host,
    sync_executor: _SyncExecutor,
    monkeypatch: pytest.MonkeyPatch,
    _popen_hermetico: type[_FakePopen],
) -> None:
    """TimeoutExpired em `start` não propaga; contador ainda incrementa."""
    monkeypatch.setattr(
        da.ServiceInstaller, "detect_installed_unit", lambda self: "hefesto-dualsense4unix"
    )
    _calls, fake_run = _fake_run_factory(
        is_active_stdout="inactive\n",
        raise_on_start=subprocess.TimeoutExpired(cmd="systemctl", timeout=5),
    )
    monkeypatch.setattr(da.subprocess, "run", fake_run)

    # Não deve levantar
    host.ensure_daemon_running()

    assert host._daemon_autostart_attempts == 1
    # O timeout do systemctl cai no fallback de Popen — que TEM de ser o fake
    # (1 spawn registrado, nenhum processo real na máquina).
    assert len(_popen_hermetico.spawned) == 1


def test_submete_ao_executor(
    host: _Host,
    sync_executor: _SyncExecutor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirma que o helper usa `_get_executor().submit(...)`."""
    monkeypatch.setattr(
        da.ServiceInstaller, "detect_installed_unit", lambda self: None
    )
    _, fake_run = _fake_run_factory(is_active_stdout="")
    monkeypatch.setattr(da.subprocess, "run", fake_run)

    host.ensure_daemon_running()

    assert len(sync_executor.submitted) == 1
