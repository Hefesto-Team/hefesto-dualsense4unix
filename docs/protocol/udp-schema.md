# Protocolo UDP — DSX canônico + dialeto do Hefesto

## Endpoint

`127.0.0.1:6969` (UDP). **Fixo** — não há arquivo de configuração que mude isso.

O daemon não lê `daemon.toml` (BUG-DAEMON-TOML-DEAD-01: o próprio código diz
isso no cabeçalho que a GUI escreve no arquivo, `app/actions/emulation_actions.py`).
Host e porta vivem em `DaemonConfig.udp_host` / `DaemonConfig.udp_port`
(`daemon/lifecycle.py`), com o mesmo default do `daemon/udp_server.py`.

Trocar a porta exige `daemon.reload` via IPC **e** um restart do daemon:
`config_overrides` aceita `udp_port` e o campo muda na hora, mas o socket é
aberto uma única vez na sequência de start (`_start_udp`) e o `reload_config`
não reinicia subsistemas — sem o restart, o daemon segue escutando na 6969.

### Quem pode mandar

Qualquer processo local. **Não há autenticação, token ou allowlist**: quem
alcança a porta manda gatilho, cor, player-LED e deadzone no controle dela. É
compatibilidade com o DSX **por decisão** (ADR-003) — os mods de Cyberpunk,
Forza e Assetto Corsa escrevem cru nessa porta e não têm onde carregar
credencial.

O que contém o estrago é o **bind em loopback**: `DEFAULT_HOST = "127.0.0.1"`,
então a porta não é alcançável de fora da máquina. O rate limit (adiante) é
proteção contra enxurrada, não contra intruso — ele limita o volume de quem já
está autorizado por estar na máquina. Consequência prática a ter em mente: numa
máquina compartilhada, ou com um jogo/mod não confiável rodando, esse processo
tem autoridade total sobre o controle. Não mude `udp_host` para `0.0.0.0`.

## Dois envelopes, a mesma porta

O daemon aceita **os dois** e decide por conteúdo, nunca por adivinhação.

**DSX canônico** — é o que o SDK da Paliverse emite. A classe `Packet` do SDK
carrega só `Instruction[] instructions`, e `type` é o ordinal do enum
`InstructionType` serializado por `Newtonsoft.Json`:

```json
{ "instructions": [ {"type": 1, "parameters": [0, 2, 15, 0, 9, 6, 7, 10]} ] }
```

**Dialeto do Hefesto** — textual, é o que a GUI, o CLI e os exemplos usam:

```json
{ "version": 1, "instructions": [ {"type": "TriggerUpdate", "parameters": ["right", "Galloping", 0, 9, 6, 7, 10]} ] }
```

Regra: `version` **ausente** = envelope do DSX (contador `udp.dsx_envelope`).
`version` **presente e diferente de `1`** continua sendo descarte com `log.warn`
(V2 5.10). `type` inteiro resolve pela tabela de ordinais; `type` string
continua valendo.

## Ordinais do `InstructionType`

| ordinal | instrução             | aceito |
|---------|-----------------------|--------|
| 1       | `TriggerUpdate`       | sim    |
| 2       | `RGBUpdate`           | sim    |
| 3       | `PlayerLED`           | sim    |
| 4       | `TriggerThreshold`    | sim    |
| 5       | `MicLED`              | sim    |
| 7       | `ResetToUserSettings` | sim    |
| 0, 6, 8+| `Invalid` / `GetDSXStatus` / `PlayerLEDNewRevision` | não — `udp.unknown_instruction` + `log.warn` |

**O enum do DSX não é único no ecossistema.** Quatro fontes públicas foram
conferidas antes de fixar esta tabela:

| fonte                                        | `TriggerThreshold` |
|----------------------------------------------|--------------------|
| `dvize/TarkovDSX` — `DSX/InstructionType.cs`  | 4 |
| `WujekFoliarz/DualSenseY-v2` — `include/udp.hpp` | 4 |
| `cosmii02/ForzaDSXlegacy` — `Program.cs`      | 4 |
| `cosmii02/RacingDSX` — `Program.cs`           | **6** |

O RacingDSX troca `TriggerThreshold` com `PlayerLEDNewRevision`. Vale a maioria
de 3 contra 1, e o desempate real é que o DualSenseY-v2 é um **servidor**: ele
tem de casar com o que os mods realmente emitem. O ordinal 6 fica **sem
mapeamento de propósito** — um mod do dialeto RacingDSX falha de forma visível
em vez de mexer no que não foi pedido.

## Instruções

Coluna **efeito real** = o que o daemon faz de fato. Nenhuma linha é
aspiracional: é o que `daemon/udp_server.py` executa, com teste para cada uma.

| type                  | layout DSX                     | layout Hefesto      | efeito real |
|-----------------------|--------------------------------|---------------------|-------------|
| `TriggerUpdate`       | `[idx, side, mode, p1..pN]`    | `[side, preset, …]` | `IController.set_trigger` via os presets de `core/trigger_effects.py`. Modos: ver abaixo. |
| `RGBUpdate`           | `[idx, r, g, b]`               | idem                | `set_led`, com clamp em 0-255. |
| `PlayerLED`           | `[idx, b1..b5]` (5 booleanos)  | `[idx, bitmask]`    | `set_player_leds`. Desambiguado por aridade (6 params = DSX). |
| `MicLED`              | `[idx, MicLEDMode]`            | `[state]`           | `set_mic_led`. `Pulse` (1) **degrada** para aceso, com `udp.mic_led.pulse_degradado`. |
| `TriggerThreshold`    | `[idx, side, value]`           | `[side, value]`     | **Deadzone do gatilho no gamepad virtual** — ver abaixo. |
| `ResetToUserSettings` | `[]`                           | `[]`                | **PARCIAL:** desliga os gatilhos e zera as deadzones. Não restaura cor/player-LED/mic. |

`side` aceita `"left"`/`"right"` ou o ordinal do enum `Trigger` (1=Left, 2=Right).

Instrução desconhecida incrementa `udp.unknown_instruction` e emite `log.warn`
— nunca é aceita em silêncio. Erro dentro de uma instrução conhecida
incrementa `udp.error.<type>`; sucesso incrementa `udp.applied.<type>`.

Não há validação por pydantic neste caminho: o parse é `json.loads` + checagem
de tipo por instrução, no próprio `UdpHandler`.

## Modos de gatilho do DSX (`TriggerMode`)

**Traduzidos** — o preset do Hefesto tem a mesma assinatura de parâmetros que o
helper C# correspondente (conferido em `DSX/Instruction.cs`):

| ordinal | `TriggerMode` do DSX      | preset do Hefesto        |
|---------|---------------------------|--------------------------|
| 0       | `Normal`                  | `Off` |
| 12      | `CustomTriggerValue`      | `Custom` (o 1º param é o `CustomTriggerValueMode`, traduzido para o modo HID) |
| 13      | `Resistance`              | `Resistance` |
| 14      | `Bow`                     | `Bow` |
| 15      | `Galloping`               | `Galloping` |
| 16      | `SemiAutomaticGun`        | `SemiAutoGun` |
| 17      | `AutomaticGun`            | `AutoGun` |
| 18      | `Machine`                 | `Machine` |
| 20-26   | `OFF`, `FEEDBACK`, `WEAPON`, `VIBRATION`, `SLOPE_FEEDBACK`, `MULTIPLE_POSITION_FEEDBACK`, `MULTIPLE_POSITION_VIBRATION` | os presets de mesmo nome |

Isso é mapeamento **semântico**, não transcrição de bytes: cada modo passa a
usar a implementação que o Hefesto já tem para aquele nome — a mesma que a GUI
e os perfis usam. Os bytes HID resultantes podem diferir dos do DSX.

**Não traduzidos** — `GameCube` (1), `VerySoft` (2), `Soft` (3), `Hard` (4),
`VeryHard` (5), `Hardest` (6), `Rigid` (7), `VibrateTrigger` (8), `Choppy` (9),
`Medium` (10), `VibrateTriggerPulse` (11), `VibrateTrigger10Hz` (19).

São **curvas de força fechadas**: o mod não manda parâmetro nenhum, o efeito
inteiro está numa tabela de bytes interna do DSX. Motivo concreto de não
estarem aqui: a única transcrição pública dessas tabelas que localizei está no
`DualSenseY-v2`, um repositório **sem licença** (`license: null` na API do
GitHub, sem arquivo `LICENSE`) — todos os direitos reservados. Copiá-las para
um projeto empacotado e distribuído seria problema de licença, não de
engenharia. Implementar com fidelidade exige documentação oficial da Paliverse
ou medir os bytes do DSX em execução. Até lá, o pedido falha com
`udp.error.TriggerUpdate` e uma mensagem que nomeia o modo.

## `controllerIndex`

**Descartado** — tudo é aplicado no controle primário. Índice `0` é silencioso
porque é o caso normal: o SDK declara `public const int ControllerIndex = 0;` e
todos os helpers de `Instruction.cs` mandam essa constante.

Índice **diferente de zero** é o caso que morde numa casa com quatro controles
(um por jogador): o mod pede o jogador 2 e o efeito sai no 1. Rotear de verdade
exige o mapa MAC→jogador, que vive no `CoopManager`, enquanto o `UdpHandler`
recebe apenas `controller` e `store` — a fiação não existe. Enquanto não
existir, o descarte é ao menos **auditável**: contador
`udp.controller_index_ignorado` e `log.warn` com o índice pedido.

## `TriggerThreshold` — o que ela faz (e onde não faz nada)

No DSX, `TriggerThreshold` **não é um efeito háptico**. É um corte no valor
ANALÓGICO que o gatilho entrega ao gamepad emulado:

```
valor_entregue = valor_bruto >= limiar ? valor_bruto : 0
```

Corte seco, sem reescala. O DualSense não tem campo de limiar no report de
saída — não existe forma de o hardware honrar isso —, então o Hefesto aplica
no mesmo ponto que o DSX: a fronteira entre o controle físico e o pad virtual
(`daemon/subsystems/gamepad.py`, `dispatch_gamepad`).

Consequências que o autor do mod precisa saber:

- **Só vale com a emulação de gamepad ligada.** Em Modo Nativo (jogo lendo o
  controle físico direto) não existe pad virtual onde cortar: o limiar fica
  guardado e não faz nada. O daemon loga `udp_trigger_threshold` em `info`
  toda vez que o valor muda — é por aí que se audita.
- **Vale para o jogador 1.** O `controllerIndex` do DSX é descartado (ver
  seção própria); os secundários do co-op local não são afetados.
- **É pegajoso.** Um limiar alto sobrevive à saída do mod. `ResetToUserSettings`
  (ou reiniciar o daemon) volta ao padrão `0`.
- Estado corrente exposto em `StateStore.udp_trigger_thresholds`; contador
  `udp.trigger_threshold.<side>.<value>`.

## Fidelidade ao DSX original — o que falta

O envelope e as seis instruções acima já são aceitas no formato canônico do
DSX. O que **ainda não** funciona sem adaptação, para não haver ilusão:

| lacuna | consequência para o mod |
|--------|--------------------------|
| Modos de gatilho "prontos" (12 dos 19 helpers de `Instruction.cs`: `Normal` à parte, todos de `GameCube` a `VibrateTriggerPulse`) | `udp.error.TriggerUpdate`; o gatilho não muda |
| `PlayerLEDNewRevision` (ordinal 6) | `udp.unknown_instruction`; sem efeito |
| Mods do dialeto RacingDSX (ordinal 6 = `TriggerThreshold`) | `udp.unknown_instruction`; sem efeito |
| `controllerIndex != 0` | aplicado no controle primário, com `log.warn` |
| `MicLED` modo `Pulse` | acende fixo em vez de pulsar |
| `GetDSXStatus` / qualquer resposta no fio | não há canal de resposta; um mod que espere confirmação do DSX não a recebe |
| `ResetToUserSettings` | restaura só gatilhos e deadzone |

Os modos "prontos" são a lacuna que mais pesa: são a maioria dos atalhos do
SDK, e é por eles que um mod simples começa.

## Rate limiting

Dois limites sobrepostos (V3-1):

- Global: 2000 pkt/s agregados.
- Per-IP: 1000 pkt/s.

IPs inativos evictados por `_sweep` periódico (máximo 1x/s).

## Extensões futuras (v2)

Schema nomeado (`{"type": "trigger", "side": "left", "mode": "Rigid", "params": {"position": 5, "force": 200}}`) previsto para v1.x+, sem pressa. Até lá, clientes enviam v1.
