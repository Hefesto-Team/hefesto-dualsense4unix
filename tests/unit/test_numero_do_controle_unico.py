"""Um controle, UM número — em toda a interface.

A aba Início numerava o card pela POSIÇÃO na lista enquanto o cabeçalho, a aba
Status, a CLI e o applet usavam o `player_slot` de sessão. Com um controle só,
a mesma janela dizia "Controle 1 — P1" no card e "Sony 3 · BT" no cabeçalho,
sobre esse mesmo controle.

Não confundir com o número do JOGADOR (`player`), que vem do daemon e só existe
em co-op — esse pode divergir do número do controle por construção.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.base import numero_do_controle


def _entry(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"index": 0, "transport": "bt"}
    base.update(kw)
    return base


class TestNumeroDoControle:
    def test_usa_o_player_slot_quando_existe(self) -> None:
        assert numero_do_controle(_entry(player_slot=3, index=0)) == 3

    def test_slot_vence_a_posicao_na_lista(self) -> None:
        """O slot sobrevive a desconectar/reconectar; a posição, não."""
        assert numero_do_controle(_entry(player_slot=4, index=1)) == 4

    def test_sem_slot_cai_na_posicao_1_based(self) -> None:
        assert numero_do_controle(_entry(index=2)) == 3

    def test_sem_slot_e_sem_indice_vira_1(self) -> None:
        assert numero_do_controle({}) == 1

    @pytest.mark.parametrize("valor", [True, False])
    def test_bool_nao_conta_como_numero(self, valor: bool) -> None:
        """`True` é `int` em Python — sem o guard viraria "Controle 1"."""
        assert numero_do_controle(_entry(player_slot=valor, index=4)) == 5


class TestTelasConcordam:
    """As três telas têm de produzir o MESMO número para a mesma entry."""

    @pytest.mark.parametrize(
        "entry",
        [
            {"player_slot": 3, "index": 0, "transport": "bt"},
            {"player_slot": 1, "index": 2, "transport": "usb"},
            {"index": 1, "transport": "bt"},  # sem slot: cai na posição
            {"transport": "bt"},  # sem nada
        ],
    )
    def test_inicio_status_e_cabecalho_dao_o_mesmo_numero(
        self, entry: dict[str, Any]
    ) -> None:
        from hefesto_dualsense4unix.app.actions.home_actions import (
            _format_controller_title,
        )
        from hefesto_dualsense4unix.app.actions.status_actions import _display_slot
        from hefesto_dualsense4unix.app.widgets.controller_card import titulo_do_card

        esperado = numero_do_controle(entry)

        # cabeçalho / seletor
        assert _display_slot(entry) == esperado

        # card da aba Início — recebe a entry, então o teste cobre de ONDE o
        # número sai, que é exatamente onde estava o defeito.
        assert _format_controller_title(entry).startswith(f"Controle {esperado}")

        # card da aba Status
        assert titulo_do_card(entry).startswith(f"Controle {esperado} ")

    def test_numero_do_jogador_pode_divergir_do_numero_do_controle(self) -> None:
        """Divergir aqui é CORRETO: são coisas diferentes.

        O daemon reusa índices de jogador quando alguém sai e outro entra, então
        o controle 2 pode legitimamente ser o jogador 3. SLOT-JOGADOR-01: a
        divergência fica LEGÍVEL — o número do jogador vem com a autoridade
        colada ("no co-op"), então os dois não se leem como um só.
        """
        from hefesto_dualsense4unix.app.actions.home_actions import (
            _format_controller_title,
        )

        entry = {"player_slot": 2, "player": 3, "transport": "bt"}
        assert _format_controller_title(entry) == "Controle 2 — P3 no co-op"

    def test_sem_jogador_o_card_so_se_identifica(self) -> None:
        """Fora do co-op o jogo vê um controle só — inventar "P" seria mentira."""
        from hefesto_dualsense4unix.app.actions.home_actions import (
            _format_controller_title,
        )

        entry = {"player_slot": 2, "transport": "bt"}
        assert _format_controller_title(entry) == "Controle 2"
