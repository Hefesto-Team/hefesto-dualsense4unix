# ADR-008: Bluetooth vs USB no polling

**Status:** aceito

## Contexto
`pydualsense` expõe HID sem diferenciar transporte. Na prática:
- USB: **250 Hz exatos**, impostos pelo endpoint de interrupção do próprio
  controle (`bInterval 6` em High Speed = 4000 us). Battery report a cada pacote.
- BT: **não tem taxa típica** — o fluxo vem em rajadas. O sustentado medido
  variou de **38 a 392 Hz** entre janelas consecutivas de 8 a 10 s, no mesmo
  controle parado. Battery report esparso, latência maior.
- Gatilho adaptativo via BT tem comportamento ligeiramente diferente em `Machine` e `Galloping`.

Os dois números vêm de
[`docs/protocol/driver-hid-playstation.md`](../protocol/driver-hid-playstation.md),
medidos em 11/08/2026 por duas réguas independentes — relógio do host e relógio
do controle — que concordam entre si e, no cabo, com o descritor USB.

## Decisão
- Daemon faz poll fixo a 60Hz (suficiente para gatilhos, economia de CPU).
- `ControllerState.transport: Literal["usb", "bt"]` exposto para UI e lógica dependente (V2-7).
- `FakeController` tem **um** replay determinístico: `tests/fixtures/hid_capture_usb.bin`. O de Bluetooth **não existe** — a nota de 31/07 abaixo registra por que ele não pode ser forjado e qual é o comando para gravá-lo quando houver um DualSense em rádio à mão. Quem cobre o replay é `tests/unit/test_fake_controller_capture.py`, só no transporte USB. Gravação por `scripts/record_hid_capture.py --transport usb --guided --output <arquivo>`, que garante equivalência byte-a-byte para as partes determinísticas do protocolo.
- Debounce de battery no evento (V2-17): dispara `battery_change` se `abs(delta_pct) >= 1` OU `elapsed_since_last >= 5.0s`, com rate ceiling de 100ms entre eventos consecutivos. Vale para ambos transportes.

## Medição
As taxas de cada transporte, no Contexto acima, estão medidas em
[`docs/protocol/driver-hid-playstation.md`](../protocol/driver-hid-playstation.md).

`docs/research/2026-04-20-polling-usb.csv` (6 frequências alvo, controle
físico, gerado por `scripts/benchmark_polling.py`) mede **outra coisa**, e
confundir as duas é a origem do "1000 Hz por USB" que este ADR afirmava: aquele
CSV cronometra o **laço de leitura** do daemon — quantas chamadas a
`read_state()` cabem num segundo —, não quantos relatórios o controle envia. O
software dar 944 voltas por segundo não faz o aparelho mandar 944 relatórios: o
endpoint entrega um a cada 4 ms, e é ele quem manda.

## Consequências
BT vê latência 16–32ms maior — aceitável para gatilhos, não para competitivo. `poll_hz` é configurável em `daemon.toml` se alguém reclamar. Event bus não é inundado em USB (battery reportada a cada 16ms sem debounce = spam).

## Nota de verificação — 2026-07-25

`poll_hz` **é** configurável, mas não por `daemon.toml` — esse arquivo não é
lido pelo daemon. A chave real é a variável de ambiente
`HEFESTO_DUALSENSE4UNIX_POLL_HZ`, lida em `daemon/main.py` na subida (ou o
parâmetro `poll_hz` do `run_daemon`).

## Nota de verificação — 2026-07-31

Esta nota fica porque é ela que impede alguém de "resolver" a ausência
forjando bytes. Até 11/08/2026 o terceiro item da Decisão prometia **dois**
replays determinísticos e dizia que "Testes W1.3 cobrem ambos"; a frase foi
substituída pelo estado real, e o que segue é a conferência que a derrubou, no
repositório de 31/07/2026:

- `tests/fixtures/hid_capture_usb.bin` — existe (2630 bytes).
- `tests/fixtures/hid_capture_bt.bin` — **não existe**. O diretório
  `tests/fixtures/` tem só o capture USB e o `__init__.py`.

Nenhum teste aponta para o capture de BT: a única citação de fixture de capture
na suíte é `tests/unit/test_fake_controller_capture.py`, e ela usa o arquivo
USB. O replay de BT nunca foi coberto porque o insumo nunca esteve aqui.

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
