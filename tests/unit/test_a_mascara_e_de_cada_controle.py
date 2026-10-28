#!/usr/bin/env python3
"""A máscara de cada aparelho na tela e na escrita.

NOTA DATADA, 27/10/2026: desde a D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES a máscara
é o modo único, igual para todos; o registro por aparelho saiu, e o `por_aparelho`
repete o modo para cada controle conectado. Desde 28/10/2026 o chip da máscara do cartão
saiu da Jogar com o cartão; o `gamepad.mask.set` ficou para o terminal, e a recusa do modo
desconhecido é medida em `test_a_mascara_do_cartao_vale_com_o_vpad_de_pe.py`.

O PEDIDO É DE PRODUTO, 03/09/2026: *"É uma máscara por controle. Mesmo caso do
anterior."* — o "anterior" é a decisão dos quatro lugares, do mesmo dia.

**A CASA JÁ TINHA A METADE DIFÍCIL.** ``external_mask`` guarda a escolha por
APARELHO desde 15/08/2026 (MÁSCARA-POR-JOGADOR-01, decisão de produto), e
``mascara_efetiva`` é consultada na criação de todo gamepad virtual — os três
degraus do daemon (``virtual_pad``, ``coop``, ``gamepad``) fecharam em 29/08.

FALTAVAM DOIS, e os dois estavam NOMEADOS no próprio módulo:

1. **a escrita.** *"Falta também o lado da escrita: quem grava a escolha do usuário é
   a rota IPC, que ainda só conhece a máscara da sessão."* ``set_mask`` e
   ``clear_mask`` existiam no registro e **não tinham um chamador em `src/`**;
2. **a tela.** ``mesa_viva`` lia o ``flavor`` da SESSÃO e escrevia o mesmo valor
   nos quatro cartões — a escolha por aparelho vivia no disco e não aparecia em
   lugar nenhum. Os seis chips da aba Jogar eram, por isso, `RECUSA_CALADO`.

AS MORDIDAS, e cada uma reprova um teste diferente:

* faça ``_mascaras_por_aparelho`` devolver ``{}`` → a tela volta a repetir a
  máscara da sessão nos quatro;
* tire o ``por_aparelho`` de ``mesa_viva`` → idem, e pelo outro lado.
"""

from __future__ import annotations


UNIQ_A = "aa:bb:cc:00:00:01"
UNIQ_B = "aa:bb:cc:00:00:02"


def test_todo_aparelho_recebe_o_modo_unico() -> None:
    """D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES (27/10/2026): a escolha por
    aparelho saiu; os dois controles recebem o modo único, na mesma sessão."""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_efetiva

    for modo in ("dualsense", "xbox", "nintendo"):
        assert mascara_efetiva(UNIQ_A, modo) == mascara_efetiva(UNIQ_B, modo) == modo


def _mesa(por_aparelho: dict[str, str], da_sessao: str = "xbox"):
    from hefesto_dualsense4unix.interface import mesa_viva

    estado = {
        "controllers": [
            {"connected": True, "uniq": UNIQ_A, "transport": "usb"},
            {"connected": True, "uniq": UNIQ_B, "transport": "bluetooth"},
        ],
        "gamepad_emulation": {"flavor": da_sessao, "por_aparelho": por_aparelho},
    }
    return {c["uniq"]: c["mascara"] for c in mesa_viva.mesa_do_estado(estado, {})}


def test_a_mesa_mostra_a_mascara_de_cada_aparelho() -> None:
    """É O DEFEITO QUE ESTE ARQUIVO CURA, e ele era invisível."""
    vistas = _mesa({UNIQ_A: "dualsense"}, da_sessao="xbox")
    assert vistas[UNIQ_A] == "DualSense", vistas
    assert vistas[UNIQ_B] == "Xbox 360", vistas


def test_sem_por_aparelho_a_mesa_faz_o_que_fazia() -> None:
    """Um daemon velho não pode quebrar a tela."""
    assert set(_mesa({}, da_sessao="dualsense").values()) == {"DualSense"}


def test_o_rotulo_sai_do_dono_da_traducao() -> None:
    """A tela mostra o RÓTULO, e a tradução tem um dono só."""
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA

    for flavor, rotulo in NOME_DA_MASCARA.items():
        assert _mesa({UNIQ_A: flavor})[UNIQ_A] == rotulo

