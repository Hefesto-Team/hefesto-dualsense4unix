"""Controle de LEDs do DualSense.

API de alto nível: lightbar RGB, 5 LEDs de jogador (bitmask) e LED do microfone.

Cobertura atual:
- Lightbar RGB: `IController.set_led` (implementado).
- LED do microfone: `IController.set_mic_led` (implementado — INFRA-SET-MIC-LED-01).
  **Não é aplicado por `apply_led_settings`**: mic_led é tratado como estado
  runtime puro (ver AUDIT-FINDING-PROFILE-MIC-LED-RESET-01 e armadilha A-06).
  Transições de mic_led vêm do botão físico ou de handlers IPC dedicados
  (`udp_server` MicLED, `HotkeyManager` mic_btn), nunca de profile switch.
- Player LEDs: `IController.set_player_leds` (implementado — player bitmask).
  Player LEDs continuam com API básica de bitmask; efeitos avançados (animação)
  dependem de sprint futura.

Uso:
    from hefesto_dualsense4unix.core.led_control import LedSettings, apply_led_settings
    apply_led_settings(controller, LedSettings(lightbar=(255, 128, 0)))
"""
from __future__ import annotations

from dataclasses import dataclass

from hefesto_dualsense4unix.core.controller import IController

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class LedSettings:
    """Configuração imutável de LEDs.

    - `lightbar`: RGB 0-255 cada.
    - `brightness_level`: multiplicador de brilho [0.0, 1.0]; aplicado
      sobre o RGB antes de enviar ao hardware. 1.0 = sem dimming.
    - `player_leds`: lista de 5 booleanos para os indicadores inferiores
      (esquerda para direita). Padrão: todos apagados.
    - `mic_led`: **reservado / no-op em `apply_led_settings`**. Preservado no
      dataclass por compatibilidade de API (callers antigos que instanciavam
      `LedSettings(lightbar=..., mic_led=...)` seguem válidos), mas o valor
      NÃO é propagado ao hardware pelo apply. Mic LED é estado runtime puro:
      muda via botão físico ou IPC `led.mic_set` / `udp MicLED`, nunca via
      profile switch (AUDIT-FINDING-PROFILE-MIC-LED-RESET-01; A-06).
    """

    lightbar: RGB
    brightness_level: float = 1.0
    player_leds: tuple[bool, bool, bool, bool, bool] = (False, False, False, False, False)
    mic_led: bool = False

    def __post_init__(self) -> None:
        if len(self.lightbar) != 3:
            raise ValueError(f"lightbar precisa 3 componentes, recebeu {len(self.lightbar)}")
        for idx, v in enumerate(self.lightbar):
            if not (0 <= v <= 255):
                raise ValueError(f"lightbar[{idx}] fora de byte: {v}")
        if not (0.0 <= self.brightness_level <= 1.0):
            raise ValueError(
                f"brightness_level fora de [0.0, 1.0]: {self.brightness_level}"
            )

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
            brightness_level=self.brightness_level,
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
    """Aplica settings no controle.

    Escala o RGB pelo `brightness_level` antes de enviar — garante que perfis
    com brilho reduzido chegam ao hardware com a intensidade correta.

    Propaga os 5 Player LEDs via `controller.set_player_leds(settings.player_leds)`
    (BUG-PLAYER-LEDS-APPLY-01; armadilha A-06 fechada para player_leds).

    Sem esta propagação, perfis que definem `player_leds` no JSON são carregados
    pelo ProfileManager e salvos no draft, mas os bits nunca chegam ao controle:
    o autoswitch e `profile.switch` exibem a marcação correta na GUI enquanto o
    hardware segue com a configuração antiga do boot ou do último toggle manual.

    **Mic LED é intencionalmente preservado**: `settings.mic_led` NÃO é aplicado
    (AUDIT-FINDING-PROFILE-MIC-LED-RESET-01; A-06 variante "campo ausente em
    LedsConfig mas aplicado com default regride estado runtime"). Transições do
    LED do microfone seguem caminho explícito — botão físico via HotkeyManager,
    IPC dedicado via UDP MicLED / `led.mic_set` futuro — e jamais colateral de
    profile switch.
    """
    effective = settings.apply_brightness(settings.brightness_level)
    controller.set_led(effective.lightbar)
    controller.set_player_leds(settings.player_leds)


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
