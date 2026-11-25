"""O watchdog do serviço depois da suspensão: o relógio do prazo e o aviso na volta.

O ``sd_notify`` é dublado no ponto em que o datagrama sairia; o relógio é um dublê que salta.
"""
from __future__ import annotations

import inspect
import time

import pytest

from hefesto_dualsense4unix.daemon.subsystems import vigia_do_laco as vl
from hefesto_dualsense4unix.utils import sd_notify

PRAZO_S = 30.0


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


def _vigia_com_watchdog(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[vl.VigiaDoLaco, _Relogio, list[str]]:
    enviados: list[str] = []

    def notificar(mensagem: str) -> bool:
        enviados.append(mensagem)
        return True

    monkeypatch.setattr(sd_notify, "notificar", notificar)
    monkeypatch.setattr(sd_notify, "prazo_do_watchdog", lambda: PRAZO_S)
    relogio = _Relogio()
    vigia = vl.VigiaDoLaco(relogio=relogio, avisar=lambda *_a, **_k: None)
    return vigia, relogio, enviados


def _o_laco_bate_e_o_tique_fecha(vigia: vl.VigiaDoLaco, relogio: _Relogio) -> None:
    vigia._batida = relogio.agora
    vigia.tique()


def test_o_prazo_do_watchdog_corre_no_relogio_que_nao_conta_a_suspensao() -> None:
    """D-1911-O-LACO-QUE-MORRE-OU-TRAVA-VOLTA-SOZINHO: vigia e systemd, um relógio."""
    padrao = inspect.signature(vl.VigiaDoLaco).parameters["relogio"].default

    assert padrao is time.monotonic
    assert vl.VigiaDoLaco(avisar=lambda *_a, **_k: None)._relogio is time.monotonic


@pytest.mark.parametrize("salto_s", [PRAZO_S * 0.7, PRAZO_S * 10], ids=["maior-que-meio", "enorme"])
def test_depois_de_um_salto_do_relogio_o_aviso_sai_na_primeira_batida_nova(
    monkeypatch: pytest.MonkeyPatch, salto_s: float
) -> None:
    """D-1911-O-LACO-QUE-MORRE-OU-TRAVA-VOLTA-SOZINHO: o salto não custa outra espera."""
    vigia, relogio, enviados = _vigia_com_watchdog(monkeypatch)
    _o_laco_bate_e_o_tique_fecha(vigia, relogio)
    vigia.alimentar_o_watchdog(relogio.agora)
    assert enviados == ["WATCHDOG=1"]

    relogio.agora += salto_s
    vigia.alimentar_o_watchdog(relogio.agora)
    assert enviados == ["WATCHDOG=1"], "o laço ainda não provou que anda: não avisa"

    _o_laco_bate_e_o_tique_fecha(vigia, relogio)
    vigia.alimentar_o_watchdog(relogio.agora)
    assert enviados == ["WATCHDOG=1"] * 2, "a primeira batida nova do laço leva o aviso"

    relogio.agora += PRAZO_S / 4
    _o_laco_bate_e_o_tique_fecha(vigia, relogio)
    vigia.alimentar_o_watchdog(relogio.agora)
    assert len(enviados) == 2, "dentro do meio prazo não repete"

    relogio.agora += PRAZO_S / 4
    _o_laco_bate_e_o_tique_fecha(vigia, relogio)
    vigia.alimentar_o_watchdog(relogio.agora)
    assert len(enviados) == 3, "fechado o meio prazo, o aviso segue no ritmo"
