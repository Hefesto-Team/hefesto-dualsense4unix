"""O transporte do mapa bate com o que aciona (regra 21 do censo do mapa).

A `vibracao.rumble.passthrough@dualsense` dizia `transporte = só cabo`,
herança do v1, com `cabo_aciona` e `radio_aciona` em `sim`. O censo lia a
coluna `transporte` só para contar, e a regra da assimetria compara um lado
com o outro, nunca com ela. A regra 21 dá dono a essa coerência, para todo
controle do mapa.
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "check_paridade_transporte.py"
MAPA_REAL = RAIZ_REAL / "docs" / "data" / "mapa-controles.csv"
REGRA = "transporte-contra-aciona"
LINHA_DA_VIBRACAO = "vibracao.rumble.passthrough@dualsense"


def _censo() -> Any:
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("censo_do_transporte", SCRIPT)
        assert spec is not None and spec.loader is not None
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = modulo
        spec.loader.exec_module(modulo)
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return modulo


CENSO = _censo()


def _cabecalho_e_linhas() -> tuple[list[str], list[dict[str, str]]]:
    with MAPA_REAL.open(encoding="utf-8", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        return list(leitor.fieldnames or []), list(leitor)


def _escrever(caminho: Path, cabecalho: list[str], linhas: list[dict[str, str]]) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=cabecalho)
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({coluna: linha.get(coluna, "") for coluna in cabecalho})
    return caminho


def _achados_da_regra(caminho: Path, raiz: Path) -> list[Any]:
    achados, _resumo, _desligadas = CENSO.censo(caminho, raiz, date(2026, 10, 10))
    return [achado for achado in achados if achado.regra == REGRA]


def _sintetica(ident: str, transporte: str, cabo: str, radio: str) -> dict[str, str]:
    return {
        "id": ident,
        "chave": ident.split("@")[0],
        "controle": "dualsense",
        "existe": "tem",
        "transporte": transporte,
        "cabo_aciona": cabo,
        "radio_aciona": radio,
        "assimetria_declarada": "de propósito, para a régua",
    }


@pytest.mark.parametrize(
    ("transporte", "cabo", "radio", "lado"),
    [
        ("só cabo", "sim", "sim", "radio"),
        ("só cabo", "sim", "parcial", "radio"),
        ("só rádio", "parcial", "sim", "cabo"),
        ("só rádio", "sim", "não", "cabo"),
    ],
)
def test_o_transporte_de_um_lado_com_o_outro_acionando_reprova(
    tmp_path: Path, transporte: str, cabo: str, radio: str, lado: str
) -> None:
    cabecalho, _ = _cabecalho_e_linhas()
    ident = "sintetica.um@pro_controller"
    caminho = _escrever(
        tmp_path / "mapa.csv", cabecalho, [_sintetica(ident, transporte, cabo, radio)]
    )
    achados = _achados_da_regra(caminho, tmp_path)
    assert len(achados) == 1, achados
    assert achados[0].ident == ident
    assert achados[0].lado == lado
    assert achados[0].nivel == CENSO.FALHA


@pytest.mark.parametrize(
    ("transporte", "cabo", "radio"),
    [
        ("cabo+rádio", "sim", "sim"),
        ("só cabo", "sim", "não"),
        ("só cabo", "sim", ""),
        ("só rádio", "não", "sim"),
        ("ambos", "sim", "sim"),
        ("sem linha no v1", "não", "sim"),
    ],
)
def test_o_transporte_coerente_passa(
    tmp_path: Path, transporte: str, cabo: str, radio: str
) -> None:
    cabecalho, _ = _cabecalho_e_linhas()
    caminho = _escrever(
        tmp_path / "mapa.csv",
        cabecalho,
        [_sintetica("sintetica.dois@dualsense", transporte, cabo, radio)],
    )
    assert _achados_da_regra(caminho, tmp_path) == []


def test_no_mapa_real_a_regra_acha_so_a_linha_da_vibracao_e_nada_com_ela_corrigida(
    tmp_path: Path,
) -> None:
    cabecalho, linhas = _cabecalho_e_linhas()
    como_esta = [dict(linha) for linha in linhas]
    for linha in como_esta:
        if linha["id"] == LINHA_DA_VIBRACAO:
            linha["transporte"] = "só cabo"
    antes = _achados_da_regra(_escrever(tmp_path / "antes.csv", cabecalho, como_esta),
                              RAIZ_REAL)
    assert [achado.ident for achado in antes] == [LINHA_DA_VIBRACAO], antes

    corrigida = [dict(linha) for linha in linhas]
    for linha in corrigida:
        if linha["id"] == LINHA_DA_VIBRACAO:
            linha["transporte"] = "cabo+rádio"
    depois = _achados_da_regra(_escrever(tmp_path / "depois.csv", cabecalho, corrigida),
                               RAIZ_REAL)
    assert depois == [], depois
