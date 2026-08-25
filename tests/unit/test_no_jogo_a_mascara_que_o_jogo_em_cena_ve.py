"""NO-JOGO-SEM-FALSO-VERDE-01/T3 — o alarme que o daemon publicava sem leitor.

**Medido em 23/08:**

    $ grep -rn "mascara_divergente" src/hefesto_dualsense4unix/app/
    (vazio)

O ``gamepad_emulation.mascara_divergente`` existe no ``state_full`` desde a
MASCARA-01 (19/08), e o comentário que o publica diz, com todas as letras, *"e
a GUI decide se mostra"*. A GUI não sabia que ele existia — F2 na forma
clássica desta casa: **a casa sabe e o produto não faz**.

Enquanto isso o cabeçalho desta aba escrevia *"O jogo vê o controle como:
DualSense"* como se ninguém tivesse pedido outra coisa. A frase não era falsa —
o jogo vê mesmo a máscara viva —, era a metade que engana: ela escolheu Xbox
360 para aquele jogo, salvou, o aparelho ficou DualSense, e a aba que existe
para responder *"o que está chegando ao jogo"* dizia que estava tudo em ordem.

**CORREÇÃO DE FATO ao texto da sprint** (25/08/2026): a mordida de T3 propõe um
payload com as chaves ``perfil`` e ``viva``. Não são essas. O dicionário que o
daemon publica é montado em `daemon/launch_env.py` e tem
``{appid, profile, mascara_perfil, mascara_viva, motivo, em_cena}`` — um teste
escrito contra os nomes da sprint passaria a medir uma ficção, e é o defeito
que esta casa chama de "medir contra a régua errada".

**A LISTA fica de fora, e é decisão do daemon, não desta tela:** ele separa
``mascara_divergente`` (o alarme — jogo em cena AGORA) de
``mascara_divergencias`` (a lista inteira) exatamente porque divergência de
jogo FECHADO é antecipação. Escrever antecipação no topo da aba ensinaria a
ignorar o aviso.
"""

from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.app.widgets.painel_no_jogo import (
    mascara_pedida_pelo_jogo_em_cena,
    texto_do_contexto,
)

#: O rótulo de cada máscara vem da aba Início (`ITENS_DE_MASCARA`), e é a razão
#: de esta aba não ter vocabulário próprio de máscara. Repetidos aqui como
#: ESPERADO da tela, nunca como fonte.
_ROTULO_XBOX = "Xbox 360"
_ROTULO_DUALSENSE = "DualSense (botões PlayStation)"


def _divergencia(
    perfil: Any = "xbox", viva: Any = "dualsense", **extra: Any
) -> dict[str, Any]:
    """O dicionário com as chaves REAIS do `launch_env._publicar_divergencias`."""
    item: dict[str, Any] = {
        "appid": 1234,
        "profile": "pragmata",
        "mascara_perfil": perfil,
        "mascara_viva": viva,
        "motivo": "mascara_diferente",
        "em_cena": True,
    }
    item.update(extra)
    return item


def _estado(
    flavor: str = "dualsense", divergente: Any = None, **gamepad_extra: Any
) -> dict[str, Any]:
    gamepad: dict[str, Any] = {"enabled": True, "flavor": flavor}
    gamepad.update(gamepad_extra)
    if divergente is not None:
        gamepad["mascara_divergente"] = divergente
    return {"connected": True, "native_mode": False, "gamepad_emulation": gamepad}


# ---------------------------------------------------------------------------
# A mordida: as DUAS máscaras na mesma linha
# ---------------------------------------------------------------------------


def test_com_divergencia_o_cabecalho_imprime_as_duas_mascaras() -> None:
    """O caso medido de 19/08: perfil `xbox`, bandeira viva `dualsense`.

    Arranque para ver reprovar: tirar a chamada de
    `mascara_pedida_pelo_jogo_em_cena` de `texto_do_contexto`. Volta a imprimir
    só a viva — que é o estado de 23/08, com o alarme publicado e sem leitor.
    """
    texto = texto_do_contexto(_estado(divergente=_divergencia()))

    assert _ROTULO_DUALSENSE in texto
    assert _ROTULO_XBOX in texto


def test_sem_divergencia_a_linha_nao_muda_uma_letra() -> None:
    """A contraprova, e ela é a metade que protege o caminho feliz.

    Uma cura que escrevesse a segunda máscara sempre — com o campo ausente, ou
    com ele `None`, que é o valor que o daemon publica no caso normal — poria
    um alarme permanente no topo da aba. Alarme que está sempre aceso ensina a
    não olhar.
    """
    sem_a_chave = texto_do_contexto(_estado())
    com_a_chave_nula = texto_do_contexto(
        _estado(mascara_divergente=None, mascara_divergencias=[])
    )

    assert sem_a_chave == com_a_chave_nula
    assert _ROTULO_DUALSENSE in sem_a_chave
    assert _ROTULO_XBOX not in sem_a_chave
    assert "pedia" not in sem_a_chave


def test_a_lista_de_divergencias_sozinha_nao_acende_nada() -> None:
    """Jogo FECHADO com perfil divergente é antecipação, não alarme.

    O daemon separa as duas chaves por isso, e esta aba lê só o alarme. Se a
    lista bastasse, a linha ficaria acesa por um jogo que ela não abriu.
    """
    texto = texto_do_contexto(
        _estado(
            mascara_divergente=None,
            mascara_divergencias=[_divergencia(em_cena=False)],
        )
    )

    assert _ROTULO_XBOX not in texto
    assert "pedia" not in texto


# ---------------------------------------------------------------------------
# O que a linha NÃO pode fazer: escrever o que não sabe nomear
# ---------------------------------------------------------------------------


def test_mascara_do_perfil_sem_nome_conhecido_faz_a_tela_calar() -> None:
    """Payload de um Hefesto mais novo (ou mais velho) que esta janela.

    A máscara do perfil vem do DISCO. Um identificador fora da lista-dona da
    aba Início não tem rótulo, e escrever o cru — "o perfil deste jogo pedia
    ps4_v2" — seria pior que calar: é uma palavra que não existe em nenhuma
    outra tela deste produto.
    """
    texto = texto_do_contexto(_estado(divergente=_divergencia(perfil="ps4_v2")))

    assert texto == texto_do_contexto(_estado())
    assert "ps4_v2" not in texto


def test_divergencia_que_nao_e_dicionario_nao_derruba_a_linha() -> None:
    """Blindagem de payload, que nesta casa é rotina e não paranoia.

    O daemon vivo é mais velho que o código com frequência suficiente para que
    a regra tenha nome próprio. Uma linha de cabeçalho que estoura leva a aba
    inteira junto.
    """
    for torto in ("divergente", 1, [], {"sem": "as chaves"}, True):
        texto = texto_do_contexto(_estado(divergente=torto))
        assert _ROTULO_DUALSENSE in texto
        assert "pedia" not in texto


def test_a_mesma_mascara_dos_dois_lados_nao_e_divergencia() -> None:
    """Defesa contra o daemon que publica um alarme que já não é alarme.

    Se o perfil pedia DualSense e o aparelho está DualSense, repetir o rótulo
    duas vezes na mesma linha ("vê como DualSense — o perfil pedia DualSense")
    é ruído que a pessoa tem de decifrar para concluir que não há nada errado.
    """
    texto = texto_do_contexto(
        _estado(divergente=_divergencia(perfil="dualsense"))
    )

    assert texto == texto_do_contexto(_estado())


# ---------------------------------------------------------------------------
# A função pura, sozinha
# ---------------------------------------------------------------------------


def test_a_funcao_devolve_none_quando_nao_ha_o_que_dizer() -> None:
    """Sem daemon, sem bloco, sem alarme: ``None`` nos três."""
    assert mascara_pedida_pelo_jogo_em_cena(None) is None
    assert mascara_pedida_pelo_jogo_em_cena({}) is None
    assert mascara_pedida_pelo_jogo_em_cena(_estado()) is None


def test_a_funcao_le_a_chave_do_daemon_e_nao_outra() -> None:
    """A régua contra a régua errada: as chaves são as do `launch_env`.

    Um teste escrito com `perfil`/`viva` — os nomes que o texto da sprint
    propunha — passaria com a cura arrancada, porque nenhum dos dois lados
    olharia para o campo que o daemon de verdade publica.
    """
    assert (
        mascara_pedida_pelo_jogo_em_cena(_estado(divergente=_divergencia()))
        == _ROTULO_XBOX
    )
    # As chaves da sprint, sozinhas, não dizem nada a ninguém.
    inventado = {"appid": 1234, "em_cena": True, "perfil": "xbox"}
    assert mascara_pedida_pelo_jogo_em_cena(_estado(divergente=inventado)) is None
