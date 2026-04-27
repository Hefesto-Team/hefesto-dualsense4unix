"""Utilitários para ler e escrever preferências da GUI em JSON.

Arquivo de estado: ~/.config/hefesto-dualsense4unix/gui_preferences.json
Tolerante a ausência do arquivo (retorna defaults).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_CONFIG_DIR = Path("~/.config/hefesto").expanduser()
_PREFS_FILE = _CONFIG_DIR / "gui_preferences.json"

_DEFAULTS: dict[str, Any] = {
    "advanced_editor": False,
}


def load_gui_prefs() -> dict[str, Any]:
    """Carrega preferências da GUI.

    Retorna dict com defaults se o arquivo não existir ou estiver corrompido.
    """
    if not _PREFS_FILE.exists():
        return dict(_DEFAULTS)
    try:
        raw = _PREFS_FILE.read_text(encoding="utf-8")
        data: dict[str, Any] = json.loads(raw)
        prefs = dict(_DEFAULTS)
        prefs.update(data)
        return prefs
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("gui_prefs: falha ao carregar preferencias, usando defaults", erro=str(exc))
        return dict(_DEFAULTS)


def save_gui_prefs(prefs: dict[str, Any]) -> None:
    """Persiste preferências da GUI em disco.

    Cria o diretório pai se necessário. Falha silenciosa com log de aviso.
    """
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _PREFS_FILE.write_text(
            json.dumps(prefs, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("gui_prefs: falha ao salvar preferencias", erro=str(exc))


def set_pref(key: str, value: Any) -> None:
    """Atalho: carrega, atualiza uma chave e salva."""
    prefs = load_gui_prefs()
    prefs[key] = value
    save_gui_prefs(prefs)
