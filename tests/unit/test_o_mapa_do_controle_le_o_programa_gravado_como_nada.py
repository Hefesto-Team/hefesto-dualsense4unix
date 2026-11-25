"""D-2511-O-PROGRAMA-GRAVADO-NO-BOTAO-VIRA-NADA: a aba Mapa do controle lê o programa como nada.

O perfil de jogo que guardava `__PROGRAMA__` num botão aparecia na aba Navegação como «— Nada —»
e na aba Mapa do controle como «Escolher um programa…»: a Navegação lê a tabela por
`acoes.tabela_efetiva`, e a tabela do perfil de jogo saía do cru. O cru de toda chave passa agora
por `acoes.sem_o_que_ninguem_faz`, e o gesto que grava aplica a mesma leitura ao que o perfil já
guardava; sem gesto o arquivo fica byte a byte. O PS fica de fora: a escolha dele vai ao degrau
da máquina.

MORDIDAS: devolver o cru ao `_base` reprova as 21 linhas da tela e o molde reprova o do molde;
devolver o cru ao `_aplicar_as_edicoes` reprova o gesto (o programa continua gravado nas outras
linhas); tirar a comparação com o perfil lido do `mapa_guardar` reprova o «sem gesto o arquivo
não muda».
"""
from __future__ import annotations

import pathlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13

JOGO = "Jogo ensaio"
OUTRO = "Perfil de agora"
NADA = acoes.rotulo(acoes.TOKEN_NADA)
LINHAS_DA_TELA = [x.b for x in a13.BOTOES_DA_PAGINA
                  if x.motor is not None and x.motor != acoes.BOTAO_PS]


def _ctx() -> Any:
    return Contexto(state={"active_profile": OUTRO}, mesa=[], conectados=[], escolhido="")


@pytest.fixture
def mapa() -> Any:
    a13._largar()
    yield a13
    a13._largar()


def _grava(nome: str, **campos: Any) -> pathlib.Path:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

    return pathlib.Path(loader.save_profile(Profile(name=nome, match=MatchManual(), **campos)))


def _abre_o_jogo(mapa: Any, ctx: Any) -> None:
    mapa.mapa_perfil(ctx, {"valor": f"{a13.PERFIL}{JOGO}"}, None)


def test_a_cobertura_da_regua_sao_as_21_linhas() -> None:
    assert len(LINHAS_DA_TELA) == 21


@pytest.mark.parametrize("linha", LINHAS_DA_TELA)
def test_o_programa_gravado_no_perfil_de_jogo_aparece_como_nada(mapa: Any, linha: str) -> None:
    """D-2511-O-PROGRAMA-GRAVADO-NO-BOTAO-VIRA-NADA: cada uma das 21 linhas diz «— Nada —»."""
    motor = a13.POR_BOTAO[linha].motor
    _grava(JOGO, button_actions={motor: acoes.TOKEN_PROGRAMA})
    ctx = _ctx()
    _abre_o_jogo(mapa, ctx)

    assert mapa._linhas(ctx, set())[f"val-{linha}"] == NADA


@pytest.mark.parametrize("linha", LINHAS_DA_TELA)
def test_a_linha_do_jogo_diz_o_mesmo_que_a_navegacao(mapa: Any, linha: str) -> None:
    """Igual à aba Navegação: o perfil ativo com o programa gravado lê o mesmo texto."""
    motor = a13.POR_BOTAO[linha].motor
    _grava(OUTRO, button_actions={motor: acoes.TOKEN_PROGRAMA})
    ctx = _ctx()
    na_navegacao = mapa._linhas(ctx, set())[f"val-{linha}"]
    mapa._largar()
    _grava(JOGO, button_actions={motor: acoes.TOKEN_PROGRAMA})
    _abre_o_jogo(mapa, ctx)

    assert mapa._linhas(ctx, set())[f"val-{linha}"] == na_navegacao == NADA


def test_o_ps_segue_com_o_degrau_da_maquina(mapa: Any) -> None:
    _grava(JOGO, button_actions={acoes.BOTAO_PS: acoes.TOKEN_PROGRAMA})
    ctx = _ctx()
    _abre_o_jogo(mapa, ctx)

    assert mapa._base(ctx, f"{a13.PERFIL}{JOGO}")["ps"] == (a13.ACAO, acoes.TOKEN_PROGRAMA)


def test_o_programa_ao_lado_de_uma_acao_real_so_muda_o_programa(mapa: Any) -> None:
    _grava(JOGO, button_actions={"cross": acoes.TOKEN_PROGRAMA, "circle": "KEY_A"})
    ctx = _ctx()
    _abre_o_jogo(mapa, ctx)
    linhas = mapa._linhas(ctx, set())

    assert linhas["val-cross"] == NADA
    assert linhas["val-circle"] != NADA


def test_sem_gesto_o_arquivo_nao_muda_e_o_guardar_recusa(mapa: Any) -> None:
    """Sem gesto na linha, nada se regrava: o arquivo fica byte a byte."""
    caminho = _grava(JOGO, button_actions={"cross": acoes.TOKEN_PROGRAMA, "options": "KEY_A"})
    antes = caminho.read_bytes()
    ctx = _ctx()
    _abre_o_jogo(mapa, ctx)
    mapa._linhas(ctx, set())

    with pytest.raises(RuntimeError, match="não havia o que guardar"):
        mapa.mapa_guardar(ctx, {}, MagicMock())

    assert caminho.read_bytes() == antes


def test_o_gesto_numa_linha_regrava_nada_no_lugar_do_programa(mapa: Any) -> None:
    """O gesto grava o que a tela mostra: o programa das outras linhas vira `__NADA__`."""
    from hefesto_dualsense4unix.profiles import loader

    _grava(JOGO, button_actions={"cross": acoes.TOKEN_PROGRAMA, "dpad_up": acoes.TOKEN_PROGRAMA,
                                 "options": acoes.TOKEN_PROGRAMA})
    ctx = _ctx()
    _abre_o_jogo(mapa, ctx)
    mapa.mapa_botao(ctx, {"b": "triangle"}, None)
    mapa.mapa_escolher(ctx, {"v": f"{a13.ACAO}:KEY_A"}, None)

    mapa.mapa_guardar(ctx, {}, MagicMock())

    guardado = loader.load_profile(JOGO).button_actions
    assert guardado == {"cross": acoes.TOKEN_NADA, "dpad_up": acoes.TOKEN_NADA,
                        "options": acoes.TOKEN_NADA, "triangle": "KEY_A"}


def test_o_gesto_na_propria_linha_do_programa_grava_nada(mapa: Any) -> None:
    from hefesto_dualsense4unix.profiles import loader

    _grava(JOGO, button_actions={"cross": acoes.TOKEN_PROGRAMA})
    ctx = _ctx()
    _abre_o_jogo(mapa, ctx)
    mapa.mapa_botao(ctx, {"b": "cross"}, None)
    mapa.mapa_escolher(ctx, {"v": f"{a13.ACAO}:{acoes.TOKEN_NADA}"}, None)

    mapa.mapa_guardar(ctx, {}, MagicMock())

    assert loader.load_profile(JOGO).button_actions == {"cross": acoes.TOKEN_NADA}


def test_o_molde_com_o_programa_tambem_diz_nada(
        mapa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2511-O-PROGRAMA-GRAVADO-NO-BOTAO-VIRA-NADA: toda chave lê o cru pela mesma regra."""
    from types import SimpleNamespace

    molde = SimpleNamespace(button_actions={"cross": acoes.TOKEN_PROGRAMA, "circle": "KEY_A"})
    monkeypatch.setattr(mapa, "_molde_da_chave", lambda chave: molde)

    base = mapa._base(_ctx(), f"{a13.MOLDE}qualquer")

    assert base["cross"] == (a13.ACAO, acoes.TOKEN_NADA)
    assert base["circle"] == (a13.ACAO, "KEY_A")
