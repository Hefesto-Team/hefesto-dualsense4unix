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
#: Cada par foi conferido contra o fonte em 02/09/2026. As duas últimas linhas
#: são as que NÃO derivaram — estão acima do ponto de inserção da onda — e estão
#: aqui de propósito: a cura fácil seria somar 59 a tudo, e somar nelas
#: QUEBRARIA duas referências que estavam certas.
ANCORAS: tuple[tuple[str, str], ...] = (
    (":1445-1446", "VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE"),
    (":1488-1494", "common[8] = int(mic_led) & 0xFF"),
    (":1280-1307", "def set_microphone_led"),
    (":4520", "def set_mic_led"),
    (":4527-4528", "report[11] no rádio"),
    (":4529-4533", "CORRIGIDO em 15/08/2026"),
    (":1553-1554", "build_bt_report"),
    (":1615-1622", "self.device.write"),
    (":2936-2949", "should_reclaim_on_wake"),
    (":361-374", "def _escrever_led_do_mic"),
    (":829", "_audio_status"),
)

#: Os endereços que a auditoria aposentou. Se um deles voltar à célula, ou a
#: deriva voltou, ou alguém somou 59 no lugar errado.
APOSENTADOS = (
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
