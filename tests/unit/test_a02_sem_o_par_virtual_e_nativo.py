"""A 02 sem o par «Virtual | Nativo»: o pacote perde o gesto e tudo o que era dele.

A decisão de 02/10/2026 (um microfone por controle, sempre, sem a escolha Nativo ou
Virtual; `OS-NOS-DE-SOM-SEM-O-ENDERECO-NO-NOME-01`). O mockup já não tem o par
(`mockup/DIVERGENCIAS.md`, 02-controles); o `--publicar 02` leva a página, e o pacote
sai antes, para a página publicada nunca ter um botão que o pacote não atende.

MORDIDA: devolver o `@gesto("02-controles.html", "mic-modo")`, uma prova dele, o campo
`mic-modo-aceso` ou a entrada de `camada.py` e uma destas réguas reprova.
"""
from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

import pacotes
from pacotes import a02_controles as a02
from pacotes import camada

PAGINA = "02-controles.html"


def test_o_gesto_mic_modo_nao_tem_dono() -> None:
    assert pacotes.gesto_da_pagina(PAGINA, "mic-modo") is None
    assert not hasattr(a02, "mic_modo")


def test_nenhuma_prova_clica_o_par() -> None:
    assert [p for p in a02.PROVAS if p["gesto"] == "mic-modo"] == []
    assert all("micModo" not in p["clique"] for p in a02.PROVAS)


def test_a_camada_nao_guarda_o_gesto_morto() -> None:
    assert (PAGINA, "mic-modo") not in camada.CAMADA


def test_o_pacote_nao_guarda_o_que_era_do_par() -> None:
    for nome in ("modo_do_mic", "nativo_fora_de_alcance", "RAZAO_DO_NATIVO_FORA",
                 "A_PAGINA_APAGA_O_NATIVO", "_MIC_NATIVO", "_ler_o_nativo",
                 "_controles_declarados", "SEM_ECO"):
        assert not hasattr(a02, nome), f"{nome} voltou ao pacote da 02"
    assert "machine_declare" not in a02.PONTE


def test_o_cartao_nao_emite_os_campos_do_par() -> None:
    campos = a02.pacote(pacotes.Contexto(
        state={}, mesa=[],
        conectados=[{"uniq": "aa:bb:cc:00:00:01", "transport": "usb", "player_slot": 1}],
        estados={}))["cards"]["aa:bb:cc:00:00:01"]
    assert "mic-modo-aceso" not in campos
    assert "mic-nativo-fora" not in campos
