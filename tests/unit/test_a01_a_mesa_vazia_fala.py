#!/usr/bin/env python3
"""A frase por cima dos lugares apagados, e o `+N` do quinto controle.

DECISÃO DELA — 04/09/2026, D-07: *"Uma frase por cima dos lugares apagados."*, e
*"o `+N` do quinto entra na mesma linha"*.

A de 31/08 fica de pé — **os lugares continuam**: *"Vamos deixar os outros dois
controles desconectados, só colocamos algo como `-` nos campos que deveriam ter
algo e escurecemos tudo."* O que muda é o estado vazio deixar de ser MUDO.

OS DOIS ESTADOS SÃO A MESMA CONTRADIÇÃO PELOS DOIS LADOS:

* mesa VAZIA — quatro lugares apagados e nenhuma palavra;
* mesa MAIOR QUE A TELA — o cabeçalho conta cinco, a fileira mostra quatro, e
  `hefesto_vivo.pintar` procura `[data-controle="p5"]`, não acha e segue **sem
  contar pintura nem erro**.
"""
from __future__ import annotations

import pathlib
import re
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


# ---------------------------------------------------------------------------
# 1. A MESA VAZIA
# ---------------------------------------------------------------------------
def test_com_a_mesa_vazia_a_aba_diz_alguma_coisa() -> None:
    """Era o estado MUDO: quatro cartões apagados e nenhuma palavra.

    A MORDIDA: troque o `if quantos == 0: return MESA_VAZIA` por `return ""` e
    a aba volta ao silêncio — reprova aqui.
    """
    fora = aba.pacote(_ctx(0))
    assert fora["mesa-frase"] == aba.MESA_VAZIA
    assert fora["mesa-frase"], "a mesa vazia voltou a ser muda"


def test_com_a_mesa_cheia_a_linha_nao_existe() -> None:
    """Zero pixel na cena que ela aprovou — dois controles na mesa.

    A frase vazia vira travessão no piloto, e o alvo `classe` do elemento de
    fora lê travessão como desligado: a linha some sozinha.

    A MORDIDA: devolva `MESA_VAZIA` sempre e a linha laranja passa a nascer em
    toda tela normal, mudando o desenho aprovado.
    """
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


# ---------------------------------------------------------------------------
# 2. O `+N` DO QUINTO
# ---------------------------------------------------------------------------
def test_com_cinco_controles_a_tela_conta_os_que_nao_cabem() -> None:
    """O quinto sumia calado e a MESMA tela afirmava dois números.

    A MORDIDA: apague o ramo `if quantos > lugares` e a contradição volta — o
    cabeçalho dizendo "5 controles" e a fileira mostrando 4, sem uma palavra.
    """
    frase = aba.pacote(_ctx(5))["mesa-frase"]
    assert "5" in frase and "4" in frase, (
        f"a frase do quinto não diz os dois números: {frase!r}")


def test_o_numero_de_lugares_se_le_do_desenho() -> None:
    """Cravar `4` poria nesta frase o mesmo defeito que ela denuncia.

    A MORDIDA: troque `lugares_da_mesa()` por um `4` literal e esta régua
    reprova assim que o desenho mudar de tamanho — que é o dia em que a frase
    passaria a mentir sem ninguém ver.
    """
    assert aba.lugares_da_mesa() == len(monta.MESA)


# ---------------------------------------------------------------------------
# 3. A PÁGINA TEM ONDE ESCREVER — os dois elementos, e o de fora apagado
# ---------------------------------------------------------------------------
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
    """A frase da mesa vazia já existia — e no lugar errado.

    `interface/jogar_vivo.py` (a BANCADA desta aba) escreve esta mesma sentença
    desde que nasceu, e o PRODUTO — a página estática, que é a que ela abre —
    não a tinha. A cópia em `a01_jogar.MESA_VAZIA` é a mesma sequência de bytes
    de propósito, e esta régua reprova no dia em que as duas se afastarem.

    O FECHO É DE UMA LINHA e é de quem cuidar do `jogar_vivo.py`: importar
    `a01_jogar.MESA_VAZIA` em vez de repetir a frase. Enquanto isso não
    acontece, a régua é o que impede duas verdades vivas.
    """
    fonte = (INTERFACE / "jogar_vivo.py").read_text(encoding="utf-8")
    # As quebras de linha do fonte não contam: o que tem de bater é a FRASE.
    achatado = re.sub(r'"\s*\n\s*"', "", fonte)
    assert aba.MESA_VAZIA in achatado, (
        "a frase da mesa vazia da bancada (`jogar_vivo.py`) e a do produto "
        "(`a01_jogar.MESA_VAZIA`) se afastaram — são duas verdades vivas")
