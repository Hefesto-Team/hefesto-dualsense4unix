# ADR-012: GUI reconnecta ao daemon automaticamente com máquina de 3 estados

**Status:** aceito

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
  - ONLINE: ` conectado via <transport>` (verde `#2d8`, U+25CF).
  - RECONNECTING: ` tentando reconectar...` (laranja `#d90`, U+25D0 — semântico intermediário).
  - OFFLINE: ` daemon offline` (vermelho `#d33`, U+25CB).
- **Botão "Reiniciar daemon"** na aba Daemon — atalho humano quando o usuário quer intervir sem esperar, roda `systemctl --user restart hefesto.service` via subprocess. Fica desabilitado se `detect_installed_units()` retornar `None`.

## Consequências

(+) Usuário tem feedback contínuo: pisca-pisca de estados transientes some; estado real aparece rápido quando estável.
(+) Reconect automático resolve o caminho feliz sem intervenção — abriu a GUI, daemon inicia, header fica verde.
(+) Botão de restart dá controle humano para quando o daemon entrou em estado patológico (hardware perdido, socket corrompido).
(−) Polling constante custa ~1 chamada IPC a cada 2 s. Mensurado em < 1% CPU numa máquina Pop!_OS 22.04.
(−) Threshold fixo de 3. Se algum dia o service demorar > 6 s para bootar, o usuário vê OFFLINE brevemente. Aceitável — melhor que thrashing.

## Nota de verificação — 2026-07-31

A máquina de 3 estados confere com o código: `RECONNECT_FAIL_THRESHOLD = 3` em
`app/constants.py`, e o tick é `_tick_reconnect_state` em
`app/actions/status_actions.py`, agendado com `RECONNECT_POLL_INTERVAL_S`.

**Duas identificações da ADR estão erradas** e quem as copiar não acha nada:

- O botão "Reiniciar daemon" roda `systemctl --user restart
  hefesto-dualsense4unix.service`, não `hefesto.service` — o nome curto é o
  layout legado do projeto. A unidade real está em `SERVICE_NORMAL`
  (`daemon/service_install.py`) e é o que
  `on_daemon_service_restart` (`app/actions/daemon_actions.py`) executa.
- A regra de sensibilidade não é `detect_installed_units()` — função com esse
  nome não existe em `src/`. Quem decide é
  `ServiceInstaller().detect_installed_unit()` (singular, método de classe),
  chamado por `_sync_restart_daemon_button_sensitivity`. Sem unidade
  instalada, o botão fica cinza com tooltip mandando rodar o `install.sh` —
  comportamento equivalente ao descrito, só o nome estava errado.

Duas coisas que a ADR não previa e valem registro, ambas conferidas no mesmo
arquivo: o restart roda em thread worker e devolve o resultado por
`GLib.idle_add` (antes era `subprocess.run` síncrono na thread GTK, que
congelava a janela por até 10 s —
BUG-GUI-SYSTEMCTL-SYNC-NA-THREAD-GTK-01); e o botão "Reiniciar" redundante da
aba Sistema foi removido, então este é o **caminho único** de restart pela GUI.
