"""O leitor do texto da tela trata o sinal de maior de dentro de um atributo como parte da tag."""
from __future__ import annotations

from hefesto_dualsense4unix.interface.frases_banidas import texto_visivel

COM_ROTEIRO = (
    '<a class="btn2" href="06-navegacao.html" '
    'onclick="if (history.length > 1) { history.back(); return false }">Cancelar</a>'
)
COM_DICA = '<a title="Maior > menor" href="#x">Voltar</a>'
COM_APOSTROFO = """<a data-x='a > b' href="#y">Guardar</a>"""


def test_o_maior_dentro_do_atributo_nao_fecha_a_tag() -> None:
    """O roteiro do clique não vira texto: lê-se só o rótulo do botão."""
    assert texto_visivel(COM_ROTEIRO).split() == ["Cancelar"]


def test_a_dica_com_o_sinal_segue_lida_inteira() -> None:
    """O atributo que a pessoa lê continua lido, com o sinal dentro."""
    assert texto_visivel(COM_DICA).split() == ["Maior", ">", "menor", "Voltar"]


def test_o_valor_entre_apostrofos_tambem_e_da_tag() -> None:
    """O valor entre apóstrofos fecha no apóstrofo, não no sinal."""
    assert texto_visivel(COM_APOSTROFO).split() == ["Guardar"]
