"""Subcomando `hefesto-dualsense4unix doctor` — health-check no CLI.

Reusa `scripts/doctor.sh` (infra: daemon, udev, uinput, applet COSMIC, WirePlumber,
controle) e adiciona checks "do daemon" via IPC (responde? pausado? perfis
listáveis?), generalizando a sacada do doctor para as features que só o daemon
conhece em runtime. FEAT-DOCTOR-CLI-AND-CHECKS-01.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import typer
from rich.console import Console

from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

console = Console()


def _find_repo_file(relpath: str) -> Path | None:
    """Localiza um arquivo do repo (script/dsx.sh) em layouts conhecidos."""
    candidates = [
        Path(__file__).resolve().parents[3] / relpath,
        Path("/usr/share/hefesto-dualsense4unix") / relpath,
        Path("/usr/local/share/hefesto-dualsense4unix") / relpath,
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _find_doctor_sh() -> Path | None:
    """Localiza `scripts/doctor.sh` em layouts conhecidos (editable e .deb)."""
    return _find_repo_file("scripts/doctor.sh")


async def _daemon_checks() -> list[tuple[str, str]]:
    """Checks que só o daemon conhece (via IPC). Retorna [(tag, mensagem)]."""
    rows: list[tuple[str, str]] = []
    try:
        async with IpcClient.connect() as client:
            status = await client.call("daemon.status")
            rows.append(("[ OK ]", "IPC responde (daemon.status atendido)"))
            if isinstance(status, dict) and status.get("paused"):
                rows.append(
                    ("[WARN]", "daemon PAUSADO — input suspenso ('daemon resume' p/ retomar)")
                )
            profiles = await client.call("profile.list")
            count = len(profiles.get("profiles", [])) if isinstance(profiles, dict) else 0
            if count > 0:
                rows.append(("[ OK ]", f"perfis listáveis via IPC ({count})"))
            else:
                rows.append(("[WARN]", "nenhum perfil listado pelo daemon"))
    except (FileNotFoundError, ConnectionError, IpcError):
        rows.append(("[WARN]", "daemon offline — checks de runtime pulados"))
    return rows


def _run_script(relpath: str, *args: str, confirm: str | None = None) -> int:
    """Roda um script do repo. `confirm` != None pede confirmação antes."""
    script = _find_repo_file(relpath)
    if script is None:
        console.print(f"[yellow]{relpath} não encontrado — pulado[/yellow]")
        return 0
    if confirm is not None and not typer.confirm(confirm):
        console.print("[dim]cancelado.[/dim]")
        return 0
    return subprocess.run(["bash", str(script), *args], check=False).returncode


def _print_storm_block() -> None:
    """Diagnóstico storm (FEAT-DSX-UNIFY-01) — read-only, sem sudo."""
    from hefesto_dualsense4unix.integrations import storm_doctor

    console.print("\n== anti-storm / sistema ==")
    for tag, message in storm_doctor.storm_report():
        console.print(f"{tag} {message}")


def doctor_cmd(
    fix: bool = False,
    quiet: bool = False,
    fix_safe: bool = False,
    reapply_all: bool = False,
) -> None:
    """Roda `scripts/doctor.sh` (infra) + diagnóstico storm + checks do daemon.

    FEAT-DSX-UNIFY-01:
    - `--fix-safe`: aplica só o SEGURO (sem sudo) — Steam Input OFF (se a Steam
      não estiver rodando) + drop-in do WirePlumber. Reversível/idempotente.
    - `--reapply-all`: invoca o `dsx.sh` (o motor privilegiado — PEDE SENHA) para
      reaplicar TUDO, incluindo a parte de udev/power. Confirma antes.
    """
    rc = 0
    sh = _find_doctor_sh()
    if sh is not None:
        args = ["bash", str(sh)]
        if fix:
            args.append("--fix")
        if quiet:
            args.append("--quiet")
        rc = subprocess.run(args, check=False).returncode
    else:
        console.print(
            "[yellow]scripts/doctor.sh não encontrado — só os checks do daemon[/yellow]"
        )

    _print_storm_block()

    console.print("\n== daemon (via IPC) ==")
    for tag, message in asyncio.run(_daemon_checks()):
        console.print(f"{tag} {message}")

    if fix_safe:
        console.print("\n== fix-safe (sem sudo) ==")
        # --apply-quiet: só edita se a Steam NÃO estiver rodando (não a fecha).
        _run_script("scripts/disable_steam_input.sh", "--apply-quiet")
        # --install: DualSense não-default, microfone preservado.
        _run_script("scripts/fix_wireplumber_default_source.sh", "--install")
        _print_storm_block()

    if reapply_all:
        console.print("\n== reaplicar tudo (dsx.sh — privilegiado) ==")
        rc = _run_script(
            "dsx.sh",
            confirm=(
                "Isto roda o dsx.sh e vai PEDIR SUA SENHA (mexe em udev/power do "
                "sistema). Continuar?"
            ),
        ) or rc

    raise typer.Exit(code=rc)


__all__ = ["doctor_cmd"]
