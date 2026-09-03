#!/usr/bin/env python3
"""UM `?` QUE ABRE É UMA PROMESSA — e a linha da ORDEM abria vazia.

O ACHADO, de pé desde 02/09/2026: *"o ponto de interrogação de uma linha sem
verbete e sem cura abre uma caixa VAZIA de 330px"*.

A CAUSA, medida: `secao_exame.DICAS_DAS_LINHAS` é indexada por chave de REGRA, e
são CINCO — `energia_do_radio`, `energia_das_portas`, `pareamentos`,
`suporte_ao_controle`, `vizinhanca_das_portas`. Um item vindo do catálogo de
ORDENS (`exame_da_mesa.itens_das_ordens`) traz `chave=ordem.chave`, que é o slug
do arranjo e não é nenhuma das cinco, e `cura=ordem.acao or None`, que pode ser
vazio. Sem verbete e sem cura, `_dica_da_linha` devolvia `""`, o `escrever()` do
piloto punha o travessão, e o `?` abria uma caixa de 330px com um traço dentro.

A decisão 9 dela — *"o `?` para de repetir a linha"* — tirou a metade do meio
(o `Item.porque`, que a linha ao lado passou a mostrar). Quem não tinha as
outras duas ficou sem nenhuma.

A CURA É REUSO, e as frases já existiam há muito: uma `Ordem` traz TRÊS linhas
(`ordens_da_mesa.Ordem.linhas`), com os rótulos de
`exame_da_mesa.ROTULOS_DA_ORDEM` — *"O que eu vi aqui"*, *"Por que importa"*,
*"Ganho esperado"*. A primeira é o `porque` que a linha já mostra; as outras
duas são exatamente o que o `?` promete, e as três telas do produto já as
escreviam — o card do GTK (`secao_exame._linha_da_ordem`) e o `--exame` no
terminal (`exame_da_mesa._imprimir_relatorio`). Esta era a única que as jogava
fora.

A MORDIDA: tire o bloco `if ordem is not None:` de
`a08_conexoes._dica_da_linha`. O primeiro teste reprova dizendo que a dica da
ordem voltou a ser vazia; o segundo, que as duas frases sumiram.
"""
from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    ROTULOS_DA_ORDEM,
    Item,
)
from hefesto_dualsense4unix.integrations.ordens_da_mesa import Linha, Ordem
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

VI = "O adaptador Bluetooth está na entrada de trás, atrás do gabinete."
IMPORTA = "Metal e distância comem o sinal, e o controle cai no meio do jogo."
GANHO = "Não medi o ganho nesta máquina — a espera é menos queda por metro."


def _ordem(acao: str = "") -> Ordem:
    """Uma ordem da mesa de mentira, com as três linhas que a tela lê."""
    return Ordem(
        chave="mover_o_bt_para_a_frente",
        acao=acao,
        o_que_eu_vi=Linha(texto=VI, selo="medido"),
        por_que_importa=Linha(texto=IMPORTA, selo="afirmado-no-doc"),
        ganho_esperado=Linha(texto=GANHO, selo="incerto"),
    )


def _item_de_ordem(acao: str = "") -> Item:
    """O `Item` que `exame_da_mesa.itens_das_ordens` monta a partir dela.

    A forma é a de lá, e não uma invenção: `chave=ordem.chave`,
    `cura=ordem.acao or None` e `porque=ordem.o_que_eu_vi.texto`. É essa forma
    que produz o buraco — a chave não é de regra, logo não tem verbete.
    """
    ordem = _ordem(acao)
    return Item(
        chave=ordem.chave,
        rotulo="Mudança recomendada",
        estado="atencao",  # (noqa-acento) chave de máquina do exame
        porque=ordem.o_que_eu_vi.texto,
        cura=ordem.acao or None,
        ordem=ordem,
    )


def test_a_chave_de_uma_ordem_nao_tem_verbete_e_e_por_isso_que_doia() -> None:
    """A PREMISSA, medida: sem esta guarda os testes abaixo podem ficar verdes
    por a chave ter ganhado verbete, e não por a cura funcionar."""
    from hefesto_dualsense4unix.app.actions.config.secao_exame import (
        DICAS_DAS_LINHAS,
    )

    item = _item_de_ordem()
    assert item.chave not in DICAS_DAS_LINHAS, (
        f"{item.chave!r} ganhou verbete em DICAS_DAS_LINHAS — o buraco desta "
        "régua mudou de forma, e ela precisa ser reescrita contra a nova.")
    assert not item.cura, "o dublê pôs cura onde o defeito era não ter nenhuma"


def test_o_interrogacao_de_uma_ordem_nao_abre_vazio() -> None:
    """O CORAÇÃO: a linha da ordem tem o que dizer, e diz.

    A MORDIDA: tire o `if ordem is not None:` de `_dica_da_linha` — esta linha
    reprova mostrando a dica vazia que o `escrever()` viraria num travessão
    dentro de uma caixa de 330px.
    """
    dica = a08._linha(_item_de_ordem())["dica"]
    assert dica, (
        "o `?` desta linha continua sem nada dentro — a caixa de 330px abre "
        "com um travessão, que é a promessa quebrada do achado de 02/09.")


def test_ele_traz_as_duas_frases_do_produto_com_o_rotulo_delas() -> None:
    """"Por que importa" e "Ganho esperado", as duas do dono, rotuladas.

    O rótulo vem de `ROTULOS_DA_ORDEM` e não é digitado aqui: uma segunda
    grafia é a que fica para trás no dia em que a primeira mudar.
    """
    dica = a08._linha(_item_de_ordem())["dica"]
    for rotulo, texto in zip(ROTULOS_DA_ORDEM[1:], (IMPORTA, GANHO), strict=True):
        assert f"<b>{rotulo}:</b>" in dica, (
            f"a dica perdeu o rótulo {rotulo!r}: {dica!r}")
        assert texto in dica, f"a dica perdeu a frase de {rotulo!r}: {dica!r}"


def test_ele_nao_repete_a_linha_que_esta_ao_lado() -> None:
    """DECISÃO 9 DELA, e ela continua valendo: *"o `?` para de repetir a linha"*.

    A primeira das três (`O que eu vi aqui`) é o `Item.porque`, que a linha ao
    lado mostra. Trazê-la para a dica faria a pessoa ler a mesma frase duas
    vezes — que é exatamente o que ela mandou tirar.
    """
    linha = a08._linha(_item_de_ordem())
    assert linha["porque"] == VI, "a linha deixou de mostrar a medição"
    assert VI not in linha["dica"], (
        "o `?` voltou a repetir a frase que a linha ao lado já mostra")
    assert ROTULOS_DA_ORDEM[0] not in linha["dica"]


def test_a_cura_continua_vindo_depois_das_duas() -> None:
    """Uma ordem COM ação tem as três coisas, e o "o que fazer" é a última.

    A ordem entre elas é a leitura: por que importa, o que se ganha, e só então
    o que fazer. Invertida, a pessoa lê a instrução antes de saber por quê.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_exame import (
        PREFIXO_DA_CURA,
    )

    dica = a08._linha(_item_de_ordem("Mova o adaptador para a entrada da frente."))["dica"]
    fazer = PREFIXO_DA_CURA + "Mova o adaptador para a entrada da frente."
    assert fazer in dica, f"a cura sumiu da dica: {dica!r}"
    assert dica.index(IMPORTA) < dica.index(fazer), (
        "o 'o que fazer' subiu para antes do 'por que importa' — a pessoa lê a "
        "instrução antes de saber a razão")


def test_uma_linha_de_regra_nao_ganhou_frase_nenhuma_a_mais() -> None:
    """A cura é PARA A ORDEM, e não pode ter mexido nas cinco regras.

    Um item de regra não traz `ordem`, então nada muda nele. Sem esta guarda a
    cura poderia ter posto rótulo em toda dica da aba.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_exame import (
        DICAS_DAS_LINHAS,
    )

    item = Item(
        chave="energia_das_portas",
        rotulo="Energia das portas",
        estado="certo",  # (noqa-acento) chave de máquina do exame
        porque="Conferido agora: nenhuma das 16 portas USB está em economia.",
        cura=None,
    )
    dica = a08._linha(item)["dica"]
    assert dica == DICAS_DAS_LINHAS["energia_das_portas"], (
        f"a dica de uma linha de REGRA mudou: {dica!r}")
    for rotulo in ROTULOS_DA_ORDEM:
        assert rotulo not in dica


# "O homem é a medida de todas as coisas." — Protágoras
