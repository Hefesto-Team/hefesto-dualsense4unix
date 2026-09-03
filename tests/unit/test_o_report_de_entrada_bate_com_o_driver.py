"""O report de ENTRADA do DualSense: a página e o mapa contra o DRIVER desta máquina.

Nasceu em 03/09/2026, de um levantamento em fonte externa. A página nova —
`docs/protocol/dualsense-report-de-entrada.md` — publica uma tabela de offsets
e um mapa de bits que vieram de CINCO fontes concordantes. Cinco fontes que
concordam ainda são prosa: nada impede que a próxima pessoa digite `9` onde
está `8`, e nenhum portão desta casa enxergaria.

**A régua não digita número nenhum: ela LÊ.** Os offsets são recalculados do
`struct dualsense_input_report` do driver COMPILADO nesta máquina, somando o
tamanho de cada campo; as máscaras de botão são lidas dos `#define
DS_BUTTONS*`. Se a página e o driver divergirem em um byte ou em um bit, isto
reprova — e se alguém mexer no driver, reprova também, que é o certo: a página
promete descrever aquele fonte.

O QUE ESTE TESTE **NÃO** MEDE, e é preciso dizer: ele não toca aparelho nenhum.
Ele prova concordância entre três textos desta árvore. Que o APARELHO publique
esses bytes é outra afirmação, e o grau dela está escrito nas células do mapa —
`afirmado-no-doc` para o mapa de bits, `medido` só para o que a bancada mediu
em 15/08/2026.

A MORDIDA, provada em 03/09/2026 (ver a docstring de cada teste): trocar UM
número na tabela da página reprova; trocar UM bit no mapa de bits reprova;
esvaziar UMA célula de offset do mapa reprova.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DRIVER = RAIZ / "assets" / "dkms" / "hid-playstation" / "hid-playstation.c"
PAGINA = RAIZ / "docs" / "protocol" / "dualsense-report-de-entrada.md"
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

#: Quanto ocupa cada tipo do driver, em bytes. `dualsense_touch_point` tem
#: `static_assert(sizeof(...) == 4)` no próprio fonte — não é chute.
TAMANHOS = {
    "u8": 1,
    "__le16": 2,
    "__le32": 4,
    "struct dualsense_touch_point": 4,
}

#: As cinco chaves do tema ENTRADA, e o que cada uma tem de trazer. A lista
#: vive aqui porque é o contrato do levantamento; o CONTEÚDO das células é lido
#: do arquivo, nunca redigitado.
CHAVES_DO_TEMA = (
    "entrada.botoes",
    "entrada.stick",
    "entrada.stick.calibracao",
    "gatilho.analogico",
    "entrada.combo.ponte",
)


def _texto(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


def _campos_do_struct() -> list[tuple[str, int]]:
    """Devolve [(nome, offset)] lido do `struct dualsense_input_report`.

    Some o tamanho campo a campo, na ordem do fonte. Não há número escrito
    aqui: se o driver ganhar um campo, os offsets seguintes andam sozinhos.
    """
    fonte = _texto(DRIVER)
    corpo = re.search(
        r"struct dualsense_input_report \{(.*?)\n\} __packed;", fonte, re.S
    )
    assert corpo, "o `struct dualsense_input_report` sumiu do driver desta árvore"

    campos: list[tuple[str, int]] = []
    offset = 0
    for linha in corpo.group(1).splitlines():
        linha = re.sub(r"/\*.*?\*/", "", linha).strip().rstrip(";")
        if not linha or linha.startswith("/*") or linha.startswith("*"):
            continue
        # O tipo sai da tabela pelo PREFIXO da linha. Nenhum dos quatro é
        # prefixo de outro, então a primeira casada é a certa.
        tipo = next((t for t in TAMANHOS if linha.startswith(t + " ")), None)
        if tipo is None:
            pytest.fail(f"tipo desconhecido no struct de entrada: {linha!r}")
        tamanho = TAMANHOS[tipo]
        declaracoes = linha[len(tipo) :].strip()
        for decl in (d.strip() for d in declaracoes.split(",")):
            nome = decl
            quantos = 1
            vetor = re.match(r"(\w+)\[(\d+)\]$", decl)
            if vetor:
                nome, quantos = vetor.group(1), int(vetor.group(2))
            campos.append((nome, offset))
            offset += tamanho * quantos
    return campos


def _mascaras_de_botao() -> dict[str, int]:
    """Lê os `#define DS_BUTTONS*` do driver e devolve {nome: máscara}."""
    fonte = _texto(DRIVER)
    mascaras: dict[str, int] = {}
    for nome, corpo in re.findall(
        r"#define\s+(DS_BUTTONS\d_\w+)\s+(BIT\(\d+\)|GENMASK\(\d+,\s*\d+\))", fonte
    ):
        bit = re.match(r"BIT\((\d+)\)", corpo)
        if bit:
            mascaras[nome] = 1 << int(bit.group(1))
        else:
            alto, baixo = (int(n) for n in re.findall(r"\d+", corpo))
            mascaras[nome] = ((1 << (alto + 1)) - 1) - ((1 << baixo) - 1)
    assert mascaras, "os `#define DS_BUTTONS*` sumiram do driver desta árvore"
    return mascaras


def _linhas_do_mapa() -> dict[str, dict[str, str]]:
    csv.field_size_limit(10**9)
    with MAPA.open(newline="", encoding="utf-8") as f:
        return {
            linha["chave"]: linha
            for linha in csv.DictReader(f)
            if linha["controle"] == "dualsense" and linha["chave"] in CHAVES_DO_TEMA
        }


# ─────────────────────────────────────────────────────────────────────────────
# A tabela de offsets da página contra o struct do driver
# ─────────────────────────────────────────────────────────────────────────────

#: Como cada campo do struct aparece na tabela da página. O offset ABSOLUTO do
#: cabo é `corpo + 1` e o do `0x31` é `corpo + 2` — as duas âncoras estão em
#: `hid-playstation.c:1581` e `:1592`, e o teste as confere logo abaixo.
LINHAS_DA_PAGINA = {
    "x": "LX",
    "y": "LY",
    "rx": "RX",
    "ry": "RY",
    "z": "**L2 analógico**",
    "rz": "**R2 analógico**",
    "seq_number": "contador de quadro",
    "buttons": "**`buttons[4]`**",
}


@pytest.mark.parametrize("campo,rotulo", sorted(LINHAS_DA_PAGINA.items()))
def test_a_pagina_publica_o_offset_que_o_driver_calcula(campo: str, rotulo: str) -> None:
    """Cada campo do corpo tem de aparecer na tabela com os TRÊS offsets certos.

    MORDIDA (03/09/2026): trocar na página o `6 | 7 | 8 | contador de quadro`
    por `6 | 8 | 8` reprova com o offset absoluto de cabo do `seq_number`.
    """
    offsets = dict(_campos_do_struct())
    assert campo in offsets, f"o driver não declara mais o campo {campo!r}"
    corpo = offsets[campo]

    # os vetores ocupam faixa; a página escreve `7-10`, o escalar escreve `7`
    largura = {"buttons": 4}.get(campo, 1)
    if largura == 1:
        celula_corpo = str(corpo)
        celula_cabo = str(corpo + 1)
        celula_radio = str(corpo + 2)
    else:
        celula_corpo = f"{corpo}-{corpo + largura - 1}"
        celula_cabo = f"{corpo + 1}-{corpo + largura}"
        celula_radio = f"{corpo + 2}-{corpo + largura + 1}"

    esperada = f"| {celula_corpo} | {celula_cabo} | {celula_radio} | {rotulo} |"
    assert esperada in _texto(PAGINA), (
        f"a página não traz a linha de {campo!r} com os offsets que o driver "
        f"calcula. Esperado começar com: {esperada!r}"
    )


def test_as_ancoras_de_cabo_e_de_radio_continuam_um_e_dois() -> None:
    """`data[1]` no cabo e `data[2]` no rádio — é o que faz o `+1` e o `+2` acima.

    MORDIDA: trocar a âncora do rádio para `&data[1]` no driver reprova aqui.
    """
    fonte = _texto(DRIVER)
    assert "(struct dualsense_input_report *)&data[1]" in fonte, (
        "o driver deixou de ancorar o corpo do report de CABO em data[1]"
    )
    assert "(struct dualsense_input_report *)&data[2]" in fonte, (
        "o driver deixou de ancorar o corpo do report de RÁDIO em data[2]"
    )
    pagina = _texto(PAGINA)
    assert "| `0x01` | cabo | 64 B | `data[1]` | — |" in pagina
    assert "`0x31` | rádio, estendido | 78 B | `data[2]` |" in pagina


def test_os_tres_tamanhos_de_report_saem_do_driver_e_do_sdl() -> None:
    """64 no cabo, 78 no `0x31`, 10 no `0x01` mínimo.

    Os dois primeiros o driver declara; o terceiro NÃO — ele vem de fonte
    externa, e a página diz isso. Aqui só se confere que os dois do driver não
    andaram debaixo da página.
    """
    fonte = _texto(DRIVER)
    assert "#define DS_INPUT_REPORT_USB_SIZE\t\t64" in fonte
    assert "#define DS_INPUT_REPORT_BT_SIZE\t\t\t78" in fonte
    pagina = _texto(PAGINA)
    assert "| `0x01` | cabo | 64 B |" in pagina
    assert "78 B | `data[2]`" in pagina
    assert "**10 B**" in pagina


# ─────────────────────────────────────────────────────────────────────────────
# O mapa de bits da página contra os `#define` do driver
# ─────────────────────────────────────────────────────────────────────────────

#: O que a página promete, por `#define` do driver: (byte, bit, rótulo).
BITS_PROMETIDOS = {
    "DS_BUTTONS0_SQUARE": ("buttons[0]", 4, "quadrado"),
    "DS_BUTTONS0_CROSS": ("buttons[0]", 5, "cruz"),
    "DS_BUTTONS0_CIRCLE": ("buttons[0]", 6, "círculo"),
    "DS_BUTTONS0_TRIANGLE": ("buttons[0]", 7, "triângulo"),
    "DS_BUTTONS1_L1": ("buttons[1]", 0, "L1"),
    "DS_BUTTONS1_R1": ("buttons[1]", 1, "R1"),
    "DS_BUTTONS1_L2": ("buttons[1]", 2, "L2 (digital)"),
    "DS_BUTTONS1_R2": ("buttons[1]", 3, "R2 (digital)"),
    "DS_BUTTONS1_CREATE": ("buttons[1]", 4, "Create"),
    "DS_BUTTONS1_OPTIONS": ("buttons[1]", 5, "Options"),
    "DS_BUTTONS1_L3": ("buttons[1]", 6, "L3"),
    "DS_BUTTONS1_R3": ("buttons[1]", 7, "R3"),
    "DS_BUTTONS2_PS_HOME": ("buttons[2]", 0, "PS"),
    "DS_BUTTONS2_TOUCHPAD": ("buttons[2]", 1, "touchpad"),
    "DS_BUTTONS2_MIC_MUTE": ("buttons[2]", 2, "mudo do microfone"),
}


@pytest.mark.parametrize("define,promessa", sorted(BITS_PROMETIDOS.items()))
def test_o_mapa_de_bits_da_pagina_bate_com_o_driver(
    define: str, promessa: tuple[str, int, str]
) -> None:
    """O bit que a página publica é o bit que o driver define.

    MORDIDA (03/09/2026): trocar na página `| `buttons[1]` | 7 | R3 |` por
    `| `buttons[1]` | 6 | R3 |` reprova em DS_BUTTONS1_R3 e em DS_BUTTONS1_L3
    de uma vez.
    """
    byte, bit, rotulo = promessa
    mascaras = _mascaras_de_botao()
    assert define in mascaras, f"o driver não define mais {define}"
    assert mascaras[define] == 1 << bit, (
        f"{define} vale {mascaras[define]:#04x} no driver, e a página promete "
        f"o bit {bit} ({1 << bit:#04x})"
    )
    esperada = f"| `{byte}` | {bit} | {rotulo} |"
    assert esperada in _texto(PAGINA), (
        f"a página não traz {esperada!r} — o mapa de bits e o driver divergem"
    )


def test_o_hat_e_valor_e_nao_bitmap() -> None:
    """O nibble baixo do `buttons[0]` é um VALOR de 0 a 8, e a página avisa.

    Ler o nibble como quatro bits mostra o D-pad neutro como cima+baixo — é o
    erro que esta linha existe para impedir.
    """
    mascaras = _mascaras_de_botao()
    assert mascaras["DS_BUTTONS0_HAT_SWITCH"] == 0x0F, (
        "o hat deixou de ocupar os quatro bits baixos do buttons[0]"
    )
    pagina = _texto(PAGINA)
    assert "| `buttons[0]` | 3..0 | **hat**, como valor:" in pagina
    assert "**8 = centro**" in pagina
    assert "O hat é **valor, não bitmap**" in pagina


def test_o_driver_desta_maquina_nao_le_os_bits_do_edge() -> None:
    """A página afirma que as costas de um Edge não chegam por evdev aqui.

    A afirmação é sobre ESTE fonte, então é ele que a sustenta: se um dia o
    driver ganhar máscara para os bits 4-7 do `buttons[2]`, esta reprova e a
    página tem de mudar.
    """
    mascaras = _mascaras_de_botao()
    do_byte_dois = {
        nome: valor for nome, valor in mascaras.items() if nome.startswith("DS_BUTTONS2_")
    }
    assert do_byte_dois, "o driver não define mais nenhuma máscara de buttons[2]"
    assert all(valor <= 0x04 for valor in do_byte_dois.values()), (
        "o driver ganhou máscara acima do bit 2 no buttons[2] — os bits do "
        f"DualSense Edge podem ter chegado: {do_byte_dois}"
    )
    assert (
        "as costas de um Edge não chegam por evdev nesta máquina" in _texto(PAGINA)
    )


# ─────────────────────────────────────────────────────────────────────────────
# O mapa de canais — as cinco linhas do tema deixaram de ter caminho incompleto
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("chave", CHAVES_DO_TEMA)
def test_a_linha_do_tema_tem_report_id_e_offset_nos_dois_transportes(chave: str) -> None:
    """O buraco que este levantamento veio fechar: `report_id` e `offset` vazios.

    MORDIDA (03/09/2026): esvaziar `radio_offset` de `gatilho.analogico` reprova
    nomeando a célula.
    """
    linhas = _linhas_do_mapa()
    assert chave in linhas, f"a linha {chave}@dualsense sumiu do mapa"
    linha = linhas[chave]
    vazias = [
        coluna
        for coluna in ("cabo_report_id", "radio_report_id", "cabo_offset", "radio_offset")
        if not (linha[coluna] or "").strip()
    ]
    assert not vazias, (
        f"{chave}@dualsense voltou a ter caminho incompleto: {vazias} vazia(s)"
    )


@pytest.mark.parametrize("chave", CHAVES_DO_TEMA)
def test_conteudo_de_transporte_viaja_com_procedencia(chave: str) -> None:
    """Célula de conteúdo escrita exige `de_onde_sei` do MESMO lado preenchido.

    É a regra 19 do `check_paridade_transporte`, repetida aqui para as cinco
    linhas do tema — porque lá ela só dispara quando `aciona` está respondido, e
    a `entrada.stick.calibracao` tem `aciona` VAZIO de propósito.
    """
    linha = _linhas_do_mapa()[chave]
    for lado in ("cabo", "radio"):
        escreveu = any(
            (linha[f"{lado}_{sufixo}"] or "").strip()
            for sufixo in ("offset", "report_id", "comando", "detalhe", "ressalva")
        )
        if escreveu:
            assert (linha[f"{lado}_de_onde_sei"] or "").strip(), (
                f"{chave}@dualsense tem conteúdo de {lado} sem `{lado}_de_onde_sei`"
            )


def test_a_calibracao_de_stick_deixou_de_ser_desconhecida_e_nao_mentiu_o_grau() -> None:
    """A linha que estava muda: `existe` subiu, e o grau NÃO subiu junto.

    Nada foi a aparelho nesta leva, então `medido` aqui seria mentira que
    portão nenhum pega — e `ate_onde_foi` tem de continuar vazio.
    """
    linha = _linhas_do_mapa()["entrada.stick.calibracao"]
    assert linha["existe"] == "tem", (
        "a `entrada.stick.calibracao@dualsense` voltou a `desconhecido` — se foi "
        "de propósito, a página `dualsense-report-de-entrada.md` §6 caducou junto"
    )
    for lado in ("cabo", "radio"):
        assert linha[f"{lado}_de_onde_sei"] == "afirmado-no-doc", (
            f"o grau de {lado} da calibração de stick não é mais `afirmado-no-doc`; "
            "só sobe com bancada, e a página diz que ninguém desta casa leu um byte"
        )
        assert not (linha[f"{lado}_ate_onde_foi"] or "").strip(), (
            f"`{lado}_ate_onde_foi` da calibração de stick foi preenchido, e nada "
            "foi enviado a aparelho nenhum nesta leva"
        )


def test_a_leitura_da_calibracao_e_a_mesma_familia_da_cor_do_plastico() -> None:
    """O `[12, 2]` e o `[1, 19]` são o mesmo mecanismo — e é o que dá crédito ao achado.

    Se a página parar de dizer isso, o leitor perde a única razão pela qual esta
    casa espera que o comando responda: o par `0x80`/`0x81` já foi medido aqui.
    """
    pagina = _texto(PAGINA)
    assert "SET_FEATURE 0x80  payload [12, 2]" in pagina
    assert "GET_FEATURE 0x81 -> 64 bytes" in pagina
    assert "`[1, 19]` devolve o serial" in pagina
    linha = _linhas_do_mapa()["entrada.stick.calibracao"]
    assert "[12, 2]" in linha["cabo_comando"], (
        "o `cabo_comando` da calibração de stick perdeu o payload de leitura"
    )
    assert "0x82" in linha["cabo_comando"] and "0x83" in linha["cabo_comando"], (
        "o `cabo_comando` perdeu o ciclo de calibração `0x82`/`0x83`"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Os NÚMEROS dentro das células do mapa — a metade que os testes acima não veem
# ─────────────────────────────────────────────────────────────────────────────
# Os testes de cima cobram que a célula não esteja VAZIA e que a PÁGINA bata com
# o driver. Sobra o meio: uma célula CHEIA pode dizer `payload[9]` onde o driver
# diz 7, e nada acusa. É o estrago que o `check_paridade_transporte` declara não
# alcançar — «nenhum portão sem hardware e sem rede consegue dizer que o byte é
# 11 e não 47». Ele alcança, quando o dono do número mora na árvore. Mora.


def _indices_citados(celula: str, palavra: str) -> set[int]:
    """Os índices que a célula cita em `palavra[...]`, com as FAIXAS abertas.

    A notação desta casa escreve faixa: `payload[32..35] = report[33..36]` é
    como `toque.touchpad@dualsense` está escrita desde que nasceu. Um leitor
    que só enxergasse `payload[32` acharia que a célula não cita o 35 — e
    reprovaria a célula CERTA, que é o pior defeito que uma régua pode ter.
    """
    achados: set[int] = set()
    for inicio, fim in re.findall(
        re.escape(palavra) + r"\[(\d+)(?:\s*\.\.\s*(\d+))?", celula
    ):
        primeiro = int(inicio)
        achados.update(range(primeiro, (int(fim) if fim else primeiro) + 1))
    return achados


#: chave do mapa -> {campo do struct: offset de CORPO que a célula tem de citar}.
#:
#: `entrada.combo.ponte` fica FORA de propósito: ela endereça só DOIS dos quatro
#: bytes de `buttons[]` — os de PS e R3 —, e cobrar dela o `payload[7]` das
#: faces reprovaria a célula certa. Quem a mede é
#: :func:`test_o_combo_da_ponte_cita_os_bits_de_ps_e_de_r3`, que calcula o byte
#: a partir do `#define` de cada botão.
OFFSETS_QUE_A_CELULA_AFIRMA = {
    "entrada.stick": {"x": 0, "y": 1, "rx": 2, "ry": 3},
    "gatilho.analogico": {"z": 4, "rz": 5},
    "entrada.botoes": {"buttons": 7},
}


@pytest.mark.parametrize("chave", sorted(OFFSETS_QUE_A_CELULA_AFIRMA))
def test_o_payload_citado_na_celula_sai_do_struct_do_driver(chave: str) -> None:
    """Cada `payload[N]` da célula é o offset do campo no struct.

    MORDIDA (03/09/2026): trocar `payload[0..3]` por `payload[1..3]` no
    `cabo_offset` de `entrada.stick` reprova nomeando o eixo X.
    """
    offsets = dict(_campos_do_struct())
    celula = _linhas_do_mapa()[chave]["cabo_offset"]
    citados = _indices_citados(celula, "payload")
    for campo, esperado in OFFSETS_QUE_A_CELULA_AFIRMA[chave].items():
        assert offsets[campo] == esperado, (
            f"o driver põe `{campo}` no payload[{offsets[campo]}] e esta régua "
            f"esperava payload[{esperado}] — o report mudou"
        )
        assert esperado in citados, (
            f"{chave}@dualsense.cabo_offset não cita payload[{esperado}], que é "
            f"onde o driver põe `{campo}`. Citados: {sorted(citados)}"
        )


@pytest.mark.parametrize("chave", sorted(OFFSETS_QUE_A_CELULA_AFIRMA))
def test_o_report_citado_na_celula_soma_a_ancora_do_transporte(chave: str) -> None:
    """`report[M]` é `payload[N]` mais a âncora do braço — 1 no cabo, 2 no rádio.

    É a assimetria que este mapa existe para pegar. Uma célula que copie o
    número do cabo para o lado do rádio aponta o campo VIZINHO, sem erro e sem
    log — e o sintoma, na mesa dela, é dado ERRADO, não dado ausente.

    MORDIDA (03/09/2026): a mesma troca do teste acima reprova aqui também, nos
    dois lados de uma vez.
    """
    offsets = dict(_campos_do_struct())
    linha = _linhas_do_mapa()[chave]
    for lado, ancora in (("cabo", 1), ("radio", 2)):
        citados = _indices_citados(linha[f"{lado}_offset"], "report")
        for campo in OFFSETS_QUE_A_CELULA_AFIRMA[chave]:
            esperado = offsets[campo] + ancora
            assert esperado in citados, (
                f"{chave}@dualsense.{lado}_offset não cita report[{esperado}] — "
                f"payload[{offsets[campo]}] (`{campo}`) mais a âncora {ancora} "
                f"do {lado}. Citados: {sorted(citados)}"
            )


#: Como a célula do mapa nomeia, em português, cada `#define` do driver.
BOTOES_NOMEADOS_NA_CELULA = {
    "quadrado": "DS_BUTTONS0_SQUARE",
    "cruz": "DS_BUTTONS0_CROSS",
    "círculo": "DS_BUTTONS0_CIRCLE",
    "triângulo": "DS_BUTTONS0_TRIANGLE",
    "L1": "DS_BUTTONS1_L1",
    "R1": "DS_BUTTONS1_R1",
    "Create": "DS_BUTTONS1_CREATE",
    "Options": "DS_BUTTONS1_OPTIONS",
    "L3": "DS_BUTTONS1_L3",
    "R3": "DS_BUTTONS1_R3",
    "PS": "DS_BUTTONS2_PS_HOME",
}


def test_cada_bit_de_botao_na_celula_e_o_bit_do_define_do_driver() -> None:
    """`5 = cruz` na célula tem de ser `DS_BUTTONS0_CROSS BIT(5)` no driver.

    MORDIDA (03/09/2026): trocar `5 = cruz` por `3 = cruz` no `cabo_offset` de
    `entrada.botoes` reprova nomeando o botão.
    """
    mascaras = _mascaras_de_botao()
    celula = _linhas_do_mapa()["entrada.botoes"]["cabo_offset"]
    for rotulo, define in BOTOES_NOMEADOS_NA_CELULA.items():
        bit = mascaras[define].bit_length() - 1
        assert mascaras[define] == 1 << bit, f"{define} deixou de ser um bit só"
        assert re.search(rf"\b{bit}\s*=\s*{re.escape(rotulo)}\b", celula), (
            f"o driver diz que `{rotulo}` é o bit {bit} (`{define}`), e a célula "
            f"`entrada.botoes@dualsense`.cabo_offset não afirma isso"
        )


def test_o_combo_da_ponte_cita_os_bits_de_ps_e_de_r3() -> None:
    """A metade de LEITURA do gesto tem endereço, e ele tem de ser o certo.

    Os dois botões do gesto caem em BYTES diferentes do mesmo `buttons[]` — é o
    que responde, sem aparelho, à pergunta que a linha carregava: não há como o
    aparelho publicar um sem o outro por acidente de máscara. Se um `#define`
    mudar de byte ou de bit, o gesto continua funcionando (o caminho é evdev) e
    só a célula fica mentindo, calada.

    MORDIDA (03/09/2026): trocar `payload[9]` por `payload[8]` no PS reprova.
    """
    mascaras = _mascaras_de_botao()
    base = dict(_campos_do_struct())["buttons"]
    linha = _linhas_do_mapa()["entrada.combo.ponte"]

    for lado, ancora in (("cabo", 1), ("radio", 2)):
        celula = linha[f"{lado}_offset"]
        for nome, define in (("PS", "DS_BUTTONS2_PS_HOME"), ("R3", "DS_BUTTONS1_R3")):
            byte = int(define.removeprefix("DS_BUTTONS")[0])
            bit = mascaras[define].bit_length() - 1
            payload = base + byte
            assert re.search(
                rf"{re.escape(nome)}\s*=\s*payload\[{payload}\]\s*bit\s*{bit}",
                celula,
            ), (
                f"a célula do {lado} tinha de dizer "
                f"`{nome} = payload[{payload}] bit {bit}` — é onde o driver põe "
                f"`{define}`"
            )
            assert re.search(
                rf"report\[{payload + ancora}\]\s*bit\s*{bit}", celula
            ), (
                f"a célula do {lado} tinha de dizer `report[{payload + ancora}] "
                f"bit {bit}` para o `{nome}`"
            )


def test_o_feature_0x05_e_da_imu_e_a_celula_desmente_quem_o_procura() -> None:
    """O achado NEGATIVO desta leva, e é o que mais poupa tempo.

    Esta casa já catalogava o `0x05` como «calibração», e ele é da IMU. Quem
    for caçar o centro do analógico ali acha viés de giro e conclui que a
    calibração não existe. A régua confere as duas metades: que o driver
    decodifique só IMU, e que a célula NOMEIE o 0x05 para desmenti-lo.

    MORDIDA (03/09/2026): tirar as três menções ao `0x05` do `cabo_report_id`
    reprova.
    """
    fonte = _texto(DRIVER)
    declarado = re.search(
        r"#define\s+DS_FEATURE_REPORT_CALIBRATION\s+(0x[0-9a-fA-F]+)", fonte
    )
    assert declarado and int(declarado.group(1), 16) == 0x05

    corpo = fonte[fonte.index("static int dualsense_get_calibration_data") :]
    corpo = corpo[: corpo.index("err_free:")]
    assert "gyro" in corpo and "acc_" in corpo, (
        "a função de calibração do driver deixou de falar de giro e acelerômetro"
    )
    for proibido in ("stick", "->x", "->rx", "deadzone"):
        assert proibido not in corpo, (
            f"a função de calibração do driver passou a mencionar `{proibido}` — "
            "se o 0x05 ganhou dado de analógico, a página §6 e a célula "
            "`entrada.stick.calibracao@dualsense` estão erradas"
        )

    celula = _linhas_do_mapa()["entrada.stick.calibracao"]["cabo_report_id"]
    assert "0x05" in celula, (
        "a célula tem de NOMEAR o 0x05 para desmenti-lo: quem não o vir citado "
        "vai procurar o analógico lá dentro de novo"
    )
    assert "0x80" in celula and "0x82" in celula, (
        "a célula tem de dizer ONDE a calibração do analógico mora"
    )
