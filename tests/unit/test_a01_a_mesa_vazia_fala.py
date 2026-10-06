#!/usr/bin/env python3
"""A frase por cima dos lugares apagados, e o `+N` do quinto controle."""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

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


def test_com_a_mesa_vazia_a_aba_diz_alguma_coisa() -> None:
    """Era o estado MUDO: quatro cartões apagados e nenhuma palavra."""
    fora = aba.pacote(_ctx(0))
    assert fora["mesa-frase"] == aba.MESA_VAZIA
    assert fora["mesa-frase"], "a mesa vazia voltou a ser muda"


def test_com_a_mesa_cheia_a_linha_nao_existe() -> None:
    """Zero pixel na cena que o usuário aprovou — dois controles na mesa."""
    for quantos in (1, 2, 3, 4):
        assert aba.pacote(_ctx(quantos))["mesa-frase"] == "", (
            f"a linha da mesa vazia apareceu com {quantos} controle(s)")


def test_sem_daemon_a_aba_nao_afirma_que_a_mesa_esta_vazia() -> None:
    """`conectados` vazio pode ser "não há" ou "ninguém respondeu".

    É a mesma guarda do `_estado_da_tela`, e ela é a armadilha desta aba:
    escrever "nenhum controle na mesa" sobre um tique sem resposta é a tela
    afirmando o que não leu.

    A MORDIDA: apague o `if not ctx.state: return ""` e a aba passa a acusar
    mesa vazia num engasgo de IPC.
    """
    vazio = Contexto(state={}, mesa=[], conectados=[], estados={})
    assert aba.pacote(vazio)["mesa-frase"] == ""


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
    corpo = onde.pagina("01-jogar.html").read_text(encoding="utf-8")
    for campo in ("mesa-frase", "mascara-ressalva"):
        assert corpo.count(f'data-campo="{campo}"') == 2, (
            f"{campo}: a página não tem o par que acende e escreve")
    assert 'class="mesa-notas ha"' not in corpo, (
        "uma linha por cima dos lugares nasce acesa — ela mudaria a cena que "
        "ela aprovou, que tem a mesa cheia")


def test_o_gemeo_da_bancada_ainda_bate() -> None:
    """A frase da mesa vazia tem UM DONO, e a bancada o usa."""
    fonte = (INTERFACE / "jogar_vivo.py").read_text(encoding="utf-8")
    achatado = re.sub(r'"\s*\n\s*"', "", fonte)
    sem_comentario = re.sub(r"#[^\n]*", "", achatado)
    usa_o_dono = bool(re.search(r"\bMESA_VAZIA\b", sem_comentario))
    tem_a_copia = aba.MESA_VAZIA in sem_comentario
    assert usa_o_dono or tem_a_copia, (
        "a bancada (`jogar_vivo.py`) não usa `a01_jogar.MESA_VAZIA` nem repete a "
        "frase dele — se ela tem uma frase própria para a mesa vazia, são duas "
        "verdades vivas sobre a mesma tela")
    if usa_o_dono and tem_a_copia:
        raise AssertionError(
            "a bancada importa `MESA_VAZIA` E ainda tem a frase digitada — "
            "a cópia sobrou do fecho e vai divergir na próxima edição")
