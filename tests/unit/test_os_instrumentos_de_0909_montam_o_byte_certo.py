"""Os instrumentos de bancada de 09/09 montam o byte certo, no report certo, e só ele.

Três decisões dela (*"1-b;2b;3-c"*) viraram três instrumentos que escrevem UM
byte do `common` — fone (`[4]`), brilho de hardware (`[42]`), microfone
(`[6]`) — mais o do envelope do som por rádio e o censo dos nós. A parte que
toca o aparelho é dela, na bancada. A parte que se prova aqui é a que já
enganou esta casa: **o byte na posição errada, o bit de autorização
esquecido, o report do transporte errado**. Uma régua que passasse com o byte
em `[5]` em vez de `[4]` mediria o alto-falante achando que mede o fone.

MORDE: trocar `COMMON_HEADPHONE_VOLUME` por 5 no instrumento do fone; apagar o
`c[0] |= VALID_FLAG0_*` de qualquer um; trocar `build_bt_report` por
`build_usb_report` em `report_para`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
ENSAIOS = RAIZ / "scripts" / "ensaios"


def _instrumento(nome: str):
    caminho = ENSAIOS / f"{nome}.py"
    if str(ENSAIOS) not in sys.path:
        sys.path.insert(0, str(ENSAIOS))
    apelido = f"instrumento_{nome}"
    spec = importlib.util.spec_from_file_location(apelido, caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[apelido] = modulo  # os dataclasses resolvem anotações por aqui
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def broker():
    return _instrumento("escrita_pelo_broker")


@pytest.fixture(scope="module")
def rep():
    from hefesto_dualsense4unix.core import ds_output_report

    return ds_output_report


# ---------------------------------------------------------------------------
# escrita_pelo_broker — o report do transporte
# ---------------------------------------------------------------------------


def test_o_common_vazio_e_zerado_e_tem_47(broker, rep):
    c = broker.common_vazio()
    assert len(c) == rep.COMMON_LEN == 47
    assert not any(c)


def test_o_cabo_ganha_o_0x02_de_64_com_o_common_em_1_a_47(broker, rep):
    c = broker.common_vazio()
    c[4] = 0x7F
    r = broker.report_para(broker.CABO, c)
    assert len(r) == rep.USB_REPORT_LEN == 64
    assert r[0] == rep.USB_REPORT_ID == 0x02
    assert r[1 : 1 + 47] == bytes(c)


def test_o_radio_ganha_o_0x31_de_78_com_tag_seq_e_crc_do_produto(broker, rep):
    c = broker.common_vazio()
    c[42] = 2
    r = broker.report_para(broker.RADIO, c, seq=5)
    assert len(r) == rep.BT_REPORT_LEN == 78
    assert r[0] == rep.BT_REPORT_ID == 0x31
    assert r[1] == 5 << 4
    assert r[2] == rep.BT_TAG == 0x10
    assert r[3 : 3 + 47] == bytes(c)
    assert int.from_bytes(r[-4:], "little") == rep.bt_crc32(r[:-4])


def test_transporte_desconhecido_e_erro_e_nao_palpite(broker):
    with pytest.raises(ValueError):
        broker.report_para("vpad (sem transporte)", broker.common_vazio())


def test_a_mascara_da_casa_zera_os_octetos_4_e_5(broker):
    assert broker.mascarar("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:00:00:ff"
    assert broker.mascarar("nao-e-mac") == "nao-e-mac"


def test_a_linha_do_caderno_segue_o_cabecalho_do_csv(broker):
    cabecalho = (RAIZ / "docs" / "data" / "ensaios.csv").read_text(encoding="utf-8").splitlines()[0]
    assert cabecalho.split(",") == list(broker.COLUNAS_DO_CADERNO), (
        "o cabeçalho do caderno mudou e a linha proposta pelos instrumentos ficaria fora de ordem"
    )
    linha = broker.linha_do_caderno(
        id="x", linha_id="y", nota="tem, vírgula", quando="2026-09-09T00:00:00"
    )
    campos = linha.split(",")
    assert campos[0] == "x" and campos[1] == "y"
    assert '"tem, vírgula"' in linha


# ---------------------------------------------------------------------------
# o fone — common[4] e SÓ ele, com o bit 0x10
# ---------------------------------------------------------------------------


def test_o_fone_escreve_o_byte_4_com_o_bit_0x10_e_nada_mais(rep):
    fone = _instrumento("o_fone_tem_volume_proprio")
    c = fone.common_do_passo(0x40, com_bit=True, alto_falante=None)
    assert c[rep.COMMON_HEADPHONE_VOLUME] == 0x40 and rep.COMMON_HEADPHONE_VOLUME == 4
    assert c[0] == rep.VALID_FLAG0_HEADPHONE_VOLUME == 0x10
    assert c[rep.COMMON_SPEAKER_VOLUME] == 0, "o alto-falante só é tocado com --alto-falante"
    resto = bytes(c[1:4]) + bytes(c[5:])
    assert not any(resto), "só o byte do fone e o flag0 existem neste common"


def test_o_fone_sem_o_bit_manda_o_byte_sem_autorizacao(rep):
    fone = _instrumento("o_fone_tem_volume_proprio")
    c = fone.common_do_passo(0x00, com_bit=False, alto_falante=None)
    assert c[0] == 0 and c[4] == 0


def test_o_fone_com_alto_falante_fixo_liga_o_0x20_tambem(rep):
    fone = _instrumento("o_fone_tem_volume_proprio")
    c = fone.common_do_passo(0x7F, com_bit=True, alto_falante=0x40)
    assert c[0] == (rep.VALID_FLAG0_HEADPHONE_VOLUME | rep.VALID_FLAG0_SPEAKER_VOLUME)
    assert c[4] == 0x7F and c[5] == 0x40


def test_o_fone_recusa_acima_do_teto():
    fone = _instrumento("o_fone_tem_volume_proprio")
    with pytest.raises(ValueError):
        fone.common_do_passo(0x80, com_bit=True, alto_falante=None)


def test_os_cinco_passos_do_fone_tem_um_positivo_e_um_negativo_com_o_bit():
    fone = _instrumento("o_fone_tem_volume_proprio")
    com_bit = {p: v for p, (v, bit, _) in fone.PASSOS.items() if bit}
    assert max(com_bit.values()) == 0x7F and min(com_bit.values()) == 0x00
    assert any(not bit for _, bit, _ in fone.PASSOS.values()), "falta o passo SEM o bit"


# ---------------------------------------------------------------------------
# o brilho de hardware — common[42], flag2 bit0, e a cor com o bit da barra
# ---------------------------------------------------------------------------


def test_o_brilho_escreve_o_42_com_o_flag2_bit0_e_a_cor_com_o_bit_da_barra(rep):
    brilho = _instrumento("o_brilho_de_hardware_da_barra")
    c = brilho.common_do_nivel(2, com_bit=True, cor=(255, 255, 255))
    assert c[42] == 2 and brilho.COMMON_LED_BRIGHTNESS == 42
    assert c[rep.COMMON_VALID_FLAG2] == rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE == 0x01
    assert rep.COMMON_VALID_FLAG2 == 38
    assert c[1] == rep.VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE
    assert (c[44], c[45], c[46]) == (255, 255, 255)
    assert c[0] == 0, "nenhum bit de flag0: brilho não é áudio nem vibração"


def test_o_brilho_sem_o_bit_deixa_o_flag2_zerado():
    brilho = _instrumento("o_brilho_de_hardware_da_barra")
    c = brilho.common_do_nivel(2, com_bit=False, cor=(255, 255, 255))
    assert c[38] == 0 and c[42] == 2


def test_o_brilho_recusa_nivel_fora_dos_tres():
    brilho = _instrumento("o_brilho_de_hardware_da_barra")
    with pytest.raises(ValueError):
        brilho.common_do_nivel(3, com_bit=True, cor=(0, 0, 0))


def test_a_escada_padrao_do_brilho_comeca_e_termina_na_base():
    brilho = _instrumento("o_brilho_de_hardware_da_barra")
    assert brilho.ESCADA_PADRAO[0] == 0 and brilho.ESCADA_PADRAO[-1] == 0
    assert 2 in brilho.ESCADA_PADRAO


# ---------------------------------------------------------------------------
# o microfone — common[6], flag0 0x40, e a razão que decide
# ---------------------------------------------------------------------------


def test_o_mic_escreve_o_6_com_o_bit_0x40_e_so_ele(rep):
    mic = _instrumento("o_byte_do_microfone_muda_a_captura")
    c = mic.common_do_nivel(0x20, com_bit=True)
    assert c[rep.COMMON_MIC_VOLUME] == 0x20 and rep.COMMON_MIC_VOLUME == 6
    assert c[0] == rep.VALID_FLAG0_MIC_VOLUME == 0x40
    assert not any(bytes(c[1:6]) + bytes(c[7:]))


def test_o_mic_recusa_acima_do_teto_real_0x40():
    mic = _instrumento("o_byte_do_microfone_muda_a_captura")
    with pytest.raises(ValueError):
        mic.common_do_nivel(0x41, com_bit=True)


def _captura(mic, pico: int):
    c = mic.Captura(rotulo="x", dispositivo="hw:9,0")
    c.amostras, c.nao_zero, c.pico = 1000, 900, pico
    return c


def test_o_veredito_do_mic_obedece_acima_de_1_5_e_nao_sabe_no_meio():
    mic = _instrumento("o_byte_do_microfone_muda_a_captura")
    def frase(pico_alto: int) -> str:
        return mic.veredito([(0x00, _captura(mic, 1000)), (0x40, _captura(mic, pico_alto))])

    assert frase(2000).startswith("OBEDECE")
    assert frase(1300).startswith("NÃO SEI")
    assert frase(1050).startswith("NÃO OBEDECE")


def test_o_veredito_do_mic_sem_voz_e_sem_medicao():
    mic = _instrumento("o_byte_do_microfone_muda_a_captura")
    muda = mic.Captura(rotulo="x", dispositivo="hw:9,0")
    assert mic.veredito([(0x00, muda), (0x40, muda)]).startswith("SEM MEDIÇÃO")


# ---------------------------------------------------------------------------
# o envelope do som no rádio — o ioctl certo e o negativo certo
# ---------------------------------------------------------------------------


def test_o_hidiocsoutput_e_o_do_cabecalho_do_kernel():
    env = _instrumento("o_envelope_do_som_no_radio")
    # _IOC(_IOC_READ|_IOC_WRITE, 'H', 0x0B, 78) — dir nos bits 30-31, len em 16-29
    assert env.hidiocsoutput(78) == (3 << 30) | (78 << 16) | (ord("H") << 8) | 0x0B


def test_o_crc_corrompido_muda_so_os_quatro_ultimos_bytes():
    env = _instrumento("o_envelope_do_som_no_radio")
    original = bytes(range(78))
    ruim = env.corromper_crc(original)
    assert ruim[:-4] == original[:-4] and ruim[-4:] != original[-4:]


def test_o_report_de_cor_do_passo_0_e_um_0x31_valido_com_a_cor(rep):
    env = _instrumento("o_envelope_do_som_no_radio")
    r = env.report_de_cor(0, 0, 255, seq=3)
    assert r[0] == 0x31 and len(r) == 78 and r[1] == 3 << 4
    assert (r[3 + 44], r[3 + 45], r[3 + 46]) == (0, 0, 255)
    assert r[3 + 1] == rep.VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE
    assert int.from_bytes(r[-4:], "little") == rep.bt_crc32(r[:-4])


def test_o_tom_sai_em_quadros_de_10_ms_de_1920_bytes():
    env = _instrumento("o_envelope_do_som_no_radio")
    quadros = env.pcm_do_tom(0.05)
    assert len(quadros) == 5 and all(len(q) == 1920 for q in quadros)


# ---------------------------------------------------------------------------
# os nós de som — o parser do pactl e a falta nomeada
# ---------------------------------------------------------------------------

PACTL_SINKS = """Sink #61
\tState: IDLE
\tName: alsa_output.usb-Sony_Interactive_Entertainment_Wireless_Controller-00.analog-surround-40
\tDescription: DualSense wireless controller (PS5) Analog Surround 4.0
\tProperties:
\t\tdevice.bus = "usb"
Sink #70
\tState: RUNNING
\tName: hefesto_controle_1
\tDescription: Alto-falante do Controle 1
"""


def test_o_parser_do_pactl_separa_blocos_e_le_nome_e_descricao():
    nos = _instrumento("os_nos_de_som_por_controle")
    blocos = nos.blocos_longos(PACTL_SINKS)
    assert [b["Name"] for b in blocos] == [
        "alsa_output.usb-Sony_Interactive_Entertainment_Wireless_Controller-00.analog-surround-40",
        "hefesto_controle_1",
    ]
    assert blocos[1]["Description"] == "Alto-falante do Controle 1"
    assert blocos[0]["device.bus"] == "usb"


def test_o_loopback_e_lido_dos_modulos_curtos():
    nos = _instrumento("os_nos_de_som_por_controle")
    saida = (
        "12\tmodule-loopback\tsource=x.monitor sink=hefesto_controle_1\n"
        "13\tmodule-null-sink\tsink_name=y\n"
    )
    assert nos.loopbacks(saida) == ["source=x.monitor sink=hefesto_controle_1"]


def test_os_nomes_dos_nos_sao_perguntados_ao_produto():
    """Os dois rótulos estavam DIGITADOS no censo. Agora ele pergunta ao dono.

    TRES-CONTAS-PARA-UM-NUMERO-01 §6 (12/09/2026). Esta régua afirmava
    `nos.NOME_DO_ALTO_FALANTE == "Alto-falante do Controle"` — ela comparava
    duas digitações, a do instrumento e a dela mesma, e nenhuma das duas era o
    produto. Mude o rótulo em `integrations/` e o par continuava verde enquanto
    o censo passava a dizer «NÃO EXISTE» a um nó que está na lista dela.

    MORDIDA: volte a digitar o rótulo em `_rotulo_do_produto` e este teste
    continua verde — mas então mude a constante no produto e ele reprova, que é
    o que a versão anterior não sabia fazer.
    """
    from hefesto_dualsense4unix.integrations.alto_falante_bt import (
        NOME_DO_ALTO_FALANTE_DO_CONTROLE,
    )
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
        NOME_DO_MICROFONE_DO_CONTROLE,
    )

    nos = _instrumento("os_nos_de_som_por_controle")
    assert nos._rotulo_do_produto("saida") == NOME_DO_ALTO_FALANTE_DO_CONTROLE
    assert nos._rotulo_do_produto("entrada") == NOME_DO_MICROFONE_DO_CONTROLE


def test_o_censo_casa_o_no_pelo_nome_de_dentro_e_nunca_pela_prosa():
    """Renomeie o `Description` à mão e o censo continua acertando o dono.

    TRES-CONTAS-PARA-UM-NUMERO-01 §6, e a ressalva dela é o que decide:

        *"aí é foda pq a ideia não é termos nada focado pro meu caso apenas,
        mas como produto que possa funcionar com outra pessoa."*
        <!-- noqa-acento: citação literal dela, palavra por palavra -->

    Medido em 09/09 na mesa dela: o mesmo `hefesto_mic_<hex6>` foi atribuído ao
    controle do CABO numa corrida e ao do RÁDIO na seguinte, sem nada ter mudado
    no áudio — o assento andou, o texto do `Description` andou junto, e o censo
    seguiu o texto. A âncora passou a ser o NOME do nó, que o daemon escreve a
    partir do endereço.

    MORDIDA: faça `_casa` voltar a aceitar o texto do `Description` (ou casar por
    substring do nome) e a última asserção cai.
    """
    from hefesto_dualsense4unix.integrations import canal_do_microfone

    nos = _instrumento("os_nos_de_som_por_controle")
    do_cabo = canal_do_microfone.nome_do_canal("aa:bb:cc:00:00:11")
    do_radio = canal_do_microfone.nome_do_canal("aa:bb:cc:00:00:22")
    assert do_cabo and do_radio and do_cabo != do_radio

    # o nó do CABO, com o `Description` que o assento do RÁDIO produziria
    assert nos._casa(do_cabo, do_cabo) is True
    assert nos._casa(do_radio, do_cabo) is False
    # prosa não casa com nada, nem a que descreve o próprio nó
    assert nos._casa("Microfone do Controle 1", do_cabo) is False
    # e sem nome de dentro (controle sem identidade legível) a resposta é NÃO
    assert nos._casa(do_cabo, "") is False
    # nem por substring: um vizinho com um dígito a mais não é o dono
    assert nos._casa(do_cabo + "1", do_cabo) is False
