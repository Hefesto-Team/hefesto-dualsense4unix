"""O número que o jogo escreveu nas lâmpadas passa a ser o do Hefesto (o par do pad, Parte 2).

Medido em 12/10/2026, quatro DualSense num jogo da Sony: o jogo acendeu 2 no
P3 do Hefesto, 3 no P4 e 4 no P2 (``o_numero_que_o_jogo_escreveu
concorda=False``). «O jogo manda, o controle obedece»: o Hefesto troca o
número do aparelho com quem tinha o do jogo, como a troca à mão da aba
Controles, e o lugar dele na mesa do jogo troca junto, para nenhum pad
renascer debaixo do jogo.

A bancada é a da STEAM-NO-FISICO-01 (o ``CoopManager`` real, os leitores e os
vpads falsos; o ``external_mask`` sobe antes do leitor falso, que não tem o
``BUTTON_MAP`` que o módulo lê ao carregar); o registro é um dublê do número,
e a troca é a do contrato do ``_set_number_locked`` (o alvo e quem tem o número
pedido, e mais ninguém).

AS MORDIDAS (12/10/2026): sem a chamada no ``sync``, o número não muda; sem a
troca na mesa do jogo, o ``_ordenar`` recria os pads.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.subsystems import external_mask  # noqa: F401
from hefesto_dualsense4unix.daemon.subsystems.coop import _CHAVE_DO_P1, CoopManager
from tests.unit.test_steam_no_fisico_01_o_jogo_ve_p1_a_p4 import (  # noqa: F401
    P1,
    P2,
    P3,
    P4,
    nascimentos,
)


class _Registro:
    """O número de cada aparelho, com a troca do ``_set_number_locked``."""

    def __init__(self) -> None:
        self.numeros = {P1: 1, P2: 2, P3: 3, P4: 4}
        self.soltas = 0

    def numero_da_lampada(self, mac: str, assign: bool = False) -> int | None:
        return self.numeros.get(mac)

    slot_for = numero_da_lampada

    def liberar_as_lampadas(self) -> bool:
        self.soltas += 1
        return True


@pytest.fixture
def registro(monkeypatch: pytest.MonkeyPatch) -> _Registro:
    reg = _Registro()

    def _trocar(ids: Any, _ext: Any, alvo: str, numero: int, **_kw: Any) -> dict[str, int]:
        assert ids is reg
        dono = next(m for m, n in reg.numeros.items() if n == numero)
        reg.numeros[dono], reg.numeros[alvo] = reg.numeros[alvo], numero
        return dict(reg.numeros)

    monkeypatch.setattr(IpcHandlersMixin, "_set_number_locked", staticmethod(_trocar))
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.connection.armar_gatilho_da_cor_por_evento",
        lambda _d, _e: None,
    )
    return reg


def _daemon(reg: _Registro) -> Any:
    return SimpleNamespace(
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=object(),
        controller=SimpleNamespace(
            primary_uniq=P1,
            _evdev=SimpleNamespace(_device_path="/dev/input/event20"),
        ),
        identity_registry=reg,
        external_registry=None,
        _coop_manager=None,
        display_authority="daemon",
    )


def _o_jogo_escreve(daemon: Any, reg: _Registro, jogo: dict[str, int]) -> None:
    daemon._numero_que_o_jogo_escreveu = {
        mac: (numero, reg.numeros[mac]) for mac, numero in jogo.items()
    }


def test_o_numero_que_o_jogo_escreveu_vira_o_do_hefesto_sem_recriar_pad(
    nascimentos: list[str], registro: _Registro  # noqa: F811
) -> None:
    daemon = _daemon(registro)
    mgr = CoopManager(daemon)
    mgr.sync()
    assert nascimentos == [P2, P3, P4]
    vpads = {mac: p.vpad for mac, p in mgr._players.items()}

    daemon.display_authority = "game"
    _o_jogo_escreve(daemon, registro, {P3: 2, P4: 3, P2: 4})
    mgr.sync(force=True)

    assert registro.numeros == {P1: 1, P2: 4, P3: 2, P4: 3}
    assert nascimentos == [P2, P3, P4], "nenhum pad renasce debaixo do jogo"
    assert {mac: p.vpad for mac, p in mgr._players.items()} == vpads
    assert mgr._mesa_do_jogo == {0: _CHAVE_DO_P1, 1: P3, 2: P4, 3: P2}
    assert registro.soltas >= 1, "as lâmpadas congeladas seguem o registro na hora"

    mgr.sync(force=True)
    assert registro.numeros == {P1: 1, P2: 4, P3: 2, P4: 3}, "concordou: não troca de novo"
    assert nascimentos == [P2, P3, P4]


def test_sem_o_jogo_na_autoridade_e_com_o_p1_no_meio_nada_troca(
    nascimentos: list[str], registro: _Registro  # noqa: F811
) -> None:
    daemon = _daemon(registro)
    mgr = CoopManager(daemon)
    mgr.sync()

    _o_jogo_escreve(daemon, registro, {P3: 2, P2: 3})
    mgr.sync(force=True)
    assert registro.numeros == {P1: 1, P2: 2, P3: 3, P4: 4}, "sem jogo, o Hefesto numera"

    daemon.display_authority = "game"
    _o_jogo_escreve(daemon, registro, {P2: 1})
    mgr.sync(force=True)
    assert registro.numeros == {P1: 1, P2: 2, P3: 3, P4: 4}, "o posto do P1 não troca por aqui"
    assert nascimentos == [P2, P3, P4]
