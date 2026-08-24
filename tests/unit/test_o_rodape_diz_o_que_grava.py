"""O rodapé promete o que faz — T4, CONFIGURAÇÕES-FECHA-01.

Três seções da aba Configurações (Os controles, A mesa, Orçamento) prometem
`QUANDO_VALE` (`app/actions/config/moldura.py:65`): *"A escolha passa a valer
quando você clicar em 'Aplicar', no rodapé."* O botão do rodapé
(`btn_footer_apply`, `gui/main.glade`) é montado por outro território
(`ConfigActionsMixin`/`footer_actions.py`) e a dica dele, até `22/08/2026`,
falava só de gatilhos, LEDs, rumble e mouse — nunca do que esta aba grava.

Este portão DERIVA a lista de seções que prometem o botão em vez de
mantê-la à mão: uma seção nova que importe `QUANDO_VALE` entra na conta
sozinha, sem editar este arquivo — o mesmo desenho de `secoes.SECOES`
(`secoes.py:38`).

A MORDIDA: arranque a palavra "Configurações" da dica do `btn_footer_apply`
no `main.glade` e rode `test_a_dica_do_footer_apply_menciona_a_aba_configuracoes`
— com pelo menos uma seção prometendo o botão, ele tem de reprovar.
"""
from __future__ import annotations

import inspect
import xml.etree.ElementTree as ET
from pathlib import Path

from hefesto_dualsense4unix.app.actions.config import moldura, secoes

RAIZ = Path(__file__).resolve().parents[2]
GLADE = RAIZ / "src/hefesto_dualsense4unix/gui/main.glade"

BTN_ID = "btn_footer_apply"


def _dica_do_footer_apply() -> str:
    """A `tooltip-text` do botão "Aplicar" do rodapé, lida do XML cru."""
    raiz = ET.parse(GLADE).getroot()
    for objeto in raiz.iter("object"):
        if objeto.get("id") != BTN_ID:
            continue
        for propriedade in objeto.findall("property"):
            if propriedade.get("name") == "tooltip-text":
                return propriedade.text or ""
        raise AssertionError(f"{BTN_ID} não tem tooltip-text em {GLADE}")
    raise AssertionError(f"{BTN_ID} não encontrado em {GLADE}")


def _secoes_que_prometem_o_footer() -> list[str]:
    """As seções cujo módulo importa/usa `QUANDO_VALE` — a promessa do botão.

    Lê o FONTE do módulo em vez de comparar `DICA` porque `QUANDO_VALE` é só
    parte da frase da dica (junto do rótulo de apoio, montado em tempo de
    execução): o que importa aqui é "esta seção CITA o Aplicar do rodapé",
    não o texto renderizado.
    """
    prometem = []
    for secao in secoes.SECOES_DA_ABA:
        fonte = inspect.getsource(secao)
        if "QUANDO_VALE" in fonte:
            prometem.append(secao.TITULO)
    return prometem


def test_pelo_menos_uma_secao_promete_o_footer_hoje() -> None:
    """Régua provada acertando: sem isto, o teste abaixo checaria o vazio."""
    assert _secoes_que_prometem_o_footer(), (
        "nenhuma seção usa QUANDO_VALE — a mordida abaixo não provaria nada"
    )


def test_a_dica_do_footer_apply_menciona_a_aba_configuracoes() -> None:
    """Quem só lê a dica do rodapé tem de saber que ele grava esta aba."""
    prometem = _secoes_que_prometem_o_footer()
    dica = _dica_do_footer_apply()

    assert prometem, "nenhuma seção promete o botão — ver teste anterior"
    assert "Configurações" in dica, (
        f"a dica do {BTN_ID} não menciona a aba Configurações, e "
        f"{prometem} prometem esse botão pelo nome: {dica!r}"
    )


def test_moldura_ainda_declara_quando_vale() -> None:
    """`QUANDO_VALE` existe e fala do "Aplicar" — a base de que este portão parte."""
    assert "Aplicar" in moldura.QUANDO_VALE
