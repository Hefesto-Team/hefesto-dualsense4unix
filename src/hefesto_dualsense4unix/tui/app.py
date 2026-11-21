"""Textual app principal do Hefesto - DualSense4Unix.

`hefesto-dualsense4unix tui` abre essa app. Tela inicial (`MainScreen`) mostra:
  - Cabeçalho com nome + versão.
  - Bloco de estado do controle (bateria, transporte, perfil ativo).
  - Lista de perfis disponíveis (do XDG).
  - Rodapé com atalhos (`q`=sair, `r`=refresh).

Comunica com daemon via IPC quando disponível; fallback: lê perfis
direto do disco e mostra "daemon offline".
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any, ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static

from hefesto_dualsense4unix import __version__
from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError
from hefesto_dualsense4unix.tui.widgets import BatteryMeter, StickPreview, TriggerBar
from hefesto_dualsense4unix.utils import identidade


@dataclass
class DaemonSnapshot:
    """Snapshot imutável do estado consultado via IPC."""

    online: bool = False
    connected: bool = False
    transport: str | None = None
    active_profile: str | None = None
    battery_pct: int | None = None
    profiles: list[dict[str, Any]] = field(default_factory=list)
    controllers: list[dict[str, Any]] = field(default_factory=list)


class EloComOServico:
    """Uma conexão com o serviço, mantida entre as chamadas e reaberta só depois da queda."""

    def __init__(self) -> None:
        self._pilha: contextlib.AsyncExitStack | None = None
        self._cliente: IpcClient | None = None

    async def chamar(self, metodo: str, params: dict[str, Any] | None = None) -> Any:
        """O resultado do método. Queda de transporte solta a conexão e levanta; a recusa do
        serviço levanta e mantém a conexão."""
        try:
            if self._cliente is None:
                self._pilha = contextlib.AsyncExitStack()
                self._cliente = await self._pilha.enter_async_context(IpcClient.connect())
            return await self._cliente.call(metodo, params)
        except IpcError as exc:
            from hefesto_dualsense4unix.app.ipc_bridge import servico_mudo

            if servico_mudo(exc):
                await self.soltar()
            raise
        except (OSError, ValueError):
            await self.soltar()
            raise

    async def soltar(self) -> None:
        pilha, self._pilha, self._cliente = self._pilha, None, None
        if pilha is not None:
            await pilha.aclose()


async def fetch_daemon_snapshot(conexao: EloComOServico | None = None) -> DaemonSnapshot:
    """Consulta o daemon via IPC; se offline, retorna snapshot vazio."""
    propria = conexao is None
    conexao = EloComOServico() if conexao is None else conexao
    try:
        try:
            status = await conexao.chamar("daemon.state_full")
            profiles = await conexao.chamar("profile.list")
        except IpcError:
            return DaemonSnapshot(online=True)
        controllers = status.get("controllers")
        return DaemonSnapshot(
            online=True,
            connected=bool(status.get("connected")),
            transport=status.get("transport"),
            active_profile=status.get("active_profile"),
            battery_pct=status.get("battery_pct"),
            profiles=profiles.get("profiles", []),
            controllers=[
                c for c in controllers if isinstance(c, dict) and c.get("connected")
            ] if isinstance(controllers, list) else [],
        )
    except (FileNotFoundError, ConnectionError, OSError):
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles
        from hefesto_dualsense4unix.profiles.manager import os_perfis_de_escolher

        try:
            profiles_raw = os_perfis_de_escolher(load_all_profiles())
            profiles = [
                {
                    "name": p.name,
                    "priority": p.priority,
                    "match_type": p.match.type,
                }
                for p in profiles_raw
            ]
        except Exception:
            profiles = []
        return DaemonSnapshot(online=False, profiles=profiles)
    finally:
        if propria:
            await conexao.soltar()


def _numero_do_controle(c: dict[str, Any]) -> int:
    from hefesto_dualsense4unix.cli.cmd_controller import _numero_exibido

    return _numero_exibido(c)


def _resumo_do_controle(c: dict[str, Any]) -> str:
    pct = c.get("battery_pct")
    cor = "green" if (pct or 0) > 40 else "yellow" if (pct or 0) > 15 else "red"
    bateria = f"{pct}%" if pct is not None else "?"
    return (
        f"Controle {_numero_do_controle(c)} [cyan]{str(c.get('transport') or '?').upper()}[/] "
        f"[{cor}]{bateria}[/]"
    )


class StatusBar(Static):
    """Barra de status inferior: bateria, transporte, perfil."""

    snapshot: reactive[DaemonSnapshot] = reactive(DaemonSnapshot, always_update=True)

    def render(self) -> str:
        s = self.snapshot
        if not s.online:
            return "[yellow]daemon offline[/] — mostrando perfis do XDG"
        if not s.connected:
            return "[red]daemon online[/], controle desconectado"
        if s.controllers:
            return " | ".join(
                [_resumo_do_controle(c) for c in s.controllers]
                + [f"perfil [magenta]{s.active_profile or '[dim]nenhum[/]'}[/]"]
            )
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
                f"[bold cyan]{identidade.atual().nome_longo}[/] [dim]v{__version__}[/] — "
                "Gerenciador DualSense para Linux",
                id="title",
            )
            with Horizontal():
                yield Static(id="info_box", classes="panel")
                with Vertical(id="preview_panel", classes="panel"):
                    yield Label("[bold]Controles[/]")
                    yield Vertical(id="controles")
            yield Label("[bold]Perfis disponíveis[/]", id="profiles_title")
            table: DataTable[str] = DataTable(id="profiles_table")
            table.add_columns("Nome", "Prioridade", "Match")
            yield table
            yield StatusBar(id="status_bar")
        yield Footer()

    def __init__(self) -> None:
        super().__init__()
        self._elo = EloComOServico()
        self._chaves: tuple[tuple[Any, Any], ...] = ()

    async def on_mount(self) -> None:
        await self.action_refresh()
        self.set_interval(0.1, self._tick_preview)

    async def on_unmount(self) -> None:
        await self._elo.soltar()

    async def _tick_preview(self) -> None:
        """Lê os valores vivos de cada controle (o `daemon.state_full`, o mesmo da janela), 10 vezes
        por segundo, na conexão que o app mantém. Sem serviço, o tique espera o próximo."""
        try:
            estado = await self._elo.chamar("daemon.state_full")
        except (OSError, ValueError, IpcError):
            return
        controles = estado.get("controllers") if isinstance(estado, dict) else None
        if isinstance(controles, list):
            await self._pintar_os_controles(
                [c for c in controles if isinstance(c, dict) and c.get("connected")]
            )

    async def _pintar_os_controles(self, controles: list[dict[str, Any]]) -> None:
        caixa = self.query_one("#controles", Vertical)
        chaves = tuple((c.get("index"), c.get("uniq")) for c in controles)
        if chaves != self._chaves:
            await caixa.remove_children()
            await caixa.mount(*[self._grupo_do_controle(c) for c in controles])
            self._chaves = chaves
        for grupo, c in zip(caixa.children, controles, strict=True):
            self._apply_preview(grupo, c)

    @staticmethod
    def _grupo_do_controle(c: dict[str, Any]) -> Vertical:
        nome = c.get("nome_declarado") or c.get("modelo")
        titulo = f"[bold]Controle {_numero_do_controle(c)}[/]"
        titulo += f" {nome}" if isinstance(nome, str) and nome.strip() else ""
        titulo += f" [dim]{str(c.get('transport') or '?').upper()}[/]"
        return Vertical(
            Label(titulo),
            TriggerBar(side_label="L2"),
            TriggerBar(side_label="R2"),
            BatteryMeter(),
            Horizontal(StickPreview(label="L"), StickPreview(label="R"), classes="sticks_row"),
        )

    @staticmethod
    def _apply_preview(grupo: Any, c: dict[str, Any]) -> None:
        entradas = c.get("inputs")
        if isinstance(entradas, dict):
            l2, r2 = grupo.query(TriggerBar)
            l2.value = int(entradas.get("l2_raw", 0))
            r2.value = int(entradas.get("r2_raw", 0))
            stick_l, stick_r = grupo.query(StickPreview)
            stick_l.x, stick_l.y = int(entradas.get("lx", 128)), int(entradas.get("ly", 128))
            stick_r.x, stick_r.y = int(entradas.get("rx", 128)), int(entradas.get("ry", 128))
        grupo.query_one(BatteryMeter).pct = c.get("battery_pct")

    async def action_refresh(self) -> None:
        snap = await fetch_daemon_snapshot(self._elo)
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
            await self._elo.chamar("profile.switch", {"name": name})
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
    .sticks_row {
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

    TITLE = identidade.atual().nome_longo
    SUB_TITLE = f"v{__version__}"
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "quit", "Sair"),
    ]

    def on_mount(self) -> None:
        self.push_screen(MainScreen())


def run_tui() -> None:
    HefestoApp().run()


__all__ = [
    "DaemonSnapshot",
    "EloComOServico",
    "HefestoApp",
    "MainScreen",
    "StatusBar",
    "fetch_daemon_snapshot",
    "run_tui",
]
