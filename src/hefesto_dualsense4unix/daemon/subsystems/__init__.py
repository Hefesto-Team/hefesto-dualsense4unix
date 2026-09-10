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

`AltoFalanteSubsystem` ENTROU NA LISTA EM 10/09/2026 — SOM-FIADO-01
-------------------------------------------------------------------
Ele ficou de fora desde que nasceu, e a razão era boa: publicava um
`module-null-sink` por controle e **nenhum `module-loopback`**, isto é, um sink
mudo por DualSense na lista de som dela. É o defeito que `app/audio_saida.py`
nomeia na invariante 4 do `PlanoDoNo`: *"um `module-null-sink` sozinho seria
exatamente o sink que aceita o áudio e o joga fora"*.

**Os dois buracos de rota fecharam, e a guarda que sobra é estrutural:**

* o CABO ganhou rota em 09/09 (SOM-POR-CONTROLE-01) — `sink_do_controle`
  resolve a placa DAQUELE controle e o nó sobe o `module-loopback` ao lado;
* o RÁDIO ganhou rota em 10/09 — o som saiu de verdade pelo report `0x35`, e
  `AltoFalanteSubsystem._casar_as_pontes` constrói uma `PonteDeSomPorRadio`
  por controle, com o hidraw e o monitor daquele controle;
* e `GerenciadorDeNosDeSom.reconciliar` guarda o par: **sem rota, sem nó.**
  Quem não entrega não é publicado, então o sumidouro não nasce nem por
  acidente — e a régua que mede isso no PRODUTO, subindo um `Daemon` de
  verdade, é `tests/unit/test_o_no_de_som_nao_nasce_sumidouro.py`.

A receita completa das TRÊS pontas foi cumprida: a lista aqui,
`_safe_start("alto_falante", …)` no `run()` de `lifecycle.py` e o
`_stop_alto_falante` no `shutdown()` de `connection.py`.

POR QUE `HotkeySubsystem` NÃO ESTÁ NA LISTA — e não é esquecimento:

* `HotkeySubsystem` (`hotkey.py:2103`) é uma **lápide, não um órfão**: os dois
  métodos são `noop` declarados, e a hotkey já está viva no `run()` desde
  sempre, por FUNÇÃO — `lifecycle.py:914` (`start_hotkey_manager`) e `:916`
  (`start_mic_hotkey`). Registrá-lo não acende nada; só acrescenta duas linhas
  de log e a impressão falsa de que o registry é quem manda.
"""
from __future__ import annotations

from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
    AltoFalanteSubsystem,
)
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
    AltoFalanteSubsystem,
    PluginsSubsystem,
    MetricsSubsystem,
]

__all__ = [
    "SUBSYSTEM_REGISTRY",
    "AltoFalanteSubsystem",
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
