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


#: FEAT-COOP-PLAYER-LED-01 / COR-03 — padrões canônicos do DualSense para os 5
#: LEDs de player (ordem física esquerda→direita: [L2, L1, centro, R1, R2]), os
#: mesmos que o PS5 usa para indicar P1..P4. Moraram em
#: `daemon.subsystems.coop` até o COR-03; agora vivem aqui (camada core, sem
#: dependência de daemon) porque a cor automática por controle usa o MESMO
#: padrão fora do co-op (D7 — "número do controle"). O coop reexporta.
#:
#: R-25 (auditoria 25/07): a tabela vai até 8. Antes ela ia até 4 e TODO
#: índice ≥5 caía no mesmo "acende os 5" — dois controles em slots 5 e 6
#: exibiam o MESMO padrão, que é exatamente a colisão que a numeração única
#: (R-24) existe para matar. Os padrões 6..8 são escolhas desta casa, com um
#: único critério: serem distinguíveis A OLHO dos canônicos 1..5 e entre si
#: (extremos / três centrais / três à esquerda).
_PLAYER_LED_PATTERNS: dict[int, tuple[bool, bool, bool, bool, bool]] = {
    1: (False, False, True, False, False),
    2: (False, True, False, True, False),
    3: (True, False, True, False, True),
    4: (True, True, False, True, True),
    5: (True, True, True, True, True),
    6: (True, False, False, False, True),
    7: (False, True, True, True, False),
    8: (True, True, True, False, False),
}

#: R-25: padrão de "slot fora da tabela" (≥9). Distinto de TODOS os de cima,
#: então nunca é confundido com um número real; só colide consigo mesmo, e
#: para isso a casa precisaria de nove controles ligados ao mesmo tempo.
_PLAYER_LED_OVERFLOW = (True, False, True, True, False)


def player_led_pattern(index: int) -> tuple[bool, bool, bool, bool, bool]:
    """Padrão canônico de player-LED do jogador/controle `index`.

    1..4 são os padrões do PS5. 5..8 são extensões desta casa (R-25) — o
    espaço de numeração é ÚNICO entre DualSense, externos e co-op (R-24), e
    um DualSense pode legitimamente cair no slot 5+ quando há externos
    numerados antes dele. ≥9 cai no padrão de overflow, distinto dos oito.
    """
    return _PLAYER_LED_PATTERNS.get(index, _PLAYER_LED_OVERFLOW)


def numero_do_padrao_de_jogador(bits: object) -> int | None:
    """INVERSA de :func:`player_led_pattern`: número que um padrão representa.

    Existe porque o único número de jogador cuja AUTORIDADE é o jogo chega
    até nós como cinco bits — o relatório de saída HID que o jogo escreve e
    que o backend guarda em ``player_leds_game``. Sem esta tradução aquele
    dado não vira número em lugar nenhum, e a interface fica só com o número
    que NÓS inventamos.

    Contar os LEDs acesos seria errado: no DualSense o jogador 1 acende o LED
    do MEIO, não o primeiro. A tradução tem de ser pela tabela.

    ``None`` para qualquer coisa fora da tabela (padrão desconhecido, lista de
    tamanho errado, ausente). Inventar um número aqui repetiria, na
    interface, o erro que a leitura de ``/sys/class/leds`` já causou uma vez
    na investigação de 25/07 — a tabela do kernel é IDÊNTICA à nossa em 1..4,
    então um padrão só diz "que número", nunca "quem escreveu".
    """
    if not isinstance(bits, (list, tuple)) or len(bits) != 5:
        return None
    alvo = tuple(bool(b) for b in bits)
    for numero, padrao in _PLAYER_LED_PATTERNS.items():
        if padrao == alvo:
            return numero
    return None


#: COR-03 — paleta automática de lightbar por controle, estilo PS5 (cores por
#: ordem de conexão). Valores canônicos desta casa (decisão documentada do
#: sprint 2026-07-16-sprint-cores-e-led-automaticos): primárias puras + rosa
#: vivo — máxima distinguibilidade entre colunas lado a lado, e o rosa (255,
#: 0, 128) em vez do magenta puro para não confundir com o azul em brilho
#: baixo. A cor daqui é a IDENTIDADE (pré-brilho, D8); quem escala pelo
#: `lightbar_brightness` do perfil é o provider (D11), pelo mesmo caminho do
#: global (`LedSettings.apply_brightness`).
#:
#: R-25: 5..8 seguem o MESMO motivo da tabela de padrões acima — com o espaço
#: de numeração único (R-24) o slot 5+ é alcançável, e "branco para todo mundo
#: acima de 4" fazia dois controles ficarem da mesma cor. Amarelo/ciano/laranja
#: fecham o círculo cromático sem chegar perto do azul-em-brilho-baixo.
_PLAYER_SLOT_COLORS: dict[int, RGB] = {
    1: (0, 0, 255),  # azul (P1 no PS5)
    2: (255, 0, 0),  # vermelho (P2)
    3: (0, 255, 0),  # verde (P3)
    4: (255, 0, 128),  # rosa (P4)
    5: (255, 255, 0),  # amarelo
    6: (0, 255, 255),  # ciano
    7: (255, 128, 0),  # laranja
    8: (128, 0, 255),  # roxo
}


def player_slot_color(slot: int) -> RGB:
    """Cor canônica de lightbar do controle `slot` (1=azul, 2=vermelho, 3=verde, 4=rosa).

    5..8 são extensões desta casa (R-25, ver tabela). Slot ≥9 cai no branco —
    fallback neutro, distinguível das oito cores acima.
    """
    return _PLAYER_SLOT_COLORS.get(slot, (255, 255, 255))


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


__all__ = [
    "RGB",
    "LedSettings",
    "apply_led_settings",
    "hex_to_rgb",
    "numero_do_padrao_de_jogador",
    "off",
    "player_bitmask",
    "player_led_pattern",
    "player_slot_color",
]
