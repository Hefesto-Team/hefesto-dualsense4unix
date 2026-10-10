"""A perda de amostras do movimento se conta pelo contador do próprio report.

A-PERDA-DE-AMOSTRAS-DO-MOVIMENTO-SE-CONTA-PELO-CONTADOR-DO-REPORT-01
(09/10/2026). O `reserved[4]` do corpo (11 a 14) é um `__le32` que anda de 1
em 1 por report, no cabo e no rádio (medido em 15/08/2026). O leitor do report
cru contava só o report do rádio com CRC ruim, e esse número não tinha leitor.

A MORDIDA: arranque o `_observe_contador` do laço e o caso 12 → 15 dá zero;
tire as duas chaves do `per_vpad` e o caso do `state_full` reprova.
"""
from __future__ import annotations

import contextlib
import socket
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.ds_output_report import BT_INPUT_CRC_SEED, bt_crc32
from hefesto_dualsense4unix.core.physical_report_reader import PhysicalReportReader
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

_CORPO = prr.CONTADOR_DE_REPORT_OFFSET


def _usb(contador: int) -> bytes:
    raw = bytearray(64)
    raw[0] = prr.INPUT_REPORT_USB
    inicio = 1 + _CORPO
    raw[inicio : inicio + 4] = contador.to_bytes(4, "little")
    return bytes(raw)


def _bt(contador: int, *, corrompido: bool = False, audio: bool = False) -> bytes:
    raw = bytearray(prr.INPUT_REPORT_BT_SIZE)
    raw[0] = prr.INPUT_REPORT_BT
    raw[1] = 0x01 | (prr.INPUT_FLAG_AUDIO if audio else 0)
    inicio = 2 + _CORPO
    raw[inicio : inicio + 4] = contador.to_bytes(4, "little")
    raw[-4:] = bt_crc32(raw[:-4], seed=BT_INPUT_CRC_SEED).to_bytes(4, "little")
    if corrompido:
        raw[20] ^= 0xFF
    return bytes(raw)


class _Vpad:
    def set_motion_streaming(self, _ligado: bool) -> None:  # pragma: no cover
        pass

    def forward_motion(self, _janela: bytes) -> None:
        pass


def _ler(reader: PhysicalReportReader, reports: list[bytes]) -> None:
    """Empurra `reports` pelo laço REAL do leitor, num fd que dá EOF no fim."""
    escritor, leitor = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    try:
        for r in reports:
            escritor.send(r)
        escritor.close()
        reader._read_until_lost(leitor.fileno())
    finally:
        with contextlib.suppress(OSError):
            escritor.close()
        leitor.close()


def _leitor() -> PhysicalReportReader:
    return PhysicalReportReader(path_provider=lambda: "/dev/hidraw-dublê", vpad=_Vpad())


@pytest.mark.parametrize("report", [_usb, _bt], ids=["cabo", "radio"])
def test_o_salto_do_contador_conta_os_reports_que_faltaram(report: Any) -> None:
    reader = _leitor()
    _ler(reader, [report(n) for n in (10, 11, 12, 15)])
    assert reader.reports_perdidos == 2
    assert reader.reports_estragados == 0


@pytest.mark.parametrize("report", [_usb, _bt], ids=["cabo", "radio"])
def test_a_volta_do_uint32_nao_e_perda(report: Any) -> None:
    reader = _leitor()
    _ler(reader, [report(0xFFFFFFFE), report(0xFFFFFFFF), report(0), report(1)])
    assert reader.reports_perdidos == 0


def test_reabrir_o_fd_nao_conta_o_salto_da_reabertura() -> None:
    reader = _leitor()
    _ler(reader, [_bt(n) for n in (100, 101)])
    _ler(reader, [_bt(n) for n in (5000, 5001, 5003)])
    assert reader.reports_perdidos == 1


def test_o_crc_ruim_segue_contado_a_parte_e_nao_vira_perda() -> None:
    reader = _leitor()
    _ler(reader, [_bt(10), _bt(11, corrompido=True), _bt(12), _bt(14)])
    assert reader.reports_estragados == 1
    assert reader.bt_drops == 1
    assert reader.reports_perdidos == 1


def test_o_report_de_audio_nao_e_estragado_nem_perdido() -> None:
    reader = _leitor()
    _ler(reader, [_bt(10), _bt(11, audio=True), _bt(12)])
    assert reader.reports_estragados == 0
    assert reader.reports_perdidos == 0


def test_o_contador_que_anda_para_tras_semeia_de_novo() -> None:
    reader = _leitor()
    _ler(reader, [_usb(500), _usb(3), _usb(4)])
    assert reader.reports_perdidos == 0


# O serviço: os dois números em cada pad, ao lado do `motion_hz`.


def _vpad_ns() -> SimpleNamespace:
    return SimpleNamespace(backend="uhid", flavor="dualsense", ff_supported=True,
                           ff_play_count=0, output_count=0, trigger_replicas=0,
                           lightbar_replicas=0, player_led_replicas=0,
                           ff_last_sent=(0, 0), motion_streaming=True)


@pytest.mark.asyncio
async def test_o_state_full_traz_a_perda_de_cada_pad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    perfis = tmp_path / "profiles"
    perfis.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: perfis)
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    daemon = MagicMock()
    daemon._last_state = None
    daemon.config = MagicMock(coop_enabled=False, mouse_emulation_enabled=False,
                              rumble_policy="balanceado", rumble_active=None)
    daemon._gamepad_device = _vpad_ns()
    daemon._motion_reader = SimpleNamespace(emit_hz=250.0, reports_perdidos=7,
                                            reports_estragados=2)
    daemon._coop_manager = SimpleNamespace(
        _players={"aabbcc000002": SimpleNamespace(
            player_index=2, vpad=_vpad_ns(),
            motion_reader=SimpleNamespace(emit_hz=120.0, reports_perdidos=0,
                                          reports_estragados=5))},
        player_count=lambda: 2,
    )
    sock = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(controller=fc, store=store,
                       profile_manager=ProfileManager(controller=fc, store=store),
                       socket_path=sock, daemon=daemon)
    await server.start()
    try:
        async with IpcClient.connect(sock) as client:
            resultado = await client.call("daemon.state_full")
    finally:
        await server.stop()
    por_jogador = {i["player"]: i for i in resultado["rumble_ff"]["per_vpad"]}
    assert (por_jogador[1]["reports_perdidos"], por_jogador[1]["reports_estragados"]) == (7, 2)
    assert (por_jogador[2]["reports_perdidos"], por_jogador[2]["reports_estragados"]) == (0, 5)
