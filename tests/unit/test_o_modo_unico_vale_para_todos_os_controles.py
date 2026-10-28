"""O-MODO-UNICO-VALE-PARA-TODOS-OS-CONTROLES-01 — DualSense, Xbox ou Nintendo Pro, para todos.

D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES (27/10/2026, a validar pelo usuário): o modo é o
par (caminho, máscara) do ``mode`` do perfil, e vale para todo controle. A bancada é a do
`test_a_mascara_do_cartao_vale_com_o_vpad_de_pe.py`: os métodos REAIS do `Daemon`, um
`CoopManager` REAL com o P2 e o P3, e o jogo aberto.

MORDIDAS:

- devolva à `external_mask.mascara_efetiva` o degrau por identidade (o controle que tinha
  máscara própria a mantém): o P2 fica no modo velho e
  `test_o_mask_set_leva_o_modo_a_todo_controle` reprova;
- arranque o `model_validator(mode="before")` `Profile._a_mascara_de_cada_controle_vira_o_modo`:
  o perfil misturado carrega no `gamepad_flavor` velho (ou reprova pela chave), e
  `test_o_perfil_misturado_vira_o_modo_que_o_jogo_via` reprova.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import ipc_handlers as ih
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import Profile
from tests.unit.test_a_mascara_do_cartao_vale_com_o_vpad_de_pe import (
    P1,
    P2,
    P3,
    PERFIL,
    _bancada,
    _Handlers,
    _mesa_com_o_jogo_aberto,
    _vpad_do,
)

__all__ = ["_bancada"]


def _todos(d: Any) -> list[Any]:
    return [d._gamepad_device, _vpad_do(P2), _vpad_do(P3)]


def _perfil(controles: dict[str, Any], modo: dict[str, Any] | None = None) -> Profile:
    bruto: dict[str, Any] = {
        "name": "Antigo",
        "match": {"type": "any"},
        "controllers": controles,
    }
    if modo is not None:
        bruto["mode"] = modo
    return Profile.model_validate(bruto)


def test_o_mask_set_leva_o_modo_a_todo_controle() -> None:
    d = _mesa_com_o_jogo_aberto()

    resposta = asyncio.run(
        ih.IpcHandlersMixin._handle_gamepad_mask_set(_Handlers(d), {"flavor": "xbox"})
    )

    assert resposta["status"] == "ok", resposta
    for uniq in (P1, P2, P3):
        assert em.mascara_efetiva(uniq, d.config.gamepad_flavor) == "xbox", uniq
    assert [v.flavor for v in _todos(d)] == ["xbox"] * 3


@pytest.mark.asyncio
async def test_o_ps_l3_anda_o_modo_de_todos() -> None:
    d = _mesa_com_o_jogo_aberto()
    gesto = hotkey.build_next_mask_callback(d)  # type: ignore[arg-type]

    for esperado in ("xbox", "nintendo", "dualsense"):
        await gesto()
        assert [v.flavor for v in _todos(d)] == [esperado] * 3, esperado
        modo = loader.load_profile(PERFIL).mode
        assert modo is not None and modo.gamepad_flavor == esperado


def test_o_perfil_misturado_vira_o_modo_que_o_jogo_via() -> None:
    """P1 DualSense, P2 Xbox e o caminho Xbox: o jogo via o Xbox 360 nos dois."""
    perfil = _perfil(
        {P1: {"mascara": "dualsense"}, P2: {"mascara": "xbox"}},
        {"kind": "gamepad", "gamepad_flavor": "dualsense", "caminho": "xbox"},
    )

    assert perfil.mode is not None
    assert (perfil.mode.caminho, perfil.mode.gamepad_flavor) == ("xbox", "xbox")
    de_novo = Profile.model_validate(perfil.model_dump(mode="json"))
    assert de_novo.model_dump(mode="json") == perfil.model_dump(mode="json"), "não é idempotente"


def test_a_mascara_dos_cartoes_vence_o_flavor_escrito() -> None:
    """O degrau por controle vencia o `gamepad_flavor`: vence também na migração."""
    perfil = _perfil(
        {P1: {"mascara": "dualsense"}, P2: {"mascara": "dualsense"}},
        {"kind": "gamepad", "gamepad_flavor": "xbox"},
    )

    assert perfil.mode is not None
    assert (perfil.mode.caminho, perfil.mode.gamepad_flavor) == ("dualsense", "dualsense")
    assert all("mascara" not in c for c in perfil.model_dump(mode="json")["controllers"].values())


def test_a_chave_velha_num_cartao_carrega_sem_erro() -> None:
    perfil = _perfil({P1: {"mascara": "nintendo"}})

    assert perfil.mode is not None
    assert (perfil.mode.kind, perfil.mode.caminho, perfil.mode.gamepad_flavor) == (
        "gamepad", None, "nintendo",
    )


def test_o_nintendo_pro_sobe_por_uinput_sem_caminho() -> None:
    d = _mesa_com_o_jogo_aberto()

    assert d.escolher_o_modo_unico("nintendo", porta="controle") in gp.DESFECHOS_EMULACAO_ATIVA

    assert vp.par_do_modo("nintendo") == (None, "nintendo")
    assert [(v.flavor, v.backend) for v in _todos(d)] == [("nintendo", "uinput")] * 3
    assert d.config.gamepad_caminho is None
    modo = loader.load_profile(PERFIL).mode
    assert modo is not None and (modo.caminho, modo.gamepad_flavor) == (None, "nintendo")
