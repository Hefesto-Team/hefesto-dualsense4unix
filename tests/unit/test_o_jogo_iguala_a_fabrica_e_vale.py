"""O jogo e o valor de fábrica do mouse.

(O-JOGO-PODE-APAGAR-E-IGUALAR-A-FABRICA-O-QUE-O-COMPUTADOR-DIZ-01.)

O QUE FOI MEDIDO (08/10/2026) E É A PREMISSA DESTAS RÉGUAS: o arquivo do jogo
guarda as seções ``leds``, ``rumble`` e ``mouse`` POR EXTENSO (o ``save_profile``
escreve o ``model_dump`` inteiro), então o ``model_fields_set`` de quem relê é
sempre «todos os campos». O valor de fábrica escrito ali é o vocabulário de
«sem escolha» da casa (``voltar_ao_do_computador`` e ``ceder_ao_computador``
escrevem o de fábrica para dizer isso), e é por isso que
``escolhas_globais_do_jogo`` descarta o igual à fábrica. Pelo formato do
arquivo não há como separar «o usuário escolheu 6» de «a cópia do 6»: separar pede um
escritor esparso e uma marca de escolha no arquivo (``schema.py``), e a
sprint manda isso VOLTAR COMO PERGUNTA. A régua do caso aberto é ``xfail``
estrito: quando a pergunta for resolvida, ela vira verde e o ``strict`` obriga
a tirar a marca.

A MORDIDA das duas que valem hoje: tire o filtro de fábrica de
``escolhas_globais_do_jogo`` e a cópia do jogo passa a vencer o computador.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import Profile, ProfileMouseConfig
from hefesto_dualsense4unix.utils import maquina as m

JOGO = "Jogo X"
DO_COMPUTADOR = 9
_FABRICA = {c: ProfileMouseConfig.model_fields[c].default for c in ("speed", "scroll_speed")}


def _perfil(**mouse: Any) -> Profile:
    return Profile.model_validate({
        "name": JOGO, "match": {"type": "criteria", "window_class": ["jogo x"]},
        "mouse": {"enabled": True, **mouse}})


def _vale() -> Profile:
    return opc.perfil_que_vale(load_profile(JOGO), opc.o_computador())


@pytest.fixture(autouse=True)
def _computador_em_nove() -> None:
    assert m.gravar_o_computador({"global": {"mouse": {"speed": DO_COMPUTADOR}}})


def test_a_copia_de_fabrica_do_arquivo_antigo_nao_vence_o_computador() -> None:
    """Arquivo de antes: o 6 por extenso é a cópia, e o computador em 9 vale."""
    save_profile(_perfil(**_FABRICA))
    assert not opc.escolhas_globais_do_jogo(load_profile(JOGO), "mouse")
    assert _vale().mouse is not None and _vale().mouse.speed == DO_COMPUTADOR


def test_o_valor_diferente_da_fabrica_e_escolha_do_jogo() -> None:
    save_profile(_perfil(speed=7, scroll_speed=_FABRICA["scroll_speed"]))
    assert opc.escolhas_globais_do_jogo(load_profile(JOGO), "mouse") == {"speed": 7}
    assert _vale().mouse is not None and _vale().mouse.speed == 7


def test_a_seccao_do_jogo_vai_ao_disco_por_extenso() -> None:
    """A premissa medida: mover UM campo no jogo grava a seção inteira."""
    save_profile(_perfil(speed=5))

    def _muda(vista: Profile) -> Profile:
        assert vista.mouse is not None
        return vista.model_copy(update={"mouse": vista.mouse.model_copy(
            update={"speed": 7})})

    opc.gravar_pelo_gesto("mouse", JOGO, _muda, origem="regua")
    bruto = json.loads(loader._profile_path(load_profile(JOGO)).read_text(encoding="utf-8"))
    assert set(bruto["mouse"]) == {"enabled", "speed", "scroll_speed"}, bruto["mouse"]


@pytest.mark.xfail(strict=True, reason=(
    "PERGUNTA ABERTA: o arquivo do jogo é denso e o valor de fábrica por extenso "
    "é «sem escolha» na casa; separar pede escritor esparso e marca de escolha"))
def test_o_jogo_que_escolhe_a_fabrica_contra_o_computador_vale() -> None:
    """O jogo move a velocidade para o 6 de fábrica com o computador em 9: vale 6."""
    save_profile(_perfil(speed=7))

    def _para_a_fabrica(vista: Profile) -> Profile:
        assert vista.mouse is not None
        return vista.model_copy(update={"mouse": vista.mouse.model_copy(
            update={"speed": _FABRICA["speed"]})})

    opc.gravar_pelo_gesto("mouse", JOGO, _para_a_fabrica, origem="regua")
    assert _vale().mouse is not None and _vale().mouse.speed == _FABRICA["speed"]
