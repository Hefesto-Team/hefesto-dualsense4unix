"""O-START-DE-QUEM-NAVEGA-A-INTERNA-SO-GUARDA-01 — o Start de quem navega a Interna só guarda.

A janela já guarda pelo Start de todo controle que navega a Interna; o defeito
estava no teclado emulado do daemon, que calava só o R1 e o L1 e deixava o Start
do primário sair como Super por cima da janela. O dono da regra é
``NavegacaoInterna.calar_o_alt_tab``, que agora sabe se o primário navega o PC
(``config.mouse_emulation_enabled``, o campo que a janela lê no ``state_full``).

Dublês: o relógio da Interna, o evdev e o módulo ``uinput`` do teclado. Nenhum
nó de verdade é aberto; o teclado é o ``UinputKeyboardDevice`` real, de modo que
a tecla Super só sobe se o produto a emitir.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import navegacao_interna as dono
from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice
from hefesto_dualsense4unix.testing import FakeController

#: Um botão da Interna que o perfil ligou a uma tecla (``key_bindings``).
BOTAO_LIGADO_A_TECLA = "cross"
TECLA_DO_PERFIL = ("KEY_ENTER",)

BOTOES = frozenset({"r1", "l1", "options", BOTAO_LIGADO_A_TECLA})


class _Relogio:
    def __call__(self) -> float:
        return 100.0


def _interna(*, agindo: bool) -> dono.NavegacaoInterna:
    n = dono.NavegacaoInterna(ligada=True, tipo=dono.TIPO_INTERNA, relogio=_Relogio())
    n.declarar_foco(agindo)
    return n


# 1 ─ O dono: as combinações de mouse com a Interna agindo e parada ─────────────


@pytest.mark.parametrize(
    ("agindo", "mouse_ligado", "esperado"),
    [
        (True, False, frozenset()),
        (True, True, frozenset({"options", BOTAO_LIGADO_A_TECLA})),
        (False, False, BOTOES),
        (False, True, BOTOES),
    ],
    ids=["agindo-mouse-desligado", "agindo-mouse-ligado", "parada-mouse-desligado",
         "parada-mouse-ligado"],
)
def test_1_o_conjunto_do_teclado_por_estado_do_mouse(
    agindo: bool, mouse_ligado: bool, esperado: frozenset[str]
) -> None:
    n = _interna(agindo=agindo)
    assert n.calar_o_alt_tab(BOTOES, mouse_ligado=mouse_ligado) == esperado


def test_1_a_interna_desligada_nao_cala_nada() -> None:
    n = dono.NavegacaoInterna(ligada=False, relogio=_Relogio())
    n.declarar_foco(True)
    assert n.calar_o_alt_tab(BOTOES, mouse_ligado=False) == BOTOES


def test_1_o_start_de_quem_nao_navega_o_pc_fica_com_a_interna() -> None:
    n = _interna(agindo=True)
    assert "options" not in n.calar_o_alt_tab(frozenset({"options"}), mouse_ligado=False)
    assert "options" in n.calar_o_alt_tab(frozenset({"options"}), mouse_ligado=True), (
        "com o mouse ligado o Start segue tecla (D-2909, nota de 08/10)")


# 2 ─ O teclado de verdade, no laço de verdade ─────────────────────────────────


class _Snap:
    buttons_pressed: ClassVar[list[str]] = []


def _uinput_de_mentira() -> tuple[SimpleNamespace, list[tuple[str, int]]]:
    emitidas: list[tuple[str, int]] = []
    modulo = SimpleNamespace()
    nomes = {k for seq in DEFAULT_BUTTON_BINDINGS.values() for k in seq if k.startswith("KEY_")}
    nomes |= set(TECLA_DO_PERFIL)
    for nome in nomes:
        setattr(modulo, nome, nome)
    dispositivo = SimpleNamespace(
        emit=lambda ev, valor, syn=True: emitidas.append((ev, valor)),
        syn=lambda: None,
        destroy=lambda: None,
    )
    modulo.Device = lambda *a, **k: dispositivo
    modulo._dispositivo = dispositivo
    return modulo, emitidas


def _estados(n: int) -> list[ControllerState]:
    return [
        ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb")
        for _ in range(n)
    ]


async def _teclas_do_laco(
    monkeypatch: pytest.MonkeyPatch, *, agindo: bool, mouse_ligado: bool
) -> set[str]:
    """Roda o ``_poll_loop`` real com Start e o botão da Interna apertados."""
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)
    n_ticks = 8
    fc = FakeController(transport="usb", states=_estados(n_ticks * 6))
    snap = _Snap()
    snap.buttons_pressed = []
    evdev = MagicMock()
    evdev.is_available.return_value = True
    evdev.snapshot.return_value = snap
    fc._evdev = evdev

    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
            autoswitch_enabled=False, mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )
    daemon._navegacao_interna = _interna(agindo=agindo)
    uinput, emitidas = _uinput_de_mentira()
    teclado = UinputKeyboardDevice(
        bindings={**DEFAULT_BUTTON_BINDINGS, BOTAO_LIGADO_A_TECLA: TECLA_DO_PERFIL}
    )
    teclado._device = uinput._dispositivo
    teclado._uinput_mod = uinput
    daemon._keyboard_device = teclado

    run_task = asyncio.create_task(daemon.run())
    prazo = time.monotonic() + 5.0
    while daemon.store.counter("poll.tick") < 2 and time.monotonic() < prazo:
        await asyncio.sleep(0.005)
    # O estado do mouse e os botões entram com o laço já vivo, sem abrir o mouse virtual.
    daemon.config.mouse_emulation_enabled = mouse_ligado
    snap.buttons_pressed = ["options", BOTAO_LIGADO_A_TECLA]
    base = daemon.store.counter("poll.tick")
    while daemon.store.counter("poll.tick") < base + n_ticks and time.monotonic() < prazo:
        await asyncio.sleep(0.005)
    daemon.stop()
    await run_task
    assert daemon.store.counter("poll.tick") >= base + n_ticks, "o laço não andou"
    return {tecla for tecla, valor in emitidas if valor == 1}


@pytest.mark.asyncio
async def test_2_mouse_desligado_e_interna_agindo_o_start_nao_tecla_super(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    teclas = await _teclas_do_laco(monkeypatch, agindo=True, mouse_ligado=False)
    assert "KEY_LEFTMETA" not in teclas, f"o Start guardou e abriu a visão geral: {teclas}"
    assert "KEY_ENTER" not in teclas, f"o botão da Interna virou tecla do perfil: {teclas}"


@pytest.mark.asyncio
async def test_2_mouse_ligado_e_interna_agindo_o_start_segue_tecla(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    teclas = await _teclas_do_laco(monkeypatch, agindo=True, mouse_ligado=True)
    assert {"KEY_LEFTMETA", "KEY_ENTER"} <= teclas, (
        f"quem navega o PC perdeu o Start como tecla: {teclas}")


@pytest.mark.asyncio
@pytest.mark.parametrize("mouse_ligado", [False, True])
async def test_2_interna_parada_nada_sai_do_teclado(
    monkeypatch: pytest.MonkeyPatch, mouse_ligado: bool
) -> None:
    teclas = await _teclas_do_laco(monkeypatch, agindo=False, mouse_ligado=mouse_ligado)
    assert {"KEY_LEFTMETA", "KEY_ENTER"} <= teclas, (
        f"fora da Interna o teclado mudou: {teclas}")


def test_2_o_laco_passa_o_estado_do_mouse_que_a_janela_le() -> None:
    """O campo é o mesmo que o ``state_full`` entrega à janela (``o_mouse_navega``)."""
    import inspect

    fonte = inspect.getsource(Daemon._poll_loop)
    assert "mouse_ligado=self.config.mouse_emulation_enabled" in fonte
