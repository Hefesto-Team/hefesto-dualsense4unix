# A luz do DualSense — o que terceiros mapearam, e o que só o aparelho fecha

**03/09/2026.** Levantamento em repositório público para as cinco linhas de
`luz.*` do DualSense que estavam com o caminho incompleto no mapa. **Nada foi ao
aparelho nesta leva** — ela estava usando a máquina com dois controles vivos.
Tudo aqui é `afirmado-no-doc` ou `inferido-do-codigo`; nenhuma célula ganhou
`ate_onde_foi`.

O pedido dela, que é o contrato deste trabalho: *"como é só informação eles
trouxeram"*. Fato com endereço — o número do report, o offset do byte, o formato
do comando. Nenhuma linha de código de terceiro foi copiada.

---

## 1. O byte do LED de jogador tem TRÊS testemunhas independentes

O driver desta máquina põe a máscara de jogador em `common[43]`, atrás do bit4 do
`valid_flag1`. Isso já estava escrito. O que faltava era saber se alguém de fora
tinha chegado ao mesmo lugar — e três projetos chegaram, sem se copiarem:

| fonte | o que diz | onde |
| --- | --- | --- |
| `hid-playstation` (DKMS desta árvore) | `common.player_leds`, 43º byte do bloco de 47; porteiro `valid_flag1` BIT(4) | `:216`, `:320-349`, `:1479-1484` |
| libsdl-org/SDL | `ucPadLights` no offset **43**; `ucEnableBits2 \|= 0x10` — comentado *"Enable touchpad lights"* | `SDL_hidapi_ps5.c`, `DS5EffectsState_t` e `HIDAPI_DriverPS5_UpdateEffects` |
| Ohjurot/DualSense-Windows | `hidOutBuffer[0x2B]` (= 43) recebe `playerLeds.bitmask` | `src/DualSenseWindows/DS5_Output.cpp:16` |
| Game Controller Collective Wiki | `PlayerLight1..5` em `43.0`–`43.4` | `Sony DualSense/Data Structures`, `SetStateData` |

E há uma quarta testemunha, que não é de terceiro nenhum — **é do aparelho**. O
descritor HID que ele publica declara `Report ID (2)` com `Report Count (47)` e
`Output` (USB), e `Report ID (49)` = 0x31 (rádio). O bloco de 47 bytes é palavra
do próprio DualSense, não leitura de ninguém.

**Os cinco padrões batem byte a byte entre o Linux e o SDL:** `4, 10, 21, 27, 31`
= `0x04, 0x0A, 0x15, 0x1B, 0x1F`. O SDL chegou neles por outro caminho, e o
`0x1F` entrou lá depois, num commit que fecha a issue #5152.

### O offset no rádio, e por que é `report[46]`

O envelope de rádio põe **três** bytes antes do bloco: `report_id`, `seq_tag`,
`tag` (`hid-playstation.c:351-355`). Então `common[43]` cai em `report[46]`. A
soma de 3 não é dedução: ela já estava **medida** no mapa, em
`luz.led_microfone` (`common[8] = report[11]`, 02/09/2026).

> **CONTRADIÇÃO, e o driver vence.** O `ReportOut31` do Game Controller
> Collective Wiki mostra só **dois** bytes de envelope (`ReportID` + um byte de
> `SeqNo`/flags). Isso poria `common[43]` em `report[45]`. O driver desta
> máquina diz três, e a medição do LED do microfone desta casa confirma três.
> **A wiki está curta em um byte.** É o único ponto em que ela diverge do
> driver em tudo que li.

---

## 2. O bit5 é o fade — e o driver do Linux NÃO o liga

`common[43]` não é só a máscara. O **bit5 (0x20)** decide se a mudança entra com
fade ou instantânea, e três fontes dizem a mesma coisa com palavras diferentes:

- SDL: `lights[player_index] | 0x20`, comentado *"0x20 changes instantly instead
  of fade"* — o SDL **sempre** liga.
- DualSense-Windows: `if (playerLedFade) buffer &= ~0x20; else buffer |= 0x20;`
  — o campo se chama `playerLedFade`.
- Game Controller Collective Wiki: `43.5 PlayerLightFade`, *"if low player
  lights fade in, if high player lights instantly change"*.

**O `hid-playstation` nunca liga o bit5.** A tabela `player_ids[]` só tem
`4/10/21/27/31`, e `:1482` copia o valor cru. **Logo o padrão que a probe do
driver acende ENTRA COM FADE.**

Isso tem consequência aqui: o produto instala uma graça de 0,5 s antes de
replicar o LED de jogador (`integrations/uhid_gamepad.py:380`). Quem for
cronometrar essa graça tem de contar o fade do driver, que a graça não espera.

Os bits 6 e 7 do mesmo byte continuam sem nome — a wiki os declara
`PlayerLightUNK : 2`, e nenhuma outra fonte os toca.

---

## 3. O ACHADO QUE VALE A LEVA: a quinta lâmpada pode não ser dela mesma

O Game Controller Collective Wiki, na seção **Hardware Revisions** da página
`Sony DualSense`:

> *"This hardware revision has made a 'breaking change' to the player LED
> handling. Now the two pairs PlayerLight1+PlayerLight5 and
> PlayerLight2+PlayerLight4 are "wired" together. This change makes it
> impossible to separately control these LEDs but does not disrupt the intended
> player light configurations. (…) If interfacing with a controller of this
> hardware revision, note that only symmetrical player LED configurations are
> possible."*

A revisão é **`Generation 0x04`** (as anteriores são `0x03`), e a detecção
sugerida é `(HardwareInfo & 0x00FFFF00) == 0x00000400`, lido do **feature report
`0x20`** — o mesmo que o driver já lê para o firmware
(`DS_FEATURE_REPORT_FIRMWARE_INFO`, `hid-playstation.c:153`, `:1281-1286`).

**Por que isto importa para esta casa, e por que ninguém tinha visto:**

1. O protocolo continua com cinco bits. **O hardware é que encolheu para três
   grupos:** `{1,5}`, `{2,4}`, `{3}`.
2. O `hid-playstation` registra **cinco** `led_classdev` independentes
   (`:1858-1868`). Em hardware `0x04` ele mente por construção: acender só o
   `player-5` acende **também** o `player-1`, e o `get_brightness` — que só lê
   `ds->player_leds_state`, a RAM do driver — continua dizendo que só o 5 está
   aceso.
3. **Os cinco padrões canônicos são palíndromos** (4, 10, 21, 27, 31). Por isso
   a diferença **não aparece em uso normal**. Ela aparece em bitmask
   assimétrico — que é exatamente o que um banco de provas faz.

**Grau: `afirmado-no-doc`, FONTE ÚNICA.** Procurei segunda fonte independente e
não achei. Isto **não contradiz** o driver: fala de hardware que o driver não
modela. **Só o aparelho fecha.**

> **Cuidado com o homônimo, que já enganou uma vez.** O commit do SDL chamado
> *"Enable the 5th player LED on the DualSense controller"* acrescenta `0x1F` —
> que é o padrão do **jogador 5**, não a quinta **lâmpada**. O bit4 já acendia
> no P3 (`0x15`) e no P4 (`0x1B`) desde sempre. São dois "quintos" diferentes.

---

## 4. Ler o estado do LED: o aparelho declara que não dá

A linha `luz.led_jogador.leitura` dizia, desde 11/08, que se lê a INTENÇÃO e
nunca o ESTADO. A leva de hoje traz a testemunha mais forte que existe sem
hardware — **o descritor HID que o próprio aparelho publica**:

- **USB:** um único report de entrada, `Report ID (1)`. Todo o resto é `Feature`,
  mais o `Report ID (2)` de saída.
- **Rádio:** entrada em `Report ID (1)` e `Report ID (49)` = 0x31.

E nenhum deles carrega campo de LED, em **quatro leituras independentes**:

| fonte | o que a entrada tem | LED? |
| --- | --- | --- |
| `struct dualsense_input_report` (`:295-315`) | eixos, botões, sensores, touchpad, `status[3]`, reservados | não |
| `USBGetStateData`/`BTGetStateData` (wiki) | idem | não — `PlayerLight*`, `LightBrightness` e `LedRed/Green/Blue` aparecem **só** na estrutura de SAÍDA |
| SDL (`PS5StatePacket_t`) | idem | não |
| DualSense-Windows (`DS5_Input.cpp`) | idem | não |

O único campo de saída que a wiki diz voltar espelhado é o `HostTimestamp`
(byte 32), e ela registra a mesma limitação para os gatilhos: *"there is no way
to read the full parameters of the current trigger effect back from the
controller"*.

**Conclusão, e ela é um fato negativo com endereço:** por HID não há canal de
leitura de LED. A célula do mapa ganhou `—` e a razão, em vez de ficar vazia —
célula vazia faz a próxima pessoa caçar de novo.

---

## 5. Existe UM canal proprietário de luz, e ninguém desta casa o tocou

`luz.recursos_proprios` perguntava por turbo e LEDs de modo. As duas metades da
resposta são opostas, e por isso a linha ficou `parcial`.

**Turbo e LED de modo: NÃO existem.** O conjunto de luz do DualSense é fechado e
tem três peças, todas já com chave própria: a lightbar RGB, as cinco lâmpadas
brancas sob o touchpad, e o LED do botão de mudo. A wiki lista o hardware de
saída como *"RGB LED (24 bit color)"* e *"Indicator Lights (5, white, capable of
fade)"*. Nenhuma das fontes lidas menciona turbo ou lâmpada de modo — e o
DualSense não tem chave de modo para indicar.

**Mas existe um canal de teste de LED, e ele é proprietário.** O feature report
`0x80` ("Set test command"; `0x81` devolve o resultado) aceita, segundo um
relato de engenharia reversa:

```
SET 0x80 0x0d 0x03 GG RR BB WW XX YY ZZ
```

> *"which seems to test all the LEDs available on the controller: every byte in
> the payload (GG, RR, ..) is the brightness of each available LED"*

Se procede, **é o único caminho conhecido que dá brilho POR LÂMPADA** — o report
de saída normal só oferece liga/desliga por bit em `common[43]` e um brilho
global de três degraus em `common[42]`. O aparelho declara `0x80` e `0x81` como
`Feature` nos **dois** transportes (descritor HID), então o canal existe.

**Grau: `afirmado-no-doc`, FONTE ÚNICA**, e o próprio autor escreveu *"seems
to"*. O mesmo relato avisa de duas armadilhas de bancada: boa parte dos comandos
fica desabilitada **com a bateria desconectada**, e o payload máximo de um GET é
**63 bytes**, não 256 como no DS4.

---

## 6. O que a internet NÃO sabe — a lista honesta

Estas são as perguntas que sobraram, e todas têm a mesma resposta: **só o
aparelho responde.**

1. **A revisão de hardware desta casa é `0x03` ou `0x04`?** Um `GET FEATURE
   0x20` responde, sem escrever nada no aparelho. Enquanto não se ler, não se
   sabe se a quinta lâmpada daqui é endereçável sozinha.
2. **O par lâmpada1+lâmpada5 realmente se acende junto?** Fonte única. Um
   bitmask assimétrico (`0x10`, só o bit4) e o olho dela fecham em segundos.
3. **`common[42]` é o brilho de QUAL luz?** *(fora do meu tema, e é uma
   contradição — ver §7.)*
4. **Os bits 6 e 7 de `common[43]`.** Ninguém os nomeou. `PlayerLightUNK : 2`.
5. **O `0x80 0x0d 0x03` faz mesmo o que o relato diz?** E quais LEDs são
   `GG RR BB WW XX YY ZZ` — sete bytes para um aparelho que tem 3 canais de
   lightbar + 5 lâmpadas + 1 de mudo. A conta não fecha em nenhuma leitura
   óbvia, e nenhuma fonte explica.
6. **O `0x81` devolve estado de LED?** Chama-se "Get test result". Ninguém
   documentou o que volta.
7. **O que o console PS5 desenha.** Continua sem observação, como a canônica já
   registrava.

---

## 7. Uma contradição fora do meu tema, escrita para quem for pegá-la

**`common[42]` — a canônica desta casa e o mapa o tratam como brilho da
LIGHTBAR** (`luz.lightbar.brilho`, com `fonte_externa = pydualsense`). Duas
fontes lidas hoje discordam:

- **DualSense-Windows** é explícito: `// Player led brightness` sobre
  `hidOutBuffer[0x2A] = ptrOutputState->playerLeds.brightness` — o campo pertence
  à `struct` de **player LEDs**, não à de lightbar.
- **Game Controller Collective Wiki** é ambíguo: chama o byte de
  `LightBrightness` (`Bright=0, Mid=1, Dim=2`) e o porteiro de
  `AllowLightBrightnessChange` — nomes genéricos, e a posição (entre o
  `LightFadeAnimation` de 41 e os `PlayerIndicators` de 43) não desempata.
- **Nem o `hid-playstation` nem o SDL escrevem esse byte alguma vez**, então
  nenhum dos dois opina.

**Não mexi na linha — não é minha, e a literatura não desempata.** Um degrau de
brilho escrito com o bit0 do `valid_flag2` ligado, e o olho dela em qual luz
mudou, fecha a pergunta numa medição.

Vale registrar o que a leva **confirmou** de graça no caminho: o **bit0 do
`valid_flag2`** — que o `hid-playstation` **não define** — é mesmo o porteiro do
byte 42. A wiki o nomeia `38.0 AllowLightBrightnessChange` e o
DualSense-Windows escreve `hidOutBuffer[0x26] = 0x03` (bits 0 e 1) exatamente
quando vai escrever brilho. A canônica desta casa já dizia "flag2 0x01" sem
fonte; agora tem duas.

---

## As fontes, com endereço

| fonte | o que rendeu |
| --- | --- |
| `assets/dkms/hid-playstation/hid-playstation.c` (nesta árvore) | report ids, a `struct` de 47 bytes, a tabela `player_ids[]`, a ausência de LED na entrada |
| libsdl-org/SDL, `src/joystick/hidapi/SDL_hidapi_ps5.c` | `DS5EffectsState_t` (offsets 41-46), `SetLightsForPlayerIndex`, o `\| 0x20`, `ucEnableBits2 \|= 0x10` |
| Ohjurot/DualSense-Windows, `src/DualSenseWindows/DS5_Output.cpp:16-27` | `0x2B` = máscara, `0x2A` = brilho "player led", `0x26 = 0x03` |
| Game Controller Collective Wiki, `Sony DualSense` e `.../Data Structures` | `SetStateData` byte a byte, `43.5 PlayerLightFade`, **as Hardware Revisions** |
| nondebug/dualsense, `report-descriptor-{usb,bluetooth}.txt` | a palavra do próprio aparelho: quais reports existem, e de que tipo |
| `blog.the.al/2024/04/02/calibrating-dualsense.html` | `SET 0x80 0x0d 0x03`, o limite de 63 bytes, a bateria desconectada |
| carpikes/ds4-tools, `ds5-calibration-tool.py:143,152` | corrobora o `0x80` sub-comando 3 (NVS lock/unlock) | <!-- ref-externa: arquivo do projeto carpikes/ds4-tools, lido pela web; não é, e não deve ser, versionado nesta árvore -->

**A régua que sustenta o que entrou no mapa:**
`tests/unit/test_luz_do_jogador_bate_com_o_fonte.py`. Ela não redigita o byte 43
— **calcula** o offset somando os campos da `struct` do driver, e **lê** os
report ids dos `#define`. Mordida provada em cinco arrancadas, uma delas no
próprio fonte do driver (`reserved3[2]` → `[3]`), que é a que prova que a régua
lê em vez de repetir.
