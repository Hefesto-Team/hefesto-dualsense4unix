"""Migração de caminhos XDG legados (curto → longo).

Versões pré-rename (`Hefesto`, commits 7f4687a..08e92b8, 2026-04-25) usavam
`PlatformDirs("hefesto")` → `~/.config/hefesto`, `~/.local/share/hefesto`. O
código atual usa `PlatformDirs("hefesto-dualsense4unix")` (ver `xdg_paths.py`).
Sem migração, perfis, sessão e preferências criados na versão antiga ficam
órfãos no caminho curto e "somem" da GUI/daemon após uma reinstalação.

E, desde a IDENTIDADE-01 (25/08/2026), há uma SEGUNDA origem, que não é
renomeação de pasta e sim troca de **app-id**: dentro do sandbox do Flatpak o
`XDG_CONFIG_HOME` é `~/.var/app/<app-id>/config`, então trocar
`br.andrefarias.Hefesto` por `io.github.hefesto_team.hefesto_dualsense4unix`
troca a pasta onde os perfis moram. O Flatpak **não migra id sozinho** — para
ele o id novo é outro aplicativo, instalado do lado —, então quem já usava
abriria a janela com a lista de perfis vazia. Ver `_raiz_do_sandbox_antigo`.

Esta migração é **idempotente** e **não-destrutiva**: copia, arquivo por
arquivo, apenas o que ainda não existe no destino, e **mantém** a origem
intacta (ela serve de backup natural). Roda no boot do daemon e da GUI (e pode
ser chamada pelo `install.sh`), cobrindo todas as formas de instalação sem
reimplementar a lógica.
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

#: O app-id de HOJE e o de ontem (IDENTIDADE-01, 25/08/2026). Os dois só
#: aparecem em caminho de sandbox do Flatpak: numa instalação nativa o
#: `~/.config/hefesto-dualsense4unix` não depende de app-id nenhum, e por isso
#: a tradução abaixo devolve `None` e nada acontece.
APP_ID = "io.github.hefesto_team.hefesto_dualsense4unix"
APP_ID_ANTIGO = "br.andrefarias.Hefesto"


def _raiz_do_sandbox_antigo(atual: Path) -> Path | None:
    """Traduz um caminho do sandbox NOVO para o mesmo lugar no sandbox ANTIGO.

    `~/.var/app/io.github.hefesto_team.hefesto_dualsense4unix/config/hefesto-dualsense4unix`
    vira
    `~/.var/app/br.andrefarias.Hefesto/config/hefesto-dualsense4unix`.

    Devolve `None` quando o caminho **não** é de sandbox — que é o caso de toda
    instalação nativa, do `.deb`, do Arch, do Fedora, do Nix e do AppImage. A
    âncora é o componente `app` imediatamente antes do id (`.var/app/<id>/`):
    sem ela, uma pasta qualquer chamada como o app-id seria confundida com o
    sandbox.

    Para o produto conseguir LER a pasta antiga de dentro do sandbox novo, o
    manifesto precisa da permissão correspondente — ela está em
    `flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml`, e é `:ro`
    porque aqui só se lê.
    """
    partes = atual.parts
    if APP_ID not in partes:
        return None
    i = partes.index(APP_ID)
    if i == 0 or partes[i - 1] != "app":
        return None
    return Path(*partes[:i], APP_ID_ANTIGO, *partes[i + 1 :])


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
    alvo_config = xdg_paths.config_dir()
    alvo_data = xdg_paths.data_dir()
    candidatos: tuple[tuple[str, Path | None, Path], ...] = (
        ("config", Path(_LEGACY.user_config_dir), alvo_config),
        ("data", Path(_LEGACY.user_data_dir), alvo_data),
        # IDENTIDADE-01 (25/08/2026): a pasta do app-id anterior, dentro do
        # sandbox. `None` fora do Flatpak, e aí a linha não existe.
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
