"""CANAL-POR-CONTROLE — LUZ: o caminho do RÁDIO escrito no mapa é o que o produto MONTA.

O PEDIDO DELA, 03/09/2026, e é o que esta régua guarda::

    "e supondo, se acharmos algo que não tenha mapeado ainda: o que sabemos é
     que ele existe. e quando colocarmos o caminho certo no specs o script
     original vai fazer uso desse place holder setado e automaticamente parear."

O mecanismo depende de uma coisa só: **o endereço escrito no mapa tem de ser o
endereço de verdade.** Um offset inventado é pior que uma célula muda — o
``html/specs.html`` o publica como fato, ``app/fatos_do_mapa.py`` o lê, e a
próxima pessoa constrói em cima dele.

O QUE ESTE ARQUIVO NÃO FAZ, e é a lição das onze réguas de 26/08/2026 que
*digitavam o que deviam LER*: ele **não tem uma tabela de offsets**. O
deslocamento do envelope é MEDIDO no builder de produção (uma marca única por
posição do ``common``, e procura-se onde ela caiu), e os bytes de cada feature
são lidos DE DENTRO do report que ``build_bt_lightbar_report`` devolve. Se o
envelope BT mudar — perder o tag ``0x10``, ganhar um byte, trocar de posição —
as células do mapa param de bater e este arquivo reprova, em vez de o mapa
seguir publicando um endereço morto.

A MORDIDA (arranque a cura e veja reprovar):

- apague o ``radio_offset`` de ``luz.lightbar.cor@dualsense`` (o travessão que
  estava lá até 03/09/2026) → ``test_toda_linha_de_luz_com_rota_no_radio_diz_o_byte``
  reprova, nomeando a linha;
- troque ``report[47..49]`` por ``report[45..47]`` (o offset do CABO escrito na
  célula do rádio, que é o erro mais fácil de cometer) →
  ``test_o_offset_escrito_no_mapa_bate_com_o_envelope_de_verdade`` reprova;
- em ``core/ds_output_report.build_bt_report``, tire o ``buf[2] = BT_TAG`` e
  ponha o common em ``[2..48]`` → o deslocamento medido cai para 2 e TODAS as
  células do rádio reprovam de uma vez.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.lightbar_gatilho import build_bt_lightbar_report

#: O mapa de canais, a partir da raiz do repositório (este arquivo mora em
#: ``tests/unit/``).
MAPA = Path(__file__).resolve().parents[2] / "docs" / "data" / "mapa-controles.csv"

#: ``common[43] = report[46]`` e ``common[44..46] = report[47..49]`` — as duas
#: formas em que esta casa escreve endereço de byte no mapa.
AFIRMACAO_DE_OFFSET = re.compile(
    r"common\[(\d+)(?:\.\.(\d+))?\]\s*=\s*report\[(\d+)(?:\.\.(\d+))?\]"
)

#: As colunas de um lado em que um endereço de byte pode aparecer. `offset` é a
#: dona; as outras entram porque a prosa desta casa repete o endereço, e um
#: endereço errado na prosa engana igual.
COLUNAS_COM_ENDERECO = ("offset", "comando")

#: As linhas de luz do DualSense cujo caminho por rádio é o report ``0x31``
#: AVULSO (ROTA-BT-EM-REGIME-01, 12/08/2026) — as que ganharam endereço de byte
#: em 03/09/2026, mais as que já o tinham.
LINHAS_DO_0X31 = (
    "luz.lightbar.cor@dualsense",
    "luz.led_jogador@dualsense",
    "luz.led_jogador.escrita_hefesto@dualsense",
    "luz.led_jogador.quinto@dualsense",
    "luz.lightbar.brilho@dualsense",
    "luz.lightbar.fade@dualsense",
    "luz.lightbar.release_leds@dualsense",
    "luz.led_microfone@dualsense",
)

#: Cor com R != B de propósito: uma cor cinza passaria com os canais trocados.
COR_DE_PROVA = (0x2A, 0x40, 0xC8)

#: Padrão de jogador assimétrico: ``--x--`` e os palíndromos do driver passariam
#: com a ordem invertida.
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
    """Onde o ``common`` cai dentro do envelope — MEDIDO, nunca digitado.

    Uma marca única por posição (1..47, nenhuma zero) e a procura da sequência
    inteira dentro do report que o builder de PRODUÇÃO devolve. Mudou o
    envelope, muda este número — e é isso que faz as células do mapa serem
    conferidas contra o código em vez de contra a memória de quem as escreveu.
    """
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
    """Toda ``common[X] = report[Y]`` da família luz respeita o envelope real.

    Vale para os DOIS lados: no cabo o ``common`` mora em ``[1..47]`` do 0x02,
    no rádio em ``[3..49]`` do 0x31. Escrever o offset do cabo na célula do
    rádio é o erro mais barato de cometer e o mais caro de descobrir — quem o
    ler monta um report que o firmware ignora, e o log diz "escrito".
    """
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
    """Nenhuma destas linhas volta a ser um travessão.

    Era o estado até 03/09/2026 em ``luz.lightbar.cor@dualsense`` e
    ``luz.led_jogador@dualsense``: ``radio_report_id`` e ``radio_offset`` eram
    ``—`` enquanto o ``radio_comando`` da MESMA linha descrevia a rota. Uma
    célula muda ao lado de uma prosa que descreve o caminho é o que faz a
    próxima pessoa concluir que caminho não há.
    """
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
    """Os índices da célula de ``luz.lightbar.cor@dualsense`` CARREGAM a cor.

    Não se compara texto com texto: monta-se o report que o produto manda por
    rádio (`build_bt_lightbar_report`, o mesmo do `_pintar_por_hidraw_bt` e do
    `reescrever_lightbar_por_hidraw`) e leem-se os bytes nas posições que a
    célula nomeia.
    """
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
    """``common[43] = report[46]`` carrega o bitmask das cinco lâmpadas.

    Cobre a quinta lâmpada de graça: ``PADRAO_DE_PROVA`` acende o bit 3 e apaga
    o 4, e o padrão inteiro é assimétrico — inverter a ordem reprova.
    """
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
        ("luz.lightbar.brilho@dualsense", 42, rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE),
        ("luz.lightbar.fade@dualsense", 41, rep.VALID_FLAG2_LIGHTBAR_SETUP_CONTROL_ENABLE),
    ),
)
def test_o_brilho_e_o_fade_dizem_o_byte_e_o_bit_que_o_valida(
    ident: str, byte_do_dado: int, bit_do_flag2: int
) -> None:
    """As duas dívidas do rádio dizem ONDE escrever E o que autoriza o campo.

    As duas são ``aciona = não`` nos DOIS transportes — ninguém as escreve. Por
    isso a célula é tudo o que quem for implementar vai ter, e um byte de dado
    sem o bit que o valida é um report que o firmware descarta em silêncio. Até
    03/09/2026 o lado do rádio das duas dava só o byte de dado.
    """
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
    """O que a célula GANHOU não pode ter apagado o que ela já dizia.

    ``luz.lightbar.cor@dualsense`` descrevia SÓ a supressão do
    ``report_thread`` (LIGHTBAR-BT-KEEPALIVE-01, 22/07/2026) e nenhum byte. Em
    03/09/2026 ela ganhou os bytes do 0x31 avulso — e a supressão FICA, porque
    as duas coisas são verdade ao mesmo tempo e são rotas diferentes. Uma cura
    que apagasse a supressão devolveria a casa ao erro que travava a barra no
    firmware.
    """
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
