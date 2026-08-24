"""Z2-7 — a fita e os cards nascem na MESMA ordem.

24/08/2026. M2 (medido e reproduzido na sprint ONDA0-Z2): a fita do
cabeçalho ordena pelo número de identidade exibido
(``_por_numero_de_identidade``, herdado da PLAYER-01/UI-SELETOR-01); a grade
de cards percorria ``conectados`` na ordem de ENUMERAÇÃO do daemon — que
diverge da ordem do número sempre que alguém liga os controles fora de
ordem, o caso normal. Com os dois ligados fora de ordem, o primeiro card
era o Controle 2 e o primeiro chip era o Controle 1: a pessoa contava a
posição na grade e clicava no chip errado.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("z2 ordem dos cards")

from typing import Any

from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin as S

#: MACs forjados da faixa permitida — os mesmos do M2 medido na sprint.
UNIQ_P1 = "aa:bb:cc:00:00:11"
UNIQ_P2 = "aa:bb:cc:00:00:22"


def _mesa_fora_de_ordem() -> list[dict[str, Any]]:
    """O cenário do M2: o Jogador 2 conectou ANTES do Jogador 1."""
    return [
        {
            "index": 0,
            "uniq": UNIQ_P2,
            "player_slot": 2,
            "transport": "bt",
            "connected": True,
        },
        {
            "index": 1,
            "uniq": UNIQ_P1,
            "player_slot": 1,
            "transport": "bt",
            "connected": True,
        },
    ]


def test_a_ordem_dos_cards_bate_com_a_ordem_da_fita() -> None:
    """A MORDIDA: reprova hoje (M2), sem cura nenhuma arrancada."""
    mesa = _mesa_fora_de_ordem()
    fita = [rotulo for rotulo, _idx in S._controller_target_rows(mesa)][1:]
    cards = S._status_card_keys_for(mesa)
    uniq_da_fita_na_ordem = [
        UNIQ_P1 if "1" in rotulo else UNIQ_P2 for rotulo in fita
    ]
    uniq_dos_cards_na_ordem = [uniq for _indice, uniq in cards]
    assert uniq_dos_cards_na_ordem == uniq_da_fita_na_ordem, (
        f"fita: {fita}, cards: {cards} — a grade e a fita nasceram em ordens "
        "diferentes; a pessoa clicaria no chip errado"
    )


def test_o_indice_de_enumeracao_viaja_intacto_na_chave() -> None:
    """Hipótese explica o que já funcionava: só a ORDEM muda, não o índice.

    O ``index`` de cada linha ainda é o que ``controller.target.set``
    espera — reordenar o índice junto seria pior que o defeito de hoje
    (clicar no chip do 1 editaria outro controle).
    """
    mesa = _mesa_fora_de_ordem()
    cards = S._status_card_keys_for(mesa)
    indices_por_uniq = {uniq: indice for indice, uniq in cards}
    assert indices_por_uniq[UNIQ_P1] == 1
    assert indices_por_uniq[UNIQ_P2] == 0


def test_sem_player_slot_vai_para_o_fim_preservando_a_ordem_relativa() -> None:
    """O desempate de `_por_numero_de_identidade` (sorted estável) também
    vale para os cards — controle sem slot não fura a fila."""
    mesa = [
        {"index": 0, "uniq": "aa:bb:cc:00:00:33", "player_slot": None,
         "transport": "bt", "connected": True},
        {"index": 1, "uniq": UNIQ_P1, "player_slot": 1,
         "transport": "bt", "connected": True},
    ]
    cards = S._status_card_keys_for(mesa)
    assert [uniq for _indice, uniq in cards] == [UNIQ_P1, "aa:bb:cc:00:00:33"]
