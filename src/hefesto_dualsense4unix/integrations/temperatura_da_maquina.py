"""O calor da máquina para a «Cor da temperatura» (A-LUZ-DE-AMBIENTE-E-DE-AVISO-01).

Só leitura do ``/sys/class/hwmon``. Os sensores do processador e da placa de vídeo se descobrem
pelo nome do chip, e o limite de cada um é o ``crit`` (ou o ``max``) que o próprio sensor declara:
nenhum número de uma máquina fica no código. O calor é a fração do caminho entre o frio (uma
constante física, a temperatura de um quarto) e esse limite, e vale o do sensor mais perto do seu.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

RAIZ_DO_HWMON = Path("/sys/class/hwmon")
#: Os chips que são o processador ou a placa de vídeo, pelo nome do driver do kernel.
CHIPS_DO_PROCESSADOR = frozenset({"k10temp", "coretemp", "zenpower", "cpu_thermal"})
CHIPS_DA_PLACA_DE_VIDEO = frozenset({"amdgpu", "radeon", "nouveau", "nvidia", "i915", "xe"})
CHIPS_DE_CALOR = CHIPS_DO_PROCESSADOR | CHIPS_DA_PLACA_DE_VIDEO
#: O azul: a temperatura de um quarto, igual para qualquer máquina.
FRIO_C = 30.0
#: Um limite que não passa disto acima do frio não é limite (a escala viraria um degrau).
FOLGA_MINIMA_C = 10.0
#: A leitura vale por tanto tempo; a descoberta dos sensores se refaz de tempos em tempos.
VALIDADE_S = 2.0
REDESCOBRIR_A_CADA_S = 30.0


@dataclass(frozen=True)
class Sensor:
    """Um sensor de temperatura: onde ler e o limite que o próprio chip declara (em °C)."""

    chip: str
    entrada: Path
    limite_c: float


def _ler_texto(caminho: Path) -> str | None:
    """O texto de um arquivo do hwmon, sem as pontas; ``None`` se não existe ou não lê."""
    texto: str | None = None
    try:
        texto = caminho.read_text().strip()
    except OSError:
        texto = None
    return texto


def _ler_milli(caminho: Path) -> float | None:
    """Um valor do hwmon em milésimos de grau, em °C; ``None`` se não existe ou não lê."""
    texto = _ler_texto(caminho)
    if texto is None or not texto.lstrip("-").isdigit():
        return None
    return int(texto) / 1000.0


def descobrir(raiz: Path = RAIZ_DO_HWMON) -> list[Sensor]:
    """Os sensores do processador e da placa de vídeo que declaram um limite (``crit``/``max``)."""
    achados: list[Sensor] = []
    try:
        pastas = sorted(raiz.glob("hwmon*"))
    except OSError:
        return achados
    for pasta in pastas:
        chip = _ler_texto(pasta / "name")
        if chip not in CHIPS_DE_CALOR:
            continue
        for entrada in sorted(pasta.glob("temp*_input")):
            prefixo = entrada.name.removesuffix("_input")
            limite = _ler_milli(pasta / f"{prefixo}_crit")
            if limite is None or limite < FRIO_C + FOLGA_MINIMA_C:
                limite = _ler_milli(pasta / f"{prefixo}_max")
            if limite is None or limite < FRIO_C + FOLGA_MINIMA_C:
                continue
            achados.append(Sensor(chip, entrada, limite))
    return achados


def calor_dos(sensores: list[Sensor]) -> float | None:
    """A maior fração (0 a 1) entre os sensores que leem; ``None`` se nenhum lê."""
    fracoes: list[float] = []
    for sensor in sensores:
        graus = _ler_milli(sensor.entrada)
        if graus is None:
            continue
        fracoes.append(max(0.0, min(1.0, (graus - FRIO_C) / (sensor.limite_c - FRIO_C))))
    return max(fracoes) if fracoes else None


def calor_da_maquina(raiz: Path = RAIZ_DO_HWMON) -> float | None:
    """O calor de agora, sem guardar nada; ``None`` sem nenhum sensor com limite."""
    return calor_dos(descobrir(raiz))


class LeitorDoCalor:
    """O calor com cache: lê a cada ``VALIDADE_S`` e redescobre os sensores de vez em quando."""

    def __init__(
        self,
        raiz: Path = RAIZ_DO_HWMON,
        agora: Callable[[], float] = time.monotonic,
    ) -> None:
        self._raiz = raiz
        self._agora = agora
        self._sensores: list[Sensor] = []
        self._descoberto_em = float("-inf")
        self._lido_em = float("-inf")
        self._calor: float | None = None

    def calor(self) -> float | None:
        agora = self._agora()
        if agora - self._lido_em < VALIDADE_S:
            return self._calor
        if not self._sensores and agora - self._descoberto_em >= REDESCOBRIR_A_CADA_S:
            self._sensores = descobrir(self._raiz)
            self._descoberto_em = agora
            logger.debug("calor_sensores", quantos=len(self._sensores))
        self._lido_em = agora
        self._calor = calor_dos(self._sensores)
        return self._calor


__all__ = [
    "FRIO_C",
    "LeitorDoCalor",
    "Sensor",
    "calor_da_maquina",
    "calor_dos",
    "descobrir",
]
