"""GUERRA-01 item 2 + BTREPORT-02 no backend — keepalive neutro e report BT.

A causa-mãe do "branco USB não vibra" (estudo 2026-07-18): o report_thread
reescrevia motores=0 com os bits de vibração do flag0 SEMPRE ligados (0xFF do
upstream) — todo rumble que o JOGO escrevia direto no hidraw do físico era
zerado em ≤0.5s. Agora os bits só ligam com rumble NOSSO ativo, ou na
transição ativa→0 (UM report de stop com flags ligados, depois neutro).

E o corolário BT: o 0x31 da pydualsense 0.7.5 é malformado (firmware
descarta) — o `prepareReport` do override monta o envelope correto pelo
builder comum e o `writeReport` carimba o contador de sequência por handle.
"""
from __future__ import annotations

import zlib

from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import ds_output_report as rep

#: Offset do flag0/motores no report por transporte (envelope + common).
_USB_FLAG0, _USB_FLAG1 = 1, 2
_USB_MOTOR_R, _USB_MOTOR_L = 3, 4
_BT_FLAG0, _BT_FLAG1 = 3, 4
_VIB = rep.VALID_FLAG0_COMPATIBLE_VIBRATION | rep.VALID_FLAG0_HAPTICS_SELECT


class _FakeDev:
    def __init__(self) -> None:
        self.written: list[bytes] = []

    def write(self, data: bytes) -> int:
        self.written.append(bytes(data))
        return len(data)


def _make_inst(
    *, bt: bool = False, suppress: bool = False
) -> bp._PinnedPyDualSense:
    """Instância sem `init()` (sem hardware): só o estado que o report usa."""
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.leftMotor = 0
    inst.rightMotor = 0
    inst.light = DSLight()
    inst.audio = DSAudio()
    inst.triggerL = DSTrigger()
    inst.triggerR = DSTrigger()
    inst.conType = ConnectionType.BT if bt else ConnectionType.USB
    inst._suppress_leds = suppress
    inst._rumble_active = False
    inst._rumble_stop_pending = False
    inst._bt_seq = 0
    inst.device = _FakeDev()
    return inst


# --- keepalive neutro: os 3 estados (idle / ativo / transição ativa→0) -------


def test_idle_sai_neutro_sem_bits_de_vibracao() -> None:
    """Sem rumble nosso: flag0 sem 0x01|0x02, sem atenuação (flag1 0x40) e sem
    vibração v2 (flag2 0x04) — o firmware mantém o estado anterior e o rumble
    de terceiros sobrevive ao keepalive."""
    inst = _make_inst()
    r = inst.prepareReport()
    assert r[0] == 0x02
    assert r[_USB_FLAG0] & _VIB == 0
    assert r[_USB_FLAG1] & rep.VALID_FLAG1_MOTOR_POWER == 0
    assert r[1 + rep.COMMON_VALID_FLAG2] & rep.VALID_FLAG2_COMPATIBLE_VIBRATION2 == 0
    assert r[_USB_MOTOR_R] == 0 and r[_USB_MOTOR_L] == 0
    # Gatilhos/mic seguem autorizados (só a vibração fica neutra).
    assert r[_USB_FLAG0] & 0x0C == 0x0C


def test_rumble_ativo_liga_flags_e_motores() -> None:
    inst = _make_inst()
    inst.setLeftMotor(200)
    inst.setRightMotor(90)
    assert inst._rumble_active is True
    r = inst.prepareReport()
    assert r[_USB_FLAG0] & _VIB == _VIB
    assert r[_USB_FLAG1] & rep.VALID_FLAG1_MOTOR_POWER
    assert r[_USB_MOTOR_L] == 200 and r[_USB_MOTOR_R] == 90


def test_transicao_ativa_para_zero_emite_um_stop_e_volta_ao_neutro() -> None:
    """ativa→0: UM report com flags ligados e motores 0 (para o motor parar de
    verdade), e o ciclo seguinte volta ao neutro."""
    inst = _make_inst()
    inst.setLeftMotor(100)
    inst.prepareReport()
    inst.setLeftMotor(0)
    inst.setRightMotor(0)
    assert inst._rumble_active is False
    assert inst._rumble_stop_pending is True

    stop = inst.prepareReport()
    assert stop[_USB_FLAG0] & _VIB == _VIB  # flags LIGADOS para parar o motor
    assert stop[_USB_MOTOR_L] == 0 and stop[_USB_MOTOR_R] == 0
    assert inst._rumble_stop_pending is False

    neutro = inst.prepareReport()
    assert neutro[_USB_FLAG0] & _VIB == 0
    assert stop != neutro  # o dedup `_last_out_report` escreve os dois


def test_zero_para_zero_nao_gera_stop() -> None:
    """0→0 (jogo/perfil re-zerando): nunca vibrou, nada de report de stop."""
    inst = _make_inst()
    inst.setLeftMotor(0)
    inst.setRightMotor(0)
    assert inst._rumble_active is False
    assert inst._rumble_stop_pending is False


def test_supressao_de_led_continua_no_caminho_novo() -> None:
    """FEAT-DSX-LIGHTBAR-SYSFS-01 intacta: `_suppress_leds` limpa lightbar
    0x04 + player 0x10 do flag1 (o kernel é o dono desses LEDs)."""
    led_bits = (
        rep.VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE
        | rep.VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE
    )
    coberto = _make_inst(suppress=True).prepareReport()
    assert coberto[_USB_FLAG1] & led_bits == 0
    descoberto = _make_inst(suppress=False).prepareReport()
    assert descoberto[_USB_FLAG1] & led_bits == led_bits


def test_supressao_zera_flag2_setup_da_lightbar() -> None:
    """LIGHTBAR-BT-KEEPALIVE-01 (regressão do BTREPORT-02, forense da captura):
    sob supressão o flag2 sai SEM os bits de setup/brilho da lightbar
    (0x02|0x01), e os bytes de lightbar/player/setup (common[41..46]) ficam
    ZERO. Falha-sem: o keepalive re-engatava a máquina de setup a 2 Hz com o
    `ledOption=Both` (0x03) da pydualsense e o firmware travava a exibição
    (sysfs mostra cor, barra apagada)."""
    setup_bits = (
        rep.VALID_FLAG2_LIGHTBAR_SETUP_CONTROL_ENABLE
        | rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE
    )
    idx_flag2 = 1 + rep.COMMON_VALID_FLAG2
    coberto = _make_inst(suppress=True).prepareReport()
    assert coberto[idx_flag2] & setup_bits == 0
    # common[41..46] = envelope USB desloca +1: report[42..47].
    assert coberto[42:48] == [0, 0, 0, 0, 0, 0]
    # Sem supressão, o setup segue ligado (o daemon é dono da lightbar).
    descoberto = _make_inst(suppress=False).prepareReport()
    assert descoberto[idx_flag2] & setup_bits == setup_bits


# --- BTREPORT-02: envelope BT correto + seq por handle -----------------------


def test_bt_sai_bem_formado_com_tag_e_crc() -> None:
    """O 0x31 do override tem o layout do kernel (seq<<4, tag 0x10, common em
    [3..49], CRC little-endian) — não o malformado da pydualsense."""
    inst = _make_inst(bt=True)
    inst.setLeftMotor(80)
    r = inst.prepareReport()
    assert len(r) == 78
    assert r[0] == 0x31
    assert r[1] == 0x00  # seq 0 no prepare (o carimbo é do writeReport)
    assert r[2] == 0x10  # tag mágico — o byte que faltava no upstream
    assert r[_BT_FLAG0] & _VIB == _VIB
    assert r[5] == 0 and r[6] == 80  # motor R em common[2], L em common[3]
    esperado = zlib.crc32(b"\xa2" + bytes(r[:74])) & 0xFFFFFFFF
    assert int.from_bytes(bytes(r[74:78]), "little") == esperado


def test_bt_neutro_tambem_fica_sem_bits_de_vibracao() -> None:
    """O keepalive neutro vale IGUAL por BT — agora que o report cola, sem
    isso o fix BT mataria o rumble direto-do-jogo do roxo (risco documentado
    do estudo)."""
    r = _make_inst(bt=True).prepareReport()
    assert r[_BT_FLAG0] & _VIB == 0
    assert r[_BT_FLAG1] & rep.VALID_FLAG1_MOTOR_POWER == 0


def test_writereport_bt_carimba_seq_crescente_com_wrap() -> None:
    """`writeReport` carimba o contador por handle (wrap 0-15) NUMA CÓPIA —
    o buffer comparado pelo dedup segue com seq 0."""
    inst = _make_inst(bt=True)
    report = inst.prepareReport()
    for _ in range(17):
        inst.writeReport(report)
    seqs = [w[1] >> 4 for w in inst.device.written]
    assert seqs == [*range(16), 0]  # 0..15 e wrap
    assert report[1] == 0x00  # original intacto (dedup vivo)
    # Cada write saiu com CRC válido para o seq carimbado.
    for w in inst.device.written:
        esperado = zlib.crc32(b"\xa2" + w[:74]) & 0xFFFFFFFF
        assert int.from_bytes(w[74:78], "little") == esperado


def test_writereport_usb_escreve_como_sempre() -> None:
    inst = _make_inst()
    report = inst.prepareReport()
    inst.writeReport(report)
    assert inst.device.written == [bytes(report)]


# --- HARM-16 com keepalive neutro: o stop forçado da saída de modo -----------


def test_force_rumble_stop_arma_o_stop_em_todos_os_handles() -> None:
    """Saída de modo com o JOGO vibrando por fora (hidraw direto): nossos
    motores estão em 0 (0→0 não gera stop) — `force_rumble_stop` arma UM
    report de stop por handle para o motor parar de verdade."""
    ctl = bp.PyDualSenseController()
    h1, h2 = _make_inst(), _make_inst(bt=True)
    ctl._handles = {"aa": h1, "bb": h2}  # type: ignore[dict-item]

    ctl.force_rumble_stop()

    for inst in (h1, h2):
        assert inst._rumble_stop_pending is True
        stop = inst.prepareReport()
        flag0 = stop[_BT_FLAG0] if inst.conType == ConnectionType.BT else stop[_USB_FLAG0]
        assert flag0 & _VIB == _VIB
        neutro = inst.prepareReport()
        flag0 = neutro[_BT_FLAG0] if inst.conType == ConnectionType.BT else neutro[_USB_FLAG0]
        assert flag0 & _VIB == 0


def test_zero_motors_on_mode_exit_prefere_o_stop_forcado() -> None:
    """`zero_motors_on_mode_exit` (HARM-16) usa `force_rumble_stop` quando o
    backend expõe; fakes/backends sem o método seguem no set_rumble(0,0)."""
    from types import SimpleNamespace

    from hefesto_dualsense4unix.daemon.subsystems.rumble import (
        zero_motors_on_mode_exit,
    )

    chamadas: list[str] = []
    com_force = SimpleNamespace(
        config=SimpleNamespace(rumble_active=None),
        controller=SimpleNamespace(
            force_rumble_stop=lambda: chamadas.append("force"),
            set_rumble=lambda weak, strong: chamadas.append("zero"),
        ),
    )
    zero_motors_on_mode_exit(com_force)  # type: ignore[arg-type]
    assert chamadas == ["force"]

    chamadas.clear()
    sem_force = SimpleNamespace(
        config=SimpleNamespace(rumble_active=None),
        controller=SimpleNamespace(
            set_rumble=lambda weak, strong: chamadas.append(f"zero={weak},{strong}")
        ),
    )
    zero_motors_on_mode_exit(sem_force)  # type: ignore[arg-type]
    assert chamadas == ["zero=0,0"]
