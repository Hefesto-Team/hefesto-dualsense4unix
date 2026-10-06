"""A prova botão a botão não pode gravar no perfil DELA."""

from __future__ import annotations

import types

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.interface import hefesto_vivo, regua_do_mockup

PAGINAS = (
    "01-jogar.html", "02-controles.html", "03-gatilhos.html",
    "04-iluminacao.html", "05-vibracao.html", "06-navegacao.html",
    "07-lancadores.html", "08-conexoes.html", "09-sistema.html",
    "10-perfis.html",
)


class _Gesto:
    """O mínimo que ``_alvos_a_clicar`` lê de um gesto da página."""

    def __init__(self, nome: str) -> None:
        self.nome = nome


@pytest.mark.parametrize("pagina", PAGINAS)  # (noqa-acento): nome do argumento
def test_o_salvar_fica_de_fora_em_toda_aba(pagina: str) -> None:
    """Em qualquer das dez, a prova pula o ``salvar`` em vez de clicá-lo."""
    vistos, pulados = regua_do_mockup._alvos_a_clicar(
        [_Gesto("salvar"), _Gesto("aplicar")], {"salvar", "aplicar"},
        pagina, hefesto_vivo.PERIGOSOS)
    assert "salvar" in pulados, (
        f"a prova clicaria `salvar` na {pagina} — e esse clique grava no "
        "perfil dela, sem diálogo e sem perguntar")
    assert "salvar" not in vistos


def test_o_coringa_nao_isenta_o_que_nao_pediu() -> None:
    """O ``("*", …)`` isenta o gesto NOMEADO, e nada mais."""
    vistos, pulados = regua_do_mockup._alvos_a_clicar(
        [_Gesto("aplicar"), _Gesto("exportar"), _Gesto("importar")],
        {"aplicar", "exportar", "importar"},
        "01-jogar.html", hefesto_vivo.PERIGOSOS)
    assert pulados == [], f"o coringa vazou para {pulados}"
    assert set(vistos) == {"aplicar", "exportar", "importar"}


def test_a_isencao_por_pagina_continua_valendo() -> None:
    """O casamento novo não pode ter apagado o velho."""
    _, pulados_perfis = regua_do_mockup._alvos_a_clicar(
        [_Gesto("detectar")], {"detectar"}, "10-perfis.html",
        hefesto_vivo.PERIGOSOS)
    vistos_lanc, _ = regua_do_mockup._alvos_a_clicar(
        [_Gesto("detectar")], {"detectar"}, "07-lancadores.html",
        hefesto_vivo.PERIGOSOS)
    assert pulados_perfis == ["detectar"], (
        "o `detectar` dos Perfis deixou de ser isento — ele grava no perfil dela")
    assert vistos_lanc == ["detectar"], (
        "o `detectar` dos Lançadores deixou de ser provado: a qualificação por "
        "página parou de valer e o coringa passou a tratar os dois igual")


def test_incluir_perigosos_continua_alcancando_o_salvar() -> None:
    """Isento não é inalcançável — quem roda com ``--incluir-perigosos`` clica."""
    vistos, pulados = regua_do_mockup._alvos_a_clicar(
        [_Gesto("salvar")], {"salvar"}, "10-perfis.html", set())
    assert vistos == ["salvar"] and pulados == []


class _PilotoDeMentira:
    """O mínimo que `_provar_cliques` toca: a bandeira e a página de agora."""

    def __init__(self, pagina: str, gestos: str, incluir: bool = False) -> None:
        self.pagina = pagina
        self.pronto = False
        self.args = types.SimpleNamespace(
            prova_clique=gestos, incluir_perigosos=incluir)


def test_a_prova_clique_recusa_o_que_mexe_na_maquina_dela() -> None:
    """A MORDIDA: tire a guarda do `_provar_cliques` e este teste passa a clicar."""
    piloto = _PilotoDeMentira("10-perfis.html", "remover")
    with pytest.raises(SystemExit) as caiu:
        hefesto_vivo.Piloto._provar_cliques(piloto)
    assert caiu.value.code == 1


def test_a_prova_clique_recusa_mesmo_quando_o_perigoso_vem_no_meio() -> None:
    """Um gesto inócuo na frente não pode comprar passagem para o perigoso."""
    piloto = _PilotoDeMentira("09-sistema.html", "atualizar,parar-ou-retomar")
    with pytest.raises(SystemExit):
        hefesto_vivo.Piloto._provar_cliques(piloto)


def test_a_prova_clique_deixa_passar_o_inocuo() -> None:
    """E a recusa não pode virar uma porta fechada: o inócuo continua clicável."""
    piloto = _PilotoDeMentira("09-sistema.html", "atualizar")
    assert hefesto_vivo.Piloto._provar_cliques(piloto) is False


def test_a_prova_clique_abre_com_incluir_perigosos() -> None:
    """A escolha continua sendo de quem roda, e ela é explícita."""
    piloto = _PilotoDeMentira("10-perfis.html", "remover", incluir=True)
    assert hefesto_vivo.Piloto._provar_cliques(piloto) is False
