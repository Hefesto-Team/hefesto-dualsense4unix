"""A linha `luz.led_microfone` do mapa aponta para o CÓDIGO, não para o vazio.

MIC-DA-MESA-ELEICAO-01 somou ~59 linhas ao `core/backend_pydualsense.py`. A
onda **sabia** da deriva: reapontou as citações na referência canônica (com
comentário explícito) e na linha `audio.saida_dedicada` do CSV. E esqueceu
justamente esta — a linha do `common[8]`, o byte que aquela onda passou a
escrever com endereço, cuja posse ganhou porta de emergência e cujo significado
foi invertido. Achado da auditoria de 02/09/2026.

**POR QUE O PORTÃO QUE JÁ EXISTE NÃO PEGAVA.** O
`scripts/validar-citacoes-de-linha.py` (DECISÃO DELA, 31/08) cobra três coisas:
que a linha exista, que a faixa não esteja invertida, e que um símbolo
PROMETIDO ao lado do endereço esteja na faixa. Uma citação que derivou para
DENTRO de um arquivo que cresceu continua existindo, continua com a faixa em
ordem, e as citações desta linha usam em massa a forma curta ``:N`` — que no
CSV o portão não casa de propósito (ela colide com hora de relógio). Logo a
deriva passa calada: o endereço resolve, e aponta para texto sem relação.

Esta régua fecha esse buraco para a linha do `common[8]`, e o faz do único jeito
que morde: **ancorando cada endereço no CONTEÚDO** que ele promete. Não é
presença de string na prosa — é ir ao arquivo, ler a faixa citada e exigir a
âncora lá dentro.

Mordida: repor qualquer endereço antigo (`:1193-1194`, `:1227-1228`,
`:1036-1056`, `:3884`, `:2403-2416`) na célula — esta régua reprova.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
BACKEND = RAIZ / "src" / "hefesto_dualsense4unix" / "core" / "backend_pydualsense.py"

#: Os campos de prosa desta linha em que os endereços vivem.
CAMPOS = (
    "cabo_evidencia",
    "radio_evidencia",
    "cabo_ressalva",
    "radio_ressalva",
    "cabo_codigo_ref",
    "radio_codigo_ref",
)

#: (faixa citada, âncora que TEM de estar dentro dela).
#:
#: Cada par foi conferido contra o fonte em 02/09/2026 e REMEDIDO em 20/09/2026.
#: O `:442-455` é o que NÃO derivou em nenhuma das ondas — está acima de todo
#: ponto de inserção — e fica aqui de propósito: a cura fácil seria somar a
#: deriva a tudo, e somar nele QUEBRARIA uma referência que estava certa.
#:
#: A REMEDIÇÃO DE 20/09/2026, e a deriva tem QUATRO tamanhos. A
#: ESCRITA-QUE-NÃO-MEDE-01 (`982e3fbca`, 19/09) somou 82 linhas ao
#: `backend_pydualsense.py`, mas não de uma vez: `_escrever_led_do_mic` ficou
#: onde estava, cinco faixas desceram 35, o `should_reclaim_on_wake` desceu 70
#: e as três do fim desceram 82. Cada par foi reapontado pela ÂNCORA, com
#: `difflib` contra o fonte de antes — nunca por aritmética.
#:
#: E UM PAR MUDOU DE FORMA, não só de lugar: aquela onda partiu a escrita em
#: duas. O `self.device.write` saiu do bloco que carimba o `seq` do rádio e foi
#: morar em `_escrever_conferindo`, que existe para DEVOLVER quantos bytes o
#: fio aceitou. A faixa nova (`:1883-1914`) cobre os dois de propósito, porque
#: é isso que a prosa do mapa promete — "o `seq` do handle carimbado e o CRC
#: refeito no próprio write". Encolhê-la para o bloco do `seq` faria a âncora
#: cair; encolhê-la para o `_escrever_conferindo` apontaria para um método que
#: não carimba `seq` nenhum.
ANCORAS: tuple[tuple[str, str], ...] = (
    (":1715-1716", "VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE"),
    (":1758-1764", "common[8] = int(mic_led) & 0xFF"),
    (":1526-1553", "def set_microphone_led"),
    (":5015", "def set_mic_led"),
    (":5022-5023", "report[11] no rádio"),
    (":5024-5028", "CORRIGIDO em 15/08/2026"),
    (":1823-1824", "build_bt_report"),
    (":1883-1914", "self.device.write"),
    (":3419-3432", "should_reclaim_on_wake"),
    (":442-455", "def _escrever_led_do_mic"),
    (":969", "_audio_status"),
)

#: Os endereços que a auditoria aposentou. Se um deles voltar à célula, ou a
#: deriva voltou, ou alguém somou 59 no lugar errado.
APOSENTADOS = (
    # AS ONZE DE BAIXO SE APOSENTARAM EM 20/09/2026, pela
    # O-NO-NASCE-FECHADO-01 (`ace69acef`): a reconciliação da exposição do
    # Modo Nativo entrou no `_poll_loop` e o arquivo cresceu 63 linhas — em
    # TRÊS degraus. As duas primeiras faixas desceram 1, a do
    # `should_reclaim_on_wake` desceu 63 e as três do `set_mic_led` desceram
    # 63 também, mas por outra inserção. Cada par foi reapontado pela ÂNCORA,
    # com `difflib` contra o fonte de `ace69acef~1` — nunca por aritmética.
    ":1714-1715",
    ":1757-1763",
    ":1525-1552",
    ":4952",
    ":4959-4960",
    ":4961-4965",
    ":1822-1823",
    ":1882-1913",
    ":3356-3369",
    ":441-454",
    ":968",
    # AS ONZE DE BAIXO SE APOSENTARAM EM 20/09/2026, pela
    # ESCRITA-QUE-NÃO-MEDE-01: o `self.device.write` ganhou um dono que mede
    # (`_escrever_conferindo`), e o arquivo cresceu 82 linhas em três degraus
    # diferentes. O `:1460-1461` nunca esteve em `ANCORAS` — ele vive só na
    # prosa do mapa, e derivou junto (+35). Entra aqui porque a régua que
    # impede a volta é esta, e meia correção deixa as duas versões vivas.
    ":1849-1856",
    ":4879-4883",
    ":4877-4878",
    ":3286-3299",
    ":1787-1788",
    ":1722-1728",
    ":1679-1680",
    ":1490-1517",
    ":1460-1461",
    ":4870",
    ":933",
    # AS DEZ DE BAIXO SE APOSENTARAM EM 17/09/2026, pela
    # BATERIA-QUE-PULA-01: a guarda `eh_report_de_estado` e o par
    # `_consumir_report`/`_recusar_report` entraram no meio do arquivo.
    # A deriva NÃO é uniforme — nove desceram 83 linhas e `:923` desceu
    # 10, porque os defaults de classe entraram acima dela e os métodos
    # novos abaixo. Somar 83 em todas apontaria `_audio_status` para
    # outra coisa; cada uma foi remedida pela ÂNCORA.
    ":1595-1596",
    ":1639-1645",
    ":1407-1434",
    ":4787",
    ":4794-4795",
    ":4796-4800",
    ":1704-1705",
    ":1766-1773",
    ":3203-3216",
    ":923",
    # AS DUAS DE BAIXO SE APOSENTARAM EM 16/09/2026: a SOM-ROTA-02 deu dono à
    # rota de saída (`common[7]`) na adoção do controle e acrescentou a
    # constante `ROTA_PADRAO_DO_SOM` com a medição que a justifica. As duas
    # foram remedidas pela ÂNCORA, uma a uma — a deriva é +49 na primeira e
    # +166 na segunda, e somar uma delas na outra apontaria para outra coisa.
    ":1546-1547",
    ":4630-4634",
    ":1589-1595",
    ":1357-1384",
    ":4621",
    ":4628-4629",
    ":1654-1655",
    ":1716-1723",
    ":3037-3050",
    ":414-427",
    ":873",
    # AS ONZE DE BAIXO SE APOSENTARAM EM 12/09/2026, e a causa tem nome:
    # a MIC-VOLUME-02 deu dono ao `common[6]` e empurrou o
    # `backend_pydualsense.py` — 68 linhas abaixo do ponto de inserção,
    # 44 acima dele. **A deriva NÃO é uma só**, e é por isso que cada par
    # foi remedido pela ÂNCORA, uma a uma, e não por uma soma única: somar
    # 68 em tudo teria quebrado as três que estavam acima do corte.
    ":1478-1479",
    ":1521-1527",
    ":1313-1340",
    ":4553",
    ":4560-4561",
    ":4562-4566",
    ":1586-1587",
    ":1648-1655",
    ":2969-2982",
    ":361-374",
    ":829",
    ":1252-1253",
    ":1286-1287",
    ":1095-1115",
    ":1346-1347",
    ":1402-1409",
    ":2462-2475",
    ":3949-3950",
    ":3952-3956",
    ":3943",
    ":1193-1194",
    ":1227-1228",
    ":1036-1056",
    ":3884",
    ":3890-3891",
    ":3893-3897",
    ":1287-1288",
    ":1343-1350",
    ":2403-2416",
    #: MIC-BT-DONO-01 (06/09/2026): +21 até `_reapply_desired`, +44 depois dele.
    ":2475-2488",
    ":3956",
    ":3962-3963",
    ":3965-3969",
)


def _linha_do_led() -> dict[str, str]:
    csv.field_size_limit(10**9)
    with MAPA.open(newline="", encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha["chave"] == "luz.led_microfone" and linha["controle"] == "dualsense":
                return linha
    pytest.fail("a linha `luz.led_microfone@dualsense` sumiu do mapa")


def _prosa(linha: dict[str, str]) -> str:
    return "\n".join(linha.get(campo) or "" for campo in CAMPOS)


def test_cada_endereco_citado_contem_a_ancora_que_promete() -> None:
    """Ir ao arquivo, ler a faixa, e exigir a âncora lá dentro."""
    corpo = BACKEND.read_text(encoding="utf-8").splitlines()
    prosa = _prosa(_linha_do_led())

    quebrados: list[str] = []
    ausentes: list[str] = []
    for faixa, ancora in ANCORAS:
        if faixa not in prosa:
            ausentes.append(f"{faixa} (âncora: {ancora})")
            continue
        numeros = [int(n) for n in re.findall(r"\d+", faixa)]
        primeira, ultima = numeros[0], numeros[-1]
        if ultima > len(corpo):
            quebrados.append(f"{faixa}: além do fim ({len(corpo)} linhas)")
            continue
        trecho = "\n".join(corpo[primeira - 1 : ultima])
        if ancora not in trecho:
            quebrados.append(
                f"{faixa}: a faixa NÃO contém {ancora!r} — "
                f"começa em {corpo[primeira - 1].strip()[:60]!r}"
            )

    assert not ausentes, (
        "endereço que a auditoria de 02/09/2026 fixou sumiu da linha "
        "`luz.led_microfone` do mapa:\n" + "\n".join(ausentes)
    )
    assert not quebrados, (
        "a linha `luz.led_microfone` do mapa cita o `backend_pydualsense.py` "
        "em endereço que derivou — a citação resolve, mas aponta para outra "
        "coisa:\n" + "\n".join(quebrados)
    )


def test_os_enderecos_aposentados_nao_voltaram() -> None:
    """A deriva não pode voltar por cima, nem por soma cega de 59."""
    prosa = _prosa(_linha_do_led())
    voltaram = [alvo for alvo in APOSENTADOS if alvo in prosa]
    assert not voltaram, (
        "voltou à linha `luz.led_microfone` um endereço que a auditoria de "
        "02/09/2026 aposentou (ele aponta para texto sem relação com o "
        f"`common[8]`): {', '.join(voltaram)}"
    )


def test_a_devolucao_de_posse_tem_caminho_de_producao() -> None:
    """O fato NOVO que a onda criou e a linha do mapa passou a registrar.

    `set_microphone_led(None)` — a devolução do `common[8]` ao kernel — deixou
    de ser código sem chamador: há o `mic.led.set` do IPC e o
    `hefesto-dualsense4unix mic led-release` da CLI. A ressalva do mapa afirma
    isso; esta régua é o que impede a afirmação de virar prosa velha.

    Mordida: apagar a chave `led-release` do `cmd_mic.py` — reprova.
    """
    ipc = (RAIZ / "src/hefesto_dualsense4unix/daemon/ipc_handlers.py").read_text(
        encoding="utf-8"
    )
    cli = (RAIZ / "src/hefesto_dualsense4unix/cli/cmd_mic.py").read_text(
        encoding="utf-8"
    )
    assert "set_microphone_led" in ipc, (
        "o `mic.led.set` deixou de chamar `set_microphone_led` — a ressalva da "
        "linha `luz.led_microfone` do mapa ficou falsa"
    )
    assert '"led-release"' in cli, (
        "a porta de emergência `mic led-release` sumiu da CLI — a ressalva da "
        "linha `luz.led_microfone` do mapa ficou falsa"
    )
