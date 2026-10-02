"""QUEM DÁ O JOGADOR 2 — a pergunta ficou; a resposta virou "o Hefesto"."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("quem dá o jogador 2")

import pytest

from hefesto_dualsense4unix.app.actions.profiles_actions import (
    texto_da_marca_do_steam_input,
)

APPID = 1599660

_AVISOS_QUE_MORRERAM = (
    "quem passa a dar o jogador 2",
    "steam input, não o hefesto",
    "o co-op volta a ser do hefesto",
)


@pytest.mark.parametrize("controles", [None, 0, 1, 2, 3, 4])
def test_a_caixinha_nao_avisa_mais_de_um_preco_que_nao_e_cobrado(
    controles: int | None,
) -> None:
    """A MORDIDA: devolva `suspend_vpads_for_steam_input` à borda de entrada da"""
    texto = texto_da_marca_do_steam_input("adicionado", APPID, controles).lower()

    for morto in _AVISOS_QUE_MORRERAM:
        assert morto not in texto, (
            f"a caixinha voltou a avisar {morto!r} — com a inversão de 09/08 o "
            "jogador 2 continua sendo do Hefesto, e avisar de uma perda que não "
            "acontece é a mesma mentira do aviso falso do co-op, só que na "
            "caixinha que ela clica no meio da noite."
        )


@pytest.mark.parametrize("controles", [2, 3, 4])
def test_com_dois_ou_mais_a_caixinha_diz_que_os_jogadores_ficam(
    controles: int,
) -> None:
    """O que substituiu o aviso: a boa notícia, com o número que ela tem na mesa."""
    texto = texto_da_marca_do_steam_input("adicionado", APPID, controles)

    assert "Hefesto" in texto, "a tela não diz de quem continuam sendo os controles"
    assert str(controles) in texto, (
        "o texto não diz QUANTOS controles ele viu — sem o número, ela não sabe "
        "se o produto está olhando para a mesa dela ou chutando."
    )
    assert "um jogador cada" in texto, (
        "some a única frase que responde à pergunta desta sprint: com dois "
        "controles, quem dá o jogador 2."
    )


def test_a_caixinha_manda_conferir_em_vez_de_prometer() -> None:
    """A fronteira do que é MEDIDO não se moveu: dizer o que o PRODUTO faz, e"""
    texto = texto_da_marca_do_steam_input("adicionado", APPID, 2)

    assert "confira" in texto.lower(), (
        "o texto não manda conferir. Como ninguém mediu o que o JOGO lista, "
        "conferir é a única instrução honesta."
    )
    for promessa in ("garantido", "vai listar dois", "os dois vão funcionar"):
        assert promessa not in texto.lower(), (
            f"o texto promete {promessa!r} — isso é SEM PROVA e não pode ser dito."
        )


@pytest.mark.parametrize("controles", [None, 0, 1])
def test_com_um_controle_ou_sem_saber_o_texto_nao_fala_de_jogadores(
    controles: int | None,
) -> None:
    """Com um controle não há jogador 2 — nem para perder, nem para prometer."""
    texto = texto_da_marca_do_steam_input("adicionado", APPID, controles)

    assert "um jogador cada" not in texto, (
        f"com controles={controles!r} a frase da mesa apareceu sem mesa."
    )
    assert "controle dobrado" in texto
    assert "gatilhos" in texto and "continuam valendo" in texto


def test_tirar_a_marca_diz_o_que_volta_a_acontecer() -> None:
    """NOTA DATADA — 09/08/2026: aqui se exigia *"o co-op volta a ser do"""
    texto = texto_da_marca_do_steam_input("removido", APPID, 2)

    assert "físico" in texto, (
        "desmarcar deixou de dizer o que muda. Se marcar diz que esconde o "
        "físico, desmarcar tem de dizer que ele volta a aparecer."
    )
    assert "co-op" not in texto.lower(), (
        "o co-op voltou ao texto — com a inversão ele não sai em momento nenhum, "
        "e citá-lo aqui sugere que sai."
    )


@pytest.mark.parametrize(
    "status",
    ["appid_invalido", "erro", "ja_estava", "nao_estava"],
)
def test_os_outros_estados_nao_falam_de_jogador_nenhum(status: str) -> None:
    """Nenhum desses mexe na allowlist, então nenhum muda o que o jogo vê."""
    texto = texto_da_marca_do_steam_input(status, APPID, 2)
    assert "jogador" not in texto.lower(), (
        f"o estado {status!r} não muda a allowlist, mas ganhou frase sobre "
        "jogadores — texto que fala de coisa que não aconteceu queima a "
        "confiança do resto."
    )


def test_a_inversao_medida_continua_no_texto() -> None:
    """A metade da SAÍDA, que a medição dela de 06/08 fixou, não pode sumir."""
    for controles in (None, 1, 2):
        texto = texto_da_marca_do_steam_input("adicionado", APPID, controles)
        assert "cor" in texto and "gatilhos" in texto and "vibração" in texto, (
            "sumiu a metade medida da INVERSÃO: dentro da marca o Hefesto mantém "
            "a saída. Sem essa frase o texto volta a sugerir que ela perde tudo."
        )


@pytest.mark.parametrize("status", ["adicionado", "removido"])
def test_toda_marcacao_manda_fechar_e_abrir_o_jogo(status: str) -> None:
    """A metade que o daemon NÃO entrega ao vivo, dita na tela."""
    texto = texto_da_marca_do_steam_input(status, APPID, 2)
    assert "Feche e abra o jogo" in texto, (
        "sumiu a única instrução que faz a marca valer inteira. Sem ela, ela "
        "marca, não vê diferença nenhuma e conclui que a caixinha não funciona."
    )
