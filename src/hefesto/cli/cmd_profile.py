"""Subcomando `hefesto profile ...`.

Opera diretamente no diretório de perfis (XDG) sem falar com o daemon
em execução. Para "ativar" via daemon rodando, W4.2 adicionará uma
implementação que envia `profile.switch` via IPC; por enquanto, o
comando `activate` grava a marca de perfil ativo em um arquivo-estado
local e, se houver hardware/daemon acessível, aplica direto.
"""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from hefesto.profiles.loader import (
    delete_profile,
    load_all_profiles,
    load_profile,
    save_profile,
)
from hefesto.profiles.schema import (
    LedsConfig,
    Match,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)

app = typer.Typer(name="profile", help="Gerencia perfis Hefesto.", no_args_is_help=True)
console = Console()


@app.command("list")
def cmd_list() -> None:
    """Lista perfis no diretório XDG."""
    profiles = load_all_profiles()
    if not profiles:
        console.print("[dim]nenhum perfil encontrado[/dim]")
        return

    table = Table(title="Perfis Hefesto")
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
        console.print(f"[red]perfil nao encontrado: {name}[/red]")
        raise typer.Exit(code=1) from None
    console.print_json(data=profile.model_dump(mode="json"))


@app.command("activate")
def cmd_activate(name: str) -> None:
    """Marca perfil como ativo. Aplica direto no controle se hardware disponível."""
    try:
        profile = load_profile(name)
    except FileNotFoundError:
        console.print(f"[red]perfil nao encontrado: {name}[/red]")
        raise typer.Exit(code=1) from None

    try:
        from hefesto.core.backend_pydualsense import PyDualSenseController
        from hefesto.profiles.manager import ProfileManager

        controller = PyDualSenseController()
        controller.connect()
        manager = ProfileManager(controller=controller)
        manager.apply(profile)
        controller.disconnect()
        console.print(f"[green]perfil aplicado no controle: {name}[/green]")
    except Exception as exc:
        console.print(
            f"[yellow]perfil nao aplicado (hardware nao detectado): {exc}[/yellow]"
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
    """Cria um perfil minimo (triggers Off, leds apagados). Edite o JSON depois."""
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
        console.print(f"[red]perfil nao encontrado: {name}[/red]")
        raise typer.Exit(code=1) from None


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
    from hefesto.utils.xdg_paths import config_dir

    marker = config_dir(ensure=True) / "active_profile.txt"
    marker.write_text(name + "\n", encoding="utf-8")


def read_active_marker() -> str | None:
    from hefesto.utils.xdg_paths import config_dir

    marker = config_dir() / "active_profile.txt"
    if not marker.exists():
        return None
    content = marker.read_text(encoding="utf-8").strip()
    return content or None


__all__ = ["app", "read_active_marker"]
