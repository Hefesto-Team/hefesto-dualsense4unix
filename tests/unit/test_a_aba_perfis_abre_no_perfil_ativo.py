"""A aba Perfis abre no perfil ativo, e o exemplo do desenho nunca passa por dado.

Medido em 06/11/2026: abrir um jogo trocava o «Perfil ativo», e a linha aberta continuava na
última escolhida; e a lista do desenho (Mortal Kombat, perfil que não existe no disco) aparecia
quando a primeira pintura passava do prazo da espera.
"""
from __future__ import annotations

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("a aba Perfis que abre no perfil ativo")

from hefesto_dualsense4unix.interface import folha_da_casa, hefesto_vivo, pacotes
from hefesto_dualsense4unix.interface.pacotes import a10_perfis as a10

PAGINA = "10-perfis.html"
TODOS = [{"nome": "Klaroro"}, {"nome": "Future Fragments"}, {"nome": "Faith"}]


@pytest.fixture(autouse=True)
def limpo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a10, "_ESCOLHIDO", "")
    monkeypatch.setattr(a10, "_VISTO", ("", ""))
    monkeypatch.setattr(a10, "_PINTADO_PARA", "")
    monkeypatch.setattr(a10, "_ULTIMO_TIQUE", 0.0)


def test_a_linha_acompanha_o_perfil_que_o_jogo_ativou() -> None:
    assert a10._escolhido(TODOS, "Klaroro") == "Klaroro"
    assert a10._escolhido(TODOS, "Future Fragments") == "Future Fragments"


def test_o_clique_continua_valendo_enquanto_o_ativo_nao_muda() -> None:
    a10._escolhido(TODOS, "Klaroro")
    a10._ESCOLHIDO = "Faith"
    assert a10._escolhido(TODOS, "Klaroro") == "Faith"


def test_o_clique_vence_o_ativo_que_ainda_nao_trocou() -> None:
    a10._escolhido(TODOS, "Klaroro")
    a10._ESCOLHIDO = "Faith"
    assert a10._escolhido(TODOS, "Future Fragments") == "Faith"


def test_ativo_fora_da_lista_nao_leva_a_linha() -> None:
    a10._escolhido(TODOS, "Klaroro")
    assert a10._escolhido(TODOS, "freestyle") == "Klaroro"


def test_reabrir_a_aba_volta_ao_perfil_ativo() -> None:
    a10._escolhido(TODOS, "Klaroro")
    a10._ESCOLHIDO = "Faith"
    pacotes.a_aba_abriu(PAGINA)
    assert a10._escolhido(TODOS, "Klaroro") == "Klaroro"


def test_reabrir_em_menos_de_dois_segundos_repinta_o_campo_do_jogo() -> None:
    assert a10._uma_vez_so("Klaroro") == ()
    assert a10._uma_vez_so("Klaroro") == a10.CAMPOS_QUE_O_USUARIO_DIGITA
    pacotes.a_aba_abriu(PAGINA)
    assert a10._uma_vez_so("Klaroro") == ()


def test_a_janela_avisa_a_aba_antes_da_primeira_pintura() -> None:
    fonte = hefesto_vivo.Piloto._instalado.__code__.co_names
    assert "a_aba_abriu" in fonte


@pytest.mark.parametrize("seletor", ['tbody[data-hef="perfis.lista"] tr',
                                     'input[data-hef="editor.jogo"]',
                                     'ol[data-hef="editor.ordem"] li'])
def test_o_desenho_fica_escondido_ate_o_dado_chegar(seletor: str) -> None:
    assert f"{folha_da_casa.SEM_OS_DADOS} {seletor}" in folha_da_casa.FOLHA_DA_CASA


def test_a_pintura_com_blocos_mostra_o_dado() -> None:
    assert "classList.add('hef-dados-na-tela')" in hefesto_vivo.BOOTSTRAP
