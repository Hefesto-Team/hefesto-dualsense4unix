# ADR-012: GUI reconnecta ao daemon automaticamente com máquina de 3 estados

## Contexto

Até 2026-04-21, a GUI abria uma vez, consultava o daemon via IPC e renderizava o resultado. Se o daemon estivesse offline ou ficasse offline depois (socket morreu, service reiniciou, controle desconectou), o header mostrava "daemon offline" em vermelho e ficava assim — usuário não sabia se precisava esperar, reiniciar o service manualmente ou fechar a GUI. Pedido explícito do usuário: "o daemon sempre deve ficar online ao abrir o app".

Um modo ingênuo seria alternar binariamente online/offline a cada tick. Ruim: toda variação transiente (2–4 s de service restart, unplug-replug) pisca o estado. Usuário vê ansiedade onde deveria ver paciência.

## Decisão

Máquina de 3 estados com threshold:

```
ONLINE -----(IPC fail)-----> RECONNECTING (falhas < 3)
RECONNECTING -(IPC fail * N)-> OFFLINE       (N >= RECONNECT_FAIL_THRESHOLD = 3)
RECONNECTING -(IPC ok)-----> ONLINE
OFFLINE -----(IPC ok)------> ONLINE
```

- Polling a **2 s** via `GLib.timeout_add_seconds(2, _tick_reconnect_state)`.
- **Threshold de 3** falhas consecutivas (6 s de indisponibilidade) antes de transicionar para OFFLINE. Absorve restart curto do systemd sem flicker.
- **Três renderers visuais** no header da GUI:
  - ONLINE: `● conectado via <transport>` (verde `#2d8`, U+25CF).
  - RECONNECTING: `◐ tentando reconectar...` (laranja `#d90`, U+25D0 — semântico intermediário).
  - OFFLINE: `○ daemon offline` (vermelho `#d33`, U+25CB).
- **Botão "Reiniciar daemon"** na aba Daemon — atalho humano quando o usuário quer intervir sem esperar, roda `systemctl --user restart hefesto.service` via subprocess. Fica desabilitado se `detect_installed_units()` retornar `None`.

## Consequências

(+) Usuário tem feedback contínuo: pisca-pisca de estados transientes some; estado real aparece rápido quando estável.
(+) Reconect automático resolve o caminho feliz sem intervenção — abriu a GUI, daemon inicia, header fica verde.
(+) Botão de restart dá controle humano para quando o daemon entrou em estado patológico (hardware perdido, socket corrompido).
(−) Polling constante custa ~1 chamada IPC a cada 2 s. Mensurado em < 1% CPU numa máquina Pop!_OS 22.04.
(−) Threshold fixo de 3. Se algum dia o service demorar > 6 s para bootar, o usuário vê OFFLINE brevemente. Aceitável — melhor que thrashing.
