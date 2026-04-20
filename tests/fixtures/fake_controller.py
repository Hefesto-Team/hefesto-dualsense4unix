"""Backend fake para testes sem hardware.

Implementa `IController` com comportamento determinístico:
- Inicia desconectado; `connect()` marca conectado e carrega um snapshot.
- `read_state()` avança entre snapshots pré-definidos (ou um padrão único).
- `set_trigger/set_led/set_rumble` gravam em listas internas pra inspeção.

Replay de captures binários (V2-13, V3-8) fica no mesmo módulo — quando o
formato `.bin` for definido em W1.3, a classe ganha `from_capture(path)`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from hefesto.core.controller import (
    ControllerState,
    IController,
    Side,
    Transport,
    TriggerEffect,
)


@dataclass
class FakeControllerCommand:
    """Registro de comando emitido — usado por testes pra asserts."""

    kind: str
    payload: object


class FakeController(IController):
    """Controle fake para testes unit e integration.

    Parâmetros:
      transport: "usb" ou "bt".
      states: sequência de `ControllerState` retornados em cada `read_state`.
        Após esgotar, repete o último indefinidamente.
    """

    DEFAULT_STATE: ClassVar[ControllerState] = ControllerState(
        battery_pct=75,
        l2_raw=0,
        r2_raw=0,
        connected=False,
        transport="usb",
    )

    def __init__(
        self,
        transport: Transport = "usb",
        states: list[ControllerState] | None = None,
    ) -> None:
        self._transport: Transport = transport
        self._states: list[ControllerState] = states or []
        self._idx: int = 0
        self._connected: bool = False
        self.commands: list[FakeControllerCommand] = []

    def connect(self) -> None:
        self._connected = True
        if not self._states:
            self._states = [
                ControllerState(
                    battery_pct=75,
                    l2_raw=0,
                    r2_raw=0,
                    connected=True,
                    transport=self._transport,
                )
            ]
        self.commands.append(FakeControllerCommand("connect", None))

    def disconnect(self) -> None:
        self._connected = False
        self.commands.append(FakeControllerCommand("disconnect", None))

    def is_connected(self) -> bool:
        return self._connected

    def read_state(self) -> ControllerState:
        if not self._connected:
            raise RuntimeError("FakeController nao conectado — chamar connect() antes")
        if self._idx < len(self._states):
            state = self._states[self._idx]
            self._idx += 1
        else:
            state = self._states[-1]
        return state

    def set_trigger(self, side: Side, effect: TriggerEffect) -> None:
        self.commands.append(FakeControllerCommand("set_trigger", (side, effect)))

    def set_led(self, color: tuple[int, int, int]) -> None:
        self.commands.append(FakeControllerCommand("set_led", color))

    def set_rumble(self, weak: int, strong: int) -> None:
        self.commands.append(FakeControllerCommand("set_rumble", (weak, strong)))

    def get_battery(self) -> int:
        if not self._states:
            return FakeController.DEFAULT_STATE.battery_pct
        idx = min(self._idx, len(self._states) - 1)
        return self._states[idx].battery_pct

    def get_transport(self) -> Transport:
        return self._transport


__all__ = ["FakeController", "FakeControllerCommand"]
