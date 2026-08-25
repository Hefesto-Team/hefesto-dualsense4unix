"""Utilitários para ler e escrever preferências da GUI em JSON.

Arquivo de estado: ~/.config/hefesto-dualsense4unix/gui_preferences.json
Tolerante a ausência do arquivo (retorna defaults).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.utils import xdg_paths
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# CHORE-CONFIG-MIGRATE-LEGACY-SHORT-PATH-01: usa o caminho XDG canônico
# (`~/.config/hefesto-dualsense4unix`) via `xdg_paths` — antes era hardcoded no
# caminho curto legado `~/.config/hefesto`, divergindo de perfis/sessão e
# deixando as preferências órfãs após reinstalar. A migração curto→longo
# (`utils.migrate_legacy_paths`) traz preferências antigas para cá.
_PREFS_NOME = "gui_preferences.json"


def _prefs_file() -> Path:
    """Caminho do arquivo de preferências, resolvido NA CHAMADA.

    LUZ-CEGA-01/E8 (25/08/2026) — era constante de módulo
    (``_CONFIG_DIR = xdg_paths.config_dir()``), e constante de módulo é
    avaliada na IMPORTAÇÃO. Sob a suíte isso vaza o ``$HOME`` REAL de quem
    roda: o ``tests/conftest.py`` isola ``XDG_CONFIG_HOME`` numa fixture de
    FUNÇÃO, que só corre DEPOIS da coleta — quando este módulo já congelou o
    caminho verdadeiro. Qualquer ``save_gui_prefs`` num teste escrevia em
    ``~/.config/hefesto-dualsense4unix/gui_preferences.json`` da máquina.

    É exatamente a classe de defeito que o CANARIO-FS-01 (05/08/2026)
    nomeia no próprio texto de reprovação — *"procure constante de módulo
    com Path.home() avaliada no import"* — e que aquele dia curou em
    ``storm_doctor._allowlist_path`` e ``EmulationActionsMixin._wp_dropin_dir``.
    Esta terceira passou. Em produção nada muda: ``config_dir()`` já resolve
    ``XDG_CONFIG_HOME`` a cada chamada.
    """
    return xdg_paths.config_dir() / _PREFS_NOME

_DEFAULTS: dict[str, Any] = {
    "advanced_editor": False,
    # `None` = ninguém corrigiu, e a detecção da sessão vale. Esta chave é o
    # que a aba Configurações grava quando a leitura de `XDG_CURRENT_DESKTOP`
    # erra — ver `app/ambiente.py`, que é o dono do valor e o único que o
    # valida. Ela mora AQUI e não em `maquina.json`: é preferência de janela,
    # e nada fora da janela a lê.
    "ambiente_corrigido": None,
}


def load_gui_prefs() -> dict[str, Any]:
    """Carrega preferências da GUI.

    Retorna dict com defaults se o arquivo não existir ou estiver corrompido.
    """
    prefs_file = _prefs_file()
    if not prefs_file.exists():
        return dict(_DEFAULTS)
    try:
        raw = prefs_file.read_text(encoding="utf-8")
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
        prefs_file = _prefs_file()
        prefs_file.parent.mkdir(parents=True, exist_ok=True)
        prefs_file.write_text(
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
