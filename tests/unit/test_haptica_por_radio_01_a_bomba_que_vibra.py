"""HAPTICA-POR-RADIO-01 (P4) — a bomba que leva a háptica ao fio, um escritor só.

O report destas réguas é o que VIBROU na mão dela em 18/09/2026: primeiro com
senoide (``scripts/ensaios/a_haptica_pelo_radio.py``), depois com o PCM do
PRAGMATA saindo do endpoint de quatro canais — *"se eu atirei x vezes vibrou x
vezes"*, 2161 reports, zero recusas.

**A régua que mais vale é a primeira:** ela compara byte a byte o que o produto
monta com os bytes medidos. Um produto que monte "quase" o report não vibra, e
"quase" é indistinguível de silêncio no fio.

Nenhuma régua daqui toca aparelho: a fonte é uma função e o escritor é uma
lista.
"""

from __future__ import annotations

import struct

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations.haptica_bt import ConversorDeHaptica

#: Os doze primeiros bytes do report que vibrou: id, seq<<4, a tag `0x91` com
#: `len` 7, os sete bytes do AudioControl (enables sem microfone, o
#: `audio_buffer_length` que tocou e o contador) e a tag `0x92` com `len` 64.
_CABECA_MEDIDA = bytes.fromhex("32 10 91 07 fe 00 00 00 00 ff 01 92 40".replace(" ", ""))


def _pcm(quadros: int, *, canal: int, amplitude: int = 20000) -> bytes:
    """PCM s16le de 4 canais com uma onda quadrada lenta num canal só."""
    dados = bytearray()
    for n in range(quadros):
        for c in range(4):
            v = amplitude if (c == canal and (n // 240) % 2 == 0) else 0
            dados += struct.pack("<h", v)
    return bytes(dados)


def _fonte_de(dados: bytes):
    """Uma fonte que entrega o que tem e depois seca (devolve b"")."""
    estado = {"i": 0}

    def ler(quantos: int) -> bytes:
        i = estado["i"]
        pedaco = dados[i : i + quantos]
        estado["i"] = i + len(pedaco)
        return pedaco

    return ler


def _escritor_para(escritas: list[bytes]):
    """O escritor devolve o NÚMERO DE BYTES, como o `os.write` do fio.

    Um dublê que devolve `None` é mais pobre que o produto, e a bomba levanta
    ao contá-lo — foi o que aconteceu ao escrever estas réguas.
    """

    def escrever(report: bytes) -> int:
        escritas.append(report)
        return len(report)

    return escrever


def _bomba(dados: bytes, **kw):
    escritas: list[bytes] = []
    bomba = af.BombaDeSomPeloRadio(
        arranjo=af.ARRANJO_HAPTICA_032,
        fonte=lambda _n: b"",
        fonte_haptica=_fonte_de(dados),
        escritor=_escritor_para(escritas),
        seco=False,
        **kw,
    )
    return bomba, escritas


# -- o report ------------------------------------------------------------------


def test_o_report_montado_e_o_que_vibrou_na_mao_dela() -> None:
    report = af.ARRANJO_HAPTICA_032.montar(
        [],
        seq=1,
        controle=af.controle_de_audio_035(contador_de_quadros=1),
        haptico=bytes(range(64)),
    )
    assert len(report) == 142, "o 0x32 tem 142 bytes com o CRC"
    assert report[:13] == _CABECA_MEDIDA
    assert report[13:77] == bytes(range(64)), "o bloco vai em [13..76]"
    assert report[77:-4] == bytes(142 - 77 - 4), "o resto fica zerado"


def test_o_crc_e_o_do_produto_e_fecha() -> None:
    report = af.ARRANJO_HAPTICA_032.montar(
        [], seq=3, controle=af.controle_de_audio_035(contador_de_quadros=9),
        haptico=bytes(64),
    )
    esperado = af.bt_crc32(report[:-4], seed=af.BT_CRC_SEED)
    assert report[-4:] == esperado.to_bytes(4, "little")


def test_sem_o_bloco_de_controle_nao_vibra_e_a_regua_sabe() -> None:
    """MEDIDO: sem o `0x91` antes do `0x92`, o motor não se mexe."""
    assert af.ARRANJO_HAPTICA_032.len_controle == 7
    report = af.ARRANJO_HAPTICA_032.montar(
        [], seq=0, controle=af.controle_de_audio_035(contador_de_quadros=1),
        haptico=bytes(64),
    )
    assert report[2] == 0x91, "a tag do AudioControl"
    assert report[11] == 0x92, "a tag do háptico, SIMPLES — não a dobrada 0xD2"


def test_o_bloco_haptico_e_o_simples_e_nao_o_dobrado() -> None:
    """As duas fontes externas descrevem o dobrado; o que vibrou foi o simples."""
    assert af.ARRANJO_HAPTICA_032.haptico_duplo is False
    assert af.ARRANJO_HAPTICA_032.len_haptico == 64


def test_o_arranjo_da_haptica_nao_escreve_no_byte_do_id() -> None:
    """Ele não leva áudio, e `pos_tag_audio=0` cairia em cima do id."""
    report = af.ARRANJO_HAPTICA_032.montar(
        [], seq=0, controle=af.controle_de_audio_035(contador_de_quadros=1),
        haptico=bytes(64),
    )
    assert report[0] == 0x32


# -- a bomba -------------------------------------------------------------------


def test_um_report_por_bloco_e_a_fonte_e_o_relogio() -> None:
    bomba, _ = _bomba(_pcm(512 * 3, canal=2))
    for _ in range(3):
        assert bomba.um_report() is not None
    assert bomba.um_report() is None, "a fonte secou: o laço para sem exceção"
    assert bomba.contagem.blocos_hapticos == 3


def test_o_pico_e_os_mudos_separam_o_jogo_quieto_da_ponte_morta() -> None:
    """"Não vibrou" tem duas causas, e os números têm de distingui-las."""
    bomba, _ = _bomba(_pcm(512 * 2, canal=2) + bytes(512 * 2 * 8))
    while bomba.um_report() is not None:
        pass
    assert bomba.contagem.blocos_hapticos == 4
    assert bomba.contagem.hapticos_mudos == 2, "os dois últimos são silêncio"
    assert bomba.contagem.pico_haptico > 60


def test_a_voz_do_jogo_nao_vai_para_os_motores() -> None:
    """Canais 1 e 2 são o alto-falante; mandá-los ao motor faria o controle
    tremer com a fala do jogo."""
    bomba, _ = _bomba(_pcm(512 * 2, canal=0) + _pcm(512 * 2, canal=1))
    while bomba.um_report() is not None:
        pass
    assert bomba.contagem.blocos_hapticos == 4
    assert bomba.contagem.hapticos_mudos == 4


def test_a_sequencia_anda_e_o_contador_de_quadros_tambem() -> None:
    """Sem o contador andando, o firmware perde a conta dos quadros.

    **Ele começa em ZERO, e isso é o caminho do som**, que tocou 70 s seguidos
    em 10/09: o contador é montado ANTES de o report ser somado. O ensaio que
    vibrou começava em 1, e o firmware aceitou os dois — o que importa é andar
    de um em um.
    """
    bomba, escritas = _bomba(_pcm(512 * 3, canal=3))
    while True:
        r = bomba.um_report()
        if r is None:
            break
        bomba.escrever(r)
    assert [e[1] >> 4 for e in escritas] == [0, 1, 2]
    assert [e[10] for e in escritas] == [0, 1, 2]


def test_o_microfone_e_perguntado_a_cada_report() -> None:
    """O bit 0 dos enables é o microfone, e o gesto dela muda no meio."""
    respostas = iter([True, False, True])
    bomba, escritas = _bomba(_pcm(512 * 3, canal=2), com_microfone=lambda: next(respostas))
    while True:
        r = bomba.um_report()
        if r is None:
            break
        bomba.escrever(r)
    assert [e[4] for e in escritas] == [af.ENABLES_COM_MIC, af.ENABLES_SEM_MIC,
                                        af.ENABLES_COM_MIC]


def test_seca_a_bomba_nao_escreve_um_byte() -> None:
    escritas: list[bytes] = []
    bomba = af.BombaDeSomPeloRadio(
        arranjo=af.ARRANJO_HAPTICA_032,
        fonte=lambda _n: b"",
        fonte_haptica=_fonte_de(_pcm(512, canal=2)),
        escritor=_escritor_para(escritas),
        seco=True,
    )
    assert bomba.escrever(bomba.um_report() or b"") is True
    assert escritas == []
    assert bomba.contagem.escritas_aceitas_pelo_kernel == 0


def test_sem_fonte_de_haptica_a_bomba_de_som_segue_como_antes() -> None:
    """A peça nova não pode mexer no caminho do alto-falante, que JÁ TOCA."""
    bomba = af.BombaDeSomPeloRadio(arranjo=af.ARRANJO_035, fonte=lambda _n: b"")
    assert bomba.fonte_haptica is None
    assert bomba.um_report() is None
    assert bomba.bytes_de_pcm_por_report == af.BYTES_DE_PCM_POR_QUADRO


def test_o_intervalo_e_o_medido_do_radio() -> None:
    bomba, _ = _bomba(b"")
    assert bomba.intervalo_de_envio_s == pytest.approx(512 / 48000)
    assert af.QUADROS_POR_BLOCO_HAPTICO * 2 * af.CANAIS_DA_HAPTICA == 4096


def test_o_conversor_e_preguicoso() -> None:
    """Uma bomba montada e nunca rodada não constrói nada."""
    bomba, _ = _bomba(_pcm(512, canal=2))
    assert bomba._conversor is None
    bomba.um_report()
    assert isinstance(bomba._conversor, ConversorDeHaptica)
