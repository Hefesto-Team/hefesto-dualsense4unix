#!/usr/bin/env python3
"""Os dois alvos que faltavam ao pintor, lidos do lado Python da régua.

O DEFEITO, medido em 02/09/2026: o ``escrever()`` do BOOTSTRAP conhecia CINCO
alvos — ``texto``, ``largura``, ``fundo``, ``valor`` e ``html``. Nem ``classe``
nem ``cor``. Isso travava cinco coisas que a página JÁ DESENHA:

===================  ==================================================
05-vibracao          qual dos quatro degraus está aceso é a classe ``on``
05-vibracao          o rótulo ``Máx``, que só existe no teto
04-iluminacao        qual botão de jogador acende
02-controles         o clique do analógico, que na GTK é COR e não texto
10-perfis            a coluna "Ajuste próprio" (``.gr.on`` contra ``.gr``)
==================================================================

O ALVO NÃO BASTA: se o pintor ganha um alvo e o LEITOR da régua não, a régua
passa a comparar coisa errada e diz PRODUTO sobre campo que ninguém tocou. Este
arquivo cobre o lado Python das duas leituras; o lado JS — e o casamento dos
dois — está em ``test_o_pintor_acende_a_classe_e_apaga_as_irmas.py``, que abre
um WebKit de verdade.

A MORDIDA: faça ``_campo()`` cair no ramo do texto para ``alvo == "classe"`` e
``test_a_classe_cravada_e_lida_do_arquivo`` reprova — a régua leria o RÓTULO do
botão ("Máximo") onde tinha de ler o estado ("max").
"""
from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.interface import regua_do_mockup as regua

#: OS QUATRO DEGRAUS DA VIBRAÇÃO, na forma em que a página os desenha: um
#: endereço só, quatro elementos, e a classe ``on`` dizendo qual está aceso.
DEGRAUS = (
    '<div data-controle="p1"><div class="seg">'
    '<button data-campo="degrau" data-hef-alvo="classe" '
    'data-hef-quando="economia">Economia</button>'
    '<button data-campo="degrau" data-hef-alvo="classe" '
    'data-hef-quando="balanceado">Balanceado</button>'
    '<button class="on" data-campo="degrau" data-hef-alvo="classe" '
    'data-hef-quando="max">Máximo</button>'
    '<button data-campo="degrau" data-hef-alvo="classe" '
    'data-hef-quando="auto">Auto</button>'
    "</div></div>"
)


# -- o que o ARQUIVO crava -----------------------------------------------
def test_a_classe_cravada_e_lida_do_arquivo():
    """O valor de um campo ``classe`` é o ESTADO, não o rótulo do botão."""
    campos = regua._campos_cravados(DEGRAUS)
    assert [c.valor for c in campos] == ["", "", "max", ""], (
        "o cravado de um alvo `classe` é o `data-hef-quando` de quem tem a "
        "classe, e vazio nos outros. Ler o texto daria "
        "['Economia','Balanceado','Máximo','Auto'] — o rótulo, não o estado.")
    assert [c.quando for c in campos] == ["economia", "balanceado", "max", "auto"]
    assert {c.dono for c in campos} == {"p1"}


def test_a_classe_booleana_nao_precisa_de_quando():
    """A coluna "Ajuste próprio" da Perfis: aceso é ``.gr.on``, apagado é ``.gr``."""
    campos = regua._campos_cravados(
        '<td class="gr on" data-campo="ajuste" data-hef-alvo="classe">✓</td>'
        '<td class="gr" data-campo="ajuste2" data-hef-alvo="classe">✓</td>')
    assert [c.valor for c in campos] == ["sim", ""]


def test_a_classe_nomeada_e_respeitada():
    """``data-hef-classe`` escolhe a classe; ``on`` é só o padrão."""
    campos = regua._campos_cravados(
        '<b data-campo="x" data-hef-alvo="classe" data-hef-classe="off" '
        'class="selo off">ativo</b>')
    assert [c.valor for c in campos] == ["sim"]


def test_a_cor_cravada_e_lida_do_estilo_e_nao_do_texto():
    """O clique do analógico é COR — e o texto ``L3`` continua sendo ``L3``.

    Se este teste passar a ver ``'L3'``, a régua voltou a ler o campo pelo
    texto e um campo de cor vira INDECIDÍVEL para sempre: pintar uma cor não
    mexe numa letra.
    """
    campos = regua._campos_cravados(
        '<span class="rotl" data-campo="l3" data-hef-alvo="cor" '
        'style="color:#6272a4">L3</span>'
        '<span class="rotl" data-campo="r3" data-hef-alvo="cor">R3</span>')
    assert [c.valor for c in campos] == ["rgb(98, 114, 164)", ""]


# -- a normalização de cor, sondada no WebKit desta máquina ---------------
def test_a_cor_normaliza_como_o_webkit_sondado():
    """A tabela é a SAÍDA LITERAL da sonda de 02/09/2026, não uma suposição.

    Se o WebKit de amanhã normalizar diferente, a guarda do DOM virgem do
    ``--prova-de-mockup`` acusa como cegueira e REPROVA — o erro possível aqui
    é barulhento, não mudo.
    """
    sondado = {
        "#6272a4": "rgb(98, 114, 164)",
        "#FF5555": "rgb(255, 85, 85)",
        "#7EB8D4": "rgb(126, 184, 212)",
        "#fff": "rgb(255, 255, 255)",
        "var(--plastico)": "var(--plastico)",
        "rgb(186, 218, 85)": "rgb(186, 218, 85)",
        "red": "red",
        "rgba(0,0,0,.5)": "rgba(0, 0, 0, 0.5)",
        "": "",
        "rgb(37.355% 50.439% 0%)": "rgb(95, 129, 0)",
        "rgb(1 2 3)": "rgb(1, 2, 3)",
        "#6272A4": "rgb(98, 114, 164)",
        " #6272a4 ": "rgb(98, 114, 164)",
        "transparent": "transparent",
        "currentColor": "currentcolor",
        "rgb(1,2,3)": "rgb(1, 2, 3)",
        "#ff5555aa": "rgba(255, 85, 85, 0.667)",
    }
    for escrito, esperado in sondado.items():
        assert regua._cor_css(escrito) == esperado, (
            f"{escrito!r} tinha de virar {esperado!r} — é o que o WebKit "
            f"devolveu em `el.style.color` na sonda de 02/09/2026")


# -- a declaração de um GRUPO ---------------------------------------------
def test_uma_declaracao_de_grupo_apaga_as_irmas_sem_virar_endereco_morto():
    """O pacote declara ``'max'`` UMA vez, e os quatro elementos são visitados.

    Sem a localização, os três não-``max`` teriam ``declarado='max'`` e
    ``vivo=''`` — e a régua acusaria TRÊS endereços mortos toda vez que o
    produto acertasse. Este é o teste que impede a régua de reprovar a cura.
    """
    cravados = regua._campos_cravados(DEGRAUS)
    vereditos = regua._classificar(
        cravados, [c.valor for c in cravados],
        {("p1", "degrau"): "max"}, [True] * 4)
    assert [v.classe for v in vereditos] == [regua.PRODUTO] * 4, (
        "com o selo da visita, os quatro são do produto: o piloto esteve nos "
        "quatro e acendeu o que devia")
    for v in vereditos:
        assert "ENDEREÇO MORTO" not in v.nota


def test_o_grupo_sem_selo_continua_indecidivel_e_nao_vira_morto():
    cravados = regua._campos_cravados(DEGRAUS)
    vereditos = regua._classificar(
        cravados, [c.valor for c in cravados], {("p1", "degrau"): "max"})
    assert [v.classe for v in vereditos] == [regua.INDECIDIVEL] * 4


def test_o_grupo_que_o_produto_declara_errado_continua_acusado():
    """A cura não pode cegar a régua: se o pacote acende o degrau ERRADO, acusa."""
    cravados = regua._campos_cravados(DEGRAUS)
    vereditos = regua._classificar(
        cravados, [c.valor for c in cravados],
        {("p1", "degrau"): "economia"}, [True] * 4)
    classes = [v.classe for v in vereditos]
    assert classes[0] == regua.MOCKUP and "ENDEREÇO MORTO" in vereditos[0].nota, (
        "o pacote manda acender `economia` e a tela continua com `max` aceso — "
        "o botão do `economia` é endereço morto, e a régua tem de dizer")
    assert classes[2] == regua.MOCKUP and "ENDEREÇO MORTO" in vereditos[2].nota


def test_o_booleano_atravessa_o_true_do_python():
    """``str(True)`` é ``'True'`` e o JS escreveria ``'true'`` — os dois acendem."""
    cravados = regua._campos_cravados(
        '<td class="gr on" data-campo="ajuste" data-hef-alvo="classe">✓</td>')
    for declarado in (True, "true", "sim", 1):
        (v,) = regua._classificar(cravados, ["sim"], {("", "ajuste"): declarado},
                                  [True])
        assert v.classe == regua.PRODUTO, f"{declarado!r} tinha de acender"
    for declarado in (False, "false", "não", 0, None, ""):
        (v,) = regua._classificar(cravados, ["sim"], {("", "ajuste"): declarado},
                                  [True])
        assert v.classe == regua.MOCKUP, f"{declarado!r} tinha de apagar"
        assert "ENDEREÇO MORTO" in v.nota
