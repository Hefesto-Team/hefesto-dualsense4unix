"""8BIT-02: escreve o LED de player dos controles externos (Nintendo/8BitDo).

O co-op precisa de um número DISTINTO por controle. O Hefesto já dá 1..N aos
DualSense (via o LED próprio deles); aqui ele continua a contagem nos externos
(o 1º externo = slot N+1) escrevendo o LED de player que o kernel expõe:
``/sys/class/leds/<inst-hid>:green:player-{1..4}`` (atributo ``brightness``;
o Nintendo usa VERDE — o DualSense usa branco). Assim o LED físico bate com o
número da GUI.

SÓ LED, nunca input: o Hefesto não adota esses controles (o input segue pelo
kernel/Steam). A regra udev ``79-external-controller-leds`` torna esses nós
graváveis pelo daemon (sudo-zero). Sem a regra, a escrita falha em SILÊNCIO
(best-effort) e o LED fica no default do kernel — sem regressão.
"""
from __future__ import annotations

import os

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Raiz da classe LED (monkeypatchável nos testes via env, como em sysfs_leds).
LEDS_ROOT: str = os.environ.get(
    "HEFESTO_DUALSENSE4UNIX_LEDS_ROOT", "/sys/class/leds"
)

#: Co-op numera 1..4 nos LEDs verdes; o 5º (azul) fica fora do padrão de player.
_MAX_PLAYER_LEDS = 4


def hid_instance_for_hidraw(hidraw_dev: str | None) -> str | None:
    """``/dev/hidraw2`` -> a instância HID (``0003:057E:2009.000E``) via sysfs.

    É o prefixo dos nós LED do controle. ``None`` quando não resolve (device
    sumiu, sem sysfs) — o chamador trata como "sem LED gravável".
    """
    if not hidraw_dev:
        return None
    name = os.path.basename(str(hidraw_dev))
    if not name.startswith("hidraw"):
        return None
    try:
        target = os.path.realpath(f"/sys/class/hidraw/{name}/device")
    except OSError:
        return None
    inst = os.path.basename(target)
    return inst or None


def _set_brightness(path: str, value: int) -> bool:
    """Escreve ``value`` no ``brightness`` do nó LED. Best-effort (False sem
    nó/permissão, nunca levanta)."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "w", encoding="ascii") as fh:
            fh.write(str(value))
        return True
    except OSError:
        return False


def write_player_number(
    hid_instance: str, number: int, leds_root: str | None = None
) -> bool:
    """Acende os LEDs verdes 1..``number`` do controle, apaga os demais.

    ``number`` capado em [1, 4] (padrão de player estilo Nintendo: N LEDs à
    esquerda). O 5º (azul) é apagado. Devolve True se escreveu em ao menos um
    nó — False quando nenhum nó existe/é gravável (sem a regra udev, sem
    regressão). Nunca levanta.
    """
    root = leds_root if leds_root is not None else LEDS_ROOT
    n = max(1, min(_MAX_PLAYER_LEDS, int(number)))
    escreveu = False
    for i in range(1, _MAX_PLAYER_LEDS + 1):
        alvo = f"{root}/{hid_instance}:green:player-{i}/brightness"
        escreveu = _set_brightness(alvo, 1 if i <= n else 0) or escreveu
    # co-op usa 1..4; garante o 5º (azul) apagado se existir.
    _set_brightness(f"{root}/{hid_instance}:blue:player-5/brightness", 0)
    return escreveu


__all__ = ["LEDS_ROOT", "hid_instance_for_hidraw", "write_player_number"]
