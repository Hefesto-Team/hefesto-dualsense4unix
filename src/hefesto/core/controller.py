"""Interface do controle DualSense.

Design síncrono deliberado (V2-7, ADR-001): o backend de referência
`pydualsense` é síncrono e backends futuros em C/Rust provavelmente
também. Acoplar a asyncio trava substituição. O daemon envolve as
chamadas em `loop.run_in_executor()` quando precisa de cooperação
com o event loop.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

Transport = Literal["usb", "bt"]
Side = Literal["left", "right"]


@dataclass(frozen=True)
class TriggerEffect:
    """Efeito de gatilho no nível HID (baixo nível).

    Factories de alto nível (galloping, machine, bow, etc.) são entregues
    em W2.1 em `hefesto.core.trigger_effects`. Aqui expomos apenas o par
    canônico `(mode, forces)` que o protocolo HID aceita.

    - `mode`: valor do enum `pydualsense.TriggerModes` (0, 1, 2, 5, 6, 33, 34, 37, 38, 252).
    - `forces`: 7 bytes (0-255) na ordem dos offsets HID 11/12..17/20 (USB)
      ou 12/13..18/21 (BT). Posições não usadas pelo modo ficam em 0.
    """

    mode: int
    forces: tuple[int, int, int, int, int, int, int] = (0, 0, 0, 0, 0, 0, 0)

    def __post_init__(self) -> None:
        if not (0 <= self.mode <= 255):
            raise ValueError(f"mode fora de byte: {self.mode}")
        if len(self.forces) != 7:
            raise ValueError(f"forces precisa ter 7 elementos, recebeu {len(self.forces)}")
        for i, b in enumerate(self.forces):
            if not (0 <= b <= 255):
                raise ValueError(f"forces[{i}] fora de byte: {b}")


@dataclass(frozen=True)
class ControllerState:
    """Snapshot imutável do controle num instante.

    Campos mínimos em W1.1; botões, sticks e touchpad entram em W1.2.

    - `buttons_pressed`: conjunto de nomes canônicos dos botões fisicamente
      pressionados neste tick (ex.: ``{"cross", "l1", "mic_btn"}``). Populado
      pelo backend via evdev (ramo primário) ou HID-raw (`micBtn`). Nomes
      seguem o vocabulário de `EvdevReader.BUTTON_MAP`; o botão Mic usa o nome
      ``"mic_btn"`` pois não tem keycode evdev estável — vem por HID-raw via
      `ds.state.micBtn` (byte misc2, bit 0x04). Ver `PyDualSenseController.read_state`.
    """

    battery_pct: int
    l2_raw: int
    r2_raw: int
    connected: bool
    transport: Transport
    raw_buttons: int = 0
    raw_lx: int = 128
    raw_ly: int = 128
    raw_rx: int = 128
    raw_ry: int = 128
    buttons_pressed: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not (0 <= self.battery_pct <= 100):
            raise ValueError(f"battery_pct fora de 0..100: {self.battery_pct}")
        for name in ("l2_raw", "r2_raw", "raw_lx", "raw_ly", "raw_rx", "raw_ry"):
            v = getattr(self, name)
            if not (0 <= v <= 255):
                raise ValueError(f"{name} fora de byte: {v}")


class IController(ABC):
    """Interface síncrona para um controle DualSense.

    Implementações conhecidas:
      - `hefesto.core.backend_pydualsense.PyDualSenseController` (hardware real).
      - `hefesto.testing.fake_controller.FakeController` (replay de capture
        ou comportamento determinístico para testes e smoke).

    Métodos de output: `set_trigger`, `set_led`, `set_rumble`, `set_player_leds`,
    `set_mic_led`. Todos síncronos (ADR-001).
    """

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def read_state(self) -> ControllerState: ...

    @abstractmethod
    def set_trigger(self, side: Side, effect: TriggerEffect) -> None: ...

    @abstractmethod
    def set_led(self, color: tuple[int, int, int]) -> None: ...

    @abstractmethod
    def set_rumble(self, weak: int, strong: int) -> None: ...

    @abstractmethod
    def set_player_leds(self, bits: tuple[bool, bool, bool, bool, bool]) -> None:
        """Define os 5 LEDs de player (indicadores abaixo do touchpad).

        ``bits[0]`` corresponde ao LED 1 (extremo esquerdo), ``bits[4]`` ao LED 5
        (extremo direito). O bitmask resultante é enviado diretamente ao hardware
        via `pydualsense.light.playerNumber` (atributo `IntFlag` aceitando qualquer
        valor de 5 bits), sem exigir PlayerID canônico.
        """
        ...

    @abstractmethod
    def set_mic_led(self, muted: bool) -> None:
        """Acende (muted=True) ou apaga (muted=False) o LED do microfone.

        Convenção de semântica: `muted=True` → LED aceso (vermelho, padrão do
        firmware indicando "mic desligado"); `muted=False` → LED apagado.

        Implementação real via `ds.audio.setMicrophoneLED(bool)` (INFRA-SET-MIC-LED-01).
        Player LEDs ainda dependem de API complementar futura.
        """
        ...

    @abstractmethod
    def get_battery(self) -> int: ...

    @abstractmethod
    def get_transport(self) -> Transport: ...


__all__ = [
    "ControllerState",
    "IController",
    "Side",
    "Transport",
    "TriggerEffect",
]
