# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Segue [SemVer](https://semver.org/lang/pt-BR/).

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
- **Systemd --user service** com `hefesto.service` e `hefesto-headless.service` mutuamente exclusivas (V2-12), `ServiceInstaller` com install/uninstall/start/stop/restart/status.
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
