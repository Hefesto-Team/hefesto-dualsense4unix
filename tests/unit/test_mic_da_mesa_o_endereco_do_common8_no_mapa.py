"""A linha `luz.led_microfone` do mapa aponta para o CÓDIGO, não para o vazio."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
BACKEND = RAIZ / "src" / "hefesto_dualsense4unix" / "core" / "backend_pydualsense.py"

CAMPOS = (
    "cabo_evidencia",
    "radio_evidencia",
    "cabo_ressalva",
    "radio_ressalva",
    "cabo_codigo_ref",
    "radio_codigo_ref",
)

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
    """Ir ao arquivo, ler a faixa, e exigir uma âncora lá dentro."""
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
    """A linha cita cada âncora na forma inteira."""
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
    """O fato NOVO que a onda criou e a linha do mapa passou a registrar."""
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
