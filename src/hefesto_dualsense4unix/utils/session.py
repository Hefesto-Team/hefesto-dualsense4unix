"""Persistência de sessão — salva e carrega o último perfil ativo do usuário.

O arquivo `~/.config/hefesto-dualsense4unix/session.json` guarda apenas o nome do
último perfil explicitamente ativado. O daemon lê esse arquivo no
startup e re-ativa o perfil automaticamente.

Nunca propaga exceção: falha silenciosa em ambos os sentidos.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import config_dir

logger = get_logger(__name__)

_SESSION_FILE = "session.json"
_PROFILE_KEY = "last_profile"


def _session_path() -> Path:
    return config_dir(ensure=True) / _SESSION_FILE


def save_last_profile(name: str) -> None:
    """Persiste o nome do último perfil ativado em session.json."""
    path = _session_path()
    try:
        data = json.dumps({_PROFILE_KEY: name}, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".session_")
        try:
            os.write(fd, data.encode())
        finally:
            os.close(fd)
        os.replace(tmp, path)
        logger.debug("session_saved", last_profile=name)
    except Exception as exc:
        logger.debug("session_save_failed", err=str(exc))


def load_last_profile() -> str | None:
    """Retorna o nome do último perfil salvo, ou None se não houver."""
    path = _session_path()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        name = data.get(_PROFILE_KEY)
        if isinstance(name, str) and name.strip():
            logger.debug("session_loaded", last_profile=name)
            return name.strip()
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    except Exception as exc:
        logger.debug("session_load_failed", err=str(exc))
    return None


__all__ = ["load_last_profile", "save_last_profile"]
