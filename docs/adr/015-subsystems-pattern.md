# ADR-015 — Padrão de subsystems do daemon

**Status:** Aceito
**Data:** 2026-04-22
**Sprint:** REFACTOR-LIFECYCLE-01

---

## Contexto

`lifecycle.py` concentrava mais de 670 linhas com responsabilidades heterogêneas: poll loop, IPC start/stop, UDP start/stop, autoswitch, mouse emulation, battery debouncer, signal handlers e shutdown. Isso tornava difícil:

- Adicionar um subsystem novo (ex.: FEAT-METRICS-01) sem modificar o arquivo central.
- Testar um subsystem em isolamento, sem o overhead do orquestrador completo.
- Escrever um plugin externo (FEAT-PLUGIN-01) que dependa de um subsystem específico.

## Decisão

Quebrar `lifecycle.py` em um pacote `src/hefesto/daemon/subsystems/` com os seguintes módulos:

```
daemon/
  lifecycle.py          (orquestrador slim, ≤ 400L com backcompat total)
  context.py            (DaemonContext dataclass)
  state_store.py        (permanece inalterado)
  subsystems/
    __init__.py         (SUBSYSTEM_REGISTRY + reexportações)
    base.py             (Protocol Subsystem: start/stop/is_enabled)
    poll.py             (BatteryDebouncer + evdev_buttons_once + PollSubsystem)
    ipc.py              (IpcSubsystem + start_ipc / stop_ipc)
    udp.py              (UdpSubsystem + start_udp / stop_udp)
    autoswitch.py       (AutoswitchSubsystem + start_autoswitch / stop_autoswitch)
    mouse.py            (MouseSubsystem + start/stop/dispatch_mouse)
    rumble.py           (RumbleSubsystem + reassert_rumble + _effective_mult_inline)
    hotkey.py           (HotkeySubsystem + start/stop_hotkey_manager + mic_button_loop)
    connection.py       (connect_with_retry + reconnect + restore_last_profile + shutdown)
```

### Protocol Subsystem

```python
class Subsystem(Protocol):
    name: str
    async def start(self, ctx: DaemonContext) -> None: ...
    async def stop(self) -> None: ...
    def is_enabled(self, config: DaemonConfig) -> bool: ...
```

Cada subsystem implementa o protocolo. A ordem de start é definida por `SUBSYSTEM_REGISTRY` em `subsystems/__init__.py`.

### DaemonContext

`DaemonContext` (em `context.py`) é uma dataclass que expõe `controller`, `bus`, `store`, `config` e `executor` para os subsystems, sem dependência do objeto `Daemon` completo.

### Backcompat

A classe `Daemon` permanece em `lifecycle.py` com a mesma API pública que existia antes do refactor:

- Métodos públicos: `run()`, `stop()`, `reload_config()`, `set_mouse_emulation()`.
- Métodos privados (chamados por testes): `_start_hotkey_manager()`, `_stop_hotkey_manager()`, `_start_mouse_emulation()`, `_stop_mouse_emulation()`, `_reassert_rumble()`, `_evdev_buttons_once()`, `_dispatch_mouse_emulation()`, `_start_ipc()`, `_start_udp()`, `_start_autoswitch()`, `_start_mic_hotkey()`.
- Atributos: `controller`, `bus`, `store`, `config`, `_hotkey_manager`, `_audio`, `_mouse_device`, `_ipc_server`, `_udp_server`, `_autoswitch`, `_last_auto_mult`, `_last_auto_change_at`.
- Todos os identificadores importáveis: `BatteryDebouncer`, `DaemonConfig`, `_effective_mult_inline`, `AUTO_DEBOUNCE_SEC`, `BATTERY_DEBOUNCE_SEC`, `BATTERY_DELTA_THRESHOLD_PCT`, `BATTERY_MIN_INTERVAL_SEC`, `DEFAULT_POLL_HZ`, `RUMBLE_POLICY_MULT`.

Os métodos privados no `Daemon` são thin wrappers que delegam para as funções nos subsystems. O poll loop (`_poll_loop`) permanece no `Daemon` porque testes fazem monkeypatch desse método.

## Como adicionar um novo subsystem

1. Criar `src/hefesto/daemon/subsystems/<nome>.py` implementando o protocolo `Subsystem`.
2. Adicionar o subsystem ao `SUBSYSTEM_REGISTRY` em `subsystems/__init__.py`.
3. Adicionar a chamada condicional em `Daemon.run()` se o subsystem precisar de controle de habilitação via config.
4. Criar testes unitários em `tests/unit/test_subsystem_<nome>.py` mockando `DaemonContext`.

Exemplo mínimo:

```python
# src/hefesto/daemon/subsystems/metrics.py
class MetricsSubsystem:
    name = "metrics"

    async def start(self, ctx: DaemonContext) -> None:
        self._collector = MetricsCollector(bus=ctx.bus, store=ctx.store)
        await self._collector.start()

    async def stop(self) -> None:
        if self._collector:
            await self._collector.stop()

    def is_enabled(self, config: DaemonConfig) -> bool:
        return config.metrics_enabled
```

## Consequências

### Positivas

- Cada subsystem pode ser testado em isolamento (mockando `DaemonContext`).
- `lifecycle.py` reduzido de 677L para ~365L (com backcompat total).
- Adicionar novo subsystem requer apenas criar um arquivo e registrá-lo.
- Separação de responsabilidades clara: poll != ipc != udp != rumble.

### Negativas

- O poll loop permanece em `lifecycle.py` por razão de backcompat de testes.
- Wrappers thin adicionam uma camada de indireção que pode confundir ao debugar.
- Imports circulares são um risco latente: subsystems não devem importar de `lifecycle` (apenas via `TYPE_CHECKING`).

## Alternativas consideradas

- **Herança**: `Daemon` estenderia classes base para cada subsystem. Rejeitada por tornar a hierarquia opaca e dificultar substituição individual.
- **asyncio.Protocol / plugin loader**: Reservado para FEAT-PLUGIN-01, que depende desta arquitetura mas é implementado separadamente.

## Referências

- Sprint REFACTOR-LIFECYCLE-01
- ADR-008: polling BT vs USB
- FEAT-PLUGIN-01: plugin loader externo (depende desta ADR)
