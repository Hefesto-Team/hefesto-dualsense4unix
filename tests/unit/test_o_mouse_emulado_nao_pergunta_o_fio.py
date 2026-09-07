"""O gatilho e o analógico viram mouse pelo MESMO caminho nos dois fios — medido.

O PEDIDO, 03/09/2026: fechar as duas linhas do mapa que nasceram de uma
observação DELA no aparelho, em 11/08/2026, no meio de um ensaio de gatilho:

    "notei uma coisa o r2 e o l2 quando o teclado tá ativo ele funciona como
    mouse, além do analogico também funcionar como mouse e o touch também, a
    exceção do touch os demais não funcionam no modo bt"

`entrada.emulacao_mouse.gatilhos@dualsense` e `.analogico@dualsense` guardam
essa frase desde então, com as vinte e seis colunas de transporte MUDAS.

O QUE ESTE ARQUIVO GUARDA
--------------------------
Um achado NEGATIVO e uma PREMISSA DERRUBADA — os dois somem sozinhos se ninguém
os defender.

1. **Não há ramo de transporte no caminho do mouse emulado.** Nem no driver que
   esta casa instala (os seis eixos do gamepad saem DEPOIS da única porta de
   barramento), nem na descoberta do nó, nem no `read_state`, nem no despacho,
   nem no portão do laço.

2. **A premissa da `nota` das duas linhas é FALSA.** Ela dizia: *"as três
   emulações passam pelo mesmo leitor de evdev, então uma diferença só no rádio
   precisa de explicação"*. São DOIS donos, não um: desde a
   TOUCHPAD-DO-SISTEMA-01 (09/08/2026) quem move o cursor com o touchpad FÍSICO
   é o **libinput**, e o `TouchpadReader` se recusa a acumular movimento nesse
   caso (`_acumula_agora`). O gatilho e o analógico, esses, só chegam ao cursor
   pela emulação do daemon. Logo a observação dela compara duas coisas que o
   Hefesto faz com UMA que ele não faz — não existe a simetria de três que
   pediria uma explicação de transporte.

   Conferido ao vivo em 03/09/2026, no nó do cabo desta mesa: o touchpad traz
   `mouse4` entre os `Handlers` de `/proc/bus/input/devices` e o udev NÃO lhe
   põe `LIBINPUT_IGNORE_DEVICE`; o nó de gamepad traz só `js0` e
   `ID_INPUT_JOYSTICK=1`.

O QUE ELE NÃO PROVA, dito na cara
----------------------------------
Nada aqui põe o dedo no aparelho. Esta régua lê CÓDIGO e lê o MAPA; quem põe o
dedo no controle é ela, na bancada.

O LADO DO RÁDIO FOI MEDIDO — 05/09/2026
---------------------------------------
Até 05/09 este bloco dizia: *"o lado RÁDIO das duas linhas continua
`desconhecido` no mapa, e por um motivo medido: às 16h de 03/09/2026 havia UM só
DualSense na mesa e ele estava no CABO (`/sys/bus/hid/devices` listava apenas
`0003:054C:0CE6`, e `0003` é `BUS_USB`). Sem nó de rádio não há o que ler."*

**A razão caducou, e ela mesma a derrubou**, com estas palavras:

    "hj as máscaras funcionam super legal em tudo o lance do R2 analógico e
     cursor tão medidos já viu"

Medido com ela na bancada, nos DOIS transportes. E o código já dizia o mesmo
pela outra ponta: `daemon/subsystems/mouse.py` e `integrations/uinput_mouse.py`
recebem o eixo já normalizado pelo daemon e escrevem no uinput — não há uma
linha que pergunte o barramento, que é justamente o que o teste
`test_o_caminho_do_mouse_emulado_nao_decide_por_transporte` prova aqui.

DOIS ENDEREÇOS MORTOS, CORRIGIDOS EM 06/09/2026 (SPECS-A-PROCEDENCIA-01)
------------------------------------------------------------------------
Este parágrafo citava `core/mouse_emulation.py`, que **não existe nesta
árvore**, e um teste — `test_o_caminho_do_mouse_nao_le_transporte` — que **não
existe neste arquivo**. Os donos reais são os dois módulos varridos por
`ESCOPOS`, logo abaixo, e o teste real é o de nome inteiro acima. O mesmo
endereço morto estava na `radio_evidencia` das duas linhas do mapa
(`entrada.emulacao_mouse.gatilhos@dualsense` e `.analogico@dualsense`), na
evidência mais NOVA que elas tinham — achado da A-RECUSA-QUE-CITOU-O-MAPA-01
§4.6, e as duas foram reapontadas no mesmo gesto que esta.

*A régua sabia o caminho certo em `ESCOPOS` e a prosa dela apontava para outro
lugar* — que é a forma exata do defeito que a
`tests/unit/test_a_procedencia_da_linha_nao_e_vazia.py` passou a cobrar do mapa.

Então as células passaram de `desconhecido`/`incerto` para `sim`/`medido`, e
esta régua acompanhou. **Ela não foi afrouxada — foi invertida**: continua
reprovando qualquer mudança silenciosa das seis células, só que agora o que ela
protege é a medição, não a ignorância que a antecedeu.
"""

from __future__ import annotations

import ast
import csv
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = RAIZ / "src" / "hefesto_dualsense4unix"
DRIVER = RAIZ / "assets" / "dkms" / "hid-playstation" / "hid-playstation.c"
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

#: As palavras que só um gate de TRANSPORTE escreveria. Igualdade exata e em
#: minúsculas, nunca substring: `uhid` é backend e `bus` sozinho é o barramento
#: de EVENTOS do daemon (`self.bus.publish`) — uma régua por substring acusaria
#: os dois.
PALAVRAS_DE_TRANSPORTE = frozenset(
    {
        "usb",
        "bt",
        "bluetooth",
        "cabo",
        "radio",
        "rádio",
        "wired",
        "wireless",
        "bus_usb",
        "bus_bluetooth",
    }
)

#: Nome de variável, atributo ou argumento que decidiria por fio. `bus` fica de
#: FORA de propósito (é o barramento de eventos); `bustype` fica dentro.
NOMES_DE_TRANSPORTE = frozenset(
    {"transport", "_transport", "transporte", "bustype", "con_type", "contype"}
)

#: Os quatro escopos que carregam o gatilho/analógico do plástico até o cursor.
#: `None` quer dizer "o módulo inteiro"; um nome, só aquela função.
ESCOPOS: tuple[tuple[str, str | None], ...] = (
    ("daemon/subsystems/mouse.py", None),
    ("integrations/uinput_mouse.py", None),
    ("daemon/lifecycle.py", "_poll_loop"),
    ("core/backend_pydualsense.py", "read_state"),
)


def _decisoes(escopo: ast.AST) -> list[ast.AST]:
    """Os nós que DECIDEM alguma coisa dentro de `escopo`.

    A distinção é o ponto inteiro da régua: `transport=state.transport` num log
    é VALOR, e o `read_state` publica o transporte como campo do estado o tempo
    todo. O que seria defeito é um `if` que muda o comportamento por fio.
    """
    testes: list[ast.AST] = []
    for no in ast.walk(escopo):
        if isinstance(no, ast.If | ast.While | ast.IfExp | ast.Assert):
            testes.append(no.test)
        elif isinstance(no, ast.comprehension):
            testes.extend(no.ifs)
        elif isinstance(no, ast.Compare | ast.BoolOp):
            testes.append(no)
    return testes


def gates_de_transporte(fonte: str, alvo: str | None) -> list[str]:
    """As decisões por FIO tomadas no escopo. Vazio é a promessa desta linha."""
    arvore = ast.parse(fonte)
    escopos: list[ast.AST] = []
    if alvo is None:
        escopos.append(arvore)
    else:
        for no in ast.walk(arvore):
            if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef) and no.name == alvo:
                escopos.append(no)
        if not escopos:
            raise AssertionError(f"função `{alvo}` não existe mais neste módulo")
    achados: list[str] = []
    for escopo in escopos:
        for teste in _decisoes(escopo):
            for no in ast.walk(teste):
                if (
                    isinstance(no, ast.Constant)
                    and isinstance(no.value, str)
                    and no.value.strip().lower() in PALAVRAS_DE_TRANSPORTE
                ):
                    achados.append(f"linha {no.lineno}: decide pelo texto {no.value!r}")
                if isinstance(no, ast.Attribute) and no.attr.lower() in NOMES_DE_TRANSPORTE:
                    achados.append(f"linha {no.lineno}: decide pelo atributo `.{no.attr}`")
                if isinstance(no, ast.Name) and no.id.lower() in NOMES_DE_TRANSPORTE:
                    achados.append(f"linha {no.lineno}: decide pelo nome `{no.id}`")
    return achados


@pytest.mark.parametrize(("relativo", "escopo_alvo"), ESCOPOS)
def test_o_caminho_do_mouse_emulado_nao_decide_por_transporte(
    relativo: str, escopo_alvo: str | None
) -> None:
    """Nenhum dos quatro escopos pode passar a mudar de comportamento por fio.

    MORDE: plante `if state.transport == "bt": return` no começo de
    `dispatch_mouse` e este nó reprova nomeando o arquivo e a linha. É a forma
    exata do defeito que o mapa de canais existe para pegar — o aparelho
    aceita, e quem recusa é uma linha nossa.
    """
    caminho = PACOTE / relativo
    achados = gates_de_transporte(caminho.read_text(encoding="utf-8"), escopo_alvo)
    assert achados == [], (
        f"{relativo}"
        + (f"::{escopo_alvo}" if escopo_alvo else "")
        + " passou a decidir por transporte:\n  "
        + "\n  ".join(achados)
        + "\nA célula `entrada.emulacao_mouse.*@dualsense` do mapa afirma que o "
        "caminho é o MESMO nos dois fios. Se a decisão é legítima, mude a célula "
        "antes de mudar o código."
    )


# --- o driver que esta casa instala ---------------------------------------

#: As âncoras do `dualsense_parse_report`, na ordem em que têm de aparecer.
_ARM_USB = "if (hdev->bus == BUS_USB && report->id == DS_INPUT_REPORT_USB &&"
_ARM_BT = "} else if (hdev->bus == BUS_BLUETOOTH && report->id == DS_INPUT_REPORT_BT &&"
_FECHA = 'hid_err(hdev, "Unhandled reportID=%d\\n", report->id);'

#: Os seis eixos que o mouse emulado lê: dois de stick (cursor) e dois de
#: gatilho (botão). `ABS_RX`/`ABS_RY` entram porque são a rolagem.
EIXOS_DO_GAMEPAD = ("ABS_X", "ABS_Y", "ABS_RX", "ABS_RY", "ABS_Z", "ABS_RZ")


def _ancoras_do_parse() -> tuple[list[str], int, int, int]:
    linhas = DRIVER.read_text(encoding="utf-8").splitlines()

    def onde(agulha: str) -> int:
        for i, ln in enumerate(linhas):
            if agulha in ln:
                return i
        raise AssertionError(f"âncora sumiu do driver: {agulha!r}")

    i_usb = onde(_ARM_USB)
    i_bt = onde(_ARM_BT)
    i_fecha = next(i for i, ln in enumerate(linhas) if i > i_bt and _FECHA in ln)
    return linhas, i_usb, i_bt, i_fecha


def test_os_eixos_do_gamepad_nascem_depois_da_porta_de_barramento() -> None:
    """Os seis eixos saem do MESMO `ds_report`, fora dos dois braços de fio.

    É a prova de que o evdev normaliza: o que muda entre USB e Bluetooth é o
    OFFSET do payload (`&data[1]` contra `&data[2]`, este sob CRC-32) e mais
    nada. Depois da porta há um caminho só.

    MORDE: mova qualquer `input_report_abs(ds->gamepad, ABS_*, ...)` para
    dentro do braço USB e este nó reprova.
    """
    linhas, i_usb, i_bt, i_fecha = _ancoras_do_parse()
    assert i_usb < i_bt < i_fecha, "a ordem dos braços de barramento mudou no driver"
    janela = range(i_usb, min(i_fecha + 60, len(linhas)))
    for eixo in EIXOS_DO_GAMEPAD:
        agulha = f"input_report_abs(ds->gamepad, {eixo},"
        ocorrencias = [i for i in janela if agulha in linhas[i]]
        assert len(ocorrencias) == 1, (
            f"`{agulha}` aparece {len(ocorrencias)} vez(es) no "
            "`dualsense_parse_report` — era para ser exatamente uma, num "
            "caminho só."
        )
        assert ocorrencias[0] > i_fecha, (
            f"`{eixo}` passou a ser reportado DENTRO de um braço de barramento "
            f"(linha {ocorrencias[0] + 1} do driver, contra o fecho em "
            f"{i_fecha + 1}). O mapa afirma que o eixo é o mesmo nos dois fios."
        )


def test_no_cabo_nao_ha_crc_de_entrada_a_conferir() -> None:
    """O `0x01` de 64 B do cabo não tem trailer de CRC — logo não há falha.

    É o que fecha o lado CABO de `combinacao.dois_no_radio.crc@dualsense`:
    `cabo_aciona = não` com `nada-a-acionar`, e a causa é o protocolo.

    MORDE: acrescente uma chamada de `ps_check_crc32` no braço USB e este nó
    reprova; troque o `static_assert` e ele reprova também.
    """
    linhas, i_usb, i_bt, i_fecha = _ancoras_do_parse()
    conferencias = [i for i in range(i_usb, i_fecha) if "ps_check_crc32(" in linhas[i]]
    assert len(conferencias) == 1, (
        "o `dualsense_parse_report` passou a conferir CRC em mais de um lugar: "
        f"linhas {[i + 1 for i in conferencias]}"
    )
    assert conferencias[0] > i_bt, (
        "a conferência de CRC de entrada saiu do braço Bluetooth — o cabo não "
        "tem trailer de CRC para conferir."
    )
    fonte = DRIVER.read_text(encoding="utf-8")
    assert re.search(r"#define\s+DS_INPUT_REPORT_USB_SIZE\s+64\b", fonte), (
        "o tamanho do report de entrada por USB mudou no driver"
    )
    assert (
        "static_assert(sizeof(struct dualsense_input_report) == "
        "DS_INPUT_REPORT_USB_SIZE - 1);" in fonte
    ), (
        "sumiu o `static_assert` que prova que os 63 bytes depois do id são "
        "TODOS payload — é ele que diz que não sobra trailer de CRC no cabo."
    )


# --- o dono do cursor do touchpad -----------------------------------------


def test_o_cursor_do_touchpad_tem_outro_dono() -> None:
    """Com o libinput no comando, o `TouchpadReader` NÃO acumula movimento.

    É a premissa derrubada: o touchpad e o par gatilho/analógico não passam
    pelo mesmo dono, então a observação dela de 11/08 não descreve três coisas
    simétricas. Aqui a régua é de COMPORTAMENTO, não de texto.

    MORDE: tire o `not self._ponteiro_do_sistema` de `_acumula_agora` e este nó
    reprova — o delta passa a acumular com o libinput já movendo o cursor, que
    é o cursor andando duas vezes.
    """
    from hefesto_dualsense4unix.core.evdev_reader import TouchpadReader

    # Caminho inexistente de propósito: o `__init__` não abre nada, e assim o
    # teste não enumera `/dev/input` nem toca no aparelho dela.
    leitor = TouchpadReader(device_path=Path("/dev/input/event-que-nao-existe"))
    leitor._touching = True

    leitor._ponteiro_do_sistema = True
    leitor._accumulate_axis_x(100)  # só ancora
    leitor._accumulate_axis_x(160)  # andaria 60, se o dono fosse o hefesto
    assert leitor.consume_motion() == (0, 0), (
        "o `TouchpadReader` acumulou movimento com o libinput como dono do "
        "cursor (TOUCHPAD-DO-SISTEMA-01)"
    )

    leitor._ponteiro_do_sistema = False
    leitor._motion_last_x = None
    leitor._accumulate_axis_x(100)
    leitor._accumulate_axis_x(160)
    assert leitor.consume_motion() == (60, 0), (
        "sem o libinput no comando o reader TEM de acumular — senão esta régua "
        "passaria por estar quebrada, não por medir"
    )


def test_o_gatilho_e_o_analogico_nao_passam_pelo_touchpad() -> None:
    """As duas fontes do cursor são funções DIFERENTES, e é isso que se guarda.

    `dispatch_mouse` lê o gatilho e o analógico de `state` (o snapshot do
    controle) e o touchpad de `_touchpad_reader.consume_motion()`. Fundir as
    duas apagaria a explicação da assimetria que ela observou.

    MORDE: faça o dreno do touchpad sair de `state` e este nó reprova.
    """
    fonte = (PACOTE / "daemon" / "subsystems" / "mouse.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    despacho = next(
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.FunctionDef) and no.name == "dispatch_mouse"
    )
    trecho = ast.get_source_segment(fonte, despacho) or ""
    for campo in ("state.l2_raw", "state.r2_raw", "state.raw_lx", "state.raw_ly"):
        assert campo in trecho, f"`dispatch_mouse` parou de ler `{campo}`"
    assert "consume_motion" in trecho, (
        "`dispatch_mouse` parou de drenar o touchpad pelo reader — as duas "
        "fontes do cursor viraram uma"
    )
    assert "_touchpad_reader" in trecho, (
        "o touchpad deixou de vir do `TouchpadReader`; se ele passou a vir de "
        "`state`, a assimetria de 11/08 perde a explicação medida"
    )


# --- as células do mapa ----------------------------------------------------

#: `id` -> (coluna, valor) que esta frente escreveu em 03/09/2026. Apagar
#: qualquer uma reabre uma pergunta que já foi respondida.
CELULAS_ESPERADAS: dict[str, dict[str, str]] = {
    # As seis células abaixo mudaram em 05/09/2026, medidas por ela nos dois
    # transportes — ver o bloco O LADO DO RÁDIO FOI MEDIDO, no topo.
    "entrada.emulacao_mouse.gatilhos@dualsense": {
        "cabo_aciona": "sim",
        "cabo_de_onde_sei": "medido",
        "radio_aciona": "sim",
        "radio_de_onde_sei": "medido",
    },
    "entrada.emulacao_mouse.analogico@dualsense": {
        "cabo_aciona": "sim",
        "cabo_de_onde_sei": "medido",
        "radio_aciona": "sim",
        "radio_de_onde_sei": "medido",
    },
    "combinacao.dois_no_radio.crc@dualsense": {
        "cabo_aciona": "não",
        "cabo_por_que_nao_aciona": "nada-a-acionar",
        "cabo_de_onde_sei": "inferido-do-codigo",
    },
    "combinacao.dois_no_radio.saida@dualsense": {
        "cabo_aciona": "não",
        "cabo_por_que_nao_aciona": "nada-a-acionar",
        "cabo_de_onde_sei": "afirmado-no-doc",
    },
    "entrada.stick.calibracao@dualsense": {
        "cabo_aceita": "sim",
        "cabo_aciona": "não",
        "radio_aciona": "não",
        "cabo_por_que_nao_aciona": "so-ela-decide",
        "radio_por_que_nao_aciona": "so-ela-decide",
    },
    "luz.recursos_proprios@dualsense": {
        "cabo_aciona": "não",
        "radio_aciona": "não",
        # A causa fica VAZIA de propósito — ela é mista, e o `cabo_detalhe` diz
        # por quê. Trocar por uma palavra do domínio sem partir a linha em duas
        # chaves é o que esta régua impede.
        "cabo_por_que_nao_aciona": "",
        "radio_por_que_nao_aciona": "",
    },
}

#: As linhas cuja `assimetria_declarada` carrega a explicação — vazia, a régua
#: 7 do `check_paridade_transporte.py` volta a acusar assimetria não declarada.
COM_ASSIMETRIA = (
    "entrada.emulacao_mouse.gatilhos@dualsense",
    "entrada.emulacao_mouse.analogico@dualsense",
    "combinacao.dois_no_radio.crc@dualsense",
    "combinacao.dois_no_radio.saida@dualsense",
    "entrada.stick.calibracao@dualsense",
)


def _linhas_do_mapa() -> dict[str, dict[str, str]]:
    with MAPA.open(newline="", encoding="utf-8") as fh:
        return {linha["id"]: linha for linha in csv.DictReader(fh)}


def test_as_celulas_respondidas_seguem_respondidas() -> None:
    """MORDE: esvazie qualquer uma das células e este nó reprova, dizendo qual."""
    mapa = _linhas_do_mapa()
    faltando: list[str] = []
    for ident, colunas in CELULAS_ESPERADAS.items():
        linha = mapa.get(ident)
        assert linha is not None, f"a linha `{ident}` sumiu do mapa"
        for coluna, esperado in colunas.items():
            atual = (linha.get(coluna) or "").strip()
            if atual != esperado:
                faltando.append(f"{ident} · {coluna}: {atual!r} (esperado {esperado!r})")
    assert faltando == [], "células do mapa mudaram sem a régua acompanhar:\n  " + "\n  ".join(
        faltando
    )


@pytest.mark.parametrize("ident", COM_ASSIMETRIA)
def test_a_assimetria_continua_declarada(ident: str) -> None:
    """A diferença entre os dois fios calada é o defeito que o mapa pega.

    MORDE: apague a `assimetria_declarada` de qualquer uma e este nó reprova.
    """
    linha = _linhas_do_mapa()[ident]
    assert (linha.get("assimetria_declarada") or "").strip(), (
        f"`{ident}` voltou a divergir entre cabo e rádio sem uma palavra de "
        "explicação"
    )
