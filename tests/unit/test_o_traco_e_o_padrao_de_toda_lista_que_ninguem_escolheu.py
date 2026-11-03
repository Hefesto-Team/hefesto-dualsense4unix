"""O «—» é a primeira opção e o padrão de toda lista que ninguém escolheu (03/11/2026).

Gatilhos e Vibração: o controle sem escolha mostra o «—» e não toca efeito do Hefesto; «Do estilo»
é uma escolha guardada, a segunda opção. Escolher o estilo em Perfis grava «Do estilo» só nas
listas de vibração sem escolha, e o «—» que a pessoa pôs de propósito fica.
"""
from __future__ import annotations

import re

import pytest

from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao as pv
from hefesto_dualsense4unix.interface.pacotes import a03_gatilhos, a05_vibracao, a10_perfis
from hefesto_dualsense4unix.profiles import formas_de_haptica as formas
from hefesto_dualsense4unix.profiles import schema
from hefesto_dualsense4unix.profiles.schema import ControllerOverrides, ControllerRumbleOverride

UNIQ = "aa:bb:cc:00:00:11"
CAMPOS = (("efeito_haptico", formas.ESCOLHAS), ("efeito_imersao", pv.ESCOLHAS))


@pytest.mark.parametrize("escolhas", [formas.ESCOLHAS, pv.ESCOLHAS, schema.ESCOLHAS_DE_IMERSAO])
def test_toda_lista_abre_no_traco_e_depois_do_estilo(escolhas: tuple[str, ...]) -> None:
    assert escolhas[:2] == ("sem_efeito", "do_estilo"), (
        "D-0311-TODA-LISTA-SEM-ESCOLHA-ABRE-NO-TRACO")


def test_a_lista_do_gatilho_abre_no_traco_e_depois_no_do_estilo() -> None:
    abertura = re.findall(r'<option value="([^"]*)"', a03_gatilhos.html_das_opcoes_de_imersao())[:2]
    assert abertura == ["sem_efeito", "do_estilo"]


@pytest.mark.parametrize(("campo", "lista"), CAMPOS)
def test_a_lista_de_vibracao_sem_escolha_mostra_o_traco(campo: str, lista: tuple[str, ...]) -> None:
    for sem in ({}, {UNIQ: {}}, {UNIQ: {"rumble": {}}}, {UNIQ: {"rumble": {campo: "xpto"}}}):
        assert a05_vibracao._escolha_da_lista(sem, UNIQ, campo, lista) == "sem_efeito"


@pytest.mark.parametrize(("campo", "lista"), CAMPOS)
def test_do_estilo_guardado_chega_a_lista(campo: str, lista: tuple[str, ...]) -> None:
    guardado = {UNIQ: {"rumble": {campo: "do_estilo"}}}
    assert a05_vibracao._escolha_da_lista(guardado, UNIQ, campo, lista) == "do_estilo"


def test_o_controle_sem_escolha_nao_toca_forma_nem_padrao() -> None:
    assert formas.forma_que_vale(None, "fps") is None
    assert formas.forma_que_vale(formas.SEM_EFEITO, "fps") is None
    assert pv.padrao_que_vale(None, "fps") is None
    assert pv.padrao_que_vale(pv.SEM_EFEITO, "fps") is None


def test_so_o_do_estilo_toca_o_que_o_estilo_pede() -> None:
    assert formas.forma_que_vale(formas.DO_ESTILO, "fps") == formas.TOQUE
    assert pv.padrao_que_vale(pv.DO_ESTILO, "fps") == "coice"
    assert formas.forma_que_vale(formas.ESTALO, "fps") == formas.ESTALO
    assert pv.padrao_que_vale("onda", "fps") == "onda"


def test_do_estilo_sem_estilo_no_perfil_nao_toca_padrao() -> None:
    assert pv.padrao_que_vale(pv.DO_ESTILO, None) is None


def _com(rumble: ControllerRumbleOverride | None) -> ControllerOverrides:
    return ControllerOverrides(rumble=rumble)


def test_escolher_o_estilo_grava_do_estilo_so_nas_listas_sem_escolha() -> None:
    for sem in (None, ControllerRumbleOverride()):
        gravado = a10_perfis._com_o_estilo_nas_listas(_com(sem)).rumble
        assert gravado is not None
        assert (gravado.efeito_haptico, gravado.efeito_imersao) == ("do_estilo", "do_estilo")


def test_escolher_o_estilo_respeita_o_traco_e_a_forma_ja_escolhida() -> None:
    rumble = ControllerRumbleOverride(efeito_haptico="sem_efeito", efeito_imersao="batida")
    assert a10_perfis._com_o_estilo_nas_listas(_com(rumble)).rumble == rumble
    meio = ControllerRumbleOverride(efeito_haptico="estalo", motor_forte_pct=40)
    gravado = a10_perfis._com_o_estilo_nas_listas(_com(meio)).rumble
    assert gravado is not None
    assert (gravado.efeito_haptico, gravado.efeito_imersao, gravado.motor_forte_pct) == (
        "estalo", "do_estilo", 40)


def test_o_perfil_antigo_sem_as_chaves_carrega_no_traco() -> None:
    antigo = ControllerRumbleOverride()
    assert antigo.efeito_haptico is None and antigo.efeito_imersao is None
    assert formas.forma_que_vale(antigo.efeito_haptico, "fps") is None
    assert pv.padrao_que_vale(antigo.efeito_imersao, "fps") is None


def _toques_do_tiro(escolha: str | None) -> list[str]:
    from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv

    feitos: list[str] = []
    motor = tv.TatoVivo([tv.AtuadorDaHaptica(
        lambda uniq, *_a, **_k: feitos.append(uniq) or True, escolha_de=lambda _u: escolha)])
    borda = tv.BordaDoRumble()
    for instante, forte in ((0.0, 0), (0.008, 200)):
        for evento in borda.ver(UNIQ, 0, forte, instante):
            motor.anotar(evento)
    motor.tique(0.01, lambda _u: tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True),
                tv.Receita(vibracao_por_tiro=True))
    return feitos


def test_o_tiro_so_toca_no_controle_que_escolheu() -> None:
    assert _toques_do_tiro(None) == []
    assert _toques_do_tiro(formas.SEM_EFEITO) == []
    assert _toques_do_tiro(formas.DO_ESTILO) == [UNIQ]
    assert _toques_do_tiro(formas.ESTALO) == [UNIQ]


@pytest.mark.parametrize("jogadores", [1, 2, 3, 4])
def test_escolher_o_estilo_em_perfis_grava_do_estilo_em_cada_lugar(jogadores: int) -> None:
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    uniqs = [f"aabbcc0000{n:02x}" for n in range(1, jogadores + 1)]
    mesa = [{"uniq": u, "jogador": n} for n, u in enumerate(uniqs, start=1)]
    novo, _ = a10_perfis._com_o_estilo(Profile(name="Lista", match=MatchAny()), POR_CHAVE["fps"],
                                       mesa)
    for uniq in uniqs:
        rumble = novo.controllers[uniq].rumble
        assert rumble is not None
        assert (rumble.efeito_haptico, rumble.efeito_imersao) == ("do_estilo", "do_estilo")
