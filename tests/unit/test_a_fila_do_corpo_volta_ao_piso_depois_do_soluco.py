"""A-FILA-DO-CORPO-VOLTA-AO-PISO-DEPOIS-DO-SOLUCO-01: o soluço do laço não deixa o corpo atrasado.

O tocador é o real, sem processo, em tempo simulado: o laço do tato leva um tique de amostras
a cada 1/60 s e o tocador tira um bloco a cada 10 ms. Um soluço de 150 ms para o laço, que
volta entregando de uma vez o que deve. Cada amostra leva o próprio número, e o atraso é a
distância entre a última levada e a que toca: ele volta ao piso, e o mudo não passa do soluço
e um bloco. Cada fila por fonte segue a mesma regra, no cabo e no rádio.

A MORDIDA (executada, com o md5 conferido na volta): sem o alvo de enchimento, a fila fica com
4.320 amostras depois do soluço → ``test_o_soluco_nao_deixa_o_corpo_atrasado``; o padrão de
fora 50 ms adiante perde os 800 primeiros quadros →
``test_o_padrao_de_fora_toca_desde_o_primeiro_golpe``.
"""
from __future__ import annotations

from array import array

import numpy as np

from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh

TAXA = eh.TAXA_DO_ENDPOINT
POR_TIQUE = round(TAXA * tv.INTERVALO_S)
MARCA = 1 << 14
PASSO_S = eh.QUADROS_POR_BLOCO / TAXA


def _valor(n: int) -> float:
    return 0.5 * (1 + n % (MARCA - 1)) / MARCA


def _tocar(soluco_s: float, *, de_s: float = 20.0, ate_s: float = 30.0) -> tuple[int, int]:
    """A fila 1 s depois do soluço e as amostras mudas, as duas em amostras.

    O laço entrega, a cada tique, o que deve desde a última entrega, no máximo um décimo de
    segundo (o ``_amostras_devidas`` de hoje); no soluço ele não entrega nada.
    """
    tocador = eh.TocadorDoRumble(
        "APARELHOTESTEX", argv_de=lambda *_a: [], ganho_da_via=lambda _dono: 1.0
    )
    levadas = mudas = 0
    entregue_ate = -tv.INTERVALO_S
    proximo_tique = 0.0
    fila = -1
    for passo in range(round(ate_s / PASSO_S)):
        agora = passo * PASSO_S
        if agora >= proximo_tique and not de_s <= agora < de_s + soluco_s:
            devidas = round(min(0.1, agora - entregue_ate) * TAXA)
            tocador.levar_o_corpo(
                array("f", [_valor(levadas + i) for i in range(devidas)]), "centro",
                sink="s", dono="d", fonte="som_no_corpo")
            levadas += devidas
            entregue_ate = agora
            while proximo_tique <= agora:
                proximo_tique += tv.INTERVALO_S
        bloco = np.frombuffer(tocador.proximo_bloco((0, 0), (0, 0), 0), "<f4")[2::4]
        mudas += int((bloco == 0).sum())
        if fila < 0 and soluco_s and agora >= de_s + soluco_s + 1.0:
            ultimo = round(float(bloco[-1]) * 2 * MARCA) - 1
            fila = ((levadas - 1) % (MARCA - 1) - ultimo) % (MARCA - 1)
    return fila, mudas


def test_sem_soluco_o_corpo_segue_sem_fila() -> None:
    """D-1911-A-FILA-DO-CORPO-TEM-ALVO-DE-DOIS-TIQUES: o piso é o enchimento do laço."""
    _fila, mudas = _tocar(0.0)
    assert mudas <= eh.QUADROS_POR_BLOCO, mudas


def test_o_soluco_nao_deixa_o_corpo_atrasado() -> None:
    """D-1911-A-FILA-DO-CORPO-TEM-ALVO-DE-DOIS-TIQUES: 1 s depois do soluço, o corpo no piso."""
    fila, mudas = _tocar(0.150)
    assert 0 <= fila <= 1920, f"o corpo ficou {fila} amostras atrás do som"
    assert mudas <= round(0.150 * TAXA) + eh.QUADROS_POR_BLOCO, mudas


def test_o_alvo_e_o_de_dois_tiques_do_laco() -> None:
    """D-1911-A-FILA-DO-CORPO-TEM-ALVO-DE-DOIS-TIQUES: o alvo do tocador e o tique do laço."""
    assert eh.ALVO_DO_CORPO_NA_FILA == 2 * POR_TIQUE


def test_o_padrao_de_fora_toca_desde_o_primeiro_golpe() -> None:
    """D-1911-A-FILA-DO-CORPO-TEM-ALVO-DE-DOIS-TIQUES: a fila nova não corta o começo do padrão."""
    tocador = eh.TocadorDoRumble(
        "APARELHOTESTEX", argv_de=lambda *_a: [], ganho_da_via=lambda _dono: 1.0
    )
    origem, uniq = tv.PREFIXO_DA_EXTENSAO + "a", "aa:bb:cc:00:00:71"

    def levar(_uniq: str, amostras: array[float], lado: str) -> bool:
        tocador.levar_o_corpo(amostras, lado, sink="s", dono="d", fonte=tv.FONTE_DE_FORA)
        return True

    fonte = tv.FonteDeFora(tv.Teto(), modo_de=lambda _u: tv.MODO_DUALSENSE, tocar_haptica=levar)
    padrao = tv.padrao_de({"golpes": [[0, 200, 60, 1.0]], "repete": False})
    fonte.registrar(origem, "golpe", padrao)
    assert fonte.tocar(origem, uniq, "esquerdo", "golpe", 0.5, None, 0.0, None).vale
    tocado, proximo_tique = [], tv.INTERVALO_S
    for passo in range(round(0.3 / PASSO_S)):
        agora = passo * PASSO_S
        if agora >= proximo_tique:
            fonte.andar(agora)
            proximo_tique += tv.INTERVALO_S
        tocado.append(np.frombuffer(tocador.proximo_bloco((0, 0), (0, 0), 0), "<f4")[2::4])
    esperado = np.asarray(tv.amostras_de(padrao, 0.0, round(0.2 * TAXA), 0.5, None))
    saida = np.concatenate(tocado)[: len(esperado)]
    assert np.allclose(saida, esperado, atol=1e-6), "o ataque do padrão ficou fora do corpo"


def test_a_continua_nao_repoe_o_tempo_do_soluco() -> None:
    """D-1911-A-FILA-DO-CORPO-TEM-ALVO-DE-DOIS-TIQUES: o Grão volta com dois tiques, não 0,1 s."""
    from tests.unit.test_o_diario_diz_o_que_o_corpo_tocou import _Alto, _passo

    passo = _passo(_Alto())
    passo._amostras_devidas("grao", 20.0)
    assert passo._amostras_devidas("grao", 20.150) == eh.ALVO_DO_CORPO_NA_FILA
