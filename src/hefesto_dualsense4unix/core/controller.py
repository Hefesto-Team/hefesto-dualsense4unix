"""Interface do controle DualSense.

Design síncrono deliberado (V2-7, ADR-001): o backend de referência
`pydualsense` é síncrono e backends futuros em C/Rust provavelmente
também. Acoplar a asyncio trava substituição. O daemon envolve as
chamadas em `loop.run_in_executor()` quando precisa de cooperação
com o event loop.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping

Transport = Literal["usb", "bt"]
Side = Literal["left", "right"]

ResultadoDeSaida = Literal[
    "escreveu", "registrado", "falhou", "sem_alvo", "nada_a_fazer"
]


@dataclass(frozen=True)
class TriggerEffect:
    """Efeito de gatilho no nível HID (baixo nível)."""

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
class OutputSpec:
    """Saída parcial desejada de um controle (PERFIL-01 / 4P-01)."""

    trigger_left: TriggerEffect | None = None
    trigger_right: TriggerEffect | None = None
    led: tuple[int, int, int] | None = None
    player_leds: tuple[bool, bool, bool, bool, bool] | None = None
    mic_led: bool | None = None
    player_led_brightness: int | None = None


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

    - `battery_state`: o ESTADO DE CARGA ao lado do percentual — uma das
      palavras de `backend_pydualsense.ESTADO_DE_CARGA` (``"descarregando"``,
      ``"carregando"``, ``"cheio"``, ``"fora_de_faixa"``, ``"erro"``) ou
      ``None`` = *"ninguém reportou ainda"*. BATERIA-PARADA-01 (B1): o
      percentual sozinho não distingue *"a barra congelou"* de *"está cheia
      porque está no cabo"*, e era essa ausência que a queixa de 26/08
      nomeava. Campo NOVO com default, para não quebrar quem constrói o
      snapshot com os cinco obrigatórios de sempre.
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
    battery_state: str | None = None

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
      - `hefesto_dualsense4unix.core.backend_pydualsense.PyDualSenseController` (hardware real).
      - `hefesto_dualsense4unix.testing.fake_controller.FakeController` (replay de capture
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
        """Define os 5 LEDs de player (indicadores abaixo do touchpad)."""
        ...

    @abstractmethod
    def set_mic_led(self, aceso: bool) -> None:
        """Acende (`aceso=True`) ou apaga (`aceso=False`) o LED do microfone."""
        ...

    @abstractmethod
    def get_battery(self) -> int: ...

    @abstractmethod
    def get_transport(self) -> Transport: ...

    # multi-controle (PyDualSenseController) sobrescreve os quatro com o

    def apply_output_defaults(self, spec: OutputSpec) -> ResultadoDeSaida | None:
        """Aplica `spec` como PADRÃO do perfil em TODOS os controles."""
        if spec.trigger_left is not None:
            self.set_trigger("left", spec.trigger_left)
        if spec.trigger_right is not None:
            self.set_trigger("right", spec.trigger_right)
        if spec.led is not None:
            self.set_led(spec.led)
        if spec.player_leds is not None:
            self.set_player_leds(spec.player_leds)
        if spec.mic_led is not None:
            self.set_mic_led(spec.mic_led)
        return None

    def apply_output_for(self, uniq: str, spec: OutputSpec) -> ResultadoDeSaida:
        """Aplica `spec` SÓ no controle de MAC `uniq` e registra o override."""
        if all(getattr(spec, campo.name) is None for campo in fields(spec)):
            return "nada_a_fazer"
        return "sem_alvo"

    def reset_output_overrides(
        self, overrides: Mapping[str, OutputSpec] | None = None
    ) -> None:
        """SUBSTITUI o mapa de overrides por-controle (ativação de perfil)."""
        return

    def resolved_player_leds_for(
        self, uniq: str
    ) -> tuple[bool, bool, bool, bool, bool] | None:
        """Padrão de player-LED RESOLVIDO do controle `uniq` (leitura pura)."""
        return None


__all__ = [
    "ControllerState",
    "IController",
    "OutputSpec",
    "ResultadoDeSaida",
    "Side",
    "Transport",
    "TriggerEffect",
]
