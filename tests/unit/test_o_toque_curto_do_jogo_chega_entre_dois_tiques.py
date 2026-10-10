"""O-TOQUE-CURTO-DO-JOGO-CHEGA-AO-CONTROLE-MESMO-ENTRE-DOIS-TIQUES-01.

A saída do jogo é atendida no fio de cada pad, e a entrega ao controle físico
fica no tique (`pump_ff`). O toque que começa e acaba entre dois tiques tem de
chegar: no `uhid` o fio guarda o pico do intervalo, e no `uinput` o efeito
tocado conta pelo menos um tique. O `replay.delay` do efeito entra no prazo.

Sem `/dev/uhid` nem `/dev/uinput`: o `uhid` fala com o kernel de mentira da
fila de 32 lugares (`test_a_entrada_de_cada_jogador_chega_inteira`), com o fio
de verdade, e o `uinput` com o evdev de mentira do handshake de FF. Os relógios
são de mentira; o tique é a chamada ao `pump_ff`.
"""
from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import uhid_gamepad, uinput_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad
from tests.unit.test_a_entrada_de_cada_jogador_chega_inteira import (
    Fisico,
    KernelDoUhid,
    Relogio,
    _esperar,
    _evento_de_saida,
    _vibracao,
    _virtual,
)
from tests.unit.test_vpad_ff_passthrough import (
    _FakeUInput,
    _install_fake_evdev,
    _rumble_effect,
)

#: O intervalo entre dois tiques do laço (60 Hz).
TIQUE_S = 1 / 60


@pytest.fixture
def kernel_do_uhid(monkeypatch: pytest.MonkeyPatch) -> Iterator[KernelDoUhid]:
    """O `/dev/uhid` de mentira: o `os.open` do nó devolve o lado do produto."""
    k = KernelDoUhid()
    abrir = os.open

    def _abrir(caminho: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if os.fsdecode(caminho) == uhid_gamepad.UHID_NODE:
            return k.fd_do_produto()
        return abrir(caminho, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", _abrir)
    try:
        yield k
    finally:
        k.fechar()


def _o_jogo_escreve(kernel: KernelDoUhid, pad: UhidDualSense, *pares: tuple[int, int]) -> None:
    """O jogo manda estes pares, e o fio do pad atende todos antes do tique."""
    antes = pad.output_count
    for fraco, forte in pares:
        assert kernel.enfileirar(_evento_de_saida(_vibracao(fraco, forte)))
    _esperar(lambda: pad.output_count >= antes + len(pares), 1.0)
    assert pad.output_count == antes + len(pares), "o fio não atendeu a saída do jogo"


def test_uhid_o_jogo_liga_e_desliga_entre_dois_tiques_e_o_pulso_chega(
    kernel_do_uhid: KernelDoUhid,
) -> None:
    fisico = Fisico()
    pad = _virtual(Relogio(), fisico)
    try:
        _o_jogo_escreve(kernel_do_uhid, pad, (200, 200), (0, 0))

        pad.pump_ff()
        assert fisico.vibracao == [(200, 200)], (
            "o tique entregou só o último par do intervalo: o pulso sumiu"
        )
        pad.pump_ff()
        assert fisico.vibracao == [(200, 200), (0, 0)]
        pad.pump_ff()
        assert fisico.vibracao == [(200, 200), (0, 0)]
    finally:
        pad.stop()


def test_uhid_o_mesmo_par_pedido_duas_vezes_no_intervalo_sai_uma_vez(
    kernel_do_uhid: KernelDoUhid,
) -> None:
    fisico = Fisico()
    pad = _virtual(Relogio(), fisico)
    try:
        _o_jogo_escreve(kernel_do_uhid, pad, (120, 60), (120, 60))

        pad.pump_ff()
        pad.pump_ff()
        assert fisico.vibracao == [(120, 60)]
    finally:
        pad.stop()


def test_uhid_o_par_que_fica_e_o_mais_forte_sai_uma_vez_so(
    kernel_do_uhid: KernelDoUhid,
) -> None:
    """Sem pulso no intervalo (o último par é o pico), nada muda: um tique, um par."""
    fisico = Fisico()
    pad = _virtual(Relogio(), fisico)
    try:
        _o_jogo_escreve(kernel_do_uhid, pad, (40, 40), (90, 90))

        pad.pump_ff()
        assert fisico.vibracao == [(90, 90)]
        pad.pump_ff()
        assert fisico.vibracao == [(90, 90)]
    finally:
        pad.stop()


class _Uinput:
    """O pad `uinput` com o evdev de mentira, o relógio de mentira e o sink gravador."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_evdev(monkeypatch)
        self.monkeypatch = monkeypatch
        self.sink: list[tuple[int, int]] = []
        self.agora = 0.0
        self.pad = UinputGamepad.for_flavor(
            "xbox", rumble_sink=lambda fraco, forte: self.sink.append((fraco, forte))
        )
        self.pad.time_fn = lambda: self.agora
        assert self.pad.start() is True
        self.device: _FakeUInput = _FakeUInput.instances[0]
        # O fio da vibração está de pé: o tique só soma e entrega (`pump_ff`), e o
        # laço do fio roda aqui por `o_fio_atende`.
        self.pad._ff_fio = SimpleNamespace(  # type: ignore[assignment]
            is_alive=lambda: True, join=lambda timeout=None: None
        )

    def o_fio_atende(self, em: float) -> None:
        """Uma volta do laço do fio (`_atender_a_vibracao`), no instante `em`."""
        self.agora = em
        pare = threading.Event()
        voltas = iter((True, False))

        def _prontos(fds: list[int], _prazo: float) -> list[int]:
            if next(voltas):
                return list(fds)
            pare.set()
            return []

        self.monkeypatch.setattr(uinput_gamepad, "prontos_para_ler", _prontos)
        self.pad._atender_a_vibracao(self.device, 7, pare)

    def tique(self, em: float) -> list[tuple[int, int]]:
        self.agora = em
        self.pad.pump_ff()
        return list(self.sink)


def test_uinput_um_efeito_de_dez_ms_entre_dois_tiques_chega_como_o_par_e_o_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    u = _Uinput(monkeypatch)
    efeito = _rumble_effect(0, strong=0xFFFF, weak=0x8000, duration_ms=10)
    u.device.game_uploads(efeito, request_id=1)
    u.device.game_plays(0)
    u.o_fio_atende(em=0.001)

    assert u.tique(em=TIQUE_S) == [(0x80, 0xFF)], (
        "o efeito de 10 ms venceu antes da soma do tique: o toque não chegou"
    )
    assert u.tique(em=2 * TIQUE_S) == [(0x80, 0xFF), (0, 0)]
    assert u.tique(em=3 * TIQUE_S) == [(0x80, 0xFF), (0, 0)]


def test_uinput_o_efeito_tocado_e_parado_no_intervalo_conta_um_tique(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    u = _Uinput(monkeypatch)
    u.device.game_uploads(_rumble_effect(0, strong=0xFFFF, weak=0xFFFF), request_id=1)
    u.device.game_plays(0)
    u.o_fio_atende(em=0.001)
    u.device.game_stops(0)
    u.o_fio_atende(em=0.005)

    assert u.tique(em=TIQUE_S) == [(0xFF, 0xFF)]
    assert u.tique(em=2 * TIQUE_S) == [(0xFF, 0xFF), (0, 0)]


def test_uinput_o_mesmo_efeito_tocado_duas_vezes_no_intervalo_sai_uma_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    u = _Uinput(monkeypatch)
    u.device.game_uploads(_rumble_effect(0, strong=0x4000, weak=0, duration_ms=200), request_id=1)
    u.device.game_plays(0)
    u.o_fio_atende(em=0.001)
    u.device.game_plays(0)
    u.o_fio_atende(em=0.004)

    assert u.tique(em=TIQUE_S) == [(0, 0x40)]
    assert u.tique(em=2 * TIQUE_S) == [(0, 0x40)]


def test_uinput_o_efeito_com_atraso_de_cem_ms_nao_chega_antes_da_hora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    u = _Uinput(monkeypatch)
    efeito = _rumble_effect(1, strong=0xFFFF, weak=0, duration_ms=200)
    efeito.ff_replay.delay = 100
    u.device.game_uploads(efeito, request_id=2)
    u.device.game_plays(1)
    u.o_fio_atende(em=0.060)

    tiques = [0.060 + n * TIQUE_S for n in range(1, 6)]
    for t in tiques:
        cedo_ms = (t - 0.060) * 1000
        assert u.tique(em=t) == [], f"o efeito com 100 ms de atraso tocou aos {cedo_ms:.1f} ms"
    assert u.tique(em=0.160) == [(0, 0xFF)]


def test_uinput_o_efeito_com_atraso_parado_antes_de_comecar_nao_toca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    u = _Uinput(monkeypatch)
    efeito = _rumble_effect(1, strong=0xFFFF, weak=0, duration_ms=50)
    efeito.ff_replay.delay = 100
    u.device.game_uploads(efeito, request_id=2)
    u.device.game_plays(1)
    u.o_fio_atende(em=0.000)
    u.device.game_stops(1)
    u.o_fio_atende(em=0.050)

    for n in range(1, 12):
        assert u.tique(em=n * TIQUE_S) == []
