"""O cartão do «não sei» não se anuncia como defeito.

O-CARTAO-DO-NAO-SEI-NAO-SE-ANUNCIA-COMO-DEFEITO-01.

Medido em 25/10/2026: com o ``/sys`` vazio, a 08 mostrava «Rádio pode desligar» e «Entrada com
pouca energia», e o exame não tinha achado defeito nenhum, só não tinha conseguido ler. O título
do verbete de ``DA_CONFERENCIA`` é o do alarme, e vale só no alarme.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import dicas_da_conexao as dicas
from hefesto_dualsense4unix.integrations import exame_da_mesa as exame

ALARMES = (exame.ESTADO_ATENCAO, exame.ESTADO_PROBLEMA)


@pytest.mark.parametrize("chave", sorted(dicas.DA_CONFERENCIA))
def test_no_nao_sei_o_cartao_diz_que_nao_deu_para_olhar(chave: str) -> None:
    _icone, alarme, _certo = dicas.DA_CONFERENCIA[chave]
    porque = "Este sistema não deixa ler isto."
    dica = dicas.dica_da_conferencia(chave, "Rótulo", exame.ESTADO_NAO_SEI, porque)
    assert dica.titulo == dicas.TITULO_SEM_VERBETE, (
        f"o «não sei» de {chave} saiu com {dica.titulo!r}, a cara do defeito")
    assert dica.titulo != alarme
    assert dica.icone == dicas.ICONE_AJUDA
    assert dica.porque == porque, "o porquê do exame segue o mesmo"
    assert dica.nivel == dicas.NOTA


@pytest.mark.parametrize("estado", ALARMES)
@pytest.mark.parametrize("chave", sorted(dicas.DA_CONFERENCIA))
def test_no_alarme_o_cartao_segue_com_o_titulo_do_verbete(chave: str, estado: str) -> None:
    icone, alarme, _certo = dicas.DA_CONFERENCIA[chave]
    dica = dicas.dica_da_conferencia(chave, "Rótulo", estado, "Vi o defeito.")
    assert (dica.titulo, dica.icone) == (dicas.limitar_o_titulo(alarme), icone)


def test_a_conferencia_sem_verbete_no_nao_sei_tambem_nao_usa_o_rotulo() -> None:
    dica = dicas.dica_da_conferencia("outra", "Coisa quebrada", exame.ESTADO_NAO_SEI, "")
    assert dica.titulo == dicas.TITULO_SEM_VERBETE


def test_a_08_num_sys_vazio_nao_mostra_alarme(tmp_path: Path) -> None:
    """O caminho do produto: o exame de verdade num /sys vazio e o painel que a 08 pinta."""
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

    sys_vazio = tmp_path / "sys"
    sys_vazio.mkdir()
    regra = tmp_path / "regra.conf"
    regra.write_text("options btusb enable_autosuspend=N\n", encoding="utf-8")
    itens = [
        exame.energia_do_radio(parametro=sys_vazio / "enable_autosuspend", conf=regra),
        exame.energia_das_portas(raiz=sys_vazio),
    ]
    assert [i.estado for i in itens] == [exame.ESTADO_NAO_SEI] * 2, (
        "a cena tem de ser o «não sei», senão não mede nada")
    painel = a08._o_painel_das_dicas(itens, None)
    titulos = [d.titulo for d in painel.visiveis]
    assert titulos == [dicas.TITULO_SEM_VERBETE] * 2, titulos
    html = a08._html_das_dicas(itens, None)
    for _icone, alarme, _certo in dicas.DA_CONFERENCIA.values():
        assert alarme not in html, f"«{alarme}» apareceu num /sys vazio"
