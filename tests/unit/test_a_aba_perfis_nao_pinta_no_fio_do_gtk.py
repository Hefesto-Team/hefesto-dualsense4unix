"""A-ABA-PERFIS-NAO-PINTA-NO-FIO-DO-GTK-01: o tique da 10 não espera a leitura dos perfis.

Quarenta e seis perfis numa pasta de mentira, a leitura pela assinatura ligada como na janela e
o pacote de verdade da 10, com a leitura dos perfis presa por 1 s: o tique da janela volta na
hora e a carga da 10 pinta depois, montada no fio `hefesto-pacote`.

Mordida: devolver a montagem ao tique (`_a_carga_na_hora` no lugar de
`_a_carga_montada_no_fundo` em `Piloto._tique`) faz o tique durar 1 s.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.interface.pacotes import a10_perfis as a10
from hefesto_dualsense4unix.interface.pacotes import fios
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
from tests.unit.test_o_pacote_de_toda_aba_se_monta_fora_do_fio_do_gtk import (
    _esperar_a_montagem,
    _piloto,
    _tique,
)

PERFIS = 46
PRESA_S = 1.0
TETO_DO_TIQUE_S = 0.1


@pytest.fixture
def pasta_cheia(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for i in range(PERFIS):
        loader.save_profile(Profile(name=f"Perfil {i:02d}", match=MatchManual(),
                                    remapeamento={"cross": "circle"}))
    monkeypatch.setattr(loader._PERFIS_PELA_ASSINATURA, "_recem_gravado_s", 0.0)
    loader.ligar_a_leitura_pela_assinatura()
    try:
        yield
    finally:
        loader.desligar_a_leitura_pela_assinatura()


def test_a_leitura_presa_dos_perfis_nao_prende_o_tique_da_janela(
        pasta_cheia: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A leitura dos perfis presa por 1 s: o tique da 10 volta na hora e pinta depois."""
    lida = loader.load_all_profiles

    def presa() -> list[Profile]:
        time.sleep(PRESA_S)
        return lida()

    monkeypatch.setattr(loader, "load_all_profiles", presa)
    quem: list[str] = []

    def da_10(pagina: str, ctx: Any) -> dict[str, Any]:
        quem.append(threading.current_thread().name)
        return a10.pacote(ctx)

    fios.ligar_a_janela()
    try:
        piloto = _piloto(monkeypatch, da_10)  # type: ignore[arg-type]
        piloto.pagina = "10-perfis.html"
        t0 = time.perf_counter()
        _tique(piloto)
        gasto = time.perf_counter() - t0
        assert gasto < TETO_DO_TIQUE_S, f"o tique da 10 esperou a leitura: {gasto * 1000:.0f} ms"
        _esperar_a_montagem(piloto)
        _tique(piloto)
        _esperar_a_montagem(piloto)
    finally:
        fios.ligar_a_janela(False)
    assert quem and set(quem) == {"hefesto-pacote"}, quem
    assert "Perfil 45" in repr(piloto._carga_de_agora), "a carga da 10 não pintou os perfis"
