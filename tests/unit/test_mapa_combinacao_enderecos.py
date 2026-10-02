"""Os endereços que a frente COMBINAÇÃO escreveu no mapa têm de bater com o"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core.ds_output_report import (
    BT_REPORT_ID,
    BT_TAG,
    COMMON_LEN,
    USB_REPORT_ID,
    build_bt_report,
    build_usb_report,
)

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
DOC = (
    RAIZ
    / "docs"
    / "protocol"
    / "combinacao-varios-controles-o-que-e-do-aparelho.md"
)

BASE_POR_LADO = {"cabo": 1, "radio": 3}

CHAVES = (
    "combinacao.cabo_e_radio.entrada",
    "combinacao.cabo_e_radio.saida",
    "combinacao.cabo_e_radio.taxa",
    "combinacao.dois_no_radio.saida",
    "combinacao.rumble_simultaneo",
    "combinacao.slot_jogador.estabilidade",
    "combinacao.tres_na_mesa",
)

GRAUS_SEM_APARELHO = frozenset({"afirmado-no-doc", "inferido-do-codigo"})

PAR_COMMON_REPORT = re.compile(r"common\[(\d+)\]\s*=\s*report\[(\d+)\]")

LEDS_DE_JOGADOR = {
    1: 0b00100,
    2: 0b01010,
    3: 0b10101,
    4: 0b11011,
    5: 0b11111,
}


def _linhas_do_mapa() -> dict[str, dict[str, str]]:
    with MAPA.open(newline="", encoding="utf-8") as fh:
        return {
            linha["chave"]: linha
            for linha in csv.DictReader(fh)
            if linha["controle"] == "dualsense" and linha["chave"] in CHAVES
        }


MAPA_DA_FRENTE = _linhas_do_mapa()


def test_as_sete_linhas_existem() -> None:
    """Se uma chave sumir do mapa, os nós abaixo passariam VAZIOS."""
    assert set(MAPA_DA_FRENTE) == set(CHAVES), (
        "a frente COMBINAÇÃO ataca sete linhas do `dualsense`; achei "
        f"{sorted(MAPA_DA_FRENTE)}"
    )


def test_a_base_declarada_e_a_que_o_produto_monta() -> None:
    """`BASE_POR_LADO` não é constante mágica — é o que o produto faz."""
    for posicao in (0, 2, 3, 43, 46):
        common = bytearray(COMMON_LEN)
        common[posicao] = 0xA7

        usb = build_usb_report(common)
        assert usb[0] == USB_REPORT_ID
        assert usb[BASE_POR_LADO["cabo"] + posicao] == 0xA7, (
            f"no cabo, common[{posicao}] devia cair em "
            f"report[{BASE_POR_LADO['cabo'] + posicao}]"
        )

        bt = build_bt_report(common)
        assert bt[0] == BT_REPORT_ID
        assert bt[2] == BT_TAG, "o tag mágico 0x10 tem de estar em report[2]"
        assert bt[BASE_POR_LADO["radio"] + posicao] == 0xA7, (
            f"no rádio, common[{posicao}] devia cair em "
            f"report[{BASE_POR_LADO['radio'] + posicao}]"
        )


@pytest.mark.parametrize("chave", CHAVES)
@pytest.mark.parametrize("lado", sorted(BASE_POR_LADO))
def test_a_aritmetica_do_common_no_mapa(chave: str, lado: str) -> None:
    """Todo `common[N] = report[M]` escrito no mapa tem de fechar a conta."""
    linha = MAPA_DA_FRENTE[chave]
    base = BASE_POR_LADO[lado]
    texto = " ".join(
        (linha.get(f"{lado}_{sufixo}") or "")
        for sufixo in ("offset", "comando", "detalhe", "ressalva")
    )
    pares = PAR_COMMON_REPORT.findall(texto)
    for n_texto, m_texto in pares:
        n, m = int(n_texto), int(m_texto)
        assert 0 <= n < COMMON_LEN, (
            f"{chave} ({lado}): common[{n}] está fora do bloco de "
            f"{COMMON_LEN} bytes"
        )
        assert m == n + base, (
            f"{chave} ({lado}): o mapa diz `common[{n}] = report[{m}]`, mas no "
            f"envelope de {lado} o common começa em report[{base}], logo o "
            f"certo é report[{n + base}]"
        )


def test_o_mostrador_do_numero_de_jogador_esta_no_lugar() -> None:
    """`common[43]` nos dois lados — e o mapa tem de dizer os dois endereços."""
    linha = MAPA_DA_FRENTE["combinacao.slot_jogador.estabilidade"]
    esperado = {
        "cabo": f"common[43] = report[{43 + BASE_POR_LADO['cabo']}]",
        "radio": f"common[43] = report[{43 + BASE_POR_LADO['radio']}]",
    }
    for lado, trecho in esperado.items():
        texto = (linha[f"{lado}_offset"] or "")
        assert trecho in texto, (
            f"a linha do número de jogador tem de dizer `{trecho}` no lado "
            f"{lado}; ela diz {texto!r}"
        )


def test_os_cinco_desenhos_do_led_de_jogador() -> None:
    """Os cinco valores do mapa recalculados pela regra de centralizar."""
    texto = (
        MAPA_DA_FRENTE["combinacao.slot_jogador.estabilidade"]["cabo_comando"]
        or ""
    )
    for jogador, bits in LEDS_DE_JOGADOR.items():
        assert bin(bits).count("1") == jogador, (
            f"a tabela deste teste está errada: jogador {jogador} devia acender "
            f"{jogador} LEDs"
        )
        assert f"{jogador} = 0x{bits:02X}" in texto, (
            f"o mapa devia dizer `{jogador} = 0x{bits:02X}` para o LED de "
            "jogador"
        )
    assert "0x20" in texto, (
        "o bit 0x20 (aplicar na hora, sem fade) é o que o SDL3 acrescenta e o "
        "kernel não usa — ele não pode sumir da célula"
    )


def test_o_dualsense_nao_tem_canal_de_taxa_e_o_mapa_diz_isso() -> None:
    """A ausência é ACHADO, e ela precisa de rede."""
    linha = MAPA_DA_FRENTE["combinacao.cabo_e_radio.taxa"]
    for lado in BASE_POR_LADO:
        texto = (linha[f"{lado}_offset"] or "") + (linha[f"{lado}_comando"] or "")
        assert "NÃO" in texto.upper() or "NAO" in texto.upper(), (
            f"o lado {lado} da taxa tem de declarar que o campo NÃO existe"
        )
        assert not PAR_COMMON_REPORT.search(texto), (
            f"o lado {lado} da taxa aponta um offset dentro do common; não há "
            "campo de intervalo no report de saída do DualSense"
        )
    assert "DualShock 4" in (linha["radio_comando"] or ""), (
        "o contraste com o DS4 (que TEM o campo, nos 6 bits baixos de "
        "report[1] do 0x11) é o que prova a ausência no DualSense"
    )


def test_nada_desta_frente_afirma_ter_ido_ao_aparelho() -> None:
    """Nesta leva ninguém escreveu no aparelho: `ate_onde_foi` não pode ter"""
    linha = MAPA_DA_FRENTE["combinacao.slot_jogador.estabilidade"]
    assert linha["radio_de_onde_sei"] in GRAUS_SEM_APARELHO, (
        "o lado rádio do número de jogador nunca foi ao aparelho; o grau tem de "
        f"ser um dos que dizem isso ({sorted(GRAUS_SEM_APARELHO)}), e está "
        f"{linha['radio_de_onde_sei']!r}"
    )
    assert not (linha["radio_ate_onde_foi"] or "").strip(), (
        "nada desta frente foi ao aparelho; `radio_ate_onde_foi` tem de ficar "
        "vazio"
    )


def test_o_documento_da_frente_existe_e_o_mapa_aponta_para_ele() -> None:
    """O mapa cita o documento; o documento tem de estar no disco."""
    assert DOC.is_file(), f"o documento desta frente sumiu: {DOC}"
    citacoes = sum(
        1
        for linha in MAPA_DA_FRENTE.values()
        for coluna, valor in linha.items()
        if coluna.startswith(("cabo_", "radio_")) and DOC.name in (valor or "")
    )
    assert citacoes >= 5, (
        "as células desta frente apontam para o documento que as sustenta; "
        f"achei {citacoes} citações"
    )
