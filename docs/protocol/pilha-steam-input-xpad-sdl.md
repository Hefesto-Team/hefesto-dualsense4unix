# A pilha Steam Input × xpad × SDL — a camada entre o controle e o jogo

**A fonte única de verdade deste projeto sobre o que acontece com um controle
DEPOIS que ele sai do driver e ANTES de o jogo lê-lo.**

- **Levantado em:** 11/08/2026, contra o código das quatro camadas e contra os
  binários instalados **na máquina dela**.
- **Por que este arquivo existe:** as três referências que esta casa já tinha
  descrevem o **aparelho** (o DualSense, o Pro, o 8BitDo). Nenhuma descreve os
  três programas que disputam esse aparelho — o `xpad` do kernel, o Steam Input
  e o SDL —, e é justamente aí que moram as regressões que voltam: o controle
  dobrado, o terceiro controle fantasma, a vibração que não chega, a taxa de
  giroscópio que ninguém confere.
- **Leitura pura.** Nada foi escrito, nenhum serviço reiniciado, nenhum controle
  derrubado. As medições desta página são `strings(1)`, `grep` e leitura de
  arquivo — a Steam estava **fechada** durante o levantamento, e há um item
  explícito na seção 7 que só se fecha com ela aberta.
- **Documentos irmãos:** a
  [referência canônica do DualSense](dualsense-referencia-canonica.md) (o
  aparelho da Sony), a
  [canônica dos externos](externos-referencia-canonica.md) (Pro e 8BitDo) e a
  [paridade Bluetooth × cabo](paridade-bluetooth-versus-cabo.md) (o transporte).
  Quando esta página e uma delas discordarem, **cada uma vence no seu escopo**:
  as outras falam do que o controle entende, esta fala do que a pilha do PC faz
  com ele.
- **Regra de uso:** esta página vence sobre docstring e comentário — mas só nas
  linhas marcadas ALTA ou MEDIDO AQUI.

---

## 0. Como ler esta página

### 0.1 Os graus

Os mesmos das outras canônicas, pelo mesmo motivo: esta casa já tomou decisão
errada por confundir "documentação de comunidade" com "fato".

| grau | significa |
|---|---|
| **ALTA** | está no código-fonte citado com `arquivo:linha`, lido nesta sessão |
| **MÉDIA** | documentação de projeto respeitado, ou binário desta máquina que confirma o mecanismo sem mostrar a lógica |
| **BAIXA** | inferência, ou fonte única |
| **MEDIDO AQUI** | conferido nesta máquina, em 11/08/2026, com o comando citado |
| **NÃO MEDIDO** | escrito para ser medido depois; nenhum número existe |

### 0.2 A régua — contra QUE versão cada linha foi lida

Esta seção não é formalidade. A armadilha nº 1 desta casa é *medir contra a
biblioteca errada*: em 01/08 o gamepad virtual foi medido contra a `libSDL2` do
sistema e concluiu-se que ele não entregava nada — a biblioteca que os jogos
usam entrega tudo.

| camada | de onde vem o código citado | o que roda na máquina dela |
|---|---|---|
| `xpad` | `torvalds/linux`, **tag `v7.0`**, `drivers/input/joystick/xpad.c` (2346 linhas) | **MEDIDO AQUI:** kernel `7.0.11-76070011-generic`, `CONFIG_JOYSTICK_XPAD=m`, `CONFIG_JOYSTICK_XPAD_FF=y`, `CONFIG_JOYSTICK_XPAD_LEDS=y` |
| `hid-playstation` | `torvalds/linux`, tag `v7.0` | DKMS desta casa, ver a canônica dos externos §1.1 |
| SDL3 | `libsdl-org/SDL`, branch `main`, buscado em 11/08/2026 | **MEDIDO AQUI:** a que a Steam distribui é `SDL-release-3.4.0-1163-g2d7f30078` (`steamrt64/libSDL3.so.0`, de 21/07) |
| SDL2 | `libsdl-org/SDL`, branch `SDL2` | **MEDIDO AQUI:** `libSDL2-2.0.so.0.3200.10` nos `pinned_libs` do runtime |
| `winebus.sys` | `ValveSoftware/wine`, branch `proton_10.0` | **MEDIDO AQUI:** Proton 10.0 e 11.0 instalados, mais GE-Proton 10-34, 11-1 e 11-3 |
| Steam Input | `strings(1)` no `steamclient.so` | **MEDIDO AQUI:** `ubuntu12_32/steamclient.so` da instalação dela |

ATENÇÃO: **os números de linha do `xpad` mudam entre versões.** O `master` do
kernel estava em `7.2.0-rc7` no dia deste levantamento e tem numeração
diferente da `v7.0` citada aqui. Quem for reconferir tem de declarar a tag,
como esta página declara.

---

## 1. O driver `xpad` — o Xbox 360 no Linux

### 1.1 O que ele é, e o que ele NÃO é

O `xpad` é um driver **USB puro**, não um driver HID. Ele não passa pelo
subsistema `hid`; casa direto na interface USB de classe proprietária da
Microsoft e monta um `input_dev` à mão. Consequência prática que importa aqui:
**um controle sob `xpad` não tem `hidraw`.** Não há canal cru para o espaço de
usuário; tudo que existe é evdev.

Isto é metade da explicação da máscara Xbox 360 deste projeto (a outra metade
está em 1.6): quem fala Xbox 360 fala **só evdev**, e por isso o vpad de
`integrations/uinput_gamepad.py` — que é evdev e nada mais — funciona
perfeitamente naquela máscara e não funciona na máscara DualSense.

**GRAU: ALTA** (`xpad.c` é `drivers/input/joystick/`, usa `usb_driver`,
`usb_fill_int_urb` e `input_allocate_device`; não há uma linha de `hid_*`).

### 1.2 Os endpoints

O probe pega os **dois primeiros endpoints de interrupção** da altsetting — um
IN, um OUT — e recusa o aparelho se faltar qualquer um dos dois:

```c
    for (i = 0; i < 2; i++) {
        struct usb_endpoint_descriptor *ep = &intf->cur_altsetting->endpoint[i].desc;
        if (usb_endpoint_xfer_int(ep)) {
            if (usb_endpoint_dir_in(ep))  ep_irq_in  = ep;
            else                          ep_irq_out = ep;
        }
    }
    if (!ep_irq_in || !ep_irq_out) { error = -ENODEV; goto err_free_in_urb; }
```

`xpad.c:2149-2164` (tag `v7.0`). A URB de entrada é preenchida logo abaixo, em
`:2170-2173`, com **`XPAD_PKT_LEN` = 64 bytes de buffer** (`xpad.c:74`) e o
`bInterval` **do próprio descritor do aparelho** — o driver não impõe taxa
nenhuma. A URB de saída nasce em `xpad_init_output`, `xpad.c:1441-1444`, com o
mesmo buffer de 64 e o `bInterval` do endpoint OUT.

**GRAU: ALTA** — código lido.

> **O buffer de 64 não é o tamanho do pacote.** É o teto alocado; o Xbox 360
> preenche 20 bytes dele. Confundir os dois números é fácil e produz
> engenharia reversa errada.

### 1.3 O pacote de entrada de 20 bytes

O layout vem do **free60**, e é o próprio driver que diz isso — o comentário
acima de `xpad360_process_packet` cita a URL da wiki como procedência
(`xpad.c:886-894`).

| byte | conteúdo | quem lê no driver |
|---|---|---|
| 0 | tipo da mensagem; tem de ser `0x00` | `xpad.c:899-901` (`if (data[0] != 0x00) return;`) |
| 1 | tamanho, `0x14` = 20 | **ninguém** no caminho com fio |
| 2 | direcional (bits 0-3), Start (4), Back (5), L3 (6), R3 (7) | `xpad.c:904-932` |
| 3 | LB (0), RB (1), Guide (2), A (4), B (5), X (6), Y (7) | `xpad.c:934-941` |
| 4 | gatilho esquerdo, 0-255 | `xpad.c:957-964` |
| 5 | gatilho direito, 0-255 | `xpad.c:957-964` |
| 6-7 | analógico esquerdo X, `s16` little-endian | `xpad.c:945-946` |
| 8-9 | analógico esquerdo Y, `s16` **invertido** (`~`) | `xpad.c:947-948` |
| 10-11 | analógico direito X, `s16` | `xpad.c:951-952` |
| 12-13 | analógico direito Y, `s16` **invertido** | `xpad.c:953-954` |
| 14-19 | **não lidos por este driver** | — |

**GRAU do que o driver lê: ALTA** (código). **GRAU do "são 20 bytes e o byte 1
é `0x14`": MÉDIA** — é documentação de comunidade (free60), citada pelo próprio
kernel, e o caminho com fio **nunca confere** esse byte. Só o caminho sem fio
(`xpad360w_process_packet`, `xpad.c:1025-1049`) olha o cabeçalho: exige
`data[1] == 0x1` para considerar os dados válidos e então chama o mesmo parser
deslocado de quatro bytes (`&data[4]`).

**O que sobra é o ponto desta seção:** treze bytes descrevem o controle inteiro.
Não há campo de sensor, não há campo de toque, não há campo de bateria. Volte a
isto em 1.5.

### 1.4 O pacote de rumble

Oito bytes, escritos pelo `input_ff_create_memless`:

```c
    case XTYPE_XBOX360:
        packet->data[0] = 0x00;
        packet->data[1] = 0x08;
        packet->data[2] = 0x00;
        packet->data[3] = strong / 256;  /* left actuator? */
        packet->data[4] = weak / 256;    /* right actuator? */
        packet->data[5] = 0x00;
        packet->data[6] = 0x00;
        packet->data[7] = 0x00;
        packet->len = 8;
```

`xpad.c:1582-1592`. As interrogações nos comentários são **do kernel**, não
desta página.

Registro do efeito: `xpad_init_ff` declara `EV_FF`/`FF_RUMBLE` e usa
`input_ff_create_memless` (`xpad.c:1640-1648`). *Memless* significa que o
kernel não guarda efeito nenhum no aparelho: cada `EVIOCSFF`/`write` do jogo é
convertido em um pacote e enviado. O contraste com o DualSense é total — ver 6.2.

Escalas: `strong`/`weak` são `u16` do evdev e viram um byte cada (`/256`). O
Xbox One divide por 512 (`xpad.c:1621-1622`), o Xbox original tem layout
próprio. **GRAU: ALTA.**

### 1.5 POR QUE o layout Xbox 360 não tem giroscópio nem touchpad

Esta é a seção que ela pediu por escrito, e a resposta tem **três camadas
independentes**. Não é uma limitação do Linux, nem uma escolha do driver — é o
protocolo.

**(a) O protocolo não carrega o dado.** O pacote de 1.3 tem vinte bytes, dos
quais treze são consumidos e seis nunca foram documentados como nada. Não há
lugar para três eixos de giroscópio (6 bytes), três de acelerômetro (6 bytes) e
dois pontos de toque (8 bytes) — o pacote inteiro teria de crescer, e ele é
fixo desde 2005. **GRAU: ALTA para "o driver não lê"; MÉDIA para "o hardware
não manda"** (o controle de Xbox 360 fisicamente não tem IMU nem touchpad; isso
é fato de produto, não leitura de código).

**(b) O driver não declara a capacidade.** `xpad_init_input` (`xpad.c:1958`)
percorre exatamente cinco tabelas, e todas cabem numa tela:

| tabela | conteúdo | linha |
|---|---|---|
| `xpad_common_btn` | A, B, X, Y, Start, Select, L3, R3 | `xpad.c:439-443` |
| `xpad360_btn` | LB, RB, Guide (`BTN_MODE`) | `xpad.c:464-468` |
| `xpad_abs` | `ABS_X`, `ABS_Y`, `ABS_RX`, `ABS_RY` — **os dois analógicos** | `xpad.c:470-474` |
| `xpad_abs_pad` | `ABS_HAT0X`, `ABS_HAT0Y` — o direcional | `xpad.c:477-480` |
| `xpad_abs_triggers` | `ABS_Z`, `ABS_RZ` — os gatilhos | `xpad.c:483-486` |

Mais `xpad_btn_paddles` (`xpad.c:489-493`) para os aparelhos com `MAP_PADDLES`,
e `ABS_PROFILE` para o Xbox Adaptive Controller.

**Não existe uma única chamada a `input_set_capability` de `EV_ABS` fora dessa
lista.** Nenhum `ABS_MT_*` (o touchpad multitoque do evdev), nenhum
`INPUT_PROP_POINTER`, nenhum device secundário de sensores. A régua dos eixos
está em `xpad_set_up_abs` (`xpad.c:1918-1947`): analógicos `-32768..32767` com
fuzz 16 e flat 128; gatilhos `0..255` (`0..1023` no Xbox One); direcional
`-1..1`. **GRAU: ALTA.**

**(c) O contraste que fecha o argumento.** O `hid-playstation` registra, para um
único DualSense, **quatro nós de entrada**: o gamepad, o `Motion Sensors`, o
`Touchpad` e o `Headset Jack`. O `xpad` registra **um**
(`input_register_device(xpad->dev)`, `xpad.c:2053`) mais, opcionalmente, um
`led_classdev` para o anel de quatro quadrantes (`xpad_led_probe`,
`xpad.c:1743`). Um aparelho, um nó, sete eixos.

**A consequência para este projeto, e é ela que custa:** a máscara Xbox 360
(`045e:028e`, `integrations/uinput_gamepad.py:54-56`) **não tem onde pôr**
giroscópio, touchpad, lightbar RGB, gatilhos adaptativos ou bateria. Não é bug
nosso nem falta de trabalho: é o formato do aparelho que estamos imitando.
Quem escolhe a máscara Xbox escolhe **rumble por evdev que funciona em tudo** e
paga com as cinco features. Quem escolhe a máscara DualSense recupera as cinco
e passa a depender do `hidraw` — que é onde a seção 3 começa.

Essa troca já estava medida na matriz de paridade e nas notas de
`integrations/uhid_gamepad.py:1-12`; o que faltava era **a explicação escrita**,
e ela é esta.

### 1.6 O nome que o `xpad` empresta ao mundo

Uma linha da tabela de aparelhos importa fora do driver:

```c
    { 0x045e, 0x028e, "Microsoft X-Box 360 pad", 0, XTYPE_XBOX360 },
```

`xpad.c:157`. Guarde a string. Ela reaparece na seção 2 **sem o driver**.

---

## 2. O espelho do Steam Input

### 2.1 O fato, já medido nesta casa

Registrado na
[TRES-CONTROLES-01](../process/sprints/2026-08-10-TRES-CONTROLES-01-o-espelho-do-espelho-no-pragmata.md),
**MEDIDO** no `/dev/input` dela com o jogo aberto, um controle físico na mão e
quatro aparelhos na lista:

| nó | nome | VID:PID | quem é |
|---|---|---|---|
| `event2` | Sony ... DualSense Wireless Controller | `054c:0ce6` | o físico |
| `event6` | DualSense Wireless Controller (Hefesto P1) | `054c:0df2` | o vpad deste projeto |
| `event21` | Microsoft X-Box 360 pad 0 | `28de:11ff` | Steam Input |
| `event23` | Microsoft X-Box 360 pad 1 | `28de:11ff` | Steam Input |

**O Steam Input faz um espelho Xbox de CADA controle que enxerga — inclusive do
gamepad virtual deste projeto.** Dois controles vistos, dois espelhos criados.

### 2.2 O mecanismo — como o espelho nasce

**MEDIDO AQUI, 11/08/2026**, por `strings(1)` no
`~/.steam/debian-installation/ubuntu12_32/steamclient.so`:

```
Couldn't initialize virtual gamepad: Couldn't open /dev/uinput for writing
Couldn't initialize virtual gamepad: Couldn't write device description
Couldn't initialize virtual gamepad: Couldn't configure axes
Couldn't initialize virtual gamepad: Couldn't configure buttons
Couldn't initialize virtual gamepad: Couldn't configure haptics
Microsoft X-Box 360 pad %u
/dev/uinput
%s/%s/virtualgamepadinfo.txt
SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD
SteamVirtualGamepadInfo
SteamVirtualGamepadInfo_Proton
```

Isto fecha o mecanismo inteiro, e cada linha responde a uma pergunta:

1. **Como o Steam cria o espelho:** abrindo `/dev/uinput` e escrevendo uma
   descrição de device — o **mesmo** mecanismo que este projeto usa no vpad de
   `integrations/uinput_gamepad.py`. Não é HID, não é kernel driver, não é
   `xpad`: é um evdev sintético. Foi por isso que a TRES-CONTROLES-01 encontrou
   o processo `steam` como o único com `/dev/uinput` aberto além do
   `input-remapper` do sistema.
2. **Com que nome:** `Microsoft X-Box 360 pad %u` — a string da seção 1.6, com
   um índice colado. O Steam **imita o nome do driver `xpad`** para que
   qualquer jogo que reconheça "um Xbox 360" reconheça o espelho, mas o
   aparelho não passa pelo `xpad` em ponto nenhum.
3. **Com que VID/PID:** `28de:11ff` — Valve, não Microsoft. O par está nomeado
   no SDL como `USB_VENDOR_VALVE` (`usb_ids.h:68`) e
   `USB_PRODUCT_STEAM_VIRTUAL_GAMEPAD` (`usb_ids.h:208`), e classificado como
   `k_eControllerType_UnknownNonSteamController` em `controller_list.h:665`.
   **A dissociação nome × identidade é o ponto:** quem procurar por nome acha um
   Xbox 360; quem procurar por VID/PID acha a Valve. Ferramentas que casam por
   nome (inclusive as nossas) veem uma coisa; o SDL vê outra.
4. **Como o jogo distingue um espelho do outro:** pelo arquivo
   `virtualgamepadinfo.txt`, cujo caminho o Steam exporta na variável
   `SteamVirtualGamepadInfo` (e `SteamVirtualGamepadInfo_Proton` para o lado
   Windows).

**GRAU dos quatro pontos: MEDIDO AQUI** para a existência das strings no
binário dela; **ALTA** para o significado de cada uma, que vem do código do SDL
citado abaixo.

### 2.3 Como o SDL lê o espelho

Três funções, todas em `libsdl-org/SDL` branch `main`:

- **Reconhecimento por VID/PID**, `SDL_joystick.c:3334-3341`:

  ```c
  bool SDL_IsJoystickSteamVirtualGamepad(Uint16 vendor_id, Uint16 product_id, Uint16 version)
  {
  #ifdef SDL_PLATFORM_MACOS
      return (vendor_id == USB_VENDOR_MICROSOFT && product_id == USB_PRODUCT_XBOX360_WIRED_CONTROLLER && version == 0);
  #else
      return (vendor_id == USB_VENDOR_VALVE && product_id == USB_PRODUCT_STEAM_VIRTUAL_GAMEPAD);
  #endif
  }
  ```

  ATENÇÃO: **no macOS o critério é `045e:028e` com `version == 0`** — que é
  exatamente o par da máscara Xbox 360 deste projeto
  (`integrations/uinput_gamepad.py:54-55`). No Linux isso **não** acontece, e
  esta página só se responsabiliza pelo Linux; mas quem um dia portar o projeto
  precisa saber que a colisão existe. **GRAU: ALTA.**

- **Descoberta e ordenação**, `SDL_sysjoystick.c:867-915`: o SDL varre
  `/dev/input`, filtra por `USB_VENDOR_VALVE`/`USB_PRODUCT_STEAM_VIRTUAL_GAMEPAD`
  e extrai o **slot** do nome, procurando a substring `"pad "` seguida de
  dígito (`GetSteamVirtualGamepadSlot`, `SDL_sysjoystick.c:237-252`). É por isso
  que o `%u` do `steamclient.so` importa: o número no nome **é** a ordem dos
  jogadores. Os espelhos são então ordenados por slot antes de qualquer outro
  joystick. **GRAU: ALTA.**

- **Nome e identidade que o jogo vê**, `SDL_steam_virtual_gamepad.c:141-150`: o
  SDL só liga esse caminho se a variável `SteamVirtualGamepadInfo` existir no
  ambiente do jogo, e o desliga de propósito quando o executável é
  `wine64-preloader` (*"Wine launched by Steam, ignoring SteamVirtualGamepadInfo"*
  — string presente também no `libSDL3.so.0` dela, **MEDIDO AQUI**). **GRAU: ALTA.**

### 2.4 O ramo que decide se o espelho chega ao jogo — e ele vem ANTES da lista de ignorados

Este é o achado mais importante desta página, e ele **qualifica** a cura da
TRES-CONTROLES-01 sem derrubá-la.

`SDL_gamepad.c:3273-3331` (SDL3) e `SDL_gamecontroller.c:2119-2177` (SDL2) têm o
**mesmo** corpo, na mesma ordem:

```c
    const char *hint = SDL_getenv_unsafe("SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD");
    bool allow_steam_virtual_gamepad = SDL_GetStringBoolean(hint, false);
    ...
    if (SDL_IsJoystickSteamVirtualGamepad(vendor_id, product_id, version)) {
        return !allow_steam_virtual_gamepad;          /* <= retorna AQUI */
    }

    if (SDL_allowed_gamepads.num_included_entries > 0) { ... }
    else {
        if (SDL_VIDPIDInList(vendor_id, product_id, &SDL_ignored_gamepads)) return true;
        return false;
    }
```

Leia a ordem: **para o par `28de:11ff`, a função retorna antes de consultar
`SDL_GAMECONTROLLER_IGNORE_DEVICES`.** Portanto, do ponto de vista do SDL:

- com `SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD` **ausente ou 0**, o SDL
  já ignora os espelhos sozinho — e o par `0x28de/0x11ff` que este projeto
  acrescentou ao `_IGNORE_VALUE` (`daemon/launch_env.py:138`, emitido em `:289-291`) é
  **redundante**, não errado;
- com a variável **em 1**, o SDL usa os espelhos — e aquele par **não os
  esconde**, porque a lista de ignorados nunca é consultada para ele.

**GRAU: ALTA** — código lido nas duas gerações do SDL, e a variável está
presente por nome no `steamclient.so` dela (**MEDIDO AQUI**).

**O que isto NÃO diz.** Não diz que a cura da TRES-CONTROLES-01 é inútil: um
jogo pode não usar SDL (título nativo com input próprio, Unity antigo, ou um
executável Windows que só enxerga o mundo pelo `winebus`), e nesses caminhos o
par não passa por este ramo.

### 2.4-bis MEDIDO EM JOGO — 11/08/2026

O item que a seção 7 listava como não medido foi medido no mesmo dia, com um
jogo em sessão (`AppId 1599660`, que está na allowlist de exceção dela) e os
controles na mesa. Instrumento: `scripts/medir_steam_virtual_gamepad.sh`,
leitura pura de `/proc/<pid>/environ`.

**1. A variável está em 1, e no processo do jogo.**
`SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD=1` apareceu em cinco processos
da árvore da Steam, incluindo o `reaper SteamLaunch` e o binário do jogo. **A
suspeita estava certa quanto ao mecanismo:** o atalho vence, e o par
`0x28de/0x11ff` do nosso `_IGNORE_VALUE` não esconde espelho nenhum.

**2. E, ainda assim, o defeito NÃO se manifesta — porque não há espelho.**
Varredura de `/sys/class/input` com o jogo rodando: nenhum dispositivo
`X-Box 360 pad` nem `Steam Virtual`. O atalho autoriza um aparelho que a Steam
não criou. O par continua **redundante**, agora por medição e não por leitura.

**3. A metade que importa da nossa lista funciona, e é outra.** O jogo recebeu
`SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6,0x28de/0x11ff`. O primeiro par
é o DualSense **físico** — ele **não** passa pelo atalho (não é o gamepad
virtual da Steam), então é consultado pelo caminho normal. É ele que faz o jogo
enxergar os vpads em vez dos físicos. Também chegou
`PROTON_DISABLE_HIDRAW=0x054C/0x0CE6`, escondendo só o físico e deixando o
`0x0DF2` do vpad intacto — que é o desenho.

**4. O quadro de dispositivos no momento da medição**, e ele fecha a história:
dois DualSense físicos (`054c:0ce6`), **dois vpads do Hefesto** (`054c:0df2`,
P1 e P2), dois controles Nintendo, e **zero espelhos**. O co-op de dois
jogadores estava de pé, num jogo com exceção de Steam Input ativa — que é
exatamente o que `docs/usage/jogos-e-mascaras.md` afirmava ser impossível até
ser corrigido no mesmo dia.

**5. O ACEITE DELA, no mesmo jogo, e é o que decide.** Palavras dela: *"na hora
do vamos ver os 4 conectaram certinho. cada qual com seu player rumble e
afins"*. Quatro controles, cada um com o seu número, a sua vibração e o resto —
com a exceção de Steam Input ativa naquele appid.

Isso fecha o par que este documento vinha perseguindo. A leitura do fonte
previa um risco real; a medição de ambiente confirmou o mecanismo e mostrou que
ele não tem alvo; e o olho dela confirmou o resultado. **Os três concordam**, e
é raro — na maior parte desta sessão eles discordaram, e foi por isso que a
sessão existiu.

**GRAU: MEDIDO AQUI.** O que continua sem medição é o comportamento com um
título que **use** o espelho: se um dia a Steam voltar a criá-lo, o atalho
passa a decidir, e aí o par vira o problema que a leitura do fonte previu. O
instrumento fica no repositório justamente para isso — é uma linha de comando,
com a Steam aberta.

### 2.5 O que faz o jogo escolher um dispositivo ou outro

Quatro critérios, em ordem de força:

1. **O que o jogo consegue ver.** Um aparelho escondido por `IGNORE_DEVICES` não
   é escolhido porque não existe para a biblioteca. É o único critério que este
   projeto controla.
2. **A ordem de enumeração.** O SDL põe os espelhos do Steam **por slot, antes
   dos demais** (`SDL_sysjoystick.c:867-915`). Um jogo que atribui jogador 1 ao
   primeiro joystick da lista escolhe o espelho.
3. **O tipo declarado.** O espelho é um Xbox 360 (prompts Xbox, mapeamento
   `xinput`); o vpad em máscara DualSense é um PS5 Edge (prompts PlayStation).
   Jogos que preferem um layout específico usam isto.
4. **O nome.** Jogos que casam por substring — `"Wireless Controller"` para
   DualSense, `"X-Box 360"` para Xbox — decidem por aqui, e é por isso que a
   canônica do DualSense exige aquela substring no item 4 do checklist do §7.

---

## 3. A desduplicação por VID/PID

### 3.1 `SDL_GAMECONTROLLER_IGNORE_DEVICES` — onde funciona de verdade

O hint é lido **uma vez**, na inicialização do subsistema
(`SDL_LoadVIDPIDList(&SDL_ignored_gamepads)`, `SDL_gamepad.c:3030-3031`; em
SDL2, `SDL_gamecontroller.c:1932-1933`), e consultado em **dois** pontos que
importam:

- **na camada de gamepad**, `SDL_ShouldIgnoreGamepad` (o corpo de 2.4) — decide
  se o aparelho vira um `SDL_Gamepad`;
- **na camada HIDAPI**, `SDL_hidapijoystick.c:384-386`:

  ```c
    if (SDL_ShouldIgnoreJoystick(device->vendor_id, device->product_id, device->version, device->name)) {
        return NULL;
    }
  ```

  ou seja, o aparelho ignorado **nem recebe driver HIDAPI**. É por este segundo
  ponto que esconder o `054c:0ce6` tira o físico do caminho do rumble e da
  lightbar do jogo, não só da lista de joysticks. `SDL_ShouldIgnoreJoystick`
  (`SDL_joystick.c:3563-3579`) chama `SDL_ShouldIgnoreGamepad` no fim, depois de
  duas listas internas.

**Formato:** lista de `0xVID/0xPID` separada por vírgula. **GRAU: MÉDIA** — é o
formato documentado do hint, é o que o próprio Proton escreve na variável irmã
(3.4), e é o que esta casa usa desde sempre. O parser propriamente dito
(`SDL_LoadVIDPIDList`) não foi lido nesta sessão.

**SDL2 e SDL3 são equivalentes neste ponto.** Os dois corpos foram comparados
lado a lado; a diferença é só de nomes (`controllers` virou `gamepads`,
`SDL_bool` virou `bool`). **GRAU: ALTA.**

> Isto **promove** a nota de `daemon/launch_env.py:190-199`, que registrava
> honestamente "SUSPEITA COM MECANISMO (forte; nenhum parser do SDL foi
> executado)". O parser continua não executado — mas o **caminho de decisão**
> agora está lido linha a linha, nas duas gerações. O que falta para virar
> MEDIDO é rodar, não ler.

### 3.2 Por que ele NÃO cobre o `winebus.sys` do Proton

Porque o `winebus` não é SDL e não lê hint nenhum do SDL. **GRAU: ALTA, por
ausência conferida:** um `grep` por `SDL_GAMECONTROLLER`, `SDL_JOYSTICK` e
`IGNORE_DEVICES` em `dlls/winebus.sys/main.c` (`ValveSoftware/wine`, branch
`proton_10.0`, 1830 linhas) devolve **zero linhas**.

O que o `winebus` faz é entregar, ou não, o `hidraw` do aparelho ao mundo
Windows. E ele tem uma preferência embutida pela família Sony:

```c
    if (is_dualshock4_gamepad(vid, pid)) prefer_hidraw = TRUE;
    if (is_dualsense_gamepad(vid, pid)) prefer_hidraw = TRUE;
```

`dlls/winebus.sys/main.c:600-601`. E o predicado:

```c
static inline BOOL is_dualsense_gamepad(WORD vid, WORD pid)
{
    if (vid != 0x054c) return FALSE;
    if (pid == 0x0ce6) return TRUE; /* DualSense */
    if (pid == 0x0df2) return TRUE; /* DualSense Edge */
    return FALSE;
}
```

`dlls/winebus.sys/unixlib.h:201-207`. **A família inteira — o físico `0ce6` E o
vpad `0df2` — recebe `hidraw` por padrão.** É exatamente o que a GUERRA-01
desta casa afirmava por medição indireta; agora está lido no fonte.

**GRAU: ALTA.**

### 3.3 O que `PROTON_DISABLE_HIDRAW` resolve — o parser, lido

```c
    if (options.disable_hidraw) return FALSE;

    if (!RtlQueryEnvironmentVariable(NULL, L"PROTON_DISABLE_HIDRAW", 21, value, ARRAY_SIZE(value) - 1, &len))
    {
        value[len] = 0;
        if (!wcscmp(value, L"1")) return FALSE;
        swprintf(vidpid, ARRAY_SIZE(vidpid), L"0x%04X/0x%04X", vid, pid);
        if (wcscasestr(value, vidpid)) return FALSE;
    }
```

`dlls/winebus.sys/main.c:543-562`. Quatro consequências, todas **ALTA**:

1. **`PROTON_DISABLE_HIDRAW=1` nega `hidraw` a TODO aparelho.** Nunca usar.
2. A agulha é montada com o molde **WIDE** `L"0x%04X/0x%04X"` — o prefixo `0x` e
   os quatro dígitos com zero à esquerda **fazem parte da busca**.
3. A busca é `wcscasestr`, isto é, **substring, sem caixa**. Logo: a caixa é
   indiferente e o **separador é livre** — a vírgula que este projeto usa serve
   porque nada exige vírgula, e um par nunca é subcadeia de outro.
4. A variável é consultada **antes** da lista de registro e antes de
   `PROTON_ENABLE_HIDRAW` (`main.c:571-578`), então negar vence.

**Isto CONFIRMA, por leitura de fonte, o que `daemon/launch_env.py:180-189`
registrava como MEDIDO por `strings(1)`.** As mesmas cadeias estão no binário
dela: `strings -a -el` no
`Proton 10.0/files/lib/wine/x86_64-windows/winebus.sys` devolve
`PROTON_DISABLE_HIDRAW`, `PROTON_ENABLE_HIDRAW` e `0x%04X/0x%04X`
(**MEDIDO AQUI, 11/08/2026**).

**A divisão de trabalho, escrita de uma vez:**

| variável | atua sobre | esconde do jogo? | tira o `hidraw`? |
|---|---|---|---|
| `SDL_GAMECONTROLLER_IGNORE_DEVICES` | SDL (jogo nativo, e o SDL interno do Proton quando usado) | **sim** | por tabela — o aparelho ignorado não recebe driver HIDAPI |
| `PROTON_DISABLE_HIDRAW` | `winebus.sys` (jogo Windows sob Proton) | não | **sim** |

Uma não substitui a outra. Emitir só a primeira deixa o jogo Windows escrevendo
no `hidraw` do físico — a "guerra de escritores" de lightbar e rumble. Emitir só
a segunda deixa o jogo nativo vendo dois controles.

### 3.4 A mina do próprio Proton — `0x0DF2` numa lista da Valve

**MEDIDO AQUI**, nos dois Protons instalados:

```python
        if (os.environ.get("SteamGameId", 0) == "2322010" and    # God of War: Ragnarok
            os.environ.get("SteamDeck", 0) == "1"):
            # Disable hidraw for Sony DualShock and DualSense controllers.
            self.env["PROTON_DISABLE_HIDRAW"] = "0x054C/0x05C4,0x054C/0x09CC,0x054C/0x0BA0,0x054C/0x0CE6,0x054C/0x0DF2"
```

`Proton 10.0/proton`, linha 1825-1828; idêntico em `Proton 11.0/proton`, linha
1873-1876.

Três leituras, e a terceira é a que importa:

1. É **atribuição**, não acréscimo: se disparar, **substitui** o valor que o
   wrapper exportou.
2. A lista inclui `0x054C/0x0DF2` — o PID do nosso vpad. Se disparar, o vpad
   perde `hidraw`, e com ele rumble, gatilhos e lightbar do jogo. É precisamente
   o que `daemon/launch_env.py:293-299` proíbe em letras maiúsculas
   (*"NUNCA incluir 0x0DF2"*).
3. **Ela não pode disparar nesta máquina**: exige `SteamDeck == "1"`, e este PC
   não é um Deck. **GRAU: ALTA** — a condição está no fonte, lida.

Fica registrado porque é a única lista da Valve, hoje, que casa com o PID que
este projeto escolheu — e porque `SteamGameId` e `SteamDeck` são variáveis de
ambiente, não hardware.

### 3.5 A escolha do PID `0x0DF2` — os efeitos colaterais que EXISTEM

O vpad se declara **DualSense Edge** (`VPAD_PRODUCT = 0x0DF2`,
`integrations/uhid_gamepad.py:123`) para se distinguir do físico `0x0CE6` e
poder ser separado por VID/PID. A pergunta é: **o SDL trata o Edge diferente do
DualSense comum?**

**Sim, em quatro pontos.** Todos ALTA, todos lidos em
`libsdl-org/SDL` branch `main`. O predicado é
`SDL_IsJoystickDualSenseEdge` (`SDL_joystick.c:3249-3253`), que resolve por
tabela: `controller_list.h:643` mapeia `054c:0df2` para
`k_eControllerType_PS5EdgeController`.

| # | onde | o que muda para o Edge | efeito sobre o vpad |
|---|---|---|---|
| 1 | `SDL_hidapi_ps5.c:443-447` | `enhanced_rumble = true` **sem** consultar a versão de firmware; o `0ce6` só ganha isso com firmware `>= 0x0224` (ou 0, por Bluetooth) | muda o formato do report de vibração — ver 6.3 |
| 2 | `SDL_hidapi_ps5.c:562-563` | nome vira `"DualSense Edge Wireless Controller"` | jogos que casam por substring `"Wireless Controller"` continuam casando; os que casam a frase inteira, não |
| 3 | `SDL_hidapi_ps5.c:988-989` | `joystick->nbuttons = 17` em vez de 13 (as quatro paddles) | o SDL **anuncia ao jogo quatro botões que o vpad nunca vai reportar** |
| 4 | `SDL_hidapi_ps5.c:851-863` | taxa de sensores 1000 Hz por USB em vez de 250 Hz | é a `GYRO-EDGE-RATE-01` — seção 5 |

Um quinto ponto, **medido no binário dela** e não no fonte: o banco de
mapeamentos embutido no `libSDL3.so.0` da Steam tem, para o Edge, **uma única
entrada, e ela é de Bluetooth**:

```
050000004c050000f20d000000010000,DualSense Edge Wireless Controller,...   (bus 0x05 = BT)
```

enquanto o DualSense comum tem cinco (`030000004c050000e60c...` para USB e
`050000004c050000e60c...` para BT). O vpad nasce `BUS_USB`
(`integrations/uhid_gamepad.py:94`), então **não casa com entrada nenhuma do
banco**. Isso não é defeito enquanto o caminho for HIDAPI (o driver PS5
sintetiza o mapeamento), mas passa a importar se algum dia o vpad DualSense for
lido pelo caminho evdev — que é o que `SDL_JOYSTICK_HIDAPI=0` faz, e é o que
este projeto já emite na máscara **Xbox** (`daemon/launch_env.py:957`).
**GRAU: MEDIDO AQUI** para o conteúdo do banco; **BAIXA** para a consequência,
que não foi exercitada.

**Balanço honesto:** a escolha do PID Edge continua certa pelo motivo pelo qual
foi feita (é o que permite ao `IGNORE_DEVICES` separar físico de virtual, e o
`hid_playstation` registra o vpad como DualSense completo). Ela **não é
gratuita**: paga com quatro botões fantasmas, um nome diferente, um caminho de
rumble diferente e uma taxa declarada quatro vezes maior que a real.

---

## 4. A ordem de precedência — quem ganha quando os três veem o mesmo controle

Ordem de execução, do mais cedo para o mais tarde. Cada degrau só decide o que
o degrau anterior deixou passar.

| # | quem | o que faz | fonte |
|---|---|---|---|
| 1 | **kernel** | cria os nós: `xpad` para Xbox, `hid-playstation` para Sony, `hidraw` para quem for HID | ALTA |
| 2 | **daemon deste projeto** | `EVIOCGRAB` no evdev do físico e o `hidraw_broker`; cria o vpad | código desta árvore |
| 3 | **Steam Input** | lê os controles que enxerga e cria **um espelho `28de:11ff` por controle** em `/dev/uinput` | MEDIDO AQUI, 2.2 |
| 4 | **wrapper `hefesto-launch`** | exporta as envs materializadas **imediatamente antes** do `exec` do jogo, via `env(1)` | `assets/hefesto-launch.sh` |
| 5 | **SDL do jogo** | aplica, nesta ordem: nome na blacklist → ramo do espelho do Steam → `_EXCEPT` → `IGNORE_DEVICES` | ALTA, `SDL_gamepad.c:3273-3331` |
| 6 | **winebus (só Proton)** | decide `hidraw` por `PROTON_DISABLE_HIDRAW` → registro → `PROTON_ENABLE_HIDRAW` → preferência embutida | ALTA, `main.c:543-601` |
| 7 | **jogo** | escolhe entre o que sobrou, pelos quatro critérios de 2.5 | — |

**Quem ganha o ambiente.** O degrau 4 vem **depois** do 3: a Steam monta o
ambiente do processo e o wrapper roda dentro dele, sobrescrevendo com `env(1)`
as variáveis que exporta. Logo, para as **seis** variáveis da `ENV_ALLOWLIST`
(`daemon/launch_env.py:80-87`), **o wrapper vence a Steam**. Para qualquer
outra — e `SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD` é uma delas, porque
**não está na allowlist** — vale o que a Steam pôs. **GRAU: ALTA** para o
mecanismo (`env(1)` e a allowlist por NOME de variável em
`assets/hefesto-launch.sh:85-91`); **NÃO MEDIDO** para o valor que a Steam põe.

### 4.1 O que o `steam_input_apps.txt` muda nessa ordem

O arquivo é `~/.config/hefesto-dualsense4unix/steam_input_apps.txt`, uma linha
por appid, `#` comenta. Três leitores, e cada um faz uma coisa diferente:

| leitor | o que a marca faz ali |
|---|---|
| o guard do Steam Input | **não** reverte o `UseSteamControllerConfig` daquele appid no `localconfig.vdf` — ou seja, o degrau 3 fica ligado para aquele jogo |
| `integrations/storm_doctor.py:50` e `:72` | o diagnóstico deixa de acusar aquele appid como conflito |
| `daemon/launch_env.py:559-590` | decide a **sessão da exceção** e **pula o arming** da máscara para aquele appid |

**O que ela NÃO muda mais, e isto é decisão dela, datada.** Até 09/08 a marca
tinha um ramo próprio no arquivo de envs: o jogo marcado recebia um ambiente
diferente (sem dedup) e o vpad era **suspenso**. A decisão de
[ESCONDER-EM-VEZ-DE-SAIR-01](../process/sprints/2026-08-09-ESCONDER-EM-VEZ-DE-SAIR-01-o-duplicado-cura-pelo-outro-lado.md)
matou esse ramo: hoje **o jogo marcado recebe exatamente a mesma env de
qualquer outro jogo**, e o vpad continua de pé para não derrubar o jogador 2 do
co-op junto.

**A consequência sobre a ordem de precedência é direta, e é a origem do terceiro
controle:** com o vpad vivo e o Steam Input ligado, o degrau 3 passa a enxergar
**dois** controles e a criar **dois** espelhos. A marca mudou de significado
("a entrada deste jogo vem da Steam") e o invariante da JOGO-01 voltou a valer
inteiro: *a allowlist muda QUAL dispositivo o jogo vê, nunca QUANTOS*.

**GRAU: ALTA** — é código desta árvore, e o obituário do ramo está escrito no
próprio `daemon/launch_env.py:47-58`.

---

## 5. Taxas de relatório — declarada contra real

### 5.1 Onde o SDL assume a taxa

```c
    if (ctx->sensors_supported) {
        // Standard DualSense sensor update rate is 250 Hz over USB
        float update_rate = 250.0f;

        if (ctx->device->is_bluetooth) {
            // Bluetooth sensor update rate appears to be 1000 Hz
            update_rate = 1000.0f;
        } else if (SDL_IsJoystickDualSenseEdge(ctx->device->vendor_id, ctx->device->product_id)) {
            // DualSense Edge sensor update rate is 1000 Hz over USB
            update_rate = 1000.0f;
        }

        SDL_PrivateJoystickAddSensor(ctx->joystick, SDL_SENSOR_GYRO, update_rate);
        SDL_PrivateJoystickAddSensor(ctx->joystick, SDL_SENSOR_ACCEL, update_rate);
    }
```

`SDL_hidapi_ps5.c:850-863`. **GRAU: ALTA — este é o lugar exato, e é um só.**

A taxa é **declarada por tabela**, a partir do VID/PID e do transporte.
Nenhuma linha do SDL mede o intervalo real entre relatórios para corrigi-la.

### 5.2 O que exatamente quebra

O número entregue por `SDL_PrivateJoystickAddSensor` é o que o jogo lê em
`SDL_GetGamepadSensorDataRate`. Um jogo que integre velocidade angular usando
essa taxa como `dt` — em vez de usar o carimbo de tempo que vem no próprio
relatório — multiplica o resultado pela razão entre declarada e real.

O vpad deste projeto declara **Edge** por construção, e portanto recebe
**1000 Hz**; ele entrega os relatórios do controle físico, que por USB são
**~250 Hz**. **A razão é 4.**

**Quem NÃO é afetado:** o jogo que integra pelo `sensor_timestamp` do relatório
(bytes 27-30, unidade 0,33 µs — o campo que a canônica do DualSense documenta
no §6), porque aí o `dt` é medido e não suposto. O SDL entrega esse carimbo
convertido, e é o caminho recomendado.

**Quem É afetado:** quem chama `SDL_GetGamepadSensorDataRate` e usa o valor como
período fixo. Quantos jogos fazem isso, **não se sabe**.

### 5.3 O que continua NÃO MEDIDO — e a régua do ensaio

**Nada disto é medição.** É leitura do código que **decide** a taxa declarada.

**O que MUDOU em 11/08:** a taxa do **controle físico** passou a ser medida —
cabo **250,0 Hz exatos** por três réguas concordantes, rádio em rajadas com
sustentado entre 38 e 392 Hz, e **nunca** os 1000 Hz que o SDL declara (ver
[driver-hid-playstation.md](driver-hid-playstation.md)).

**O que continua sem medição é outra coisa:** a taxa que o **vpad** entrega ao
jogo, que não é obrigatoriamente a do físico — entre os dois há o espelho de
motion, o rate-limit de 250 Hz do `uhid_gamepad.py` e o poll do daemon. E
continua não havendo linha nesta árvore que reconcilie a taxa declarada com a
entregue: nem conversão, nem aviso, nem um número guardado.

O ensaio que fecha, e a régua é metade dele:

1. abrir um jogo (ou um programa de teste) **com a SDL3 que a Steam distribui** —
   `~/.steam/debian-installation/steamrt64/libSDL3.so.0`, hoje
   `SDL-release-3.4.0-1163-g2d7f30078`. Medir contra a `libSDL2` do sistema já
   produziu, nesta casa, um alarme falso inteiro;
2. ler `SDL_GetGamepadSensorDataRate` — deve dizer 1000;
3. contar eventos `SDL_EVENT_GAMEPAD_SENSOR_UPDATE` do giroscópio por segundo,
   por trinta segundos — a expectativa é ~250;
4. a razão entre (2) e (3) é o número que falta.

Enquanto ele não vier, o grau desta seção é **NÃO MEDIDO**, e a frase honesta é
*"não medido"*.

> **`GYRO-EDGE-RATE-01` é NOME DE DIVERGÊNCIA, não sprint.** Não existe arquivo
> com esse nome em `docs/process/sprints/`, e citá-lo como sprint faz parecer
> que alguém está com o trabalho na mão. A correção já está registrada na
> [canônica dos externos](externos-referencia-canonica.md) e na
> [canônica do DualSense](dualsense-referencia-canonica.md).

**O irmão já medido, no aparelho vizinho:** o Pro Controller **declara** 8 ms no
comentário do driver e 15 ms no default, e **entrega** 11,2 ms — medido três
vezes em 07/08. É a mesma família de defeito com um segundo aparelho e um número
real. Isso torna a hipótese plausível; **não** a prova aqui.

---

## 6. O rumble pela pilha do Steam Input

**ESTE DEFEITO ESTÁ ABERTO E SEM CAUSA PROVADA.** Cinco suspeitos já caíram
(a regressão nossa, o wrapper, a máscara, a caixinha do Steam Input, o dongle);
o registro canônico é a
[ESTADO-DA-NOITE-01](../process/sprints/2026-08-10-ESTADO-DA-NOITE-01-o-que-ela-achou-com-o-controle-na-mao.md),
§6, e o método de bancada é o
[METODO-DE-ISOLAMENTO](../process/METODO-DE-ISOLAMENTO.md).

**Esta seção não escolhe causa.** Ela documenta o caminho do rumble em cada
camada para **estreitar a busca** — e derruba um sexto suspeito.

### 6.1 Os três caminhos, e eles não se parecem

| máscara / modo | como o pedido do jogo chega | o que carrega |
|---|---|---|
| **Xbox 360** (`045e:028e`, evdev) | `EVIOCSFF` / `write` de `ff_effect` no evdev do vpad; nós convertemos e escrevemos no físico | dois `u16` (strong, weak) e nada mais |
| **DualSense** (`054c:0df2`, uhid) | `write` no `hidraw` do vpad, report `0x02` de saída; chega a nós como `UHID_OUTPUT` | os 47 bytes do report comum, com **três** bytes de flags |
| **Modo Nativo** (sem vpad) | o jogo escreve direto no `hidraw` do físico | idem |

A diferença estrutural é que **no caminho evdev não há autorização a perder** —
um `ff_effect` é sempre um pedido de vibração. No caminho DualSense o **mesmo**
report `0x02` carrega lightbar, gatilhos, áudio e microfone, e são os bits de
flag que dizem se os bytes 2 e 3 são vibração ou lixo herdado. Todo defeito de
"chegou zerado" mora aí.

### 6.2 O que o kernel faz — a régua contra a qual comparar

`hid-playstation.c:1323-1332` (tag `v7.0`):

```c
        if (ds->update_rumble) {
            /* Select classic rumble style haptics and enable it. */
            common->valid_flag0 |= DS_OUTPUT_VALID_FLAG0_HAPTICS_SELECT;
            if (ds->use_vibration_v2)
                common->valid_flag2 |= DS_OUTPUT_VALID_FLAG2_COMPATIBLE_VIBRATION2;
            else
                common->valid_flag0 |= DS_OUTPUT_VALID_FLAG0_COMPATIBLE_VIBRATION;
            common->motor_left  = ds->motor_left;
            common->motor_right = ds->motor_right;
            ds->update_rumble = false;
        }
```

Os bits: `COMPATIBLE_VIBRATION` = `BIT(0)` do `valid_flag0`, `HAPTICS_SELECT` =
`BIT(1)` do `valid_flag0`, `COMPATIBLE_VIBRATION2` = `BIT(2)` do `valid_flag2`
(`hid-playstation.c:148-160`). O `valid_flag2` fica no **byte 38** do corpo
comum de 47 (`struct dualsense_output_report_common`, `hid-playstation.c:261`,
com `static_assert(... == 47)` em `:290`).

**E o kernel decide `use_vibration_v2` do mesmo jeito que o SDL** — este
paralelo importa para a seção 6.3:

```c
    if (hdev->product == USB_DEVICE_ID_SONY_PS5_CONTROLLER) {
        /* Feature version 2.21 introduced new vibration method. */
        ds->use_vibration_v2 = ds->update_version >= DS_FEATURE_VERSION(2, 21);
    } else if (hdev->product == USB_DEVICE_ID_SONY_PS5_CONTROLLER_2) {
        ds->use_vibration_v2 = true;
    }
```

`hid-playstation.c:1783-1788`. O `PS5_CONTROLLER_2` é o **Edge**, e para ele o
método v2 é **incondicional**, sem olhar versão — exatamente a mesma forma que o
SDL usa em `SDL_hidapi_ps5.c:443-447`. **Duas engenharias independentes tratam o
Edge como "sempre v2".** É a razão de o PID escolhido pelo vpad mudar o formato
do rumble que ele recebe, e não uma peculiaridade do SDL.

Dois detalhes que valem por si:

- **`update_rumble` é one-shot.** O driver zera a flag depois de emitir. Um
  report seguinte **sem** os bits não repete o pedido — ele simplesmente não
  fala de vibração. Foi isso que produziu, nesta casa, o "tremendo sem parar" e
  o gate correspondente.
- **`HAPTICS_SELECT` mata os haptics de áudio.** Quem o liga troca os motores
  voice-coil de "PCM do jogo" para "rumble emulado". O SDL o liga em todo
  rumble; o kernel também.

**GRAU: ALTA.**

### 6.3 O que o SDL faz — e por que o PID Edge muda o formato

`SDL_hidapi_ps5.c:721-738` (branch `main`):

```c
    if (ctx->vibration_supported) {
        if (ctx->rumble_left || ctx->rumble_right) {
            if (ctx->enhanced_rumble) {
                effects.ucEnableBits3 |= 0x04; // Enable improved rumble emulation on 2.24 firmware and newer
                effects.ucRumbleLeft  = ctx->rumble_left;
                effects.ucRumbleRight = ctx->rumble_right;
            } else {
                effects.ucEnableBits1 |= 0x01; // Enable rumble emulation
                // Shift to reduce effective rumble strength to match Xbox controllers
                effects.ucRumbleLeft  = ctx->rumble_left >> 1;
                effects.ucRumbleRight = ctx->rumble_right >> 1;
            }
            effects.ucEnableBits1 |= 0x02; // Disable audio haptics
        } else {
            // Leaving emulated rumble bits off will restore audio haptics
        }
```

Os nomes do SDL e os do kernel são a mesma coisa com etiquetas diferentes, e a
tabela de tradução é obrigatória para ler as duas fontes juntas
(`DS5EffectsState_t`, `SDL_hidapi_ps5.c:164-187`):

| campo do SDL | offset no corpo | nome no kernel |
|---|---|---|
| `ucEnableBits1` | 0 | `valid_flag0` |
| `ucEnableBits2` | 1 | `valid_flag1` |
| `ucRumbleRight` | 2 | `motor_right` (weak) |
| `ucRumbleLeft` | 3 | `motor_left` (strong) |
| `ucEnableBits3` | **38** | `valid_flag2` |

Agora o ponto: **`enhanced_rumble` é verdadeiro incondicionalmente para o PID do
Edge** (`SDL_hidapi_ps5.c:443-447`), sem consultar a versão de firmware que o
`0ce6` precisa ter. Logo, para o vpad deste projeto o SDL emite **sempre** o
ramo de cima:

- `valid_flag0` = `0x02` (só `HAPTICS_SELECT`), **sem** `COMPATIBLE_VIBRATION`;
- `valid_flag2` = `0x04` (`COMPATIBLE_VIBRATION2`), no byte 38;
- amplitudes **em escala cheia** (o ramo de baixo divide por dois).

E na **parada** (`rumble_left == 0 && rumble_right == 0`) nenhum bit é ligado:
sai um report com flags zeradas e motores zerados. É a causa-raiz do "tremendo
sem parar" já documentada no §8 da canônica do DualSense.

**GRAU: ALTA.**

### 6.4 O sexto suspeito, e ele CAI

A pergunta óbvia depois de 6.3 é: *o vpad descarta o rumble do SDL porque o bit
que ele espera (`0x01`) nunca vem?*

**Não.** O gate deste projeto aceita os **dois** ramos desde 09/08:

```python
    if body[_VALID_FLAG0_OFFSET] & _VIBRATION_FLAGS:      # 0x03 = v1
        return True
    return (
        len(body) > rep.COMMON_VALID_FLAG2
        and bool(body[rep.COMMON_VALID_FLAG2] & rep.VALID_FLAG2_COMPATIBLE_VIBRATION2)
    )
```

`integrations/uhid_gamepad.py:736-765` (`_fala_de_vibracao`). O report do SDL
Edge liga `0x02` no `valid_flag0` — passa pelo **primeiro** teste — e ainda
ligaria `0x04` no `valid_flag2`, que é o segundo. **Passa duas vezes.**

E a parada do SDL tem discriminador próprio, `_e_a_parada_do_sdl`
(`integrations/uhid_gamepad.py:708-733`), que exige `valid_flag0 == 0`,
`valid_flag1 == 0` e motores zerados — exatamente o report que 6.3 descreve.

**Conclusão desta subseção: o formato que o SDL emite para um Edge atravessa o
gate do vpad.** Este suspeito cai por leitura de código, dos dois lados. **GRAU:
ALTA.**

### 6.5 O que a leitura NÃO elimina — as portas que continuam abertas

Escrito como lista de portas, não como hipótese preferida. Nenhuma foi medida.

1. **Ninguém escreve.** O Steam Input, ao adotar o controle, pode simplesmente
   não repassar o force-feedback ao aparelho de origem — o jogo vibra o
   **espelho** `28de:11ff`, que é um evdev com `FF` declarado (o `steamclient.so`
   tem a mensagem `Couldn't configure haptics`, **MEDIDO AQUI**), e o espelho
   não tem para onde mandar. Isto é consistente com o único dado quantitativo
   que existe: 19 escritas em três horas de jogo, ou seja, **silêncio no canal**.
2. **Escreve, e não é o jogo.** O contador do anel não sabe **quem** escreveu, e
   o `hid-playstation` escreve no mesmo canal. A retratação já está registrada
   no `CHANGELOG.md`.
3. **Escreve pelo caminho errado.** Sob Proton, o pedido do jogo Windows pode
   sair pelo `winebus` no `hidraw` do **físico** em vez do vpad — e o físico é
   quem o daemon controla. `PROTON_DISABLE_HIDRAW` existe para fechar essa
   porta, e ele só sai com `cobertura_total` (`daemon/launch_env.py:953-964`).
4. **A quantidade de bits de autorização.** Sabe-se que o **conjunto**
   funciona; **nunca** se ensaiou de quantos o firmware precisa, um a um. São
   quatro na mesa: `COMPATIBLE_VIBRATION`, `HAPTICS_SELECT`, `MOTOR_POWER` e
   `COMPATIBLE_VIBRATION2`. O ramo Edge do SDL entrega dois deles; o kernel
   entrega dois; **são conjuntos diferentes**, e ninguém verificou se o aparelho
   aceita o do SDL.
5. **`SDL_HINT_JOYSTICK_ENHANCED_REPORTS`.** O driver PS5 do SDL tem três modos
   (`SDL_hidapi_ps5.c:212-222`): `"0"` nunca usa recursos avançados, `"1"`
   sempre, `"auto"` anuncia mas **não toca no estado do controle até o
   aplicativo pedir explicitamente**. Em `auto`, um jogo que use o gamepad sem
   pedir rumble deixa o caminho inteiro adormecido. Que valor a Steam põe nesse
   hint **não foi medido**.

**O ensaio que separa as cinco** já existe e é o mesmo de sempre: o anel dos
últimos pedidos crus no vpad, com bytes, ramo e idade, durante uma sessão de
jogo real com o Steam Input no caminho. Ele responde, de uma vez: *chegou pedido
e nós descartamos? / era o kernel se passando por jogo? / ninguém escreveu?*
Segue esperando a sessão.

---

## 7. O que continua em aberto por falta de medição

Uma variável por linha, que é como se ataca isto.

| # | pergunta | o ensaio que a fecha | seção |
|---|---|---|---|
| 1 | a Steam põe `SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD=1` no ambiente do jogo? | com o jogo aberto: `tr '\0' '\n' < /proc/<pid>/environ \| grep -i SDL_` — leitura pura, custo zero | 2.4 |
| 2 | logo, o par `0x28de/0x11ff` no `IGNORE_DEVICES` esconde alguma coisa, ou é redundante? | decorre de (1): se a variável for 1, o par não age pelo caminho SDL | 2.4 |
| 3 | a taxa real do giroscópio do vpad Edge — 250 ou 1000 para o jogo? | os quatro passos de 5.3, **contra a SDL3 da Steam** | 5 |
| 4 | de quantos bits de autorização o firmware precisa para vibrar? | bancada, um bit por vez, com o controle na mão dela | 6.5 |
| 5 | o pedido de rumble do jogo chega ao vpad numa sessão com Steam Input? | o anel de pedidos crus, sessão de jogo real | 6.5 |
| 6 | em que valor a Steam deixa `SDL_HINT_JOYSTICK_ENHANCED_REPORTS`? | mesmo comando de (1) | 6.5 |

Os itens 1, 2 e 6 saem **do mesmo comando**, custam trinta segundos e fecham
três linhas de uma vez. É o melhor negócio desta tabela.

---

## 8. Fontes

**Código lido nesta sessão** (a tag ou branch está em 0.2)

- `xpad.c` — `https://github.com/torvalds/linux/blob/v7.0/drivers/input/joystick/xpad.c`
- `hid-playstation.c` — `https://github.com/torvalds/linux/blob/v7.0/drivers/hid/hid-playstation.c`
- `SDL_hidapi_ps5.c` — `https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_ps5.c`
- `SDL_gamepad.c` — `https://github.com/libsdl-org/SDL/blob/main/src/joystick/SDL_gamepad.c`
- `SDL_joystick.c` — `https://github.com/libsdl-org/SDL/blob/main/src/joystick/SDL_joystick.c`
- `SDL_sysjoystick.c` (Linux) — `https://github.com/libsdl-org/SDL/blob/main/src/joystick/linux/SDL_sysjoystick.c`
- `SDL_hidapijoystick.c` — `https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapijoystick.c`
- `SDL_steam_virtual_gamepad.c` — `https://github.com/libsdl-org/SDL/blob/main/src/joystick/SDL_steam_virtual_gamepad.c`
- `usb_ids.h`, `controller_list.h` — mesmo diretório `src/joystick/` do SDL
- `SDL_gamecontroller.c` (SDL2) — `https://github.com/libsdl-org/SDL/blob/SDL2/src/joystick/SDL_gamecontroller.c`
- `winebus.sys` — `https://github.com/ValveSoftware/wine/blob/proton_10.0/dlls/winebus.sys/main.c`
  e `.../dlls/winebus.sys/unixlib.h`

**Documentação de comunidade**

- free60, o layout do pacote do Xbox 360 — citada pelo próprio comentário do
  `xpad`, `http://www.free60.org/wiki/Gamepad`
- Proton, DualSense advanced features — `https://github.com/ValveSoftware/Proton/issues/5900`

**Binários desta máquina** (leitura por `strings(1)`, 11/08/2026)

- `~/.steam/debian-installation/ubuntu12_32/steamclient.so`
- `~/.steam/debian-installation/steamrt64/libSDL3.so.0`
- `Proton 10.0/files/lib/wine/x86_64-windows/winebus.sys` e o script `proton`
  dos Protons 10.0 e 11.0

**Nesta árvore**

- [a canônica do DualSense](dualsense-referencia-canonica.md) — o aparelho, os
  47 bytes, o §8 do rumble preso
- [a canônica dos externos](externos-referencia-canonica.md) — Pro e 8BitDo, e o
  irmão medido da divergência de taxas
- [paridade Bluetooth × cabo](paridade-bluetooth-versus-cabo.md) — o transporte
- [TRES-CONTROLES-01](../process/sprints/2026-08-10-TRES-CONTROLES-01-o-espelho-do-espelho-no-pragmata.md)
  — a medição do `/dev/input` com quatro nós
- [ESCONDER-EM-VEZ-DE-SAIR-01](../process/sprints/2026-08-09-ESCONDER-EM-VEZ-DE-SAIR-01-o-duplicado-cura-pelo-outro-lado.md)
  — a decisão dela que reabriu a conta pelo outro lado
- [WRAPPER-EM-TODOS-01](../process/sprints/2026-08-03-WRAPPER-EM-TODOS-01-a-invariante-duplicado-melhor-que-zero-com-quatro.md)
  — a cobertura, e por que o `IGNORE` só sai com um vpad por físico
- [LUGAR-À-MESA-01](../process/sprints/2026-08-06-LUGAR-A-MESA-01-tres-controles-ligados-e-um-jogador-so.md)
  — a cobertura POR PAR, que ainda não existe
- [ESTADO-DA-NOITE-01](../process/sprints/2026-08-10-ESTADO-DA-NOITE-01-o-que-ela-achou-com-o-controle-na-mao.md)
  — o defeito do rumble, e os cinco suspeitos caídos
- [METODO-DE-ISOLAMENTO](../process/METODO-DE-ISOLAMENTO.md) — como se ensaia um
  bit de cada vez
