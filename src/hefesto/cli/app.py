"""Stub inicial da CLI Typer. Esqueleto criado em W0.1;
subcomandos reais chegam a partir de W4.1 (daemon) e W5.3 (completo).
"""
from __future__ import annotations

import typer

app = typer.Typer(
    name="hefesto",
    help="Daemon de gatilhos adaptativos para DualSense no Linux.",
    add_completion=True,
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Mostra a versão instalada."""
    from hefesto import __version__
    typer.echo(__version__)


def main() -> None:
    """Entry point declarado em pyproject.toml [project.scripts]."""
    app()


if __name__ == "__main__":
    main()
