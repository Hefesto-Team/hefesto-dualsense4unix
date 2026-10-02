"""Internacionalização (i18n) via gettext padrão freedesktop."""
from __future__ import annotations

import gettext
import locale
import os
from pathlib import Path

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TEXTDOMAIN = "hefesto-dualsense4unix"

_initialized = False


def _candidate_locale_dirs() -> list[Path]:
    """Lista paths onde procurar catálogos `.mo`, em ordem de preferência."""
    candidates: list[Path] = []

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        candidates.append(Path(xdg_data_home) / "locale")

    candidates.append(Path.home() / ".local" / "share" / "locale")

    candidates.append(Path("/usr/share/locale"))

    candidates.append(Path("/app/share/hefesto-dualsense4unix/locale"))

    candidates.append(Path("/app/share/locale"))

    pkg_locale = Path(__file__).resolve().parent.parent / "locale"
    candidates.append(pkg_locale)

    return candidates


def _find_locale_dir() -> Path | None:
    """Retorna o primeiro path que contém pelo menos 1 `.mo` do projeto."""
    for path in _candidate_locale_dirs():
        if not path.is_dir():
            continue
        for lang_dir in path.iterdir():
            mo = lang_dir / "LC_MESSAGES" / f"{TEXTDOMAIN}.mo"
            if mo.is_file():
                return path
    return None


def init_locale() -> str | None:
    """Inicializa gettext + locale do sistema. Idempotente."""
    global _initialized
    if _initialized:
        return locale.getlocale(locale.LC_MESSAGES)[0]

    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error as exc:
        logger.debug("i18n_setlocale_falhou", err=str(exc))

    locale_dir = _find_locale_dir()
    if locale_dir is None:
        logger.debug(
            "i18n_no_catalog_found",
            candidates=[str(p) for p in _candidate_locale_dirs()],
            hint="Mantendo strings hardcoded PT-BR (fallback gettext).",
        )
        _initialized = True
        return None

    gettext.bindtextdomain(TEXTDOMAIN, str(locale_dir))
    gettext.textdomain(TEXTDOMAIN)


    active = locale.getlocale(locale.LC_MESSAGES)[0]
    logger.info(
        "i18n_initialized",
        locale=active or "C",
        locale_dir=str(locale_dir),
        domain=TEXTDOMAIN,
    )
    _initialized = True
    return active


def _(message: str) -> str:
    """Wrapper canônico para gettext."""
    if not _initialized:
        return message
    return gettext.gettext(message)


__all__ = ["TEXTDOMAIN", "_", "init_locale"]
