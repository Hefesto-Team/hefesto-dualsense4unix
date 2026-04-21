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

app.add_typer(profile_app, name="profile")


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


def main() -> None:
    """Entry point declarado em pyproject.toml [project.scripts]."""
    app()


if __name__ == "__main__":
    main()
