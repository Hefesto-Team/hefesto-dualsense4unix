"""Registry de subsystems do daemon.

Ordem de start: poll → ipc → udp → autoswitch → mouse → rumble → bt_mic →
plugins → metrics. Cada subsystem implementa o protocolo definido em base.py.

MetricsSubsystem é condicional: só sobe se metrics_enabled=True na config.
BtMicSubsystem é condicional e OPT-IN: só sobe com
`HEFESTO_DUALSENSE4UNIX_BT_MIC=1` (ou `DaemonConfig.bt_mic_enabled`).

AVISO AO PRÓXIMO QUE MEXER AQUI (BT-MIC-REGISTRY-01, 25/07): esta lista é
**declarativa**. Quem de fato sobe os subsystems é `Daemon.run()`
(`daemon/lifecycle.py`), com uma chamada `_safe_start(...)` por subsystem —
`SUBSYSTEM_REGISTRY` não é iterado por ninguém em produção. Foi assim que o
`BtMicSubsystem` nasceu órfão: existia a classe, existia o gate documentado
por env var, e não existia a linha no `run()`. **Acrescentar um subsystem
aqui NÃO o liga**: a lista e o `run()` têm de andar juntos, e o teste
`tests/unit/test_bt_mic_subsystem_registrado.py` trava exatamente isso.
"""
from __future__ import annotations

from hefesto_dualsense4unix.daemon.subsystems.autoswitch import AutoswitchSubsystem
from hefesto_dualsense4unix.daemon.subsystems.base import Subsystem
from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem
from hefesto_dualsense4unix.daemon.subsystems.gamepad import GamepadSubsystem
from hefesto_dualsense4unix.daemon.subsystems.ipc import IpcSubsystem
from hefesto_dualsense4unix.daemon.subsystems.metrics import MetricsSubsystem
from hefesto_dualsense4unix.daemon.subsystems.mouse import MouseSubsystem
from hefesto_dualsense4unix.daemon.subsystems.plugins import PluginsSubsystem
from hefesto_dualsense4unix.daemon.subsystems.poll import PollSubsystem
from hefesto_dualsense4unix.daemon.subsystems.rumble import RumbleSubsystem
from hefesto_dualsense4unix.daemon.subsystems.udp import UdpSubsystem

# Registry canônico — ordem de inserção = ordem de start/stop.
# stop ocorre na ordem inversa (implementado em lifecycle.py).
# MetricsSubsystem é o último a subir e o primeiro a parar (ordem inversa).
# PluginsSubsystem sobe antes de Metrics (acesso a controller).
# BtMicSubsystem entra ANTES do Plugins: ele não depende de nada do daemon
# (descobre os controles pelo sysfs por conta própria) e, na ordem inversa,
# parar antes do IPC/poll garante que as pontes de áudio — e portanto o
# microfone de cada controle — sejam DESLIGADAS cedo no shutdown.
SUBSYSTEM_REGISTRY: list[type[Subsystem]] = [
    PollSubsystem,
    IpcSubsystem,
    UdpSubsystem,
    AutoswitchSubsystem,
    MouseSubsystem,
    GamepadSubsystem,
    RumbleSubsystem,
    BtMicSubsystem,
    PluginsSubsystem,
    MetricsSubsystem,
]

__all__ = [
    "SUBSYSTEM_REGISTRY",
    "AutoswitchSubsystem",
    "BtMicSubsystem",
    "GamepadSubsystem",
    "IpcSubsystem",
    "MetricsSubsystem",
    "MouseSubsystem",
    "PluginsSubsystem",
    "PollSubsystem",
    "RumbleSubsystem",
    "Subsystem",
    "UdpSubsystem",
]
