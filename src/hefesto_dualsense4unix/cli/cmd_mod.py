"""Subcomando ``hefesto-dualsense4unix mod ...``: as modificações (ADR-021).

Nenhum comando daqui fala com o serviço pelo IPC: todos escrevem o registro
(``mods.json``), e o supervisor do serviço o relê e obedece em um segundo.
"""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from hefesto_dualsense4unix.mods.instalador import (
    InstalacaoRecusadaError,
    Lugares,
    Resultado,
    atualizar,
    desligar,
    instalar,
    ler_estado,
    ler_registro,
    ligar,
    manifesto_instalado,
    remover,
)
from hefesto_dualsense4unix.mods.manifesto import o_que_a_permissao_deixa

app = typer.Typer(
    name="mod",
    help="Instala e controla as modificações, que rodam fora do serviço.",
    no_args_is_help=True,
)

console = Console()

_ORIGENS = {
    "oficial": "[green]oficial[/green]",
    "comunidade": "[yellow]comunidade[/yellow]",
    "local": "[cyan]local[/cyan]",
}


def _recusar(exc: InstalacaoRecusadaError) -> typer.Exit:
    console.print(f"[red]{exc.frase}[/red]")
    return typer.Exit(code=1)


def _mostrar_permissoes(permissoes: list[str]) -> None:
    if not permissoes:
        console.print("  [dim]nenhuma permissão[/dim]")
    for palavra in permissoes:
        console.print(f"  [bold]{palavra}[/bold]: {o_que_a_permissao_deixa(palavra)}")


def _dizer_o_resultado(resultado: Resultado, verbo: str) -> None:
    entrada = resultado.entrada
    console.print(
        f"«{entrada.nome}» {entrada.versao} {verbo} "
        f"({_ORIGENS[entrada.origem]}, commit {entrada.commit[:12] or 'sem git'})."
    )
    if resultado.permissoes_novas:
        console.print("Ela pede:")
        _mostrar_permissoes(resultado.permissoes_novas)
        console.print(f"Para ligar: [bold]hefesto-dualsense4unix mod ligar {entrada.id}[/bold]")
    elif not entrada.ligada:
        console.print(f"Para ligar: [bold]hefesto-dualsense4unix mod ligar {entrada.id}[/bold]")


@app.command("instalar")
def cmd_instalar(
    origem: str = typer.Argument(..., help="Endereço git ou pasta com o hefesto-mod.json."),
    ref: str | None = typer.Option(None, "--ref", help="A tag (ou o ramo) a instalar."),
) -> None:
    """Instala sem ligar. «Oficial» só com tag assinada pelo time; o resto é «comunidade»."""
    try:
        resultado = instalar(origem, ref=ref)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    _dizer_o_resultado(resultado, "instalada")


@app.command("atualizar")
def cmd_atualizar(
    mod_id: str = typer.Argument(..., help="O id da modificação."),
    ref: str | None = typer.Option(None, "--ref", help="A tag nova."),
) -> None:
    """Baixa de novo; se a versão nova pede permissão nova, ela desliga até o «sim»."""
    try:
        resultado = atualizar(mod_id, ref=ref)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    _dizer_o_resultado(resultado, "atualizada")


@app.command("listar")
def cmd_listar() -> None:
    """As modificações instaladas e o estado de cada uma."""
    try:
        lugares = Lugares.do_xdg()
        registro = ler_registro(lugares.registro)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    if not registro:
        console.print("[dim]Nenhuma modificação instalada.[/dim]")
        return
    estado = ler_estado(lugares.estado)
    tabela = Table(show_header=True)
    tabela.add_column("Id", style="cyan")
    tabela.add_column("Versão")
    tabela.add_column("Origem")
    tabela.add_column("Estado")
    tabela.add_column("Motivo")
    for mod_id, entrada in sorted(registro.items()):
        vivo = estado.get(mod_id, {})
        agora = str(vivo.get("estado") or ("ligada" if entrada.ligada else "desligada"))
        motivo = str(vivo.get("motivo") or "")
        if vivo.get("ultima_linha"):
            motivo = f"{motivo} {vivo['ultima_linha']}".strip()
        tabela.add_row(mod_id, entrada.versao, _ORIGENS[entrada.origem], agora, motivo)
    console.print(tabela)


@app.command("permissoes")  # noqa-acento: palavra do contrato, ASCII
def cmd_permissoes(mod_id: str = typer.Argument(..., help="O id da modificação.")) -> None:
    """O que a modificação instalada pede, uma linha por permissão."""
    try:
        manifesto = manifesto_instalado(mod_id)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    console.print(f"«{manifesto.nome}» pede:")
    _mostrar_permissoes(manifesto.permissoes)


@app.command("ligar")
def cmd_ligar(
    mod_id: str = typer.Argument(..., help="O id da modificação."),
    sim: bool = typer.Option(False, "--sim", help="Aceita as permissões sem perguntar."),
) -> None:
    """Mostra as permissões, pede o «sim» e liga."""
    try:
        manifesto = manifesto_instalado(mod_id)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    console.print(f"«{manifesto.nome}» pede:")
    _mostrar_permissoes(manifesto.permissoes)
    if not sim and not typer.confirm("Ligar com estas permissões?", default=False):
        console.print("Não liguei.")
        raise typer.Exit(code=1)
    try:
        ligar(mod_id)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    console.print(f"«{manifesto.nome}» ligada; o serviço abre em um segundo.")


@app.command("desligar")
def cmd_desligar(mod_id: str = typer.Argument(..., help="O id da modificação.")) -> None:
    """Desliga; o serviço para o processo dela."""
    try:
        entrada = desligar(mod_id)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    console.print(f"«{entrada.nome}» desligada.")


@app.command("remover")
def cmd_remover(mod_id: str = typer.Argument(..., help="O id da modificação.")) -> None:
    """Para, apaga o código, os dados e a linha do registro, e confere os três."""
    try:
        restos = remover(mod_id)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    if restos:
        console.print(f"[red]«{mod_id}» não saiu inteira; ficou:[/red]")
        for resto in restos:
            console.print(f"  {resto}")
        raise typer.Exit(code=1)
    console.print(f"«{mod_id}» removida: o código, os dados e o registro não existem mais.")


__all__ = ["app"]
