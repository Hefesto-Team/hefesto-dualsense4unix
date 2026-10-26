"""O pacote DSU que o Azahar aceita, montado e lido sem socket (E2 do servidor DSU).

O que os testes cobram é a forma do pacote, byte a byte, contra o que o cliente
do emulador monta e confere: tamanhos 22, 32 e 100; CRC do zlib com os bytes
8..11 zerados; pedido malformado que não derruba nada.
"""

from __future__ import annotations

import re
import struct
import zlib
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import protocolo_dsu as p

CLIENTE = 24872
MAC_FORJADO = "02:fe:00:7a:19:c3"


def _pedido(tipo: int, corpo: bytes, *, client_id: int = CLIENTE) -> bytes:
    pacote = bytearray(p.MAGIC_DO_CLIENTE)
    pacote += struct.pack("<HHII", 1001, 4 + len(corpo), 0, client_id)
    pacote += struct.pack("<I", tipo) + corpo
    struct.pack_into("<I", pacote, 8, zlib.crc32(bytes(pacote)) & 0xFFFFFFFF)
    return bytes(pacote)


def _hex(b: bytes) -> str:
    return " ".join(f"{x:02x}" for x in b)


PEDIDO_DE_PORTAS_DO_AZAHAR = _pedido(p.TIPO_PORTAS, struct.pack("<i", 1) + b"\x00\x00\x00\x00")
PEDIDO_DE_DADOS_DO_AZAHAR = _pedido(p.TIPO_DADOS, bytes([1, 0]) + b"\x00" * 6)


def test_os_vetores_do_pad_0_batem_byte_a_byte() -> None:
    assert _hex(PEDIDO_DE_PORTAS_DO_AZAHAR) == (
        "44 53 55 43 e9 03 0c 00 c7 5b 8e 33 28 61 00 00 01 00 10 00 01 00 00 00 00 00 00 00"
    )
    assert _hex(PEDIDO_DE_DADOS_DO_AZAHAR) == (
        "44 53 55 43 e9 03 0c 00 37 89 10 44 28 61 00 00 02 00 10 00 01 00 00 00 00 00 00 00"
    )


def test_os_tres_tamanhos_e_o_campo_de_comprimento() -> None:
    versao = p.montar_versao(7)
    porta = p.montar_porta(7, slot=0)
    dados = p.montar_dados(7, slot=0, mac=MAC_FORJADO, contador=1, timestamp_us=1)
    assert (len(versao), len(porta), len(dados)) == (22, 32, 100)
    for pacote, campo in ((versao, 6), (porta, 16), (dados, 84)):
        assert pacote[0:4] == b"DSUS"
        assert struct.unpack_from("<HH", pacote, 4) == (1001, campo)


def test_o_crc_e_o_do_zlib_com_os_bytes_8_a_11_zerados() -> None:
    for pacote in (
        p.montar_versao(1),
        p.montar_porta(1, slot=2, estado=2, mac=MAC_FORJADO),
        p.montar_dados(1, slot=1, mac=MAC_FORJADO, contador=9, timestamp_us=123456),
    ):
        zerado = pacote[:8] + b"\x00\x00\x00\x00" + pacote[12:]
        assert struct.unpack_from("<I", pacote, 8)[0] == zlib.crc32(zerado) & 0xFFFFFFFF
        assert p.crc_do_pacote(pacote) == zlib.crc32(zerado) & 0xFFFFFFFF


def test_o_pedido_do_azahar_vira_portas_1_0_e_dados_flag_1_slot_0() -> None:
    portas = p.interpretar_pedido(PEDIDO_DE_PORTAS_DO_AZAHAR)
    dados = p.interpretar_pedido(PEDIDO_DE_DADOS_DO_AZAHAR)
    assert portas == p.PedidoDePortas(CLIENTE, (0,))
    assert dados == p.PedidoDeDados(CLIENTE, 1, 0, b"\x00" * 6)
    assert isinstance(dados, p.PedidoDeDados) and dados.por_slot and not dados.por_mac
    assert p.interpretar_pedido(_pedido(p.TIPO_VERSAO, b"")) == p.PedidoDeVersao(CLIENTE)


def test_pedido_de_portas_de_25_bytes_vale_o_mesmo() -> None:
    curto = _pedido(p.TIPO_PORTAS, struct.pack("<i", 1) + b"\x00")
    assert len(curto) == 25
    assert p.interpretar_pedido(curto) == p.PedidoDePortas(CLIENTE, (0,))


def test_o_excesso_do_datagrama_e_truncado() -> None:
    assert p.interpretar_pedido(PEDIDO_DE_PORTAS_DO_AZAHAR + b"\xff\xff") == p.PedidoDePortas(
        CLIENTE, (0,)
    )


def _mutacoes_da_saida(pacote: bytes) -> dict[str, bytes]:
    def refeito(b: bytearray) -> bytes:
        return bytes(b)

    crc = bytearray(pacote)
    crc[8] ^= 0x01
    comprimento = bytearray(pacote)
    comprimento[6] += 1
    versao = bytearray(pacote)
    struct.pack_into("<H", versao, 4, 1000)
    tipo = bytearray(pacote)
    struct.pack_into("<I", tipo, 16, 0x110001)
    return {
        "bit do CRC": refeito(crc),
        "comprimento +1": refeito(comprimento),
        "versão 1000": refeito(versao),
        "tipo 0x110001": refeito(tipo),
        "um byte a mais": pacote + b"\x00",
    }


@pytest.mark.parametrize(
    ("pacote", "tipo"),
    [
        (p.montar_versao(5), p.TIPO_VERSAO),
        (p.montar_porta(5, slot=3, estado=2, modelo=2, conexao=1, mac=MAC_FORJADO), p.TIPO_PORTAS),
        (
            p.montar_dados(
                5,
                slot=0,
                mac=MAC_FORJADO,
                contador=3,
                timestamp_us=4,
                toques=(p.Toque(True, 9, 1919, 1079), p.TOQUE_INATIVO),
                aceleracao=(0.0, 1.0, 0.0),
                giro=(1.5, -2.5, 0.25),
            ),
            p.TIPO_DADOS,
        ),
    ],
)
def test_o_validador_da_saida_aceita_cada_tipo_e_recusa_cada_mutacao(
    pacote: bytes, tipo: int
) -> None:
    assert p.validar_saida(pacote) == tipo
    for nome, mutado in _mutacoes_da_saida(pacote).items():
        assert p.validar_saida(mutado) is None, nome


def test_o_conteudo_dos_dados_esta_nos_offsets_do_protocolo() -> None:
    d = p.montar_dados(
        5,
        slot=2,
        mac=MAC_FORJADO,
        contador=0xAABBCCDD,
        timestamp_us=0x1122334455667788,
        toques=(p.Toque(True, 7, 1919, 1079), p.Toque(True, 8, 3, 4)),
        aceleracao=(1.0, 2.0, 3.0),
        giro=(4.0, 5.0, 6.0),
    )
    assert d[20:24] == bytes([2, 2, 2, 1])
    assert d[24:30] == bytes.fromhex("02fe007a19c3")
    assert d[31] == 1
    assert struct.unpack_from("<I", d, 32)[0] == 0xAABBCCDD
    assert d[40:44] == bytes([128] * 4)
    assert d[56:62] == bytes([1, 7]) + struct.pack("<HH", 1919, 1079)
    assert d[62:68] == bytes([1, 8]) + struct.pack("<HH", 3, 4)
    assert struct.unpack_from("<Q", d, 68)[0] == 0x1122334455667788
    assert struct.unpack_from("<fff", d, 76) == (1.0, 2.0, 3.0)
    assert struct.unpack_from("<fff", d, 88) == (4.0, 5.0, 6.0)


def test_slot_vazio_leva_o_numero_e_zeros() -> None:
    porta = p.montar_porta(1, slot=2)
    assert porta[20] == 2
    assert porta[21:31] == b"\x00" * 10 and porta[31] == 0


def _com_comprimento(pacote: bytes, comprimento: int) -> bytes:
    b = bytearray(pacote)
    struct.pack_into("<H", b, 6, comprimento)
    struct.pack_into("<I", b, 8, p.crc_do_pacote(bytes(b)))
    return bytes(b)


def test_pedido_malformado_da_none_sem_excecao() -> None:
    casos = {
        "quantidade 5": _pedido(p.TIPO_PORTAS, struct.pack("<i", 5) + b"\x00" * 5),
        "quantidade 0": _pedido(p.TIPO_PORTAS, struct.pack("<i", 0)),
        "quantidade negativa": _pedido(p.TIPO_PORTAS, struct.pack("<i", -1) + b"\x00"),
        "slot 4": _pedido(p.TIPO_PORTAS, struct.pack("<i", 1) + b"\x04"),
        "slot faltando": _pedido(p.TIPO_PORTAS, struct.pack("<i", 2) + b"\x00"),
        "dados curto": _pedido(p.TIPO_DADOS, b"\x01\x00"),
        "dados longo": _pedido(p.TIPO_DADOS, bytes([1, 0]) + b"\x00" * 7),
        "magic do servidor": b"DSUS" + PEDIDO_DE_PORTAS_DO_AZAHAR[4:],
        "versão 1000": PEDIDO_DE_PORTAS_DO_AZAHAR[:4]
        + struct.pack("<H", 1000)
        + PEDIDO_DE_PORTAS_DO_AZAHAR[6:],
        "datagrama menor que 16+comprimento": PEDIDO_DE_PORTAS_DO_AZAHAR[:-1],
        "tipo de motor": _pedido(0x110001, b"\x00" * 8),
        "tipo desconhecido": _pedido(0x123456, b""),
        "vazio": b"",
        "só o magic": b"DSUC",
        "comprimento 0": _com_comprimento(PEDIDO_DE_PORTAS_DO_AZAHAR, 0),
    }
    crc_ruim = bytearray(PEDIDO_DE_PORTAS_DO_AZAHAR)
    crc_ruim[8] ^= 0x80
    casos["CRC errado"] = bytes(crc_ruim)
    for nome, datagrama in casos.items():
        assert p.interpretar_pedido(datagrama) is None, nome


def test_valor_fora_do_campo_e_recusado_sem_struct_error() -> None:
    with pytest.raises(ValueError, match="contador"):
        p.montar_dados(1, slot=0, mac=MAC_FORJADO, contador=1 << 32, timestamp_us=0)
    with pytest.raises(ValueError, match="contador"):
        p.montar_dados(1, slot=0, mac=MAC_FORJADO, contador=-1, timestamp_us=0)
    with pytest.raises(ValueError, match="timestamp"):
        p.montar_dados(1, slot=0, mac=MAC_FORJADO, contador=0, timestamp_us=1 << 64)
    with pytest.raises(ValueError, match="x do toque"):
        p.montar_dados(
            1,
            slot=0,
            mac=MAC_FORJADO,
            contador=0,
            timestamp_us=0,
            toques=(p.Toque(True, 1, 70000, 0), p.TOQUE_INATIVO),
        )
    with pytest.raises(ValueError, match="mac"):
        p.mac_em_bytes("02:fe")


def test_o_mac_de_fixture_e_da_faixa_forjada_e_sem_sequencia_simples() -> None:
    assert MAC_FORJADO.startswith("02:fe:00:")
    octetos = MAC_FORJADO.split(":")
    assert len(set(octetos)) == 6
    assert re.fullmatch(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", MAC_FORJADO)
    assert p.mac_em_bytes(MAC_FORJADO) == bytes.fromhex("02fe007a19c3")


def test_o_modulo_do_codec_nao_faz_io() -> None:
    fonte = Path(p.__file__).read_text(encoding="utf-8")
    for proibido in ("import socket", "import time", "import os", "open(", "threading"):
        assert proibido not in fonte, proibido
