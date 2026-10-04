"""O produto monta o MESMO report que fez o som sair na bancada dela.

MEDIDO EM 10/09/2026: o alto-falante do DualSense tocou por rádio, 70 segundos
contínuos, sem um corte, com a orelha dela e o alcance testado. Os bytes que
saíram no fio começam assim::

    35 10 91 07 fe 00 00 00 00 ff 01 93 c8 …

Este arquivo existe porque **o ensaio e o produto podiam divergir em silêncio**.
O `scripts/ensaios/o_som_pelo_035.py` monta o report com um `bytearray` próprio;
`integrations/alto_falante_bt.ARRANJO_035` monta pelo caminho genérico do
:class:`Arranjo`. Duas montagens da mesma coisa é a régua paralela que esta casa
já pagou onze vezes — e a única defesa é comparar as duas, byte a byte, em toda
combinação que importa.

O QUE CADA TESTE MORDE
-----------------------
* tirar o ``0x11`` ou o bloco de som do ``0x36`` da ponte, ou mudá-los de
  lugar, reprova `test_a_ponte_leva_o_0x11_e_o_quadro_que_tocaram_dentro_do_0x36`
  (desde 03/10/2026 a ponte escreve o ``0x36``; o ``0x35`` segue montável
  para o ensaio);
* mudar o intervalo da bomba reprova
  `test_a_cadencia_e_a_medida_e_nao_a_nominal` — o `rodar()` volta a 100/s;
* apagar a guarda `if self.len_haptico:` de `Arranjo.montar` reprova
  `test_o_arranjo_sem_haptico_nao_estraga_o_byte_de_id` — o byte de id vira
  `0xD2` e o firmware descarta calado, que é o silêncio de sempre;
* o contador parado reprova `test_o_contador_de_quadros_avanca_a_cada_report`;
* qualquer mudança no layout reprova `test_os_bytes_sao_os_que_ela_ouviu`.
"""
from __future__ import annotations

import pytest

import hefesto_dualsense4unix.core.ds_output_report as rep
from hefesto_dualsense4unix.integrations import alto_falante_bt as af

TAMANHO_035 = 334

QUADRO = bytes(range(200))


def report_como_o_ensaio_monta(
    quadro: bytes,
    *,
    seq: int,
    contador: int,
    rota: int,
    buffer: bytes,
    com_mic: bool = False,
) -> bytes:
    """A montagem do ENSAIO, escrita à mão — é ela que tocou."""
    pkt = bytearray(TAMANHO_035)
    pkt[0] = 0x35
    pkt[1] = (seq & 0x0F) << 4
    pkt[2] = 0x11 | 0x80
    pkt[3] = 7
    pkt[4] = 0xFF if com_mic else 0xFE
    pkt[5:10] = buffer
    pkt[10] = contador & 0xFF
    pkt[11] = rota | 0x80
    pkt[12] = 200
    pkt[13:213] = quadro
    crc = rep.bt_crc32(bytes(pkt[:-4]), seed=rep.BT_CRC_SEED)
    pkt[-4:] = crc.to_bytes(4, "little")
    return bytes(pkt)


@pytest.mark.parametrize("seq", [0, 1, 7, 15])
@pytest.mark.parametrize("contador", [0, 1, 147, 255])
@pytest.mark.parametrize("com_mic", [False, True])
@pytest.mark.parametrize("rota", [af.BLOCO_SPEAKER, af.BLOCO_FONE])
def test_os_bytes_sao_os_que_ela_ouviu(
    seq: int, contador: int, com_mic: bool, rota: int
) -> None:
    """Byte a byte, em 64 combinações: o produto monta o que o ensaio montou."""
    do_ensaio = report_como_o_ensaio_monta(
        QUADRO, seq=seq, contador=contador, rota=rota,
        buffer=af.BUFFER_QUE_TOCOU, com_mic=com_mic,
    )
    do_produto = af.ARRANJO_035.montar(
        [QUADRO],
        seq=seq,
        tag_audio=rota,
        controle=af.controle_de_audio_035(
            contador_de_quadros=contador, com_microfone=com_mic
        ),
    )
    assert do_produto == do_ensaio, (
        "o produto diverge do report que TOCOU na bancada dela em 10/09/2026 — "
        f"primeiro byte diferente: "
        f"{next(i for i in range(TAMANHO_035) if do_produto[i] != do_ensaio[i])}"
    )


@pytest.mark.parametrize("com_mic", [False, True])
@pytest.mark.parametrize("rota", [af.BLOCO_SPEAKER, af.BLOCO_FONE])
def test_a_ponte_leva_o_0x11_e_o_quadro_que_tocaram_dentro_do_0x36(
    com_mic: bool, rota: int
) -> None:
    """O ``0x36`` da ponte carrega o MESMO ``0x11`` e o MESMO bloco de som do ``0x35``."""
    class _Codificador:
        def codificar(self, _pcm: bytes) -> bytes:
            return QUADRO

    bomba = af.BombaDeSomPeloRadio(
        fonte=lambda n: b"\x01" * n, codificador=_Codificador(), tag_audio=rota,
        com_microfone=com_mic,
    )
    do_produto = bomba.um_report() or b""
    do_ensaio = report_como_o_ensaio_monta(
        QUADRO, seq=0, contador=0, rota=rota, buffer=af.BUFFER_QUE_TOCOU, com_mic=com_mic,
    )
    assert do_produto[0] == af.DEGRAU_COMBINADO
    assert do_produto[2:11] == do_ensaio[2:11], "o 0x11 diverge do que tocou"
    assert do_produto[11:13] == bytes((0x90, 63)), "o 0x10 vai em todo quadro"
    # sem háptica neste quadro, o som sobe na cadeia para logo depois do 0x10
    assert do_produto[76:78] == do_ensaio[11:13], "a tag do som diverge da que tocou"
    assert do_produto[78:278] == do_ensaio[13:213], "o quadro Opus saiu fora do lugar"


def test_a_cadencia_e_a_medida_e_nao_a_nominal() -> None:
    """512/48000, e não 10 ms — o aparelho come 93,75 quadros/s, não 100."""
    bomba = af.BombaDeSomPeloRadio(
        fonte=lambda n: b"\x00" * n
    )
    assert bomba.intervalo_de_envio_s == pytest.approx(512 / 48_000)
    reports_por_segundo = 1.0 / bomba.intervalo_de_envio_s
    assert reports_por_segundo == pytest.approx(93.75), (
        "alimentar a 100/s é a taxa de ESTOURO que segurou esta casa por nove "
        f"passadas; o arranjo declara {reports_por_segundo:.2f}/s"
    )


def test_o_contador_de_quadros_avanca_a_cada_report() -> None:
    """O `[10]` conta QUADROS. Parado em zero, o firmware perde a conta."""
    bomba = af.BombaDeSomPeloRadio(
        fonte=lambda n: b"\x00" * n
    )
    contadores = []
    sequencias = []
    for _ in range(4):
        report = bomba.um_report()
        assert report, "a bomba seca ainda monta o report; só não o escreve"
        contadores.append(report[10])
        sequencias.append(report[1] >> 4)
    assert contadores == [0, 1, 2, 3], (
        f"o contador de quadros não avançou: {contadores}"
    )
    assert sequencias == [0, 1, 2, 3], f"a sequência não avançou: {sequencias}"


def test_o_arranjo_sem_haptico_nao_estraga_o_byte_de_id() -> None:
    """A guarda do háptico: sem ela o `[0]` vira `0xD2` e o firmware cala."""
    assert af.ARRANJO_035.len_haptico == 0
    assert af.ARRANJO_035.pos_tag_haptico == 0, (
        "este teste só prova o que promete se a posição do háptico for 0 — é "
        "ela que colide com o byte de id"
    )
    report = af.ARRANJO_035.montar(
        [QUADRO], controle=af.controle_de_audio_035(contador_de_quadros=0)
    )
    assert report[0] == 0x35, (
        f"o byte de id saiu 0x{report[0]:02x} em vez de 0x35 — a guarda "
        "`if self.len_haptico:` foi arrancada de `Arranjo.montar`"
    )


def test_o_microfone_entra_no_mesmo_report_que_leva_o_som() -> None:
    """O bit 0 dos enables. É a metade da integração que ela pediu."""
    sem = af.controle_de_audio_035(contador_de_quadros=0, com_microfone=False)
    com = af.controle_de_audio_035(contador_de_quadros=0, com_microfone=True)
    assert sem[0] == 0xFE
    assert com[0] == 0xFF
    assert com[0] ^ sem[0] == 0x01, "a diferença tem de ser SÓ o bit 0"

    bomba = af.BombaDeSomPeloRadio(
        fonte=lambda n: b"\x00" * n, com_microfone=True
    )
    report = bomba.um_report()
    assert report and report[4] == 0xFF, (
        "a bomba não levou o pedido de microfone ao fio"
    )


def test_o_buffer_recusa_tamanho_errado() -> None:
    """Cinco bytes, e nem um a mais — senão o contador cai no lugar errado."""
    with pytest.raises(ValueError, match="5 bytes"):
        af.controle_de_audio_035(contador_de_quadros=0, buffer=b"\x00" * 4)
