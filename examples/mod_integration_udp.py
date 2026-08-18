#!/usr/bin/env python3
"""Exemplo de integração via UDP DSX-compativel.

Demonstra como um mod externo (jogo, overlay, script) pode controlar os
gatilhos adaptativos, lightbar, player LEDs e mic LED do DualSense em
runtime, enviando JSON ao endpoint UDP `127.0.0.1:6969` do daemon Hefesto.

Schema: docs/protocol/udp-schema.md (versão 1, compatível bit-a-bit com DSX
Paliverse). Pré-requisito: daemon do Hefesto rodando com `udp_enabled=True`
(default em `daemon.toml`). Inicie com:

    hefesto-dualsense4unix daemon start --foreground

Em outro terminal, rode este script:

    python examples/mod_integration_udp.py

Você deverá ver na ordem (cada efeito dura ~1s):
  1) Gatilho R2 com efeito Rigid posição 5, força 200.
  2) Lightbar magenta (RGB 255, 0, 255).
  3) Player LED bitmask 0b10101 (LEDs 1, 3, 5 acesos).
  4) Mic LED on (1).
  5) Reset ao perfil ativo do usuário.

Para uso em produção, embarque um socket UDP no seu mod e envie
`json.dumps(envelope).encode()` para `127.0.0.1:6969`.
"""
from __future__ import annotations

import json
import socket
import time
from typing import Any

HEFESTO_HOST = "127.0.0.1"
HEFESTO_PORT = 6969


def send(envelope: dict[str, Any]) -> None:
    """Envia um envelope DSX-compativel ao daemon Hefesto via UDP."""
    payload = json.dumps(envelope).encode("utf-8")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(payload, (HEFESTO_HOST, HEFESTO_PORT))


def trigger_update(side: str, mode: str, *params: int) -> dict[str, Any]:
    """Constroi envelope `TriggerUpdate` (compat DSX v1).

    Aridade dos params depende do mode (ver docs/protocol/udp-schema.md).
    Exemplos:
      Rigid: [position, force]
      Pulse: [start_position, force, frequency]
      Galloping: [start_position, end_position, first_foot, second_foot, frequency]
    """
    return {
        "version": 1,
        "instructions": [
            {
                "type": "TriggerUpdate",
                "parameters": [side, mode, *params],
            }
        ],
    }


def rgb_update(idx: int, r: int, g: int, b: int) -> dict[str, Any]:
    """Lightbar RGB 24-bit (0..255 por canal)."""
    return {
        "version": 1,
        "instructions": [
            {
                "type": "RGBUpdate",
                "parameters": [idx, r, g, b],
            }
        ],
    }


def player_led(idx: int, bitmask: int) -> dict[str, Any]:
    """Player LEDs inferiores. bitmask 0b00001 ate 0b11111 (5 LEDs)."""
    return {
        "version": 1,
        "instructions": [
            {
                "type": "PlayerLED",
                "parameters": [idx, bitmask],
            }
        ],
    }


def mic_led(state: int) -> dict[str, Any]:
    """Mic LED: 0 off, 1 on (luz vermelha)."""
    return {
        "version": 1,
        "instructions": [
            {
                "type": "MicLED",
                "parameters": [state],
            }
        ],
    }


def reset_to_user_settings() -> dict[str, Any]:
    """Reverte o controle ao perfil ativo do daemon (descarta efeitos do mod)."""
    return {
        "version": 1,
        "instructions": [
            {
                "type": "ResetToUserSettings",
                "parameters": [],
            }
        ],
    }


def main() -> int:
    print("Exemplo de integração UDP DSX-compativel — Hefesto-Dualsense4Unix")
    print(f"Enviando para {HEFESTO_HOST}:{HEFESTO_PORT}")
    print()

    print("1) Gatilho R2: Rigid posição 5, força 200")
    send(trigger_update("right", "Rigid", 5, 200))
    time.sleep(1.5)

    print("2) Lightbar magenta (255, 0, 255)")
    send(rgb_update(0, 255, 0, 255))
    time.sleep(1.5)

    print("3) Player LED bitmask 0b10101 (LEDs 1, 3, 5 acesos)")
    send(player_led(0, 0b10101))
    time.sleep(1.5)

    print("4) Mic LED on")
    send(mic_led(1))
    time.sleep(1.5)

    print("5) Reset ao perfil do usuário")
    send(reset_to_user_settings())
    time.sleep(0.5)

    print()
    print("Pronto. Se nenhum efeito foi visível, confirme que o daemon está")
    print("rodando: hefesto-dualsense4unix daemon start --foreground")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
