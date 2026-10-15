"""Os padrões de vibração da aba Vibração: Batida, Onda e Tranco.

Um padrão é uma sequência de passos `(ms, esquerdo, direito)`, de 0 a 255 em cada motor. Quem
toca é a fila do controle: manda o par de cada passo, espera o tempo dele e, no fim, devolve a mão
ao jogo. Este módulo só sabe a forma; o envio e a espera chegam por parâmetro, e é por isso que a
régua o toca sem aparelho e sem relógio.
"""
from __future__ import annotations

from collections.abc import Callable

#: `(ms, esquerdo, direito)`.
Passo = tuple[int, int, int]

#: O motor esquerdo é o pesado (`strong`); o direito, o leve (`weak`).
ESQUERDO = "esquerdo"
DIREITO = "direito"
AMBOS = "ambos"
MOTORES: tuple[str, ...] = (ESQUERDO, DIREITO, AMBOS)

#: As três formas, na ordem em que a tela as mostra. A chave é a que o clique manda.
PADROES: dict[str, tuple[Passo, ...]] = {
    # duas pancadas e um respiro, como um coração
    "batida": ((110, 255, 255), (90, 0, 0), (110, 190, 190), (520, 0, 0)),
    # sobe e desce devagar, sem corte
    "onda": ((90, 60, 60), (90, 120, 120), (90, 190, 190), (90, 255, 255),
             (90, 190, 190), (90, 120, 120), (90, 60, 60), (60, 0, 0)),
    # um golpe seco, um segundo menor e o silêncio
    "tranco": ((150, 255, 255), (70, 0, 0), (90, 150, 150), (60, 0, 0)),
}

ROTULOS: dict[str, str] = {"batida": "Batida", "onda": "Onda", "tranco": "Tranco"}

#: Quanto um padrão pode durar: a fila do controle espera por ele.
TETO_MS = 2000


def sequencia(padrao: str, motores: str = AMBOS) -> tuple[Passo, ...]:
    """Os passos do padrão pedido com o motor que não toca em zero. Recusa o que não conhece."""
    if padrao not in PADROES:
        raise ValueError(f"padrão de vibração desconhecido: {padrao!r}. "
                         f"Os que existem: {', '.join(PADROES)}")
    if motores not in MOTORES:
        raise ValueError(f"motor desconhecido: {motores!r}. Os que existem: {', '.join(MOTORES)}")
    return tuple(
        (ms, 0 if motores == DIREITO else esq, 0 if motores == ESQUERDO else dir_)
        for ms, esq, dir_ in PADROES[padrao])


def tocar(
    padrao: str,
    motores: str,
    enviar: Callable[[int, int], None],
    esperar: Callable[[float], None],
    *,
    pontos_esquerdo: int = 100,
    pontos_direito: int = 100,
) -> None:
    """Percorre o padrão: `enviar(esquerdo, direito)` e `esperar(segundos)` a cada passo.

    `pontos_*` é a barra de cada motor (0 a 100): o padrão sai reduzido por ela, como o
    «Testar». O silêncio final é de quem chama (devolver a mão ao jogo).
    """
    for ms, esq, dir_ in sequencia(padrao, motores):
        enviar(_reduzido(esq, pontos_esquerdo), _reduzido(dir_, pontos_direito))
        esperar(ms / 1000.0)


def _reduzido(valor: int, pontos: int) -> int:
    return max(0, min(255, round(valor * int(pontos) / 100.0)))
