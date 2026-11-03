"""A resposta dos motores diz o efeito que vale.

A-RESPOSTA-DOS-MOTORES-DIZ-O-EFEITO-QUE-VALE-01. O ``rumble.motores.set`` devolve, para o efeito
háptico e para o padrão dos motores, o que ``formas_de_haptica.escolha_que_vale`` diz com o estilo
do perfil que se grava: «Do estilo» no perfil com estilo quando ninguém escolheu, «—» no perfil sem
estilo, e a escolha gravada quando há uma. É a mesma resposta para os quatro jogadores, porque o
campo sai do perfil e não do transporte (D-0311-A-LISTA-SEM-ESCOLHA-SEGUE-O-ESTILO-DO-PERFIL).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import formas_de_haptica as formas
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import ESCOLHAS_DE_IMERSAO, MatchAny, Profile
from hefesto_dualsense4unix.utils import xdg_paths
from tests.unit.test_cada_motor_tem_o_seu_multiplicador import _Handlers

MACS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
LISTAS = {"efeito_haptico": formas.ESCOLHAS, "efeito_imersao": ESCOLHAS_DE_IMERSAO}
SEM_ESTILO = (None, "nativo", "personalizado")
PEDIDOS: dict[str, dict[str, Any]] = {
    "forca_do_forte": {"forte_pct": 40},
    "forca_do_fraco": {"fraco_pct": 60},
    "forca_da_haptica": {"haptica_pct": 30},
    "haptico_impacto": {"efeito_haptico": "impacto"},
    "imersao_onda": {"efeito_imersao": "onda"},
    "haptico_sem_efeito": {"efeito_haptico": "sem_efeito"},
    "imersao_sem_efeito": {"efeito_imersao": "sem_efeito"},
    "haptico_do_estilo": {"efeito_haptico": "do_estilo"},
    "imersao_do_estilo": {"efeito_imersao": "do_estilo"},
}


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    monkeypatch.setattr(xdg_paths, "profiles_dir", _dir)
    return alvo


def _grava(mac: str, estilo: str | None, **pedido: Any) -> dict[str, Any]:
    h = _Handlers(ativo="Ensaio", primario=MACS[0])
    return asyncio.run(h._handle_rumble_motores_set({"uniq": mac, **pedido}))


def _novo_perfil(estilo: str | None) -> None:
    save_profile(Profile(name="Ensaio", match=MatchAny(), estilo=estilo))


@pytest.mark.parametrize("mac", MACS)
def test_perfil_com_estilo_e_so_a_forca_diz_do_estilo_nas_duas_listas(
    perfis: Path, mac: str
) -> None:
    """MORDIDA: devolver o ``or "sem_efeito"`` da resposta e as duas listas dizem «—»."""
    _novo_perfil("fps")

    corpo = _grava(mac, "fps", forte_pct=40)

    assert corpo["status"] == "ok" and corpo["gravado"] is True
    assert (corpo["efeito_haptico"], corpo["efeito_imersao"]) == ("do_estilo", "do_estilo")


@pytest.mark.parametrize("mac", MACS)
@pytest.mark.parametrize("estilo", SEM_ESTILO)
def test_perfil_sem_estilo_diz_sem_efeito(perfis: Path, mac: str, estilo: str | None) -> None:
    _novo_perfil(estilo)

    corpo = _grava(mac, estilo, forte_pct=40)

    assert (corpo["efeito_haptico"], corpo["efeito_imersao"]) == ("sem_efeito", "sem_efeito")


@pytest.mark.parametrize("mac", MACS)
@pytest.mark.parametrize("estilo", ["fps", *SEM_ESTILO])
@pytest.mark.parametrize("nome", list(PEDIDOS))
def test_a_resposta_e_a_escolha_que_vale_do_perfil(
    perfis: Path, mac: str, estilo: str | None, nome: str
) -> None:
    """MORDIDA: o padrão dos motores pela lista das formas e o ``onda`` gravado sai como outro.

    O segundo pedido igual não grava nada e responde o mesmo.
    """
    _novo_perfil(estilo)
    pedido = PEDIDOS[nome]

    for gravado in (True, False):
        corpo = _grava(mac, estilo, **pedido)

        assert corpo["gravado"] is gravado
        for campo, escolhas in LISTAS.items():
            assert corpo[campo] == formas.escolha_que_vale(pedido.get(campo), estilo, escolhas), (
                f"{campo} na resposta não é o que a lista da aba Vibração mostra"
            )
        for campo, escolha in pedido.items():
            if campo in LISTAS:
                assert corpo[campo] == escolha, "a escolha gravada não saiu como está"
