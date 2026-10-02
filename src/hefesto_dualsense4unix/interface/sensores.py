"""sensor_widgets.py — giroscópio, microfone, touchpad, lightbar e alto-falante."""
from __future__ import annotations

from typing import Final

RGB = tuple[float, float, float]


#: Fundo de escala das barras de giroscópio, em graus/s. O DualSense reporta
ESCALA_GYRO_GRAUS_S: Final[float] = 500.0


def texto_eixo(graus_por_s: float) -> str:
    """Rótulo numérico de um eixo, em largura FIXA."""
    return f"{graus_por_s:>+7.1f}"


#: `ESCALA_GYRO_GRAUS_S`, e o mesmo raciocínio: o sensor vai a ±4 g
ESCALA_ACCEL_G: Final[float] = 2.0


def texto_eixo_g(g: float) -> str:
    """Rótulo numérico de um eixo de acelerômetro, em largura FIXA."""
    return f"{g:>+7.2f}"


from hefesto_dualsense4unix.core.speaker_scale import (  # noqa: E402
    fracao_do_volume,
    percentual_do_volume,
    volume_do_percentual,
)


def texto_volume(volume: int, muted: bool | None) -> str:
    """Rótulo do alto-falante: "Mudo" ou a porcentagem do volume."""
    if muted:
        return "Mudo"
    return f"{percentual_do_volume(volume)} %"


def texto_toques(quantidade: int) -> str:
    """Rótulo do touchpad: "Sem toque" ou "N toque"/"N toques"."""
    if quantidade <= 0:
        return "Sem toque"
    if quantidade == 1:
        return "1 toque"
    return f"{quantidade} toques"


def posicao_normalizada(
    x: int, y: int, largura: int, altura: int
) -> tuple[float, float]:
    """Coordenada absoluta do kernel -> fração 0.0..1.0 do retângulo."""
    fx = x / largura if largura > 0 else 0.0
    fy = y / altura if altura > 0 else 0.0
    return (max(0.0, min(1.0, fx)), max(0.0, min(1.0, fy)))


__all__ = [
    "ESCALA_ACCEL_G",
    "ESCALA_GYRO_GRAUS_S",
    "fracao_do_volume",
    "percentual_do_volume",
    "posicao_normalizada",
    "texto_eixo",
    "texto_eixo_g",
    "texto_toques",
    "texto_volume",
    "volume_do_percentual",
]
