"""E-8 — as quatro travas do instrumento que mede giroscópio e perda de report."""
from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path
from typing import Any

_RAIZ = Path(__file__).resolve().parents[2]
_INSTRUMENTO = _RAIZ / "scripts" / "ensaios" / "giro_e_buraco.py"


def _carregar_o_instrumento() -> Any:
    """Carrega o instrumento pelo caminho — `scripts/ensaios/` não é pacote."""
    pasta = str(_INSTRUMENTO.parent)
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    especificacao = importlib.util.spec_from_file_location(
        "giro_e_buraco_sob_ensaio", _INSTRUMENTO
    )
    if especificacao is None or especificacao.loader is None:
        raise AssertionError(f"não consegui carregar {_INSTRUMENTO}")
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[especificacao.name] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo


E8 = _carregar_o_instrumento()

#: Os números MEDIDOS no feature 0x05 dos quatro DualSense da mesa 2+2, em
SPEED_2X_MEDIDO = 1080
DENOM_MEDIDO = 17694

LSB_POR_DPS_ESPERADO = SPEED_2X_MEDIDO and DENOM_MEDIDO / SPEED_2X_MEDIDO


def _feature_0x05(
    *,
    bias: tuple[int, int, int] = (23, -3, -4),
    mais: tuple[int, int, int] = (8870, 8841, 8838),
    menos: tuple[int, int, int] = (-8824, -8847, -8845),
    speed_plus: int = 540,
    speed_minus: int = 540,
) -> bytes:
    """Um feature 0x05 forjado com o layout do `hid-playstation.c`."""
    corpo = bytearray(E8.TAMANHO_CALIBRACAO - 1)
    struct.pack_into("<3h", corpo, 0, *bias)
    for indice in range(3):
        struct.pack_into("<h", corpo, 6 + indice * 4, mais[indice])
        struct.pack_into("<h", corpo, 8 + indice * 4, menos[indice])
    struct.pack_into("<h", corpo, 18, speed_plus)
    struct.pack_into("<h", corpo, 20, speed_minus)
    for indice in range(3):
        struct.pack_into("<h", corpo, 22 + indice * 4, 8192)
        struct.pack_into("<h", corpo, 24 + indice * 4, -8192)
    return bytes([E8.FEATURE_CALIBRACAO]) + bytes(corpo)


def _calibracao_do_feature(bruto: bytes) -> Any:
    """Roda o MESMO parser do instrumento sobre um feature forjado."""

    class _NoFalso:
        fd = -1

        def fechar(self) -> None:
            return None

    def _abrir(_caminho: str, *, escrita: bool = True) -> Any:
        assert escrita is False, "o instrumento tem de pedir fd de LEITURA (Lei 3)"
        return _NoFalso()

    def _ioctl(_fd: int, _pedido: int, buf: bytearray, _mutar: bool) -> int:
        buf[: len(bruto)] = bruto
        return len(bruto)

    original_abrir = E8.abrir_no_hidraw
    original_ioctl = E8.fcntl.ioctl
    E8.abrir_no_hidraw = _abrir
    E8.fcntl.ioctl = _ioctl
    try:
        alvo = E8.Aparelho("hidraw0", "/dev/hidraw0", "", "", "", "cabo", False, "")
        return E8.ler_calibracao(alvo)
    finally:
        E8.abrir_no_hidraw = original_abrir
        E8.fcntl.ioctl = original_ioctl


def _report(
    transporte: str,
    *,
    contador: int,
    seq: int = 1,
    carimbo: int = 0,
    giro: tuple[int, int, int] = (0, 0, 0),
    acel: tuple[int, int, int] = (0, 0, 8192),
) -> bytes:
    """Um report de entrada forjado, com o envelope do transporte pedido."""
    perfil = E8.PERFIL_DO_TRANSPORTE[transporte]
    quadro = bytearray(perfil["tamanho"])
    quadro[0] = perfil["report_id"]
    corpo = perfil["corpo"]
    quadro[corpo + E8.OFFSET_SEQ_NO_CORPO] = seq & 0xFF
    struct.pack_into("<3h", quadro, corpo + E8.OFFSET_GIRO_NO_CORPO, *giro)
    struct.pack_into("<3h", quadro, corpo + E8.OFFSET_ACEL_NO_CORPO, *acel)
    struct.pack_into("<I", quadro, corpo + E8.OFFSET_CONTADOR_NO_CORPO, contador)
    struct.pack_into("<I", quadro, corpo + E8.OFFSET_TS_NO_CORPO, carimbo)
    return bytes(quadro)


def _medida(transporte: str) -> Any:
    return E8.Medida(
        aparelho=E8.Aparelho(
            "hidraw0", "/dev/hidraw0", "", "aa:bb:cc:dd:ee:ff", "", transporte, False, ""
        )
    )


def test_a_regua_do_giroscopio_sai_do_feature_e_nao_da_constante_1024() -> None:
    """A conversão para graus/s usa a calibração da UNIDADE, não o 1024 do driver."""
    calibracao = _calibracao_do_feature(_feature_0x05())
    assert calibracao.ok, calibracao.motivo
    assert calibracao.speed_2x == SPEED_2X_MEDIDO
    assert abs(calibracao.lsb_por_dps - LSB_POR_DPS_ESPERADO) < 0.05
    assert calibracao.lsb_por_dps < E8.DS_GYRO_RES_PER_DEG_S / 50

    medida = _medida(E8.CABO)
    medida.calib = calibracao
    for i in range(3):
        medida.giros_crus.append((21, 0, 0) if i == 0 else (0, 0, 0))
    medida.giros_crus[:] = [(21, 0, 0)]
    medida.aceis_crus[:] = [(0, 0, 8192)]
    medida.finalizar()

    esperado = 21 * SPEED_2X_MEDIDO / DENOM_MEDIDO
    assert abs(medida.giro_mediano_dps - esperado) < 0.01
    assert medida.giro_ingenuo_mediano < esperado / 50


def test_o_parser_do_feature_0x05_le_os_campos_nos_offsets_do_driver() -> None:
    """Os offsets do feature 0x05 são os do `hid-playstation.c`, não outros."""
    calibracao = _calibracao_do_feature(_feature_0x05(speed_plus=500, speed_minus=580))
    assert calibracao.speed_2x == 1080

    assert calibracao.bias_lido == (23, -3, -4)

    esperado_x = abs(8870 - 23) + abs(-8824 - 23)
    assert calibracao.denom[0] == esperado_x

    ruim = _calibracao_do_feature(_feature_0x05(mais=(0, 0, 0), menos=(0, 0, 0), bias=(0, 0, 0)))
    assert not ruim.ok
    assert ruim.dps_por_lsb == (0.0, 0.0, 0.0)


def test_a_perda_e_contada_pelo_le32_do_reserved_e_nao_pelo_seq_number() -> None:
    """O buraco na fila é contado pelo `__le32` de `corpo[11]`, nos dois transportes."""
    for transporte in (E8.CABO, E8.RADIO):
        medida = _medida(transporte)
        seq_anda = transporte == E8.CABO
        for indice, contador in enumerate((100, 101, 104)):
            seq = (contador if seq_anda else 1) & 0xFF
            E8._consumir(
                medida,
                _report(transporte, contador=contador, seq=seq, carimbo=indice * 12000),
                agora_ns=indice * 4_000_000,
            )
        assert medida.aproveitados == 3, transporte
        assert medida.pares == 2, transporte
        assert medida.reports_perdidos == 2, f"{transporte}: dois reports sumiram"
        assert medida.saltos_do_contador == [2], transporte
        if not seq_anda:
            assert medida.seq_parado == 2

    inteira = _medida(E8.RADIO)
    for indice, contador in enumerate((7, 8, 9, 10)):
        E8._consumir(
            inteira,
            _report(E8.RADIO, contador=contador, seq=1, carimbo=indice * 7500),
            agora_ns=indice * 2_500_000,
        )
    assert inteira.reports_perdidos == 0
    assert inteira.saltos_do_contador == []


def test_o_silencio_maximo_inclui_a_cauda_que_nunca_fechou() -> None:
    """Um aparelho que cala e não volta aparece com o silêncio INTEIRO.

    Um silêncio que não termina não fecha par nenhum, e par nenhum é amostra
    nenhuma: sem a cauda, o instrumento reportava o p95 do pedacinho em que o
    aparelho falou como se fosse o da janela. Foi medido em 15/08/2026 às
    22h21 — um DualSense de rádio calou nos últimos ~55 s de uma janela de 60 s
    e a tabela imprimiu "silêncio máximo 19,03 ms".

    MORDIDA PROVADA no mesmo minuto: com `silencio_maximo_ms` devolvendo só
    `max(intervalos_host_ms)`, a primeira asserção reprovou com 19,0 contra os
    55000 esperados.
    """
    medida = _medida(E8.RADIO)
    medida.intervalos_host_ms.extend([2.5, 3.0, 19.03])
    medida.segundos = 60.0
    medida.cauda_muda_ms = 55_000.0

    assert medida.silencio_maximo_ms == 55_000.0
    assert medida.fracao_da_janela_medida < 0.01

    normal = _medida(E8.CABO)
    normal.intervalos_host_ms.extend([4.0, 4.0, 8.13])
    normal.segundos = 0.016
    normal.cauda_muda_ms = 3.17
    assert normal.silencio_maximo_ms == 8.13
    assert normal.fracao_da_janela_medida == 1.0
