# O modo de relatório do DualSense — o que faz o `0x01` virar `0x31`

**Levantado em 03/09/2026, em fonte pública, sem tocar o aparelho.** Nada nesta
página foi medido aqui. O grau de cada afirmação está escrito ao lado dela, e a
regra é a de sempre: o que eu li em repositório de terceiro é
`afirmado-no-doc`, nunca `medido`.

O que esta página fecha são quatro linhas do mapa que estavam MUDAS —
`plataforma.modo_relatorio`, `plataforma.handshake_usb`,
`plataforma.taxa_relatorios.botao` e o que faltava em
`plataforma.limitador_subcomando` e `plataforma.escrita_crua`.

O endereço do driver desta máquina é sempre
`assets/dkms/hid-playstation/hid-playstation.c`, e quando eu escrever só `:NNN`
é dele que estou falando.

---

## 1. Não existe `SET_REPORT_MODE` no DualSense. A troca é EFEITO COLATERAL de uma leitura

A auditoria de 11/08/2026 desta casa concluiu, e continua certa: **não há
equivalente Sony do `SET_REPORT_MODE`**. O que faltava era a outra metade — se
não há comando, o que troca o modo?

### Por cabo não há o que trocar

O report de entrada `0x01`, **64 bytes com o byte de id**, já é o report
COMPLETO. Não há segundo modo no fio.

| quem diz | onde | grau |
|---|---|---|
| o driver desta máquina | `:140-141` (`DS_INPUT_REPORT_USB 0x01`, `_SIZE 64`) e o despacho em `:1579-1581` | fonte desta máquina |
| o descritor lido do aparelho dela | `plataforma.descritor_hid@dualsense`: *"INPUT `0x01` (64 B com o id)"* | MEDIDO nesta casa, 15/08/2026 |
| o SDL | `SDL_hidapi_ps5.c:413-415` — lê UM report de entrada e decide pelo TAMANHO: `size == 64` ⇒ *"Connected over USB"*, modo completo. Ele **não pergunta nada** | afirmado-no-doc |

### Por rádio o aparelho NASCE mudo, e uma leitura o acorda

Por rádio o DualSense começa emitindo o `0x01` de **10 bytes com o id** — o
modo básico, sem IMU, sem touchpad, sem bateria — e só passa ao `0x31` de 78
bytes **depois que o host faz um `GET_REPORT` num feature report**.

O descritor que esta casa leu em 15/08 **já declarava os dois** (*"INPUT `0x01`
(10 B com o id) e `0x31` (78 B)"*). O que ninguém tinha era o gatilho.

**Quatro fontes independentes dizem que é uma leitura de feature — e nomeiam
TRÊS ids diferentes:**

| fonte | id que ela nomeia | o que ela diz |
|---|---|---|
| `libsdl-org/SDL`, `src/joystick/hidapi/SDL_hidapi_ps5.c:426-429` | **`0x09`** (serial/pairing info) | comentário no fonte: *"Read the serial number (Bluetooth address in reverse byte order) — This will also enable enhanced reports over Bluetooth"* |
| o MESMO arquivo, `:434-437` | **`0x20`** (firmware info) | *"Read the firmware version — This will also enable enhanced reports over Bluetooth"* |
| `dsremap` (documentação de engenharia reversa) | **`0x20`** | *"Over Bluetooth, report 0x01 is a simplified version, as for the Dualshock, but after GET_REPORT 0x20 it becomes 0x31"* |
| `nondebug/dualsense` | **`0x05`** (calibração) | ler a calibração é o que troca o report de entrada por rádio do `0x01` truncado para o `0x31` expandido |

E o DS4Windows diz a mesma coisa em linguagem de produto, sem citar id nenhum:
*"PC friendly mode: only basic button/axes information is sent by the
controller to the PC"* × *"Native PS mode: controller sends its full set of
information, including motion sensors data, status, touchpad states etc"*, e
quando ele reconhece o controle *"a request is sent for them to change into
Native PS mode"*.

> **A LEITURA QUE CONCILIA AS TRÊS É MINHA, E É INFERÊNCIA — não fato.**
> Três fontes nomeiam três ids diferentes e as três funcionam para quem as
> escreveu. A explicação mais econômica é que **o gatilho não é um id
> específico: é o ATO de fazer `GET_REPORT` num feature que o aparelho
> responde.** Isso NÃO está escrito em fonte nenhuma, e não foi medido aqui.
> Quem for à bancada mede assim: por rádio, com o `hid-playstation`
> desvinculado, ler um feature de cada vez e ver em qual deles o `0x01` de 10 B
> vira `0x31` de 78 B.

### Por que o driver desta máquina nunca vê o report básico

`dualsense_create` faz TRÊS leituras de feature, nesta ordem, **todas antes de
`ps_gamepad_create`** — ou seja, antes de o driver consumir o primeiro report
de entrada:

| ordem | função | linha | feature que ela lê |
|---|---|---|---|
| 1ª | `dualsense_get_mac_address` | `:1897` (corpo em `:1309`, pedido em `:1318`) | **`0x09`** (`DS_FEATURE_REPORT_PAIRING_INFO`, `:151`) |
| 2ª | `dualsense_get_firmware_info` | `:1904` (pedido em `:1285`) | **`0x20`** (`:153`) |
| 3ª | `dualsense_get_calibration_data` | `:1929` (pedido em `:1169`) | **`0x05`** (`:149`) |

São **os três ids que as três fontes nomeiam**, todos lidos na probe.

**E a confirmação mais forte que dá para ter sem tocar em hardware é
ESTRUTURAL, dentro do próprio arquivo:** `dualsense_parse_report` (`:1562`)
**não tem ramo nenhum para o `0x01` por Bluetooth** — ele conhece USB `0x01`/64
e rádio `0x31`/78, e tudo o mais cai no `hid_err(hdev, "Unhandled reportID=%d")`
de `:1594`. Já `dualshock4_parse_report` **tem** esse ramo
(`DS4_INPUT_REPORT_BT_MINIMAL`, `:2623-2634`), com o comentário que explica por
quê: *"Some third-party pads never switch to the full 0x11 report."*

O caminho do DualSense pode se dar ao luxo de não ter o ramo **porque a probe
já virou o aparelho antes**. As duas metades do mesmo arquivo só fazem sentido
juntas, e é a fonte externa que as junta.

> **O DIAGNÓSTICO QUE ISSO NOS DÁ, e ele é falsificável.** Se um DualSense por
> rádio algum dia NÃO virar, o kernel diz, com estas palavras:
>
> ```
> playstation 0005:054C:0CE6.NNNN: Unhandled reportID=1
> ```
>
> Nenhuma outra situação produz essa linha para um DualSense. Quem vir isso no
> `dmesg` está vendo o aparelho preso no modo básico.

### A troca é de mão única enquanto o controle estiver ligado

Wiki do SDL3, `SDL_HINT_JOYSTICK_ENHANCED_REPORTS`, literal: *"Once enhanced
reports are enabled, they can't be disabled on PlayStation controllers without
power cycling the controller."*

**Grau: afirmado-no-doc, fonte única.** Nenhuma segunda fonte confirma, e não
foi medido aqui.

---

## 2. Não existe handshake USB no DualSense

`handshake`, `baudrate 3M` e `no-timeout` são vocabulário do **Switch Pro /
hid-nintendo** (saída `0x80`, resposta `0x81`) — é o que as linhas irmãs
`plataforma.handshake_usb@pro` e `@sn30` carregam, e está certo lá.

No DualSense **não há nada disso**, e três corpos independentes concordam pelo
silêncio:

- o driver desta máquina não tem uma linha de handshake no caminho DualSense —
  a auditoria de 11/08/2026 desta casa já tinha varrido `src/` e achado só o
  handshake de force-feedback do uinput, que é outra coisa;
- o `SDL_hidapi_ps5.c` inteiro não faz aperto de mão nenhum: ele **lê um report
  de entrada e olha o tamanho** (`:405-422`);
- nem `nondebug/dualsense`, nem `dsremap`, nem o DS4Windows citam handshake.

**O que ocupa esse lugar no DualSense é o que está na §1**: por cabo, nada — o
aparelho já nasce completo; por rádio, o `GET_REPORT` num feature. Quem procurar
handshake no DualSense vai procurar um fantasma, e é isso que a linha do mapa
passa a dizer.

---

## 3. Não há canal de TAXA no DualSense — e a fonte que parecia discordar não discorda

Esta casa já mediu o que o aparelho ENTREGA (cabo 250,0 Hz exatos; rádio
variável em rajadas, de ~38 a ~392 Hz entre janelas consecutivas — a canônica,
§5). O que faltava era saber se dá para PEDIR.

| quem | tem campo de taxa para o DualSense? |
|---|---|
| driver desta máquina | **não.** O DualShock 4 tem `bt_poll_interval` na struct (`:483-484`), um `dualshock4_set_bt_poll_interval` (`:2873`) e um default na probe (`:3022`); a `struct dualsense` (`:233`) não tem equivalente de nada disso, e a saída é `schedule_work` sob demanda (`:1417-1422`), sem estrangulamento nenhum |
| SDL | **não.** Não há ajuste de taxa para PS5 em `SDL_hidapi_ps5.c` |
| `nondebug/dualsense`, `dsremap` | **não citam** |

**A fonte que parecia discordar, e por que ela não discorda:** a página de
solução de problemas do DS4Windows diz que o ajuste *BT Poll Rate* *"applies to
DS4 and DualSense controllers on Bluetooth"*. Mas **os textos do próprio
programa dizem o contrário**: o rótulo é `DS4BTPollRate` = *"DS4 BT Poll
Rate"*, e o `tooltip` em `DS4Windows/Properties/Resources.resx` é literal —
*"Determines the poll rate used for the **DS4 hardware** when connected via
Bluetooth."* O valor mora em `ProfileSchema.Legacy.cs` (`BTPollRate`, default
**4**) e o setter em `DS4Library/DS4Device.cs` recusa fora de `0..16`.

**Fico com os textos do programa e com as outras duas implementações: é campo
de hardware do DS4.** A medição desta casa está do mesmo lado — um aparelho com
intervalo negociado não entrega 38 Hz numa janela e 392 Hz na seguinte, parado
sobre a mesa.

**Consequência para o mapa:** a linha `plataforma.taxa_relatorios.botao` nunca
poderá ter `report_id`, porque não há report a citar. Um botão de taxa na
interface só pode **MEDIR**, nunca **COMANDAR**. Isso é decisão de
classificação, e ela fica escrita para a próxima pessoa não caçar o report.

### O que existe é POLÍTICA DE HOST — e um número bateu duas vezes

| | keepalive quando nada muda | piso entre escritas |
|---|---|---|
| **esta casa** | `OUT_REPORT_KEEPALIVE_SEC = 0.5 s` | `REPORT_THREAD_THROTTLE_SEC = 0.008 s`, teto adaptativo `0.032 s` |
| **SDL** | `BLUETOOTH_DISCONNECT_TIMEOUT_MS = 500` (`SDL_hidapi_ps5.c:44`, usado em `:1653`) | não tem piso: ele **funde** a escrita pendente com a nova (`:1132-1136`) |
| **DS4Windows** | — | `BTPollRate` default 4 ms; a documentação sugere **≥ 10 ms** com vários controles no rádio |
| **driver do Linux** | nenhum | nenhum |

Os **0,5 s** são o mesmo número a que duas casas chegaram sem se falar. E a
fusão da escrita pendente do SDL é a mesma ideia do dedup de report idêntico
daqui. Nenhum dos dois é limite do APARELHO: são políticas de quem escreve.

---

## 4. Dois detalhes de escrita crua que a fonte externa entrega de graça

### 4.1 Por cabo, os 15 bytes finais são enchimento opcional

| quem | quantos bytes escreve no `0x02` |
|---|---|
| o descritor lido do aparelho dela (15/08/2026) | **48** com o id — declara 47 de payload |
| SDL (`:1107-1109`) | **48**, exatamente |
| driver desta máquina | **63** — `DS_OUTPUT_REPORT_USB_SIZE` (`:145`), struct em `:361-366`: 1 id + 47 do `common` + **15 reservados** |

Duas implementações em produção, dois tamanhos, as duas funcionando. **Os 15
reservados são opcionais.** E os 48 do SDL são confirmação independente do
número que o descritor desta casa já dava.

### 4.2 Por rádio, o número de sequência NÃO é cobrado — e o CRC errado é um NADA silencioso

O cabeçalho do `0x31` de saída: `[0]=0x31`, `[1]` = sequência/tag, `[2]=0x10`
fixo, `[3..49]` = o mesmo `common` de 47 bytes do cabo, e os 4 últimos são
CRC-32 com o prefixo `0xA2`. (Driver: struct em `:351-359`, montagem em
`:1386-1396`, e o comentário de `:1387` — *"Tag must be set. Exact meaning is
unclear."* SDL: `:1100-1104` e o CRC em `:1117-1121`.)

**A sequência não é cobrada pelo firmware.** O driver do Linux incrementa o
nibble alto a cada report e dá a volta em 16 (`:1393-1396`). O SDL escreve um
`0x00` literal em `:1101` e **nunca incrementa** — e
`HIDAPI_DriverPS5_InternalSendJoystickEffect` (`:1070`) é o funil único de todo
efeito por rádio que ele manda (chamado de `:781`). Duas implementações em
produção, comportamentos opostos, as duas funcionando.

**Um CRC errado transforma o report num nada — e o SDL DEPENDE disso.**
`HIDAPI_DriverPS5_TickleBluetooth` (`:814-830`) manda de propósito um `0x31` de
78 bytes zerado e **sem CRC**, com o comentário *"This is just a dummy packet
that should have no effect, since we don't set the CRC"*, só para manter a
pilha Bluetooth acordada depois de 500 ms de silêncio.

> **Para esta casa isto é o MECANISMO por trás de uma ressalva que já estava
> escrita** em `plataforma.escrita_crua@dualsense`: o sucesso do `os.write()`
> num hidraw diz que o KERNEL aceitou os bytes, não que o firmware executou
> alguma coisa. Um CRC errado por rádio é exatamente isso — uma escrita que dá
> certo e não faz nada. Agora se sabe nomear a causa mais provável quando um
> report por rádio "sai" e o controle não reage.

---

## 5. A SEGUNDA BUSCA — os hosts de Bluetooth escritos do zero

**Acrescentado em 03/09/2026, na mesma leva, depois de uma segunda varredura.**
As fontes das seções acima são todas *clientes* do aparelho: falam com ele por
cima de um kernel que já resolveu o vínculo. Existe uma veia que ninguém neste
repositório tinha citado, e ela é melhor para esta pergunta: **os hosts
Bluetooth escritos do zero para um Raspberry Pi Pico W.**

| projeto | o que é |
|---|---|
| `awalol/DS5Dongle` | dongle de DualSense num Pico 2 W |
| `SundayMoments/DS5_Bridge` | fork do anterior, com áudio e mais instrumentação |
| `rafaelvaloto/Pico_W-Dualsense` | firmware de host Bluetooth Classic |
| `Pim-Hartendorp/Raspberry-pi-pico-2W-DS5-host` | leitura de entradas por API em C |
| `cadouthat/pico-dualsense` | biblioteca de leitura |

**Por que eles valem mais que uma wiki**, e é estrutural: quem fala com o
controle sem BlueZ e sem kernel **tem de acertar tudo**, e o que não é
obrigatório eles não escrevem. A ordem de inicialização deles é a lista mínima.

### 5.1 A pergunta 3 da lista abaixo FECHOU: escrever também vira o modo

A versão desta página de algumas horas antes dizia, na lista do que a internet
não sabe: *"Ninguém diz se um report de SAÍDA `0x31` também vira o modo. O SDL
nunca tenta."* **As duas metades estavam erradas, e a fonte era o mesmo arquivo
do SDL, mais adiante.**

- `HIDAPI_DriverPS5_SetEnhancedMode` (`:876-884`) manda um pacote de efeitos
  vazio com o comentário *"Switch into enhanced report mode"*. É o SDL
  **tentando**, e é a rota que ele usa quando a aplicação pede modo estendido.
- `HIDAPI_DriverPS5_TickleBluetooth` (`:829-833`), no ramo em que o controle
  ainda está no modo básico, desiste de cutucar e desconecta, com esta razão
  escrita: *"We can't even send an invalid effects packet, or it will put the
  controller in enhanced mode."*

**Então o gatilho tem DOIS caminhos, não um:** ler um feature pelo canal de
controle, **ou** escrever um output `0x31` pelo canal de interrupção — e o
segundo funciona mesmo com o CRC errado, que é o que torna a frase do SDL uma
queixa e não uma receita.

**Grau: `afirmado-no-doc`, fonte única, e ela é forte porque é uma fonte
dizendo algo CONTRA o próprio interesse** — o SDL preferiria poder cutucar a
pilha sem trocar o modo, e escreve que não pode.

E há um número de tempo, o único publicado: depois de forçar o modo, o SDL
espera **10 ms** antes de mandar mais efeitos (`:1084-1088`, *"Wait briefly
before sending additional effects"*). Escolha de engenharia, não medida do
aparelho.

### 5.2 A lista mínima de inicialização, por dois hosts independentes

| projeto | ordem dos features no vínculo novo |
|---|---|
| `awalol/DS5Dongle` (`src/bt.cpp:908-913`) | `0x09`, `0x20`, `0x22`, `0x05` |
| `SundayMoments/DS5_Bridge` (`src/bt.cpp:5448-5456`) | `0x20`, `0x09`, `0x22`, `0x05`, espaçados de **5 ms** |

**São os mesmos quatro**, em ordem quase igual, e são quatro dos que o censo dos
dezessete desta casa já mediu. Nenhum dos dois lê mais nada para começar a
funcionar, e nenhum dos dois trata o `0x01` depois disso. **Para pôr um
DualSense de pé por rádio, esses quatro bastam** — e três deles são os três
gatilhos da §1, o que fecha o círculo.

O `DS5_Bridge` também espaça: 5 ms entre pedidos de feature, fila de 16
(`:100-101`), no máximo 4 envios de áudio seguidos e estado velho aos 3 ms
(`:95-96`). Continua sendo política de host — nenhum deles cita limite do
aparelho.

### 5.3 As sementes de CRC não são mágicas: são o cabeçalho HIDP

Esta casa já sabe as três sementes e já mediu, em 27/08, que **escrever**
feature por rádio pede `0x53`. O que estes projetos acrescentam é a **razão
mecânica**, e ela explica as quatro de uma vez.

O `DS5Dongle` põe `0xA2` como **primeiro byte do pacote na rede** antes de todo
report de saída (`src/bt.cpp:846-850`), e o gabarito de CRC do mesmo arquivo
começa literalmente com `0xa2, 0x31, 0x01` (`:83-84`). O SDL chama a variável de
cabeçalho HIDP com todas as letras.

| byte | transação HIDP | onde aparece em uso |
|---|---|---|
| `0x43` | `GET_REPORT` \| `FEATURE` | `DS5Dongle:882`, `DS5_Bridge:5420` |
| `0x53` | `SET_REPORT` \| `FEATURE` | `DS5Dongle:895`, `DS5_Bridge:5433` |
| `0xA3` | `DATA` \| `FEATURE` | a resposta que chega, `DS5Dongle:671` |
| `0xA2` | `DATA` \| `OUTPUT` | todo report de saída, `DS5Dongle:850` |

**O que isso muda para quem escreve aqui:** o hidraw do Linux esconde esse byte
— você escreve começando no report id —, mas o CRC que o firmware confere
**inclui o byte escondido**. É a explicação de um fato que esta casa pagou caro
para achar medindo.

### 5.4 Três pedaços da escada `0x31`-`0x39`, de graça

Não é do assunto desta página, e fica aqui porque foi lido no caminho e a
canônica registra estes pontos como abertos. **Grau: `afirmado-no-doc`.**

- **O `0x36` carrega o `common` de 47 bytes no offset 13.** Não é dedução: o
  `DS5_Bridge` localiza o payload tratando os dois casos explicitamente — `0x31`
  → offset **3** (conferindo que o byte 2 é o tag `0x10`), `0x36` → offset
  **13** (`src/bt.cpp:4575-4614`). O offset 3 do `0x31` bate byte a byte com a
  struct do driver desta máquina, o que dá crédito ao 13 do `0x36`.
- **O `0x39` é áudio em lote e não carrega estado do controle** (`:4691`); e o
  contador de sequência é **um por vínculo, não um por report id** — ele é
  compartilhado com o `0x39` e atribuído logo antes do L2CAP (`:1741-1744`).
- **O `0x32` de 142 bytes é o report de estado de um host real.** O `DS5Dongle`
  acende lightbar e player LEDs escrevendo `0x32` com **142 bytes**, cabeçalho
  `0x32 0x10 0x90 0x3f` e a estrutura de estado a partir do offset 4
  (`src/bt.cpp:917-923`). **142 é exatamente o número desta casa** — o descritor
  do rádio declara 141 mais o id, e o `btmon` de 15/08 registrou `dlen 147` =
  142 + 5. **Aviso:** o `0x31` e o `0x32` **não** compartilham o cabeçalho, então
  quem for medir a escada não pode supor um envelope só.

### 5.5 O feature `0x08` escrito é controle de energia

Esta casa leu o feature `0x08` (48 bytes) e o achou **todo zero nos quatro
aparelhos**. O que ninguém aqui sabia é o que acontece ao **escrevê-lo**: o
`DS5_Bridge` desliga o controle mandando `SET_REPORT` do feature `0x08` com o
byte de valor `0x02`, sob o comentário de que **`1` = ligado e `2` = desligado**
(`src/bt.cpp:2375-2387`).

**É pista para a família `energia`, não afirmação medida** — e é escrita no
aparelho: quem ensaiar isso desliga um controle de verdade.

---

## 6. O QUE A INTERNET NÃO SABE

Esta lista é entrega tanto quanto a de cima: ela diz onde **só o aparelho
responde**, e é o que sobra para a bancada.

1. **Ninguém mediu o teto de escrita do DualSense.** Não achei uma única fonte
   pública com uma curva de "quantos reports de saída por segundo antes de
   degradar". Todo número que existe — os 4 ms do DS4Windows, os 8 ms daqui, os
   500 ms e os 10 ms do SDL, os 5 ms e os 3 ms do `DS5_Bridge` — é política de
   host, escolhida, nunca um limite medido do aparelho. **Onze fontes depois, o
   número do fabricante continua não existindo.**
2. **Ninguém sabe QUAL feature é o gatilho**, nem se o gatilho é o id ou o ato.
   Quatro fontes, três ids, nenhuma comparação — e os dois hosts de Pico W leem
   os três, o que não desempata.
3. **Ninguém mediu quanto tempo a troca leva.** Os 10 ms do SDL (§5.1) são
   escolha de engenharia; ninguém publica o intervalo entre a leitura do feature
   e o primeiro `0x31`, nem o que acontece com um efeito mandado antes disso.
   <!-- Esta entrada SUBSTITUIU a de algumas horas antes, que dizia "ninguém diz
        se um report de SAÍDA 0x31 também vira o modo, e o SDL nunca tenta". As
        duas metades caíram na segunda varredura: o SDL tenta, e diz que não
        consegue evitar. Ver §5.1. -->
4. **Ninguém documenta como voltar ao modo básico** sem desligar o controle, nem
   se a troca sobrevive a suspensão do host ou a uma reconexão sem novo
   pareamento.
5. **O byte 1 do `0x31` de ENTRADA continua sem dono.** As wikis o leem como
   bit0 `HasHID`, bit1 `HasMic`, bits 4-7 `SeqNo`; o `dsremap` viu a constante
   `0x51`. O driver desta máquina simplesmente o pula (`&data[2]`, `:1592`).
   Ninguém mediu isso aqui, e as duas leituras podem ser a mesma coisa vista de
   ângulos diferentes.
6. **Nada disto vale para o DualSense Edge**, que ninguém desta lista separa do
   DualSense comum nesta parte do protocolo.

---

## As fontes, com endereço

| fonte | o que ela sustenta aqui |
|---|---|
| `libsdl-org/SDL` — `src/joystick/hidapi/SDL_hidapi_ps5.c` | os dois comentários do gatilho (`:426-429`, `:434-437`); a detecção de modo por tamanho (`:405-422`); o cabeçalho e o CRC do `0x31` (`:1100-1121`); os 48 B do cabo (`:1107-1109`); o keepalive sem CRC (`:814-830`) e o `BLUETOOTH_DISCONNECT_TIMEOUT_MS = 500` (`:44`) |
| wiki do SDL3 — `SDL_HINT_JOYSTICK_ENHANCED_REPORTS` | a troca é de mão única até desligar o controle |
| `dsremap` — *Reverse engineering* | `GET_REPORT 0x20` vira o `0x31`; o byte extra depois do id |
| `nondebug/dualsense` | ler a calibração vira o report; o `0x01` por rádio tem 10 bytes |
| DS4Windows (`CircumSpector/DS4Windows` e a documentação) | *PC friendly mode* × *Native PS mode*; o `BTPollRate` (default 4, `0..16`) é campo **do DS4**, pelos textos do próprio programa |
| `assets/dkms/hid-playstation/hid-playstation.c` | tudo que leva `:NNN` nesta página — é o fonte que compilou o módulo carregado nesta máquina |
| `awalol/DS5Dongle` — `src/bt.cpp` | a lista mínima de features (`:908-913`); o cabeçalho HIDP na rede (`:846-850`, `:83-84`, `:671`, `:882`, `:895`); o `0x32` de 142 B (`:917-923`) |
| `SundayMoments/DS5_Bridge` — `src/bt.cpp` | a mesma lista com espaçamento de 5 ms (`:5448-5456`, `:100-101`); o `common` do `0x36` no offset 13 (`:4575-4614`); a sequência compartilhada (`:1741-1744`); o feature `0x08` de energia (`:2375-2387`) |
| `flok/pydualsense` — `pydualsense.py` | vale pelo que NÃO tem: nenhum passo de modo, e um "TODO" de detectar a conexão (`:193`) |

Nenhuma linha de código de terceiro foi copiada para esta árvore. O que veio
foi número, offset, ordem e endereço — que é informação, não obra.

---

## O método, para a próxima leva repetir

Ela pediu um jeito de preencher a lacuna da Sony sem bancada:
*"lançar novo workflow pra agentes procurarem no Github tais canais ou tais id.
(…) como é só informação eles trouxeram e me ajudaram no mapa do controle."*
<!-- noqa-acento: citação literal dela -->

O que funcionou, na ordem:

1. **Ler a casa primeiro.** A canônica e o `hid-playstation.c` desta árvore já
   respondiam metade. Caçar o que já se sabe é o desperdício mais comum.
2. **Busca por CÓDIGO, não por prosa.** A busca de código do GitHub achou em
   segundos o que a busca em texto não achava — e a frase distintiva de um
   comentário é a melhor consulta que existe.
3. **Procurar quem teve de implementar do ZERO.** Foi a veia nova desta leva
   (§5) e a que rendeu mais: um host que não fala com o kernel não pode pular
   passo nenhum.
4. **Contar as fontes que concordam SEM se citarem.** Três projetos publicando
   três ids diferentes para o mesmo efeito disseram, sem querer, que o gatilho
   talvez não seja o id.
5. **Fazer a segunda varredura antes de fechar.** A primeira varredura desta
   leva escreveu na lista do §6 que o SDL *"nunca tenta"* mandar output para
   trocar o modo. A segunda achou a frase contrária no mesmo arquivo. **Uma
   lista do que não se sabe é uma afirmação, e afirmação se confere.**
6. **Cruzar com o driver antes de acreditar.** Nada nesta página contradiz o
   `hid-playstation`; se contradissesse, o driver venceria e a contradição seria
   o achado.
