"""O que a leva de fonte externa escreveu no mapa tem de bater com o driver.

O DEFEITO QUE ESTE ARQUIVO EXISTE PARA NÃO DEIXAR VOLTAR
--------------------------------------------------------
Em 03/09/2026 uma leva peneirou repositório público e trouxe FATO para cinco
linhas de `plataforma.*` do DualSense — a maior delas sendo que **não existe
`SET_REPORT_MODE` no DualSense**: por rádio o aparelho nasce mandando o `0x01`
de 10 bytes e só passa ao `0x31` de 78 depois que o host faz um `GET_REPORT`
num feature report. Quem trouxe isso trouxe números: `0x09`, `0x20`, `0x05`,
`0x01`, `0x31`, 64, 78, 63, 47, `0x10`.

**Número lido em repositório de terceiro é exatamente o que nenhum portão desta
casa sabe conferir.** A docstring do `check_paridade_transporte.py` mediu essa
cegueira e a escreveu com todas as letras: o byte do LED de jogador trocado de
11 para 47 passou com `rc=0`. A régua daquele portão cobra a PROVENIÊNCIA de
quem escreveu, não o conteúdo — de propósito, porque sem hardware e sem rede ela
não pode cobrar mais.

Só que **destes** números uma boa parte NÃO precisa de hardware nem de rede para
ser conferida: eles estão no `hid-playstation.c` que compilou o módulo carregado
nesta máquina, dentro da árvore, em `assets/dkms/`. Este arquivo é a régua que
faltava para essa metade.

O QUE ELE MORDE
---------------
1. **Os ids e tamanhos que o mapa cita** contra os `#define` do driver. Se
   alguém trocar `0x09` por `0x0B` numa célula, ou se um `apt upgrade` do
   kernel mudar um tamanho, o teste reprova apontando os dois lados.
2. **A ORDEM da probe**, que é o argumento inteiro da linha
   `plataforma.modo_relatorio`: as três leituras de feature acontecem ANTES de
   `ps_gamepad_create`. Se a ordem inverter, a explicação de por que o driver
   nunca vê o modo básico morre, e a célula passa a mentir.
3. **A assimetria estrutural entre os dois parsers** — o do DualShock 4 tem
   ramo para o report mínimo por rádio, o do DualSense não tem. É a
   confirmação mais forte que dá para ter sem tocar no aparelho, e ela é
   frágil: um patch futuro que acrescente o ramo ao DualSense derruba o
   argumento, e é bom que derrube ruidosamente.
4. **A honestidade de grau.** Nada foi ao aparelho nesta leva. Toda célula que
   ela escreveu tem de continuar `afirmado-no-doc` e nenhuma pode ter ganhado
   `ate_onde_foi`. Um `medido` aqui seria mentira que o portão de paridade não
   pega — ele confere a FORMA (quem afirma diz de onde sabe), nunca a origem.
5. **As duas linhas classificadas como NÃO-CANAL** — `handshake_usb` e
   `taxa_relatorios.botao` — não podem ganhar `report_id` de aparelho. Elas
   foram decididas: uma é vocabulário de outro controle, a outra é feature
   nossa de medição. Escrever um `0x..` ali é a próxima pessoa caçando o
   fantasma que esta leva foi mandada matar.

A PROVA DA MORDIDA está registrada na mensagem do commit desta leva.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
DRIVER = RAIZ / "assets" / "dkms" / "hid-playstation" / "hid-playstation.c"
LEITURA = RAIZ / "docs" / "protocol" / "dualsense-modo-de-relatorio.md"

#: As linhas que a leva de 03/09/2026 escreveu, e o que ela afirmou em cada uma.
LINHAS_DA_LEVA = (
    "plataforma.modo_relatorio",
    "plataforma.handshake_usb",
    "plataforma.taxa_relatorios.botao",
    "plataforma.limitador_subcomando",
    "plataforma.escrita_crua",
)

#: As duas que a leva DECIDIU não serem canal do aparelho. Ver o item 5 acima.
SEM_CANAL_NO_APARELHO = (
    "plataforma.handshake_usb",
    "plataforma.taxa_relatorios.botao",
)

#: `#define` do driver -> valor que o mapa e a leitura citam. É esta tabela que
#: transforma "eu li num repositório" em "confere com o que roda aqui".
DEFINES_QUE_O_MAPA_CITA = {
    "DS_INPUT_REPORT_USB": "0x01",
    "DS_INPUT_REPORT_USB_SIZE": "64",
    "DS_INPUT_REPORT_BT": "0x31",
    "DS_INPUT_REPORT_BT_SIZE": "78",
    "DS_OUTPUT_REPORT_USB": "0x02",
    "DS_OUTPUT_REPORT_USB_SIZE": "63",
    "DS_OUTPUT_REPORT_BT": "0x31",
    "DS_OUTPUT_REPORT_BT_SIZE": "78",
    "DS_FEATURE_REPORT_CALIBRATION": "0x05",
    "DS_FEATURE_REPORT_PAIRING_INFO": "0x09",
    "DS_FEATURE_REPORT_FIRMWARE_INFO": "0x20",
    "DS_OUTPUT_TAG": "0x10",
}

#: A ordem que sustenta a célula `radio_comando` de `plataforma.modo_relatorio`.
ORDEM_DA_PROBE = (
    "dualsense_get_mac_address",
    "dualsense_get_firmware_info",
    "dualsense_get_calibration_data",
    "ps_gamepad_create",
)


@pytest.fixture(scope="module")
def fonte_do_driver() -> str:
    if not DRIVER.is_file():
        pytest.fail(
            f"{DRIVER} sumiu. Este teste existe porque o driver DENTRO da árvore "
            "é a única régua sem rede para os números que a leva trouxe de fora; "
            "sem ele a leva volta a ser inconferível."
        )
    return DRIVER.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def linhas_do_mapa() -> dict[str, dict[str, str]]:
    with MAPA.open(newline="", encoding="utf-8") as f:
        return {
            linha["chave"]: linha
            for linha in csv.DictReader(f)
            if linha["controle"] == "dualsense"
        }


def _corpo(fonte: str, funcao: str) -> str:
    """O texto da função nomeada até a chave que a fecha na coluna zero."""
    inicio = fonte.index(f"{funcao}(struct")
    resto = fonte[inicio:]
    fim = re.search(r"\n\}\n", resto)
    return resto[: fim.end()] if fim else resto


def _bloco(fonte: str, abertura: str) -> str:
    """O texto de uma declaração de struct até o `};` que a fecha."""
    inicio = fonte.index(abertura)
    resto = fonte[inicio:]
    fim = re.search(r"\n\} __packed;\n", resto)
    return resto[: fim.end()] if fim else resto


@pytest.mark.parametrize("nome,valor", sorted(DEFINES_QUE_O_MAPA_CITA.items()))
def test_o_numero_que_o_mapa_cita_e_o_numero_do_driver(
    fonte_do_driver: str, nome: str, valor: str
) -> None:
    """Cada id e cada tamanho da leva bate com o `#define` que roda aqui."""
    achado = re.search(rf"^#define\s+{nome}\s+(\S+)", fonte_do_driver, re.MULTILINE)
    assert achado is not None, (
        f"`#define {nome}` sumiu do driver desta máquina. As células de "
        "`plataforma.modo_relatorio@dualsense` e a leitura em "
        f"{LEITURA.name} citam esse nome; se ele mudou, elas envelheceram junto."
    )
    assert achado.group(1) == valor, (
        f"`{nome}` vale {achado.group(1)!r} no driver e o mapa cita {valor!r}. "
        "Um dos dois está errado, e o driver é quem roda."
    )


def test_o_common_de_saida_tem_os_47_bytes_que_a_casa_conta(
    fonte_do_driver: str,
) -> None:
    """Os 47 bytes do `common` e os 63 do 0x02 sustentam a `cabo_detalhe`.

    A célula de `plataforma.escrita_crua@dualsense` diz que os 15 bytes finais
    do report de saída por cabo são enchimento OPCIONAL, e a conta que sustenta
    isso é 1 + 47 + 15 == 63. Se qualquer parcela mudar, a conta some.
    """
    assert (
        "static_assert(sizeof(struct dualsense_output_report_common) == 47);"
        in fonte_do_driver
    ), "o `common` deixou de ter 47 bytes: a conta 1 + 47 + 15 == 63 da célula caiu"

    usb = _bloco(fonte_do_driver, "struct dualsense_output_report_usb {")
    assert "u8 reserved[15];" in usb, (
        "os 15 bytes reservados do report de saída por cabo sumiram: a célula "
        "`cabo_detalhe` de `plataforma.escrita_crua@dualsense` afirma que são eles "
        "a diferença entre os 48 bytes que o SDL escreve e os 63 do driver"
    )


def test_a_probe_le_os_features_antes_de_criar_o_gamepad(
    fonte_do_driver: str,
) -> None:
    """A ORDEM é o argumento inteiro da linha `plataforma.modo_relatorio`.

    As três leituras de feature (0x09, 0x20, 0x05) acontecem antes de o driver
    passar a consumir report de entrada. É por isso que ele nunca vê o modo
    básico por rádio — e é por isso que ele pode não ter ramo para o `0x01`
    por Bluetooth. Inverter a ordem mata a explicação.
    """
    corpo = _corpo(fonte_do_driver, "dualsense_create")
    posicoes = []
    for chamada in ORDEM_DA_PROBE:
        assert chamada in corpo, (
            f"`{chamada}` sumiu de `dualsense_create`. A célula `radio_comando` de "
            "`plataforma.modo_relatorio@dualsense` cita esta sequência pelo nome."
        )
        posicoes.append(corpo.index(chamada))
    assert posicoes == sorted(posicoes), (
        "a ordem da probe mudou: a célula do mapa afirma que as TRÊS leituras de "
        f"feature vêm antes de `ps_gamepad_create`, e hoje a ordem é {ORDEM_DA_PROBE} "
        f"nas posições {posicoes}"
    )


def test_o_parser_do_dualsense_nao_tem_ramo_para_o_0x01_por_radio(
    fonte_do_driver: str,
) -> None:
    """A assimetria entre os dois parsers é a confirmação sem hardware.

    O DualShock 4 precisa do ramo mínimo porque clone nenhum garante a troca; o
    DualSense não precisa porque a probe já o virou. Um patch que acrescente o
    ramo ao DualSense derruba o argumento da célula, e tem de derrubar alto.
    """
    ds4 = _corpo(fonte_do_driver, "dualshock4_parse_report")
    assert "DS4_INPUT_REPORT_BT_MINIMAL" in ds4, (
        "o DualShock 4 perdeu o ramo do report mínimo por rádio — o CONTRASTE que "
        "a célula `radio_evidencia` usa como prova deixou de existir"
    )

    ds = _corpo(fonte_do_driver, "dualsense_parse_report")
    assert "MINIMAL" not in ds, (
        "o parser do DualSense ganhou um ramo de report mínimo. Se o driver passou "
        "a precisar dele, o aparelho pode NÃO estar sendo virado pela probe — e a "
        "célula `radio_evidencia` de `plataforma.modo_relatorio@dualsense` precisa "
        "ser remedida antes de continuar afirmando o contrário."
    )
    assert 'hid_err(hdev, "Unhandled reportID=%d\\n", report->id);' in ds, (
        "sumiu a linha que produz `Unhandled reportID=1` — o diagnóstico "
        "falsificável que a célula oferece para o dia em que um DualSense não virar"
    )


@pytest.mark.parametrize("chave", LINHAS_DA_LEVA)
def test_nada_desta_leva_se_promoveu_a_medido(
    linhas_do_mapa: dict[str, dict[str, str]], chave: str
) -> None:
    """Nada foi ao aparelho em 03/09/2026, e o grau tem de continuar dizendo isso.

    O portão de paridade confere a FORMA — quem afirma diz de onde sabe — e não
    tem como saber que a origem foi um repositório na internet. Esta é a régua
    que sabe.
    """
    linha = linhas_do_mapa[chave]
    for lado in ("cabo", "radio"):
        assert not linha[f"{lado}_ate_onde_foi"].strip(), (
            f"{chave}@dualsense ganhou `{lado}_ate_onde_foi` = "
            f"{linha[f'{lado}_ate_onde_foi']!r}. A leva de fonte externa não tocou "
            "o aparelho: um degrau aqui exige ensaio no caderno, não leitura."
        )


@pytest.mark.parametrize("chave", SEM_CANAL_NO_APARELHO)
def test_a_linha_que_nao_e_canal_do_aparelho_nao_ganha_report_id(
    linhas_do_mapa: dict[str, dict[str, str]], chave: str
) -> None:
    """Feature nossa e vocabulário de outro controle não têm report a citar.

    `handshake_usb` é vocabulário do Switch Pro; `taxa_relatorios.botao` é
    feature nossa de MEDIÇÃO, e o DualSense não tem campo de taxa. As duas foram
    classificadas de propósito, para ninguém gastar uma leva caçando o report.
    """
    linha = linhas_do_mapa[chave]
    for lado in ("cabo", "radio"):
        celula = linha[f"{lado}_report_id"]
        assert celula.strip().startswith("—"), (
            f"{chave}@dualsense: `{lado}_report_id` = {celula!r} deixou de começar "
            "pelo travessão que diz `não há report`."
        )
        achados = re.findall(r"0x[0-9A-Fa-f]{2}", celula)
        assert not achados, (
            f"{chave}@dualsense ganhou {achados} em `{lado}_report_id`. Esta linha "
            "foi DECIDIDA como não sendo canal do aparelho — se a decisão caiu, ela "
            "cai com medição e com nota datada, não escrevendo um id por cima."
        )
        assert linha[f"{lado}_de_onde_sei"].strip(), (
            f"{chave}@dualsense afirma sobre `{lado}` sem dizer de onde sabe"
        )


def test_a_leitura_da_leva_continua_na_arvore() -> None:
    """As células apontam a leitura completa; ela não pode sumir sem aviso."""
    assert LEITURA.is_file(), (
        f"{LEITURA} sumiu, e cinco linhas do mapa apontam para ela — inclusive a "
        "lista do que a internet NÃO sabe, que é o que a bancada vai ensaiar"
    )
    texto = LEITURA.read_text(encoding="utf-8")
    assert "O QUE A INTERNET NÃO SABE" in texto, (
        "a seção do que NÃO se achou saiu da leitura. Ela é entrega tanto quanto o "
        "que se achou: é ela que diz onde só o aparelho responde"
    )


#: Os CINCO ids que a célula `radio_comando` de `plataforma.modo_relatorio` tem
#: direito de nomear: os dois reports de ENTRADA que ela contrasta e os TRÊS
#: features cuja leitura dispara a troca. Nem um a mais, nem um a menos.
IDS_DO_GATILHO = {
    "0x01": "DS_INPUT_REPORT_USB",
    "0x31": "DS_INPUT_REPORT_BT",
    "0x05": "DS_FEATURE_REPORT_CALIBRATION",
    "0x09": "DS_FEATURE_REPORT_PAIRING_INFO",
    "0x20": "DS_FEATURE_REPORT_FIRMWARE_INFO",
}


def test_os_ids_que_a_celula_do_gatilho_nomeia_sao_os_do_driver(
    linhas_do_mapa: dict[str, dict[str, str]], fonte_do_driver: str
) -> None:
    """O BURACO QUE ESTE TESTE FECHA, medido em 03/09/2026 com a cura arrancada.

    O `test_o_numero_que_o_mapa_cita_e_o_numero_do_driver` lê SÓ o driver: ele
    confere que o `#define` continua valendo o que a leva citou, e **nunca abre
    o CSV**. A docstring deste arquivo prometia que trocar `0x09` por `0x0B`
    numa célula reprovaria — e a mordida mediu que NÃO reprovava: 23 testes
    passaram com o id trocado. É a forma que esta casa já conhece de cor, a
    régua confundindo *«a fonte ainda diz X»* com *«a célula diz X»*.

    Este teste lê os DOIS lados. Ele cobra que o conjunto de ids nomeado na
    célula seja exatamente `IDS_DO_GATILHO` — trocar um reprova, apagar um
    reprova, inventar um sexto reprova — e que cada um valha, no driver desta
    máquina, o que a célula diz que vale.
    """
    celula = linhas_do_mapa["plataforma.modo_relatorio"]["radio_comando"]
    citados = set(re.findall(r"0x[0-9A-Fa-f]{2}", celula))

    assert citados == set(IDS_DO_GATILHO), (
        "`plataforma.modo_relatorio@dualsense.radio_comando` nomeia "
        f"{sorted(citados)} e o argumento da célula precisa de exatamente "
        f"{sorted(IDS_DO_GATILHO)}: os dois reports de entrada que ela contrasta "
        "e os três features cuja leitura dispara a troca. Um id a mais ou a "
        "menos é outra afirmação, e ela precisa de outra fonte."
    )

    for id_citado, define in sorted(IDS_DO_GATILHO.items()):
        achado = re.search(
            rf"^#define\s+{define}\s+(\S+)", fonte_do_driver, re.MULTILINE
        )
        assert achado is not None, f"`#define {define}` sumiu do driver"
        assert achado.group(1).lower() == id_citado.lower(), (
            f"a célula nomeia {id_citado} para {define}, e o driver desta "
            f"máquina diz {achado.group(1)}. O driver é quem roda."
        )
