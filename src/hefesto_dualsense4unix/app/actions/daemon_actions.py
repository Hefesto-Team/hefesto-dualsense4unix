"""Aba Daemon: status systemd --user + controles.

SIMPLIFY-UNIT-01: unit única `hefesto-dualsense4unix.service`. Sem dropdown de seleção.
BUG-DAEMON-STATUS-MISMATCH-01: `_daemon_status()` cruza 3 fontes (systemd
  is-active, is-enabled, pid file) para apresentar label PT-BR fiel ao estado
  real. Evita mostrar "failed" quando o daemon está vivo fora do systemd.
"""
# ruff: noqa: E402
from __future__ import annotations

import os
import re
import signal
import subprocess
from typing import Any, Literal

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.ipc_bridge import _get_executor
from hefesto_dualsense4unix.daemon.service_install import SERVICE_NORMAL, ServiceInstaller
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# Tipo canônico para o estado do daemon (BUG-DAEMON-STATUS-MISMATCH-01).
DaemonStatus = Literal["online_systemd", "online_avulso", "iniciando", "offline"]


class DaemonActionsMixin(WidgetAccessMixin):
    """Controla a aba Daemon."""

    _daemon_autostart_guard: bool
    # Contador anti-loop de tentativas de autostart por sessão da GUI.
    # Máximo 2 tentativas: após a segunda falha, o helper vira no-op até
    # a próxima reabertura do processo (BUG-DAEMON-AUTOSTART-01).
    _daemon_autostart_attempts: int = 0

    def install_daemon_tab(self) -> None:
        self._daemon_autostart_guard = False
        # Inicializa contador anti-loop por instância (bootstrap da GUI).
        self._daemon_autostart_attempts = 0
        # BUG-GUI-DAEMON-STATUS-INITIAL-01: o refresh da view chama
        # `systemctl is-active/is-enabled/status` — cada um com timeout 5 s.
        # Em bootstrap, rodar síncrono bloquearia a thread GTK por até 15 s
        # em sistemas onde systemctl trava (ex.: usuário sem unit instalada
        # combinado com journal lento). Descarregamos em thread worker e
        # atualizamos a view via `GLib.idle_add` quando os dados chegam. O
        # label default do Glade ("—" neutro) mostra o estado "Consultando"
        # até o resultado pintar — em vez do falso-negativo "Offline".
        self._set_daemon_status_consulting()
        self._refresh_daemon_view_async()
        self._sync_restart_daemon_button_sensitivity()

    def _set_daemon_status_consulting(self) -> None:
        """Mostra o estado transitório "Consultando..." no label da aba Daemon.

        Usado no bootstrap da aba, antes do primeiro `_refresh_daemon_view_async`
        retornar. Evita falso-negativo "Offline" em cenário onde o daemon está
        ativo mas `systemctl` ainda não respondeu (BUG-GUI-DAEMON-STATUS-INITIAL-01).
        """
        label = self._get("daemon_status_label")
        if label is None:
            return
        label.set_markup('<span foreground="#888">● Consultando...</span>')
        label.set_tooltip_text(
            "Verificando estado do daemon via systemctl. Aguarde."
        )

    def _refresh_daemon_view_async(self) -> None:
        """Dispara `_refresh_daemon_view` em thread worker, sem bloquear o GTK.

        BUG-GUI-DAEMON-STATUS-INITIAL-01: a versão síncrona chama 3 subprocess
        `systemctl ...` com timeout 5 s cada. No bootstrap da GUI isso pode
        atrasar o primeiro frame visível — o usuário vê o label default antes
        do refresh terminar. Em thread worker, a UI renderiza imediatamente e
        o label é pintado quando `systemctl` retorna (tipicamente < 200 ms).
        """
        def _worker() -> None:
            try:
                status = self._daemon_status()
                enabled = self._systemctl_oneline(["is-enabled", SERVICE_NORMAL])
                text = self._systemctl_status_text(SERVICE_NORMAL)
            except Exception as exc:
                logger.warning("daemon_view_async_falhou", erro=str(exc))
                return
            GLib.idle_add(self._apply_daemon_view, status, enabled, text)

        _get_executor().submit(_worker)

    def _apply_daemon_view(
        self, status: DaemonStatus, enabled: str, text: str
    ) -> bool:
        """Aplica o resultado do refresh assíncrono na thread GTK.

        Espelha `_refresh_daemon_view` mas sem reexecutar subprocess — recebe
        os valores já consultados em thread worker. Retorna `False` para que
        `GLib.idle_add` não reagende.
        """
        self._set_daemon_status_markup(status, enabled)

        self._daemon_autostart_guard = True
        try:
            sw = self._get("daemon_autostart_switch")
            if sw is not None:
                sw.set_active(enabled == "enabled")
        finally:
            self._daemon_autostart_guard = False

        btn_migrate = self._get("btn_migrate_to_systemd")
        if btn_migrate is not None:
            btn_migrate.set_visible(status == "online_avulso")

        self._set_daemon_text(text)
        return False  # não repetir via GLib

    def ensure_daemon_running(self) -> None:
        """Garante daemon ativo no bootstrap da GUI (BUG-DAEMON-AUTOSTART-01).

        Executado em thread worker via `_get_executor()` — nunca bloqueia
        a thread GTK. Fluxo:

          1. Se `detect_installed_unit()` retorna `None`, no-op (usuário
             sem unit instalada, provavelmente nunca rodou `install.sh`).
          2. Se `systemctl --user is-active hefesto-dualsense4unix.service` já retorna
             `active`, no-op (daemon já está rodando).
          3. Caso contrário, dispara `systemctl --user start hefesto-dualsense4unix.service`
             com timeout de 5s. Falha silenciosa via `logger.warning`.

        Anti-loop: limite de 2 tentativas por sessão (`_daemon_autostart_attempts`).
        Após a segunda falha, o helper vira no-op até a próxima abertura
        do processo da GUI.
        """
        if self._daemon_autostart_attempts >= 2:
            return

        def _worker() -> None:
            try:
                installed = ServiceInstaller().detect_installed_unit()
            except Exception as exc:
                logger.warning("autostart_detect_falhou", erro=str(exc))
                return
            if installed is None:
                logger.debug("autostart_sem_unit_instalada")
                return

            active = self._is_service_active()
            if active == "active":
                logger.debug("autostart_daemon_ja_ativo")
                return

            # BUG-MULTI-INSTANCE-01: se o pid file do daemon aponta para um
            # processo vivo (ex.: daemon rodando fora do systemd via CLI),
            # não disparar systemctl start — evita spawn duplicado.
            if self._daemon_pid_alive():
                logger.debug("autostart_daemon_vivo_via_pid_file")
                return

            self._daemon_autostart_attempts += 1
            logger.info(
                "autostart_disparando",
                tentativa=self._daemon_autostart_attempts,
                estado_anterior=active,
            )
            rc = self._start_service_blocking()
            if rc == 0:
                logger.info("autostart_ok", unit=SERVICE_NORMAL)
            else:
                logger.warning(
                    "autostart_falhou",
                    unit=SERVICE_NORMAL,
                    rc=rc,
                    tentativa=self._daemon_autostart_attempts,
                )

        _get_executor().submit(_worker)

    def _daemon_pid_alive(self) -> bool:
        """Retorna True se o pid file do daemon aponta para processo vivo.

        Usado pelo `ensure_daemon_running` para não duplicar spawn quando
        o daemon foi lançado fora do systemd (BUG-MULTI-INSTANCE-01).
        """
        try:
            from hefesto_dualsense4unix.utils.single_instance import is_alive
            from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir
        except Exception:
            return False
        pid_file = runtime_dir() / "daemon.pid"
        try:
            raw = pid_file.read_text(encoding="ascii").strip()
        except (FileNotFoundError, OSError):
            return False
        if not raw.isdigit():
            return False
        return is_alive(int(raw))

    def _is_service_active(self) -> str:
        """Retorna saída de `systemctl --user is-active hefesto-dualsense4unix.service`.

        Retorna string vazia se systemctl indisponível.
        """
        result = self._invoke_systemctl(
            ["is-active", SERVICE_NORMAL], capture=True, check=False
        )
        if result is None:
            return ""
        return (result.stdout or "").strip()

    def _start_service_blocking(self) -> int:
        """Sobe o daemon. systemctl primeiro, fallback Popen em sandbox (Flatpak).

        Retorna 0 se subiu com sucesso (systemctl OK ou Popen vivo após probe),
        ou returncode != 0 / -1 em falha.

        Em ambiente Flatpak (FLATPAK_ID definido) ou quando systemctl
        retorna FileNotFoundError, o fallback usa subprocess.Popen do
        binário do app, mantendo o daemon como child do processo da GUI.
        Bloqueia — chamar apenas de thread worker.
        """
        import os
        import sys
        from pathlib import Path

        is_sandbox = bool(os.environ.get("FLATPAK_ID")) or not Path("/run/systemd/system").exists()

        if not is_sandbox:
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "start", SERVICE_NORMAL],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                if result.returncode == 0:
                    return 0
                logger.warning(
                    "systemctl_start_falhou_tentando_popen",
                    rc=result.returncode,
                    stderr=(result.stderr or "")[:200],
                )
            except (FileNotFoundError, subprocess.SubprocessError) as exc:
                logger.info("systemctl_indisponivel_usando_popen", erro=str(exc))

        # Fallback: spawn do daemon como child via Popen.
        # Slot self._daemon_popen é cleanado em _shutdown_backend.
        try:
            existing = getattr(self, "_daemon_popen", None)
            if existing is not None and existing.poll() is None:
                logger.debug("daemon_popen_ja_ativo", pid=existing.pid)
                return 0
            cmd = [sys.executable, "-m", "hefesto_dualsense4unix",
                   "daemon", "start", "--foreground"]
            popen = subprocess.Popen(  # noqa: S603
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._daemon_popen = popen
            logger.info("daemon_popen_iniciado", pid=popen.pid, sandbox=is_sandbox)
            # Probe rápido — daemon deve estar vivo após 500ms.
            import time
            time.sleep(0.5)
            if popen.poll() is None:
                return 0
            logger.warning("daemon_popen_morreu_no_boot", rc=popen.returncode)
            return popen.returncode if popen.returncode is not None else -1
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            logger.warning("daemon_popen_falhou", erro=str(exc))
            return -1

    def _sync_restart_daemon_button_sensitivity(self) -> None:
        """Habilita/desabilita o botão 'Reiniciar daemon' conforme unit presente.

        Se nenhum unit foi instalado, o botão vira cinza com tooltip guiando
        o usuário para `install.sh`. Idempotente e seguro em bootstrap.
        """
        btn = self._get("btn_restart_daemon")
        if btn is None:
            return
        installed = ServiceInstaller().detect_installed_unit()
        if installed:
            btn.set_sensitive(True)
            btn.set_tooltip_text(
                "Executa systemctl --user restart hefesto-dualsense4unix.service"
            )
        else:
            btn.set_sensitive(False)
            btn.set_tooltip_text(
                "serviço hefesto-dualsense4unix.service não instalado — rode install.sh"
            )

    # --- handlers ---

    def on_daemon_start(self, _btn: Gtk.Button) -> None:
        self._run_systemctl_async("start")

    def on_daemon_stop(self, _btn: Gtk.Button) -> None:
        self._run_systemctl_async("stop")

    def on_daemon_restart(self, _btn: Gtk.Button) -> None:
        self._run_systemctl_async("restart")

    def on_daemon_refresh(self, _btn: Gtk.Button) -> None:
        self._refresh_daemon_view()
        self._sync_restart_daemon_button_sensitivity()

    def on_daemon_service_restart(self, _btn: Gtk.Button) -> None:
        """Handler do botão 'Reiniciar daemon' (UX-RECONNECT-01).

        Executa `systemctl --user restart hefesto-dualsense4unix.service` com timeout=10s.
        Cobre ausência de systemd (FileNotFoundError) e falha do unit
        (CalledProcessError) exibindo MessageDialog informativo. Nunca
        usa shell=True.
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "restart", SERVICE_NORMAL],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except FileNotFoundError:
            logger.error("systemctl_missing", unit=SERVICE_NORMAL)
            self._show_restart_error(
                "systemctl não encontrado — sistema sem systemd --user."
            )
            return
        except subprocess.SubprocessError as exc:
            logger.error("systemctl_subprocess_error", err=str(exc))
            self._show_restart_error(f"Falha ao executar systemctl: {exc}")
            return

        if result.returncode != 0:
            stderr = (result.stderr or "").strip() or "(sem stderr)"
            logger.error(
                "daemon_restart_failed",
                unit=SERVICE_NORMAL,
                rc=result.returncode,
                stderr=stderr,
            )
            self._show_restart_error(
                f"systemctl restart {SERVICE_NORMAL} falhou "
                f"(rc={result.returncode}):\n{stderr}"
            )
            return

        logger.info("daemon_restart_ok", unit=SERVICE_NORMAL)
        self._toast_daemon(
            f"systemctl --user restart {SERVICE_NORMAL} → ok"
        )
        self._refresh_daemon_view()

    def _show_restart_error(self, message: str) -> None:
        window: Gtk.Window | None = getattr(self, "window", None)
        dialog = Gtk.MessageDialog(
            transient_for=window,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text="Não foi possível reiniciar o daemon",
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def on_daemon_view_logs(self, _btn: Gtk.Button) -> None:
        logs = self._journalctl_tail(SERVICE_NORMAL, lines=80)
        self._set_daemon_text(logs or "(sem saída)")

    def on_daemon_autostart_toggled(
        self, _switch: Gtk.Switch, state: bool
    ) -> bool:
        if self._daemon_autostart_guard:
            return False
        action = "enable" if state else "disable"
        self._run_systemctl_async(action)
        return False

    # --- handlers do botão "Migrar para systemd" ---

    def on_daemon_migrate_to_systemd(self, _btn: Gtk.Button) -> None:
        """Handler do botão 'Migrar para systemd' (BUG-DAEMON-STATUS-MISMATCH-01).

        Visível apenas quando o daemon está no estado `online_avulso`.
        Sequência:
          1. Lê pid do arquivo do daemon.
          2. Envia SIGTERM ao processo avulso (grace via single_instance).
          3. Dispara `systemctl --user start hefesto-dualsense4unix.service`.
          4. Atualiza a view.
        Executado em thread worker para não bloquear a thread GTK.
        """
        def _worker() -> None:
            pid = self._read_daemon_pid()
            if pid is not None:
                try:
                    from hefesto_dualsense4unix.utils.single_instance import is_alive
                    if is_alive(pid):
                        logger.info(
                            "daemon_migrate_sigterm",
                            pid=pid,
                        )
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except (ProcessLookupError, PermissionError) as exc:
                            logger.warning(
                                "daemon_migrate_sigterm_falhou",
                                pid=pid,
                                err=str(exc),
                            )
                except Exception as exc:
                    logger.warning("daemon_migrate_import_falhou", err=str(exc))

            rc = self._start_service_blocking()
            if rc == 0:
                logger.info("daemon_migrate_start_ok", unit=SERVICE_NORMAL)
            else:
                logger.warning(
                    "daemon_migrate_start_falhou",
                    unit=SERVICE_NORMAL,
                    rc=rc,
                )
            GLib.idle_add(self._on_migrate_done, rc)

        _get_executor().submit(_worker)

    def _on_migrate_done(self, rc: int) -> bool:
        """Callback pós-migração — executa na thread principal GTK."""
        if rc == 0:
            self._toast_daemon(
                "Daemon migrado para systemd com sucesso."
            )
        else:
            self._toast_daemon(
                f"Falha ao iniciar hefesto-dualsense4unix.service via systemd (rc={rc})."
            )
        self._refresh_daemon_view()
        return False

    # --- helpers ---

    def _read_daemon_pid(self) -> int | None:
        """Lê o PID do arquivo de pid do daemon; retorna None se ausente/inválido."""
        try:
            from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir
        except Exception:
            return None
        pid_file = runtime_dir() / "daemon.pid"
        try:
            raw = pid_file.read_text(encoding="ascii").strip()
        except (FileNotFoundError, OSError):
            return None
        if not raw.isdigit():
            return None
        pid = int(raw)
        return pid if pid > 0 else None

    def _daemon_status(self) -> DaemonStatus:
        """Determina o estado canônico do daemon cruzando 3 fontes.

        Fontes consultadas:
          1. `systemctl --user is-active hefesto-dualsense4unix.service` → systemd_active.
          2. `systemctl --user is-enabled hefesto-dualsense4unix.service` → systemd_enabled.
          3. `is_alive(pid)` via pid file → process_alive.

        Matriz de decisão (BUG-DAEMON-STATUS-MISMATCH-01):
          systemd active + process_alive + enabled  → online_systemd
          systemd active + process_alive            → online_systemd
          systemd inactive/failed + process_alive   → online_avulso
          systemd active + not process_alive        → iniciando
          systemd inactive/failed + not process_alive → offline
        """
        systemd_active = (
            self._systemctl_oneline(["is-active", SERVICE_NORMAL]) == "active"
        )
        pid = self._read_daemon_pid()
        process_alive: bool
        if pid is not None:
            try:
                from hefesto_dualsense4unix.utils.single_instance import is_alive
                process_alive = is_alive(pid)
            except Exception:
                process_alive = False
        else:
            process_alive = False

        if systemd_active and process_alive:
            return "online_systemd"
        if not systemd_active and process_alive:
            return "online_avulso"
        if systemd_active and not process_alive:
            return "iniciando"
        return "offline"

    def _refresh_daemon_view(self) -> None:
        """Atualiza a aba Daemon com base no estado canônico do daemon.

        Consulta `_daemon_status()` (3 fontes) e pinta o label com cor e
        tooltip PT-BR amigável. Também atualiza o switch auto-start e o
        botão "Migrar para systemd" (visível apenas em `online_avulso`).
        """
        status = self._daemon_status()
        enabled = self._systemctl_oneline(["is-enabled", SERVICE_NORMAL])
        self._set_daemon_status_markup(status, enabled)

        self._daemon_autostart_guard = True
        try:
            sw = self._get("daemon_autostart_switch")
            if sw is not None:
                sw.set_active(enabled == "enabled")
        finally:
            self._daemon_autostart_guard = False

        # Botão "Migrar para systemd" visível apenas em estado online_avulso.
        btn_migrate = self._get("btn_migrate_to_systemd")
        if btn_migrate is not None:
            btn_migrate.set_visible(status == "online_avulso")

        text = self._systemctl_status_text(SERVICE_NORMAL)
        self._set_daemon_text(text)

    def _run_systemctl_async(self, action: str) -> None:
        """Executa systemctl em thread worker para não bloquear a thread GTK."""
        unit = SERVICE_NORMAL

        def _worker() -> None:
            result = self._invoke_systemctl([action, unit], capture=True)
            rc = result.returncode if result is not None else -1
            GLib.idle_add(self._on_systemctl_done, action, unit, rc)

        _get_executor().submit(_worker)

    def _on_systemctl_done(self, action: str, unit: str, rc: int) -> bool:
        """Callback pós-systemctl — executa na thread principal GTK."""
        self._toast_daemon(f"systemctl {action} {unit} → rc={rc}")
        self._refresh_daemon_view()
        return False  # não repetir via GLib

    def _set_daemon_status_markup(
        self, status: DaemonStatus, enabled: str
    ) -> None:
        """Pinta o label de status com cor e tooltip PT-BR conforme estado canônico.

        Cores:
          verde (#2d8)  — online_systemd
          amarelo (#ca0) — online_avulso, iniciando
          vermelho (#d33) — offline
        """
        label = self._get("daemon_status_label")
        if label is None:
            return

        status_map: dict[DaemonStatus, tuple[str, str, str]] = {
            "online_systemd": (
                "#2d8",
                "● Online (systemd + auto-start)"
                if enabled == "enabled"
                else "● Online (gerenciado pelo systemd)",
                "Daemon em execução sob controle do systemd. "
                "Reinício automático habilitado caso o processo falhe.",
            ),
            "online_avulso": (
                "#ca0",
                "● Online (processo avulso, sem systemd)",
                "Daemon em execução fora do systemd. "
                "Não há reinício automático. "
                "Use 'Migrar para systemd' para ativar gerenciamento completo.",
            ),
            "iniciando": (
                "#ca0",
                "● Iniciando...",
                "systemd reporta unit ativa mas o processo ainda não escreveu "
                "o pid file. Aguarde alguns segundos.",
            ),
            "offline": (
                "#d33",
                "○ Offline",
                "Daemon não está em execução. "
                "Use 'Iniciar' para subir via systemd ou "
                "'hefesto-dualsense4unix daemon start' na linha de comando.",
            ),
        }
        color, text, tooltip = status_map[status]
        label.set_markup(f'<span foreground="{color}">{text}</span>')
        label.set_tooltip_text(tooltip)

    def _set_daemon_text(self, text: str) -> None:
        view: Gtk.TextView = self._get("daemon_status_text")
        buf: Gtk.TextBuffer = view.get_buffer()
        text = re.sub(r"\x1b\[[0-9;]*m", "", text)
        buf.set_text(text)
        end_iter = buf.get_end_iter()
        mark = buf.create_mark(None, end_iter, False)
        view.scroll_to_mark(mark, 0.0, False, 0.0, 0.0)
        buf.delete_mark(mark)

    def _systemctl_oneline(self, args: list[str]) -> str:
        result = self._invoke_systemctl(args, capture=True, check=False)
        if result is None:
            return ""
        return (result.stdout or "").strip().splitlines()[:1][0] if result.stdout.strip() else ""

    def _systemctl_status_text(self, unit: str) -> str:
        result = self._invoke_systemctl(
            ["status", unit, "--no-pager"], capture=True, check=False
        )
        if result is None:
            return "(systemctl indisponível)"
        return (result.stdout or "") + (result.stderr or "")

    def _journalctl_tail(self, unit: str, lines: int = 80) -> str:
        try:
            result = subprocess.run(
                [
                    "journalctl",
                    "--user",
                    "-u",
                    unit,
                    "-n",
                    str(lines),
                    "--no-pager",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            return f"journalctl indisponível: {exc}"
        return (result.stdout or "") + (result.stderr or "")

    def _invoke_systemctl(
        self,
        args: list[str],
        *,
        capture: bool = False,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                ["systemctl", "--user", *args],
                capture_output=capture,
                text=True,
                check=check,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return None

    def _toast_daemon(self, msg: str) -> None:
        bar: Any = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id("daemon")
        bar.push(ctx_id, msg)
