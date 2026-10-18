"""«Movimento do cursor» e «Rolagem» só aparecem na linha que os atende.

Sprint CURSOR-E-ROLAGEM-SO-NA-LINHA-QUE-OS-ATENDE-01.

Medido antes de curar (17/10/2026), sobre `acoes_de_botao.por_grupo` (o que a aba 06 desenha) e
`resolver` (quem atende o que se guardou):

* as 19 linhas de botão (fora o PS) ofereciam «Movimento do cursor» e «Rolagem», que só um
  eixo atende: o `resolver` as mandava para `sem_dono`;
* o analógico esquerdo oferecia «Rolagem» e o direito «Movimento do cursor» (o device liga o
  cursor só no esquerdo e a rolagem só no direito);
* a linha de um analógico oferecia 31 ações (20 teclas soltas, comandos e os dois tokens de eixo
  trocados) e só 4 têm atendente.

A lista de cada tipo de linha sai de UMA declaração (`LINHAS_DA_ACAO_DE_EIXO`), que o `resolver`
lê também (nele é a mesma decisão de antes, agora de uma fonte só). MORDIDAS (arrancadas e
devolvidas): voltar o `por_grupo` ao filtro velho devolve o cursor aos botões e reprova as de
lista; declarar o cursor nos dois eixos reprova a do cursor só no esquerdo e a do que o eixo
emite; devolver o `_o_que_a_linha_mostra` ao rótulo cru reprova a do perfil antigo.
"""
from __future__ import annotations

import pathlib
from typing import Any

import pytest

from hefesto_dualsense4unix.core import acoes_de_botao as acoes

ESQ, DIR = acoes.EIXO_ESQUERDO, acoes.EIXO_DIREITO
EIXOS = (ESQ, DIR)
LINHAS_DE_BOTAO = [b for b in acoes.BOTOES if b not in EIXOS and b != acoes.BOTAO_PS]
DE_EIXO = {acoes.TOKEN_CURSOR, acoes.TOKEN_ROLAGEM, acoes.TOKEN_WASD, acoes.TOKEN_SETAS}


def _tokens(linha: str | None) -> set[str]:
    tokens = {acoes.token_do_rotulo(r) for _g, rotulos in acoes.por_grupo(linha) for r in rotulos}
    tokens.discard(None)
    return {t for t in tokens if t is not None}


@pytest.mark.parametrize("linha", LINHAS_DE_BOTAO)
def test_a_linha_de_botao_nao_oferece_nenhuma_acao_de_eixo(linha: str) -> None:
    oferecidos = _tokens(linha)
    assert not oferecidos & DE_EIXO, f"{linha} oferece {sorted(oferecidos & DE_EIXO)}"
    assert oferecidos, f"{linha} ficou sem lista"


def test_o_cursor_e_so_do_esquerdo_e_a_rolagem_so_do_direito() -> None:
    assert acoes.TOKEN_CURSOR in _tokens(ESQ) and acoes.TOKEN_ROLAGEM not in _tokens(ESQ)
    assert acoes.TOKEN_ROLAGEM in _tokens(DIR) and acoes.TOKEN_CURSOR not in _tokens(DIR)


@pytest.mark.parametrize("linha", EIXOS)
def test_a_linha_do_analogico_so_oferece_o_que_o_eixo_emite(linha: str) -> None:
    """Nada de tecla solta, de botão do mouse nem de comando: só o próprio, as teclas e o Nada."""
    proprio = acoes.TOKEN_CURSOR if linha == ESQ else acoes.TOKEN_ROLAGEM
    esperado = {proprio, acoes.TOKEN_WASD, acoes.TOKEN_SETAS, acoes.TOKEN_NADA}
    assert _tokens(linha) == esperado, sorted(_tokens(linha) ^ esperado)


def test_a_lista_geral_e_a_do_ps_seguem_como_eram() -> None:
    assert _tokens(None) >= DE_EIXO, "a lista geral perdeu uma ação de eixo"
    assert not _tokens(acoes.BOTAO_PS) & DE_EIXO


@pytest.mark.parametrize("linha", [*LINHAS_DE_BOTAO, *EIXOS])
def test_a_lista_e_o_resolver_dizem_o_mesmo(linha: str) -> None:
    """O que a linha oferece tem quem o atenda; o que ela não oferece (e o resolver conhece como
    de eixo) cai em `sem_dono` ali. A lista e o `resolver` leem a mesma declaração."""
    oferecidos = _tokens(linha)
    for token in sorted(DE_EIXO):
        _mouse, _teclado, sem_dono = acoes.resolver({linha: token})
        if token in oferecidos:
            assert linha not in sem_dono, f"{linha} oferece {token} e ninguém o atende"
        else:
            assert linha in sem_dono, f"{linha} não oferece {token} mas o resolver o atende"


@pytest.mark.parametrize("linha", EIXOS)
@pytest.mark.parametrize(
    "token", ["KEY_E", "BTN_LEFT", "KEY_LEFTALT+KEY_TAB", "__TOGGLE_OSK__"])
def test_o_que_o_eixo_nao_emite_cai_em_sem_dono(linha: str, token: str) -> None:
    if token not in acoes.ACOES:
        pytest.skip("token de comando sem esse nome nesta versão")
    assert token not in _tokens(linha)
    assert linha in acoes.resolver({linha: token})[2]


def test_o_perfil_antigo_com_a_acao_fora_do_lugar_mostra_nada(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
) -> None:
    """Cursor num botão, Rolagem no esquerdo, Cursor no direito e uma tecla solta num analógico:
    o perfil carrega sem migração calada e cada linha mostra «— Nada —», o que ela faz.
    MORDIDA: devolver `acoes.rotulo(token)` em `_o_que_a_linha_mostra` reprova."""
    monkeypatch.syspath_prepend(
        str(pathlib.Path(__file__).resolve().parents[2] / "src/hefesto_dualsense4unix/interface"))
    import pacotes
    from pacotes import a06_navegacao

    from tests.unit.test_a_06_nao_manda_para_o_vazio import (
        ESTADO,
        FALSO,
        MESA,
        _perfil_de_mentira,
    )

    _perfil_de_mentira(monkeypatch, tmp_path, button_actions={
        "cross": acoes.TOKEN_CURSOR, "circle": acoes.TOKEN_ROLAGEM,
        ESQ: acoes.TOKEN_ROLAGEM, DIR: "KEY_E", "square": "KEY_ESC"})
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})
    mesa = a06_navegacao.pacote(ctx)["mesa"]
    nada = acoes.rotulo(acoes.TOKEN_NADA)
    for linha in ("cross", "circle", ESQ, DIR):
        assert mesa[f"acao-{linha}"] == nada, (linha, mesa[f"acao-{linha}"])
    assert mesa["acao-square"] == "Esc", "a linha de botão com tecla legítima mudou"


def test_o_de_fabrica_dos_analogicos_segue_na_lista_deles() -> None:
    """O de fábrica de cada linha é oferecido por ela: a tela nunca mostra o padrão sem opção."""
    padrao = acoes.padrao()
    for linha in (*LINHAS_DE_BOTAO, *EIXOS):
        assert padrao[linha] in _tokens(linha), f"{linha}: o de fábrica não está na lista"
