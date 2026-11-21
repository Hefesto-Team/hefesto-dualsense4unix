"""Migração de caminhos XDG legados (curto → longo)."""
from __future__ import annotations

import shutil
from pathlib import Path

from filelock import FileLock
from platformdirs import PlatformDirs

from hefesto_dualsense4unix.utils import xdg_paths
from hefesto_dualsense4unix.utils.escrita_inteira import escrever_inteiro
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.memoria_dos_controles import CASA, CLASSIFICACAO, CONTROLES

logger = get_logger(__name__)

_LEGACY = PlatformDirs("hefesto")

APP_ID = "io.github.hefesto_team.hefesto_dualsense4unix"
APP_ID_ANTIGO = "br.andrefarias.Hefesto"

MARCA = ".caminhos_de_antes_migrados"

NOMES_DE_QUEM_USA = frozenset(
    Path(nome).name for nome, (classe, _) in CLASSIFICACAO.items() if classe in (CONTROLES, CASA)
)


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
    """O nome é um que o produto grava e que é de quem usa, pela `CLASSIFICACAO` da memória.

    O que o install refaz fica de fora; na pasta `profiles`, só o perfil `.json`.
    """
    if rel.parts[0] == "profiles":
        return rel.suffix == ".json"
    return rel.parts[0] in NOMES_DE_QUEM_USA


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
    """Copia a configuração e os dados do layout curto legado e do sandbox antigo, uma vez só.

    A marca `.caminhos_de_antes_migrados` na configuração atual diz que a cópia já
    aconteceu, inclusive quando não havia nada a copiar: o perfil apagado depois não
    volta, e a bandeira desligada continua desligada. Só os nomes do produto viajam.
    """
    results: dict[str, list[str]] = {}
    alvo_config = xdg_paths.config_dir()
    alvo_data = xdg_paths.data_dir()
    marca = alvo_config / MARCA
    if marca.exists():
        return results
    candidatos: tuple[tuple[str, Path | None, Path], ...] = (
        ("config", Path(_LEGACY.user_config_dir), alvo_config),
        ("data", Path(_LEGACY.user_data_dir), alvo_data),
        ("config_app_id_antigo", _raiz_do_sandbox_antigo(alvo_config), alvo_config),
        ("data_app_id_antigo", _raiz_do_sandbox_antigo(alvo_data), alvo_data),
    )
    try:
        alvo_config.mkdir(parents=True, exist_ok=True)
        with FileLock(str(marca) + ".lock"):
            if marca.exists():
                return results
            for name, legacy, alvo in candidatos:
                if legacy is None or not legacy.is_dir():
                    continue
                if legacy.resolve() == alvo.resolve():
                    continue
                copied = _copy_missing(legacy, alvo)
                if copied:
                    results[name] = copied
                    logger.info(
                        "legacy_paths_migrated",
                        area=name,
                        src=str(legacy),
                        dst=str(alvo),
                        count=len(copied),
                    )
            escrever_inteiro(marca, "feita\n")
    except OSError as exc:  # pragma: no cover
        logger.warning("legacy_paths_migrate_failed", error=str(exc))
    return results


__all__ = ["APP_ID", "APP_ID_ANTIGO", "migrate_legacy_paths"]
