"""Os padrões de vibração da aba Vibração: Tranco, Batida, Onda, Coice e Pancada do lado.

Um padrão é uma sequência de passos `(ms, esquerdo, direito)`, de 0 a 255 em cada motor. Quem
toca é a fila do controle: manda o par de cada passo, espera o tempo dele e, no fim, devolve a mão
ao jogo. Este módulo só sabe a forma; o envio e a espera chegam por parâmetro, e é por isso que a
régua o toca sem aparelho e sem relógio.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

#: `(ms, esquerdo, direito)`.
Passo = tuple[int, int, int]

#: O motor esquerdo é o pesado (`strong`); o direito, o leve (`weak`).
ESQUERDO = "esquerdo"
DIREITO = "direito"
AMBOS = "ambos"
MOTORES: tuple[str, ...] = (ESQUERDO, DIREITO, AMBOS)

#: As formas, na ordem em que a tela as mostra. A chave é a que o clique manda. O Ronco (contínuo)
#: não entra: o teto de 2000 ms e o silêncio no fim valem para todo padrão.
PADROES: dict[str, tuple[Passo, ...]] = {
    # duas pancadas e um respiro, como um coração
    "batida": ((110, 255, 255), (90, 0, 0), (110, 190, 190), (520, 0, 0)),
    # sobe e desce devagar, sem corte
    "onda": ((90, 60, 60), (90, 120, 120), (90, 190, 190), (90, 255, 255),
             (90, 190, 190), (90, 120, 120), (90, 60, 60), (60, 0, 0)),
    # um golpe seco, um segundo menor e o silêncio
    "tranco": ((150, 255, 255), (70, 0, 0), (90, 150, 150), (60, 0, 0)),
    # o coice da arma: um golpe fundo que cai logo, para a soltura do tiro
    "coice": ((60, 200, 120), (60, 0, 0)),
    # um golpe só; no motor do lado de onde veio o som (`motores`), nos dois quando não se sabe
    "pancada_do_lado": ((90, 255, 255), (60, 0, 0)),
}

ROTULOS: dict[str, str] = {
    "batida": "Batida", "onda": "Onda", "tranco": "Tranco", "coice": "Coice",
    "pancada_do_lado": "Pancada do lado",
}

#: O que o efeito imersão de um controle guarda (``rumble.efeito_imersao``): «Do estilo» é o
#: automático (o padrão do estilo, `POR_ESTILO`), «Sem efeito» cala o controle.
DO_ESTILO = "do_estilo"
SEM_EFEITO = "sem_efeito"
#: Os padrões na ordem da lista da tela, depois das duas escolhas de sempre.
ESCOLHAS: tuple[str, ...] = (DO_ESTILO, SEM_EFEITO, "tranco", "batida", "onda", "coice",
                             "pancada_do_lado")
#: Cada padrão em uma linha, para a lista (até 36 letras).
DICAS: dict[str, str] = {
    DO_ESTILO: "O que o estilo pede",
    SEM_EFEITO: "Os motores não tocam efeito",
    "tranco": "Um golpe seco e um respiro",
    "batida": "Duas pancadas, como um coração",
    "onda": "Sobe e desce devagar",
    "coice": "O recuo da arma, ao soltar",
    "pancada_do_lado": "Um golpe do lado do som",
}
#: O Coice é o recuo: toca quando o dedo solta o gatilho, não quando aperta.
NA_SOLTURA = frozenset({"coice"})


class NaSoltura(NamedTuple):
    """Onde um padrão do estilo toca ao soltar o gatilho, e depois de quanto tempo de aperto."""

    segurado_s: float
    #: o gatilho que vale (``"esquerdo"``/``"direito"``); ``None``: os dois
    lado: str | None


#: A Onda do Furtivo (20/10/2026) toca ao soltar a mira (L2) segurada por 2 s ou mais, e não ao
#: apertar: o atirador de elite solta o fôlego (a Carga · fôlego preso é a imersão do L2).
NA_SOLTURA_DO_ESTILO: dict[tuple[str, str], NaSoltura] = {
    ("furtivo", "onda"): NaSoltura(2.0, "esquerdo"),
}


def na_soltura_do_estilo(padrao: str, estilo: object) -> NaSoltura | None:
    """A regra de soltura que o estilo dá a este padrão; ``None`` quando ele toca no aperto."""
    return NA_SOLTURA_DO_ESTILO.get((estilo, padrao)) if isinstance(estilo, str) else None


#: A Pancada do lado olha de onde veio o som do jogo.
DO_LADO_DO_SOM = frozenset({"pancada_do_lado"})

#: Quanto um padrão pode durar: a fila do controle espera por ele.
TETO_MS = 2000


def escolha_valida(valor: object) -> str | None:
    """A escolha do perfil como padrão; ``None`` quando não há escolha ou é «Do estilo»."""
    if isinstance(valor, str) and valor in ESCOLHAS and valor != DO_ESTILO:
        return valor
    return None


#: O padrão que cada estilo pede (a tabela `S` da página de 19/10/2026). O estilo fora daqui deixa
#: os motores «só ao jogo»; o Ronco, contínuo, nunca entra aqui.
POR_ESTILO: dict[str, str] = {
    "fps": "coice",
    "acao": "tranco",  # (noqa-acento): chave
    "luta": "pancada_do_lado",
    "souls": "tranco",
    "furtivo": "onda",
    "aventura": "onda",
    "terror": "batida",
    "esportes": "tranco",
}


def padrao_que_vale(escolha: object, estilo: object) -> str | None:
    """O padrão que toca de verdade, ou ``None`` quando os motores deste controle não tocam nada.

    Sem escolha («Do estilo») vale o do estilo, e nenhum quando o estilo não pede; «Sem efeito»
    cala. A Bateria longa não troca o padrão: ela só baixa a força, e quem baixa é o chamador.
    """
    if escolha == SEM_EFEITO:
        return None
    dela = escolha_valida(escolha)
    if dela is not None:
        return dela
    if not isinstance(estilo, str):
        return None
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import chave_do_catalogo

    return POR_ESTILO.get(str(chave_do_catalogo(estilo)))


def duracao_ms(padrao: str) -> int:
    """Quanto o padrão dura, em ms (a soma dos passos)."""
    return sum(ms for ms, _esq, _dir in PADROES[padrao])


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
