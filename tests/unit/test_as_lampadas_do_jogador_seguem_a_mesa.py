"""As cinco lâmpadas do LED do jogador seguem o assento vivo, não o mockup.

QUEIXA DELA, 14/09/2026, com os dois controles na mesa:

    *"a interface tá dessincronizada com os controles reais. (o player do   # noqa-acento: citação literal dela
     controle , o led indicativo do player)"*

O QUE ESTAVA QUEBRADO: o `<div class="lampadas">` da aba Controles não tinha
`data-campo`. Sem endereço, o `achar()` do piloto passa ao largo dele — o HTML
que o gerador escreveu UMA VEZ, com o jogador da CENA do mockup, ficava na tela
até a janela ser fechada. Um controle que trocasse de assento mostrava o padrão
de outro jogador, calado.

E O ASSENTO TROCA POR DESENHO, que é o que torna isto um defeito e não um
detalhe: a ordem é a da CHEGADA (`daemon/subsystems/identity`, decisão dela — o
controle branco não pode ser sempre o player 3), então o número de um mesmo
aparelho muda entre uma sessão e outra, e muda no replug.

A CURA NÃO INVENTOU DESENHO: quem monta as cinco lâmpadas é `monta.luzinhas`, a
MESMA função com que o gerador escreveu o HTML, e ela deriva o padrão de
`core.led_control.player_led_pattern` — o caminho por onde o produto acende as
luzes de verdade. O pacote a chama com o jogador da mesa.

A RESSALVA CONTINUA DE PÉ, e esta régua não a fecha: o que a tela desenha é o
padrão DERIVADO do assento, não uma leitura do aparelho. O `state_full` publica
`player_slot` e **não** `player_leds`; um perfil que escreva as cinco luzes na
mão pode divergir do desenhado, e a tela não tem como saber. Está dito na dica da
moldura (`aba02.DICA_LED_JOGADOR`) desde que ela nasceu.
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PAGINA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/02-controles.html"

UNIQ = "aa:bb:cc:00:00:02"


def _ctx(jogador: int) -> pacotes.Contexto:
    controle = {"uniq": UNIQ, "connected": True, "player": jogador,
                "transport": "usb"}
    item = {"uniq": UNIQ, "pref": "p1", "jogador": jogador, "nome": "Prova",
            "cor": "", "transporte": "usb", "via": "cabo", "alvo": True,
            "mascara": "dualsense"}
    state: dict[str, Any] = {"controllers": [controle]}
    return pacotes.Contexto(state=state, mesa=[item], conectados=[controle],
                            estados={}, externos=[])


def _lampadas(jogador: int) -> str:
    cards = a02.pacote(_ctx(jogador))["cards"]
    assert len(cards) == 1
    return str(next(iter(cards.values())).get("lampadas") or "")


def test_o_desenho_tem_o_endereco_das_lampadas() -> None:
    """MORDIDA: sem `data-campo`, o piloto nunca visita as cinco lâmpadas.

    E ela cobra os QUATRO, um por coluna: um endereço que só o card aberto
    tivesse deixaria os três fechados com o desenho do mockup — e é justamente ao
    trocar de card que o assento muda de cara.
    """
    html = PAGINA.read_text(encoding="utf-8")
    divs = re.findall(r'<div class="lampadas"[^>]*>', html)
    assert divs, "a aba não tem mais o campo das cinco lâmpadas"
    for div in divs:
        assert 'data-campo="lampadas"' in div, (
            f"lâmpadas sem endereço: {div} — o piloto não as repinta, e a tela "
            f"volta a mostrar o jogador da cena do mockup"
        )
        assert 'data-hef-alvo="html"' in div, (
            f"lâmpadas sem alvo `html`: {div}. O que muda entre um jogador e "
            f"outro é o DESENHO inteiro das cinco, não uma classe"
        )


@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_cada_assento_tem_o_seu_desenho(jogador: int) -> None:
    """As quatro respostas são diferentes entre si — senão a pintura não diz nada."""
    saida = _lampadas(jogador)
    assert saida, f"o pacote não emitiu as lâmpadas do P{jogador}"
    assert saida.count("<i") == 5, (
        f"o desenho do P{jogador} tem {saida.count('<i')} lâmpadas, e o DualSense "
        f"tem cinco"
    )


def test_os_quatro_desenhos_nao_se_repetem() -> None:
    desenhos = {j: _lampadas(j) for j in (1, 2, 3, 4)}
    assert len(set(desenhos.values())) == 4, (
        f"dois assentos desenham as mesmas lâmpadas: "
        f"{ {j: d.count('class=\"on\"') for j, d in desenhos.items()} }"
    )


def test_o_p1_acende_a_do_meio() -> None:
    """O padrão canônico do PS5, e é o que a dica da moldura promete por escrito."""
    acesas = [i for i, tag in enumerate(re.findall(r"<i[^>]*>", _lampadas(1)))
              if "on" in tag]
    assert acesas == [2], (
        f"o P1 devia acender só a lâmpada do meio (índice 2); acendeu {acesas}"
    )


def test_o_desenho_vem_do_dono_e_nao_de_uma_tabela_daqui() -> None:
    """A régua contra a terceira cópia do padrão do PS5.

    `monta.luzinhas` é quem o gerador usa; se o pacote passar a montar o HTML por
    conta própria, os dois divergem no dia em que alguém mexer num deles — e a
    tela desenha um padrão que o produto não acende.
    """
    import sys

    sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))
    from hefesto_dualsense4unix.interface.monta import luzinhas

    for jogador in (1, 2, 3, 4):
        assert _lampadas(jogador) == luzinhas(jogador), (
            f"o pacote desenhou o P{jogador} diferente do `monta.luzinhas` — há "
            f"uma segunda receita das cinco lâmpadas na casa"
        )
