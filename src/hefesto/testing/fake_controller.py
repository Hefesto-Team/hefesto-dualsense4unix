"""Backend fake para testes sem hardware.

Implementa `IController` com comportamento determinístico:
- Inicia desconectado; `connect()` marca conectado e carrega um snapshot.
- `read_state()` avança entre snapshots pré-definidos (ou um padrão único).
- `set_trigger/set_led/set_rumble` gravam em listas internas pra inspeção.

Replay de captures binários (V2-13, V3-8, INFRA.2): formato é JSONL
comprimido com gzip; `FakeController.from_capture(path)` carrega e
cada `read_state()` avança pela trilha temporal.
"""
from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
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


@dataclass
class FakeLedState:
    """Último estado de LED aplicado via set_led — inspecionado em testes.

    - `color`: RGB (r, g, b) enviado ao hardware (ja com brightness escalado).
    - `brightness`: valor float [0.0, 1.0] do último set_led_with_brightness.
      Fica em None se set_led foi chamado sem brightness (compatibilidade).
    """

    color: tuple[int, int, int]
    brightness: float | None = None


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
        self.last_player_leds: tuple[bool, bool, bool, bool, bool] | None = None
        # Último estado de LED gravado — inspecionado em testes de brightness.
        self.last_led: FakeLedState | None = None

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
            raise RuntimeError("FakeController não conectado — chamar connect() antes")
        if self._idx < len(self._states):
            state = self._states[self._idx]
            self._idx += 1
        else:
            state = self._states[-1]
        return state

    def set_trigger(self, side: Side, effect: TriggerEffect) -> None:
        self.commands.append(FakeControllerCommand("set_trigger", (side, effect)))

    def set_led(self, color: tuple[int, int, int]) -> None:
        self.last_led = FakeLedState(color=color)
        self.commands.append(FakeControllerCommand("set_led", color))

    def set_rumble(self, weak: int, strong: int) -> None:
        self.commands.append(FakeControllerCommand("set_rumble", (weak, strong)))

    def set_player_leds(self, bits: tuple[bool, bool, bool, bool, bool]) -> None:
        """Grava bitmask de player LEDs para inspeção em testes."""
        self.last_player_leds = bits
        self.commands.append(FakeControllerCommand("set_player_leds", bits))

    def get_battery(self) -> int:
        if not self._states:
            return FakeController.DEFAULT_STATE.battery_pct
        idx = min(self._idx, len(self._states) - 1)
        return self._states[idx].battery_pct

    def get_transport(self) -> Transport:
        return self._transport

    @classmethod
    def from_capture(cls, path: Path | str) -> FakeController:
        """Carrega capture .bin gerado por record_hid_capture.py.

        Lê header (transport, version, sample_hz), converte cada sample em
        `ControllerState` e devolve `FakeController` pronto com a sequência
        cronológica. Testes chamam `connect()` e depois `read_state()` em
        loop pra iterar pelos snapshots.
        """
        p = Path(path)
        with gzip.open(p, "rb") as f:
            raw = f.read().decode("utf-8")

        lines = [line for line in raw.splitlines() if line.strip()]
        if not lines:
            raise ValueError(f"capture vazio: {p}")

        header = json.loads(lines[0])
        if header.get("type") != "header":
            raise ValueError(f"primeiro registro de {p} não é header")
        if header.get("version") != 1:
            raise ValueError(f"capture version {header.get('version')} não suportado")

        transport_raw = header.get("transport", "usb")
        if transport_raw not in ("usb", "bt"):
            raise ValueError(f"transport invalido no capture: {transport_raw}")
        transport: Transport = transport_raw

        states: list[ControllerState] = []
        for raw_line in lines[1:]:
            sample = json.loads(raw_line)
            state = ControllerState(
                battery_pct=int(sample.get("battery", 0)),
                l2_raw=int(sample.get("l2", 0)),
                r2_raw=int(sample.get("r2", 0)),
                connected=bool(sample.get("connected", True)),
                transport=transport,
                raw_lx=int(sample.get("lx", 128)),
                raw_ly=int(sample.get("ly", 128)),
                raw_rx=int(sample.get("rx", 128)),
                raw_ry=int(sample.get("ry", 128)),
            )
            states.append(state)

        return cls(transport=transport, states=states)


__all__ = ["FakeController", "FakeControllerCommand", "FakeLedState"]
