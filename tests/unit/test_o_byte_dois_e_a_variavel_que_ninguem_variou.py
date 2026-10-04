"""O BYTE [2] DO DEGRAU — a variável que as seis passadas não variaram."""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.core.ds_output_report import (
    BT_CRC_SEED,
    BT_TAG,
    COMMON_LEN,
    bt_crc32,
    build_bt_report,
)
from hefesto_dualsense4unix.integrations import alto_falante_bt as af

COMMON = build_bt_report(bytes(range(COMMON_LEN)))[3 : 3 + COMMON_LEN]
QUADROS = [b"\xaa" * af.BYTES_POR_QUADRO_OPUS, b"\xbb" * af.BYTES_POR_QUADRO_OPUS]


def test_o_terceiro_corpo_traz_o_byte_dois_que_a_bancada_mediu() -> None:
    """`[2] = 0x10`, o mesmo do 0x31 que acendeu a lightbar por rádio."""
    pkt = af.montar_com_o_common_preservado(QUADROS, COMMON)
    assert pkt[2] == BT_TAG == 0x10, (
        f"o terceiro corpo saiu com [2]=0x{pkt[2]:02x}; o único valor que esta "
        "bancada viu o firmware aceitar é 0x10, e os dois arranjos já escrevem "
        "0x91 ali — sem variar este byte, a passada é a sétima repetição"
    )


def test_os_dois_arranjos_continuam_escrevendo_noventa_e_um_ali() -> None:
    """O *"sem"* do par, e ele NÃO é um defeito a curar — é o outro lado."""
    pacotes = {a.nome: a.montar(QUADROS) for a in af.ARRANJOS}
    assert set(pacotes) == {"ds5dongle", "senshi"}
    for nome, pkt in pacotes.items():
        assert pkt[2] == 0x91, (
            f"o arranjo {nome} deixou de escrever 0x91 em [2]; o *sem* do par "
            f"com/sem sumiu: 0x{pkt[2]:02x}"
        )


def test_o_common_de_quarenta_e_sete_bytes_sobrevive_em_tres_a_quarenta_e_nove() -> None:
    """Preservado quer dizer IDÊNTICO, e a régua compara os 47 bytes."""
    pkt = af.montar_com_o_common_preservado(QUADROS, COMMON)
    vindo = bytes(pkt[af.OFFSET_DO_COMMON : af.OFFSET_DO_COMMON + COMMON_LEN])
    assert vindo == COMMON, (
        "o `common` não chegou intacto em [3..49] — o envelope que a bancada "
        f"mediu foi desmontado: {vindo[:8].hex()} != {COMMON[:8].hex()}"
    )


def test_o_common_e_o_mesmo_que_o_produto_ja_manda_no_trinta_e_um() -> None:
    """O envelope é EMPRESTADO, não reconstruído — dono único."""
    trinta_e_um = build_bt_report(bytes(range(COMMON_LEN)))
    assert trinta_e_um[2] == BT_TAG
    pkt = af.montar_com_o_common_preservado(QUADROS, trinta_e_um[3 : 3 + COMMON_LEN])
    assert bytes(pkt[3:50]) == bytes(trinta_e_um[3:50]), (
        "o corpo do 0x39 não carrega o MESMO common do 0x31 do produto"
    )


def test_um_common_de_tamanho_errado_e_recusado() -> None:
    """Ausência é resposta: um envelope truncado não vira report silencioso."""
    with pytest.raises(ValueError, match="47"):
        af.montar_com_o_common_preservado(QUADROS, COMMON[:-1])


def test_o_opus_comeca_logo_depois_do_common() -> None:
    """[50] é a tag, [51] o `len`, e os quadros a partir de [52]."""
    pkt = af.montar_com_o_common_preservado(QUADROS, COMMON)
    assert af.OFFSET_APOS_O_COMMON == 50
    assert pkt[50] == af.tag_tlv(af.BLOCO_SPEAKER, duplo=True)
    assert pkt[51] == af.BYTES_POR_QUADRO_OPUS
    assert bytes(pkt[52:252]) == QUADROS[0]
    assert bytes(pkt[252:452]) == QUADROS[1]


def test_o_orcamento_do_degrau_e_respeitado_e_nao_estimado() -> None:
    """493 bytes livres no 0x39 — e o que não cabe é RECUSADO, não truncado."""
    assert af.orcamento_do_degrau(0x39) == 493
    cabem = [b"\x01" * af.BYTES_POR_QUADRO_OPUS] * 2
    assert len(af.montar_com_o_common_preservado(cabem, COMMON)) == 547
    with pytest.raises(ValueError, match="não cabem"):
        af.montar_com_o_common_preservado(
            [b"\x01" * af.BYTES_POR_QUADRO_OPUS] * 3, COMMON
        )


def test_o_crc_e_o_do_produto_e_fecha_sobre_o_corpo_inteiro() -> None:
    """A hipótese do CRC está REFUTADA, e esta régua guarda a refutação."""
    import zlib

    assert zlib.crc32(b"\xa2") == 0xEADA2D49
    pkt = af.montar_com_o_common_preservado(QUADROS, COMMON)
    esperado = bt_crc32(pkt[:-4], seed=BT_CRC_SEED).to_bytes(4, "little")
    assert bytes(pkt[-4:]) == esperado, "o CRC do terceiro corpo não fecha"


@pytest.mark.parametrize("tag", [0x13, 0x16])
def test_a_tag_do_bloco_continua_escolhivel(tag: int) -> None:
    """0x13 (alto-falante) e 0x16 (fone) — as duas que o ensaio já varreu."""
    pkt = af.montar_com_o_common_preservado(QUADROS, COMMON, tag_audio=tag)
    assert pkt[2] == BT_TAG, "variar a tag não pode mexer no byte [2]"
    assert pkt[af.OFFSET_APOS_O_COMMON] == af.tag_tlv(tag, duplo=True)


def test_a_sequencia_rotaciona_no_nibble_alto() -> None:
    """O nibble de sequência já estava tratado e não explica o silêncio."""
    for seq in (0, 1, 15, 16, 17):
        pkt = af.montar_com_o_common_preservado(QUADROS, COMMON, seq=seq)
        assert pkt[1] == (seq & 0x0F) << 4, f"seq={seq} saiu como 0x{pkt[1]:02x}"


#: O ``common`` no ``0x36`` da ponte: o bloco ``0x10`` em [11], os dados em [13].
_COMMON_NO_0X36 = slice(13, 13 + COMMON_LEN)


def _bomba(common: bytes | None) -> af.BombaDeSomPeloRadio:
    """A bomba da ponte, com um encoder de mentira. **Nasce SECA.**"""
    quadro = b"\xcc" * af.BYTES_POR_QUADRO_OPUS
    return af.BombaDeSomPeloRadio(
        fonte=lambda n: b"\x00" * n,
        codificador=type("Enc", (), {"codificar": lambda self, pcm: quadro})(),
        common=common,
    )


def test_o_corpo_que_a_bomba_monta_leva_o_common_do_produto() -> None:
    """O ``0x10`` do ``0x36`` da BOMBA leva o mesmo ``common`` do 0x31 do produto."""
    envelope = af.common_de_audio()
    report = _bomba(envelope).um_report()
    assert report is not None
    do_produto = bytes(build_bt_report(envelope)[3 : 3 + COMMON_LEN])
    assert report[11] == af.tag_tlv(BT_TAG), "o bloco 0x10 não está em [11]"
    assert bytes(report[_COMMON_NO_0X36]) == do_produto, (
        "o corpo que a BOMBA monta não leva o mesmo `common` que o 0x31 do "
        f"produto: {bytes(report[13:25]).hex()} != {do_produto[:12].hex()}"
    )


def test_a_bomba_sem_estado_manda_o_0x10_neutro() -> None:
    """Na bancada de 03/10 o ``0x10`` neutro bastou, e sem ele a háptica calou."""
    report = _bomba(None).um_report()
    assert report is not None
    assert report[11] == af.tag_tlv(BT_TAG), "o 0x10 saiu do quadro"
    assert bytes(report[13:76]) == bytes(63), "o neutro tem as validades zeradas"


def test_o_envelope_do_ensaio_pede_os_tres_campos_que_o_mapa_nomeia() -> None:
    """Rota, volume e pré-amp — os TRÊS, com os bits de validação ligados."""
    from hefesto_dualsense4unix.core import ds_output_report as rep

    envelope = af.common_de_audio()
    assert len(envelope) == COMMON_LEN
    assert envelope[0] & rep.VALID_FLAG0_SPEAKER_VOLUME, "o volume não foi autorizado"
    assert envelope[0] & rep.VALID_FLAG0_AUDIO_PATH, "a rota não foi autorizada"
    assert envelope[1] & rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE, "o pré-amp não foi"
    assert envelope[rep.COMMON_SPEAKER_VOLUME] == af.VOLUME_QUE_ELA_OUVIU
    rota = (
        envelope[rep.COMMON_AUDIO_PATH] & rep.OUTPUT_PATH_SEL_MASK
    ) >> rep.OUTPUT_PATH_SEL_SHIFT
    assert rota == rep.SAIDA_SO_NO_ALTO_FALANTE
    assert envelope[rep.COMMON_AUDIO_CONTROL2] & rep.SP_PREAMP_GAIN_MASK == (
        rep.SP_PREAMP_GAIN_PADRAO
    )


def test_o_envelope_nao_apaga_o_caminho_do_microfone() -> None:
    """A cicatriz de 02/08/2026: o `common[7]` carrega a rota E o mic."""
    from hefesto_dualsense4unix.core import ds_output_report as rep

    envelope = af.common_de_audio()
    assert envelope[rep.COMMON_AUDIO_PATH] & rep.AUDIO_CONTROL_FORCE_INTERNAL_MIC, (
        "o `common[7]` foi escrito com base zero e apagou o caminho do "
        f"microfone: 0x{envelope[rep.COMMON_AUDIO_PATH]:02x}"
    )


def test_os_arranjos_externos_continuam_sem_common() -> None:
    """A recusa é SÓ do corpo que preserva — os dois candidatos não mudam."""
    for arranjo in af.ARRANJOS:
        assert arranjo.common_preservado is False
