"""A régua das seis linhas de PLATAFORMA e IDENTIDADE do DualSense.

Ela nasceu em 03/09/2026, na leva que foi caçar em repositório de terceiro o que
falta no mapa da Sony — e o risco dessa leva tem nome: **um número copiado
errado passa por todo portão desta casa**. O `check_paridade_transporte.py` diz
isso na própria docstring: ele é cego ao CONTEÚDO das colunas sem domínio, e um
`report[11]` trocado para `report[27]` atravessa com `rc=0`.

Esta régua fecha metade desse buraco, e só a metade que dá para fechar sem
aparelho: os report IDs e os tamanhos que o mapa cita para a PROBE e para a
IDENTIDADE do DualSense têm um DONO nesta árvore — os `#define` do
`hid-playstation` compilado nesta máquina. A régua não guarda número nenhum: ela
lê o dono e cobra que o mapa diga o mesmo.

O que ela NÃO alcança, dito na cara: o layout do `0x09` (onde está o endereço do
host) e a existência do `0x0A` vêm de fonte externa, e nenhum `#define` local os
sustenta. Para esses, a régua cobra apenas que a AFIRMAÇÃO continue lá, escrita —
porque o defeito que mais custou nesta casa não foi o número errado, foi a
célula que ficou muda de novo.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
DRIVER = RAIZ / "assets" / "dkms" / "hid-playstation" / "hid-playstation.c"


def _linhas_do_mapa() -> dict[str, dict[str, str]]:
    with MAPA.open(newline="", encoding="utf-8") as f:
        return {
            linha["id"]: linha for linha in csv.DictReader(f) if linha["controle"] == "dualsense"
        }


@pytest.fixture(scope="module")
def mapa() -> dict[str, dict[str, str]]:
    return _linhas_do_mapa()


@pytest.fixture(scope="module")
def defines_do_driver() -> dict[str, int]:
    """Os `#define DS_FEATURE_REPORT_*` do driver, lidos do fonte.

    O dono desta lista é o driver, nunca esta régua: por isso o dicionário é
    EXTRAÍDO, e um `#define` renumerado por um `apt upgrade` do DKMS aparece
    aqui como teste vermelho, e não como mapa silenciosamente velho.
    """
    fonte = DRIVER.read_text(encoding="utf-8", errors="replace")
    achados = dict(
        re.findall(
            r"^#define\s+(DS_FEATURE_REPORT_[A-Z_]+)\s+(0x[0-9a-fA-F]+|\d+)\s*$",
            fonte,
            re.MULTILINE,
        )
    )
    return {nome: int(valor, 0) for nome, valor in achados.items()}


def test_o_driver_desta_maquina_ainda_declara_os_tres_reports_da_probe(
    defines_do_driver: dict[str, int],
) -> None:
    """O controle positivo da régua: sem os `#define`, tudo abaixo é vácuo."""
    assert defines_do_driver["DS_FEATURE_REPORT_PAIRING_INFO"] == 0x09
    assert defines_do_driver["DS_FEATURE_REPORT_PAIRING_INFO_SIZE"] == 20
    assert defines_do_driver["DS_FEATURE_REPORT_FIRMWARE_INFO"] == 0x20
    assert defines_do_driver["DS_FEATURE_REPORT_FIRMWARE_INFO_SIZE"] == 64
    assert defines_do_driver["DS_FEATURE_REPORT_CALIBRATION"] == 0x05
    assert defines_do_driver["DS_FEATURE_REPORT_CALIBRATION_SIZE"] == 41


@pytest.mark.parametrize("lado", ["cabo", "radio"])
def test_a_probe_cita_os_tres_reports_com_os_numeros_do_driver(
    mapa: dict[str, dict[str, str]], defines_do_driver: dict[str, int], lado: str
) -> None:
    """Os dois lados da probe têm de nomear os MESMOS três que o driver pede.

    O lado do rádio cita os três por herança explícita («os MESMOS três»), então
    a cobrança de número recai no cabo e a do rádio recai na palavra que declara
    a herança — cobrar hex repetido ali empurraria quem escreve a duplicar o
    dono, que é o defeito que esta casa já pagou.
    """
    linha = mapa["plataforma.probe@dualsense"]
    celula = linha[f"{lado}_report_id"]
    assert celula, f"`{lado}_report_id` de plataforma.probe voltou a ficar mudo"

    if lado == "cabo":
        for nome in (
            "DS_FEATURE_REPORT_PAIRING_INFO",
            "DS_FEATURE_REPORT_FIRMWARE_INFO",
            "DS_FEATURE_REPORT_CALIBRATION",
        ):
            hexa = f"0x{defines_do_driver[nome]:02X}"
            assert hexa in celula, (
                f"o mapa não cita {hexa} ({nome}), que é o que o driver desta "
                f"máquina pede na probe do DualSense"
            )
            tamanho = defines_do_driver[f"{nome}_SIZE"]
            assert f"{tamanho} B" in celula, (
                f"o mapa não cita o tamanho {tamanho} B de {nome}: uma resposta "
                f"de tamanho errado é `-EINVAL` antes de qualquer parse"
            )
    else:
        assert "MESMOS três" in celula


def test_a_probe_por_radio_declara_a_semente_do_crc_da_resposta(
    mapa: dict[str, dict[str, str]],
) -> None:
    """`0xA3` é da RESPOSTA; `0x53` é do PEDIDO. Trocar as duas é o erro fácil."""
    fonte = DRIVER.read_text(encoding="utf-8", errors="replace")
    semente = re.search(r"#define\s+PS_FEATURE_CRC32_SEED\s+(0x[0-9a-fA-F]+)", fonte)
    assert semente is not None, "o driver deixou de declarar PS_FEATURE_CRC32_SEED"

    celula = mapa["plataforma.probe@dualsense"]["radio_report_id"]
    assert semente.group(1).upper().replace("0X", "0x") in celula


def test_o_retry_nao_inventa_report_proprio(mapa: dict[str, dict[str, str]]) -> None:
    """O retry reenvia o que falhou. Um report «do retry» seria fantasma."""
    linha = mapa["plataforma.probe.retry@dualsense"]
    assert "0x09" in linha["cabo_report_id"]
    assert "0x20" in linha["cabo_report_id"]
    assert "0x05" in linha["cabo_report_id"]
    assert "0x31" in linha["radio_report_id"], (
        "o que se perde ao desistir por rádio não é só o endereço: é o report de "
        "entrada completo, e a célula tem de dizer isso"
    )


def test_o_pareamento_diz_onde_mora_o_endereco_do_host(
    mapa: dict[str, dict[str, str]],
) -> None:
    """O achado desta leva: o `0x09` traz DOIS endereços, e o driver lê um só."""
    linha = mapa["identidade.pareamento@dualsense"]
    assert "0x09" in linha["cabo_report_id"]
    assert "0x0A" in linha["cabo_report_id"]
    assert "buf[1..6]" in linha["cabo_offset"], "sumiu o endereço do próprio controle"
    assert "buf[10..15]" in linha["cabo_offset"], (
        "sumiu o offset do endereço do HOST — que é o achado inteiro desta linha"
    )
    assert "buf[7..22]" in linha["cabo_offset"], "sumiu a link key de 16 bytes do 0x0A"


def test_o_pareamento_declara_que_a_escrita_e_so_do_cabo(
    mapa: dict[str, dict[str, str]],
) -> None:
    """A ausência do `0x0A` por rádio é afirmação, e afirmação some sozinha."""
    linha = mapa["identidade.pareamento@dualsense"]
    assert "0x0A" in linha["radio_report_id"]
    assert "NÃO EXISTE" in linha["radio_report_id"]
    assert linha["assimetria_declarada"], (
        "cabo e rádio divergem nesta linha; a assimetria não pode ficar muda"
    )


def test_o_inventario_esta_classificado_como_feature_nossa(
    mapa: dict[str, dict[str, str]],
) -> None:
    """`—` com razão escrita, para ninguém gastar uma leva caçando fantasma."""
    linha = mapa["plataforma.inventario@dualsense"]
    for coluna in ("cabo_report_id", "radio_report_id", "cabo_offset", "radio_offset"):
        assert linha[coluna] == "—", (
            f"{coluna} de plataforma.inventario deixou de ser `—`: se alguém achou "
            f"um report de inventário no DualSense, a razão escrita tem de cair junto"
        )
    assert "FEATURE NOSSA" in linha["cabo_ressalva"]
    assert "0x22" in linha["cabo_ressalva"], (
        "a ressalva tem de apontar o que o APARELHO oferece no lugar — senão a "
        "classificação vira só um `—`"
    )


def test_o_fallback_de_identidade_nao_finge_ter_endereco(
    mapa: dict[str, dict[str, str]],
) -> None:
    """No DualSense o driver aborta a probe; não há degrau para degradar."""
    linha = mapa["identidade.req_dev_info.fallback@dualsense"]
    assert linha["cabo_offset"] == "—"
    assert linha["radio_offset"] == "—"
    assert "0x09" in linha["cabo_report_id"]
    assert "ERR_PTR" in linha["cabo_report_id"], (
        "a célula tem de dizer QUE o driver aborta, não só que não há fallback"
    )


def test_o_censo_de_features_do_clone_bate_com_o_descritor_declarado(
    mapa: dict[str, dict[str, str]],
) -> None:
    """As duas listas são a impressão digital do transporte — e são exatas.

    Os dois conjuntos abaixo foram lidos em 03/09/2026 dos `report_descriptor`
    que o kernel guarda no sysfs para os dois controles da mesa dela — leitura de
    arquivo cacheado, sem um byte de tráfego para o aparelho. Escrevê-los aqui é
    o preço de não ter o aparelho dentro da suíte: se o firmware mudar, ou se
    alguém copiar a lista errada para o mapa, os dois lados divergem e isto
    fica vermelho.
    """
    censo_por_cabo = {
        "0x05",
        "0x08",
        "0x09",
        "0x0A",
        "0x0B",
        "0x0C",
        "0x20",
        "0x21",
        "0x22",
        "0x80",
        "0x81",
        "0x82",
        "0x83",
        "0x84",
        "0x85",
        "0xA0",
        "0xE0",
        "0xF0",
        "0xF1",
        "0xF2",
        "0xF4",
        "0xF5",
    }
    censo_por_radio = {
        "0x05",
        "0x08",
        "0x09",
        "0x0B",
        "0x20",
        "0x22",
        "0x80",
        "0x81",
        "0x82",
        "0x83",
        "0xF0",
        "0xF1",
        "0xF2",
        "0xF4",
        "0xF5",
        "0xF6",
        "0xF7",
    }
    assert len(censo_por_cabo) == 22
    assert len(censo_por_radio) == 17

    linha = mapa["plataforma.distinguir_clone@dualsense"]

    #: O censo é a ÚNICA corrida de hex separada por espaço dentro de uma crase.
    #: Ler assim, e não «todo hex da célula», é o que separa a LISTA da prosa em
    #: volta dela — que cita `0x03` e `0x0A` de propósito, para dizer que não
    #: estão lá.
    corrida = re.compile(r"`((?:0x[0-9A-F]{2} )+0x[0-9A-F]{2})`")

    def censo(celula: str) -> set[str]:
        achados = corrida.findall(celula)
        assert len(achados) == 1, (
            "a célula deixou de ter exatamente UMA lista de report IDs entre "
            "crases; sem isso não há censo a conferir"
        )
        return set(achados[0].split())

    assert censo(linha["cabo_report_id"]) == censo_por_cabo, (
        "o censo por cabo divergiu do `report_descriptor` lido no sysfs"
    )
    assert censo(linha["radio_report_id"]) == censo_por_radio, (
        "o censo por rádio divergiu do `report_descriptor` lido no sysfs"
    )
    assert "0x03" in linha["cabo_report_id"], (
        "sumiu o 0x03, que é o discriminador que o SDL usa e que nenhum descritor genuíno declara"
    )
    assert "0x0A" not in censo_por_radio, (
        "o 0x0A é a diferença entre os dois censos, e é o que sustenta "
        "`identidade.pareamento`: escrever pareamento é operação de cabo"
    )
