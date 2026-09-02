"""MIC-DA-MESA-ELEICAO-01 — as réguas da borda do microfone COM ENDEREÇO.

Quatro perguntas, e cada uma nasceu de um caminho que estava aberto:

1. **O byte de áudio recusa lixo.** Ele era lido de `self.states[54]`, que é o
   report já digerido pela pydualsense 0.7.5 — sem CRC, sem report id, sem o
   `INPUT_FLAG_AUDIO`. Com a ponte de mic por BT de pé, o Opus ocupa
   `raw[3:74]` e o byte cai DENTRO dessa janela. É o PS-PRESO-01 inteiro: foi
   assim que os botões MIC e PS ficaram presos e ela desligou o controle.
   Enquanto o byte só pintava um selo, o estrago era cosmético; a partir da
   eleição, um pacote corrompido de rádio elege microfone sozinho.

2. **A borda tem `uniq`.** O `BUTTON_DOWN` não carrega endereço e o
   `read_state()` só vê o primário — numa mesa de quatro, três apertos
   ficariam sem dono.

3. **A borda é CONTADOR, não leitura de estado.** Um toque duplo entre duas
   amostragens devolveria o mesmo valor de estado e a segunda eleição sumiria.
   Sumir uma borda é sumir uma eleição dela.

4. **O tempo é parte da régua.** Uma régua que roda o tique uma vez mede um
   INSTANTE, não um comportamento — em 29/08 uma regressão só apareceu aos 181
   segundos, com 67 testes verdes. Aqui o tempo é simulado report a report,
   porque o que se mede é o CONTADOR ao longo de uma sessão inteira, não o
   relógio de parede.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import STATUS_MIC_MUDO

_MAC_A = "aabbcc000001"
_MAC_B = "aabbcc000002"


def _handle() -> Any:
    """Handle com só o estado que `_captura_status_audio` toca."""
    h = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    h._audio_status = None
    h._mic_mudo = None
    h._mic_mudo_seq = 0
    h._mic_mudo_em = None
    return h


def _report_usb(status: int) -> bytes:
    """Report `0x01` de USB com `status[1]` valendo `status`.

    `_USB_STRUCT_BASE` é 1 e `JACK_STATUS_OFFSET` é 53, logo o byte mora no
    índice 54 — o mesmo que o caminho velho lia do `states`.
    """
    corpo = bytearray(64)
    corpo[0] = prr.INPUT_REPORT_USB
    corpo[1 + prr.JACK_STATUS_OFFSET] = status
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


# ---------------------------------------------------------------------------
# 1. O byte de áudio recusa lixo
# ---------------------------------------------------------------------------


def test_report_integro_e_lido() -> None:
    """A metade que prova que a disciplina não é "parar de funcionar"."""
    h = _handle()
    h._captura_status_audio(_report_usb(STATUS_MIC_MUDO))
    assert h._audio_status == STATUS_MIC_MUDO

    h2 = _handle()
    h2._captura_status_audio(_report_bt(STATUS_MIC_MUDO))
    assert h2._audio_status == STATUS_MIC_MUDO


def test_report_de_audio_do_bt_nao_mexe_no_cache() -> None:
    """PS-PRESO-01: com o mic ligado, `raw[3:74]` é Opus e o byte 55 é ruído.

    CURA A ARRANCAR: voltar `_captura_status_audio` a ler `self.states[54]` —
    o byte passa a acompanhar o lixo e esta régua reprova.
    """
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


# ---------------------------------------------------------------------------
# 2 e 3. A borda tem `uniq`, e é CONTADOR
# ---------------------------------------------------------------------------


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
    return b


def test_a_borda_carrega_o_uniq_de_quem_apertou() -> None:
    """O Jogador 2 aperta: UM evento com o `uniq` dele, NENHUM com o do 1."""
    a, b = _handle(), _handle()
    backend = _backend({_MAC_A: a, _MAC_B: b})

    for h in (a, b):
        h._captura_status_audio(_report_usb(0x00))
    b._captura_status_audio(_report_usb(STATUS_MIC_MUDO))

    bordas = backend.bordas_do_mic()
    assert bordas[_MAC_A][0] == 0, "o Jogador 1 não encostou no botão"
    assert bordas[_MAC_B][0] == 1
    assert bordas[_MAC_B][1] is True, "o valor DEPOIS da virada"


def test_toque_duplo_entre_duas_leituras_conta_duas_bordas() -> None:
    """CURA A ARRANCAR: trocar o contador por leitura do estado atual.

    A sequência mudo → não-mudo → mudo devolve o MESMO estado do começo. Quem
    lê estado vê "nada mudou" e a eleição do meio some; quem CONTA vê duas.
    """
    h = _handle()
    backend = _backend({_MAC_A: h})
    h._captura_status_audio(_report_usb(STATUS_MIC_MUDO))
    antes = backend.bordas_do_mic()[_MAC_A]

    h._captura_status_audio(_report_usb(0x00))
    h._captura_status_audio(_report_usb(STATUS_MIC_MUDO))
    depois = backend.bordas_do_mic()[_MAC_A]

    assert depois[1] == antes[1], "o ESTADO voltou ao que era — este é o ponto"
    assert depois[0] - antes[0] == 2, "e o CONTADOR viu os dois apertos"


def test_report_repetido_nao_inventa_borda() -> None:
    """O laço lê ~31 reports/s. Sem a comparação, seriam 31 eleições por segundo."""
    h = _handle()
    backend = _backend({_MAC_A: h})
    for _ in range(200):
        h._captura_status_audio(_report_usb(STATUS_MIC_MUDO))
    assert backend.bordas_do_mic()[_MAC_A][0] == 0, "a PRIMEIRA leitura não é borda"


def test_handle_sem_uniq_resolvivel_fica_de_fora() -> None:
    """Key por path ("/dev/hidraw3") não vira pseudo-MAC.

    Eleição sem endereço é eleição do controle errado — melhor não emitir.
    """
    h = _handle()
    backend = _backend({"/dev/hidraw3": h})
    h._captura_status_audio(_report_usb(0x00))
    h._captura_status_audio(_report_usb(STATUS_MIC_MUDO))
    assert backend.bordas_do_mic() == {}


# ---------------------------------------------------------------------------
# 4. O TEMPO é parte da régua
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("apertos", [1, 7, 60])
def test_o_contador_sobrevive_a_uma_sessao_inteira(apertos: int) -> None:
    """~200 s de reports a 31 Hz, com apertos espalhados: a conta tem de fechar.

    Existe porque a regressão de 29/08 só apareceu aos 181 segundos, com 67
    testes verdes. Aqui o tempo é contado em REPORTS (que é o relógio real
    deste laço) e não em segundos de parede, para a régua ser estável no CI.
    """
    h = _handle()
    backend = _backend({_MAC_A: h})
    total = 31 * 200
    quando = {int(total * (i + 1) / (apertos + 1)) for i in range(apertos)}
    mudo = False
    h._captura_status_audio(_report_usb(0x00))
    for i in range(total):
        if i in quando:
            mudo = not mudo
        h._captura_status_audio(_report_usb(STATUS_MIC_MUDO if mudo else 0x00))

    assert backend.bordas_do_mic()[_MAC_A][0] == apertos
