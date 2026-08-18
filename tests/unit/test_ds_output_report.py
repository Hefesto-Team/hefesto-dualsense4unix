"""BTREPORT-02 — o builder comum do output report DS5 (USB 0x02 / BT 0x31).

Layout validado contra o `hid-playstation` do kernel (structs
`dualsense_output_report_usb`/`_bt`/`_common`), nunca contra a pydualsense
(cujo 0x31 é malformado — o firmware o descarta). O CRC de referência é
recalculado AQUI com zlib puro, independente do builder.
"""
from __future__ import annotations

import zlib

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep


def _crc_referencia(report: bytes | bytearray) -> int:
    """Receita canônica: seed 0xA2 (header HIDP DATA|OUTPUT) + bytes [0..73]."""
    return zlib.crc32(b"\xa2" + bytes(report[:74])) & 0xFFFFFFFF


def _common_marcado() -> bytearray:
    """Payload de 47 bytes com todos os offsets distinguíveis (0..46)."""
    return bytearray(range(rep.COMMON_LEN))


class TestBuildUsb:
    def test_envelope_e_payload(self) -> None:
        common = _common_marcado()
        r = rep.build_usb_report(common)
        assert len(r) == rep.USB_REPORT_LEN == 64
        assert r[0] == 0x02
        assert bytes(r[1 : 1 + rep.COMMON_LEN]) == bytes(common)
        assert all(b == 0 for b in r[1 + rep.COMMON_LEN :])  # padding zero

    def test_common_de_tamanho_errado_e_erro(self) -> None:
        with pytest.raises(ValueError):
            rep.build_usb_report(bytearray(46))


class TestBuildBt:
    def test_envelope_seq_tag_e_payload(self) -> None:
        common = _common_marcado()
        r = rep.build_bt_report(common, seq=5)
        assert len(r) == rep.BT_REPORT_LEN == 78
        assert r[0] == 0x31
        assert r[1] == 0x50  # seq no nibble ALTO
        assert r[2] == 0x10  # tag mágico obrigatório
        assert bytes(r[3 : 3 + rep.COMMON_LEN]) == bytes(common)
        assert all(b == 0 for b in r[3 + rep.COMMON_LEN : 74])  # reservado

    def test_crc_confere_com_a_receita_0xa2(self) -> None:
        r = rep.build_bt_report(_common_marcado(), seq=7)
        assert int.from_bytes(r[74:78], "little") == _crc_referencia(r)

    def test_seq_mascarado_em_4_bits(self) -> None:
        assert rep.build_bt_report(bytearray(47), seq=15)[1] == 0xF0
        assert rep.build_bt_report(bytearray(47), seq=16)[1] == 0x00

    def test_vetor_conhecido_release_leds(self) -> None:
        """Vetor de referência: o report de Reset LED state (flag1=0x08) que
        já foi VALIDADO AO VIVO (LIGHTBAR-BT-RESET-01) sai byte a byte igual
        pelo builder comum."""
        from hefesto_dualsense4unix.core.lightbar_reset import (
            build_bt_release_leds_report,
        )

        common = bytearray(rep.COMMON_LEN)
        common[1] = rep.VALID_FLAG1_RELEASE_LEDS
        assert bytes(rep.build_bt_report(common, seq=0)) == (
            build_bt_release_leds_report(seq=0)
        )
        # E o CRC do vetor confere com a receita independente.
        r = rep.build_bt_report(common, seq=0)
        assert int.from_bytes(r[74:78], "little") == _crc_referencia(r)


class TestStampSeq:
    def test_carimba_seq_e_recalcula_crc(self) -> None:
        r = rep.build_bt_report(_common_marcado(), seq=0)
        original = bytes(r)
        rep.stamp_bt_seq(r, 9)
        assert r[1] == 0x90
        assert int.from_bytes(r[74:78], "little") == _crc_referencia(r)
        # Só seq+CRC mudam — payload intacto.
        assert bytes(r[2:74]) == original[2:74]

    def test_funciona_em_list_de_ints(self) -> None:
        """O report_thread trabalha com list[int] — o carimbo tem que aceitar."""
        r = list(rep.build_bt_report(_common_marcado(), seq=0))
        rep.stamp_bt_seq(r, 3)
        assert r[1] == 0x30
        assert int.from_bytes(bytes(r[74:78]), "little") == _crc_referencia(
            bytes(r)
        )

    def test_rejeita_buffer_que_nao_e_0x31(self) -> None:
        with pytest.raises(ValueError):
            rep.stamp_bt_seq(bytearray(64), 1)
        usb = rep.build_usb_report(bytearray(rep.COMMON_LEN))
        with pytest.raises(ValueError):
            rep.stamp_bt_seq(usb, 1)
