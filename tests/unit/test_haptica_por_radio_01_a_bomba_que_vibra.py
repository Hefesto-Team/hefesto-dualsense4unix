"""HAPTICA-POR-RADIO-01 (P4) — a bomba que leva a háptica ao fio, um escritor só."""

from __future__ import annotations

import struct

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations.haptica_bt import ConversorDeHaptica

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
    """O escritor devolve o NÚMERO DE BYTES, como o `os.write` do fio."""

    def escrever(report: bytes) -> int:
        escritas.append(report)
        return len(report)

    return escrever


def _bomba(dados: bytes, **kw):
    escritas: list[bytes] = []
    bomba = af.BombaDeSomPeloRadio(
        fonte=bytes,
        fonte_haptica=_fonte_de(dados),
        escritor=_escritor_para(escritas),
        seco=False,
        **kw,
    )
    return bomba, escritas


def _so_a_haptica(bloco: bytes, *, contador: int = 1, seq: int = 1) -> bytes:
    """O ``0x36`` que a bomba monta num quadro sem som: ``0x11``, ``0x10`` e ``0x12``."""
    return af.montar_relatorio_combinado(
        seq=seq,
        controle=af.controle_de_audio_035(contador_de_quadros=contador),
        common=bytes(af.COMMON_LEN),
        haptico=bloco,
    )


def test_o_report_da_haptica_e_o_0x36_que_vibrou_na_mao_dela() -> None:
    """A bancada de 03/10 (trecho 2): só a háptica, com o ``0x10`` neutro, vibrou."""
    report = _so_a_haptica(bytes(range(64)))
    assert len(report) == af.TAMANHO_DO_DEGRAU[0x36]
    assert report[:2] == bytes((0x36, 0x10))
    assert report[2:11] == _CABECA_MEDIDA[2:11], "o 0x11 é o mesmo que vibrou no 0x32"
    assert report[11:13] == bytes((0x90, 63)), "o 0x10 vai em todo quadro"
    assert report[76:78] == bytes((0x92, 0x40)), "a háptica, SIMPLES — não a dobrada 0xD2"
    assert report[78:142] == bytes(range(64)), "o bloco vai em [78..141]"
    assert report[142:-4] == bytes(len(report) - 142 - 4), "sem som, o resto fica zerado"


def test_o_crc_e_o_do_produto_e_fecha() -> None:
    report = _so_a_haptica(bytes(64), contador=9, seq=3)
    esperado = af.bt_crc32(report[:-4], seed=af.BT_CRC_SEED)
    assert report[-4:] == esperado.to_bytes(4, "little")


def test_sem_o_0x10_a_bomba_nao_monta() -> None:
    """MEDIDO em 03/10 (trecho 8): sem o ``0x10`` a háptica cala. A bomba sempre o manda."""
    bomba, _ = _bomba(_pcm(512, canal=2))
    report = bomba.um_report() or b""
    assert report[11] == 0x90, "a bomba montou o quadro sem o 0x10"
    assert report[76] == 0x92


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
    """Canais 1 e 2 são o alto-falante; mandá-los ao motor faria o controle"""
    bomba, _ = _bomba(_pcm(512 * 2, canal=0) + _pcm(512 * 2, canal=1))
    while bomba.um_report() is not None:
        pass
    assert bomba.contagem.blocos_hapticos == 4
    assert bomba.contagem.hapticos_mudos == 4


def test_a_sequencia_anda_e_o_contador_de_quadros_tambem() -> None:
    """Sem o contador andando, o firmware perde a conta dos quadros."""
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
        fonte=bytes,
        fonte_haptica=_fonte_de(_pcm(512, canal=2)),
        escritor=_escritor_para(escritas),
        seco=True,
    )
    assert bomba.escrever(bomba.um_report() or b"") is True
    assert escritas == []
    assert bomba.contagem.escritas_aceitas_pelo_kernel == 0


def test_sem_fonte_de_haptica_a_bomba_de_som_segue_como_antes() -> None:
    """A peça nova não pode mexer no caminho do alto-falante, que JÁ TOCA."""
    bomba = af.BombaDeSomPeloRadio(fonte=lambda _n: b"")
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
