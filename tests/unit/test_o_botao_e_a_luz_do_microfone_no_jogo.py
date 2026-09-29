"""O botão do microfone chega ao jogo (O-BOTAO-E-A-LUZ-DO-MICROFONE-NO-JOGO-01).

A Forja de 29/09 (sala «A Voz») reprovou *«o botão do microfone nunca
chegou»*. A causa, lida no código: o `hid-playstation` consome o botão e o
evdev não o traz; os dois caminhos do jogo (o primário e o co-op) montam os
botões só do evdev; e o `PhysicalReportReader`, que já lê o mesmo byte para o
clique do touchpad, não entregava o bit. O `buttons[2] & 0x04` do pad virtual
saía zero no cabo e no rádio, P1 a P4.

As réguas usam o `UhidDualSense` e o `PhysicalReportReader` de produção. Os
números não vêm do vpad: o bit é o `DS_BUTTONS2_MIC_MUTE = 0x04` do
`hid-playstation.c`, escrito aqui à mão, e o report emitido é relido por um
parser do próprio teste. Nenhum hidraw, /dev/uhid ou controle real é tocado:
o hidraw do físico é um `os.pipe()` e o /dev/uhid é um dublê por fd.
"""
from __future__ import annotations

import os
import struct
import time
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.ds_output_report import (
    BT_INPUT_CRC_SEED,
    bt_crc32,
)
from hefesto_dualsense4unix.core.physical_report_reader import PhysicalReportReader
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    UHID_INPUT2,
    UhidDualSense,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

#: `DS_BUTTONS2_MIC_MUTE` do `drivers/hid/hid-playstation.c`, e o byte do
#: `struct dualsense_input_report` em que ele mora (`buttons[2]`, o décimo
#: byte do payload). Escritos à mão: a régua não pergunta ao vpad o número
#: que o vpad escreve.
_BIT_DO_MIC = 0x04
_BYTE_BUTTONS2 = 9
_BIT_DO_CLIQUE = 0x02
_BIT_DO_PS = 0x01


# --------------------------------------------------------------------------
# Reports crus do controle FÍSICO
# --------------------------------------------------------------------------


def _usb(*, mic: bool = False, marca: int = 0) -> bytes:
    """Report 0x01 (64 B) do cabo; `marca` muda o giroscópio entre reports."""
    raw = bytearray(64)
    raw[0] = 0x01
    raw[1:5] = bytes([0x80, 0x80, 0x80, 0x80])
    raw[1 + 15] = marca & 0xFF
    raw[1 + 32] = 0x80
    raw[1 + 36] = 0x80
    if mic:
        raw[1 + _BYTE_BUTTONS2] |= _BIT_DO_MIC
    return bytes(raw)


def _bt(
    *, mic: bool = False, marca: int = 0, corrupto: bool = False, audio: bool = False
) -> bytes:
    """Report 0x31 (78 B) do rádio com o CRC de INPUT (seed 0xA1)."""
    raw = bytearray(78)
    raw[0] = 0x31
    raw[1] = 0x02 if audio else 0x00
    raw[2:6] = bytes([0x80, 0x80, 0x80, 0x80])
    raw[2 + 15] = marca & 0xFF
    raw[2 + 32] = 0x80
    raw[2 + 36] = 0x80
    if mic:
        raw[2 + _BYTE_BUTTONS2] |= _BIT_DO_MIC
    raw[-4:] = bt_crc32(raw[:-4], seed=BT_INPUT_CRC_SEED).to_bytes(4, "little")
    if corrupto:
        raw[2 + _BYTE_BUTTONS2] ^= _BIT_DO_MIC  # depois do CRC
    return bytes(raw)


# --------------------------------------------------------------------------
# /dev/uhid de mentira, um fd por vpad
# --------------------------------------------------------------------------


class _UhidPorFd:
    """Guarda o que cada vpad escreve no /dev/uhid, separado por fd."""

    def __init__(self) -> None:
        self.proximo = 4242
        self.escritas: dict[int, list[bytes]] = {}

    def corpos(self, fd: int) -> list[bytes]:
        """Payloads (63 B, sem o id) dos reports 0x01 emitidos por um vpad."""
        saida: list[bytes] = []
        for raw in list(self.escritas.get(fd, [])):
            if len(raw) < 6:
                continue
            etype, size = struct.unpack("<IH", raw[:6])
            if etype != UHID_INPUT2:
                continue
            report = raw[6 : 6 + size]
            if report and report[0] == 0x01:
                saida.append(report[1:])
        return saida


@pytest.fixture()
def uhid(monkeypatch: pytest.MonkeyPatch) -> _UhidPorFd:
    fake = _UhidPorFd()
    real_open, real_write = os.open, os.write
    real_read, real_close = os.read, os.close
    real_set_blocking = os.set_blocking

    def _eh_nosso(fd: int) -> bool:
        return fd in fake.escritas

    def _open(path: Any, *a: Any, **k: Any) -> int:
        if str(path) == uhid_gamepad.UHID_NODE:
            fd = fake.proximo
            fake.proximo += 1
            fake.escritas[fd] = []
            return fd
        return real_open(path, *a, **k)

    def _write(fd: int, data: bytes) -> int:
        if _eh_nosso(fd):
            fake.escritas[fd].append(bytes(data))
            return len(data)
        return real_write(fd, data)

    def _read(fd: int, size: int) -> bytes:
        if _eh_nosso(fd):
            raise BlockingIOError
        return real_read(fd, size)

    def _close(fd: int) -> None:
        if _eh_nosso(fd):
            return
        real_close(fd)

    def _set_blocking(fd: int, blocking: bool) -> None:
        if _eh_nosso(fd):
            return
        real_set_blocking(fd, blocking)

    monkeypatch.setattr(os, "open", _open)
    monkeypatch.setattr(os, "close", _close)
    monkeypatch.setattr(os, "set_blocking", _set_blocking)
    monkeypatch.setattr(os, "write", _write)
    monkeypatch.setattr(os, "read", _read)
    return fake


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


def _vpad(jogador: int = 1) -> UhidDualSense:
    pad = UhidDualSense(player=jogador, blueprint=_blueprint())
    assert pad.start()
    return pad


def _mic_aceso(corpo: bytes) -> bool:
    return bool(corpo[_BYTE_BUTTONS2] & _BIT_DO_MIC)


def _o_jogo_ve_o_mic(fake: _UhidPorFd, fd: int) -> bool:
    """O último report que o jogo leu tem o bit? Nenhum report = não tem."""
    corpos = fake.corpos(fd)
    return bool(corpos) and _mic_aceso(corpos[-1])


def _esperar(cond: Callable[[], bool], timeout_s: float = 3.0) -> bool:
    limite = time.monotonic() + timeout_s
    while time.monotonic() < limite:
        if cond():
            return True
        time.sleep(0.005)
    return cond()


def _rodar_pelo_pipe(fake: _UhidPorFd, reports: list[bytes]) -> list[bytes]:
    """O laço de leitura DE PRODUÇÃO, com o hidraw do físico num pipe."""
    lido, escrita = os.pipe()
    pad = _vpad()
    fd = pad._fd
    assert fd is not None
    leitor = PhysicalReportReader(
        path_provider=lambda: "/dev/hidraw-de-mentira",
        vpad=pad,
        max_hz=0,
        opener=lambda _path: os.dup(lido),
    )
    try:
        assert leitor.start() is True
        assert _esperar(lambda: pad.motion_streaming)
        for report in reports:
            os.write(escrita, report)
            time.sleep(0.01)  # um report por read: o pipe é um stream
        assert _esperar(lambda: leitor.reports_seen >= len(reports))
    finally:
        leitor.stop()
        pad.stop()
        os.close(escrita)
        os.close(lido)
    return fake.corpos(fd)


# --------------------------------------------------------------------------
# 0. O número do bit
# --------------------------------------------------------------------------


class TestONumeroDoBit:
    def test_o_reader_le_o_bit_do_driver(self) -> None:
        assert prr.MIC_BUTTON_BIT == _BIT_DO_MIC
        assert prr.BUTTONS2_OFFSET == _BYTE_BUTTONS2

    def test_o_vpad_escreve_o_bit_do_driver(self) -> None:
        assert uhid_gamepad._BUTTONS2_BITS["mic_btn"] == _BIT_DO_MIC
        assert uhid_gamepad._BUTTONS2_OFFSET == _BYTE_BUTTONS2


# --------------------------------------------------------------------------
# 1. O aperto chega ao report do vpad, no cabo e no rádio
# --------------------------------------------------------------------------


class TestOApertoChegaAoJogo:
    """Mordida: sem a chamada do observador no laço, os dois reprovam."""

    @pytest.mark.parametrize("transporte", ["cabo", "radio"])
    def test_acende_e_apaga_com_o_fisico(
        self, uhid: _UhidPorFd, transporte: str
    ) -> None:
        fazer = _usb if transporte == "cabo" else _bt
        fluxo = [
            fazer(marca=1),
            fazer(mic=True, marca=2),
            fazer(mic=True, marca=3),
            fazer(marca=4),
        ]
        corpos = _rodar_pelo_pipe(uhid, fluxo)
        assert any(_mic_aceso(c) for c in corpos), (
            f"no {transporte}, o botão do microfone apertado no físico nunca "
            "acendeu o bit 0x04 do buttons[2] no report que o jogo lê"
        )
        acesos = [i for i, c in enumerate(corpos) if _mic_aceso(c)]
        apagado_depois = [c for c in corpos[acesos[-1] + 1 :] if not _mic_aceso(c)]
        assert apagado_depois, f"no {transporte}, soltar o botão não apagou o bit"

    def test_o_botao_nao_acende_o_clique_nem_o_ps(self, uhid: _UhidPorFd) -> None:
        corpos = _rodar_pelo_pipe(uhid, [_usb(marca=1), _usb(mic=True, marca=2)])
        com_mic = [c for c in corpos if _mic_aceso(c)]
        assert com_mic
        assert not any(
            c[_BYTE_BUTTONS2] & (_BIT_DO_CLIQUE | _BIT_DO_PS) for c in com_mic
        )


# --------------------------------------------------------------------------
# 2. "Não sei" não solta o botão
# --------------------------------------------------------------------------


class _VpadQueGuarda:
    """Dublê do vpad com o método que o reader procura, e o que chegou."""

    def __init__(self) -> None:
        self.entregas: list[bool] = []

    def forward_mic_button(self, pressed: bool) -> None:
        self.entregas.append(bool(pressed))

    def set_motion_streaming(self, _on: bool) -> None:
        return None


def _leitor(vpad: Any) -> PhysicalReportReader:
    return PhysicalReportReader(path_provider=lambda: None, vpad=vpad, max_hz=0)


class TestONaoSeiNaoSolta:
    """Mordida: tratar o `None` do CRC ruim como `False` reprova."""

    @pytest.mark.parametrize(
        "ruim",
        [
            _bt(mic=False, corrupto=True),
            _bt(audio=True),
            _bt()[:64],
            bytes([0x05]) + bytes(63),
        ],
        ids=["crc-ruim", "audio-do-radio", "curto", "outro-id"],
    )
    def test_report_ruim_nao_mexe(self, ruim: bytes) -> None:
        vpad = _VpadQueGuarda()
        leitor = _leitor(vpad)
        leitor._observe_mic_button(_bt(mic=True))
        leitor._observe_mic_button(ruim)
        assert vpad.entregas == [True], (
            "um report que não diz nada soltou (ou reapertou) o botão"
        )
        assert leitor.mic_button_forwards == 1

    def test_so_borda(self) -> None:
        vpad = _VpadQueGuarda()
        leitor = _leitor(vpad)
        for _ in range(10):
            leitor._observe_mic_button(_usb(mic=True))
        leitor._observe_mic_button(_usb())
        assert vpad.entregas == [True, False]

    def test_vpad_sem_o_metodo_degrada_calado(self) -> None:
        class _SemMetodo:
            def set_motion_streaming(self, _on: bool) -> None:
                return None

        leitor = _leitor(_SemMetodo())
        leitor._observe_mic_button(_usb(mic=True))
        assert leitor.mic_button_forwards == 0


# --------------------------------------------------------------------------
# 3. O tique do evdev não apaga o bit
# --------------------------------------------------------------------------


class TestOTiqueNaoApaga:
    """Mordida: gravar o botão no `_buttons` reprova."""

    def test_dez_tiques_sem_mic_btn(self, uhid: _UhidPorFd) -> None:
        pad = _vpad()
        fd = pad._fd
        assert fd is not None
        pad.set_motion_streaming(True)
        pad.forward_mic_button(True)
        for i in range(10):
            pad.forward_buttons(frozenset({"cross"} if i % 2 else set()))
            pad.forward_motion(bytes([i + 1]) + bytes(prr.MOTION_WINDOW_LEN - 1))
        corpo = uhid.corpos(fd)[-1]
        assert _mic_aceso(corpo), "o tique do evdev apagou o botão do microfone"
        assert pad.mic_button_count == 1
        pad.stop()

    def test_o_mic_btn_do_conjunto_continua_valendo(self, uhid: _UhidPorFd) -> None:
        pad = _vpad()
        fd = pad._fd
        assert fd is not None
        pad.forward_buttons(frozenset({"mic_btn"}))
        assert _mic_aceso(uhid.corpos(fd)[-1])
        pad.stop()


# --------------------------------------------------------------------------
# 4. O hotplug não prende o dedo
# --------------------------------------------------------------------------


class TestOHotplugNaoPrende:
    """Mordida: tirar o esquecimento (do reader ou do vpad) reprova."""

    def test_perda_e_reabertura(self, uhid: _UhidPorFd) -> None:
        pad = _vpad()
        fd = pad._fd
        assert fd is not None
        leitor = _leitor(pad)
        pad.set_motion_streaming(True)
        leitor._observe_mic_button(_usb(mic=True))
        assert _mic_aceso(uhid.corpos(fd)[-1])
        # A perda do fd, como o laço a faz: esquece e desliga o streaming.
        leitor._reset_mic_button()
        pad.set_motion_streaming(False)
        assert not _mic_aceso(uhid.corpos(fd)[-1]), (
            "perder o físico com o dedo no botão deixou o bit preso no jogo"
        )
        pad.set_motion_streaming(True)
        leitor._observe_mic_button(_usb())
        assert not _mic_aceso(uhid.corpos(fd)[-1])
        leitor._observe_mic_button(_usb(mic=True, marca=9))
        assert _mic_aceso(uhid.corpos(fd)[-1]), (
            "depois da reabertura o aperto não voltou a chegar ao jogo"
        )
        pad.stop()

    def test_reabrir_com_o_dedo_apertado_reentrega(self, uhid: _UhidPorFd) -> None:
        pad = _vpad()
        fd = pad._fd
        assert fd is not None
        leitor = _leitor(pad)
        pad.set_motion_streaming(True)
        leitor._observe_mic_button(_usb(mic=True))
        leitor._reset_mic_button()
        pad.set_motion_streaming(False)
        pad.set_motion_streaming(True)
        leitor._observe_mic_button(_usb(mic=True))
        assert _mic_aceso(uhid.corpos(fd)[-1])
        pad.stop()


# --------------------------------------------------------------------------
# 5. O 0x02 que o driver do vpad manda a cada aperto
# --------------------------------------------------------------------------


def _evento_de_output(corpo: bytes) -> bytes:
    """UHID_OUTPUT: 4 B de tipo + data[4096] + size + rtype."""
    report = bytes([0x02]) + corpo
    dados = bytearray(4 + uhid_gamepad.HID_MAX_DESCRIPTOR_SIZE + 2 + 1)
    dados[4 : 4 + len(report)] = report
    struct.pack_into(
        "<H", dados, 4 + uhid_gamepad.HID_MAX_DESCRIPTOR_SIZE, len(report)
    )
    return bytes(dados)


#: `struct dualsense_output_report_common`: `mute_button_led` e
#: `power_save_control` são o nono e o décimo byte.
_MUTE_BUTTON_LED = 8
_POWER_SAVE_CONTROL = 9


def _corpo_do_driver(mudo: bool) -> bytes:
    """O que o `hid-playstation` do lado do vpad escreve ao alternar o mudo.

    `dualsense_output_worker`: `valid_flag1 |= MIC_MUTE_LED_CONTROL_ENABLE |
    POWER_SAVE_CONTROL_ENABLE`, o `mute_button_led` e o bit de mudo do
    `power_save_control`; `valid_flag0` zero e os motores zero.
    """
    corpo = bytearray(47)
    corpo[1] = (
        rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
        | rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE
    )
    corpo[_MUTE_BUTTON_LED] = 1 if mudo else 0
    corpo[_POWER_SAVE_CONTROL] = rep.POWER_SAVE_MIC_MUTE if mudo else 0
    return bytes(corpo)


def _corpo_do_jogo_vibrando(fraco: int, forte: int) -> bytes:
    corpo = bytearray(47)
    corpo[0] = 0x01 | 0x02
    corpo[2] = fraco
    corpo[3] = forte
    return bytes(corpo)


class _Pias:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, Any]] = []

    def ligar(self, pad: UhidDualSense) -> None:
        pad.rumble_sink = lambda w, s: self.chamadas.append(("rumble", (w, s)))
        pad.trigger_sink = lambda lado, v: self.chamadas.append(("gatilho", lado))
        pad.lightbar_sink = lambda r, g, b: self.chamadas.append(("barra", (r, g, b)))
        pad.player_led_sink = lambda *a: self.chamadas.append(("numero", a))


@pytest.fixture()
def jogo_aberto(uhid: _UhidPorFd) -> Iterator[tuple[UhidDualSense, _Pias]]:
    pad = _vpad()
    pias = _Pias()
    pias.ligar(pad)
    pad._game_open = True
    pad._bound_at = pad.time_fn() - 10.0
    try:
        yield pad, pias
    finally:
        pad.stop()


class TestO0x02DoDriverNaoViraEscrita:
    """O aperto agora chega ao driver do vpad, que responde com um 0x02."""

    def test_nao_chama_pia_nenhuma(
        self, jogo_aberto: tuple[UhidDualSense, _Pias], uhid: _UhidPorFd
    ) -> None:
        pad, pias = jogo_aberto
        fd = pad._fd
        assert fd is not None
        antes = len(uhid.escritas[fd])
        for mudo in (True, False, True, False):
            pad._handle_output(_evento_de_output(_corpo_do_driver(mudo)))
            pad._flush_replicas()
        assert pias.chamadas == [], (
            f"o 0x02 do driver do vpad virou escrita no controle: {pias.chamadas}"
        )
        assert len(uhid.escritas[fd]) == antes, "o 0x02 do driver virou eco no jogo"
        assert pad.ff_descartado_count == 0
        assert pad.mic_led_do_jogo_recusado == 0, (
            "o 0x02 do driver do vpad foi contado como pedido de luz do jogo"
        )

    def test_o_pedido_de_luz_do_jogo_e_contado_e_nao_pinta(
        self, jogo_aberto: tuple[UhidDualSense, _Pias]
    ) -> None:
        """Mordida: sem o contador, reprova."""
        pad, pias = jogo_aberto
        corpo = bytearray(47)
        corpo[1] = rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
        corpo[_MUTE_BUTTON_LED] = 2  # piscando, na língua da Sony
        pad._handle_output(_evento_de_output(bytes(corpo)))
        pad._flush_replicas()
        assert pias.chamadas == [], "o pedido de luz do jogo pintou o controle"
        assert pad.mic_led_do_jogo_recusado == 1
        assert pad.mic_led_do_jogo_amostra == 2

    def test_nao_para_a_vibracao_do_jogo(
        self, jogo_aberto: tuple[UhidDualSense, _Pias]
    ) -> None:
        """Mordida: com o gate do `_fala_de_vibracao` arrancado, reprova."""
        pad, pias = jogo_aberto
        pad._handle_output(_evento_de_output(_corpo_do_jogo_vibrando(90, 200)))
        assert pias.chamadas == [("rumble", (90, 200))]
        pad._handle_output(_evento_de_output(_corpo_do_driver(True)))
        pad._handle_output(_evento_de_output(_corpo_do_driver(False)))
        assert ("rumble", (0, 0)) not in pias.chamadas, (
            "o 0x02 do driver do vpad parou a vibração que o jogo pediu"
        )


# --------------------------------------------------------------------------
# 6. Quatro jogadores, no tempo
# --------------------------------------------------------------------------


class TestQuatroJogadoresNoTempo:
    """30 s de relógio virtual, um aperto a cada 1,5 s alternando os quatro."""

    def test_cada_aperto_so_no_vpad_do_dono(self, uhid: _UhidPorFd) -> None:
        pads = [_vpad(j) for j in range(1, 5)]
        fds = [p._fd for p in pads]
        leitores = [_leitor(p) for p in pads]
        transportes = [_usb, _bt, _bt, _bt]  # P1 no cabo, P2 a P4 no rádio
        for p in pads:
            p.set_motion_streaming(True)
        apertos = [0, 0, 0, 0]
        t = 0.0
        marca = 0
        while t < 30.0:
            dono = int(t / 1.5) % 4
            if int(t / 1.5) % 8 >= 4:
                transportes[dono] = _usb if transportes[dono] is _bt else _bt
            for i, leitor in enumerate(leitores):
                marca += 1
                leitor._observe_mic_button(
                    transportes[i](mic=(i == dono), marca=marca)
                )
            for i, fd in enumerate(fds):
                assert fd is not None
                aceso = _o_jogo_ve_o_mic(uhid, fd)
                assert aceso == (i == dono), (
                    f"t={t:.1f}s: o aperto do P{dono + 1} "
                    f"{'não chegou ao' if i == dono else 'acendeu o'} vpad do P{i + 1}"
                )
            apertos[dono] += 1
            # soltura
            for i, leitor in enumerate(leitores):
                marca += 1
                leitor._observe_mic_button(transportes[i](marca=marca))
            t += 1.5
        for i, fd in enumerate(fds):
            assert fd is not None
            assert not _o_jogo_ve_o_mic(uhid, fd), f"bit preso no P{i + 1}"
            assert pads[i].mic_button_count == apertos[i]
            assert leitores[i].mic_button_forwards == apertos[i]
        for p in pads:
            p.stop()


# --------------------------------------------------------------------------
# 7. O `state_full` publica as duas contas, com o vpad de produção
# --------------------------------------------------------------------------


@pytest.fixture
async def servidor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, uhid: _UhidPorFd
) -> AsyncIterator[tuple[Path, Any]]:
    perfis = tmp_path / "profiles"
    perfis.mkdir()

    def _perfis(ensure: bool = False) -> Path:
        if ensure:
            perfis.mkdir(parents=True, exist_ok=True)
        return perfis

    monkeypatch.setattr(loader_module, "profiles_dir", _perfis)
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    daemon = MagicMock()
    daemon._last_state = None
    daemon.config = MagicMock(
        mouse_emulation_enabled=False,
        mouse_speed=6,
        mouse_scroll_speed=1,
        rumble_policy="balanceado",
        rumble_policy_custom_mult=0.7,
        rumble_active=None,
    )
    daemon._motion_reader = SimpleNamespace(emit_hz=0.0)
    daemon._coop_manager = None
    caminho = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=ProfileManager(controller=fc, store=store),
        socket_path=caminho,
        daemon=daemon,
    )
    await server.start()
    try:
        yield caminho, daemon
    finally:
        await server.stop()


async def _o_vpad_do_p1(caminho: Path) -> dict[str, Any]:
    async with IpcClient.connect(caminho) as cliente:
        resultado = await cliente.call("daemon.state_full")
    por_vpad = resultado["rumble_ff"]["per_vpad"]
    assert isinstance(por_vpad, list) and por_vpad
    return dict(por_vpad[0])


@pytest.mark.asyncio
async def test_state_full_publica_o_botao_e_a_luz_recusada(
    servidor: tuple[Path, Any],
) -> None:
    """Mordida: sem as chaves no bloco do vpad, reprova."""
    caminho, daemon = servidor
    pad = _vpad()
    pad._game_open = True
    pad._bound_at = pad.time_fn() - 10.0
    pad.forward_mic_button(True)
    pad.forward_mic_button(False)
    pad.forward_mic_button(True)
    corpo = bytearray(47)
    corpo[1] = rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
    corpo[_MUTE_BUTTON_LED] = 1
    pad._handle_output(_evento_de_output(bytes(corpo)))
    daemon._gamepad_device = pad
    try:
        item = await _o_vpad_do_p1(caminho)
    finally:
        pad.stop()
    assert item["mic_button_forwards"] == 2
    assert item["mic_led_do_jogo_recusado"] == 1
    assert item["mic_led_do_jogo_amostra"] == 1


@pytest.mark.asyncio
async def test_state_full_nao_inventa_com_vpad_dublado(
    servidor: tuple[Path, Any],
) -> None:
    caminho, daemon = servidor
    daemon._gamepad_device = SimpleNamespace(
        backend="uinput",
        flavor="xbox360",
        mic_button_count=MagicMock(),
        mic_led_do_jogo_recusado=MagicMock(),
        mic_led_do_jogo_amostra=MagicMock(),
    )
    item = await _o_vpad_do_p1(caminho)
    assert item["mic_button_forwards"] == 0
    assert item["mic_led_do_jogo_recusado"] == 0
    assert item["mic_led_do_jogo_amostra"] is None


# --------------------------------------------------------------------------
# 8. As réguas que faltavam (conferência de 29/09)
# --------------------------------------------------------------------------


class TestOLacoEsqueceNaPerda:
    """A régua 4 pelo LAÇO de produção, e não pelo `_reset_mic_button` na mão.

    Mordida: tirar o `_reset_mic_button()` do `finally` do `_run` reprova (o
    teste que chama o esquecimento direto passa com ele arrancado do laço).
    """

    def test_reabrir_com_o_dedo_apertado_pelo_laco(self, uhid: _UhidPorFd) -> None:
        pad = _vpad()
        fd = pad._fd
        assert fd is not None
        canos = [os.pipe(), os.pipe()]
        aberturas: list[int] = []

        def _abrir(_path: str) -> int:
            if len(aberturas) >= len(canos):
                raise OSError("sem mais físico")
            lido = canos[len(aberturas)][0]
            aberturas.append(lido)
            return os.dup(lido)

        leitor = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-de-mentira",
            vpad=pad,
            max_hz=0,
            opener=_abrir,
        )
        try:
            assert leitor.start() is True
            assert _esperar(lambda: pad.motion_streaming)
            os.write(canos[0][1], _usb(mic=True, marca=1))
            assert _esperar(lambda: leitor.reports_seen >= 1)
            assert _esperar(lambda: _o_jogo_ve_o_mic(uhid, fd))
            # O físico some com o dedo no botão: EOF no primeiro cano.
            os.close(canos[0][1])
            assert _esperar(lambda: len(aberturas) == 2 and pad.motion_streaming)
            os.write(canos[1][1], _usb(mic=True, marca=2))
            assert _esperar(lambda: leitor.reports_seen >= 2)
            assert _esperar(lambda: _o_jogo_ve_o_mic(uhid, fd)), (
                "o laço reabriu o físico com o dedo no botão e o aperto não "
                "voltou a chegar ao jogo: o cache do reader não esqueceu"
            )
        finally:
            leitor.stop()
            pad.stop()
            os.close(canos[1][1])
            for lido, _ in canos:
                os.close(lido)


class TestALuzPorBitENaoPorIgualdade:
    """A sprint separa o 0x02 do driver pelo bit 0x02, não por `== 0x03`.

    Mordidas: trocar o teste de bit por `flag1 != 0x03` reprova o primeiro;
    por `flag1 == 0x01`, o segundo; contar antes do `_replicating()`, o
    terceiro.
    """

    def test_o_driver_com_a_barra_junto_nao_conta(
        self, jogo_aberto: tuple[UhidDualSense, _Pias]
    ) -> None:
        pad, _pias = jogo_aberto
        corpo = bytearray(_corpo_do_driver(True))
        corpo[1] |= 0x04  # o worker do driver junta a barra pendente
        pad._handle_output(_evento_de_output(bytes(corpo)))
        assert pad.mic_led_do_jogo_recusado == 0

    def test_o_jogo_com_a_barra_junto_conta(
        self, jogo_aberto: tuple[UhidDualSense, _Pias]
    ) -> None:
        pad, _pias = jogo_aberto
        corpo = bytearray(47)
        corpo[1] = rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE | 0x04
        corpo[_MUTE_BUTTON_LED] = 1
        pad._handle_output(_evento_de_output(bytes(corpo)))
        assert pad.mic_led_do_jogo_recusado == 1
        assert pad.mic_led_do_jogo_amostra == 1

    def test_a_escrita_do_nascimento_nao_conta(
        self, jogo_aberto: tuple[UhidDualSense, _Pias]
    ) -> None:
        pad, _pias = jogo_aberto
        pad._bound_at = pad.time_fn()  # ainda na carência do probe
        corpo = bytearray(47)
        corpo[1] = rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
        pad._handle_output(_evento_de_output(bytes(corpo)))
        assert pad.mic_led_do_jogo_recusado == 0


def test_o_stop_solta_o_botao_e_zera_as_contas(uhid: _UhidPorFd) -> None:
    """Mordida: sem o reset no `stop()`, a próxima vida nasce apertada."""
    pad = _vpad()
    pad._game_open = True
    pad._bound_at = pad.time_fn() - 10.0
    pad.forward_mic_button(True)
    corpo = bytearray(47)
    corpo[1] = rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
    pad._handle_output(_evento_de_output(bytes(corpo)))
    assert pad.mic_button and pad.mic_button_count == 1
    assert pad.mic_led_do_jogo_recusado == 1
    pad.stop()
    assert pad.mic_button is False
    assert pad.mic_button_count == 0
    assert pad.mic_led_do_jogo_recusado == 0
    assert pad.mic_led_do_jogo_amostra is None
