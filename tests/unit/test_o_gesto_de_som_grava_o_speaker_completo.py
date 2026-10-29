"""O gesto de som grava o alto-falante completo, e o perfil antigo sem volume carrega.

O-GESTO-DE-SOM-GRAVA-O-SPEAKER-COMPLETO-01: em 28/10 a rota clicada num controle sem som
próprio no perfil mandou `{'rota': 3}` ao perfil do jogo, e o `ProfileSpeakerConfig`
recusou com «'volume' é obrigatório».

A MORDIDA: tire o `speaker` de `o_padrao_do_computador.ACOMPANHA`, e o gesto levanta o
`ValidationError`.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import Profile
from hefesto_dualsense4unix.utils import maquina as m

JOGO = "Jogo do som"
P1 = "aabbcc000001"
P2 = "aabbcc000002"
VOLUME_DO_COMPUTADOR = 180


@pytest.fixture(autouse=True)
def _computador_sabe_o_volume() -> None:
    assert m.gravar_o_computador({"controles": {
        P1: {"speaker": {"volume": VOLUME_DO_COMPUTADOR}},
        P2: {"speaker": {"volume": VOLUME_DO_COMPUTADOR}},
    }})


def _perfil_sem_som_no_controle() -> None:
    save_profile(Profile.model_validate({
        "name": JOGO, "match": {"type": "criteria", "window_class": ["jogo do som"]},
    }))


def _com_a_rota(uniq: str, rota: int) -> Any:
    def _muda(vista: Profile) -> Profile:
        controles = dict(vista.controllers or {})
        entrada = controles[uniq]
        assert entrada.speaker is not None
        controles[uniq] = entrada.model_copy(
            update={"speaker": entrada.speaker.model_copy(update={"rota": rota})})
        return vista.model_copy(update={"controllers": controles})

    return _muda


def _bruto() -> dict[str, Any]:
    return json.loads(loader._profile_path(load_profile(JOGO)).read_text(encoding="utf-8"))


@pytest.mark.parametrize("uniq", [P1, P2])
def test_a_rota_vai_ao_perfil_com_o_volume_que_vale(uniq: str) -> None:
    _perfil_sem_som_no_controle()
    opc.gravar_pelo_gesto("som", JOGO, _com_a_rota(uniq, 3), uniq=uniq, origem="regua")
    assert _bruto()["controllers"][uniq]["speaker"] == {"volume": VOLUME_DO_COMPUTADOR, "rota": 3}
    salvo = load_profile(JOGO).controllers or {}
    assert salvo[uniq].speaker is not None and salvo[uniq].speaker.rota == 3


def test_o_volume_sozinho_nao_arrasta_a_rota() -> None:
    _perfil_sem_som_no_controle()

    def _volume(vista: Profile) -> Profile:
        controles = dict(vista.controllers or {})
        entrada = controles[P1]
        assert entrada.speaker is not None
        controles[P1] = entrada.model_copy(
            update={"speaker": entrada.speaker.model_copy(update={"volume": 90})})
        return vista.model_copy(update={"controllers": controles})

    opc.gravar_pelo_gesto("som", JOGO, _volume, uniq=P1, origem="regua")
    assert "rota" not in _bruto()["controllers"][P1]["speaker"]


def test_o_perfil_antigo_com_som_sem_volume_carrega_sem_ele() -> None:
    perfil = Profile.model_validate({
        "name": JOGO, "match": {"type": "any"},
        "speaker": {"rota": 2},
        "controllers": {P1: {"speaker": {"rota": 3}, "mic": {"muted": True}},
                        P2: {"speaker": {"volume": 40, "rota": 1}}},
    })
    controles = perfil.controllers or {}
    assert perfil.speaker is None
    assert controles[P1].speaker is None and controles[P1].mic is not None
    assert controles[P2].speaker is not None and controles[P2].speaker.volume == 40
