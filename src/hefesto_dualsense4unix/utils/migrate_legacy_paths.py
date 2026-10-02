"""Migração de caminhos XDG legados (curto → longo)."""
from __future__ import annotations

import shutil
from pathlib import Path

from platformdirs import PlatformDirs

from hefesto_dualsense4unix.utils import xdg_paths
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_LEGACY = PlatformDirs("hefesto")

APP_ID = "io.github.hefesto_team.hefesto_dualsense4unix"
APP_ID_ANTIGO = "br.andrefarias.Hefesto"


def _raiz_do_sandbox_antigo(atual: Path) -> Path | None:
    """Traduz um caminho do sandbox NOVO para o mesmo lugar no sandbox ANTIGO."""
    partes = atual.parts
    if APP_ID not in partes:
        return None
    i = partes.index(APP_ID)
    if i == 0 or partes[i - 1] != "app":
        return None
    return Path(*partes[:i], APP_ID_ANTIGO, *partes[i + 1 :])


def _copy_missing(src_root: Path, dst_root: Path) -> list[str]:
    """Copia recursivamente de `src_root` para `dst_root` só os arquivos ausentes."""
    if not src_root.is_dir():
        return []
    copied: list[str] = []
    for src in sorted(src_root.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(src_root)
        dst = dst_root / rel
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(str(rel))
    return copied


def migrate_legacy_paths() -> dict[str, list[str]]:
    """Copia config/data do layout curto legado para o longo atual."""
    results: dict[str, list[str]] = {}
    alvo_config = xdg_paths.config_dir()
    alvo_data = xdg_paths.data_dir()
    candidatos: tuple[tuple[str, Path | None, Path], ...] = (
        ("config", Path(_LEGACY.user_config_dir), alvo_config),
        ("data", Path(_LEGACY.user_data_dir), alvo_data),
        ("config_app_id_antigo", _raiz_do_sandbox_antigo(alvo_config), alvo_config),
        ("data_app_id_antigo", _raiz_do_sandbox_antigo(alvo_data), alvo_data),
    )
    pairs = tuple((n, o, d) for n, o, d in candidatos if o is not None)
    for name, legacy, target in pairs:
        try:
            if not legacy.is_dir() or legacy.resolve() == target.resolve():
                continue
            copied = _copy_missing(legacy, target)
            if copied:
                results[name] = copied
                logger.info(
                    "legacy_paths_migrated",
                    area=name,
                    src=str(legacy),
                    dst=str(target),
                    count=len(copied),
                )
        except OSError as exc:  # pragma: no cover - defensivo
            logger.warning("legacy_paths_migrate_failed", area=name, error=str(exc))
    return results


__all__ = ["APP_ID", "APP_ID_ANTIGO", "migrate_legacy_paths"]
