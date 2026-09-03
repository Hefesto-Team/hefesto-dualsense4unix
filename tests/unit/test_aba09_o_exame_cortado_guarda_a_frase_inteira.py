#!/usr/bin/env python3
"""O EXAME DA ABA SISTEMA CORTA A FRASE — e agora guarda o inteiro. 03/09/2026.

MEDIDO NO PRODUTO INSTALADO, na mesa dela, com um DualSense White no cabo. A
foto do `hefesto_vivo --oculta --abre 09-sistema.html` mostrou CINCO das SEIS
linhas do exame cortadas em reticências, e sem `title` não havia como ler o
resto — nem passando o rato, nem rolando, nem alargando a janela:

    o texto que o `doctor` devolveu                            o que a tela mostrava
    ─────────────────────────────────────────────────────────  ────────────────────────
    cura do travamento do USB ATIVA (mic e fone … preservados)  …(mic e fone do co…
    áudio presente no único controle no cabo (mic+fone …)       …no cabo (mic+fon…
    quirk anti-storm ativo (054c:0ce6 — áudio USB espaçado)     …áudio USB esp…
    Steam Input desligado para o DualSense                      inteira (38 car)
    WirePlumber configurado (51-hefesto-dualsense-no-…​.conf)    …(51-hefesto-dualsense-n…
    regra áudio-off inativa — … estão liberados. O que fazer:   …o mic e o fone do controle…
      nada.

O CORTE É DO DESENHO E FICA: `paginas/09-sistema.html:825` diz
`overflow:hidden;text-overflow:ellipsis;white-space:nowrap`, e a `.saude` tem
25,5px de altura fixa. Quebrar a linha em duas mudaria a altura do quadro —
desenho, e desenho é decisão dela. O que NÃO é decisão dela é a frase ficar
inalcançável.

A ÚLTIMA LINHA É A QUE OBRIGOU A CURA, e ela não perde informação: INVERTE. O
que sobra na tela, ao lado de um selo `NOTA`, é *"regra áudio-off inativa — o
mic e o fone do controle…"*, que se lê como problema com o microfone dela. As
duas metades escondidas são **"estão liberados"** e **"O que fazer: nada"** — a
resposta inteira.

POR QUE NENHUM PORTÃO PEGOU, e o padrão tem nome nesta casa — *a régua confunde
a PALAVRA com o ATO*: `test_a_saude_do_sistema_diz_o_que_fazer` exige o literal
`"O que fazer:"` DENTRO da string, e a string sempre o teve. Ele ficou verde
sobre uma tela que cortava a frase antes justamente dessa metade. Esta régua é a
outra metade dele: a frase que o portão exige tem de estar ALCANÇÁVEL.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

# OS GLIFOS VÊM DO PRODUTO, e não digitados: `aba_sistema.py:133` é o dono, e um
# símbolo teclado aqui seria a segunda cópia — a que diverge no dia em que ela
# trocar o glifo. O `ruff` também reprova o da NOTA cru, por ambiguidade.
from hefesto_dualsense4unix.gui.aba_sistema import GLIFO_INFO, GLIFO_OK

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: A página que o PRODUTO renderiza — não a bancada.
PAGINA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/09-sistema.html"

#: A frase que motivou a cura, com as duas metades que a tela escondia. Ela é o
#: texto REAL do `storm_doctor` desta máquina, copiado da saída dele — não uma
#: invenção de teste.
A_QUE_INVERTE = ("regra áudio-off inativa — o mic e o fone do controle estão "
                 "liberados. O que fazer: nada.")

#: As seis do exame de 03/09, com os comprimentos medidos. Só a quarta cabe.
SEIS = (
    "cura do travamento do USB ATIVA (mic e fone do controle preservados)",
    "áudio presente no único controle no cabo (mic+fone do DualSense ativos)",
    "quirk anti-storm ativo (054c:0ce6 — áudio USB espaçado)",
    "Steam Input desligado para o DualSense",
    "WirePlumber configurado (51-hefesto-dualsense-no-default-source.conf)",
    A_QUE_INVERTE,
)


@pytest.fixture
def a09():
    from pacotes import a09_sistema as mod

    return mod


def test_o_corte_do_desenho_continua_existindo() -> None:
    """A régua mede uma tela que CORTA. Se o corte sumir, ela para de fazer sentido.

    Sem esta guarda, uma mudança de desenho que passasse a quebrar a linha
    deixaria as asserções abaixo verdes por um motivo que não é mais o motivo —
    e a próxima pessoa leria "cobrimos o corte" sobre uma tela que não corta.
    """
    css = PAGINA.read_text(encoding="utf-8")
    regra = re.search(r"\.saude \.txt span:last-child\{([^}]*)\}", css)

    assert regra, (
        "a regra que corta a linha do exame sumiu de `09-sistema.html`. Se o "
        "desenho passou a quebrar a frase em duas linhas, esta régua inteira "
        "caducou — leia o docstring antes de apagá-la."
    )
    assert "text-overflow:ellipsis" in regra.group(1)
    assert "white-space:nowrap" in regra.group(1)


@pytest.mark.parametrize("texto", SEIS)
def test_toda_linha_do_exame_leva_a_frase_inteira_no_title(a09, texto: str) -> None:
    """A MORDIDA: tire o `title=` de `_linha_do_exame`. Executada:

        AssertionError: a linha do exame corta na tela e não guarda a frase
        inteira em lugar nenhum — 'regra áudio-off inativa …' é o que a tela
        mostra, e as metades escondidas são a resposta.

    Cobre as SEIS, e não só as cortadas: qual delas corta depende da largura da
    janela e do tamanho da fonte dela. Uma régua que só cobrisse as cinco de
    hoje ficaria verde no dia em que a sexta crescesse um caractere.
    """
    achado = {"selo": "OK", "cls": "ok", "g": GLIFO_OK, "txt": texto}

    html_da_linha = a09._linha_do_exame(achado)

    assert f'title="{_escapado(texto)}"' in html_da_linha, (
        "a linha do exame corta na tela e não guarda a frase inteira em lugar "
        f"nenhum — {texto!r} é o que o doctor devolveu, e a tela mostra só o "
        f"começo.\n\nSaiu: {html_da_linha!r}"
    )


def test_a_metade_que_a_tela_esconde_e_a_resposta(a09) -> None:
    """O caso que decidiu a cura: o corte não perde informação, INVERTE o sentido.

    A MORDIDA é a mesma — sem o `title`, o único texto que existe no HTML é o
    do `<span>`, que a folha corta em ~51 caracteres. Executada com o `title`
    arrancado:

        AssertionError: 'estão liberados' e 'O que fazer: nada' não estão
        alcançáveis: a tela para em 'o mic e o fone do controle…'
    """
    saiu = a09._linha_do_exame(
        {"selo": "NOTA", "cls": "nt", "g": GLIFO_INFO, "txt": A_QUE_INVERTE})

    # As duas metades que a foto mostrou escondidas. Não basta o texto estar no
    # `<span>` — é justamente ele que a folha corta.
    dentro_do_title = saiu.split('title="', 1)[-1].split('"', 1)[0]
    for metade in ("estão liberados", "O que fazer: nada"):
        assert _escapado(metade) in dentro_do_title, (
            f"{metade!r} não está alcançável: a tela para em 'o mic e o fone "
            "do controle…' e quem lê conclui o contrário do que o exame diz."
        )


def test_o_title_e_escapado_como_o_resto(a09) -> None:
    """A frase vem do `doctor`, não daqui — e ela entra num ATRIBUTO agora.

    O texto do exame já carrega parênteses, travessões e nomes de arquivo; um
    dia carregará aspas. Sem escapar, a primeira aspa fecharia o atributo e o
    resto da frase viraria marcação dentro do `innerHTML` que o piloto escreve.

    A MORDIDA: troque `html.escape(txt, quote=True)` por `txt`. Executada:

        AssertionError: a aspa saiu crua no atributo e quebrou a marcação
    """
    saiu = a09._linha_do_exame(
        {"selo": "NOTA", "cls": "nt", "g": GLIFO_INFO,
         "txt": 'o perfil "meu_perfil" & o <script> do jogo'})

    assert '"meu_perfil"' not in saiu, "a aspa saiu crua no atributo e quebrou a marcação"
    assert "&quot;meu_perfil&quot;" in saiu
    assert "&lt;script&gt;" in saiu
    assert "&amp;" in saiu


def _escapado(texto: str) -> str:
    import html as _h

    return _h.escape(texto, quote=True)
