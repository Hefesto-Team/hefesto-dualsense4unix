"""O-SENSOR-HAPTICO-PARA-EM-100-COMO-OS-MOTORES-01 (27/10/2026): a escala muda, a força fica.

A barra da háptica passa a ir de 0 a 100, como os motores, e o 100 é o fator 2,0 que o 200 dava
(D-2710-A-HAPTICA-VAI-DE-0-A-100-COM-O-MESMO-FATOR). A chave velha ``haptica_pct`` (0 a 200) vira
``haptica`` (0 a 100) na borda do esquema, por onde passam o perfil, o ``maquina.json``, o
``.historico`` devolvido, o perfil importado e o rascunho. As réguas leem o FATOR que chega ao
laço, e não o número que o próprio esquema escreveu.

MORDIDAS: arrancar o ``mode="before"`` (o perfil de 200 é recusado, fora de 0 a 100); arrancar o
``vezes 2,0`` de ``fator_da_haptica`` (o 100 cai para o fator 1,0); devolver a tupla do
``rumble.motores.set`` ao campo velho (o pedido de 100 vira 50 e o fator cai para 1,0).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.ganho_da_haptica import GanhoDaHaptica
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import (
    historico_dir,
    restaurar_do_historico,
    save_profile,
)
from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale
from hefesto_dualsense4unix.profiles.schema import (
    ControllerRumbleOverride,
    MatchAny,
    Profile,
)
from tests.unit.test_cada_motor_tem_o_seu_multiplicador import BRANCO, _grava_ipc, _Handlers
from tests.unit.test_o_ganho_da_haptica_tem_dono import perfis  # noqa: F401

_QUATRO = tuple(f"aabbcc00000{n}" for n in (1, 2, 3, 4))


def _perfil_velho(pct: int) -> dict[str, object]:
    return {
        "name": "Bancada",
        "match": {"type": "any"},
        "controllers": {u: {"rumble": {"haptica_pct": pct}} for u in _QUATRO},
    }


def _fator_no_laco(perfil: Profile, uniq: str) -> float:
    dono = GanhoDaHaptica()
    dono.ler_do_perfil(perfil.controllers)
    return dono.fator(uniq)


@pytest.mark.parametrize(("velho", "novo", "fator"), [(200, 100, 2.0), (150, 75, 1.5),
                                                       (100, 50, 1.0), (0, 0, 0.0)])
def test_o_perfil_velho_carrega_na_escala_nova_com_o_mesmo_fator(
        velho: int, novo: int, fator: float) -> None:
    perfil = Profile.model_validate(_perfil_velho(velho))
    for uniq in _QUATRO:
        rumble = (perfil.controllers or {})[uniq].rumble
        assert rumble is not None and rumble.haptica == novo
        assert _fator_no_laco(perfil, uniq) == pytest.approx(fator), (velho, uniq)


def test_carregar_duas_vezes_nao_converte_de_novo() -> None:
    uma = Profile.model_validate(_perfil_velho(200))
    gravado = uma.model_dump(mode="json")
    rumble = gravado["controllers"][_QUATRO[0]]["rumble"]
    assert rumble["haptica"] == 100 and "haptica_pct" not in rumble, (
        "a próxima gravação leva só a chave nova")
    duas = Profile.model_validate(json.loads(json.dumps(gravado)))
    assert duas.model_dump(mode="json") == gravado
    assert _fator_no_laco(duas, _QUATRO[0]) == pytest.approx(2.0)


def test_as_duas_chaves_juntas_sao_recusadas() -> None:
    with pytest.raises(ValueError, match=r"haptica_pct.*haptica"):
        ControllerRumbleOverride.model_validate({"haptica_pct": 200, "haptica": 100})


def test_o_historico_velho_devolvido_sai_convertido(perfis: Path) -> None:  # noqa: F811
    save_profile(Profile(name="Bancada", match=MatchAny()))
    pasta = historico_dir("bancada", ensure=True)
    (pasta / "20261001T000000_000000.json").write_text(
        json.dumps(_perfil_velho(200)), encoding="utf-8")
    restaurar_do_historico("Bancada", "20261001T000000_000000")
    devolvido = loader_module.load_profile("Bancada")
    rumble = (devolvido.controllers or {})[_QUATRO[0]].rumble
    assert rumble is not None and rumble.haptica == 100
    assert _fator_no_laco(devolvido, _QUATRO[0]) == pytest.approx(2.0)


def test_o_maquina_json_com_os_quatro_a_200_sai_com_os_quatro_a_100(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.utils import maquina

    arquivo = tmp_path / "maquina.json"
    arquivo.write_text(json.dumps({
        maquina.VERSION_FIELD: maquina.MAQUINA_SCHEMA_VERSION,
        "computador": {"controles": {u: {"rumble": {"haptica_pct": 200}} for u in _QUATRO}},
    }), encoding="utf-8")
    monkeypatch.setattr(maquina, "caminho_da_maquina", lambda: arquivo)
    computador = maquina.carregar_maquina().computador
    assert sorted(computador.controles) == sorted(_QUATRO)
    dono = GanhoDaHaptica()
    dono.ler_do_perfil(computador.controles)
    for uniq in _QUATRO:
        rumble = computador.controles[uniq].rumble
        assert rumble is not None and rumble.haptica == 100
        assert dono.fator(uniq) == pytest.approx(2.0)
    despejo = computador.model_dump(mode="json")["controles"][_QUATRO[0]]["rumble"]
    assert "haptica_pct" not in despejo and despejo["haptica"] == 100


def test_o_ipc_de_100_grava_100_e_chega_ao_fator_2(
        perfis: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    from hefesto_dualsense4unix.daemon import ganho_da_haptica as mod

    dono = GanhoDaHaptica()
    monkeypatch.setattr(mod, "GANHO", dono)
    save_profile(Profile(name="Bancada", match=MatchAny()))
    corpo = _grava_ipc(_Handlers(ativo="Bancada", primario=BRANCO), uniq=BRANCO,
                       haptica_pct=100)
    assert corpo["status"] == "ok" and corpo["haptica_pct"] == 100
    dele = (o_que_vale(loader_module.load_profile("Bancada")).controllers or {})[BRANCO]
    assert dele.rumble is not None and dele.rumble.haptica == 100
    assert dono.fator(BRANCO) == pytest.approx(2.0)
    assert dono.pct_que_vale(BRANCO) == 100
