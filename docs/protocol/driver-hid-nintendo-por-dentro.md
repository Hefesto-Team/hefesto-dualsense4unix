# O driver `hid-nintendo` por dentro — o C que governa o Pro e o clone 8BitDo

- **Levantado em:** 11/08/2026, lendo o **fonte do módulo que roda nesta
  máquina** e medindo os dois controles `057E:2009` que estavam ligados na hora
  (um por cabo, um por rádio)
- **Por que existe:** a página canônica dos externos descreve o **comportamento
  observável**. Esta descreve o **código que produz esse comportamento** — struct,
  offset, bitmask e `arquivo.c:linha` — para que a próxima pergunta de protocolo
  se responda lendo, e não remedindo
- **Relação com as outras páginas:** esta página **complementa** e **não
  substitui** `docs/protocol/externos-referencia-canonica.md`. Onde a canônica
  já responde, esta cita a seção e segue. Onde as duas divergirem sobre um
  número **medido**, a canônica vence; onde divergirem sobre o que o **código
  faz**, esta vence, porque foi lida do fonte instalado

---

## 0. Como ler

### 0.1 As três fontes, e elas não têm o mesmo peso

| marca | o que significa |
|---|---|
| **[DRIVER-AQUI]** | lido no fonte do módulo instalado nesta máquina. Verdade local, verificável agora |
| **[MAINLINE]** | trecho que os patches da casa **não** tocam, logo é o `hid-nintendo` de origem |
| **[COMUNIDADE]** | engenharia reversa pública (dekuNukem e derivados). O driver a cita como fonte, e ela **já foi refutada nesta casa em pelo menos um número** |
| **[MEDIDO 11/08]** | medido no hardware dela hoje, com a régua descrita na seção 9 |

Graus de confiança: **ALTA**, **MÉDIA**, **SEM PROVA** — a mesma escala da
página canônica.

### 0.2 A correção de premissa que abre esta página

O envelope de subcomando do protocolo Switch é o report **`0x01`**, não o
`0x10`. O `0x10` existe e é **rumble puro, sem subcomando**. Os dois têm
cabeçalho parecido, e é por isso que se trocam.

Isto não é novidade: `docs/protocol/externos-referencia-canonica.md`, seção 3.3,
já traz a tabela certa. Fica registrado aqui porque a troca reapareceu, e
porque o próprio comentário do fonte é a prova mais curta — `hid-nintendo.c:581`:

```c
u8 output_id; /* must be 0x01 for subcommand, 0x10 for rumble only */
```

**[DRIVER-AQUI]** e **[MAINLINE]**, grau **ALTA**.

---

## 1. Qual driver é a verdade desta máquina

**Não é o `hid-nintendo` do kernel.** O módulo carregado é um fork da casa,
por DKMS, e o kernel o marca `(OE)`:

| item | valor |
|---|---|
| pacote DKMS | `hefesto-hid-nintendo/1.0.0`, estado `installed` |
| binário | `/lib/modules/7.0.11-76070011-generic/updates/dkms/hid-nintendo.ko.zst` |
| fonte na máquina | `/usr/src/hefesto-hid-nintendo-1.0.0/hid-nintendo.c`, 3303 linhas |
| fonte no repositório | `assets/dkms/hid-nintendo/hid-nintendo.c` |

**As duas cópias são byte a byte a mesma** — `sha256` idêntico nas duas, e
igual ao `SHA256_PATCHED_C` declarado em `assets/dkms/hid-nintendo/patch/BASELINE`:

```
8fa3ae00eed5c2a769acc5f8fe5a716e0c02e40c05c2e675db315e83d9151dae
```

**Consequência prática, e é o motivo de eu ter conferido:** toda citação
`hid-nintendo.c:linha` desta página vale igual para quem abrir o arquivo no
repositório e para quem abrir o arquivo instalado. **[MEDIDO 11/08]**, grau
**ALTA**.

### 1.1 O que separa este fork do mainline

Base: `v7.0.11` (commit Pop!\_OS em `assets/dkms/hid-nintendo/patch/BASELINE`),
mais quatro patches aplicados em ordem. **Nada além deles** — a paridade é
verificável revertendo na ordem inversa, e o `BASELINE` publica o `sha256` do
vanilla para isso.

| patch | o que muda |
|---|---|
| `0001` | não transmitir depois de esgotar o rate-limit; retry de probe por Bluetooth; limites viram parâmetros |
| `0002` | registrar os LED class devices mesmo quando o SET inicial falha |
| `0003` | encher o comando USB até o tamanho de report declarado; sobreviver a quem nunca responde `REQ_DEV_INFO` |
| `0004` | parar de esperar por um controle que ficou mudo |

**O que isso vale para esta página:** conferi, patch a patch, que **nenhum**
deles toca o nome dos LEDs, o bitmask do `0x30`, o subcomando do LED HOME, as
escalas da IMU ou o cálculo de taxa. Logo, tudo o que as seções 2 a 5 afirmam
sobre esses pontos é **[MAINLINE]** — vale em qualquer máquina com
`hid-nintendo`, não só nesta. Grau **ALTA**.

### 1.2 Os onze parâmetros, e os valores que estão valendo agora

O mainline tem **zero** parâmetros de módulo; a presença de
`/sys/module/hid_nintendo/parameters/` é, ela mesma, o marcador de "fork
carregado" que o doctor usa.

| parâmetro | default do fork | **valendo agora** |
|---|---|---|
| `bt_probe_retries` | 0 | **3** |
| `input_report_wait_ms` | 250 | **500** |
| `probe_info_timeout_ms` | 2000 | **4000** |
| `sync_send_tries` | 2 | **4** |
| `subcmd_rate_max_attempts` | 25 | 25 |
| `subcmd_silence_streak_max` | 0 | **3** |
| `skip_tx_on_rate_exceeded` | N | **Y** |
| `register_leds_on_set_failure` | N | **Y** |
| `usb_cmd_pad_to_report` | N | **Y** |
| `usb_send_conn_status` | N | **Y** |
| `usb_probe_degrade` | N | **Y** |

Os valores vêm de `assets/modprobe.d/hefesto-hid-nintendo.conf` e conferem, um a
um, com o que está em `/sys/module/hid_nintendo/parameters/` neste momento.
**[MEDIDO 11/08]**, grau **ALTA**.

**Os três últimos são a cura do clone**, e estão **ligados** — ou seja, a
correção que o `assets/dkms/hid-nintendo/README.md` descrevia como "escrita,
compilada e nunca carregada" **está no ar hoje**. A seção 6.4 mostra a prova.

---

## 2. O envelope de output

### 2.1 As duas structs, com offset real

**Subcomando** — `hid-nintendo.c:580`, `__packed`, 11 bytes de cabeçalho:

| offset | campo | bytes | conteúdo |
|---|---|---|---|
| 0 | `output_id` | 1 | `0x01` |
| 1 | `packet_num` | 1 | contador, **0 a 0xF** |
| 2 | `rumble_data` | 8 | 4 bytes por motor; zeros quando só se quer o subcomando |
| 10 | `subcmd_id` | 1 | o subcomando |
| 11 | `data[]` | variável | argumento do subcomando |

**Rumble puro** — `hid-nintendo.c:574`, 10 bytes, sem `subcmd_id` e sem `data`:
`output_id` = `0x10`, `packet_num`, `rumble_data[8]`.

**O contador de pacote é um só para os dois envelopes.** O mesmo campo
`ctlr->subcmd_num` é incrementado e enrolado em `0xF` tanto no caminho de
subcomando (`hid-nintendo.c:1204`) quanto no de rumble (`hid-nintendo.c:2065`):

```c
subcmd->packet_num = ctlr->subcmd_num;
if (++ctlr->subcmd_num > 0xF)
	ctlr->subcmd_num = 0;
```

**Não há CRC em barramento nenhum** — nem cabo, nem rádio. Quem vier do
DualSense espera um e não vai achar. **[DRIVER-AQUI]**/**[MAINLINE]**, grau
**ALTA**.

### 2.2 Quantos bytes o driver realmente transmite

`joycon_send_subcmd` (`hid-nintendo.c:1183`) transmite
`sizeof(*subcmd) + data_len`, isto é **11 + o tamanho do argumento**:

| subcomando | `data_len` | bytes no fio | onde |
|---|---|---|---|
| `SET_REPORT_MODE` `0x03` | 1 | **12** | `hid-nintendo.c:1543` |
| `SET_PLAYER_LIGHTS` `0x30` | 1 | **12** | `hid-nintendo.c:1220` |
| `SET_HOME_LIGHT` `0x38` | 5 | **16** | `hid-nintendo.c:1233` |
| `ENABLE_IMU` `0x40` | 1 | **12** | `hid-nintendo.c:1569` |
| `ENABLE_VIBRATION` `0x48` | 1 | **12** | `hid-nintendo.c:1562` |

**A ressalva que a canônica já tinha levantado como dívida (seção 7.2, item 3)
fica confirmada pelo fonte:** o descritor do controle declara **63 bytes** de
dados para os reports de saída, e o driver transmite **12**. O firmware
genuíno perdoa a transferência curta. **É exatamente esse perdão que o clone
não dá** no report `0x80` — ver a seção 6.2. Grau **ALTA**.

### 2.3 Os dois subcomandos que esta página foi pedida para cobrir

**`0x30` — Set Player Lights** (`hid-nintendo.c:1220`), um byte de argumento:

```c
req->data[0] = (flash << 4) | on;
```

**`0x40` — Enable IMU** (`hid-nintendo.c:1569`), um byte de argumento:

```c
req->data[0] = 0x01; /* note: 0x00 would disable */
```

O `ENABLE_IMU` é disparado **incondicionalmente, em todo barramento**, dentro
do `joycon_init` (chamada em `hid-nintendo.c:2937`), sob o único porteiro
`joycon_has_imu()` — que olha o **tipo** do controle, nunca o bus. A canônica
já afirmava isto na seção 3.5; fica confirmado.

**Corolário que vale repetir porque é dívida aberta:** o `enable_imu` do
produto (`core/external_leds.py`) monta o mesmo pacote que o kernel já mandou
sozinho. A canônica classifica isso como "provável código morto" (seção 7.2,
item 4), e nada no fonte do driver contradiz.

### 2.4 A tabela de subcomandos definidos

De `hid-nintendo.c:127` a `:149`. **Definido não é usado** — a última coluna é
a diferença que importa:

| id | nome | o driver usa? |
|---|---|---|
| `0x01` | `MANUAL_BT_PAIRING` | não |
| `0x02` | `REQ_DEV_INFO` | **sim** — identidade e MAC, no probe |
| `0x03` | `SET_REPORT_MODE` | **sim** — sempre `0x30` |
| `0x08` | `LOW_POWER_MODE` | não |
| `0x10` | `SPI_FLASH_READ` | **sim** — calibração |
| `0x11` | `SPI_FLASH_WRITE` | não |
| `0x30` | `SET_PLAYER_LIGHTS` | **sim** |
| `0x31` | `GET_PLAYER_LIGHTS` | **não — e isto é a seção 3.3** |
| `0x38` | `SET_HOME_LIGHT` | **sim** |
| `0x40` | `ENABLE_IMU` | **sim** |
| `0x41` | `SET_IMU_SENSITIVITY` | **não** — as escalas ficam no default |
| `0x48` | `ENABLE_VIBRATION` | **sim** |
| `0x50` | `GET_REGULATED_VOLTAGE` | não |

**[DRIVER-AQUI]**, conferido por `grep` de cada símbolo. Grau **ALTA**.

---

## 3. Os player LEDs

### 3.1 O bitmask, byte a byte

Um byte, dois nibbles (`hid-nintendo.c:1219`, o comentário é do próprio
mainline):

```
/* Supply nibbles for flash and on. Ones correspond to active */
        bit 7 6 5 4 | 3 2 1 0
            \_flash_/ \__on__/
```

- **nibble baixo (`on`)** — bit *i* aceso liga o player LED *i+1*, **fixo**;
- **nibble alto (`flash`)** — bit *i* aceso põe o player LED *i+1* para
  **piscar em hardware**;
- os dois nibbles são independentes: pisca sem aceso é um estado válido do
  aparelho.

**O driver nunca usa o pisca.** As duas únicas chamadas passam `flash = 0`
literal (`hid-nintendo.c:2486` e `:2555`). O piscar do aparelho existe, é
alcançável por `hidraw`, e **nenhum caminho do kernel o alcança**.
**[MAINLINE]**, grau **ALTA**. (A canônica já dizia isto na seção 3.6; aqui
fica o `arquivo:linha`.)

### 3.2 Os nós que o driver cria

`joycon_leds_create` (`hid-nintendo.c:2513`) monta o nome como
`"%s:%s:%s"` = `dev_name` + cor + função:

| nó | cor | `max_brightness` | subcomando por trás |
|---|---|---|---|
| `<inst>:green:player-1` a `-4` | `"green"` literal (`hid-nintendo.c:2539`) | **1** | `0x30` |
| `<inst>:blue:player-5` | `"blue"` literal (`hid-nintendo.c:2578`) | **15** | `0x38` — ver seção 4 |

Medido agora, os dez nós dos dois controles ligados existem e têm exatamente
esses `max_brightness`. **[MEDIDO 11/08]**, grau **ALTA**.

**Escrever um nó verde reescreve os quatro.**
`joycon_player_led_brightness_set` (`hid-nintendo.c:2466`) **ignora o
`brightness` que recebeu** e recompõe o bitmap inteiro a partir do estado
guardado dos quatro:

```c
for (i = 0; i < JC_NUM_LEDS; i++)
	val |= ctlr->leds[i].brightness << i;
```

O comentário acima da função é explícito: *"Because the subcommand sets all the
leds at once, the brightness argument is ignored"* (`hid-nintendo.c:2465`).

### 3.3 A pergunta decisiva: o driver relê o aparelho?

**Não. Nunca. Em nenhum caminho.** Três provas independentes, todas
verificáveis em segundos:

1. **Não existe `brightness_get`.** O driver só instala
   `brightness_set_blocking` (`hid-nintendo.c:2548` e `:2587`). `grep -c
   brightness_get` no fonte devolve **0**.
2. **`GET_PLAYER_LIGHTS` (`0x31`) é definido e jamais chamado.** O `grep` do
   símbolo devolve **uma única linha**: a própria `#define` em
   `hid-nintendo.c:142`. O aparelho sabe responder qual é o estado real das
   lâmpadas; o driver nunca pergunta.
3. **O nó de sysfs não tem por onde reler.** `ls` de um nó de player LED
   devolve `brightness`, `device`, `max_brightness`, `power`, `subsystem`,
   `trigger`, `uevent` — nada que possa disparar leitura de hardware.

**Portanto: `brightness` no sysfs é um cache de escrita.** Ele responde o que
foi escrito por último (ou o padrão que o probe inventou), **nunca o que a
lâmpada está fazendo**. **[DRIVER-AQUI]**/**[MAINLINE]**, grau **ALTA**.

### 3.4 E aqui o mesmo defeito do DualSense é pior: nesta máquina ele é opção ligada

A pergunta que originou esta seção foi: *medimos hoje que num DualSense o nó
sysfs afirma um valor enquanto o aparelho mostra outro; vale o mesmo aqui?*

**Vale, e nesta máquina há um caminho a mais para divergir, ligado de
propósito.** A ordem em `joycon_leds_create` é:

1. `led->brightness` recebe o padrão da tabela — `hid-nintendo.c:2546`,
   **antes de qualquer transmissão**;
2. só então `joycon_set_player_leds()` é chamado — `hid-nintendo.c:2555`;
3. se essa chamada **falhar**, o mainline **pula o registro** e não há nó
   nenhum. Com `register_leds_on_set_failure=Y` — que é o que está valendo —
   o fork **registra assim mesmo** (`hid-nintendo.c:2561`).

O resultado é um nó de sysfs que afirma um padrão de player que **o aparelho
nunca recebeu**, porque o único `set` falhou com `-ETIMEDOUT`. Isso não é
defeito do patch: é o preço, escolhido e documentado, de poder curar o
controle na escrita seguinte em vez de deixá-lo sem LEDs pela conexão inteira.
Mas quem for **ler** o nó precisa saber.

**Regra que sai daqui, e é a mesma dos dois lados da casa:** o nó de player LED
é **fonte de intenção, nunca de estado**. Para saber o que a lâmpada está
fazendo há dois caminhos, e nenhum deles é o sysfs: perguntar `0x31` por
`hidraw`, ou o olho dela. A docstring de `read_player_pattern` em
`core/external_leds.py` já avisa que "esta função NÃO enxerga lâmpada nenhuma";
esta seção é o **porquê**, no nível do driver. Grau **ALTA**.

### 3.5 O padrão que o probe acende sozinho

`hid-nintendo.c:2527` aloca um id por IDA e usa `id % 8`
(`JC_NUM_LED_PATTERNS`) como índice na tabela oficial da Nintendo
(`hid-nintendo.c:632`): `{1,0,0,0}`, `{1,1,0,0}`, `{1,1,1,0}`, `{1,1,1,1}`,
`{1,0,0,1}`, `{1,0,1,0}`, `{1,0,1,1}`, `{0,1,1,0}`.

Confere com o que está aceso agora — o controle do rádio no padrão 0
(`player-1`) e o do cabo no padrão 1 (`player-1` e `player-2`).

**Duas consequências que mordem:**

- o índice é **por ordem de probe do kernel**, não por jogador. Desconectar e
  reconectar troca o padrão;
- **não existe estado "sem número"**: o kernel sempre acende alguma coisa,
  antes de qualquer software da casa opinar.

---

## 4. A quinta lâmpada — confirmada, e ela não é um quinto jogador

**Confirmado pelo fonte: `:blue:player-5` é o LED HOME.** O driver registra o
`home_led` com o nome de função `LED_FUNCTION_PLAYER5`
(`hid-nintendo.c:2579`), dentro do bloco rotulado `home_led:`
(`hid-nintendo.c:2573`), e a escrita nele chama
`joycon_home_led_brightness_set` -> `joycon_set_home_led` -> subcomando
**`0x38`**, não `0x30`.

Isto **confirma** o que `docs/protocol/externos-referencia-canonica.md` já
afirmava na seção 3.6, agora com o `arquivo:linha`. Grau **ALTA**.

**O que ela é fisicamente:** o anel de luz sob o botão Home do Pro Controller.
Escala **0 a 15** porque o `0x38` é um programa de PWM; o Linux manda uma
versão curta de 5 bytes (`hid-nintendo.c:1242`):

```c
data[0] = 0x01;
data[1] = brightness << 4;
data[2] = brightness | (brightness << 4);
data[3] = 0x11;
data[4] = 0x11;
```

**Quem ganha o nó:** só quem passa em `jc_type_has_right()`
(`hid-nintendo.c:747`), isto é `JOYCON_CTLR_TYPE_JCR` ou
`JOYCON_CTLR_TYPE_PRO`. Um Joy-Con esquerdo não tem botão Home e não ganha o
nó — por isso o registro está sob condicional.

**O 8BitDo tem?** **O nó, sim.** `0003:057E:2009.0008:blue:player-5` existe
agora, com `max_brightness=15`. **[MEDIDO 11/08]**

**Mas o nó não prova a lâmpada.** O tipo do clone foi **sintetizado a partir do
PID** (seção 6.3), então `jc_type_has_right()` respondeu "sim" sem que o clone
tenha confirmado nada. Se o SN30 Pro tem anel de Home aceso por `0x38` é
**pergunta de olho**, e continua aberta — a canônica já a tem enfileirada como
P-4 (seção 8.4). Grau **SEM PROVA** para a lâmpada física; **ALTA** para o nó.

**A dívida que esta seção não resolve, e não deve resolver sozinha:**
`write_player_number` em `core/external_leds.py` escreve `1` no
`:blue:player-5` tratando-o como bit "+5" da numeração. A canônica já
classifica isso como defeito conhecido, "não voltar sem corrigir" (seção 7.2,
item 5). O fonte do driver **confirma o diagnóstico**: o nó é HOME, é outro
subcomando, e a escala é 0-15.

---

## 5. A IMU

### 5.1 As escalas, e de onde saem os números

Todas em `hid-nintendo.c:229` a `:261`, com a aritmética no comentário.
**[MAINLINE]**, grau **ALTA**.

| grandeza | fundo de escala | resolução declarada ao `evdev` | define |
|---|---|---|---|
| acelerômetro | +-8000 mG (**+-8 g**) | **4096** LSB/g | `JC_IMU_ACCEL_RES_PER_G` |
| giroscópio | **+-2000 graus/s** | **14247** LSB por (grau/s) x1000 | `JC_IMU_GYRO_RES_PER_DPS` |

Dois detalhes que enganam quem só olha a tabela:

1. **O giroscópio é reescalado por 1000.** `JC_IMU_PREC_RANGE_SCALE = 1000`
   existe porque 14,247 truncado para 14 perderia precisão demais. Por isso
   `JC_IMU_MAX_GYRO_MAG` é `32767000`, não `32767`. Quem ler o eixo cru sem
   dividir por 1000 erra por três ordens de grandeza.
2. **O 14,247 já traz uma correção de fabricante.** O valor geométrico seria
   16,38375 LSB/dps; a STMicro recomenda somar 15% para saturar a faixa sem
   ceifar, e o driver adota a recomendação. O número **não** é derivável só do
   fundo de escala.

`SET_IMU_SENSITIVITY` (`0x41`) **nunca é enviado** — as escalas acima são o
default do aparelho, e o driver as assume sem nunca as confirmar.

### 5.2 O formato no fio

Cada relatório de entrada carrega **três amostras**, little-endian,
12 bytes cada (`hid-nintendo.c:594` e `:1600`):

| offset na amostra | eixo |
|---|---|
| 0 | `accel_x` |
| 2 | `accel_y` |
| 4 | `accel_z` |
| 6 | `gyro_x` |
| 8 | `gyro_y` |
| 10 | `gyro_z` |

Dentro do `struct joycon_input_report` (`hid-nintendo.c:603`) elas começam no
**offset 13**, logo após `id`(0), `timer`(1), `bat_con`(2),
`button_status`(3-5), `left_stick`(6-8), `right_stick`(9-11),
`vibrator_report`(12). Total do bloco de IMU: **36 bytes**, terminando no 48.

**Há um `input_sync` por amostra**, dentro do laço de três — logo, no `evdev`,
**um `SYN_REPORT` = uma amostra de IMU**. É essa igualdade que torna a medição
da seção 5.4 possível sem tocar em `hidraw`.

### 5.3 A taxa declarada — e o driver declara duas coisas diferentes

O comentário de `joycon_parse_imu_report` (`hid-nintendo.c:1621`) é a fonte que
todo mundo cita. Ele diz, **[COMUNIDADE]**, que em modo padrão o controle
empurra relatórios assim:

| caso | declarado |
|---|---|
| Joy-Con (Bluetooth) | 15 ms |
| Joy-Con no grip por USB | 15 ms |
| **Pro Controller (USB)** | **15 ms** |
| **Pro Controller (Bluetooth)** | **8 ms** — *"this is the wildcard"* |

E o próprio comentário **desmente o 8 ms na frase seguinte**:

> *"In my own testing, I've discovered that my pro controller either reports IMU
> sample batches every 11ms or every 15ms. This rate is stable after
> connecting."*

Ele explica por quê: alguns stacks Bluetooth fixam o **SSR** do link (o
comentário cita o Android fixando 11 ms), e a taxa do controle passa a ser a do
link, não a do firmware.

**O driver não confia no número declarado — ele aprende o de verdade.**
`imu_avg_delta_ms` começa em `JC_IMU_DFLT_AVG_DELTA_MS = 15` e é **recalculado
a cada 300 amostras** (`hid-nintendo.c:1694`). É esse valor aprendido, não o
declarado, que vira o carimbo de tempo `MSC_TIMESTAMP` entregue ao userspace.

### 5.4 O que este hardware entrega — medido hoje

O projeto tinha registrado *"o Pro declara 8 ms e entrega 11,2 ms"*.
**Confirmado, por duas rotas independentes.**

**Rota A — o próprio kernel dizendo.** O `dmesg` desta sessão, na compensação
de pacote perdido do Pro por Bluetooth:

```
nintendo 0005:057E:2009.0007: compensating for 4 dropped IMU reports
nintendo 0005:057E:2009.0007: delta=61 avg_delta=11
```

`avg_delta=11` é o valor que o driver **aprendeu** sozinho, em dezenas de
linhas ao longo da sessão. Nunca 8, nunca 15.

**Rota B — contagem de `SYN_REPORT` no `evdev`**, 6 segundos por controle:

| controle | transporte | amostras/s | ms por amostra | **ms por relatório** |
|---|---|---|---|---|
| Pro genuíno | Bluetooth | 266,1 | 3,76 | **11,27** |
| 8BitDo SN30 Pro | cabo | 200,5 | 4,99 | **14,96** |

**Veredito:** o **8 ms declarado é refutado** para este link — o Pro entrega
**11,27 ms**, que bate com os 11,2 ms já medidos em 07/08 por `hidraw` cru, e
com o `avg_delta=11` do kernel. Três rotas, três instrumentos, mesmo número.
**[MEDIDO 11/08]**, grau **ALTA**.

O 8BitDo por cabo cai no ramo de **15 ms**, exatamente o que o comentário
declara para Pro Controller por USB. E os 4,99 ms por amostra batem com o
*"usually 5ms apart"* do mesmo comentário. Grau **ALTA**.

**A ressalva honesta, e ela é grande:** os dois controles não estavam no mesmo
transporte. **Não posso separar "clone" de "cabo" com esta medição.** O que
está provado é que o 8BitDo por cabo entrega 15 ms; se o Pro genuíno por cabo
entrega o mesmo (o esperado) é conclusão por analogia, não medição. Fica
enfileirado na seção 8.

### 5.5 O aviso de perda, e como não o ler errado

`JC_IMU_DROPPED_PKT_WARNING = 3` (`hid-nintendo.c:227`), e o teste é `>` — o
aviso sai a partir de **4** perdidos. A conta (`hid-nintendo.c:1714`) usa o
limiar `avg_delta * 3 / 2`, logo é sempre relativa à taxa aprendida.

**`N` conta relatórios, não amostras.** "compensating for 4 dropped IMU
reports" são **12 amostras**. A canônica já registra isso na seção 3.5; repito
porque é erro de fator 3 e ele já foi cometido.

---

## 6. O 8BitDo SN30 Pro em modo Switch

### 6.1 Atualização datada: hoje ele está na mesa, e probou inteiro

`docs/protocol/externos-referencia-canonica.md` registra, na seção 5, que nada
sobre o 8BitDo **em modo Switch** havia sido medido, e na seção 1.2 que ele
aparecia com o link de pé e sem HID nenhum.

**Isso mudou. Em 11/08/2026 o 8BitDo está ligado por cabo, em modo Switch, com
a probe concluída.** O device HID `0003:057E:2009.0008` tem:

| o que | prova |
|---|---|
| driver ligado | `driver` -> `nintendo` |
| dois inputs | `Nintendo Co., Ltd. Pro Controller` e `... (IMU)` |
| `hidraw` | `hidraw7` |
| cinco LEDs | `:green:player-1` a `-4` e `:blue:player-5` |
| bateria | `nintendo_switch_controller_battery_0003:057E:2009.0008` |

Compare com o estado quebrado que o `assets/dkms/hid-nintendo/README.md`
descreve, em que o diretório tinha só `modalias power report_descriptor
subsystem uevent`. **A cura do patch `0003` está no ar e funcionou.**
**[MEDIDO 11/08]**, grau **ALTA**.

### 6.2 O que ele implementa igual, diferente, e o que não implementa

| item | genuíno | 8BitDo | grau |
|---|---|---|---|
| VID:PID | `057E:2009` | **igual** | ALTA |
| serial / `HID_UNIQ` | `000000000001` | **igual** | ALTA |
| `HID_NAME`, `MODALIAS` | colidem | **igual** | ALTA |
| **`bcdDevice`** | **`0210`** | **`0200`** | **ALTA — é o único discriminador** |
| endpoint OUT | `ep_01` | `ep_02` | MÉDIA |
| relatório `0x30` (botões/analógicos/IMU) | sim | **sim** | MEDIDO 11/08 |
| **IMU de verdade** | sim | **sim — 200,5 amostras/s medidas** | MEDIDO 11/08 |
| **handshake USB (`0x80 0x02`) com 2 bytes** | responde | **não responde** | ALTA |
| handshake com 64 bytes | responde | **responde** (a probe conclui) | MÉDIA |
| `REQ_DEV_INFO` (`0x02`) | responde | **não confirmado** — a identidade pode ter vindo sintetizada | SEM PROVA |

**O que ele NÃO implementa, e é a causa de tudo:** o clone **ignora o comando
USB curto**. O driver mainline monta `u8 buf[2]` e transmite **2 bytes**,
embora o descritor do próprio controle declare 63 bytes de dados para o report
`0x80` e o endpoint seja de 64 (`wMaxPacketSize=0x0040`, `bInterval=8`,
medido agora). Conferi o descritor do 8BitDo ligado agora, e
a declaração está lá:

```
85 80 09 05 75 08 95 3f 91 83
```

`85 80` = Report ID `0x80`; `95 3f` = Report Count **63**. **[MEDIDO 11/08]**,
grau **ALTA**.

O genuíno perdoa a transferência curta; o clone não. Sem resposta ao handshake,
o driver cai no ramo *"assume ble pro controller"* **sem nunca ter posto o
controle em modo USB**, e morre um passo adiante em `-ETIMEDOUT`. O `-110` é
consequência, não causa. O comentário em `hid-nintendo.c:1104` documenta isso
no próprio fonte, e credita o relato original à linux-input (2023), que nunca
virou patch upstream. **[COMUNIDADE]** para a origem do relato; **[DRIVER-AQUI]**
para a cura.

**Sobre os descritores:** o do 8BitDo por cabo tem **203 bytes** e declara os
IDs `0x01 0x10 0x21 0x30 0x80 0x81 0x82`; o do Pro por rádio tem **170 bytes**
e declara `0x01 0x10 0x11 0x12 0x21 0x30 0x31 0x32 0x33 0x3F`. **Não conclua
"o clone declara menos" a partir disso** — os dois estão em transportes
diferentes, e os `0x80`/`0x81`/`0x82` são justamente os reports **de USB**,
enquanto os `0x11`/`0x31` são de MCU/NFC. A comparação só valeria com os dois
no mesmo barramento. Grau **ALTA** para os números; **SEM PROVA** para
qualquer conclusão sobre firmware.

### 6.3 A rede de segurança: identidade sintetizada

Com `usb_probe_degrade=Y` (ligado agora), um controle que não responde
`REQ_DEV_INFO` **não perde o device**. `joycon_synthesize_info`
(`hid-nintendo.c:2764`) reconstrói:

- **o tipo, a partir do PID** — `USB_DEVICE_ID_NINTENDO_PROCON` vira
  `JOYCON_CTLR_TYPE_PRO`. É por isso que o clone ganha nó de IMU e de LED HOME
  **sem ter confirmado nenhum dos dois**;
- **o MAC**, do status de conexão USB se ele veio; senão, um endereço
  **sintético e estável entre replugs**, montado com o bit de "localmente
  administrado" ligado (primeiro octeto `0x02`) para nunca colidir com OUI de
  fabricante, seguido de vendor e product.

`joycon_may_degrade` (`hid-nintendo.c:2745`) restringe tudo isso a **USB**. Por
Bluetooth uma falha significa link degradado, e fingir que o controle respondeu
seria mentira — lá a cura é `bt_probe_retries`.

**Ressalva de leitura, e ela é o gancho da seção 6.4:** eu **não** consigo
dizer, do estado atual, se a identidade do 8BitDo veio real ou sintetizada. A
linha que diferencia (`falling back to a synthesized identity`) sai no `dmesg`
do probe, e o probe dele é anterior ao buffer que consegui ler. Grau **SEM
PROVA** para qual dos dois caminhos foi tomado hoje.

### 6.4 A dívida: a marca existe, é conferida, e ninguém no produto a lê

**Verificado, e a dívida é real.**

- **Quem escreve:** `assets/84-nintendo-pro-variant.rules`, oito regras, casando
  `ATTR{bcdDevice}` em quatro subsistemas (`usb`, `hid`, `hidraw`, `input`).
  Entrega `HEFESTO_CONTROLLER_VARIANT` = `nintendo-pro` ou `8bitdo-pro-clone`,
  mais os symlinks `/dev/hefesto/nintendo-pro` e `/dev/hefesto/8bitdo-pro-clone`.
- **Quem confere:** `scripts/doctor.sh` — e confere **só a presença do arquivo
  de regra**. Não lê a marca em device nenhum.
- **Quem lê no produto:** **ninguém.** `grep -rn HEFESTO_CONTROLLER_VARIANT src/`
  devolve zero linhas.

Isto já está documentado em `docs/data/mapa-controles.csv` e no estudo de 07/08
sobre a cobertura do install. **Esta página não redescobre a dívida — ela
acrescenta as três medições que faltavam para fechá-la.**

**Medição 1 — a marca está viva no `hidraw`, agora:**

```
/dev/hidraw7  ->  HEFESTO_CONTROLLER_VARIANT=8bitdo-pro-clone
                  DEVLINKS=/dev/hefesto/8bitdo-pro-clone
```

**Medição 2 — e não está no device `hid`.** `udevadm info -q property` no
device `hid` do mesmo controle devolve `DEVPATH` e `HID_NAME`, sem a marca.
Não é a regra que falha: `udevadm test` no mesmo caminho **casa e imprime**
`HEFESTO_CONTROLLER_VARIANT=8bitdo-pro-clone`. O que falta é **persistência** —
o udev só guarda propriedade no banco para device com nó em `/dev`, e o device
`hid` não tem. A regra do nível `hid` serve para quem escuta o **evento**, não
para quem consulta depois.

**Medição 3 — por Bluetooth a marca é impossível.** O Pro por rádio pendura em
`/devices/virtual/misc/uhid/`, e a cadeia de pais inteira tem **zero**
ocorrência de `bcdDevice`. `bcdDevice` é descritor **USB**. Nenhuma regra
baseada nele pode marcar um controle por rádio, hoje ou nunca.

**O que seria preciso para distinguir os dois em runtime:**

1. **Por cabo — barato, e o produto já está com a chave na mão.** Ler
   `HEFESTO_CONTROLLER_VARIANT` **do nó `hidraw`**, onde ela está persistida.
   `core/external_leds.py` já resolve o caminho do `hidraw` para o device
   (`hid_instance_for_hidraw`), então o leitor é uma consulta a mais no
   caminho que já existe. Alternativa sem udev: ler `bcdDevice` subindo do
   `hidraw` até o `usb_device` — a mesma informação, sem depender de a regra
   estar instalada.
2. **Por rádio — não resolvido, e não é falta de código.** Não há `bcdDevice`.
   O único eixo que sobrou é a **OUI** do endereço, que o produto já usa em
   outro lugar (`NINTENDO_REAL_OUI` em `daemon/subsystems/external_identity.py`).
   Se o 8BitDo em modo Switch anuncia uma OUI própria, resolve; se ele clona a
   da Nintendo também, **não há discriminador conhecido**. Isto é pergunta
   aberta e a canônica já a tem como P-2.
3. **O desempate a jusante.** A canônica e o estudo de 07/08 registram que
   `friendly_type()` consulta o par VID/PID antes da OUI, e por isso os dois
   Pro devolvem hoje a mesma string. Um leitor da marca **sem** corrigir esse
   desempate continua sem efeito visível.

Grau **ALTA** para as três medições e para o diagnóstico; **SEM PROVA** para o
caminho por rádio.

---

## 7. Cabo contra Bluetooth

### 7.1 O que muda no envelope

**Nada.** O `struct joycon_subcmd_request` é o mesmo, o `packet_num` é o mesmo,
o `0x30` é o mesmo. `__joycon_hid_send` (`hid-nintendo.c:867`) chama
`hid_hw_output_report` sem olhar o bus.

Isto é o **oposto** do DualSense, onde o envelope muda de tamanho e ganha CRC
ao sair do cabo. A canônica já faz essa contraposição na seção 3.3; o fonte
confirma. Grau **ALTA**.

### 7.2 O que muda no handshake

**Aqui muda tudo, e só de um lado.** `joycon_init` (`hid-nintendo.c:2839`)
tem um bloco inteiro que **só existe por USB**:

| passo | comando | só USB? |
|---|---|---|
| status de conexão (opcional, `usb_send_conn_status`) | `0x80 0x01` | **sim** |
| handshake | `0x80 0x02` | **sim** |
| baudrate 3M | `0x80 0x03` | **sim** |
| handshake de novo | `0x80 0x02` | **sim** |
| manter em modo USB | `0x80 0x04` | **sim** |
| `REQ_DEV_INFO`, calibração, IMU, report mode, rumble | subcomandos `0x01` | **não — os dois** |

Por Bluetooth o driver **pula o bloco inteiro** e vai direto aos subcomandos. O
controle já está no modo certo; não há o que negociar.

**A armadilha de diagnóstico que mora aqui:** um controle **de cabo** cujo
handshake falha é tratado *como se estivesse no rádio* — e todos os
subcomandos seguintes vão para um aparelho que não está ouvindo. No mainline
isso acontece **em silêncio**, porque `joycon_send_usb` só reporta em
`hid_dbg`. O patch `0003` acrescenta a linha que falta
(`hid-nintendo.c:2892`):

> `USB handshake got no reply (ret=%d); the controller was never put in USB mode`

Se essa linha aparecer no `dmesg`, o problema é o transporte, não o timeout.

### 7.3 O que muda nas taxas

| medida | cabo | Bluetooth | onde |
|---|---|---|---|
| rate limiter de subcomando | **20 ms** | **60 ms** | `hid-nintendo.c:978` e `:979` |
| janela de TX válida (delta de relatório) | 8 a 17 ms | 8 a 17 ms | `hid-nintendo.c:973` |
| deltas válidos seguidos exigidos | 3 | 3 | `hid-nintendo.c:976` |
| espera após receber, antes de transmitir | 4 ms | 4 ms | `hid-nintendo.c:975` |
| relatório de IMU, **medido hoje** | **14,96 ms** (8BitDo) | **11,27 ms** (Pro) | seção 5.4 |

**O rádio custa 3x mais caro por subcomando** — 60 ms contra 20 ms. É por isso
que "acender as cinco lâmpadas" pelo sysfs, que custa cinco subcomandos
(quatro redundantes do `0x30` mais o `0x38`), pesa muito mais no rádio.

Duas observações que só aparecem lendo o C:

1. **A janela válida de 8 a 17 ms é a mesma nos dois transportes** — e ela
   abraça de propósito tanto o ramo de 11 ms quanto o de 15 ms. O driver foi
   escrito sabendo que a taxa varia.
2. **`joycon_enforce_subcmd_rate` (`hid-nintendo.c:981`) espera por relatório
   de entrada antes de transmitir.** Um controle **mudo** nunca produz os
   deltas válidos, então o laço ia até o teto sempre. Com os valores desta
   máquina isso custava `4 x 25 x 500 ms = 50 s` de bloqueio sob mutex **por
   escrita de LED**. É o que o patch `0004` corta, e é por isso que
   `subcmd_silence_streak_max=3` está ligado.

### 7.4 O que só existe no rádio

`assets/dkms/hid-nintendo/README.md` registra o achado que não sai do fonte e
que é o mais contraintuitivo da mesa: **o 8BitDo precisa do sniff Bluetooth e o
Pro genuíno precisa que não haja** — dois controles com requisitos de firmware
opostos no mesmo adaptador. A canônica desenvolve isso na seção 6.3. Nada nesta
página contradiz.

---

## 8. O que eu NÃO consegui verificar

Honestidade primeiro, porque cada linha aqui é trabalho de outra sessão.

1. **Se o 8BitDo teve identidade real ou sintetizada hoje.** A linha decisiva
   do `dmesg` é anterior ao buffer legível. Custa um replug com `dmesg -w`.
2. **Se o clone responde `REQ_DEV_INFO`.** Mesma medição que a anterior.
3. **Pro genuíno por cabo.** Não estava no cabo, então a taxa de 15 ms por USB
   segue medida **só** no clone. Sem isso não dá para separar "efeito do
   transporte" de "efeito do firmware" na seção 5.4.
4. **8BitDo por rádio em modo Switch.** É o que decidiria se a distinção por
   OUI funciona (seção 6.4, item 2). Continua a P-2 da canônica.
5. **Se o anel de Home do 8BitDo acende.** O nó existe; a lâmpada é pergunta de
   olho. P-4 da canônica.
6. **Se `0x31` (`GET_PLAYER_LIGHTS`) responde de verdade.** Sei que o driver
   nunca pergunta. **Não** testei perguntar por `hidraw` — e não testei de
   propósito: disputar o `hidraw` com o driver vivo é a terceira das armadilhas
   listadas nas instruções da raiz do repositório, e o instrumento mentiria
   "aplicado" sem ter aplicado.
7. **Comparar descritores no mesmo barramento.** Ver a ressalva na seção 6.2.

---

## 9. Notas de instrumento

**A régua da seção 5.4 foi validada antes de eu acreditar nela.** Registro o
caminho porque a primeira tentativa estava errada e teria produzido um número
convincente e falso.

- **O que não funcionou:** contar **bytes** de `/dev/input/eventN`. Dá 1098
  eventos/s no 8BitDo, que parece taxa mas não é — o `evdev` **suprime eixo que
  não mudou**, então a contagem depende de quanto o controle está tremendo, não
  da taxa do link.
- **O que funcionou:** contar **só `SYN_REPORT`** (`type == EV_SYN && code ==
  SYN_REPORT`). Isso só é legítimo porque o fonte mostra **um `input_sync` por
  amostra**, dentro do laço de três (seção 5.2) — a régua foi conferida contra
  o código antes de ser usada.
- **A validação independente:** a rota B devolveu **11,27 ms** para o Pro
  genuíno. O kernel, sozinho e por outro caminho, vinha imprimindo
  `avg_delta=11`; e em 07/08 o projeto mediu **11,2 ms** por `hidraw` cru.
  **Três instrumentos, três rotas, mesmo número.** É isso que autoriza tratar o
  8 ms declarado como refutado.

**Sobre ler `dmesg`:** as linhas de IMU citadas na seção 5.4 são
`hid_warn_ratelimited` — elas só existem porque o link estava perdendo pacote.
Num link limpo o `avg_delta` não aparece no log, e a rota B passa a ser a única
disponível sem `hidraw`.

---

## 10. Fontes

**Fonte primária — o driver desta máquina.** `hid-nintendo.c`, 3303 linhas,
instalado em `/usr/src/hefesto-hid-nintendo-1.0.0/` e versionado em
`assets/dkms/hid-nintendo/`, `sha256` conferido igual nos dois e igual ao
declarado em `assets/dkms/hid-nintendo/patch/BASELINE`. Todas as citações
`hid-nintendo.c:linha` desta página apontam para ele.

**Mainline.** Não foi baixado: a separação entre "fork" e "mainline" foi feita
**localmente**, conferindo quais linhas os quatro patches em
`assets/dkms/hid-nintendo/patch/` tocam. É por isso que as marcas
**[MAINLINE]** desta página são afirmações sobre **o que os patches não
mudaram**, e não sobre um arquivo que eu tenha lido de outro lugar. Grau
**ALTA** para a separação; quem quiser o texto vanilla reverte os patches na
ordem inversa, como o `BASELINE` ensina.

**Comunidade.** dekuNukem, *Nintendo Switch Reverse Engineering* — citado pelo
próprio driver em `hid-nintendo.c:116` como origem dos `#define` de report. Toda
afirmação que vem daí está marcada **[COMUNIDADE]**, e ao menos uma delas (a
taxa de 8 ms por Bluetooth) **está refutada nesta casa**.

**Páginas irmãs, que esta não repete:**

- `docs/protocol/externos-referencia-canonica.md` — o comportamento observável
  dos dois externos, o inventário, a bateria, o rumble, o rádio e a fila de
  perguntas abertas;
- `docs/protocol/paridade-bluetooth-versus-cabo.md` — a régua do requisito de
  paridade;
- `assets/dkms/hid-nintendo/README.md` — a história dos quatro patches, o
  procedimento de A/B sem reboot e a escada de diagnóstico do clone;
- `assets/84-nintendo-pro-variant.rules` — a regra que separa os dois `057E:2009`,
  com o limite honesto dos dois clones idênticos.
