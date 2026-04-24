"""Testes do UinputKeyboardDevice (FEAT-KEYBOARD-EMULATOR-01)."""
from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS
from hefesto.integrations.uinput_keyboard import (
    DEVICE_NAME,
    SUPPORTED_KEYS,
    UinputKeyboardDevice,
)


def _fake_uinput_module() -> MagicMock:
    """Fabrica módulo uinput fake cobrindo todas as `SUPPORTED_KEYS`."""
    mod = MagicMock()
    # Cada KEY_* ganha código fictício único e estável por nome.
    for name in SUPPORTED_KEYS:
        setattr(mod, name, (1, hash(name) & 0xFFFF))
    return mod


def _started_device(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[UinputKeyboardDevice, MagicMock, MagicMock]:
    fake_mod = _fake_uinput_module()
    fake_device = MagicMock()
    fake_mod.Device.return_value = fake_device
    monkeypatch.setitem(sys.modules, "uinput", fake_mod)
    dev = UinputKeyboardDevice()
    assert dev.start() is True
    return dev, fake_mod, fake_device


def _emits_for(fake_device: MagicMock, code: Any) -> list:
    return [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == code
    ]


# --- start / stop ------------------------------------------------------------

def test_device_name_identifica_hefesto() -> None:
    assert "Hefesto" in DEVICE_NAME
    assert "Keyboard" in DEVICE_NAME


def test_start_e_stop_idempotentes(monkeypatch: pytest.MonkeyPatch) -> None:
    dev, _, fake_device = _started_device(monkeypatch)
    assert dev.is_active() is True
    # Segundo start é no-op.
    assert dev.start() is True
    # Stop libera e segundo stop não explode.
    dev.stop()
    assert dev.is_active() is False
    dev.stop()
    fake_device.destroy.assert_called_once()


def test_start_sem_modulo_uinput_retorna_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Módulo uinput ausente → device não sobe, sem exceção."""
    # Remove da lista de módulos e invalida import — simula "não instalado".
    monkeypatch.setitem(sys.modules, "uinput", None)
    dev = UinputKeyboardDevice()
    # `import uinput` vai retornar None/ImportError: a camada usa try/except.
    # Como `sys.modules["uinput"] = None` provoca ImportError, o path é coberto.
    result = dev.start()
    assert result is False
    assert dev.is_active() is False


# --- dispatch edge-triggered -------------------------------------------------

def test_dispatch_options_emite_leftmeta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Options pressionado → KEY_LEFTMETA value=1 (press)."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(frozenset({"options"}))

    emits = _emits_for(fake_device, fake_mod.KEY_LEFTMETA)
    assert len(emits) == 1
    assert emits[0][1][1] == 1  # press
    assert fake_device.syn.called


def test_dispatch_options_release_emite_value_0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(frozenset({"options"}))
    fake_device.reset_mock()
    dev.dispatch(frozenset())  # solta

    emits = _emits_for(fake_device, fake_mod.KEY_LEFTMETA)
    assert len(emits) == 1
    assert emits[0][1][1] == 0  # release


def test_dispatch_r1_emite_combo_alt_tab(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R1 → Alt+Tab: KEY_LEFTALT press + KEY_TAB press, ambos value=1."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(frozenset({"r1"}))

    alt_emits = _emits_for(fake_device, fake_mod.KEY_LEFTALT)
    tab_emits = _emits_for(fake_device, fake_mod.KEY_TAB)
    assert len(alt_emits) == 1 and alt_emits[0][1][1] == 1
    assert len(tab_emits) == 1 and tab_emits[0][1][1] == 1


def test_dispatch_r1_release_inverte_ordem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release do combo solta na ordem reversa: KEY_TAB depois KEY_LEFTALT."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(frozenset({"r1"}))
    fake_device.reset_mock()
    dev.dispatch(frozenset())

    # A ordem de chamada na mock guarda sequência global de método.
    emit_calls = [c for c in fake_device.method_calls if c[0] == "emit"]
    # Espera: primeiro KEY_TAB,0 depois KEY_LEFTALT,0.
    assert emit_calls[0][1] == (fake_mod.KEY_TAB, 0)
    assert emit_calls[0][2].get("syn") is False
    assert emit_calls[1][1] == (fake_mod.KEY_LEFTALT, 0)


def test_dispatch_l1_emite_alt_shift_tab(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(frozenset({"l1"}))

    assert len(_emits_for(fake_device, fake_mod.KEY_LEFTALT)) == 1
    assert len(_emits_for(fake_device, fake_mod.KEY_LEFTSHIFT)) == 1
    assert len(_emits_for(fake_device, fake_mod.KEY_TAB)) == 1


def test_dispatch_create_emite_sysrq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(frozenset({"create"}))

    emits = _emits_for(fake_device, fake_mod.KEY_SYSRQ)
    assert len(emits) == 1 and emits[0][1][1] == 1


def test_dispatch_botao_nao_mapeado_e_ignorado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cross/triangle/r3 etc. NÃO podem produzir emit no teclado (são do mouse)."""
    dev, _fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(frozenset({"cross", "triangle", "r3", "dpad_up"}))

    # Nenhum emit deve ter acontecido.
    assert not any(c[0] == "emit" for c in fake_device.method_calls)


def test_dispatch_hold_nao_repete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Botão segurado em ticks consecutivos emite apenas 1x (edge-trigger)."""
    dev, _fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(frozenset({"options"}))
    fake_device.reset_mock()
    dev.dispatch(frozenset({"options"}))
    dev.dispatch(frozenset({"options"}))

    # Segundo/terceiro tick não devem gerar novo emit.
    assert not any(c[0] == "emit" for c in fake_device.method_calls)


def test_dispatch_multiplos_botoes_edge_independentes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Options+Create juntos → 2 sequências distintas; soltar um mantém o outro."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(frozenset({"options", "create"}))
    fake_device.reset_mock()

    # Solta só options
    dev.dispatch(frozenset({"create"}))

    leftmeta = _emits_for(fake_device, fake_mod.KEY_LEFTMETA)
    sysrq = _emits_for(fake_device, fake_mod.KEY_SYSRQ)
    assert len(leftmeta) == 1 and leftmeta[0][1][1] == 0  # release options
    assert not sysrq  # create continua pressionado — nada novo emitido


# --- set_bindings dinâmico ---------------------------------------------------

def test_set_bindings_troca_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Troca runtime de bindings permite sub-sprint de persistência."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.set_bindings({"options": ("KEY_ESC",)})
    dev.dispatch(frozenset({"options"}))

    assert _emits_for(fake_device, fake_mod.KEY_ESC)
    assert not _emits_for(fake_device, fake_mod.KEY_LEFTMETA)


def test_set_bindings_libera_teclas_pressionadas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Se troca acontece com botão pressionado, solta as teclas antes de trocar."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(frozenset({"options"}))  # KEY_LEFTMETA pressionado
    fake_device.reset_mock()

    dev.set_bindings({"options": ("KEY_ESC",)})

    # KEY_LEFTMETA foi liberada antes da troca
    releases = _emits_for(fake_device, fake_mod.KEY_LEFTMETA)
    assert any(e[1][1] == 0 for e in releases)


# --- dispatch sem start ------------------------------------------------------

def test_dispatch_sem_start_e_noop() -> None:
    """Device não inicializado ignora dispatch em silêncio."""
    dev = UinputKeyboardDevice()
    # Não levanta, não loga exceção.
    dev.dispatch(frozenset({"options"}))
    assert dev.is_active() is False


# --- defaults propagam ao construtor ----------------------------------------

def test_construtor_usa_default_bindings() -> None:
    dev = UinputKeyboardDevice()
    assert dev.bindings == dict(DEFAULT_BUTTON_BINDINGS)


# --- cobertura de SUPPORTED_KEYS ---------------------------------------------

def test_supported_keys_cobre_todas_as_defaults() -> None:
    """Todas as teclas KEY_* usadas pelos defaults devem estar em SUPPORTED_KEYS.

    Tokens virtuais `__*__` (FEAT-KEYBOARD-UI-01, ex: __OPEN_OSK__) são
    delegados ao `virtual_token_callback` e não precisam estar em
    SUPPORTED_KEYS — filtramos antes de comparar.
    """
    from hefesto.core.keyboard_mappings import is_virtual_token

    default_keys = {
        k
        for seq in DEFAULT_BUTTON_BINDINGS.values()
        for k in seq
        if not is_virtual_token(k)
    }
    faltantes = default_keys - set(SUPPORTED_KEYS)
    assert not faltantes, f"faltam em SUPPORTED_KEYS: {faltantes}"

# "O todo é maior que a soma das partes." — Aristóteles
