# ADR-008: Bluetooth vs USB no polling

**Status:** aceito

## Contexto
`pydualsense` expõe HID sem diferenciar transporte. Na prática:
- USB: 1000Hz possível, battery report a cada pacote.
- BT: 250Hz típico, battery report esparso, latência maior.
- Gatilho adaptativo via BT tem comportamento ligeiramente diferente em `Machine` e `Galloping`.

## Decisão
- Daemon faz poll fixo a 60Hz (suficiente para gatilhos, economia de CPU).
- `ControllerState.transport: Literal["usb", "bt"]` exposto para UI e lógica dependente (V2-7).
- `FakeController` tem dois replays determinísticos: `tests/fixtures/hid_capture_usb.bin` e `tests/fixtures/hid_capture_bt.bin`. Gravação via `scripts/record_hid_capture.py --script captures/script_default.yaml` (V3-8) garante equivalência byte-a-byte para partes determinísticas do protocolo. Testes W1.3 cobrem ambos.
- Debounce de battery no evento (V2-17): dispara `battery_change` se `abs(delta_pct) >= 1` OU `elapsed_since_last >= 5.0s`, com rate ceiling de 100ms entre eventos consecutivos. Vale para ambos transportes.

## Consequências
BT vê latência 16–32ms maior — aceitável para gatilhos, não para competitivo. `poll_hz` é configurável em `daemon.toml` se alguém reclamar. Event bus não é inundado em USB (battery reportada a cada 16ms sem debounce = spam).
