"""Backend real usando `pydualsense` para falar HID com o DualSense.

Thin adapter: traduz chamadas da `IController` para a API do pydualsense e
converte estado interno em `ControllerState` imutável. Mantém intencionalmente
sem lógica de negócio — facilita troca do backend no futuro (ADR-001).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydualsense import pydualsense

from hefesto.core.controller import (
    ControllerState,
    IController,
    Side,
    Transport,
    TriggerEffect,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PyDualSenseController(IController):
    """Implementação de `IController` baseada em `pydualsense`."""

    def __init__(self) -> None:
        self._ds: pydualsense | None = None
        self._transport: Transport = "usb"

    def connect(self) -> None:
        if self._ds is not None:
            logger.debug("pydualsense ja conectado; reutilizando")
            return
        ds = pydualsense()
        ds.init()
        self._ds = ds
        self._transport = self._detect_transport(ds)
        logger.info("controle conectado via %s", self._transport)

    def disconnect(self) -> None:
        if self._ds is None:
            return
        try:
            self._ds.close()
        finally:
            self._ds = None

    def is_connected(self) -> bool:
        return self._ds is not None and self._ds.conType is not None

    def read_state(self) -> ControllerState:
        ds = self._require()
        state = ds.state
        battery = self._read_battery_raw(ds)
        return ControllerState(
            battery_pct=battery,
            l2_raw=int(state.L2),
            r2_raw=int(state.R2),
            connected=self.is_connected(),
            transport=self._transport,
            raw_lx=int(state.LX) & 0xFF,
            raw_ly=int(state.LY) & 0xFF,
            raw_rx=int(state.RX) & 0xFF,
            raw_ry=int(state.RY) & 0xFF,
        )

    def set_trigger(self, side: Side, effect: TriggerEffect) -> None:
        ds = self._require()
        trigger = ds.triggerL if side == "left" else ds.triggerR
        trigger.mode = self._coerce_mode(effect.mode)
        for idx, value in enumerate(effect.forces):
            trigger.setForce(idx, value)

    def set_led(self, color: tuple[int, int, int]) -> None:
        ds = self._require()
        r, g, b = color
        ds.light.setColorI(r, g, b)

    def set_rumble(self, weak: int, strong: int) -> None:
        ds = self._require()
        ds.setLeftMotor(strong)
        ds.setRightMotor(weak)

    def get_battery(self) -> int:
        return self._read_battery_raw(self._require())

    def get_transport(self) -> Transport:
        return self._transport

    def _require(self) -> pydualsense:
        if self._ds is None:
            raise RuntimeError("pydualsense nao inicializado — chamar connect() antes")
        return self._ds

    @staticmethod
    def _detect_transport(ds: pydualsense) -> Transport:
        con = getattr(ds, "conType", None)
        if con is None:
            return "usb"
        name = str(getattr(con, "name", con)).lower()
        return "usb" if "usb" in name else "bt"

    @staticmethod
    def _read_battery_raw(ds: pydualsense) -> int:
        battery = getattr(ds.state, "battery", None)
        if battery is None:
            return 0
        level = getattr(battery, "Level", battery)
        try:
            value = int(level)
        except (TypeError, ValueError):
            return 0
        return max(0, min(100, value))

    @staticmethod
    def _coerce_mode(mode: int) -> object:
        from pydualsense.enums import TriggerModes
        try:
            return TriggerModes(mode)
        except ValueError:
            logger.warning("mode fora do enum TriggerModes: %s — mantendo raw", mode)
            return mode


__all__ = ["PyDualSenseController"]
