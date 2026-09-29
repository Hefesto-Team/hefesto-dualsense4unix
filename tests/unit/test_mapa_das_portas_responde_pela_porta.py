"""O número que ela escreveu no gabinete responde pelo aparelho.

CONEXÕES · MAPA 2D 01, tarefa ``MAPA-3`` (25/08/2026).

O DEFEITO, EM UMA FRASE
------------------------

Ela numerou as entradas do gabinete numa foto para poder falar comigo; o produto
continua falando ``3-1.1.4``, e por isso não consegue dizer a ninguém — nem a
ela — onde encostar a mão.

A CHAVE DE HOJE NÃO DISTINGUE OS ADAPTADORES — MEDIDO
-------------------------------------------------------

``MesaDeclarada.radios`` é indexado por ``vid:pid``, e os adaptadores Bluetooth
desta bancada são ``2357:0604`` **os dois**. Declarar "isto é um adaptador
Bluetooth" numa linha declara nas duas; declarar em qual entrada cada um está é
impossível. Não é defeito daquele campo — é a prova de que a pergunta "onde ele
está" precisa de outra chave, e é essa chave que este módulo usa.

A BANCADA É A DE ``test_mapa_a_bancada_de_mentira``, que é a leitura de 25/08
às 02h30. Nenhum caminho de ``/sys`` desta máquina é tocado.
"""
from __future__ import annotations

from hefesto_dualsense4unix.integrations.mapa_das_portas import (
    caminho_de,
    filhas_de,
    porta_de,
    portas_livres,
    resumo_do_mapa,
    vizinhas_de_verdade,
)
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa
from tests.unit.test_mapa_a_bancada_de_mentira import (
    bancada_de_agora,
    mapa_dela,
)


# --- 1. A pergunta "onde ele está" -------------------------------------------
#
# O CASAMENTO PELO SERIAL SAIU EM 28/09/2026 (A-CONEXOES-DIZ-O-QUE-O-PRODUTO-JA-
# MEDE-01). `mapa_das_portas.porta_do_adaptador` casava o adaptador com a
# entrada pelo serial USB, que só nos TP-Link é o endereço Bluetooth, e nunca
# teve chamador. A mesma pergunta o produto responde pelo lugar do adaptador no
# sysfs (`bluez_dbus.lugares_dos_adaptadores`), que vale para qualquer máquina.
# As quatro réguas daqui mediam o casamento, e saíram com ele.


# --- 2. As duas traduções -----------------------------------------------------


def test_o_caminho_vira_numero_e_o_numero_vira_caminho() -> None:
    """As duas pontas da mesma amarração, incluindo a entrada por extensão."""
    mapa = mapa_dela()

    assert porta_de(mapa, "3-1.1.4") == "15a"
    assert porta_de(mapa, "3-1.2") == "9"
    assert porta_de(mapa, "1-6") == "2"
    assert caminho_de(mapa, "15a") == "3-1.1.4"
    assert caminho_de(mapa, "4") == "3-1"
    assert filhas_de(mapa, "15") == ("15a",)


def test_caminho_que_ela_nao_declarou_devolve_nada() -> None:
    """Sem declaração não há número — e a tela volta a falar como fala hoje.

    Mordida: fazer ``porta_de`` devolver o próprio caminho quando não acha. A
    tela passa a escrever "Entrada 3-1.1.4", que é o jargão de sempre com uma
    palavra nova por cima.
    """
    mapa = mapa_dela()

    assert porta_de(mapa, "9-9") is None
    assert porta_de(mapa, "") is None, "caminho vazio casou com alguma entrada"
    assert caminho_de(mapa, "42") is None
    assert porta_de(MapaDaMesa(), "3-1.1.4") is None, (
        "quem nunca desenhou a mesa recebeu um número mesmo assim"
    )


# --- 3. O que está livre, e o que está colado ---------------------------------


def test_as_entradas_vazias_sao_as_que_ela_pode_usar() -> None:
    """A resposta que a ordem de serviço consome: onde ainda cabe um dongle.

    Duas regras não óbvias moram nesta lista, e as duas estão medidas na mesa
    de agora:

    * a entrada 11 está DECLARADA (é onde o Wi-Fi morava às 21h de 24/08) e
      está LIVRE, porque o aparelho saiu dali;
    * a entrada 15 hospeda a extensão e **não** está livre, mesmo com o dongle
      a três metros — o cabo ocupa o buraco.

    Mordida: tirar a guarda ``if filhas_de(...)``. A 15 entra na lista, e a
    tela manda a pessoa desplugar a própria extensão para usar uma entrada que
    já está ocupada.
    """
    livres = portas_livres(mapa_dela(), bancada_de_agora().censo())

    assert livres == ("3", "5", "6", "8", "10", "11", "12", "14"), (
        f"a lista de entradas livres mudou: {livres}"
    )
    assert "15" not in livres, (
        "a entrada que hospeda a extensão foi anunciada como livre"
    )


def test_as_duas_entradas_da_frente_sao_vizinhas_e_o_sysfs_nao_sabe() -> None:
    """O par que só o desenho DELA enxerga — e é o ponto do mapa inteiro.

    MEDIDO: os dois receptores de 2,4 GHz da frente do gabinete são ``1-3`` e
    ``1-6``. Três portas de distância na numeração do kernel, um centímetro de
    distância no plástico. ``vizinhancas_apertadas`` não vê este par, porque
    ela responde pelo soquete — e o soquete não é o gabinete.

    Mordida exercida em 25/08/2026: troquei ``vizinhas_de_verdade`` por
    ``mesa_de_radio.vizinhancas_apertadas`` sobre a mesma bancada. Ela devolveu
    ZERO pares, o par ("1", "2") sumiu, e o teste reprovou — que é o produto
    voltando a não enxergar dois rádios encostados um no outro.
    """
    from hefesto_dualsense4unix.integrations.mesa_de_radio import (
        vizinhancas_apertadas,
    )

    bancada = bancada_de_agora()
    mesa = bancada.mesa()

    pares = vizinhas_de_verdade(mapa_dela(), bancada.censo())

    assert pares == (("1", "2"), ), (
        f"a vizinhança pelo desenho dela mudou: {pares}"
    )
    # E a régua velha, sobre a MESMA mesa, não vê nada — é a medição que
    # justifica a régua nova existir.
    assert vizinhancas_apertadas([*mesa.adaptadores, *mesa.radios]) == [], (
        "a vizinhança pelo sysfs passou a ver o par da frente; se isso mudou, "
        "a razão de ser da vizinhança pelo mapa mudou junto e tem de ser remedida"
    )


def test_a_entrada_por_extensao_nao_e_vizinha_da_fileira() -> None:
    """Uma entrada por extensão está a três metros de quem ficou na fileira.

    Este é o defeito do §6 da sprint, e ele custa uma acusação falsa: hoje o
    produto pinta de laranja um par que está do outro lado da sala.

    A declaração muda de uma linha em relação à mesa dela — o segundo dongle
    Bluetooth vai para a entrada 14, ao lado da 15 que hospeda a extensão. É
    declaração, não medição: o mapa é o que ela desenha, e desenhar outro é
    legítimo.

    Mordida: dobrar a entrada filha na vaga da entrada que a hospeda (tratar
    ``15a`` como se fosse ``15`` na fileira). O par ("14", "15a") aparece, e o
    teste reprova.
    """
    mapa = MapaDaMesa.model_validate(
        {
            "faces": [{"nome": "Hub", "portas": ["13", "14", "15"]}],
            "portas": {
                "14": {"caminho": "3-1.1.1"},
                "15a": {"caminho": "3-1.1.4", "filha_de": "15"},
            },
        }
    )

    pares = vizinhas_de_verdade(mapa, bancada_de_agora().censo())

    assert pares == (), (
        "o dongle na ponta da extensão virou vizinho de quem ficou na fileira: "
        f"{pares}. O produto pinta de laranja um par que está a três metros"
    )


# --- 4. O resumo que a linha de "Conexões" consome ----------------------------


def test_o_resumo_conta_faces_entradas_e_aparelhos_colocados() -> None:
    """Os três números da linha-resumo, e nada de texto.

    Mordida: contar as entradas do dicionário ``portas`` em vez das faces. A
    ``15a`` entra na conta, o resumo diz "16 entradas" e a fileira do desenho
    tem 15 — o número da tela deixa de bater com o metal.
    """
    resumo = resumo_do_mapa(mapa_dela(), bancada_de_agora().censo())

    assert (resumo.faces, resumo.entradas, resumo.colocados) == (3, 15, 7), (
        f"o resumo mudou: {resumo}"
    )
    assert not resumo.vazio


def test_quem_nunca_desenhou_tem_resumo_vazio() -> None:
    """Zero entradas declaradas é estado legítimo, e a tela tem de saber disso."""
    resumo = resumo_do_mapa(MapaDaMesa(), bancada_de_agora().censo())

    assert resumo.vazio, f"o mapa vazio não se reconheceu vazio: {resumo}"
    assert (resumo.faces, resumo.entradas, resumo.colocados) == (0, 0, 0)
