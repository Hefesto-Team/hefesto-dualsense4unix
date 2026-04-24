"""Testes de `hefesto.core.keyboard_mappings` (FEAT-KEYBOARD-EMULATOR-01)."""
from __future__ import annotations

import pytest

from hefesto.core.keyboard_mappings import (
    DEFAULT_BUTTON_BINDINGS,
    format_binding,
    parse_binding,
)


def test_default_bindings_cobertura_sprint_3() -> None:
    """Sub-sprint 3 (FEAT-KEYBOARD-UI-01) expande os defaults.

    - 4 originais (sub-sprint 1): options/create/l1/r1.
    - L3/R3 mapeiam para tokens virtuais __OPEN_OSK__/__CLOSE_OSK__.
    - 3 regiões de touchpad viram KEY_BACKSPACE/ENTER/DELETE
      (INFRA-EVDEV-TOUCHPAD-01 destravou o caminho).
    """
    assert set(DEFAULT_BUTTON_BINDINGS.keys()) == {
        "options", "create", "l1", "r1",
        "l3", "r3",
        "touchpad_left_press", "touchpad_middle_press", "touchpad_right_press",
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
    não podem ter binding no teclado — evitaria dupla emissão.

    Exceção deliberada (FEAT-KEYBOARD-UI-01): `r3` está em BUTTON_TO_UINPUT
    (BTN_MIDDLE do mouse) E em DEFAULT_BUTTON_BINDINGS (token __CLOSE_OSK__).
    A colisão é segura porque o mouse só despacha r3 quando
    `mouse_emulation_enabled=True`, e nesse modo o usuário pode via UI
    desativar o binding de teclado para r3. Quem habilitar ambos sem UI
    sobreescrita terá BTN_MIDDLE + fechar OSK — comportamento documentado.
    """
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
    colisoes_inesperadas = (
        set(DEFAULT_BUTTON_BINDINGS.keys()) & mouse_buttons
    ) - {"r3"}  # r3 documentada como exceção aceita
    assert not colisoes_inesperadas, (
        f"botões {colisoes_inesperadas} colidem inesperadamente com mouse"
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
