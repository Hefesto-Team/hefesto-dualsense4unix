"""O-CORPO-SOMA-CADA-FONTE-NO-SEU-LADO-01: cada fonte do corpo tem a própria fila, e o bloco soma.

O tocador é o real, sem processo (``argv_de`` vazio), em tempo simulado: a cada tique de 10 ms
cada fonte viva leva 480 amostras e sai um bloco. A contínua vale 0,1 no centro por 1 s; o
padrão vale 0,3 à esquerda por 0,5 s. O mesmo tocador serve o cabo e o rádio, nos dois modos.

A MORDIDA (executada, com o md5 conferido na volta): a fila única de volta (a fonte ignorada)
→ ``test_a_continua_e_o_padrao_somam_cada_um_no_seu_lado`` reprova com 0 amostras somadas.
"""
from __future__ import annotations

from array import array

import numpy as np

from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh

Q = eh.QUADROS_POR_BLOCO
ESQUERDO, DIREITO = eh.CANAIS_DO_LADO["esquerdo"][0], eh.CANAIS_DO_LADO["direito"][0]


def _tocar(fontes: dict[tuple[str, str], tuple[float, int]]) -> np.ndarray:
    """``{(fonte, lado): (valor, tiques)}``: o que sai do tocador, quadro a quadro."""
    tocador = eh.TocadorDoRumble("APARELHOTESTEX", argv_de=lambda *_a: [])
    blocos = []
    for tique in range(max(t for _v, t in fontes.values())):
        for (fonte, lado), (valor, tiques) in fontes.items():
            if tique < tiques:
                tocador.levar_o_corpo(
                    array("f", [valor] * Q), lado, sink="s", dono="d", fonte=fonte)
        blocos.append(tocador.proximo_bloco((0, 0), (0, 0), 0))
    while tocador.tocando_o_corpo:
        blocos.append(tocador.proximo_bloco((0, 0), (0, 0), 0))
    return np.frombuffer(b"".join(blocos), "<f4").reshape(-1, eh.CANAIS_DA_HAPTICA)


def _quantas(saida: np.ndarray, canal: int, valor: float) -> int:
    return int(np.isclose(saida[:, canal], valor, atol=1e-6).sum())


def test_a_continua_e_o_padrao_somam_cada_um_no_seu_lado() -> None:
    """D-1911-CADA-FONTE-DO-CORPO-SOMA-NO-SEU-LADO: o padrão inteiro à esquerda, por cima."""
    saida = _tocar({("continua", "centro"): (0.1, 100), ("golpe", "esquerdo"): (0.3, 50)})
    assert _quantas(saida, ESQUERDO, 0.4) == 50 * Q, "o padrão não somou à contínua"
    assert _quantas(saida, ESQUERDO, 0.3) == 0
    assert _quantas(saida, DIREITO, 0.3) + _quantas(saida, DIREITO, 0.4) == 0, (
        "o padrão da esquerda saiu no direito")
    assert _quantas(saida, ESQUERDO, 0.1) == 50 * Q
    assert _quantas(saida, DIREITO, 0.1) == 100 * Q, "a contínua não saiu inteira"
    assert len(saida) == 100 * Q, "uma fonte atrasou a outra"


def test_o_mesmo_padrao_nos_dois_lados_do_mesmo_controle() -> None:
    """D-1911-CADA-FONTE-DO-CORPO-SOMA-NO-SEU-LADO: um lado não troca o outro de lugar."""
    saida = _tocar({("golpe", "esquerdo"): (0.3, 30), ("golpe", "direito"): (0.3, 30)})
    assert _quantas(saida, ESQUERDO, 0.3) == 30 * Q
    assert _quantas(saida, DIREITO, 0.3) == 30 * Q
    assert len(saida) == 30 * Q
