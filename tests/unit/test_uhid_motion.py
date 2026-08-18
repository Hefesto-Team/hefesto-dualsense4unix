"""Motion no vpad uhid (GYRO-01) — forward_motion, streaming e calibração.

O que se trava aqui:

1. **Anti-regressão do report neutro**: sem reader, `_encode_body` produz um
   payload BYTE A BYTE idêntico ao histórico (IMU zerada, 0x80 nos contatos do
   touchpad em 32/36) — quem não tem gyro fluindo não muda NADA.
2. **forward_motion** preenche a janela 15..39 verbatim, anda o seq e rejeita
   janela de tamanho errado (report torto quebraria o parse do driver).
3. **Gate de streaming**: ligado, os forwards do poll loop viram só-cache (quem
   emite é o reader); desligado, volta o delta do poll com IMU NEUTRA (nunca um
   gyro congelado).
4. **Calibração por unidade**: `calibration_0x05` válido (41 B, id 0x05) entra
   no lugar do canônico; inválido/None mantém o canônico (fail-safe).

Mesmo fake de /dev/uhid dos testes irmãos (`test_uhid_gamepad.py`) — nada real.
"""
from __future__ import annotations

import struct
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    _MOTION_NEUTRAL,
    _MOTION_WINDOW,
    _MOTION_WINDOW_LEN,
    UHID_INPUT2,
    UhidDualSense,
)

_FEATURE_09 = bytes([0x09]) + bytes.fromhex("010000ccbbaa") + bytes(13)
_CANONICAL_05 = bytes([0x05]) + bytes(range(40))


def _blueprint() -> dict[str, Any]:
    return {
        "descriptor": bytes([0x05, 0x01, 0x09, 0x05, 0xA1, 0x01]),
        "features": {
            0x05: _CANONICAL_05,
            0x09: _FEATURE_09,
            0x20: bytes([0x20]) + bytes(63),
        },
    }


class _FakeFd:
    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.reads: list[bytes] = []


@pytest.fixture()
def fake_uhid(monkeypatch: pytest.MonkeyPatch) -> _FakeFd:
    fake = _FakeFd()
    monkeypatch.setattr(uhid_gamepad.os, "open", lambda *_a, **_k: 4242)
    monkeypatch.setattr(uhid_gamepad.os, "close", lambda _fd: None)
    monkeypatch.setattr(uhid_gamepad.os, "set_blocking", lambda _fd, _b: None)

    def _write(_fd: int, data: bytes) -> int:
        fake.writes.append(data)
        return len(data)

    def _read(_fd: int, _size: int) -> bytes:
        if not fake.reads:
            raise BlockingIOError
        return fake.reads.pop(0)

    monkeypatch.setattr(uhid_gamepad.os, "write", _write)
    monkeypatch.setattr(uhid_gamepad.os, "read", _read)
    return fake


def _input_bodies(fake: _FakeFd) -> list[bytes]:
    """Payloads dos reports 0x01 emitidos (INPUT2), na ordem."""
    bodies = []
    for raw in fake.writes:
        if len(raw) < 6:
            continue
        etype, size = struct.unpack("<IH", raw[:6])
        if etype != UHID_INPUT2:
            continue
        report = raw[6 : 6 + size]
        if report and report[0] == 0x01:
            bodies.append(report[1:])
    return bodies


_WINDOW = bytes(range(100, 100 + _MOTION_WINDOW_LEN))


class TestEncodeNeutro:
    def test_report_neutro_e_identico_ao_historico(self, fake_uhid: _FakeFd) -> None:
        # Reconstrói o payload como o encoder SEMPRE fez (pré-GYRO-01):
        # zeros + 0x80 nos contatos + status + sticks neutros. Byte a byte.
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_buttons(frozenset())
        esperado = bytearray(63)
        for offset in (32, 36):
            esperado[offset] = 0x80
        esperado[52] = 0x1F
        esperado[0:6] = bytes([0x80, 0x80, 0x80, 0x80, 0, 0])
        esperado[7] = 0x08  # d-pad neutro (HAT)
        esperado[6] = 1  # seq do primeiro report emitido
        assert _input_bodies(fake_uhid)[-1] == bytes(esperado)

    def test_janela_neutra_tem_o_shape_do_kernel(self) -> None:
        assert len(_MOTION_NEUTRAL) == _MOTION_WINDOW_LEN
        assert _MOTION_NEUTRAL[32 - 15] == 0x80
        assert _MOTION_NEUTRAL[36 - 15] == 0x80
        assert sum(_MOTION_NEUTRAL) == 0x80 * 2  # todo o resto zerado


class TestForwardMotion:
    def test_preenche_a_janela_15_a_39_verbatim(self, fake_uhid: _FakeFd) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_motion(_WINDOW)
        body = _input_bodies(fake_uhid)[-1]
        assert body[_MOTION_WINDOW] == _WINDOW
        # Sticks/status não são tocados pelo motion.
        assert body[0:6] == bytes([0x80, 0x80, 0x80, 0x80, 0, 0])
        assert body[52] == 0x1F

    def test_janela_nova_anda_o_seq(self, fake_uhid: _FakeFd) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_motion(_WINDOW)
        pad.forward_motion(bytes(reversed(_WINDOW)))
        bodies = _input_bodies(fake_uhid)
        assert [b[6] for b in bodies[-2:]] == [1, 2]

    def test_janela_repetida_nao_reemite(self, fake_uhid: _FakeFd) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_motion(_WINDOW)
        antes = len(_input_bodies(fake_uhid))
        pad.forward_motion(_WINDOW)
        assert len(_input_bodies(fake_uhid)) == antes

    @pytest.mark.parametrize("tamanho", [0, 24, 26, 63])
    def test_janela_de_tamanho_errado_e_rejeitada(
        self, fake_uhid: _FakeFd, tamanho: int
    ) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_motion(bytes(tamanho))
        assert _input_bodies(fake_uhid) == []
        assert pad._motion_window == _MOTION_NEUTRAL

    def test_sem_device_e_no_op(self) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        pad.forward_motion(_WINDOW)  # não explode
        assert pad.motion_forward_count == 0

    def test_conta_janelas_emitidas(self, fake_uhid: _FakeFd) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_motion(_WINDOW)
        pad.forward_motion(_WINDOW)  # repetida: suprimida pelo delta
        pad.forward_motion(bytes(reversed(_WINDOW)))
        assert pad.motion_forward_count == 2


class TestStreamingGate:
    def test_streaming_faz_o_poll_virar_so_cache(self, fake_uhid: _FakeFd) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.set_motion_streaming(True)
        pad.forward_analog(lx=10, ly=20, rx=30, ry=40, l2=50, r2=60)
        pad.forward_buttons(frozenset({"cross"}))
        pad.forward_battery(50)
        assert _input_bodies(fake_uhid) == []  # ninguém emitiu: o reader é o relógio
        pad.forward_motion(_WINDOW)
        bodies = _input_bodies(fake_uhid)
        assert len(bodies) == 1
        # O report do reader carrega o CACHE do poll junto (sticks+botões+janela).
        assert bodies[0][0:6] == bytes([10, 20, 30, 40, 50, 60])
        assert bodies[0][7] & 0x20  # cross
        assert bodies[0][_MOTION_WINDOW] == _WINDOW

    def test_desligar_streaming_volta_ao_neutro_e_ao_delta(
        self, fake_uhid: _FakeFd
    ) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.set_motion_streaming(True)
        pad.forward_motion(_WINDOW)
        pad.set_motion_streaming(False)
        bodies = _input_bodies(fake_uhid)
        # O OFF emite na hora o report com a janela NEUTRA (fail-safe: um gyro
        # congelado no report seria rotação fantasma infinita na mira).
        assert bodies[-1][_MOTION_WINDOW] == _MOTION_NEUTRAL
        # E o poll loop volta a emitir sozinho.
        pad.forward_analog(lx=1, ly=2, rx=3, ry=4, l2=5, r2=6)
        assert _input_bodies(fake_uhid)[-1][0:6] == bytes([1, 2, 3, 4, 5, 6])

    def test_streaming_e_idempotente(self, fake_uhid: _FakeFd) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.set_motion_streaming(True)
        pad.set_motion_streaming(True)
        assert pad.motion_streaming is True
        pad.set_motion_streaming(False)
        antes = len(_input_bodies(fake_uhid))
        pad.set_motion_streaming(False)  # repetido: não reemite nada
        assert len(_input_bodies(fake_uhid)) == antes

    def test_stop_zera_o_estado_de_motion(self, fake_uhid: _FakeFd) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.set_motion_streaming(True)
        pad.forward_motion(_WINDOW)
        pad.stop()
        assert pad.motion_streaming is False
        assert pad._motion_window == _MOTION_NEUTRAL
        assert pad.motion_forward_count == 0


class TestCalibracaoPorUnidade:
    _CALIB = bytes([0x05]) + bytes([0xAB]) * 40

    def test_calibracao_valida_substitui_a_canonica(self, fake_uhid: _FakeFd) -> None:
        pad = UhidDualSense(
            player=1, blueprint=_blueprint(), calibration_0x05=self._CALIB
        )
        assert pad.start()
        assert pad._features[0x05] == self._CALIB

    def test_sem_calibracao_fica_a_canonica(self, fake_uhid: _FakeFd) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        assert pad._features[0x05] == _CANONICAL_05

    @pytest.mark.parametrize(
        "torta",
        [
            bytes([0x05]) + bytes(39),  # 40 B — curta
            bytes([0x05]) + bytes(41),  # 42 B — longa
            bytes([0x09]) + bytes(40),  # id errado
            b"",
        ],
    )
    def test_calibracao_torta_cai_na_canonica(
        self, fake_uhid: _FakeFd, torta: bytes
    ) -> None:
        pad = UhidDualSense(
            player=1, blueprint=_blueprint(), calibration_0x05=torta
        )
        assert pad.start()  # o vpad NASCE mesmo assim (invariante)
        assert pad._features[0x05] == _CANONICAL_05

    def test_for_flavor_repassa_a_calibracao(self) -> None:
        pad = UhidDualSense.for_flavor(
            "dualsense",
            player=2,
            blueprint=_blueprint(),
            calibration_0x05=self._CALIB,
        )
        assert pad is not None
        assert pad.calibration_0x05 == self._CALIB
