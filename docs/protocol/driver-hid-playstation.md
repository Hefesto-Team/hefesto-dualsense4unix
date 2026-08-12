# O driver `hid-playstation` — a referência do lado do kernel

O que o **código C do driver** faz com o DualSense, campo a campo, e o que ele
entrega ao espaço de usuário. Escrito em 11/08/2026.

Esta página **não repete** a
[referência canônica do protocolo](dualsense-referencia-canonica.md): aquela
descreve o que o *aparelho* entende, e continua sendo a fonte de tudo que o
firmware aceita. Esta descreve o que o *driver* escolhe usar disso, o que ele
deixa em branco, e o que ele mostra em `/sys`. Onde as duas se tocam, esta
página cita a outra em vez de reescrevê-la.

## Como ler os graus de confiança

Mesma convenção da canônica (§ "Como ler os graus de confiança"), com um grau a
mais que esta página usa muito:

| grau | significa |
|---|---|
| **FONTE DESTA MÁQUINA** | lido no `.c` que compilou o módulo carregado agora. É o grau mais forte desta página: não é "o kernel faz assim", é "este kernel faz assim". |
| **ALTA** | está no kernel mainline, ou na enum da própria Sony, ou em duas ou mais engenharias reversas independentes que concordam |
| **MÉDIA** | uma fonte de comunidade respeitada, sem contradição conhecida |
| **BAIXA** | inferência ou fonte única |
| **MEDIDO AQUI** | conferido nesta máquina, nesta árvore, com a régua declarada |

## A fonte, e por que ela vale mais que o mainline

**GRAU: FONTE DESTA MÁQUINA.**

O módulo carregado agora **não é o do kernel**. É o DKMS desta casa:

```
$ modinfo -F filename hid_playstation
/lib/modules/7.0.11-76070011-generic/updates/dkms/hid-playstation.ko.zst
$ dkms status | grep playstation
hefesto-hid-playstation/1.0.0, 7.0.11-76070011-generic, x86_64: installed
```

O fonte está em `/usr/src/hefesto-hid-playstation-1.0.0/hid-playstation.c` e é
**byte a byte idêntico** ao vendorado em
`assets/dkms/hid-playstation/hid-playstation.c` (conferido por `diff` em
11/08/2026; 3171 linhas). **Todas as citações desta página usam o caminho da
árvore**, no formato `hid-playstation.c:LINHA`.

### O contraste com o mainline, e por que ele é curto

Segundo `assets/dkms/hid-playstation/README.md`, este fonte é **vanilla v7.0.11
mais dois patches**. Conferidos os hunks dos dois patches em 11/08/2026:

| patch | o que toca | toca o DualSense? |
|---|---|---|
| `0001` | renomeia `ps_get_report` para `__ps_get_report` e embrulha num laço de retry (hunks em 9, 21, 787, 823 do vanilla) | **não**, é código comum de leitura de feature report |
| `0002` | um `#define` de offset do DualShock4 e o caminho de pairing info do DS4 (hunks em 61, 382, 2228, 2243) | **não**, é código exclusivo do DS4 |

**Consequência que importa:** nenhuma linha específica do DualSense nesta página
foi patchada. As structs, a tabela de player LEDs, o `output_worker` e os
feature reports são **vanilla v7.0.11**. O que está descrito aqui vale
igualmente para o mainline daquela versão — a única coisa que o fork muda no
caminho do DualSense é *quantas vezes* um feature report é tentado na probe.

### O autor

O driver é da **Sony Interactive Entertainment** (`MODULE_AUTHOR`), copyright
2020-2022, escrito por Roderick Colenbrander. A canônica já trata disso em
§1.2 e não se repete aqui. O que aquela seção registra como limite honesto — "o
fonte do `hid-playstation` **não foi relido nesta passagem**" — é exatamente o
que esta página vem fechar.

## 1. As structs C dos reports

**GRAU: FONTE DESTA MÁQUINA** para tudo nesta seção.

Os identificadores e tamanhos, em `hid-playstation.c:140-154`:

| constante | valor |
|---|---|
| `DS_INPUT_REPORT_USB` / `_SIZE` | `0x01` / 64 |
| `DS_INPUT_REPORT_BT` / `_SIZE` | `0x31` / 78 |
| `DS_OUTPUT_REPORT_USB` / `_SIZE` | `0x02` / 63 |
| `DS_OUTPUT_REPORT_BT` / `_SIZE` | `0x31` / 78 |

Note o `0x31` nos **dois** sentidos: entrada e saída por rádio compartilham o
mesmo report ID, com tamanhos iguais e conteúdos completamente diferentes.

### 1.1. Entrada — `struct dualsense_input_report`

`hid-playstation.c:295-317`. O driver declara **um só** corpo de entrada e o
ancora em endereços diferentes conforme o transporte (`:1580-1595`):

- **USB, report `0x01`:** o corpo começa em `data[1]`. Somar **1** aos offsets.
- **BT, report `0x31`:** o corpo começa em `data[2]`. Somar **2**. O `data[1]`
  é pulado sem nome nem comentário — o driver não o lê nunca.

O `static_assert` de `:317` amarra o tamanho em `DS_INPUT_REPORT_USB_SIZE - 1`,
ou seja 63 bytes.

| off. struct | abs. USB | abs. BT | campo (nome real) | tipo | o que é |
|---|---|---|---|---|---|
| 0 | 1 | 2 | `x` | `u8` | analógico esquerdo, eixo X |
| 1 | 2 | 3 | `y` | `u8` | analógico esquerdo, eixo Y |
| 2 | 3 | 4 | `rx` | `u8` | analógico direito, eixo X |
| 3 | 4 | 5 | `ry` | `u8` | analógico direito, eixo Y |
| 4 | 5 | 6 | `z` | `u8` | gatilho esquerdo (L2) analógico |
| 5 | 6 | 7 | `rz` | `u8` | gatilho direito (R2) analógico |
| 6 | 7 | 8 | `seq_number` | `u8` | contador de sequência; **o driver não o lê** |
| 7-10 | 8-11 | 9-12 | `buttons[4]` | `u8[4]` | botões e hat (ver abaixo) |
| 11-14 | 12-15 | 13-16 | `reserved[4]` | `u8[4]` | nunca lido |
| 15-20 | 16-21 | 17-22 | `gyro[3]` | `__le16[3]` | giroscópio X, Y, Z |
| 21-26 | 22-27 | 23-28 | `accel[3]` | `__le16[3]` | acelerômetro X, Y, Z |
| 27-30 | 28-31 | 29-32 | `sensor_timestamp` | `__le32` | relógio do controle, unidade 0,33 us |
| 31 | 32 | 33 | `reserved2` | `u8` | nunca lido |
| 32-35 | 33-36 | 34-37 | `points[0]` | `struct` | primeiro ponto de toque |
| 36-39 | 37-40 | 38-41 | `points[1]` | `struct` | segundo ponto de toque |
| 40-51 | 41-52 | 42-53 | `reserved3[12]` | `u8[12]` | nunca lido |
| 52-54 | 53-55 | 54-56 | `status[3]` | `u8[3]` | bateria e jack (ver abaixo) |
| 55-62 | 56-63 | 57-64 | `reserved4[8]` | `u8[8]` | nunca lido |

Por Bluetooth, os **4 últimos bytes dos 78** são CRC-32 e o driver os confere
antes de qualquer parse (`:1585-1590`); reprovado, o report inteiro é
descartado com `-EILSEQ` e a mensagem `DualSense input CRC's check failed` — a
mesma assinatura que a
[paridade Bluetooth versus cabo](paridade-bluetooth-versus-cabo.md) registra na
contenção com vários controles.

**`buttons[4]`** (`:157-172`):

| byte | máscara | nome no fonte | evdev |
|---|---|---|---|
| `buttons[0]` | `GENMASK(3,0)` | `DS_BUTTONS0_HAT_SWITCH` | `ABS_HAT0X` / `ABS_HAT0Y` |
| `buttons[0]` | `BIT(4)` | `DS_BUTTONS0_SQUARE` | `BTN_WEST` |
| `buttons[0]` | `BIT(5)` | `DS_BUTTONS0_CROSS` | `BTN_SOUTH` |
| `buttons[0]` | `BIT(6)` | `DS_BUTTONS0_CIRCLE` | `BTN_EAST` |
| `buttons[0]` | `BIT(7)` | `DS_BUTTONS0_TRIANGLE` | `BTN_NORTH` |
| `buttons[1]` | `BIT(0)`..`BIT(3)` | `_L1`, `_R1`, `_L2`, `_R2` | `BTN_TL`, `BTN_TR`, `BTN_TL2`, `BTN_TR2` |
| `buttons[1]` | `BIT(4)`, `BIT(5)` | `_CREATE`, `_OPTIONS` | `BTN_SELECT`, `BTN_START` |
| `buttons[1]` | `BIT(6)`, `BIT(7)` | `_L3`, `_R3` | `BTN_THUMBL`, `BTN_THUMBR` |
| `buttons[2]` | `BIT(0)` | `DS_BUTTONS2_PS_HOME` | `BTN_MODE` |
| `buttons[2]` | `BIT(1)` | `DS_BUTTONS2_TOUCHPAD` | `BTN_LEFT` no nó de touchpad |
| `buttons[2]` | `BIT(2)` | `DS_BUTTONS2_MIC_MUTE` | **nenhum** — consumido internamente |

`buttons[3]` existe na struct e **não é lido em lugar nenhum**.

O botão de mudo do microfone é o único que não vira evento: o driver detecta a
borda de subida e **alterna o estado de mudo por conta própria**, programando o
aparelho (`:1631-1641`). O comentário do fonte é explícito — "the driver is
expected to read the button state and program the device to mute/unmute audio
at the hardware level". Quem quiser a posse desse LED precisa disputá-la; o
[IPC](ipc-unix-socket.md) já documenta o `muted: null` que devolve a posse.

**`status[3]`** (`:175-180`):

| campo | máscara | nome no fonte |
|---|---|---|
| `status[0]` | `GENMASK(3,0)` | `DS_STATUS0_BATTERY_CAPACITY` |
| `status[0]` | `GENMASK(7,4)` | `DS_STATUS0_CHARGING` |
| `status[1]` | `BIT(0)` | `DS_STATUS1_HP_DETECT` |
| `status[1]` | `BIT(1)` | `DS_STATUS1_MIC_DETECT` |
| `status[1]` | `BIT(2)` | `DS_STATUS1_MIC_MUTE` — **definido e nunca lido** |

`status[2]` existe e não é lido.

A tradução de bateria (`:1724-1753`) confirma linha a linha o que a canônica
§6 já descreve: `nibble * 10 + 5` limitado a 100, e cinco casos de estado de
carga (`0x0` descarregando, `0x1` carregando, `0x2` cheia, `0xa`/`0xb`
tensão/temperatura fora de faixa, `0xf` erro). Nada a acrescentar.

**`DS_STATUS1_JACK_DETECT`** (`:179`) é `HP_DETECT | MIC_DETECT`, e o driver só
o lê **sob USB** (`:1648`), com o comentário "Bluetooth audio is currently not
supported".

**`struct dualsense_touch_point`** (`:286-291`), 4 bytes:

| off. | campo | o que é |
|---|---|---|
| 0 | `contact` | `BIT(7)` = `DS_TOUCH_POINT_INACTIVE`; os 7 bits baixos são o ID do contato |
| 1 | `x_lo` | 8 bits baixos de X |
| 2 | `x_hi:4, y_lo:4` | campo de bits: 4 bits altos de X, 4 bits baixos de Y |
| 3 | `y_hi` | 8 bits altos de Y |

Resolução declarada: `DS_TOUCHPAD_WIDTH` 1920 por `DS_TOUCHPAD_HEIGHT` 1080
(`:230-231`).

### 1.2. Saída — `struct dualsense_output_report_common`

`hid-playstation.c:320-349`, com `static_assert` de **exatamente 47 bytes**.
Este bloco é idêntico nos dois transportes; só o cabeçalho muda.

| off. | abs. USB (`0x02`) | abs. BT (`0x31`) | campo (nome real) | o driver escreve? |
|---|---|---|---|---|
| 0 | 1 | 3 | `valid_flag0` | sim |
| 1 | 2 | 4 | `valid_flag1` | sim |
| 2 | 3 | 5 | `motor_right` | sim |
| 3 | 4 | 6 | `motor_left` | sim |
| 4 | 5 | 7 | `headphone_volume` | **nunca** (comentário do fonte: `0x0 - 0x7f`) |
| 5 | 6 | 8 | `speaker_volume` | sim, um único valor fixo |
| 6 | 7 | 9 | `mic_volume` | **nunca** (comentário: `0x0 - 0x40`) |
| 7 | 8 | 10 | `audio_control` | sim |
| 8 | 9 | 11 | `mute_button_led` | sim |
| 9 | 10 | 12 | `power_save_control` | sim |
| 10-36 | 11-37 | 13-39 | `reserved2[27]` | **nunca** |
| 37 | 38 | 40 | `audio_control2` | sim |
| 38 | 39 | 41 | `valid_flag2` | sim |
| 39-40 | 40-41 | 42-43 | `reserved3[2]` | **nunca** |
| 41 | 42 | 44 | `lightbar_setup` | só na probe |
| 42 | 43 | 45 | `led_brightness` | **nunca** |
| 43 | 44 | 46 | `player_leds` | sim |
| 44 | 45 | 47 | `lightbar_red` | sim |
| 45 | 46 | 48 | `lightbar_green` | sim |
| 46 | 47 | 49 | `lightbar_blue` | sim |

Os offsets batem com a tabela da canônica §2, campo a campo. O que a canônica
não tinha é a **última coluna**, e ela é o assunto da seção 6 desta página.

**O achado que a tabela esconde:** os gatilhos adaptativos moram inteiramente
dentro de `reserved2[27]`. A canônica §4 os coloca em `common[10..31]` — 11
bytes para o direito, 11 para o esquerdo —, e `reserved2` cobre `common[10..36]`.
Do ponto de vista do driver os gatilhos adaptativos **não têm nome**: são 27
bytes de reserva que ele zera e nunca toca.

### 1.3. Os invólucros por transporte

**USB, `struct dualsense_output_report_usb`** (`:361-366`), 63 bytes:

| off. | campo |
|---|---|
| 0 | `report_id` = `0x02` |
| 1-47 | `common` |
| 48-62 | `reserved[15]` |

**BT, `struct dualsense_output_report_bt`** (`:351-359`), 78 bytes:

| off. | campo |
|---|---|
| 0 | `report_id` = `0x31` |
| 1 | `seq_tag` |
| 2 | `tag` = `DS_OUTPUT_TAG` (`0x10`) |
| 3-49 | `common` |
| 50-73 | `reserved[24]` |
| 74-77 | `crc32` (`__le32`) |

O `seq_tag` (`:203-205`, montado em `:1389-1395`) é `GENMASK(7,4)` de número de
sequência mais `GENMASK(3,0)` de tag. O driver incrementa o número a cada report
e o rola em 16; o tag baixo ele fixa em zero. Sobre o `tag` alto o comentário é
honesto: *"Tag must be set. Exact meaning is unclear."*

**CRC-32** (`:136-138`, `:795-803`, `:1436-1443`): três sementes, prefixadas ao
buffer antes do `crc32_le` — entrada `0xA1`, saída `0xA2`, feature `0xA3`. A
canônica §7 já registra as três com grau ALTA; aqui elas ficam com **FONTE
DESTA MÁQUINA**.

A struct `dualsense_output_report` (`:373-384`) é só um despachante: guarda
`data`, `len`, e ponteiros `bt`, `usb` e `common`, de modo que o resto do driver
escreve em `common` sem saber por onde vai sair.

## 2. Os flags de validação, bit a bit

**GRAU: FONTE DESTA MÁQUINA.** Defines em `hid-playstation.c:207-219`.

A coluna que importa é a última: **quantas vezes o símbolo aparece no arquivo
inteiro**. Uma ocorrência significa que ele foi definido e **nunca usado**.

> **A coluna "autoriza" diz o que o report DECLARA, não o que o firmware
> EXIGE** (acrescentado em 12/08/2026). Os nomes abaixo são os do driver, e o
> driver descreve a intenção do protocolo. **Onde alguém já perguntou ao
> aparelho, a resposta divergiu:** os bytes de motor foram obedecidos com os
> bits `0x01` e `0x02` **desligados** — medido na bancada de 11/08 com o olho
> dela, e registrado na
> [canônica do DualSense](dualsense-referencia-canonica.md), §2. Para todos os
> outros bits desta seção **ninguém perguntou**, e ler esta tabela como
> porteiro é justamente o erro que já custou uma cura inteira aqui.

### `valid_flag0` (offset 0 do `common`)

| bit | valor | nome no fonte | autoriza | usos |
|---|---|---|---|---|
| 0 | `0x01` | `DS_OUTPUT_VALID_FLAG0_COMPATIBLE_VIBRATION` | `motor_left`/`motor_right`, rumble v1 | 2 |
| 1 | `0x02` | `DS_OUTPUT_VALID_FLAG0_HAPTICS_SELECT` | seleciona rumble clássico no lugar dos haptics VCM | 2 |
| 2 | `0x04` | **não existe no driver** | gatilho direito (canônica §2) | 0 |
| 3 | `0x08` | **não existe no driver** | gatilho esquerdo (canônica §2) | 0 |
| 4 | `0x10` | **não existe no driver** | `headphone_volume` (canônica §2, MÉDIA) | 0 |
| 5 | `0x20` | `DS_OUTPUT_VALID_FLAG0_SPEAKER_VOLUME_ENABLE` | `speaker_volume` | 2 |
| 6 | `0x40` | `DS_OUTPUT_VALID_FLAG0_MIC_VOLUME_ENABLE` | `mic_volume` | **1 — nunca usado** |
| 7 | `0x80` | `DS_OUTPUT_VALID_FLAG0_AUDIO_CONTROL_ENABLE` | `audio_control` | 2 |

### `valid_flag1` (offset 1 do `common`)

| bit | valor | nome no fonte | autoriza | usos |
|---|---|---|---|---|
| 0 | `0x01` | `..._MIC_MUTE_LED_CONTROL_ENABLE` | `mute_button_led` | 2 |
| 1 | `0x02` | `..._POWER_SAVE_CONTROL_ENABLE` | `power_save_control` | 3 |
| 2 | `0x04` | `..._LIGHTBAR_CONTROL_ENABLE` | `lightbar_red/green/blue` | 2 |
| 3 | `0x08` | `DS_OUTPUT_VALID_FLAG1_RELEASE_LEDS` | soltar os LEDs de volta ao aparelho | **1 — nunca usado** |
| 4 | `0x10` | `..._PLAYER_INDICATOR_CONTROL_ENABLE` | `player_leds` | 2 |
| 5 | `0x20` | **não existe no driver** | desconhecido | 0 |
| 6 | `0x40` | **não existe no driver** | `reduce_motor_power` (canônica §2) | 0 |
| 7 | `0x80` | `..._AUDIO_CONTROL2_ENABLE` | `audio_control2` | 2 |

### `valid_flag2` (offset 38 do `common`)

| bit | valor | nome no fonte | autoriza | usos |
|---|---|---|---|---|
| 0 | `0x01` | **não existe no driver** | `led_brightness` (canônica §2) | 0 |
| 1 | `0x02` | `..._LIGHTBAR_SETUP_CONTROL_ENABLE` | `lightbar_setup` | 2 |
| 2 | `0x04` | `..._COMPATIBLE_VIBRATION2` | rumble v2 | 2 |

### Os bits que o driver NUNCA liga

Somando as duas causas — não definido, ou definido e não usado:

| bit | recurso | por quê |
|---|---|---|
| `flag0` bit2, bit3 | **gatilhos adaptativos** | omissão declarada: a canônica §1.2 cita a `linux-input`, "have a dialog on how to expose these over time in a generic way" |
| `flag0` bit4 | volume do fone | não existe no driver |
| `flag0` bit6 | volume do microfone | **definido e nunca usado** |
| `flag1` bit3 | `RELEASE_LEDS` | **definido e nunca usado** |
| `flag1` bit5, bit6 | desconhecido / `reduce_motor_power` | não existem no driver |
| `flag2` bit0 | brilho dos player LEDs | não existe no driver |

O `flag0` bit6 e o `flag1` bit3 merecem destaque: são **nomes da Sony que o
próprio driver da Sony escreveu e não ligou**. O `RELEASE_LEDS` em particular é
a resposta de firmware para "devolva as luzes ao aparelho", que é a pergunta que
a chave `luz.lightbar.release_leds` do
[mapa de controles](../data/mapa-controles.csv) faz. **Existe o bit, existe o
nome, e o kernel nunca o usou** — nem a favor nem contra a hipótese
`LIGHTBAR-BT-CLAIM-01` registrada na canônica §5, que foi testada ao vivo por
outro caminho (`LIGHT_OUT`) e não teve efeito.

### Uma armadilha real no `output_worker`

**GRAU: FONTE DESTA MÁQUINA.** O `dualsense_output_worker` (`:1448-1558`) monta
**um** report com todas as atualizações pendentes, e quase todas usam `|=`. Duas
não usam:

- `hid-playstation.c:1491` — `common->valid_flag0 = DS_OUTPUT_VALID_FLAG0_AUDIO_CONTROL_ENABLE;`
- `hid-playstation.c:1520` — `common->valid_flag1 = DS_OUTPUT_VALID_FLAG1_AUDIO_CONTROL2_ENABLE;`

São **atribuições**, não OR. As duas estão dentro do caminho de mudança de
estado do jack (`:1489-1533`). Se um evento de jack coincidir com um rumble
pendente, a linha 1491 **apaga** os bits de vibração que as linhas 1460-1464
acabaram de ligar; se coincidir com uma atualização de lightbar ou de player
LEDs, a linha 1520 apaga os bits das linhas 1471 e 1480. Os campos de dado
continuam preenchidos — e o driver já limpou os `update_*`, então, **se o bit
fizer falta, a atualização é perdida e não adiada**.

**O "se" acima é novo, e ele encolhe metade desta armadilha.** Até 11/08/2026
esta página afirmava, sem ressalva, que *"sem o bit de validação o aparelho
ignora os campos"*. **Para os dois bytes de motor isso é falso, e está medido no
aparelho** — ver a
[canônica do DualSense](dualsense-referencia-canonica.md), §2, *"Os BITS de
vibração não são porteiro dos BYTES de motor"* (ensaio
`keepalive-premissa-troca-de-lado`, com o olho dela). Logo:

| bloco apagado pela atribuição | o que se espera hoje |
|---|---|
| **vibração** (`common[2]`, `common[3]`) | **não se perde** — o firmware obedeceu aos bytes com os bits desligados. GRAU: MEDIDO AQUI para o mecanismo, **INFERIDO** para este caminho específico do jack, que ninguém provocou |
| **lightbar e player LEDs** | **sem medição.** Ninguém repetiu o ensaio de troca-de-lado para cor nem para as cinco lâmpadas; enquanto isso, a leitura conservadora (o bit faz falta) é a que fica |

Isso só ocorre **sob USB** (o caminho de jack é USB-only, `:1648`) e só na
transição de plugar ou desplugar fone. É estreito, e é real. Não medimos.
**GRAU da consequência: BAIXA** — lida no código, nunca provocada no aparelho.

**O ensaio que resolve:** plugar um fone no controle no cabo enquanto um rumble
está em curso, e ver se o rumble morre no ato. Variável única, custo de um
minuto — e agora ele tem uma previsão a derrubar: **pela medição de 11/08, o
rumble NÃO deve morrer**, e o bloco a vigiar é o da cor.

## 3. A rota sysfs — e a pergunta que decide

### Que nós o driver cria

**GRAU: FONTE DESTA MÁQUINA, confirmado por MEDIDO AQUI.**

Dois grupos, mais o de bateria:

**1. Atributos no dispositivo HID** (`hid-playstation.c:1120-1147`): dois nós
somente-leitura, `DEVICE_ATTR_RO`, registrados como grupo `ps_device_attrs`:

- `firmware_version` — imprime `ps_dev->fw_version` como `0x%08x`
- `hardware_version` — imprime `ps_dev->hw_version` como `0x%08x`

Medido nesta máquina em 11/08/2026:

```
/sys/bus/hid/drivers/playstation/0003:054C:0CE6.0009/firmware_version -> 0x0110002a
/sys/bus/hid/drivers/playstation/0003:054C:0CE6.0009/hardware_version -> 0x00000711
/sys/bus/hid/drivers/playstation/0005:054C:0CE6.0006/firmware_version -> 0x0110002a
/sys/bus/hid/drivers/playstation/0005:054C:0CE6.0006/hardware_version -> 0x00000710
```

Dois controles distintos (`hw_version` diferente), mesmo firmware. Os valores
vêm do feature report `0x20` lido **uma vez na probe** e nunca mais — ver seção
5.

**2. LEDs em `/sys/class/leds`** (`:961-994` para os player LEDs, `:998-1035`
para a barra). O nome é montado em `:962-970` como
`<input_dev_name>:<cor>:<função>`, onde `input_dev_name` é o nome do nó de
gamepad (`:1941`). Por controle, **seis nós**:

| nó | classe | `max_brightness` | escreve o quê |
|---|---|---|---|
| `inputN:white:player-1` .. `player-5` | `led_classdev` | **1** | um bit de `player_leds` (`common[43]`) |
| `inputN:rgb:indicator` | `led_classdev_mc` | **255** | `lightbar_red/green/blue` (`common[44..46]`) |

O nó RGB é multicolor: `multi_index` devolve `red green blue` e
`multi_intensity` recebe os três componentes, que o
`dualsense_lightbar_set_brightness` (`:1332-1346`) passa por
`led_mc_calc_color_components` antes de mandar ao aparelho.

Medido nesta máquina em 11/08/2026, os seis nós de cada um dos dois controles:

```
0003:054C:0CE6.0009 (cabo)  input111:white:player-1..5 = 0 1 0 0 0   max=1
                            input111:rgb:indicator     bri=255 max=255 multi_intensity="255 0 0"
0005:054C:0CE6.0006 (rádio) input30:white:player-1..5  = 0 0 0 1 0   max=1
                            input30:rgb:indicator      bri=255 max=255 multi_intensity="0 0 255"
```

**3. Bateria:** `ps_device_register_battery` cria o nó `power_supply` padrão,
alimentado por `status[0]` a cada report de entrada. Nada de específico a
documentar.

### A pergunta que decide: o driver relê o aparelho?

**Não. Ele devolve o que foi escrito por ele mesmo. GRAU: FONTE DESTA MÁQUINA.**

A prova está em três linhas. O `brightness_get` dos player LEDs é
`dualsense_player_led_get_brightness` (`hid-playstation.c:1348-1354`), e o corpo
inteiro é:

```c
return !!(ds->player_leds_state & BIT(led - ds->player_leds));
```

`hid-playstation.c:1353`. O `ds->player_leds_state` é um `u8` na struct
`dualsense` (`:277`). **Não há leitura de report, não há `hid_hw_raw_request`,
não há ida ao aparelho.** É uma variável em RAM do kernel.

Quem escreve nessa variável é apenas:

1. `dualsense_player_led_set_brightness` (`:1356-1372`) — a escrita pelo próprio
   sysfs, que liga ou desliga **um bit** e agenda o `output_worker`;
2. `dualsense_set_player_leds` (`:1828-1849`) — a atribuição do padrão de
   jogador, **uma única vez na probe** (`:2000`).

Nada mais. E o report de **entrada** não carrega estado de LED em campo nenhum
que o driver leia — o `dualsense_parse_report` (`:1562`) toca sticks, botões,
mudo do mic, jack, IMU, touchpad e bateria, e nunca `player_leds_state`.

**Portanto a medição desta casa está CONFIRMADA pelo código:** se alguém
escrever o report de saída por HID cru — via `hidraw`, contornando o driver —,
o aparelho muda e `player_leds_state` **não muda**. O nó sysfs passa a afirmar
um valor que o aparelho não está mostrando, e nada no driver jamais o corrige.
O mesmo vale para a barra: `ps_lightbar_register` (`:998-1035`) sequer instala
um `brightness_get`, e crava `led_cdev->brightness = 255` em `:1023`.

A leitura ao vivo acima ilustra isso de outro ângulo: nenhum dos dois controles
mostra um padrão que a tabela do driver saiba produzir. O do cabo tem só o
`player-2` aceso (bitmask `0b00010` = 2) e o do rádio só o `player-4` (`0b01000`
= 8) — e os únicos valores que `player_ids[]` produz são 4, 10, 21, 27 e 31.
São escritas de userspace, bit a bit, pelos nós individuais. O sysfs é um
**espelho da última escrita que passou por ele**, não um retrato do aparelho.

> Isto é a mesma armadilha que a canônica dos externos já registra em outro
> aparelho — "valor gravado no `sysfs` NÃO é prova de que alguma luz acendeu"
> ([externos](externos-referencia-canonica.md)). Aqui ela fica provada pelo
> fonte, para o DualSense, com a linha exata.

## 4. A numeração de player LEDs — a contradição, resolvida

**GRAU: FONTE DESTA MÁQUINA.** A tabela está em
`hid-playstation.c:1836-1842`, dentro de `dualsense_set_player_leds`:

```c
static const int player_ids[5] = {
        BIT(2),
        BIT(3) | BIT(1),
        BIT(4) | BIT(2) | BIT(0),
        BIT(4) | BIT(3) | BIT(1) | BIT(0),
        BIT(4) | BIT(3) | BIT(2) | BIT(1) | BIT(0)
};
```

O comentário logo acima (`:1830-1835`) declara a intenção: *"Behavior on the
PlayStation 5 console is to center the player id across the LEDs, so e.g.
player 1 would be `--x--` with x being 'on'."*

Traduzindo, com `BIT(0)` na primeira lâmpada:

| jogador | índice | expressão | bitmask | figura |
|---|---|---|---|---|
| P1 | `player_ids[0]` | `BIT(2)` | `0b00100` = 4 | `--x--` |
| P2 | `player_ids[1]` | `BIT(3) \| BIT(1)` | `0b01010` = 10 | `-x-x-` |
| P3 | `player_ids[2]` | `BIT(4) \| BIT(2) \| BIT(0)` | `0b10101` = 21 | `x-x-x` |
| **P4** | `player_ids[3]` | `BIT(4) \| BIT(3) \| BIT(1) \| BIT(0)` | `0b11011` = 27 | **`xx-xx`** |
| P5 | `player_ids[4]` | todos | `0b11111` = 31 | `xxxxx` |

**A orientação não importa.** As cinco figuras são palíndromos, então ler
`BIT(0)` da esquerda ou da direita dá o mesmo desenho. Não há como errar o P4
por engano de lado.

### O veredito sobre a divergência aberta

A canônica §5 registra, com nota datada de 11/08/2026, uma contradição em
aberto sobre o P4 — a página dizia `x-xx-`, o código desta árvore diz `xx-xx`,
e nenhum dos dois lados tinha sido medido.

**O fonte do driver decide a favor do código desta árvore.**

| | P1 | P2 | P3 | **P4** | P5 |
|---|---|---|---|---|---|
| canônica §5 (antes) | `--x--` | `-x-x-` | `x-x-x` | **`x-xx-`** | `xxxxx` |
| `core/led_control.py` | `--x--` | `-x-x-` | `x-x-x` | **`xx-xx`** | `xxxxx` |
| **driver, `:1836-1842`** | `--x--` | `-x-x-` | `x-x-x` | **`xx-xx`** | `xxxxx` |

O `x-xx-` da canônica é, byte a byte, o `_PLAYER_LED_OVERFLOW` de
`src/hefesto_dualsense4unix/core/led_control.py` — o padrão de "slot fora da
tabela". A escolha desta casa de usá-lo como marca de overflow **continua
segura**, porque ele não colide com nenhum dos cinco do driver.

**Grau: ALTA para o driver (código do funcionário da Sony, comentário
explicando a intenção do console), e a linha da canônica deve ganhar sua nota
datada.** O que isto ainda **não** prova é o comportamento do console PS5 —
prova o que o kernel Linux manda ao aparelho. Se algum dia alguém quiser a
verdade do console, isso continua sendo uma observação de aparelho, e continua
sendo do olho dela.

### Quem escolhe o número, e por que ele não é o número do jogo

`ps_device_set_player_id` (`:673-682`) chama `ida_alloc` sobre um **IDA global
do módulo** (`ps_player_id_allocator`, `:87`), compartilhado por **todos** os
dispositivos PlayStation. O primeiro a registrar recebe 0.

Três consequências, todas **FONTE DESTA MÁQUINA**:

1. **É base zero**, e o índice entra direto em `player_ids[]` (`:1844`). O
   `player_id` 0 acende `--x--`.
2. **É `% ARRAY_SIZE(player_ids)`** (`:1844`): o sexto controle volta a `--x--`.
   O driver não tem noção de overflow — a tabela de 8 mais overflow em
   `core/led_control.py` é invenção desta casa, e cobre um buraco real.
3. **Conta qualquer coisa que o driver aceite**, inclusive o gamepad virtual
   deste projeto. É a ordem de registro no kernel, não a ordem de entrada no
   jogo. A memória desta casa já registra esse tropeço, e ele fica aqui com
   linha de código.

O padrão é enviado uma única vez, em `:2000`, logo após `ps_device_set_player_id`
em `:1993`. Depois disso o driver **nunca mais** mexe nos player LEDs por conta
própria.

## 5. Feature reports: calibração, firmware, pareamento

**GRAU: FONTE DESTA MÁQUINA** para tudo nesta seção.

Os três são lidos **exclusivamente na probe** (`:1897`, `:1904`, `:1929`),
nesta ordem: pareamento, firmware, calibração. Nenhum é relido depois. Por
Bluetooth os três passam por conferência de CRC-32 com semente `0xA3`
(`:874-880`) — os **4 últimos bytes são CRC, não dado**, e a canônica §7 já
alerta que tratá-los como calibração corrompe a unidade.

### `0x05` — calibração da IMU, 41 bytes

`dualsense_get_calibration_data`, `:1149-1272`. O parse está em `:1176-1192`,
todos `get_unaligned_le16` sobre `buf`, e todos com sinal (`short`). **Este
layout é a lacuna que a canônica §5 deixou aberta** — ela documenta o tamanho e
a imutabilidade, não os campos.

| offset | variável no fonte |
|---|---|
| 0 | (report ID) |
| 1-2 | `gyro_pitch_bias` |
| 3-4 | `gyro_yaw_bias` |
| 5-6 | `gyro_roll_bias` |
| 7-8 | `gyro_pitch_plus` |
| 9-10 | `gyro_pitch_minus` |
| 11-12 | `gyro_yaw_plus` |
| 13-14 | `gyro_yaw_minus` |
| 15-16 | `gyro_roll_plus` |
| 17-18 | `gyro_roll_minus` |
| 19-20 | `gyro_speed_plus` |
| 21-22 | `gyro_speed_minus` |
| 23-24 | `acc_x_plus` |
| 25-26 | `acc_x_minus` |
| 27-28 | `acc_y_plus` |
| 29-30 | `acc_y_minus` |
| 31-32 | `acc_z_plus` |
| 33-34 | `acc_z_minus` |
| 35-36 | não lido |
| 37-40 | CRC-32 por Bluetooth; não lido no cabo |

As fórmulas (`:1196-1250`), normalizando para as escalas de `:226-229`
(`DS_ACC_RES_PER_G` 8192, `DS_GYRO_RES_PER_DEG_S` 1024 — a canônica §5 já as
declara com grau ALTA):

- **Giroscópio**, por eixo: `bias = 0`;
  `sens_numer = (gyro_speed_plus + gyro_speed_minus) * 1024`;
  `sens_denom = |eixo_plus - eixo_bias| + |eixo_minus - eixo_bias|`.
  Note que o `bias` de calibração **é descartado** no cálculo final: ele entra
  só no denominador, e o valor bruto não é deslocado.
- **Acelerômetro**, por eixo: `range_2g = plus - minus`;
  `bias = plus - range_2g / 2`; `sens_numer = 2 * 8192`;
  `sens_denom = range_2g`.

Mapeamento para evdev: giro em `ABS_RX`/`ABS_RY`/`ABS_RZ` (pitch, yaw, roll) e
acelerômetro em `ABS_X`/`ABS_Y`/`ABS_Z`, num nó de entrada separado chamado
`Motion Sensors`.

**A rede de segurança que importa para o vpad deste projeto** (`:1219-1232` e
`:1252-1265`): se qualquer `sens_denom` sair zero, o driver **não falha** — ele
emite `hid_warn` ("Invalid gyro calibration data for axis...") e substitui por
`sens_numer = DS_GYRO_RANGE`, `sens_denom = S16_MAX`, isto é, a escala nominal
sem calibração. O comentário do fonte diz para quem isso existe: *"to prevent
crashes during report handling of virtual, clone or broken devices not
implementing calibration data properly"*. Um DualSense virtual que devolva 41
bytes zerados **é aceito**, com aviso no `dmesg` e sensor sem calibração.

### `0x20` — firmware info, 64 bytes

`dualsense_get_firmware_info`, `:1276-1307`. O driver lê **três** campos dos 64:

| offset | tamanho | destino | como aparece |
|---|---|---|---|
| 24-27 | `__le32` | `ps_dev->hw_version` | sysfs `hardware_version` |
| 28-31 | `__le32` | `ps_dev->fw_version` | sysfs `firmware_version` |
| 44-45 | `__le16` | `ds->update_version` | **não aparece em sysfs** |

Os outros 56 bytes não são lidos por este driver. **A canônica §7 diz "versão
nos bytes 44-45"** — está certa, e agora com nome: é o `update_version`, que
**não** é a versão de firmware.

O `update_version` é o campo mais interessante dos três, porque é o único que
muda **comportamento**. O comentário de `:1295-1301` explica: é uma versão de
*capacidade*, distinta da de firmware, porque existem variações de placa dentro
da mesma carcaça. O uso está em `:1918-1923`:

- `USB_DEVICE_ID_SONY_PS5_CONTROLLER` (`0x0CE6`, DualSense comum):
  `use_vibration_v2 = update_version >= DS_FEATURE_VERSION(2, 21)`;
- `USB_DEVICE_ID_SONY_PS5_CONTROLLER_2` (`0x0DF2`, DualSense Edge):
  `use_vibration_v2 = true`, incondicional.

`DS_FEATURE_VERSION(major, minor)` (`:183-186`) empacota maior no byte alto e
menor no baixo, então 2.21 é `0x0215`.

E aqui está o que decide o bit de rumble: `use_vibration_v2` escolhe entre
`valid_flag2` bit2 (v2) e `valid_flag0` bit0 (v1), em `:1461-1465`. **O bit
certo de vibração depende de um campo de feature report que só é lido na
probe.** Um gamepad virtual que se declare Edge (PID `0x0DF2`) recebe `v2`
incondicionalmente, sem que o `0x20` precise dizer coisa alguma.

### `0x09` — pairing info, 20 bytes

`dualsense_get_mac_address`, `:1309-1330`. O driver lê **6 bytes** dos 20:

| offset | destino |
|---|---|
| 1-6 | `ps_dev->mac_address` (ordem little endian, conforme `:110`) |

Confirma a canônica §7 ("MAC nos bytes 1-6"). O endereço vira `hdev->uniq` com
`%pMR` em `:1902` — que é o formato **invertido**, e é por isso que o
`mac_address` é guardado em little endian.

Este é o **único** lugar de onde o driver tira o endereço no caminho do
DualSense, e é por isso que uma falha aqui custa o controle inteiro: é a
primeira chamada da `dualsense_create` (`:1897`) e o `return` é imediato. O
mesmo problema no DualShock4 é a razão de existir do patch `0002` deste DKMS.

### O retry da probe — o que o fork acrescenta

`ps_get_report`, `:939-959`, com um comentário de 40 linhas (`:885-938`) que
documenta a medição que o justifica. O resumo, já registrado em
`assets/dkms/hid-playstation/README.md` e reproduzido aqui só pelo que muda o
comportamento:

- `feature_retries` (padrão **0** = uma tentativa, comportamento do vanilla),
  teto de 10;
- espaçamento por transporte: Bluetooth começa em `2 x 3000 ms` e dobra até o
  teto de `4 x 3000 ms`, porque os 3 s são o `REPORT_REQ_TIMEOUT` do BlueZ que
  uma tentativa falha já gastou; USB fica em 100 ms fixos, porque ali não há
  BlueZ no caminho;
- **todas** as falhas que `__ps_get_report` detecta são repetidas — erro de
  transporte, transferência curta, report ID errado, CRC ruim —, porque
  qualquer uma delas descreve uma transferência que não chegou inteira.

Ler feature report é operação pura, sem efeito colateral; repetir é seguro.

## 6. As taxas de relatório, medidas

**GRAU: MEDIDO AQUI, 11/08/2026.** A canônica §5, na nota datada de 11/08,
registra que a taxa **nunca havia sido medida em transporte nenhum**. Esta
seção mede.

### A régua, declarada

Duas réguas independentes, sobre o nó evdev `Motion Sensors` de cada controle
(que emite `MSC_TIMESTAMP` a **cada** report, e por isso não sofre a filtragem
de valores repetidos que afetaria o nó de gamepad):

1. **Relógio do host:** contagem de `SYN_REPORT` dividida pelo tempo de parede.
2. **Relógio do controle:** média das diferenças de `MSC_TIMESTAMP`, que o
   driver deriva do `sensor_timestamp` do próprio aparelho (`:1689-1701`,
   unidade 0,33 us convertida para us). Esta régua **não depende do agendamento
   do host**.

Leitura de evdev é passiva: não abre `hidraw`, não escreve nada, não disputa
com o daemon. É exatamente o cuidado que a armadilha 3 do
[COMO-OLHAR-A-TELA.md](../process/COMO-OLHAR-A-TELA.md) manda ter.

### O que o driver impõe: nada

**GRAU: FONTE DESTA MÁQUINA.** Para o **DualShock4** o driver negocia a taxa:
existem `bt_poll_interval` e `update_bt_poll_interval` na struct (`:483-484`),
um `dualshock4_set_bt_poll_interval` (`:2873-2877`), o campo `hw_control` no
report de saída (`:2566-2570`) e um padrão de 4 ms aplicado na probe (`:3022`).

Para o **DualSense não existe nada disso**. Nenhum campo, nenhuma função,
nenhum default. O driver **não pede taxa nenhuma** ao DualSense, em transporte
nenhum. O que chega é o que o aparelho e o transporte decidem.

### Cabo: 250 Hz, e o número vem do descritor

O controle no cabo é USB High Speed (`speed=480`). Na interface 3 (HID), os
dois endpoints de interrupção têm `bInterval = 6`:

```
bInterfaceNumber 3 / bInterfaceClass 3 Human Interface Device
  bEndpointAddress 0x84  EP 4 IN   Interrupt  bInterval 6
  bEndpointAddress 0x03  EP 3 OUT  Interrupt  bInterval 6
```

Em High Speed o intervalo de serviço é `2^(bInterval-1)` microquadros de 125 us,
logo `2^5 x 125 us = 4000 us` = **250 Hz**. Medido:

| régua | resultado |
|---|---|
| relógio do host | **250,0 Hz** (4,00 ms), 2501 reports em 10,000 s |
| relógio do controle | **250,0 Hz** (delta médio 4000,3 us) |

As duas réguas concordam, e concordam com o descritor. **Os 250 Hz do cabo
estão fechados**, e não como afirmação do SDL: como o intervalo de serviço que
o endpoint declara nesta máquina.

### Rádio: variável, em rajadas, e longe de 1000 Hz

Cinco janelas de 8 a 10 s, no mesmo controle, sem tocar nele:

| janela | régua do host | régua do controle (média) | mediana | p05 | p95 |
|---|---|---|---|---|---|
| 1 (10 s) | 363,3 Hz | — | — | — | — |
| 2 (10 s) | — | 239,9 Hz | 2510 us | 1255 us | 13 179 us |
| 3 (8 s) | 334,1 Hz | 392,4 Hz | 1883 us | 1255 us | 8158 us |
| 4 (8 s) | 55,4 Hz | 38,3 Hz | 5648 us | 1255 us | 187 637 us |
| 5 (8 s) | 69,7 Hz | 48,5 Hz | 6275 us | 1882 us | 97 583 us |

Três leituras honestas:

1. **A taxa por rádio não é estável.** Ela caiu de ~334 Hz para ~55 Hz entre
   duas janelas consecutivas de 8 s, no mesmo controle, sem nenhuma mudança que
   eu tenha feito.
2. **O fluxo é em rajadas.** O p05 do intervalo é teimosamente **1255 us**
   (~797 Hz instantâneos) enquanto o p95 chega a 187 ms. Dentro da rajada o
   controle é rápido; o que varia é o silêncio entre rajadas.
3. **Os 1000 Hz que o SDL declara para Bluetooth não aparecem em nenhuma
   janela**, nem como média nem como mediana. O valor sustentado mais alto
   medido foi ~392 Hz.

Isto **corrobora** a medição independente que a
[paridade Bluetooth versus cabo](paridade-bluetooth-versus-cabo.md) já
registrava por outra régua (contagem de bytes: "~300 Hz, 1.402.128 bytes em
60 s"). Duas réguas diferentes, em datas diferentes, na mesma faixa.

**O que NÃO foi controlado, e por isso não se conclui:** o estado físico do
controle. Ele estava parado sobre a mesa, e o colapso das janelas 4 e 5 é
**consistente** com economia de energia do enlace Bluetooth (sniff mode) num
controle ocioso — mas isso é **hipótese, GRAU BAIXA**, não medição. Não testei
com o controle em movimento contínuo.

**O ensaio que resolve:** repetir as cinco janelas com o controle sendo movido
sem parar, e comparar. Se a taxa se sustentar acima de 300 Hz sob movimento e
só colapsar em repouso, a hipótese de economia de energia fica de pé. Variável
única, custo de dois minutos.

**O que isto faz com o `GYRO-EDGE-RATE-01`** (canônica §5): a premissa da
sprint era que o vpad se declara Edge e entrega ~250 Hz, e que um jogo poderia
integrar por uma taxa declarada 4x errada. O cabo agora está medido e é
exatamente 250 Hz. O rádio está medido e **não** é 1000 Hz. A pergunta que
sobra deixou de ser "qual é a taxa" e passou a ser "o que o SDL declara ao
jogo", que é medição do lado do SDL, com a régua do SDL3 da Steam — e essa
continua por fazer.

## 7. O que o driver NÃO faz

Consolidado, porque é aqui que este projeto tem de agir sozinho. Tudo
**FONTE DESTA MÁQUINA**.

### Campos que o driver declara e nunca escreve

| campo | offset no `common` | quem tem de escrever |
|---|---|---|
| `headphone_volume` | 4 | este projeto |
| `mic_volume` | 6 | este projeto |
| `reserved2[27]` — **os gatilhos adaptativos** | 10-36 | este projeto |
| `reserved3[2]` | 39-40 | ninguém sabe o que são |
| `led_brightness` | 42 | este projeto |
| `lightbar_setup` | 41 | o driver só o escreve **uma vez**, na probe |

### Recursos ausentes por decisão

- **Gatilhos adaptativos.** Sem campo, sem bit de validação (`flag0` bit2 e
  bit3 não existem no fonte), sem sysfs. A canônica §1.2 já cita a justificativa
  na `linux-input`. Os 27 bytes existem no report e o driver os zera.
- **Haptics VCM.** Pior que ausência: o driver **liga ativamente**
  `HAPTICS_SELECT` (`:1460`) em todo rumble, que é o bit que seleciona a
  vibração clássica **no lugar** dos haptics. Ver canônica §3 e §8.
- **Áudio por Bluetooth.** Duas exclusões explícitas: o nó de jack só é criado
  sob USB (`:1954-1962`, "Bluetooth audio is currently not supported") e o parse
  de estado de jack também (`:1648`).
- **Volume do microfone e do fone.** Os campos existem, os comentários do fonte
  dão as faixas (`0x0-0x7f` e `0x0-0x40`), e o `flag0` bit6 existe com nome —
  e nunca é ligado.
- **Brilho dos player LEDs.** O `led_brightness` existe no report; o bit que o
  autoriza (`flag2` bit0) **não existe no driver**; e o `max_brightness` dos
  cinco nós sysfs é **1** — ou seja, pela rota sysfs os player LEDs são
  binários, sem os 3 níveis que a canônica §5 documenta.
- **Devolver os LEDs ao aparelho.** `RELEASE_LEDS` definido, nunca usado.
- **Piscar player LED.** `ps_led_info` tem um campo `blink_set` (`:132`), e o
  `player_leds_info` do DualSense (`:1858-1869`) passa **`NULL`** para ele nos
  cinco. O DualShock4 usa `blink_set`; o DualSense não. Nada de `delay_on`/
  `delay_off` úteis no sysfs.
- **Reler qualquer coisa.** Os três feature reports são lidos uma vez na probe.
  Nenhum estado de LED é relido nunca. Ver seção 3.

### O que o driver faz que atrapalha, se você não contar com ele

1. **Ele escreve na barra na probe, sozinho.** `dualsense_reset_leds`
   (`:1791-1813`) manda um report com `valid_flag2` = setup e
   `lightbar_setup` = `LIGHT_OUT` (fade out), e logo depois `:1983` chama
   `dualsense_set_lightbar(ds, 0, 0, 128)` — **azul**. O comentário de
   `:1798-1804` explica: por Bluetooth o aparelho roda uma animação na barra ao
   ligar e mantém uma cor, e o driver precisa reconfigurar antes de poder
   programar. Todo controle que sobe passa por azul.
2. **Ele numera e acende os player LEDs na probe** (`:2000`), pela ordem de
   registro no kernel, contando qualquer dispositivo PlayStation — inclusive um
   gamepad virtual.
3. **Ele alterna o mudo do microfone sozinho**, na borda de subida do botão
   (`:1631-1641`), e programa o aparelho.
4. **Ele marca a versão do HID:** `hdev->version |= HID_PLAYSTATION_VERSION_PATCH`
   (`0x8000`, `:89` e `:1879`), justamente para que o userspace consiga
   distinguir um controle sob `hid-playstation` de um sob `hid-generic`. É um
   discriminador barato e confiável, e não estava documentado nesta árvore.

### Os parâmetros de módulo desta máquina

Três, todos `0644` (graváveis em `/sys/module/hid_playstation/parameters/`),
todos lidos **na probe** — mudar exige replug, nunca `rmmod`, que derrubaria
todos os controles conectados:

| parâmetro | padrão | efeito |
|---|---|---|
| `feature_retries` | 0 | tentativas extras de feature report na probe |
| `ds4_short_pairing_info` | N | aceita pairing info curto do clone DualShock4 |
| `ds4_synthetic_mac` | N | fabrica endereço local quando nenhum pode ser lido |

Os dois últimos **não tocam o caminho do DualSense**.

## 8. Fontes

**Fonte desta máquina (a que decide):**

- `assets/dkms/hid-playstation/hid-playstation.c` — 3171 linhas, idêntico byte a
  byte a `/usr/src/hefesto-hid-playstation-1.0.0/hid-playstation.c`, que é o
  fonte do módulo carregado agora.
- `assets/dkms/hid-playstation/README.md` e os dois `patch/*.patch` — proveniência
  e escopo dos patches.

**Mainline:** vanilla v7.0.11 de `pop-os/linux`, no commit registrado em
`assets/dkms/hid-playstation/patch/BASELINE`. Conforme a seção de proveniência,
todo o caminho do DualSense descrito aqui é vanilla — nenhum patch o toca.

**Medições desta máquina, 11/08/2026:** `dkms status`, `modinfo`, `lsusb -v`,
leitura dos nós de `/sys/class/leds` e `/sys/bus/hid/drivers/playstation/`, e
contagem passiva de `SYN_REPORT` e `MSC_TIMESTAMP` nos nós evdev de
`Motion Sensors` dos dois controles.

**Páginas desta árvore que esta aqui complementa e não substitui:**

- [dualsense-referencia-canonica.md](dualsense-referencia-canonica.md) — o que o
  aparelho entende. Precede esta página em tudo que é firmware.
- [paridade-bluetooth-versus-cabo.md](paridade-bluetooth-versus-cabo.md) — o que
  funciona em cada transporte.
- [externos-referencia-canonica.md](externos-referencia-canonica.md) — a mesma
  leitura de driver para Pro e 8BitDo, e a armadilha do sysfs vista lá primeiro.
- [trigger-modes.md](trigger-modes.md) — os modos de gatilho, cuja fonte
  canônica hoje é a §4 da referência canônica.

## O que esta página muda em outras

Três linhas de outras páginas ficam desatualizadas a partir daqui. Nenhuma foi
apagada; cada uma precisa da sua nota datada.

1. **Canônica §5, o P4.** A contradição em aberto está **resolvida a favor do
   código**: o driver diz `xx-xx`. A linha `x-xx-` da canônica descreve o
   `_PLAYER_LED_OVERFLOW`, não o jogador 4.
2. **Canônica §5, as taxas.** Deixaram de ser "não medido". Cabo: 250 Hz, duas
   réguas mais o descritor. Rádio: variável entre ~55 e ~392 Hz, em rajadas,
   nunca 1000 Hz. O que sobra por medir é o que o SDL **declara**, não o que o
   aparelho **entrega**.
3. **Canônica §1.2, o limite honesto.** "O fonte do `hid-playstation` não foi
   relido nesta passagem" deixou de valer: foi relido, é o desta máquina, e as
   citações têm número de linha.
