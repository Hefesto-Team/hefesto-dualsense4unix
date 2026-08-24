"""T5, CONFIGURAÇÕES-FECHA-01 — as constantes de Hz não se desgarram do CSV.

`HZ_INPUT_SEM_MIC`, `HZ_INPUT_COM_MIC` e `HZ_AUDIO_COM_MIC`
(`integrations/radio_da_mesa.py`) são a medição do A/B de 2026-07-25 copiada à
mão para dentro do Python. A mesma medição está no
`docs/data/mapa-controles.csv`, na célula `radio_ressalva` da linha
`audio.microfone` — e até esta sprint nada comparava as duas cópias: remedir
o A/B e esquecer o CSV (ou vice-versa) deixava a aba Configurações e o mapa de
canais discordando sobre o mesmo fato, e nenhum portão notava.

Este arquivo é a fatia mínima da Z6/PAREAMENTO-01 que esta aba carrega
sozinha — não a ponte geral entre medição, CSV e tela.

A MORDIDA já foi provada em 23/08 pelo AUDITORIA-DE-PERDA-01: trocar
`HZ_INPUT_SEM_MIC` de 260,4 para 300,0 deixando a `radio_ressalva` para trás
passava limpo (36 testes verdes e portão OK). Este arquivo é o portão que
falta.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    CHAVE_NO_MAPA_DE_CANAIS,
    HZ_AUDIO_COM_MIC,
    HZ_INPUT_COM_MIC,
    HZ_INPUT_SEM_MIC,
)

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs/data/mapa-controles.csv"

#: `"260,4"` → `260.4` — a forma como o `radio_ressalva` escreve os números,
#: em português (vírgula decimal).
_NUMERO_PT_BR = re.compile(r"(\d+,\d)")


def _radio_ressalva(chave: str) -> str:
    with MAPA.open(newline="", encoding="utf-8") as fh:
        linhas = [linha for linha in csv.DictReader(fh) if linha["chave"] == chave]
    assert linhas, f"nenhuma linha com chave={chave!r} em {MAPA}"
    return linhas[0]["radio_ressalva"]


def test_a_regua_acha_a_linha_e_a_celula() -> None:
    """Régua provada acertando antes de confiar na comparação abaixo."""
    ressalva = _radio_ressalva(CHAVE_NO_MAPA_DE_CANAIS)
    assert "Hz de input" in ressalva
    assert "Hz de áudio" in ressalva


def test_as_tres_constantes_de_hz_batem_com_o_csv() -> None:
    """Os três números do Python são os três primeiros números `X,Y Hz` do CSV.

    A célula descreve, nesta ordem: mic desligado (input), mic ligado
    (input), mic ligado (áudio) — a mesma ordem das três constantes.
    """
    ressalva = _radio_ressalva(CHAVE_NO_MAPA_DE_CANAIS)
    achados = _NUMERO_PT_BR.findall(ressalva)
    assert len(achados) >= 3, (
        f"menos de três números 'X,Y' na radio_ressalva de "
        f"{CHAVE_NO_MAPA_DE_CANAIS!r}: {ressalva!r}"
    )
    sem_mic, com_mic_input, com_mic_audio = (
        float(v.replace(",", ".")) for v in achados[:3]
    )

    assert sem_mic == HZ_INPUT_SEM_MIC, (
        f"HZ_INPUT_SEM_MIC={HZ_INPUT_SEM_MIC} não bate com o CSV ({sem_mic}) "
        f"— remedir um dos dois lados sem o outro é o defeito que este "
        f"portão existe para pegar"
    )
    assert com_mic_input == HZ_INPUT_COM_MIC, (
        f"HZ_INPUT_COM_MIC={HZ_INPUT_COM_MIC} não bate com o CSV "
        f"({com_mic_input})"
    )
    assert com_mic_audio == HZ_AUDIO_COM_MIC, (
        f"HZ_AUDIO_COM_MIC={HZ_AUDIO_COM_MIC} não bate com o CSV "
        f"({com_mic_audio})"
    )
