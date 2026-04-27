"""Entry point da GUI Hefesto - Dualsense4Unix (GTK3)."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

from hefesto_dualsense4unix.app.app import HefestoApp
from hefesto_dualsense4unix.utils.logging_config import configure_logging, get_logger


def _kill_previous_instances(logger) -> None:
    """Mata QUALQUER processo Hefesto - Dualsense4Unix anterior antes de subir.

    Cobre:
      - GUI antiga (python -m hefesto_dualsense4unix.app.main)
      - Daemon avulso (hefesto-dualsense4unix daemon start)
      - Daemon via Popen interno do GUI anterior
      - Flatpak runtime do app (br.andrefarias.Hefesto)

    Garante isolamento absoluto: a nova instância sempre começa do zero, sem
    socket/pid file órfão de execução anterior. Pula o próprio PID via
    os.getpid() para não suicídio em pkill recursivo.
    """
    own_pid = os.getpid()
    own_ppid = os.getppid()

    patterns = [
        r"hefesto_dualsense4unix\.app\.main",
        r"hefesto-dualsense4unix daemon start",
        r"hefesto-dualsense4unix-gui",
        r"br\.andrefarias\.Hefesto",
    ]

    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pat in patterns:
            try:
                # pgrep retorna PIDs uma por linha; filtramos os nossos.
                out = subprocess.run(
                    ["pgrep", "-f", pat],
                    capture_output=True,
                    text=True,
                    timeout=2,
                ).stdout.strip()
                for pid_str in out.split("\n"):
                    if not pid_str.strip():
                        continue
                    try:
                        pid = int(pid_str)
                    except ValueError:
                        continue
                    if pid in (own_pid, own_ppid):
                        continue
                    try:
                        os.kill(pid, sig)
                    except (ProcessLookupError, PermissionError):
                        continue
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        if sig == signal.SIGTERM:
            time.sleep(0.5)

    logger.info("previous_instances_killed", own_pid=own_pid)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    logger = get_logger(__name__)
    _ = argv

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
