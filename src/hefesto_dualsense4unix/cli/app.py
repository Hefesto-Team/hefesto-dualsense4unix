"""CLI Typer do Hefesto - Dualsense4Unix.

Subcomandos implementados em W1.3:
  - `hefesto-dualsense4unix version`
  - `hefesto-dualsense4unix daemon start [--poll-hz N] [--foreground] [--headless] [--no-reconnect]`
  - `hefesto-dualsense4unix daemon {install-service,uninstall-service,start,stop,restart,status}`

A flag `--headless` de `daemon start` apenas seta `HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT=1`
(desativa auto-switch X11). Não existe mais unit separada (SIMPLIFY-UNIT-01).

Demais subcomandos (profile, test, led, battery, status) chegam em W5.3.
"""
from __future__ import annotations

import os

import typer

app = typer.Typer(
    name="hefesto-dualsense4unix",
    help="Daemon de gatilhos adaptativos para DualSense no Linux.",
    add_completion=True,
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    """Callback de `--version`: imprime versão e sai."""
    if value:
        from hefesto_dualsense4unix import __version__
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main_callback(
    _version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Mostra a versão e sai.",
    ),
) -> None:
    """Callback global para flags root (`--version`)."""

daemon_app = typer.Typer(
    name="daemon",
    help="Controle do daemon de background.",
    no_args_is_help=True,
)
app.add_typer(daemon_app, name="daemon")

from hefesto_dualsense4unix.cli.cmd_emulate import app as emulate_app  # noqa: E402
from hefesto_dualsense4unix.cli.cmd_gamepad import app as gamepad_app  # noqa: E402
from hefesto_dualsense4unix.cli.cmd_mouse import app as mouse_app  # noqa: E402
from hefesto_dualsense4unix.cli.cmd_plugin import app as plugin_app  # noqa: E402
from hefesto_dualsense4unix.cli.cmd_profile import app as profile_app  # noqa: E402
from hefesto_dualsense4unix.cli.cmd_test import app as test_app  # noqa: E402

app.add_typer(profile_app, name="profile")
app.add_typer(test_app, name="test")
app.add_typer(emulate_app, name="emulate")
app.add_typer(mouse_app, name="mouse")
app.add_typer(gamepad_app, name="gamepad")
app.add_typer(plugin_app, name="plugin")


@app.command()
def status() -> None:
    """Mostra status do daemon e do controle."""
    from hefesto_dualsense4unix.cli.cmd_status import status_cmd

    status_cmd()


@app.command()
def doctor(
    fix: bool = typer.Option(False, "--fix", help="Aplica correções seguras (udev + WirePlumber)."),
    quiet: bool = typer.Option(False, "--quiet", help="Só mostra FAIL/WARN."),
) -> None:
    """Diagnóstico de saúde: daemon, udev, applet, áudio + checks do daemon via IPC."""
    from hefesto_dualsense4unix.cli.cmd_doctor import doctor_cmd

    doctor_cmd(fix=fix, quiet=quiet)


@app.command()
def battery() -> None:
    """Percentual de bateria do controle."""
    from hefesto_dualsense4unix.cli.cmd_status import battery_cmd

    battery_cmd()


@app.command()
def led(
    color: str = typer.Option(..., help="Hex (#RRGGBB) ou CSV R,G,B."),
    brightness: int | None = typer.Option(
        None, "--brightness", min=0, max=100,
        help="Luminosidade 0-100%% (depende de FEAT-LED-BRIGHTNESS-01 no daemon).",
    ),
) -> None:
    """Define a cor (e, opcionalmente, luminosidade) da lightbar.

    - Sem daemon rodando: aplica direto no hardware (brightness escala
      linearmente o RGB como aproximação — 100%% = cor pura, 0%% = apagado).
    - Com daemon rodando: envia `led.set` via IPC. Quando FEAT-LED-BRIGHTNESS-01
      estiver mergeada, o daemon honrará o parâmetro `brightness` sem
      distorcer o RGB.
    """
    from hefesto_dualsense4unix.cli.cmd_test import cmd_led

    cmd_led(color=color, brightness=brightness)


@app.command()
def tui() -> None:
    """Abre a TUI Textual do Hefesto - Dualsense4Unix."""
    from hefesto_dualsense4unix.tui.app import run_tui

    run_tui()


@app.command()
def tray() -> None:
    """Abre o tray icon GTK3 (requer pip install com extra tray)."""
    from hefesto_dualsense4unix.cli.cmd_tray import tray_cmd

    tray_cmd()


@app.command()
def mic(
    action: str = typer.Argument(
        "status", help="on | off | status — liga/desliga o mic embutido do DualSense."
    ),
) -> None:
    """Liga/desliga o microfone embutido do DualSense (via WirePlumber).

    Por padrão o mic vem suprimido (sem virar microfone padrão / sem spam).
    `mic on` libera o mic quando você for jogar algo que precise dele; `mic off`
    volta a suprimir. Mesmo caminho usado pelo botão na GUI e no applet COSMIC.
    """
    from hefesto_dualsense4unix.cli.cmd_mic import mic_cmd

    mic_cmd(action)


@app.command()
def version() -> None:
    """Mostra a versão instalada."""
    from hefesto_dualsense4unix import __version__
    typer.echo(__version__)


@daemon_app.command("start")
def daemon_start(
    poll_hz: int = typer.Option(60, "--poll-hz", help="Frequência de poll HID em Hz."),
    foreground: bool = typer.Option(
        True, "--foreground/--no-foreground", help="Rodar em primeiro plano."
    ),
    headless: bool = typer.Option(
        False, "--headless", help="Desliga auto-switch X11 (set HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT=1)."  # noqa: E501
    ),
    reconnect: bool = typer.Option(
        True, "--reconnect/--no-reconnect", help="Tenta reconectar se o controle cair."
    ),
) -> None:
    """Inicia o daemon no processo atual."""
    if headless:
        os.environ["HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT"] = "1"

    from hefesto_dualsense4unix.daemon.main import run_daemon

    exit_code = run_daemon(poll_hz=poll_hz, auto_reconnect=reconnect)
    raise typer.Exit(code=exit_code)


@daemon_app.command("install-service")
def daemon_install_service(
    enable: bool = typer.Option(
        False,
        "--enable",
        help="Habilitar auto-start no boot (WantedBy=default.target).",
    ),
) -> None:
    """Copia a unit systemd --user `hefesto-dualsense4unix.service`.

    Por padrão NÃO habilita auto-start (opt-in explícito via `--enable`).
    Ver BUG-MULTI-INSTANCE-01.
    """
    from hefesto_dualsense4unix.daemon.service_install import ServiceInstaller

    installer = ServiceInstaller()
    dst = installer.install(enable=enable)
    typer.echo(f"unit instalada: {dst}")
    if enable:
        typer.echo("auto-start habilitado (systemctl --user enable hefesto-dualsense4unix.service)")
    else:
        typer.echo(
            "auto-start NÃO habilitado — use "
            "'systemctl --user enable hefesto-dualsense4unix.service' se desejar"
        )


@daemon_app.command("uninstall-service")
def daemon_uninstall_service() -> None:
    """Remove a unidade `hefesto-dualsense4unix.service` de ~/.config/systemd/user/."""
    from hefesto_dualsense4unix.daemon.service_install import ServiceInstaller

    installer = ServiceInstaller()
    removed = installer.uninstall()
    if not removed:
        typer.echo("nenhuma unit instalada.")
        return
    for p in removed:
        typer.echo(f"removido: {p}")


@daemon_app.command("stop")
def daemon_stop() -> None:
    """Para o daemon gerenciado pelo systemd --user."""
    from hefesto_dualsense4unix.daemon.service_install import ServiceInstaller

    ServiceInstaller().stop()


@daemon_app.command("restart")
def daemon_restart() -> None:
    """Reinicia o daemon gerenciado pelo systemd --user."""
    from hefesto_dualsense4unix.daemon.service_install import ServiceInstaller

    ServiceInstaller().restart()


@daemon_app.command("status")
def daemon_status() -> None:
    """Mostra status do daemon via systemctl."""
    from hefesto_dualsense4unix.daemon.service_install import ServiceInstaller

    text = ServiceInstaller().status_text()
    typer.echo(text)


def _toggle_pause(method: str, label: str) -> None:
    """Chama daemon.pause/resume via IPC (FEAT-DAEMON-PAUSE-RESUME-01)."""
    import asyncio

    from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

    async def _call() -> bool:
        try:
            async with IpcClient.connect() as client:
                await client.call(method)
                return True
        except (FileNotFoundError, ConnectionError, IpcError):
            return False

    if asyncio.run(_call()):
        typer.echo(f"daemon {label}")
    else:
        typer.echo(
            "daemon offline — pausar/retomar exige o daemon rodando "
            "(inicie com 'hefesto-dualsense4unix daemon start')"
        )
        raise typer.Exit(code=1)


@daemon_app.command("pause")
def daemon_pause() -> None:
    """Pausa o despacho de input — o daemon segue vivo, mas para de afetar o sistema."""
    _toggle_pause("daemon.pause", "pausado")


@daemon_app.command("resume")
def daemon_resume() -> None:
    """Retoma o despacho de input previamente pausado."""
    _toggle_pause("daemon.resume", "retomado")


@daemon_app.command("disable")
def daemon_disable() -> None:
    """Desliga: para o daemon e desabilita o auto-start (mantém instalado)."""
    from hefesto_dualsense4unix.daemon.service_install import ServiceInstaller

    ServiceInstaller().disable()
    typer.echo(
        "daemon parado e auto-start desabilitado — religue com "
        "'hefesto-dualsense4unix daemon enable'"
    )


@daemon_app.command("enable")
def daemon_enable() -> None:
    """Habilita o auto-start no boot e inicia o daemon."""
    from hefesto_dualsense4unix.daemon.service_install import ServiceInstaller

    ServiceInstaller().enable()
    typer.echo("auto-start habilitado e daemon iniciado")


def main() -> None:
    """Entry point declarado em pyproject.toml [project.scripts]."""
    # FEAT-I18N-INFRASTRUCTURE-01 (v3.4.0): inicializa locale ANTES do
    # Typer parsear argv para que `--help` e mensagens de erro do nosso
    # callback global respeitem `LANG=en_US.UTF-8` quando o usuário pedir.
    from hefesto_dualsense4unix.utils.i18n import init_locale

    init_locale()
    app()


if __name__ == "__main__":
    main()
