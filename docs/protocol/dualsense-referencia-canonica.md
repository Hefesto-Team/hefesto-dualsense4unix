# DualSense — a referência canônica do protocolo

**A fonte única de verdade deste projeto sobre o que o controle entende.**

- **Levantado em:** 01/08/2026, por dois agentes de pesquisa, e conferido contra
  o código desta árvore
- **Por que este arquivo existe:** ela pediu, literal — *"pode documentar a
  pesquisa dos agentes e salvar elas permanentemente no projeto como
  documentação física? E atualizar as demais docs principais pra nunca mais
  termos essa lacuna de conhecimento no repo?"*
- **Regra de uso:** quando este documento e outro discordarem, **este vence** —
  mas só nas linhas marcadas ALTA. Ver "Como ler os graus de confiança"

## Como ler os graus de confiança

Toda linha técnica aqui carrega um grau, e ele não é decorativo. Esta casa já
tomou decisão errada por confundir "documentação de comunidade" com "fato".

| grau | significa | exemplo |
|---|---|---|
| **ALTA** | está no kernel mainline, ou na enum da própria Sony, ou em ≥2 engenharias reversas independentes que concordam | o mapa dos 47 bytes do report de saída |
| **MÉDIA** | uma fonte de comunidade respeitada, sem contradição conhecida | o byte de volume do fone |
| **BAIXA** | inferência ou fonte única | os modos de gatilho "não oficiais" |
| **MEDIDO AQUI** | conferido nesta máquina, nesta árvore | a curva do volume do alto-falante |

E a regra que a origina: **medir contra a ferramenta errada produz um resultado
convincente e falso.** Em 01/08 mediu-se o gamepad virtual contra a `libSDL2`
do Ubuntu e concluiu-se que ele não entregava nada; a biblioteca que os jogos
usam entrega tudo. Todo instrumento tem de declarar contra o que mediu.

---

## 1. De onde vem a documentação da Sony

**O SDK do PS5 (`libpad` / `ScePad`) é fechado, sob NDA.** O acesso passa por
PlayStation Partners → GDPA → DevNet. Nada dele é público, e não adianta
procurar.

**Duas partes escaparam por vias legítimas, e são o alicerce deste documento:**

### 1.1. O header da Sony dentro do Steamworks SDK — ALTA

A Valve redistribui, no Steamworks SDK ≥ 1.55, o arquivo
`public/steam/isteamdualsense.h`, que traz o header da Sony **verbatim**, com o
cabeçalho `Copyright (C) 2019 Sony Interactive Entertainment Inc.`

Ele define a enum oficial dos modos de gatilho e as faixas de cada parâmetro:

```c
typedef enum ScePadTriggerEffectMode {
  SCE_PAD_TRIGGER_EFFECT_MODE_OFF,
  SCE_PAD_TRIGGER_EFFECT_MODE_FEEDBACK,
  SCE_PAD_TRIGGER_EFFECT_MODE_WEAPON,
  SCE_PAD_TRIGGER_EFFECT_MODE_VIBRATION,
  SCE_PAD_TRIGGER_EFFECT_MODE_MULTIPLE_POSITION_FEEDBACK,
  SCE_PAD_TRIGGER_EFFECT_MODE_SLOPE_FEEDBACK,
  SCE_PAD_TRIGGER_EFFECT_MODE_MULTIPLE_POSITION_VIBRATION,
} ScePadTriggerEffectMode;

FeedbackParam { position(0~9); strength(0~8); }
WeaponParam   { startPosition(2~7); endPosition; strength(0~8); }
VibrationParam{ position(0~9); amplitude(0~8); frequency(0~255 Hz); }
MultiplePositionFeedbackParam  { strength[10] (0~8); }
SlopeFeedbackParam { startPosition; endPosition; startStrength(1~8); endStrength(1~8); }
MultiplePositionVibrationParam { frequency(0~255); amplitude[10] (0~8); }
```

ATENÇÃO: **Ressalva jurídica, e ela é séria:** o texto é da Sony e está marcado
*"SIE CONFIDENTIAL"*. Use como referência de **semântica e faixas**, cite a
URL — **nunca copie o header para dentro deste repositório.**

Fonte: `https://github.com/rlabrecque/SteamworksSDK/blob/master/public/steam/isteamdualsense.h`

### 1.2. O driver `hid-playstation` — escrito por um funcionário da Sony — ALTA

O driver do kernel Linux foi escrito por **Roderick Colenbrander, da Sony
Interactive Entertainment**. É a fonte mais próxima de oficial em aberto, e ele
explicou as decisões por escrito na lista `linux-input`.

**O que ele implementa:** botões e eixos, bateria, IMU com calibração, touchpad,
lightbar, player LEDs, rumble clássico, mute do microfone, CRC-32 do Bluetooth,
firmware info, pareamento.

**O que ele deixou de fora, DE PROPÓSITO** — e esta frase é a razão de este
projeto poder existir:

> *"the DualSense features a haptics system based on voicecoil motors, which
> requires PCM data (or special HID packets using Bluetooth). There is no
> appropriate API yet in the Linux kernel to expose these."*

E sobre os gatilhos adaptativos: ficaram de fora para *"have a dialog on how to
expose these over time in a generic way"*.

**Consequência prática:** o espaço de usuário é o dono desses bytes **por
omissão declarada do driver**, não por acidente. É por isso que eles chegam
intactos ao `hidraw`.

Fontes: `https://yhbt.net/lore/all/20210117230956.173031-3-roderick@gaikai.com/T/`
· `https://github.com/torvalds/linux/blob/master/drivers/hid/hid-playstation.c`

### 1.3. O que a Sony publicou para PC — nada de técnico

O app **PlayStation Accessories** (Windows) atualiza firmware e customiza o
Edge. **Não há SDK, API nem nota técnica.** Tudo que funciona em PC é o jogo
falando HID cru.

---

## 2. O report de saída `0x02` — os 47 bytes do `common`

**Grau: ALTA** (kernel mainline 6.18 + `dualsensectl`, idênticos).

| off | campo | faixa | validado por |
|---|---|---|---|
| 0, 1 | `valid_flag0`, `valid_flag1` | — | — |
| 2, 3 | `motor_right`, `motor_left` | 0-255 | flag0 bit0/bit1 |
| 4 | `headphone_volume` | **0x00–0x7F** | flag0 bit4 *(MÉDIA)* |
| 5 | `speaker_volume` | 0x00–0xFF | flag0 bit5 |
| 6 | `mic_volume` | **0x00–0x40** | flag0 bit6 |
| 7 | `audio_control` | ver §3 | flag0 bit7 |
| 8 | `mute_button_led` | — | flag1 bit0 |
| 9 | `power_save_control` | bit4 = mic mute | flag1 bit1 |
| 10 | `right_trigger_motor_mode` | ver §4 | flag0 0x04 |
| 11–20 | `right_trigger_param[10]` | — | idem |
| 21 | `left_trigger_motor_mode` | — | flag0 0x08 |
| 22–31 | `left_trigger_param[10]` | — | idem |
| 32–35 | `host_timestamp` (u32) | sincronismo de haptics | — |
| 36 | `reduce_motor_power` | — | flag1 bit6 |
| 37 | `audio_control2` | bits0-2 **pré-amp**; bit4 beam forming | **flag1 bit7** |
| 38 | `valid_flag2` | bit1 lightbar setup, bit2 vibration v2 | — |
| 39 | `haptics_flags` | bit0 filtro passa-baixa | — |
| 41 | `lightbar_setup` | **bit1 = fade out** | flag2 bit1 |
| 42 | `led_brightness` | 0-2 | flag2 bit0 |
| 43 | `player_leds` | `& 0x1F`; 0x20 = sem fade | flag1 bit4 |
| 44–46 | lightbar R, G, B | — | flag1 bit2 |

**Nota de proveniência que muda o que estava escrito nesta árvore:** o
`core/ds_output_report.py` marcava `common[4..7]` como *"PROVÁVEL, não medido"*,
porque o kernel os declarava `reserved`. **Isso caducou:** o Linux 6.18
(patches da Collabora, tratamento do jack de áudio) **nomeia esses campos
exatamente assim**. Os bytes 5, 6 e 7 podem ser promovidos a ALTA; o byte 4
(fone) segue MÉDIA.

---

## 3. Áudio — o caso do alto-falante que a mantenedora descreveu

Ela deu o exemplo: *"Zelda Skyward Sword: o speaker do controle faz os barulhos
da espada enquanto na tela tem o som normal do jogo"*.

**No PS5** o jogo abre uma **porta de áudio dedicada** ao alto-falante do pad —
mono, 48 kHz, paralela à saída principal. Não é mixagem: são portas diferentes.
A API é NDA (o identificador exato não foi encontrado em fonte pública, e **não
deve ser inventado**).

**No hardware, a rota é um campo do report**, e está documentada — ALTA:

```
audio_control (byte 7):
  bit0 FORCE_INTERNAL_MIC     bit1 FORCE_HEADSET_MIC
  bit2 ECHO_CANCEL            bit3 NOISE_CANCEL
  bits 4-5  OUTPUT_PATH_SEL:
     0 = estéreo -> fone
     1 = canal L -> fone (mono)
     2 = L -> fone,  R -> ALTO-FALANTE     <-- o caso Zelda
     3 = canal R -> alto-falante interno
  bits 6-7  INPUT_PATH: 0 ambos, 1 chat, 2 ASR
```

### O que isso corrige na medição desta casa

Em 01/08 mediu-se a curva do volume do alto-falante: **mudo até 38, satura em
102** — 60% do curso inerte. A explicação está aqui: o kernel 6.18, para fazer
o alto-falante soar quando o fone sai, escreve **três** campos:

```c
common->audio_control  = FIELD_PREP(...OUTPUT_PATH_SEL, 0x3);   /* a ROTA */
common->speaker_volume = 0x64;                                  /* 100 */
common->audio_control2 = FIELD_PREP(...SP_PREAMP_GAIN, 0x2);    /* o PRÉ-AMP */
```

Este projeto escreve **só o volume**. Os 64 passos úteis são a assinatura de
estar mexendo em um de três botões — e o `0x64` que o kernel escolhe é
exatamente o topo da faixa medida aqui. **A medição desta casa e o kernel
concordam**, e o que falta é o pré-amp e a rota.

### Haptics VCM — ALTA para USB, MÉDIA para Bluetooth

- **Por USB é ÁUDIO.** O DualSense é uma placa USB Audio de **4 canais**:
  **canais 1-2 = fone/alto-falante, canais 3-4 = os dois motores voice-coil.**
  O jogo toca PCM nos canais traseiros. Em Linux, o perfil precisa ser
  `Analog Surround 4.0` e o node precisa expor FL/FR/RL/RR.
- ATENÇÃO: **O bit que MATA os haptics:** `valid_flag0` bit1 (`HAPTICS_SELECT`). O
  SDL o liga em **todo rumble**, com o comentário `// Disable audio haptics`.
  Quem asserta esse bit troca os VCM de "PCM do jogo" para "rumble emulado".
- **Por Bluetooth não é áudio, é HID** — palavras do autor do driver:
  *"special HID packets using Bluetooth"*. Report `0x32`, corpo TLV, `pid 0x12`
  para áudio (64 bytes), CRC-32 semente `0xA2`. PCM de 3000 Hz, 2 canais, 8
  bits com sinal.

### Microfone

- **USB:** placa de áudio comum. Volume em `common[6]`, **máximo 0x40** (não
  0xFF). Caminho e processamento em `audio_control`. Mute em
  `power_save_control` bit4.
- **Detecção de jack — novidade do 6.18, ALTA:** `DS_STATUS1_HP_DETECT` (bit0)
  e `DS_STATUS1_MIC_DETECT` (bit1) **no report de entrada, byte 53**. Dá para
  saber se há fone sem adivinhar.
- **Bluetooth:** não há A2DP/HFP. Áudio Opus tunelado em HID — **mono, 48 kHz,
  quadros de 10 ms de 71 bytes**, dentro do report `0x31` com o bit1 do byte 1
  ligado. Este projeto já implementa a leitura.

---

## 4. Gatilhos adaptativos — a seção que corrige esta árvore

**Grau: ALTA** (a enum da Sony + três engenharias reversas independentes que
concordam: gist do Nielk1, `dualsensectl`, wiki do Game Controller Collective).

### Os modos, no fio

| byte | nome | status |
|---|---|---|
| `0x00` | **Off** | **MEDIDO AQUI** — ver a nota abaixo |
| `0x05` | **Off** | oficial |
| `0x21` | **Feedback** | oficial |
| `0x25` | **Weapon** | oficial |
| `0x26` | **Vibration** | oficial |
| `0x22` | Bow | não oficial, vivo no firmware |
| `0x23` | Galloping | não oficial |
| `0x27` | Machine | não oficial |
| `0x01`/`0x02`/`0x06` | Simple_Feedback / Weapon / Vibration | legado |
| `0x11`/`0x12` | Limited_Feedback / Limited_Weapon | legado |
| `0xFC`/`0xFD`/`0xFE` | **Debug — corrompem o estado. NÃO USAR** | — |

`MultiplePositionFeedback` e `SlopeFeedback` **não têm byte próprio**: são
`0x21` com o array de zonas. `MultiplePositionVibration` é `0x26`. Isso fecha
exatamente com os 7 modos da enum da Sony.

### O `0x00` também desliga — MEDIDO AQUI em 05/08/2026

Esta tabela listava só o `0x05` como Off, e essa omissão sustentou uma suspeita
inteira (`ENTREGA-QUE-NÃO-LIGOU-01`, defeito 2): como **todo** caminho de
desligar desta árvore manda `0x00` — `off()`, `trigger.reset`, o release do
Modo Nativo, o fim de sessão de jogo — e a tabela não o reconhecia, concluiu-se
que *"Desligar" podia não desfazer*.

**Medido com a mão dela**, pelo IPC, com o daemon vivo: `Rigid` (`0x21` com as
dez zonas ativas, força 255) endurece o L2 — *"duro"*; `Off` (`0x00`) o solta —
*"soltou"*.

**Os dois bytes desligam.** O `0x05` é o que a enum da Sony chama de
`MODE_OFF`; o `0x00` é honrado pelo firmware do mesmo jeito, e é o que esta
árvore usa em produção desde sempre. Quem for unificar num só: é troca de
higiene, **não** correção de defeito — e a decisão está medida, não suposta.

### O empacotamento dos 11 bytes — e o erro que ele revela

```
byte 0    = modo
bytes 1-10 = parâmetros

Feedback  (0x21): [1,2] activeZones u16LE ; [3..6] forceZones u32LE
                  (3 bits por zona, valor = strength - 1)
Weapon    (0x25): [1,2] (1<<start)|(1<<end) ; [3] strength - 1
Vibration (0x26): [1,2] activeZones ; [3..6] amplitudeZones ; [9] frequency
Bow       (0x22): [1,2] (1<<start)|(1<<end) ; [3,4] (str-1) | (snap-1)<<3
Galloping (0x23): [1,2] zonas ; [3] secondFoot | firstFoot<<3 ; [4] frequency
Machine   (0x27): [1,2] zonas ; [3] ampA | ampB<<3 ; [4] frequency ; [5] period
```

**Os modos oficiais NÃO recebem posições cruas.** Recebem um **bitmask de zonas
ativas** e **forças de 3 bits com valor `força − 1`**.

### O que isso significa para `core/trigger_effects.py` — A CONFERIR NO HARDWARE

A tabela desta árvore herdou a nomenclatura opaca de uma engenharia reversa de
2020 (`Rigid_A/B/AB`, `Pulse_A/B/AB`). Decodificada contra as fontes acima:

| `TriggerMode` daqui | valor | o firmware entende |
|---|---|---|
| `RIGID_A` | 0x21 | Feedback (oficial) — hoje é o `FEEDBACK`, e sete presets o usam |
| `RIGID_B` | **0x05** | **OFF** — nenhum preset o manda mais |
| `RIGID_AB` | 0x25 | Weapon |
| `PULSE_A` | 0x22 | Bow |
| `PULSE_B` | 0x06 | Simple_Vibration |
| `PULSE_AB` | 0x26 | Vibration — os cinco presets que ela aprovou |
| `CALIBRATION` | 0xFC | **Debug — REMOVIDO da enum em 01/08; o `custom()` recusa 0xFC-0xFE** |

Desde a TRIGGER-CANON-01 os nomes da coluna 1 são **alias** dos canônicos
(`FEEDBACK`, `WEAPON`, `VIBRATION`, `BOW`, `GALLOPING`, `MACHINE`) — eles
ficam porque estão em perfis no disco dela.

Consequência, se a decodificação estiver certa: `rigid()`, `simple_rigid()` e
`feedback()` mandam **OFF** — não fazem nada; `weapon()` **vibra** em vez de
resistir; e por aí.

**MEDIDO E CURADO em 01/08/2026 — TRIGGER-CANON-01.** Ela testou pela aba
Gatilhos e a decodificação se confirmou: *"rígido e desligado sem diferença"*,
*"resistência nada também"*, *"arco, galope e pulso e metralhadora funcionam"*.

E a medição trouxe DUAS correções ao que estava escrito aqui:

1. **a previsão de que os cinco presets de `0x26` seriam idênticos ERROU.**
   Ela: *"eles são bem diferentes viu"*. O motivo é instrutivo — os
   `forces[0]`/`forces[1]` desta árvore caíam em cima do bitmask de zonas, e
   cada preset produzia um bitmask ACIDENTAL diferente. Os parâmetros chegam e
   surtem efeito nos modos não oficiais;
2. **o empacotamento errado é um defeito INDEPENDENTE do modo errado**, e a
   prova é o `0x25`: ele é o Weapon OFICIAL, estava com o número certo, e não
   fez nada. Os modos oficiais VALIDAM os parâmetros; os legados e os não
   oficiais não.

E o aceite de produto dela mudou o objetivo da correção: *"as duas temos nomes
perfeitos, pq essa é a sensação de usar ambas"*. Os cinco que funcionam **não
foram tocados** — os bytes deles viraram dado, travados em
`tests/unit/test_trigger_canon_01.py`. Os sete que não faziam nada passaram a
mandar o modo oficial correto COM o bitmask de zonas.

**E refutou um bug registrado** (feito em 01/08, ver `trigger_effects.py`): o
`BUG-TRIGGER-MULTIPOS-FORCA8-01` concluiu
*"o campo tem 3 bits, logo o máximo é 7 e a força 8 satura"*. A codificação real
é `(strength − 1) & 0x07` com `strength` em 1..8, e `strength == 0` significa
**zona inativa** — expresso no bitmask que esta árvore não escreve. Os 8 níveis
SÃO expressáveis.

### Leitura de estado — recurso que ninguém usa aqui

O **nibble alto** do byte de status de cada gatilho, no report de entrada, diz
o que o gatilho está sentindo. A Apple expõe os mesmos estados com nome:
`feedbackNoLoad`, `feedbackLoadApplied`, `weaponReady`, `weaponFiring`,
`weaponFired`, `vibrationIsVibrating`, mais a posição do braço.

---

## 5. Sensores, touchpad e luzes — confirmações

**IMU — ALTA.** `8192` LSB/g (±4 g) e `1024` LSB/(°/s) (±2048 °/s). Calibração
no feature report `0x05`, 41 bytes, **imutável por unidade** — cachear por MAC
está certo.

**Taxas do SDL — e uma divergência a investigar:** DualSense por USB **250 Hz**;
por Bluetooth **1000 Hz**; **DualSense Edge por USB 1000 Hz**. O gamepad virtual
deste projeto se declara **Edge** (PID `0x0DF2`) e entrega os ~250 Hz do físico.
Um jogo que integre velocidade angular pela taxa declarada teria escala 4×
errada. **Não medido** — sprint `GYRO-EDGE-RATE-01`.

**Touchpad — ALTA.** 1920×1080, **2 pontos**, cada um com id e flag de contato
**invertida** (`0x80` = sem dedo). Clique é botão. Confirma o que está em
`core/physical_report_reader.py`.

**Lightbar e player LEDs — ALTA.** `lightbar_setup` bit1 é literalmente o **fade
out** (confirma a armadilha `LIGHTBAR-BT-KEEPALIVE-01` desta casa).
`led_brightness` tem 3 níveis. Padrões oficiais do PS5:
P1 `--x--`, P2 `-x-x-`, P3 `x-x-x`, P4 `x-xx-`, P5 `xxxxx`.

---

## 6. O que o report de ENTRADA carrega — e o byte que este projeto esquece

| off | campo |
|---|---|
| 0-5 | sticks e gatilhos analógicos |
| 6 | `ucCounter` |
| 7-10 | botões e hat |
| 15-20 | giroscópio |
| 21-26 | acelerômetro |
| 27-30 | `sensor_timestamp` (unidade 0,33 µs) — é o `dt` que o SDL integra |
| 32-35, 36-39 | os dois pontos de toque |
| 52 | `ucBatteryLevel` (`nibble*10+5`) |
| **53** | **`status[1]`: bit0 `HP_DETECT`, bit1 `MIC_DETECT`, bit2 `MIC_MUTE`** |

ATENÇÃO: **O gamepad virtual deste projeto nunca escreve o byte 53** — ele sai sempre
`0x00`. Consequência: o vpad anuncia **"fone e microfone sempre plugados"**, que
é o pior default possível justamente para o caso do alto-falante. Sprint aberta.

---

## 7. O que um DualSense virtual precisa cumprir — checklist

Derivada do que o SDL exige no probe e do que os jogos procuram. **ALTA.**

**Identidade**
1. VID `0x054C`, PID reconhecido pela camada-alvo
2. `BUS_USB`, descriptor **sem** o item `85 31` (que é o de Bluetooth)
3. Report de entrada `0x01` de **exatamente 64 bytes** — o SDL usa `size == 64`
   para decidir "é USB, modo enhanced"
4. Nome do device HID contendo **"Wireless Controller"** — jogos casam por essa
   substring
5. `/dev/hidraw` acessível pelo usuário da sessão
6. MAC único por instância

**Feature reports**
7. `0x09` com ≥ 7 bytes, MAC nos bytes 1-6
8. `0x20` com ≥ 46 bytes, versão nos bytes 44-45
9. `0x05` com 41 bytes de calibração **daquela unidade**

**Saída honrada**
10. Rumble nos bytes 2-3; **a parada do SDL vem com `valid_flag0 == 0` e
    motores zerados** — ver §8
11. Gatilhos nos blocos de 11 bytes, com os bits `0x04`/`0x08`
12. Lightbar, brilho e player LEDs com seus flags
13. Áudio: os sete campos da §2

**Áudio (alto-falante e haptics)**
14. Um device de áudio de **4 canais** associado ao controle
15. Casado por nome ("Wireless Controller") ou por ContainerId
16. **Não suspenso** quando o jogo enumera — o Wine não enumera sink suspenso
17. Só USB

---

## 8. A causa-raiz do rumble preso — achado de 01/08

O `integrations/uhid_gamepad.py` traz um comentário: *"Isto é MITIGAÇÃO, não a
cura. A cura seria descobrir por que o stop se perde"*.

**A cura foi encontrada.** No SDL, `RumbleJoystick(0, 0)` zera os motores e
chama `UpdateEffects`. Lá dentro:

```c
if (ctx->rumble_left || ctx->rumble_right) {
    effects.ucEnableBits1 |= 0x02;   /* desliga haptics de áudio */
} else {
    /* deixar os bits desligados restaura os haptics de áudio */
}
```

⇒ **Na parada, o SDL emite um report com `valid_flag0 == 0x00` e motores
zerados.** O portão deste projeto (`if not body[flag0] & 0x03: return`) descarta
**exatamente** esse report. É a receita do "tremendo sem parar".

O portão está certo pelo motivo certo (report de gatilho traz motores zerados).
O discriminador que separa os dois casos é limpo:

- **parada do SDL:** `valid_flag0 == 0` **e** `valid_flag1 == 0` **e** motores
  zerados;
- **report de gatilho:** `valid_flag0 & 0x0C ≠ 0`;
- **report de lightbar/player:** `valid_flag1 & 0x14 ≠ 0`.

---

## 9. Fontes

**Oficiais / semi-oficiais**
- `isteamdualsense.h` (header da Sony no Steamworks SDK) —
  `https://github.com/rlabrecque/SteamworksSDK/blob/master/public/steam/isteamdualsense.h`
- `hid-playstation.c` (kernel, autor da SIE) —
  `https://github.com/torvalds/linux/blob/master/drivers/hid/hid-playstation.c`
- Série de patches e cover letters na `linux-input` —
  `https://yhbt.net/lore/all/20210117230956.173031-3-roderick@gaikai.com/T/`
- Patches do jack de áudio (Collabora, 6.18) —
  `https://lwn.net/Articles/1026850/`
- Apple GameController (`GCDualSenseAdaptiveTriggerStatus`) —
  `https://developer.apple.com/documentation/gamecontroller/gcdualsenseadaptivetrigger`

**Engenharia reversa de comunidade (boa, não oficial)**
- Gist do Nielk1 (o mais completo sobre gatilhos) —
  `https://gist.github.com/Nielk1/6d54cc2c00d2201ccb8c2720ad7538db`
- `dualsensectl` — `https://github.com/nowrep/dualsensectl`
- Game Controller Collective Wiki —
  `https://controllers.fandom.com/wiki/Sony_DualSense/Data_Structures`
- `SDL_hidapi_ps5.c` —
  `https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_ps5.c`
- SAxense (haptics por BT) — `https://github.com/egormanga/SAxense`
- DS5Dongle (mic por BT, fonte canônica) — `https://github.com/awalol/DS5Dongle`

**Caminho do jogo**
- Proton, DualSense advanced features —
  `https://github.com/ValveSoftware/Proton/issues/5900`
- Wine + DualSense por hidraw —
  `https://nick.tay.blue/2024/01/21/wine-dualsense/`
- `dualsense-games-compat-check` (replica o que os jogos fazem) —
  `https://github.com/ClearlyClaire/dualsense-games-compat-check`
