"""Subcomando `hefesto-dualsense4unix rumble policy|passthrough`.

A política de intensidade da vibração e o repasse do jogo, que antes só a aba
Vibração ajustava. Cascas finas sobre `rumble.policy_set`,
`rumble.policy_custom` e `rumble.passthrough`: o serviço valida os parâmetros e
esta casca diz o que ele respondeu.
"""
from __future__ import annotations

import typer

from hefesto_dualsense4unix.cli.chamada_ao_servico import chamar, console

app = typer.Typer(
    name="rumble",
    help="Intensidade da vibração e repasse do jogo.",
    no_args_is_help=True,
)


@app.command("policy")
def cmd_policy(
    politica: str = typer.Argument(
        ..., help="economia | balanceado | max | auto | custom (com o multiplicador)."
    ),
    mult: float | None = typer.Argument(
        None, help="Só com `custom`: o multiplicador (0 a 2; acima de 1 amplifica)."
    ),
) -> None:
    """Escolhe a intensidade da vibração: `rumble policy max`, `rumble policy custom 0.7`."""
    if politica == "custom":
        if mult is None:
            console.print(
                "[red]falta o multiplicador[/red] — `rumble policy custom <mult>`."
            )
            raise typer.Exit(code=2)
        resposta = chamar("rumble.policy_custom", {"mult": mult})
        valor = resposta.get("mult") if isinstance(resposta, dict) else mult
        console.print(f"vibração: [green]custom[/green] (multiplicador {valor})")
        return
    if mult is not None:
        console.print(
            "[red]só `custom` leva multiplicador[/red] — `rumble policy custom <mult>`."
        )
        raise typer.Exit(code=2)
    resposta = chamar("rumble.policy_set", {"policy": politica})
    valor = resposta.get("policy") if isinstance(resposta, dict) else politica
    console.print(f"vibração: [green]{valor}[/green]")


@app.command("passthrough")
def cmd_passthrough(
    acao: str = typer.Argument(..., help="on devolve a vibração ao jogo; off não solta nada."),
    uniq: str = typer.Option(
        "", "--uniq", help="Só neste controle (o MAC normalizado). Sem isto, todos."
    ),
) -> None:
    """Devolve a vibração ao jogo (`on`); o serviço só solta o que foi fixado à mão."""
    if acao not in ("on", "off"):
        console.print(f"[red]ação inválida: {acao}[/red] — use: on | off")
        raise typer.Exit(code=2)
    ligado = acao == "on"
    params: dict[str, object] = {"enabled": ligado}
    if uniq:
        params["uniq"] = uniq
    chamar("rumble.passthrough", params)
    if ligado:
        console.print("vibração: [green]o jogo manda[/green]")
    else:
        console.print(
            "vibração: [dim]sem mudança — o serviço só solta a vibração fixada "
            "(`passthrough on`)[/dim]"
        )


__all__ = ["app"]
