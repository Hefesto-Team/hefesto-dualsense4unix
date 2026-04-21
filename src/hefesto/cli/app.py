"""CLI Typer do Hefesto.

Subcomandos implementados em W1.3:
  - `hefesto version`
  - `hefesto daemon start [--poll-hz N] [--foreground] [--headless] [--no-reconnect]`

Demais subcomandos (profile, test, led, battery, status) chegam em W5.3.
"""
from __future__ import annotations

import os

import typer

app = typer.Typer(
    name="hefesto",
    help="Daemon de gatilhos adaptativos para DualSense no Linux.",
    add_completion=True,
    no_args_is_help=True,
)

daemon_app = typer.Typer(
    name="daemon",
    help="Controle do daemon de background.",
    no_args_is_help=True,
)
app.add_typer(daemon_app, name="daemon")

from hefesto.cli.cmd_profile import app as profile_app  # noqa: E402
from hefesto.cli.cmd_test import app as test_app  # noqa: E402

app.add_typer(profile_app, name="profile")
app.add_typer(test_app, name="test")


@app.command()
def status() -> None:
    """Mostra status do daemon e do controle."""
    from hefesto.cli.cmd_status import status_cmd

    status_cmd()


@app.command()
def battery() -> None:
    """Percentual de bateria do controle."""
    from hefesto.cli.cmd_status import battery_cmd

    battery_cmd()


@app.command()
def led(
    color: str = typer.Option(..., help="Hex (#RRGGBB) ou CSV R,G,B."),
) -> None:
    """Define a cor da lightbar direto no controle."""
    from hefesto.cli.cmd_test import cmd_led

    cmd_led(color=color)


@app.command()
def version() -> None:
    """Mostra a versão instalada."""
    from hefesto import __version__
    typer.echo(__version__)


@daemon_app.command("start")
def daemon_start(
    poll_hz: int = typer.Option(60, "--poll-hz", help="Frequência de poll HID em Hz."),
    foreground: bool = typer.Option(
        True, "--foreground/--no-foreground", help="Rodar em primeiro plano."
    ),
    headless: bool = typer.Option(
        False, "--headless", help="Desliga auto-switch X11 (set HEFESTO_NO_WINDOW_DETECT=1)."
    ),
    reconnect: bool = typer.Option(
        True, "--reconnect/--no-reconnect", help="Tenta reconectar se o controle cair."
    ),
) -> None:
    """Inicia o daemon no processo atual."""
    if headless:
        os.environ["HEFESTO_NO_WINDOW_DETECT"] = "1"

    from hefesto.daemon.main import run_daemon

    exit_code = run_daemon(poll_hz=poll_hz, auto_reconnect=reconnect)
    raise typer.Exit(code=exit_code)


@daemon_app.command("install-service")
def daemon_install_service(
    headless: bool = typer.Option(False, "--headless", help="Instala unit headless."),
) -> None:
    """Copia a unit systemd --user e habilita, respeitando Conflicts mutuo."""
    from hefesto.daemon.service_install import ServiceInstaller

    installer = ServiceInstaller()
    dst = installer.install(headless=headless)
    typer.echo(f"unit instalada: {dst}")


@daemon_app.command("uninstall-service")
def daemon_uninstall_service() -> None:
    """Remove todas as unidades do Hefesto de ~/.config/systemd/user/."""
    from hefesto.daemon.service_install import ServiceInstaller

    installer = ServiceInstaller()
    removed = installer.uninstall()
    if not removed:
        typer.echo("nenhuma unit instalada.")
        return
    for p in removed:
        typer.echo(f"removido: {p}")


@daemon_app.command("stop")
def daemon_stop(
    headless: bool = typer.Option(False, "--headless"),
) -> None:
    """Para o daemon gerenciado pelo systemd --user."""
    from hefesto.daemon.service_install import ServiceInstaller

    ServiceInstaller().stop(headless=headless)


@daemon_app.command("restart")
def daemon_restart(
    headless: bool = typer.Option(False, "--headless"),
) -> None:
    """Reinicia o daemon gerenciado pelo systemd --user."""
    from hefesto.daemon.service_install import ServiceInstaller

    ServiceInstaller().restart(headless=headless)


@daemon_app.command("status")
def daemon_status(
    headless: bool = typer.Option(False, "--headless"),
) -> None:
    """Mostra status do daemon via systemctl."""
    from hefesto.daemon.service_install import ServiceInstaller

    text = ServiceInstaller().status_text(headless=headless)
    typer.echo(text)


def main() -> None:
    """Entry point declarado em pyproject.toml [project.scripts]."""
    app()


if __name__ == "__main__":
    main()
