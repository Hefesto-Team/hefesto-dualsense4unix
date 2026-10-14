"""OS-QUATRO-EM-HARMONIA-01, item 6: cada borda do som e da háptica diz o controle.

Em 14/10/2026, com quatro controles, o journal não dizia qual deles saiu do
``HAPTICS_SELECT``, quanto cada um levava no fio nem a quem o alto-falante
respondia. Cada borda vira uma linha com o ``uniq`` (a máscara cobre), uma vez
por mudança e nunca por volta, nos quatro controles.
"""

from __future__ import annotations

import pytest
import structlog

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from tests.unit import test_a_haptica_chega_a_quem_entra_depois as h
from tests.unit.test_a_haptica_chega_a_quem_entra_depois import mesa  # noqa: F401
from tests.unit.test_o_ganho_da_haptica_tem_dono import BRANCO, PRETO, _CaboDeMentira, _dono
from tests.unit.test_o_mudo_do_microfone_sobrevive_a_reconexao import (
    KEY_1,
    KEY_2,
    _ctl_com,
    _handle_recem_nascido,
)


def _eventos(diario: list[dict], nome: str) -> list[dict]:
    return [r for r in diario if r["event"] == nome]


def test_a_borda_do_haptics_select_diz_o_controle_uma_vez() -> None:
    """MORDIDA: tire o ``haptics_select_borda`` de ``set_haptica_de_audio_for``."""
    ctl = _ctl_com(_handle_recem_nascido(radio=True))
    ctl._handles[KEY_2] = _handle_recem_nascido(radio=False)
    with structlog.testing.capture_logs() as diario:
        for _ in range(3):
            ctl.set_haptica_de_audio_for(KEY_1, True)
        ctl.set_haptica_de_audio_for(KEY_2, True)
        ctl.set_haptica_de_audio_for(KEY_1, False)
    bordas = [(r["uniq"], r["haptica_de_audio"]) for r in _eventos(diario, "haptics_select_borda")]
    um, dois = ctl._key_to_uniq(KEY_1), ctl._key_to_uniq(KEY_2)
    assert bordas == [(um, True), (dois, True), (um, False)]


def test_o_portao_do_cabo_diz_o_controle_dono() -> None:
    """MORDIDA: tire o ``uniq=dono`` do ``haptica_do_cabo_portao``."""
    cabo = _CaboDeMentira()
    with structlog.testing.capture_logs() as diario:
        cabo.volta(_dono(branco=50, preto=150), [BRANCO, PRETO])
    ditos = {r["uniq"]: r["motores"] for r in _eventos(diario, "haptica_do_cabo_portao")}
    assert ditos == {BRANCO: "0.5000", PRETO: "1.5000"}


@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
def test_o_ganho_do_radio_e_dito_por_controle_na_borda(
    monkeypatch: pytest.MonkeyPatch, quantos: int
) -> None:
    """MORDIDA: tire o ``_dizer_o_ganho_do_radio`` da volta do rádio."""
    uniqs = [f"aabbcc0000{n:02x}" for n in range(1, quantos + 1)]
    pcts = dict(zip(uniqs, (40, 80, 120, 150), strict=False))
    monkeypatch.setattr(mod.GANHO, "pct_que_vale", lambda u: pcts.get(u, 100))
    sub = mod.AltoFalanteSubsystem()
    vivos = {u: f"/dev/hidraw{i}" for i, u in enumerate(uniqs)}
    primeiro = [(u, pcts[u]) for u in uniqs]
    with structlog.testing.capture_logs() as diario:
        for _ in range(3):
            sub._dizer_o_ganho_do_radio(vivos)
        pcts[uniqs[-1]] = 10
        sub._dizer_o_ganho_do_radio(vivos)
    ditos = [(r["uniq"], r["pct"]) for r in _eventos(diario, "som_radio_ganho_da_haptica")]
    assert ditos == [*primeiro, (uniqs[-1], 10)]


def test_o_ganho_do_radio_volta_a_ser_dito_quando_o_controle_reentra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mod.GANHO, "pct_que_vale", lambda _u: 70)
    sub = mod.AltoFalanteSubsystem()
    um = "aabbcc000001"
    with structlog.testing.capture_logs() as diario:
        sub._dizer_o_ganho_do_radio({um: "/dev/hidraw1"})
        sub._dizer_o_ganho_do_radio({})
        sub._dizer_o_ganho_do_radio({um: "/dev/hidraw1"})
    assert len(_eventos(diario, "som_radio_ganho_da_haptica")) == 2


@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
def test_a_volta_do_radio_diz_o_ganho_de_cada_controle(
    mesa: h._Mesa, monkeypatch: pytest.MonkeyPatch, quantos: int  # noqa: F811
) -> None:
    """A volta inteira das pontes, de 1 a 4 no rádio: cada um diz o seu ganho, uma vez.

    MORDIDA: tire o ``_dizer_o_ganho_do_radio`` da volta do rádio e o diário cala.
    """
    radio = (h._P1, h._P2, h._P3, h._P4)[:quantos]
    pcts = dict(zip(radio, (40, 80, 120, 150), strict=False))
    monkeypatch.setattr(mod.GANHO, "pct_que_vale", lambda u: pcts.get(u, 100))
    controles = [h._Controle(u, "bt", f"/dev/hidraw{n + 1}") for n, u in enumerate(radio)]
    with structlog.testing.capture_logs() as diario:
        mesa.volta(*controles)
        mesa.volta(*controles)
    ditos = [(r["uniq"], r["pct"]) for r in _eventos(diario, "som_radio_ganho_da_haptica")]
    assert sorted(ditos) == sorted(pcts.items())
