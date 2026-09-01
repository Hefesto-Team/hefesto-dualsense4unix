#!/usr/bin/env python3
"""A RÉGUA DO "A luz não acende": ele derruba o rádio, e recusa no cabo.

O BOTÃO cura um defeito real do Bluetooth: a barra de luz para de obedecer, e o
caminho de volta é a RECONEXÃO — cair do rádio e entrar de novo pelo PS.

POR QUE ELE PRECISA DE RÉGUA PRÓPRIA: ele não fala com o daemon. A régua dos
botões passa um dublê de PONTE e cobra qual função foi chamada; este gesto chama
`integrations/gesto_de_reconexao.desconectar`, que fala D-Bus. Uma prova que só
olhasse a ponte diria que ele não faz nada.

AS TRÊS COISAS QUE ELA COBRA:

1. **No cabo, RECUSA.** O `title` do botão apagado promete isso com todas as
   letras — *"Este controle está no cabo, onde a barra de luz não depende de
   reconexão nenhuma"*. Um botão que aceita o clique e não derruba nada é o que
   responde calado.
2. **`ja_estava_fora` É SUCESSO.** A linha é do módulo: *"para quem espera o
   botão PS, os dois estados pedem exatamente o mesmo gesto"*. Tratá-lo como
   falha faria a tela acusar erro num controle que já está pronto para o PS.
3. **`nao_deu` LEVANTA com a frase do módulo.** Um `False` ali significa "não
   sei", e quem chama não pode fingir que significa "não caiu".

A MORDIDA: tire a guarda do transporte — o caso 1 reprova dizendo que o botão
aceitou derrubar um controle que está no cabo.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: Faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def gesto(pac):
    fn = pac.gesto_da_pagina("08-conexoes.html", "luz-nao-acende")
    assert fn is not None, "08-conexoes.html:luz-nao-acende perdeu o dono"
    return fn


def _ctx(pac, transporte: str):
    dele = {"uniq": UNIQ, "transport": transporte, "connected": True}
    return pac.Contexto(state={"controllers": [dele]}, mesa=[], conectados=[dele],
                        estados={})


def test_no_cabo_recusa_dizendo(pac, gesto, monkeypatch) -> None:
    """E não chega a pedir nada ao BlueZ — a recusa vem ANTES do subprocesso."""
    from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio

    pediu: list[str] = []
    monkeypatch.setattr(radio, "desconectar",
                        lambda mac, **_: pediu.append(mac))

    with pytest.raises(RuntimeError) as erro:
        gesto(_ctx(pac, "usb"), {"uniq": UNIQ}, None)

    frase = str(erro.value)
    assert "cabo" in frase.lower(), f"a recusa não diz que é do cabo: {frase!r}"
    assert pediu == [], (
        "o gesto recusou e AINDA ASSIM falou com o BlueZ — a guarda tem de vir "
        "antes do subprocesso, senão ela é decoração")


def test_no_radio_pede_o_disconnect(pac, gesto, monkeypatch) -> None:
    from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio

    pediu: list[str] = []

    def falso(mac: str, **_: Any) -> radio.Resultado:
        pediu.append(mac)
        return radio.Resultado(radio.ESTADO_DESCONECTOU, radio.FRASE_DESCONECTOU, "…")

    monkeypatch.setattr(radio, "desconectar", falso)
    gesto(_ctx(pac, "bt"), {"uniq": UNIQ}, None)
    assert pediu == [UNIQ], f"pediu {pediu}, esperava o uniq do controle clicado"


def test_ja_estava_fora_conta_como_sucesso(pac, gesto, monkeypatch) -> None:
    """A linha é do módulo: os dois estados pedem o MESMO gesto dela (apertar PS)."""
    from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio

    monkeypatch.setattr(
        radio, "desconectar",
        lambda mac, **_: radio.Resultado(
            radio.ESTADO_JA_ESTAVA_FORA, radio.FRASE_JA_ESTAVA_FORA, "…"))
    gesto(_ctx(pac, "bt"), {"uniq": UNIQ}, None)  # não levanta


@pytest.mark.parametrize("estado", ["ESTADO_NAO_DEU", "ESTADO_SEM_ALVO"])
def test_o_que_nao_caiu_levanta_com_a_frase_do_produto(
    pac, gesto, monkeypatch, estado: str,
) -> None:
    """A frase é a que o módulo escreveu para ela, não uma minha.

    Reescrevê-la aqui seria a segunda verdade: o módulo tem quatro frases em
    português, pensadas para quem está com o controle na mão.
    """
    from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio

    codigo = getattr(radio, estado)
    frase = getattr(radio, estado.replace("ESTADO_", "FRASE_"))
    monkeypatch.setattr(radio, "desconectar",
                        lambda mac, **_: radio.Resultado(codigo, frase, "…"))
    with pytest.raises(RuntimeError) as erro:
        gesto(_ctx(pac, "bt"), {"uniq": UNIQ}, None)
    assert str(erro.value) == frase, (
        f"o gesto disse {str(erro.value)!r} e o produto diz {frase!r}")


def test_clique_solto_recusa(pac, gesto) -> None:
    """A luz é de um aparelho, não da mesa. Sem `uniq`, não há alvo."""
    with pytest.raises(ValueError):
        gesto(_ctx(pac, "bt"), {}, None)


def test_o_endereco_nunca_sai_inteiro() -> None:
    """O módulo mascara, e é dele que a frase vem.

    NESTA CASA ISSO É PORTÃO: dois deles reprovam um MAC de doze hexa em
    arquivo versionado, e uma exceção de tela vira log. O caso mede a garantia
    na origem, que é onde ela não depende de quem chama lembrar.
    """
    from hefesto_dualsense4unix.integrations.gesto_de_reconexao import mascarar

    mascarado = mascarar("aa:bb:cc:dd:ee:ff")
    assert "dd" not in mascarado.lower() and "ee" not in mascarado.lower(), (
        f"o quarto e o quinto octeto sobreviveram à máscara: {mascarado!r}")
