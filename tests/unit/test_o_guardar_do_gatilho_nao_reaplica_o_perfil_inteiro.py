#!/usr/bin/env python3
"""A RÉGUA DO ESCOPO DA GRAVAÇÃO DO GATILHO: o clique grava, e não reaplica a mesa.

O DEFEITO QUE ELA FECHA, medido em 03/09/2026 clicando o produto INSTALADO com
um DualSense no cabo. O gesto terminava em `perfil.gravar_e_reaplicar`, que
termina em `p.profile_switch(...)` — o daemon aplica o perfil INTEIRO. Com a
barra de luz apagada antes e UM gesto só (`--prova-clique guardar`):

    antes   lightbar_on: false · lightbar_rgb: [0, 0, 0]
    depois  lightbar_on: true  · lightbar_rgb: [0, 0, 255]

Ela desliga a barra na aba Iluminação, vai aos Gatilhos, clica "Guardar esse
efeito" — e a barra acende. Um botão cujo nome promete UM efeito desfazendo
escolha viva dela em outra aba, calado.

POR QUE A REAPLICAÇÃO NÃO FAZ FALTA: esta aba aplica NA HORA (decisão de
01/09, *"clicar já aplica"*): o clique já mandou o efeito ao aparelho, e o
`profile_switch` reaplicaria por cima um gatilho que já estava lá, levando junto
nove seções que ninguém pediu.

DESDE 15/10/2026 O «Guardar esse efeito» SAIU com o desenho do todo, e a gravação
mora no próprio clique (`modo` e `imersao`, pelo `_gravar_so_o_gatilho`). A régua
mede o mesmo caminho de disco pelo `modo`.

AS TRÊS COISAS QUE ESTA RÉGUA COBRA:

1. **Grava.** Tirar o `profile_switch` não pode ter tirado a gravação junto.
2. **Não chama `profile_switch`.** É a cura.
3. **Chama `launch_env.refresh`.** É a metade que tinha de sobreviver: sem ela o
   perfil novo só chega ao jogo no próximo start do daemon.

A MORDIDA: devolva `perfil.gravar_e_reaplicar(novo, ctx, p)` no lugar de
`_gravar_so_o_gatilho(novo, p)` — o caso 2 reprova dizendo que o clique mandou
o daemon reaplicar o perfil inteiro.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

UNIQ = "aa:bb:cc:00:00:01"


class PonteDeMentira:
    """A ponte que ANOTA o que lhe pediram, para a régua ler o escopo."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append("profile_switch")
        return True

    def chamar(self, metodo: str, **_: Any) -> bool:
        self.chamadas.append(metodo)
        return True

    def trigger_set_detalhado(self, *_a: Any, **_k: Any) -> tuple[bool, str, dict]:
        self.chamadas.append("trigger_set_detalhado")
        return (True, "", {"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []})


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def gesto(pac):
    fn = pac.gesto_da_pagina("03-gatilhos.html", "modo")
    assert fn is not None, "03-gatilhos.html:modo perdeu o dono"
    return fn


@pytest.fixture
def disco(monkeypatch):
    """Um disco de mentira com um `Profile` DE VERDADE dentro."""
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import Profile

    estado = {"Mortal Kombat": Profile(name="Mortal Kombat", match={"type": "any"})}
    gravados: list[Any] = []
    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n], raising=False)
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **_: gravados.append(prof), raising=False)
    return estado, gravados


def _ctx(pac):
    dele = {"uniq": UNIQ, "transport": "usb", "connected": True}
    return pac.Contexto(state={"active_profile": "Mortal Kombat",
                               "controllers": [dele]},
                        mesa=[], conectados=[dele], estados={})


def _clique() -> dict[str, str]:
    """Um modo NOVO no L2, para haver o que gravar."""
    return {"uniq": UNIQ, "lado": "e", "valor": "Rigid"}


def test_o_clique_grava_no_disco(pac, gesto, disco) -> None:
    """Caso 1: tirar a reaplicação não pode ter levado a gravação junto."""
    _, gravados = disco
    gesto(_ctx(pac), _clique(), PonteDeMentira())
    assert len(gravados) == 1, (
        f"o clique gravou {len(gravados)} vez(es)")


def test_o_clique_nao_manda_reaplicar_o_perfil_inteiro(pac, gesto, disco) -> None:
    """Caso 2, A CURA: `profile_switch` reaplica a barra de luz por cima dela."""
    p = PonteDeMentira()
    gesto(_ctx(pac), _clique(), p)
    assert "profile_switch" not in p.chamadas, (
        "o clique do gatilho mandou o daemon REAPLICAR o perfil inteiro "
        f"(chamadas={p.chamadas}). Isso reacende a barra de luz que ela apagou "
        "na aba Iluminação — um botão de escopo estreito desfazendo escolha "
        "viva dela em outra aba, calado. Esta aba já aplica na hora; não há "
        "gatilho a reaplicar aqui.")


def test_o_clique_avisa_a_antecipacao_de_lancamento(pac, gesto, disco) -> None:
    """Caso 3: sem isto o perfil novo só chega ao jogo no próximo start."""
    p = PonteDeMentira()
    gesto(_ctx(pac), _clique(), p)
    assert "launch_env.refresh" in p.chamadas, (
        f"o clique gravou e não releu o que os jogos recebem (chamadas={p.chamadas})")
