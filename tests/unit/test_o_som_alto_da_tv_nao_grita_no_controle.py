"""O som alto da TV não grita no controle (O-SOM-ALTO-DA-TV-NAO-GRITA-NO-CONTROLE-01).

Um estrondo de 0,5 s depois de silêncio, pelo ``Passo`` do produto até o ``tocar_o_corpo`` dos
quatro controles, cada um num ganho da háptica. Antes da cura o grave saía cortado em 0,7 e o
ganho do fluxo o levava ao teto do PCM: meio segundo no máximo, e zero 20 ms depois do fim.

MORDIDAS:
- troque a ``cauda`` do ``TetoDoCorpo.passar`` por ``0.0`` e
  ``test_o_susto_desce_devagar_ate_zero_em_tres_segundos`` reprova: o corte seco volta;
- troque ``teto.teto = ...`` do ``Passo._sob_o_teto`` por ``teto.teto = float("inf")`` e
  ``test_o_susto_sai_a_setenta_por_cento_do_pico_de_hoje_em_todo_ganho`` reprova: o pico volta
  a 100%;
- troque o ganho do ``TetoDoCorpo.passar`` por ``max(-teto, min(teto, x))`` e
  ``test_o_susto_baixa_o_ganho_sem_cravar_a_onda_no_teto`` reprova: a onda volta a quadrar;
- troque ``entrada * FRACAO_DO_SUSTO > teto`` por ``entrada > teto`` e
  ``test_o_grave_que_nunca_gritou_nao_ganha_cauda`` reprova: o vão da batida zumbe;
- tire a limpeza de ``_tetos_do_corpo`` do ``Passo._levar_o_corpo`` e
  ``test_o_susto_nao_sobrevive_ao_efeito_desligado`` reprova: a cauda volta ao religar.
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


def _passo(monkeypatch: pytest.MonkeyPatch) -> tuple[tv.Passo, _Alto]:
    monkeypatch.setattr(tv.GANHO, "fator", lambda uniq: FATORES[uniq])
    alto = _Alto()
    motor = tv.TatoVivo([])
    motor.escolhas = {norm_mac(u): fh.SOM_NO_CORPO for u in P}
    daemon = SimpleNamespace(_alto_falante_subsystem=alto, store=state_store.StateStore())
    return tv.Passo(daemon, motor), alto


def _levar(passo: tv.Passo, pcm: bytes, uniqs: tuple[str, ...] = P, ligado: bool = True) -> None:
    passo.receita_vigente = tv.Receita(som_no_corpo_escolhido=ligado)
    passo_do_pcm = QUADROS_DO_TIQUE * 4
    for i in range(0, len(pcm), passo_do_pcm):
        passo.alimentar_o_corpo(pcm[i:i + passo_do_pcm])
        passo._levar_o_corpo(passo.receita_vigente, uniqs, lambda _u: _XBOX)


def _tocar(monkeypatch: pytest.MonkeyPatch, pcm: bytes) -> dict[str, list[float]]:
    passo, alto = _passo(monkeypatch)
    _levar(passo, pcm)
    return alto.saida


def _batida(nivel: float, segundos: float = 4.0) -> bytes:
    quadros = array("h")
    for i in range(round(fh.TAXA * segundos)):
        t = i / fh.TAXA
        v = int(32767 * nivel * math.sin(2.0 * math.pi * 80 * t)) if t % 0.5 < 0.15 else 0
        quadros.extend((v, v))
    return quadros.tobytes()


def _silencio(segundos: float) -> bytes:
    return bytes(4 * round(fh.TAXA * segundos))


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


def _maior_trecho_no_pico(amostras: list[float]) -> float:
    """O maior trecho seguido, em ms, com a amostra a 0,5% do pico: a onda cravada no teto."""
    limiar = 0.995 * max(map(abs, amostras))
    maior = atual = 0
    for x in amostras:
        atual = atual + 1 if abs(x) >= limiar else 0
        maior = max(maior, atual)
    return 1000.0 * maior / fh.TAXA


def test_o_susto_baixa_o_ganho_sem_cravar_a_onda_no_teto(
        monkeypatch: pytest.MonkeyPatch, pcm: bytes) -> None:
    """O teto é ganho, não corte: no estrondo, a onda nunca fica parada no pico."""
    saida = _tocar(monkeypatch, pcm)
    for uniq, fator in FATORES.items():
        assert _maior_trecho_no_pico(_no_controle(saida[uniq], fator)) < 1.0, uniq


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
    picos = {u: max(map(abs, _no_controle(saida[u], f))) for u, f in FATORES.items()}
    for u, f in FATORES.items():
        assert picos[u] == pytest.approx(max(map(abs, esperado)) * f, rel=1e-4), "o ganho age"


def test_o_grave_que_nunca_gritou_nao_ganha_cauda(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uma batida que passava limpa sai no teto, e o vão entre as batidas continua mudo."""
    pcm = _batida(0.15)
    grave = fh.FiltroDoCorpo().processar(pcm)
    assert fh.teto_do_susto(1.5) < max(map(abs, grave)) < min(fh.TETO_DO_CORPO, 1.0 / 1.5)
    saida = _tocar(monkeypatch, pcm)[P[1]]
    vaos = [abs(x) for i, x in enumerate(saida) if i >= fh.TAXA and (i / fh.TAXA) % 0.5 > 0.25]
    assert max(vaos) < 0.01


def test_o_susto_nao_sobrevive_ao_efeito_desligado(
        monkeypatch: pytest.MonkeyPatch, pcm: bytes) -> None:
    """Desligado no meio da cauda, o Som no corpo religa sem o susto velho."""
    passo, alto = _passo(monkeypatch)
    fim = round(fh.TAXA * (SILENCIO_S + ESTRONDO_S + 0.1)) * 4
    _levar(passo, pcm[:fim])
    _levar(passo, _silencio(0.5), ligado=False)
    antes = {u: len(alto.saida[u]) for u in P}
    _levar(passo, _silencio(1.0))
    for uniq in P:
        assert max(map(abs, alto.saida[uniq][antes[uniq]:]), default=0.0) < 0.01, uniq


def test_o_susto_de_um_controle_nao_vaza_para_quem_chega(
        monkeypatch: pytest.MonkeyPatch, pcm: bytes) -> None:
    """O controle que chega depois do estrondo não herda a cauda nem o ganho baixo do outro."""
    passo, alto = _passo(monkeypatch)
    fim = round(fh.TAXA * (SILENCIO_S + ESTRONDO_S)) * 4
    _levar(passo, pcm[:fim] + _silencio(0.3), uniqs=(P[0],))
    _levar(passo, _batida(0.02, segundos=1.0), uniqs=P[:2])
    esperado = fh.FiltroDoCorpo().processar(pcm[:fim] + _silencio(0.3) + _batida(0.02, 1.0))
    chegou = len(alto.saida[P[1]])
    assert chegou == fh.TAXA
    assert alto.saida[P[1]] == pytest.approx(list(esperado[-chegou:]), abs=1e-6)
    assert max(map(abs, alto.saida[P[0]][-chegou:])) > 0.2
