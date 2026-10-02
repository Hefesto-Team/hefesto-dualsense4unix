"""Subcomando `hefesto-dualsense4unix tray` — o ícone de bandeja do produto."""
from __future__ import annotations

import asyncio
import subprocess
from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.app.actions.atos_da_bandeja import (
    LANCADOR_DO_PAINEL as LANCADOR_DO_PAINEL,
)
from hefesto_dualsense4unix.app.actions.atos_da_bandeja import (
    abrir_o_painel as _abrir_o_painel,
)
from hefesto_dualsense4unix.app.actions.atos_da_bandeja import (
    mexer_no_servico as _servico,
)

console = Console()


def _chamar(metodo: str, argumentos: dict[str, Any] | None = None) -> Any:
    """Uma chamada de IPC ao daemon, com o silêncio certo quando ele não está."""
    from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

    async def _ir() -> Any:
        async with IpcClient.connect() as cliente:
            return await cliente.call(metodo, argumentos or {})

    try:
        return asyncio.run(_ir())
    except (FileNotFoundError, ConnectionError, IpcError, OSError, RuntimeError):
        return None


def _listar_perfis() -> list[dict[str, Any]]:
    resposta = _chamar("profile.list")
    if not isinstance(resposta, dict):
        return []
    perfis = resposta.get("profiles")
    return perfis if isinstance(perfis, list) else []


def _trocar_de_perfil(nome: str) -> bool:
    """Troca pelo IPC; se o daemon não responder, tenta pela CLI."""
    if _chamar("profile.switch", {"name": nome}) is not None:
        return True
    try:
        subprocess.Popen(
            ["hefesto-dualsense4unix", "profile", "activate", nome],
            start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return False
    return True


def _estado() -> dict[str, Any] | None:
    """O snapshot que vira `N controles · Bat N% · Perfil` no menu.

    `daemon.state_full` E NÃO `daemon.status`: o `status` não traz a lista de
    controles, e o `AppTray._controllers_suffix_from_state` a lê para dizer
    quantos estão na mesa. Pedir o menor dos dois faria o tray mostrar sempre
    «1 controle».
    """
    resposta = _chamar("daemon.state_full")
    return resposta if isinstance(resposta, dict) else None


def _definir_o_modo(ligado: bool) -> bool:
    """O interruptor da aba Jogar, pelo mesmo plano de IPC que ela despacha."""
    from hefesto_dualsense4unix.app.actions.jogar.painel import plano_do_modo
    from hefesto_dualsense4unix.app.actions.mode_transition import (
        MODE_GAMEPAD,
        MODE_NATIVE,
    )

    if ligado:
        _servico("start")
    plano = plano_do_modo(MODE_GAMEPAD if ligado else MODE_NATIVE)
    if plano is None:
        return False
    pegou = True
    for metodo, params in plano:
        if _chamar(metodo, params) is None:
            pegou = False
    return pegou


def _reconectar_os_controles() -> bool:
    """O «Reconectar controles» da aba Jogar — os MESMOS dois passos."""
    primeiro = _chamar("coop.sync") is not None
    segundo = _chamar("identity.renumber") is not None
    return primeiro and segundo


def tray_cmd() -> None:
    """Sobe o ícone de bandeja e fica em primeiro plano até `Sair`."""
    from hefesto_dualsense4unix.app.tray import AppTray
    from hefesto_dualsense4unix.integrations.tray import probe_gi_availability

    ok, motivo = probe_gi_availability()
    if not ok:
        console.print(f"[yellow]Tray indisponível:[/] {motivo}")
        raise typer.Exit(code=2)

    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    bandeja = AppTray(
        on_show_window=_abrir_o_painel,
        on_quit=Gtk.main_quit,
        on_list_profiles=_listar_perfis,
        on_switch_profile=_trocar_de_perfil,
        on_state=_estado,
        on_set_modo=_definir_o_modo,
        on_reconectar=_reconectar_os_controles,
        on_servico=_servico,
    )
    if not bandeja.start():
        console.print(
            "[red]não consegui criar o ícone de bandeja[/] — "
            "não há quem hospede o `org.kde.StatusNotifierWatcher` nesta sessão")
        raise typer.Exit(code=3)

    console.print("[green]tray ativo[/] — clique no ícone para abrir o menu.")
    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass
    finally:
        bandeja.stop()


__all__ = ["tray_cmd"]
