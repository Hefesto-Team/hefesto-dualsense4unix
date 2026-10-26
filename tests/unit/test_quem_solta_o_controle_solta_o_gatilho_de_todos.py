"""QUEM-SOLTA-O-CONTROLE-SOLTA-O-GATILHO-DE-TODOS-01: parar o Hefesto e entrar no Modo Nativo
deixam os dois gatilhos dos quatro controles em Off no fio.

A mesa: o Starlight Blue e o White no cabo, o Cosmic Red e o Galactic Purple no rádio, o perfil
com o Rígido nos dois lados, o destino da aba Conexões mirando o White e um bloco do jogo
pendurado no gatilho direito do Cosmic Red. Os handles são `_PinnedPyDualSense` de verdade (o
`writeReport` dele carimba o `seq` e o CRC do rádio) sobre um hidraw de mentira que anota cada
escrita num diário comum, junto com o mudo e o `disconnect`.
"""
from __future__ import annotations

import asyncio
import zlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.core.trigger_effects import build_from_name

STARLIGHT_BLUE = "AA:BB:CC:00:00:01"
WHITE = "AA:BB:CC:00:00:02"
COSMIC_RED = "AA:BB:CC:00:00:03"
GALACTIC_PURPLE = "AA:BB:CC:00:00:04"
MESA = (STARLIGHT_BLUE, WHITE, COSMIC_RED, GALACTIC_PURPLE)
NO_RADIO = (COSMIC_RED, GALACTIC_PURPLE)

BLOCO_DO_JOGO = bytes([0x21, 0x05, 0x40, 0, 0, 0, 0, 0, 0, 0, 0])
BLOCO_OFF = bytes(11)
RIGIDO = build_from_name("Rigid", [3, 8])


class _Diario:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, str, bytes]] = []

    def escritas_de(self, mac: str) -> list[bytes]:
        return [q for tipo, quem, q in self.eventos if tipo == "escrita" and quem == mac]

    def posicao(self, tipo: str) -> int:
        return next(i for i, (t, _q, _b) in enumerate(self.eventos) if t == tipo)


class _Hidraw:
    def __init__(self, diario: _Diario, mac: str) -> None:
        self._diario = diario
        self._mac = mac

    def write(self, quadro: bytes) -> int:
        self._diario.eventos.append(("escrita", self._mac, bytes(quadro)))
        return len(quadro)


def _handle(diario: _Diario, mac: str) -> bp._PinnedPyDualSense:
    handle = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    handle.leftMotor = 0
    handle.rightMotor = 0
    handle.light = DSLight()
    handle.audio = DSAudio()
    handle.triggerL = DSTrigger()
    handle.triggerR = DSTrigger()
    handle.conType = ConnectionType.BT if mac in NO_RADIO else ConnectionType.USB
    handle._suppress_leds = True
    handle._rumble_active = False
    handle._rumble_stop_pending = False
    handle._bt_seq = 0
    handle._raw_trigger_left = None
    handle._raw_trigger_right = None
    handle._output_muted = False
    handle.device = _Hidraw(diario, mac)
    return handle


def _mesa(diario: _Diario) -> bp.PyDualSenseController:
    ctl = bp.PyDualSenseController()
    ctl._handles = {mac: _handle(diario, mac) for mac in MESA}  # type: ignore[misc]
    ctl._primary_key = STARLIGHT_BLUE
    ctl.apply_output_defaults(OutputSpec(trigger_left=RIGIDO, trigger_right=RIGIDO))
    assert ctl.set_output_target(MESA.index(WHITE)) == 1
    assert ctl.set_game_trigger_for(COSMIC_RED, "right", BLOCO_DO_JOGO) is True
    assert ctl._handles[COSMIC_RED]._raw_trigger_right == BLOCO_DO_JOGO
    diario.eventos.clear()
    return ctl


def _common(quadro: bytes) -> bytes:
    if quadro[0] == 0x31 and len(quadro) == 78:
        return quadro[3:50]
    assert quadro[0] == 0x02, quadro[:3].hex()
    return quadro[1:48]


def _solta_os_dois(quadro: bytes) -> bool:
    """O report autoriza os dois gatilhos (`flag0` `0x04|0x08`) e os põe em Off."""
    common = _common(quadro)
    return (
        common[0] & 0x0C == 0x0C
        and common[10:21] == BLOCO_OFF
        and common[21:32] == BLOCO_OFF
    )


def _radio_valido(quadro: bytes, seq: int) -> bool:
    crc = zlib.crc32(b"\xa2" + quadro[:74]) & 0xFFFFFFFF
    return (
        len(quadro) == 78
        and quadro[1] >> 4 == seq
        and quadro[2] == 0x10
        and int.from_bytes(quadro[74:78], "little") == crc
    )


def _o_proximo_report_solta(ctl: bp.PyDualSenseController, mac: str) -> bool:
    """O que a volta de escrita do handle manda a seguir também solta (sem bloco do jogo)."""
    return _solta_os_dois(bytes(ctl._handles[mac].prepareReport()))


def _o_desejo_e_o_do_perfil(ctl: bp.PyDualSenseController) -> None:
    for mac in MESA:
        desejo = ctl._merged_desired_for_key(mac)
        assert desejo.trigger_left == RIGIDO, mac
        assert desejo.trigger_right == RIGIDO, mac
        uniq = ctl._key_to_uniq(mac)
        assert uniq is not None
        donos = ctl._desired_owner_by_uniq.get(uniq, {})
        assert "trigger_left" not in donos and "trigger_right" not in donos, (mac, donos)
        override = ctl._desired_by_uniq.get(uniq)
        if override is not None:
            assert override.trigger_left is None and override.trigger_right is None, mac


class TestOBackendTemUmDonoSo:
    def test_solta_os_quatro_sem_olhar_o_destino_e_sem_gravar_desejo(self) -> None:
        diario = _Diario()
        ctl = _mesa(diario)

        resultado = ctl.soltar_os_gatilhos()

        assert resultado == dict.fromkeys(MESA, True)
        for mac in MESA:
            escritas = diario.escritas_de(mac)
            assert len(escritas) == 1, (mac, len(escritas))
            assert _solta_os_dois(escritas[0]), mac
            assert _o_proximo_report_solta(ctl, mac), mac
        assert ctl._handles[COSMIC_RED]._raw_trigger_right is None
        _o_desejo_e_o_do_perfil(ctl)

    def test_no_radio_o_report_leva_o_seq_e_o_crc_do_handle(self) -> None:
        diario = _Diario()
        ctl = _mesa(diario)
        for mac in NO_RADIO:
            ctl._handles[mac]._bt_seq = 6

        ctl.soltar_os_gatilhos()

        for mac in NO_RADIO:
            (quadro,) = diario.escritas_de(mac)
            assert _radio_valido(quadro, 6), mac
            assert ctl._handles[mac]._bt_seq == 7, mac

    def test_sob_o_mudo_o_jogo_e_o_dono_e_nada_se_escreve(self) -> None:
        diario = _Diario()
        ctl = _mesa(diario)
        ctl.set_output_mute(True)
        diario.eventos.clear()

        assert ctl.soltar_os_gatilhos() == {}
        assert diario.eventos == []

    def test_o_reconnect_nao_escreve_off(self) -> None:
        diario = _Diario()
        ctl = _mesa(diario)
        chaves = [(mac, f"/dev/hidraw{i}".encode(), False) for i, mac in enumerate(MESA)]
        with patch.object(
            bp.PyDualSenseController, "_enumerate_device_keys", return_value=chaves
        ):
            ctl.connect()

        for mac in MESA:
            assert not any(_solta_os_dois(q) for q in diario.escritas_de(mac)), mac
            gatilho = ctl._handles[mac].triggerR
            assert int(gatilho.mode.value) != 0, mac


async def _no_executor(fn: Any, *args: Any) -> Any:
    return fn(*args)


def _daemon_que_para(ctl: bp.PyDualSenseController, diario: _Diario, *, nativo: bool) -> Any:
    def disconnect() -> None:
        diario.eventos.append(("disconnect", "", b""))

    ctl.disconnect = disconnect  # type: ignore[method-assign]
    return SimpleNamespace(
        controller=ctl,
        _run_blocking=_no_executor,
        _executor=None,
        _external_executor=None,
        _tasks=[],
        is_native_mode=lambda: nativo,
    )


class TestAParada:
    def test_o_ultimo_passo_da_parada_e_soltar_o_controle(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems import a_ordem_de_parada

        assert a_ordem_de_parada()[-1].nome == "controle"

    def test_a_parada_solta_os_quatro_antes_do_disconnect(self) -> None:
        """Prova da D-1610-QUEM-SOLTA-O-CONTROLE-SOLTA-OS-GATILHOS-DOS-QUATRO."""
        from hefesto_dualsense4unix.daemon.connection import soltar_o_controle

        diario = _Diario()
        ctl = _mesa(diario)
        asyncio.run(soltar_o_controle(_daemon_que_para(ctl, diario, nativo=False)))

        corte = diario.posicao("disconnect")
        for mac in MESA:
            antes = [
                q
                for i, (tipo, quem, q) in enumerate(diario.eventos)
                if tipo == "escrita" and quem == mac and i < corte
            ]
            assert any(_solta_os_dois(q) for q in antes), mac
        for mac in NO_RADIO:
            assert _radio_valido(diario.escritas_de(mac)[0], 0), mac

    def test_a_parada_em_modo_nativo_nao_escreve_por_cima_do_jogo(self) -> None:
        from hefesto_dualsense4unix.daemon.connection import soltar_o_controle

        diario = _Diario()
        ctl = _mesa(diario)
        asyncio.run(soltar_o_controle(_daemon_que_para(ctl, diario, nativo=True)))

        assert [tipo for tipo, _q, _b in diario.eventos] == ["disconnect"]


def _daemon_que_entra_no_nativo(ctl: bp.PyDualSenseController, diario: _Diario) -> Any:
    from hefesto_dualsense4unix.daemon import lifecycle

    daemon = lifecycle.Daemon.__new__(lifecycle.Daemon)
    daemon.controller = ctl
    daemon.config = SimpleNamespace(rumble_active=None, rumble_active_uniq=None)

    def sem_mouse(*_a: Any, **_k: Any) -> None:
        diario.eventos.append(("mouse", "", b""))

    def sem_vpad(*_a: Any, **_k: Any) -> None:
        diario.eventos.append(("vpad", "", b""))
        ctl.end_game_session_for(COSMIC_RED)

    daemon.set_mouse_emulation = sem_mouse  # type: ignore[method-assign]
    daemon.set_gamepad_emulation = sem_vpad  # type: ignore[method-assign]
    mudo_original = ctl.set_output_mute

    def mudo(muted: bool) -> None:
        diario.eventos.append(("mudo", "", b""))
        mudo_original(muted)

    ctl.set_output_mute = mudo  # type: ignore[method-assign]
    return daemon


class TestOModoNativo:
    def test_entrar_solta_os_quatro_antes_do_mudo_e_depois_do_vpad(self) -> None:
        diario = _Diario()
        ctl = _mesa(diario)
        _daemon_que_entra_no_nativo(ctl, diario)._release_controller_to_game()

        mudo = diario.posicao("mudo")
        vpad = diario.posicao("vpad")
        for mac in MESA:
            soltas = [
                i
                for i, (tipo, quem, q) in enumerate(diario.eventos)
                if tipo == "escrita" and quem == mac and _solta_os_dois(q)
            ]
            assert soltas, mac
            assert vpad < soltas[-1] < mudo, (mac, vpad, soltas, mudo)
            assert _o_proximo_report_solta(ctl, mac), mac
        assert ctl._output_mute is True

    def test_o_desejo_volta_do_nativo_com_o_gatilho_do_perfil(self) -> None:
        diario = _Diario()
        ctl = _mesa(diario)
        _daemon_que_entra_no_nativo(ctl, diario)._release_controller_to_game()

        _o_desejo_e_o_do_perfil(ctl)
        ctl.set_output_mute(False)
        ctl.apply_output_defaults(OutputSpec(trigger_left=RIGIDO, trigger_right=RIGIDO))
        for mac in MESA:
            handle = ctl._handles[mac]
            assert int(handle.triggerL.mode.value) == int(RIGIDO.mode), mac
            assert int(handle.triggerR.mode.value) == int(RIGIDO.mode), mac

    def test_a_falha_ao_soltar_vira_log_e_o_mudo_sai_mesmo_assim(self) -> None:
        diario = _Diario()
        ctl = _mesa(diario)
        daemon = _daemon_que_entra_no_nativo(ctl, diario)

        def quebra() -> dict[str, bool]:
            raise RuntimeError("hidraw sumiu")

        ctl.soltar_os_gatilhos = quebra  # type: ignore[method-assign]
        with patch("hefesto_dualsense4unix.daemon.lifecycle.logger") as diario_do_daemon:
            daemon._release_controller_to_game()

        nomes = [c.args[0] for c in diario_do_daemon.warning.call_args_list]
        assert "gatilhos_nao_soltos_no_nativo" in nomes
        assert ctl._output_mute is True
