"""O-POINT-AND-CLICK-E-ESTILO-DE-JOGO-E-NAO-MODO-01 — o estilo abre na navegação do jogo.

D-2710-O-POINT-AND-CLICK-E-ESTILO-COM-A-TABELA-DA-06 (27/10/2026, a validar pelo usuário): o
estilo Point and click grava `mode.kind = desktop` com o arranjo `point_and_click`, e a tabela é a
do «Perfil jogo - navegação» da aba 06 (sem escolha, o `molde:point_and_click`). O arranjo é do
perfil; sem o campo, vale o da sessão. D-2710-DO-NINTENDO-PRO-O-PS-R3-VAI-A-NAVEGACAO: o PS + R3
anda DualSense, Xbox e Navegação, e do Nintendo Pro (sem caminho) cai na Navegação.

O que a régua lê é o que os devices RECEBERAM, pela subclasse do `Daemon` real de
`test_o_point_and_click_aplica_o_perfil_que_a_navegacao_escolhe.py`, e o perfil relido do disco.

MORDIDAS: tire o `arranjo=arranjo` de `secao_do_modo_do_estilo` (o estilo grava sem arranjo, e o
perfil abre na Navegação da sessão); devolva o `point_and_click` à chamada do arranjo no
`_aplicar_ponte` (o PS + R3 cai no Point and click); tire o `_arranjo_do_perfil` da propriedade
`arranjo_do_desktop` (o perfil abre no arranjo da sessão).
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.profiles import estilos_de_jogo as ej
from hefesto_dualsense4unix.profiles.loader import load_profile, perfil_em_disco, save_profile
from hefesto_dualsense4unix.profiles.manager import secao_do_modo_do_estilo
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile, ProfileModeConfig
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils.session import (
    ARRANJO_NAVEGACAO,
    ARRANJO_POINT_AND_CLICK,
    load_arranjo_do_desktop,
)
from tests.unit.test_o_point_and_click_aplica_o_perfil_que_a_navegacao_escolhe import (
    PERFIL_ATIVO,
    _daemon,
    _DaemonQueAnota,
    _gravar,
)
from tests.unit.test_o_point_and_click_serve_a_visual_novel import _aplicar, disco

__all__ = ["disco"]

SEM_ESCOLHA_DA_06: dict[str, Any] = {
    **PERFIL_ATIVO, "mouse": {"enabled": True, "speed": 9, "scroll_speed": 2}}


def _triangulo(d: _DaemonQueAnota) -> tuple[str, ...] | None:
    valor = d._keyboard_device.bindings[-1].get("triangle")
    return tuple(valor) if valor is not None else None


def _com_o_modo(modo: dict[str, Any] | None) -> dict[str, Any]:
    corpo = dict(SEM_ESCOLHA_DA_06)
    if modo is not None:
        corpo["mode"] = modo
    return corpo


def _ativar(d: _DaemonQueAnota) -> None:
    perfil = load_profile("perfil-ativo")
    d.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")


def _na_navegacao_da_sessao(d: _DaemonQueAnota) -> None:
    d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo=ARRANJO_NAVEGACAO)
    assert d.quadrado() == ("KEY_SPACE",), "premissa: a Navegação aplica as linhas do perfil"
    assert load_arranjo_do_desktop() == ARRANJO_NAVEGACAO


def test_o_estilo_grava_o_desktop_com_o_arranjo_e_sem_molde(disco: dict[str, Any]) -> None:
    """Prova da D-2710-O-POINT-AND-CLICK-E-ESTILO-COM-A-TABELA-DA-06: o estilo grava o arranjo."""
    _aplicar("Point and click")

    prof = disco["perfil"]
    assert prof.estilo == "point_and_click"
    assert prof.mode is not None
    assert (prof.mode.kind, prof.mode.arranjo) == ("desktop", ARRANJO_POINT_AND_CLICK)
    assert prof.button_actions is None, "o estilo voltou a gravar um molde próprio"
    assert prof.tabela_no_jogo is None


def test_o_perfil_do_estilo_abre_no_point_and_click_com_a_sessao_na_navegacao() -> None:
    """Prova da D-2710-O-POINT-AND-CLICK-E-ESTILO-COM-A-TABELA-DA-06: o arranjo é do perfil."""
    receita = ej.POR_CHAVE["point_and_click"].receita_invisivel
    assert receita is not None
    _mudou, modo = secao_do_modo_do_estilo(None, receita.modo, receita.arranjo)
    assert modo is not None
    d = _daemon(_com_o_modo(modo.model_dump(mode="json", exclude_none=True)))
    _na_navegacao_da_sessao(d)

    _ativar(d)

    assert d.arranjo_do_desktop == ARRANJO_POINT_AND_CLICK
    assert _triangulo(d) == ("KEY_ESC",), "a tabela não é a do molde Point and click da 06"
    assert d.quadrado() != ("KEY_SPACE",), "o perfil abriu na Navegação da sessão"
    assert load_arranjo_do_desktop() == ARRANJO_NAVEGACAO, "a ativação reescreveu a sessão"


def test_a_escolha_da_06_vale_no_perfil_do_estilo() -> None:
    d = _daemon({**PERFIL_ATIVO, "mode": {"kind": "desktop", "arranjo": "point_and_click"}})
    _na_navegacao_da_sessao(d)

    _ativar(d)

    assert d.quadrado() == ("KEY_LEFTCTRL",), "a escolha da aba 06 (Visual novel) não valeu"


def test_o_perfil_velho_sem_o_campo_abre_no_arranjo_da_sessao() -> None:
    d = _daemon(_com_o_modo({"kind": "desktop"}))
    _na_navegacao_da_sessao(d)

    _ativar(d)

    assert d.arranjo_do_desktop == ARRANJO_NAVEGACAO
    assert d.quadrado() == ("KEY_SPACE",)


class _DaemonDoGesto(_DaemonQueAnota):
    """O vpad de pé com o modo pedido; derrubá-lo só anota."""

    def __init__(self, modo: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._gamepad_device = SimpleNamespace(flavor=modo)
        self.config.gamepad_emulation_enabled = True
        self.config.gamepad_caminho = "xbox" if modo == "xbox" else None
        self.derrubou: list[bool] = []

    def set_gamepad_emulation(self, enabled: bool, flavor: str | None = None, *,
                              origin: Any, caminho: str | None = None,
                              caminho_e_escolha: bool = True,
                              grava_o_modo: Any = False) -> bool:
        self.derrubou.append(enabled)
        self._gamepad_device = None
        self.config.gamepad_emulation_enabled = False
        return True


@pytest.mark.parametrize("modo", ["xbox", "nintendo"])
@pytest.mark.parametrize("perfil_com_estilo", [False, True], ids=["sem-estilo", "com-estilo"])
def test_o_ps_r3_cai_na_navegacao_e_nunca_no_point_and_click(
    modo: str, perfil_com_estilo: bool,
) -> None:
    """Prova da D-2710-DO-NINTENDO-PRO-O-PS-R3-VAI-A-NAVEGACAO, e do Xbox também."""
    corpo = _com_o_modo({"kind": "desktop", "arranjo": "point_and_click"}
                        if perfil_com_estilo else None)
    d = _DaemonDoGesto(modo, controller=FakeController(transport="usb"),
                       config=DaemonConfig(mouse_speed=6, mouse_scroll_speed=1))
    _gravar("perfil-ativo", corpo)
    d.store.set_active_profile("perfil-ativo")
    d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo=ARRANJO_POINT_AND_CLICK)
    if perfil_com_estilo:
        _ativar(d)
    d._gamepad_device = SimpleNamespace(flavor=modo)
    d.config.gamepad_emulation_enabled = True
    d.derrubou.clear()

    alvo = hotkey.proxima_ponte(hotkey.ponte_atual(d))
    assert alvo == hotkey.PONTE_MOUSE_TECLADO, f"do {modo}, o PS + R3 foi a {alvo}"
    assert hotkey._aplicar_ponte(d, alvo) is True

    assert d.derrubou == [False]
    assert d.arranjo_do_desktop == ARRANJO_NAVEGACAO
    assert d.quadrado() == ("KEY_SPACE",), "o PS + R3 aplicou a tabela do Point and click"
    gravado = perfil_em_disco(PERFIL_ATIVO["name"])
    assert gravado is not None, "o gesto não gravou o modo no perfil ativo"
    disco = gravado.mode
    assert disco is not None and disco.kind == "desktop"
    assert disco.arranjo == (ARRANJO_NAVEGACAO if perfil_com_estilo else None)


def test_o_perfil_salvo_sem_estilo_nao_ganha_a_chave_do_arranjo() -> None:
    salvo = save_profile(Profile(name="Sem Estilo", match=MatchAny(),
                                 mode=ProfileModeConfig(kind="desktop")))
    bruto = json.loads(salvo.read_text(encoding="utf-8"))

    assert bruto["mode"]["kind"] == "desktop"
    assert "arranjo" not in bruto["mode"], bruto["mode"]
