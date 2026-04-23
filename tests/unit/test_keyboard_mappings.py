"""Testes de `hefesto.core.keyboard_mappings` (FEAT-KEYBOARD-EMULATOR-01)."""
from __future__ import annotations

import pytest

from hefesto.core.keyboard_mappings import (
    DEFAULT_BUTTON_BINDINGS,
    format_binding,
    parse_binding,
)


def test_default_bindings_cobertura_sprint_1() -> None:
    """Sub-sprint 1 entrega os 4 bindings conservadores.

    L3/R3 ficam fora (entram com UI+onboard em sub-sprint 3).
    Touchpad-press fica fora (evdev_reader ainda não expõe).
    L2/R2 inversão fica fora (depende de persistência).
    """
    assert set(DEFAULT_BUTTON_BINDINGS.keys()) == {
        "options", "create", "l1", "r1",
    }


def test_default_bindings_valores_canonicos() -> None:
    assert DEFAULT_BUTTON_BINDINGS["options"] == ("KEY_LEFTMETA",)
    assert DEFAULT_BUTTON_BINDINGS["create"] == ("KEY_SYSRQ",)
    assert DEFAULT_BUTTON_BINDINGS["r1"] == ("KEY_LEFTALT", "KEY_TAB")
    assert DEFAULT_BUTTON_BINDINGS["l1"] == (
        "KEY_LEFTALT", "KEY_LEFTSHIFT", "KEY_TAB",
    )


def test_default_bindings_nao_colide_com_mouse() -> None:
    """Botões usados pelo mouse (BUTTON_TO_UINPUT + DPAD_TO_KEY + EDGE_KEY_MAP)
    não podem ter binding no teclado — evitaria dupla emissão."""
    from hefesto.integrations.uinput_mouse import (
        BUTTON_TO_UINPUT,
        DPAD_TO_KEY,
        EDGE_KEY_MAP,
    )

    mouse_buttons = (
        set(BUTTON_TO_UINPUT.keys())
        | set(DPAD_TO_KEY.keys())
        | set(EDGE_KEY_MAP.keys())
    )
    colisoes = set(DEFAULT_BUTTON_BINDINGS.keys()) & mouse_buttons
    assert not colisoes, (
        f"botões {colisoes} mapeiam ao mesmo tempo para mouse e teclado"
    )


def test_parse_binding_tecla_unica() -> None:
    assert parse_binding("KEY_ENTER") == ("KEY_ENTER",)


def test_parse_binding_combo() -> None:
    assert parse_binding("KEY_LEFTALT+KEY_TAB") == ("KEY_LEFTALT", "KEY_TAB")
    assert parse_binding("KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_T") == (
        "KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_T",
    )


def test_parse_binding_strip_e_upper() -> None:
    assert parse_binding(" key_leftalt + key_tab ") == ("KEY_LEFTALT", "KEY_TAB")


def test_parse_binding_vazio() -> None:
    assert parse_binding("") == ()
    assert parse_binding("   ") == ()


def test_parse_binding_rejeita_formato_invalido() -> None:
    with pytest.raises(ValueError, match="fora do padrão"):
        parse_binding("ENTER")
    with pytest.raises(ValueError, match="fora do padrão"):
        parse_binding("Ctrl+C")


def test_format_binding_inverso_de_parse() -> None:
    for spec in ("KEY_ENTER", "KEY_LEFTALT+KEY_TAB",
                 "KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_T"):
        assert format_binding(parse_binding(spec)) == spec

# "Conhece-te a ti mesmo." — Sócrates
