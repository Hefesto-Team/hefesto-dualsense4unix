"""AS DICAS DIZEM CADA AJUSTE — A-GESTAO-DOS-CONTROLES-NO-PRODUTO-01, em cartões desde 04/10/2026.

AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01: a «Sugestão de Conexão» (uma linha por ajuste) e o exame de
cinco frases viraram uma fileira de cartões. Cada ajuste do exame, a proposta da central e o Wi-Fi
que cai viram UM cartão; o que está certo vira uma linha «✓ …» no fim.

MORDIDAS: tirar o `if estado == "certo"` do `_o_painel_das_dicas` põe o certo entre os cartões;
tirar o `calada=` do `dica_da_ordem` devolve a ordem calada ao topo.
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "mockup/08-conexoes.html"


def _a08() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _ordem(chave: str, acao: str, destino: str = "", arranjo: str = "") -> Any:
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import Identidade, Linha, Ordem

    frase = Linha(texto="O hub divide o caminho. Isto não entra no cartão.", selo="")
    return Ordem(chave=chave, acao=acao,  # (noqa-acento) campo da Ordem
                 o_que_eu_vi=frase, por_que_importa=frase, ganho_esperado=frase,
                 alvo=Identidade(caminho="3-1.2"), destino=destino, arranjo=arranjo)


def _item(chave: str, estado: str, cura: str | None = None, ordem: Any = None,
          porque: str = "o que eu vi") -> Any:
    from hefesto_dualsense4unix.integrations.exame_da_mesa import Item

    return Item(chave=chave, rotulo=chave, estado=estado, porque=porque, cura=cura, ordem=ordem)


def _titulos(dicas: Any) -> list[str]:
    return [d.titulo for d in dicas]


def test_cada_ajuste_do_exame_vira_um_cartao_e_o_certo_vira_a_linha_do_fim() -> None:
    from hefesto_dualsense4unix.integrations.exame_da_mesa import (
        ESTADO_ATENCAO,
        ESTADO_CERTO,
        ESTADO_NAO_SEI,
        ESTADO_PROBLEMA,
    )
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        R3_DONGLE_ATRAS_DE_HUB,
        R4_TECLADO_SO_NO_HUB,
    )

    a08 = _a08()
    vivos = [
        _item("a", ESTADO_ATENCAO,
              ordem=_ordem(R3_DONGLE_ATRAS_DE_HUB, "Tire o adaptador do hub.")),
        _item("energia_das_portas", ESTADO_PROBLEMA, cura="Ligue o hub na tomada."),
        _item("b", ESTADO_ATENCAO, ordem=_ordem(R4_TECLADO_SO_NO_HUB, "Ligue o teclado direto.")),
        _item("suporte_ao_controle", ESTADO_CERTO),
        _item("pareamentos", ESTADO_NAO_SEI, cura="Isto é uma nota."),
    ]
    painel = a08._o_painel_das_dicas(vivos, None)
    assert _titulos(painel.visiveis) == [
        "Entrada com pouca energia", "Bluetooth atrás de hub", "Teclado só no hub"], painel
    assert _titulos(painel.demais) == ["Pareamento incompleto"], "a nota vai para «mais N»"
    assert painel.certos == ("Suporte ao controle",)
    html = a08._html_das_dicas(vivos, None)
    assert html.count("<section ") == 4 and "mais 1" in html
    assert "✓ Suporte ao controle" in html
    assert "O que fazer: Ligue o hub na tomada." in html, "a cura do dono sumiu do cartão"
    assert "Isto não entra no cartão" not in html, "só a primeira frase do porquê vai ao ⓘ"
    assert 'class="cd-pic"' not in html, "sem destino não há de→para"


def test_sem_ajuste_o_painel_diz_que_nao_ha_o_que_mudar() -> None:
    from hefesto_dualsense4unix.integrations.dicas_da_conexao import NADA_A_MUDAR
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_CERTO

    a08 = _a08()
    for vivos in ([], [_item("energia_do_radio", ESTADO_CERTO)]):
        painel = a08._o_painel_das_dicas(vivos, None)
        assert painel.vazio
        assert NADA_A_MUDAR in a08._html_das_dicas(vivos, None)
    assert NADA_A_MUDAR == "Nada a mudar agora."


def test_a_ordem_com_destino_traz_o_de_para_e_a_calada_vai_para_o_fim(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_ATENCAO
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        R2_DOIS_RADIOS_COLADOS,
        R3_DONGLE_ATRAS_DE_HUB,
    )

    a08 = _a08()
    calada = _ordem(R2_DOIS_RADIOS_COLADOS, "Isto ela calou.", arranjo="a2")
    com = _ordem(R3_DONGLE_ATRAS_DE_HUB, "Mova o adaptador Bluetooth para a Entrada 9",
                 destino="9", arranjo="a1")
    monkeypatch.setattr(a08, "_DISPENSADAS", {R2_DOIS_RADIOS_COLADOS: "a2"})
    painel = a08._o_painel_das_dicas([_item("c", ESTADO_ATENCAO, ordem=calada),
                                      _item("p", ESTADO_ATENCAO, ordem=com)], None)
    assert _titulos((*painel.visiveis, *painel.demais)) == [
        "Bluetooth atrás de hub", "Dois rádios colados"]
    assert painel.visiveis[1].calada and painel.visiveis[1].acao.rotulo == "Voltar a mostrar"
    assert painel.visiveis[1].acao.dados == (("v", "0"),), "a linha do exame que o ignorar chama"
    assert painel.visiveis[0].para and painel.visiveis[0].de
    html = a08._html_das_dicas([_item("p", ESTADO_ATENCAO, ordem=com)], None)
    assert 'class="cd-pic"' in html and "Entrada 9" in html


@pytest.mark.parametrize(("caminho", "esperado"), [
    ("9-1.2", "Entrada 15"),
    ("10-1.1.4", "Entrada 9"),
    ("9-7", "9-7"),
])
def test_as_duas_pontas_dizem_a_entrada(monkeypatch: pytest.MonkeyPatch, caminho: str,
                                        esperado: str) -> None:
    """26/09/2026, foto dela: a caixa da esquerda mostrava «4-1.1.4» e a da direita «Entrada 2»."""
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import Identidade, Linha, Ordem
    from hefesto_dualsense4unix.utils.maquina import MapaDaMesa, MaquinaConfig, PortaDeclarada

    a08 = _a08()
    mapa = MapaDaMesa(portas={
        "9": PortaDeclarada(caminho="9-1.1.4", nos=["9-1.1-port4", "10-1.1-port4"]),
        "15": PortaDeclarada(caminho="9-1.2", nos=["9-1-port2", "10-1-port2"]),
    })
    documento = MaquinaConfig(mapa=mapa)
    monkeypatch.setattr(a08, "_declaracao", lambda recarregar=False: documento)
    vazio = Linha(texto="", selo="")
    ordem = Ordem(chave="k", acao="Mova isto para a entrada 2",  # (noqa-acento) campo da Ordem
                  o_que_eu_vi=vazio, por_que_importa=vazio, ganho_esperado=vazio,
                  alvo=Identidade(caminho=caminho), destino="2", arranjo="a")
    assert a08._a_ordem_na_tela(ordem) == (esperado, "Entrada 2")


@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
@pytest.mark.parametrize("de, para", [("L1", "L2"), ("L2", "L1"), ("L3", "L1")])
def test_a_proposta_da_central_e_um_cartao_com_o_botao_de_mover(
        jogador: int, de: str, para: str) -> None:
    a08 = _a08()
    lugares = [{"id": "L1", "nome": "Esquerda"}, {"id": "L2", "nome": "Meio"},
               {"id": "L3", "entrada": "Entrada 4"}]
    aparelhos = [{"id": "ap", "tipo": "controle", "lugar": de, "jogador": jogador},
                 {"id": "outro", "tipo": "controle", "lugar": de, "jogador": 9},
                 {"id": "caixa", "tipo": "caixa", "lugar": para}]
    cena = {"proposta": {"controle": "ap", "destino": para}, "lugares": lugares,
            "aparelhos": aparelhos}
    nomes = {"L1": "Esquerda", "L2": "Meio", "L3": "Entrada 4"}
    painel = a08._o_painel_das_dicas([], cena)
    assert len(painel.visiveis) == 1
    cartao = painel.visiveis[0]
    assert cartao.titulo == f"{nomes[de]} dividido em 2"
    assert (cartao.de, cartao.para) == (f"P{jogador} · {nomes[de]}", nomes[para])
    assert cartao.acao.rotulo == f"Levar P{jogador} para o {nomes[para]}"
    assert cartao.acao.gesto == "aceitar-sugestao"
    assert dict(cartao.acao.dados) == {"alvo": "ap", "destino": para}


def test_o_adaptador_sem_folga_diz_sufocado_e_pesa_mais() -> None:
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_ATENCAO

    a08 = _a08()
    cena = {"proposta": {"controle": "ap", "destino": "L2"},
            "lugares": [{"id": "L1", "nome": "Meio"}, {"id": "L2", "nome": "Direita"}],
            "aparelhos": [{"id": "ap", "tipo": "controle", "lugar": "L1", "jogador": 2}],
            "evitados": [{"lugar": "L1", "ini": 0, "fim": 59}], "canais_medidos": {"L1": True}}
    painel = a08._o_painel_das_dicas([_item("x", ESTADO_ATENCAO, cura="Antes.")], cena)
    assert painel.visiveis[0].titulo == "Meio sufocado" and painel.visiveis[0].nivel == "grave"
    assert "só 20 dos 79 canais" in painel.visiveis[0].porque


def test_sem_proposta_ou_com_proposta_sem_aparelho_nao_ha_cartao() -> None:
    a08 = _a08()
    cena = {"proposta": {"controle": "sumiu", "destino": "L1"},
            "lugares": [{"id": "L1", "nome": "A"}], "aparelhos": []}
    for c in (None, {}, cena):
        assert a08._o_painel_das_dicas([], c).vazio


def test_a_pagina_da_bancada_tem_as_dicas_e_nao_tem_a_sugestao() -> None:
    html = BANCADA.read_text(encoding="utf-8")
    assert len(re.findall(r'data-campo="dicas" data-hef-alvo="html"', html)) == 1
    for sobrou in ('class="sugestao"', 'class="ordem-tit"', 'data-campo="ordem"',
                   'class="col-exame"', 'data-campo="exame-calada"'):
        assert sobrou not in html, f"a bancada ainda tem {sobrou}: o quadro velho não saiu"


def test_o_lugar_que_o_bluez_ainda_nao_nomeou_nao_entra_na_frase() -> None:
    """No primeiro tique o BlueZ ainda não disse o adaptador (`sabido` falso): sem nome, sem cartão.

    A proposta volta no tique seguinte, quando os dois lugares têm nome; um cartão com o nome em
    branco diria «dividido em 1» de um adaptador que ninguém nomeou.
    """
    a08 = _a08()
    anonimo = {"id": "L2", "nome": "", "entrada": "", "sabido": False}
    esquerda = {"id": "L1", "nome": "Esquerda"}
    para_o_anonimo = {"proposta": {"controle": "ap", "destino": "L2"},
                      "lugares": [esquerda, anonimo],
                      "aparelhos": [{"id": "ap", "tipo": "controle", "lugar": "L1",
                                     "jogador": 2}]}
    assert a08._o_painel_das_dicas([], para_o_anonimo).vazio
    do_anonimo = {**para_o_anonimo, "proposta": {"controle": "ap", "destino": "L1"},
                  "aparelhos": [{"id": "ap", "tipo": "controle", "lugar": "L2", "jogador": 2}]}
    assert a08._o_painel_das_dicas([], do_anonimo).vazio
