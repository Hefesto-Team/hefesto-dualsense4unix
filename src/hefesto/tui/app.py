"""Textual app principal do Hefesto.

`hefesto tui` abre essa app. Tela inicial (`MainScreen`) mostra:
  - Cabeçalho com nome + versão.
  - Bloco de estado do controle (bateria, transporte, perfil ativo).
  - Lista de perfis disponíveis (do XDG).
  - Rodapé com atalhos (`q`=sair, `r`=refresh).

Comunica com daemon via IPC quando disponível; fallback: lê perfis
direto do disco e mostra "daemon offline".
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static

from hefesto import __version__
from hefesto.tui.widgets import BatteryMeter, StickPreview, TriggerBar


@dataclass
class DaemonSnapshot:
    """Snapshot imutável do estado consultado via IPC."""

    online: bool = False
    connected: bool = False
    transport: str | None = None
    active_profile: str | None = None
    battery_pct: int | None = None
    profiles: list[dict[str, Any]] = field(default_factory=list)


async def fetch_daemon_snapshot() -> DaemonSnapshot:
    """Consulta o daemon via IPC; se offline, retorna snapshot vazio."""
    try:
        from hefesto.cli.ipc_client import IpcClient, IpcError

        async with IpcClient.connect() as client:
            try:
                status = await client.call("daemon.status")
                profiles = await client.call("profile.list")
            except IpcError:
                return DaemonSnapshot(online=True)
            return DaemonSnapshot(
                online=True,
                connected=bool(status.get("connected")),
                transport=status.get("transport"),
                active_profile=status.get("active_profile"),
                battery_pct=status.get("battery_pct"),
                profiles=profiles.get("profiles", []),
            )
    except (FileNotFoundError, ConnectionError, OSError):
        # Daemon offline: carrega perfis direto do disco.
        from hefesto.profiles.loader import load_all_profiles
        from hefesto.profiles.schema import MatchAny

        try:
            profiles_raw = load_all_profiles()
            profiles = [
                {
                    "name": p.name,
                    "priority": p.priority,
                    "match_type": "any" if isinstance(p.match, MatchAny) else "criteria",
                }
                for p in profiles_raw
            ]
        except Exception:
            profiles = []
        return DaemonSnapshot(online=False, profiles=profiles)


class StatusBar(Static):
    """Barra de status inferior: bateria, transporte, perfil."""

    snapshot: reactive[DaemonSnapshot] = reactive(DaemonSnapshot, always_update=True)

    def render(self) -> str:
        s = self.snapshot
        if not s.online:
            return "[yellow]daemon offline[/] — mostrando perfis do XDG"
        if not s.connected:
            return "[red]daemon online[/], controle desconectado"
        battery = f"{s.battery_pct}%" if s.battery_pct is not None else "?"
        color = (
            "green"
            if (s.battery_pct or 0) > 40
            else "yellow"
            if (s.battery_pct or 0) > 15
            else "red"
        )
        profile = s.active_profile or "[dim]nenhum[/]"
        return (
            f"[{color}]bateria {battery}[/] | "
            f"transporte [cyan]{s.transport}[/] | "
            f"perfil [magenta]{profile}[/]"
        )


class MainScreen(Screen[None]):
    """Tela inicial: estado + perfis."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "app.quit", "Sair"),
        Binding("r", "refresh", "Atualizar"),
    ]

    snapshot: reactive[DaemonSnapshot] = reactive(DaemonSnapshot, always_update=True)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Label(
                f"[bold cyan]Hefesto[/] [dim]v{__version__}[/] — "
                "daemon de gatilhos adaptativos para DualSense",
                id="title",
            )
            with Horizontal():
                yield Static(id="info_box", classes="panel")
                with Vertical(id="preview_panel", classes="panel"):
                    yield Label("[bold]Gatilhos[/]")
                    yield TriggerBar(side_label="L2", id="trigger_l2")
                    yield TriggerBar(side_label="R2", id="trigger_r2")
                    yield Label("[bold]Bateria[/]")
                    yield BatteryMeter(id="battery_meter")
                    with Horizontal(id="sticks_row"):
                        yield StickPreview(label="L", id="stick_l")
                        yield StickPreview(label="R", id="stick_r")
            yield Label("[bold]Perfis disponíveis[/]", id="profiles_title")
            table: DataTable[str] = DataTable(id="profiles_table")
            table.add_columns("Nome", "Prioridade", "Match")
            yield table
            yield StatusBar(id="status_bar")
        yield Footer()

    async def on_mount(self) -> None:
        await self.action_refresh()
        # Poll curto pra atualizar widgets visuais (trigger/stick/battery).
        # Usa set_interval do Textual; timer é cancelado automaticamente no unmount.
        self.set_interval(0.1, self._tick_preview)

    async def _tick_preview(self) -> None:
        """Lê estado do controle direto pra atualizar widgets a 10Hz.

        Usa o IPC quando disponível pra reaproveitar conexão do daemon.
        Em offline, cai em leitura direta via PyDualSenseController (mas
        sem hardware retorna valores padrão — safe).
        """
        try:
            from hefesto.cli.ipc_client import IpcClient

            async with IpcClient.connect() as client:
                status = await client.call("daemon.status")
            self._apply_preview(
                l2=0,  # daemon.status não inclui analog ainda
                r2=0,
                lx=128,
                ly=128,
                rx=128,
                ry=128,
                battery=status.get("battery_pct"),
            )
        except Exception:
            # IPC ausente: mantém widgets nos últimos valores
            return

    def _apply_preview(
        self,
        *,
        l2: int,
        r2: int,
        lx: int,
        ly: int,
        rx: int,
        ry: int,
        battery: int | None,
    ) -> None:
        self.query_one("#trigger_l2", TriggerBar).value = l2
        self.query_one("#trigger_r2", TriggerBar).value = r2
        self.query_one("#battery_meter", BatteryMeter).pct = battery
        stick_l = self.query_one("#stick_l", StickPreview)
        stick_l.x = lx
        stick_l.y = ly
        stick_r = self.query_one("#stick_r", StickPreview)
        stick_r.x = rx
        stick_r.y = ry

    async def action_refresh(self) -> None:
        snap = await fetch_daemon_snapshot()
        self.snapshot = snap
        info_box = self.query_one("#info_box", Static)
        info_text = (
            f"daemon: {'[green]online[/]' if snap.online else '[yellow]offline[/]'}\n"
            f"controle: {'[green]conectado[/]' if snap.connected else '[red]desconectado[/]'}\n"
            f"transporte: {snap.transport or '[dim]n/d[/]'}\n"
            f"bateria: {snap.battery_pct if snap.battery_pct is not None else '[dim]?[/]'}%\n"
            f"perfil ativo: {snap.active_profile or '[dim]nenhum[/]'}"
        )
        info_box.update(info_text)

        table = self.query_one("#profiles_table", DataTable)
        table.clear()
        for p in snap.profiles:
            table.add_row(
                str(p.get("name", "?")),
                str(p.get("priority", "")),
                str(p.get("match_type", "")),
            )

        status = self.query_one("#status_bar", StatusBar)
        status.snapshot = snap

    @on(DataTable.RowSelected)
    async def on_profile_selected(self, event: DataTable.RowSelected) -> None:
        table = event.data_table
        row = table.get_row(event.row_key)
        name = str(row[0])
        await self._try_activate(name)

    async def _try_activate(self, name: str) -> None:
        """Tenta ativar perfil via IPC; silencioso em erro."""
        try:
            from hefesto.cli.ipc_client import IpcClient

            async with IpcClient.connect() as client:
                await client.call("profile.switch", {"name": name})
            await self.action_refresh()
        except Exception:
            self.notify(
                f"não foi possivel ativar '{name}' (daemon offline?)",
                severity="warning",
            )


class HefestoApp(App[None]):
    """App principal Textual."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #title {
        padding: 1 2;
        background: $boost;
        color: $accent;
        text-style: bold;
    }
    #profiles_title {
        padding: 1 2 0 2;
    }
    .panel {
        padding: 1 2;
        border: heavy $primary;
        margin: 1 2;
        width: 1fr;
        height: auto;
    }
    #info_box {
        width: 1fr;
    }
    #preview_panel {
        width: 1fr;
    }
    #sticks_row {
        height: auto;
    }
    StickPreview {
        width: 12;
        height: 6;
        margin-right: 2;
    }
    TriggerBar {
        height: 1;
    }
    BatteryMeter {
        height: 1;
    }
    DataTable {
        margin: 0 2;
    }
    StatusBar {
        padding: 1 2;
        background: $surface;
        color: $text;
        dock: bottom;
    }
    """

    TITLE = "Hefesto"
    SUB_TITLE = f"v{__version__}"
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "quit", "Sair"),
    ]

    def on_mount(self) -> None:
        self.push_screen(MainScreen())


def run_tui() -> None:
    HefestoApp().run()


def main_async(argv: list[str] | None = None) -> None:
    """Entry point síncrono que roda o asyncio app."""
    asyncio.run(HefestoApp().run_async())


__all__ = [
    "DaemonSnapshot",
    "HefestoApp",
    "MainScreen",
    "StatusBar",
    "fetch_daemon_snapshot",
    "run_tui",
]
