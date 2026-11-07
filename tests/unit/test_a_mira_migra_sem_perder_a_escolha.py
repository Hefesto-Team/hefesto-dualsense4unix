"""O perfil gravado antes da mira nova carrega sem perder a escolha de ninguém.

A forma antiga se reconhece pelos campos que saíram; a nova nunca passa pela tabela, e por isso
ler duas vezes dá o mesmo. MORDIDAS: zerar a zona na migração reprova a tabela; tirar a detecção
da forma antiga faz o `inverter` novo cair na segunda leitura.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    MatchAny,
    Profile,
    ProfileMovimentoConfig,
)

ANTIGA = {
    "destino": "analogico_direito",
    "sensibilidade": 6,
    "eixo_horizontal": "yaw",
    "inverter_horizontal": False,
    "inverter_vertical": False,
    "zona_morta_graus_s": 3.0,
    "teto_graus_s": 220.0,
    "pixels_por_grau": 12.0,
    "gatilho": None,
}


def _ler(**mudou: object) -> ProfileMovimentoConfig:
    return ProfileMovimentoConfig.model_validate({**ANTIGA, **mudou})


@pytest.mark.parametrize(
    ("antiga", "nova"),
    [(6, 4), (1, 1), (12, 10), (2, 2), (3, 2), (5, 4), (7, 6), (9, 8), (11, 9)],
)
def test_a_sensibilidade_vira_h_e_v(antiga: int, nova: int) -> None:
    secao = _ler(sensibilidade=antiga)
    assert (secao.sensibilidade_h, secao.sensibilidade_v) == (nova, nova)


def test_a_zona_morta_segue_igual() -> None:
    assert _ler(zona_morta_graus_s=60.0).zona_morta_graus_s == 60.0


def test_o_teto_padrao_vira_a_velocidade_padrao_e_o_outro_fica() -> None:
    assert _ler().velocidade_do_jogo == 180.0
    assert "velocidade_do_jogo" not in _ler().model_fields_set
    assert _ler(teto_graus_s=300.0).velocidade_do_jogo == 300.0


def test_o_inverter_antigo_era_a_correcao_do_sinal_e_cai() -> None:
    secao = _ler(inverter_horizontal=True, inverter_vertical=True)
    assert (secao.inverter_horizontal, secao.inverter_vertical) == (False, False)


def test_a_peca_que_so_ligou_o_chip_e_o_inverter_tambem_e_forma_antiga() -> None:
    """O chip velho escreveu `acelerometro` e a Calibrar, os `inverter`: nada mais denuncia."""
    secao = ProfileMovimentoConfig.model_validate({
        "destino": "analogico_direito", "acelerometro": "analogico_direito",
        "lado": "analogico_direito", "inverter_horizontal": True, "inverter_vertical": True,
    })
    assert (secao.inverter_horizontal, secao.inverter_vertical) == (False, False)
    assert secao.destino == "analogico_direito"


def test_o_eixo_horizontal_sai_e_o_roll_nao_recusa() -> None:
    assert not hasattr(_ler(eixo_horizontal="roll"), "eixo_horizontal")


@pytest.mark.parametrize("destino", ["nenhum", "analogico_esquerdo", "analogico_direito"])
def test_a_migracao_nao_liga_nem_desliga_nada(destino: str) -> None:
    assert _ler(destino=destino).destino == destino


def test_a_forma_nova_nao_passa_pela_tabela() -> None:
    secao = ProfileMovimentoConfig.model_validate(
        {"destino": "analogico_direito", "inverter_horizontal": True, "sensibilidade_h": 6}
    )
    assert secao.inverter_horizontal is True
    assert secao.sensibilidade_h == 6


def test_ler_duas_vezes_nao_muda_na_segunda() -> None:
    primeira = _ler(sensibilidade=9, zona_morta_graus_s=7.0, teto_graus_s=300.0)
    dump = primeira.model_dump(mode="json")
    segunda = ProfileMovimentoConfig.model_validate(dump)
    assert segunda == primeira
    assert segunda.model_dump(mode="json") == dump


def test_o_inverter_que_a_pessoa_liga_depois_de_migrar_sobrevive() -> None:
    migrada = _ler(inverter_horizontal=True)
    campos = {**migrada.model_dump(exclude_unset=True), "inverter_horizontal": True}
    gravada = ProfileMovimentoConfig.model_validate(campos).model_dump(mode="json")
    assert ProfileMovimentoConfig.model_validate(gravada).inverter_horizontal is True


def test_os_campos_antigos_nao_voltam_ao_disco() -> None:
    dump = _ler(sensibilidade=9).model_dump(mode="json")
    assert not {"sensibilidade", "eixo_horizontal", "teto_graus_s"} & set(dump)


def test_o_perfil_inteiro_migra_na_secao_e_em_cada_peca(tmp_path: Path) -> None:
    bruto = Profile(name="Velho", match=MatchAny(type="any")).model_dump(mode="json")
    bruto["movimento"] = {**ANTIGA, "sensibilidade": 12}
    bruto["controllers"] = {
        "aabbcc000001": {"movimento": {**ANTIGA, "sensibilidade": 1, "zona_morta_graus_s": 60.0,
                                       "inverter_horizontal": True, "inverter_vertical": True}},
        "aabbcc000002": {"movimento": {**ANTIGA, "sensibilidade": 8}},
    }
    arquivo = tmp_path / "velho.json"
    arquivo.write_text(json.dumps(bruto), encoding="utf-8")
    perfil = Profile.model_validate(json.loads(arquivo.read_text(encoding="utf-8")))
    assert perfil.movimento.sensibilidade_h == 10
    p1 = perfil.controllers["aabbcc000001"].movimento
    p2 = perfil.controllers["aabbcc000002"].movimento
    assert (p1.sensibilidade_h, p1.zona_morta_graus_s, p1.inverter_vertical) == (1, 60.0, False)
    assert p2.sensibilidade_v == 7
    relido = Profile.model_validate(perfil.model_dump(mode="json"))
    assert relido.controllers["aabbcc000001"] == perfil.controllers["aabbcc000001"]


def test_o_innocent_assault_fica_com_h_v_um_e_zona_60_e_anda() -> None:
    secao = _ler(sensibilidade=1, zona_morta_graus_s=60.0, inverter_horizontal=True,
                 inverter_vertical=True)
    arranjo = rot.arranjo_da_peca(None, secao)
    assert (arranjo.sensibilidade_h, arranjo.sensibilidade_v) == (1, 1)
    assert arranjo.zona_morta_graus_s == 60.0
    assert not arranjo.inverter_horizontal
    giro = (0.0, 120.0, 0.0)
    assert rot.deflexao_do_tique(SimpleNamespace(), "aa:bb:cc:00:00:01", giro, arranjo)[0] != 0


def test_a_peca_so_leva_ao_disco_o_que_escolheu() -> None:
    secao = ProfileMovimentoConfig(destino="analogico_direito", sensibilidade_h=7)
    dump = ControllerOverrides(movimento=secao).model_dump(mode="json")["movimento"]
    assert dump["sensibilidade_h"] == 7
    assert "sensibilidade_v" not in dump
    assert "piso" not in dump
    assert "velocidade_do_jogo" not in dump


def test_o_piso_do_perfil_vale_na_peca_sem_opiniao() -> None:
    mesa = ProfileMovimentoConfig(destino="analogico_direito", piso=0.1, velocidade_do_jogo=90.0)
    peca = ProfileMovimentoConfig.model_validate({**ANTIGA, "sensibilidade": 9})
    arranjo = rot.arranjo_da_peca(mesa, peca)
    assert arranjo.piso == 0.1
    assert arranjo.velocidade_do_jogo == 90.0
    assert rot.arranjo_da_peca(mesa, ProfileMovimentoConfig(piso=0.2)).piso == 0.2
