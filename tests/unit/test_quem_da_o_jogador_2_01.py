"""QUEM DÁ O JOGADOR 2 — a pergunta ficou; a resposta virou "o Hefesto".

QUEM-DÁ-O-JOGADOR-2-01 (08/08/2026). Com **dois** controles na mesa, marcar um
jogo na allowlist recolhia os gamepads virtuais dos secundários — e o co-op do
Hefesto saía de cena junto. MEDIDO no journal dela: `coop_derrubado_pela_
excecao_steam_input`, sete vezes quando esta sprint foi escrita, **vinte** no fim
do dia.

O defeito daquela sprint era o SILÊNCIO: com um controle, a frase da caixinha
estava completa; com dois, ela omitia a troca do dono do jogador 2 — e a omissão
custou a ela uma sessão inteira de Sackboy. A cura foi o aviso.

NOTA DATADA — 09/08/2026 (ESCONDER-EM-VEZ-DE-SAIR-01, decisão dela)
===================================================================
**O aviso saiu porque o defeito que ele avisava foi CURADO, não porque
incomodava.** A marca inverteu de lado: em vez de recolher os controles
virtuais, ela esconde o controle FÍSICO. Os virtuais ficam de pé, um por
controle, e o jogador 2 continua sendo do Hefesto — que é exatamente o que o
aviso dizia que se perdia.

Manter a frase agora seria a doença de sempre pelo avesso: **a tela avisando de
um preço que o produto parou de cobrar.** É a mesma classe de erro que a
`AVISO-FALSO-DO-COOP-01` está curando no badge, e por isso este arquivo não foi
apagado — ele passou a travar a fronteira do outro lado:

1. a caixinha **não pode** avisar de uma perda que não acontece mais;
2. a caixinha **não pode** prometer que o jogo vai LISTAR dois jogadores —
   isso depende do jogo, ninguém mediu nesta máquina, e a prova é dela (§6 do
   desenho: abrir o jogo marcado com dois controles e contar);
3. a metade MEDIDA da `CONTROLE-SONY-MEDIDO-01` (dentro da marca, a saída
   continua sendo do Hefesto) tem de continuar dita;
4. toda marcação tem de mandar **fechar e abrir o jogo** — metade da marca é a
   env que o jogo lê UMA vez, na abertura (`assets/hefesto-launch.sh`, `exec env
   "$@"`), e foi marcar com o jogo aberto que produziu o "Jogador 3" fantasma.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.actions.profiles_actions import (
    texto_da_marca_do_steam_input,
)

APPID = 1599660

#: O que a caixinha dizia até 08/08 e não pode voltar a dizer: a troca do dono
#: do jogador 2. Cada trecho é uma frase que ERA verdadeira e hoje é mentira.
_AVISOS_QUE_MORRERAM = (
    "quem passa a dar o jogador 2",
    "steam input, não o hefesto",
    "o co-op volta a ser do hefesto",
)


# --- o aviso da perda morreu com a perda -------------------------------------


@pytest.mark.parametrize("controles", [None, 0, 1, 2, 3, 4])
def test_a_caixinha_nao_avisa_mais_de_um_preco_que_nao_e_cobrado(
    controles: int | None,
) -> None:
    """A MORDIDA: devolva `suspend_vpads_for_steam_input` à borda de entrada da
    marca e este teste continua verde — e passa a estar MENTINDO, que é o
    ponto. Ele não é o guarda do daemon (esse é
    `test_esconder_em_vez_de_sair_01.py`); é o guarda da TELA, e o que ele
    trava é que ninguém traga o texto do preço de volta sem trazer o preço.
    """
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
    """O que substituiu o aviso: a boa notícia, com o número que ela tem na mesa.

    ARRANQUE o ramo `jogadores` de `texto_da_marca_do_steam_input` e o texto
    volta a ser mudo sobre a mesa dela — verdadeiro, mas incompleto exatamente
    onde a sprint anterior mediu que a incompletude custa caro.
    """
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
    """A fronteira do que é MEDIDO não se moveu: dizer o que o PRODUTO faz, e
    nunca garantir o que o JOGO vai listar.

    O produto sustenta "os dois vpads ficam de pé" — isso tem teste. Quantos
    jogadores o jogo mostra depende do jogo, e a prova é dela, no aparelho.
    """
    texto = texto_da_marca_do_steam_input("adicionado", APPID, 2)

    assert "confira" in texto.lower(), (
        "o texto não manda conferir. Como ninguém mediu o que o JOGO lista, "
        "conferir é a única instrução honesta."
    )
    for promessa in ("garantido", "vai listar dois", "os dois vão funcionar"):
        assert promessa not in texto.lower(), (
            f"o texto promete {promessa!r} — isso é SEM PROVA e não pode ser dito."
        )


# --- e cala quando não há o que dizer ----------------------------------------


@pytest.mark.parametrize("controles", [None, 0, 1])
def test_com_um_controle_ou_sem_saber_o_texto_nao_fala_de_jogadores(
    controles: int | None,
) -> None:
    """Com um controle não há jogador 2 — nem para perder, nem para prometer.

    E `None` (não deu para ler a contagem) cai no mesmo lugar de propósito:
    falhar para o lado de dizer menos nunca inventa; falhar para o lado de falar
    sempre encheria a tela de frase irrelevante.
    """
    texto = texto_da_marca_do_steam_input("adicionado", APPID, controles)

    assert "um jogador cada" not in texto, (
        f"com controles={controles!r} a frase da mesa apareceu sem mesa."
    )
    # o essencial da frase continua lá
    assert "controle dobrado" in texto
    assert "gatilhos" in texto and "continuam valendo" in texto


def test_tirar_a_marca_diz_o_que_volta_a_acontecer() -> None:
    """NOTA DATADA — 09/08/2026: aqui se exigia *"o co-op volta a ser do
    Hefesto"*. Não volta: ele nunca saiu. O que desmarcar devolve agora é o
    contrário — o jogo volta a enxergar TAMBÉM o controle físico, que é o
    controle dobrado de volta, e é isso que a tela tem de dizer.
    """
    texto = texto_da_marca_do_steam_input("removido", APPID, 2)

    assert "físico" in texto, (
        "desmarcar deixou de dizer o que muda. Se marcar diz que esconde o "
        "físico, desmarcar tem de dizer que ele volta a aparecer."
    )
    assert "co-op" not in texto.lower(), (
        "o co-op voltou ao texto — com a inversão ele não sai em momento nenhum, "
        "e citá-lo aqui sugere que sai."
    )


# --- o que a cura não pode quebrar -------------------------------------------


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
    """A metade da SAÍDA, que a medição dela de 06/08 fixou, não pode sumir.

    O contrapeso desta sprint e da anterior: mexer no texto não pode custar a
    frase que a `CONTROLE-SONY-MEDIDO-01` conquistou — dentro da marca o Hefesto
    mantém cor, gatilhos e vibração. É a metade que ela usa.
    """
    for controles in (None, 1, 2):
        texto = texto_da_marca_do_steam_input("adicionado", APPID, controles)
        assert "cor" in texto and "gatilhos" in texto and "vibração" in texto, (
            "sumiu a metade medida da INVERSÃO: dentro da marca o Hefesto mantém "
            "a saída. Sem essa frase o texto volta a sugerir que ela perde tudo."
        )


@pytest.mark.parametrize("status", ["adicionado", "removido"])
def test_toda_marcacao_manda_fechar_e_abrir_o_jogo(status: str) -> None:
    """A metade que o daemon NÃO entrega ao vivo, dita na tela.

    O `SDL_GAMECONTROLLER_IGNORE_DEVICES` do `steam_app_<appid>.env` é lido UMA
    vez, na abertura. Marcar com o jogo aberto muda o daemon e não muda o que
    aquele processo já enumerou — foi assim que nasceu o "Jogador 3" fantasma
    de 08/08.
    """
    texto = texto_da_marca_do_steam_input(status, APPID, 2)
    assert "Feche e abra o jogo" in texto, (
        "sumiu a única instrução que faz a marca valer inteira. Sem ela, ela "
        "marca, não vê diferença nenhuma e conclui que a caixinha não funciona."
    )
