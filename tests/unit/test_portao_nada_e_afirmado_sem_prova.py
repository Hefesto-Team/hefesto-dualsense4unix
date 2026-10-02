#!/usr/bin/env python3
"""NADA-MOCKADO-01 — o portão que responde à pergunta dela, e não envelhece."""
from __future__ import annotations

import csv
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs/data/mapa-controles.csv"

TETO_SEM_PROVA_NEM_RESSALVA = 35

TETO_SEM_PROVA = 105

_SIM = {"sim", "1", "true"}


def _linhas() -> list[dict[str, str]]:
    with MAPA.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _fortes_sem_prova() -> list[tuple[str, str, str]]:
    """`(chave, transporte, de_onde_sei)` de toda afirmação forte sem prova."""
    fora = []
    for linha in _linhas():
        for lado in ("cabo", "radio"):
            if linha.get(f"{lado}_aciona", "").strip().lower() not in _SIM:
                continue
            if linha.get("provado_por", "").strip():
                continue
            fora.append((linha.get("chave", ""), lado,
                         linha.get(f"{lado}_de_onde_sei", "").strip()))
    return fora


def _sem_prova_nem_ressalva() -> list[tuple[str, str, str]]:
    fora = []
    for linha in _linhas():
        for lado in ("cabo", "radio"):
            if linha.get(f"{lado}_aciona", "").strip().lower() not in _SIM:
                continue
            if linha.get("provado_por", "").strip():
                continue
            if linha.get(f"{lado}_ressalva", "").strip():
                continue
            fora.append((linha.get("chave", ""), lado,
                         linha.get(f"{lado}_de_onde_sei", "").strip()))
    return fora


def test_a_divida_das_afirmacoes_sem_prova_nem_ressalva_nao_cresce() -> None:
    """O piso da pergunta dela: nada de novo é afirmado sem sustentação."""
    achados = _sem_prova_nem_ressalva()

    assert len(achados) <= TETO_SEM_PROVA_NEM_RESSALVA, (
        f"{len(achados)} linhas do mapa dizem que o aparelho ACIONA sem "
        f"`provado_por` e sem ressalva declarada — o teto é "
        f"{TETO_SEM_PROVA_NEM_RESSALVA}. As novas:\n  " +
        "\n  ".join(f"{c} [{lado}] de_onde_sei={fonte or '(vazio)'}"
                    for c, lado, fonte in achados[TETO_SEM_PROVA_NEM_RESSALVA:]))


def test_o_teto_acompanha_a_realidade_e_nunca_sobra() -> None:
    """Um teto folgado é um portão desligado — e é a cicatriz de 03/09."""
    achados = len(_sem_prova_nem_ressalva())

    assert achados == TETO_SEM_PROVA_NEM_RESSALVA, (
        f"a dívida é {achados} e o teto diz {TETO_SEM_PROVA_NEM_RESSALVA} — "
        + ("baixe a constante no mesmo commit que baixou a dívida"
           if achados < TETO_SEM_PROVA_NEM_RESSALVA
           else "alguém afirmou sem sustentar"))


def test_a_divida_maior_das_afirmacoes_sem_prova_nao_cresce() -> None:
    """As 105 que afirmam forte e ninguém provou — com ou sem ressalva."""
    achados = _fortes_sem_prova()

    assert len(achados) == TETO_SEM_PROVA, (
        f"as afirmações fortes sem `provado_por` são {len(achados)} e o teto "
        f"diz {TETO_SEM_PROVA}")


def test_medido_e_provado_nao_podem_discordar() -> None:
    """`de_onde_sei = medido` sem `provado_por` é o mapa discordando de si."""
    teto = 20
    mudas = [(c, lado) for c, lado, fonte in _fortes_sem_prova()
             if fonte == "medido"]

    assert len(mudas) <= teto, (
        f"{len(mudas)} linhas dizem `de_onde_sei=medido` e não dizem quem "
        f"provou — o teto é {teto}:\n  " +
        "\n  ".join(f"{c} [{lado}]" for c, lado in mudas[teto:]))
