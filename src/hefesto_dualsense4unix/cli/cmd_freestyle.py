"""Subcomando `hefesto-dualsense4unix freestyle on|off|status`.

O botão «Modo Freestyle» da aba Jogar, no terminal. Ligar é o mesmo caminho do
«Ativar» do Freestyle na aba Perfis, e desligar devolve a escolha do usuário;
quem decide é o serviço (`freestyle.set`), e esta casca só pede e diz o que o
serviço respondeu.
"""
from __future__ import annotations

from typing import Any

import typer

from hefesto_dualsense4unix.cli.chamada_ao_servico import chamar, console

app = typer.Typer(
    name="freestyle",
    help="O Modo Freestyle: um perfil só vale para todo jogo.",
    no_args_is_help=True,
)


def _dizer(ligado: bool) -> None:
    selo = "[green]ligado[/green]" if ligado else "[dim]desligado[/dim]"
    console.print(f"Modo Freestyle: {selo}")


def _pedir(ligado: bool) -> None:
    resposta = chamar("freestyle.set", {"ligado": ligado})
    estado = resposta.get("freestyle_ligado") if isinstance(resposta, dict) else None
    if not isinstance(estado, bool):
        console.print(
            "[yellow]o serviço respondeu sem dizer o estado do Freestyle; "
            "confira com `freestyle status`[/yellow]"
        )
        raise typer.Exit(code=1)
    _dizer(estado)
    if estado != ligado:
        raise typer.Exit(code=1)


@app.command("on")
def cmd_on() -> None:
    """Liga o Modo Freestyle."""
    _pedir(True)


@app.command("off")
def cmd_off() -> None:
    """Desliga o Modo Freestyle e devolve a escolha de perfil de antes."""
    _pedir(False)


@app.command("status")
def cmd_status(
    as_json: bool = typer.Option(False, "--json", help="Saída como JSON (scripts)."),
) -> None:
    """Diz se o Modo Freestyle está ligado."""
    estado: Any = chamar("daemon.status")
    ligado = estado.get("freestyle_ligado") if isinstance(estado, dict) else None
    if not isinstance(ligado, bool):
        console.print("[yellow]o serviço não informou o estado do Freestyle[/yellow]")
        raise typer.Exit(code=1)
    if as_json:
        console.print_json(data={"freestyle_ligado": ligado})
        return
    _dizer(ligado)


__all__ = ["app"]
