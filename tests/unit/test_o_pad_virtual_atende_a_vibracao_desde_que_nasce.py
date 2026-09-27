"""O-PAD-VIRTUAL-ATENDE-A-VIBRACAO-DESDE-QUE-NASCE-01 — o pad uinput não trava ninguém.

Na noite de 27/09/2026 a sessão dela caiu duas vezes (e mais duas às 12h43 e
12h51) pela mesma cadeia: o construtor do python-evdev abria o próprio nó do
pad logo depois de criá-lo; o `gilrs` do `cosmic-osk` mandava um efeito de
vibração ao pad novo; o kernel esperava o dono responder por até 30 s com a
trava do nó presa; o dono estava parado no `open()` do mesmo nó; o logind
travava no `TakeDevice`, e o `cosmic-comp` abortava.

As duas réguas medem as duas metades da cura, e as duas mordem:

- criar o pad não abre o próprio nó (devolva o `_find_device` do python-evdev
  e reprova);
- o pedido de efeito é atendido pelo fio do pad, sem tique nenhum (devolva o
  atendimento ao `pump_ff` do tique e ninguém responde).
"""
from __future__ import annotations

import contextlib
import os
import sys
import time
import types
from collections import deque
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad
from tests.unit.test_vpad_ff_passthrough import _EC, _AbsInfo, _event, _rumble_effect


class _UInputComoOPythonEvdev:
    """Imita o construtor do python-evdev: cria e, em seguida, `_find_device`.

    O `fd` é a ponta de leitura de um `os.pipe()`: o «kernel» do teste avisa
    que há evento escrevendo um byte na outra ponta, e o `read_one` o consome.
    """

    instancias: ClassVar[list[_UInputComoOPythonEvdev]] = []
    abriu_o_proprio_no: ClassVar[int] = 0

    def __init__(self, events: dict[int, list[Any]], **kwargs: Any) -> None:
        self.events = events
        self.kwargs = kwargs
        self.fd, self._aviso = os.pipe()
        os.set_blocking(self.fd, False)
        self.fila: deque[SimpleNamespace] = deque()
        self.uploads_pendentes: dict[int, SimpleNamespace] = {}
        self.uploads_feitos: list[SimpleNamespace] = []
        self.fechado = False
        type(self).instancias.append(self)
        self.device = self._find_device(self.fd)

    def _find_device(self, fd: int) -> object:
        """O que o python-evdev faz: abre `/dev/input/eventN` do pad recém-criado."""
        type(self).abriu_o_proprio_no += 1
        return object()

    def write(self, etype: int, code: int, value: int) -> None:
        return

    def syn(self) -> None:
        return

    def close(self) -> None:
        self.fechado = True
        for fd in (self.fd, self._aviso):
            with contextlib.suppress(OSError):
                os.close(fd)

    def read_one(self) -> SimpleNamespace | None:
        with contextlib.suppress(BlockingIOError):
            os.read(self.fd, 1)
        return self.fila.popleft() if self.fila else None

    def begin_upload(self, request_id: int) -> SimpleNamespace:
        return SimpleNamespace(
            request_id=request_id, retval=-1, effect=self.uploads_pendentes[request_id]
        )

    def end_upload(self, upload: SimpleNamespace) -> None:
        self.uploads_feitos.append(upload)

    def o_jogo_manda_um_efeito(self, effect: SimpleNamespace, *, request_id: int) -> None:
        self.uploads_pendentes[request_id] = effect
        self.fila.append(_event(_EC.EV_UINPUT, _EC.UI_FF_UPLOAD, request_id))
        os.write(self._aviso, b"x")


@pytest.fixture
def evdev_de_mentira(monkeypatch: pytest.MonkeyPatch) -> type[_UInputComoOPythonEvdev]:
    _UInputComoOPythonEvdev.instancias = []
    _UInputComoOPythonEvdev.abriu_o_proprio_no = 0
    mod = types.ModuleType("evdev")
    mod.UInput = _UInputComoOPythonEvdev  # type: ignore[attr-defined]
    mod.AbsInfo = _AbsInfo  # type: ignore[attr-defined]
    mod.ecodes = _EC  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "evdev", mod)
    return _UInputComoOPythonEvdev


def _pad_xbox() -> UinputGamepad:
    pad = UinputGamepad.for_flavor("xbox", rumble_sink=lambda _w, _s: None)
    assert pad.start() is True
    return pad


def test_criar_o_pad_nunca_abre_o_proprio_no(
    evdev_de_mentira: type[_UInputComoOPythonEvdev],
) -> None:
    pad = _pad_xbox()
    try:
        assert evdev_de_mentira.instancias, "o pad não nasceu do UInput"
        assert evdev_de_mentira.abriu_o_proprio_no == 0, (
            "criar o pad abriu o próprio nó: é a espera circular de 30 s com "
            "o gilrs do cosmic-osk que derrubou a sessão dela em 27/09"
        )
        assert evdev_de_mentira.instancias[0].device is None
    finally:
        pad.stop()


def test_o_pedido_de_vibracao_e_atendido_sem_tique(
    evdev_de_mentira: type[_UInputComoOPythonEvdev],
) -> None:
    pad = _pad_xbox()
    aparelho = evdev_de_mentira.instancias[0]
    try:
        inicio = time.monotonic()
        aparelho.o_jogo_manda_um_efeito(
            _rumble_effect(0, strong=0x8000, weak=0x4000), request_id=7
        )
        # Nenhum `pump_ff`: só o fio do pad pode responder.
        while not aparelho.uploads_feitos and time.monotonic() - inicio < 1.0:
            time.sleep(0.002)
        esperou = time.monotonic() - inicio
        assert aparelho.uploads_feitos, (
            "o pedido de efeito ficou sem resposta sem o tique: quem mandou "
            "(o jogo, o cosmic-osk) fica preso com a trava do nó no kernel"
        )
        assert aparelho.uploads_feitos[0].retval == 0
        assert esperou < 0.5
        assert 0 in pad._ff_effects
    finally:
        pad.stop()


def test_o_stop_encerra_o_fio_antes_de_fechar(
    evdev_de_mentira: type[_UInputComoOPythonEvdev],
) -> None:
    pad = _pad_xbox()
    aparelho = evdev_de_mentira.instancias[0]
    fio = pad._ff_fio
    assert fio is not None and fio.is_alive()
    aparelho.o_jogo_manda_um_efeito(_rumble_effect(1, strong=1, weak=1), request_id=8)
    pad.stop()
    assert not fio.is_alive()
    assert aparelho.fechado
    assert pad._ff_fio is None


def test_o_tique_segue_entregando_ao_fisico(
    evdev_de_mentira: type[_UInputComoOPythonEvdev],
) -> None:
    entregues: list[tuple[int, int]] = []
    pad = UinputGamepad.for_flavor("xbox", rumble_sink=lambda w, s: entregues.append((w, s)))
    assert pad.start() is True
    aparelho = evdev_de_mentira.instancias[0]
    try:
        aparelho.o_jogo_manda_um_efeito(
            _rumble_effect(0, strong=0x8000, weak=0x4000, duration_ms=500), request_id=9
        )
        inicio = time.monotonic()
        while not aparelho.uploads_feitos and time.monotonic() - inicio < 1.0:
            time.sleep(0.002)
        aparelho.fila.append(_event(_EC.EV_FF, 0, 1))
        os.write(aparelho._aviso, b"x")
        while pad._ff_play_count == 0 and time.monotonic() - inicio < 1.0:
            time.sleep(0.002)
        pad.pump_ff()
        assert entregues == [(0x40, 0x80)]
    finally:
        pad.stop()
