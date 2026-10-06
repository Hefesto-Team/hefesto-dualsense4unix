"""Os órfãos de 09/08/2026 voltando a ligar na interface.

Uma auditoria de 09/08 isolou quatro capacidades que existiam no código, tinham
teste próprio e **zero chamadores em `src/`** — cada uma de um dos recursos que
o usuário nomeou (*"vibração, giroscópio, touchpad, microfone, áudio específico do
DualSense. Falo isso ingame"*):

======================  ==========================  ==========  ============
capacidade              onde morava                 recurso     órfã desde
======================  ==========================  ==========  ============
``forward_jack``        ``uhid_gamepad``            fone/mic    02/08
``motion_forward_count````uhid_gamepad``            giroscópio  19/07
``touchpad_click``      ``uhid_gamepad``            touchpad    TOUCH-CLICK-01
o rumble APLICADO       ``core/rumble`` (classe     vibração    —
                        morta no daemon)
======================  ==========================  ==========  ============

O ``forward_jack`` era o pior dos quatro, e reincidente: a sprint
``2026-08-03-ENTREGA-QUE-NAO-LIGOU-01`` já o tinha declarado órfão — *"não tem
chamador, e não emitiria se tivesse"* — e seis dias depois ele continuava com
os DOIS defeitos. Por isso o primeiro bloco deste arquivo mede as duas coisas
separadamente: que alguém chama, e que o report SAI.

A vibração é o caso diferente dos quatro: ``RumbleEngine.last_applied`` não
tinha chamador porque a **classe inteira** não era instanciada pelo daemon real
(o próprio ``ipc_handlers`` já registrava isso: *"o antigo `_rumble_engine` NÃO
é instanciado no daemon real"*), e ela saiu da árvore em 28/09/2026. Fiá-la
seria fiar um objeto morto. O que
respondia à pergunta de produto —  — passou a ser
medido no caminho VIVO (``apply_game_rumble``), e é isso que o bloco 5 tranca.

Nada aqui toca hardware: o hidraw do físico é um ``os.pipe()``, o ``/dev/uhid``
é o mesmo fake dos testes irmãos e o daemon é dublado.
"""
from __future__ import annotations

import os
import struct
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.interface.cartao_do_controle import motores_no_fisico
from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.core.ds_output_report import (
    BT_INPUT_CRC_SEED,
    bt_crc32,
)
from hefesto_dualsense4unix.core.physical_report_reader import (
    INPUT_REPORT_BT_SIZE,
    JACK_STATUS_OFFSET,
    PhysicalReportReader,
    extract_jack_status,
)
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
    anotar_rumble_no_vpad,
    apply_game_rumble,
    make_primary_rumble_sink,
)
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    UHID_INPUT2,
    UhidDualSense,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

_HP_DETECT = 0x01
_MIC_DETECT = 0x02
_MIC_MUTE = 0x04


def _usb_report(*, jack: int = 0, marca: int = 0) -> bytes:
    """Report 0x01 (64 B) do físico com o byte 53 pedido."""
    raw = bytearray(64)
    raw[0] = 0x01
    raw[1:7] = bytes([0x80, 0x80, 0x80, 0x80, 0, 0])
    raw[1 + 15] = marca & 0xFF
    raw[1 + 32] = 0x80
    raw[1 + 36] = 0x80
    raw[1 + JACK_STATUS_OFFSET] = jack & 0xFF
    return bytes(raw)


def _bt_report(*, jack: int = 0, corrupt: bool = False) -> bytes:
    """Report 0x31 (78 B) com CRC de INPUT (seed 0xA1) válido — ou corrompido."""
    raw = bytearray(INPUT_REPORT_BT_SIZE)
    raw[0] = 0x31
    raw[1] = 0x01
    raw[2 + JACK_STATUS_OFFSET] = jack & 0xFF
    crc = bt_crc32(raw[:-4], seed=BT_INPUT_CRC_SEED)
    raw[-4:] = crc.to_bytes(4, "little")
    if corrupt:
        raw[2 + JACK_STATUS_OFFSET] ^= 0xFF
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


_FD_UHID = 4243


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


def _esperar(cond: Any, timeout_s: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.005)
    return cond()


class TestExtrairOJackDoReportCru:
    def test_usb_sem_nada_plugado(self) -> None:
        assert extract_jack_status(_usb_report()) == 0

    def test_usb_com_fone_e_mic(self) -> None:
        jack = _HP_DETECT | _MIC_DETECT
        assert extract_jack_status(_usb_report(jack=jack)) == jack

    def test_bt_com_crc_valido(self) -> None:
        assert extract_jack_status(_bt_report(jack=_HP_DETECT)) == _HP_DETECT

    def test_bt_com_crc_corrompido_nao_diz_nada(self) -> None:
        """``None`` e não ``0``: rádio corrompido não despluga o fone do usuário."""
        assert extract_jack_status(_bt_report(jack=_HP_DETECT, corrupt=True)) is None

    def test_report_de_outro_id_nao_diz_nada(self) -> None:
        assert extract_jack_status(bytes([0x05]) + bytes(63)) is None

    def test_report_curto_demais_nao_diz_nada(self) -> None:
        assert extract_jack_status(bytes([0x01, 0x00])) is None

    def test_report_vazio_nao_diz_nada(self) -> None:
        assert extract_jack_status(b"") is None


def test_o_offset_do_jack_e_o_mesmo_nos_dois_lados() -> None:
    """O reader e o vpad falam do MESMO byte, e é o teste que os prende."""
    assert JACK_STATUS_OFFSET == uhid_gamepad._STATUS1_OFFSET


class TestOEncoderDoJack:
    def test_forward_jack_emite_o_report(self, fake_uhid: _FakeUhid) -> None:
        """MORDIDA: apagar o `_emit_if_changed` de `forward_jack`."""
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        antes = len(fake_uhid.bodies())

        pad.forward_jack(_HP_DETECT | _MIC_MUTE)

        bodies = fake_uhid.bodies()
        assert len(bodies) > antes, "o byte 53 mudou e NENHUM report saiu"
        assert bodies[-1][uhid_gamepad._STATUS1_OFFSET] == (_HP_DETECT | _MIC_MUTE)
        assert pad.jack_forward_count == 1

    def test_so_os_tres_bits_conhecidos_viajam(self, fake_uhid: _FakeUhid) -> None:
        """O resto do byte é do firmware e não é nosso para encaminhar."""
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_jack(0xFF)
        assert fake_uhid.bodies()[-1][uhid_gamepad._STATUS1_OFFSET] == 0b111

    def test_jack_repetido_nao_reemite(self, fake_uhid: _FakeUhid) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_jack(_HP_DETECT)
        antes = len(fake_uhid.bodies())
        pad.forward_jack(_HP_DETECT)
        assert len(fake_uhid.bodies()) == antes
        assert pad.jack_forward_count == 1

    def test_emite_mesmo_com_o_reader_como_relogio(
        self, fake_uhid: _FakeUhid
    ) -> None:
        """Com `motion_streaming` ligado, só o reader emite — e é ele que chama."""
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.set_motion_streaming(True)
        antes = len(fake_uhid.bodies())
        pad.forward_jack(_MIC_DETECT)
        assert len(fake_uhid.bodies()) > antes

    def test_perder_o_fisico_zera_o_fone(self, fake_uhid: _FakeUhid) -> None:
        """Fail-safe: sem reader, o vpad para de anunciar um fone que não há."""
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.set_motion_streaming(True)
        pad.forward_jack(_HP_DETECT | _MIC_DETECT)
        assert pad.jack == {"fone": True, "microfone": True, "mudo": False}

        pad.set_motion_streaming(False)

        assert pad.jack == {"fone": False, "microfone": False, "mudo": False}
        assert fake_uhid.bodies()[-1][uhid_gamepad._STATUS1_OFFSET] == 0


class TestOJackChegaAoJogo:
    def _rodar_fluxo(self, fake: _FakeUhid, reports: list[bytes]) -> list[bytes]:
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
            assert _esperar(lambda: reader.jack_forwards >= 1, timeout_s=1.0)
        finally:
            reader.stop()
            pad.stop()
            os.close(escrita)
            os.close(lido)
        return fake.bodies()

    def test_plugar_o_fone_atravessa_ate_o_report_do_jogo(
        self, fake_uhid: _FakeUhid
    ) -> None:
        """O teste que MORDE, ponta a ponta."""
        fluxo = [
            _usb_report(marca=1),
            _usb_report(jack=_HP_DETECT, marca=2),
            _usb_report(jack=_HP_DETECT, marca=3),
        ]
        bodies = self._rodar_fluxo(fake_uhid, fluxo)
        com_fone = [
            b for b in bodies if b[uhid_gamepad._STATUS1_OFFSET] & _HP_DETECT
        ]
        assert com_fone, (
            "nenhum report saiu com o bit de fone — o jogo continua sem saber "
            "que há fone no controle (forward_jack órfão desde 02/08)"
        )

    def test_desplugar_apaga_o_bit(self, fake_uhid: _FakeUhid) -> None:
        fluxo = [
            _usb_report(jack=_HP_DETECT, marca=1),
            _usb_report(jack=0, marca=2),
        ]
        bodies = self._rodar_fluxo(fake_uhid, fluxo)
        assert bodies, "o vpad não emitiu nada"
        assert not (bodies[-1][uhid_gamepad._STATUS1_OFFSET] & _HP_DETECT)


class TestOReaderNaoInventaJack:
    """As três defesas do `_observe_jack`, sem thread nenhuma."""

    def _reader(self, vpad: Any) -> PhysicalReportReader:
        return PhysicalReportReader(
            path_provider=lambda: None, vpad=vpad, max_hz=0
        )

    def test_report_ruim_nao_mexe_no_estado(self) -> None:
        recebidos: list[int] = []
        vpad = SimpleNamespace(forward_jack=recebidos.append)
        reader = self._reader(vpad)
        reader._observe_jack(_usb_report(jack=_HP_DETECT))
        reader._observe_jack(_bt_report(jack=0, corrupt=True))
        assert recebidos == [_HP_DETECT], (
            "um report com CRC ruim desplugou o fone — 'não sei' virou 'não há'"
        )

    def test_vpad_sem_o_metodo_degrada_calado(self) -> None:
        """Contrato duck-typed, o mesmo do `forward_motion`: o uinput não tem."""
        reader = self._reader(SimpleNamespace())
        reader._observe_jack(_usb_report(jack=_HP_DETECT))
        assert reader.jack_forwards == 0

    def test_reabrir_reentrega_o_fone(self) -> None:
        """MORDIDA: apagar o `_reset_jack()` do fail-safe do `_run`."""
        recebidos: list[int] = []
        vpad = SimpleNamespace(forward_jack=recebidos.append)
        reader = self._reader(vpad)
        reader._observe_jack(_usb_report(jack=_HP_DETECT))
        reader._reset_jack()
        reader._observe_jack(_usb_report(jack=_HP_DETECT))
        assert recebidos == [_HP_DETECT, _HP_DETECT]


def _daemon_de_rumble(*, policy: str = "max", mult: float = 1.0) -> Any:
    controller = MagicMock()
    controller.set_rumble_for = None
    daemon = MagicMock()
    daemon.controller = controller
    daemon.config = MagicMock(
        rumble_active=None,
        rumble_policy=policy,
        rumble_policy_custom_mult=mult,
    )
    daemon._last_auto_mult = 1.0
    daemon._last_auto_change_at = 0.0
    daemon.store.snapshot.return_value = SimpleNamespace(controller=None)
    return daemon


class TestARumbleQueChegaAosMotores:
    def test_apply_game_rumble_devolve_o_par_efetivo(self) -> None:
        """O par que VOLTA é o que foi ao motor, já com a política aplicada."""
        from hefesto_dualsense4unix.daemon.subsystems.rumble import (
            RUMBLE_POLICY_MULT,
        )

        mult = RUMBLE_POLICY_MULT["max"]
        daemon = _daemon_de_rumble(policy="max")
        assert apply_game_rumble(daemon, 100, 200) == (
            min(255, round(100 * mult)),
            min(255, round(200 * mult)),
        )

    def test_a_politica_aparece_no_par_devolvido(self) -> None:
        """É a multiplicação invisível: 20 pedido vira 6 no motor em economia."""
        daemon = _daemon_de_rumble(policy="economia")
        assert apply_game_rumble(daemon, 20, 100) == (6, 30)

    def test_rumble_fixado_pela_janela_nao_devolve_par(self) -> None:
        """``None`` = nada foi escrito, e é diferente de ``(0, 0)``."""
        daemon = _daemon_de_rumble()
        daemon.config.rumble_active = (10, 20)
        assert apply_game_rumble(daemon, 100, 200) is None

    def test_falha_do_backend_nao_devolve_par(self) -> None:
        daemon = _daemon_de_rumble()
        daemon.controller.set_rumble.side_effect = OSError("hidraw sumiu")
        assert apply_game_rumble(daemon, 100, 200) is None

    def test_o_sink_do_p1_anota_no_vpad(self, fake_uhid: _FakeUhid) -> None:
        """MORDIDA: apagar o `anotar_rumble_no_vpad` do sink."""
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        daemon = _daemon_de_rumble(policy="economia")
        daemon._gamepad_device = pad
        daemon.controller.primary_uniq = None

        make_primary_rumble_sink(daemon)(20, 100)

        assert pad.rumble_no_fisico == (6, 30)
        assert pad.rumble_no_fisico_ha_s is not None

    def test_anotar_ignora_none_e_vpad_sem_o_metodo(self) -> None:
        pad = SimpleNamespace()
        anotar_rumble_no_vpad(pad, (1, 2))
        anotar_rumble_no_vpad(None, (1, 2))
        registros: list[tuple[int, int]] = []
        vpad = SimpleNamespace(
            registrar_rumble_no_fisico=lambda w, s: registros.append((w, s))
        )
        anotar_rumble_no_vpad(vpad, None)
        assert registros == []
        anotar_rumble_no_vpad(vpad, (3, 4))
        assert registros == [(3, 4)]

    def test_a_sessao_nova_nao_herda_o_que_foi_aos_motores(
        self, fake_uhid: _FakeUhid
    ) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.registrar_rumble_no_fisico(120, 60)
        pad.stop()
        assert pad.rumble_no_fisico is None
        assert pad.rumble_no_fisico_ha_s is None


# 5. O `state_full` carrega os quatro


def _vpad_completo(**extra: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "backend": "uhid",
        "flavor": "dualsense",
        "ff_supported": True,
        "ff_play_count": 0,
        "output_count": 0,
        "trigger_replicas": 0,
        "lightbar_replicas": 0,
        "player_led_replicas": 0,
        "ff_last_sent": (0, 0),
        "motion_streaming": True,
        "motion_forward_count": 0,
        "touchpad_click": False,
        "touchpad_click_count": 0,
        "jack_forward_count": 0,
        "jack": {"fone": False, "microfone": False, "mudo": False},
        "rumble_no_fisico": None,
        "rumble_no_fisico_ha_s": None,
    }
    base.update(extra)
    return SimpleNamespace(**base)


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


@pytest.fixture
async def servidor(tmp_path: Path, isolated_profiles_dir: Path) -> Any:
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)

    daemon_mock = MagicMock()
    daemon_mock._last_state = None
    daemon_mock.config = MagicMock(
        mouse_emulation_enabled=False,
        mouse_speed=6,
        mouse_scroll_speed=1,
        rumble_policy="balanceado",
        rumble_policy_custom_mult=0.7,
        rumble_active=None,
    )
    daemon_mock._gamepad_device = _vpad_completo()
    daemon_mock._motion_reader = SimpleNamespace(emit_hz=0.0)
    daemon_mock._coop_manager = None

    socket_path = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=socket_path,
        daemon=daemon_mock,
    )
    await server.start()
    try:
        yield socket_path, daemon_mock
    finally:
        await server.stop()


async def _item_do_p1(socket_path: Path) -> dict[str, Any]:
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.state_full")
    per_vpad = result["rumble_ff"]["per_vpad"]
    assert isinstance(per_vpad, list) and per_vpad
    return per_vpad[0]


@pytest.mark.asyncio
async def test_state_full_publica_os_quatro_orfaos(servidor: Any) -> None:
    """MORDIDA: apagar qualquer uma das quatro chaves do `per_vpad`."""
    socket_path, daemon = servidor
    daemon._gamepad_device = _vpad_completo(
        motion_forward_count=812,
        touchpad_click=True,
        jack={"fone": True, "microfone": True, "mudo": False},
        jack_forward_count=3,
        rumble_no_fisico=(120, 60),
        rumble_no_fisico_ha_s=0.4,
    )
    item = await _item_do_p1(socket_path)

    assert item["motion_forwards"] == 812
    assert item["touchpad_pressionado"] is True
    assert item["jack"] == {"fone": True, "microfone": True, "mudo": False}
    assert item["jack_forwards"] == 3
    assert item["rumble_no_fisico"] == [120, 60]
    assert item["rumble_no_fisico_ha_s"] == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_state_full_nao_inventa_numero_quando_o_vpad_e_mock(
    servidor: Any,
) -> None:
    """A blindagem de sempre deste payload: MagicMock não vira dado."""
    socket_path, daemon = servidor
    daemon._gamepad_device = _vpad_completo(
        motion_forward_count=MagicMock(),
        touchpad_click=MagicMock(),
        jack=MagicMock(),
        rumble_no_fisico=MagicMock(),
        rumble_no_fisico_ha_s=MagicMock(),
    )
    item = await _item_do_p1(socket_path)

    assert item["motion_forwards"] == 0
    assert item["touchpad_pressionado"] is False
    assert item["jack"] is None
    assert item["rumble_no_fisico"] is None
    assert item["rumble_no_fisico_ha_s"] is None


def _entry() -> dict[str, Any]:
    return {"player": 1, "is_primary": True}


def _estado(**vpad: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"player": 1, "visto_ha_s": {}}
    item.update(vpad)
    return {"rumble_ff": {"per_vpad": [item]}}


class TestAVibracaoMostraOQueFoiAosMotores:


    def test_numero_velho_nao_entra(self) -> None:
        """Um par congelado ao lado da palavra "chegando" é a mentira confortável."""
        assert (
            motores_no_fisico(
                {"rumble_no_fisico": [120, 60], "rumble_no_fisico_ha_s": 30.0}
            )
            is None
        )

    def test_parada_do_jogo_nao_e_numero(self) -> None:
        assert (
            motores_no_fisico(
                {"rumble_no_fisico": [0, 0], "rumble_no_fisico_ha_s": 0.1}
            )
            is None
        )

    def test_daemon_antigo_nao_quebra_a_linha(self) -> None:
        assert motores_no_fisico({}) is None
        assert motores_no_fisico(None) is None
