"""O pacote do «Data Out» do Forza vira um estado da corrida.

Da A-TELEMETRIA-DA-CORRIDA-CHEGA-AO-GATILHO-01. Puro: bytes entram, um ``EstadoDaCorrida`` sai, sem
socket nem relógio. Lê-se só o que o jogo publica e nenhum campo que as fontes não mostram; o
tamanho do pacote diz o formato (232, 311, 324 ou 331 bytes, little-endian). Os deslocamentos e as
fontes de cada campo: ``docs/protocol/telemetria-da-corrida.md``.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass

FORMATO_CURTO = "sled"
FORMATO_LONGO = "dash"
FORMATO_HORIZON = "horizon"
FORMATO_MOTORSPORT_2023 = "motorsport_2023"

FORMATO_DO_TAMANHO: dict[int, str] = {
    232: FORMATO_CURTO,
    311: FORMATO_LONGO,
    324: FORMATO_HORIZON,
    331: FORMATO_MOTORSPORT_2023,
}
INICIO_DO_DASH: dict[str, int] = {
    FORMATO_LONGO: 232,
    FORMATO_HORIZON: 244,
    FORMATO_MOTORSPORT_2023: 232,
}

_TIPOS_DO_SLED = "iI" + "f" * 27 + "iiii" + "f" * 20 + "iiiii"
_SLED = struct.Struct("<" + _TIPOS_DO_SLED)
_DASH = struct.Struct("<" + "f" * 17 + "H" + "B" * 6 + "bbb")

assert _SLED.size == 232
assert _DASH.size == 79

_I_CORRIDA_LIGADA = 0
_I_INSTANTE_MS = 1
_I_RPM_MAXIMO = 2
_I_RPM_OCIOSO = 3
_I_RPM = 4
_I_ACELERACAO = 5
_I_VELOCIDADE = 8
_I_RAZAO_DE_PATINACAO = 21
_I_GIRO_DAS_RODAS = 25
_I_NA_ZEBRA = 29
_I_PATINACAO_COMBINADA = 45
_D_VELOCIDADE = 3
_D_ACELERADOR = 19
_D_FREIO = 20
_D_MARCHA = 23

QUATRO = tuple[float, float, float, float]


@dataclass(frozen=True)
class EstadoDaCorrida:
    """O que um pacote diz: do formato curto sempre; os pedais, a marcha e a velocidade escalar
    só do longo (``None`` no curto)."""

    formato: str
    corrida_ligada: bool
    instante_ms: int
    rpm: float
    rpm_maximo: float
    rpm_ocioso: float
    aceleracao: tuple[float, float, float]
    velocidade_vetor: tuple[float, float, float]
    razao_de_patinacao: QUATRO
    giro_das_rodas: QUATRO
    na_zebra: tuple[bool, bool, bool, bool]
    patinacao_combinada: QUATRO
    velocidade: float | None = None
    acelerador: float | None = None
    freio: float | None = None
    marcha: int | None = None

    @property
    def velocidade_do_carro(self) -> float:
        """A velocidade em m/s: a do «Dash»; no curto, o módulo do vetor."""
        if self.velocidade is not None:
            return self.velocidade
        return math.sqrt(sum(v * v for v in self.velocidade_vetor))

    @property
    def tem_pedais(self) -> bool:
        return self.acelerador is not None and self.freio is not None

    @property
    def fracao_da_rotacao(self) -> float | None:
        """A rotação entre a marcha lenta (0) e o máximo (1); ``None`` sem o máximo do motor."""
        faixa = self.rpm_maximo - self.rpm_ocioso
        if self.rpm_maximo <= 0.0 or faixa <= 0.0:
            return None
        return max(0.0, min(1.0, (self.rpm - self.rpm_ocioso) / faixa))


def _real(valor: float) -> float:
    """O float do pacote; o que não é número (NaN, infinito) vira zero."""
    return float(valor) if math.isfinite(valor) else 0.0


def _quatro(campos: tuple[float | int, ...], inicio: int) -> QUATRO:
    a, b, c, d = (_real(float(x)) for x in campos[inicio:inicio + 4])
    return (a, b, c, d)


def ler_o_pacote(dados: bytes) -> EstadoDaCorrida | None:
    """O estado da corrida deste pacote; ``None`` quando o tamanho não é de formato conhecido."""
    formato = FORMATO_DO_TAMANHO.get(len(dados))
    if formato is None:
        return None
    s = _SLED.unpack_from(dados, 0)
    ax, ay, az = (_real(x) for x in s[_I_ACELERACAO:_I_ACELERACAO + 3])
    vx, vy, vz = (_real(x) for x in s[_I_VELOCIDADE:_I_VELOCIDADE + 3])
    zebra = tuple(bool(x) for x in s[_I_NA_ZEBRA:_I_NA_ZEBRA + 4])
    estado = EstadoDaCorrida(
        formato=formato,
        corrida_ligada=s[_I_CORRIDA_LIGADA] != 0,
        instante_ms=int(s[_I_INSTANTE_MS]),
        rpm=_real(s[_I_RPM]),
        rpm_maximo=_real(s[_I_RPM_MAXIMO]),
        rpm_ocioso=_real(s[_I_RPM_OCIOSO]),
        aceleracao=(ax, ay, az),
        velocidade_vetor=(vx, vy, vz),
        razao_de_patinacao=_quatro(s, _I_RAZAO_DE_PATINACAO),
        giro_das_rodas=_quatro(s, _I_GIRO_DAS_RODAS),
        na_zebra=(zebra[0], zebra[1], zebra[2], zebra[3]),
        patinacao_combinada=_quatro(s, _I_PATINACAO_COMBINADA),
    )
    if formato == FORMATO_CURTO:
        return estado
    d = _DASH.unpack_from(dados, INICIO_DO_DASH[formato])
    return EstadoDaCorrida(
        **{**estado.__dict__,
           "velocidade": _real(d[_D_VELOCIDADE]),
           "acelerador": d[_D_ACELERADOR] / 255.0,
           "freio": d[_D_FREIO] / 255.0,
           "marcha": int(d[_D_MARCHA])},
    )


def montar_o_pacote(
    formato: str = FORMATO_LONGO,
    *,
    corrida_ligada: bool = True,
    rpm: float = 3000.0,
    rpm_maximo: float = 8000.0,
    rpm_ocioso: float = 800.0,
    aceleracao: tuple[float, float, float] = (0.0, 0.0, 0.0),
    velocidade_vetor: tuple[float, float, float] = (0.0, 0.0, 0.0),
    razao_de_patinacao: QUATRO = (0.0, 0.0, 0.0, 0.0),
    giro_das_rodas: QUATRO = (0.0, 0.0, 0.0, 0.0),
    na_zebra: tuple[bool, bool, bool, bool] = (False, False, False, False),
    patinacao_combinada: QUATRO = (0.0, 0.0, 0.0, 0.0),
    velocidade: float = 0.0,
    acelerador: int = 0,
    freio: int = 0,
    marcha: int = 1,
) -> bytes:
    """Um pacote sintético no formato documentado: o inverso de ``ler_o_pacote``, para os testes e
    o ensaio sem jogo. Os campos que o Hefesto não lê vão zerados."""
    sled: list[float | int] = [0] * len(_TIPOS_DO_SLED)
    sled[_I_CORRIDA_LIGADA] = 1 if corrida_ligada else 0
    sled[_I_RPM_MAXIMO], sled[_I_RPM_OCIOSO], sled[_I_RPM] = rpm_maximo, rpm_ocioso, rpm
    sled[_I_ACELERACAO:_I_ACELERACAO + 3] = aceleracao
    sled[_I_VELOCIDADE:_I_VELOCIDADE + 3] = velocidade_vetor
    sled[_I_RAZAO_DE_PATINACAO:_I_RAZAO_DE_PATINACAO + 4] = razao_de_patinacao
    sled[_I_GIRO_DAS_RODAS:_I_GIRO_DAS_RODAS + 4] = giro_das_rodas
    sled[_I_NA_ZEBRA:_I_NA_ZEBRA + 4] = [int(x) for x in na_zebra]
    sled[_I_PATINACAO_COMBINADA:_I_PATINACAO_COMBINADA + 4] = patinacao_combinada
    curto = _SLED.pack(*[float(x) if tipo == "f" else int(x)
                         for tipo, x in zip(_TIPOS_DO_SLED, sled, strict=True)])
    if formato == FORMATO_CURTO:
        return curto
    dash: list[float | int] = [0.0] * 17 + [0] * 10
    dash[_D_VELOCIDADE] = velocidade
    dash[_D_ACELERADOR], dash[_D_FREIO], dash[_D_MARCHA] = acelerador, freio, marcha
    longo = _DASH.pack(*dash)
    if formato == FORMATO_LONGO:
        return curto + longo
    if formato == FORMATO_HORIZON:
        return curto + bytes(12) + longo + bytes(1)
    if formato == FORMATO_MOTORSPORT_2023:
        return curto + longo + bytes(20)
    raise ValueError(f"formato desconhecido: {formato}")


__all__ = [
    "FORMATO_CURTO",
    "FORMATO_DO_TAMANHO",
    "FORMATO_HORIZON",
    "FORMATO_LONGO",
    "FORMATO_MOTORSPORT_2023",
    "INICIO_DO_DASH",
    "EstadoDaCorrida",
    "ler_o_pacote",
    "montar_o_pacote",
]
