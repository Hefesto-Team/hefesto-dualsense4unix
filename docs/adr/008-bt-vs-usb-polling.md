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

## Medição
Os números de USB acima vêm de `docs/research/2026-04-20-polling-usb.csv` (6
frequências alvo, controle físico, gerado por `scripts/benchmark_polling.py`).

## Consequências
BT vê latência 16–32ms maior — aceitável para gatilhos, não para competitivo. `poll_hz` é configurável em `daemon.toml` se alguém reclamar. Event bus não é inundado em USB (battery reportada a cada 16ms sem debounce = spam).

## Nota de verificação — 2026-07-25

`poll_hz` **é** configurável, mas não por `daemon.toml` — esse arquivo não é
lido pelo daemon. A chave real é a variável de ambiente
`HEFESTO_DUALSENSE4UNIX_POLL_HZ`, lida em `daemon/main.py` na subida (ou o
parâmetro `poll_hz` do `run_daemon`).

## Nota de verificação — 2026-07-31

O terceiro item da Decisão fala em **dois** replays determinísticos. Só existe
um. Conferido no repositório em 31/07/2026:

- `tests/fixtures/hid_capture_usb.bin` — existe (2630 bytes).
- `tests/fixtures/hid_capture_bt.bin` — **não existe**. O diretório
  `tests/fixtures/` tem só o capture USB e o `__init__.py`.

Nenhum teste aponta para o capture de BT: a única citação de fixture de capture
na suíte é `tests/unit/test_fake_controller_capture.py`, e ela usa o arquivo
USB. A frase "Testes W1.3 cobrem ambos" não se sustenta — o replay de
BT nunca foi coberto porque o insumo nunca esteve aqui.

A fixture **não foi inventada de propósito**. Ela só pode nascer de uma
gravação num DualSense real emparelhado por Bluetooth; forjar bytes sintéticos
daria um replay que passa e não representa o transporte — o oposto do que um
capture determinístico serve para fazer. Fica registrada como ausência, e a
gravação como trabalho aberto para quando houver o controle em BT à mão.

O comando de gravação citado na mesma linha também não roda: `--script
captures/script_default.yaml` não existe em `scripts/record_hid_capture.py`
(zero ocorrências de `--script` no arquivo). O YAML existe em `captures/`, mas
nenhum flag o consome. A invocação real, do `--help` do próprio script, exige
`--transport` e `--output`:

```bash
python scripts/record_hid_capture.py --transport bt --guided \
    --output tests/fixtures/hid_capture_bt.bin
```

`--guided` narra passo a passo o que apertar, que é o que dá a
reprodutibilidade que a ADR atribuía ao YAML.
