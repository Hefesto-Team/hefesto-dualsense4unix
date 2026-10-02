"""MIC-DA-MESA-ELEICAO-01 — as réguas da borda do microfone COM ENDEREÇO."""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import STATUS_MIC_MUDO

_MAC_A = "aabbcc000001"
_MAC_B = "aabbcc000002"


def _handle() -> Any:
    """Handle com o estado da eleição do mic — pedido AO PRODUTO."""
    h = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    h._audio_status = None
    h.zerar_estado_da_borda_do_mic()
    return h


_REPORTS = 8


def _segurar(h: Any, status: int, reports: int = _REPORTS, *, botao: bool = False) -> None:
    """Repete o MESMO report — o estado do firmware e o do botão — `reports` vezes."""
    for _ in range(reports):
        h._captura_status_audio(_report_usb(status, botao=botao))


def _apertar(h: Any, status: int) -> None:
    """Um aperto do botão: o dedo desce com o firmware no valor de antes, o"""
    antes = h._audio_status if isinstance(h._audio_status, int) else 0x00
    _segurar(h, antes, reports=1, botao=True)
    _segurar(h, status, botao=True)
    _segurar(h, status)


def _report_usb(status: int, *, botao: bool = False) -> bytes:
    """Report `0x01` de USB com `status[1]` valendo `status`."""
    corpo = bytearray(64)
    corpo[0] = prr.INPUT_REPORT_USB
    corpo[1 + prr.JACK_STATUS_OFFSET] = status
    if botao:
        corpo[1 + prr.BUTTONS2_OFFSET] |= prr.MIC_BUTTON_BIT
    return bytes(corpo)


def _report_bt(status: int, *, audio: bool = False, crc_bom: bool = True) -> bytes:
    """Report `0x31` de 78 B, com CRC-32 de verdade (ou de mentira)."""
    corpo = bytearray(prr.INPUT_REPORT_BT_SIZE)
    corpo[0] = prr.INPUT_REPORT_BT
    corpo[1] = prr.INPUT_FLAG_AUDIO if audio else 0x00
    corpo[2 + prr.JACK_STATUS_OFFSET] = status
    crc = prr.bt_crc32(bytes(corpo[:-4]), seed=prr.BT_INPUT_CRC_SEED)
    if not crc_bom:
        crc ^= 0xFFFFFFFF
    corpo[-4:] = crc.to_bytes(4, "little")
    return bytes(corpo)


def test_report_integro_e_lido() -> None:
    """A metade que prova que a disciplina não é "parar de funcionar"."""
    h = _handle()
    h._captura_status_audio(_report_usb(STATUS_MIC_MUDO))
    assert h._audio_status == STATUS_MIC_MUDO

    h2 = _handle()
    h2._captura_status_audio(_report_bt(STATUS_MIC_MUDO))
    assert h2._audio_status == STATUS_MIC_MUDO


def test_report_de_audio_do_bt_nao_mexe_no_cache() -> None:
    """PS-PRESO-01: com o mic ligado, `raw[3:74]` é Opus e o byte 55 é ruído."""
    h = _handle()
    h._captura_status_audio(_report_bt(0x00))
    assert h._audio_status == 0x00

    h._captura_status_audio(_report_bt(0xFF, audio=True))
    assert h._audio_status == 0x00, "um report de ÁUDIO não diz nada sobre o jack"


def test_crc_ruim_do_radio_nao_mexe_no_cache() -> None:
    """CRC ruim é "não sei", e "não sei" NÃO é `0x00` nem o valor corrompido."""
    h = _handle()
    h._captura_status_audio(_report_bt(0x00))
    h._captura_status_audio(_report_bt(STATUS_MIC_MUDO, crc_bom=False))
    assert h._audio_status == 0x00


def test_report_de_id_desconhecido_nao_mexe_no_cache() -> None:
    """Report de feature, `0x05` parcial, tamanho curto: nada disso é estado."""
    h = _handle()
    h._captura_status_audio(_report_usb(0x00))
    h._captura_status_audio(bytes([0x05, 0xFF, 0xFF]))
    assert h._audio_status == 0x00


class _LockFalso:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: Any) -> None:
        return None


def _backend(handles: dict[str, Any]) -> Any:
    """Backend real, sem device: só o dict de handles e o lock."""
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    b = PyDualSenseController.__new__(PyDualSenseController)
    b._handles = handles
    b._io_lock = _LockFalso()
    b._mic_mute_by_uniq = {}
    return b


def test_a_borda_carrega_o_uniq_de_quem_apertou() -> None:
    """O Jogador 2 aperta: UM evento com o `uniq` dele, NENHUM com o do 1."""
    a, b = _handle(), _handle()
    backend = _backend({_MAC_A: a, _MAC_B: b})

    for h in (a, b):
        _segurar(h, 0x00)
    _apertar(b, STATUS_MIC_MUDO)

    bordas = backend.bordas_do_mic()
    assert bordas[_MAC_A][0] == 0, "o Jogador 1 não encostou no botão"
    assert bordas[_MAC_B][0] == 1
    assert bordas[_MAC_B][1] is True, "o que o aperto pede: o microfone estava livre"


def test_toque_duplo_entre_duas_leituras_conta_duas_bordas() -> None:
    """CURA A ARRANCAR: trocar o contador por leitura do estado atual."""
    h = _handle()
    backend = _backend({_MAC_A: h})
    _segurar(h, STATUS_MIC_MUDO)
    antes = backend.bordas_do_mic()[_MAC_A]

    _apertar(h, 0x00)
    _apertar(h, STATUS_MIC_MUDO)
    depois = backend.bordas_do_mic()[_MAC_A]

    assert bool(h._audio_status & STATUS_MIC_MUDO), "o ESTADO voltou ao que era"
    assert depois[0] - antes[0] == 2, "e o CONTADOR viu os dois apertos"


def test_report_repetido_nao_inventa_borda() -> None:
    """O laço lê ~31 reports/s. Sem a comparação, seriam 31 eleições por segundo."""
    h = _handle()
    backend = _backend({_MAC_A: h})
    for _ in range(200):
        h._captura_status_audio(_report_usb(STATUS_MIC_MUDO))
    assert backend.bordas_do_mic()[_MAC_A][0] == 0, "a PRIMEIRA leitura não é borda"


def test_handle_sem_uniq_resolvivel_fica_de_fora() -> None:
    """Key por path ("/dev/hidraw3") não vira pseudo-MAC."""
    h = _handle()
    backend = _backend({"/dev/hidraw3": h})
    _segurar(h, 0x00)
    _apertar(h, STATUS_MIC_MUDO)
    assert backend.bordas_do_mic() == {}


@pytest.mark.parametrize("apertos", [1, 7, 60])
def test_o_contador_sobrevive_a_uma_sessao_inteira(apertos: int) -> None:
    """~200 s de reports a 31 Hz, com apertos espalhados: a conta tem de fechar."""
    h = _handle()
    backend = _backend({_MAC_A: h})
    total = 31 * 200
    quando = {int(total * (i + 1) / (apertos + 1)) for i in range(apertos)}
    mudo = False
    h._captura_status_audio(_report_usb(0x00))
    dedo = 0
    for i in range(total):
        if i in quando:
            mudo = not mudo
            dedo = 3
        h._captura_status_audio(
            _report_usb(STATUS_MIC_MUDO if mudo else 0x00, botao=dedo > 0)
        )
        dedo = max(0, dedo - 1)

    assert backend.bordas_do_mic()[_MAC_A][0] == apertos, (
        "os apertos dela estão espalhados em 200 s de reports, e a conta tem "
        "de fechar um a um"
    )


def test_o_bit_que_oscila_com_o_botao_parado_nao_e_aperto() -> None:
    """O gating do rádio: o bit vira e volta SESSENTA vezes, e o dedo não desceu."""
    h = _handle()
    backend = _backend({_MAC_A: h})
    _segurar(h, 0x00)
    partida = backend.bordas_do_mic()[_MAC_A][0]

    for i in range(60):
        _segurar(h, STATUS_MIC_MUDO if i % 2 else 0x00, reports=2)

    assert backend.bordas_do_mic()[_MAC_A][0] == partida, (
        "o gating do firmware virou aperto — é o defeito que corta o "
        "microfone dela aos 1,1 s"
    )
