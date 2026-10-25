"""O cartão do «não sei» não se anuncia como defeito.

O-CARTAO-DO-NAO-SEI-NAO-SE-ANUNCIA-COMO-DEFEITO-01.

Medido em 25/10/2026: com o ``/sys`` vazio, a 08 mostrava «Rádio pode desligar» e «Entrada com
pouca energia», e o exame não tinha achado defeito nenhum, só não tinha conseguido ler. O título
do verbete de ``DA_CONFERENCIA`` é o do alarme, e vale só no alarme.

O-CARTAO-DO-NAO-SEI-DIZ-DE-QUE-ASSUNTO-E-01 (25/10/2026): os dois cartões do ``/sys`` vazio saíam
iguais (o mesmo título, o ``ICONE_AJUDA`` e o mesmo ``aria-label``); só o ⓘ os separava. O «não
sei» leva o ícone do assunto (o do verbete) e o nome da região leva o assunto da conferência,
sem veredito: o rótulo do exame do rádio («Economia de energia desligada») afirma o que não se leu.

MORDIDAS (25/10/2026): o ``ICONE_AJUDA`` de volta no «não sei» reprova o ícone; o ``aria-label``
sem o assunto reprova os nomes iguais; o rótulo do exame no lugar do assunto reprova o veredito.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import dicas_da_conexao as dicas
from hefesto_dualsense4unix.integrations import exame_da_mesa as exame

ALARMES = (exame.ESTADO_ATENCAO, exame.ESTADO_PROBLEMA)


@pytest.mark.parametrize("chave", sorted(dicas.DA_CONFERENCIA))
def test_no_nao_sei_o_cartao_diz_que_nao_deu_para_olhar(chave: str) -> None:
    icone, alarme, _certo = dicas.DA_CONFERENCIA[chave]
    porque = "Este sistema não deixa ler isto."
    dica = dicas.dica_da_conferencia(chave, "Rótulo", exame.ESTADO_NAO_SEI, porque)
    assert dica.titulo == dicas.TITULO_SEM_VERBETE, (
        f"o «não sei» de {chave} saiu com {dica.titulo!r}, a cara do defeito")
    assert dica.titulo != alarme
    assert dica.icone == icone, f"o «não sei» de {chave} perdeu o ícone do assunto"
    assert dica.assunto == dicas.ASSUNTO_DA_CONFERENCIA[chave], (
        "o nome da região perdeu de que conferência é")
    assert dica.porque == porque, "o porquê do exame segue o mesmo"
    assert dica.nivel == dicas.NOTA


@pytest.mark.parametrize("estado", ALARMES)
@pytest.mark.parametrize("chave", sorted(dicas.DA_CONFERENCIA))
def test_no_alarme_o_cartao_segue_com_o_titulo_do_verbete(chave: str, estado: str) -> None:
    icone, alarme, _certo = dicas.DA_CONFERENCIA[chave]
    dica = dicas.dica_da_conferencia(chave, "Rótulo", estado, "Vi o defeito.")
    assert (dica.titulo, dica.icone) == (dicas.limitar_o_titulo(alarme), icone)
    assert dica.assunto == "", "no alarme o título já diz o assunto"


def test_o_assunto_do_nao_sei_nao_afirma_o_que_nao_se_leu() -> None:
    """Todo verbete tem assunto, e nenhum assunto é veredito (o alarme, o «certo» do Wi-Fi ou o
    rótulo do exame do rádio, que dizem um estado)."""
    assert set(dicas.ASSUNTO_DA_CONFERENCIA) == set(dicas.DA_CONFERENCIA)
    vereditos = {alarme for _i, alarme, _c in dicas.DA_CONFERENCIA.values()}
    vereditos |= {dicas.DA_CONFERENCIA["vizinhanca_das_portas"][2], exame.ROTULO_ENERGIA_DO_RADIO}
    rotulo = exame.ROTULO_ENERGIA_DO_RADIO
    for chave, assunto in dicas.ASSUNTO_DA_CONFERENCIA.items():
        dica = dicas.dica_da_conferencia(chave, rotulo, exame.ESTADO_NAO_SEI, "")
        assert dica.assunto == assunto and assunto not in vereditos, (chave, dica.assunto)


def test_a_conferencia_sem_verbete_no_nao_sei_tambem_nao_usa_o_rotulo() -> None:
    dica = dicas.dica_da_conferencia("outra", "Coisa quebrada", exame.ESTADO_NAO_SEI, "")
    assert dica.titulo == dicas.TITULO_SEM_VERBETE
    assert (dica.icone, dica.assunto) == (dicas.ICONE_AJUDA, "Coisa quebrada")


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
    nomes = re.findall(r'<section class="cartao-dica[^"]*" role="region" aria-label="([^"]*)"',
                       html)
    nota = f"{dicas.PALAVRA_DO_NIVEL[dicas.NOTA]}: {dicas.TITULO_SEM_VERBETE}"
    assert nomes == [f"{nota}, {dicas.ASSUNTO_DA_CONFERENCIA[i.chave]}" for i in itens], nomes
    assert len(set(nomes)) == 2, f"os dois cartões têm o mesmo nome: {nomes}"
    assert exame.ROTULO_ENERGIA_DO_RADIO not in html, "o nome do «não sei» afirma o que não leu"
    icones = re.findall(r'<span class="cd-ic"><svg class="i" aria-hidden="true"><use href="#rd-'
                        r'([^"]+)"', html)
    assert icones == [dicas.DA_CONFERENCIA[i.chave][0] for i in itens], icones
    assert len(set(icones)) == 2, f"os dois cartões têm o mesmo ícone: {icones}"
