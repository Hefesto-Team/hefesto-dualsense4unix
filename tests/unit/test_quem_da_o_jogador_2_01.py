"""A caixinha do Steam Input diz que a marca troca o dono do jogador 2.

QUEM-DÁ-O-JOGADOR-2-01 (08/08/2026). Com **dois** controles na mesa, marcar um
jogo na allowlist recolhe os gamepads virtuais dos secundários — e o co-op do
Hefesto sai de cena junto. MEDIDO no journal dela:
`coop_derrubado_pela_excecao_steam_input`, **sete vezes** em 08/08.

Isso é o desenho funcionando: são justamente esses vpads que produziriam o
controle dobrado que a marca existe para acabar. O que muda é **quem entrega o
jogador 2** — passa a ser o Steam Input, não nós.

O DEFEITO ERA O SILÊNCIO
========================
Com um controle, a frase antiga estava completa. Com dois, ela omitia a troca —
e a omissão custou a ela uma sessão inteira de Sackboy: marcou a caixinha às
01:43:16, e a partida virou *"um caos"*.

O QUE ESTE TEXTO NÃO PROMETE, DE PROPÓSITO
==========================================
Que o jogo vai ver dois jogadores. **Ninguém mediu** se o Steam Input entrega os
dois controles físicos ao jogo nesta máquina — é SEM PROVA, e prometer seria
inventar. O texto diz o que muda e manda conferir, que é o que a casa sustenta.
Estes testes travam essa fronteira nos dois sentidos: o aviso tem de aparecer, e
não pode virar promessa.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.actions.profiles_actions import (
    texto_da_marca_do_steam_input,
)

APPID = 1599660


# --- o aviso aparece quando ela tem dois na mesa ------------------------------


@pytest.mark.parametrize("controles", [2, 3, 4])
def test_com_dois_ou_mais_a_marca_avisa_da_troca(controles: int) -> None:
    """ARRANQUE A CURA e este teste REPROVA: ela perde o jogador 2 em silêncio."""
    texto = texto_da_marca_do_steam_input("adicionado", APPID, controles)
    assert "Steam Input" in texto, (
        "a caixinha não diz quem passa a dar o jogador 2. Com dois controles, "
        "marcar recolhe os vpads dos secundários e o co-op do Hefesto sai de "
        "cena — e ela descobre isso dentro do jogo, não na tela."
    )
    assert "jogador 2" in texto, "o aviso não nomeia o que ela vai perder de vista"
    assert str(controles) in texto, (
        "o aviso não diz QUANTOS controles ele viu — sem o número, ela não sabe "
        "se o produto está olhando para a mesa dela ou chutando."
    )


def test_o_aviso_manda_conferir_em_vez_de_prometer() -> None:
    """A fronteira do que é MEDIDO: dizer o que muda, não garantir o resultado.

    Ninguém mediu se o Steam Input entrega os dois controles ao jogo. Um texto
    que prometesse "os dois continuam funcionando" seria invenção — e invenção
    numa caixinha é pior que silêncio, porque ela confia e não confere.
    """
    texto = texto_da_marca_do_steam_input("adicionado", APPID, 2)
    assert "confira" in texto.lower(), (
        "o aviso não manda conferir. Como ninguém mediu se o Steam Input entrega "
        "os dois, conferir é a única instrução honesta."
    )
    for promessa in ("continuam funcionando", "os dois vão funcionar", "garantido"):
        assert promessa not in texto.lower(), (
            f"o texto promete {promessa!r} — isso é SEM PROVA e não pode ser dito."
        )


# --- e cala quando não há o que avisar ---------------------------------------


@pytest.mark.parametrize("controles", [None, 0, 1])
def test_com_um_controle_ou_sem_saber_o_texto_nao_muda(controles: int | None) -> None:
    """Com um controle a frase antiga já estava completa — não poluir.

    E `None` (não deu para ler a contagem) cai no mesmo lugar de propósito: o
    texto sem o aviso é VERDADEIRO para um controle e apenas incompleto para
    dois. Falhar para o lado de dizer menos nunca inventa; falhar para o lado de
    avisar sempre encheria a tela de aviso irrelevante.
    """
    texto = texto_da_marca_do_steam_input("adicionado", APPID, controles)
    assert "Steam Input" not in texto, (
        f"com controles={controles!r} o aviso do jogador 2 apareceu sem motivo."
    )
    # o essencial da frase antiga continua lá
    assert "controle dobrado" in texto
    assert "gatilhos continuam valendo" in texto


def test_tirar_a_marca_avisa_a_volta_do_coop() -> None:
    """O caminho de volta também é informação — e é a boa notícia."""
    texto = texto_da_marca_do_steam_input("removido", APPID, 2)
    assert "co-op volta" in texto.lower(), (
        "tirar a marca devolve o co-op do Hefesto, e a tela não diz. Se marcar "
        "avisa da perda, desmarcar tem de avisar da volta."
    )
    assert "co-op" not in texto_da_marca_do_steam_input("removido", APPID, 1).lower(), (
        "com um controle só não há co-op para voltar — o aviso vira ruído."
    )


# --- o que a cura não pode quebrar -------------------------------------------


@pytest.mark.parametrize(
    "status",
    ["appid_invalido", "erro", "ja_estava", "nao_estava"],
)
def test_os_outros_estados_nao_ganharam_aviso(status: str) -> None:
    """Nenhum desses mexe na allowlist, então nenhum troca o dono de nada."""
    texto = texto_da_marca_do_steam_input(status, APPID, 2)
    assert "jogador 2" not in texto, (
        f"o estado {status!r} não muda a allowlist, mas ganhou o aviso da troca "
        "— texto que avisa de coisa que não aconteceu queima a confiança do resto."
    )


def test_a_inversao_medida_continua_no_texto() -> None:
    """A metade da SAÍDA, que a medição dela de 06/08 fixou, não pode sumir.

    O contrapeso desta sprint: acrescentar o aviso do co-op não pode custar a
    frase que a `CONTROLE-SONY-MEDIDO-01` conquistou — que a cor e os gatilhos
    dela CONTINUAM valendo dentro da marca. É a metade que ela usa.
    """
    for controles in (None, 1, 2):
        texto = texto_da_marca_do_steam_input("adicionado", APPID, controles)
        assert "cor e os seus gatilhos continuam valendo" in texto, (
            "sumiu a metade medida da INVERSÃO: dentro da marca o Hefesto mantém "
            "a saída. Sem essa frase o texto volta a sugerir que ela perde tudo."
        )
