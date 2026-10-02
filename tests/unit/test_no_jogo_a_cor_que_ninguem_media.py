"""NO-JOGO-SEM-FALSO-VERDE-01/T7 — a cor das seis linhas, com GTK de verdade."""

from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("a cor das linhas da aba No jogo")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
pytest.importorskip("gi.repository.Gtk", reason="precisa da typelib Gtk")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.widgets.controller_card import (
    SITUACAO_CHEGANDO,
    SITUACAO_NUNCA,
    SITUACAO_PARADO,
)
from hefesto_dualsense4unix.app.widgets.painel_no_jogo import (
    COR_DA_SITUACAO,
    PALAVRA_DA_SITUACAO,
    PainelNoJogo,
)

_janelas_vivas: list[Any] = []

_ENTRY: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "player": 1,
    "player_slot": 1,
}

_VELHO = 30.0


def _estado(visto: dict[str, Any], **vpad_extra: Any) -> dict[str, Any]:
    """Um `state_full` mínimo com o vpad do jogador 1 e os carimbos pedidos."""
    vpad: dict[str, Any] = {"player": 1, "visto_ha_s": dict(visto)}
    vpad.update(vpad_extra)
    return {
        "connected": True,
        "native_mode": False,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
        "controllers": [dict(_ENTRY)],
        "rumble_ff": {"per_vpad": [vpad]},
    }


def _painel_pintado(state: dict[str, Any]) -> PainelNoJogo:
    """Um painel REAL, dentro de uma janela, já repintado com ``state``."""
    painel = PainelNoJogo()
    janela = Gtk.OffscreenWindow()
    janela.add(painel)
    janela.show_all()
    _janelas_vivas.append(janela)
    painel.atualizar(_ENTRY, state)
    return painel


def _valor(painel: PainelNoJogo, recurso: str) -> Any:
    """O rótulo da coluna da DIREITA de um recurso — o que ganha cor."""
    _rotulo, valor = painel._linhas[recurso]
    return valor


def test_a_linha_que_esta_chegando_sai_verde() -> None:
    """"no jogo agora" é a única frase desta tela que afirma coisa boa."""
    painel = _painel_pintado(_estado({"touchpad_click": 0.5}))

    valor = _valor(painel, "touchpad")

    assert valor.get_use_markup() is True
    assert COR_DA_SITUACAO[SITUACAO_CHEGANDO] in valor.get_label()
    assert valor.get_text() == PALAVRA_DA_SITUACAO[SITUACAO_CHEGANDO]


def test_a_linha_que_parou_sai_amarela() -> None:
    """E "parou" pede atenção: era para estar chegando e não está."""
    painel = _painel_pintado(_estado({"touchpad_click": _VELHO}))

    valor = _valor(painel, "touchpad")

    assert valor.get_use_markup() is True
    assert COR_DA_SITUACAO[SITUACAO_PARADO] in valor.get_label()
    assert valor.get_text() == PALAVRA_DA_SITUACAO[SITUACAO_PARADO]


def test_as_duas_cores_nao_sao_a_mesma() -> None:
    """A régua sabe distinguir as duas — senão um `COR_DA_SITUACAO` de uma cor"""
    verde = _valor(
        _painel_pintado(_estado({"touchpad_click": 0.5})), "touchpad"
    ).get_label()
    amarela = _valor(
        _painel_pintado(_estado({"touchpad_click": _VELHO})), "touchpad"
    ).get_label()

    assert verde != amarela


def test_a_linha_sem_pedido_fica_apagada_e_sem_cor() -> None:
    """"sem pedido ainda" é explicação, não defeito: apagada, e sem markup."""
    painel = _painel_pintado(_estado({"touchpad_click": 0.5}))

    valor = _valor(painel, "lightbar")

    assert valor.get_style_context().has_class("dim-label")
    assert valor.get_use_markup() is False
    assert valor.get_text() == PALAVRA_DA_SITUACAO[SITUACAO_NUNCA]


def test_a_linha_que_acorda_perde_o_apagado() -> None:
    """O painel REUSA os mesmos seis rótulos a cada tique — e a classe gruda."""
    painel = _painel_pintado(_estado({}))
    valor = _valor(painel, "touchpad")
    assert valor.get_style_context().has_class("dim-label")

    painel.atualizar(_ENTRY, _estado({"touchpad_click": 0.5}))

    assert valor.get_style_context().has_class("dim-label") is False
    assert COR_DA_SITUACAO[SITUACAO_CHEGANDO] in valor.get_label()


def test_a_linha_que_adormece_volta_a_ficar_apagada() -> None:
    """E o caminho de volta, que é a contraprova do de cima."""
    painel = _painel_pintado(_estado({"touchpad_click": 0.5}))
    valor = _valor(painel, "touchpad")
    assert valor.get_style_context().has_class("dim-label") is False

    painel.atualizar(_ENTRY, _estado({}))

    assert valor.get_style_context().has_class("dim-label")
    assert valor.get_use_markup() is False


def test_o_numero_dos_motores_sobrevive_a_pintura() -> None:
    """A frase mais longa desta coluna, colorida, tem de chegar inteira à tela."""
    state = _estado(
        {"rumble": 0.5},
        rumble_no_fisico=[255, 255],
        rumble_no_fisico_ha_s=0.2,
        ff_ultimos_reports=[
            {"ha_s": 0.2, "weak": 255, "strong": 255, "ramo": "v1"}
        ],
    )

    valor = _valor(_painel_pintado(state), "vibracao")

    assert valor.get_text() == (
        f"{PALAVRA_DA_SITUACAO[SITUACAO_CHEGANDO]} (motores: 255/255)"
    )
    assert COR_DA_SITUACAO[SITUACAO_CHEGANDO] in valor.get_label()
