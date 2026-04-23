"""Registry de subsystems do daemon.

Ordem de start: poll → ipc → udp → autoswitch → mouse → rumble → metrics.
Cada subsystem implementa o protocolo definido em base.py.

MetricsSubsystem é condicional: só sobe se metrics_enabled=True na config.
"""
from __future__ import annotations

from hefesto.daemon.subsystems.autoswitch import AutoswitchSubsystem
from hefesto.daemon.subsystems.base import Subsystem
from hefesto.daemon.subsystems.ipc import IpcSubsystem
from hefesto.daemon.subsystems.metrics import MetricsSubsystem
from hefesto.daemon.subsystems.mouse import MouseSubsystem
from hefesto.daemon.subsystems.plugins import PluginsSubsystem
from hefesto.daemon.subsystems.poll import PollSubsystem
from hefesto.daemon.subsystems.rumble import RumbleSubsystem
from hefesto.daemon.subsystems.udp import UdpSubsystem

# Registry canônico — ordem de inserção = ordem de start/stop.
# stop ocorre na ordem inversa (implementado em lifecycle.py).
# MetricsSubsystem é o último a subir e o primeiro a parar (ordem inversa).
# PluginsSubsystem sobe antes de Metrics (acesso a controller).
SUBSYSTEM_REGISTRY: list[type[Subsystem]] = [
    PollSubsystem,
    IpcSubsystem,
    UdpSubsystem,
    AutoswitchSubsystem,
    MouseSubsystem,
    RumbleSubsystem,
    PluginsSubsystem,
    MetricsSubsystem,
]

__all__ = [
    "SUBSYSTEM_REGISTRY",
    "AutoswitchSubsystem",
    "IpcSubsystem",
    "MetricsSubsystem",
    "MouseSubsystem",
    "PluginsSubsystem",
    "PollSubsystem",
    "RumbleSubsystem",
    "Subsystem",
    "UdpSubsystem",
]
