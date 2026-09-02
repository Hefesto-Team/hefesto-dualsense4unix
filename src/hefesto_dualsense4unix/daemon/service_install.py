"""Instalação e gestão da unidade systemd --user `hefesto-dualsense4unix.service`.

Unidade única (SIMPLIFY-UNIT-01). A dualidade histórica normal/headless foi
eliminada porque o Hefesto - Dualsense4Unix é inerentemente um daemon desktop com DualSense.

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

#: O nome da unit do daemon, e ele NÃO se digita: vem de `utils/identidade.py`.
#: Foi um literal digitado que fez a aba Sistema afirmar `not-found` sobre uma
#: unit `enabled`, em 01/09/2026.
SERVICE_NORMAL = identidade.atual().unit_daemon

# Diretórios system-wide onde .deb e empacotamentos Debian-likes instalam
# units de user systemd. detect_installed_unit() checa esses paths além
# do user dir. Lista mutável para facilitar monkeypatch em testes.
SYSTEM_UNIT_DIRS: list[Path] = [
    Path("/usr/lib/systemd/user"),
    Path("/etc/systemd/user"),
]


def user_unit_dir() -> Path:
    """`~/.config/systemd/user/` — só RESPONDE o caminho.

    T-13 (ONDA0-Z7 · O AMBIENTE PRESUMIDO 01, 24/08/2026): antes o
    `mkdir(parents=True, exist_ok=True)` era efeito colateral de PERGUNTAR
    onde a pasta é — numa máquina sem systemd de usuário, `status_text()` e
    `detect_installed_unit()` (LEITURA) criavam a pasta e seguiam como se
    estivesse tudo bem. Quem precisa que a pasta EXISTA cria —
    `ServiceInstaller.install` é o único chamador que grava algo nela.
    """
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "systemd" / "user"


#: T-13 (ONDA0-Z7): a mesma resposta que `status_text` já escrevia para "unit
#: não instalada" — reaproveitada para "não há systemd de usuário para
#: perguntar", que é um estado DIFERENTE (a unit pode até estar instalada,
#: copiada por um `install.sh` anterior) mas leva à MESMA ação daqui.
_SEM_SYSTEMD_DE_USUARIO = (
    "hefesto-dualsense4unix.service não instalada.\n"
    "Para instalar via systemd --user:\n"
    "  hefesto-dualsense4unix daemon install-service\n"
    "Para iniciar em foreground sem systemd:\n"
    "  hefesto-dualsense4unix daemon start --foreground"
)


def _systemctl_de_usuario_disponivel() -> bool:
    """``systemctl`` existe no ``PATH`` E responde por uma instância de usuário?

    T-13 (ONDA0-Z7, 24/08/2026). Sem esta conferência, `status_text()` ou
    deixava `RuntimeError` escapar (``systemctl`` ausente do PATH — o
    ``FileNotFoundError`` de ``_systemctl`` não é pego aqui) ou devolvia a
    saída CRUA de erro do systemctl (``Failed to connect to bus: ...``) em
    vez da mensagem amigável que este arquivo já escreve para "sem systemd"
    (`_SEM_SYSTEMD_DE_USUARIO`, acima).

    ``systemctl --user is-system-running`` imprime um ESTADO em stdout
    (``running``/``degraded``/``starting``/...) quando há bus de usuário
    respondendo, e stdout VAZIO (erro só em stderr, retcode != 0) quando não
    há — container/chroot/SSH sem sessão de login, distro sem systemd.
    """
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
    """Localiza `assets/` contendo a unidade `.service`.

    Ordem:
      1. `HEFESTO_DUALSENSE4UNIX_ASSETS_DIR` env (sobrescreve tudo, útil pra testes).
      2. Repo layout: `<source>/assets/` relativo ao módulo.
      3. `/usr/share/hefesto-dualsense4unix/assets/` (pacote instalado).
    """
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
        """Copia a unit para o diretório do usuário.

        `enable=True` habilita auto-start no boot (BUG-MULTI-INSTANCE-01: opt-in).
        Default é só copiar e fazer daemon-reload — o usuário decide explicitamente
        se quer que o daemon suba no login.
        """
        assets = find_assets_dir()
        src = assets / SERVICE_NORMAL
        if not src.exists():
            raise FileNotFoundError(f"unit source não existe: {src}")

        unit_dir = user_unit_dir()
        dst = unit_dir / SERVICE_NORMAL
        if not self.dry_run:
            # T-13: quem GRAVA cria a pasta — user_unit_dir() só responde o
            # caminho desde 24/08/2026.
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
        """Para o daemon e desabilita o auto-start, mantendo a unit instalada.

        Distinto de `pause` (runtime, daemon vivo, sem input) e de `uninstall`
        (remove a unit). É o "desligar" do programa sem desinstalar.
        """
        self._disable_if_installed(SERVICE_NORMAL)
        self.stop()

    def status_text(self) -> str:
        """Retorna o output de `systemctl --user status <unit>`.

        Se a unit não está instalada (nenhum arquivo em `~/.config/systemd/user/`
        nem em `SYSTEM_UNIT_DIRS`), retorna mensagem clara em vez de string
        vazia — o `systemctl status <unit-inexistente>` escreve a explicação em
        stderr e fica com stdout vazio, o que confunde o usuário CLI.

        T-13 (ONDA0-Z7, 24/08/2026): a MESMA mensagem agora também cobre
        ``systemctl`` ausente do ``PATH`` ou sem instância de usuário
        respondendo — antes esses dois casos ou explodiam (``RuntimeError``,
        propagado de ``_systemctl``) ou devolviam a saída crua de erro do
        systemctl, em vez da orientação de "rode em foreground" que este
        arquivo já sabia escrever.
        """
        if not _systemctl_de_usuario_disponivel():
            return _SEM_SYSTEMD_DE_USUARIO
        if self.detect_installed_unit() is None:
            return _SEM_SYSTEMD_DE_USUARIO
        result = self._systemctl(
            "status", SERVICE_NORMAL, capture=True, check=False
        )
        if result is None:
            return ""
        # systemctl status escreve em stdout em sucesso, mas em alguns casos
        # (unit failed sem journal) só popula stderr. Concatenamos para garantir
        # que o usuário veja algo util.
        stdout = (getattr(result, "stdout", "") or "").strip()
        stderr = (getattr(result, "stderr", "") or "").strip()
        if stdout and stderr:
            return f"{stdout}\n\n[stderr]\n{stderr}"
        return stdout or stderr

    def detect_installed_unit(self) -> str | None:
        """Retorna `"hefesto-dualsense4unix"` se a unit está em algum path
        conhecido — user dir (install.sh) OU system dirs (.deb), senão `None`.

        Caminhos checados em ordem:
          1. `~/.config/systemd/user/` — install.sh.
          2. `SYSTEM_UNIT_DIRS` (module-level) — paths de instalação Debian.
        """
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

# "A simplicidade é a sofisticação máxima." — Leonardo da Vinci
