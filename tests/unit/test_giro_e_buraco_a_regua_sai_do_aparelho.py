"""E-8 — as quatro travas do instrumento que mede giroscópio e perda de report.

O DEFEITO QUE ESTE ARQUIVO FECHA
--------------------------------
`scripts/ensaios/giro_e_buraco.py` nasceu em 15/08/2026 para fechar
`movimento.giroscopio` e `movimento.imu.perda`, e as duas coisas que ele mede
dependem de números que **não estão em documentação nenhuma**: a régua do
giroscópio sai do feature 0x05 de CADA unidade, e o contador de reports está
num campo que o driver do kernel chama de `reserved` e nunca lê.

Os dois são frágeis do mesmo jeito: uma edição bem-intencionada os "simplifica"
de volta para a constante bonita (`1024`) ou para o campo com nome bonito
(`seq_number`), e o instrumento continua imprimindo tabela — com números
errados por 62x, ou com perda zero para sempre. Nenhum dos dois erros produz
exceção. É exatamente o tipo de defeito que só um teste pega.

O QUE ESTE ARQUIVO NÃO FAZ, E É DE PROPÓSITO
---------------------------------------------
**Não abre `/dev/hidraw` nem `/dev/input` nenhum.** Não precisa: as quatro
travas são aritmética sobre bytes, e bytes se fabricam. Um teste que abrisse o
nó de verdade mediria a mesa de hoje — que muda — em vez da regra.

O QUE CADA TESTE PROVA, E A MORDIDA DE CADA UM
-----------------------------------------------
1. `test_a_regua_do_giroscopio_sai_do_feature_e_nao_da_constante_1024`
   A conversão cru -> graus/s usa `speed_2x / sens_denom` da unidade.
   MORDIDA (15/08/2026): trocado `dps_por_lsb` por `1 / DS_GYRO_RES_PER_DEG_S`
   — o valor caiu de 1,281 para 0,0205 graus/s e o teste reprovou.
2. `test_o_parser_do_feature_0x05_le_os_campos_nos_offsets_do_driver`
   Os offsets do feature 0x05 são os do `hid-playstation.c`.
   MORDIDA: deslocado o `speed_plus` de 18 para 20 — `speed_2x` virou 1200 em
   vez de 1080 e o teste reprovou.
3. `test_a_perda_e_contada_pelo_le32_do_reserved_e_nao_pelo_seq_number`
   Um report que some vira `reports_perdidos`, no cabo E no rádio; e no rádio,
   onde o `seq_number` fica parado, contar por ele daria zero.
   MORDIDA: trocado `OFFSET_CONTADOR_NO_CORPO` por `OFFSET_SEQ_NO_CORPO` — o
   caso do rádio passou a acusar 0 perdidos com 2 reports sumidos, e reprovou.
4. `test_o_silencio_maximo_inclui_a_cauda_que_nunca_fechou`
   Um aparelho que cala e não volta tem de aparecer com o silêncio inteiro.
   MORDIDA: `silencio_maximo_ms` devolvendo só `max(intervalos_host_ms)` — um
   controle calado por 55 s de uma janela de 60 s apareceu com "19 ms", que é
   o número que o bruto das 22h21 de 15/08/2026 guarda, e o teste reprovou.
"""
from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path
from typing import Any

_RAIZ = Path(__file__).resolve().parents[2]
_INSTRUMENTO = _RAIZ / "scripts" / "ensaios" / "giro_e_buraco.py"


def _carregar_o_instrumento() -> Any:
    """Carrega o instrumento pelo caminho — `scripts/ensaios/` não é pacote.

    Mesmo precedente de `test_cor_do_plastico_recusa_o_alvo_errado`: o nome sob
    o qual ele entra em `sys.modules` é outro, para que este arquivo nunca
    roube o módulo de quem o importa pelo nome real.
    """
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
#: 15/08/2026. Não são inventados: `speed_2x = 1080` saiu igual nas quatro
#: unidades, e os denominadores ficaram entre 17577 e 17829.
SPEED_2X_MEDIDO = 1080
DENOM_MEDIDO = 17694

#: O que o par acima significa: ~16,4 LSB crus por grau/s no fio. A constante
#: do driver (1024) é 62 vezes maior, e é a armadilha que este arquivo guarda.
LSB_POR_DPS_ESPERADO = SPEED_2X_MEDIDO and DENOM_MEDIDO / SPEED_2X_MEDIDO


def _feature_0x05(
    *,
    bias: tuple[int, int, int] = (23, -3, -4),
    mais: tuple[int, int, int] = (8870, 8841, 8838),
    menos: tuple[int, int, int] = (-8824, -8847, -8845),
    speed_plus: int = 540,
    speed_minus: int = 540,
) -> bytes:
    """Um feature 0x05 forjado com o layout do `hid-playstation.c`.

    O kernel entrega o report com o id em `data[0]`; o corpo começa em
    `data[1]`, e é dali que todos os offsets abaixo contam. Os defaults
    reproduzem `speed_2x = 1080` e `sens_denom ~ 17694`.
    """
    corpo = bytearray(E8.TAMANHO_CALIBRACAO - 1)
    struct.pack_into("<3h", corpo, 0, *bias)
    for indice in range(3):
        struct.pack_into("<h", corpo, 6 + indice * 4, mais[indice])
        struct.pack_into("<h", corpo, 8 + indice * 4, menos[indice])
    struct.pack_into("<h", corpo, 18, speed_plus)
    struct.pack_into("<h", corpo, 20, speed_minus)
    # Acelerômetro: +-1 g em ~8192 LSB, como as quatro unidades medidas.
    for indice in range(3):
        struct.pack_into("<h", corpo, 22 + indice * 4, 8192)
        struct.pack_into("<h", corpo, 24 + indice * 4, -8192)
    return bytes([E8.FEATURE_CALIBRACAO]) + bytes(corpo)


def _calibracao_do_feature(bruto: bytes) -> Any:
    """Roda o MESMO parser do instrumento sobre um feature forjado.

    `ler_calibracao` abre o hidraw, e abrir hidraw num teste seria medir a mesa.
    Aqui só o ioctl é trocado: a leitura devolve os bytes de cima, e todo o
    resto do caminho — offsets, `speed_2x`, denominadores, a validação — é o do
    instrumento, sem cópia.
    """

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
    """A conversão para graus/s usa a calibração da UNIDADE, não o 1024 do driver.

    Este é o teste central do arquivo. A régua errada não levanta exceção nem
    produz número absurdo: ela só encolhe tudo por 62x, o que faz um controle
    girando passar por parado — e um controle negativo que não consegue
    reprovar não é controle negativo.

    MORDIDA PROVADA em 15/08/2026: com `dps_por_lsb` devolvendo
    `1 / DS_GYRO_RES_PER_DEG_S`, o |w| do caso abaixo caiu de 1,281 para 0,0205
    graus/s e as duas asserções reprovaram.
    """
    calibracao = _calibracao_do_feature(_feature_0x05())
    assert calibracao.ok, calibracao.motivo
    assert calibracao.speed_2x == SPEED_2X_MEDIDO
    assert abs(calibracao.lsb_por_dps - LSB_POR_DPS_ESPERADO) < 0.05
    # O ponto do teste: a régua NÃO é 1024, e a diferença é de mais de 60x.
    assert calibracao.lsb_por_dps < E8.DS_GYRO_RES_PER_DEG_S / 50

    medida = _medida(E8.CABO)
    medida.calib = calibracao
    # 21 LSB crus por eixo é a ordem de grandeza do repouso medido na mesa.
    for i in range(3):
        medida.giros_crus.append((21, 0, 0) if i == 0 else (0, 0, 0))
    medida.giros_crus[:] = [(21, 0, 0)]
    medida.aceis_crus[:] = [(0, 0, 8192)]
    medida.finalizar()

    esperado = 21 * SPEED_2X_MEDIDO / DENOM_MEDIDO
    assert abs(medida.giro_mediano_dps - esperado) < 0.01
    # E a régua ingênua, que fica impressa ao lado, tem de mostrar o erro.
    assert medida.giro_ingenuo_mediano < esperado / 50


def test_o_parser_do_feature_0x05_le_os_campos_nos_offsets_do_driver() -> None:
    """Os offsets do feature 0x05 são os do `hid-playstation.c`, não outros.

    `speed_2x` mora em 18 e 20; os `plus`/`minus` de cada eixo em 6/8, 10/12 e
    14/16; e o `bias` de 0, 2, 4 entra APENAS no denominador — o driver zera o
    bias do giroscópio de propósito (`:1200, :1206, :1212`), e copiar essa
    escolha é o que faz a conta daqui bater com a do kernel.

    MORDIDA PROVADA em 15/08/2026: `speed_plus` lido de 20 em vez de 18 fez
    `speed_2x` virar 1200, e a primeira asserção reprovou.
    """
    calibracao = _calibracao_do_feature(_feature_0x05(speed_plus=500, speed_minus=580))
    assert calibracao.speed_2x == 1080

    # O bias é LIDO (vai para a tabela) mas não subtrai nada da leitura.
    assert calibracao.bias_lido == (23, -3, -4)

    # Denominador do eixo X: |mais - bias| + |menos - bias|.
    esperado_x = abs(8870 - 23) + abs(-8824 - 23)
    assert calibracao.denom[0] == esperado_x

    # Calibração degenerada NÃO vira régua silenciosa: sem denominador não há
    # conta possível, e o instrumento tem de dizer isso em vez de dividir por
    # zero ou cair no 1024.
    ruim = _calibracao_do_feature(_feature_0x05(mais=(0, 0, 0), menos=(0, 0, 0), bias=(0, 0, 0)))
    assert not ruim.ok
    assert ruim.dps_por_lsb == (0.0, 0.0, 0.0)


def test_a_perda_e_contada_pelo_le32_do_reserved_e_nao_pelo_seq_number() -> None:
    """O buraco na fila é contado pelo `__le32` de `corpo[11]`, nos dois transportes.

    O `seq_number` de `corpo[6]` só anda no CABO: medido em 15/08/2026, por
    rádio ele fica constante em 1 — delta zero em 1628 de 1628 pares no bruto
    `2026-08-15-E8-A-unidade-no-radio-que-dormiu-e-caiu.csv`. Um contador
    de perda montado sobre ele veria zero para sempre no transporte em que a
    perda é mais provável — que é o pior modo de falha possível para esta
    célula do mapa.

    MORDIDA PROVADA em 15/08/2026: trocando `OFFSET_CONTADOR_NO_CORPO` por
    `OFFSET_SEQ_NO_CORPO`, o caso do rádio passou a acusar 0 perdidos com 2
    reports sumidos, e a asserção do rádio reprovou.
    """
    for transporte in (E8.CABO, E8.RADIO):
        medida = _medida(transporte)
        # No rádio o seq fica PARADO — é o que o aparelho faz de verdade.
        seq_anda = transporte == E8.CABO
        # 100, 101, [102 e 103 somem], 104
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
            # A prova de que o contador bom não é o `seq_number`: por rádio ele
            # ficou parado nos DOIS pares, inclusive no par em que houve perda.
            assert medida.seq_parado == 2

    # E o caso simétrico, sem o qual a regra viraria "acusar sempre": fila
    # inteira, contador de 1 em 1, zero perdidos.
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
    # E a fração da janela coberta denuncia que o p95 acima não é da janela.
    assert medida.fracao_da_janela_medida < 0.01

    # Simétrico: sem cauda, o máximo continua sendo o maior intervalo medido.
    normal = _medida(E8.CABO)
    normal.intervalos_host_ms.extend([4.0, 4.0, 8.13])
    normal.segundos = 0.016
    normal.cauda_muda_ms = 3.17
    assert normal.silencio_maximo_ms == 8.13
    assert normal.fracao_da_janela_medida == 1.0
