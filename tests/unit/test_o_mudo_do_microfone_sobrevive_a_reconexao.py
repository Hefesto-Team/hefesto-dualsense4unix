"""MIC-BT-DONO-01 — a posse do mudo de microfone sobrevive ao handle novo.

**O defeito, e ele é de POSSE, não de áudio.** `_mic_mute_desejado` era
atributo de instância do `_PinnedPyDualSense`, e o handle é RECRIADO a cada
reconexão. Um `mic unmute` dela evaporava no próximo handle novo, em silêncio,
e o firmware — que retém o mudo — voltava a mudo. O mapa de canais registra
exatamente isso em `audio.microfone.mudo@dualsense`, `radio_ressalva`:
*"um `mic unmute` evapora no próximo handle novo, em silêncio, e o firmware
volta a mudo. Como reconexão é rotina no rádio, o defeito é muito mais visível
por BT."*

**Por que se asserta o BYTE e não o atributo — e por que são DOIS asserts.**
`common[9] == 0x00` sozinho PASSA com a cura arrancada: o handle novo nasce com
o registrador zerado. O que separa "mandamos desmutar" de "não somos donos" é o
bit de autorização `VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE` do `common[1]` —
sem ele o firmware ignora o byte inteiro e quem manda volta a ser o kernel.

**Os endereços vêm do mapa** (`docs/data/mapa-controles.csv`,
`audio.microfone.mudo@dualsense`), não da lembrança:

    cabo   report 0x02 — common[9] bit 0x10 = report[10]; flag1 0x02
    rádio  report 0x31 — common[9] bit 0x10 = report[12]

A prova com o aparelho de verdade caindo e voltando no rádio é da
MESA-DE-QUATRO-01; aqui a reconexão é simulada com handle novo, que é o
mecanismo exato do defeito.
"""

from __future__ import annotations

from typing import Any

from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import ds_output_report as rep

#: Máscara da casa (octetos 4 e 5 zerados) — nada de MAC real em arquivo
#: versionado.
KEY_1 = "AA:BB:CC:00:00:01"
UNIQ_1 = "aabbcc000001"
KEY_2 = "AA:BB:CC:00:00:02"

#: Os offsets do mapa, escritos uma vez só.
FLAG1_NO_CABO, MUDO_NO_CABO = 2, 10
FLAG1_NO_RADIO, MUDO_NO_RADIO = 4, 12


def _handle_recem_nascido(*, radio: bool = True) -> Any:
    """Um `_PinnedPyDualSense` como o hotplug o entrega: SEM dono do mudo.

    `__new__` de propósito — o `__init__` real abre hidraw. O que importa para
    esta régua é que `_mic_mute_desejado` nasce `None`, que é o caso quebrado,
    e que `prepareReport()` seja o do produto (o mesmo `_build_common`).
    """
    handle = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    handle.leftMotor = 0
    handle.rightMotor = 0
    handle.light = DSLight()
    handle.audio = DSAudio()
    handle.triggerL = DSTrigger()
    handle.triggerR = DSTrigger()
    handle.conType = ConnectionType.BT if radio else ConnectionType.USB
    handle._suppress_leds = bool(radio)
    handle._rumble_active = False
    handle._rumble_stop_pending = False
    handle._bt_seq = 0
    handle._raw_trigger_left = None
    handle._raw_trigger_right = None
    handle._volumes_audio = [None, None, None, None]
    handle._preamp_audio = None
    handle._mic_led_desejado = None
    #: o caso quebrado, e é o ponto inteiro da sprint.
    handle._mic_mute_desejado = None
    return handle


def _ctl_com(handle: Any, key: str = KEY_1) -> bp.PyDualSenseController:
    ctl = bp.PyDualSenseController()
    ctl._handles = {key: handle}
    ctl._primary_key = key
    return ctl


def _reconectar(ctl: bp.PyDualSenseController, *, radio: bool, key: str = KEY_1) -> Any:
    """A queda e a volta: handle NOVO no lugar do velho, e o tique de hotplug.

    É o mecanismo do defeito em duas linhas — `_open_one` devolve um objeto
    novo, e `_reapply_desired` é o único lugar onde o estado de quem já estava
    lá volta a ser pendurado.
    """
    novo = _handle_recem_nascido(radio=radio)
    ctl._handles = {key: novo}
    ctl._reapply_desired(key, novo)
    return novo


class TestOMudoSobreviveAoHandleNovo:
    def test_o_desmutar_dela_sobrevive_no_radio(self) -> None:
        """O caso da queixa: ela desmuta, o rádio cai e volta, e o mic segue vivo.

        Os DOIS asserts, e o primeiro é o que morde: sem o bit de autorização
        o `common[9] == 0` é o report de quem NÃO é dono — indistinguível do
        handle recém-nascido, que é o defeito.
        """
        ctl = _ctl_com(_handle_recem_nascido(radio=True))
        assert ctl.set_microphone_mute(False, uniq=KEY_1) is True

        novo = _reconectar(ctl, radio=True)
        report = novo.prepareReport()

        assert report[0] == rep.BT_REPORT_ID
        assert report[FLAG1_NO_RADIO] & rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE
        assert report[MUDO_NO_RADIO] == 0x00

    def test_o_mudo_dela_sobrevive_no_radio(self) -> None:
        """A outra ponta da mesma posse: mudo pedido continua mudo pedido."""
        ctl = _ctl_com(_handle_recem_nascido(radio=True))
        assert ctl.set_microphone_mute(True, uniq=KEY_1) is True

        novo = _reconectar(ctl, radio=True)
        report = novo.prepareReport()

        assert report[FLAG1_NO_RADIO] & rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE
        assert report[MUDO_NO_RADIO] == rep.POWER_SAVE_MIC_MUTE

    def test_no_cabo_o_mesmo_byte_sobrevive(self) -> None:
        """`cabo E rádio` é o ponto 4 dela, então o cabo tem régua própria —
        e o endereço é OUTRO (report[10], não report[12])."""
        ctl = _ctl_com(_handle_recem_nascido(radio=False))
        assert ctl.set_microphone_mute(False, uniq=KEY_1) is True

        novo = _reconectar(ctl, radio=False)
        report = novo.prepareReport()

        assert report[0] == rep.USB_REPORT_ID
        assert report[FLAG1_NO_CABO] & rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE
        assert report[MUDO_NO_CABO] == 0x00

    def test_sem_posse_o_handle_novo_devolve_o_campo_ao_kernel(self) -> None:
        """O contrário, e ele é requisito: quem nunca pediu não vira dono.

        Sem isto a cura seria o defeito do AUDIO-OWNER-01 de volta — mandar
        `common[9]=0x00` autorizado por cima da decisão do kernel.
        """
        ctl = _ctl_com(_handle_recem_nascido(radio=True))

        novo = _reconectar(ctl, radio=True)
        report = novo.prepareReport()

        assert not report[FLAG1_NO_RADIO] & rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE

    def test_devolver_a_posse_nao_rependura_nada(self) -> None:
        """`None` é a ORDEM *"devolvo ao kernel"* — e ela também tem de
        sobreviver à reconexão, senão a devolução dura até o próximo drop."""
        ctl = _ctl_com(_handle_recem_nascido(radio=True))
        ctl.set_microphone_mute(True, uniq=KEY_1)
        ctl.set_microphone_mute(None, uniq=KEY_1)

        novo = _reconectar(ctl, radio=True)
        report = novo.prepareReport()

        assert not report[FLAG1_NO_RADIO] & rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE
        assert report[MUDO_NO_RADIO] == 0x00

    def test_a_posse_nao_vaza_para_o_vizinho(self) -> None:
        """Posse por-uniq: o Controle 2 reconectando não herda o mudo do 1."""
        h1 = _handle_recem_nascido(radio=True)
        ctl = _ctl_com(h1)
        ctl._handles = {KEY_1: h1, KEY_2: _handle_recem_nascido(radio=True)}
        ctl.set_microphone_mute(True, uniq=KEY_1)

        novo2 = _handle_recem_nascido(radio=True)
        ctl._handles[KEY_2] = novo2
        ctl._reapply_desired(KEY_2, novo2)

        assert novo2._mic_mute_desejado is None
        assert not novo2.prepareReport()[FLAG1_NO_RADIO] & (
            rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE
        )


class TestAQuemPerguntar:
    def test_a_leitura_nao_mente_na_janela_pos_hotplug(self) -> None:
        """A fonte de verdade é o MAPA, não o atributo do handle.

        A janela existe de verdade: entre o handle novo entrar em `_handles` e
        o `_reapply_desired` correr, o atributo é `None`. Quem responde ali é
        `microphone_mute_for`, e ela alimenta o `state_full` e o rótulo da
        tela — dizer "o kernel é o dono" sobre um controle nosso é a tela
        mentindo para ela.
        """
        ctl = _ctl_com(_handle_recem_nascido(radio=True))
        ctl.set_microphone_mute(False, uniq=KEY_1)

        #: o hotplug trocou o handle e AINDA não reaplicou.
        ctl._handles = {KEY_1: _handle_recem_nascido(radio=True)}

        assert ctl.microphone_mute_for(KEY_1) is False
        assert ctl.microphone_mute_for(UNIQ_1) is False

    def test_a_escrita_que_falhou_nao_vira_posse(self) -> None:
        """Contrato do MIC-USB-01, e ele continua valendo: handle que estourou
        no meio da escrita não é posse — afirmar posse ali é o produto mentindo
        sobre uma ordem que nunca saiu."""
        handle = _handle_recem_nascido(radio=True)

        def _explode(_muted: bool | None) -> None:
            raise OSError("controle sumiu no meio da escrita")

        handle.set_microphone_mute = _explode
        ctl = _ctl_com(handle)

        assert ctl.set_microphone_mute(True, uniq=KEY_1) is False
        assert ctl.microphone_mute_for(KEY_1) is None
        assert ctl._mic_mute_by_uniq == {}


class TestOEnderecoDaPosse:
    def test_sem_doze_hex_nao_se_reivindica_nada(self) -> None:
        """A armadilha do pseudo-MAC, nomeada na sprint: `norm_mac` recolhe os
        dígitos hex de um CAMINHO (`/dev/hidraw4` → `deda4`), e sem a guarda de
        12 a posse iria parar no controle errado na próxima reconexão.

        O custo é honesto e está escrito: naquele controle o mudo continua
        sendo do kernel.
        """
        handle = _handle_recem_nascido(radio=True)
        ctl = _ctl_com(handle, key="/dev/hidraw4")

        assert ctl.set_microphone_mute(True) is True
        assert ctl._mic_mute_by_uniq == {}

        novo = _reconectar(ctl, radio=True, key="/dev/hidraw4")
        assert novo._mic_mute_desejado is None
