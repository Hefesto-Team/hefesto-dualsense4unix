"""D-2511-O-ARRANJO-JULGA-PELO-QUE-ESTA-MAQUINA-LEU-E-RESPONDEU: o arranjo julga pelo que leu.

O motor trazia duas frases da máquina de teste de 24/08 como se fossem leitura desta: o dongle no
«hub» do barramento ganhava +60 e «no alto do rack», o do gabinete ficava «na altura da
escrivaninha», e a linha do Wi-Fi no hub escrevia os caminhos `4-1` e `4-1.1` de lá. A altura vem
da resposta de quem usa (`mesa.altura_da_antena`), e o caminho, da leitura.

MORDIDAS: devolver `p.onde == "hub"` à regra do dongle, o literal «alto do rack» ao veredito ou
os caminhos de 24/08 à linha do Wi-Fi reprova o caso que o nomeia.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from tests.unit import mesa_do_mockup as mock
from tests.unit.test_arranjo_da_mesa_bate_com_o_mockup import (
    _mesa,
    _receita_do_ouro,
    _veredito,
    como_o_mockup_planeja,
    como_o_mockup_receita,
    ouro,
)

ALTURAS = ("acima", "abaixo", None)
PALAVRAS_DE_24_08 = ("rack", "escrivaninha", "5000M", "4-1")


def _julga_o_dongle(entrada: str, altura: str | None) -> motor.Veredito | None:
    mesa = _mesa(altura=altura)
    achada = motor.por_num(mesa.faces, entrada)
    assert achada is not None
    return motor.julgar(achada, "bt", mesa)


def _texto_de_tudo(altura: str | None) -> str:
    mesa = _mesa(altura=altura)
    partes: list[str] = []
    for entrada in motor.todas_as_entradas(mesa.faces):
        veredito = motor.julgar(entrada, "bt", mesa)
        if veredito is not None:
            partes.append(veredito.porque)
    for movimento in motor.receita(mesa):
        partes.append(movimento.titulo)
        partes.extend(linha.texto for linha in movimento.linhas)
    partes.extend(motor.consequencias(mesa))
    plano = motor.planejar(mesa)
    for motivo in plano.motivo.values():
        partes.extend(razao.texto for razao in motivo.razoes)
    return "\n".join(partes)


@pytest.mark.parametrize("altura", ALTURAS, ids=str)
def test_o_motor_diz_o_mesmo_do_javascript_em_cada_resposta(altura: str | None) -> None:
    """D-2511-O-ARRANJO-JULGA-PELO-QUE-ESTA-MAQUINA-LEU-E-RESPONDEU: porte e página iguais.

    O ouro vem da página do mapa rodada em `node` com a altura trocada: plano, receita, o que
    se perde e o veredito de quatro entradas livres dizem o mesmo no Python e no JavaScript.
    """
    mesa = _mesa(altura=altura)
    chave = f"altura/{'null' if altura is None else altura}"
    assert como_o_mockup_planeja(motor.planejar(mesa)) == ouro(f"{chave}/planejar")
    assert como_o_mockup_receita(motor.receita(mesa)) == _receita_do_ouro(f"{chave}/receita")
    assert motor.consequencias(mesa) == ouro(f"{chave}/consequencias")
    for n in ("3", "5", "11", "13"):
        assert _veredito(_julga_o_dongle(n, altura)) == ouro(f"{chave}/julgar/{n}")


def test_sem_resposta_o_hub_do_barramento_nao_ganha_o_alto_nem_a_frase() -> None:
    """D-2511-O-ARRANJO-JULGA-PELO-QUE-ESTA-MAQUINA-LEU-E-RESPONDEU: sem resposta, sem altura.

    Com `altura_da_antena=None` o dongle numa entrada do hub não ganha os +60 nem «Melhor
    lugar», e nenhuma frase do arranjo traz o rack, a escrivaninha ou os caminhos de 24/08.
    """
    for entrada in ("3", "11", "13"):
        veredito = _julga_o_dongle(entrada, None)
        assert veredito is not None
        assert (veredito.v, veredito.texto, veredito.porque) == (
            "serve", "Serve", motor.FRASE_SEM_ALTURA), entrada
    assert not any(
        razao.texto == motor.FRASE_DA_ALTURA["acima"]
        for motivo in motor.planejar(_mesa(altura=None)).motivo.values()
        for razao in motivo.razoes
    )
    texto = _texto_de_tudo(None)
    for palavra in PALAVRAS_DE_24_08:
        assert palavra not in texto, palavra


def test_com_a_resposta_a_frase_segue_o_que_foi_respondido() -> None:
    """D-2511-O-ARRANJO-JULGA-PELO-QUE-ESTA-MAQUINA-LEU-E-RESPONDEU: a frase repete a resposta.

    `abaixo` diz «Serve» e «abaixo da cabeça, como você disse» em toda entrada livre, hub ou
    gabinete; `acima` diz «Melhor lugar» e conta o bônus de +60 entre as razões.
    """
    for entrada in ("3", "11", "13"):
        abaixo = _julga_o_dongle(entrada, "abaixo")
        acima = _julga_o_dongle(entrada, "acima")
        assert abaixo is not None and acima is not None
        assert (abaixo.v, abaixo.porque) == ("serve", motor.FRASE_DA_ALTURA["abaixo"])
        assert (acima.v, acima.porque) == ("melhor", motor.FRASE_DA_ALTURA["acima"])
    assert "abaixo da cabeça" in " ".join(motor.consequencias(_mesa(altura="abaixo")))
    assert "cabeça" not in " ".join(motor.consequencias(_mesa(altura="acima")))
    razoes = [
        razao.texto
        for motivo in motor.planejar(_mesa(altura="acima")).motivo.values()
        for razao in motivo.razoes
    ]
    assert motor.FRASE_DA_ALTURA["acima"] in razoes


def test_o_wifi_num_hub_traz_o_caminho_lido_aqui_e_nao_o_de_24_08() -> None:
    """D-2511-O-ARRANJO-JULGA-PELO-QUE-ESTA-MAQUINA-LEU-E-RESPONDEU: o caminho é o da leitura."""
    mapa: dict[str, Any] = {**mock.MAPA, "11": "7-2.3"}
    leitura = {**mock.LEITURA_ANTES, "wifi": "7-2.3"}
    mesa = _mesa(mapa=mapa, leitura=leitura)
    linhas = [
        linha for movimento in motor.receita(mesa) for linha in movimento.linhas
        if "no hub" in linha.texto and "tráfego" in linha.texto
    ]
    assert linhas, "o Wi-Fi no hub não gerou a linha de hoje"
    assert any("7-2.3" in linha.texto and linha.selo == motor.SELO_MEDIDO for linha in linhas)
    for linha in linhas:
        assert "4-1" not in linha.texto and "5000M" not in linha.texto, linha.texto


def test_o_wifi_num_hub_sem_caminho_lido_perde_os_numeros_e_o_selo_medido() -> None:
    """D-2511-O-ARRANJO-JULGA-PELO-QUE-ESTA-MAQUINA-LEU-E-RESPONDEU: sem leitura, sem «medido»."""
    mesa = _mesa(mapa={**mock.MAPA, "11": "7-2.3"}, leitura={
        chave: caminho for chave, caminho in mock.LEITURA_ANTES.items() if chave != "wifi"})
    aparelho = next(a for a in mesa.aparelhos if a.classe == "wifi")
    linha = motor._linha_de_hoje(mesa, aparelho, "11")
    assert linha.selo == motor.SELO_DERIVADO
    assert "<code>" not in linha.texto and "5000M" not in linha.texto


def test_o_exemplo_da_pagina_e_o_mapa_sao_a_mesma_resposta() -> None:
    """D-2511-O-ARRANJO-JULGA-PELO-QUE-ESTA-MAQUINA-LEU-E-RESPONDEU: a mesa do exemplo responde."""
    assert mock.ALTURA_DO_EXEMPLO == "abaixo"
    assert mock.mesa().altura == "abaixo"
    assert motor.Mesa(aparelhos=(), faces=(), mapa={}, leitura={}).altura is None
