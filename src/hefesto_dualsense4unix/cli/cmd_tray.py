"""Subcomando `hefesto-dualsense4unix tray`.

Abre o tray icon GTK3 e fica em primeiro plano atualizando status via IPC
a cada 2s. Ctrl+C ou Sair no menu encerra.

Gracefully falha quando PyGObject/AppIndicator não estão disponíveis,
mostrando comando exato pra instalar.
"""
from __future__ import annotations

import asyncio
import subprocess
import threading

import typer
from rich.console import Console

console = Console()


def tray_cmd() -> None:
    from hefesto_dualsense4unix.integrations.tray import TrayController, probe_gi_availability

    ok, msg = probe_gi_availability()
    if not ok:
        console.print(f"[yellow]Tray indisponível:[/] {msg}")
        raise typer.Exit(code=2)

    controller = TrayController()
    if not controller.start():
        console.print("[red]falha ao criar tray icon[/]")
        raise typer.Exit(code=3)

    console.print("[green]tray ativo[/] — clique no icone pra acessar o menu.")

    # Roda IPC refresh em thread separada; Gtk.main bloqueia na principal.
    stop_flag = threading.Event()

    def refresh_loop() -> None:
        while not stop_flag.is_set():
            try:
                asyncio.run(_refresh_once(controller))
            except Exception as exc:
                controller.update_status(f"erro: {exc}")
            stop_flag.wait(2.0)

    t = threading.Thread(target=refresh_loop, daemon=True, name="hefesto-dualsense4unix-tray-refresh")  # noqa: E501
    t.start()

    try:
        controller.run()  # bloqueante
    except KeyboardInterrupt:
        pass
    finally:
        stop_flag.set()
        controller.stop()


async def _refresh_once(controller: TrayController) -> None:
    from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

    try:
        async with IpcClient.connect() as client:
            status = await client.call("daemon.status")
            profiles = await client.call("profile.list")
    except (FileNotFoundError, ConnectionError, IpcError, OSError):
        controller.update_status("daemon offline")
        return

    bateria = status.get("battery_pct")
    perfil = status.get("active_profile") or "nenhum"
    controller.update_status(f"Bat {bateria}% | Perfil: {perfil}")

    profile_names = [p["name"] for p in profiles.get("profiles", [])]
    controller.update_profiles(profile_names, on_select=_activate_profile)


def _activate_profile(name: str) -> None:
    async def _do() -> None:
        from hefesto_dualsense4unix.cli.ipc_client import IpcClient

        try:
            async with IpcClient.connect() as client:
                await client.call("profile.switch", {"name": name})
        except Exception:
            subprocess.Popen(["hefesto-dualsense4unix", "profile", "activate", name])

    asyncio.run(_do())


from hefesto_dualsense4unix.integrations.tray import TrayController  # noqa: E402

__all__ = ["tray_cmd"]
