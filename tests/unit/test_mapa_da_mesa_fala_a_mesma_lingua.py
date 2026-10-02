"""Os dois módulos de barramento passam a falar do mesmo aparelho pelo mesmo nome."""
from __future__ import annotations

from tests.unit.test_mapa_a_bancada_de_mentira import bancada_de_agora


def test_o_caminho_do_adaptador_bate_com_o_do_censo() -> None:
    """Todo ``Adaptador.caminho`` existe como ``Aparelho.nome_do_kernel``."""
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
    """A mesma palavra, do lado dos outros rádios da faixa."""
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
    """Rádio na placa-mãe não pendura em USB nenhum, e o caminho é ``""``."""
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador

    assert Adaptador(interface="hci0").caminho == "", (
        "o adaptador embutido inventou um caminho de barramento"
    )
    assert Adaptador(interface="hci0", busnum=3, devpath="").caminho == ""
    assert Adaptador(interface="hci0", busnum=0, devpath="1.1").caminho == ""
