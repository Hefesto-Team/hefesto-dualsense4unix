"""O controle vibra no modo do firmware dele (O-CONTROLE-VIBRA-NO-MODO-DO-FIRMWARE-DELE-01).

O vpad se apresenta com a feature 0x20 canônica (`update_version` `0x0630`), então o
jogo, o kernel e o SDL falam com ele em vibração v2. O Hefesto repassava esses bytes
ao controle físico em v1 (`COMPATIBLE_VIBRATION`, flag0 bit 0), sem nunca perguntar a
versão do firmware do físico. Agora o backend lê a feature 0x20 na conexão e o
`_build_common` pede o modo que o firmware entende: v2 liga o `COMPATIBLE_VIBRATION2`
(flag2 bit 2) e tira o `COMPATIBLE_VIBRATION`; v1 e «sem leitura» ficam como sempre.

MORDE? Arranque o ramo `if self._vibracao_v2:` de `_build_common`, ou leia o limiar
como `0x0215`: as réguas de baixo reprovam (mordida de 13/10/2026 no relato da sprint).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as backend_mod
from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import (
    LIMITE_DA_VIBRACAO_V2,
    PyDualSenseController,
    _PinnedPyDualSense,
    fala_a_vibracao_v2,
    versao_do_firmware,
)

FLAG0_V1 = rep.VALID_FLAG0_COMPATIBLE_VIBRATION
FLAG2_V2 = rep.VALID_FLAG2_COMPATIBLE_VIBRATION2

FIXTURE_0X20 = (
    Path(__file__).resolve().parents[1] / "fixtures" / "hid"
    / "dualsense_usb_feature_0x20_firmware.bin"
)


def _feature_0x20(versao: int, *, bt: bool = False, corromper: bool = False) -> bytes:
    """64 bytes da feature 0x20 com o `update_version` (u16 LE) no byte 44."""
    corpo = bytearray(64)
    corpo[0] = 0x20
    corpo[44:46] = versao.to_bytes(2, "little")
    if bt:
        crc = rep.bt_crc32(bytes(corpo[:-4]), seed=rep.BT_FEATURE_CRC_SEED)
        corpo[-4:] = crc.to_bytes(4, "little")
        if corromper:
            corpo[10] ^= 0xFF
    return bytes(corpo)


def _handle(
    *, edge: bool = False, bt: bool = False, path: bytes = b"/dev/hidraw3"
) -> _PinnedPyDualSense:
    """Um handle da pydualsense com o suficiente para montar o `common`."""
    handle = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    handle.leftMotor = 200
    handle.rightMotor = 200
    handle._rumble_active = True
    handle._rumble_stop_pending = False
    handle._suppress_leds = False
    handle._volumes_audio = [None, None, None, None]
    handle._mic_mute_desejado = None
    handle._preamp_audio = None
    handle._raw_trigger_right = None
    handle._raw_trigger_left = None
    handle._pinned_path = path
    handle.is_edge = edge
    if bt:
        handle.conType = SimpleNamespace(name="BT")

    class _Valor:
        value = 0x00

    class _Luz:
        ledOption = _Valor()  # noqa: N815
        pulseOptions = _Valor()  # noqa: N815
        brightness = _Valor()
        playerNumber = _Valor()  # noqa: N815
        TouchpadColor = (0, 0, 0)

    class _Gatilho:
        mode = _Valor()
        forces = (0,) * 7

    class _Audio:
        microphone_led = 0
        microphone_mute = 0

    handle.light = _Luz()
    handle.audio = _Audio()
    handle.triggerR = _Gatilho()
    handle.triggerL = _Gatilho()
    return handle


def _backend(**handles: Any) -> PyDualSenseController:
    inst = PyDualSenseController.__new__(PyDualSenseController)
    PyDualSenseController.__init__(inst, evdev_reader=MagicMock())
    inst._handles = dict(handles)
    inst._primary_key = next(iter(handles), None)
    return inst


@pytest.fixture()
def hidraw(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Dubla a leitura da feature: um payload por path (ou uma exceção)."""
    estado: dict[str, Any] = {"pedidos": []}

    def _fake(path: str, report_id: int, size: int, opener: Any = None) -> bytes:
        estado["pedidos"].append((path, report_id, size))
        payload = estado[path]
        if isinstance(payload, Exception):
            raise payload
        return bytes(payload)

    monkeypatch.setattr(backend_mod, "_read_feature_via_hidraw", _fake)
    return estado


# --- o montador do report -------------------------------------------------


@pytest.mark.parametrize("transporte", ["cabo", "radio"])
def test_firmware_novo_pede_a_v2_e_tira_a_v1(transporte: str) -> None:
    handle = _handle(bt=transporte == "radio")
    handle.set_vibracao_v2(True)
    common = handle._build_common(rumble_asserted=True)

    assert common[rep.COMMON_VALID_FLAG2] & FLAG2_V2, "a v2 não saiu no flag2"
    assert not common[0] & FLAG0_V1, "a v1 saiu junto da v2"
    assert common[3] == 200 and common[2] == 200, "o byte do motor não saiu cheio"
    quadro = (
        rep.build_bt_report(common) if transporte == "radio" else rep.build_usb_report(common)
    )
    deslocamento = 3 if transporte == "radio" else 1
    assert quadro[deslocamento + rep.COMMON_VALID_FLAG2] & FLAG2_V2
    assert not quadro[deslocamento] & FLAG0_V1


@pytest.mark.parametrize("transporte", ["cabo", "radio"])
def test_firmware_antigo_fica_na_v1_de_sempre(transporte: str) -> None:
    handle = _handle(bt=transporte == "radio")
    handle.set_vibracao_v2(False)
    common = handle._build_common(rumble_asserted=True)

    assert common[0] & FLAG0_V1
    assert not common[rep.COMMON_VALID_FLAG2] & FLAG2_V2
    assert common[2] == 200 and common[3] == 200


def test_sem_leitura_o_handle_nasce_na_v1() -> None:
    handle = _handle()
    common = handle._build_common(rumble_asserted=True)

    assert common[0] & FLAG0_V1
    assert not common[rep.COMMON_VALID_FLAG2] & FLAG2_V2


@pytest.mark.parametrize("v2", [True, False])
def test_sem_rumble_nosso_nenhum_dos_dois_bits_sai(v2: bool) -> None:
    handle = _handle()
    handle._rumble_active = False
    handle.set_vibracao_v2(v2)
    common = handle._build_common(rumble_asserted=False)

    assert not common[0] & FLAG0_V1
    assert not common[rep.COMMON_VALID_FLAG2] & FLAG2_V2


@pytest.mark.parametrize("v2", [True, False])
def test_a_haptica_por_audio_com_motor_nao_leva_nenhum_bit_de_vibracao(v2: bool) -> None:
    """A vibração do jogo vai como áudio: o report não leva nenhum dos bits, v1 ou v2.

    A-VIBRACAO-DO-CABO-ACORDA-O-MOTOR-E-DEVOLVE-A-HAPTICA-01. MORDIDA: devolva o ramo
    `if self._vibracao_v2:` ao caso da háptica e o `flag2` leva o V2.
    """
    handle = _handle()
    handle.set_vibracao_v2(v2)
    handle.set_haptica_de_audio(True)
    common = handle._build_common(rumble_asserted=True)

    assert not common[0] & rep.VALID_FLAG0_HAPTICS_SELECT
    assert not common[0] & FLAG0_V1
    assert not common[rep.COMMON_VALID_FLAG2] & FLAG2_V2


@pytest.mark.parametrize("v2", [True, False])
def test_a_haptica_por_audio_com_o_motor_parado_leva_a_soltura(v2: bool) -> None:
    """Os motores a 0 com a háptica tocando: o report de soltura leva os bits (para o motor)."""
    handle = _handle()
    handle.leftMotor = handle.rightMotor = 0
    handle.set_vibracao_v2(v2)
    handle.set_haptica_de_audio(True)
    common = handle._build_common(rumble_asserted=True)

    assert bool(common[rep.COMMON_VALID_FLAG2] & FLAG2_V2) is v2
    assert bool(common[0] & FLAG0_V1) is (not v2)


@pytest.mark.parametrize("led_option", [0, 1, 2, 3])
def test_a_v1_de_hoje_e_byte_a_byte_a_mesma_nos_quatro_led_option(led_option: int) -> None:
    handle = _handle()
    handle.light.ledOption.value = led_option
    common = handle._build_common(rumble_asserted=True)

    brilho = rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE
    assert common[0] == 0xFF & ~rep.VALID_FLAG0_AUDIO_MASK
    assert common[rep.COMMON_VALID_FLAG2] == (led_option & ~brilho) | brilho


# --- o limiar -------------------------------------------------------------


@pytest.mark.parametrize(
    ("lido", "edge", "esperado"),
    [
        (0x0630, False, True),
        (0x0224, False, True),
        (0x0223, False, False),
        (0x0215, False, False),
        (None, False, False),
        (None, True, True),
        (0x0100, True, True),
    ],
)
def test_o_limiar_da_v2_e_o_do_sdl(lido: int | None, edge: bool, esperado: bool) -> None:
    assert LIMITE_DA_VIBRACAO_V2 == 0x0224
    assert fala_a_vibracao_v2(lido, edge=edge) is esperado


# --- o leitor da 0x20 -----------------------------------------------------


def test_a_feature_real_do_blueprint_diz_0x0630() -> None:
    assert versao_do_firmware(FIXTURE_0X20.read_bytes()) == 0x0630


def test_64_bytes_sinteticos_devolvem_a_versao() -> None:
    assert versao_do_firmware(_feature_0x20(0x0630)) == 0x0630
    assert _feature_0x20(0x0630)[44:46] == bytes([0x30, 0x06])
    assert versao_do_firmware(bytes(40)) is None
    assert versao_do_firmware(None) is None


def test_cabo_le_a_0x20_pelo_hidraw_do_controle(hidraw: dict[str, Any]) -> None:
    hidraw["/dev/hidraw3"] = _feature_0x20(0x0630)
    backend = _backend(aabbcc000001=_handle())

    assert backend.read_update_version("aabbcc000001") == 0x0630
    assert hidraw["pedidos"] == [("/dev/hidraw3", 0x20, 64)]


def test_radio_com_crc_errado_devolve_vazio(hidraw: dict[str, Any]) -> None:
    hidraw["/dev/hidraw3"] = _feature_0x20(0x0630, bt=True, corromper=True)
    backend = _backend(aabbcc000001=_handle(bt=True))

    assert backend.read_update_version("aabbcc000001") is None


def test_radio_com_crc_certo_devolve_a_versao(hidraw: dict[str, Any]) -> None:
    hidraw["/dev/hidraw3"] = _feature_0x20(0x0224, bt=True)
    backend = _backend(aabbcc000001=_handle(bt=True))

    assert backend.read_update_version("aabbcc000001") == 0x0224


def test_falha_de_leitura_devolve_vazio(hidraw: dict[str, Any]) -> None:
    hidraw["/dev/hidraw3"] = OSError(5, "Input/output error")
    backend = _backend(aabbcc000001=_handle())

    assert backend.read_update_version("aabbcc000001") is None


# --- a conexão: cada controle no modo do firmware dele ---------------------


def test_dois_controles_no_mesmo_backend_cada_um_na_versao_dele(
    hidraw: dict[str, Any],
) -> None:
    p1 = _handle(path=b"/dev/hidraw3")
    p2 = _handle(path=b"/dev/hidraw7", bt=True)
    backend = _backend(aabbcc000001=p1, aabbcc000002=p2)
    hidraw["/dev/hidraw3"] = _feature_0x20(0x0630)
    hidraw["/dev/hidraw7"] = _feature_0x20(0x0223, bt=True)

    backend._conhecer_o_firmware("aabbcc000001", p1)
    backend._conhecer_o_firmware("aabbcc000002", p2)

    c1 = p1._build_common(rumble_asserted=True)
    c2 = p2._build_common(rumble_asserted=True)
    assert c1[rep.COMMON_VALID_FLAG2] & FLAG2_V2 and not c1[0] & FLAG0_V1
    assert c2[0] & FLAG0_V1 and not c2[rep.COMMON_VALID_FLAG2] & FLAG2_V2
    assert backend._firmware_por_uniq == {"aabbcc000001": 0x0630, "aabbcc000002": 0x0223}


def test_leitura_que_falha_deixa_o_dualsense_comum_na_v1(hidraw: dict[str, Any]) -> None:
    handle = _handle()
    backend = _backend(aabbcc000001=handle)
    hidraw["/dev/hidraw3"] = OSError(5, "Input/output error")

    backend._conhecer_o_firmware("aabbcc000001", handle)

    assert handle._build_common(rumble_asserted=True)[0] & FLAG0_V1
    assert backend._firmware_por_uniq == {"aabbcc000001": None}


def test_o_edge_e_sempre_v2_mesmo_sem_leitura(hidraw: dict[str, Any]) -> None:
    handle = _handle(edge=True)
    backend = _backend(aabbcc000001=handle)
    hidraw["/dev/hidraw3"] = OSError(5, "Input/output error")

    backend._conhecer_o_firmware("aabbcc000001", handle)

    common = handle._build_common(rumble_asserted=True)
    assert common[rep.COMMON_VALID_FLAG2] & FLAG2_V2 and not common[0] & FLAG0_V1


def test_o_connect_le_o_firmware_de_todo_handle_novo(
    monkeypatch: pytest.MonkeyPatch, hidraw: dict[str, Any]
) -> None:
    """O gancho da conexão: o `connect` chama `_conhecer_o_firmware` do handle novo."""
    handle = _handle()
    backend = _backend()
    backend._handles = {}
    backend._primary_key = None
    hidraw["/dev/hidraw3"] = _feature_0x20(0x0630)
    visto: list[str] = []
    original = PyDualSenseController._conhecer_o_firmware

    def _espia(self: Any, key: str, h: Any) -> None:
        visto.append(key)
        original(self, key, h)

    monkeypatch.setattr(PyDualSenseController, "_conhecer_o_firmware", _espia)
    monkeypatch.setattr(
        backend, "_enumerate_device_keys", lambda: [("aabbcc000001", b"/dev/hidraw3", False)]
    )
    monkeypatch.setattr(backend, "_open_one", lambda path, *, is_edge: handle)
    for nome in (
        "_refresh_sysfs_leds",
        "assumir_volume_padrao_na_adocao",
        "_reapply_desired",
        "reassert_resolved_outputs",
    ):
        monkeypatch.setattr(backend, nome, lambda *a, **k: None)

    backend.connect()

    assert visto == ["aabbcc000001"]
    assert handle._vibracao_v2 is True


@pytest.mark.parametrize("bt", [False, True], ids=["cabo", "radio"])
def test_a_reconexao_que_nao_le_herda_o_firmware_ja_lido(
    hidraw: dict[str, Any], bt: bool
) -> None:
    """O firmware é do controle: o handle novo cuja leitura falha fica no modo já lido.

    A troca de nó e a reconexão recriam o handle; um CRC do rádio que não fecha
    nesse instante não devolve o controle à v1 que ele não fala.
    """
    primeiro = _handle(path=b"/dev/hidraw3", bt=bt)
    backend = _backend(aabbcc000001=primeiro)
    hidraw["/dev/hidraw3"] = _feature_0x20(0x0630, bt=bt)
    backend._conhecer_o_firmware("aabbcc000001", primeiro)

    segundo = _handle(path=b"/dev/hidraw9", bt=bt)
    backend._handles = {"aabbcc000001": segundo}
    hidraw["/dev/hidraw9"] = _feature_0x20(0x0630, bt=True, corromper=True) if bt else OSError(
        5, "Input/output error"
    )
    backend._conhecer_o_firmware("aabbcc000001", segundo)

    common = segundo._build_common(rumble_asserted=True)
    assert common[rep.COMMON_VALID_FLAG2] & FLAG2_V2 and not common[0] & FLAG0_V1
    assert backend._firmware_por_uniq == {"aabbcc000001": 0x0630}


def test_a_leitura_nova_vence_a_guardada(hidraw: dict[str, Any]) -> None:
    """Firmware atualizado entre duas conexões: vale o que o controle diz agora."""
    primeiro = _handle(path=b"/dev/hidraw3")
    backend = _backend(aabbcc000001=primeiro)
    hidraw["/dev/hidraw3"] = _feature_0x20(0x0630)
    backend._conhecer_o_firmware("aabbcc000001", primeiro)

    segundo = _handle(path=b"/dev/hidraw9")
    backend._handles = {"aabbcc000001": segundo}
    hidraw["/dev/hidraw9"] = _feature_0x20(0x0223)
    backend._conhecer_o_firmware("aabbcc000001", segundo)

    assert segundo._build_common(rumble_asserted=True)[0] & FLAG0_V1
    assert backend._firmware_por_uniq == {"aabbcc000001": 0x0223}
