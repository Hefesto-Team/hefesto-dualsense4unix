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

Quebrar `lifecycle.py` em um pacote `src/hefesto_dualsense4unix/daemon/subsystems/` com os seguintes módulos:

```
daemon/
  lifecycle.py          (orquestrador slim, ≤ 400L com backcompat total)
  context.py            (DaemonContext dataclass)
  state_store.py        (permanece inalterado)
  subsystems/
    __init__.py         (SUBSYSTEM_REGISTRY: a lista única; subir e parar)
    base.py             (Protocol Subsystem: start/stop/is_enabled)
    poll.py             (BatteryDebouncer + evdev_buttons_once)
    ipc.py              (start_ipc)
    udp.py              (start_udp)
    autoswitch.py       (start_autoswitch)
    mouse.py            (start/stop/dispatch_mouse)
    rumble.py           (reassert_rumble + _effective_mult_inline)
    hotkey.py           (start/stop_hotkey_manager + mic_button_loop)
    connection.py       (reconnect_loop + restore_last_profile + shutdown)
```

### A lista única (nota de 16/10/2026)

O desenho de abril previa uma classe por subsystem, todas sobre o protocolo `Subsystem`. Só cinco
delas (`BtMic`, `AltoFalante`, `Conexoes`, `Plugins`, `Metrics`) foram construídas; as outras oito
(`Poll`, `Ipc`, `Udp`, `Dsu`, `Autoswitch`, `Mouse`, `Gamepad`, `Rumble`) ficavam na lista sem que o
`Daemon` as usasse, e o `run()` e o `shutdown()` mantinham, cada um, a sua lista escrita à mão.
Esquecer uma das duas era o defeito: o `BtMic` e o `AltoFalante` nasceram órfãos assim.

Hoje `SUBSYSTEM_REGISTRY` é uma tupla de `Passo(nome, partida, quando, parada, parar_em, ...)`.
`Daemon.run()` chama `subir(self)` (e `subir(self, depois_do_controle=True)` para as extensões), e
`connection.shutdown` chama `parar(self)`, que percorre a lista pela posição `parar_em` de cada entrada.
A ordem de parada não é a de partida, e fica declarada na própria entrada: o som e o microfone caem antes
do IPC, e o controle é a última coisa a ir. A parada que falha vira o aviso `subsystem_parada_falhou`
no diário e não impede as seguintes. A régua é
`tests/unit/test_o_subsystem_sobe_e_desce_por_uma_lista_so.py`.

### DaemonContext

`DaemonContext` (em `context.py`) é uma dataclass que expõe `controller`, `bus`, `store`, `config` e `executor` para os subsystems, sem dependência do objeto `Daemon` completo.

### Backcompat

A classe `Daemon` permanece em `lifecycle.py` com a mesma API pública que existia antes do refactor:

- Métodos públicos: `run()`, `stop()`, `reload_config()`, `set_mouse_emulation()`.
- Métodos privados (chamados por testes): `_start_hotkey_manager()`, `_start_mouse_emulation()`, `_reassert_rumble()`, `_evdev_buttons_once()`, `_dispatch_mouse_emulation()`, `_start_ipc()`, `_start_udp()`, `_start_autoswitch()`.
- Atributos: `controller`, `bus`, `store`, `config`, `_hotkey_manager`, `_audio`, `_mouse_device`, `_ipc_server`, `_udp_server`, `_autoswitch`, `_last_auto_mult`, `_last_auto_change_at`.
- Todos os identificadores importáveis: `BatteryDebouncer`, `DaemonConfig`, `_effective_mult_inline`, `AUTO_DEBOUNCE_SEC`, `BATTERY_DEBOUNCE_SEC`, `BATTERY_DELTA_THRESHOLD_PCT`, `BATTERY_MIN_INTERVAL_SEC`, `DEFAULT_POLL_HZ`, `RUMBLE_POLICY_MULT`.

Os métodos privados no `Daemon` são thin wrappers que delegam para as funções nos subsystems. O poll loop (`_poll_loop`) permanece no `Daemon` porque testes fazem monkeypatch desse método.

## Como adicionar um novo subsystem

1. Escrever o subsystem em `src/hefesto_dualsense4unix/daemon/subsystems/<nome>.py`.
2. Acrescentar **uma entrada** `Passo(...)` ao `SUBSYSTEM_REGISTRY` em `subsystems/__init__.py`, com a partida,
   a condição `quando` (se depende da config), a parada e a posição `parar_em` entre as vizinhas.
3. Não tocar em `Daemon.run()` nem em `connection.shutdown`: eles só percorrem a lista. A régua
   (`tests/unit/test_o_subsystem_sobe_e_desce_por_uma_lista_so.py`) reprova a classe `*Subsystem` que
   ficar fora da lista e o `_safe_start` escrito fora dela.
4. Criar o teste do gate e da parada em `tests/unit/test_subsystem_<nome>.py`.

## Consequências

### Positivas

- Cada subsystem pode ser testado em isolamento (mockando `DaemonContext`).
- `lifecycle.py` reduzido de 677L para ~365L (com backcompat total).
- Adicionar novo subsystem requer apenas criar o arquivo e acrescentar uma entrada à lista.
- A ordem de partida e a de parada moram num lugar só: a régua reprova a classe `*Subsystem` fora da
  lista, o `_safe_start` fora dela e o `_start_*`/`_stop_*` que a lista nomeia sem o `Daemon` ter.

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
