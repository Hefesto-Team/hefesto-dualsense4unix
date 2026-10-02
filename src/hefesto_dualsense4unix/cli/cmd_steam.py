"""Subcomando `hefesto-dualsense4unix gamepad steam-input ...` — o desfazer."""
from __future__ import annotations

import contextlib

import typer
from rich.console import Console
from rich.markup import escape

# não podem importar este módulo (typer/rich no topo). A função mudou de casa
from hefesto_dualsense4unix.integrations.steam_launch_options import nome_do_appid

app = typer.Typer(
    name="steam-input",
    help="Exceção do Steam Input — os jogos em que o Steam Input fica ligado.",
    no_args_is_help=True,
)
console = Console()


def _entradas() -> list[tuple[str, str | None]]:
    """A allowlist como `[(appid, nome ou None)]`, na ordem do arquivo."""
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        parse_steam_input_allowlist,
        steam_input_allowlist_path,
    )

    caminho = steam_input_allowlist_path()
    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError:
        texto = ""
    return [(appid, nome_do_appid(appid)) for appid in parse_steam_input_allowlist(texto)]


def _rotulo(appid: str, nome: str | None) -> str:
    """Uma linha por jogo, com nome — o formato que a sprint pediu."""
    return f"{escape(nome)} (appid {appid})" if nome else f"appid {appid} (não instalado)"


def _resolver(alvo: str, entradas: list[tuple[str, str | None]]) -> str | None:
    """Traduz o que a pessoa digitou em appid. `None` = não deu para decidir."""
    bruto = alvo.strip()
    if bruto.isdigit():
        return bruto
    procurado = bruto.casefold()
    exatos = [appid for appid, nome in entradas if nome and nome.casefold() == procurado]
    if len(exatos) == 1:
        return exatos[0]
    parciais = [appid for appid, nome in entradas if nome and procurado in nome.casefold()]
    if len(parciais) == 1:
        return parciais[0]
    candidatos = exatos or parciais
    if not candidatos:
        console.print(f"[red]nenhum jogo da exceção casa com[/red] {escape(bruto)!r}")
        console.print("[dim]veja os nomes com 'gamepad steam-input list'.[/dim]")
        return None
    console.print(f"[yellow]{escape(bruto)!r} casa com mais de um jogo:[/yellow]")
    por_appid = dict(entradas)
    for appid in candidatos:
        console.print(f"  {_rotulo(appid, por_appid.get(appid))}")
    console.print("[dim]repita usando o appid.[/dim]")
    return None


def _avisar_daemon() -> None:
    """Faz a mudança valer agora, sem reiniciar nada (best-effort)."""
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.app.ipc_bridge import _run_call

        _run_call("launch_env.refresh", {}, timeout=1.0)


@app.command("list")
def cmd_list() -> None:
    """Lista os jogos da exceção do Steam Input, um por linha, pelo nome."""
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        steam_input_allowlist_path,
    )

    entradas = _entradas()
    caminho = steam_input_allowlist_path()
    if not entradas:
        console.print("[dim]Nenhum jogo na exceção do Steam Input.[/dim]")
        console.print(
            "[dim]O Hefesto entrega o controle em todos os jogos. "
            "A exceção nasce do botão 'Este jogo não funciona'.[/dim]"
        )
        return

    console.print("Jogos em que o Hefesto não deixa o Steam Input ser desligado:")
    for appid, nome in entradas:
        console.print(
            f"  {_rotulo(appid, nome)} — nele o controle físico fica "
            "escondido; cor, gatilhos e jogadores continuam do Hefesto"
        )
    console.print(f"\n[dim]arquivo: {caminho}[/dim]")
    console.print(
        "[dim]para desfazer: 'gamepad steam-input remove <nome ou appid>', "
        "ou a caixinha no editor do perfil, na aba Perfis.[/dim]"
    )


@app.command("remove")
def cmd_remove(
    jogo: str = typer.Argument(
        ...,
        metavar="JOGO",
        help="AppID (2111190) ou parte do nome do jogo ('mullet').",
    ),
) -> None:
    """Tira um jogo da exceção — o guarda volta a desligar o Steam Input nele."""
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        remove_appid_from_steam_input_allowlist,
    )

    entradas = _entradas()
    appid = _resolver(jogo, entradas)
    if appid is None:
        raise typer.Exit(code=1)

    rotulo = _rotulo(appid, dict(entradas).get(appid))
    status = remove_appid_from_steam_input_allowlist(appid)

    if status == "removido":
        console.print(f"[green]desfeito:[/green] {rotulo} saiu da exceção.")
        console.print(
            "[dim]o guarda volta a desligar o Steam Input nesse jogo. Cor, "
            "gatilhos, vibração e jogadores não mudam — eles já valiam com a "
            "marca.[/dim]"
        )
        _avisar_daemon()
        return

    if status == "nao_estava":
        console.print(f"[yellow]{rotulo} já não estava na exceção[/yellow] — nada a desfazer.")
        raise typer.Exit(code=1)
    if status == "appid_invalido":
        console.print(f"[red]appid inválido:[/red] {escape(appid)!r}")
        raise typer.Exit(code=2)
    console.print("[red]não deu para escrever a allowlist[/red] (permissão? disco cheio?).")
    raise typer.Exit(code=1)


__all__ = ["app", "nome_do_appid"]
