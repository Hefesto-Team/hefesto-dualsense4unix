"""Entry point da GUI Hefesto - Dualsense4Unix (GTK3)."""
from __future__ import annotations

import sys

from hefesto_dualsense4unix.app.app import HefestoApp
from hefesto_dualsense4unix.utils.logging_config import configure_logging, get_logger


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    logger = get_logger(__name__)
    _ = argv

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
