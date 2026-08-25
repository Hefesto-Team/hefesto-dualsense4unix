"""O hub de dois barramentos não é a mesa dela estando errada.

CONEXÕES · MAPA 2D 01, tarefa ``MAPA-6`` (25/08/2026).

O QUE ESTÁ MEDIDO
------------------

O hub dela é UM plástico com DOIS chips: o lado USB 2.0 enumera em
``3-1``/``3-1.1`` e o lado USB 3.0 em ``4-1``/``4-1.1``. Os dois barramentos
pendem do mesmo controlador PCI (``0000:0c:00.3``), e os dois lados têm o mesmo
``devpath``. É o mesmo aparelho de bancada visto por dois barramentos.

Um aparelho no buraco AZUL daquele hub pendura em ``4-1.1`` enquanto os vizinhos
dele penduram em ``3-1``. A comparação de prefixo crua acusa a face "Hub" de
hospedar uma entrada que não pendura nela — e a acusação é FALSA: ela declarou
certo, e o produto é que não sabe o que é um hub de dois barramentos.

Acusar falsamente é pior que não acusar: a pessoa vai mexer numa mesa que está
certa, e o produto perde a credibilidade justamente na tela que existe para
dizer onde as coisas estão.

A BANCADA
----------

``bancada_com_o_wifi_no_hub`` — a mesa dela às 21h de 24/08/2026, com o Archer
T3U em ``4-1.1.2``. É a leitura "antes" de um ensaio real, e é o único estado
em que o hub de dois barramentos aparece: às 02h30 de 25/08 o Wi-Fi já tinha
saído para uma traseira, e o lado 3.0 do hub ficou vazio.
"""
from __future__ import annotations

from hefesto_dualsense4unix.integrations.mapa_das_portas import incoerencias
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa
from tests.unit.test_mapa_a_bancada_de_mentira import (
    bancada_com_o_wifi_no_hub,
    bancada_de_agora,
    mapa_dela,
)


def test_o_wifi_no_lado_usb3_do_mesmo_hub_nao_acusa() -> None:
    """A mesa dela, declarada certa, não recebe acusação nenhuma.

    Mordida exercida em 25/08/2026: troquei o
    ``_mesmo_plastico_em_dois_barramentos`` por um ``return False``, que é a
    comparação de prefixo crua. Saiu UMA incoerência apontando a entrada 11 —
    a acusação falsa contra a mesa dela — e o teste reprovou nomeando a
    entrada e a âncora.
    """
    achadas = incoerencias(mapa_dela(), bancada_com_o_wifi_no_hub().censo())

    assert achadas == (), (
        "o produto acusou a mesa dela de estar errada. O hub de dois "
        "barramentos é UM plástico, e o lado 3.0 dele enumera noutro "
        f"barramento de propósito: {achadas}"
    )


def test_aparelho_que_de_fato_nao_pendura_acusa() -> None:
    """E a régua ainda sabe dizer não — senão a cura seria "nunca acusar nada".

    A entrada 9 sai do hub e passa a apontar para ``1-3``, que pendura direto
    na placa, noutro controlador PCI. Aí a acusação é verdadeira: ela declarou
    na face errada, e a tela tem de conseguir dizer isso.

    Mordida: fazer ``incoerencias`` devolver sempre ``()``. Este teste reprova,
    e é ele que impede a cura preguiçosa de passar no teste de cima.
    """
    mapa = mapa_dela().model_dump(mode="json")
    mapa["portas"]["9"]["caminho"] = "1-3"
    mapa["portas"]["1"]["caminho"] = None

    achadas = incoerencias(
        MapaDaMesa.model_validate(mapa), bancada_com_o_wifi_no_hub().censo()
    )

    assert len(achadas) == 1, f"esperava uma acusação e vieram {len(achadas)}: {achadas}"
    assert achadas[0].porta == "9", f"acusou a entrada errada: {achadas[0]}"
    assert achadas[0].face == "Hub"
    assert achadas[0].caminho == "1-3"
    assert achadas[0].ancora == "3-1", (
        f"a âncora da face Hub deixou de ser o hub dela: {achadas[0]}"
    )


def test_face_que_pendura_direto_na_placa_nunca_acusa() -> None:
    """Frente e traseira não têm cabo, e face sem âncora não acusa ninguém.

    É a regra que faz o mapa servir a um notebook: quem declara "Esquerda: 1,
    2" e "Direita: 3" não tem hub nenhum, e o produto não pode inventar uma
    incoerência a partir disso.

    Mordida: fazer ``_ancora_da_face`` devolver o primeiro hub que encontrar em
    vez de ``""`` quando não há nenhum. A traseira passa a ter âncora e acusa
    as entradas que penduram na placa — todas elas.
    """
    achadas = incoerencias(mapa_dela(), bancada_de_agora().censo())

    assert achadas == (), (
        f"a mesa de agora, declarada certa, recebeu acusação: {achadas}"
    )


def test_entrada_declarada_com_o_aparelho_fora_nao_acusa() -> None:
    """O aparelho saiu da mesa; o mapa continua valendo para quando ele voltar.

    Na leitura de 02h30 a entrada 11 está declarada e vazia — o Wi-Fi mudou de
    buraco. Acusar aqui seria cobrar dela um aparelho que ela mesma tirou.

    Mordida: tirar a guarda ``caminho not in caminho_por_nome``. Toda entrada
    declarada e vazia vira acusação, e a mesa dela passa a acusar sempre que
    ela desplugar qualquer coisa.
    """
    achadas = incoerencias(mapa_dela(), bancada_de_agora().censo())
    entradas = {achada.porta for achada in achadas}

    assert "11" not in entradas, (
        f"a entrada vazia virou acusação: {achadas}"
    )


def test_mapa_vazio_nao_acusa_nada() -> None:
    """Quem nunca desenhou não pode receber acusação sobre o que não desenhou."""
    assert incoerencias(MapaDaMesa(), bancada_de_agora().censo()) == ()
