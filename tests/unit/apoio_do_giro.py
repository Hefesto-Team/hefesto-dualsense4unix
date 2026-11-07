"""O que o hub entrega num tique: o ângulo percorrido e o tempo do kernel que ele cobre."""

from __future__ import annotations

TIQUE_S = 0.01


def tique_de(
    velocidade: tuple[float, float, float] | None, segundos: float = TIQUE_S
) -> tuple[tuple[float, float, float], float] | None:
    """A leitura que dá ``velocidade`` graus/s de média, ou ``None`` sem leitor."""
    if velocidade is None:
        return None
    return (
        (velocidade[0] * segundos, velocidade[1] * segundos, velocidade[2] * segundos),
        segundos,
    )
