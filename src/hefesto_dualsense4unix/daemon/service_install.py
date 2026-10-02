"""Instalação e gestão da unidade systemd --user `hefesto-dualsense4unix.service`.

Unidade única (SIMPLIFY-UNIT-01). A dualidade histórica normal/headless foi
eliminada porque o Hefesto - DualSense4Unix é inerentemente um daemon desktop com DualSense.

Path canônico: `~/.config/systemd/user/`. Para descobrir o `.service`
original, lemos o diretório `assets/` do repo (desenvolvimento) ou
`/usr/share/hefesto-dualsense4unix/assets/` (pacote instalado).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from hefesto_dualsense4unix.utils import identidade
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

SERVICE_NORMAL = identidade.atual().unit_daemon

SYSTEM_UNIT_DIRS: list[Path] = [
    Path("/usr/lib/systemd/user"),
    Path("/etc/systemd/user"),
]


def user_unit_dir() -> Path:
    """`~/.config/systemd/user/` — só RESPONDE o caminho."""
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "systemd" / "user"


_SEM_SYSTEMD_DE_USUARIO = (
    "hefesto-dualsense4unix.service não instalada.\n"
    "Para instalar via systemd --user:\n"
    "  hefesto-dualsense4unix daemon install-service\n"
    "Para iniciar em foreground sem systemd:\n"
    "  hefesto-dualsense4unix daemon start --foreground"
)


def _systemctl_de_usuario_disponivel() -> bool:
    """``systemctl`` existe no ``PATH`` E responde por uma instância de usuário?"""
    if shutil.which("systemctl") is None:
        return False
    try:
        resultado = subprocess.run(
            ["systemctl", "--user", "is-system-running"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return bool(resultado.stdout.strip())


def find_assets_dir() -> Path:
    """Localiza `assets/` contendo a unidade `.service`."""
    override = os.environ.get("HEFESTO_DUALSENSE4UNIX_ASSETS_DIR")
    if override:
        return Path(override)

    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidate = ancestor / "assets"
        if (candidate / SERVICE_NORMAL).exists():
            return candidate

    system_path = Path("/usr/share/hefesto-dualsense4unix/assets")
    if (system_path / SERVICE_NORMAL).exists():
        return system_path

    raise FileNotFoundError("assets/ não encontrado (nem via HEFESTO_DUALSENSE4UNIX_ASSETS_DIR)")


@dataclass
class ServiceInstaller:
    """Instala/remove a unidade `hefesto-dualsense4unix.service`."""

    dry_run: bool = False

    def install(self, *, enable: bool = False) -> Path:
        """Copia a unit para o diretório do usuário."""
        assets = find_assets_dir()
        src = assets / SERVICE_NORMAL
        if not src.exists():
            raise FileNotFoundError(f"unit source não existe: {src}")

        unit_dir = user_unit_dir()
        dst = unit_dir / SERVICE_NORMAL
        if not self.dry_run:
            unit_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        logger.info("service_copied", src=str(src), dst=str(dst))

        self._systemctl("daemon-reload")
        if enable:
            self._systemctl("enable", SERVICE_NORMAL)
            logger.info("service_enabled", unit=SERVICE_NORMAL)

        return dst

    def uninstall(self) -> list[Path]:
        removed: list[Path] = []
        self._disable_if_installed(SERVICE_NORMAL)
        dst = user_unit_dir() / SERVICE_NORMAL
        if dst.exists():
            if not self.dry_run:
                dst.unlink()
            removed.append(dst)
        self._systemctl("daemon-reload")
        return removed

    def start(self) -> None:
        self._systemctl("start", SERVICE_NORMAL)

    def stop(self) -> None:
        self._systemctl("stop", SERVICE_NORMAL)

    def restart(self) -> None:
        self._systemctl("restart", SERVICE_NORMAL)

    def enable(self) -> None:
        """Habilita o auto-start no boot e inicia o daemon (FEAT-DAEMON-DISABLE-CONTROL-01)."""
        self._systemctl("enable", SERVICE_NORMAL, check=False)
        self.start()

    def disable(self) -> None:
        """Para o daemon e desabilita o auto-start, mantendo a unit instalada."""
        self._disable_if_installed(SERVICE_NORMAL)
        self.stop()

    def status_text(self) -> str:
        """Retorna o output de `systemctl --user status <unit>`."""
        if not _systemctl_de_usuario_disponivel():
            return _SEM_SYSTEMD_DE_USUARIO
        if self.detect_installed_unit() is None:
            return _SEM_SYSTEMD_DE_USUARIO
        result = self._systemctl(
            "status", SERVICE_NORMAL, capture=True, check=False
        )
        if result is None:
            return ""
        stdout = (getattr(result, "stdout", "") or "").strip()
        stderr = (getattr(result, "stderr", "") or "").strip()
        if stdout and stderr:
            return f"{stdout}\n\n[stderr]\n{stderr}"
        return stdout or stderr

    def detect_installed_unit(self) -> str | None:
        """Retorna `"hefesto-dualsense4unix"` se a unit está em algum path"""
        candidates = [user_unit_dir() / SERVICE_NORMAL]
        candidates.extend(d / SERVICE_NORMAL for d in SYSTEM_UNIT_DIRS)
        for path in candidates:
            if path.exists():
                return "hefesto-dualsense4unix"
        return None

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
                "systemctl não encontrado — distro sem systemd (ver ADR-009)"
            ) from exc


__all__ = [
    "SERVICE_NORMAL",
    "ServiceInstaller",
    "find_assets_dir",
    "user_unit_dir",
]

