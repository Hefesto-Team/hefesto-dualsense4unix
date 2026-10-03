"""Subcomando `hefesto-dualsense4unix mic on|off|status|bt|bt-status`.

Dois microfones diferentes moram aqui, e a diferença é de TRANSPORTE:

**No cabo** o mic do DualSense é um dispositivo de áudio USB comum — o
PipeWire o publica sozinho e o trabalho é só de POLÍTICA (deixar ou não que
ele vire a entrada padrão do sistema). É o que `on`/`off`/`status` fazem,
reusando `scripts/fix_wireplumber_default_source.sh` (mesma lógica do
install/doctor):

- on     -> --enable-mic     (remove os drop-ins de supressão 51/52/53; mic livre)
- off    -> --disable-source (instala 52/53; mic do controle some, sem spam)
- status -> --status

A supressão por default é OFF do ponto de vista do mic (o install instala 52/53),
então "ligar quando precisar" é `mic on`. Pensado para a GUI e o applet COSMIC
acionarem o mesmo caminho do CLI. FEAT-DUALSENSE-MIC-TOGGLE-01.

**Em Bluetooth não existe fonte de áudio nenhuma para o PipeWire publicar**: o
DualSense não fala A2DP/HFP/HSP e manda o áudio como Opus dentro dos reports
HID. Aí não há política a ajustar — é preciso IMPLEMENTAR o transporte. É o que
`bt` faz, subindo a ponte de `integrations/dualsense_bt_audio.py` (BT-MIC-01);
`bt-status` mostra as pré-condições sem mexer em nada.

MIC-USB-01 (25/07) — AS TRÊS CAMADAS DE MUDO. Medido ao vivo com o controle no
cabo: o microfone estava mudo por três motivos empilhados, em três donos
diferentes, e cada cura revelava o de baixo. Este módulo agora alcança os três:

1. **rota do WirePlumber** — `mute:true` persistido por ROTA de placa em
   `~/.local/state/wireplumber/default-routes`, restaurado a cada conexão sem
   nada no log. Cura: `scripts/doctor.sh --fix` (ou `--enable-mic` aqui);
2. **perfil da placa** — preso em `input:iec958-stereo` (capta: o «sem sinal» de
   25/07 era o mudo do firmware), porque o WirePlumber marca a analógica indisponível
   sem fone plugado. Mas o mic EMBUTIDO usa esse caminho (no mixer ALSA o
   controle de captura se chama `Headset`). Cura: `scripts/doctor.sh --fix`;
3. **firmware do controle** — o mesmo estado que o botão físico de mic alterna
   e que acende o LED. Cura: `mute`/`unmute`/`release` daqui, pelo `mic.set` do
   IPC. Até esta sprint só o botão físico o alcançava.

`promote`/`demote` são de uma quarta pergunta, que não é de mudo e sim de
POLÍTICA: quem é o microfone PADRÃO do sistema.
"""
from __future__ import annotations

import contextlib
import signal
import subprocess
import threading
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.utils.repo_files import encontrar_arquivo_do_repo

console = Console()

_SCRIPT_NAME = "fix_wireplumber_default_source.sh"
_ACTION_FLAG = {
    "on": "--enable-mic",
    "off": "--disable-source",
    "status": "--status",
    # para o DualSense não ser eleito sozinho — o que é correto e nunca foi o
    "promote": "--promote-source",
    "demote": "--install",
}

_ACOES_FIRMWARE: dict[str, bool | None] = {
    "mute": True,
    "unmute": False,
    "release": None,
}

_ACOES_LED: dict[str, bool | None] = {
    "led-on": True,
    "led-off": False,
    "led-release": None,
}

#: Ações que NÃO passam pelo script do WirePlumber (são a ponte por BT).
_ACOES_BT = ("bt", "bt-status")

_RECONCILIA_S = 5.0


def _find_script() -> Path | None:
    """Localiza o script do WirePlumber."""
    return encontrar_arquivo_do_repo(f"scripts/{_SCRIPT_NAME}")


def mic_cmd(action: str = "status", uniq: str | None = None) -> None:
    """Liga (on) / desliga (off) / consulta (status) o mic do DualSense.

    `bt` sobe a ponte do microfone por Bluetooth; `bt-status` diagnostica.
    `mute`/`unmute`/`release` mexem no mudo do FIRMWARE do controle
    (MIC-USB-01, camada 3); `led-on`/`led-off`/`led-release` mexem no LED do
    botão de mudo, que é OUTRO byte e não muta nada (MIC-DA-MESA-ELEICAO-01);
    `promote`/`demote` na política de microfone padrão.
    `uniq` (MAC normalizado) escolhe o controle nas ações de firmware.
    """
    action = action.lower()
    if action in _ACOES_BT:
        raise typer.Exit(code=_mic_bt(status_apenas=action == "bt-status"))
    if action in _ACOES_FIRMWARE:
        raise typer.Exit(code=_mic_firmware(_ACOES_FIRMWARE[action], uniq=uniq))
    if action in _ACOES_LED:
        raise typer.Exit(code=_mic_led(_ACOES_LED[action], uniq=uniq))

    flag = _ACTION_FLAG.get(action)
    if flag is None:
        console.print(
            f"[red]ação inválida: {action}[/red] — use: on | off | status | "
            "promote | demote | mute | unmute | release | "
            "led-on | led-off | led-release | bt | bt-status"
        )
        raise typer.Exit(code=2)

    script = _find_script()
    if script is None:
        console.print(
            f"[red]{_SCRIPT_NAME} não encontrado[/red] — reinstale ou rode o script "
            "manualmente."
        )
        raise typer.Exit(code=1)

    rc = subprocess.run(["bash", str(script), flag], check=False).returncode
    # disable-source devolve 2 quando o DualSense é a única fonte (aviso, não falha).
    if action == "off" and rc == 2:
        rc = 0
    raise typer.Exit(code=rc)


def _mic_led(aceso: bool | None, *, uniq: str | None = None) -> int:
    """Manda `mic.led.set` ao daemon (MIC-DA-MESA-ELEICAO-01)."""
    import asyncio

    from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

    payload: dict[str, object] = {"aceso": aceso}
    if uniq:
        payload["uniq"] = uniq

    async def _chamar() -> dict[str, object] | None:
        try:
            async with IpcClient.connect() as client:
                resposta = await client.call("mic.led.set", payload)
        except (FileNotFoundError, ConnectionError, IpcError, OSError):
            return None
        return resposta if isinstance(resposta, dict) else {}

    resultado = asyncio.run(_chamar())
    if resultado is None:
        console.print(
            "[red]daemon offline[/red] — o LED do microfone só se altera pelo "
            "daemon (inicie com 'hefesto-dualsense4unix daemon start')."
        )
        return 1
    if resultado.get("status") != "ok":
        console.print(
            "[yellow]nenhum controle recebeu o pedido[/yellow] — conecte o "
            "DualSense (ou confira o MAC passado em uniq)."
        )
        return 1
    pedido = {
        True: "ACESO (este microfone está vivo)",
        False: "apagado",
        None: "posse devolvida ao kernel (repintada com o mudo de fato antes)",
    }[aceso]
    console.print(f"  LED do microfone ......... {pedido}")
    return 0


def _mic_firmware(muted: bool | None, *, uniq: str | None = None) -> int:
    """Manda `mic.set` ao daemon e imprime o que o controle passou a declarar."""
    import asyncio

    from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

    payload: dict[str, object] = {"muted": muted}
    if uniq:
        payload["uniq"] = uniq

    async def _chamar() -> dict[str, object] | None:
        try:
            async with IpcClient.connect() as client:
                resposta = await client.call("mic.set", payload)
        except (FileNotFoundError, ConnectionError, IpcError, OSError):
            return None
        return resposta if isinstance(resposta, dict) else {}

    resultado = asyncio.run(_chamar())
    if resultado is None:
        console.print(
            "[red]daemon offline[/red] — o mudo do firmware só se altera pelo "
            "daemon (inicie com 'hefesto-dualsense4unix daemon start'), ou "
            "aperte o botão de microfone do controle."
        )
        return 1
    if resultado.get("status") != "ok":
        console.print(
            "[yellow]nenhum controle recebeu o pedido[/yellow] — conecte o "
            "DualSense (ou confira o MAC passado em uniq)."
        )
        return 1

    pedido = {True: "MUDO", False: "ATIVO", None: "posse devolvida ao kernel"}[muted]
    console.print(f"  microfone do firmware .... {pedido}")
    audio = resultado.get("audio")
    if isinstance(audio, dict):
        declarado = audio.get("mic_mudo")
        selo = "MUDO" if declarado else "ativo"
        console.print(f"  o controle declara ....... {selo}")
        if declarado:
            console.print(
                "  [dim]ainda mudo? o firmware pode levar um report para "
                "convergir. Se o medidor seguir parado, o resto é WirePlumber: "
                "rode `scripts/doctor.sh --fix`.[/dim]"
            )
    else:
        console.print(
            "  [dim]o controle ainda não entregou um report de estado — o selo "
            "aparece no próximo tick.[/dim]"
        )
    return 0


# O estudo «O-PS-PRESO» de 16/08/2026 mediu um DualSense
# desde 23/08: `daemon.state_full` → `bt_mic.uniqs`, os `uniq` cuja ponte SUBIU.


_SEM_DAEMON = "sem-daemon"
_DAEMON_VELHO = "velho"
_DAEMON_RESPONDE = "ok"


def _pontes_ja_de_pe() -> tuple[frozenset[str], str]:
    """Quem JÁ tem ponte de microfone de pé, pela régua do daemon."""
    import asyncio

    from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

    async def _chamar() -> dict[str, object] | None:
        try:
            async with IpcClient.connect() as client:
                resposta = await client.call("daemon.state_full")
        except (FileNotFoundError, ConnectionError, IpcError, OSError):
            return None
        return resposta if isinstance(resposta, dict) else {}

    estado = asyncio.run(_chamar())
    if estado is None:
        return frozenset(), _SEM_DAEMON
    return _ler_bloco_bt_mic(estado)


def _ler_bloco_bt_mic(estado: dict[str, object]) -> tuple[frozenset[str], str]:
    """A leitura pura do bloco `bt_mic` do `state_full` — sem IPC, testável."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    bloco = estado.get("bt_mic")
    if not isinstance(bloco, dict):
        return frozenset(), _DAEMON_VELHO
    uniqs = bloco.get("uniqs")
    if isinstance(uniqs, list):
        return frozenset(
            n for n in (norm_mac(str(u)) or "" for u in uniqs) if n
        ), _DAEMON_RESPONDE
    if not bloco.get("running"):
        return frozenset(), _DAEMON_RESPONDE
    return frozenset(), _DAEMON_VELHO


def _livres(nos: list[Any], ja_de_pe: frozenset[str]) -> tuple[list[Any], list[Any]]:
    """Reparte os nós em `(livres, tomados)` pelo conjunto do daemon."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    livres: list[Any] = []
    tomados: list[Any] = []
    for no in nos:
        uniq = norm_mac(str(getattr(no, "uniq", ""))) or ""
        (tomados if uniq and uniq in ja_de_pe else livres).append(no)
    return livres, tomados


def _mic_bt(*, status_apenas: bool) -> int:
    """Diagnostica (e opcionalmente sobe) a ponte do mic por BT. Devolve o rc."""
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
        GerenciadorMicBluetooth,
        diagnosticar,
        nos_dualsense_bluetooth,
    )

    diag = diagnosticar()
    console.print("[bold]Microfone do DualSense por Bluetooth[/bold]")
    console.print(
        f"  libopus ............ {diag.libopus or '[red]ausente[/red]'}\n"
        f"  pactl .............. {'ok' if diag.pactl else '[red]ausente[/red]'}\n"
        f"  module-pipe-source . {'ok' if diag.pipe_source else '[red]ausente[/red]'}\n"
        f"  broker de hidraw ... {'ok' if diag.broker else 'ausente (usa os.open)'}"
    )
    if diag.controles:
        for no in diag.controles:
            console.print(f"  controle BT ........ {no.caminho}  {no.uniq}")
    else:
        console.print("  controle BT ........ [yellow]nenhum[/yellow]")

    ja_de_pe, situacao = _pontes_ja_de_pe()
    if situacao == _DAEMON_VELHO:
        console.print(
            "  pontes do daemon ... [yellow]não sei[/yellow] (o daemon vivo não "
            "publica `bt_mic.uniqs`)"
        )
    elif ja_de_pe:
        console.print(f"  pontes do daemon ... {', '.join(sorted(ja_de_pe))}")
    else:
        console.print("  pontes do daemon ... nenhuma")

    if not diag.pronto:
        for falta in diag.impedimentos:
            console.print(f"  [yellow]![/yellow] {falta}")
        return 0 if not diag.controles and diag.libopus and diag.pactl else 1
    if status_apenas:
        console.print("\n  pronto — `hefesto-dualsense4unix mic bt` sobe a ponte.")
        return 0

    if situacao == _DAEMON_VELHO:
        console.print(
            "\n[red]não subo a ponte[/red] — o daemon está de pé e não diz de "
            "quem são as pontes que ele segura.\n"
            "  Por quê: subir a segunda ponte no mesmo controle põe DOIS donos "
            "no report 0x32, que foi o que travou um DualSense em 16/08/2026.\n"
            "  O que fazer: reinicie o daemon sobre esta versão "
            "(`hefesto-dualsense4unix daemon restart`) e rode de novo — daí ele "
            "publica `bt_mic.uniqs` e esta régua enxerga."
        )
        return 1

    livres, tomados = _livres(diag.controles, ja_de_pe)
    for no in tomados:
        console.print(
            f"  [dim]pulo {no.uniq}: o daemon já segura a ponte dele[/dim]"
        )
    if not livres:
        console.print(
            "\n[yellow]nada a fazer[/yellow] — todo controle em BT já tem ponte "
            "de microfone de pé, e quem a segura é o daemon.\n"
            "  Por quê: uma segunda ponte no mesmo controle seria um segundo "
            "dono do report 0x32.\n"
            "  O que fazer: para desligar, use o interruptor do card na aba "
            "Configurações — quem subiu é quem derruba."
        )
        return 0

    gerenciador = GerenciadorMicBluetooth()
    parar = threading.Event()

    def _sinal(_sig: int, _frm: object) -> None:
        parar.set()
        gerenciador.parar()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(ValueError):
            signal.signal(sig, _sinal)

    console.print("\n  subindo a ponte… (Ctrl-C encerra e desliga o mic)\n")
    console.print(
        "  [dim]sem-ouvinte = quadros descartados porque nenhum app está "
        "gravando (esperado)[/dim]\n"
    )
    try:
        while not parar.is_set():
            de_pe, agora = _pontes_ja_de_pe()
            if agora == _DAEMON_VELHO:
                console.print(
                    "  [yellow]o daemon parou de dizer de quem são as pontes — "
                    "encerro para não virar o segundo dono do 0x32[/yellow]"
                )
                break
            alvos, _ = _livres(nos_dualsense_bluetooth(), de_pe)
            gerenciador.reconciliar(alvos)
            pontes = gerenciador.pontes
            if not pontes:
                console.print("  [yellow]nenhuma ponte de pé[/yellow]")
            for ponte in pontes.values():
                st = ponte.estatistica()
                selo = "MUDO" if st.mudo else "ativo"
                entregues = max(0, st.quadros_audio - st.quadros_descartados)
                console.print(
                    f"  [green]{st.source}[/green]  {selo}  "
                    f"quadros={st.quadros_audio} entregues={entregues} "
                    f"sem-ouvinte={st.quadros_descartados} "
                    f"invalidos={st.quadros_invalidos} rearmes={st.rearmes} "
                    f"mudo={st.mudo_pct:.0f}%"
                )
            if gerenciador.dormir(_RECONCILIA_S):
                break
    finally:
        gerenciador.parar()
        console.print("\n  ponte encerrada; microfone devolvido ao estado anterior.")
    return 0


__all__ = ["mic_cmd"]
