"""Os dois módulos de barramento passam a falar do mesmo aparelho pelo mesmo nome.

CONEXÕES · MAPA 2D 01, tarefa ``MAPA-2`` (25/08/2026).

O DEFEITO, MEDIDO
------------------

``censo_do_barramento.Aparelho`` publica ``nome_do_kernel`` — ``3-1.1.4``, que
é o nome do diretório em ``/sys/bus/usb/devices``. ``mesa_de_radio.Adaptador``
tem as DUAS metades daquele nome (``busnum`` e ``devpath``) e não montava
nenhuma. Resultado: os dois módulos leem o mesmo barramento, na mesma máquina,
no mesmo segundo, e não havia uma palavra em comum para dizer "este aparelho é
aquele aparelho". Era a única peça que faltava para o mapa existir.

A âncora tinha de ser essa e não o ``vid:pid``: os dois adaptadores Bluetooth
desta bancada são ``2357:0604`` os dois. Chavear por modelo responde "que
espécie de aparelho é este", que é outra pergunta.
"""
from __future__ import annotations

from tests.unit.test_mapa_a_bancada_de_mentira import bancada_de_agora


def test_o_caminho_do_adaptador_bate_com_o_do_censo() -> None:
    """Todo ``Adaptador.caminho`` existe como ``Aparelho.nome_do_kernel``.

    Mordida exercida em 25/08/2026: troquei o corpo de
    ``_caminho_de_barramento`` por ``f"{busnum}-{devpath.replace('.', '-')}"``,
    que é o erro plausível — o sysfs usa traço entre barramento e porta e ponto
    entre as portas, e trocar um pelo outro produz um nome que PARECE certo. A
    interseção ficou vazia e o teste reprovou imprimindo os dois conjuntos.
    """
    bancada = bancada_de_agora()
    censo = bancada.censo()
    adaptadores = bancada.adaptadores()

    do_censo = {aparelho.nome_do_kernel for aparelho in censo.conectados()}
    dos_adaptadores = {a.caminho for a in adaptadores if a.caminho}

    assert dos_adaptadores, "nenhum adaptador montou caminho nenhum"
    assert dos_adaptadores <= do_censo, (
        "os dois módulos leram o mesmo barramento e não falam a mesma língua.\n"
        f"  do adaptador: {sorted(dos_adaptadores)}\n"
        f"  do censo:     {sorted(do_censo)}"
    )
    assert dos_adaptadores == {"3-1.1.1", "3-1.1.4"}, (
        f"os adaptadores desta bancada mudaram de lugar: {sorted(dos_adaptadores)}"
    )


def test_o_caminho_do_radio_vizinho_tambem_bate() -> None:
    """A mesma palavra, do lado dos outros rádios da faixa.

    Mordida: a mesma de cima, no ``RadioUsb.caminho``. Sem ela o Wi-Fi da mesa
    não tem como ser achado no mapa, e a frase "o Wi-Fi está na entrada 7"
    nunca sai.
    """
    bancada = bancada_de_agora()
    censo = bancada.censo()
    mesa = bancada.mesa()

    do_censo = {aparelho.nome_do_kernel for aparelho in censo.conectados()}
    dos_radios = {radio.caminho for radio in mesa.radios if radio.caminho}

    assert dos_radios, "nenhum rádio vizinho montou caminho nenhum"
    assert dos_radios <= do_censo, (
        f"rádio com caminho que o censo não conhece: {sorted(dos_radios - do_censo)}"
    )
    assert "4-4" in dos_radios, (
        "o Archer T3U saiu da leitura; ele é o rádio que a ordem de serviço "
        f"desta leva veio mover de lugar. Caminhos: {sorted(dos_radios)}"
    )


def test_o_adaptador_embutido_nao_inventa_entrada() -> None:
    """Rádio na placa-mãe não pendura em USB nenhum, e o caminho é ``""``.

    É o caso MAIS comum lá fora — o notebook —, e é onde um caminho inventado
    faria mais estrago: ``"0-"`` casaria com entrada nenhuma e o produto diria
    "não sei onde está" em vez de "está dentro da máquina".

    Mordida: tirar a guarda ``if not busnum or not devpath``. O embutido passa
    a responder ``"0-"``, e o teste reprova.
    """
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador

    assert Adaptador(interface="hci0").caminho == "", (
        "o adaptador embutido inventou um caminho de barramento"
    )
    assert Adaptador(interface="hci0", busnum=3, devpath="").caminho == ""
    assert Adaptador(interface="hci0", busnum=0, devpath="1.1").caminho == ""
