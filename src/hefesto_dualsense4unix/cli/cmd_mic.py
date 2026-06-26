"""Subcomando `hefesto-dualsense4unix mic on|off|status`.

Liga/desliga o microfone embutido do DualSense reusando
`scripts/fix_wireplumber_default_source.sh` (mesma lógica do install/doctor):

- on     -> --enable-mic     (remove os drop-ins de supressão 51/52/53; mic livre)
- off    -> --disable-source (instala 52/53; mic do controle some, sem spam)
- status -> --status

A supressão por default é OFF do ponto de vista do mic (o install instala 52/53),
então "ligar quando precisar" é `mic on`. Pensado para a GUI e o applet COSMIC
acionarem o mesmo caminho do CLI. FEAT-DUALSENSE-MIC-TOGGLE-01.
"""
from __future__ import annotations

import subprocess
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
    """Liga (on) / desliga (off) / consulta (status) o mic do DualSense."""
    action = action.lower()
    flag = _ACTION_FLAG.get(action)
    if flag is None:
        console.print(
            f"[red]ação inválida: {action}[/red] — use: on | off | status"
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


__all__ = ["mic_cmd"]
