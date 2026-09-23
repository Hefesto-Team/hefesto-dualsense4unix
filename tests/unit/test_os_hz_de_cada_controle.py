"""Os Hz de verdade de cada controle — AR-MEDIDO-01 (23/09/2026), R10 dela.

Quem conta é o leitor do nó de MOVIMENTO (``MotionSensorReader``), que já lia
o nó para o giroscópio: um pacote por relatório de estado, carimbado pelo
kernel. Nada aqui abre ``/dev/input``: os eventos são dublês com o carimbo
escrito à mão.

A MORDIDA, feita em 23/09/2026: tirar a exclusão do intervalo que atravessa um
``SYN_DROPPED`` faz ``test_o_pacote_que_o_nosso_buffer_perdeu_nao_derruba_os_hz``
reprovar — o número cai de 800 para 520,7, e a tela diria que o RÁDIO
entregou menos quando quem perdeu foi a nossa thread. Devolvida, md5 conferido.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from hefesto_dualsense4unix.core.evdev_reader import MotionSensorReader
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub

ECODES = SimpleNamespace(
    EV_SYN=0, SYN_REPORT=0, SYN_DROPPED=3, EV_ABS=3, EV_MSC=4,
    ABS_X=0, ABS_Y=1, ABS_Z=2, ABS_RX=3, ABS_RY=4, ABS_RZ=5,
)


class Relogio:
    def __init__(self) -> None:
        self.agora = 50.0

    def __call__(self) -> float:
        return self.agora


def _leitor(relogio: Relogio) -> MotionSensorReader:
    leitor = MotionSensorReader(device_path=Path("/nao/existe"), target_uniq="aabbcc000011")
    leitor._relogio_da_taxa = relogio
    leitor._active_dev = object()
    leitor._zerar_a_taxa(aberto=True)
    return leitor


def _syn(leitor: MotionSensorReader, carimbo: float, *, codigo: int = 0) -> None:
    sec = int(carimbo)
    usec = round((carimbo - sec) * 1e6)
    leitor._handle_event(SimpleNamespace(type=0, code=codigo, sec=sec, usec=usec), ECODES)


def _pacotes(leitor: MotionSensorReader, inicio: float, hz: float, quantos: int) -> float:
    """``quantos`` pacotes a ``hz``; o relógio do processo anda junto."""
    relogio = leitor._relogio_da_taxa
    carimbo = inicio
    for _ in range(quantos):
        _syn(leitor, carimbo)
        carimbo += 1.0 / hz
        relogio.agora += 1.0 / hz
    return carimbo - 1.0 / hz


def test_o_no_que_recebe_250_pacotes_por_segundo_diz_250() -> None:
    relogio = Relogio()
    leitor = _leitor(relogio)
    _pacotes(leitor, 1_000.0, 250.0, 500)
    hz = leitor.hz_do_movimento()
    assert hz is not None and 245.0 <= hz <= 255.0


def test_o_pacote_que_o_nosso_buffer_perdeu_nao_derruba_os_hz() -> None:
    """O ``SYN_DROPPED`` é perda NOSSA, não do rádio: o buraco não entra."""
    relogio = Relogio()
    leitor = _leitor(relogio)
    fim = _pacotes(leitor, 1_000.0, 800.0, 400)
    _syn(leitor, fim + 0.0001, codigo=3)
    # 350 ms de pacotes que a thread não leu: o próximo chega com o carimbo
    # de depois do buraco.
    relogio.agora += 0.350
    _pacotes(leitor, fim + 0.350, 800.0, 400)
    hz = leitor.hz_do_movimento()
    assert hz is not None and hz >= 760.0, f"o buraco do nosso buffer virou rádio lento: {hz}"


def test_o_silencio_do_radio_derruba_os_hz() -> None:
    """Sem ``SYN_DROPPED``, o buraco é do enlace — e ele TEM de aparecer."""
    relogio = Relogio()
    leitor = _leitor(relogio)
    fim = _pacotes(leitor, 1_000.0, 800.0, 400)
    relogio.agora += 0.350
    _pacotes(leitor, fim + 0.350, 800.0, 400)
    hz = leitor.hz_do_movimento()
    assert hz is not None and hz < 700.0


def test_no_aberto_e_mudo_por_uma_janela_inteira_e_zero() -> None:
    relogio = Relogio()
    leitor = _leitor(relogio)
    _pacotes(leitor, 1_000.0, 250.0, 100)
    relogio.agora += 1.5
    assert leitor.hz_do_movimento() == 0.0


def test_no_fechado_ou_recem_aberto_e_nao_sei() -> None:
    relogio = Relogio()
    leitor = _leitor(relogio)
    _pacotes(leitor, 1_000.0, 250.0, 50)
    assert leitor.hz_do_movimento() is None, "menos de uma janela aberto não é taxa"
    relogio.agora += 2.0
    leitor._active_dev = None
    assert leitor.hz_do_movimento() is None
    leitor._active_dev = object()
    leitor._reset_on_disconnect()
    assert leitor.hz_do_movimento() is None


def test_o_carimbo_que_salta_para_tras_nao_vira_intervalo() -> None:
    relogio = Relogio()
    leitor = _leitor(relogio)
    fim = _pacotes(leitor, 1_000.0, 250.0, 250)
    _pacotes(leitor, fim - 3_600.0, 250.0, 250)
    hz = leitor.hz_do_movimento()
    assert hz is not None and 240.0 <= hz <= 260.0


# ---------------------------------------------------------------- o hub


class _Leitor:
    def __init__(self, hz: object) -> None:
        self._hz = hz

    def hz_do_movimento(self) -> object:
        return self._hz


def test_o_hub_pergunta_ao_leitor_e_registra_a_demanda() -> None:
    hub = SensorHub(auto_manutencao=False, relogio=lambda: 7.0)
    hub._motion["aabbcc000011"] = _Leitor(412.5)
    assert hub.hz_do_movimento("aabbcc000011") == 412.5
    assert hub._demanda["aabbcc000011"] == 7.0


def test_o_hub_sem_leitor_ou_com_resposta_torta_diz_nao_sei() -> None:
    hub = SensorHub(auto_manutencao=False)
    assert hub.hz_do_movimento("aabbcc000011") is None
    hub._motion["aabbcc000011"] = _Leitor(True)
    assert hub.hz_do_movimento("aabbcc000011") is None
    hub._motion["aabbcc000011"] = _Leitor("400")
    assert hub.hz_do_movimento("aabbcc000011") is None
