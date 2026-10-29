"""A migração do modo único conta uma vez por perfil, e de novo só quando o resultado muda.

A-MIGRACAO-DO-MODO-UNICO-NAO-LOGA-A-CADA-CARGA-01: em 28/10 foram 1363 linhas de
`mascara_por_controle_virou_o_modo` em três minutos, uma por carga do mesmo perfil.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.profiles import schema
from hefesto_dualsense4unix.profiles.schema import Profile

P1 = "aabbcc000001"
P2 = "aabbcc000002"


@pytest.fixture(autouse=True)
def _memoria_limpa() -> Iterator[None]:
    guardada = dict(schema._MIGRACOES_JA_CONTADAS)
    schema._MIGRACOES_JA_CONTADAS.clear()
    yield
    schema._MIGRACOES_JA_CONTADAS.clear()
    schema._MIGRACOES_JA_CONTADAS.update(guardada)


def _carregar(nome: str, controles: dict[str, Any]) -> Profile:
    return Profile.model_validate(
        {"name": nome, "match": {"type": "any"}, "controllers": controles}
    )


def _linhas(captured: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in captured if e.get("event") == "mascara_por_controle_virou_o_modo"]


def test_cem_cargas_do_mesmo_perfil_contam_uma_vez() -> None:
    controles = {P1: {"mascara": "xbox"}, P2: {"mascara": "xbox"}}
    with structlog.testing.capture_logs() as captured:
        for _ in range(100):
            perfil = _carregar("Planet Lust", controles)
    assert len(_linhas(captured)) == 1
    assert perfil.mode.gamepad_flavor == "xbox"


def test_o_resultado_que_muda_conta_de_novo() -> None:
    with structlog.testing.capture_logs() as captured:
        _carregar("Planet Lust", {P1: {"mascara": "xbox"}})
        _carregar("Planet Lust", {P1: {"mascara": "xbox"}})
        _carregar("Planet Lust", {P1: {"mascara": "nintendo"}})
    assert [e["modo"] for e in _linhas(captured)] == ["xbox", "nintendo"]


def test_cada_perfil_conta_a_sua() -> None:
    with structlog.testing.capture_logs() as captured:
        for nome in ("Um", "Dois", "Um", "Dois"):
            _carregar(nome, {P1: {"mascara": "dualsense"}})
    assert sorted(e["perfil"] for e in _linhas(captured)) == ["Dois", "Um"]
