"""Sem perfil ativo, a luz animada lê o computador — 18/10/2026.

A aba Iluminação grava o efeito no ``maquina.json`` quando não há perfil (``onde_grava``: sem
perfil, grava no computador). O ``perfil_ativo`` da luz devolvia ``None`` no nome vazio, e o
efeito escolhido na tela nunca tocava: a luz ficava fixa. O tato já lia o computador
(D-1610-O-TATO-LE-O-COMPUTADOR-SEM-PERFIL-ATIVO); a luz passa a ler o mesmo
``perfil_que_vale`` do perfil vazio.

O gatilho do jogo (``gatilho_do_jogo``) não lê perfil nenhum: ele diz no barramento os bytes que
o jogo escreveu, e o computador não guarda gatilho (``DO_JOGO["triggers"]``). Não há buraco ali, e
o último teste prova isso pelo avesso.

MORDIDA: devolva o ``return None`` do nome vazio em ``perfil_ativo`` e os testes do efeito
reprovam; troque o computador do ramo pelo perfil vazio puro e o efeito do controle some.
"""
from __future__ import annotations

import ast
import inspect
from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems import gatilho_do_jogo as gj
from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.schema import ler_o_efeito_da_luz

STARLIGHT = "aa:bb:cc:00:00:01"
BRANCO = "aa:bb:cc:00:00:02"
RESPIRAR = "respirar;ff0000;4"
CHAMA = "chama;00ff00;6"


def _daemon(nome: str | None = None) -> Any:
    return SimpleNamespace(store=SimpleNamespace(active_profile=nome))


def _escolhe(efeito: str | None, uniq: str | None = None) -> None:
    """O gesto da aba Iluminação sem perfil: grava no computador."""
    onde = opc.gravar("luz", {"leds": {"efeito": efeito}}, uniq=uniq)
    assert onde == opc.COMPUTADOR, "sem perfil o gesto grava no computador"


def test_sem_perfil_o_efeito_do_computador_chega_a_luz() -> None:
    _escolhe(RESPIRAR)

    perfil = luz.perfil_ativo(_daemon(None))

    assert perfil is not None
    assert perfil.leds.efeito == RESPIRAR
    plano = luz.plano_do_perfil(perfil, [STARLIGHT, BRANCO])
    esperado = ler_o_efeito_da_luz(RESPIRAR)
    assert {u: p.efeito for u, p in plano.items()} == {STARLIGHT: esperado, BRANCO: esperado}


def test_nome_vazio_e_nome_ausente_valem_o_mesmo() -> None:
    _escolhe(RESPIRAR)
    for nome in (None, ""):
        perfil = luz.perfil_ativo(_daemon(nome))
        assert perfil is not None and perfil.leds.efeito == RESPIRAR


def test_cada_controle_fica_com_o_efeito_dele() -> None:
    _escolhe(RESPIRAR)
    _escolhe(CHAMA, uniq=BRANCO)

    perfil = luz.perfil_ativo(_daemon(None))

    assert perfil is not None
    plano = luz.plano_do_perfil(perfil, [STARLIGHT, BRANCO])
    assert plano[STARLIGHT].efeito.base == "respirar"
    assert plano[BRANCO].efeito.base == "chama"


def test_o_computador_vazio_continua_sem_efeito() -> None:
    perfil = luz.perfil_ativo(_daemon(None))

    assert perfil is None or luz.plano_do_perfil(perfil, [STARLIGHT]) == {}


def test_o_computador_que_esvaziou_nao_deixa_resto() -> None:
    _escolhe(RESPIRAR)
    assert luz.perfil_ativo(_daemon(None)) is not None
    _escolhe(None)

    perfil = luz.perfil_ativo(_daemon(None))

    assert perfil is None or luz.plano_do_perfil(perfil, [STARLIGHT]) == {}


def test_o_passo_do_laco_pinta_o_efeito_do_computador() -> None:
    """Pelo laço real: sem perfil ativo, o primeiro tique escreve um quadro do efeito."""
    _escolhe(RESPIRAR)
    escritos: list[tuple[str, tuple[int, int, int]]] = []
    animada = luz.LuzAnimada(lambda u, c: escritos.append((u, c)), lambda u: None)
    daemon = _daemon(None)
    daemon.controller = SimpleNamespace(
        list_controllers=lambda: [SimpleNamespace(uniq=STARLIGHT)])
    passo = luz.Passo(daemon, animada)
    passo._plano = {}
    perfil = luz.perfil_ativo(daemon)
    assert perfil is not None
    passo._plano = luz.plano_do_perfil(perfil, [STARLIGHT])

    assert passo._plano and STARLIGHT in passo._plano
    assert animada.tique(1.0, passo._plano) == 1
    assert escritos and escritos[0][0] == STARLIGHT


def test_o_perfil_ativo_continua_mandando_sobre_o_computador(
    monkeypatch: Any,
) -> None:
    """Com perfil ativo o ramo do computador não entra: vale a leitura do arquivo."""
    _escolhe(RESPIRAR)
    chamadas: list[str] = []

    def _sem_arquivo(nome: str) -> None:
        chamadas.append(nome)

    monkeypatch.setattr("hefesto_dualsense4unix.profiles.loader.perfil_em_disco", _sem_arquivo)

    assert luz.perfil_ativo(_daemon("Sackboy")) is None
    assert chamadas == ["Sackboy"]


def test_o_gatilho_do_jogo_nao_le_perfil_e_o_computador_nao_guarda_gatilho() -> None:
    """Não há buraco no gatilho: o módulo só decodifica o bloco que o jogo escreveu."""
    arvore = ast.parse(inspect.getsource(gj))
    lidos = {
        no.attr for no in ast.walk(arvore)
        if isinstance(no, ast.Attribute) and no.attr in {"active_profile", "store"}
    } | {
        no.value for no in ast.walk(arvore)
        if isinstance(no, ast.Constant) and no.value in {"active_profile", "store"}
    }
    assert lidos == set()
    assert "triggers" in opc.DO_JOGO, "o gatilho é o efeito de cada jogo, não do computador"
