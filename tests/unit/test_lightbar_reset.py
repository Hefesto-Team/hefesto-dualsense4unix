"""LIGHTBAR-BT-RESET-01 — o report "Reset LED state" que destrava a lightbar.

Formato validado contra o layout do hid-playstation DESTA máquina (estudo
2026-07-18, por desmontagem do módulo): header 0x31/seq<<4/tag 0x10, common em
[3..49] (flag1=0x08 em [4]), CRC-32 seed 0xA2 little-endian em [74..77].
"""
from __future__ import annotations

import zlib
from typing import Any

from hefesto_dualsense4unix.core.lightbar_reset import (
    BT_REPORT_LEN,
    build_bt_release_leds_report,
    send_release_leds,
)


class TestBuildReport:
    def test_header_e_tamanho(self) -> None:
        r = build_bt_release_leds_report()
        assert len(r) == BT_REPORT_LEN == 78
        assert r[0] == 0x31  # report id BT
        assert r[1] == 0x00  # seq 0 no nibble alto
        assert r[2] == 0x10  # tag mágico obrigatório

    def test_flag1_reset_leds_e_resto_zerado(self) -> None:
        r = build_bt_release_leds_report()
        assert r[3] == 0x00  # valid_flag0: nada de rumble/haptics
        assert r[4] == 0x08  # valid_flag1: SÓ o Reset LED state
        # nenhum outro byte do common ligado (não toca cor/player/mute/rumble).
        assert all(b == 0 for b in r[5:74])

    def test_seq_no_nibble_alto_com_mascara(self) -> None:
        assert build_bt_release_leds_report(seq=3)[1] == 0x30
        assert build_bt_release_leds_report(seq=15)[1] == 0xF0
        # >15 é mascarado (wrap de 4 bits), nunca vaza para o nibble baixo.
        assert build_bt_release_leds_report(seq=16)[1] == 0x00

    def test_crc_confere_com_a_receita_0xa2(self) -> None:
        r = build_bt_release_leds_report(seq=5)
        esperado = zlib.crc32(b"\xa2" + r[:74]) & 0xFFFFFFFF
        assert int.from_bytes(r[74:78], "little") == esperado


class _FakeDevice:
    def __init__(self, written_ret: Any = None, raises: bool = False) -> None:
        self.reports: list[bytes] = []
        self._ret = written_ret
        self._raises = raises

    def write(self, data: bytes) -> Any:
        if self._raises:
            raise OSError("hidraw sumiu")
        self.reports.append(bytes(data))
        return self._ret if self._ret is not None else len(data)


class TestSendReleaseLeds:
    def test_envia_o_report_e_devolve_true(self) -> None:
        dev = _FakeDevice()
        assert send_release_leds(dev) is True
        assert len(dev.reports) == 1
        assert dev.reports[0] == build_bt_release_leds_report()

    def test_write_none_conta_como_sucesso(self) -> None:
        # hidapi pode devolver None em write OK (binding sem retorno).
        class _D(_FakeDevice):
            def write(self, data: bytes) -> None:
                self.reports.append(bytes(data))
                return None

        dev = _D()
        assert send_release_leds(dev) is True

    def test_falha_e_best_effort(self) -> None:
        assert send_release_leds(_FakeDevice(raises=True)) is False

    def test_write_incompleto_devolve_false(self) -> None:
        assert send_release_leds(_FakeDevice(written_ret=10)) is False
