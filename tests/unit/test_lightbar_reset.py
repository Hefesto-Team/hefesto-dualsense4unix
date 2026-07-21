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
    should_reclaim_on_wake,
)

_KDEF = (0, 0, 128)  # KERNEL_DEFAULT_BLUE do backend


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


class TestShouldReclaimOnWake:
    """LIGHTBAR-BT-RESET-02 (Onda L): reenviar o 0x08 SÓ na assinatura do wake
    BT (nó sysfs voltou ao default do kernel com o desired resolvido diferente),
    nunca por timer. Falha-sem: antes da Onda L o 0x08 só saía para handles
    NOVOS, então o wake sem reabrir handle (caso 17:28) deixava a lightbar
    apagada até desconectar/reconectar."""

    def test_borda_do_wake_bt_dispara(self) -> None:
        # BT + nó voltou ao default do kernel + desired é vermelho → reclaim.
        assert should_reclaim_on_wake("bt", (255, 0, 0), _KDEF, _KDEF) is True

    def test_usb_nunca_dispara(self) -> None:
        # USB não tem o claim da lightbar — mesma assinatura, mas não mexe.
        assert should_reclaim_on_wake("usb", (255, 0, 0), _KDEF, _KDEF) is False

    def test_claim_intacto_nao_dispara(self) -> None:
        # A cor atual ainda é a desejada (claim OK) → não pisca à toa.
        assert should_reclaim_on_wake("bt", (255, 0, 0), (255, 0, 0), _KDEF) is False

    def test_desired_igual_ao_default_e_indistinguivel(self) -> None:
        # Se o próprio desired É o default do kernel, a assinatura não distingue
        # "wake" de "cor correta" → não mexe.
        assert should_reclaim_on_wake("bt", _KDEF, _KDEF, _KDEF) is False

    def test_desired_ausente_nao_dispara(self) -> None:
        assert should_reclaim_on_wake("bt", None, _KDEF, _KDEF) is False

    def test_no_ilegivel_nao_dispara(self) -> None:
        # get_rgb() devolveu None (nó ilegível) → não afirma a borda.
        assert should_reclaim_on_wake("bt", (255, 0, 0), None, _KDEF) is False


class TestOndaLFiadaNoBackend:
    """Guarda de fiação: o backend chama a função nova no connect() e loga o
    reenvio de wake — sem isso, a função pura existiria sem efeito."""

    def test_connect_chama_should_reclaim_on_wake(self) -> None:
        from pathlib import Path

        fonte = Path(
            "src/hefesto_dualsense4unix/core/backend_pydualsense.py"
        ).read_text(encoding="utf-8")
        assert "should_reclaim_on_wake" in fonte
        assert "lightbar_reset_reenviado_wake" in fonte

    def test_reclaim_de_wake_gateado_por_modo_nativo(self) -> None:
        # O laço de reclaim NÃO pode reenviar o 0x08 em Modo Nativo (output
        # mutado = o jogo é dono do LED). O gate `_output_mute` precisa estar
        # no bloco do reclaim, antes de montar os candidatos.
        import re
        from pathlib import Path

        fonte = Path(
            "src/hefesto_dualsense4unix/core/backend_pydualsense.py"
        ).read_text(encoding="utf-8")
        bloco = fonte[fonte.index("reclaim_candidates") :][:600]
        assert re.search(r"self\._output_mute", bloco), (
            "o reclaim de wake precisa ser no-op sob _output_mute (Modo Nativo)"
        )


class _FakeBtHandle:
    """Stub de handle pydualsense BT com `device` gravador (para o 0x08)."""

    class _Trigger:
        def __init__(self) -> None:
            self.mode: object = None
            self.forces: list[int] = [0] * 7

        def setForce(self, idx: int, value: int) -> None:  # noqa: N802 — API pydualsense
            self.forces[idx] = value

    class _Light:
        def __init__(self) -> None:
            self.colors: list[tuple[int, int, int]] = []
            self.playerNumber: object = None

        def setColorI(self, r: int, g: int, b: int) -> None:  # noqa: N802 — API pydualsense
            self.colors.append((r, g, b))

    class _Audio:
        def setMicrophoneLED(self, flag: bool) -> None:  # noqa: N802 — API pydualsense
            pass

    def __init__(self) -> None:
        self.connected = True
        self.triggerL = self._Trigger()
        self.triggerR = self._Trigger()
        self.light = self._Light()
        self.audio = self._Audio()
        self.conType = type("CT", (), {"name": "BT"})()
        self.device = _FakeDevice()
        self.closed = False

    def setLeftMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        pass

    def setRightMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        pass

    def close(self) -> None:
        self.closed = True


class TestReset01AdocaoSobModoNativo:
    """LIGHTBAR-BT-RESET-01 x FEAT-NATIVE-OUTPUT-MUTE-01: a adoção de handle
    BT novo NÃO pode enviar o 0x08 com o output mutado (Modo Nativo = o jogo é
    dono do hidraw; contrato de ZERO write nosso). Falha-sem: um drop+reconnect
    BT com jogo em foco reabre o handle (key/MAC estável → cai em new_handles)
    e o write cru saía por baixo do jogo — mesmo gate que o irmão RESET-02
    (wake) já tinha."""

    @staticmethod
    def _connect_um_bt_novo(*, mute: bool) -> _FakeBtHandle:
        from unittest.mock import patch

        from hefesto_dualsense4unix.core.backend_pydualsense import (
            PyDualSenseController,
        )
        from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

        reader = EvdevReader(device_path=None)
        reader._device_path = None
        inst = PyDualSenseController(evdev_reader=reader)
        inst._output_mute = mute
        handle = _FakeBtHandle()
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[("AA:BB:CC:00:00:01", b"/dev/hidraw9", False)],
        ), patch.object(PyDualSenseController, "_open_one", return_value=handle):
            inst.connect()
        return handle

    def test_modo_nativo_nao_escreve_o_0x08_na_adocao(self) -> None:
        handle = self._connect_um_bt_novo(mute=True)
        assert handle.device.reports == [], (
            "adoção sob _output_mute escreveu report cru no hidraw do jogo"
        )

    def test_sem_mute_o_0x08_continua_saindo(self) -> None:
        # Não-regressão da cura original (adoção derrubava o claim BT): sem
        # Modo Nativo o Reset LED state precisa continuar sendo enviado.
        handle = self._connect_um_bt_novo(mute=False)
        assert build_bt_release_leds_report() in handle.device.reports


class _FakeNode:
    """Nó sysfs LED fake: devolve a cor pedida e aceita escritas."""

    def __init__(self, rgb: tuple[int, int, int]) -> None:
        self._rgb = rgb

    def get_rgb(self) -> tuple[int, int, int]:
        return self._rgb

    def set_rgb(self, r: int, g: int, b: int) -> bool:
        return True

    def set_players(self, players: object) -> bool:
        return True


class TestReset02WakeSobModoNativo:
    """LIGHTBAR-BT-RESET-02 x FEAT-NATIVE-OUTPUT-MUTE-01 (comportamental): o
    reclaim de wake (handle EXISTENTE cujo nó voltou ao default do kernel) não
    pode escrever o 0x08 sob Modo Nativo — e precisa continuar escrevendo sem
    ele. Cobre o gate por execução real do connect(), não só por texto-fonte."""

    @staticmethod
    def _connect_com_wake(*, mute: bool) -> _FakeBtHandle:
        from unittest.mock import patch

        from hefesto_dualsense4unix.core.backend_pydualsense import (
            PyDualSenseController,
        )
        from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

        reader = EvdevReader(device_path=None)
        reader._device_path = None
        inst = PyDualSenseController(evdev_reader=reader)
        handle = _FakeBtHandle()
        key = "AA:BB:CC:00:00:01"
        inst._handles = {key: handle}  # type: ignore[dict-item]
        inst._primary_key = key
        inst.set_led((255, 0, 0))  # desired ≠ default do kernel
        handle.device.reports.clear()  # só interessa o que o connect() escrever
        # Assinatura do wake: o kernel resetou a classe LED para o default.
        inst._sysfs = {key: _FakeNode(_KDEF)}  # type: ignore[dict-item]
        inst._output_mute = mute
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[(key, b"/dev/hidraw9", False)],
        ):
            inst.connect()  # handle já presente → NÃO é new_handle → rota wake
        return handle

    def test_wake_em_nativo_nao_reenvia_o_0x08(self) -> None:
        handle = self._connect_com_wake(mute=True)
        assert handle.device.reports == [], (
            "reclaim de wake sob _output_mute escreveu por baixo do jogo"
        )

    def test_wake_sem_mute_reenvia_o_0x08(self) -> None:
        handle = self._connect_com_wake(mute=False)
        assert build_bt_release_leds_report() in handle.device.reports
