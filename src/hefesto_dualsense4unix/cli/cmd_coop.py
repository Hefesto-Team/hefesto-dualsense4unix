"""Subcomando `hefesto-dualsense4unix coop ...` (FEAT-DSX-COOP-LOCAL-01).

O CO-OP LOCAL faz cada controle físico virar um jogador SEPARADO (P1, P2, …)
com seu próprio gamepad virtual — ao contrário do modo "N controles, 1 player"
(todos recebem o mesmo output e só o primário envia input).

    hefesto-dualsense4unix coop on          # reconcilia os jogadores agora
    hefesto-dualsense4unix coop off         # RECUSADO: explica, não desliga
    hefesto-dualsense4unix coop status [--json]

COOP-SEM-INTERRUPTOR-01 (06/08/2026) — NOTA DATADA: o co-op deixou de ser uma
opção, por decisão da mantenedora: *"todos e tudo no Hefesto tem que tá com o
permitir co-op ligado (…) se eu conecto 4 controles no PC eu espero, com 4
pessoas jogando, que cada um controle o próprio personagem. Ninguém esperaria
controlar o mesmo personagem com cada controle."* O `off` sobreviveu como
EXPLICAÇÃO — sumir com o subcomando devolveria um "No such command" que não
ensina nada a quem o tem num script ou na memória muscular.

Pré-requisitos para 2 pessoas jogarem: gamepad virtual ligado
(`hefesto-dualsense4unix gamepad on`) + 2+ controles conectados. Erros de IPC
(daemon offline) viram mensagem clara sem traceback.
"""
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.cli.ipc_client import IpcError

app = typer.Typer(
    name="coop",
    help="Co-op local: cada controle vira um jogador (P1, P2, …).",
    no_args_is_help=True,
)
console = Console()


def _call_sync(method: str, params: dict[str, Any] | None = None) -> Any:
    """Chama método IPC e converte IpcError/OSError em mensagem amigável."""
    from hefesto_dualsense4unix.app.ipc_bridge import _run_call

    try:
        return _run_call(method, params, timeout=1.0)
    except IpcError as exc:
        console.print(f"[red]daemon recusou chamada:[/red] {exc.message}")
        raise typer.Exit(code=2) from None
    except (FileNotFoundError, ConnectionError, OSError) as exc:
        console.print(f"[red]daemon offline[/red] (socket IPC inacessível): {exc}")
        raise typer.Exit(code=3) from None


@app.command("on")
def cmd_on() -> None:
    """Reconcilia o co-op local agora (cada controle = um jogador)."""
    result = _call_sync("coop.set", {"enabled": True})
    players = result.get("players") if isinstance(result, dict) else None
    console.print("[green]co-op local ligado[/green]")
    if isinstance(players, int):
        console.print(f"jogadores ativos agora: {players}")
    console.print(
        "[dim]lembre: precisa do gamepad virtual ligado (hefesto-dualsense4unix "
        "gamepad on) + 2+ controles.[/dim]"
    )


#: COOP-SEM-INTERRUPTOR-01 (06/08/2026): o que o `coop off` responde. Três
#: linhas, e cada uma faz um trabalho: o FATO (não desliga mais), o PORQUÊ (a
#: decisão dela, com o motivo dela) e a SAÍDA REAL para quem queria um controle
#: de reserva — que nunca precisou de flag nenhuma.
COOP_OFF_RECUSA = (
    "[yellow]o co-op local não desliga mais.[/yellow]\n"
    "cada controle conectado é um jogador — decisão da mantenedora "
    "(06/08/2026): ninguém conecta quatro controles no PC esperando que os "
    "quatro movam o mesmo personagem.\n"
    "[dim]quer um controle de reserva? deixe-o desconectado. O co-op também "
    "sai de cena sozinho nos jogos com Steam Input (exceção medida), e volta "
    "quando o jogo fecha.[/dim]"
)


@app.command("off")
def cmd_off() -> None:
    """RECUSADO: o co-op local não desliga mais — explica o porquê.

    Não fala com o daemon de propósito: não há estado a mudar, e uma recusa que
    depende do socket viraria "daemon offline" para quem só precisava entender
    o que aconteceu com o comando. A mesma recusa existe no daemon
    (`coop.set {enabled:false}` -> `status: "recusado"`), para quem chega pelo
    IPC em vez da CLI.

    Sai com código 2 (o mesmo de "daemon recusou chamada"): um script que
    dependia de desligar o co-op tem de ENXERGAR que não desligou — um `0`
    silencioso seria a CLI mentindo.
    """
    console.print(COOP_OFF_RECUSA)
    raise typer.Exit(code=2)


#: LUGAR-À-MESA-01/E0a (06/08/2026) — o travessão que substitui o zero.
#:
#: Daemon ANTIGO não publica `coop.externals` (a chave nasceu no EXT-COUNT-01,
#: 25/07). Imprimir `0 controles externos` ali seria trocar uma mentira velha
#: ("jogadores ativos: 1" com três na mesa) por uma mentira NOVA e mais
#: convincente, porque ela tem número. Ausência de dado é `—`, a mesma regra
#: que `slot_label` já aplica na GUI (`app/actions/external_controllers.py`).
SEM_DADO = "—"

#: A ressalva que a LUGAR-À-MESA-01 tornou OBRIGATÓRIA em qualquer boca que
#: emita número de jogador: o Hefesto numera a LUZ, e quem numera o jogador
#: DENTRO do jogo é o jogo (ele escolhe o índice pela ordem em que abre os
#: dispositivos). Prometer "o número aceso é o mesmo do jogo" está proibido
#: por aquela sprint — ver a seção "O que fica ABERTO", item 1.
NOTA_QUEM_NUMERA = "(dentro do jogo, quem numera é o jogo)"


def _plural_externos(n: int) -> str:
    """`1 externo` / `2 externos` — o rótulo concorda com o número."""
    return "1 externo" if n == 1 else f"{n} externos"


def linhas_de_contagem(players: Any, externals: Any) -> list[str]:
    """As DUAS contagens do co-op, nomeadas — LUGAR-À-MESA-01/E0a.

    Função pura (sem IPC, sem `console`) porque o que se testa aqui é a
    HONESTIDADE do texto, não o encanamento.

    A queixa medida em 06/08/2026, com três controles ligados: o `coop status`
    respondia `jogadores ativos: 1` — verdade que engana, porque "jogadores"
    ali significa "quem tem controle virtual do Hefesto", e não "quem está com
    um controle na mão". São duas perguntas e agora são duas linhas, cada uma
    com o nome do que conta:

    - ``jogadores pelo Hefesto`` — quem tem vpad do Hefesto (`coop.players`);
    - ``controles na mesa`` — todo aparelho conectado, externo inclusive
      (`coop.players` + `coop.externals`, publicado desde 25/07 e sem um único
      leitor até aqui).

    Ausência de dado vira ``—`` e NUNCA ``0`` (ver :data:`SEM_DADO`).
    """
    jogadores = players if isinstance(players, int) and not isinstance(players, bool) else None
    ext = (
        externals
        if isinstance(externals, int) and not isinstance(externals, bool) and externals >= 0
        else None
    )
    linhas = [
        f"jogadores pelo Hefesto: {jogadores if jogadores is not None else SEM_DADO}"
    ]
    if jogadores is None or ext is None:
        linhas.append(f"controles na mesa: {SEM_DADO}")
        linhas.append("(este daemon não sabe dizer — atualize o daemon)")
        return linhas
    if ext == 0:
        linhas.append(f"controles na mesa: {jogadores} (nenhum externo)")
        return linhas
    linhas.append(f"controles na mesa: {jogadores + ext}, sendo {_plural_externos(ext)}")
    linhas.append(NOTA_QUEM_NUMERA)
    return linhas


@app.command("status")
def cmd_status(
    as_json: bool = typer.Option(False, "--json", help="Saída como JSON (scripts)."),
) -> None:
    """Mostra o estado atual do co-op local no daemon."""
    state = _call_sync("daemon.state_full")
    coop = state.get("coop") if isinstance(state, dict) else None
    if not isinstance(coop, dict):
        coop = {"enabled": None, "players": None}

    if as_json:
        console.print_json(data=coop)
        return

    enabled = coop.get("enabled")
    players = coop.get("players")
    if enabled is None:
        console.print(
            "[yellow]estado indisponível — daemon não expõe estado do co-op.[/yellow]"
        )
        raise typer.Exit(code=1)

    label = "[green]ligado[/green]" if enabled else "[dim]desligado[/dim]"
    console.print(f"co-op local: {label}")
    # LUGAR-À-MESA-01/E0a: `coop["externals"]` está publicado desde 25/07
    # (`daemon/ipc_handlers.py`, EXT-COUNT-01) e nunca teve leitor — doze dias
    # de campo mudo enquanto a CLI dizia "jogadores ativos: 1" com três
    # controles na mesa dela. `.get` sem default: daemon antigo devolve None,
    # que `linhas_de_contagem` traduz em `—`, jamais em `0`.
    for linha in linhas_de_contagem(players, coop.get("externals")):
        console.print(linha, highlight=False)


__all__ = [
    "COOP_OFF_RECUSA",
    "NOTA_QUEM_NUMERA",
    "SEM_DADO",
    "app",
    "linhas_de_contagem",
]
