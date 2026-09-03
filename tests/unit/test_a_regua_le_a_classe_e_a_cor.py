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

O ALVO TAMBÉM NÃO BASTA DOS DOIS LADOS: entre o que o PACOTE emite e o que a
tela mostra há uma tradução, e comparar os dois crus acusa endereço morto sobre
o produto que acertou. Foi o que aconteceu com os dois alvos novos, e os dois
achados são de 02/09/2026:

* a **cor** declarada não passava pelo ``_cor_css``. O pacote emite
  ``'#0000FF'`` (é o que ``a04_iluminacao._hex`` devolve), a tela mostra
  ``'rgb(0, 0, 255)'``, e a régua chamava de ENDEREÇO MORTO. Só ``var(--x)``
  escapava — a única forma que os testes usavam.
* a **classe** era CEGA ao token errado: um ``'maximo'`` (noqa-acento, é
  token de máquina) no lugar de ``'max'`` apaga os quatro degraus, e a régua
  dava os MESMOS quatro PRODUTO da tela que acende certo — o detector de
  endereço morto estava desarmado.

A MORDIDA, e são quatro:

1. faça ``_campo()`` cair no ramo do texto para ``alvo == "classe"`` e
   ``test_a_classe_cravada_e_lida_do_arquivo`` reprova — a régua leria o RÓTULO
   do botão ("Máximo") onde tinha de ler o estado ("max");
2. faça ``_declarado_neste_elemento`` devolver ``declarado`` cru no alvo ``cor``
   e ``test_a_cor_declarada_pelo_pacote_passa_pela_mesma_normalizacao`` reprova
   no ``#6272a4``;
3. tire o ramo do token desconhecido e
   ``test_o_token_que_nenhum_degrau_conhece_e_endereco_morto`` reprova com
   quatro PRODUTO sobre uma tela apagada;
4. faça o token desconhecido acusar SEM olhar o ``ligado()`` e
   ``test_apagar_o_grupo_inteiro_continua_sendo_legitimo`` reprova — o travessão
   do lugar vazio apaga o grupo DE PROPÓSITO.

A sonda de cor contra o WebKit de verdade mora no arquivo vizinho,
``test_o_pintor_acende_a_classe_e_apaga_as_irmas.py``: aqui não há tabela de
respostas digitada à mão, e a razão está escrita lá.
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


# -- a cor DECLARADA atravessa a mesma normalização -----------------------
def test_a_cor_declarada_pelo_pacote_passa_pela_mesma_normalizacao():
    """O terceiro lado do casamento, e era o que faltava.

    OS TRÊS LADOS têm de falar a mesma língua, e só DOIS falavam::

        o ARQUIVO   `_Leitor._campo`  -> `_cor_css(_do_estilo(...))`  normalizado
        a TELA      `LER_CAMPOS`      -> `el.style.color`   normalizado pelo CSSOM
        o PACOTE    `_classificar`    -> `_como_a_tela_escreveria()`  CRU

    E NÃO É HIPÓTESE: `a04_iluminacao._hex([0,0,255])` devolve `'#0000FF'` —
    hexadecimal —, e as duas páginas de Iluminação cravam a cor em hexadecimal
    também. O pacote acerta a cor, a tela mostra a cor certa, e a régua dizia
    ENDEREÇO MORTO. Só a forma `var(--x)` escapava, que é justamente a única que
    os testes usavam.

    A MORDIDA: faça `_declarado_neste_elemento` devolver `declarado` para o
    alvo `cor` e este teste reprova no `#6272a4`.
    """
    cravados = regua._campos_cravados(
        '<span data-campo="l3" data-hef-alvo="cor" style="color:#6272a4">L3</span>')
    for declarado in ("#6272a4", "#6272A4", "rgb(98, 114, 164)",
                      "rgb(98,114,164)"):
        (v,) = regua._classificar(cravados, ["rgb(98, 114, 164)"],
                                  {("", "l3"): declarado}, [True])
        assert v.classe == regua.PRODUTO, (
            f"o pacote declarou {declarado!r}, a tela mostra "
            f"'rgb(98, 114, 164)' e a régua disse {v.classe}: {v.nota}")


def test_a_cor_que_o_pacote_erra_continua_acusada():
    """A cura não pode cegar a régua: cor DIFERENTE continua endereço morto."""
    cravados = regua._campos_cravados(
        '<span data-campo="l3" data-hef-alvo="cor" style="color:#6272a4">L3</span>')
    (v,) = regua._classificar(cravados, ["rgb(98, 114, 164)"],
                              {("", "l3"): "#FF5555"}, [True])
    assert v.classe == regua.MOCKUP and "ENDEREÇO MORTO" in v.nota


def test_a_cor_vazia_declarada_e_a_cor_apagada_na_tela():
    """`None` num campo de cor APAGA a cor de linha — não escreve travessão.

    O `escrever()` do piloto faz `el.style.color = ''` no vazio, e `''` é o que
    o leitor devolve. Traduzir o vazio para `'—'`, como o texto faz, acusaria
    endereço morto sobre o analógico que acabou de ser solto.
    """
    cravados = regua._campos_cravados(
        '<span data-campo="l3" data-hef-alvo="cor">L3</span>')
    for declarado in (None, ""):
        (v,) = regua._classificar(cravados, [""], {("", "l3"): declarado}, [True])
        assert v.classe == regua.PRODUTO, f"{declarado!r}: {v.nota}"


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


def test_o_token_que_nenhum_degrau_conhece_e_endereco_morto():
    """O DETECTOR DE ENDEREÇO MORTO ESTAVA DESARMADO neste alvo.

    Medido em 02/09/2026: com o pacote emitindo ``'maximo'`` (noqa-acento, é
    valor de máquina) — um token que NENHUM dos quatro degraus conhece —, a
    tela fica INTEIRAMENTE APAGADA, e a régua dava os MESMOS ``4 PRODUTO`` da
    tela que acende certo. A causa: a
    localização do grupo colapsava toda declaração que não casa para ``''``, e
    ``''`` é exatamente o que um degrau apagado mostra.

    O defeito que o enunciado desta cura manda impedir — *"o segundo clique
    deixa dois degraus acesos"* — tem um irmão que ninguém via: **nenhum aceso**.

    A MORDIDA: tire o ramo do token desconhecido de
    ``_declarado_neste_elemento`` e este teste reprova com quatro PRODUTO.
    """
    cravados = regua._campos_cravados(DEGRAUS)
    apagada = ["", "", "", ""]
    vereditos = regua._classificar(cravados, apagada,
                                   {("p1", "degrau"): "maximo"}, [True] * 4)  # noqa-acento: valor
    conta = regua._contar(vereditos)
    assert conta[regua.MOCKUP] == 3, (
        "os três degraus que a tela mostra apagados E o arquivo cravou apagados "
        f"têm de acusar o token que ninguém conhece: {conta}")
    mortos = [v for v in vereditos if "ENDEREÇO MORTO" in v.nota]
    assert len(mortos) == 3 and "'maximo'" in mortos[0].nota, (  # (noqa-acento): valor citado
        "a nota tem de NOMEAR o token que o pacote emitiu — senão quem lê o "
        "relato não sabe o que procurar no código")

    # e o token CERTO continua dando os quatro do produto: a régua nova não
    # pode acusar quem acerta.
    acesa = ["", "", "max", ""]
    certos = regua._classificar(cravados, acesa, {("p1", "degrau"): "max"},
                                [True] * 4)
    assert [v.classe for v in certos] == [regua.PRODUTO] * 4


def test_apagar_o_grupo_inteiro_continua_sendo_legitimo():
    """Um lugar VAZIO da mesa apaga os quatro degraus, e isso não é defeito.

    O molde do lugar sem dono escreve travessão, e o ``ligado()`` dos dois lados
    trata o travessão como DESLIGADO. Se esta régua nova acusasse aqui, ela
    reprovaria a cura do estado vazio — o defeito que esta casa já nomeou onze
    vezes num dia.
    """
    cravados = regua._campos_cravados(DEGRAUS)
    for declarado in ("—", "", None, False):
        vereditos = regua._classificar(cravados, ["", "", "", ""],
                                       {("p1", "degrau"): declarado}, [True] * 4)
        classes = [v.classe for v in vereditos]
        assert classes[:2] == [regua.PRODUTO] * 2, (
            f"{declarado!r} apaga o grupo DE PROPÓSITO: {classes}")
        assert not any("ENDEREÇO MORTO" in v.nota for v in vereditos[:2])


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
