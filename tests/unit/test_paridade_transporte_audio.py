"""PARIDADE-BYTE-01 — volume do alto-falante e pré-amp, no cabo e no rádio."""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep

from tests.conftest import EnvelopeDeTransporte

VOLUMES = [0x00, 0x40, 0xC0, rep.TETO_SPEAKER_VOLUME]


@pytest.mark.parametrize("volume", VOLUMES)
def test_o_volume_do_alto_falante_sai_no_byte_certo_nos_dois(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte, volume: int
) -> None:
    """common[5] leva o volume e o flag0 0x20 é quem o autoriza."""
    ds5_de_bancada.set_audio_volumes(speaker=volume)

    report = ds5_de_bancada.prepareReport()
    assert transporte.problemas_do_envelope(report) == []
    common = transporte.extrair_common(report)

    assert common[rep.COMMON_SPEAKER_VOLUME] == volume, (
        f"{transporte.nome}: o volume saiu {common[rep.COMMON_SPEAKER_VOLUME]} "
        f"em common[5], esperado {volume}"
    )
    assert common[0] & rep.VALID_FLAG0_SPEAKER_VOLUME, (
        f"{transporte.nome}: o volume foi escrito sem o bit 0x20 do flag0 — o "
        "firmware ignora byte cujo bit de validação está apagado"
    )


def test_o_preamp_sai_no_byte_certo_nos_dois(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
) -> None:
    """SOM-ROTA-01: sem o common[37] o deslizante dela vale 40% do curso."""
    ds5_de_bancada.set_audio_volumes(speaker=0xC0, preamp=rep.SP_PREAMP_GAIN_PADRAO)
    common = transporte.extrair_common(ds5_de_bancada.prepareReport())

    assert common[rep.COMMON_AUDIO_CONTROL2] & rep.SP_PREAMP_GAIN_MASK == (
        rep.SP_PREAMP_GAIN_PADRAO
    ), f"{transporte.nome}: o ganho do pré-amp não chegou em common[37]"
    assert common[1] & rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE, (
        f"{transporte.nome}: o pré-amp saiu sem o bit 0x80 do flag1"
    )


def test_a_posse_do_audio_e_por_byte_nos_dois(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
) -> None:
    """Quem pede só o alto-falante autoriza SÓ o alto-falante — nos dois."""
    ds5_de_bancada.set_audio_volumes(speaker=0xC0)
    common = transporte.extrair_common(ds5_de_bancada.prepareReport())

    assert common[0] & rep.VALID_FLAG0_SPEAKER_VOLUME
    assert common[0] & rep.VALID_FLAG0_HEADPHONE_VOLUME == 0
    assert common[0] & rep.VALID_FLAG0_MIC_VOLUME == 0
    assert common[0] & rep.VALID_FLAG0_AUDIO_PATH == 0
    assert common[rep.COMMON_AUDIO_PATH] == 0


def test_sem_dono_o_audio_nao_sai_em_nenhum_dos_dois(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
) -> None:
    """AUDIO-OWNER-01 nos dois transportes: sem posse, nem bit nem valor."""
    common = transporte.extrair_common(ds5_de_bancada.prepareReport())
    assert common[0] & rep.VALID_FLAG0_AUDIO_MASK == 0, (
        f"{transporte.nome}: autorizamos áudio sem ter escrito valor nenhum — "
        "é 'volume zero' a 60 Hz com cara de keepalive"
    )
    assert list(common[4:8]) == [0, 0, 0, 0]
    assert common[1] & rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE == 0
    assert common[rep.COMMON_AUDIO_CONTROL2] == 0


def test_o_common_do_audio_e_identico_e_so_o_envelope_muda(
    transportes: tuple[EnvelopeDeTransporte, ...], fabrica_de_bancada: Any
) -> None:
    """As duas metades da frase do BTREPORT-02, provadas de uma vez."""
    commons: dict[str, bytes] = {}
    reports: dict[str, bytes] = {}
    for envelope in transportes:
        handle = fabrica_de_bancada(envelope)
        handle.set_audio_volumes(speaker=0xC0, preamp=rep.SP_PREAMP_GAIN_PADRAO)
        report = bytes(handle.prepareReport())
        reports[envelope.nome] = report
        commons[envelope.nome] = envelope.extrair_common(report)

    assert commons["usb"] == commons["bt"], (
        "o payload de 47 bytes divergiu entre cabo e rádio — o áudio deixou de "
        "ser a mesma feature nos dois transportes"
    )

    usb = next(t for t in transportes if t.nome == "usb")
    bt = next(t for t in transportes if t.nome == "bt")
    assert len(reports["usb"]) != len(reports["bt"])
    assert reports["usb"][0] != reports["bt"][0]
    assert usb.tag is None and bt.tag == rep.BT_TAG
    assert usb.sequencia_de(reports["usb"]) is None
    assert bt.sequencia_de(reports["bt"]) == 0
    assert usb.crc_do_report(reports["usb"]) is None
    assert bt.crc_do_report(reports["bt"]) == bt.crc_esperado(reports["bt"])
