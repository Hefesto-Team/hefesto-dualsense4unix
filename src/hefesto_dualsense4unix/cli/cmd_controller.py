"""Subcomando `hefesto-dualsense4unix controller ...` (FEAT-DSX-CONTROLLER-SELECTOR-01).

Escolhe o ALVO das ações de output (lightbar, gatilhos, player-LED, rumble,
mic-LED) quando há 2+ controles conectados. Por padrão o output é broadcast (vai
para TODOS) — por isso, com 2 controles, ambos mostram o Player 1. Com um alvo
selecionado, as ações miram SÓ aquele controle (seleciono o Controle 2 → seto o
LED dele como Player 2).

    hefesto-dualsense4unix controller list
    hefesto-dualsense4unix controller target 2      # mira o Controle 2
    hefesto-dualsense4unix controller target all    # volta ao broadcast (padrão)

A numeração é 1-based e bate com a coluna "Controle N" da listagem. COR-01
(D6): "Controle N" é o SLOT DE SESSÃO do controle (`player_slot` do payload —
estável a replug; o mesmo número da GUI e do applet), com fallback para a
posição+1 quando o daemon ainda não expõe o campo. O contrato IPC
`controller.target.set` continua POSICIONAL (0-based): o mapeamento
slot→índice acontece AQUI, na borda de exibição. Erros de IPC (daemon
offline) viram mensagem clara sem traceback.
"""
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.cli.ipc_client import IpcError

app = typer.Typer(
    name="controller",
    help="Seletor de controle: mira as ações de output num controle específico.",
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


def _slot_of(controller: dict[str, Any]) -> int | None:
    """`player_slot` do payload IPC, ou None (daemon antigo / sem slot).

    Defensivo por contrato (COR-01): o campo é exposto por daemons novos;
    ausência = fallback posicional. `bool` é excluído (True é int em Python
    e viraria "Controle 1" fantasma num payload malformado).
    """
    slot = controller.get("player_slot")
    if isinstance(slot, int) and not isinstance(slot, bool) and slot >= 1:
        return slot
    return None


def _numero_exibido(controller: dict[str, Any]) -> int:
    """Número "Controle N" exibido: o slot de sessão, ou posição+1 (fallback)."""
    slot = _slot_of(controller)
    if slot is not None:
        return slot
    return int(controller.get("index", 0)) + 1


def _conectados() -> list[dict[str, Any]]:
    """Lista de controles CONECTADOS do `daemon.state_full` (defensiva)."""
    state = _call_sync("daemon.state_full")
    controllers = state.get("controllers") if isinstance(state, dict) else None
    if not isinstance(controllers, list):
        return []
    return [c for c in controllers if isinstance(c, dict) and c.get("connected")]


@app.command("target")
def cmd_target(
    alvo: str = typer.Argument(
        ...,
        metavar="<n|all>",
        help="Número do controle (o 'Controle N' da listagem) ou 'all' para broadcast.",
    ),
) -> None:
    """Mira as ações de output em UM controle (ou em todos com 'all')."""
    raw = alvo.strip().lower()
    conectados: list[dict[str, Any]] = []
    if raw in ("all", "todos", "*"):
        index: int | None = None
    else:
        try:
            n = int(raw)
        except ValueError:
            console.print(
                f"[red]alvo inválido:[/red] '{alvo}' — use um número (1, 2, …) ou 'all'."
            )
            raise typer.Exit(code=2) from None
        if n < 1:
            console.print("[red]alvo inválido:[/red] o número do controle começa em 1.")
            raise typer.Exit(code=2)
        # COR-01 (D6): a usuária digita o número que VÊ na listagem (slot de
        # sessão). Mapeia slot→índice posicional na borda; daemon antigo (sem
        # `player_slot` em nenhum controle) cai no mapeamento posicional
        # histórico (n-1). Slot conhecido porém sem controle conectado (ex.:
        # reserva de um controle desligado) é erro claro, nunca um chute.
        conectados = _conectados()
        com_slot = [c for c in conectados if _slot_of(c) is not None]
        if com_slot:
            alvos = [c for c in com_slot if _slot_of(c) == n]
            if not alvos:
                console.print(
                    f"[red]Controle {n} não está conectado.[/red] Veja os números "
                    "em 'controller list'."
                )
                raise typer.Exit(code=2)
            index = int(alvos[0].get("index", n - 1))
        else:
            index = n - 1
    result = _call_sync("controller.target.set", {"index": index})
    effective = result.get("target_index") if isinstance(result, dict) else None
    if effective is None:
        console.print("[green]alvo de output: todos os controles[/green] (broadcast)")
    else:
        numero = int(effective) + 1
        for c in conectados:
            if int(c.get("index", -1)) == int(effective):
                numero = _numero_exibido(c)
                break
        console.print(f"[green]alvo de output: Controle {numero}[/green]")


@app.command("list")
def cmd_list(
    as_json: bool = typer.Option(False, "--json", help="Saída como JSON (scripts)."),
    external: bool = typer.Option(
        False,
        "--external",
        help="Inclui o inventário read-only de gamepads externos (todos os vendors).",
    ),
) -> None:
    """Lista os controles conectados e qual é o alvo de output atual."""
    state = _call_sync("daemon.state_full")
    controllers = state.get("controllers") if isinstance(state, dict) else None
    target_index = state.get("output_target_index") if isinstance(state, dict) else None
    if not isinstance(controllers, list):
        controllers = []
    conectados = [c for c in controllers if isinstance(c, dict) and c.get("connected")]

    # 8BIT-01: inventário read-only dos gamepads externos (opt-in do
    # `controller.list`). `externos is None` = daemon em execução não expõe a
    # chave (código antigo) — distinto de "lista vazia" (sondou e não achou).
    externos: list[dict[str, Any]] | None = None
    if external:
        listagem = _call_sync("controller.list", {"external": True})
        raw_ext = listagem.get("external") if isinstance(listagem, dict) else None
        if isinstance(raw_ext, list):
            externos = [e for e in raw_ext if isinstance(e, dict)]

    if as_json:
        data: dict[str, Any] = {
            "controllers": conectados,
            "output_target_index": target_index,
        }
        if externos is not None:
            data["external"] = externos
        console.print_json(data=data)
        return

    if not conectados:
        console.print("[yellow]nenhum controle conectado.[/yellow]")
        if not external:
            raise typer.Exit(code=1)
    else:
        # COR-01 (D6): o rótulo "Controle N" é o slot de sessão (`player_slot`),
        # estável a replug — o mesmo número da GUI e do applet. Fallback
        # posicional (index+1) para daemon antigo sem o campo.
        alvo_label = "todos (broadcast)"
        if target_index is not None:
            alvo_label = f"Controle {int(target_index) + 1}"
            for c in conectados:
                if int(c.get("index", -1)) == int(target_index):
                    alvo_label = f"Controle {_numero_exibido(c)}"
                    break
        console.print(f"alvo de output: [cyan]{alvo_label}[/cyan]")
        for c in conectados:
            idx = int(c.get("index", 0))
            transporte = (c.get("transport") or "?").upper()
            marcas: list[str] = []
            if c.get("is_primary"):
                marcas.append("primário")
            if target_index is not None and idx == target_index:
                marcas.append("alvo")
            sufixo = f" [{', '.join(marcas)}]" if marcas else ""
            console.print(f"  Controle {_numero_exibido(c)} — {transporte}{sufixo}")

    if external:
        if externos is None:
            console.print(
                "[yellow]o daemon em execução não expõe o inventário de externos "
                "(código antigo — reinicie o daemon).[/yellow]"
            )
            return
        console.print("gamepads externos (somente leitura):")
        if not externos:
            console.print("  [dim]nenhum gamepad externo detectado.[/dim]")
        for e in externos:
            nome = e.get("name") or "?"
            vid = e.get("vid") or "????"
            pid = e.get("pid") or "????"
            bus = str(e.get("bus") or "?").upper()
            driver = e.get("driver") or "?"
            console.print(f"  {nome} — {vid}:{pid} — {bus} — driver {driver}")


__all__ = ["app"]
