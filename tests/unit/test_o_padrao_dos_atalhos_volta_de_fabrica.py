#!/usr/bin/env python3
"""A RÉGUA DO "Voltar ao padrão" da aba Navegação — e do que ele NÃO pode fazer.

O BOTÃO promete devolver ao de fábrica as 21 linhas de *o que cada botão faz*. A
rota é gravar `key_bindings = None` no perfil ATIVO e mandar o daemon reaplicar.

POR QUE ELE PRECISA DE RÉGUA PRÓPRIA, e não de uma linha em `PROVAS`: a régua
dos botões passa um dublê de ponte e cobra QUAL função foi chamada. Este gesto
não fala com o daemon primeiro — ele **lê e grava um perfil em disco**, e só
depois pede o `profile.switch`. Uma prova que só olhasse a ponte diria que ele
funciona mesmo se o que fosse para o disco estivesse errado.

AS TRÊS COISAS QUE ELA COBRA, e cada uma é um jeito diferente de o botão mentir:

1. **`None`, e nunca `{}`.** O esquema define os dois: `None` é *"herda
   `DEFAULT_BUTTON_BINDINGS`"* e `{}` é *"desativa todos os bindings"*
   (`profiles/schema.py:985-987`). Gravar `{}` devolveria um controle MUDO com o
   botão dizendo "de fábrica" — o pior tipo de acerto aparente.
2. **Reaplicar.** Gravar sem `profile.switch` deixa a tela dizendo uma coisa e o
   aparelho fazendo outra até a próxima troca de perfil.
3. **Não fazer nada quando já está de fábrica.** Um `profile.switch` no meio de
   uma partida não é de graça, e regravar um perfil idêntico é barulho.

A MORDIDA: troque o `None` por `{}` no gesto — o caso 1 reprova dizendo que o
teclado ficaria mudo. Tire o `gravar_e_reaplicar` — o caso 2 reprova.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))


class PonteDeMentira:
    """Guarda o que foi pedido ao daemon, na ordem."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(("profile_switch", (nome,)))
        return True

    def chamar(self, metodo: str, **_: Any) -> bool:
        self.chamadas.append(("chamar", (metodo,)))
        return True


class PerfilDeMentira:
    """O mínimo de um `Profile` que este gesto toca: o nome e os bindings.

    O `model_copy` é o idioma do pydantic que o gesto usa, e o dublê o imita em
    vez de trazer o modelo de verdade: instanciar um `Profile` exigiria um
    `match` válido, e a régua passaria a medir o esquema em vez do botão.
    """

    def __init__(self, nome: str, key_bindings: dict[str, list[str]] | None) -> None:
        self.name = nome
        self.key_bindings = key_bindings

    def model_copy(self, *, update: dict[str, Any]) -> PerfilDeMentira:
        novo = PerfilDeMentira(self.name, self.key_bindings)
        for k, v in update.items():
            setattr(novo, k, v)
        return novo


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def gesto(pac):
    fn = pac.gesto_da_pagina("06-navegacao.html", "padrao-definicoes")
    assert fn is not None, "06-navegacao.html:padrao-definicoes perdeu o dono"
    return fn


@pytest.fixture
def disco(monkeypatch):
    """Um disco de mentira: guarda o que o gesto mandou gravar."""
    from hefesto_dualsense4unix.profiles import loader

    gravados: list[PerfilDeMentira] = []
    estado: dict[str, PerfilDeMentira] = {}

    def falso_load(nome: str) -> PerfilDeMentira:
        return estado[nome]

    def falso_save(prof: PerfilDeMentira, **_: Any) -> None:
        gravados.append(prof)

    monkeypatch.setattr(loader, "load_profile", falso_load, raising=False)
    monkeypatch.setattr(loader, "save_profile", falso_save, raising=False)
    return estado, gravados


def _ctx(pac, ativo: str):
    return pac.Contexto(state={"active_profile": ativo}, mesa=[], conectados=[], estados={})


def test_grava_none_e_nunca_dicionario_vazio(pac, gesto, disco) -> None:
    """`None` herda o de fábrica; `{}` cala o teclado. São coisas opostas."""
    estado, gravados = disco
    estado["Mortal Kombat"] = PerfilDeMentira("Mortal Kombat", {"r1": ["KEY_F11"]})
    p = PonteDeMentira()

    gesto(_ctx(pac, "Mortal Kombat"), {}, p)

    assert len(gravados) == 1, f"gravou {len(gravados)} vez(es), esperava uma"
    assert gravados[0].key_bindings is None, (
        f"gravou {gravados[0].key_bindings!r}. `None` herda o "
        f"`DEFAULT_BUTTON_BINDINGS`; `{{}}` DESLIGA todos os bindings "
        f"(`profiles/schema.py:985-987`) — o segundo devolveria um controle "
        f"mudo com o botão dizendo 'de fábrica'.")
    assert gravados[0].name == "Mortal Kombat", "gravou por cima de outro perfil"


def test_reaplica_o_perfil_ativo_e_relê_o_ambiente(pac, gesto, disco) -> None:
    """Gravar sem reaplicar deixa a tela e o aparelho dizendo coisas diferentes."""
    estado, _ = disco
    estado["Mortal Kombat"] = PerfilDeMentira("Mortal Kombat", {"r1": ["KEY_F11"]})
    p = PonteDeMentira()

    gesto(_ctx(pac, "Mortal Kombat"), {}, p)

    nomes = [c[0] for c in p.chamadas]
    assert "profile_switch" in nomes, (
        f"o gesto fez {nomes} e não pediu o `profile.switch`. O perfil mudou no "
        f"disco e o aparelho continua com os atalhos velhos até a próxima troca.")
    assert ("chamar", ("launch_env.refresh",)) in p.chamadas, (
        "o `launch_env.refresh` não foi pedido — o perfil novo só chegaria ao "
        "jogo no próximo start do daemon.")


def test_ja_de_fabrica_nao_mexe_em_nada(pac, gesto, disco) -> None:
    """Regravar um perfil idêntico é barulho, e o `switch` não é de graça."""
    estado, gravados = disco
    estado["Navegacao"] = PerfilDeMentira("Navegacao", None)
    p = PonteDeMentira()

    gesto(_ctx(pac, "Navegacao"), {}, p)

    assert gravados == [], "gravou um perfil que já estava de fábrica"
    assert p.chamadas == [], (
        f"pediu {p.chamadas} ao daemon sem ter o que mudar — um "
        f"`profile.switch` no meio de uma partida não é de graça.")


def test_sem_perfil_ativo_recusa_dizendo(pac, gesto, disco) -> None:
    """Os atalhos são do PERFIL, não da máquina. Sem perfil, não há o que zerar.

    E a recusa tem de DIZER: um botão que responde calado quando não há quem
    atenda é a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` em miniatura.
    """
    p = PonteDeMentira()
    with pytest.raises(RuntimeError) as erro:
        gesto(_ctx(pac, ""), {}, p)
    frase = str(erro.value)
    assert "perfil" in frase.lower(), f"a recusa não nomeia o perfil: {frase!r}"
    assert p.chamadas == [], "recusou e ainda assim falou com o daemon"


def test_as_nove_linhas_que_o_perfil_alcanca_sao_as_do_produto() -> None:
    """A conta que sustenta o botão: 9 de 21, e as 12 restantes são fixas.

    ELA NÃO SE DIGITA. Se `DEFAULT_BUTTON_BINDINGS` crescer, este caso reprova e
    obriga a REVER a frase do gesto — que hoje afirma, com todas as letras, que
    as outras 12 estão sempre de fábrica. É essa afirmação que faz o botão fechar
    inteiro, e ela é a primeira coisa que caducaria.
    """
    from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS

    assert len(DEFAULT_BUTTON_BINDINGS) == 9, (
        f"`DEFAULT_BUTTON_BINDINGS` tem {len(DEFAULT_BUTTON_BINDINGS)} botões e "
        f"a frase do gesto `padrao-definicoes` diz NOVE. Se ele cresceu, a "
        f"conta das 21 linhas mudou — releia o docstring do gesto antes de "
        f"mexer neste número.")
    esperados = {"options", "create", "l1", "r1", "l3", "r3",
                 "touchpad_left_press", "touchpad_middle_press",
                 "touchpad_right_press"}
    assert set(DEFAULT_BUTTON_BINDINGS) == esperados, (
        f"os botões que o perfil alcança mudaram: "
        f"{sorted(set(DEFAULT_BUTTON_BINDINGS) ^ esperados)}")
