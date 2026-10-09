"""O-TECLADO-SO-DENTRO-DO-JOGO-TEM-DONO-01 — «Só dentro do jogo» digita só com um jogo aberto.

Medido antes de curar (08/10/2026): a terceira palavra da Função do teclado
levantava `RuntimeError` no gesto, a lista voltava sozinha e o perfil não tinha
campo nenhum que dissesse «só dentro». O laço de poll só consultava o teclado do
desktop no tique em que o gamepad virtual NÃO despachava — o inverso do pedido.

O leitor aqui é o teclado virtual de mentira, que anota cada `dispatch` e cada
`prime` que o LAÇO REAL do daemon faz — nunca a flag que a cura trava.
"""
from __future__ import annotations

import asyncio
import time
import types
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import mouse as sub_mouse
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController


class _TecladoDeMentira:
    """Anota o que o laço lhe pede; não toca em uinput."""

    def __init__(self) -> None:
        self.dispatches: list[frozenset[str]] = []
        self.primes: list[frozenset[str]] = []

    def dispatch(self, botoes: frozenset[str]) -> None:
        self.dispatches.append(frozenset(botoes))

    def prime(self, botoes: frozenset[str]) -> None:
        self.primes.append(frozenset(botoes))

    def stop(self) -> None:
        pass


def _estado() -> ControllerState:
    return ControllerState(  # type: ignore[call-arg]
        battery_pct=80, connected=True, transport="usb", l2_raw=0, r2_raw=0)


async def _roda_o_laco(
    monkeypatch: pytest.MonkeyPatch, *, so_dentro: bool, no_jogo: bool,
) -> _TecladoDeMentira:
    """Roda o laço de produção por alguns tiques com o Cruz apertado."""
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)

    class _Snap:
        buttons_pressed = ["cross"]  # noqa: RUF012

    fc = FakeController(transport="usb", states=[_estado() for _ in range(40)])
    evdev = MagicMock()
    evdev.is_available.return_value = True
    evdev.snapshot.return_value = _Snap()
    fc._evdev = evdev
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
            autoswitch_enabled=False, mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )
    teclado = _TecladoDeMentira()
    daemon._keyboard_device = teclado
    daemon._teclado_so_no_jogo = so_dentro
    if no_jogo:
        daemon._gamepad_device = MagicMock()
        daemon._dispatch_gamepad_emulation = lambda estado, botoes: None  # type: ignore[method-assign]
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {})

    run_task = asyncio.create_task(daemon.run())
    prazo = time.monotonic() + 5.0
    while len(teclado.dispatches) + len(teclado.primes) < 3 and time.monotonic() < prazo:
        await asyncio.sleep(0.005)
    daemon.stop()
    await run_task
    return teclado


@pytest.mark.asyncio
async def test_so_dentro_o_teclado_fica_calado_fora_do_jogo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fora do jogo, com «Só dentro»: o Cruz não digita (o teclado só semeia a borda).

    MORDIDA: voltar o laço a despachar sempre fora do jogo (tirar o `if
    self._teclado_so_no_jogo` do ramo do desktop) deixa o Cruz em `dispatches`.
    """
    teclado = await _roda_o_laco(monkeypatch, so_dentro=True, no_jogo=False)
    digitou = [d for d in teclado.dispatches if d]
    assert not digitou, f"«Só dentro do jogo» digitou fora do jogo: {digitou[:2]}"
    assert teclado.primes, "o laço não chegou a semear a borda do teclado"


@pytest.mark.asyncio
async def test_so_dentro_o_teclado_digita_com_o_jogo_aberto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com o gamepad virtual despachando, o Cruz chega ao teclado.

    MORDIDA: tirar o ramo `so_dentro` de `despachar_no_jogo` deixa
    `dispatches` vazio e este caso reprova.
    """
    teclado = await _roda_o_laco(monkeypatch, so_dentro=True, no_jogo=True)
    assert any("cross" in d for d in teclado.dispatches), (
        f"«Só dentro do jogo» não digitou com o jogo aberto: {teclado.dispatches[:2]}")


@pytest.mark.asyncio
async def test_sem_o_campo_o_teclado_segue_como_sempre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem `teclado_so_no_jogo`: digita fora do jogo e fica calado dentro (o de sempre)."""
    fora = await _roda_o_laco(monkeypatch, so_dentro=False, no_jogo=False)
    assert any("cross" in d for d in fora.dispatches), "«Só fora» deixou de digitar fora"
    dentro = await _roda_o_laco(monkeypatch, so_dentro=False, no_jogo=True)
    assert not [d for d in dentro.dispatches if d], (
        "«Só fora do jogo» digitou com o jogo aberto")


def test_o_campo_do_perfil_chega_ao_daemon_mesmo_com_o_lock_manual() -> None:
    """A ativação trava o sinal do portão ANTES de qualquer saída por lock manual.

    MORDIDA: mover a chamada de `trocar_a_tabela_no_jogo` para depois do retorno
    do lock deixa o `profile.reaplicar` do gesto sem efeito na hora.
    """
    daemon = Daemon(
        controller=FakeController(transport="usb", states=[_estado()]),
        config=DaemonConfig(
            auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
            autoswitch_enabled=False, mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )
    daemon._suppress_manual_ts = time.monotonic()
    perfil = Profile(name="regua", match=MatchAny(), teclado_emulado=True,
                     teclado_so_no_jogo=True)
    daemon.apply_profile_suppression(False, profile=perfil, origin="autoswitch")
    assert daemon._teclado_so_no_jogo is True

    perfil = Profile(name="regua", match=MatchAny(), teclado_emulado=True)
    daemon.apply_profile_suppression(False, profile=perfil, origin="autoswitch")
    assert daemon._teclado_so_no_jogo is False


def test_o_campo_sobrevive_ao_disco_e_so_nasce_quando_escolhido() -> None:
    """Omitido quando `None` (perfil de ontem intacto) e preservado quando ela escolhe."""
    sem = Profile(name="a", match=MatchAny()).model_dump(mode="json", exclude_none=True)
    assert "teclado_so_no_jogo" not in sem
    com = Profile(name="a", match=MatchAny(), teclado_so_no_jogo=True)
    assert Profile.model_validate(com.model_dump(mode="json")).teclado_so_no_jogo is True


def test_trocar_a_tabela_trava_o_campo_do_teclado() -> None:
    daemon: Any = types.SimpleNamespace(_tabela_no_jogo=None, _teclado_so_no_jogo=False)
    sub_mouse.trocar_a_tabela_no_jogo(
        daemon, types.SimpleNamespace(teclado_so_no_jogo=True, tabela_no_jogo=None))
    assert daemon._teclado_so_no_jogo is True
