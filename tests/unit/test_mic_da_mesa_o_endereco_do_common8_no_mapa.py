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

Mordida: repor na célula um endereço que derivou (o
`core/backend_pydualsense.py:1820-1821` de antes da 6e-4) — esta régua reprova.
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

#: As âncoras que a linha promete no `backend_pydualsense.py`.
#:
#: DESDE 25/09/2026 A RÉGUA NÃO DIGITA ENDEREÇO. Até ali ela guardava onze
#: pares (faixa, âncora) e uma lista de aposentados, e cada leva que fazia o
#: backend crescer pagava a remedição à mão: sete vezes entre 12/09 e 25/09,
#: a última com a O-BRILHO-DAS-LUZES-DE-NUMERO-01 e a
#: A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01 (a costura da 6e-4). A causa era a
#: prosa: a linha citava o backend na forma curta (`:5339`), que o
#: `scripts/reapontar-citacoes.py` e o validador não alcançam no CSV (a forma
#: curta colide com hora de relógio). A prosa passou a citar
#: `core/backend_pydualsense.py:N`, que o reapontador leva sozinho a cada leva,
#: e a régua passou a LER as citações dela: toda faixa citada contém uma
#: âncora, e toda âncora é citada. O `:1563-1564` que a linha tinha na forma
#: inteira caía numa docstring desde antes da 6e-4: foi para a queda do flag1.
ANCORAS: tuple[str, ...] = (
    "VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE",
    "common[8] = int(mic_led) & 0xFF",
    "def set_microphone_led",
    "def set_mic_led",
    "report[11] no rádio",
    "CORRIGIDO em 15/08/2026",
    "build_bt_report",
    "self.device.write",
    "should_reclaim_on_wake",
    "def _escrever_led_do_mic",
    "_audio_status",
)

#: A citação do backend na prosa, na forma que o reapontador leva.
CITACAO = re.compile(r"backend_pydualsense\.py:(\d+)(?:-(\d+))?(?![\d-])")


def _linha_do_led() -> dict[str, str]:
    csv.field_size_limit(10**9)
    with MAPA.open(newline="", encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha["chave"] == "luz.led_microfone" and linha["controle"] == "dualsense":
                return linha
    pytest.fail("a linha `luz.led_microfone@dualsense` sumiu do mapa")


def _prosa(linha: dict[str, str]) -> str:
    return "\n".join(linha.get(campo) or "" for campo in CAMPOS)


def test_cada_endereco_citado_contem_uma_ancora() -> None:
    """Ir ao arquivo, ler a faixa, e exigir uma âncora lá dentro.

    Mordida: repor na célula um endereço de antes da 6e-4
    (`core/backend_pydualsense.py:1820-1821`) — a faixa cai fora da âncora e
    esta régua reprova.
    """
    corpo = BACKEND.read_text(encoding="utf-8").splitlines()
    citadas = [
        (m.group(0), int(m.group(1)), int(m.group(2) or m.group(1)))
        for m in CITACAO.finditer(_prosa(_linha_do_led()))
    ]
    assert len(citadas) >= len(ANCORAS), (
        "a linha `luz.led_microfone` do mapa quase não cita o backend na forma "
        f"inteira ({len(citadas)} citações): a régua ficaria verde sobre nada"
    )
    quebrados = []
    for texto, primeira, ultima in citadas:
        if primeira > ultima or ultima > len(corpo):
            quebrados.append(f"{texto}: faixa impossível ({len(corpo)} linhas)")
            continue
        trecho = "\n".join(corpo[primeira - 1 : ultima])
        if not any(ancora in trecho for ancora in ANCORAS):
            quebrados.append(
                f"{texto}: nenhuma âncora dentro — começa em "
                f"{corpo[primeira - 1].strip()[:60]!r}"
            )
    assert not quebrados, (
        "a linha `luz.led_microfone` do mapa cita o `backend_pydualsense.py` "
        "em endereço que derivou; rode `scripts/reapontar-citacoes.py "
        "--escrever`:\n" + "\n".join(quebrados)
    )


def test_toda_ancora_e_citada() -> None:
    """A linha cita cada âncora na forma inteira.

    Mordida: apagar da célula a citação do `set_mic_led` — esta régua reprova.
    """
    corpo = BACKEND.read_text(encoding="utf-8").splitlines()
    cobertas: set[str] = set()
    for m in CITACAO.finditer(_prosa(_linha_do_led())):
        primeira, ultima = int(m.group(1)), int(m.group(2) or m.group(1))
        trecho = "\n".join(corpo[primeira - 1 : ultima])
        cobertas.update(a for a in ANCORAS if a in trecho)
    faltam = [a for a in ANCORAS if a not in cobertas]
    assert not faltam, (
        "a linha `luz.led_microfone` do mapa deixou de citar: " + ", ".join(faltam)
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
