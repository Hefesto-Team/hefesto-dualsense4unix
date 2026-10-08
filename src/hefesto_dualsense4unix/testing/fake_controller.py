"""Backend fake para testes sem hardware."""
from __future__ import annotations

import gzip
import json
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from hefesto_dualsense4unix.core.controller import (
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
    """Último estado de LED aplicado via set_led — inspecionado em testes."""

    color: tuple[int, int, int]
    brightness: float | None = None


class FakeController(IController):
    """Controle fake para testes unit e integration.

    Tem tomada, como o aparelho: plugado (o padrão), o `connect()` liga; depois de
    `desplugar()` ele falha na hora em que RODA, como o backend real sem dispositivo,
    venha a sonda do `reconnect_loop` de quando vier, até um `plugar()`. Antes da tomada o
    dublê religava sozinho: a sonda chamava `connect()` e ele punha `_connected = True` sem
    aparelho (medido sob carga: `disconnect` em 0,113 s, `connect` em 0,114 s, a queda desfeita
    antes de o laço de poll a ver). Trocar o método na instância não bastava: a sonda já na fila
    do executor religava DEPOIS da queda publicada. Por isso a decisão é tomada dentro da trava.
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
        plugado: bool = True,
    ) -> None:
        self._tomada = threading.Lock()
        self.plugado: bool = plugado
        self.tentativas_de_conexao: int = 0
        self._transport: Transport = transport
        self._states: list[ControllerState] = states or []
        self._idx: int = 0
        self._connected: bool = False
        self.commands: list[FakeControllerCommand] = []
        self.last_player_leds: tuple[bool, bool, bool, bool, bool] | None = None
        self.last_led: FakeLedState | None = None
        self.mic_led_history: list[bool] = []
        self._next_buttons: frozenset[str] = frozenset()
        self.mic_btn_pressed: bool = False

    def set_buttons(self, names: Iterable[str]) -> None:
        """Define o conjunto de botões pressionados injetado no próximo read_state."""
        self._next_buttons = frozenset(names)

    def connect(self) -> None:
        # a decisão é tomada DENTRO da trava do desplugar: uma sonda já na fila do executor
        # não religa depois da queda publicada
        with self._tomada:
            self.tentativas_de_conexao += 1
            if not self.plugado:
                raise RuntimeError("sem dispositivo: o controle está desplugado")
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

    def desplugar(self) -> None:
        """O controle sai da tomada e NÃO volta sozinho: o `connect()` falha até o `plugar()`."""
        with self._tomada:
            self.plugado = False
            self.disconnect()

    def plugar(self) -> None:
        """O controle volta à tomada. Não conecta: quem conecta é o `connect()` da sonda."""
        with self._tomada:
            self.plugado = True

    def disconnect(self) -> None:
        self._connected = False
        self.commands.append(FakeControllerCommand("disconnect", None))

    def is_connected(self) -> bool:
        return self._connected

    def read_state(self) -> ControllerState:
        """Retorna próximo estado da lista (ou repete o último)."""
        if not self._connected:
            raise RuntimeError("FakeController não conectado — chamar connect() antes")
        if self._idx < len(self._states):
            state = self._states[self._idx]
            self._idx += 1
        else:
            state = self._states[-1]
        if not state.buttons_pressed:
            extra: frozenset[str] = frozenset()
            if self.mic_btn_pressed:
                extra = frozenset({"mic_btn"})
            combined = self._next_buttons | extra
            if combined:
                import dataclasses
                state = dataclasses.replace(state, buttons_pressed=combined)
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

    def set_mic_led(self, aceso: bool) -> None:
        """Grava histórico de chamadas para inspeção em testes (INFRA-SET-MIC-LED-01)."""
        self.mic_led_history.append(bool(aceso))
        self.commands.append(FakeControllerCommand("set_mic_led", bool(aceso)))

    def get_battery(self) -> int:
        if not self._states:
            return FakeController.DEFAULT_STATE.battery_pct
        idx = min(self._idx, len(self._states) - 1)
        return self._states[idx].battery_pct

    def get_transport(self) -> Transport:
        return self._transport

    @classmethod
    def from_capture(cls, path: Path | str) -> FakeController:
        """Carrega capture .bin gerado por record_hid_capture.py."""
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
