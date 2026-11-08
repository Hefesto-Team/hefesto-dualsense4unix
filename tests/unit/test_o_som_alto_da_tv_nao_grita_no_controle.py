"""O som alto da TV não grita no controle (O-SOM-ALTO-DA-TV-NAO-GRITA-NO-CONTROLE-01).

Um estrondo de 0,5 s depois de silêncio, pelo ``Passo`` do produto até o ``tocar_o_corpo`` dos
quatro controles, cada um num ganho da háptica. Antes da cura o grave saía cortado em 0,7 e o
ganho do fluxo o levava ao teto do PCM: meio segundo no máximo, e zero 20 ms depois do fim.

MORDIDAS:
- troque a ``cauda`` do ``TetoDoCorpo.passar`` por ``0.0`` e
  ``test_o_susto_desce_devagar_ate_zero_em_tres_segundos`` reprova: o corte seco volta;
- troque ``teto.teto = ...`` do ``Passo._sob_o_teto`` por ``teto.teto = float("inf")`` e
  ``test_o_susto_sai_a_setenta_por_cento_do_pico_de_hoje_em_todo_ganho`` reprova: o pico volta
  a 100%.
"""
from __future__ import annotations

import itertools
import math
import random
from array import array
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon import state_store
from hefesto_dualsense4unix.daemon.subsystems import diario_do_corpo as dc
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles import formas_de_haptica as fh

P = tuple(f"aa:bb:cc:00:00:{i:02x}" for i in range(1, 5))
FATORES = dict(zip(P, (1.0, 1.5, 2.0, 0.3), strict=True))
_XBOX = tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True)
SILENCIO_S, ESTRONDO_S, DEPOIS_S = 2.0, 0.5, 4.0
QUADROS_DO_TIQUE = fh.TAXA // 60
JANELA = fh.TAXA // 50


def _pcm_do_jogo(nivel: float = 0.9) -> bytes:
    sorteio = random.Random(20261108)
    antes, estrondo, depois = (round(fh.TAXA * s) for s in (SILENCIO_S, ESTRONDO_S, DEPOIS_S))
    mono = [sorteio.gauss(0.0, 0.003) for _ in range(antes)]
    for i in range(estrondo):
        grave = 0.6 * math.sin(2.0 * math.pi * 70 * i / fh.TAXA)
        mono.append(nivel * (grave + 0.4 * max(-1.0, min(1.0, sorteio.gauss(0.0, 0.5)))))
    mono += [sorteio.gauss(0.0, 0.003) for _ in range(depois)]
    quadros = array("h")
    for x in mono:
        v = int(32767 * max(-1.0, min(1.0, x)))
        quadros.extend((v, v))
    return quadros.tobytes()


class _Alto:
    def __init__(self) -> None:
        self.saida: dict[str, list[float]] = {u: [] for u in P}

    def tocar_o_corpo(self, uniq: str, amostras: Any, _lado: str = "centro") -> dc.DesfechoDoCorpo:
        self.saida[uniq].extend(amostras)
        return dc.DesfechoDoCorpo(None)


def _tocar(monkeypatch: pytest.MonkeyPatch, pcm: bytes) -> dict[str, list[float]]:
    monkeypatch.setattr(tv.GANHO, "fator", lambda uniq: FATORES[uniq])
    alto = _Alto()
    motor = tv.TatoVivo([])
    motor.escolhas = {norm_mac(u): fh.SOM_NO_CORPO for u in P}
    daemon = SimpleNamespace(_alto_falante_subsystem=alto, store=state_store.StateStore())
    passo = tv.Passo(daemon, motor)
    passo.receita_vigente = tv.Receita(som_no_corpo_escolhido=True)
    passo_do_pcm = QUADROS_DO_TIQUE * 4
    for i in range(0, len(pcm), passo_do_pcm):
        passo.alimentar_o_corpo(pcm[i:i + passo_do_pcm])
        passo._levar_o_corpo(passo.receita_vigente, P, lambda _u: _XBOX)
    return alto.saida


def _no_controle(amostras: list[float], fator: float) -> list[float]:
    return [max(-1.0, min(1.0, x * fator)) for x in amostras]


def _picos(saida: list[float]) -> list[float]:
    return [max(map(abs, saida[i:i + JANELA]), default=0.0) for i in range(0, len(saida), JANELA)]


def _janela_em(segundos: float) -> int:
    return round(segundos * fh.TAXA / JANELA)


@pytest.fixture(scope="module")
def pcm() -> bytes:
    return _pcm_do_jogo()


def test_o_estrondo_levava_o_corpo_de_hoje_ao_teto(pcm: bytes) -> None:
    """O grave do estrondo passa de longe o corte de hoje: o pico de hoje era o corte."""
    grave = fh.FiltroDoCorpo().processar(pcm)
    assert max(map(abs, grave)) > 2 * fh.TETO_DO_CORPO


def test_o_susto_sai_a_setenta_por_cento_do_pico_de_hoje_em_todo_ganho(
        monkeypatch: pytest.MonkeyPatch, pcm: bytes) -> None:
    """D-0811-O-SOM-ALTO-DA-TV-NAO-GRITA-NO-CONTROLE: o pico sai a 70% do de hoje, em todo ganho."""
    saida = _tocar(monkeypatch, pcm)
    for uniq, fator in FATORES.items():
        no_controle = _no_controle(saida[uniq], fator)
        pico_de_hoje = min(1.0, fh.TETO_DO_CORPO * fator)
        pico = max(map(abs, no_controle))
        assert pico == pytest.approx(fh.FRACAO_DO_SUSTO * pico_de_hoje, rel=0.02), (uniq, fator)
        assert sum(1 for x in no_controle if abs(x) >= 0.999) == 0, "nada encosta no teto do PCM"


def test_o_susto_segura_enquanto_o_som_alto_dura(
        monkeypatch: pytest.MonkeyPatch, pcm: bytes) -> None:
    saida = _tocar(monkeypatch, pcm)
    for uniq, fator in FATORES.items():
        picos = _picos(_no_controle(saida[uniq], fator))
        pico = max(picos)
        dentro = picos[_janela_em(SILENCIO_S + 0.04):_janela_em(SILENCIO_S + ESTRONDO_S)]
        assert min(dentro) >= 0.6 * pico, uniq


def test_o_susto_desce_devagar_ate_zero_em_tres_segundos(
        monkeypatch: pytest.MonkeyPatch, pcm: bytes) -> None:
    """D-0811-O-SOM-ALTO-DA-TV-NAO-GRITA-NO-CONTROLE: segura e solta até zero em uns 3 s."""
    saida = _tocar(monkeypatch, pcm)
    fim = SILENCIO_S + ESTRONDO_S
    for uniq, fator in FATORES.items():
        picos = _picos(_no_controle(saida[uniq], fator))
        pico = max(picos)
        em = {s: picos[_janela_em(fim + s)] / pico for s in (0.3, 1.5, 2.5, 3.1)}
        assert em[0.3] >= 0.8, f"{uniq}: o susto cortou seco em vez de segurar"
        assert 0.3 <= em[1.5] <= 0.7, f"{uniq}: a soltura não desce devagar"
        assert em[2.5] < 0.1
        assert em[3.1] < 0.01, f"{uniq}: o susto não chegou a zero"
        caindo = picos[_janela_em(fim + 0.1):_janela_em(fim + 3.0)]
        assert all(b <= a + 0.02 * pico for a, b in itertools.pairwise(caindo))


def test_o_grave_abaixo_do_teto_passa_sem_mudar(monkeypatch: pytest.MonkeyPatch) -> None:
    """O Som no corpo de sempre não muda: sem som alto, nem teto, nem cauda."""
    quadros = array("h")
    for i in range(fh.TAXA):
        v = int(32767 * 0.02 * math.sin(2.0 * math.pi * 100 * i / fh.TAXA))
        quadros.extend((v, v))
    pcm = quadros.tobytes()
    esperado = list(fh.FiltroDoCorpo().processar(pcm))
    saida = _tocar(monkeypatch, pcm)
    for uniq in P:
        assert saida[uniq] == pytest.approx(esperado, abs=1e-6), uniq
