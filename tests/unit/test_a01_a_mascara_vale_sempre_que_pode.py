#!/usr/bin/env python3
"""A máscara: ela vale sempre que PODE valer, e a tela para de ficar calada.

A QUEIXA É DO USUÁRIO, 04/09/2026, e é a primeira da lista:

    *"independente do modo a mascara deve funcionar ali sempre. E todas as
     demais features do programa também."*

O QUE FOI MEDIDO — e esta régua tranca cada fato:

1. **`gamepad.mask.set` grava SEMPRE**, sem gate de modo
   (`daemon/ipc_handlers.py:4022`); `set_mask` persiste em
   `controller_masks.json`; `mascara_efetiva` é consultada na criação de todo
   gamepad virtual (`gamepad.py:1322`, `uinput_gamepad.py:187`). **Logo a
   escolha do usuário JÁ vale sempre que pode valer** — o motor estava pronto;
2. o que faltava era a TELA dizer isso. Fora do modo `gamepad` não existe vpad,
   então o clique era aceito, gravado, e não mudava nada que se visse — que é
   exatamente o que ela sente como *"não funciona"*;
3. o chip **Nintendo Pro** recusa em TODO modo: `mascaras_validas()` devolve
   `{dualsense, xbox}`. Um botão que nunca funciona não pode parecer que
   funciona.

AS DUAS CURAS SÃO DIFERENTES DE PROPÓSITO, e a diferença é a D-03 dela lida com
cuidado (*"cinza antes, com a razão na dica"*):

    a máscara fora do modo jogo   → RESSALVA. Ela PODE escolher agora, e a
                                    escolha vale quando o vpad nascer. Apagar o
                                    chip diria "você não pode escolher", que é
                                    falso — e trocaria a queixa de uso por outra
                                    pior.
    o Nintendo Pro                → CINZA. Ele nunca pode. É o caso em que o
                                    cinza é a verdade.

NOTA DATADA — 13/09/2026, JOGAR-A-FAIXA-QUE-PULA-01 §3.1: a RESSALVA saiu da
tela (*"em todas as abas da interface"*, TELA-CALADA-01). O motor que ela
anunciava continua trancado aqui; o que mudou de contrato é a metade 2.

NOTA DATADA — 28/10/2026, A-JOGAR-SE-PUBLICA-COM-OS-CONTROLES-E-A-02-SAI-01: o chip da
máscara saiu da Jogar com o cartão (a máscara é o modo único desde a D-2710, escolhido
na fileira do Status). Ficam o motor e o catálogo; as réguas do chip saíram com ele.
"""
from __future__ import annotations

import pathlib
import sys


RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"


for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from pacotes import a01_jogar as aba

def test_a_escolha_da_mascara_persiste_e_vale_na_criacao_do_vpad() -> None:
    """As duas pontas do caminho que a queixa de uso supõe quebrado."""
    from hefesto_dualsense4unix.daemon.subsystems import external_mask

    assert callable(external_mask.o_arquivo_de_mascaras_vira_o_modo), (
        "a escolha de antes do modo único perdeu quem a leva ao modo")
    fonte = (RAIZ / "src/hefesto_dualsense4unix/daemon/subsystems/gamepad.py"
             ).read_text(encoding="utf-8")
    assert "mascara_efetiva(" in fonte, (
        "a criação do gamepad virtual deixou de consultar `mascara_efetiva` — a "
        "escolha do modo parou de valer, e a ressalva da tela passou a "
        "prometer o que não acontece")


def test_o_produto_diz_quais_mascaras_ele_monta() -> None:
    """A lista não se digita: ela sai do catálogo do vpad.

    A MORDIDA: troque `mascaras_montaveis()` por um literal
    `{"DualSense", "Xbox 360"}` e a régua ainda passa hoje — mas o gerador
    deixa de acender o chip sozinho no dia em que o produto aprender a montar
    um terceiro. Esta asserção é o que amarra os dois lados.
    """
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascaras_validas
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA

    assert aba.mascaras_montaveis() == {
        NOME_DA_MASCARA[f] for f in mascaras_validas() if f in NOME_DA_MASCARA}
    assert "Nintendo Pro" in aba.mascaras_montaveis(), (
        "o Nintendo Pro saiu do catálogo do vpad, ou a tela perdeu o rótulo "
        "dele — nos dois casos o chip volta a nascer cinza")


def test_a_mascara_nao_consta_mais_como_botao_sem_dono() -> None:
    """Ela tinha dono desde 03/09, e o arquivo listava os dois ao mesmo tempo."""
    assert "mascara" not in aba.BOTOES_SEM_DONO, (
        "o `mascara` voltou aos BOTOES_SEM_DONO — e ele tem dono: "
        "`gamepad.mask.set` recebe `uniq` desde 03/09/2026")
    from hefesto_dualsense4unix.interface import pacotes

    mentem = sorted(
        nome for nome in aba.BOTOES_SEM_DONO
        if ("01-jogar.html", nome) in pacotes.GESTOS
    )
    assert not mentem, (
        f"botão(ões) listado(s) em BOTOES_SEM_DONO com `@gesto` registrado: "
        f"{mentem}. A lista manda a próxima pessoa construir o que já está "
        f"construído — foi o que o `mascara` fez em 03/09 e o `modo-steam` "
        f"em 20/09")
