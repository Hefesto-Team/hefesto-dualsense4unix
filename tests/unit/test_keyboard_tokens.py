"""Testes de tokens virtuais `__OPEN_OSK__`/`__CLOSE_OSK__` no UinputKeyboardDevice.

Cobre FEAT-KEYBOARD-UI-01 (59.3) — tokens não devem emitir via uinput; são
delegados ao `virtual_token_callback` do subsystem. Teste monkeypatch do
`_uinput_mod` para não depender de /dev/uinput real.
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.core.keyboard_mappings import (
    DEFAULT_BUTTON_BINDINGS,
    TOKEN_CLOSE_OSK,
    TOKEN_OPEN_OSK,
    is_virtual_token,
)
from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice


class _FakeUinput:
    """Stand-in para o módulo `uinput`. Apenas expõe KEY_* como sentinelas."""

    class _KeyEv:
        def __init__(self, name: str) -> None:
            self.name = name

    def __getattr__(self, name: str) -> Any:
        if name.startswith("KEY_") or name.startswith("BTN_"):
            return _FakeUinput._KeyEv(name)
        raise AttributeError(name)


class _FakeDevice:
    def __init__(self) -> None:
        self.emitted: list[tuple[str, int]] = []
        self.synced: int = 0

    def emit(self, ev: Any, value: int, syn: bool = True) -> None:
        self.emitted.append((ev.name, value))

    def syn(self) -> None:
        self.synced += 1

    def destroy(self) -> None:
        pass


def _make_device_preset(
    bindings: dict[str, Any] | None = None,
) -> tuple[UinputKeyboardDevice, _FakeDevice, list[tuple[str, str]]]:
    calls: list[tuple[str, str]] = []

    def cb(token: str, phase: str) -> None:
        calls.append((token, phase))

    dev = UinputKeyboardDevice(
        bindings=bindings or dict(DEFAULT_BUTTON_BINDINGS),
        virtual_token_callback=cb,
    )
    fake_device = _FakeDevice()
    dev._device = fake_device
    dev._uinput_mod = _FakeUinput()
    return dev, fake_device, calls


def test_is_virtual_token_detecta_corretamente() -> None:
    assert is_virtual_token("__OPEN_OSK__")
    assert is_virtual_token("__CLOSE_OSK__")
    assert not is_virtual_token("KEY_C")
    assert not is_virtual_token("__")
    assert not is_virtual_token("")


def test_token_virtual_delega_ao_callback_e_nao_emite() -> None:
    dev, fake_device, calls = _make_device_preset()
    # L3 default = __OPEN_OSK__; press então release
    dev.dispatch(frozenset({"l3"}))
    dev.dispatch(frozenset())
    assert calls == [(TOKEN_OPEN_OSK, "press"), (TOKEN_OPEN_OSK, "release")]
    # Nada emitido via uinput.
    assert fake_device.emitted == []


def test_token_virtual_r3_fecha_osk() -> None:
    dev, fake_device, calls = _make_device_preset()
    dev.dispatch(frozenset({"r3"}))
    assert calls == [(TOKEN_CLOSE_OSK, "press")]
    assert fake_device.emitted == []


def test_sem_callback_nao_emite_nem_quebra() -> None:
    """Quando `virtual_token_callback=None`, token é ignorado silenciosamente."""
    dev = UinputKeyboardDevice(bindings={"l3": (TOKEN_OPEN_OSK,)})
    fake = _FakeDevice()
    dev._device = fake
    dev._uinput_mod = _FakeUinput()

    # 2 ciclos press/release sem callback registrado — nenhuma emissão.
    dev.dispatch(frozenset({"l3"}))
    dev.dispatch(frozenset())
    dev.dispatch(frozenset({"l3"}))
    dev.dispatch(frozenset())

    assert fake.emitted == []
    # Flag sinaliza que o warning foi observado internamente; o sistema
    # não duplica warning em loops futuros mesmo com milhares de eventos.
    assert dev._virtual_token_warned is True


def test_key_real_continua_emitindo() -> None:
    """Bindings 'KEY_*' não são afetados — continuam emitindo via uinput."""
    dev, fake_device, calls = _make_device_preset(bindings={"r1": ("KEY_LEFTALT", "KEY_TAB")})
    dev.dispatch(frozenset({"r1"}))
    dev.dispatch(frozenset())
    assert calls == []  # callback não chamado — binding é real
    # press: LEFTALT, TAB ; release ordem reversa: TAB, LEFTALT
    emitted_names = [ev_name for ev_name, _v in fake_device.emitted]
    assert emitted_names == ["KEY_LEFTALT", "KEY_TAB", "KEY_TAB", "KEY_LEFTALT"]


def test_binding_misto_e_rejeitado() -> None:
    """`__OPEN_OSK__ + KEY_TAB` é rejeitado — nem callback nem emit."""
    dev, fake_device, calls = _make_device_preset(
        bindings={"l3": (TOKEN_OPEN_OSK, "KEY_TAB")}
    )
    dev.dispatch(frozenset({"l3"}))
    assert calls == []
    assert fake_device.emitted == []
