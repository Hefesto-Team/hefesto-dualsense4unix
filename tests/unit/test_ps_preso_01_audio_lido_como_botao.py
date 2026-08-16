"""PS-PRESO-01 (16/08/2026) — áudio lido como botão prendeu o MIC e o PS.

**O relato dela**, ao vivo, com o controle na mão::

    "tive que desligar o controler pq o teclado, o mouse (tava teclando sem
     parar e o botão direito do mouse também), cara, foi muito mas muito
     estranho, desliguei o controle e parou fiquei com medo"

    "eu não havia pressionado o botão, mas notei outra coisa: o botão de
     microfone e o ps tava como se eu tivesse pressionado."

**Essa segunda frase é o diagnóstico inteiro.** MIC e PS moram no MESMO byte do
`struct dualsense_input_report` (`buttons[2]`, o payload[9]). Dois botões
vizinhos presos ao mesmo tempo não é botão emperrado — é o byte errado sendo
lido como botão.

**A causa.** Com o microfone ligado, o DualSense manda áudio Opus **no mesmo
report `0x31`, com os mesmos 78 bytes, e com CRC-32 VÁLIDO**. A única coisa que
separa um report de áudio de um report de input é o bit ``0x02`` do byte 1.

O `_struct_base` conferia id, tamanho e CRC — e nenhum dos três pega áudio,
porque o report de áudio é legítimo em todos. Então ele devolvia base, e os
bytes de Opus caíam exatamente sobre os eixos e os botões.

**O estrago, medido no log.** Três minutos depois de a ponte do mic subir::

    20:19:26  ps_button_action_steam   outcome=refocus_fallback_spawn
    20:19:26  steam_spawn_requested
    20:19:26  ps_solo_released         held_ms=295.0
    20:19:26  ps_button_action_steam   outcome=refocus_fallback_spawn   (de novo)
    20:19:27  ps_solo_released         held_ms=331.7                    (e de novo)

O PS "pressionado" dezenas de vezes por segundo, cada vez pedindo foco na Steam.
Sem `wmctrl` na máquina, cada pedido virava um LANÇAMENTO da Steam. Foi isso o
"teclado e mouse com vida própria" — nunca foi o teclado. Três segundos depois o
controle caiu inteiro (`errno 19` nos três leitores).

**Por que nenhum teste pegou.** O projeto tinha teste de CRC, de tamanho e de id
— as três defesas que o report de áudio ATRAVESSA por ser legítimo. Faltava a
única que o separa. E `INPUT_FLAG_AUDIO` existia num módulo só
(`integrations/dualsense_bt_audio.py`), que o caminho de leitura nunca importou.

**A lição que vale além deste bug:** um payload que passa por todas as validações
de FORMA e ainda assim é semanticamente outra coisa é o caso em que validar mais
forte não ajuda — só conhecer o protocolo ajuda.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.core.physical_report_reader import (
    INPUT_FLAG_AUDIO,
    INPUT_REPORT_BT,
    INPUT_REPORT_BT_SIZE,
    INPUT_REPORT_USB,
    _struct_base,
    extract_motion_window,
)
from hefesto_dualsense4unix.core.ds_output_report import BT_INPUT_CRC_SEED, bt_crc32

#: `buttons[2]` do `struct dualsense_input_report` — onde moram MIC e PS.
_BUTTONS2_NO_PAYLOAD = 9
#: O byte 1 de um `0x31` normal de input: o bit HID ligado, o de áudio não.
_FLAG_HID = 0x01


def _report_bt(*, com_audio: bool, recheio: int = 0xFF) -> bytes:
    """Um `0x31` de 78 bytes com CRC VÁLIDO — de áudio ou de input.

    O recheio `0xFF` imita o pior caso real: bytes de Opus que, lidos como
    `buttons[2]`, acendem TODOS os botões de uma vez (foi assim que MIC e PS
    apareceram presos juntos).
    """
    corpo = bytearray(INPUT_REPORT_BT_SIZE - 4)
    corpo[0] = INPUT_REPORT_BT
    corpo[1] = _FLAG_HID | (INPUT_FLAG_AUDIO if com_audio else 0x00)
    for i in range(2, len(corpo)):
        corpo[i] = recheio
    crc = bt_crc32(bytes(corpo), seed=BT_INPUT_CRC_SEED)
    return bytes(corpo) + crc.to_bytes(4, "little")


class TestOReportDeAudioNaoEInput:
    def test_a_mordida_audio_com_crc_valido_e_recusado(self) -> None:
        """Arranque o filtro do bit e este teste reprova.

        E note o que ele prova junto: o report é PERFEITO em id, tamanho e CRC.
        As três defesas que existiam antes o deixariam passar.
        """
        audio = _report_bt(com_audio=True)
        assert audio[0] == INPUT_REPORT_BT
        assert len(audio) == INPUT_REPORT_BT_SIZE
        crc = int.from_bytes(audio[-4:], "little")
        assert bt_crc32(audio[:-4], seed=BT_INPUT_CRC_SEED) == crc, (
            "o report de áudio TEM CRC válido — é por isso que o CRC não protegia"
        )
        assert _struct_base(audio) is None, (
            "áudio Opus foi aceito como estado de input: os bytes caem sobre os "
            "botões e prendem MIC e PS (PS-PRESO-01)"
        )

    def test_input_de_verdade_continua_passando(self) -> None:
        """O filtro não pode virar 'recusa tudo no rádio'."""
        assert _struct_base(_report_bt(com_audio=False)) == 2

    def test_o_usb_nao_e_afetado(self) -> None:
        """O bit é do envelope BT; no cabo não existe report de áudio assim."""
        usb = bytes([INPUT_REPORT_USB]) + bytes(63)
        assert _struct_base(usb) == 1

    def test_a_janela_de_motion_tambem_recusa_audio(self) -> None:
        """Um consumidor, um portão: motion herda a mesma disciplina.

        Se o motion tivesse um caminho próprio, o giroscópio passaria a receber
        Opus e a mira giraria sozinha.
        """
        assert extract_motion_window(_report_bt(com_audio=True)) is None
        assert extract_motion_window(_report_bt(com_audio=False)) is not None

    def test_crc_ruim_continua_recusado(self) -> None:
        """A defesa velha não pode ter sido perdida no caminho."""
        ruim = bytearray(_report_bt(com_audio=False))
        ruim[-1] ^= 0xFF
        assert _struct_base(bytes(ruim)) is None


class TestOsBotoesQueFicaramPresos:
    def test_audio_recusado_nunca_vira_buttons2(self) -> None:
        """O byte que prendeu MIC e PS não pode mais ser alcançado.

        Com recheio 0xFF, `buttons[2]` viria com todos os bits em 1 — MIC e PS
        inclusive. É a foto exata do que ela viu.
        """
        audio = _report_bt(com_audio=True, recheio=0xFF)
        base = _struct_base(audio)
        assert base is None, (
            "com base válida, payload[9] seria 0xFF = todos os botões "
            "pressionados, MIC e PS entre eles"
        )

    def test_um_report_de_input_com_buttons2_cheio_ainda_passa(self) -> None:
        """Botões de verdade todos apertados é possível — e tem de passar.

        O filtro separa áudio de input, não 'muitos botões' de 'poucos'.
        """
        entrada = _report_bt(com_audio=False, recheio=0xFF)
        base = _struct_base(entrada)
        assert base == 2
        assert entrada[base + _BUTTONS2_NO_PAYLOAD] == 0xFF


class TestAsDuasConstantesNaoPodemDivergir:
    def test_o_bit_e_o_mesmo_dos_dois_lados(self) -> None:
        """A constante é duplicada de propósito; divergir seria pior que duplicar.

        O caminho quente da leitura não pode importar o módulo de áudio (ctypes,
        libopus). Então o valor vive nos dois lugares — e este teste é o que
        impede que um mude sem o outro.
        """
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            INPUT_FLAG_AUDIO as DO_AUDIO,
        )
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            INPUT_REPORT_BT as ID_DO_AUDIO,
        )
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            INPUT_REPORT_BT_SIZE as TAM_DO_AUDIO,
        )

        assert INPUT_FLAG_AUDIO == DO_AUDIO
        assert INPUT_REPORT_BT == ID_DO_AUDIO
        assert INPUT_REPORT_BT_SIZE == TAM_DO_AUDIO

    def test_o_reconhecedor_de_audio_concorda_com_o_portao(self) -> None:
        """As duas leituras do MESMO report têm de dizer a mesma coisa."""
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            eh_report_de_audio,
        )

        audio = _report_bt(com_audio=True)
        entrada = _report_bt(com_audio=False)
        assert eh_report_de_audio(audio) and _struct_base(audio) is None
        assert not eh_report_de_audio(entrada) and _struct_base(entrada) == 2


@pytest.mark.parametrize("recheio", [0x00, 0x7F, 0xAA, 0xFF])
def test_qualquer_recheio_de_opus_e_recusado(recheio: int) -> None:
    """Opus é binário arbitrário — nenhum valor pode escapar pelo filtro."""
    assert _struct_base(_report_bt(com_audio=True, recheio=recheio)) is None
