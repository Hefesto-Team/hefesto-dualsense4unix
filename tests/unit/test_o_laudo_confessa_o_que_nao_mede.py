"""O laudo tem quatro blocos, e o quarto **nunca some** — a ``CAL-7``.

``CALIBRAR-AS-ENTRADAS-01`` §4.3 (26/08/2026).

O EXAME É A MOLDURA, E FOI A PALAVRA DELA
-------------------------------------------

*"vai servir pra desculpa de olharmos a saúde do seu computador"*. O laudo
aparece **antes** de ela encaixar qualquer coisa, e é o que faz a tela valer a
pena mesmo se ela fechar ali.

Quatro blocos, sempre nesta ordem: **O que está bem** · **O que merece
atenção** · **O que eu não consegui conferir** · **O que eu não meço**.

POR QUE O QUARTO NUNCA SOME
----------------------------

Ele é o que impede o exame de virar promessa. Um laudo que só fala do que sabe
ensina a pessoa a confiar nele para tudo — inclusive para o que ele nunca
mediu. É a mesma disciplina do cabeçalho *"O que NÃO verifiquei"* das entregas
desta casa: a confissão é a parte que dá valor ao resto.
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
    LAUDO_ATENCAO,
    LAUDO_BEM,
    LAUDO_NAO_CONFERI,
    LAUDO_NAO_MECO,
    LogicaDaCalibracao,
)
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
    Energia,
)
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import NoDeEntrada
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa
from tests.unit.test_a_fase_sentada_resolve_o_hub import GravadorDeMentira
from tests.unit.test_entradas_do_gabinete import _entradas


def _mesa_perfeita() -> tuple[NoDeEntrada, ...]:
    """Duas entradas, as duas ocupadas, as duas com painel, zero excesso.

    Nada a relatar em bloco nenhum — que é exatamente o caso em que esconder o
    quarto bloco seria tentador.
    """
    return (
        NoDeEntrada(
            no="usb1-port1",
            caminho_sysfs="/mentira/usb1-port1",
            hub="usb1",
            numero=1,
            estado="configured",
            painel="right",
            aparelho="1-1",
            excesso_de_corrente=0,
        ),
        NoDeEntrada(
            no="usb1-port2",
            caminho_sysfs="/mentira/usb1-port2",
            hub="usb1",
            numero=2,
            estado="configured",
            painel="left",
            aparelho="1-2",
            excesso_de_corrente=0,
        ),
    )


def _logica(entradas, censo: Censo | None = None) -> LogicaDaCalibracao:
    return LogicaDaCalibracao(
        MapaDaMesa(), censo or Censo(), entradas, gravar=GravadorDeMentira()
    )


# ---------------------------------------------------------------------------
# A mordida
# ---------------------------------------------------------------------------


def test_o_quarto_bloco_nunca_some() -> None:
    """Mesa perfeita, e "O que eu não meço" **continua na tela**.

    MORDIDA: esconder o bloco quando não há nada a relatar — o
    ``default_factory`` do ``Laudo.nao_meco`` virando tupla vazia, ou
    ``blocos()`` filtrando bloco vazio. O bloco some e o teste reprova, porque
    é ele que impede o exame de virar promessa.
    """
    laudo = _logica(_mesa_perfeita()).laudo()
    titulos = [titulo for titulo, _linhas in laudo.blocos()]

    assert titulos == [LAUDO_BEM, LAUDO_ATENCAO, LAUDO_NAO_CONFERI, LAUDO_NAO_MECO], (
        f"os quatro blocos saíram fora de ordem ou faltou algum: {titulos}"
    )
    assert laudo.nao_meco, (
        "'O que eu não meço' sumiu numa mesa sem nada a relatar — e é "
        "justamente aí que o laudo vira promessa"
    )
    assert laudo.atencao == (), "inventou atenção onde não há nada"
    assert any("interferência" in linha for linha in laudo.nao_meco)
    assert any("bateria" in linha for linha in laudo.nao_meco)


def test_o_bloco_do_que_esta_bem_conta_o_que_conferiu() -> None:
    """"zero em 2" — o número, não o adjetivo.

    Um laudo que diz "está tudo bem" não é conferível; um que diz "zero em 2"
    é. É a mesma razão pela qual o progresso mostra os dois números (R26).
    """
    laudo = _logica(_mesa_perfeita()).laudo()
    assert any("zero em 2" in linha for linha in laudo.bem), laudo.bem


def test_o_excesso_de_corrente_vai_para_atencao_com_a_entrada_nomeada() -> None:
    """Excesso de corrente é sintoma, e a linha diz EM QUAL entrada.

    "Alguma entrada teve excesso" não conserta nada. O nó nomeado conserta.
    """
    com_excesso = (
        NoDeEntrada(
            no="usb1-port1",
            caminho_sysfs="/mentira/usb1-port1",
            hub="usb1",
            numero=1,
            estado="configured",
            painel="right",
            aparelho="1-1",
            excesso_de_corrente=3,
        ),
    )
    laudo = _logica(com_excesso).laudo()
    assert any("usb1-port1" in linha for linha in laudo.atencao), laudo.atencao
    assert laudo.bem == (), "disse que está bem com excesso de corrente na mesa"


def test_a_declaracao_incoerente_do_descritor_vira_atencao() -> None:
    """MEDIDO em 22/08/2026 nos três TP-Link: ``bmAttributes=e0`` com 500 mA.

    Declara fonte própria E pede meio ampère da entrada. Quem consome esse dado
    precisa ver a contradição junto da declaração, senão desenha "hub
    alimentado" em cima de um bit que não sustenta a afirmação.
    """
    mentiroso = Aparelho(
        no="/mentira/3-1",
        nome_do_kernel="3-1",
        especie="adaptador Bluetooth",
        energia=Energia(corrente_pedida_ma=500, autoalimentado_declarado=True),
    )
    laudo = _logica((), Censo(aparelhos=(mentiroso,))).laudo()
    assert any("3-1" in linha for linha in laudo.atencao), laudo.atencao


def test_o_que_nao_conferi_conta_as_vazias_e_as_sem_painel() -> None:
    """As entradas que nunca receberam nada não viram "problema": viram lacuna.

    A diferença é honesta e é o desenho: o produto não sabe se elas existem no
    metal ou se são conectores internos que ninguém alcança. É exatamente o que
    a caminhada da fase em pé existe para responder.
    """
    laudo = _logica(_entradas()).laudo()
    assert laudo.nao_conferi, "11 buracos vazios e nada no bloco da lacuna"
    assert any("11" in linha for linha in laudo.nao_conferi), laudo.nao_conferi
    # E o quarto bloco continua lá, com a mesa cheia de lacuna.
    assert laudo.nao_meco
