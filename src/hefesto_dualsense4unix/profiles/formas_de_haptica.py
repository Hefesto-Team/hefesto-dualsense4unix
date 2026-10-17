"""As formas do efeito háptico: do toque seco ao som no corpo (funções puras).

A háptica viaja como áudio de quatro canais a 48 kHz; o toque do tiro é uma forma de onda curta
somada aos canais dos atuadores: senos com um ataque e uma queda até zero. O disparo é da receita
do estilo; a forma é a escolha da pessoa, uma por controle (``efeito_haptico`` do perfil). O ganho
de toda forma é o Sensor háptico, que age adiante, no caminho do áudio: nada aqui lê barra nem
perfil. O Som no corpo é o único contínuo (o grave do som do jogo, de 40 a 220 Hz, com ganho fixo
e teto) e só toca por escolha manual, nunca como padrão de estilo.
"""
from __future__ import annotations

import functools
import math
import sys
from array import array
from dataclasses import dataclass

TAXA = 48_000

#: «Do estilo» é o automático (o que o estilo pede, e o Toque de hoje quando ele não pede nada);
#: «Sem efeito» cala o toque deste controle.
DO_ESTILO = "do_estilo"
SEM_EFEITO = "sem_efeito"
TOQUE = "toque"
IMPACTO = "impacto"
ESTALO = "estalo"
GUARDA = "guarda"
APARO = "aparo"
SOM_NO_CORPO = "som_no_corpo"

#: As escolhas, na ordem em que a tela as mostra. A chave é a que o perfil guarda.
ESCOLHAS: tuple[str, ...] = (
    DO_ESTILO, SEM_EFEITO, TOQUE, IMPACTO, ESTALO, GUARDA, APARO, SOM_NO_CORPO)

ROTULOS: dict[str, str] = {
    DO_ESTILO: "Do estilo",
    SEM_EFEITO: "Sem efeito",
    TOQUE: "Toque",
    IMPACTO: "Impacto",
    ESTALO: "Estalo",
    GUARDA: "Guarda",
    APARO: "Aparo",
    SOM_NO_CORPO: "Som no corpo",
}

#: O que se sente, em uma linha (até 36 letras, para caber na coluna da lista).
DICAS: dict[str, str] = {
    DO_ESTILO: "O que o estilo pede",
    SEM_EFEITO: "O controle não toca",
    TOQUE: "Um toque seco e curto",
    IMPACTO: "Uma pancada funda",
    ESTALO: "Um clique fino",
    GUARDA: "Metal contra metal, médio",
    APARO: "Metal agudo, mais longo",
    SOM_NO_CORPO: "O grave do jogo vira tremor",
}

#: As formas longas: a Bateria longa as troca pelo Toque, e o rádio só as toca com fatia livre.
FORMAS_LONGAS = frozenset({GUARDA, APARO, SOM_NO_CORPO})

#: O que cada estilo pede, quando pede uma forma. Vazio de propósito: nenhum estilo escolhe forma
#: sozinho até a sprint dos estilos (E1), e o Som no corpo, contínuo, nunca entra aqui.
POR_ESTILO: dict[str, str] = {}


@dataclass(frozen=True)
class Forma:
    """Senos somados (``hz``, peso; os pesos somam 1), com ataque e duração em ms."""

    componentes: tuple[tuple[int, float], ...]
    ataque_ms: int
    #: ``None``: a duração vem do pedido (o Toque do estilo, de 25 a 60 ms).
    duracao_ms: int | None


FORMAS: dict[str, Forma] = {
    TOQUE: Forma(((160, 1.0),), 3, None),
    IMPACTO: Forma(((60, 0.6), (160, 0.4)), 2, 80),
    ESTALO: Forma(((250, 1.0),), 1, 15),
    GUARDA: Forma(((115, 0.6), (220, 0.4)), 3, 850),
    APARO: Forma(((170, 0.5), (270, 0.5)), 3, 600),
}


def amostras(
    chave: str, energia: float, duracao_ms: int | None = None, taxa: int = TAXA
) -> array[float]:
    """As amostras de UMA forma: sobe no ataque, cai até zero no fim, nunca passa de ``energia``."""
    forma = FORMAS.get(chave)
    if forma is None:
        raise ValueError(
            f"forma de háptica desconhecida: {chave!r}. As que existem: {', '.join(FORMAS)}")
    duracao = forma.duracao_ms if forma.duracao_ms is not None else (duracao_ms or 40)
    n = max(2, round(taxa * max(1, int(duracao)) / 1000))
    forca = max(0.0, min(1.0, float(energia)))
    envelopes, ondas = _molde(chave, n, taxa)
    pares = zip(envelopes, ondas, strict=True)
    return array("f", [forca * envelope * onda for envelope, onda in pares])


@functools.lru_cache(maxsize=32)
def _molde(chave: str, n: int, taxa: int) -> tuple[array[float], array[float]]:
    """O envelope e a onda de uma forma, sem a força: a conta dos senos, feita uma vez por duração.

    O toque sai no laço do tato, no fio do daemon: a Guarda (850 ms, dois senos) custa uns 20 ms
    de conta, e refazê-la a cada tiro seguraria a entrada dos quatro controles.
    """
    forma = FORMAS[chave]
    ataque = max(1, min(n - 1, round(taxa * forma.ataque_ms / 1000)))
    passos = [(2.0 * math.pi * hz / taxa, peso) for hz, peso in forma.componentes]
    envelopes, ondas = array("d", bytes(8 * n)), array("d", bytes(8 * n))
    for i in range(n):
        if i < ataque:
            envelopes[i] = i / ataque
        else:
            envelopes[i] = ((n - 1 - i) / (n - 1 - ataque)) ** 2 if n - 1 > ataque else 0.0
        ondas[i] = sum(peso * math.sin(passo * i) for passo, peso in passos)
    return envelopes, ondas


def escolha_valida(valor: object) -> str | None:
    """A escolha do perfil como chave conhecida; ``None`` quando não há escolha ou não se lê.

    ``None`` quer dizer «Do estilo»: o perfil que não escolheu nada se comporta como sempre.
    """
    return valor if isinstance(valor, str) and valor in ESCOLHAS and valor != DO_ESTILO else None


def forma_do_estilo(estilo: object) -> str:
    """A forma que o estilo pede; o Toque de hoje quando ele não pede nenhuma."""
    return POR_ESTILO.get(estilo, TOQUE) if isinstance(estilo, str) else TOQUE


def forma_que_vale(escolha: object, estilo: object, economia: bool = False) -> str | None:
    """A forma que toca de verdade, ou ``None`` quando este controle não toca.

    ``economia`` é a Bateria longa: Guarda e Aparo viram o Toque, e o Som no corpo cala.
    """
    chave = escolha_valida(escolha)
    if chave == SEM_EFEITO:
        return None
    if chave is None:
        chave = forma_do_estilo(estilo)
    if economia and chave in FORMAS_LONGAS:
        return None if chave == SOM_NO_CORPO else TOQUE
    return chave


# --- O Som no corpo: o grave do som do jogo -------------------------------------------------

#: A faixa do corpo: abaixo de 40 Hz o atuador não responde, acima de 220 Hz já é toque.
CORTE_BAIXO_HZ = 40
CORTE_ALTO_HZ = 220
#: Valores de partida: o ganho é fixo (o Sensor háptico regula adiante) e o teto protege o atuador.
GANHO_DO_CORPO = 4.0
TETO_DO_CORPO = 0.7
_ESCALA_DO_PCM = 32768.0


class _Biquad:
    """Um filtro de segunda ordem (Butterworth), com o estado entre os pedaços."""

    def __init__(self, tipo: str, corte_hz: float, taxa: int) -> None:
        w = 2.0 * math.pi * corte_hz / taxa
        cos_w, alfa = math.cos(w), math.sin(w) / (2.0 * 0.7071067811865476)
        if tipo == "passa-baixa":
            b0 = b2 = (1.0 - cos_w) / 2.0
            b1 = 1.0 - cos_w
        else:
            b0 = b2 = (1.0 + cos_w) / 2.0
            b1 = -(1.0 + cos_w)
        a0 = 1.0 + alfa
        self.b0, self.b1, self.b2 = b0 / a0, b1 / a0, b2 / a0
        self.a1, self.a2 = (-2.0 * cos_w) / a0, (1.0 - alfa) / a0
        self.x1 = self.x2 = self.y1 = self.y2 = 0.0

    def passar(self, x: float) -> float:
        y = (self.b0 * x + self.b1 * self.x1 + self.b2 * self.x2
             - self.a1 * self.y1 - self.a2 * self.y2)
        self.x2, self.x1 = self.x1, x
        self.y2, self.y1 = self.y1, y
        return y


class FiltroDoCorpo:
    """O som do jogo (PCM estéreo, s16le) vira o grave de 40 a 220 Hz, mono, com ganho e teto."""

    def __init__(self, taxa: int = TAXA) -> None:
        self.taxa = taxa
        self._alto = _Biquad("passa-alta", CORTE_BAIXO_HZ, taxa)
        self._baixo = _Biquad("passa-baixa", CORTE_ALTO_HZ, taxa)

    def processar(self, pcm: bytes) -> array[float]:
        """O pedaço filtrado. Meio quadro solto no fim do pedaço é descartado."""
        quadros = array("h")
        quadros.frombytes(pcm[: len(pcm) - len(pcm) % 4])
        if sys.byteorder != "little":  # pragma: no cover — o formato é little-endian
            quadros.byteswap()
        saida = array("f", bytes(4 * (len(quadros) // 2)))
        for i in range(len(saida)):
            mono = (quadros[2 * i] + quadros[2 * i + 1]) / (2.0 * _ESCALA_DO_PCM)
            y = GANHO_DO_CORPO * self._baixo.passar(self._alto.passar(mono))
            saida[i] = max(-TETO_DO_CORPO, min(TETO_DO_CORPO, y))
        return saida


__all__ = [
    "APARO",
    "CORTE_ALTO_HZ",
    "CORTE_BAIXO_HZ",
    "DICAS",
    "DO_ESTILO",
    "ESCOLHAS",
    "ESTALO",
    "FORMAS",
    "FORMAS_LONGAS",
    "GANHO_DO_CORPO",
    "GUARDA",
    "IMPACTO",
    "POR_ESTILO",
    "ROTULOS",
    "SEM_EFEITO",
    "SOM_NO_CORPO",
    "TAXA",
    "TETO_DO_CORPO",
    "TOQUE",
    "FiltroDoCorpo",
    "Forma",
    "amostras",
    "escolha_valida",
    "forma_do_estilo",
    "forma_que_vale",
]
