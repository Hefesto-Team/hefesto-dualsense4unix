"""Subcomando `hefesto-dualsense4unix controller ...` (FEAT-DSX-CONTROLLER-SELECTOR-01).

Escolhe o ALVO das ações de output (lightbar, gatilhos, player-LED, rumble,
mic-LED) quando há 2+ controles conectados. Por padrão o output é broadcast (vai
para TODOS) — por isso, com 2 controles, ambos mostram o Player 1. Com um alvo
selecionado, as ações miram SÓ aquele controle (seleciono o Controle 2 → seto o
LED dele como Player 2).

    hefesto-dualsense4unix controller list
    hefesto-dualsense4unix controller target 2      # mira o Controle 2
    hefesto-dualsense4unix controller target all    # volta ao broadcast (padrão)
    hefesto-dualsense4unix controller numbers       # nosso nº x nº do jogo x LED

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


# --- PLAYER-LED-01: diagnóstico honesto da numeração --------------------------

#: O aviso que esta sprint obriga a deixar ONDE alguém vai ler o LED. Impresso
#: em toda execução de `controller numbers`, não escondido atrás de `--verbose`:
#: a armadilha custou uma conclusão errada na investigação de 25/07 e custaria
#: de novo se dependesse de alguém pedir ajuda.
_AVISO_SYSFS = (
    "O padrão aceso NÃO identifica quem o escreveu. O jogo escreve o padrão "
    "como relatório HID de saída, interceptado em espaço de usuário — ele "
    "nunca chega à classe de LED do kernel. O que /sys/class/leds mostra é o "
    "número que o KERNEL deu no probe, por um contador que aloca o menor "
    "identificador livre contando físicos e virtuais juntos; e a tabela de "
    "padrões do kernel é IDÊNTICA à nossa em 1..4. As colunas confiáveis são "
    "'nosso' e 'jogo', que vêm do daemon — não do sysfs."
)

#: Caminho do barramento HID, sobrescrevível para teste hermético.
_HID_BUS_ROOT = "/sys/bus/hid/devices"


def _padrao(bits: Any) -> str:
    """Desenha 5 LEDs de player (`` aceso, `` apagado); `—` sem leitura."""
    if not isinstance(bits, (list, tuple)) or not bits:
        return "—"
    return "".join("" if b else "" for b in list(bits)[:5])


def _numero_do_padrao(bits: Any) -> str:
    """Decodifica o padrão contra a tabela canônica; senão devolve o desenho.

    Contar LEDs acesos seria errado: no DualSense o jogador 1 acende o LED do
    MEIO, não o primeiro. A tradução tem de ser pela tabela — a mesma
    `player_led_pattern` que o resto do projeto usa, que é idêntica à do kernel
    em 1..5 (1..4 são do PS5; 5 é "todos acesos").

    Padrão fora da tabela não vira número: mostra-se o desenho e deixa-se a
    interpretação para quem lê. Inventar um número aqui seria repetir, na
    interface, o erro que a leitura de `/sys/class/leds` já causou uma vez.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    if not isinstance(bits, (list, tuple)):
        return "—"
    alvo = tuple(bool(b) for b in list(bits)[:5])
    for numero in range(1, 9):
        if player_led_pattern(numero) == alvo:
            return str(numero)
    return _padrao(bits)


def _hid_devices_por_ordem_de_registro() -> list[tuple[str, str | None, bool]]:
    """`[(nome, uniq, e_nosso_vpad)]` dos HIDs do driver `playstation`.

    ORDENADO PELO CONTADOR HEXADECIMAL do fim do nome, nunca pelo nome. Esta
    regra de método é resultado de um erro de análise real (25/07): listar
    `/sys/bus/hid/devices` por nome põe `0003:*` (USB) antes de `0005:*`
    (Bluetooth) e sugere que o kernel agrupa por barramento — é artefato da
    ordenação alfabética. A cronologia de verdade é o contador depois do ponto.

    Só leitura de sysfs; qualquer nó ilegível é simplesmente pulado (rodar isto
    sem permissão, ou fora do Linux, devolve lista vazia em vez de estourar).
    """
    import glob
    import os

    saida: list[tuple[int, str, str | None, bool]] = []
    for caminho in glob.glob(os.path.join(_HID_BUS_ROOT, "*")):
        nome = os.path.basename(caminho)
        _, _, contador_hex = nome.rpartition(".")
        try:
            contador = int(contador_hex, 16)
        except ValueError:
            continue
        try:
            driver = os.path.basename(os.path.realpath(os.path.join(caminho, "driver")))
        except OSError:
            continue
        if driver != "playstation":
            continue
        uniq: str | None = None
        phys = ""
        try:
            with open(os.path.join(caminho, "uevent"), encoding="utf-8") as fh:
                for linha in fh:
                    if linha.startswith("HID_UNIQ="):
                        uniq = linha.split("=", 1)[1].strip().lower().replace(":", "")
                    elif linha.startswith("HID_PHYS="):
                        phys = linha.split("=", 1)[1].strip()
        except OSError:
            continue
        nosso = phys.startswith("hefesto-vpad") or bool(
            uniq and uniq.startswith("02fe")
        )
        saida.append((contador, nome, uniq or None, nosso))
    saida.sort(key=lambda item: item[0])
    return [(nome, uniq, nosso) for _, nome, uniq, nosso in saida]


def _numeros_do_kernel() -> dict[str, int]:
    """`{uniq: número que o kernel provavelmente deu}` — INFERIDO, não lido.

    O `hid-playstation` atribui o menor identificador livre no probe e o
    materializa acendendo os LEDs; ele NÃO publica esse número em lugar nenhum
    do sysfs. A melhor aproximação disponível é a ordem de registro (o contador
    hexadecimal), contando físicos e virtuais juntos — que é exatamente como o
    contador do kernel funciona.

    É aproximação e a saída diz isso: um controle que desconecta e volta libera
    o identificador dele no meio da fila, e a reconstrução aqui não tem como
    saber disso sem ter estado presente. Serve para responder "o número que
    você está vendo pode ser do kernel?", não para afirmar autoria.
    """
    numeros: dict[str, int] = {}
    for posicao, (_nome, uniq, _nosso) in enumerate(
        _hid_devices_por_ordem_de_registro(), start=1
    ):
        if uniq:
            numeros.setdefault(uniq, posicao)
    return numeros


def _padroes_acesos() -> dict[str, tuple[bool, ...]]:
    """`{uniq: padrão aceso na classe LED}` — leitura crua, ver `_AVISO_SYSFS`."""
    from hefesto_dualsense4unix.core import sysfs_leds

    saida: dict[str, tuple[bool, ...]] = {}
    try:
        nos = sysfs_leds.discover()
    except OSError:
        return saida
    for chave, no in nos.items():
        try:
            bits = no.get_players()
        except OSError:
            bits = None
        if bits is not None:
            saida[chave] = bits
    return saida


@app.command("numbers")
def cmd_numbers(
    as_json: bool = typer.Option(False, "--json", help="Saída como JSON (scripts)."),
) -> None:
    """Nosso número x número do jogo x padrão aceso x número do kernel.

    PLAYER-LED-01 (entrega 5). Existe porque, com quatro controles na mesa, era
    IMPOSSÍVEL distinguir esses quatro números a olho: a tabela de padrões do
    kernel é idêntica à nossa em 1..4, então o LED aceso não diz quem o
    escreveu. Aqui cada coluna declara a própria procedência.
    """
    state = _call_sync("daemon.state_full")
    controllers = state.get("controllers") if isinstance(state, dict) else None
    sinal = state.get("game_signal") if isinstance(state, dict) else None
    if not isinstance(controllers, list):
        controllers = []
    conectados = [c for c in controllers if isinstance(c, dict) and c.get("connected")]
    acesos = _padroes_acesos()
    kernel = _numeros_do_kernel()

    linhas: list[dict[str, Any]] = []
    for c in conectados:
        uniq = c.get("uniq") if isinstance(c.get("uniq"), str) else None
        bits_jogo = c.get("player_leds_game")
        linhas.append(
            {
                "controle": _numero_exibido(c),
                "uniq": uniq,
                "transporte": c.get("transport"),
                "nosso_numero": c.get("player"),
                "player_slot": c.get("player_slot"),
                "numero_do_jogo": (
                    _numero_do_padrao(bits_jogo) if bits_jogo is not None else None
                ),
                "player_leds_game": bits_jogo,
                "retido_pelo_gate": c.get("game_output_retido") or [],
                "padrao_aceso_sysfs": (
                    list(acesos[uniq]) if uniq and uniq in acesos else None
                ),
                "numero_do_kernel_inferido": kernel.get(uniq) if uniq else None,
            }
        )

    if as_json:
        console.print_json(
            data={
                "autoridade_de_exibicao": (
                    sinal.get("authority") if isinstance(sinal, dict) else None
                ),
                "controles": linhas,
                "aviso": _AVISO_SYSFS,
            }
        )
        return

    if not conectados:
        console.print("[yellow]nenhum controle conectado.[/yellow]")
        raise typer.Exit(code=1)

    autoridade = (
        sinal.get("authority") if isinstance(sinal, dict) else None
    ) or "desconhecida"
    console.print(f"autoridade de exibição: [cyan]{autoridade}[/cyan]")
    for linha in linhas:
        console.print(
            f"\n[bold]Controle {linha['controle']}[/bold] — "
            f"{(linha['transporte'] or '?').upper()}"
        )
        console.print(f"  nosso número (daemon)........: {linha['nosso_numero'] or '—'}")
        console.print(
            f"  número do jogo (camada GAME).: {linha['numero_do_jogo'] or '—'}"
            f"   {_padrao(linha['player_leds_game'])}"
        )
        retido = linha["retido_pelo_gate"]
        console.print(
            f"  retido pelo gate agora.......: "
            f"{', '.join(retido) if retido else 'nada'}"
        )
        console.print(
            f"  padrão aceso em /sys.........: "
            f"{_padrao(linha['padrao_aceso_sysfs'])}   [dim](ambíguo)[/dim]"
        )
        console.print(
            f"  número do kernel (inferido)..: "
            f"{linha['numero_do_kernel_inferido'] or '—'}"
        )
    console.print(f"\n[yellow]Atenção:[/yellow] [dim]{_AVISO_SYSFS}[/dim]")


__all__ = ["app"]
