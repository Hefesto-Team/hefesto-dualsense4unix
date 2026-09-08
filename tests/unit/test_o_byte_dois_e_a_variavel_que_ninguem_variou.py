"""O BYTE [2] DO DEGRAU — a variável que as seis passadas não variaram.

**ESTE ARQUIVO NÃO FECHA O ITEM DO ALTO-FALANTE PELO RÁDIO, e não pretende.**
Quem fecha é a ORELHA DELA, num ensaio de bancada com o negativo de rota, na
forma que os ensaios de 15/08/2026 já usaram. O que ele prova é que o par
com/sem existe e está bem montado — que o *"com"* que faltava agora pode ser
escrito.

O QUE A MEDIÇÃO DE 08/09/2026 ACHOU, e é aritmética, não hipótese::

    0x31 do produto           : [2]=0x10   <- o ÚNICO valor medido obedecendo
    0x39 ds5dongle 0x13 e 0x16: [2]=0x91
    0x39 senshi    0x13 e 0x16: [2]=0x91

`OFFSET_DO_COMMON = 3` diz, citando a medição de 15/08/2026, que o `common` de
47 bytes mora em [3..49] — e para ele cair ali o [2] tem de ser `0x10`. **Os
dois arranjos escrevem `0x91` exatamente ali**, sobrescrevendo o único byte
cujo valor esta bancada já viu o firmware aceitar. As seis passadas do ensaio
variaram a TAG e o ARRANJO, e não variaram este byte.

**O QUE ESTE ARQUIVO NÃO AFIRMA, e a proibição é literal do mapa** (`audio.
saida_dedicada.payload_do_degrau@dualsense`.radio_ressalva, transcrita em
`integrations/alto_falante_bt.py`): *"NÃO ESCREVER, EM LUGAR NENHUM, que
'descobrimos o áudio por Bluetooth' ou que a ponte funciona."* Não funciona, e
não há ponte: há um canal que responde. `os.write()` devolve sucesso quando o
KERNEL aceita, nunca quando o firmware obedece — **FALÁCIA DO CANAL QUE
RESPONDE**.

NENHUM TESTE DESTE ARQUIVO ESCREVE NUM CONTROLE. Tudo aqui é montagem de bytes
em memória.
"""

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

#: Um `common` que não é só zeros — para que "preservado" tenha o que provar.
COMMON = build_bt_report(bytes(range(COMMON_LEN)))[3 : 3 + COMMON_LEN]
QUADROS = [b"\xaa" * af.BYTES_POR_QUADRO_OPUS, b"\xbb" * af.BYTES_POR_QUADRO_OPUS]


# ---------------------------------------------------------------------------
# MORDIDA 1 — o [2] do terceiro corpo é o do PRODUTO, e não o dos arranjos
# ---------------------------------------------------------------------------


def test_o_terceiro_corpo_traz_o_byte_dois_que_a_bancada_mediu() -> None:
    """`[2] = 0x10`, o mesmo do 0x31 que acendeu a lightbar por rádio.

    ARRANQUE A CURA (troque o `pkt[2] = BT_TAG` por
    `tag_tlv(BLOCO_AUDIO_CONTROL)`, que é o que os dois arranjos fazem) e esta
    régua REPROVA — e a passada volta a ser a sétima repetição das seis.
    """
    pkt = af.montar_com_o_common_preservado(QUADROS, COMMON)
    assert pkt[2] == BT_TAG == 0x10, (
        f"o terceiro corpo saiu com [2]=0x{pkt[2]:02x}; o único valor que esta "
        "bancada viu o firmware aceitar é 0x10, e os dois arranjos já escrevem "
        "0x91 ali — sem variar este byte, a passada é a sétima repetição"
    )


def test_os_dois_arranjos_continuam_escrevendo_noventa_e_um_ali() -> None:
    """O *"sem"* do par, e ele NÃO é um defeito a curar — é o outro lado.

    Os dois arranjos são leitura de fonte externa e ficam como as fontes os
    declaram. Trocar o [2] deles seria apagar a metade que dá sentido à
    comparação, e inventar uma terceira leitura das fontes.
    """
    pacotes = af.montar_pelos_dois_arranjos(QUADROS)
    assert set(pacotes) == {"ds5dongle", "senshi"}
    for nome, pkt in pacotes.items():
        assert pkt[2] == 0x91, (
            f"o arranjo {nome} deixou de escrever 0x91 em [2]; o *sem* do par "
            f"com/sem sumiu: 0x{pkt[2]:02x}"
        )


# ---------------------------------------------------------------------------
# MORDIDA 2 — o `common` chega INTACTO, byte a byte
# ---------------------------------------------------------------------------


def test_o_common_de_quarenta_e_sete_bytes_sobrevive_em_tres_a_quarenta_e_nove() -> None:
    """Preservado quer dizer IDÊNTICO, e a régua compara os 47 bytes.

    É o que a fonte da afirmação exige: o `common` que esta bancada mediu
    obedecendo é este, e um que chegue com um byte trocado não é ele.

    ARRANQUE A CURA (escreva o `common` em qualquer outro offset) e esta régua
    REPROVA dizendo em que byte a cópia divergiu.
    """
    pkt = af.montar_com_o_common_preservado(QUADROS, COMMON)
    vindo = bytes(pkt[af.OFFSET_DO_COMMON : af.OFFSET_DO_COMMON + COMMON_LEN])
    assert vindo == COMMON, (
        "o `common` não chegou intacto em [3..49] — o envelope que a bancada "
        f"mediu foi desmontado: {vindo[:8].hex()} != {COMMON[:8].hex()}"
    )


def test_o_common_e_o_mesmo_que_o_produto_ja_manda_no_trinta_e_um() -> None:
    """O envelope é EMPRESTADO, não reconstruído — dono único.

    Montar um segundo `common` aqui seria a décima segunda régua sobre o mesmo
    estado nesta casa. Quem o monta é `build_bt_report`, e este teste prova que
    é o mesmo objeto que atravessa.
    """
    trinta_e_um = build_bt_report(bytes(range(COMMON_LEN)))
    assert trinta_e_um[2] == BT_TAG
    pkt = af.montar_com_o_common_preservado(QUADROS, trinta_e_um[3 : 3 + COMMON_LEN])
    assert bytes(pkt[3:50]) == bytes(trinta_e_um[3:50]), (
        "o corpo do 0x39 não carrega o MESMO common do 0x31 do produto"
    )


def test_um_common_de_tamanho_errado_e_recusado() -> None:
    """Ausência é resposta: um envelope truncado não vira report silencioso.

    Um `common` de 46 bytes deslocaria tudo o que vem depois em um byte, e o
    firmware descartaria em silêncio — o sintoma indistinguível de *"o aparelho
    não faz"*, que é justamente o que o par com/sem existe para separar.
    """
    with pytest.raises(ValueError, match="47"):
        af.montar_com_o_common_preservado(QUADROS, COMMON[:-1])


# ---------------------------------------------------------------------------
# MORDIDA 3 — o Opus vai DEPOIS, e cabe nos 493 bytes livres
# ---------------------------------------------------------------------------


def test_o_opus_comeca_logo_depois_do_common() -> None:
    """[50] é a tag, [51] o `len`, e os quadros a partir de [52].

    O offset é DERIVADO (`OFFSET_DO_COMMON + COMMON_LEN`), nunca digitado: um
    número à mão aqui envelheceria na primeira vez que o `common` mudasse de
    tamanho, e o sintoma seria de novo o silêncio.
    """
    pkt = af.montar_com_o_common_preservado(QUADROS, COMMON)
    assert af.OFFSET_APOS_O_COMMON == 50
    assert pkt[50] == af.tag_tlv(af.BLOCO_SPEAKER, duplo=True)
    assert pkt[51] == af.BYTES_POR_QUADRO_OPUS
    assert bytes(pkt[52:252]) == QUADROS[0]
    assert bytes(pkt[252:452]) == QUADROS[1]


def test_o_orcamento_do_degrau_e_respeitado_e_nao_estimado() -> None:
    """493 bytes livres no 0x39 — e o que não cabe é RECUSADO, não truncado.

    `orcamento_do_degrau` já é o dono deste número (total - envelope - common -
    CRC). Um report montado por cima do fim seria descartado pelo firmware em
    silêncio.
    """
    assert af.orcamento_do_degrau(0x39) == 493
    cabem = [b"\x01" * af.BYTES_POR_QUADRO_OPUS] * 2
    assert len(af.montar_com_o_common_preservado(cabem, COMMON)) == 547
    with pytest.raises(ValueError, match="não cabem"):
        af.montar_com_o_common_preservado(
            [b"\x01" * af.BYTES_POR_QUADRO_OPUS] * 3, COMMON
        )


def test_o_crc_e_o_do_produto_e_fecha_sobre_o_corpo_inteiro() -> None:
    """A hipótese do CRC está REFUTADA, e esta régua guarda a refutação.

    `bt_crc32` faz `zlib.crc32(bytes([0xA2]) + data)`, e
    `zlib.crc32(b"\\xa2") == 0xEADA2D49` — a semente que o DS5Dongle usa. **As
    duas convenções são a MESMA**, ditas de dois jeitos. Quem for atrás do CRC
    por causa do silêncio das seis passadas gasta o dia no lugar errado.
    """
    import zlib

    assert zlib.crc32(b"\xa2") == 0xEADA2D49
    pkt = af.montar_com_o_common_preservado(QUADROS, COMMON)
    esperado = bt_crc32(pkt[:-4], seed=BT_CRC_SEED).to_bytes(4, "little")
    assert bytes(pkt[-4:]) == esperado, "o CRC do terceiro corpo não fecha"


# ---------------------------------------------------------------------------
# MORDIDA 4 — a tag do bloco continua VARIÁVEL, porque ela é a outra pergunta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tag", [0x13, 0x16])
def test_a_tag_do_bloco_continua_escolhivel(tag: int) -> None:
    """0x13 (alto-falante) e 0x16 (fone) — as duas que o ensaio já varreu.

    O terceiro corpo varia o [2]; ele não pode PERDER a variável que as seis
    passadas já variavam, senão o par com/sem deixa de ser comparável com o que
    já foi medido.
    """
    pkt = af.montar_com_o_common_preservado(QUADROS, COMMON, tag_audio=tag)
    assert pkt[2] == BT_TAG, "variar a tag não pode mexer no byte [2]"
    assert pkt[af.OFFSET_APOS_O_COMMON] == af.tag_tlv(tag, duplo=True)


def test_a_sequencia_rotaciona_no_nibble_alto() -> None:
    """O nibble de sequência já estava tratado e não explica o silêncio.

    A bomba rotaciona (`VOLTA_DA_SEQUENCIA = 16`); o terceiro corpo tem de
    obedecer à mesma disciplina, senão ele introduz uma variável NOVA no par —
    e um par com duas variáveis não separa nada.
    """
    for seq in (0, 1, 15, 16, 17):
        pkt = af.montar_com_o_common_preservado(QUADROS, COMMON, seq=seq)
        assert pkt[1] == (seq & 0x0F) << 4, f"seq={seq} saiu como 0x{pkt[1]:02x}"


# ---------------------------------------------------------------------------
# MORDIDA 5 — E TUDO ISSO NO CAMINHO QUE ELA VAI RODAR
# ---------------------------------------------------------------------------
#
# AS QUATRO MORDIDAS ACIMA CHAMAM `montar_com_o_common_preservado` DIRETO, e
# passam o `common` na mão. **O ensaio não passa por ali.** Ele vai por
# `BombaDeSomPeloRadio.um_report`, que chamava `arranjo.montar` SEM `common` —
# e o ramo `common_preservado` caía no `bytes(COMMON_LEN)` do valor omitido.
#
# Medido em 08/09/2026, no caminho do `--escrever`:
#
#     common no 0x31 do produto : flag0 e flag1 ligados, volume e rota pedidos
#     common no corpo do ensaio : todos os 47 bytes em zero — pede NADA
#
# Um `common` zerado tem os bits de validação apagados: ele não pede rota, não
# pede volume, não pede pré-amp. E o mapa diz que POR RÁDIO O KERNEL NÃO
# ESCREVE NENHUM DOS TRÊS. A passada teria custado a orelha dela para medir um
# corpo que não pedia nada — e o silêncio dela seria lido como "o aparelho não
# faz", que é exatamente o que o par com/sem existe para NÃO concluir.
#
# A REGRA QUE ISSO DEIXA: uma afirmação sobre bytes tem de ser medida no
# caminho que a pessoa vai rodar, não no atalho que a régua acha cômodo.


def _bomba(common: bytes | None) -> af.BombaDeSomPeloRadio:
    """A bomba do ensaio, com um encoder de mentira. **Nasce SECA.**"""
    quadro = b"\xcc" * af.BYTES_POR_QUADRO_OPUS
    return af.BombaDeSomPeloRadio(
        arranjo=af.ARRANJO_POR_NOME["common-preservado"],
        fonte=lambda n: b"\x00" * n,
        codificador=type("Enc", (), {"codificar": lambda self, pcm: quadro})(),
        common=common,
    )


def test_o_corpo_que_a_bomba_monta_leva_o_common_do_produto() -> None:
    """[3..49] do report da BOMBA é o mesmo do 0x31 do produto. Byte a byte.

    ARRANQUE A CURA (tire o `common=self.common` de
    `BombaDeSomPeloRadio.um_report`) e esta régua REPROVA dizendo que o
    envelope saiu zerado.
    """
    envelope = af.common_de_audio()
    report = _bomba(envelope).um_report()
    assert report is not None
    do_produto = bytes(build_bt_report(envelope)[3 : 3 + COMMON_LEN])
    assert bytes(report[3 : 3 + COMMON_LEN]) == do_produto, (
        "o corpo que a BOMBA monta não leva o mesmo `common` que o 0x31 do "
        f"produto: {bytes(report[3:15]).hex()} != {do_produto[:12].hex()}"
    )
    assert bytes(report[3 : 3 + COMMON_LEN]) != bytes(COMMON_LEN), (
        "o envelope saiu ZERADO — ele não pede rota, volume nem pré-amp, e o "
        "corpo iria ao fio pedindo NADA"
    )
    assert report[2] == BT_TAG


def test_a_bomba_recusa_o_corpo_preservado_sem_common() -> None:
    """Ausência é resposta: um envelope que não pede nada não vai ao fio.

    Deixar o padrão zerado passar seria um instrumento dando VERMELHO sobre
    nada — e mais caro que os que dão verde, porque quem paga é a orelha dela
    numa passada que não mediu coisa nenhuma.

    Troque o `raise` por um `common = bytes(COMMON_LEN)` e esta régua REPROVA.
    """
    with pytest.raises(ValueError, match="pedindo NADA"):
        _bomba(None)


def test_o_envelope_do_ensaio_pede_os_tres_campos_que_o_mapa_nomeia() -> None:
    """Rota, volume e pré-amp — os TRÊS, com os bits de validação ligados.

    O mapa (`audio.alto_falante*`) é explícito: são três campos, o kernel
    escreve os três juntos, e **por rádio ele não escreve nenhum**. Um
    envelope que ligasse o bit e deixasse o byte em zero mandaria "volume
    zero" com cara de autoridade — a mesma classe do keepalive de vibração
    que este projeto já pagou.

    O volume é o único número desta bancada com veredito de ORELHA: 85 =
    "bep bep bep", 0 = "mudo" (15/08/2026).
    """
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
    """A cicatriz de 02/08/2026: o `common[7]` carrega a rota E o mic.

    Escrever o byte com base ZERO fez o `parec` do microfone dela cair de
    131.072 bytes para **zero**. Um ensaio de ALTO-FALANTE que calasse o
    microfone dela de passagem seria o pior desfecho possível — ela tem quatro
    controles na mesa e o microfone pelo rádio é a única coisa que já
    funcionou.

    Zere o `AUDIO_CONTROL_BASE_SEGURA` de `common_de_audio` e esta régua
    REPROVA.
    """
    from hefesto_dualsense4unix.core import ds_output_report as rep

    envelope = af.common_de_audio()
    assert envelope[rep.COMMON_AUDIO_PATH] & rep.AUDIO_CONTROL_FORCE_INTERNAL_MIC, (
        "o `common[7]` foi escrito com base zero e apagou o caminho do "
        f"microfone: 0x{envelope[rep.COMMON_AUDIO_PATH]:02x}"
    )


def test_os_arranjos_externos_continuam_sem_common() -> None:
    """A recusa é SÓ do corpo que preserva — os dois candidatos não mudam.

    Eles põem a tag do AudioControl no byte [2] e não têm onde guardar um
    `common`. Exigir um deles seria inventar campo em leitura de fonte
    externa, que é o oposto do que este módulo protege.
    """
    for arranjo in af.ARRANJOS:
        bomba = af.BombaDeSomPeloRadio(arranjo=arranjo, fonte=lambda n: b"\x00" * n)
        assert bomba.common is None
        assert arranjo.common_preservado is False
