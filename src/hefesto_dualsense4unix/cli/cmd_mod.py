"""Subcomando ``hefesto-dualsense4unix mod ...``: as modificações (ADR-021).

Nenhum comando daqui fala com o serviço pelo IPC: todos escrevem o registro
(``mods.json``), e o supervisor do serviço o relê e obedece em um segundo.
"""
from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError, Resultado

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
    from hefesto_dualsense4unix.mods.manifesto import o_que_a_permissao_deixa

    if not permissoes:
        console.print("  [dim]nenhuma permissão[/dim]")
    for palavra in permissoes:
        console.print(f"  [bold]{palavra}[/bold]: {o_que_a_permissao_deixa(palavra)}")


def _nomes_das_instaladas() -> dict[str, str]:
    """O nome de cada extensão instalada, lido ANTES de instalar: a que o ``substitui`` manda
    embora sai do registro, e a frase do fim a conhece pelo nome (sem ele, pelo id)."""
    from hefesto_dualsense4unix.mods.instalador import (
        InstalacaoRecusadaError,
        Lugares,
        ler_registro,
    )

    try:
        return {mod_id: e.nome for mod_id, e in ler_registro(Lugares.do_xdg().registro).items()}
    except InstalacaoRecusadaError:
        return {}


def frase_das_substituidas(ids: list[str], nomes: dict[str, str]) -> str:
    """«Saiu a «X».» (ou «Saíram a «X» e a «Y».»); vazia quando nenhuma saiu."""
    if not ids:
        return ""
    citadas = [f"a «{nomes.get(mod_id, mod_id)}»" for mod_id in ids]
    lista = citadas[0] if len(citadas) == 1 else f"{', '.join(citadas[:-1])} e {citadas[-1]}"
    return f"{'Saiu' if len(ids) == 1 else 'Saíram'} {lista}."


def _dizer_o_resultado(resultado: Resultado, verbo: str, nomes: dict[str, str]) -> None:
    entrada = resultado.entrada
    console.print(
        f"«{entrada.nome}» {entrada.versao} {verbo} "
        f"({_ORIGENS[entrada.origem]}, commit {entrada.commit[:12] or 'sem git'})."
    )
    if resultado.substituidas:
        console.print(frase_das_substituidas(resultado.substituidas, nomes), markup=False)
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
    sim: bool = typer.Option(False, "--sim", help="Aceita o aviso da extensão sem perguntar."),
) -> None:
    """Instala sem ligar. «Oficial» só com tag assinada pelo time; o resto é «comunidade»."""
    from hefesto_dualsense4unix.mods.instalador import (
        AvisoParaVerError,
        InstalacaoRecusadaError,
        instalar,
    )

    nomes = _nomes_das_instaladas()
    try:
        try:
            resultado = instalar(origem, ref=ref, aviso_visto="")
        except AvisoParaVerError as aviso:
            console.print(aviso.frase, markup=False)
            if not sim and not typer.confirm("Instalar mesmo assim?", default=False):
                console.print("Não instalei.")
                raise typer.Exit(code=1) from aviso
            resultado = instalar(origem, ref=ref, aviso_visto=aviso.aviso)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    _dizer_o_resultado(resultado, "instalada", nomes)


@app.command("atualizar")
def cmd_atualizar(
    mod_id: str = typer.Argument(..., help="O id da modificação."),
    ref: str | None = typer.Option(None, "--ref", help="A tag nova."),
) -> None:
    """Baixa de novo; se a versão nova pede permissão nova, ela desliga até o «sim»."""
    from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError, atualizar

    nomes = _nomes_das_instaladas()
    try:
        resultado = atualizar(mod_id, ref=ref)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    _dizer_o_resultado(resultado, "atualizada", nomes)


@app.command("listar")
def cmd_listar() -> None:
    """As modificações instaladas e o estado de cada uma."""
    from hefesto_dualsense4unix.mods.instalador import (
        InstalacaoRecusadaError,
        Lugares,
        ler_estado,
        ler_registro,
    )

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


@app.command("permissoes")  # (noqa-acento)
def cmd_permissoes(mod_id: str = typer.Argument(..., help="O id da modificação.")) -> None:
    """O que a modificação instalada pede, uma linha por permissão."""
    from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError, manifesto_instalado

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
    from hefesto_dualsense4unix.mods.instalador import (
        InstalacaoRecusadaError,
        Lugares,
        aviso_por_ver,
        ler_registro,
        ligar,
        manifesto_instalado,
    )

    try:
        manifesto = manifesto_instalado(mod_id)
        entrada = ler_registro(Lugares.do_xdg().registro).get(mod_id)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    aviso = aviso_por_ver(entrada, manifesto) if entrada is not None else ""
    if aviso:
        console.print(f"«{manifesto.nome}» avisa: {aviso}", markup=False)
    console.print(f"«{manifesto.nome}» pede:")
    _mostrar_permissoes(manifesto.permissoes)
    if manifesto.processo is not None and shutil.which("bwrap") is None:
        console.print("Sem o bwrap, ela roda sem caixa e pode mais do que estas permissões.")
    if not sim and not typer.confirm("Ligar com estas permissões?", default=False):
        console.print("Não liguei.")
        raise typer.Exit(code=1)
    try:
        ligar(mod_id, permissoes_vistas=manifesto.permissoes, aviso_visto=aviso)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    if manifesto.processo is not None:
        console.print(f"«{manifesto.nome}» ligada; o serviço abre em um segundo.")
    elif manifesto.lancador is not None:
        console.print(f"«{manifesto.nome}» ligada; os jogos dela aparecem na aba Experimental.")
    else:
        console.print(f"«{manifesto.nome}» ligada.")


@app.command("desligar")
def cmd_desligar(mod_id: str = typer.Argument(..., help="O id da modificação.")) -> None:
    """Desliga; o serviço para o processo dela."""
    from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError, desligar

    try:
        entrada = desligar(mod_id)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    console.print(f"«{entrada.nome}» desligada.")


@app.command("remover")
def cmd_remover(mod_id: str = typer.Argument(..., help="O id da modificação.")) -> None:
    """Para, apaga o código, os dados e a linha do registro, e confere os três. O ``meu.css``
    fica: é escrita da pessoa, e reinstalar a extensão o encontra."""
    from hefesto_dualsense4unix.mods.instalador import (
        InstalacaoRecusadaError,
        o_css_que_fica,
        remover,
    )

    try:
        restos = remover(mod_id)
    except InstalacaoRecusadaError as exc:
        raise _recusar(exc) from exc
    if restos:
        console.print(f"[red]«{mod_id}» não saiu inteira; ficou:[/red]")
        for resto in restos:
            console.print(f"  {resto}")
        raise typer.Exit(code=1)
    fica = o_css_que_fica(mod_id)
    if fica is None:
        console.print(f"«{mod_id}» removida: o código, os dados e o registro não existem mais.")
        return
    console.print(f"«{mod_id}» removida: o código, os dados e o registro não existem mais. "
                  f"O seu CSS ficou em {fica}, e volta se você instalar a extensão de novo.")


__all__ = ["app"]
