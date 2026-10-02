"""Subcomando `hefesto-dualsense4unix test ...`."""
from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any, Literal

import typer
from rich.console import Console

from hefesto_dualsense4unix.core.controller import IController
from hefesto_dualsense4unix.core.led_control import hex_to_rgb
from hefesto_dualsense4unix.core.trigger_effects import build_from_name

app = typer.Typer(name="test", help="Exercita efeitos direto no hardware.", no_args_is_help=True)
console = Console()


def _parse_params(raw: str | None) -> list[int]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    try:
        return [int(p) for p in parts]
    except ValueError as exc:
        raise typer.BadParameter(f"params: inteiros separados por virgula. Erro: {exc}") from None


MSG_RAW_COM_DAEMON = (
    "o daemon está no ar, e o --raw abriria um SEGUNDO controlador para "
    "disputar o mesmo /dev/hidraw com ele.\n\n"
    "Medido em 01/08/2026: o report_thread do daemon sobrescrevia o efeito em "
    "menos de 0,5 s, e este comando imprimia \"trigger aplicado\" mesmo assim "
    "— o instrumento brigando com o produto e anunciando sucesso.\n\n"
    "Corrigido em 11/08/2026 (RUMBLE-SEM-DONO-01): o keepalive PERPÉTUO "
    "acabou. Hoje o daemon só reconfirma o mesmo report na janela de "
    "confirmação que segue cada mudança real — não mais para sempre. Mudou o "
    "prazo, não a recusa: o report OUT do DualSense é ATÔMICO (gatilho, "
    "vibração e luz saem no mesmo buffer), então o primeiro write do daemon "
    "depois do seu leva o seu efeito cru junto, e nada avisa quando isso "
    "acontece.\n\n"
    "Saídas, em ordem de preferência:\n"
    "  1. use a aba Gatilhos da janela, que passa pelo daemon;\n"
    "  2. use --mode com NOME de preset (sem --raw), que também passa;\n"
    "  3. para bancada crua: systemctl --user stop hefesto-dualsense4unix, "
    "rode o --raw, e religue depois."
)


def _recusar_raw_com_daemon_vivo() -> None:
    """Recusa o `--raw` quando o daemon está no ar."""
    from hefesto_dualsense4unix.app.ipc_bridge import daemon_status_basic

    vivo = False
    try:
        vivo = daemon_status_basic() is not None
    except Exception:
        vivo = False  # sem socket, sem daemon: o --raw tem o hidraw só para ele
    if vivo:
        console.print(f"[red]--raw recusado:[/red] {MSG_RAW_COM_DAEMON}")
        raise typer.Exit(code=1)


@app.command("trigger")
def cmd_trigger(
    side: str = typer.Option(..., help="left ou right"),
    mode: str = typer.Option(..., help="Nome do preset (Rigid, Galloping, ...)."),
    params: str | None = typer.Option(None, help="CSV de inteiros: '0,9,7,7,10'"),
    raw: bool = typer.Option(
        False, "--raw", help="mode e valor inteiro (0-255); params sao 7 bytes HID."
    ),
) -> None:
    if side not in ("left", "right"):
        raise typer.BadParameter("side deve ser left ou right")
    side_literal: Literal["left", "right"] = "left" if side == "left" else "right"

    params_list = _parse_params(params)

    if raw:
        from hefesto_dualsense4unix.core.controller import TriggerEffect

        try:
            mode_int = int(mode)
        except ValueError:
            raise typer.BadParameter("modo --raw exige inteiro em --mode") from None
        if len(params_list) != 7:
            raise typer.BadParameter("modo --raw exige 7 valores em --params")
        _recusar_raw_com_daemon_vivo()
        effect = TriggerEffect(
            mode=mode_int,
            forces=(
                params_list[0], params_list[1], params_list[2], params_list[3],
                params_list[4], params_list[5], params_list[6],
            ),
        )
    else:
        effect = build_from_name(mode, params_list)
        # cmd_led) para NÃO abrir um 2º PyDualSenseController e brigar pelo hidraw
        from hefesto_dualsense4unix.app.ipc_bridge import trigger_set

        if trigger_set(side_literal, mode, params_list):
            console.print(
                f"[green]trigger (via daemon):[/green] {side_literal} {mode} {params_list}"
            )
            return

    _apply_on_hardware(lambda c: c.set_trigger(side_literal, effect))
    console.print(f"[green]trigger aplicado: {side_literal} {mode} {params_list}[/green]")


@app.command("led")
def cmd_led(
    color: str = typer.Option(..., help="Cor em hex (#FF0080) ou nome r,g,b."),
    brightness: int | None = typer.Option(
        None, "--brightness", min=0, max=100,
        help="Luminosidade 0-100%% (depende de FEAT-LED-BRIGHTNESS-01 no daemon).",
    ),
) -> None:
    """Aplica cor (e luminosidade opcional) na lightbar."""
    rgb = hex_to_rgb(color) if color.startswith("#") or len(color) == 6 else _parse_rgb_csv(color)

    if _apply_via_ipc(rgb, brightness):
        extra = f" brightness={brightness}%" if brightness is not None else ""
        console.print(f"[green]lightbar (via daemon):[/green] rgb={rgb}{extra}")
        return

    final_rgb = _scale_rgb(rgb, brightness) if brightness is not None else rgb
    _apply_on_hardware(lambda c: c.set_led(final_rgb))
    if brightness is not None:
        console.print(
            f"[green]lightbar (hardware):[/green] rgb={rgb} brightness={brightness}%% "
            f"-> rgb_aplicado={final_rgb}"
        )
    else:
        console.print(f"[green]lightbar:[/green] rgb={rgb}")


def _apply_via_ipc(rgb: tuple[int, int, int], brightness: int | None) -> bool:
    """Tenta enviar `led.set` via IPC; retorna True em sucesso, False em falha.

    BUG-CLI-BRIGHTNESS-UNIDADE-01 (25/07): a CLI expõe `--brightness` em
    PORCENTAGEM (0-100, `min=0, max=100` no typer) e mandava o número cru; o
    handler `led.set` valida FRAÇÃO (`0.0 <= brightness <= 1.0`,
    `ipc_handlers.py:1067`). O resultado eram dois erros silenciosos:
    `--brightness 50` fazia o IPC recusar e o comando caía no fallback de
    hardware sem dizer nada, e `--brightness 1` passava na validação como
    `1.0` — ou seja, era aplicado como **100%**, o oposto do pedido.
    A conversão mora aqui porque a unidade amigável é da CLI: a GUI já manda
    fração (`app/ipc_bridge.py:414` `led_set`), que é o contrato do daemon.
    (O docstring antigo dizia que o daemon "ignora" o parâmetro; ele valida e
    aplica desde a FEAT-LED-BRIGHTNESS-01.)
    """
    from hefesto_dualsense4unix.app.ipc_bridge import _run_call
    from hefesto_dualsense4unix.cli.ipc_client import IpcError

    params: dict[str, object] = {"rgb": list(rgb)}
    if brightness is not None:
        params["brightness"] = max(0, min(100, int(brightness))) / 100.0
    try:
        _run_call("led.set", params, timeout=0.5)
    except (IpcError, FileNotFoundError, ConnectionError, OSError):
        return False
    return True


def _scale_rgb(rgb: tuple[int, int, int], brightness: int) -> tuple[int, int, int]:
    """Escala linear do RGB pela luminosidade (0-100%%)."""
    factor = max(0, min(100, brightness)) / 100.0
    return (
        round(rgb[0] * factor),
        round(rgb[1] * factor),
        round(rgb[2] * factor),
    )


@app.command("rumble")
def cmd_rumble(
    weak: int = typer.Option(0, min=0, max=255),
    strong: int = typer.Option(0, min=0, max=255),
) -> None:
    from hefesto_dualsense4unix.app.ipc_bridge import rumble_set

    if rumble_set(weak, strong):
        console.print(f"[green]rumble (via daemon):[/green] weak={weak} strong={strong}")
        return

    _apply_on_hardware(lambda c: c.set_rumble(weak=weak, strong=strong))
    console.print(f"[green]rumble: weak={weak} strong={strong}[/green]")


def _parse_rgb_csv(value: str) -> tuple[int, int, int]:
    parts = [int(p.strip()) for p in value.split(",")]
    if len(parts) != 3:
        raise typer.BadParameter("formato: R,G,B (3 valores 0-255)")
    for idx, b in enumerate(parts):
        if not (0 <= b <= 255):
            raise typer.BadParameter(f"rgb[{idx}] fora de 0-255")
    return (parts[0], parts[1], parts[2])


def _apply_on_hardware(action: Callable[[IController], Any]) -> None:
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    controller = PyDualSenseController()
    try:
        controller.connect()
        action(controller)
    finally:
        with contextlib.suppress(Exception):
            controller.disconnect()


__all__ = ["app"]
