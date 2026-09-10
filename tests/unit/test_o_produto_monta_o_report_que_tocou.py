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
* trocar `ARRANJO_PADRAO` de volta para um dos candidatos do `0x39` reprova
  `test_o_padrao_do_produto_e_o_que_tocou`;
* apagar `intervalo_de_envio_s` do `ARRANJO_035` reprova
  `test_a_cadencia_e_a_medida_e_nao_a_nominal` — a bomba volta a 100/s;
* apagar a guarda `if self.len_haptico:` de `Arranjo.montar` reprova
  `test_o_arranjo_sem_haptico_nao_estraga_o_byte_de_id` — o byte de id vira
  `0xD2` e o firmware descarta calado, que é o silêncio de sempre;
* apagar `controle_conta_quadros` reprova
  `test_o_contador_de_quadros_avanca_a_cada_report`;
* qualquer mudança no layout reprova `test_os_bytes_sao_os_que_ela_ouviu`.
"""
from __future__ import annotations

import dataclasses

import pytest

import hefesto_dualsense4unix.core.ds_output_report as rep
from hefesto_dualsense4unix.integrations import alto_falante_bt as af

#: O tamanho do `0x35` com o byte de id — declarado no descritor do aparelho.
TAMANHO_035 = 334

#: Um quadro Opus de mentira, do tamanho exato que o CBR de 160 kbps fecha.
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
    """A montagem do ENSAIO, escrita à mão — é ela que tocou.

    Deliberadamente uma segunda implementação: se ela fosse importada do
    módulo, este arquivo mediria o produto contra si mesmo, que é o defeito
    que a casa nomeia como *trava medida contra a própria saída*.
    """
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


def test_o_padrao_do_produto_e_o_que_tocou() -> None:
    """Quem manda som sem escolher arranjo recebe o MEDIDO, não um candidato.

    Os dois candidatos de fonte externa descrevem o `0x39` de 547 B com DOIS
    quadros, e as nove passadas de áudio desta casa bateram todas neles. O
    padrão tem de ser o que a orelha dela aprovou.
    """
    assert af.ARRANJO_PADRAO is af.ARRANJO_035
    assert af.ARRANJO_PADRAO.degrau == 0x35, "o degrau que toca é o QUINTO, não o teto"
    assert af.ARRANJO_PADRAO.quadros_de_audio == 1, (
        "o `0x35` leva UM quadro; dois é o arranjo do `0x39`, que ficou mudo"
    )
    assert af.ARRANJO_PADRAO not in af.ARRANJOS, (
        "`ARRANJOS` é «os candidatos de fonte externa, registrados sem "
        "escolher» — o medido não é candidato, e misturá-lo apaga a "
        "procedência que este módulo existe para proteger"
    )


def test_a_cadencia_e_a_medida_e_nao_a_nominal() -> None:
    """512/48000, e não 10 ms — o aparelho come 93,75 quadros/s, não 100."""
    bomba = af.BombaDeSomPeloRadio(
        arranjo=af.ARRANJO_035, fonte=lambda n: b"\x00" * n
    )
    assert bomba.intervalo_de_envio_s == pytest.approx(512 / 48_000)
    reports_por_segundo = 1.0 / bomba.intervalo_de_envio_s
    assert reports_por_segundo == pytest.approx(93.75), (
        "alimentar a 100/s é a taxa de ESTOURO que segurou esta casa por nove "
        f"passadas; esta bomba manda {reports_por_segundo:.2f}/s"
    )


def test_o_nominal_continua_valendo_para_quem_nao_mediu() -> None:
    """A cadência medida não pode sequestrar os arranjos que ninguém mediu."""
    bomba = af.BombaDeSomPeloRadio(
        arranjo=af.ARRANJO_DS5DONGLE, fonte=lambda n: b"\x00" * n
    )
    assert af.ARRANJO_DS5DONGLE.intervalo_de_envio_s is None
    assert bomba.intervalo_de_envio_s == pytest.approx(
        bomba.ms_por_report / 1000.0
    ), "sem medição, vale o nominal — e ele fica visível como nominal"


def test_o_contador_de_quadros_avanca_a_cada_report() -> None:
    """O `[10]` conta QUADROS. Parado em zero, o firmware perde a conta."""
    bomba = af.BombaDeSomPeloRadio(
        arranjo=af.ARRANJO_035, fonte=lambda n: b"\x00" * n
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


def test_o_contador_conta_QUADROS_e_nao_reports() -> None:  # noqa: N802
    """Um arranjo de DOIS quadros avança de dois em dois. A distinção é real.

    ESTE TESTE NASCEU FROUXO E FOI APERTADO NA MORDIDA, em 10/09/2026. Ele
    média contra o `ARRANJO_035`, que carrega UM quadro — e ali
    `+= quadros_de_audio` e `+= 1` dão o mesmo número. A mordida
    (`self._quadros_mandados += 1`) passou, e uma régua que passa com a cura
    arrancada não mede nada.

    A cura da régua é medir contra um arranjo que carrega DOIS.
    """
    de_dois = dataclasses.replace(af.ARRANJO_DS5DONGLE, controle_conta_quadros=True)
    assert de_dois.quadros_de_audio == 2, (
        "este teste só morde se o arranjo levar mais de um quadro"
    )
    bomba = af.BombaDeSomPeloRadio(arranjo=de_dois, fonte=lambda n: b"\x00" * n)
    for _ in range(3):
        bomba.um_report()
    assert bomba._quadros_mandados == 6, (
        f"contou {bomba._quadros_mandados} — está contando REPORTS, não quadros"
    )


def test_o_arranjo_sem_haptico_nao_estraga_o_byte_de_id() -> None:
    """A guarda do háptico: sem ela o `[0]` vira `0xD2` e o firmware cala.

    É o defeito mais caro possível nesta área, porque o sintoma é exatamente o
    mesmo de um payload errado: silêncio.
    """
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
        arranjo=af.ARRANJO_035, fonte=lambda n: b"\x00" * n, com_microfone=True
    )
    report = bomba.um_report()
    assert report and report[4] == 0xFF, (
        "a bomba não levou o pedido de microfone ao fio"
    )


def test_o_buffer_recusa_tamanho_errado() -> None:
    """Cinco bytes, e nem um a mais — senão o contador cai no lugar errado."""
    with pytest.raises(ValueError, match="5 bytes"):
        af.controle_de_audio_035(contador_de_quadros=0, buffer=b"\x00" * 4)
