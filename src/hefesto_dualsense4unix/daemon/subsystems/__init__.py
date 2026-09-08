"""Registry de subsystems do daemon.

Ordem de start: poll → ipc → udp → autoswitch → mouse → rumble → bt_mic →
plugins → metrics. Cada subsystem implementa o protocolo definido em base.py.

MetricsSubsystem é condicional: só sobe se metrics_enabled=True na config.
BtMicSubsystem é condicional e OPT-IN: só sobe quando ela ligou o microfone de
ALGUM controle (`DaemonConfig.bt_mic_uniqs`, a fonte que lê o `maquina.json`) ou
com `HEFESTO_DUALSENSE4UNIX_BT_MIC=1`, que é o caminho à mão e vale por todos.

AVISO AO PRÓXIMO QUE MEXER AQUI (BT-MIC-REGISTRY-01, 25/07): esta lista é
**declarativa**. Quem de fato sobe os subsystems é `Daemon.run()`
(`daemon/lifecycle.py`), com uma chamada `_safe_start(...)` por subsystem —
`SUBSYSTEM_REGISTRY` não é iterado por ninguém em produção. Foi assim que o
`BtMicSubsystem` nasceu órfão: existia a classe, existia o gate documentado
por env var, e não existia a linha no `run()`. **Acrescentar um subsystem
aqui NÃO o liga**: a lista e o `run()` têm de andar juntos, e o teste
`tests/unit/test_bt_mic_subsystem_registrado.py` trava exatamente isso.

SÃO **TRÊS** LUGARES, E ESTE AVISO DIZIA DOIS (medido em 07/09/2026). O
desligamento não passa pela lista tampouco: `daemon/connection.py:1368,1386`
chama `_stop_bt_mic` e `_stop_metrics` **pelo nome**. Quem seguir a receita de
duas metades sobe o subsystem e nunca o para — e, no caso do som, o nó fica na
lista de saída dela depois de o daemon morrer. A receita completa é: a lista
aqui, o `_safe_start` no `run()` e o `_stop_*` no `shutdown()`.

POR QUE `AltoFalanteSubsystem` E `HotkeySubsystem` NÃO ESTÃO NA LISTA, e os
dois motivos são diferentes — **nenhum dos dois é esquecimento**:

* `AltoFalanteSubsystem` (`alto_falante.py`) publica um `module-null-sink` por
  controle e **nenhum `module-loopback`**: o monitor do nó não vai a lugar
  nenhum. Ligá-lo hoje põe um sink mudo por DualSense na lista de som dela —
  quatro, medidos na mesa em 07/09/2026, dois deles no rádio, onde não há rota
  nenhuma. É o defeito que `app/audio_saida.py` nomeia na invariante 4 do
  `PlanoDoNo`: *"um `module-null-sink` sozinho seria exatamente o sink que
  aceita o áudio e o joga fora"*. A régua que trava o par —
  *se subir, tem de ter rota* — é
  `tests/unit/test_o_no_de_som_nao_nasce_sumidouro.py`. Ela **permite** a cura
  correta (dar rota ao gerenciador) e reprova só a fiação crua;
* `HotkeySubsystem` (`hotkey.py:1988`) é uma **lápide, não um órfão**: os dois
  métodos são `noop` declarados, e a hotkey já está viva no `run()` desde
  sempre, por FUNÇÃO — `lifecycle.py:914` (`start_hotkey_manager`) e `:916`
  (`start_mic_hotkey`). Registrá-lo não acende nada; só acrescenta duas linhas
  de log e a impressão falsa de que o registry é quem manda.
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
