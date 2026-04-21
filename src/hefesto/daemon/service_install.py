"""Instalação e gestão das unidades systemd --user.

Respeita a decisão V2-12 (Conflicts= mútuo entre `hefesto.service` e
`hefesto-headless.service`). Ao habilitar uma, desabilita a outra.

Path canônico: `~/.config/systemd/user/`. Para descobrir os `.service`
originais, lemos o diretório `assets/` do repo (desenvolvimento) ou
`/usr/share/hefesto/assets/` (pacote instalado). Em modo de desenvolvimento,
descobrimos via `importlib.resources` se empacotado como wheel.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)

SERVICE_NORMAL = "hefesto.service"
SERVICE_HEADLESS = "hefesto-headless.service"


def user_unit_dir() -> Path:
    """`~/.config/systemd/user/` (cria se não existe)."""
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    target = base / "systemd" / "user"
    target.mkdir(parents=True, exist_ok=True)
    return target


def find_assets_dir() -> Path:
    """Localiza `assets/` contendo as unidades `.service`.

    Ordem:
      1. `HEFESTO_ASSETS_DIR` env (sobrescreve tudo, útil pra testes).
      2. Repo layout: `<source>/assets/` relativo ao módulo.
      3. `/usr/share/hefesto/assets/` (pacote instalado).
    """
    override = os.environ.get("HEFESTO_ASSETS_DIR")
    if override:
        return Path(override)

    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidate = ancestor / "assets"
        if (candidate / SERVICE_NORMAL).exists():
            return candidate

    system_path = Path("/usr/share/hefesto/assets")
    if (system_path / SERVICE_NORMAL).exists():
        return system_path

    raise FileNotFoundError("assets/ nao encontrado (nem via HEFESTO_ASSETS_DIR)")


@dataclass
class ServiceInstaller:
    """Instala/remove unidades e coordena mutual exclusion."""

    dry_run: bool = False

    def install(self, *, headless: bool) -> Path:
        assets = find_assets_dir()
        target_name = SERVICE_HEADLESS if headless else SERVICE_NORMAL
        opposite_name = SERVICE_NORMAL if headless else SERVICE_HEADLESS

        src = assets / target_name
        if not src.exists():
            raise FileNotFoundError(f"unit source nao existe: {src}")

        dst = user_unit_dir() / target_name
        if not self.dry_run:
            shutil.copy2(src, dst)
        logger.info("service_copied", src=str(src), dst=str(dst))

        self._systemctl("daemon-reload")
        self._disable_if_installed(opposite_name)
        self._systemctl("enable", target_name)

        return dst

    def uninstall(self) -> list[Path]:
        removed: list[Path] = []
        for name in (SERVICE_NORMAL, SERVICE_HEADLESS):
            self._disable_if_installed(name)
            dst = user_unit_dir() / name
            if dst.exists():
                if not self.dry_run:
                    dst.unlink()
                removed.append(dst)
        self._systemctl("daemon-reload")
        return removed

    def start(self, *, headless: bool) -> None:
        name = SERVICE_HEADLESS if headless else SERVICE_NORMAL
        self._systemctl("start", name)

    def stop(self, *, headless: bool) -> None:
        name = SERVICE_HEADLESS if headless else SERVICE_NORMAL
        self._systemctl("stop", name)

    def restart(self, *, headless: bool) -> None:
        name = SERVICE_HEADLESS if headless else SERVICE_NORMAL
        self._systemctl("restart", name)

    def status_text(self, *, headless: bool) -> str:
        name = SERVICE_HEADLESS if headless else SERVICE_NORMAL
        result = self._systemctl("status", name, capture=True, check=False)
        return result.stdout if result is not None else ""

    def detect_installed_units(self) -> list[str]:
        """Retorna nomes das units (.service) presentes em `user_unit_dir()`."""
        base = user_unit_dir()
        return [n for n in (SERVICE_NORMAL, SERVICE_HEADLESS) if (base / n).exists()]

    def _disable_if_installed(self, name: str) -> None:
        if (user_unit_dir() / name).exists():
            self._systemctl("disable", name, check=False)

    def _systemctl(
        self,
        *args: str,
        capture: bool = False,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str] | None:
        cmd = ["systemctl", "--user", *args]
        logger.debug("systemctl_call", cmd=cmd, dry_run=self.dry_run)
        if self.dry_run:
            return None
        try:
            return subprocess.run(
                cmd,
                check=check,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "systemctl nao encontrado — distro sem systemd (ver ADR-009)"
            ) from exc


__all__ = [
    "SERVICE_HEADLESS",
    "SERVICE_NORMAL",
    "ServiceInstaller",
    "find_assets_dir",
    "user_unit_dir",
]
