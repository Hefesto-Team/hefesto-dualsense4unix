"""Subcomandos `hefesto-dualsense4unix status` e `hefesto-dualsense4unix battery`."""
from __future__ import annotations

import contextlib
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from hefesto_dualsense4unix.utils import identidade

console = Console()

_ROTULOS_DE_CAMPO: dict[str, str] = {
    "active_profile": "active_profile (em vigor agora)",
}


class DaemonNaoRespondeuError(RuntimeError):
    """O serviço aceitou a conexão e não respondeu no prazo (parado ou travado)."""


def _daemon_status_via_ipc() -> dict[str, Any] | None:
    """O ``daemon.state_full``; ``None`` só com o serviço comprovadamente parado.

    Serviço que ATENDE a conexão e não responde não é «fora do ar»: levanta
    :class:`DaemonNaoRespondeuError`, e quem chama diz isso (e não abre o aparelho,
    que o serviço travado ainda segura). Serviço que recusa sai com o motivo, rc 2.
    """
    from hefesto_dualsense4unix.app.ipc_bridge import ATENDEU, MUDO, pedir_ao_servico
    from hefesto_dualsense4unix.cli.chamada_ao_servico import sair_se_o_servico_vive

    desfecho = pedir_ao_servico("daemon.state_full")
    if desfecho.estado == MUDO:
        raise DaemonNaoRespondeuError(desfecho.motivo)
    sair_se_o_servico_vive(console, desfecho)
    if desfecho.estado == ATENDEU and isinstance(desfecho.corpo, dict):
        return desfecho.corpo
    return None


def _status_ou_sair() -> dict[str, Any] | None:
    """O status do serviço, ou ``None`` fora do ar; serviço mudo sai com rc 1."""
    try:
        return _daemon_status_via_ipc()
    except DaemonNaoRespondeuError as exc:
        console.print(f"[red]{exc}[/red] — confira o serviço: `hefesto-dualsense4unix doctor`")
        raise typer.Exit(code=1) from exc


def _os_controles(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Os controles conectados, na lista que o `controller list` lê (`daemon.state_full`).

    Daemon que não publica a lista, e a leitura direta do aparelho, trazem um controle só, no topo.
    """
    lista = data.get("controllers")
    if isinstance(lista, list):
        return [c for c in lista if isinstance(c, dict) and c.get("connected")]
    return [data] if data.get("connected") else []


def _o_controle_em_dados(controle: dict[str, Any], posicao: int) -> dict[str, Any]:
    """Um controle como a linha e o JSON o mostram: número, cor do plástico, transporte e carga."""
    from hefesto_dualsense4unix.cli.cmd_controller import _numero_exibido

    nome = controle.get("nome_declarado") or controle.get("modelo")
    transporte = controle.get("transport")
    return {
        "numero": _numero_exibido(controle) if "index" in controle else posicao,
        "nome": nome if isinstance(nome, str) and nome.strip() else None,
        "transporte": str(transporte).upper() if transporte else None,
        "bateria": controle.get("battery_pct"),
        "estado_da_bateria": controle.get("battery_state"),
    }


def _os_dados_dos_controles(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [_o_controle_em_dados(c, i) for i, c in enumerate(_os_controles(data), start=1)]


def _o_rotulo(dados: dict[str, Any]) -> str:
    nome = f" ({dados['nome']})" if dados["nome"] else ""
    return f"Controle {dados['numero']}{nome}"


def status_cmd(como_json: bool = False) -> None:
    """Uma linha por controle conectado (cor do plástico, transporte, bateria) e o perfil."""
    data = _status_ou_sair()
    if data is None:
        if not como_json:
            console.print("[yellow]daemon offline — mostrando leitura direta do hardware[/yellow]")
        data = _fallback_hardware_read()
    controles = _os_dados_dos_controles(data)
    perfil = data.get("active_profile")
    if como_json:
        console.print_json(data={"active_profile": perfil, "controllers": controles})
        return

    table = Table(title=f"{identidade.atual().nome_longo} — Status")
    table.add_column("Campo", style="cyan")
    table.add_column("Valor")
    table.add_row(
        _ROTULOS_DE_CAMPO["active_profile"], str(perfil) if perfil is not None else "[dim]n/d[/dim]"
    )
    if not controles:
        table.add_row("controles", "[dim]nenhum conectado[/dim]")
    for dados in controles:
        bateria = f"{dados['bateria']}%" if dados["bateria"] is not None else "n/d"
        table.add_row(_o_rotulo(dados), f"{dados['transporte'] or 'n/d'} — bateria {bateria}")
    console.print(table)


def battery_cmd(como_json: bool = False) -> None:
    """A bateria de cada controle conectado, uma linha por controle."""
    data = _status_ou_sair()
    if data is None:
        data = _fallback_hardware_read()
    controles = _os_dados_dos_controles(data)
    if como_json:
        console.print_json(data={"controllers": controles})
        return
    if not controles:
        console.print("[red]nenhum controle ao alcance[/red]")
        raise typer.Exit(code=1)
    for dados in controles:
        bateria = dados["bateria"]
        if bateria is None:
            console.print(f"{_o_rotulo(dados)}: [red]bateria desconhecida[/red]")
            continue
        cor = "green" if bateria > 40 else "yellow" if bateria > 15 else "red"
        console.print(f"{_o_rotulo(dados)}: [{cor}]{bateria}%[/{cor}]")
    if all(dados["bateria"] is None for dados in controles):
        raise typer.Exit(code=1)


def _fallback_hardware_read() -> dict[str, Any]:
    """A leitura direta do aparelho. Sem controle aberto, devolve ``None`` em tudo o que
    o aparelho diria: o backend de um posto vago responde bateria 0 e transporte USB,
    e repassar isso seria inventar um controle."""
    sem_controle: dict[str, Any] = {
        "connected": False, "transport": None, "active_profile": None, "battery_pct": None,
    }
    try:
        from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

        controller = PyDualSenseController()
        controller.connect()
        try:
            if not controller.is_connected():
                return sem_controle
            state = controller.read_state()
            return {
                "connected": state.connected,
                "transport": state.transport,
                "active_profile": None,
                "battery_pct": state.battery_pct,
            }
        finally:
            with contextlib.suppress(Exception):
                controller.disconnect()
    except Exception as exc:
        console.print(f"[red]sem controle disponivel: {exc}[/red]")
        return sem_controle


__all__ = ["DaemonNaoRespondeuError", "battery_cmd", "status_cmd"]
