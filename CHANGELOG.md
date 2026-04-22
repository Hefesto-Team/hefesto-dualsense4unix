# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Segue [SemVer](https://semver.org/lang/pt-BR/).

## [Unreleased — rumo a 1.1.0]

### Adicionado (2026-04-22)
- **Módulo `single_instance`**: `acquire_or_takeover(name)` via `fcntl.flock` + SIGTERM(2s)→SIGKILL. Daemon e GUI passam a ser mutuamente exclusivos (modelo "última vence" no daemon). Previne 2+ instâncias criando `UinputMouseDevice` concorrentes (causa do bug "cursor voando" reportado pelo usuário).
- `install.sh`: flags `--enable-autostart` e `--enable-hotplug-gui`. Prompts interativos com default **NÃO** para ambos. Opt-in explícito elimina comportamento invasivo padrão.
- `uninstall.sh`: `pkill -TERM` → `pkill -KILL` residual após `systemctl stop` — zero processo órfão.
- `assets/hefesto.service`: `SuccessExitStatus=143 SIGTERM` (takeover não dispara respawn), `StartLimitIntervalSec=30 StartLimitBurst=3` (teto anti-loop).
- `HefestoApp.quit_app`: menu "Sair" do tray agora encerra daemon junto (`systemctl --user stop hefesto.service`).

### Corrigido (2026-04-22)
- **Cursor "voando" ao ativar aba Mouse**: causado por 2 daemons concorrentes criando 2 `UinputMouseDevice` separados que disputavam stick do DualSense via evdev e emitiam REL_X/REL_Y em paralelo. Fix via single-instance takeover.
- **PIDs renascendo ao matar processo**: cadeia de 5 fontes de spawn sem mutex (install.sh restart + hotplug unit + udev ADD + launcher GUI + ensure_daemon_running da GUI). Takeover + StartLimit corrige.
- `ensure_daemon_running` consulta pid file via `is_alive()` — não duplica `systemctl start` se o daemon já está vivo fora do systemd.
- Memória Claude (não faz parte do repo) atualizada refletindo HEAD real.

### Adicionado em docs (2026-04-22)
- **23 novas specs de sprint** em `docs/process/sprints/`, incluindo: BUG-TRAY-SINGLE-FLASH-01, BUG-DAEMON-STATUS-MISMATCH-01, BUG-RUMBLE-APPLY-IGNORED-01, FEAT-PLAYER-LEDS-APPLY-01, FEAT-BUTTON-SVG-01, UI-STATUS-STICKS-REDESIGN-01, UI-THEME-BORDERS-PURPLE-01, UI-PROFILES-EDITOR-SIMPLE-01, UI-GLOBAL-FOOTER-ACTIONS-01, UI-DAEMON-LOG-WRAP-01, UI-EMULATION-ALIGN-01, UI-MOUSE-CLEANUP-01, FEAT-TRIGGER-PRESETS-POSITION-01, FEAT-RUMBLE-POLICY-01, FEAT-DEB-PACKAGE-01, FEAT-FIRMWARE-UPDATE-01 (experimental, 3 fases), REFACTOR-HOTKEY-EVDEV-01, REFACTOR-DAEMON-RELOAD-01, FEAT-LED-BRIGHTNESS-02, FEAT-LED-BRIGHTNESS-03, DOCS-VERSION-SYNC-01. Especificações com critérios de aceite executáveis por dev jr.
- `docs/process/SPRINT_ORDER.md`: roadmap atualizado com 42 sprints em 3 waves + ordem paralelizável.
- `docs/process/HISTORICO_V1.md`: apêndice da onda pós-v1.0.0.
- `VALIDATOR_BRIEF.md`: armadilhas A-10 (múltiplas instâncias) e A-11 (race de udev ADD).

### Testes (2026-04-22)
- `test_single_instance.py` (6 testes): acquire, is_alive, pid órfão, takeover via fork com SIGTERM, release.
- `test_quit_app_stops_daemon.py` (4 testes): mock systemctl, FileNotFoundError, TimeoutExpired, tray.stop().
- `test_service_install.py`: atualizado para default `enable=False`, novo `test_install_enable_opt_in`.
- Total da suíte: **412 passed, 4 skipped** (skipped = quit_app no venv sem GdkPixbuf).

---

## [1.0.0] — 2026-04-21

Primeira release estável. Daemon + CLI + TUI + GUI GTK3 inteiros, falando com DualSense real via HID híbrido (pydualsense + evdev). 10 sprints de endurecimento e polimento sobre a 0.1.0.

### Adicionado
- **GUI GTK3 com banner visual**: logo circular (martelo + circuito tech) no canto superior-esquerdo, wordmark "Hefesto" em xx-large bold, subtitle "daemon de gatilhos adaptativos para DualSense". Janela com título `Hefesto - DSX para Unix`.
- **Reconnect automático na GUI**: máquina de 3 estados (`Online` / `Reconectando` / `Offline`) com polling IPC em thread worker, absorvendo restarts curtos do daemon sem flicker. Botão "Reiniciar Daemon" na aba Daemon dispara `systemctl --user restart hefesto.service` via subprocess assíncrono. Ver ADR-012.
- **Aba Mouse**: emulação mouse+teclado opt-in via `uinput` — Cross/L2 → BTN_LEFT, Triangle/R2 → BTN_RIGHT, D-pad → KEY_UP/DOWN/LEFT/RIGHT, analógico esquerdo → movimento com deadzone 20/128 e escala configurável, analógico direito → REL_WHEEL/REL_HWHEEL com rate-limit 50ms, R3 → BTN_MIDDLE. Toggle default OFF, sliders de velocidade na GUI.
- **Regra udev USB autosuspend**: `assets/72-ps5-controller-autosuspend.rules` força `power/control=on` e `autosuspend_delay_ms=-1` para `054c:0ce6` e `054c:0df2`. Elimina desconexão transiente do DualSense no Pop!_OS / Ubuntu / Fedora. Ver ADR-013.
- **`install.sh` orquestrado**: instalação completa em passada única — deps do sistema, venv, pacote editável, udev rules (com prompt interativo de sudo), `.desktop` + ícone + launcher desanexado, symlink `~/.local/bin/hefesto`, unit systemd `--user`, start automático do daemon. Flags `--no-udev`, `--no-systemd`, `--yes`, `--help`.
- **4 ADRs novos** (010–013) cobrindo socket IPC liveness probe, distinção glyphs vs emojis, máquina de reconnect, USB autosuspend.
- **Polish consistente de UI PT-BR**: Title Case em status (`Conectado Via USB`, `Tentando Reconectar...`, `Daemon Offline`, `Controle Desconectado`). Botões em português (`Iniciar`, `Parar`, `Reiniciar`, `Atualizar`, `Ver Logs`). Acentuação completa em labels visíveis. Siglas USB/BT/IPC/UDP preservadas em maiúsculas.

### Corrigido
- **Socket IPC com unlink cego** (crítico): `IpcServer.start()` agora faz liveness probe com timeout 0.1s antes de deletar o socket; `stop()` respeita `st_ino` registrado no start (soberania de subsistema, meta-regra 9.3). Smoke isolado via env var `HEFESTO_IPC_SOCKET_NAME=hefesto-smoke.sock`. Ver ADR-010.
- **AssertionError ruidoso em `udp_server.connection_made`**: assert gratuito contra `asyncio.DatagramTransport` removido (Python 3.10 entrega `_SelectorDatagramTransport` que não passa isinstance público). Journal limpo em cada startup.
- **GUI congelava com daemon lento ou offline**: `asyncio.run()` síncrono a 20 Hz na thread GTK bloqueava a janela. Migração para `ThreadPoolExecutor` com callbacks via `GLib.idle_add`; `LIVE_POLL_INTERVAL_MS = 100` (10 Hz); timeout de 250ms no `open_unix_connection`. Janela permanece responsiva mesmo com IPC morto.
- **Dualidade `hefesto.service` / `hefesto-headless.service` removida**: unit única. Dropdown da aba Daemon virou label estática `Unit: hefesto.service`. API singular `detect_installed_unit()`.
- **Glyphs Unicode de estado preservados**: `●` (U+25CF), `○` (U+25CB), `▮`/`▯` (U+25AE/U+25AF), `◐` (U+25D0) são UI textual funcional, não emojis. Distinção formalizada em ADR-011.

### Modificado
- **Novo ícone canônico** (`assets/appimage/Hefesto.png`): martelo + placa de circuito, gradiente teal→magenta. Cache GTK `hicolor` populado em 9 tamanhos (16 a 512 px) pelo `install.sh`.
- **`VALIDATOR_BRIEF.md`** criado na raiz com invariantes, contratos de runtime e registro das armadilhas A-01 a A-06 descobertas durante esta onda.

### Diagnósticos

- `pytest tests/unit` → **335 passed**, zero failures.
- `ruff check src/ tests/` limpo.
- `./scripts/check_anonymity.sh` OK.
- Smoke USB + BT completos sem traceback, socket de produção preservado.

---

## [0.1.0] — 2026-04-20

### Adicionado
- **Core HID**: `IController` síncrona, backend híbrido `PyDualSenseController` (output HID via pydualsense, input via evdev para contornar conflito com `hid_playstation`), `FakeController` determinístico com replay de capture.
- **Trigger effects**: 19 factories nomeadas (`Off`, `Rigid`, `Pulse`, `PulseA/B`, `Resistance`, `Bow`, `Galloping`, `SemiAutoGun`, `AutoGun`, `Machine`, `Feedback`, `Weapon`, `Vibration`, `SlopeFeedback`, `MultiPositionFeedback`, `MultiPositionVibration`, `SimpleRigid`, `Custom`), todas validadas em ranges com clamp em 255.
- **LED e rumble**: `LedSettings` imutável, `RumbleEngine` com throttle de 20ms e stop imediato.
- **Daemon**: `Daemon.run()` com poll 60Hz, signal handlers SIGINT/SIGTERM, BatteryDebouncer (V2-17), integração com IpcServer, UdpServer e AutoSwitcher.
- **EventBus pubsub** com `asyncio.Queue` por subscriber, drop-oldest em overflow, thread-safe via `call_soon_threadsafe`.
- **StateStore** thread-safe com `RLock`, snapshot imutável, contadores.
- **Profile schema v1** com pydantic v2 (`MatchCriteria` AND/OR, `MatchAny` sentinel), loader atômico com `filelock`, `ProfileManager` com activate/apply/select_for_window.
- **AutoSwitcher** com poll 2Hz e debounce 500ms, respeita `HEFESTO_NO_WINDOW_DETECT`.
- **Window detection X11** via `python-xlib`, `wm_class` segundo elemento (V3-6), `exe_basename` via `/proc/PID/exe`.
- **IPC JSON-RPC 2.0** sobre Unix socket 0600 com 8 métodos v1 e `IpcClient` async.
- **UDP server compat DSX** em `127.0.0.1:6969` com `RateLimiter` global 2000/s + per-IP 1000/s + `_sweep` periódico (V3-1), 6 tipos de instrução.
- **Gamepad virtual** Xbox 360 via `python-uinput` (VID `045e:028e`), forward analog + botões + d-pad com diff de estado.
- **HotkeyManager** com combo sagrado (PS+D-pad) e buffer 150ms, passthrough bloqueado em modo emulação (V2-4).
- **Systemd --user service** com unit única `hefesto.service` (SIMPLIFY-UNIT-01 revogou a dualidade normal/headless original da V2-12), `ServiceInstaller` com install/uninstall/start/stop/restart/status.
- **CLI completo**: `version`, `status`, `battery`, `led`, `tui`, `daemon start/install-service/uninstall-service/stop/restart/status`, `profile list/show/activate/create/delete`, `test trigger/led/rumble`, `emulate xbox360`.
- **TUI Textual**: `HefestoApp` com `MainScreen` mostrando info do daemon, lista de perfis, preview widgets (`TriggerBar`, `BatteryMeter`, `StickPreview`) com poll 10Hz via IPC.
- **Captures HID**: `record_hid_capture.py` grava estado em JSONL gzip (`.bin`), `FakeController.from_capture()` reproduz cronologicamente; gate de 5MB no CI.
- **9 ADRs** cobrindo escolhas de arquitetura.
- **Documentação completa**: protocolo UDP, IPC, trigger modes, quickstart.
- **Diário de descobertas** em `docs/process/discoveries/` (5 jornadas documentadas).

### Runtime validado
- 279 testes unit verdes em Python 3.10, 3.11 e 3.12.
- Smoke runtime real contra DualSense USB conectado em Pop!_OS 22.04, kernel 6.17.
- Proof visual (SVG) da TUI commitado em `docs/process/discoveries/assets/`.

### Pendente para v0.2+
- Captures HID com input ativo (#54).
- Matriz de distros testadas (`DOCS.2`).
- Guia de criação de perfis com `xprop` (`DOCS.1`).
- Benchmark de polling 60/120/1000 Hz (`INFRA.1`).
- Tray GTK3 AppIndicator (`W5.4`, opcional).
- Release PyPI (`W7.1`).
- AppImage bundle (`W7.2`, opcional).

### Não-escopo confirmado
- Windows, macOS, Wayland nativo, Bluetooth Audio.
- HidHide — superado pelo backend híbrido evdev+pydualsense (jornada em `docs/process/discoveries/2026-04-20-hotfix-2-hid-playstation-kernel-conflict.md`).

[0.1.0]: https://github.com/AndreBFarias/hefesto/releases/tag/v0.1.0
