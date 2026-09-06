"""A tela não diz "rádio" sobre um transporte que o daemon não publicou.

Medido em 05/09/2026: `interface/mesa_viva.mesa_do_estado` montava a palavra
curta do transporte com

    "via": "USB" if transporte == "usb" else "BT"

— e o `else` pegava a AUSÊNCIA. Um controle cujo `transport` o daemon não
publicasse aparecia na aba 01 como **"BT"**: a tela afirmando rádio sobre um
campo que ninguém leu.

**O DONO MUDOU DE ENDEREÇO EM 06/09/2026, e a régua foi junto.** Havia dois
dicionários para o mesmo fato: `pacotes.VIA_DO_TRANSPORTE` (a SIGLA de máquina)
e `home_actions._PALAVRA_DO_TRANSPORTE` (a palavra da tela). A decisão dela
(D-05, e o glossário desta casa) é *cabo* e *rádio*, e a sigla sobrou num lugar
só — a contagem do topo, `2 USB · 0 BT`. Hoje o `mesa_viva` lê
`home_actions.palavra_do_transporte`, e esta régua confere contra ELE: o que ela
protege não é a palavra, é o ato de **não afirmar o que ninguém leu**.

**E A AUSÊNCIA CONFESSA, EM VEZ DE CALAR.** Esta régua exigia `""` (o travessão
do piloto) e o dono responde `"não sei por onde"`, com a razão escrita desde o
produto estável: *"'?' não é resposta — é a tela encolhendo os ombros"*. Os dois
comportamentos são honestos; o que a casa não aguenta é os DOIS, que é o defeito
de dois donos que esta régua veio matar em 05/09. Decidido em 06/09 por
delegação (`D-0609-A-AUSENCIA-DO-TRANSPORTE-CONFESSA`): fica a frase do dono, e
o travessão continua sendo o que o piloto escreve onde não há texto nenhum.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.interface import mesa_viva


@pytest.mark.parametrize("ausente", [None, "", "   "])
def test_transporte_ausente_nao_vira_radio(ausente):
    saida = mesa_viva._via_do_transporte(ausente)
    for afirmacao in home_actions._PALAVRA_DO_TRANSPORTE.values():
        assert saida != afirmacao, (
            f"com transport={ausente!r} a tela escreveu {saida!r}. Afirmar um "
            "transporte sobre um campo vazio é a tela inventando o que não leu."
        )


def test_a_ausencia_confessa_com_a_frase_do_dono():
    """Sem leitura, a tela diz que não sabe — e diz com a frase de UM dono."""
    assert (mesa_viva._via_do_transporte(None)
            == home_actions.PALAVRA_DE_TRANSPORTE_DESCONHECIDO)


def test_os_dois_transportes_conhecidos_continuam_certos():
    """As palavras não se digitam aqui: elas vêm do dono, chave por chave."""
    for chave, palavra in home_actions._PALAVRA_DO_TRANSPORTE.items():
        assert mesa_viva._via_do_transporte(chave) == palavra
    assert (mesa_viva._via_do_transporte("BT")
            == home_actions.palavra_do_transporte("bt")), (
        "o daemon pode mandar maiúscula")


def test_ha_um_dono_so_e_o_mesa_viva_o_le():
    """A cópia não pode voltar: a tela toda lê a MESMA função."""
    for chave in (*home_actions._PALAVRA_DO_TRANSPORTE, "", None, "algo-novo"):
        assert (mesa_viva._via_do_transporte(chave)
                == home_actions.palavra_do_transporte(chave)), (
            "o `mesa_viva` deixou de ler `home_actions.palavra_do_transporte` "
            "e voltou a traduzir por conta própria"
        )


def test_um_transporte_novo_aparece_cru_em_vez_de_sumir():
    """Um daemon mais recente tem de conseguir mostrar o que trouxe.

    MORDIDA: faça o dono devolver a frase do "não sei" para o que o mapa não
    conhece e esta régua reprova — um transporte novo ficaria escondido atrás de
    uma frase genérica, e ninguém saberia que ele existe.
    """
    assert mesa_viva._via_do_transporte("dock") == "dock"


def test_a_mesa_montada_nao_afirma_via_sem_leitura():
    """A ponta que ela vê: o dicionário que vai para a aba 01."""
    estado = {"controllers": [{"uniq": "aabbcc000011", "connected": True}]}
    mesa = mesa_viva.mesa_do_estado(estado, {})
    assert mesa, "a mesa veio vazia — esta régua perdeu o objeto"
    for afirmacao in home_actions._PALAVRA_DO_TRANSPORTE.values():
        assert mesa[0]["via"] != afirmacao, (
            f"a mesa afirma via={mesa[0]['via']!r} para um controle cujo "
            "transporte o daemon não publicou"
        )
