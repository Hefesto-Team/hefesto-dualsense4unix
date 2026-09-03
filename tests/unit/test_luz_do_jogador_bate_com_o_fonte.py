"""O caminho do LED de jogador no mapa tem de bater com o fonte do driver.

Nascido em 03/09/2026, na leva de levantamento em fonte externa. O mapa ganhou
`report_id` e `offset` para as linhas de `luz.led_jogador.*` do DualSense, e a
régua que faltava é justamente a que a regra 19 do `check_paridade_transporte`
declara IMPOSSÍVEL para ela: *"nenhum portão sem hardware e sem rede consegue
dizer que o byte é 11 e não 47"*.

Esta régua consegue — porque o fonte do driver está VERSIONADO nesta árvore
(`assets/dkms/hid-playstation/hid-playstation.c`, o mesmo que compilou o módulo
carregado). Então o byte não é redigitado: ele é **calculado** somando os campos
de `struct dualsense_output_report_common` até chegar em `player_leds`, e os
report ids são **lidos** dos `#define`. Se alguém trocar 43 por 47 no mapa, ou
se o driver mudar a estrutura, isto reprova.

É o remédio para o defeito que esta casa já nomeou em levas anteriores: *a régua
DIGITAVA o que devia LER*.

MORDIDA PROVADA em 03/09/2026, arrancando uma cura de cada vez:
  · `report[44]` -> `report[47]` na célula do cabo   -> reprova
  · `0x02` -> `0x03` no `cabo_report_id`             -> reprova
  · `common[43]` -> `common[42]`                     -> reprova
  · apagar o `— ` da linha `leitura`                 -> reprova
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
DRIVER = RAIZ / "assets" / "dkms" / "hid-playstation" / "hid-playstation.c"

#: Quantos bytes o envelope põe ANTES do bloco `common` em cada transporte.
#: Não é chute: sai do mesmo fonte, das duas `struct`s de saída, e a soma de 3 do
#: rádio já está MEDIDA no mapa em `luz.led_microfone` (`common[8] = report[11]`).
PREFIXO_DO_ENVELOPE = {"cabo": 1, "radio": 3}


def _fonte_do_driver() -> str:
    if not DRIVER.is_file():
        pytest.skip(f"o fonte do driver não está nesta árvore: {DRIVER}")
    return DRIVER.read_text(encoding="utf-8", errors="replace")


def _define(fonte: str, nome: str) -> int:
    """Lê um `#define NOME 0xNN` do fonte, em vez de redigitar o número."""
    achado = re.search(rf"^#define\s+{re.escape(nome)}\s+(0x[0-9A-Fa-f]+|\d+)\s*$",
                       fonte, re.MULTILINE)
    assert achado is not None, f"`#define {nome}` sumiu do fonte do driver"
    return int(achado.group(1), 0)


def _offset_do_campo(fonte: str, estrutura: str, campo: str) -> int:
    """Soma os campos da `struct` até o campo pedido e devolve o byte dele.

    Só entende os tipos que a estrutura de saída do DualSense usa — `u8` solto e
    `u8 nome[N]`. Se um tipo novo aparecer, o teste falha em vez de adivinhar,
    que é o comportamento que se quer de uma régua.
    """
    corpo = re.search(rf"struct\s+{re.escape(estrutura)}\s*\{{(.*?)\n\}}",
                      fonte, re.DOTALL)
    assert corpo is not None, f"`struct {estrutura}` sumiu do fonte do driver"

    offset = 0
    for linha in corpo.group(1).splitlines():
        limpa = re.sub(r"/\*.*?\*/", " ", linha).split("//")[0].strip()
        if not limpa or not limpa.endswith(";"):
            continue
        membro = re.fullmatch(r"(\w+)\s+(\w+)(?:\[(\d+)\])?\s*;", limpa)
        assert membro is not None, f"campo que esta régua não sabe medir: {limpa!r}"
        tipo, nome, quantos = membro.group(1), membro.group(2), membro.group(3)
        assert tipo == "u8", (
            f"`{estrutura}.{nome}` é `{tipo}`, e esta régua só soma `u8`. "
            "O driver mudou de forma: confira a conta antes de confiar no mapa."
        )
        if nome == campo:
            return offset
        offset += int(quantos) if quantos else 1

    raise AssertionError(f"`{estrutura}.{campo}` não existe mais no fonte")


def _linhas_do_mapa() -> dict[str, dict[str, str]]:
    with MAPA.open(encoding="utf-8") as f:
        return {
            linha["chave"]: linha
            for linha in csv.DictReader(f)
            if linha["controle"] == "dualsense"
        }


CHAVES_QUE_ESCREVEM = ("luz.led_jogador.padrao_driver", "luz.led_jogador.quinto")


@pytest.mark.parametrize("chave", CHAVES_QUE_ESCREVEM)
@pytest.mark.parametrize("lado", ("cabo", "radio"))
def test_o_offset_do_led_de_jogador_e_o_que_o_fonte_calcula(chave: str, lado: str) -> None:
    """`common[N]` e `report[M]` no mapa têm de sair da soma dos campos."""
    fonte = _fonte_do_driver()
    comum = _offset_do_campo(fonte, "dualsense_output_report_common", "player_leds")
    no_report = comum + PREFIXO_DO_ENVELOPE[lado]

    celula = _linhas_do_mapa()[chave][f"{lado}_offset"]
    assert f"common[{comum}]" in celula, (
        f"{chave}/{lado}: o fonte põe `player_leds` no byte {comum} do bloco, "
        f"e a célula diz outra coisa: {celula!r}"
    )
    assert f"report[{no_report}]" in celula, (
        f"{chave}/{lado}: com {PREFIXO_DO_ENVELOPE[lado]} byte(s) de envelope, "
        f"`common[{comum}]` cai em `report[{no_report}]`; a célula diz: {celula!r}"
    )


@pytest.mark.parametrize("chave", CHAVES_QUE_ESCREVEM)
@pytest.mark.parametrize(
    ("lado", "simbolo"),
    (("cabo", "DS_OUTPUT_REPORT_USB"), ("radio", "DS_OUTPUT_REPORT_BT")),
)
def test_o_report_id_do_led_de_jogador_e_o_que_o_fonte_define(
    chave: str, lado: str, simbolo: str
) -> None:
    """O `report_id` do mapa tem de ser o `#define` do driver, não um número solto."""
    esperado = f"0x{_define(_fonte_do_driver(), simbolo):02x}"
    celula = _linhas_do_mapa()[chave][f"{lado}_report_id"]
    assert esperado in celula.lower(), (
        f"{chave}/{lado}: o fonte define `{simbolo}` como {esperado}; "
        f"a célula diz: {celula!r}"
    )


def test_o_porteiro_do_led_de_jogador_e_o_bit4_do_flag1() -> None:
    """O mapa cita `flag1 bit4 (0x10)`, e o fonte tem de concordar."""
    fonte = _fonte_do_driver()
    achado = re.search(
        r"#define\s+DS_OUTPUT_VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE\s+BIT\((\d+)\)",
        fonte,
    )
    assert achado is not None, "o porteiro do LED de jogador sumiu do fonte"
    bit = int(achado.group(1))
    assert bit == 4, f"o driver mudou o porteiro para o bit {bit}: o mapa está velho"

    celula = _linhas_do_mapa()["luz.led_jogador.padrao_driver"]["cabo_offset"]
    assert f"bit{bit}" in celula.replace(" ", "") and "0x10" in celula, (
        f"a célula devia nomear o bit{bit} (0x10) do flag1; diz: {celula!r}"
    )


def test_a_entrada_do_dualsense_nao_tem_campo_de_led() -> None:
    """A linha `leitura` diz `—`, e o fonte tem de sustentar a negativa.

    Se um dia o driver ganhar um campo de LED no report de ENTRADA, esta régua
    reprova — e aí a linha `luz.led_jogador.leitura` deixou de ser verdade.
    """
    fonte = _fonte_do_driver()
    corpo = re.search(r"struct\s+dualsense_input_report\s*\{(.*?)\n\}", fonte, re.DOTALL)
    assert corpo is not None, "`struct dualsense_input_report` sumiu do fonte"

    proibidas = ("led", "player", "lightbar", "bright")
    for linha in corpo.group(1).splitlines():
        nu = linha.split("/*")[0].split("//")[0].lower()
        for palavra in proibidas:
            assert palavra not in nu, (
                "o report de ENTRADA do DualSense ganhou algo com "
                f"{palavra!r} ({linha.strip()!r}). A linha "
                "`luz.led_jogador.leitura` diz que não há por onde ler o estado "
                "do LED: confira antes de acreditar no mapa."
            )

    mapa = _linhas_do_mapa()["luz.led_jogador.leitura"]
    for lado in ("cabo", "radio"):
        assert mapa[f"{lado}_offset"].startswith("—"), (
            f"a linha `leitura` tem de declarar a ausência com `—` no {lado}; "
            f"diz: {mapa[f'{lado}_offset']!r}"
        )
        assert mapa[f"{lado}_report_id"].startswith("—"), (
            f"a linha `leitura` tem de declarar a ausência com `—` no {lado}; "
            f"diz: {mapa[f'{lado}_report_id']!r}"
        )


def test_o_que_veio_de_fonte_externa_declara_de_onde_veio() -> None:
    """Toda linha que esta leva preencheu tem de dizer a proveniência.

    É a regra 19 do `check_paridade_transporte` aplicada às cinco linhas desta
    leva, e com uma cobrança a mais: quem citou repositório de terceiro tem de
    ter `fonte_externa` preenchida, senão o endereço morre na prosa.
    """
    linhas = _linhas_do_mapa()
    for chave in (*CHAVES_QUE_ESCREVEM, "luz.led_jogador.leitura", "luz.recursos_proprios"):
        linha = linhas[chave]
        assert linha["fonte_externa"].strip(), (
            f"{chave}: a leva de 03/09/2026 leu repositório de terceiro e a célula "
            "`fonte_externa` está vazia — o endereço tem de sobreviver à prosa"
        )
        for lado in ("cabo", "radio"):
            assert linha[f"{lado}_de_onde_sei"].strip(), (
                f"{chave}/{lado}: há conteúdo escrito e `de_onde_sei` vazio"
            )


def test_nada_desta_leva_se_declarou_medido() -> None:
    """Nada foi ao aparelho em 03/09/2026: nenhuma célula pode dizer `medido`.

    Escrever `medido` para o que se LEU num repositório é a mentira que portão
    nenhum pega — então ela vira teste. Vale só para as duas linhas que NASCERAM
    nesta leva; as irmãs têm medição anterior, e legítima.
    """
    linhas = _linhas_do_mapa()
    for chave in ("luz.led_jogador.quinto", "luz.recursos_proprios"):
        linha = linhas[chave]
        for lado in ("cabo", "radio"):
            assert linha[f"{lado}_ate_onde_foi"].strip() == "", (
                f"{chave}/{lado}: `ate_onde_foi` foi preenchido, e nesta leva "
                "nada tocou o aparelho"
            )
        assert linha["cabo_de_onde_sei"] != "medido", f"{chave}: `medido` sem medição"
        assert linha["radio_de_onde_sei"] != "medido", f"{chave}: `medido` sem medição"
