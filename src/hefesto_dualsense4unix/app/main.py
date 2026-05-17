"""Entry point da GUI Hefesto - Dualsense4Unix (GTK3)."""
from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING

from hefesto_dualsense4unix.app.app import HefestoApp
from hefesto_dualsense4unix.utils.i18n import init_locale
from hefesto_dualsense4unix.utils.logging_config import configure_logging, get_logger

if TYPE_CHECKING:
    import structlog


def _is_systemd_managed(pid: int) -> bool:
    """Retorna True se o processo é child do systemd user (PID 1 user-instance)
    ou do systemd init (PID 1). Não mexer em daemons systemd-managed para
    evitar StartLimitBurst-hit + auto-restart loops.
    """
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("PPid:"):
                    ppid = int(line.split()[1])
                    break
            else:
                return False
        # PPid=1 é systemd init OR user systemd. Suficiente para "não tocar".
        if ppid == 1:
            return True
        # systemd user instance (--user) tem cmdline "/usr/lib/systemd/systemd --user"
        with open(f"/proc/{ppid}/cmdline") as f:
            cmd = f.read().replace("\0", " ")
        return "/usr/lib/systemd/systemd" in cmd or "systemd --user" in cmd
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError, ValueError):
        return False


def _kill_previous_instances(logger: structlog.stdlib.BoundLogger) -> None:
    """Mata processos GUI anteriores; preserva daemon managed por systemd.

    Cobre:
      - GUI antiga (python -m hefesto_dualsense4unix.app.main)
      - Daemon avulso (hefesto-dualsense4unix daemon start) — APENAS se NÃO
        managed por systemd. Daemons via systemctl ficam intactos para o
        Restart=on-failure não bater em StartLimitBurst.
      - Flatpak runtime do app (br.andrefarias.Hefesto)

    Pula próprio PID + PPID. Defesa anti-loop: daemons systemd-managed são
    detectados via /proc/<pid>/status PPid e preservados.
    """
    own_pid = os.getpid()
    own_ppid = os.getppid()

    patterns = [
        r"hefesto_dualsense4unix\.app\.main",
        r"hefesto-dualsense4unix-gui",
        r"br\.andrefarias\.Hefesto",
    ]
    # Daemon: pattern separado para checar systemd-managed antes de matar.
    daemon_pattern = r"hefesto-dualsense4unix daemon start"

    def _kill(pid: int, sig: int) -> None:
        if pid in (own_pid, own_ppid):
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, sig)

    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pat in patterns:
            try:
                out = subprocess.run(
                    ["pgrep", "-f", pat],
                    capture_output=True, text=True, timeout=2,
                ).stdout.strip()
                for pid_str in out.split("\n"):
                    if not pid_str.strip():
                        continue
                    try:
                        _kill(int(pid_str), sig)
                    except ValueError:
                        continue
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

        # Daemon: matar APENAS se não-systemd-managed.
        try:
            out = subprocess.run(
                ["pgrep", "-f", daemon_pattern],
                capture_output=True, text=True, timeout=2,
            ).stdout.strip()
            for pid_str in out.split("\n"):
                if not pid_str.strip():
                    continue
                try:
                    pid = int(pid_str)
                except ValueError:
                    continue
                if _is_systemd_managed(pid):
                    logger.debug("daemon_systemd_managed_preservado", pid=pid)
                    continue
                _kill(pid, sig)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        if sig == signal.SIGTERM:
            time.sleep(0.5)

    logger.info("previous_instances_killed", own_pid=own_pid)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    logger = get_logger(__name__)
    _unused_argv = argv

    # FEAT-I18N-INFRASTRUCTURE-01 (v3.4.0): inicializa locale ANTES de
    # qualquer Gtk.Builder ou widget, garantindo que set_translation_domain
    # consiga resolver labels traduzíveis do Glade no boot.
    init_locale()

    # Garantia de instância única absoluta — mata qualquer processo antigo do
    # Hefesto - Dualsense4Unix antes de subir. Evita estado inconsistente, socket
    # órfão, pid file zumbi.
    _kill_previous_instances(logger)

    try:
        app = HefestoApp()
    except Exception as exc:
        logger.error("hefesto_app_init_failed", err=str(exc))
        print(f"Falha ao iniciar GUI Hefesto - Dualsense4Unix: {exc}", file=sys.stderr)
        return 1

    logger.info("hefesto_app_starting")
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
