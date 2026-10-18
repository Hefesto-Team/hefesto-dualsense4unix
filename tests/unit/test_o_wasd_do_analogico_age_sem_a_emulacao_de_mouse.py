"""O WASD do analógico age sem a emulação de mouse.

Sprint O-WASD-DO-ANALOGICO-AGE-SEM-A-EMULACAO-DE-MOUSE-01.

Medido antes de curar (17/10/2026): com a emulação de mouse desligada e «Teclas WASD» no
analógico esquerdo, o laço de produção não emitia tecla nenhuma, porque a chamada de
`teclas_do_analogico_no_desktop` morava dentro do `dispatch_mouse`, e o laço só o chama com o
`_mouse_device` de pé.

A régua roda o `Daemon.run` de verdade (o laço), sobre o `uinput` de mentira que grava o que o
teclado privado do analógico emite. MORDIDAS (arrancadas e devolvidas): a chamada de volta para
dentro do `dispatch_mouse` e fora do laço reprova as de «sem mouse»; tirar a condição de
`emu_active` reprova a da supressão; tirar o `_keyboard_device`/`_teclado_so_no_jogo` de
`teclas_do_analogico_no_desktop` reprova as do teclado.
"""
from __future__ import annotations

import asyncio
import sys
import time
import types
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import mouse as sub_mouse
from hefesto_dualsense4unix.testing import FakeController
from tests.unit.test_o_gatilho_vira_clique_sem_ligar_o_cursor import (
    _estado,
    _saidas,
    _UinputPorDevice,
)

CENTRO = 128
PRAZO_S = 5.0


class _MouseDoDesktop:
    """O `_mouse_device` do desktop, de pé: só o que o `dispatch_mouse` e a soltura tocam."""

    def dispatch(self, **_kw: Any) -> None:
        pass

    def soltar_o_clique_travado(self) -> None:
        pass

    def definir_ajuste(self, *_a: Any) -> None:
        pass

    def stop(self) -> None:
        pass


def _teclas(mod: _UinputPorDevice) -> list[tuple[str, int]]:
    return [(n, v) for n, v in _saidas(mod)[1] if n.startswith("KEY_")]


async def _rodar_o_laco(
    monkeypatch: pytest.MonkeyPatch,
    mod: _UinputPorDevice,
    *,
    transporte: str = "usb",
    mouse_ligado: bool = False,
    so_no_jogo: bool = False,
    teclado: bool = True,
    suspensa: bool = False,
    token: str = acoes.TOKEN_WASD,
) -> list[tuple[str, int]]:
    """Sobe o laço com o analógico esquerdo à esquerda e devolve as teclas que saíram."""
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {})
    monkeypatch.setattr(sub_mouse, "mover_o_cursor_pelo_giro", lambda *a, **k: None)

    class _Snap:
        buttons_pressed: list[str] = []  # noqa: RUF012

    fc = FakeController(transport=transporte, states=[  # type: ignore[arg-type]
        _estado(raw_lx=32, raw_ly=CENTRO, raw_rx=CENTRO, raw_ry=CENTRO, transport=transporte)
        for _ in range(60)])
    evdev = MagicMock()
    evdev.is_available.return_value = True
    evdev.snapshot.return_value = _Snap()
    fc._evdev = evdev
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200, ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
            mouse_emulation_enabled=mouse_ligado, keyboard_emulation_enabled=False,
        ),
    )
    if mouse_ligado:
        daemon._mouse_device = _MouseDoDesktop()
    if teclado:
        daemon._keyboard_device = MagicMock()
    daemon._emulation_suppressed = suspensa
    sub_mouse.trocar_a_tabela_no_jogo(daemon, types.SimpleNamespace(
        button_actions={acoes.EIXO_ESQUERDO: token}, key_bindings=None,
        teclado_so_no_jogo=so_no_jogo))

    run_task = asyncio.create_task(daemon.run())
    prazo = time.monotonic() + PRAZO_S
    while daemon.store.counter("input.settling.tick") < 3 and time.monotonic() < prazo:
        await asyncio.sleep(0.005)
    # Dá ao laço o tempo de despachar a tecla com o analógico à esquerda.
    fim = time.monotonic() + (PRAZO_S if not (so_no_jogo or suspensa or not teclado) else 0.3)
    while not _teclas(mod) and time.monotonic() < fim:
        await asyncio.sleep(0.005)
    daemon.stop()
    await run_task
    return _teclas(mod)


@pytest.fixture
def uinput(monkeypatch: pytest.MonkeyPatch) -> _UinputPorDevice:
    mod = _UinputPorDevice()
    monkeypatch.setitem(sys.modules, "uinput", mod)
    return mod


@pytest.mark.asyncio
@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("mouse_ligado", [False, True], ids=["sem-mouse", "com-mouse"])
async def test_o_wasd_digita_com_ou_sem_a_emulacao_de_mouse(
    monkeypatch: pytest.MonkeyPatch, uinput: _UinputPorDevice, transporte: str, mouse_ligado: bool,
) -> None:
    saiu = await _rodar_o_laco(
        monkeypatch, uinput, transporte=transporte, mouse_ligado=mouse_ligado)
    assert ("KEY_A", 1) in saiu, (
        f"o analógico em WASD não digitou (mouse ligado={mouse_ligado}, {transporte})")
    assert saiu.count(("KEY_A", 1)) == 1, "a tecla foi apertada mais de uma vez"


@pytest.mark.asyncio
async def test_as_setas_digitam_sem_a_emulacao_de_mouse(
    monkeypatch: pytest.MonkeyPatch, uinput: _UinputPorDevice,
) -> None:
    saiu = await _rodar_o_laco(monkeypatch, uinput, token=acoes.TOKEN_SETAS)
    assert ("KEY_LEFT", 1) in saiu, saiu


@pytest.mark.asyncio
async def test_so_dentro_do_jogo_cala_o_desktop_sem_a_emulacao_de_mouse(
    monkeypatch: pytest.MonkeyPatch, uinput: _UinputPorDevice,
) -> None:
    saiu = await _rodar_o_laco(monkeypatch, uinput, so_no_jogo=True)
    assert not saiu, f"«Só dentro do jogo» digitou no desktop: {saiu}"


@pytest.mark.asyncio
async def test_o_teclado_desativado_cala_o_analogico_sem_a_emulacao_de_mouse(
    monkeypatch: pytest.MonkeyPatch, uinput: _UinputPorDevice,
) -> None:
    saiu = await _rodar_o_laco(monkeypatch, uinput, teclado=False)
    assert not saiu, f"«Desativado» digitou no desktop: {saiu}"


@pytest.mark.asyncio
async def test_a_emulacao_suspensa_cala_o_analogico(
    monkeypatch: pytest.MonkeyPatch, uinput: _UinputPorDevice,
) -> None:
    saiu = await _rodar_o_laco(monkeypatch, uinput, suspensa=True)
    assert not saiu, f"a supressão que ela ligou deixou o analógico digitar: {saiu}"


@pytest.mark.asyncio
async def test_a_linha_sem_wasd_nao_abre_teclado_nem_digita(
    monkeypatch: pytest.MonkeyPatch, uinput: _UinputPorDevice,
) -> None:
    saiu = await _rodar_o_laco(monkeypatch, uinput, token=acoes.TOKEN_NADA)
    assert not saiu, saiu


def test_o_dispatch_mouse_nao_atende_mais_as_teclas_do_analogico(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A origem: o atendente é do laço, e o `dispatch_mouse` (que só roda com o mouse de pé)
    não o chama. MORDIDA: a chamada de volta no `dispatch_mouse` reprova."""
    chamadas: list[Any] = []
    monkeypatch.setattr(
        sub_mouse, "teclas_do_analogico_no_desktop", lambda *a, **k: chamadas.append(a))
    monkeypatch.setattr(sub_mouse, "mover_o_cursor_pelo_giro", lambda *a, **k: None)
    daemon = types.SimpleNamespace(
        _mouse_device=_MouseDoDesktop(), _touchpad_reader=None, store=None)
    sub_mouse.dispatch_mouse(daemon, _estado(), frozenset())
    assert not chamadas, "o dispatch_mouse voltou a atender as teclas do analógico"


def test_parar_a_emulacao_de_mouse_nao_solta_a_tecla_do_analogico(
    monkeypatch: pytest.MonkeyPatch, uinput: _UinputPorDevice,
) -> None:
    """A tecla é do analógico, não do mouse: desligar a emulação com o analógico empurrado
    não solta a tecla (soltá-la e reapertá-la no tique seguinte repetiria a tecla)."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {})
    daemon = types.SimpleNamespace(
        config=types.SimpleNamespace(mouse_emulation_enabled=True),
        _mouse_device=_MouseDoDesktop(), _tabela_no_jogo=None, _teclado_so_no_jogo=False,
        _keyboard_device=MagicMock(), _outros={})
    sub_mouse.trocar_a_tabela_no_jogo(daemon, types.SimpleNamespace(
        button_actions={acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD}, key_bindings=None))
    sub_mouse.teclas_do_analogico_no_desktop(daemon, _estado(raw_lx=32))
    assert ("KEY_A", 1) in _teclas(uinput)
    sub_mouse.stop_mouse_emulation(daemon, persist=False)
    assert ("KEY_A", 0) not in _teclas(uinput), "desligar o mouse soltou a tecla do analógico"
    sub_mouse.fechar_as_teclas_do_analogico(daemon)
