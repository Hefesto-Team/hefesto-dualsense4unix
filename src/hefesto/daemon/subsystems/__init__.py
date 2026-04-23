"""Registry de subsystems do daemon.

Ordem de start: poll → ipc → udp → autoswitch → mouse → rumble.
Cada subsystem implementa o protocolo definido em base.py.
"""
from __future__ import annotations

from hefesto.daemon.subsystems.autoswitch import AutoswitchSubsystem
from hefesto.daemon.subsystems.base import Subsystem
from hefesto.daemon.subsystems.ipc import IpcSubsystem
from hefesto.daemon.subsystems.mouse import MouseSubsystem
from hefesto.daemon.subsystems.poll import PollSubsystem
from hefesto.daemon.subsystems.rumble import RumbleSubsystem
from hefesto.daemon.subsystems.udp import UdpSubsystem

# Registry canônico — ordem de inserção = ordem de start/stop.
# stop ocorre na ordem inversa (implementado em lifecycle.py).
SUBSYSTEM_REGISTRY: list[type[Subsystem]] = [
    PollSubsystem,
    IpcSubsystem,
    UdpSubsystem,
    AutoswitchSubsystem,
    MouseSubsystem,
    RumbleSubsystem,
]

__all__ = [
    "SUBSYSTEM_REGISTRY",
    "AutoswitchSubsystem",
    "IpcSubsystem",
    "MouseSubsystem",
    "PollSubsystem",
    "RumbleSubsystem",
    "Subsystem",
    "UdpSubsystem",
]
