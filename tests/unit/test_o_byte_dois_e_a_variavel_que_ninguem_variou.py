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
