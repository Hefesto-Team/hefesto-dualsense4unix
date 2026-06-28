"""Lógica pura do seletor de controle na GUI (FEAT-DSX-CONTROLLER-SELECTOR-01).

Cobre os helpers estáticos do `StatusActionsMixin` que montam as linhas da combo
e mapeiam o `output_target_index` do daemon para a posição ativa — sem GTK.
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin


def _conectado(index: int, transport: str, *, primary: bool = False) -> dict[str, object]:
    return {
        "index": index,
        "connected": True,
        "transport": transport,
        "is_primary": primary,
    }


def test_rows_comeca_com_todos() -> None:
    rows = StatusActionsMixin._controller_target_rows(
        [_conectado(0, "bt", primary=True), _conectado(1, "usb")]
    )
    assert rows[0] == ("Todos os controles", None)
    assert rows[1] == ("Controle 1 — BT", 0)
    assert rows[2] == ("Controle 2 — USB", 1)


def test_rows_transporte_ausente_vira_interrogacao() -> None:
    rows = StatusActionsMixin._controller_target_rows(
        [{"index": 0, "connected": True}, {"index": 1, "connected": True}]
    )
    assert rows[1] == ("Controle 1 — ?", 0)


def test_active_position_alvo_todos() -> None:
    rows = StatusActionsMixin._controller_target_rows(
        [_conectado(0, "bt"), _conectado(1, "usb")]
    )
    assert StatusActionsMixin._target_active_position(rows, None) == 0


def test_active_position_alvo_segundo_controle() -> None:
    rows = StatusActionsMixin._controller_target_rows(
        [_conectado(0, "bt"), _conectado(1, "usb")]
    )
    # output_target_index=1 → posição 2 na combo (0=Todos, 1=Controle1, 2=Controle2).
    assert StatusActionsMixin._target_active_position(rows, 1) == 2


def test_active_position_alvo_inexistente_cai_em_todos() -> None:
    rows = StatusActionsMixin._controller_target_rows([_conectado(0, "usb")])
    # alvo aponta para um índice que não está na lista → "Todos" (posição 0).
    assert StatusActionsMixin._target_active_position(rows, 5) == 0
