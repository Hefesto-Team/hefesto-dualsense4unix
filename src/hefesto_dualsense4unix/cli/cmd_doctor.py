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


def _find_doctor_sh() -> Path | None:
    """Localiza `scripts/doctor.sh` em layouts conhecidos (editable e .deb)."""
    candidates = [
        # editable/nativo: src/hefesto_dualsense4unix/cli/cmd_doctor.py -> raiz/scripts
        Path(__file__).resolve().parents[3] / "scripts" / "doctor.sh",
        Path("/usr/share/hefesto-dualsense4unix/scripts/doctor.sh"),
        Path("/usr/local/share/hefesto-dualsense4unix/scripts/doctor.sh"),
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


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


def doctor_cmd(fix: bool = False, quiet: bool = False) -> None:
    """Roda `scripts/doctor.sh` (infra) + checks do daemon via IPC."""
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

    console.print("\n== daemon (via IPC) ==")
    for tag, message in asyncio.run(_daemon_checks()):
        console.print(f"{tag} {message}")

    raise typer.Exit(code=rc)


__all__ = ["doctor_cmd"]
