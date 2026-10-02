"""CANAL-POR-CONTROLE — LUZ: o caminho do RÁDIO escrito no mapa é o que o produto MONTA."""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.lightbar_gatilho import build_bt_lightbar_report

MAPA = Path(__file__).resolve().parents[2] / "docs" / "data" / "mapa-controles.csv"

AFIRMACAO_DE_OFFSET = re.compile(
    r"common\[(\d+)(?:\.\.(\d+))?\]\s*=\s*report\[(\d+)(?:\.\.(\d+))?\]"
)

COLUNAS_COM_ENDERECO = ("offset", "comando")

#: As linhas de luz do DualSense cujo caminho por rádio é o report ``0x31``
LINHAS_DO_0X31 = (
    "luz.lightbar.cor@dualsense",
    "luz.led_jogador@dualsense",
    "luz.led_jogador.escrita_hefesto@dualsense",
    "luz.led_jogador.quinto@dualsense",
    "luz.led_jogador.brilho@dualsense",
    "luz.lightbar.fade@dualsense",
    "luz.lightbar.release_leds@dualsense",
    "luz.led_microfone@dualsense",
)

COR_DE_PROVA = (0x2A, 0x40, 0xC8)

PADRAO_DE_PROVA = (True, False, True, True, False)


def _linhas_de_luz() -> list[dict[str, str]]:
    with MAPA.open(encoding="utf-8", newline="") as fh:
        return [
            linha
            for linha in csv.DictReader(fh)
            if linha["familia"] == "luz" and linha["controle"] == "dualsense"
        ]


def _por_id() -> dict[str, dict[str, str]]:
    return {linha["id"]: linha for linha in _linhas_de_luz()}


def _deslocamento_medido(construir) -> int:
    """Onde o ``common`` cai dentro do envelope — MEDIDO, nunca digitado."""
    marca = bytes(range(1, rep.COMMON_LEN + 1))
    report = bytes(construir(marca))
    onde = report.find(marca)
    assert onde >= 0, "o common não aparece inteiro dentro do envelope"
    return onde


DESLOCAMENTO = {
    "cabo": _deslocamento_medido(rep.build_usb_report),
    "radio": _deslocamento_medido(rep.build_bt_report),
}


def test_o_offset_escrito_no_mapa_bate_com_o_envelope_de_verdade() -> None:
    """Toda ``common[X] = report[Y]`` da família luz respeita o envelope real."""
    achados = 0
    for linha in _linhas_de_luz():
        for lado, deslocamento in DESLOCAMENTO.items():
            for coluna in COLUNAS_COM_ENDERECO:
                texto = linha.get(f"{lado}_{coluna}", "") or ""
                for casamento in AFIRMACAO_DE_OFFSET.finditer(texto):
                    achados += 1
                    inicio_common = int(casamento.group(1))
                    inicio_report = int(casamento.group(3))
                    assert inicio_report - inicio_common == deslocamento, (
                        f"{linha['id']} · {lado}_{coluna}: a célula diz "
                        f"`{casamento.group(0)}`, e o envelope de verdade põe o "
                        f"common em report[{deslocamento}..] — o deslocamento "
                        f"medido é {deslocamento}, não "
                        f"{inicio_report - inicio_common}"
                    )
                    fim_common = casamento.group(2)
                    fim_report = casamento.group(4)
                    if fim_common and fim_report:
                        assert int(fim_report) - int(fim_common) == deslocamento, (
                            f"{linha['id']} · {lado}_{coluna}: a faixa "
                            f"`{casamento.group(0)}` começa certo e termina "
                            "errado"
                        )
    assert achados >= 20, (
        "as afirmações de offset da família luz sumiram do mapa — esta régua "
        f"achou só {achados}; alguém apagou o caminho de byte em vez de o "
        "corrigir"
    )


@pytest.mark.parametrize("ident", LINHAS_DO_0X31)
def test_toda_linha_de_luz_com_rota_no_radio_diz_o_byte(ident: str) -> None:
    """Nenhuma destas linhas volta a ser um travessão."""
    linha = _por_id()[ident]
    for coluna in ("radio_report_id", "radio_offset"):
        valor = (linha.get(coluna, "") or "").strip()
        assert valor and valor != "—", (
            f"{ident}: `{coluna}` voltou a ser vazio/travessão — o caminho do "
            "rádio desta luz existe no código e tem de ter endereço no mapa"
        )


@pytest.mark.parametrize("ident", LINHAS_DO_0X31)
def test_o_report_id_do_radio_e_o_0x31_do_codigo(ident: str) -> None:
    """O número do report não é digitado no mapa: ele é o do ``ds_output_report``."""
    linha = _por_id()[ident]
    esperado = f"0x{rep.BT_REPORT_ID:02x}"
    assert esperado in linha["radio_report_id"].lower(), (
        f"{ident}: `radio_report_id` = {linha['radio_report_id']!r}, e o report "
        f"de output BT deste projeto é {esperado} "
        "(`core/ds_output_report.BT_REPORT_ID`)"
    )


def test_a_cor_sai_no_byte_que_a_celula_do_radio_promete() -> None:
    """Os índices da célula de ``luz.lightbar.cor@dualsense`` CARREGAM a cor."""
    celula = _por_id()["luz.lightbar.cor@dualsense"]["radio_offset"]
    faixa = AFIRMACAO_DE_OFFSET.search(celula)
    assert faixa is not None and faixa.group(4), (
        "a célula do rádio da cor deixou de nomear a FAIXA `common[44..46] = "
        f"report[..]`: {celula[:120]!r}"
    )
    primeiro = int(faixa.group(3))

    report = build_bt_lightbar_report(COR_DE_PROVA, None)
    assert report[0] == rep.BT_REPORT_ID
    lido = tuple(report[primeiro : primeiro + 3])
    assert lido == COR_DE_PROVA, (
        f"a célula manda ler report[{primeiro}..{primeiro + 2}] e ali está "
        f"{lido}, não a cor pedida {COR_DE_PROVA} — o endereço do mapa não é o "
        "do report que o produto monta"
    )

    bit = AFIRMACAO_DE_OFFSET.findall(celula)
    endereco_do_flag = next(
        int(alvo) for origem, _, alvo, _ in bit if int(origem) == 1
    )
    assert report[endereco_do_flag] & rep.VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE, (
        f"report[{endereco_do_flag}] não traz o bit 0x04 do flag1 — a cor iria "
        "no byte certo sem autorização, e o firmware a ignoraria"
    )


@pytest.mark.parametrize(
    "ident",
    (
        "luz.led_jogador@dualsense",
        "luz.led_jogador.escrita_hefesto@dualsense",
        "luz.led_jogador.quinto@dualsense",
    ),
)
def test_o_numero_do_jogador_sai_no_byte_que_a_celula_do_radio_promete(
    ident: str,
) -> None:
    """``common[43] = report[46]`` carrega o bitmask das cinco lâmpadas."""
    celula = _por_id()[ident]["radio_offset"]
    pares = [
        (int(origem), int(alvo))
        for origem, _, alvo, _ in AFIRMACAO_DE_OFFSET.findall(celula)
    ]
    assert pares, f"{ident}: a célula do rádio não nomeia byte nenhum"
    endereco_do_numero = next(
        (alvo for origem, alvo in pares if origem == 43), None
    )
    assert endereco_do_numero is not None, (
        f"{ident}: a célula do rádio deixou de nomear o `common[43]`, que é "
        "onde o número do jogador mora no report"
    )

    report = build_bt_lightbar_report(None, PADRAO_DE_PROVA)
    esperado = sum(1 << i for i, aceso in enumerate(PADRAO_DE_PROVA) if aceso)
    assert report[endereco_do_numero] == esperado, (
        f"{ident}: a célula manda ler report[{endereco_do_numero}] e ali está "
        f"{report[endereco_do_numero]:#04x}, não o bitmask {esperado:#04x}"
    )

    endereco_do_flag = next((alvo for origem, alvo in pares if origem == 1), None)
    if endereco_do_flag is not None:
        assert (
            report[endereco_do_flag]
            & rep.VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE
        ), (
            f"{ident}: report[{endereco_do_flag}] não traz o bit 0x10 do flag1 "
            "— o número iria no byte certo sem autorização"
        )


@pytest.mark.parametrize(
    ("ident", "byte_do_dado", "bit_do_flag2"),
    (
        ("luz.led_jogador.brilho@dualsense", 42, rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE),
        ("luz.lightbar.fade@dualsense", 41, rep.VALID_FLAG2_LIGHTBAR_SETUP_CONTROL_ENABLE),
    ),
)
def test_o_brilho_e_o_fade_dizem_o_byte_e_o_bit_que_o_valida(
    ident: str, byte_do_dado: int, bit_do_flag2: int
) -> None:
    """As duas dívidas do rádio dizem ONDE escrever E o que autoriza o campo."""
    celula = _por_id()[ident]["radio_offset"]
    pares = {
        int(origem): int(alvo)
        for origem, _, alvo, _ in AFIRMACAO_DE_OFFSET.findall(celula)
    }
    assert byte_do_dado in pares, (
        f"{ident}: a célula do rádio não nomeia `common[{byte_do_dado}]`"
    )
    assert rep.COMMON_VALID_FLAG2 in pares, (
        f"{ident}: a célula do rádio nomeia o byte de dado mas não o "
        f"`common[{rep.COMMON_VALID_FLAG2}]` (valid_flag2) que o autoriza — "
        "quem implementar escreve o campo e o firmware o ignora"
    )

    common = bytearray(rep.COMMON_LEN)
    common[byte_do_dado] = 0x5A
    common[rep.COMMON_VALID_FLAG2] = bit_do_flag2
    report = rep.build_bt_report(common)

    assert report[pares[byte_do_dado]] == 0x5A, (
        f"{ident}: report[{pares[byte_do_dado]}] não é o `common"
        f"[{byte_do_dado}]` no envelope do rádio"
    )
    assert report[pares[rep.COMMON_VALID_FLAG2]] & bit_do_flag2, (
        f"{ident}: report[{pares[rep.COMMON_VALID_FLAG2]}] não é o valid_flag2 "
        "no envelope do rádio"
    )


def test_a_supressao_do_fluxo_continua_registrada_na_celula_da_cor() -> None:
    """O que a célula GANHOU não pode ter apagado o que ela já dizia."""
    celula = _por_id()["luz.lightbar.cor@dualsense"]["radio_offset"].lower()
    assert "supress" in celula, (
        "a célula do rádio da cor deixou de registrar que, no report do FLUXO, "
        "esses mesmos bytes saem ZERADOS — é o LIGHTBAR-BT-KEEPALIVE-01, e "
        "sem essa metade a célula convida a religar a escrita de LED no "
        "report_thread"
    )
    assert "avuls" in celula, (
        "a célula do rádio da cor deixou de dizer que os bytes que ela nomeia "
        "são os do 0x31 AVULSO — sem isso ela volta a ser lida como uma "
        "descrição do report do fluxo, que é o que ela era até 03/09/2026"
    )
