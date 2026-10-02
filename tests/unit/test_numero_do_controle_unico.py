"""Um controle, UM número — em toda a interface.

A aba Início numerava o card pela POSIÇÃO na lista enquanto o cabeçalho, a aba
Status, a CLI e o applet usavam o `player_slot` de sessão. Com um controle só,
a mesma janela dizia "Controle 1 — P1" no card e "Sony 3 · BT" no cabeçalho,
sobre esse mesmo controle.

Não confundir com o número do JOGADOR (`player`), que vem do daemon e só existe
em co-op — esse pode divergir do número do controle por construção.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_numero_do_controle_unico: importa código da janela GTK")

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


