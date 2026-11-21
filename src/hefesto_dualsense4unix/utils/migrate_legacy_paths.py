"""Migração de caminhos XDG legados (curto → longo)."""
from __future__ import annotations

import shutil
from pathlib import Path

from filelock import FileLock
from platformdirs import PlatformDirs

from hefesto_dualsense4unix.utils import xdg_paths
from hefesto_dualsense4unix.utils.escrita_inteira import escrever_inteiro
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_LEGACY = PlatformDirs("hefesto")

APP_ID = "io.github.hefesto_team.hefesto_dualsense4unix"
APP_ID_ANTIGO = "br.andrefarias.Hefesto"

MARCA = ".caminhos_de_antes_migrados"
ARQUIVOS_DA_CONFIG = frozenset({"session.json", "maquina.json"})


def _raiz_do_sandbox_antigo(atual: Path) -> Path | None:
    """Traduz um caminho do sandbox NOVO para o mesmo lugar no sandbox ANTIGO."""
    partes = atual.parts
    if APP_ID not in partes:
        return None
    i = partes.index(APP_ID)
    if i == 0 or partes[i - 1] != "app":
        return None
    return Path(*partes[:i], APP_ID_ANTIGO, *partes[i + 1 :])


def _e_do_produto(rel: Path) -> bool:
    """O nome é um dos que o produto grava na configuração: perfil, sessão, bandeira, máquina."""
    partes = rel.parts
    if len(partes) == 2:
        return partes[0] == "profiles" and partes[1].endswith(".json")
    if len(partes) != 1:
        return False
    nome = partes[0]
    return nome in ARQUIVOS_DA_CONFIG or nome.endswith(".flag")


def _copy_missing(src_root: Path, dst_root: Path) -> list[str]:
    """Copia de `src_root` para `dst_root` só os arquivos do produto que ainda faltam."""
    if not src_root.is_dir():
        return []
    copied: list[str] = []
    for src in sorted(src_root.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(src_root)
        dst = dst_root / rel
        if dst.exists() or not _e_do_produto(rel):
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(str(rel))
    return copied


def migrate_legacy_paths() -> dict[str, list[str]]:
    """Copia a configuração do layout curto legado para o longo atual, uma vez só.

    A marca `.caminhos_de_antes_migrados` na configuração atual diz que a cópia já
    aconteceu, inclusive quando não havia nada a copiar: o perfil apagado depois não
    volta, e a bandeira desligada continua desligada. Só os nomes do produto viajam.
    """
    results: dict[str, list[str]] = {}
    alvo_config = xdg_paths.config_dir()
    marca = alvo_config / MARCA
    if marca.exists():
        return results
    candidatos: tuple[tuple[str, Path | None], ...] = (
        ("config", Path(_LEGACY.user_config_dir)),
        ("config_app_id_antigo", _raiz_do_sandbox_antigo(alvo_config)),
    )
    try:
        alvo_config.mkdir(parents=True, exist_ok=True)
        with FileLock(str(marca) + ".lock"):
            if marca.exists():
                return results
            for name, legacy in candidatos:
                if legacy is None or not legacy.is_dir():
                    continue
                if legacy.resolve() == alvo_config.resolve():
                    continue
                copied = _copy_missing(legacy, alvo_config)
                if copied:
                    results[name] = copied
                    logger.info(
                        "legacy_paths_migrated",
                        area=name,
                        src=str(legacy),
                        dst=str(alvo_config),
                        count=len(copied),
                    )
            escrever_inteiro(marca, "feita\n")
    except OSError as exc:  # pragma: no cover
        logger.warning("legacy_paths_migrate_failed", error=str(exc))
    return results


__all__ = ["APP_ID", "APP_ID_ANTIGO", "migrate_legacy_paths"]
