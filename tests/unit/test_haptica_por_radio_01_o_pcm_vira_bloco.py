"""HAPTICA-POR-RADIO-01 (P2) — o PCM de 48 kHz vira bloco de 64 B a 3 kHz."""

from __future__ import annotations

import math
import struct

import pytest

from hefesto_dualsense4unix.integrations import haptica_bt as hb


def _pcm(quadros: int, *, canal: int, frequencia: float = 200.0, amplitude: int = 32767,
         canais: int = 4) -> bytes:
    """PCM s16le entrelaçado com a senoide num canal só, o resto em silêncio."""
    dados = bytearray()
    for n in range(quadros):
        for c in range(canais):
            v = 0
            if c == canal:
                v = round(amplitude * math.sin(2 * math.pi * frequencia * n / hb.TAXA_DE_ENTRADA))
            dados += struct.pack("<h", max(-32768, min(32767, v)))
    return bytes(dados)


def _int8(bloco: bytes) -> list[int]:
    return [b - 256 if b > 127 else b for b in bloco]


def test_o_bloco_tem_sessenta_e_quatro_bytes_e_trinta_e_duas_amostras() -> None:
    c = hb.ConversorDeHaptica()
    blocos = c.alimentar(_pcm(512, canal=2))
    assert len(blocos) == 1
    assert len(blocos[0]) == hb.BYTES_DO_BLOCO == 64
    assert hb.FATOR == 16


def test_o_silencio_nao_mexe_os_motores() -> None:
    c = hb.ConversorDeHaptica()
    blocos = c.alimentar(bytes(512 * 2 * 4))
    assert blocos == [hb.bloco_de_silencio()]


def test_so_os_canais_tres_e_quatro_entram() -> None:
    """O alto-falante do controle não pode virar vibração."""
    c = hb.ConversorDeHaptica()
    for canal_do_som in (0, 1):
        c.limpar()
        blocos = c.alimentar(_pcm(512, canal=canal_do_som))
        assert blocos == [hb.bloco_de_silencio()], f"o canal {canal_do_som + 1} vazou"


def test_a_senoide_dos_motores_sai_com_amplitude() -> None:
    c = hb.ConversorDeHaptica()
    blocos = c.alimentar(_pcm(512 * 4, canal=2, frequencia=200.0))
    amostras = [v for bloco in blocos for v in _int8(bloco)[0::2]]
    assert max(amostras) > 100, amostras
    assert min(amostras) < -100, amostras


def test_o_pico_nao_estoura_para_o_outro_lado() -> None:
    """`-128` é o valor que vira `+` quando alguém soma sem olhar: o piso é -127."""
    c = hb.ConversorDeHaptica(ganho=4.0)
    blocos = c.alimentar(_pcm(512 * 2, canal=2, frequencia=100.0))
    amostras = [v for bloco in blocos for v in _int8(bloco)]
    assert max(amostras) == 127
    assert min(amostras) == -127


def test_o_filtro_derruba_o_que_dobraria_em_cima_do_sinal() -> None:
    """3,3 kHz está acima do Nyquist de 1,5 kHz e volta como 300 Hz sem o filtro."""
    c = hb.ConversorDeHaptica()
    blocos = c.alimentar(_pcm(512 * 4, canal=2, frequencia=3300.0))
    amostras = [v for bloco in blocos for v in _int8(bloco)]
    assert max(abs(v) for v in amostras) < 30, max(amostras)


def test_o_resto_fica_guardado_entre_as_entregas() -> None:
    """O jogo não entrega múltiplos de 512 quadros — picotar é ruído no motor."""
    pcm = _pcm(512, canal=2)
    inteiro = hb.ConversorDeHaptica().alimentar(pcm)
    aos_pedacos: list[bytes] = []
    c = hb.ConversorDeHaptica()
    passo = 7 * 2 * 4
    for i in range(0, len(pcm), passo):
        aos_pedacos += c.alimentar(pcm[i : i + passo])
    assert aos_pedacos == inteiro


def test_limpar_esquece_o_resto() -> None:
    c = hb.ConversorDeHaptica()
    c.alimentar(_pcm(500, canal=2))
    c.limpar()
    assert c.alimentar(bytes(512 * 2 * 4)) == [hb.bloco_de_silencio()]


def test_os_dois_motores_saem_entrelacados() -> None:
    c = hb.ConversorDeHaptica()
    blocos = c.alimentar(_pcm(512, canal=3, frequencia=200.0))
    valores = _int8(blocos[0])
    assert all(v == 0 for v in valores[0::2]), "o canal 3 recebeu o que era do 4"
    assert any(v != 0 for v in valores[1::2]), "o canal 4 não chegou ao segundo motor"


def test_a_taxa_e_a_cadencia_do_radio() -> None:
    """32 amostras a 3 kHz são os 10,667 ms do quadro que o firmware consome."""
    assert pytest.approx(512 / 48000) == hb.AMOSTRAS_POR_CANAL / hb.TAXA_DO_BLOCO
    assert hb.CANAIS_DOS_MOTORES == (2, 3)
    assert hb.CANAIS_DE_ENTRADA == 4
