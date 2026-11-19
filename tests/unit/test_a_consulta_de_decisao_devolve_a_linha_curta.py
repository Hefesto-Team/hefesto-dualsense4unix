"""A consulta de decisão devolve a linha curta (id, estado, título, escolha, revoga), sem a
deliberação."""
from __future__ import annotations

import csv
import importlib.util
import pathlib
import types

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INSTRUMENTO = RAIZ / "scripts" / "decisao.py"

COLUNAS = ["id", "titulo", "a_pergunta", "caminhos", "recomendacao", "preco_do_outro_lado",
           "estado", "escolha", "revoga"]


def _carregar() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("_decisao", INSTRUMENTO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _csv(pasta: pathlib.Path) -> pathlib.Path:
    arq = pasta / "decisoes.csv"
    with arq.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerow({"id": "D-A-BANDEJA-FECHA", "titulo": "A bandeja fecha pelo núcleo",
                    "a_pergunta": "Como fecha?",
                    "caminhos": "A, o sinal padrão | B, o prazo LONGO-DEMAIS", "recomendacao": "A",
                    "preco_do_outro_lado": "com B a bandeja PRECO-ESCONDIDO", "estado": "decidida",
                    "escolha": "A: o sinal padrão", "revoga": "D-A-BANDEJA-VELHA"})
        w.writerow({"id": "D-O-SOM-DO-RADIO", "titulo": "O som pelo rádio",
                    "a_pergunta": "Qual report?",
                    "caminhos": "0x35 | 0x31", "recomendacao": "0x35", "preco_do_outro_lado": "",
                    "estado": "caduca", "escolha": "0x35", "revoga": ""})
    return arq


def test_a_consulta_devolve_a_linha_curta_sem_a_deliberacao(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _carregar()
    assert mod.main(["bandeja", "--csv", str(_csv(tmp_path))]) == 0
    saida = capsys.readouterr().out
    assert "D-A-BANDEJA-FECHA [decidida] A bandeja fecha pelo núcleo" in saida
    assert "escolha: A: o sinal padrão" in saida and "revoga: D-A-BANDEJA-VELHA" in saida
    assert "LONGO-DEMAIS" not in saida and "PRECO-ESCONDIDO" not in saida
    assert "D-O-SOM-DO-RADIO" not in saida


def test_o_termo_casa_sem_acento_nem_caixa_e_todos_os_termos_valem(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _carregar()
    arq = _csv(tmp_path)
    assert mod.main(["RADIO", "--csv", str(arq)]) == 0
    saida = capsys.readouterr().out
    assert "D-O-SOM-DO-RADIO [caduca]" in saida and "revoga:" not in saida
    assert mod.main(["radio", "bandeja", "--csv", str(arq)]) == 1
    assert "0 decisão(ões)" in capsys.readouterr().out


def test_a_escolha_longa_sai_cortada_e_o_inteira_a_mostra_toda(tmp_path: pathlib.Path) -> None:
    mod = _carregar()
    d = {"id": "D-X", "estado": "decidida", "titulo": "t", "escolha": "palavra " * 200,
         "revoga": ""}
    curta = mod.linha_curta(d)
    assert curta.endswith("… (--inteira)") and len(curta) < 450
    assert mod.linha_curta(d, inteira=True).count("palavra") == 200
