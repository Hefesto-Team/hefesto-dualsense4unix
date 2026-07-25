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
"""
from __future__ import annotations

import contextlib
import signal
import subprocess
import threading
from pathlib import Path

import typer
from rich.console import Console

console = Console()

_SCRIPT_NAME = "fix_wireplumber_default_source.sh"
_ACTION_FLAG = {
    "on": "--enable-mic",
    "off": "--disable-source",
    "status": "--status",
}

#: Ações que NÃO passam pelo script do WirePlumber (são a ponte por BT).
_ACOES_BT = ("bt", "bt-status")

#: Cadência da reconciliação de hotplug do `mic bt`. Não é polling de dados —
#: o áudio flui numa thread bloqueada no hidraw; isto só pergunta ao sysfs se
#: apareceu/sumiu controle, e o laço DORME num Event entre uma e outra.
_RECONCILIA_S = 5.0


def _find_script() -> Path | None:
    """Localiza o script do WirePlumber em layouts conhecidos (editable e .deb)."""
    candidates = [
        Path(__file__).resolve().parents[3] / "scripts" / _SCRIPT_NAME,
        Path("/usr/share/hefesto-dualsense4unix/scripts") / _SCRIPT_NAME,
        Path("/usr/local/share/hefesto-dualsense4unix/scripts") / _SCRIPT_NAME,
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def mic_cmd(action: str = "status") -> None:
    """Liga (on) / desliga (off) / consulta (status) o mic do DualSense.

    `bt` sobe a ponte do microfone por Bluetooth; `bt-status` diagnostica.
    """
    action = action.lower()
    if action in _ACOES_BT:
        raise typer.Exit(code=_mic_bt(status_apenas=action == "bt-status"))

    flag = _ACTION_FLAG.get(action)
    if flag is None:
        console.print(
            f"[red]ação inválida: {action}[/red] — use: on | off | status | bt | bt-status"
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


# ---------------------------------------------------------------------------
# Microfone por Bluetooth (BT-MIC-01)
# ---------------------------------------------------------------------------


def _mic_bt(*, status_apenas: bool) -> int:
    """Diagnostica (e opcionalmente sobe) a ponte do mic por BT. Devolve o rc.

    Import tardio de propósito: `mic on/off/status` não pode passar a depender
    de nada que a ponte carrega (ctypes/libopus), e o CLI inteiro não pode
    ficar mais lento por causa de um subcomando.
    """
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
        GerenciadorMicBluetooth,
        diagnosticar,
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

    if not diag.pronto:
        for falta in diag.impedimentos:
            console.print(f"  [yellow]![/yellow] {falta}")
        # Falta de controle em BT não é erro do programa: é o estado normal de
        # quem está no cabo. Só o que a usuária pode CONSERTAR vira rc != 0.
        return 0 if not diag.controles and diag.libopus and diag.pactl else 1
    if status_apenas:
        console.print("\n  pronto — `hefesto-dualsense4unix mic bt` sobe a ponte.")
        return 0

    gerenciador = GerenciadorMicBluetooth()
    parar = threading.Event()

    def _sinal(_sig: int, _frm: object) -> None:
        parar.set()
        gerenciador.parar()

    # SIGINT/SIGTERM param a ponte pelo MESMO caminho do Ctrl-C: o `parar()`
    # manda o 0x32 de desligar em cada controle. Sair sem isso deixaria o
    # microfone de alguém ligado — o pior fim possível para este comando.
    for sig in (signal.SIGINT, signal.SIGTERM):
        # `signal.signal` levanta ValueError fora da thread principal.
        with contextlib.suppress(ValueError):
            signal.signal(sig, _sinal)

    console.print("\n  subindo a ponte… (Ctrl-C encerra e desliga o mic)\n")
    # Legenda do "sem-ouvinte": enquanto NENHUM app estiver gravando, o
    # PipeWire deixa a source suspensa e não drena o fifo — a ponte descarta os
    # quadros em vez de bloquear (é a invariante do módulo). Ver ~100% de
    # descarte com o medidor parado é o comportamento CERTO, não uma falha; o
    # número cai para perto de zero assim que alguém abre o microfone.
    console.print(
        "  [dim]sem-ouvinte = quadros descartados porque nenhum app está "
        "gravando (esperado)[/dim]\n"
    )
    try:
        while not parar.is_set():
            gerenciador.reconciliar()
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
