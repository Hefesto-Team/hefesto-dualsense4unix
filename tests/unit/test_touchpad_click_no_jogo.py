"""O CLIQUE do touchpad chega ao jogo (TOUCH-CLICK-01 / SENSOR-VIVO-01 E4)."""
from __future__ import annotations

import ast
import os
import struct
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.ds_output_report import (
    BT_INPUT_CRC_SEED,
    bt_crc32,
)
from hefesto_dualsense4unix.core.physical_report_reader import (
    BUTTONS2_OFFSET,
    INPUT_REPORT_BT_SIZE,
    MOTION_WINDOW_LEN,
    TOUCHPAD_CLICK_BIT,
    PhysicalReportReader,
    extract_touchpad_click,
)
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    UHID_INPUT2,
    UhidDualSense,
)

_RAIZ = Path(__file__).resolve().parents[2]


def _referencias(caminho: Path) -> set[str]:
    """Nomes que o módulo REFERENCIA em código — prosa e comentários fora."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Name):
            nomes.add(no.id)
        elif isinstance(no, ast.Attribute):
            nomes.add(no.attr)
        elif isinstance(no, ast.alias):
            nomes.add(no.name)
            if no.asname:
                nomes.add(no.asname)
        elif isinstance(no, ast.ImportFrom) and no.module:
            nomes.add(no.module)
    return nomes


def _referencia(nomes: set[str], alvo: str) -> bool:
    return any(alvo == nome or alvo in nome.split(".") for nome in nomes)


_CONTATO_P1 = 32
_CONTATO_P2 = 36
_SEM_DEDO = 0x80


def _usb_report(
    *, dedo: bool = False, clique: bool = False, marca: int = 0
) -> bytes:
    """Report 0x01 (64 B) do físico, com dedo e/ou clique conforme pedido."""
    raw = bytearray(64)
    raw[0] = 0x01
    raw[1:7] = bytes([0x80, 0x80, 0x80, 0x80, 0, 0])
    raw[1 + 15] = marca & 0xFF
    raw[1 + _CONTATO_P1] = 0x00 if dedo else _SEM_DEDO
    raw[1 + _CONTATO_P2] = _SEM_DEDO
    if dedo:
        raw[1 + _CONTATO_P1 + 1] = 0x40
    if clique:
        raw[1 + BUTTONS2_OFFSET] |= TOUCHPAD_CLICK_BIT
    return bytes(raw)


def _bt_report(*, clique: bool = False, corrupt: bool = False) -> bytes:
    """Report 0x31 (78 B) com CRC de INPUT (seed 0xA1) válido — ou corrompido."""
    raw = bytearray(INPUT_REPORT_BT_SIZE)
    raw[0] = 0x31
    raw[1] = 0x01
    if clique:
        raw[2 + BUTTONS2_OFFSET] |= TOUCHPAD_CLICK_BIT
    crc = bt_crc32(raw[:-4], seed=BT_INPUT_CRC_SEED)
    raw[-4:] = crc.to_bytes(4, "little")
    if corrupt:
        raw[2 + BUTTONS2_OFFSET] ^= 0xFF
    return bytes(raw)


_FEATURE_09 = bytes([0x09]) + bytes.fromhex("010000ccbbaa") + bytes(13)


def _blueprint() -> dict[str, Any]:
    return {
        "descriptor": bytes([0x05, 0x01, 0x09, 0x05, 0xA1, 0x01]),
        "features": {
            0x05: bytes([0x05]) + bytes(range(40)),
            0x09: _FEATURE_09,
            0x20: bytes([0x20]) + bytes(63),
        },
    }


class _FakeUhid:
    """Coleta o que o vpad escreve no /dev/uhid — os bytes que o jogo lê."""

    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def bodies(self) -> list[bytes]:
        """Payloads (63 B, sem o report id) dos reports 0x01 emitidos."""
        saida: list[bytes] = []
        for raw in list(self.writes):
            if len(raw) < 6:
                continue
            etype, size = struct.unpack("<IH", raw[:6])
            if etype != UHID_INPUT2:
                continue
            report = raw[6 : 6 + size]
            if report and report[0] == 0x01:
                saida.append(report[1:])
        return saida


_FD_UHID = 4242


@pytest.fixture()
def fake_uhid(monkeypatch: pytest.MonkeyPatch) -> _FakeUhid:
    fake = _FakeUhid()
    real_open, real_write = os.open, os.write
    real_read, real_close = os.read, os.close
    real_set_blocking = os.set_blocking

    def _open(path: Any, *a: Any, **k: Any) -> int:
        if str(path) == uhid_gamepad.UHID_NODE:
            return _FD_UHID
        return real_open(path, *a, **k)

    def _write(fd: int, data: bytes) -> int:
        if fd == _FD_UHID:
            fake.writes.append(bytes(data))
            return len(data)
        return real_write(fd, data)

    def _read(fd: int, size: int) -> bytes:
        if fd == _FD_UHID:
            raise BlockingIOError
        return real_read(fd, size)

    def _close(fd: int) -> None:
        if fd == _FD_UHID:
            return
        real_close(fd)

    def _set_blocking(fd: int, blocking: bool) -> None:
        if fd == _FD_UHID:
            return
        real_set_blocking(fd, blocking)

    monkeypatch.setattr(uhid_gamepad.os, "open", _open)
    monkeypatch.setattr(uhid_gamepad.os, "close", _close)
    monkeypatch.setattr(uhid_gamepad.os, "set_blocking", _set_blocking)
    monkeypatch.setattr(uhid_gamepad.os, "write", _write)
    monkeypatch.setattr(uhid_gamepad.os, "read", _read)
    return fake


def _contar(bodies: list[bytes]) -> tuple[int, int]:
    """(com dedo, com clique) — a MESMA conta do experimento da sprint."""
    com_dedo = sum(1 for b in bodies if not (b[_CONTATO_P1] & _SEM_DEDO))
    com_clique = sum(1 for b in bodies if b[BUTTONS2_OFFSET] & TOUCHPAD_CLICK_BIT)
    return com_dedo, com_clique


def _esperar(cond, timeout_s: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.005)
    return cond()


class TestExtrairOCliqueDoReportCru:
    def test_usb_sem_clique(self) -> None:
        assert extract_touchpad_click(_usb_report()) is False

    def test_usb_com_clique(self) -> None:
        assert extract_touchpad_click(_usb_report(clique=True)) is True

    def test_usb_ignora_os_outros_bits_do_mesmo_byte(self) -> None:
        raw = bytearray(_usb_report())
        raw[1 + BUTTONS2_OFFSET] = 0x01 | 0x04
        assert extract_touchpad_click(bytes(raw)) is False

    def test_bt_com_crc_valido(self) -> None:
        assert extract_touchpad_click(_bt_report(clique=True)) is True

    def test_bt_com_crc_corrompido_nao_diz_nada(self) -> None:
        assert extract_touchpad_click(_bt_report(clique=True, corrupt=True)) is None

    def test_bt_com_tamanho_errado_nao_diz_nada(self) -> None:
        assert extract_touchpad_click(_bt_report()[:64]) is None

    def test_report_de_outro_id_nao_diz_nada(self) -> None:
        assert extract_touchpad_click(bytes([0x05]) + bytes(63)) is None

    def test_report_vazio_nao_diz_nada(self) -> None:
        assert extract_touchpad_click(b"") is None

    def test_report_curto_demais_nao_diz_nada(self) -> None:
        assert extract_touchpad_click(bytes([0x01, 0x00])) is None


class TestOsNumerosBatemComOVpad:
    def test_offset_e_bit_sao_os_mesmos_do_encoder(self) -> None:
        assert BUTTONS2_OFFSET == uhid_gamepad._BUTTONS2_OFFSET
        assert TOUCHPAD_CLICK_BIT == uhid_gamepad._TOUCHPAD_BIT

    def test_o_clique_esta_fora_da_janela_de_motion(self) -> None:
        janela = range(
            prr.MOTION_WINDOW_OFFSET, prr.MOTION_WINDOW_OFFSET + MOTION_WINDOW_LEN
        )
        assert BUTTONS2_OFFSET not in janela

    def test_o_caminho_do_jogo_nao_recebe_nome_de_touchpad(self) -> None:
        from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

        nomes = set(EvdevReader.BUTTON_MAP.values())
        assert not (nomes & uhid_gamepad._TOUCHPAD_BUTTONS)


class TestOCliqueChegaAoJogo:
    """Reprodução do experimento da sprint sobre os bytes que SAEM ao jogo."""

    def _rodar_fluxo(
        self, fake: _FakeUhid, reports: list[bytes]
    ) -> list[bytes]:
        """O hidraw do físico é um pipe; o /dev/uhid é o fake da fixture."""
        lido, escrita = os.pipe()
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake",
            vpad=pad,
            max_hz=0,
            opener=lambda _path: os.dup(lido),
        )
        try:
            assert reader.start() is True
            assert _esperar(lambda: pad.motion_streaming)
            for report in reports:
                os.write(escrita, report)
                time.sleep(0.01)
            assert _esperar(lambda: reader.reports_seen >= len(reports))
        finally:
            reader.stop()
            pad.stop()
            os.close(escrita)
            os.close(lido)
        return fake.bodies()

    def test_com_dedo_e_com_clique_sobem_os_dois(
        self, fake_uhid: _FakeUhid
    ) -> None:
        """O aceite da sprint: hoje `com clique` é 0; entregue, os dois sobem."""
        fluxo = [
            _usb_report(marca=1),
            _usb_report(dedo=True, marca=2),
            _usb_report(dedo=True, clique=True, marca=3),
            _usb_report(dedo=True, clique=True, marca=4),
            _usb_report(dedo=True, marca=5),
        ]
        bodies = self._rodar_fluxo(fake_uhid, fluxo)
        com_dedo, com_clique = _contar(bodies)
        assert com_dedo > 0, "o dedo parou de chegar ao jogo (regressão do motion)"
        assert com_clique > 0, (
            "clique ZERO num report em que o dedo aparece — "
            "o caminho do jogo não recebe o clique do touchpad"
        )

    def test_o_clique_sai_no_mesmo_report_em_que_o_dedo_aparece(
        self, fake_uhid: _FakeUhid
    ) -> None:
        fluxo = [
            _usb_report(dedo=True, marca=1),
            _usb_report(dedo=True, clique=True, marca=2),
            _usb_report(dedo=True, clique=True, marca=3),
        ]
        bodies = self._rodar_fluxo(fake_uhid, fluxo)
        juntos = [
            b
            for b in bodies
            if (b[BUTTONS2_OFFSET] & TOUCHPAD_CLICK_BIT)
            and not (b[_CONTATO_P1] & _SEM_DEDO)
        ]
        assert juntos, "nenhum report saiu com dedo E clique ao mesmo tempo"

    def test_soltar_o_touchpad_apaga_o_bit(
        self, fake_uhid: _FakeUhid
    ) -> None:
        fluxo = [
            _usb_report(dedo=True, clique=True, marca=1),
            _usb_report(dedo=True, marca=2),
        ]
        bodies = self._rodar_fluxo(fake_uhid, fluxo)
        assert bodies, "o vpad não emitiu nada"
        assert not (bodies[-1][BUTTONS2_OFFSET] & TOUCHPAD_CLICK_BIT)


class TestOEncoderDoVpad:
    def test_forward_touchpad_click_acende_o_bit(self, fake_uhid: _FakeUhid) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_touchpad_click(True)
        assert fake_uhid.bodies()[-1][BUTTONS2_OFFSET] & TOUCHPAD_CLICK_BIT
        assert pad.touchpad_click_count == 1

    def test_o_clique_sobrevive_ao_forward_buttons_do_poll_loop(
        self, fake_uhid: _FakeUhid
    ) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_touchpad_click(True)
        pad.forward_buttons(frozenset({"cross"}))
        corpo = fake_uhid.bodies()[-1]
        assert corpo[BUTTONS2_OFFSET] & TOUCHPAD_CLICK_BIT
        assert corpo[7] & 0x20

    def test_clique_repetido_nao_reemite(self, fake_uhid: _FakeUhid) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_touchpad_click(True)
        antes = len(fake_uhid.bodies())
        pad.forward_touchpad_click(True)
        assert len(fake_uhid.bodies()) == antes

    def test_emite_mesmo_com_streaming_ligado(self, fake_uhid: _FakeUhid) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.set_motion_streaming(True)
        antes = len(fake_uhid.bodies())
        pad.forward_touchpad_click(True)
        assert len(fake_uhid.bodies()) > antes
        assert fake_uhid.bodies()[-1][BUTTONS2_OFFSET] & TOUCHPAD_CLICK_BIT

    def test_nome_de_botao_continua_valendo(self, fake_uhid: _FakeUhid) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_buttons(frozenset({"touchpad_middle_press"}))
        assert fake_uhid.bodies()[-1][BUTTONS2_OFFSET] & TOUCHPAD_CLICK_BIT


class _FakeVpad:
    player = 2

    def __init__(self) -> None:
        self.cliques: list[bool] = []
        self.streaming: list[bool] = []
        self.windows: list[bytes] = []

    def forward_motion(self, window: bytes) -> None:
        self.windows.append(bytes(window))

    def forward_touchpad_click(self, pressed: bool) -> None:
        self.cliques.append(bool(pressed))

    def set_motion_streaming(self, on: bool) -> None:
        self.streaming.append(bool(on))


class TestCoopCadaJogadorTemOSeu:
    def test_o_reader_entrega_o_clique_ao_vpad_daquele_jogador(self) -> None:
        p1, p2 = _FakeVpad(), _FakeVpad()
        r1 = PhysicalReportReader(path_provider=lambda: None, vpad=p1)
        r2 = PhysicalReportReader(path_provider=lambda: None, vpad=p2)
        r2._observe_touchpad_click(_usb_report(dedo=True, clique=True))
        assert p2.cliques == [True]
        assert p1.cliques == [], "o clique do P2 vazou para o vpad do P1"
        assert r2.touchpad_clicks == 1
        assert r1.touchpad_clicks == 0

    def test_o_coop_sobe_o_reader_do_caminho_do_jogo(self) -> None:
        nomes = _referencias(
            _RAIZ / "src/hefesto_dualsense4unix/daemon/subsystems/coop.py"
        )
        assert _referencia(nomes, "PhysicalReportReader")
        assert not _referencia(nomes, "sensor_hub")

    def test_o_reader_nao_conhece_o_sensor_hub(self) -> None:
        nomes = _referencias(
            _RAIZ / "src/hefesto_dualsense4unix/core/physical_report_reader.py"
        )
        assert not _referencia(nomes, "sensor_hub"), (
            "o caminho do jogo passou a depender do leitor sob demanda da janela"
        )
        assert not _referencia(nomes, "SensorHub")


class TestOCliqueNaoPrende:
    def test_perder_o_streaming_solta_o_botao(self, fake_uhid: _FakeUhid) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.set_motion_streaming(True)
        pad.forward_touchpad_click(True)
        assert pad.touchpad_click is True
        pad.set_motion_streaming(False)
        assert pad.touchpad_click is False
        assert not (fake_uhid.bodies()[-1][BUTTONS2_OFFSET] & TOUCHPAD_CLICK_BIT)

    def test_o_reader_esquece_o_clique_ao_perder_o_fd(self) -> None:
        vpad = _FakeVpad()
        reader = PhysicalReportReader(path_provider=lambda: None, vpad=vpad)
        reader._observe_touchpad_click(_usb_report(clique=True))
        assert vpad.cliques == [True]
        reader._reset_touchpad_click()
        reader._observe_touchpad_click(_usb_report(clique=True))
        assert vpad.cliques == [True, True]

    def test_stop_do_reader_solta_o_clique_no_vpad(self) -> None:
        vpad = _FakeVpad()
        reader = PhysicalReportReader(path_provider=lambda: None, vpad=vpad)
        reader._observe_touchpad_click(_usb_report(clique=True))
        reader.stop()
        assert vpad.streaming[-1] is False

    def test_crc_ruim_nao_solta_um_clique_apertado(self) -> None:
        vpad = _FakeVpad()
        reader = PhysicalReportReader(path_provider=lambda: None, vpad=vpad)
        reader._observe_touchpad_click(_usb_report(clique=True))
        reader._observe_touchpad_click(_bt_report(corrupt=True))
        assert vpad.cliques == [True], "rádio corrompido soltou o botão"

    def test_vpad_sem_o_metodo_degrada_calado(self) -> None:
        class _Uinput:
            player = 1

        reader = PhysicalReportReader(path_provider=lambda: None, vpad=_Uinput())
        reader._observe_touchpad_click(_usb_report(clique=True))
        assert reader.touchpad_clicks == 0

    def test_vpad_que_explode_nao_derruba_o_reader(self) -> None:
        class _Bomba(_FakeVpad):
            def forward_touchpad_click(self, pressed: bool) -> None:
                raise RuntimeError("boom")

        reader = PhysicalReportReader(path_provider=lambda: None, vpad=_Bomba())
        reader._observe_touchpad_click(_usb_report(clique=True))


class TestOCursorNaoAnda:
    def test_a_fiacao_do_clique_nao_fala_com_cursor_nenhum(self) -> None:
        nomes = _referencias(
            _RAIZ / "src/hefesto_dualsense4unix/core/physical_report_reader.py"
        )
        for proibido in (
            "TouchpadReader",
            "consume_motion",
            "emit_touchpad_move",
            "UinputMouseDevice",
            "mouse",
        ):
            assert not _referencia(nomes, proibido), (
                f"o caminho do clique passou a chamar {proibido}"
            )

    def test_o_poll_loop_continua_descartando_o_movimento_com_vpad_de_pe(
        self,
    ) -> None:
        fonte = (
            _RAIZ / "src/hefesto_dualsense4unix/daemon/lifecycle.py"
        ).read_text(encoding="utf-8")
        alvo = "if grace_passed and self._gamepad_device is not None:"
        assert alvo in fonte
        trecho = fonte.split(alvo, 1)[1][:600]
        assert "discard_touchpad_motion" in trecho

    def test_a_regra_76_continua_tirando_o_no_do_vpad_do_libinput(self) -> None:
        regra = (
            _RAIZ / "assets/76-dualsense-touchpad-libinput-ignore.rules"
        ).read_text(encoding="utf-8")
        # TOUCHPAD-DO-SISTEMA-01 (09/08/2026): o curinga `*DualSense*Touchpad`
        assert 'ATTRS{name}=="*Hefesto*Touchpad"' in regra
        assert 'ATTRS{uniq}=="02:fe:*"' in regra
        assert 'ENV{LIBINPUT_IGNORE_DEVICE}="1"' in regra

    def test_o_vpad_nao_ganhou_metodo_de_cursor(self) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        for proibido in ("emit_touchpad_move", "consume_motion", "forward_cursor"):
            assert not hasattr(pad, proibido)
