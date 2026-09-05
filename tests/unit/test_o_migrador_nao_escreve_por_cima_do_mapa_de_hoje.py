"""O migrador do mapa não escreve por cima do trabalho que ele não produziu.

`scripts/migrar-mapa-v2.py` rodou UMA vez, em 11/08/2026. Depois disso o
`docs/data/mapa-controles.csv` cresceu de 204 para 308 linhas, preenchidas por
cerca de trezentos agentes lendo repositórios externos e por validação ao vivo
na bancada dela.

Medido em 05/09/2026: rodá-lo de novo lia o retrato congelado
(`mapa-controles-v1.csv`, 204 linhas) e escrevia **264 linhas por cima das
308** — sem backup, porque o guardado já existe, e imprimindo
`prova: nenhum campo do v1 se perdeu`, que compara o v2 recém-montado com o v1
que o gerou e nunca olha o destino.

A palavra dela, no dia: *"Não podemos perder ou regenerar errado isso e
desconsiderar o excelente trabalho deles."*

Esta régua LÊ o cabeçalho do arquivo — não digita o que ele deve ser.
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
V1_CONGELADO = RAIZ / "docs" / "data" / "mapa-controles-v1.csv"


def _modulo():
    caminho = RAIZ / "scripts" / "migrar-mapa-v2.py"
    spec = importlib.util.spec_from_file_location("migrar_mapa_v2", caminho)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["migrar_mapa_v2"] = mod
    spec.loader.exec_module(mod)
    return mod


def _cabecalho(caminho: Path) -> list[str]:
    with open(caminho, encoding="utf-8", newline="") as fh:
        return next(csv.reader(fh), [])


def test_o_mapa_de_hoje_esta_no_formato_v2():
    assert _cabecalho(MAPA)[:1] == ["chave"], (
        "o mapa deixou de ser v2 — esta régua e a trava do migrador dependem disso"
    )


def test_o_mapa_de_hoje_tem_mais_linhas_que_o_retrato_congelado():
    if not V1_CONGELADO.exists():
        pytest.skip("o v1 congelado não está nesta árvore")
    with open(MAPA, encoding="utf-8") as fh:
        de_hoje = sum(1 for _ in fh) - 1
    with open(V1_CONGELADO, encoding="utf-8") as fh:
        congelado = sum(1 for _ in fh) - 1
    assert de_hoje > congelado, (
        f"o mapa tem {de_hoje} linhas e o retrato de 11/08 tem {congelado}: "
        "se esta conta se inverter, alguém já regenerou por cima"
    )


def test_o_migrador_reconhece_o_destino_ja_migrado():
    assert _modulo().destino_ja_e_v2() is True


def test_o_migrador_recusa_escrever_quando_o_destino_ja_e_v2(capsys):
    mod = _modulo()
    assert mod.main([]) == 1, "o migrador aceitou escrever por cima do mapa de hoje"
    assert "RECUSADO" in capsys.readouterr().err


def test_a_recusa_nao_encostou_no_arquivo(tmp_path):
    antes = MAPA.read_bytes()
    _modulo().main([])
    assert MAPA.read_bytes() == antes, "o migrador tocou no mapa apesar de recusar"


def test_a_mordida_com_o_destino_no_formato_velho_ele_aceitaria(tmp_path, monkeypatch):
    """A trava tem de MORDER: com um destino em formato v1, ela solta.

    Sem esta metade, `destino_ja_e_v2` podendo devolver `True` sempre passaria
    nos testes acima e travaria a migração legítima de qualquer árvore nova.
    """
    mod = _modulo()
    falso = tmp_path / "mapa-controles.csv"
    falso.write_text("id,controle,familia\n", encoding="utf-8")
    monkeypatch.setattr(mod, "V2", falso)
    assert mod.destino_ja_e_v2() is False


def test_a_mordida_destino_ausente_tambem_solta(tmp_path, monkeypatch):
    mod = _modulo()
    monkeypatch.setattr(mod, "V2", tmp_path / "nao-existe.csv")
    assert mod.destino_ja_e_v2() is False
