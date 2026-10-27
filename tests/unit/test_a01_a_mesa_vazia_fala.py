#!/usr/bin/env python3
"""A frase por cima dos lugares apagados, e o `+N` do quinto controle."""
from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"


for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import monta
from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a01_jogar as aba

VIVO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "paused": False,
}


def _ctx(quantos: int) -> Contexto:
    """Um contexto com `quantos` controles na mesa — e o `state` de pé."""
    conectados = [
        {"uniq": f"aa:bb:cc:00:00:{i:02x}", "connected": True, "player_slot": i}
        for i in range(1, quantos + 1)
    ]
    return Contexto(state={**VIVO, "controllers": conectados}, mesa=[],
                    conectados=conectados, estados={})


def test_com_a_mesa_vazia_a_linha_nao_existe() -> None:
    """Os quatro lugares «Desconectado» já dizem; a frase por cima saiu por ordem (19/10/2026)."""
    assert aba.pacote(_ctx(0))["mesa-frase"] == "", "a frase da mesa vazia voltou"


def test_com_a_mesa_cheia_a_linha_nao_existe() -> None:
    """Zero pixel na cena que o usuário aprovou — dois controles na mesa."""
    for quantos in (1, 2, 3, 4):
        assert aba.pacote(_ctx(quantos))["mesa-frase"] == "", (
            f"a linha da mesa vazia apareceu com {quantos} controle(s)")


def test_sem_daemon_a_aba_nao_afirma_que_a_mesa_esta_vazia() -> None:
    """`conectados` vazio pode ser "não há" ou "ninguém respondeu".

    É a mesma guarda do `_estado_da_tela`, e ela é a armadilha desta aba:
    escrever "nenhum controle na mesa" sobre um tique sem resposta é a tela
    afirmando o que não leu. Com o serviço parado a mesa também não escreve que ele parou
    (20/10/2026): o Status em Desligado é o único sinal.

    A MORDIDA: faça o `if not ctx.state` de `_frase_da_mesa` devolver uma frase e a aba escreve
    sobre o engasgo de IPC; tire o `if not ctx.state` e a mesa vazia lê como "há 0 controles".
    """
    vazio = Contexto(state={}, mesa=[], conectados=[], estados={})
    fora = aba.pacote(vazio)
    assert fora["mesa-frase"] == ""
    assert fora["hef-posicao"] == aba.POSICAO_COM_O_SERVICO_PARADO


def test_com_cinco_controles_a_tela_conta_os_que_nao_cabem() -> None:
    """O quinto sumia calado e a MESMA tela afirmava dois números."""
    frase = aba.pacote(_ctx(5))["mesa-frase"]
    assert "5" in frase and "4" in frase, (
        f"a frase do quinto não diz os dois números: {frase!r}")


def test_o_numero_de_lugares_se_le_do_desenho() -> None:
    """Cravar `4` poria nesta frase o mesmo defeito que ela denuncia."""
    assert aba.lugares_da_mesa() == len(monta.MESA)


def test_a_pagina_publica_os_dois_elementos_da_linha() -> None:
    """Um `data-campo`, DOIS elementos: o que acende e o que escreve.

    Só o de fora e a linha aparece VAZIA (o piloto escreve o travessão no texto
    que não existe); só o de dentro e ela fica ACESA PARA SEMPRE, dizendo
    "nenhum controle na mesa" com dois controles na mesa.

    A MORDIDA: tire o `data-hef-alvo="classe"` do `<div class="mesa-notas">` no
    `aba01.MIOLO`, regere, e o `_conferir` do gerador reprova ANTES desta régua
    — que é o lugar certo para essa notícia.
    """
    corpo = onde.pagina("01-jogar.html", publicado=True).read_text(encoding="utf-8")
    for campo in ("mesa-frase", "mascara-ressalva"):
        assert corpo.count(f'data-campo="{campo}"') == 2, (
            f"{campo}: a página não tem o par que acende e escreve")
    assert 'class="mesa-notas ha"' not in corpo, (
        "uma linha por cima dos lugares nasce acesa — ela mudaria a cena que "
        "ela aprovou, que tem a mesa cheia")

