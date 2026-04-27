"""Subcomando `hefesto-dualsense4unix profile ...`.

Opera diretamente no diretório de perfis (XDG) sem falar com o daemon
em execução. Para "ativar" via daemon rodando, W4.2 adicionará uma
implementação que envia `profile.switch` via IPC; por enquanto, o
comando `activate` grava a marca de perfil ativo em um arquivo-estado
local e, se houver hardware/daemon acessível, aplica direto.

FEAT-CLI-PARITY-01: adiciona `apply --file <json>` (carrega JSON, valida
via pydantic, salva e ativa via IPC/hardware) e `save <nome>
--from-active` (clona o perfil marcado como ativo para um novo nome).
"""
from __future__ import annotations

import json as _json
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from hefesto_dualsense4unix.cli.ipc_client import IpcError
from hefesto_dualsense4unix.profiles.loader import (
    delete_profile,
    load_all_profiles,
    load_profile,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    Match,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)

app = typer.Typer(name="profile", help="Gerencia perfis Hefesto - Dualsense4Unix.", no_args_is_help=True)  # noqa: E501
console = Console()


@app.command("list")
def cmd_list() -> None:
    """Lista perfis no diretório XDG."""
    profiles = load_all_profiles()
    if not profiles:
        console.print("[dim]nenhum perfil encontrado[/dim]")
        return

    table = Table(title="Perfis Hefesto - Dualsense4Unix")
    table.add_column("Nome", style="cyan")
    table.add_column("Prioridade", justify="right")
    table.add_column("Match", style="magenta")
    table.add_column("Triggers", style="yellow")

    for p in profiles:
        match_desc = _describe_match(p)
        triggers_desc = f"L={p.triggers.left.mode} R={p.triggers.right.mode}"
        table.add_row(p.name, str(p.priority), match_desc, triggers_desc)

    console.print(table)


@app.command("show")
def cmd_show(name: str) -> None:
    """Mostra o JSON bruto de um perfil."""
    try:
        profile = load_profile(name)
    except FileNotFoundError:
        console.print(f"[red]perfil não encontrado: {name}[/red]")
        raise typer.Exit(code=1) from None
    console.print_json(data=profile.model_dump(mode="json"))


@app.command("activate")
def cmd_activate(name: str) -> None:
    """Marca perfil como ativo. Aplica direto no controle se hardware disponível."""
    try:
        profile = load_profile(name)
    except FileNotFoundError:
        console.print(f"[red]perfil não encontrado: {name}[/red]")
        raise typer.Exit(code=1) from None

    try:
        from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
        from hefesto_dualsense4unix.profiles.manager import ProfileManager

        controller = PyDualSenseController()
        controller.connect()
        manager = ProfileManager(controller=controller)
        manager.apply(profile)
        controller.disconnect()
        console.print(f"[green]perfil aplicado no controle: {name}[/green]")
    except Exception as exc:
        console.print(
            f"[yellow]perfil não aplicado (hardware não detectado): {exc}[/yellow]"
        )

    _write_active_marker(name)


@app.command("create")
def cmd_create(
    name: str = typer.Argument(..., help="Nome do perfil."),
    priority: int = typer.Option(5, help="Prioridade para resolução de match."),
    match_regex: str | None = typer.Option(None, help="Regex contra wm_name."),
    match_class: list[str] = typer.Option(  # noqa: B008
        default_factory=list, help="Window class (repetir para multiplos)."
    ),
    match_exe: list[str] = typer.Option(  # noqa: B008
        default_factory=list, help="Basename de exe (repetir)."
    ),
    fallback: bool = typer.Option(False, "--fallback", help="Perfil com MatchAny (prioridade 0)."),
) -> None:
    """Cria um perfil mínimo (triggers Off, leds apagados). Edite o JSON depois."""
    match: Match
    if fallback:
        match = MatchAny()
        priority = 0
    else:
        match = MatchCriteria(
            window_class=match_class or [],
            window_title_regex=match_regex,
            process_name=match_exe or [],
        )

    profile = Profile(
        name=name,
        match=match,
        priority=priority,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Off"),
        ),
        leds=LedsConfig(lightbar=(0, 0, 0)),
    )
    path = save_profile(profile)
    console.print(f"[green]perfil criado: {path}[/green]")


@app.command("delete")
def cmd_delete(
    name: str,
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirma delete."),
) -> None:
    """Remove um perfil."""
    if not yes:
        typer.confirm(f"Deletar perfil {name!r}?", abort=True)
    try:
        delete_profile(name)
        console.print(f"[green]perfil deletado: {name}[/green]")
    except FileNotFoundError:
        console.print(f"[red]perfil não encontrado: {name}[/red]")
        raise typer.Exit(code=1) from None


@app.command("apply")
def cmd_apply(
    file: Path = typer.Option(  # noqa: B008
        ..., "--file", "-f", exists=True, readable=True, dir_okay=False,
        help="Caminho para um JSON de perfil (mesmo schema de `profile show`).",
    ),
    save: bool = typer.Option(
        True, "--save/--no-save",
        help="Se gravar o perfil no diretório XDG antes de ativar (default: sim).",
    ),
) -> None:
    """Valida um JSON de perfil, salva no disco e ativa via daemon (se online).

    Útil para aplicar drafts exportados pela GUI ou gerados por scripts.
    Em `--no-save`, o perfil é validado mas NÃO persistido — apenas o
    JSON de origem é usado, e a ativação requer que o perfil JÁ exista
    no XDG com o mesmo `name` (caso contrário, exit 1).
    """
    try:
        raw = _json.loads(file.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError) as exc:
        console.print(f"[red]falha ao ler JSON:[/red] {exc}")
        raise typer.Exit(code=1) from None

    try:
        profile = Profile.model_validate(raw)
    except ValidationError as exc:
        console.print(f"[red]JSON não valida contra schema do perfil:[/red]\n{exc}")
        raise typer.Exit(code=1) from None

    if save:
        path = save_profile(profile)
        console.print(f"[green]perfil salvo:[/green] {path}")
    else:
        # Sem gravar: só garante que existe no XDG para o profile.switch pegar.
        try:
            load_profile(profile.name)
        except FileNotFoundError:
            console.print(
                f"[red]--no-save exige perfil ja presente no XDG:[/red] "
                f"{profile.name!r} não encontrado."
            )
            raise typer.Exit(code=1) from None

    _activate_via_ipc_or_fallback(profile.name)


@app.command("save")
def cmd_save(
    name: str = typer.Argument(..., help="Nome do novo perfil a criar."),
    from_active: bool = typer.Option(
        False, "--from-active",
        help="Clona o perfil ativo (marker XDG) com o novo nome.",
    ),
) -> None:
    """Cria um perfil clonando o ativo (snapshot do que está em uso)."""
    if not from_active:
        console.print(
            "[red]profile save requer --from-active[/red] "
            "(clone de outro perfil pelo nome chega em sprint futura)."
        )
        raise typer.Exit(code=2)

    active_name = read_active_marker()
    if active_name is None:
        console.print(
            "[red]nenhum perfil ativo marcado.[/red] "
            "Rode `hefesto-dualsense4unix profile activate <nome>` antes."
        )
        raise typer.Exit(code=1)

    try:
        source = load_profile(active_name)
    except FileNotFoundError:
        console.print(
            f"[red]perfil ativo ausente no disco:[/red] {active_name}"
        )
        raise typer.Exit(code=1) from None

    # Clone imutável via pydantic: serializa, troca o nome, revalida.
    payload = source.model_dump(mode="json")
    payload["name"] = name
    try:
        clone = Profile.model_validate(payload)
    except ValidationError as exc:
        console.print(f"[red]falha ao clonar perfil:[/red] {exc}")
        raise typer.Exit(code=1) from None

    path = save_profile(clone)
    console.print(
        f"[green]perfil clonado:[/green] {active_name} -> {name} ({path})"
    )


def _activate_via_ipc_or_fallback(name: str) -> None:
    """Tenta `profile.switch` no daemon; em falha, grava marker e avisa.

    Mantido em função isolada para reuso em `apply`. Mensagens claras
    (sem traceback) para todos os modos de falha.
    """
    # Import adiado para não pagar custo de asyncio/socket em `profile list`.
    from hefesto_dualsense4unix.app.ipc_bridge import _run_call

    try:
        _run_call("profile.switch", {"name": name}, timeout=1.0)
        console.print(f"[green]perfil ativado via daemon:[/green] {name}")
        _write_active_marker(name)
        return
    except IpcError as exc:
        console.print(f"[yellow]daemon recusou profile.switch:[/yellow] {exc.message}")
    except (FileNotFoundError, ConnectionError, OSError):
        console.print(
            "[yellow]daemon offline — gravando marker local apenas.[/yellow]"
        )

    _write_active_marker(name)
    console.print(
        f"[dim]marker local atualizado: próxima inicialização do daemon usara '{name}'[/dim]"
    )


def _describe_match(profile: Profile) -> str:
    m = profile.match
    if isinstance(m, MatchAny):
        return "[dim]any[/dim]"
    parts: list[str] = []
    if m.window_class:
        parts.append(f"class={','.join(m.window_class)}")
    if m.window_title_regex:
        parts.append(f"title~={m.window_title_regex}")
    if m.process_name:
        parts.append(f"exe={','.join(m.process_name)}")
    return " ".join(parts) if parts else "[dim]vazio[/dim]"


def _write_active_marker(name: str) -> None:
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir

    marker = config_dir(ensure=True) / "active_profile.txt"
    marker.write_text(name + "\n", encoding="utf-8")


def read_active_marker() -> str | None:
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir

    marker = config_dir() / "active_profile.txt"
    if not marker.exists():
        return None
    content = marker.read_text(encoding="utf-8").strip()
    return content or None


__all__ = ["app", "read_active_marker"]
