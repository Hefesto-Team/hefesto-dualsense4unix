"""Entry point da GUI Hefesto - Dualsense4Unix (GTK3)."""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING


def _force_xwayland_on_cosmic() -> bool:
    """Força GDK_BACKEND=x11 (XWayland) quando a sessão é COSMIC.

    No cosmic-comp (Wayland nativo), os popups de GtkComboBox/GtkMenu abrem
    com fundo claro, mal-posicionados e com grab quebrado (fecham sozinhos,
    exigem "segurar o clique"). Rodar a GUI sob XWayland contorna o bug.

    IMPORTANTE: a própria sessão COSMIC do Pop!_OS exporta
    `GDK_BACKEND=wayland,x11` (lista de fallback que PREFERE wayland) — que é
    exatamente o que dispara o bug. Por isso sobrescrevemos esse valor; só não
    mexemos se já for `x11` puro ou se o usuário pediu opt-out via
    `HEFESTO_DUALSENSE4UNIX_NO_XWAYLAND=1` (ex.: um COSMIC futuro que conserte
    o grab de popups e queira Wayland nativo de volta).

    Retorna True se aplicou (para logar depois que o logging subir).
    """
    if os.environ.get("HEFESTO_DUALSENSE4UNIX_NO_XWAYLAND") == "1":
        return False
    if os.environ.get("GDK_BACKEND", "") == "x11":
        return False  # já é XWayland puro — nada a fazer
    desktop = (
        os.environ.get("XDG_CURRENT_DESKTOP", "")
        + os.environ.get("XDG_SESSION_DESKTOP", "")
    ).lower()
    if "cosmic" in desktop:
        os.environ["GDK_BACKEND"] = "x11"
        return True
    return False


# CRÍTICO: setar GDK_BACKEND ANTES de importar HefestoApp. A cadeia de imports
# da app (gi.repository) ABRE um GdkDisplay já no import — se o backend não
# estiver definido aqui, o display abre em Wayland e o ajuste em main() chega
# tarde demais. Por isso o call é no topo do módulo, não dentro de main().
def _sanear_loaders_do_gdk_pixbuf() -> bool:
    """Descarta um `GDK_PIXBUF_MODULE_FILE` herdado que não saiba ler SVG.

    BUG-TRAY-ICONE-INVISIVEL-01 (medido em 18/08/2026, Pop!_OS 22.04): o snap do
    terminal exporta essa variável apontando para um cache de loaders PRÓPRIO,
    dentro do confinamento dele. Todo processo GTK lançado daquele terminal
    herda o apontamento e perde o loader de SVG do sistema — o `rsvg-convert`
    renderiza o ícone sem reclamar, e o mesmo arquivo falha no `GdkPixbuf` com
    "Couldn't recognize the image file format".

    O estrago é silencioso e não é só o ícone da bandeja, que some da barra sem
    erro nenhum no log: qualquer SVG da interface cai junto.

    A variável só é removida quando o cache apontado REALMENTE não declara svg —
    quem tiver um cache próprio legítimo e completo continua com ele de pé. E a
    remoção acontece no topo do módulo, antes de o GdkPixbuf inicializar: depois
    disso ele já leu o cache e a correção chega tarde.
    """
    caminho = os.environ.get("GDK_PIXBUF_MODULE_FILE")
    if not caminho:
        return False
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            cache = arquivo.read()
    except OSError:
        # Ilegível conta como inútil: melhor cair no padrão do sistema.
        del os.environ["GDK_PIXBUF_MODULE_FILE"]
        return True

    # Não basta o cache MENCIONAR svg — o do snap menciona. O que importa é se
    # os módulos que ele aponta são carregáveis AQUI. Um loader empacotado
    # dentro do confinamento traz o librsvg dele, ligado a uma glibc mais nova
    # que a do hospedeiro, e o dlopen falha com "version `GLIBC_2.xx' not
    # found". O GTK não trata isso como ícone faltando: ele aborta o processo
    # inteiro no `ensure_surface_for_gicon`, e a janela morre ao abrir.
    modulos = [
        linha.strip().strip('"')
        for linha in cache.splitlines()
        if linha.strip().startswith('"/') and linha.rstrip().endswith('.so"')
    ]
    if modulos and all(not os.path.exists(m) or _de_outro_confinamento(m) for m in modulos):
        del os.environ["GDK_PIXBUF_MODULE_FILE"]
        return True
    if "svg" not in cache:
        del os.environ["GDK_PIXBUF_MODULE_FILE"]
        return True
    return False


def _de_outro_confinamento(modulo: str) -> bool:
    """O módulo mora dentro de um pacote confinado que não é o nosso processo."""
    for raiz in ("/snap/", "/var/lib/snapd/snap/"):
        if modulo.startswith(raiz):
            return not (os.environ.get("SNAP") or "").startswith(raiz)
    return False


_XWAYLAND_FORCED = _force_xwayland_on_cosmic()
_PIXBUF_SANEADO = _sanear_loaders_do_gdk_pixbuf()

from hefesto_dualsense4unix.app.app import HefestoApp
from hefesto_dualsense4unix.utils.i18n import init_locale
from hefesto_dualsense4unix.utils.logging_config import configure_logging, get_logger

if TYPE_CHECKING:
    import structlog


def _is_systemd_managed(pid: int) -> bool:
    """Retorna True se o processo é child do systemd user (PID 1 user-instance)
    ou do systemd init (PID 1). Não mexer em daemons systemd-managed para
    evitar StartLimitBurst-hit + auto-restart loops.
    """
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("PPid:"):
                    ppid = int(line.split()[1])
                    break
            else:
                return False
        # PPid=1 é systemd init OR user systemd. Suficiente para "não tocar".
        if ppid == 1:
            return True
        # systemd user instance (--user) tem cmdline "/usr/lib/systemd/systemd --user"
        with open(f"/proc/{ppid}/cmdline") as f:
            cmd = f.read().replace("\0", " ")
        return "/usr/lib/systemd/systemd" in cmd or "systemd --user" in cmd
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError, ValueError):
        return False


def _kill_previous_instances(logger: structlog.stdlib.BoundLogger) -> None:
    """Mata processos GUI anteriores; preserva daemon managed por systemd.

    Cobre:
      - GUI antiga (python -m hefesto_dualsense4unix.app.main)
      - Daemon avulso (hefesto-dualsense4unix daemon start) — APENAS se NÃO
        managed por systemd. Daemons via systemctl ficam intactos para o
        Restart=on-failure não bater em StartLimitBurst.
      - Flatpak runtime do app (br.andrefarias.Hefesto)

    Pula próprio PID + PPID. Defesa anti-loop: daemons systemd-managed são
    detectados via /proc/<pid>/status PPid e preservados.
    """
    own_pid = os.getpid()
    own_ppid = os.getppid()

    patterns = [
        r"hefesto_dualsense4unix\.app\.main",
        r"hefesto-dualsense4unix-gui",
        r"br\.andrefarias\.Hefesto",
    ]
    # Daemon: pattern separado para checar systemd-managed antes de matar.
    daemon_pattern = r"hefesto-dualsense4unix daemon start"

    def _kill(pid: int, sig: int) -> None:
        if pid in (own_pid, own_ppid):
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, sig)

    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pat in patterns:
            try:
                out = subprocess.run(
                    ["pgrep", "-f", pat],
                    capture_output=True, text=True, timeout=2,
                ).stdout.strip()
                for pid_str in out.split("\n"):
                    if not pid_str.strip():
                        continue
                    try:
                        _kill(int(pid_str), sig)
                    except ValueError:
                        continue
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

        # Daemon: matar APENAS se não-systemd-managed.
        try:
            out = subprocess.run(
                ["pgrep", "-f", daemon_pattern],
                capture_output=True, text=True, timeout=2,
            ).stdout.strip()
            for pid_str in out.split("\n"):
                if not pid_str.strip():
                    continue
                try:
                    pid = int(pid_str)
                except ValueError:
                    continue
                if _is_systemd_managed(pid):
                    logger.debug("daemon_systemd_managed_preservado", pid=pid)
                    continue
                _kill(pid, sig)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        if sig == signal.SIGTERM:
            time.sleep(0.5)

    logger.info("previous_instances_killed", own_pid=own_pid)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    logger = get_logger(__name__)
    # XWayland forçado no topo do módulo (antes do import da app abrir o
    # display). Aqui só registramos o resultado depois que o logging subiu.
    if _XWAYLAND_FORCED:
        logger.info("gdk_backend_x11_forcado_cosmic")
    _unused_argv = argv

    # CHORE-CONFIG-MIGRATE-LEGACY-SHORT-PATH-01: migra config legada curta→longa
    # ANTES de qualquer leitura de preferências/perfis pela app (idempotente).
    from hefesto_dualsense4unix.utils.migrate_legacy_paths import migrate_legacy_paths

    migrate_legacy_paths()

    # FEAT-I18N-INFRASTRUCTURE-01 (v3.4.0): inicializa locale ANTES de
    # qualquer Gtk.Builder ou widget, garantindo que set_translation_domain
    # consiga resolver labels traduzíveis do Glade no boot.
    init_locale()

    # BUG-DOCK-ICON-WMCLASS-MISMATCH-01 (v3.4.3): seta prgname ANTES de
    # qualquer Gtk init para o GTK derivar `app_id` Wayland corretamente.
    # Sem isso, a dock COSMIC não associa janela ao .desktop e mostra
    # icone generico. prgname deve casar com basename do .desktop file.
    # Também seta application_name (usado em window title bar fallback).
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk
    GLib.set_prgname("hefesto-dualsense4unix")
    GLib.set_application_name("Hefesto - Dualsense4Unix")
    # Default icon do app — janelas filhas (diálogos, etc.) herdam.
    with contextlib.suppress(Exception):
        Gtk.Window.set_default_icon_name("hefesto-dualsense4unix")

    # Garantia de instância única absoluta — mata qualquer processo antigo do
    # Hefesto - Dualsense4Unix antes de subir. Evita estado inconsistente, socket
    # órfão, pid file zumbi.
    _kill_previous_instances(logger)

    try:
        app = HefestoApp()
    except Exception as exc:
        logger.error("hefesto_app_init_failed", err=str(exc))
        print(f"Falha ao iniciar GUI Hefesto - Dualsense4Unix: {exc}", file=sys.stderr)
        return 1

    logger.info("hefesto_app_starting")
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
