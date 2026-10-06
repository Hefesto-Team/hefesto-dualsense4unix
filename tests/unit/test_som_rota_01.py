"""SOM-ROTA-01 — a rota, o pré-amplificador e o canal do controle."""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import _byte_da_rota


class _Handle:
    """O mínimo de um handle: o que `set_audio_volumes` mexe."""

    def __init__(self) -> None:
        self._volumes_audio: list[int | None] = [None, None, None, None]
        self._preamp_audio: int | None = None


def _handle_com_rota(valor: int) -> _Handle:
    h = _Handle()
    h._volumes_audio[3] = valor
    return h


def test_o_preamp_tem_bit_proprio_e_offset_proprio() -> None:
    """O `audio_control2` mora longe dos outros quatro, e no OUTRO flag."""
    from hefesto_dualsense4unix.core import backend_pydualsense as bp

    assert rep.COMMON_AUDIO_CONTROL2 == 37
    assert rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE == 0x80

    fonte = __import__("inspect").getsource(bp._PinnedPyDualSense._build_common)
    assert "flag1 |= rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE" in fonte
    assert "flag0 |= rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE" not in fonte, (
        "o pré-amp é autorizado pelo flag1; no flag0 o firmware o ignora"
    )


def test_os_tetos_de_volume_nao_sao_todos_255() -> None:
    """O fone vai até `0x7F` e o microfone até `0x40`."""
    assert rep.TETO_HEADPHONE_VOLUME == 0x7F
    assert rep.TETO_MIC_VOLUME == 0x40
    assert rep.TETO_SPEAKER_VOLUME == 0xFF, "o alto-falante é o único que vai a 255"


def test_o_clamp_do_volume_respeita_o_teto_de_cada_campo() -> None:
    """E o clamp acontece na PORTA, não no fio."""
    from hefesto_dualsense4unix.core.backend_pydualsense import _AUDIO_TETOS

    assert _AUDIO_TETOS == (0x7F, 0xFF, 0x40, 0xFF)


def test_a_rota_omitida_nao_toma_a_posse_do_byte_do_microfone() -> None:
    """`common[7]` carrega DUAS coisas, e é por isso que o default é não tocar."""
    assert _byte_da_rota(_Handle(), None) is None


@pytest.mark.parametrize(
    "rota",
    [
        rep.SAIDA_ESTEREO_NO_FONE,
        rep.SAIDA_MONO_NO_FONE,
        rep.SAIDA_L_FONE_R_ALTO_FALANTE,
        rep.SAIDA_SO_NO_ALTO_FALANTE,
    ],
)
def test_a_rota_entra_nos_bits_4_e_5(rota: int) -> None:
    """Os quatro valores do `OUTPUT_PATH_SEL`, no lugar certo do byte."""
    novo = _byte_da_rota(_Handle(), rota)

    assert novo is not None
    assert (novo & rep.OUTPUT_PATH_SEL_MASK) >> rep.OUTPUT_PATH_SEL_SHIFT == rota


def test_trocar_a_rota_preserva_o_caminho_do_microfone() -> None:
    """A parte mais fácil de errar da sprint, e a mais silenciosa."""
    mic_configurado = 0b0000_1001
    handle = _handle_com_rota(mic_configurado)

    novo = _byte_da_rota(handle, rep.SAIDA_L_FONE_R_ALTO_FALANTE)

    assert novo is not None
    assert novo & ~rep.OUTPUT_PATH_SEL_MASK == mic_configurado, (
        "os bits do microfone têm de sobreviver à troca de rota"
    )
    assert (novo & rep.OUTPUT_PATH_SEL_MASK) >> rep.OUTPUT_PATH_SEL_SHIFT == 2


def test_a_rota_substitui_a_anterior_em_vez_de_somar() -> None:
    """E trocar de rota não acumula bits — 3 depois de 1 é 3, não 3|1."""
    handle = _handle_com_rota(
        rep.SAIDA_SO_NO_ALTO_FALANTE << rep.OUTPUT_PATH_SEL_SHIFT
    )
    novo = _byte_da_rota(handle, rep.SAIDA_MONO_NO_FONE)
    assert novo is not None
    assert (novo & rep.OUTPUT_PATH_SEL_MASK) >> rep.OUTPUT_PATH_SEL_SHIFT == 1


def test_o_preamp_sem_dono_sai_zerado_e_sem_autorizacao(monkeypatch: Any) -> None:
    """Autorizar um byte sem escrevê-lo é mandar ZERO — a 60 Hz."""
    from hefesto_dualsense4unix.core import backend_pydualsense as bp

    fonte = __import__("inspect").getsource(bp._PinnedPyDualSense._build_common)

    assert "if preamp is None:" in fonte
    assert "flag1 &= ~rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE" in fonte, (
        "sem dono, o bit de autorização do pré-amp tem de sair APAGADO"
    )


def test_a_devolucao_da_posse_leva_o_preamp_junto() -> None:
    """"Devolver" não pode devolver metade."""
    from hefesto_dualsense4unix.core import backend_pydualsense as bp

    fonte = __import__("inspect").getsource(
        bp._PinnedPyDualSense.release_audio_volumes
    )
    assert "self._preamp_audio = None" in fonte


def test_a_rota_preserva_o_microfone_quando_assume_o_byte_do_zero() -> None:
    """A REGRESSÃO de 02/08/2026, medida na bancada e curada no mesmo dia."""
    novo = _byte_da_rota(_Handle(), rep.SAIDA_SO_NO_ALTO_FALANTE)

    assert novo is not None
    assert novo & rep.AUDIO_CONTROL_FORCE_INTERNAL_MIC, (
        "sem o FORCE_INTERNAL_MIC na base, a primeira escrita da rota mata o "
        "microfone do controle — medido"
    )
    assert (novo & rep.OUTPUT_PATH_SEL_MASK) >> rep.OUTPUT_PATH_SEL_SHIFT == 3


def _backend_com_um_handle() -> tuple[Any, Any]:
    """`PyDualSenseController` real com um handle mínimo e sem hardware.

    Real de propósito: o que se afere aqui é a leitura que sobe ao daemon, e um
    dublê de backend provaria apenas que a chave foi digitada.
    """
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

    reader = EvdevReader(device_path=None)
    reader._device_path = None
    inst = PyDualSenseController(evdev_reader=reader)
    handle = _Handle()
    inst._handles = {"AA:BB:CC:00:00:01": handle}
    inst._primary_key = "AA:BB:CC:00:00:01"
    return inst, handle


def test_sem_posse_do_byte_a_chave_da_rota_nem_existe() -> None:
    """Ausência é resposta — a mesma regra do volume não ajustado."""
    inst, handle = _backend_com_um_handle()
    handle._volumes_audio = [180, 180, None, None]
    handle._speaker_volume_pref = 180

    estado = inst.speaker_state_for()

    assert estado is not None
    assert estado["volume"] == 180
    assert "rota" not in estado


@pytest.mark.parametrize(
    "rota",
    [
        rep.SAIDA_ESTEREO_NO_FONE,
        rep.SAIDA_MONO_NO_FONE,
        rep.SAIDA_L_FONE_R_ALTO_FALANTE,
        rep.SAIDA_SO_NO_ALTO_FALANTE,
    ],
)
def test_o_canal_em_vigor_sobe_ao_daemon(rota: int) -> None:
    """Os quatro valores voltam pela leitura, e só os bits 4-5 são lidos."""
    inst, handle = _backend_com_um_handle()
    handle._volumes_audio = [180, 180, None, _byte_da_rota(_Handle(), rota)]
    handle._speaker_volume_pref = 180

    estado = inst.speaker_state_for()

    assert estado is not None
    assert estado["rota"] == rota


def test_a_leitura_ignora_o_meio_byte_do_microfone() -> None:
    """Só os bits 4-5 são canal — o resto é o caminho do mic, e não é lido."""
    inst, handle = _backend_com_um_handle()
    byte = rep.AUDIO_CONTROL_FORCE_INTERNAL_MIC | (
        rep.SAIDA_SO_NO_ALTO_FALANTE << rep.OUTPUT_PATH_SEL_SHIFT
    )
    handle._volumes_audio = [180, 180, None, byte]
    handle._speaker_volume_pref = 180

    estado = inst.speaker_state_for()

    assert estado is not None
    assert estado["rota"] == rep.SAIDA_SO_NO_ALTO_FALANTE
