"""Subcomando `hefesto-dualsense4unix lightbar-reset` — o instrumento do 0x08.

LIGHTBAR-MEDIR-O-0X08-01 (08/08/2026).

POR QUE ESTE COMANDO EXISTE
===========================
A adoção de um DualSense por Bluetooth derruba o "claim" da lightbar na máquina
de estados do FIRMWARE (medido 17-18/07, `core/lightbar_reset.py:1-11`): a barra
apaga e passa a IGNORAR as escritas de cor, enquanto os LEDs de jogador e os
gatilhos adaptativos seguem funcionando. A cura conhecida é um report 0x31 com
``valid_flag1 = 0x08`` ("Reset LED state"), que devolve o claim ao host.

Só que essa cura foi **removida** do produto em `108b711` (04/08), com base numa
sprint que mediu 7 eventos de correlação perfeita: o 0x08 mandado logo após a
conexão TRAVOU a barra em todos. E a mesma sprint registra um controle negativo
que a contradiz — o 0x08 num controle conectado havia dez minutos **não travou**.

Em 08/08 mediu-se o outro lado: cinco dias e vinte adoções por Bluetooth **sem
nenhum 0x08**. Arrancou-se a causa alegada — e o que se escreveu aqui sobre o
efeito estava ERRADO.

CORREÇÃO DATADA (11/08/2026), porque a afirmação abaixo era falsa
-----------------------------------------------------------------
Este docstring dizia que, nesses cinco dias sem 0x08, "a barra continuou morta".
**Não continuou.** A escavação do journal do daemon e dos transcritos achou a
barra **ACESA** no rádio DENTRO daqueles cinco dias, quatro vezes, três delas
com fala literal dela: 08/08 16:39, 08/08 21:35, 08/08 23:48 e 11/08 11:40
(ensaios ``lightbar-bt-aceso-*`` em ``docs/data/ensaios.csv``; a correção está
registrada no ensaio ``lightbar-bt-sem-0x08-cinco-dias``).

O erro de método é o que importa guardar: eu registrei como MEDIÇÃO uma frase
que só existia neste docstring. É a armadilha ``A-12`` de
``docs/process/METODO-DE-ISOLAMENTO.md`` — o caderno envelhecer sem que ninguém
note.

O suspeito 0x08 **continua ausente e a barra OBEDECEU** — o que mantém o 0x08
fora do banco dos réus, mas pela razão OPOSTA à que estava escrita aqui.

A hipótese que este comando torna falsificável segue de pé, e segue sem ensaio
que a feche:

    o 0x08 DEVOLVE o claim — e só o derruba quando mandado dentro da janela
    de ~3,4 s pós-conexão.

O que 12/08 acrescentou, e que nenhuma das medições acima tinha: a variável que
separava "obedeceu" de "não obedeceu" era **quem estava com o hidraw aberto no
instante da probe** — e era o Steam. Ver o terceiro gabarito em
``docs/process/METODO-DE-ISOLAMENTO.md``.

POR QUE PELO DAEMON, E NÃO POR UM SCRIPT
========================================
Um script que abrisse o hidraw brigaria com o daemon pelo mesmo dispositivo — a
armadilha nº 3 do `docs/process/COMO-OLHAR-A-TELA.md` ("o instrumento pode estar
brigando com o produto", que já fez `test trigger --raw` imprimir "aplicado" sem
ter aplicado). Aqui quem escreve é o handle que o daemon **já tem aberto**, pelo
mesmo `writeReport` (sequência e CRC corretos) que todo report nosso usa.

ISTO NÃO É CURA
===============
Nenhum caminho automático chama isto. Se o reset voltar à adoção, ele volta lá —
com decisão própria, teste próprio e a nota datada que a casa exige.
"""
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.cli.ipc_client import IpcError

console = Console()


def cmd_lightbar_reset(uniq: str | None = None) -> None:
    """Manda o Reset LED state e conta o que aconteceu, sem enfeitar."""
    from hefesto_dualsense4unix.app.ipc_bridge import _run_call

    params: dict[str, Any] = {}
    if uniq:
        params["uniq"] = uniq
    try:
        resultado = _run_call("lightbar.reset", params or None, timeout=2.0)
    except IpcError as exc:
        console.print(f"[red]daemon recusou:[/red] {exc.message}")
        raise typer.Exit(code=2) from None
    except (FileNotFoundError, ConnectionError, OSError) as exc:
        console.print(f"[red]daemon offline[/red] (socket IPC inacessível): {exc}")
        console.print(
            "[dim]este comando precisa do daemon: é ele que tem o handle aberto.[/dim]"
        )
        raise typer.Exit(code=3) from None

    enviados = {}
    if isinstance(resultado, dict):
        bruto = resultado.get("enviados")
        if isinstance(bruto, dict):
            enviados = bruto

    if not enviados:
        # Não é erro: é a resposta "não havia handle aberto". Dizer "falhou"
        # aqui mandaria alguém procurar defeito onde só há controle desligado.
        console.print(
            "[yellow]Nenhum controle com handle aberto[/yellow] — nada foi enviado."
        )
        raise typer.Exit(code=1)

    for key, ok in enviados.items():
        marca = "[green]enviado[/green]" if ok else "[red]falhou[/red]"
        console.print(f"  {key}: {marca}")

    if any(enviados.values()):
        console.print()
        console.print("[bold]Olhe a barra de luz agora.[/bold]")
        console.print(
            "[dim]Acendeu na cor do perfil = o 0x08 devolveu o claim, e a cura é "
            "reenviá-lo FORA da janela de conexão.[/dim]"
        )
        console.print(
            "[dim]Continuou apagada = o 0x08 não é a cura, e a origem é outra.[/dim]"
        )
        console.print(
            "[dim]Os LEDs de jogador podem apagar no ato — a repintura seguinte "
            "deve trazê-los de volta; se não vierem, isso também é dado.[/dim]"
        )


def cmd_player_leds(acao: str) -> None:
    """Comuta a supressão do LED de jogador e diz o que fazer em seguida."""
    from hefesto_dualsense4unix.app.ipc_bridge import _run_call

    normalizada = acao.strip().lower()
    if normalizada not in {"on", "off"}:
        console.print("[red]use 'on' ou 'off'[/red]")
        raise typer.Exit(code=2)
    suprimir = normalizada == "off"
    try:
        _run_call("debug.player_leds", {"suprimir": suprimir}, timeout=3.0)
    except IpcError as exc:
        console.print(f"[red]daemon recusou:[/red] {exc.message}")
        raise typer.Exit(code=2) from None
    except (FileNotFoundError, ConnectionError, OSError) as exc:
        console.print(f"[red]daemon offline[/red]: {exc}")
        raise typer.Exit(code=3) from None

    if suprimir:
        console.print("[yellow]LED de jogador SUPRIMIDO[/yellow] — nada será escrito.")
        console.print()
        console.print("[bold]Agora desligue e religue UM controle[/bold], e olhe a barra.")
        console.print(
            "[dim]Acendeu = a escrita do player-LED era quem derrubava o claim.[/dim]"
        )
        console.print(
            "[dim]Apagada = a causa é a conexão em si, e este caminho está inocente.[/dim]"
        )
        console.print("[dim]Depois: `hefesto-dualsense4unix player-leds on`.[/dim]")
    else:
        console.print("[green]LED de jogador devolvido[/green] — produto no normal.")


__all__ = ["cmd_lightbar_reset", "cmd_player_leds"]
