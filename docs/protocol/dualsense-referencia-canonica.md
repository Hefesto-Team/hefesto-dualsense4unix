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
| **FONTE DESTA MÁQUINA** | lido no fonte que compilou o módulo carregado agora, com `caminho:linha` | o padrão de player LED do jogador 4 |

E a regra que a origina: **medir contra a ferramenta errada produz um resultado
convincente e falso.** Em 01/08 mediu-se o gamepad virtual contra a `libSDL2`
do Ubuntu e concluiu-se que ele não entregava nada; a biblioteca que os jogos
usam entrega tudo. Todo instrumento tem de declarar contra o que mediu.

**A régua de fonte, fixada em 11/08/2026 — toda citação diz contra QUE fonte
foi feita.** São duas metades:

1. **Fonte externa se cita por tag ou commit, nunca por ramo.** `master` e
   `main` andam sozinhos, e uma citação de linha contra eles apodrece sem
   ninguém notar. Toda URL desta página está fixada.
2. **Afirmação sobre *"o kernel"* diz QUAL kernel.** O que roda aqui é
   `7.0.11-76070011-generic`, e o `hid-playstation` dele **não é o vanilla**: é
   o DKMS desta árvore (`assets/dkms/hid-playstation/`), que é o `v7.0.11` do
   Pop!_OS mais os dois patches desta casa — proveniência e `sha256` conferidos
   em `assets/dkms/hid-playstation/patch/BASELINE`. É esse arquivo que as
   linhas **FONTE DESTA MÁQUINA** citam.

**Consequência de grau, e ela derruba linhas que já estiveram escritas aqui:**
grau herdado de *"o kernel tal faz assim"*, sem o fonte na mão, **não é ALTA**.
Ou se abre o arquivo e se cita a linha — e aí é FONTE DESTA MÁQUINA — ou o grau
desce.

## O que caducou em 11/08/2026 — leia antes de citar esta página

Oito afirmações daqui foram confrontadas **linha a linha contra o código desta
árvore** em 11/08/2026, a partir das ressalvas do mapa de canais
(`docs/data/mapa-controles.csv`). Este índice é só o atalho.

**E a segunda passagem do mesmo dia mudou o que se faz com o que caduca**, por
decisão dela: **fato errado se substitui, decisão medida se data.** Número
errado não guarda decisão nenhuma — mantê-lo ao lado do certo só obriga a
próxima pessoa a escolher entre duas afirmações, e ela pode escolher errado. O
que ganha nota datada é o que, se sumisse, faria alguém repetir trabalho ou
pagar um custo já pago.

| onde | o que a página dizia | o que vale em 11/08 |
|---|---|---|
| §2 | `common[4..7]` é PROVÁVEL; o kernel os chama `reserved[4]` | **CADUCOU** — ALTA nos bytes 5, 6 e 7. O byte 4 se parte em dois: campo ALTA, **bit** de autorização MÉDIA |
| §3 | *"Este projeto escreve só o volume"* | **CADUCOU** — o pré-amp e a rota são escritos desde 01-02/08 |
| §3 | o áudio por Bluetooth sai no report `0x32` | **CONTRADIÇÃO EM ABERTO** com o `0x39` que o código descreve — **nenhum dos dois medido** |
| §4 | a decodificação dos modos está curada | `weapon()` e `vibration()` seguem mandando o modo ERRADO pela régua desta própria seção — **não medido** |
| §5 | player LED do jogador 4 | **CORRIGIDO** — é `xx-xx`, pelo fonte do driver desta máquina. O padrão que estava escrito aqui é o de *slot fora da tabela* do código desta casa |
| §5 | a taxa do giroscópio, *"nunca medida"* | **MEDIDA em 11/08** — cabo 250,0 Hz exatos, rádio variável em rajadas. O que continua aberto é o que o **SDL declara ao jogo**, não o que o aparelho entrega |
| §6 | *"o gamepad virtual nunca escreve o byte 53"* | **CADUCOU** — escreve desde 09/08, e a conclusão que se tirava dali estava **invertida** |
| §6 | byte 52 = `ucBatteryLevel` | **INCOMPLETO** — o nibble ALTO é estado de carga, e o código o decodifica em cinco casos |

**E uma nona, medida na bancada de 11→12/08/2026, que é a mais cara das nove:**
a coluna *"validado por"* da tabela do §2 descreve o que o report **declara**,
não o que o firmware **exige**. Para os dois bytes de motor os dois divergem —
o aparelho obedeceu a `common[2]`/`common[3]` **com os bits de vibração
desligados**, e essa diferença derrubou a premissa de uma cura inteira que já
estava escrita nesta árvore. A medição, com a fala dela e a ressalva de escopo,
está no §2, em *"Os BITS de vibração não são porteiro dos BYTES de motor"*.

**Documento irmão:**
[os externos — Pro Controller e 8BitDo](externos-referencia-canonica.md). Esta
página vale **só para o DualSense**. Os controles das outras linhagens têm
envelope, escalas de IMU, régua de bateria e limitador de taxa **diferentes** —
e um instrumento escrito para um deles escreve lixo no outro.

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

Fonte, fixada no commit (o repositório não publica tag, e o ramo padrão anda):
`https://github.com/rlabrecque/SteamworksSDK/blob/df2baabf574a738ef1ea90a7e89339107fc0a279/public/steam/isteamdualsense.h`

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
· mainline fixado na tag,
`https://github.com/torvalds/linux/blob/v7.0/drivers/hid/hid-playstation.c`
· **e o fonte que roda aqui**, que é o que esta página cita por linha:
`assets/dkms/hid-playstation/hid-playstation.c` — `v7.0.11` do Pop!_OS
(`raw.githubusercontent.com/pop-os/linux/3af2f9de43174ce5063110f94b7b01226499ba13/drivers/hid/hid-playstation.c`)
mais os dois patches desta casa

### 1.3. O que a Sony publicou para PC — nada de técnico

O app **PlayStation Accessories** (Windows) atualiza firmware e customiza o
Edge. **Não há SDK, API nem nota técnica.** Tudo que funciona em PC é o jogo
falando HID cru.

---

## 2. O report de saída `0x02` — os 47 bytes do `common`

**Grau: FONTE DESTA MÁQUINA** — a `struct dualsense_output_report_common` do
driver que roda aqui (`assets/dkms/hid-playstation/hid-playstation.c:320-348`,
com o `static_assert` de 47 bytes em `:349`) e o `dualsensectl` são idênticos
campo a campo.

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
porque o kernel os declarava `reserved`. **Isso caducou**, e a fonte que o
derruba está no disco: o driver desta máquina **nomeia esses campos exatamente
assim** — `headphone_volume`, `speaker_volume`, `mic_volume` e `audio_control`
em `assets/dkms/hid-playstation/hid-playstation.c:329-332`, com os tetos `0x7f`
e `0x40` escritos no próprio comentário do fonte. (A origem upstream é a série
do jack de áudio da Collabora, que entrou no 6.18; o que se cita aqui por linha
é o fonte compilado nesta máquina, não o 6.18.) Os bytes 5, 6 e 7 podem ser
promovidos a ALTA; o byte 4 (fone) segue MÉDIA.

> **NOTA DATADA — 11/08/2026: o código não tinha acompanhado, e ele se
> contradizia sozinho.**
>
> A nota acima é de 01/08 e diz *"podem ser promovidos"*. Dez dias depois o
> comentário do `core/ds_output_report.py` **ainda** afirmava que o kernel
> declara `common[4..7]` como `reserved[4]`, que nunca os escreve, e que o
> mapeamento é PROVÁVEL — enquanto **o mesmo arquivo**, umas dezenas de linhas
> abaixo, atribuía "ao kernel 6.18", sem dizer contra que fonte, os tetos
> `0x7F` (fone) e `0x40` (microfone). Um comentário negava a fonte que o outro
> citava, e nenhum dos dois apontava para um arquivo que alguém pudesse abrir.
>
> **Curado hoje**, sem tocar em lógica: `core/ds_output_report.py:70-96`. O
> texto de 01/08 ficou visível ali dentro, riscado por nota, não por deleção.
>
> **O grau, agora explícito** — e ele se parte em dois no byte 4, que é o
> ponto que se perdia quando a linha dizia só *"MÉDIA"*:
>
> | | o CAMPO | o BIT que o autoriza |
> |---|---|---|
> | `common[5]` alto-falante | **ALTA** — `hid-playstation.c:330` | **ALTA** — `SPEAKER_VOLUME_ENABLE`, `:209` |
> | `common[6]` microfone | **ALTA** — `:331`, com o teto `0x40` no comentário do fonte | **ALTA** — `MIC_VOLUME_ENABLE`, `:210` |
> | `common[7]` caminho de áudio | **ALTA** — `:332` | **ALTA** — `AUDIO_CONTROL_ENABLE`, `:211` |
> | `common[4]` fone | **ALTA** — `:329`, com o teto `0x7f` no comentário do fonte | **MÉDIA** — o driver define enable para os outros três e **nenhum** para o fone; o `0x10` desta árvore é de comunidade, e **ninguém mediu o que ele faz** |
>
> **A fonte, agora com endereço:** o `hid-playstation` **foi relido em 11/08**,
> e o que se releu é o desta máquina —
> `assets/dkms/hid-playstation/hid-playstation.c`, o fonte que compilou o
> módulo carregado agora. As linhas da tabela acima saem dele. A leitura
> completa, seção a seção, está em
> [o driver `hid-playstation` por dentro](driver-hid-playstation.md).
>
> **O que a releitura NÃO fecha:** o bit `0x10`. Ele não existe no driver em
> forma nenhuma, então nenhuma leitura de fonte pode promovê-lo — quem quiser
> grau MEDIDO AQUI para ele precisa do ensaio da lista final desta página, com
> headset no jack.

### Os BITS de vibração não são porteiro dos BYTES de motor

**Grau: MEDIDO AQUI**, na bancada de 11→12/08/2026, com o olho dela como
aceite. Ensaio `keepalive-premissa-troca-de-lado`
(`docs/data/ensaios.csv:24`), instrumento
`scripts/ensaio_o_keepalive_mata_o_rumble.py`, report montado pelo
`_build_common` do próprio produto.

A tabela acima diz que `motor_right`/`motor_left` são *"validados por flag0
bit0/bit1"*. Isso descreve o que o report **declara** — e esta casa leu ali,
por meses, uma promessa que o firmware não faz: a de que **sem os bits o
aparelho ignora os bytes**.

**O ensaio, desenhado para não pedir cronômetro à mão dela.** Com o daemon
parado, um `EV_FF` pelo evdev ligou o motor **esquerdo**. Em seguida saiu **um
único** report com os bits de vibração **desligados** (`flag0` `0x01|0x02`, a
atenuação `0x40` do `flag1` e o `0x04` do `flag2`) pedindo `common[2] = 200`
(direito) e `common[3] = 0` (esquerdo). Literal dela: *"esquerda e senti que
foi pra direita e lá morreu"*.

**O tremor trocou de lado.** Logo o report agiu, e agiu **pelos bytes**. O lado
que estava parado começou a vibrar e o que estava vibrando parou, sem que
nenhum bit de autorização estivesse ligado naquele report.

**A dose-resposta que fechou a conta pelo outro lado** (ensaios
`keepalive-dose-cabo` e `keepalive-dose-radio`, `docs/data/ensaios.csv:22-23`):
subindo a constante de keepalive do produto de **0,5 s para 8,0 s**, a vibração
de terceiros passou a durar **oito segundos exatos** nos dois transportes.
Literal dela: *"cibrou ambos por 8 segundos"*. A duração seguiu o valor da
constante — isso é relação causal, não vizinhança.

**O escopo, dito com todas as letras, porque a generalização aqui é tentadora:**

- **o que está medido** é que, com a vibração **já autorizada por um report
  anterior de outro escritor** (o driver do kernel, no caminho do `EV_FF`), os
  reports seguintes agem sobre `common[2]`/`common[3]` **independentemente dos
  próprios bits**;
- **o que NÃO está medido** é o aparelho recém-ligado: se um report com os bits
  nunca ligados desde o *power-on* põe um motor para girar do silêncio, ninguém
  aqui viu;
- **o que NÃO está medido para nenhum outro bloco.** Os blocos de gatilho
  (`common[10..20]` e `common[21..31]`), os de LED e os de áudio também saem em
  **todo** report, fora de qualquer condicional. A previsão de que se
  comportassem como os motores foi **medida para o gatilho e caiu** (ver §4, e
  `docs/data/ensaios.csv:29-30,37`); para LED e áudio continua sem ensaio.

**A consequência para quem escreve neste aparelho**, e é a razão de esta
subseção existir: **não há valor neutro para `common[2]`/`common[3]`**. O
report é atômico, os dois bytes viajam em todo write, e o aparelho não devolve
o que o outro escritor pediu — então "carregar o último valor conhecido" seria
carregar o **nosso** zero com outro nome. Quem quiser preservar a vibração de
outro dono só tem uma saída: **o write que não acontece**. Foi essa a cura
aplicada aqui (`RUMBLE-SEM-DONO-01`, em
`core/backend_pydualsense.py`: o keepalive deixou de ser perpétuo e passou a
valer só na janela de confirmação depois de cada mudança real).

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
102** — 60% do curso inerte. A explicação está aqui: o driver desta máquina,
para fazer o alto-falante soar quando o fone sai, escreve **três** campos —
`assets/dkms/hid-playstation/hid-playstation.c:1508-1524`, no ramo `else` da
borda de `DS_STATUS1_HP_DETECT`:

```c
common->audio_control  = FIELD_PREP(...OUTPUT_PATH_SEL, 0x3);   /* a ROTA */
common->speaker_volume = 0x64;                                  /* 100 */
common->audio_control2 = FIELD_PREP(...SP_PREAMP_GAIN, 0x2);    /* o PRÉ-AMP */
```

Este projeto escreve **só o volume**. Os 64 passos úteis são a assinatura de
estar mexendo em um de três botões — e o `0x64` que o driver escolhe é
exatamente o topo da faixa medida aqui. **A medição desta casa e o driver
concordam**, e o que falta é o pré-amp e a rota. (O comentário do próprio fonte,
em `:1514`, diz que a faixa aceita parece ser `[0x3d..0x64]`.)

> **NOTA DATADA — 11/08/2026: o parágrafo acima descreve o produto de 01/08,
> e induz a refazer trabalho já feito.**
>
> *"Este projeto escreve só o volume"* **caducou**. Os três campos são
> escritos hoje, e cada um tem endereço:
>
> | campo | onde é escrito | grau |
> |---|---|---|
> | volume, `common[5]` | o laço dos quatro bytes de áudio — `_AUDIO_COMMON_OFFSETS` em `core/backend_pydualsense.py:930-932` | **ALTA** — lido no código |
> | pré-amp, `common[37]` | `core/backend_pydualsense.py:935-940`, com o `VALID_FLAG1_AUDIO_CONTROL2_ENABLE` em `:937`; o valor padrão `0x2` é o `SP_PREAMP_GAIN_PADRAO` em `core/ds_output_report.py:184` | **ALTA** — lido no código |
> | rota, `common[7]` bits 4-5 | `core/backend_pydualsense.py:259-287` (`_byte_da_rota`) | **MEDIDO** — com a orelha dela em 02/08, rota 3 audível, rota 0 sem fone inaudível |
>
> *(Os endereços das duas primeiras linhas foram REAPONTADOS em 13/08/2026: eles
> apontavam para `:780-782`, `:783-790`/`:789` e `:2695`, que a refatoração do
> `_build_common` mudou de lugar — `:789` caiu no meio de um docstring e o flag
> passou a viver em `:937`. As afirmações não mudaram; só o endereço estava
> podre. Desde então `scripts/validar-citacoes-de-linha.py` abre cada endereço
> deste documento e reprova quando ele não contém o que promete.)*
>
> **E a medição da curva caducou junto, que é o efeito mais caro deste
> parágrafo.** O *"mudo até 38, satura em 102"* foi levantado **sem** o
> pré-amp, num caminho de código que não existe mais. O número continua
> verdadeiro sobre o que foi medido em 01/08 e **deixou de descrever o produto
> de hoje**; a curva **com** pré-amp é **não medida**. Quem citar os 64 passos
> úteis como propriedade do hardware está citando uma régua que mediu outra
> coisa.
>
> Só o **quarto** item do áudio de saída continua não escrito, e ele não é
> registrador nenhum: são os **dados** de PCM (a §7, itens 14 a 17). Não
> confundir *"o Hefesto não toca som"* com *"o Hefesto não mexe no
> alto-falante"*.

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

> **NOTA DATADA — 11/08/2026: CONTRADIÇÃO INTERNA EM ABERTO, e não é a que
> parece.**
>
> A linha acima e o `integrations/dualsense_bt_audio.py` discordam sobre o
> report que leva **os dados de áudio para fora** — e a discordância
> sobreviveu porque os dois falam de `0x32` em algum ponto:
>
> | fonte | diz | grau |
> |---|---|---|
> | esta página | os blocos TLV de áudio saem no report **`0x32`**, tag `0x12` | **BAIXA** — fonte única de comunidade (SAxense) |
> | `integrations/dualsense_bt_audio.py:31` e `:213-219` | o `0x32` é o **AudioControl** (liga/desliga do microfone, tag `0x11`); quem carrega háptico (`0x12`) e alto-falante (`0x13`/`0x16`) é o report **`0x39`** | **BAIXA** — lido do firmware `DS5Dongle`, não medido |
>
> **O `0x32` que esta casa mediu não decide a questão.** O que foi medido ao
> vivo em 25/07 é o `0x32` de **controle** — 142 bytes, TLV `0x11|0x80`, o
> byte que destrava o microfone (`integrations/dualsense_bt_audio.py:210`).
> Isso não é o report de **payload**, e nunca foi. Ninguém aqui escreveu um
> byte de áudio de saída por rádio.
>
> **Não escolhemos um lado.** Os dois candidatos são de fonte única e nenhum
> foi medido nesta máquina; a coincidência do número `0x32` é exatamente o
> tipo de semelhança que produz alarme convincente e falso.
>
> **O ensaio que resolve:** ler o *report descriptor* do DualSense por
> Bluetooth e ver quais IDs de output existem e com que tamanho declarado — é
> como o `0x32` de 142 bytes já foi estabelecido (`85 32 09 32 95 8d 91 02`,
> registrado em `integrations/dualsense_bt_audio.py:207-211`). Se houver um
> `0x39` no descritor, com tamanho compatível com dois blocos de 200 bytes, a
> contradição fecha sem tocar no controle. É leitura pura, sem escrita, sem
> risco.

### Microfone

- **USB:** placa de áudio comum. Volume em `common[6]`, **máximo 0x40** (não
  0xFF). Caminho e processamento em `audio_control`. Mute em
  `power_save_control` bit4.
- **Detecção de jack — FONTE DESTA MÁQUINA:** `DS_STATUS1_HP_DETECT` (bit0) e
  `DS_STATUS1_MIC_DETECT` (bit1) **no report de entrada, byte 53**, definidos em
  `assets/dkms/hid-playstation/hid-playstation.c:177-178` (e o `MIC_MUTE` do
  bit2 em `:180`). Dá para saber se há fone sem adivinhar. Upstream isto veio
  com a série do jack de áudio da Collabora, no 6.18; aqui está lido no fonte
  que compilou o módulo carregado agora.
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

### O lado, confirmado no aparelho — MEDIDO AQUI em 11/08/2026

**Grau: MEDIDO AQUI.** Ensaio `gatilho-lado-nao-esta-invertido`
(`docs/data/ensaios.csv:36`), com o controle na mão dela.

A tabela do §2 põe `right_trigger_motor_mode` em `common[10]` (autorizado por
`flag0 0x04`) e `left_trigger_motor_mode` em `common[21]` (`flag0 0x08`). Isso
era leitura de fonte; agora tem aceite no plástico. Autorizando **só** o
direito, o R2 endureceu e o L2 ficou solto — literal dela: *"r2 duro, l2
solto"*. A suspeita de que o mapeamento de lado estivesse invertido nasceu numa
rodada anterior e foi **eliminada na mesma sessão**.

**A ressalva de método, e ela vale mais que o resultado:** numa das rodadas o
lado que **não** foi autorizado ficou solto, e isso foi registrado, por engano,
como prova de que ele obedece. Não é. Um gatilho solto prova que o comando
**não vazou de lado** — é controle negativo, não obediência. Ela pegou o erro.

### O gatilho chega pelo RÁDIO, e o alvo por MAC é respeitado lá — MEDIDO AQUI em 12/08/2026

**Grau: MEDIDO AQUI**, ensaios `gatilho-esq-radio-1216` e `gatilho-esq-cabo-1216`
(`docs/data/ensaios.csv:63-64`) e `gatilho-dir-radio-isolado-2221`
(`ensaios.csv:67`), com quatro DualSense na mesa — dois no cabo, dois no rádio —
e o olho dela em cada um.

Até 12/08 **nenhum** ensaio sustentava o efeito adaptativo por Bluetooth: a
afirmação vinha de leitura de código, e foi o portão `grau-sem-ensaio` (12/08)
que flagrou a falta. Agora tem plástico atrás:

- **`Rigid[0,8]` aplicado só no L2**, às 22:16:53, nos quatro controles: **L2
  duro em todos os quatro**, cabo e rádio. O **R2 intocado** é o controle
  negativo do próprio ensaio — solto nos quatro —, e é ele que separa
  *"obedeceu"* de *"achei que estava diferente"*.
- **`Rigid[0,8]` só no R2 de UM controle do rádio**, mirado por `uniq` (o MAC),
  às 22:21:06: **só o mirado endureceu**; nos outros três o R2 seguiu solto.
  O ensaio prova duas coisas na mesma janela — o gatilho **direito** obedece por
  rádio, e o endereçamento por MAC é respeitado **no Bluetooth**. Sem o controle
  negativo dos três soltos, um `uniq` ignorado viraria broadcast e o isolamento
  seria ilusão.

**O que estes ensaios NÃO fecham:** continua valendo o que a lista de abertos diz
— só o modo `Rigid` foi exercitado, com **um** jogo de parâmetros, e o elemento
específico de que o efeito depende segue sem isolamento.

### O keepalive apaga o rumble de terceiros, mas NÃO o gatilho

**Grau: MEDIDO AQUI**, ensaios `gatilho-keepalive-8s`, `gatilho-keepalive-30s`
e `gatilho-quem-apaga-nao-e-o-keepalive` (`docs/data/ensaios.csv:29-30,37`).

Da medição do §2 (*"os bits não são porteiro dos bytes"*) veio uma previsão
natural: como os blocos de gatilho também saem em **todo** report, o keepalive
apagaria o efeito de gatilho de outro escritor pelo mesmo mecanismo com que
apagava o rumble. **A previsão foi medida e caiu.**

Um `Rigid` (posição 3, força 8) escrito por report cru **por fora** do daemon,
com o daemon **vivo** e o keepalive em 0,5 s, sobreviveu a 8 s e a 30 s — o L2
duro nas duas leituras, o R2 solto. O rumble, sob exatamente o mesmo keepalive,
morria em menos de meio segundo. **São mecanismos diferentes**, e o keepalive
está inocentado para o gatilho.

**O que ficou aberto, e é fenômeno sem suspeito:** aos **120 s** a leitura se
inverteu — o L2 solto e o R2 *"vivo"*, literal dela. O resultado **não é
monotônico**, então não é decaimento. A leitura provável (e é **inferência**,
não medição) é que algo reaplicou o perfil ativo naquele intervalo, apagando o
efeito de terceiro no esquerdo e ligando o do perfil no direito. **Quem
reaplica, e com que período, não foi medido.**

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

> **NOTA DATADA — 11/08/2026: a cura da TRIGGER-CANON-01 não alcançou dois
> presets, e são justamente os dois de nome oficial.**
>
> A seção acima conta a leva curada. Conferido no código hoje, **dois efeitos
> continuam mandando o modo que esta própria tabela chama de errado**, e
> ninguém mediu se fazem alguma coisa:
>
> | função | manda | a tabela desta seção decodifica como | deveria ser |
> |---|---|---|---|
> | `weapon()` — `core/trigger_effects.py:461-466` | `PULSE_B` = **`0x06`** (`:129`) | Simple_Vibration, **legado** | `0x25`, o Weapon oficial |
> | `vibration()` — `core/trigger_effects.py:469-481` | `PULSE_A` = **`0x22`** (`:128`) | **Bow**, não oficial | `0x26`, o Vibration oficial |
>
> Eles ficaram **fora dos dois grupos** da cura: não estão entre os SETE que
> ela mediu como inertes e que foram corrigidos, nem entre os CINCO que ela
> aprovou pela sensação e cujos bytes viraram dado travado em
> `tests/unit/test_trigger_canon_01.py`. Caíram no vão.
>
> **Grau: BAIXA, e a incerteza é real, não formal.** A régua que os condena é
> a decodificação desta seção, que é ALTA; mas a §4 também registra que os
> modos **não oficiais e legados NÃO validam parâmetros** — foi por isso que
> os cinco presets de `0x26` produziram sensações diferentes por acidente. Um
> `0x22` com os parâmetros de uma vibração pode muito bem estar entregando
> algo que ela aprova. **Nada aqui autoriza trocar os bytes sem a mão dela no
> gatilho.**
>
> **O ensaio que resolve, e ele é o mesmo de 01/08:** aplicar os dois pela aba
> Gatilhos, com o daemon vivo, e perguntar o que o dedo sente. Se
> `weapon()` não resistir e `vibration()` não pulsar, é a mesma classe de
> defeito já curada; se ela gostar do que sente, o nome é que está errado, e
> a decisão dela em 01/08 já disse qual vence — *"as duas temos nomes
> perfeitos, pq essa é a sensação de usar ambas"*.

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

> **Contraste obrigatório, acrescentado em 11/08/2026 — estas escalas são
> SÓ do DualSense.** O Pro Controller usa `4096` LSB/g (±8 g) e `14,247`
> LSB/(°/s) (±2000 °/s), medidos no driver desta máquina e registrados na
> [canônica dos externos](externos-referencia-canonica.md), seção 3.5. Quem
> comparar eixos das duas linhagens sem converter erra por **2×** no
> acelerômetro e por cerca de **14×** no giroscópio. GRAU: ALTA.

### As taxas de relatório — o que o APARELHO entrega, medido em 11/08/2026

**Grau: MEDIDO AQUI.** Antes do número, o que o driver impõe: **nada**. Ele não
pede taxa nenhuma ao DualSense, nem por cabo nem por rádio — não há campo,
função nem default no fonte desta máquina. O contraste dentro do mesmo arquivo
é a prova:
o **DualShock 4** tem `bt_poll_interval` na struct
(`assets/dkms/hid-playstation/hid-playstation.c:483-484`, dentro de
`struct dualshock4` de `:462`), um `dualshock4_set_bt_poll_interval` (`:2873`)
e um default aplicado na probe (`:3022`); a `struct dualsense` de `:233` **não
tem equivalente de nada disso**. O que chega é o que o aparelho e o transporte
decidem, e foi isso que se mediu.

**As réguas, declaradas** — duas, independentes, sobre o nó evdev
`Motion Sensors`, que emite `MSC_TIMESTAMP` a cada report:

1. **relógio do host** — contagem de `SYN_REPORT` sobre tempo de parede;
2. **relógio do controle** — média das diferenças de `MSC_TIMESTAMP`, que o
   driver deriva do `sensor_timestamp` do próprio aparelho. Esta **não depende
   do agendamento do host**.

**O cabo: 250,0 Hz exatos**, e três fontes independentes concordam.

| o que diz | quem diz |
|---|---|
| **250,0 Hz** (4,00 ms; 2501 reports em 10,000 s) | relógio do host |
| **250,0 Hz** (delta médio 4000,3 us) | relógio do controle |
| **250 Hz** previstos: `bInterval = 6` nos dois endpoints de interrupção, e em High Speed o intervalo de serviço é `2^5 × 125 us = 4000 us` | o descritor USB |

A terceira nem é medição: é o intervalo de serviço que o endpoint **declara**.
**Os 250 Hz do cabo estão fechados.**

**O rádio: variável, em rajadas, e nunca 1000 Hz.** Cinco janelas de 8 a 10 s,
mesmo controle, parado sobre a mesa, e as duas réguas por janela (o traço é
janela em que aquela régua não foi colhida):

| janela | relógio do host | relógio do controle |
|---|---|---|
| 1 (10 s) | 363,3 Hz | — |
| 2 (10 s) | — | 239,9 Hz |
| 3 (8 s) | 334,1 Hz | 392,4 Hz |
| 4 (8 s) | 55,4 Hz | 38,3 Hz |
| 5 (8 s) | 69,7 Hz | 48,5 Hz |

**O rádio não tem taxa típica.** A média sustentada mais alta foi ~392 Hz e a
mais baixa ~38 Hz, no mesmo controle, entre janelas consecutivas, sem que nada
mudasse. E o fluxo é **em rajadas**: o p05 do intervalo é teimosamente 1255 us
(~797 Hz **instantâneos**) enquanto o p95 chega a 187 ms — dentro da rajada o
controle é rápido, e o que varia é o silêncio entre rajadas. Quem citar um
número só para o rádio está citando **uma janela**, não o transporte.

**Os 1000 Hz que o SDL declara para Bluetooth não aparecem em janela nenhuma**,
nem como média nem como mediana.

A medição completa, com as cinco janelas e as medianas, está em
[o driver `hid-playstation` por dentro](driver-hid-playstation.md), seção 6.

**O que isto NÃO fecha, e é a divergência que continua aberta:** o SDL
**declara** DualSense por USB 250 Hz, por Bluetooth 1000 Hz, e **Edge por USB
1000 Hz**. O gamepad virtual deste projeto se declara **Edge** (`VPAD_PRODUCT =
0x0DF2`, `integrations/uhid_gamepad.py:123`) e entrega os 250 Hz do físico. Um
jogo que integre velocidade angular pela taxa declarada teria escala 4× errada.
O lado do **aparelho** está medido acima; o lado do **SDL** não.

> **NOTA DATADA — 11/08/2026: a régua é metade do ensaio, e ela custou um
> alarme falso inteiro.**
>
> A metade que falta só vale medida contra a **SDL3 que a Steam distribui**,
> que é a biblioteca que os jogos usam — **nunca** contra a `libSDL2` do
> sistema. Medir contra a biblioteca errada já produziu, nesta casa, um alarme
> falso inteiro (é a armadilha do topo desta página). Enquanto o número não
> vier de lá, o grau daquela metade é **BAIXA**, e a frase honesta é *"não
> medido"*.
>
> **`GYRO-EDGE-RATE-01` é NOME DE DIVERGÊNCIA, não sprint.** Não existe
> arquivo com esse nome em `docs/process/sprints/`, e chamá-lo de sprint faz
> parecer que alguém está com o trabalho na mão. O apelido está registrado em
> [divergências nomeadas](../process/DIVERGENCIAS-NOMEADAS.md), que é onde se
> confere o que cada nome desses quer dizer.
>
> **O aparelho vizinho já mostrou que a família de defeito é real:** o Pro
> **declara** 8 ms no comentário do driver, 15 ms no default, e **entrega**
> 11,2 ms — medido três vezes em 07/08, na
> [canônica dos externos](externos-referencia-canonica.md), seção 3.5. É o
> mesmo desenho de defeito, com um segundo aparelho e um número medido. Não é
> prova sobre o DualSense.

**Touchpad — ALTA.** 1920×1080, **2 pontos**, cada um com id e flag de contato
**invertida** (`0x80` = sem dedo). Clique é botão. Confirma o que está em
`core/physical_report_reader.py`.

**Lightbar — ALTA.** `lightbar_setup` bit1 é literalmente o **fade out**
(confirma a armadilha `LIGHTBAR-BT-KEEPALIVE-01` desta casa). `led_brightness`
tem 3 níveis.

**O firmware GUARDA a cor entre conexões — MEDIDO AQUI em 12/08/2026.** Ensaio
`lightbar-firmware-guarda-a-cor` (`docs/data/ensaios.csv:48`): um controle voltou
de uma **desconexão completa** exibindo o **magenta** que tinha sido escrito por
`hidraw` cru vários minutos antes, atravessando um `Disconnect` pelo BlueZ e uma
reconexão inteira. Literal dela: *"azul player 4 cor magenta"*.

**E o firmware guarda a cor SEM REFORÇO NENHUM: 136 s cronometrados — MEDIDO
AQUI em 12/08/2026, à noite.** Ensaio `cor-rota-hidraw-sem-steam-2235`
(`docs/data/ensaios.csv:71`), com o **daemon parado** às 22:34:53 e a **Steam
fechada** — ou seja, sem escritor nenhum na máquina. Magenta (255,0,255) escrito
por report `0x31` nos **dois** controles do rádio às 22:35:02; às 22:37:18 as
duas barras continuavam magenta, **o dobro do prazo de 60 s que o ensaio
pedia**. Literal dela: *"dois bt tão magenta... seguem iguais, nenhum mudou"*.

**Uma cor escrita não precisa de keepalive para ficar de pé — QUANDO NÃO HÁ
OUTRO ESCRITOR.** A condição não é detalhe: é o que o ensaio de fato mediu
(daemon parado, Steam fechada), e sem ela a frase vira prescrição sem prova.
Com escritor concorrente a conta se inverte, e a mesma bancada mediu isso: a
Steam repinta na probe (`lightbar-probe-suja-steam`) e a reafirmação passa a ser
justamente o instrumento com que o produto disputa a barra. O que o ensaio
autoriza afirmar é sobre o FIRMWARE, não sobre a política de escrita do produto.
O custo de reafirmar por hábito já foi medido noutro lugar, e ali é real: no
rumble, a reafirmação perpétua **apagava motor alheio** (§2, *Os BITS de
vibração não são porteiro dos BYTES de motor*). O ensaio de controle na mesma bancada
(`cor-rota-sysfs-sem-steam-2237`, `ensaios.csv:72`) fecha o par: sem outro
escritor, **as duas rotas obedecem** — as mesmas barras saíram do magenta escrito
por `0x31` e viraram verde escrito por `sysfs`. A rota `sysfs` **não** é rota
morta; o que a derrubava era a disputa na probe, não a rota.

**A consequência muda o que se lê de uma barra apagada:** ela **não** é o
aparelho esquecendo a cor. É alguém mandando apagar, ou escrevendo preto. A
pergunta certa deixa de ser *"por que o controle perdeu a cor?"* e passa a ser
**quem escreveu, e com que report** — e em 12/08 essa pergunta ganhou um nome
com medição no fio: ver
[a pilha do Steam Input](pilha-steam-input-xpad-sdl.md), seção 6-bis.

**Os padrões de player LED — FONTE DESTA MÁQUINA.** A tabela sai do driver, em
`assets/dkms/hid-playstation/hid-playstation.c:1836-1842`, e o comentário logo
acima (`:1831-1834`) diz de onde ela vem: *"Behavior on the PlayStation 5
console is to center the player id across the LEDs"*.

| jogador | `player_ids[N]` no fonte | valor | as cinco lâmpadas |
|---|---|---:|---|
| P1 | `BIT(2)` | 4 | `--x--` |
| P2 | `BIT(3) \| BIT(1)` | 10 | `-x-x-` |
| P3 | `BIT(4) \| BIT(2) \| BIT(0)` | 21 | `x-x-x` |
| **P4** | `BIT(4) \| BIT(3) \| BIT(1) \| BIT(0)` (`:1840`) | **27** | **`xx-xx`** |
| P5 | `BIT(4) \| BIT(3) \| BIT(2) \| BIT(1) \| BIT(0)` | 31 | `xxxxx` |

**As cinco figuras são palíndromos.** 4, 10, 21, 27 e 31 leem igual nos dois
sentidos, então **não há como errar por orientação** — a pergunta *"a figura
começa pela esquerda ou pela direita?"* não muda nenhuma das cinco, e por isso
é uma pergunta mal formulada. Este parágrafo existe para encerrá-la.

> **NOTA DATADA — 11/08/2026: o P4 já custou quatro leituras por olho, e o
> fonte resolveu em uma. Fica registrado para ninguém repetir o caminho.**
>
> Esta página atribuiu ao jogador 4, até hoje, uma figura que **é de outra
> coisa**: `x-xx-`, byte a byte o `_PLAYER_LED_OVERFLOW` de
> `core/led_control.py:119` — o padrão de *"slot fora da tabela"* (≥9),
> escolhido justamente para **não** se confundir com número de jogador nenhum.
> Alguém trocou os dois. **O código desta casa sempre esteve certo**
> (`core/led_control.py:105-114`, com o P4 em `:109`); quem estava errado era
> a página, e o número saiu.
>
> **O custo já pago, que é o motivo desta nota existir:** antes de alguém
> abrir o fonte do driver, houve **quatro tentativas de ler o padrão pelo
> olho**, e as quatro falharam — porque o que se escreveu no aparelho para
> "ver o P4" (`0x02`, `0x08`, `0x05`, `0x01`, `0x10`) são valores que a tabela
> do driver **não produz**. Não se estava olhando o P4; estava-se olhando
> figuras inventadas. Quem for medir player LED por observação escreve `27`,
> ou não está medindo o P4.
>
> **O limite desta resposta, e ele é honesto:** o fonte prova o que o **Linux**
> manda ao aparelho. Não prova o que o **console PS5** desenha — nenhum
> PS5 foi observado aqui, e o comentário do driver diz *"follow a similar
> mapping"*, que é semelhança declarada, não igualdade medida. Para o produto
> isto não muda nada: o que roda na máquina dela é o Linux.
>
> **NOTA DATADA — 11/08/2026, ponto 2: o `lightbar_setup` tem DOIS regimes
> neste produto, e esta página não os distingue.**
>
> A frase *"bit1 é o fade out"* é ALTA e continua verdadeira sobre o campo. O
> que falta é o que este projeto faz com ele, e são coisas opostas por
> transporte:
>
> - **fora de supressão (cabo):** o `flag2` sai com setup **e** brilho
>   ligados em TODO report, e o `common[41]` vai sempre zero
>   (`core/backend_pydualsense.py:818`) — escolha deliberada, travada por
>   teste;
> - **sob supressão (rádio):** o bit de setup é **explicitamente limpo**
>   (`core/backend_pydualsense.py:772-777`), porque reengatá-lo em regime
>   trava a exibição no firmware — é a `LIGHTBAR-BT-KEEPALIVE-01`.
>
> E o perigo registrado, que esta página não carregava: a
> `LIGHTBAR-BT-CLAIM-01` propôs usar o `LIGHT_OUT` para *"tomar a barra de
> volta"*. **Testado ao vivo: nenhum efeito.** Quem executasse aquela proposta
> escreveria código para APAGAR a barra achando que a acendia. GRAU: MEDIDO
> AQUI.

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

> **NOTA DATADA — 11/08/2026: o parágrafo acima está errado DUAS VEZES, e o
> título desta seção envelheceu com ele.**
>
> **(1) O byte 53 é escrito hoje.** A sprint fechou em 09/08/2026
> (`JACK-QUE-NAO-LIGOU-01`), e o caminho inteiro existe:
>
> | etapa | onde | grau |
> |---|---|---|
> | lê o byte 53 do report cru do físico | `core/physical_report_reader.py:392` (`extract_jack_status`), offset em `:142` | **ALTA** — lido no código |
> | entrega ao vpad na borda | `core/physical_report_reader.py:884-912` (`_observe_jack`) | **ALTA** |
> | o vpad espelha, mascarado nos três bits conhecidos | `integrations/uhid_gamepad.py:1747` (`forward_jack`), com `_STATUS1_BITS_CONHECIDOS = 0x07` em `:536` | **ALTA** |
> | o byte sai no report do vpad | `integrations/uhid_gamepad.py:1729`, offset `_STATUS1_OFFSET = 53` em `:526` | **ALTA** |
>
> **(2) A conclusão estava INVERTIDA — e este é o erro mais perigoso dos
> dois**, porque sobreviveria mesmo se a sprint nunca tivesse fechado. Os bits
> são de **detecção**: `HP_DETECT` **ligado** significa *"há fone"*. Com o byte
> em `0x00`, o vpad não anunciava *"fone e microfone sempre plugados"* —
> anunciava **"nada plugado"**, que é o oposto. O código diz isso com todas as
> letras em `integrations/uhid_gamepad.py:528-531`: *"O valor neutro do byte
> 53: nada plugado, nada mudo (...) é honesto, porque 'não sei' e 'não há'
> levam o jogo à mesma decisão (usar o alto-falante do controle)"*.
>
> Ou seja: o default de antes era o **melhor** possível para o caso do
> alto-falante, e não o pior. Quem lesse o parágrafo original e fosse
> "consertar" o default inverteria um byte que já estava certo.
>
> **(3) O título da seção** — *"e o byte que este projeto esquece"* — deixou
> de descrever a árvore em 09/08. Fica como está, porque decisão medida não se
> apaga, mas o byte não é mais esquecido.
>
> **NOTA DATADA — 11/08/2026: o byte 52 da tabela acima está INCOMPLETO.**
>
> A linha diz `ucBatteryLevel` (`nibble*10+5`), e isso descreve só o **nibble
> baixo**. O **nibble alto é o estado de carga**: o driver desta máquina parte
> o byte em dois campos nomeados —
> `assets/dkms/hid-playstation/hid-playstation.c:175-176`,
> `DS_STATUS0_BATTERY_CAPACITY` = `GENMASK(3, 0)` e `DS_STATUS0_CHARGING` =
> `GENMASK(7, 4)` — e o código desta casa o decodifica em cinco casos
> (`core/physical_report_reader.py:392-427`, `decodificar_bateria`):
>
> | nibble alto | significa | o que esta árvore faz |
> |---|---|---|
> | `0x0` | descarregando | `(nível*10+5, carregando=False)` |
> | `0x1` | carregando | `(nível*10+5, carregando=True)` |
> | `0x2` | cheio | `(100, carregando=True)` — o campo do vpad só sabe dizer dois estados |
> | `0xa`, `0xb`, `0xf` | erro de temperatura / carga | `(None, False)` = **"não sei"**, que não dispara alerta |
>
> A escala **não é percentual**: são **11 níveis** (5, 15, ..., 95, 100) num
> nibble. E este byte também é espelhado ao vpad desde 09/08
> (`integrations/uhid_gamepad.py:1798` `forward_battery`, saindo em `:1726`,
> offset `_STATUS_OFFSET = 52` em `:504`) — a mesma leva do byte 53.
>
> **Grau: FONTE DESTA MÁQUINA** — o `switch` de `charging_status` dentro de
> `dualsense_parse_report` está em
> `assets/dkms/hid-playstation/hid-playstation.c:1727-1753`, com o
> `min(battery_data * 10 + 5, 100)` em `:1733` e `:1737`, e o código desta casa
> aplica a mesma conta nos dois sentidos. **O grau não é mais herdado de "o
> kernel 6.18 faz assim":** é o fonte que compilou o módulo carregado agora, com
> a linha na mão. **Não medido:** o que o **jogo** faz com o número — nenhum
> jogo foi observado lendo bateria do vpad.

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

> **Acrescentado em 11/08/2026 — as TRÊS sementes de CRC-32, não uma.** Esta
> página só documentava a de saída. O mesmo CRC vale nos três sentidos, com
> semente diferente em cada um, e por Bluetooth **o feature report também é
> assinado** — os 4 últimos bytes do `0x05` lido de um físico BT são CRC, não
> calibração. Quem os tratar como dado corrompe a calibração daquela unidade.
>
> | sentido | semente | onde |
> |---|---|---|
> | saída (`HIDP DATA\|OUTPUT`) | `0xA2` | `core/ds_output_report.py:51` |
> | entrada (`HIDP DATA\|INPUT`) | `0xA1` | `core/ds_output_report.py:57` |
> | feature (`GET_REPORT` por BT) | `0xA3` | `core/ds_output_report.py:58` |
>
> GRAU: **ALTA** (`ps_check_crc32` do `hid-playstation`; as três estão em uso
> nesta árvore). As sementes são **compartilhadas com o DualShock 4** — ver a
> [canônica dos externos](externos-referencia-canonica.md).

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

> **NOTA DATADA — 12/08/2026: por que a parada do SDL funciona no APARELHO, e o
> que isso explica.** O achado do §2 (*os bits de vibração não são porteiro dos
> bytes de motor*) fecha esta seção pelo outro lado: um report com
> `valid_flag0 == 0` e motores zerados **para o motor de verdade** no DualSense
> físico, e é por isso que o SDL pode desligar a vibração assim. Quem descartava
> aquele report era o **nosso** parser de vpad, não o firmware.
>
> **GRAU: MEDIDO AQUI** para o mecanismo (§2, ensaio
> `keepalive-premissa-troca-de-lado`); **INFERIDO** para a atribuição de
> intenção ao SDL — ninguém aqui perguntou aos autores dele por que a parada tem
> essa forma. A hipótese explica o que **já** funcionava, que é a régua desta
> casa: a parada do SDL sempre funcionou no controle físico, e agora se sabe por
> quê.

---

## O que continua em aberto por falta de medição — 11/08/2026

Estas cinco linhas **não** foram resolvidas na conferência de 11/08, e nenhuma
delas se resolve lendo código: cada uma precisa do controle na mão. Estão aqui
juntas porque é assim que se ataca uma de cada vez, com variável única.

**Três perguntas entraram nesta lista em 12/08**, saídas da bancada de 11→12/08
e escritas aqui porque nenhuma delas se responde lendo arquivo:

| # | pergunta em aberto | o ensaio que a fecha | onde |
|---|---|---|---|
| 6 | de **quantos** bits de autorização o firmware precisa para vibrar? Sabe-se que o conjunto inteiro funciona e que os bytes agem sem os bits; não se sabe qual bit ainda compra alguma coisa | bancada, **um bit por vez**, com a vibração em curso e o controle na mão dela | §2 |
| 7 | os bits são porteiro dos blocos de **LED** e de **áudio**? | o mesmo desenho de troca-de-lado do §2, aplicado a cor e a volume — mudar o valor com o bit desligado e ver se muda | §2 |
| 8 | **quem** reaplica o efeito de gatilho com período de minutos? | reproduzir a rodada de 120 s do §4 com o daemon parado, e depois com ele vivo | §4 |

A **6** é a que dá lucro, porque ela é a poda — todo bit que se mostrar
dispensável pode parar de ser escrito, e foi assim que a lightbar encolheu de
cinco canais para um.

| # | pergunta em aberto | o ensaio que a fecha | onde |
|---|---|---|---|
| 1 | o áudio de saída por Bluetooth sai no `0x32` ou no `0x39`? | ler o *report descriptor* por BT e listar os IDs de output com o tamanho declarado — **leitura pura, sem escrita** | §3 |
| 2 | `weapon()` e `vibration()` fazem alguma coisa no gatilho? | aplicar os dois pela aba Gatilhos, daemon vivo, e perguntar o que o dedo sente | §4 |
| 3 | a taxa que o **SDL declara** ao jogo para o vpad Edge: 250 ou 1000 Hz? | medir **contra a SDL3 que a Steam distribui** — nunca contra a `libSDL2` do sistema. A taxa do **aparelho** já está medida (§5) | §5 |
| 4 | o bit `0x10` (autorização do volume do fone) existe neste firmware? | com headset no jack, variar `common[4]` com e sem o bit e ouvir | §2 |
| 5 | a curva do volume do alto-falante **com** o pré-amp ligado | refazer a curva pelo caminho de hoje; a de 01/08 mediu um código que não existe mais | §3 |

**Duas perguntas saíram desta lista em 11/08, e é bom saber para onde foram:**
o padrão do player LED do **jogador 4** foi respondido pelo **fonte do driver**,
e a §5 traz a tabela e a ressalva do que o fonte não cobre (o console PS5); e a
**taxa do aparelho** foi medida nos dois transportes, também na §5 — o que
sobrou dela é a pergunta 3 acima, que é do lado do SDL, não do lado do controle.

A pergunta 3 tem irmão já medido no aparelho vizinho (o Pro declara 8 ms e
entrega 11,2 ms) — ver a
[canônica dos externos](externos-referencia-canonica.md), seção 3.5. Isso torna
a hipótese plausível; **não** a torna provada aqui.

A régua de paridade entre transportes, e o que já está medido em cada um, mora
em [paridade Bluetooth × cabo](paridade-bluetooth-versus-cabo.md).

---

## 9. Fontes

**Toda URL desta lista está fixada em tag ou commit**, pela régua de fonte do
topo desta página: `master` e `main` andam, e uma citação de linha contra eles
apodrece sozinha. Quem acrescentar fonte aqui fixa também.

**Oficiais / semi-oficiais**
- `hid-playstation.c` **como roda nesta máquina** — a fonte que esta página
  cita por linha: `assets/dkms/hid-playstation/hid-playstation.c` desta árvore.
  Proveniência, `sha256` e a lista de patches em
  `assets/dkms/hid-playstation/patch/BASELINE`; o vanilla veio de
  `https://raw.githubusercontent.com/pop-os/linux/3af2f9de43174ce5063110f94b7b01226499ba13/drivers/hid/hid-playstation.c`
- `isteamdualsense.h` (header da Sony no Steamworks SDK), fixado no commit —
  `https://github.com/rlabrecque/SteamworksSDK/blob/df2baabf574a738ef1ea90a7e89339107fc0a279/public/steam/isteamdualsense.h`
- `hid-playstation.c` (kernel mainline, autor da SIE), fixado na tag `v7.0` —
  `https://github.com/torvalds/linux/blob/v7.0/drivers/hid/hid-playstation.c`
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
- `SDL_hidapi_ps5.c`, fixado na tag `release-3.4.14` —
  `https://github.com/libsdl-org/SDL/blob/release-3.4.14/src/joystick/hidapi/SDL_hidapi_ps5.c`
- SAxense (haptics por BT) — `https://github.com/egormanga/SAxense`
- DS5Dongle (mic por BT, fonte canônica) — `https://github.com/awalol/DS5Dongle`

**Caminho do jogo**
- Proton, DualSense advanced features —
  `https://github.com/ValveSoftware/Proton/issues/5900`
- Wine + DualSense por hidraw —
  `https://nick.tay.blue/2024/01/21/wine-dualsense/`
- `dualsense-games-compat-check` (replica o que os jogos fazem) —
  `https://github.com/ClearlyClaire/dualsense-games-compat-check`
