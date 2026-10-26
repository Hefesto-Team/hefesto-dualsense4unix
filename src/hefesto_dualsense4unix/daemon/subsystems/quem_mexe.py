"""A mão está no controle? Botão, gatilho ou eixo fora da zona morta.

Foi o sinal do portão da háptica (``D-2609-QUEM-JOGA-E-QUEM-MEXE``, 26/09/2026),
que caducou em 26/10/2026 (A-HAPTICA-E-DO-JOGO-SEM-PORTAO-DE-QUEM-MEXE-01):
o que o jogo toca no endpoint de um controle chega a esse controle, mexa
alguém nele ou não, e o Hefesto só potencializa, nunca veta. As marcas da
partida (``QuemMexe``) e a fiação que as alimentava no laço e no co-op saíram.
Fica só a pergunta, que a bancada da entrada sozinha
(``scripts/ensaios/a_entrada_que_nasce_sozinha.py``) usa para separar o chiado
do aparelho da mão.
"""

from __future__ import annotations

from collections.abc import Iterable

from hefesto_dualsense4unix.integrations.uinput_mouse import MOVE_DEADZONE, STICK_CENTER

#: A zona morta do repouso (``uinput_mouse.MOVE_DEADZONE``): o repouso de um
#: DualSense fica a poucas unidades do centro.
ZONA_MORTA = MOVE_DEADZONE


def teve_entrada(
    *,
    botoes: Iterable[str],
    lx: int,
    ly: int,
    rx: int,
    ry: int,
    l2: int,
    r2: int,
) -> bool:
    """A mão está no controle neste tique? Botão, gatilho ou eixo fora da zona."""
    if botoes:
        return True
    if l2 > ZONA_MORTA or r2 > ZONA_MORTA:
        return True
    return any(abs(eixo - STICK_CENTER) > ZONA_MORTA for eixo in (lx, ly, rx, ry))


__all__ = ["ZONA_MORTA", "teve_entrada"]
