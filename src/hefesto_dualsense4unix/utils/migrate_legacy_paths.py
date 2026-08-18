"""Migração de caminhos XDG legados (curto → longo).

Versões pré-rename (`Hefesto`, commits 7f4687a..08e92b8, 2026-04-25) usavam
`PlatformDirs("hefesto")` → `~/.config/hefesto`, `~/.local/share/hefesto`. O
código atual usa `PlatformDirs("hefesto-dualsense4unix")` (ver `xdg_paths.py`).
Sem migração, perfis, sessão e preferências criados na versão antiga ficam
órfãos no caminho curto e "somem" da GUI/daemon após uma reinstalação.

Esta migração é **idempotente** e **não-destrutiva**: copia, arquivo por
arquivo, apenas o que ainda não existe no destino longo, e **mantém** o
diretório curto intacto (ele serve de backup natural). Roda no boot do daemon
e da GUI (e pode ser chamada pelo `install.sh`), cobrindo todas as formas de
instalação sem reimplementar a lógica.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from platformdirs import PlatformDirs

from hefesto_dualsense4unix.utils import xdg_paths
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# Layout antigo, anterior ao rename para o nome longo.
_LEGACY = PlatformDirs("hefesto")


def _copy_missing(src_root: Path, dst_root: Path) -> list[str]:
    """Copia recursivamente de `src_root` para `dst_root` só os arquivos ausentes.

    Retorna os caminhos relativos copiados. Nunca sobrescreve um arquivo que já
    exista no destino — preserva o que o usuário tem no layout atual.
    """
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
    """Copia config/data do layout curto legado para o longo atual.

    Idempotente: nas execuções seguintes não há nada a copiar. Tolera erros
    (loga e segue) — nunca deve derrubar o boot do daemon ou da GUI.
    """
    results: dict[str, list[str]] = {}
    pairs: tuple[tuple[str, Path, Path], ...] = (
        ("config", Path(_LEGACY.user_config_dir), xdg_paths.config_dir()),
        ("data", Path(_LEGACY.user_data_dir), xdg_paths.data_dir()),
    )
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


__all__ = ["migrate_legacy_paths"]
