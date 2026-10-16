"""Sem perfil ativo, o tato lê a escolha do computador — 16/10/2026.

A aba Vibração grava a forma do toque e o padrão dos motores no ``maquina.json`` quando
não há jogo (``onde_grava``: sem perfil, grava no computador). O laço do tato, porém,
devolvia ``DESLIGADA`` no nome vazio e nenhuma das cinco leituras valia sem ``_VISTA_LIDA``
com o nome ativo: quem não tinha perfil escolhia na tela e o controle não tocava.

A cura: sem perfil, a vista é o computador por baixo de um perfil vazio, pelo mesmo
``perfil_que_vale`` da tela. O computador vazio continua desligado.

MORDIDA: devolva o ``return DESLIGADA`` do nome vazio em ``receita_ativa`` e os testes da
escolha reprovam; tire a guarda do nome nas leituras e o computador vaza para o perfil.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

STARLIGHT = "aa:bb:cc:dd:ee:01"
BRANCO = "aa:bb:cc:dd:ee:02"


@pytest.fixture(autouse=True)
def _vistas_limpas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tv, "_PELO_CARREGADOR", None)
    monkeypatch.setattr(tv, "_VISTA_LIDA", None)
    monkeypatch.setattr(tv, "_VISTA_DO_COMPUTADOR", None)


def _daemon(nome: str | None = None) -> Any:
    return SimpleNamespace(store=SimpleNamespace(active_profile=nome))


def _escolhe(uniq: str, haptico: str | None = None, imersao: str | None = None) -> None:
    """O gesto da aba Vibração sem perfil: grava no computador, por controle."""
    rumble = {
        c: v for c, v in (("efeito_haptico", haptico), ("efeito_imersao", imersao))
        if v is not None}
    onde = opc.gravar("vibracao", {"rumble": rumble}, uniq=uniq)
    assert onde == opc.COMPUTADOR, "sem perfil o gesto grava no computador"


def test_sem_perfil_a_forma_e_o_padrao_do_computador_chegam_ao_tato() -> None:
    # D-1610-O-TATO-LE-O-COMPUTADOR-SEM-PERFIL-ATIVO
    _escolhe(STARLIGHT, "impacto", "batida")
    _escolhe(BRANCO, "estalo")
    daemon = _daemon(None)

    receita = tv.receita_ativa(daemon)

    assert receita != tv.DESLIGADA
    assert receita.efeitos_escolhidos and receita.padroes_escolhidos
    assert tv.escolhas_ativas(daemon) == {
        tv.norm_mac(STARLIGHT): "impacto", tv.norm_mac(BRANCO): "estalo"}
    assert tv.escolhas_de_imersao_ativas(daemon) == {tv.norm_mac(STARLIGHT): "batida"}
    # O computador não guarda gatilho: a vista do perfil vazio não acorda momento nem vibração
    # do gatilho que ninguém escolheu.
    assert tv.momentos_ativos(daemon) == tv.SEM_MOMENTOS
    assert tv.vibracao_do_gatilho_ativa(daemon) == tv.SEM_VIBRACAO


def test_nome_vazio_e_nome_ausente_valem_o_mesmo() -> None:
    _escolhe(STARLIGHT, "impacto")
    for nome in (None, ""):
        daemon = _daemon(nome)
        assert tv.receita_ativa(daemon).efeitos_escolhidos
        assert tv.escolhas_ativas(daemon) == {tv.norm_mac(STARLIGHT): "impacto"}


def test_o_passo_do_laco_leva_a_escolha_ao_motor() -> None:
    _escolhe(STARLIGHT, "impacto", "batida")
    motor = tv.TatoVivo([])
    passo = tv.Passo(_daemon(None), motor)

    receita = passo.receita_de_agora(0.0)

    assert receita.efeitos_escolhidos
    assert motor.escolhas == {tv.norm_mac(STARLIGHT): "impacto"}
    assert motor.escolhas_de_imersao == {tv.norm_mac(STARLIGHT): "batida"}


def test_cada_controle_fica_com_a_escolha_dele() -> None:
    _escolhe(STARLIGHT, "impacto")
    daemon = _daemon(None)
    tv.receita_ativa(daemon)
    escolhas = tv.escolhas_ativas(daemon)
    assert tv.norm_mac(BRANCO) not in escolhas
    assert escolhas == {tv.norm_mac(STARLIGHT): "impacto"}


def test_o_computador_vazio_continua_desligado() -> None:
    daemon = _daemon(None)

    assert tv.receita_ativa(daemon) == tv.DESLIGADA
    assert tv.escolhas_ativas(daemon) == {}
    assert tv.escolhas_de_imersao_ativas(daemon) == {}
    assert tv.momentos_ativos(daemon) == tv.SEM_MOMENTOS
    assert tv.vibracao_do_gatilho_ativa(daemon) == tv.SEM_VIBRACAO
    assert tv.estilo_ativo(daemon) is None


def test_o_computador_que_esvaziou_nao_deixa_resto() -> None:
    """Escolheu, voltou ao de fábrica: a vista velha não fica tocando."""
    _escolhe(STARLIGHT, "impacto")
    daemon = _daemon(None)
    assert tv.receita_ativa(daemon).efeitos_escolhidos

    opc.voltar_o_computador_ao_de_fabrica("vibracao", STARLIGHT)

    assert tv.receita_ativa(daemon) == tv.DESLIGADA
    assert tv.escolhas_ativas(daemon) == {}


def test_com_perfil_ativo_o_perfil_manda_e_o_computador_nao_vaza_na_troca() -> None:
    """Perfil → sem perfil → perfil: cada nome lê a vista dele, nunca a do vizinho."""
    _escolhe(STARLIGHT, "impacto")
    perfil = Profile(
        name="Tiro", match=MatchCriteria(window_class=["tiro"]), estilo="fps",
        controllers={STARLIGHT: {"rumble": {"efeito_haptico": "estalo"}}})  # type: ignore[arg-type]
    loader.save_profile(perfil, origem="régua")

    com_perfil = _daemon("Tiro")
    sem_perfil = _daemon(None)

    tv.receita_ativa(com_perfil)
    do_perfil = tv.escolhas_ativas(com_perfil)
    assert tv.escolhas_ativas(sem_perfil) == {}, "a vista do perfil não vale sem perfil"

    tv.receita_ativa(sem_perfil)
    assert tv.escolhas_ativas(sem_perfil) == {tv.norm_mac(STARLIGHT): "impacto"}
    assert tv.escolhas_ativas(com_perfil) == {}, "a vista do computador não vale no perfil"

    tv.receita_ativa(com_perfil)
    assert tv.escolhas_ativas(com_perfil) == do_perfil


def test_a_leitura_do_laco_nao_valida_o_modelo_de_novo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O laço é de 60 Hz: o computador do disco vira vista uma vez, não por tique."""
    _escolhe(STARLIGHT, "impacto")
    contas = {"vista": 0}
    original = opc.perfil_que_vale

    def _contada(*a: Any, **kw: Any) -> Any:
        contas["vista"] += 1
        return original(*a, **kw)

    monkeypatch.setattr(opc, "perfil_que_vale", _contada)
    daemon = _daemon(None)

    for _ in range(120):
        tv.receita_ativa(daemon)

    assert contas["vista"] == 1, contas
