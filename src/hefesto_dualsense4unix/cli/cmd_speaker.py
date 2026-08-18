"""Subcomando `hefesto-dualsense4unix speaker volume|mute|unmute|release|status`.

SOM-02 (E3), o irmão do `mic release`. O alto-falante do controle tem TRÊS
camadas de volume e este comando só alcança a do MEIO — o registrador de volume
no report HID, que é a única que vale nos dois transportes e a única sem
leitura:

1. **rota/sink do PipeWire** — `wpctl`/`pactl` e o estado persistido do
   WirePlumber. Tem leitura, tem persistência e não custa posse nenhuma. Se o
   sink do controle estiver MUDO, mexer aqui não faz som sair: o `doctor` sabe
   detectar essa condição e a reporta de propósito, porque alto-falante mudo
   pode ser escolha dela;
2. **registrador de volume no HID** — é o que este comando manda, pelo
   `speaker.set` do IPC;
3. **fluxo de áudio por Bluetooth** — não implementado (o DualSense não fala
   A2DP/HFP/HSP). Por BT, subir o volume da camada 2 mexe num registrador que
   não tem o que tocar.

O PREÇO da camada 2, dito antes do primeiro uso: a partir da primeira escrita o
hefesto manda o volume do alto-falante E do fone em TODO report, e o valor que o
firmware tinha é sobrescrito. Não existe leitura desse registrador — nada pode
dizer qual era o volume antes, então nada pode restaurá-lo. `speaker release`
devolve o CONTROLE, não o valor: o firmware fica com o último número que
mandamos, e o preço acaba de qualquer forma quando o controle desconecta.

Por que `release` é a entrega obrigatória: sem ele, o primeiro uso do volume
sequestrava o alto-falante até a próxima desconexão e não havia saída sem a
janela. Por que `volume` vem junto: sem ele, um `speaker mute` pela linha de
comando cairia direto na armadilha medida — mudo como PRIMEIRA escrita tranca o
alto-falante em zero e o próprio mudo não o solta. Por isso `mute`/`unmute` aqui
têm a MESMA guarda da interface: sem volume conhecido, o pedido é recusado com o
caminho dito por extenso, e nada é mandado ao daemon.
"""
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.core.speaker_scale import (
    percentual_do_volume,
    volume_do_percentual,
)

console = Console()

#: Verbos aceitos. `volume` é o único que pede um número.
_ACOES = ("status", "volume", "mute", "unmute", "release")

#: Fim da linha de ajuda, repetido nas recusas — o texto que diz o CAMINHO.
_DICA_VOLUME = "ajuste um volume primeiro (ex.: `speaker volume 60`)"


def _pct_para_bruto(pct: int) -> int:
    """0-100 % da linha de comando -> 0-255 do protocolo.

    A conta é a MESMA da janela: as duas importam de `core/speaker_scale.py`. A
    resposta do registrador é fortemente não-linear (medida em 01/08/2026 com o
    microfone do próprio controle como instrumento), e uma régua linear aqui
    faria `speaker volume 60` e os 60 % do controle deslizante mandarem valores
    diferentes para o mesmo registrador, com resultado audível diferente. Duas
    contas para a mesma grandeza é a receita de a linha de comando contradizer
    a janela.

    A régua mora em `core/` e não junto dos widgets por dois motivos: a curva é
    propriedade do DualSense e não do desenho da tela, e `app/widgets/` puxa
    GTK no import do pacote — importá-la de lá fazia este comando carregar a
    interface gráfica inteira para escrever um byte, num ambiente que pode nem
    ter interface. Há teste travando as duas coisas.
    """
    return volume_do_percentual(pct)


def _bruto_para_pct(volume: int) -> int:
    """0-255 do protocolo -> 0-100 %, pela mesma régua remapeada da janela."""
    return percentual_do_volume(volume)


def _chamar(metodo: str, params: dict[str, Any]) -> tuple[str, Any]:
    """Fala com o daemon. Devolve ("ok", resultado) | ("offline", None) | ("erro", msg).

    Três desfechos e não dois: "o daemon não está de pé" e "o daemon recusou o
    pedido" pedem mensagens diferentes de quem está no terminal — a primeira se
    resolve subindo o daemon, a segunda lendo o motivo.
    """
    import asyncio

    from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

    async def _rodar() -> tuple[str, Any]:
        try:
            async with IpcClient.connect() as client:
                return "ok", await client.call(metodo, params)
        except IpcError as exc:
            return "erro", exc.message
        except (FileNotFoundError, ConnectionError, OSError):
            return "offline", None

    return asyncio.run(_rodar())


def _bloco_speaker(payload: Any, uniq: str | None) -> dict[str, Any] | None:
    """Acha o bloco `speaker` do controle pedido dentro do `daemon.state_full`.

    `uniq` ausente = o PRIMÁRIO, exatamente como o `speaker.set` roteia. Ausência
    da chave é resposta: significa que ninguém tomou a posse do volume ainda (ou
    que ela foi devolvida), e é o que a janela pinta como "não ajustado".
    """
    if not isinstance(payload, dict):
        return None
    for entrada in payload.get("controllers") or []:
        if not isinstance(entrada, dict):
            continue
        if uniq is not None and entrada.get("uniq") != uniq:
            continue
        if uniq is None and not entrada.get("is_primary"):
            continue
        bloco = entrada.get("speaker")
        return bloco if isinstance(bloco, dict) else None
    return None


def _imprimir_status(bloco: dict[str, Any] | None) -> None:
    """Uma linha honesta: a porcentagem que NÓS mandamos, ou "não ajustado"."""
    if bloco is None:
        console.print("  alto-falante ............. não ajustado")
        console.print(
            "  [dim]o volume é do firmware do controle e ele não o devolve; "
            "mandar um volume passa a mandá-lo em todo report[/dim]"
        )
        return
    volume = bloco.get("volume")
    volume = volume if isinstance(volume, int) else 0
    selo = "mudo" if bloco.get("muted") else f"{_bruto_para_pct(volume)} %"
    console.print(f"  alto-falante ............. {selo}")
    console.print(
        "  [dim]posse do hefesto: o valor sai em todo report até `speaker "
        "release` ou até o controle desconectar[/dim]"
    )


def speaker_cmd(
    action: str = "status",
    value: int | None = None,
    uniq: str | None = None,
) -> None:
    """Volume / mudo / devolução da posse do alto-falante do DualSense.

    `uniq` (MAC normalizado) escolhe o controle; omitido = o primário.
    """
    action = (action or "status").lower()
    if action not in _ACOES:
        console.print(
            f"[red]ação inválida: {action}[/red] — use: " + " | ".join(_ACOES)
        )
        raise typer.Exit(code=2)

    alvo: dict[str, Any] = {"uniq": uniq} if uniq else {}

    if action == "status":
        estado, payload = _chamar("daemon.state_full", {})
        if estado != "ok":
            raise typer.Exit(code=_reclamar_do_daemon(estado, payload))
        _imprimir_status(_bloco_speaker(payload, uniq))
        raise typer.Exit(code=0)

    if action == "volume":
        if value is None:
            console.print(
                "[red]falta o valor[/red] — `speaker volume <0-100>` "
                "(porcentagem; o protocolo usa 0-255 e a conversão é nossa)."
            )
            raise typer.Exit(code=2)
        if not 0 <= value <= 100:
            console.print(f"[red]volume fora de 0-100: {value}[/red]")
            raise typer.Exit(code=2)
        bruto = _pct_para_bruto(value)
        estado, resposta = _chamar("speaker.set", {"volume": bruto, **alvo})
        raise typer.Exit(code=_relatar(estado, resposta, f"volume {value} %"))

    if action == "release":
        estado, resposta = _chamar("speaker.set", {"release": True, **alvo})
        codigo = _relatar(estado, resposta, "posse devolvida")
        if codigo == 0:
            console.print(
                "  [dim]o hefesto parou de mandar o volume. O que estiver "
                "valendo continua até você desconectar o controle — não há "
                "leitura desse registrador, então não há o que restaurar.[/dim]"
            )
        raise typer.Exit(code=codigo)

    # mute / unmute — a MESMA guarda da interface (armadilha 2, medida): sem
    # volume conhecido, o mudo é a primeira escrita, tranca o alto-falante em
    # zero e o próprio comando não o solta. Recusar ANTES de mandar é a entrega:
    # o daemon também recusa, mas quem está no terminal precisa do caminho, não
    # de um código de erro.
    estado, payload = _chamar("daemon.state_full", {})
    if estado != "ok":
        raise typer.Exit(code=_reclamar_do_daemon(estado, payload))
    if _bloco_speaker(payload, uniq) is None:
        console.print(
            "[yellow]não há volume conhecido para este controle[/yellow] — "
            f"{_DICA_VOLUME}."
        )
        console.print(
            "  [dim]mudo como primeira escrita mandaria ZERO e o desmudo não "
            "teria o que restaurar (medido na SOM-02).[/dim]"
        )
        raise typer.Exit(code=1)
    mudo = action == "mute"
    estado, resposta = _chamar("speaker.set", {"muted": mudo, **alvo})
    raise typer.Exit(code=_relatar(estado, resposta, "mudo" if mudo else "ativo"))


def _reclamar_do_daemon(estado: str, mensagem: Any) -> int:
    """Mensagem única para "daemon offline" e "daemon recusou". Devolve o rc."""
    if estado == "offline":
        console.print(
            "[red]daemon offline[/red] — o volume do alto-falante só se altera "
            "pelo daemon (inicie com 'hefesto-dualsense4unix daemon start')."
        )
    else:
        console.print(f"[red]o daemon recusou o pedido[/red] — {mensagem}")
    return 1


def _relatar(estado: str, resposta: Any, pedido: str) -> int:
    """Imprime o desfecho de um `speaker.set` e devolve o código de saída."""
    if estado != "ok":
        return _reclamar_do_daemon(estado, resposta)
    if not isinstance(resposta, dict) or resposta.get("status") != "ok":
        console.print(
            "[yellow]nenhum controle recebeu o pedido[/yellow] — conecte o "
            "DualSense (ou confira o MAC passado em --uniq)."
        )
        return 1
    console.print(f"  alto-falante ............. {pedido}")
    bloco = resposta.get("speaker")
    _imprimir_status(bloco if isinstance(bloco, dict) else None)
    return 0


__all__ = ["speaker_cmd"]
