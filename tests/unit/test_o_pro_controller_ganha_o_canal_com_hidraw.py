"""A máscara Pro Controller segue no uinput, e o doctor diz isso numa linha.

Sprint O-PRO-CONTROLLER-GANHA-O-CANAL-COM-HIDRAW-01. O passo 0 (16/10/2026) leu o
`is_hidraw_enabled` do winebus do Proton: o hidraw por padrão é só do DualSense,
do DualShock 4 e de volantes e manches da lista; o 057e:2009 só o ganharia pela
`PROTON_ENABLE_HIDRAW`. Ativou o decidido por delegação de 13/10: a Pro segue no
uinput de hoje, e o doctor diz o que ela entrega.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.integrations import virtual_pad as vp


@pytest.mark.parametrize("caminho", [None, "dualsense", "xbox"])
def test_a_pro_nao_pede_o_uhid_em_modo_nenhum(caminho: str | None) -> None:
    assert not vp.quer_uhid(caminho, "nintendo")


def test_o_jogo_ve_a_pro_so_fora_do_modo_xbox() -> None:
    assert vp.o_jogo_ve_a_pro("dualsense", ["dualsense", "nintendo"])
    assert vp.o_jogo_ve_a_pro(None, ["nintendo"])
    assert not vp.o_jogo_ve_a_pro("xbox", ["nintendo"])  # no modo Xbox o jogo vê o Xbox 360
    assert not vp.o_jogo_ve_a_pro("dualsense", ["dualsense", "xbox"])
    assert not vp.o_jogo_ve_a_pro("dualsense", "nintendo")


def _estado(flavor: str, caminho: str, por_aparelho: dict[str, str]) -> dict[str, Any]:
    return {
        "gamepad_emulation": {
            "enabled": True, "flavor": flavor, "caminho": caminho, "por_aparelho": por_aparelho,
        }
    }


def test_a_linha_sai_quando_um_controle_mostra_a_pro() -> None:
    """MORDIDA: tire a chamada do `_daemon_checks`, e o doctor cala a Pro."""
    estado = _estado("dualsense", "dualsense", {"aa:bb:cc:00:00:01": "nintendo"})
    assert cmd_doctor._linha_da_mascara_pro(estado) == ("[INFO]", vp.LINHA_DA_PRO_NO_UINPUT)
    assert "uinput" in vp.LINHA_DA_PRO_NO_UINPUT
    assert "giroscópio" in vp.LINHA_DA_PRO_NO_UINPUT


@pytest.mark.parametrize(
    "estado",
    [
        _estado("nintendo", "xbox", {}),
        _estado("dualsense", "dualsense", {"aa:bb:cc:00:00:01": "dualsense"}),
        # a da sessão é Pro, mas o controle conectado veste o DualSense
        _estado("nintendo", "dualsense", {"aa:bb:cc:00:00:01": "dualsense"}),
        {"gamepad_emulation": {"enabled": False, "flavor": "nintendo"}},
        None,
    ],
)
def test_a_linha_nao_sai_sem_a_pro_no_jogo(estado: object) -> None:
    assert cmd_doctor._linha_da_mascara_pro(estado) is None


def test_sem_controle_conectado_vale_a_mascara_da_sessao() -> None:
    assert cmd_doctor._linha_da_mascara_pro(_estado("nintendo", "dualsense", {})) is not None


class _Cliente:
    def __init__(self, estado: dict[str, Any]) -> None:
        self._estado = estado

    async def __aenter__(self) -> _Cliente:
        return self

    async def __aexit__(self, *_a: object) -> None:
        return None

    async def call(self, metodo: str, *_a: object) -> Any:
        return {
            "daemon.status": {},
            "profile.list": {"profiles": []},
            "daemon.state_full": self._estado,
            "controller.list": {"controllers": []},
        }[metodo]


def test_o_doctor_mostra_a_linha_da_pro(monkeypatch: pytest.MonkeyPatch) -> None:
    estado = _estado("nintendo", "dualsense", {"aa:bb:cc:00:00:01": "nintendo"})
    monkeypatch.setattr(cmd_doctor.IpcClient, "connect", lambda *_a, **_k: _Cliente(estado))
    linhas = asyncio.run(cmd_doctor._daemon_checks())
    assert ("[INFO]", vp.LINHA_DA_PRO_NO_UINPUT) in linhas
    assert cmd_doctor._gravidade_das_linhas(linhas) == 0
