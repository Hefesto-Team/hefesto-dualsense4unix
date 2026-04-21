"""Widgets visuais da TUI (W5.2).

- `TriggerBar`: barra de pressão L2/R2 (0-255) com faixa colorida por
  intensidade. Cor verde até 85, amarelo até 170, vermelho acima.
- `BatteryMeter`: percentual + barra de nível com cor por faixa.
- `StickPreview`: mini-mapa do stick (posição x/y relativa ao centro).

Todos são `Static` reativos: mudar a propriedade dispara re-render.
"""
from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static

MAX_ANALOG = 255
CENTER_STICK = 128


def _color_for_trigger(value: int) -> str:
    if value <= 85:
        return "green"
    if value <= 170:
        return "yellow"
    return "red"


def _color_for_battery(value: int) -> str:
    if value > 40:
        return "green"
    if value > 15:
        return "yellow"
    return "red"


def _bar(value: int, max_value: int = MAX_ANALOG, width: int = 30) -> str:
    filled = int(value / max_value * width)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


class TriggerBar(Static):
    """Barra de pressão pra um gatilho (L2 ou R2)."""

    side_label: reactive[str] = reactive("L2", always_update=True)
    value: reactive[int] = reactive(0, always_update=True)

    def __init__(
        self,
        side_label: str = "L2",
        value: int = 0,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.side_label = side_label
        self.value = value

    def render(self) -> str:
        clamped = max(0, min(MAX_ANALOG, self.value))
        color = _color_for_trigger(clamped)
        bar = _bar(clamped)
        return f"[bold]{self.side_label:>2}[/] [{color}]{bar}[/] [dim]{clamped:>3}/255[/]"


class BatteryMeter(Static):
    """Bateria com barra de nível e cor por faixa."""

    pct: reactive[int | None] = reactive(None, always_update=True)
    charging: reactive[bool] = reactive(False, always_update=True)

    def __init__(
        self, pct: int | None = None, charging: bool = False, *, id: str | None = None
    ) -> None:
        super().__init__(id=id)
        self.pct = pct
        self.charging = charging

    def render(self) -> str:
        if self.pct is None:
            return "[dim]bateria: ?[/]"
        value = max(0, min(100, self.pct))
        color = _color_for_battery(value)
        icon = self._icon_for_level(value)
        suffix = " [cyan]CHG[/]" if self.charging else ""
        return f"{icon} [{color}]{value:>3}%[/]{suffix}"

    @staticmethod
    def _icon_for_level(value: int) -> str:
        if value >= 80:
            return "▮▮▮▮"
        if value >= 60:
            return "▮▮▮▯"
        if value >= 40:
            return "▮▮▯▯"
        if value >= 20:
            return "▮▯▯▯"
        return "▯▯▯▯"


class StickPreview(Static):
    """Mini-mapa 7x5 mostrando posicao do stick (x/y 0-255)."""

    x: reactive[int] = reactive(CENTER_STICK, always_update=True)
    y: reactive[int] = reactive(CENTER_STICK, always_update=True)
    label: reactive[str] = reactive("L", always_update=True)

    def __init__(
        self,
        label: str = "L",
        x: int = CENTER_STICK,
        y: int = CENTER_STICK,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.label = label
        self.x = x
        self.y = y

    def render(self) -> str:
        cols = 7
        rows = 5
        cx = int(self.x / MAX_ANALOG * (cols - 1))
        cy = int(self.y / MAX_ANALOG * (rows - 1))
        cx = max(0, min(cols - 1, cx))
        cy = max(0, min(rows - 1, cy))

        lines: list[str] = []
        for r in range(rows):
            line = ""
            for c in range(cols):
                if r == cy and c == cx:
                    line += "[yellow]o[/]"
                elif r == rows // 2 and c == cols // 2:
                    line += "[dim]+[/]"
                else:
                    line += "·"
            lines.append(line)
        return f"[bold]{self.label}[/]\n" + "\n".join(lines)


__all__ = ["BatteryMeter", "StickPreview", "TriggerBar"]
