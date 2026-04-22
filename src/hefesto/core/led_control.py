"""Controle de LEDs do DualSense.

API de alto nível: lightbar RGB, 5 LEDs de jogador (bitmask) e LED do microfone.
O backend (`IController.set_led`) só aceita a cor da lightbar hoje; os player
LEDs e o mic LED dependem de API complementar no backend (a adicionar quando
houver necessidade em W5.x). Aqui expomos dataclasses de configuração que a
TUI e os perfis consomem.

Uso:
    from hefesto.core.led_control import LedSettings, apply_led_settings
    apply_led_settings(controller, LedSettings(lightbar=(255, 128, 0)))
"""
from __future__ import annotations

from dataclasses import dataclass

from hefesto.core.controller import IController

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class LedSettings:
    """Configuração imutável de LEDs.

    - `lightbar`: RGB 0-255 cada.
    - `player_leds`: lista de 5 booleanos para os indicadores inferiores
      (esquerda para direita). Padrão: todos apagados.
    - `mic_led`: estado do LED do microfone (True=ligado).
    """

    lightbar: RGB
    player_leds: tuple[bool, bool, bool, bool, bool] = (False, False, False, False, False)
    mic_led: bool = False

    def __post_init__(self) -> None:
        if len(self.lightbar) != 3:
            raise ValueError(f"lightbar precisa 3 componentes, recebeu {len(self.lightbar)}")
        for idx, v in enumerate(self.lightbar):
            if not (0 <= v <= 255):
                raise ValueError(f"lightbar[{idx}] fora de byte: {v}")

    def apply_brightness(self, level: float) -> LedSettings:
        """Devolve cópia com canais RGB escalados por ``level`` (clamp 0-255).

        ``level`` é multiplicador linear. Valores fora de [0.0, 1.0] são
        tolerados e acabam truncados pelo clamp por canal; isso cobre
        futura curva de resposta não-linear sem quebrar o contrato atual.
        """
        r, g, b = self.lightbar
        scaled: RGB = (
            max(0, min(255, int(r * level))),
            max(0, min(255, int(g * level))),
            max(0, min(255, int(b * level))),
        )
        return LedSettings(
            lightbar=scaled,
            player_leds=self.player_leds,
            mic_led=self.mic_led,
        )


def player_bitmask(leds: tuple[bool, bool, bool, bool, bool]) -> int:
    """Converte 5 flags em bitmask 0-31 (mesmo layout usado pelo protocolo DSX)."""
    value = 0
    for idx, on in enumerate(leds):
        if on:
            value |= 1 << idx
    return value


def apply_led_settings(controller: IController, settings: LedSettings) -> None:
    """Aplica settings no controle. Usa apenas `set_led` por enquanto.

    Player LEDs e mic LED são mantidos no `LedSettings` para serialização
    de perfis; o backend completará quando expor API específica.
    """
    controller.set_led(settings.lightbar)


def off() -> LedSettings:
    return LedSettings(lightbar=(0, 0, 0))


def hex_to_rgb(hex_str: str) -> RGB:
    """Converte '#RRGGBB' ou 'RRGGBB' para tupla (r, g, b)."""
    s = hex_str.strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"hex_to_rgb espera formato RRGGBB, recebeu: {hex_str!r}")
    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
    except ValueError as exc:
        raise ValueError(f"hex_to_rgb: componente não numérico em {hex_str!r}") from exc
    return (r, g, b)


__all__ = ["RGB", "LedSettings", "apply_led_settings", "hex_to_rgb", "off", "player_bitmask"]
