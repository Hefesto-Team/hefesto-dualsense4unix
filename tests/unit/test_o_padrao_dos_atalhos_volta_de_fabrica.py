#!/usr/bin/env python3
"""A régua do «Voltar ao padrão» da aba Navegação: o mouse e o teclado voltam UM DEGRAU.

O gesto `padrao-da-aba` (que substituiu o `padrao-definicoes` em 15/10/2026) lê e grava em disco,
e só depois pede a releitura ao daemon; uma prova que olhasse só a ponte diria que ele funciona
mesmo com o disco errado. Aqui o disco é o lar de mentira da suíte, e as três coisas que ele cobra:

1. **Sem perfil ativo, o computador volta ao de fábrica**: os atalhos (`key_bindings`,
   `button_actions`) e o teclado voltam a `None`, que é «herda o de fábrica» (`{}` calaria o
   controle), e os gestos são declarados de volta à máquina.
2. **Com um jogo que escolheu, volta o que o jogo escolheu, não o computador.** O degrau de baixo
   só vale quando o perfil nada sobrepõe.
3. **Se o daemon recusar os gestos, a tela diz por quê** em vez de calar.

MORDIDAS: trocar o `voltar_o_computador_ao_de_fabrica` por nada reprova o caso 1; tirar o
`voltar_ao_do_computador` reprova o caso 2; engolir o `ok` do `machine_declare` reprova o 3.
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

    def __init__(self, *, aceita_os_gestos: bool = True) -> None:
        self.chamadas: list[tuple[str, Any]] = []
        self.aceita = aceita_os_gestos

    def machine_declare(self, dados: dict[str, Any]) -> Any:
        self.chamadas.append(("machine_declare", dados))
        return (True, None) if self.aceita else (False, "o daemon não respondeu")

    def resultado(self, metodo: str, **params: Any) -> dict[str, Any]:
        self.chamadas.append((metodo, params))
        return {"status": "ok"}

    def profile_reaplicar(self, nome: str, *, prender: bool = False) -> bool:
        self.chamadas.append(("profile_reaplicar", nome))
        return True

    def chamar(self, metodo: str, **_: Any) -> bool:
        self.chamadas.append((metodo, None))
        return True


@pytest.fixture
def gesto() -> Any:
    import pacotes

    fn = pacotes.gesto_da_pagina("06-navegacao.html", "padrao-da-aba")
    assert fn is not None, "06-navegacao.html:padrao-da-aba perdeu o dono"
    return fn


def _ctx(ativo: str) -> Any:
    import pacotes

    return pacotes.Contexto(state={"active_profile": ativo}, mesa=[], conectados=[], estados={})


def test_sem_perfil_ativo_quem_volta_e_o_computador(gesto: Any) -> None:
    """Os atalhos são do COMPUTADOR: sem perfil, ele volta, e os gestos são declarados."""
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from hefesto_dualsense4unix.utils.maquina import gravar_o_computador

    assert gravar_o_computador({"global": {
        "key_bindings": {"r1": ["KEY_F11"]}, "button_actions": {"cross": "KEY_ENTER"},
        "teclado_emulado": True, "teclado_sempre": True}})
    ponte = PonteDeMentira()
    gesto(_ctx(""), {}, ponte)
    do_global = o_computador().global_
    assert do_global.key_bindings is None and do_global.button_actions is None
    assert do_global.teclado_emulado is None and do_global.teclado_sempre is None
    assert any(c[0] == "machine_declare" for c in ponte.chamadas), ponte.chamadas
    assert any(c[0] == "mouse.emulation.set" for c in ponte.chamadas), ponte.chamadas


def test_com_jogo_que_escolheu_volta_o_do_jogo_e_o_computador_fica(gesto: Any) -> None:
    """Degrau de cima: o jogo perde a escolha dele, e o que o computador diz continua."""
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.utils.maquina import gravar_o_computador

    assert gravar_o_computador({"global": {"key_bindings": {"l1": ["KEY_F5"]}}})
    loader.save_profile(Profile(
        name="Mortal Kombat", match=MatchManual(), key_bindings={"r1": ["KEY_F11"]},
        teclado_emulado=True, teclado_sempre=True))
    ponte = PonteDeMentira()
    gesto(_ctx("Mortal Kombat"), {}, ponte)
    depois = loader.load_profile("Mortal Kombat")
    assert not depois.key_bindings and not depois.teclado_sempre, (
        f"o jogo manteve a escolha dele: {depois.key_bindings} {depois.teclado_sempre}")
    assert o_computador().global_.key_bindings == {"l1": ["KEY_F5"]}, (
        "o degrau de baixo foi dado com o jogo escolhendo: o computador também voltou")


def test_sem_o_daemon_a_tela_diz_por_que_os_gestos_nao_voltaram(gesto: Any) -> None:
    """Gravou o disco e o daemon não aceitou os gestos: o clique recusa dizendo."""
    with pytest.raises(RuntimeError) as erro:
        gesto(_ctx(""), {}, PonteDeMentira(aceita_os_gestos=False))
    assert "os gestos não" in str(erro.value), str(erro.value)


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
