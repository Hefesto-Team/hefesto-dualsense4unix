# Os externos — a referência canônica do Pro Controller e do 8BitDo

**A fonte única de verdade deste projeto sobre o que os controles que NÃO são
DualSense entendem.**

- **Levantado em:** 07/08/2026, entre 19h10 e 19h45, com a máquina dela **viva**
  e os **quatro** controles no rádio — dois DualSense, um Pro Controller
  Nintendo genuíno e um 8BitDo em modo PS4. Por três frentes de pesquisa
  simultâneas (o driver do kernel, o rádio, o conhecimento público), e conferido
  contra o código desta árvore.
- **Leitura pura.** Nenhuma escrita em `hidraw`, nenhum serviço reiniciado,
  nenhum controle derrubado. O que só fecha escrevendo no aparelho está na
  seção 8, como protocolo para ela executar.
- **Por que este arquivo existe:** ela pediu, literal — *"não deveríamos mapear
  a conexão bt dos outros 2, pro e 8bitdo?"*. E a lacuna estava medida: um
  `grep -i -E "nintendo|8bitdo|pro controller|057e"` em `docs/protocol/`
  devolvia **zero linhas**. A casa mapeou o DualSense a fundo e nunca mapeou os
  vizinhos.
- **Documento irmão:**
  [a referência canônica do DualSense](dualsense-referencia-canonica.md). Quando
  as duas páginas discordarem, **cada uma vence no seu aparelho** — e as
  diferenças entre as linhagens estão marcadas aqui, uma a uma, porque é
  justamente onde um instrumento escrito para um controle escreve lixo no outro.
- **Regra de uso:** esta página vence sobre docstring, comentário de regra
  `udev` e página de uso — mas só nas linhas marcadas ALTA ou MEDIDO AQUI.

---

## 0. Como ler esta página

### 0.1 Os graus de confiança

Toda linha técnica aqui carrega um grau, e ele não é decorativo. É a mesma
tabela da referência do DualSense, e pela mesma razão: esta casa já tomou
decisão errada por confundir "documentação de comunidade" com "fato".

| grau | significa |
|---|---|
| **ALTA** | está no código do driver que **esta máquina carrega**, ou em duas engenharias reversas independentes que concordam |
| **MÉDIA** | uma fonte de comunidade respeitada, sem contradição conhecida, **ainda não conferida na máquina dela** |
| **BAIXA** | inferência, ou fonte única, ou derivação de duas medições que não se tocam |
| **MEDIDO AQUI** | conferido nesta máquina, nesta sessão, com o comando citado |

### 0.2 As três camadas que esta página separa — e é o motivo de ela existir

A referência do DualSense separa "a Sony documenta" de "o kernel implementa".
Aqui a separação é de **três** camadas, e confundi-las já produziu conclusão
errada nesta casa duas vezes:

1. **O DRIVER FAZ.** O que o `hid-nintendo` ou o `hid-playstation` **desta
   árvore** emitem e parseiam. Verificável por leitura de código, sem hardware.
   É a camada mais barata e a mais confiável — e **não** diz o que o aparelho
   aceita.
2. **O APARELHO ACEITA.** O que o firmware honra de verdade. Só fecha
   **medindo**, com o controle na mão dela. É a camada mais cara e a mais rasa
   deste documento.
3. **ALGUÉM NA INTERNET DISSE.** Engenharia reversa de comunidade. **Toda linha
   desta camada é SUSPEITA até ser conferida contra a máquina dela**, e cada uma
   diz aqui se foi conferida, e com que desfecho.

E a lei desta página, medida no 8BitDo e válida para os dois aparelhos:

> **O descritor DECLARA; o firmware IMPLEMENTA; e os dois divergem.** O 8BitDo
> declara, em 364 bytes de descritor, a árvore de reports inteira de um
> DualShock 4 — e falha nos três feature reports que a árvore promete. Qualquer
> detecção de capacidade por descritor classifica esse controle como um
> DualShock 4 completo, e erra.

---

## 1. O inventário — os quatro aparelhos, agora

**MEDIDO AQUI, 07/08/2026 19h38 a 19h41** (`/proc/bus/input/devices`,
`/sys/class/hidraw/*/device/uevent`, `/sys/bus/hid/devices/`, `hcitool con`,
`busctl` no `org.bluez`):

| aparelho | OUI | VID:PID (BT) | driver | instância HID | hidraw | descritor |
|---|---|---|---|---|---|---|
| **Pro Controller** genuíno | `e0:f6:b5` | `057e:2009` | `nintendo` | `.0017`, de 06/08 22:21:11 | `hidraw7` | **170 B** |
| **8BitDo em modo PS4** | `e4:17:d8` | `054c:05c4` | `playstation` | **NENHUMA** — ver 1.2 | **nenhum** | 364 B (lido às 19h26) |
| DualSense | `a0:fa:9c` | `054c:0ce6` | `playstation` | `.0024` | `hidraw6` | 320 B |
| DualSense | `14:3a:9a` | `054c:0ce6` | `playstation` | `.0026`, de 07/08 19:07:16 | `hidraw8` | 320 B |

Endereços mascarados pela máscara da casa (octetos 4 e 5 zerados); há portão que
reprova o contrário.

**As duas premissas do pedido dela estão certas, e ficam MEDIDO AQUI:** o Pro
genuíno por Bluetooth casa com o driver `nintendo`; o 8BitDo em modo PS4 casa com
o `playstation`. É exatamente essa bifurcação de driver que o
`resolve_external_leds` (`core/external_leds.py`) usa para escolher entre o
caminho da barra verde e o da lightbar RGB.

### 1.1 Os módulos, e eles NÃO são os do kernel de fábrica

**MEDIDO AQUI:** os dois drivers carregados são os **DKMS desta casa**
(`modinfo -F filename` aponta para `updates/dkms`), não o vanilla. Toda medição
de taxa, de probe e de recuperação desta página **só vale declarando isso**.

`hid_nintendo`, parâmetros vivos em 07/08/2026 19h39
(`for f in /sys/module/hid_nintendo/parameters/*; do echo "$(basename $f)=$(cat $f)"; done`):

| parâmetro | aqui | vanilla |
|---|---|---|
| `bt_probe_retries` | **3** | 0 |
| `input_report_wait_ms` | **500** | 250 |
| `probe_info_timeout_ms` | **4000** | 2000 |
| `sync_send_tries` | **4** | 2 |
| `subcmd_rate_max_attempts` | 25 | 25 |
| `subcmd_silence_streak_max` | **3** | 0 |
| `skip_tx_on_rate_exceeded` | **Y** | (não existe) |
| `register_leds_on_set_failure` | **Y** | (não existe) |
| `usb_cmd_pad_to_report`, `usb_send_conn_status`, `usb_probe_degrade` | **Y** | (não existem) |

`hid_playstation`, mesma leitura: `ds4_short_pairing_info=Y`,
`ds4_synthetic_mac=Y`, `feature_retries=2`. GRAU: MEDIDO AQUI.

### 1.2 O achado desta varredura — o 8BitDo com o link de pé e SEM HID nenhum

Este é o fato mais importante desta página, e ele **aconteceu durante a
varredura**, entre uma frente e outra:

- **19h17 a 19h30** — as três frentes mediram o 8BitDo com o link inteiro de pé
  e **mudo**: ACL vivo, HID registrado (`0005:054C:05C4.0025`, desde 19:05:44),
  `/dev/hidraw2` criado, três nós de input, nó de bateria — e **zero** relatórios
  em 3 s, em 6 s e de novo em 20 s de leitura pura do `hidraw`, e zero eventos de
  `evdev` nos três nós. Controle positivo no mesmo minuto e no mesmo rádio: o Pro
  entregando ~89 relatórios/s. GRAU: MEDIDO AQUI.
- **~19h33** — o `bluetoothd` registra `profiles/input/server.c` recusando
  conexão de entrada com `Operation already in progress (114)` às 19:32:58 e
  `HUP or ERR on socket: Connection refused (111)` às 19:33:42. GRAU: MEDIDO
  AQUI.
- **19h38 a 19h41** — o 8BitDo **não tem mais HID nenhum**: nada em
  `/sys/bus/hid/devices/`, nada em `/sys/devices/virtual/misc/uhid/`, nenhum
  `hidraw`, nenhum nó de input, nenhum nó de bateria. **E o link de rádio
  continua de pé:** `hcitool con` mostra `ACL e4:17:d8:00:00:83 handle 12 state 1
  lm CENTRAL AUTH ENCRYPT`, e o BlueZ diz `Connected=true`, `Bonded=true`,
  `Trusted=true`. GRAU: MEDIDO AQUI.

**A leitura, e o grau de cada parte:**

| afirmação | GRAU |
|---|---|
| o 8BitDo passou de "mudo com HID" para "sem HID, com ACL vivo" numa janela de 8 minutos, observada | **MEDIDO AQUI** |
| esta é uma **terceira** forma de zumbi, que a casa não tinha catalogado — as duas da vigia 3 são "SDP não resolvido" e "pilha do controle travada" | **MEDIDO AQUI** (leitura de `scripts/bt_health_watchdog.sh` contra o estado medido) |
| a sessão HIDP caiu **do lado do aparelho**, com o ACL preservado | **BAIXA** — é a explicação com mecanismo, e separá-la de "o BlueZ derrubou" exige `btmon` como root |
| isto enterra a hipótese "ele só manda quando algo muda, o silêncio parado na mesa é normal" | **BAIXA** — enfraquece muito, mas silêncio e queda de HIDP podem ter causas distintas |

**E o defeito de produto que sai daí, MEDIDO AQUI:** o watchdog rodou às
19:33:20, 19:35:20, 19:37:20 e 19:39:21 — quatro passagens **depois** do HID
sumir — e **não disse uma palavra** sobre o 8BitDo. Ele só logou a política de
link do Pro. A razão está no próprio script, `scripts/bt_health_watchdog.sh`
linha 165: a vigia pula todo aparelho cujo cache de SDP já tenha
`[ServiceRecords]`, com o comentário *"é OUTRA doença (bond, driver, ...)"*. O
8BitDo tem o cache completo, porque já conectou dezenas de vezes. **A doença
está nomeada no comentário e não tem cura em lugar nenhum.**

---

## 2. Onde as três frentes DISCORDARAM

Discordância registrada vale mais que consenso fabricado. Estas são todas, com
quem vence e por quê.

| # | o que discordou | as versões | quem vence, e por quê |
|---|---|---|---|
| 1 | **taxa de relatórios do Pro por Bluetooth** | frente do rádio: **89,1/s** (446 em 5,0 s); frente pública: **86/s** (259 em 3,0 s) | **89,2/s** — MEDIDO AQUI numa terceira leitura de **6,0 s** (536 relatórios, todos `0x30`, todos de 49 bytes). As duas janelas longas concordam; a de 3 s é curta demais para a resolução que o número exige. **11,2 ms** entre relatórios |
| 2 | **unidade do contador de perda de IMU** | frente do rádio: `N` são **amostras**, e divide por 3 para achar relatórios; frentes do driver e pública: `N` são **relatórios** | **relatórios** — ALTA. O código diz `dropped_pkts = (delta - min(delta, threshold)) / avg_delta_ms`, e `avg_delta_ms` é o intervalo entre **relatórios**. A divisão por 3 da frente do rádio subestima a perda em 3x |
| 3 | **tamanho do descritor do 8BitDo** | frente do rádio: **364 bytes**, com aviso de que `stat` mente; frente pública: "parser próprio sobre o descritor (**4096 bytes**)" | **364** — MEDIDO AQUI. Os 4096 são o tamanho da **página do sysfs**, não do descritor. A frente pública caiu na armadilha que a frente do rádio tinha acabado de documentar. Ver nota de instrumento 2 |
| 4 | **quantas perdas de IMU o Pro teve** | 1319 avisos (19h20) / 1374 episódios e 8994 relatórios (19h30) / 2388 rajadas no boot | **nenhuma está errada** — o número **cresce enquanto se mede**. Às 19h41: **1613** episódios e **10285** relatórios perdidos hoje; **2684** e **18897** no boot inteiro. MEDIDO AQUI. Toda contagem desta métrica tem de vir com o carimbo de hora |
| 5 | **o limiar do aviso de perda** | frente do driver: "a partir de 3 pacotes perdidos" | **a partir de 4** — ALTA. O código é `if (dropped_pkts > JC_IMU_DROPPED_PKT_WARNING)` com a constante em **3**, e `>` não é `>=` |
| 6 | **quantos subcomandos o driver envia no probe** | frente do driver: "DOZE subcomandos"; a mesma frente, três linhas depois: "`grep` devolve exatamente **sete** usos de `subcmd_id = JC_SUBCMD`" | **as duas estão certas e falam de coisas diferentes** — ALTA. São **sete** funções que montam subcomando no arquivo inteiro, e o probe as chama **doze vezes** (a leitura de SPI é chamada seis vezes com endereços distintos). Conferido: os sete usos estão nas linhas 1226, 1240, 1265, 1549, 1562, 1575 e 2704 de `assets/dkms/hid-nintendo/hid-nintendo.c` |

**Uma sétima divergência, que é com o passado desta casa e não entre as
frentes:** a seção 3.4 do
[estudo dos externos de 07/08](../process/estudos/2026-08-07-ISOLAR-os-externos-o-metodo-da-lightbar-no-pro-e-no-8bitdo.md)
registrou *"~268 pacotes por segundo"* no Pro. **Aquilo não era a taxa do
rádio** — era a taxa de **amostra** de IMU, que é 3x a de relatório. Os dois
números são compatíveis (89,2 x 3 = 268), e a página fica corrigida aqui, com
data. GRAU: MEDIDO AQUI.

---

## 3. O Pro Controller genuíno — `057e:2009`, driver `nintendo`

### 3.1 O que o distingue, por barramento

| chave | por Bluetooth | por USB | GRAU |
|---|---|---|---|
| VID:PID | `057e:2009` — **igual ao do clone** | `057e:2009` — **igual ao do clone** | MEDIDO AQUI |
| nome | `Pro Controller` — **igual ao do clone** | idem | MEDIDO AQUI |
| `bcdDevice` | **não existe** — o Modalias por rádio é `usb:v057Ep2009d0001`, com `d0001` fixo | `0210` genuíno, `0200` clone | MEDIDO AQUI |
| versão de HID que o kernel imprime | `BLUETOOTH HID v80.01` | — | MEDIDO AQUI |
| **OUI do endereço de rádio** | **`e0:f6:b5` genuíno, `e4:17:d8` clone** | — | MEDIDO AQUI |

ATENÇÃO: **o discriminador de USB não atravessa para o Bluetooth.** O campo
`d` do Modalias publicado por rádio é `0001` nos dois, e **não** é o `bcdDevice`.
Por rádio o **único** discriminador entre o Pro genuíno e o clone é a OUI. A
árvore trata isso certo em três lugares independentes que concordam:
`NINTENDO_REAL_OUI` em `daemon/subsystems/external_identity.py:200`,
`scripts/bt_active_mode.sh`, e `assets/82-nintendo-pro-nosniff.rules`; e a
`assets/84-nintendo-pro-variant.rules`, que usa o `bcdDevice`, é escopada só ao
cabo. GRAU: ALTA.

### 3.2 Pareamento e probe — o que o driver faz sozinho, sem o Hefesto pedir

**Por Bluetooth NÃO existe handshake.** Todo o ramo (`JC_USB_CMD_HANDSHAKE
0x02`, `BAUDRATE_3M 0x03`, `NO_TIMEOUT 0x04`, dentro do report de saída `0x80`)
roda sob `joycon_using_usb()`, que é literalmente `hdev->bus == BUS_USB`. Por
rádio o driver vai direto ao `joycon_read_info()`. GRAU: ALTA
(`assets/dkms/hid-nintendo/hid-nintendo.c:862`, `:2847`, `:2854`, `:2880`).

**A sequência exata do probe por rádio**, doze subcomandos, nesta ordem — GRAU:
ALTA (`joycon_init`, por volta de `:2839` a `:2985`):

1. `REQ_DEV_INFO` (`0x02`);
2. magia de calibração do stick esquerdo (SPI `0x8010`) e do direito (`0x801B`);
3. leitura da calibração dos dois sticks;
4. magia de calibração da IMU (SPI `0x8026`);
5. leitura da calibração de fábrica da IMU (SPI `0x6020`, 24 bytes);
6. `ENABLE_IMU` (`0x40`, argumento `0x01`);
7. `SET_REPORT_MODE` (`0x03`, argumento `0x30`);
8. `ENABLE_VIBRATION` (`0x48`, argumento `0x01`);
9. `SET_PLAYER_LIGHTS` (`0x30`);
10. `SET_HOME_LIGHT` (`0x38`, brilho 0).

**A calibração do Pro NÃO vem de feature report** — vem da flash SPI do próprio
controle, pelo subcomando `0x10`, com endereço de fábrica (`0x603d`/`0x6046`
para sticks, `0x6020` para IMU) e endereço de usuário com byte mágico (`0xB2
0xA1` em `0x8010`/`0x8026`). Sem o mágico, o driver usa a de fábrica. GRAU: ALTA
(`:186-212`, `:1252-1300`). **Contraste com o DualSense**, onde a calibração é o
feature report `0x05` de 41 bytes
([referência canônica](dualsense-referencia-canonica.md), seção 5): um
instrumento escrito para um **não serve** para o outro.

**O que o driver NUNCA envia, em barramento nenhum** — e isto é o que fecha, pelo
código, metade da hipótese H2 do estudo de hoje:

| subcomando | o que faria | emitido pelo Linux? |
|---|---|---|
| `0x01` `MANUAL_BT_PAIRING` | reescrever a informação de pareamento | **não** |
| `0x06` `SET_HCI_STATE` | `00` desconectar/dormir, `01` reiniciar, `02` reiniciar em pareamento | **não** |
| `0x07` `RESET_PAIRING_INFO` | esquecer o host | **não** |
| `0x08` `LOW_POWER_MODE` | pôr o controle em HID OFF ao desconectar | **não** |

GRAU: ALTA. As quatro constantes existem no cabeçalho (`:128`, `:133`, `:134`,
`:135`) e **nenhum caminho de código as usa** — `grep -n "subcmd_id = JC_SUBCMD"`
devolve sete linhas, e nenhuma é uma dessas. **Consequência: o kernel não toca no
pareamento nem no estado de energia do Pro.** Se o Pro tem timer de ociosidade,
ele não vem do driver.

### 3.3 Os reports — o envelope, e ele é o OPOSTO do DualSense

O descritor de 170 bytes declara — MEDIDO AQUI (parser próprio sobre
`/sys/class/hidraw/hidraw7/device/report_descriptor`, tamanho real por
`wc -c`):

| direção | report | corpo | o que é | o driver usa? |
|---|---|---|---|---|
| saída | `0x01` | 48 B | rumble + subcomando | **sim** |
| saída | `0x10` | 48 B | rumble puro | **sim** |
| saída | `0x11`, `0x12` | 48 B | dados de MCU/NFC/IR | não |
| entrada | `0x21` | 48 B | resposta de subcomando | **sim** |
| entrada | `0x30` | 48 B | estado completo (botões + IMU) | **sim** |
| entrada | `0x31` | 361 B | MCU/NFC/IR | parseia |
| entrada | `0x32`, `0x33` | 361 B | MCU/NFC/IR | não |
| entrada | `0x3F` | botões + hat + 4 eixos | o relatório "simples" de HID puro | **não** |

**Só chega o `0x30`.** MEDIDO AQUI: 536 relatórios em 6,0 s, **todos** `0x30`,
**todos** de 49 bytes no fio (1 de ID + 48 de corpo). Não chega `0x3F`, não chega
`0x21` fora de subcomando. Quem escolhe é o driver, pelo `SET_REPORT_MODE` com
`data[0] = 0x30`, e **o Linux nunca pede outro modo**. GRAU: ALTA + MEDIDO AQUI.

ATENÇÃO — **a diferença estrutural com o DualSense, e ela é grande:**

| | Pro Controller | DualSense |
|---|---|---|
| o Bluetooth muda o report? | **não** — o envelope é idêntico por cabo e por rádio | **sim** — report inteiro diferente |
| CRC-32 | **não existe** | **sim**, sementes `0xA1`/`0xA2`/`0xA3` |
| número de sequência | só o `packet_num`, **4 bits** (0 a 0xF), byte 1 da saída | `_bt_seq` |
| item `85 31` no descritor | não se aplica | é a marca do Bluetooth |

GRAU: ALTA (`struct joycon_subcmd_request` em `:580-586`; `__joycon_hid_send` em
`:867-881`, sem qualquer CRC; contraste com a
[referência do DualSense](dualsense-referencia-canonica.md), seções 2 e 7).
**Um instrumento que assuma CRC no Pro escreve lixo.**

A única diferença de conteúdo entre os barramentos é o report `0x80` (comandos de
USB), que só existe no cabo. GRAU: ALTA.

### 3.4 A taxa — o limitador que custa caro

O `joycon_enforce_subcmd_rate` roda antes de **cada** subcomando e de **cada**
pacote de rumble. Para liberar a transmissão exige **três** condições juntas —
GRAU: ALTA (`:973-1048`):

1. pelo menos `JC_SUBCMD_VALID_DELTA_REQ` = **3** relatórios de entrada
   consecutivos com intervalo entre 8 e 17 ms;
2. pelo menos **60 ms** desde o último envio por Bluetooth
   (`JC_SUBCMD_RATE_LIMITER_BT_MS`), contra **20 ms** por USB;
3. conseguido isso, ainda dorme `JC_SUBCMD_TX_OFFSET_MS` = **4 ms** para não
   colidir com a recepção.

Teto: `subcmd_rate_max_attempts` = **25** tentativas.

**O que acontece ao estourar as 25 tentativas DEPENDE do módulo, e a máquina dela
NÃO roda o vanilla.** No vanilla o driver loga `exceeded max attempts` e
**transmite assim mesmo, sem ritmo** — e o comentário do próprio código diz que é
isso que derruba o link Bluetooth. Aqui, com `skip_tx_on_rate_exceeded=Y`, o TX é
**suprimido**: a função devolve `-EAGAIN`, o envio síncrono o converte em
`-ETIMEDOUT`, e **nenhum byte vai ao rádio**. GRAU: ALTA (`:1021-1035`) +
MEDIDO AQUI (o parâmetro).

ATENÇÃO: **isto muda a leitura do E-1 do estudo de hoje.** As 348 recusas de
06 e 07/08 foram pedidos **nossos recusados antes de ir ao ar**, não tráfego que
degradou o rádio. O storm era de CPU e de log, não de rádio. GRAU: ALTA (segue
do código, dado o parâmetro medido).

**O `subcmd_silence_streak_max=3`** (remendo da casa, ligado aqui) faz o driver
desistir cedo de um controle mudo. O comentário do próprio remendo traz a
medição que o justifica, e ela é a régua do custo: **sem ele, UMA escrita de LED
num controle calado custa 4 x 25 x 500 ms = 50 segundos segurando o
`output_mutex`, mais 100 linhas de log, repetido para sempre a cada escrita.**
GRAU: ALTA (`:883-911`) + MEDIDO AQUI (o parâmetro).

### 3.5 A IMU

**Quem liga é o DRIVER, incondicionalmente, em TODO barramento.** O
`joycon_enable_imu()` (subcomando `0x40`, `data[0] = 0x01`) é chamado dentro do
`joycon_init` sob `if (joycon_has_imu(ctlr))`, **sem nenhum porteiro de bus**
(`:1569-1580`, chamada em `:2937`). O pacote que ele monta é **byte a byte** o
mesmo que o `build_enable_imu_packet` (`core/external_leds.py:155`) monta.
GRAU: ALTA.

**As escalas, e elas NÃO são as do DualSense:**

| | Pro Controller | DualSense |
|---|---|---|
| acelerômetro | **4096** LSB/g, mais ou menos 8 g | 8192 LSB/g, mais ou menos 4 g |
| giroscópio | **14,247** LSB por grau/s, mais ou menos 2000 graus/s | 1024 LSB por grau/s, mais ou menos 2048 |

GRAU: ALTA (`JC_IMU_ACCEL_RES_PER_G` em `:237`, `JC_IMU_GYRO_RES_PER_DPS` em
`:259`, com `JC_IMU_PREC_RANGE_SCALE` de 1000 em `:256`; contra a
[referência do DualSense](dualsense-referencia-canonica.md), seção 5).
**Armadilha carregada:** quem comparar eixos do Pro com eixos do DualSense sem
converter erra por **2x** no acelerômetro e por cerca de **14x** no giroscópio.

**A base de tempo — três medições que fecham entre si:**

| medida | valor | GRAU |
|---|---|---|
| relatórios `0x30` no fio | **89,2/s**, um a cada **11,2 ms** | MEDIDO AQUI (6,0 s de `hidraw` puro) |
| amostras de IMU por relatório | **3** (usualmente 5 ms entre elas) | ALTA (`:1644-1646`) |
| taxa de amostra esperada | 89,2 x 3 = **268/s** | derivada — e bate com os 267 SYN/s medidos no nó de IMU |
| `avg_delta` que o kernel **aprende** | **11 ms** em 1460 das 1613 amostras de hoje, com cauda até 22 | MEDIDO AQUI (`journalctl -k \| grep -oP 'avg_delta=\K[0-9]+' \| sort -n \| uniq -c`) |

**Três fontes publicadas erram este número, e ficam refutadas aqui:**

| fonte | diz | GRAU da fonte | desfecho |
|---|---|---|---|
| dekuNukem | "@60Hz, ou @120Hz se Pro Controller" | MÉDIA | **refutado** nesta mesa |
| comentário do driver | "pro controller (bluetooth): every 8 ms" (125 Hz) | o próprio autor chama de *"o coringa"* | **refutado** nesta mesa |
| default do driver | `JC_IMU_DFLT_AVG_DELTA_MS` = **15** | ALTA como default | **36% maior que a realidade deste link** — e o driver o corrige sozinho depois de 300 amostras |

**Honestidade obrigatória:** o próprio comentário do driver já avisava que o
número publicado não vale — *"In my own testing, I've discovered that my pro
controller either reports IMU sample batches every 11ms or every 15ms."* O
controle dela está no ramo de 11 ms. GRAU: ALTA.

ATENÇÃO: **quem integrar velocidade angular do Pro pela constante do driver, em
vez de pelo valor aprendido, erra a escala.** É o análogo, para o Pro, da
divergência que a `GYRO-EDGE-RATE-01` deixa aberta para o DualSense.

#### O instrumento de qualidade de rádio que estava de graça no journal

O driver avisa sempre que perde **mais de 3** relatórios de IMU seguidos
(`JC_IMU_DROPPED_PKT_WARNING` = 3, e o teste é `>`), com a linha
`compensating for N dropped IMU reports`. `N` conta **relatórios**, não amostras
— ver a divergência 2 da seção 2. GRAU: ALTA (`:1718-1725`).

**MEDIDO AQUI, 07/08/2026 19h41:**

| janela | episódios | relatórios perdidos |
|---|---|---|
| boot inteiro | **2684** | **18897** |
| hoje (07/08) | **1613** | **10285** |

E a perda **não é uniforme** — é a coisa mais próxima de um medidor de contenção
de rádio que esta casa tem. Por janela de 10 minutos, hoje (MEDIDO AQUI):

```
12:00 a 14:00   1 a 4 episódios por janela      2 controles
14:20 a 15:20   13, 21, 43, 118, 42             3 controles + o storm de LED (até 15:27)
16:50 a 18:30   18, 25, 1, 2                    2 controles
18:40 a 19:30   103, 439, 208, 117, 155, 175    QUATRO controles no rádio
```

Os dois externos entraram às 18:40:19 e 18:41:38. **A partir do minuto em que o
rádio passou a ter quatro links, a perda de IMU do Pro subiu de uma a duas dezenas
por dez minutos para centenas.** GRAU: MEDIDO AQUI para os números;
**BAIXA** para a causa (é correlação com mecanismo plausível — contenção de
banda BR/EDR —, e o `btmon` que a fecharia não roda sem privilégio; ver 8.1).

ATENÇÃO — **isto contradiz a leitura "o Pro é o estável"**, e a contradição é
útil: o **link** do Pro não cai (20h33m sem trocar de instância), mas o **rádio**
dele está furado o dia inteiro, e piora com a mesa cheia. É a primeira medida
quantitativa da qualidade do link do Pro que a casa tem. **É também a explicação
candidata para o que ela sente** quando a mesa enche.

### 3.6 Os LEDs — e o que a árvore faz de errado neles

**São CINCO nós, com DUAS escalas e DOIS subcomandos diferentes** — GRAU: ALTA
(`:1219-1250`, `:2466-2510`, `:2547`, `:2586`) + MEDIDO AQUI (as escalas, em
`/sys/class/leds/*057E*/max_brightness`):

| nó | `max_brightness` | subcomando | payload |
|---|---|---|---|
| `:green:player-1..4` | **1** | `SET_PLAYER_LIGHTS` (`0x30`) | um byte: `(flash << 4) \| on` |
| `:blue:player-5` | **15** | `SET_HOME_LIGHT` (`0x38`) | 5 bytes: `01, brilho<<4, brilho\|(brilho<<4), 0x11, 0x11` |

Três consequências, e as três mordem:

1. **O `player-5` NÃO é um quinto jogador — é o LED HOME.** Ele tem escala 0-15
   porque o `0x38` é um **programa de PWM** (25 bytes de argumento na
   documentação pública: ciclos, duração, intensidades, transição); o Linux manda
   uma versão curta de 5 bytes. GRAU: ALTA para o subcomando e a escala; MÉDIA
   para os 25 bytes (fonte única de comunidade).
2. **O driver nunca usa o pisca em hardware:** ele sempre manda `flash = 0`.
   GRAU: ALTA.
3. **Escrever UM nó verde reescreve os QUATRO.** O
   `joycon_player_led_brightness_set` recompõe o bitmap dos quatro a partir do
   estado guardado e manda **um** subcomando `0x30`. O azul é um subcomando
   **separado**. Portanto uma escrita de "cinco lâmpadas" pelo `sysfs` custa
   **cinco** subcomandos ao rádio — quatro redundantes mais o do HOME. GRAU:
   ALTA.

**O driver acende sozinho um padrão de jogador no probe, antes de qualquer
software.** O `joycon_leds_create` aloca um id num IDA global e usa
`player_id % 8` como índice na tabela oficial da Nintendo — `{1,0,0,0}`,
`{1,1,0,0}`, `{1,1,1,0}`, `{1,1,1,1}`, `{1,0,0,1}`, `{1,0,1,0}`, `{1,0,1,1}`,
`{0,1,1,0}` — e loga `assigned player N led pattern`. GRAU: ALTA (`:630-641`,
com a URL da Nintendo no comentário; `:2513-2534`).

ATENÇÃO: **não existe estado "sem número" no Pro.** Com a escrita nossa calada
(`EXTERNAL_PLAYER_LED_ENABLED = False`), o que fica aceso é o padrão do kernel ou
o resíduo da última escrita nossa — hoje, `player-1=1, player-2=1, player-3=0,
player-4=0`, congelado desde 15:24:01 de 07/08. É o custo que a decisão dela
aceitou, e está registrado para ninguém o redescobrir como surpresa.

### 3.7 O rumble

- **Tubulação própria e contínua.** Enquanto houver efeito, o driver reenvia o
  último pacote a cada `JC_RUMBLE_PERIOD_MS` = **50 ms** (disparado pelo bit
  `vibrator_report` de cada relatório de entrada), e ainda manda
  `JC_RUMBLE_ZERO_AMP_PKT_CNT` = **5** pacotes de amplitude zero para **parar**.
  GRAU: ALTA (`:379-381`, `:1818-1841`, `:2044-2112`).
- **Cada um desses passa pelo MESMO limitador de 60 ms.** A chamada a
  `joycon_enforce_subcmd_rate` está em `:2069`, dentro do envio de rumble. GRAU:
  ALTA.
- **O driver expõe só `FF_RUMBLE` via `ff_memless`**, mapeando
  `strong_magnitude` no motor esquerdo e `weak_magnitude` no direito. As
  **frequências** ficam presas nos defaults 160 Hz (baixa) e 320 Hz (alta),
  enquanto o hardware aceita 41 a 626 Hz e 82 a 1253 Hz. Nada em espaço de
  usuário chega a essas frequências pelo `evdev` — só por `hidraw` cru. GRAU:
  ALTA para o driver; MÉDIA para as faixas do hardware (comunidade).
- **O rumble do Pro é HD rumble**, não amplitude simples: report de saída `0x10`
  com um byte de tempo e 4+4 bytes (banda alta e banda baixa) por lado, com
  tabelas de frequência **exponenciais**. GRAU: MÉDIA (fonte de comunidade; o
  kernel confirma apenas o ID do report).
- ATENÇÃO: **aviso de segurança de hardware.** A documentação pública diz, em
  letra grande: *"don't use real maximum values for Amplitude. Otherwise, they
  can damage the linear actuators"*. GRAU: MÉDIA — **fonte única, e por isso
  mesmo a ser respeitada, não testada.**

**A consequência que muda a leitura do E-1**, e ela tem nome: **existe um segundo
escritor possível da janela de TX do Pro** — qualquer jogo, ou a Steam, via
`ff_memless` — e ele produziria as **mesmas** linhas de `exceeded max attempts`
**sem nenhuma escrita do Hefesto no journal**. O E-1 concluiu "não há segundo
escritor **nesta janela**"; a janela dele não continha jogo com rumble no Pro.
GRAU: ALTA para o mecanismo; **SEM PROVA** de que tenha ocorrido.

**E há relato público independente do mesmo mecanismo:** o Pro Controller cai por
Bluetooth no Linux quando o rumble está ligado, reproduzido em **dois**
adaptadores diferentes, com `Bluetooth: Frame is too long (len 54, expected len
51)` no kernel. Aberto em 30/01/2021, **sem cura registrada**. GRAU: **MÉDIA** —
relato de usuário com log, não medição controlada, **não conferido nesta
máquina**. Casa com o comentário do kernel, o que não é o mesmo que confirmar.

### 3.8 Bateria — o instrumento que a casa quase usou errado

O `hid-nintendo` publica **só** `capacity_level` (cinco degraus), mais `status`,
`present` e `scope`. **Não existe `capacity`**: o vetor de propriedades tem
quatro entradas e a de percentual não é uma delas. GRAU: ALTA (`:1843-1878`,
`:2611-2659`) + MEDIDO AQUI (o nó
`nintendo_switch_controller_battery_0005:057E:2009.0017` existe, e não tem
arquivo `capacity`).

O byte `bat_con` do relatório `0x30`: **bit 0** = alimentado pelo host, **bit 4**
= carregando, **três bits altos** (`>> 5`) = o nível em cinco degraus (0 vazio,
1 baixo, 2 médio, 3 alto, 4 cheio). `status` só vira `Full` quando a capacidade é
`Full` **e** há alimentação externa. GRAU: ALTA.

**Não há percentual em lugar nenhum do protocolo** — o degrau é o dado, não uma
simplificação do driver. Concorda com dekuNukem (*"Battery level. 8=full,
6=medium, 4=low, 2=critical, 0=empty. LSB=Charging"* — o nibble dele são os bits
altos daqui). GRAU: ALTA (duas fontes independentes concordando).

ATENÇÃO: **é o defeito de instrumento que o item E-3 do estudo de hoje
apontou.** Um amostrador que leia `capacity` gravaria `AUSENTE` a noite inteira
neste controle. A régua de cinco degraus **funciona e tem sinal** — hoje o Pro
leu `capacity_level=Full`, `status=Charging` — só não tem percentual, e **não se
compara** com a régua do DualSense.

### 3.9 Energia — como se desliga um Pro, e por que ninguém desliga

- **O firmware não tem timer de ociosidade que desligue o aparelho num host que
  não seja o Switch.** Ele nunca desliga de verdade: fica em `sleep` e drena. A
  frase da fonte: *"For some weird reason, Nintendo does not allow turning Switch
  controllers off. They just stay in a sleep mode"*, e isso *"drains the battery
  fully in only about a week or two"*. GRAU: **MÉDIA** — fonte única de
  comunidade, ainda que com código que a implementa. **Coerente** com o medido
  aqui (20h33m de pé sem cair), o que não é confirmação.
- **Quem desligaria é o HOST, por subcomando `0x06` — e o Linux nunca o manda.**
  Ver a tabela de 3.2. É a **única** alavanca real de "desligar o Pro" que
  existe, e nem o kernel nem o Hefesto a usam. **Se ela algum dia pedir "desligar
  o controle pelo aplicativo", é por aqui.** GRAU: ALTA para a ausência de
  emissão; MÉDIA para a semântica do subcomando.
- **O console faz uma coisa que o Linux não faz:** *"Switch always sends `x08
  00` subcmd after every connection"* — isto é, **desliga explicitamente** o
  modo de baixa energia de transporte a cada conexão. Um controle que tenha sido
  posto em `0x08 01` por outro host fica em HID OFF ao desconectar, e **o Linux
  nunca o tira desse estado**. GRAU: **MÉDIA** (semântica de fonte única;
  a ausência de emissão pelo Linux é ALTA, verificada por `grep`). É uma quinta
  hipótese para "o controle não volta sozinho", e é mais barata de testar que a
  H3.
- **O firmware tem pareamento manual por subcomando `0x01`, em três passos**
  (manda o endereço do host, recebe o do controle, salva), e a documentação
  pública diz que serve *"to change on the fly the pairing info for the next
  session"*. **Isto dá mecanismo NOMEADO à H3** (*"volta ao Switch e esquece este
  host"*), que o E-5 ia testar só pelo comportamento: **o Switch reescreve a
  informação de pareamento por subcomando, e o BlueZ não fica sabendo.** GRAU:
  MÉDIA para a semântica; ALTA para o Linux nunca emitir.

### 3.10 O que existe no aparelho e não tem consumidor nenhum no Linux

Canais de MCU/NFC/IR: entradas `0x31`, `0x32`, `0x33` (361 bytes), saídas `0x11`
e `0x12`, e os subcomandos `0x20`, `0x21`, `0x22` (reset e configuração do MCU).
GRAU: ALTA (as constantes em `:120-141`; o descritor MEDIDO AQUI).

Fica registrado **para ninguém "descobrir" isso como oportunidade**: é o caminho
de NFC e amiibo, sem uso nenhum neste produto.

---

## 4. O 8BitDo em modo PS4 — `054c:05c4`, driver `playstation`

### 4.1 O clone COPIA o descritor inteiro — e falha em tudo o que ele promete

O descritor dele tem **364 bytes** e **31** report IDs, e declara **tudo** o que
um DualShock 4 v1 por Bluetooth declara: entradas `0x01` e `0x11` (77 bytes de
corpo, os 78 exatos que o kernel espera), saídas `0x11` a `0x19`, features `0x02`
a `0x09`, `0xa3` (48 bytes), `0x82`-`0x84`, `0x90`-`0x93`, `0xa0`, `0xa4`,
`0xf0`-`0xf2`. GRAU: MEDIDO AQUI (parser próprio; tamanho por `wc -c`).

**E o firmware falha nos três feature reports que importam.** MEDIDO AQUI, na
subida das 19:05:44-45 (`journalctl -k \| grep 05C4`):

```
Failed to retrieve feature with reportID 163: -5   (x3, com retry em 100 ms e 200 ms)
Failed to retrieve DualShock4 firmware info: -5
Failed to retrieve feature with reportID 5: -5     (x3)
Failed to retrieve DualShock4 calibration info: -5
Invalid gyro calibration data for axis (3),(4),(5), disabling calibration.
Invalid accelerometer calibration data for axis (0),(1),(2), disabling calibration.
Registered DualShock4 controller hw_version=0x00000000 fw_version=0x00000000
```

Tempo da borda ao registro: cerca de **1,5 s**. As três tentativas são uma mais
as duas de `feature_retries=2` (MEDIDO AQUI). E isto é **reprodutível a cada
reconexão**: as **dez** subidas dele neste boot têm o mesmo bloco, palavra por
palavra. GRAU: MEDIDO AQUI.

ATENÇÃO: **o `-5` não é o erro real.** O comentário do remendo da casa mede que
é o timeout de 3 s do HIDP do BlueZ, achatado em `-EIO` pelo `uhid`. GRAU: ALTA
(comentário de `ps_get_report` em `assets/dkms/hid-playstation/hid-playstation.c`).

**Ele registra assim mesmo** por causa do remendo
`assets/dkms/hid-playstation/patch/0002-HID-playstation-survive-a-DualShock4-pairing-info-rep.patch`.
Sem ele, o aparelho ficava sem driver nenhum. GRAU: ALTA.

**A resposta à pergunta "o que vale para o DS4 vale para ele?" é esta linha:**
**declarar não é implementar.** É a lei da seção 0.2, medida.

### 4.2 O envelope DualShock 4 por Bluetooth

Mesmo formato do DualSense, com outros números — GRAU: ALTA
(`hid-playstation.c:110-112`, `:361-368`, `:493-565` com `static_assert`,
`:2431-2540`):

| | por USB | por Bluetooth |
|---|---|---|
| entrada | `0x01`, 64 B, **sem CRC** | `0x11`, **78 B**, CRC-32 nos 4 últimos, semente **`0xA1`** |
| saída | `0x05`, 32 B | `0x11`, **78 B**, CRC-32 semente **`0xA2`**, mais **dois** bytes de cabeçalho que o USB não tem (`hw_control` e `audio_control`) |
| feature | — | CRC-32 semente **`0xA3`** |

As sementes `0xA1`/`0xA2`/`0xA3` são **compartilhadas** entre DualShock 4 e
DualSense; a referência do DualSense só documenta a de saída. GRAU: ALTA.

**Feature reports que o driver lê no probe:** por Bluetooth, exatamente **dois**
— `0xA3` (firmware info, 49 B, explicitamente **sem** verificação de CRC porque
o report não a suporta) e `0x05` (calibração, 41 B, **com** CRC semente `0xA3`).
Por USB, outros dois — `0x12` (pairing info) e `0x02` (calibração, 37 B). GRAU:
ALTA (`:2186-2212`, `:2003-2070`). **É o mapa exato do que o clone precisaria
responder para ter sensor calibrado — dois reports, e ele falha nos dois.**

**Endereço: por Bluetooth o driver NÃO o lê por feature report** — pega de
`hdev->uniq`, que o HIDP já preencheu, e faz `sscanf`. Só por USB ele lê o
pairing info. GRAU: ALTA (`:2300-2340`). **É por isso que o clone sobrevive à
probe por rádio e morre no cabo**, e é para o cabo que existem os parâmetros
`ds4_short_pairing_info` e `ds4_synthetic_mac`, ambos em `Y` aqui.

ATENÇÃO: **a identidade por OUI do `daemon/subsystems/external_identity.py`
depende de o `uniq` ser o endereço real** — o que por Bluetooth é garantido pelo
HIDP, e **por USB pode ser o endereço sintético** que o `degrade` fabrica.

### 4.3 A taxa — e o único botão de taxa que existe nesta mesa

**O `hid-playstation` NÃO tem limitador de taxa nenhum.** Toda escrita é um
`schedule_work` que monta o report e chama `hid_hw_output_report` na hora: sem
esperar relatório de entrada, sem intervalo mínimo, sem contagem de tentativas.
GRAU: ALTA (`:2461-2540`, `:2826-2832`).

**É a diferença estrutural entre os dois drivers, e ela decide o alvo:** o storm
de subcomando do `hid-nintendo` **não pode alcançar** o 8BitDo em modo PS4. E é
a razão pela qual `write_lightbar_slot` é barata e `write_player_number` é cara,
mesmo as duas parecendo "escrever um arquivo".

**O botão de taxa:** os **6 bits baixos** do `hw_control` do report de saída
`0x11` são o **intervalo de poll em milissegundos** (`0x00`/`0x01` = 1 ms, `0x02`
= 2 ms, ... `0x3E` = 62 ms, `0x3F` = desabilitado). O Linux pede **4 ms**, uma
única vez, no probe. Os dois bits altos do mesmo byte são `0x80` = HID e `0x40` =
exigir CRC-32, e é por eles que o valor escrito é `0xC0` mais o intervalo. Esse
campo **não existe** no report de saída por USB. GRAU: ALTA (`:401-413`,
`:2517-2532`, `:2834-2840`, chamada em `:2983`).

ATENÇÃO: **é o parâmetro de rádio mais direto que existe em qualquer controle
desta mesa** — o Pro não tem equivalente, e o DualSense também não. Ninguém aqui
mexeu nele. Candidato natural a uma medição de permanência, e como só fecha
escrevendo, está na seção 8 como protocolo.

### 4.4 O relatório curto — e a hipótese que ele NÃO explica

O DualShock 4 por Bluetooth **nasce** mandando um report curto `0x01` de 10
bytes (só sticks e botões) e só passa ao `0x11` completo depois de receber um
report de saída do host. O driver **aceita** o curto: reusa o parser e retorna
antes de sensores, touchpad e bateria, pela variável `is_minimal`. O comentário
do kernel nomeia esta classe de aparelho: *"Some third-party pads never switch
to the full 0x11 report."* GRAU: ALTA (`:361-362`, `:2585-2596`, `:2629`) —
**vanilla**, `grep -c minimal` nos dois remendos da casa devolve 0.

**MORRE aqui a explicação mais natural para o mudo** — *"ele só manda o `0x01`
curto e o driver o ignora"*. Dois caminhos independentes a matam:

1. o driver **trata** o `0x01` curto por Bluetooth, e o trata em silêncio;
2. o `hidraw` entrega **todo** relatório de entrada, parseado ou não — e
   entregou **zero**.

**O aparelho não manda o relatório errado. Ele não manda relatório nenhum.**
GRAU: MEDIDO AQUI.

**E não há report desconhecido chegando:** o boot inteiro não tem uma linha
`Unhandled reportID` nem `DualShock4 input CRC's check failed` para o `05C4` —
as ocorrências de CRC do boot são todas do DualSense. Como o driver loga em
`hid_err` qualquer report que não case, o silêncio no log é coerente com "não
chega relatório nenhum", e **não** é prova de que o CRC dele esteja certo. GRAU:
MEDIDO AQUI para a ausência de linhas; ALTA para o mecanismo do log.

### 4.5 O silêncio, e o que ele virou às 19h33

**MEDIDO AQUI, 19h17 a 19h30** — leitura pura, sem `EVIOCGRAB`, com controle
positivo no mesmo minuto:

| nó | janela | eventos |
|---|---|---|
| `/dev/hidraw2` (8BitDo) | 3 s, 6 s e 20 s | **zero** relatórios |
| `event8`, `event9`, `event10` (8BitDo: gamepad, sensores, touchpad) | 3 s, 4 s e 10 s | **zero** eventos |
| `hidraw` do Pro | 5 s e 6 s | 446 e 536 relatórios |
| nó de IMU do Pro | 10 s | 267 SYN/s |
| nós de sensores dos dois DualSense | 10 s | 155 a 265 SYN/s |

RESSALVA HONESTA, e ela é do instrumento: **o `evdev` suprime `SYN_REPORT`
quando nada muda**, então o zero de `evdev` sozinho **não** prova silêncio. Quem
prova é o `hidraw`, que entrega tudo. O `evdev` entra como **confirmação**, não
como prova.

**E às 19h33 o HID sumiu com o link de pé** — ver a seção 1.2, que é onde essa
história termina, e onde está o defeito de watchdog que ela abre.

**A cadência da queda, MEDIDA nas dez subidas deste boot:** intervalos de 41,9 /
74,8 / 17,9 / 26,6 / 24,0 / **905,4** (a noite inteira, ela dormindo) / 47,6 /
198,0 / 25,4 minutos. Tirando a noite, a mediana é cerca de **26 minutos**. E
todas as voltas, até 19h05, foram por link **entrante** — o aparelho é que
pageia. GRAU: MEDIDO AQUI.

**A hipótese que junta as duas medições:** o ciclo de cerca de 26 min é
compatível com *"o link sobe, o aparelho nunca transmite, e algo derruba um link
sem tráfego"*. GRAU: **BAIXA** — é hipótese **com mecanismo**, derivada de duas
medições próprias, sem nenhuma fonte de terceiro. **É falsificável:** se o
timeout de supervisão dele for da ordem de dezenas de segundos, ela morre; se ele
estiver mudo **e** o link durar 26 min, ela ganha. E o timeout de supervisão é
exatamente o que não se lê sem privilégio (8.1).

### 4.6 A bateria que MENTE

O nó `ps-controller-battery-e4:17:d8:00:00:83` lia, enquanto existia,
`capacity=100` e `status=Unknown`. **Esses são exatamente os valores de
inicialização** que o driver grava antes de qualquer relatório —
`ps_dev->battery_capacity = 100; /* initial value until parse_report. */` e
`POWER_SUPPLY_STATUS_UNKNOWN` — e o parse só os sobrescreve no caminho do
relatório **completo**. GRAU: ALTA (`hid-playstation.c:2905-2906`, `:2690-2738`)
+ MEDIDO AQUI.

**É prova independente, por um segundo caminho, de que nenhum relatório completo
foi processado desde a subida.** Se tivesse havido um só, os dois campos teriam
mudado juntos.

ATENÇÃO — **é o defeito de instrumento da E-3 com o sinal trocado:**

| aparelho | o arquivo `capacity` | o que um amostrador ingênuo conclui |
|---|---|---|
| Pro Controller | **não existe** | "AUSENTE" a noite inteira — mede o instrumento, não o controle |
| 8BitDo em PS4 | **existe e mente** | "bateria cheia" de um controle que nunca falou |

Para o 8BitDo, `100/Unknown` significa **"nunca falou"**, não "cheia". É um
instrumento de graça para qualquer medição futura dele.

### 4.7 Os LEDs

Neste modo ele **não tem barra de jogador**: tem a lightbar RGB do DualShock 4,
nos nós `input<N>:red`, `:green`, `:blue` e `:global`, que é o caminho `ds4` do
`resolve_external_leds`, ancorado em `DRIVERS=="playstation"` pela
`assets/79-external-controller-leds.rules`. GRAU: MEDIDO AQUI (os nós existem, e
tinham valores gravados: `red=64`, `global=1`).

ATENÇÃO: **valor gravado no `sysfs` NÃO é prova de que alguma luz acendeu.**
Aquilo é a cache do subsistema de LED do kernel. E o SN30 Pro **não tem lightbar
RGB física**: os quatro LEDs azuis dele são indicadores de **modo** (LED1
D-input, LED2 X-input, LED3 macOS, rotativo = Switch ou pareamento). GRAU:
**MÉDIA** — a semântica dos LEDs vem do manual do fabricante, e **a parte física
nunca foi olhada nesta casa**. Fecha com cinco segundos de olho dela.

**O produto não escreve nesses nós desde 07/08 02:59**
(`EXTERNAL_PLAYER_LED_ENABLED = False`).

### 4.8 Sensores e touchpad — a correção a uma linha que a casa escreveu hoje

A seção 3.2 do estudo de hoje concluiu, dos nós `Wireless Controller Motion
Sensors` e `... Touchpad`, que *"ele tem giroscópio neste modo"*.

**A existência dos nós NÃO prova nada sobre o hardware.** O driver os cria
**incondicionalmente** para qualquer `054c:05c4`: `ps_sensors_create` e
`ps_touchpad_create` são chamados na probe sem consultar o aparelho, logo depois
do gamepad e antes de qualquer coisa que dependa do que o controle respondeu.
GRAU: ALTA (`hid-playstation.c:2958` e `:2965`, sem condicional) + MEDIDO AQUI
(os nós existiam **e** estavam mudos).

**MEDIDO era a existência, e a existência não era a pergunta.** A nota 3 da
[página do 8BitDo](../usage/troubleshooting-8bitdo.md) — *"pergunta em aberto"* —
**continua aberta**, e esta linha é a correção datada de uma conclusão de hoje.

---

## 5. O 8BitDo em modo Switch — `057e:2009`, driver `nintendo`

**Não está na mesa, e não tem bond neste adaptador.** São **quatro** bonds, e
nenhum é ele. GRAU: MEDIDO AQUI. **Qualquer medição daquele modo começa por um
pareamento novo** — é o item mais caro desta página.

**Nada do que esta página afirma sobre "o 8BitDo" foi medido naquele modo.**

O que se sabe sem ele ligado:

| afirmação | GRAU |
|---|---|
| contra o Pro genuíno ele colide em **tudo** o que se consulta: VID/PID (`057e:2009`), nome (`Pro Controller`), serial (`000000000001`), `HID_NAME` e `MODALIAS` | ALTA |
| por rádio o **único** discriminador é a OUI — `e0:f6:b5` genuíno, `e4:17:d8` clone | ALTA (três lugares independentes da árvore concordam) |
| por cabo há um segundo, o `bcdDevice` `0210`/`0200` — que **não existe** por Bluetooth | ALTA |
| os dois têm requisitos de firmware **incompatíveis** quanto ao sniff — ver 6.3 | ALTA (A/B de 23/07, transcrito em `scripts/bt_active_mode.sh`) |

**A OUI separa clone de genuíno, mas NÃO diz em que modo o clone está** — é o
mesmo rádio nos dois modos. Quem separa os modos é o par **nome + VID/PID**
(`Wireless Controller`/`054c:05c4` contra `Pro Controller`/`057e:2009`) **e** o
driver que pega. **Nenhuma chave sozinha basta: precisa das duas.** GRAU: ALTA.

ATENÇÃO — **o buraco sério, e ele expõe a doutrina da casa:** que o 8BitDo
mantenha o **mesmo endereço de rádio** nos dois modos **nunca foi medido aqui**.
GRAU: **BAIXA** (derivação de um modo só). **As regras `udev` casam por
`HID_UNIQ`, isto é, por endereço.** Se o endereço mudar com o modo, elas mudam de
alvo sem avisar — e a `assets/82-nintendo-pro-nosniff.rules`, que existe
precisamente para **não** pegar o clone, pode estar acertando por sorte. Fecha
com um pareamento novo no modo Switch e uma leitura de endereço; está em 8.2.

---

## 6. O rádio — o que vale para os quatro

### 6.1 O que NÃO distingue nada

| campo | valor | consequência | GRAU |
|---|---|---|---|
| **Class of Device** | **`0x2508`** nos **quatro** (classe maior 5 Peripheral, menor `0x02` Gamepad, bit 13 Limited Discoverable) | **quem tentar discriminar controle por CoD acerta zero** | MEDIDO AQUI; MÉDIA para a decodificação (Assigned Numbers do SIG) |
| versão de HID | `v80.01` no Pro; **`v1.00` no 8BitDo em PS4 e nos dois DualSense** | separa a linhagem Nintendo da Sony; **não** separa clone de genuíno dentro da Sony | MEDIDO AQUI |
| nome anunciado | `Pro Controller`; **`Wireless Controller`** no 8BitDo em PS4 — idêntico ao de um DualShock 4 verdadeiro | inútil como discriminador dentro da linhagem | MEDIDO AQUI |

### 6.2 O que distingue

| campo | Pro genuíno | 8BitDo em PS4 | DualSense | GRAU |
|---|---|---|---|---|
| UUIDs de SDP | `0x1000`, `0x1124`, `0x1200` | `0x1124`, `0x1200` | `0x1124`, `0x1200` | MEDIDO AQUI |
| Modalias (DID) | `usb:v057Ep2009d0001` | `usb:v054Cp05C4d0100` | `usb:v054Cp0CE6d0100` | MEDIDO AQUI |
| `ServicesResolved` **agora** | **false** | **false** | **true** nos dois | MEDIDO AQUI |

O `0x1000` a mais no Pro é o **único** discriminador de SDP medido entre as
linhagens nesta mesa. Nenhum caminho da árvore lê UUIDs de SDP — a identidade sai
de `HID_UNIQ`, VID e PID, e está certo.

ATENÇÃO: **`ServicesResolved=false` NÃO implica controle mudo.** O Pro entrega
89 relatórios por segundo com ela em `false`. **A vigia de zumbi não pode usar
essa propriedade sozinha como sintoma** — e não usa: ela a combina com "zero
`hidraw`", que é o que salva a heurística de dar falso positivo no Pro. GRAU:
MEDIDO AQUI.

### 6.3 O transporte, e o sniff

**Os quatro são HID CLÁSSICO sobre L2CAP (BR/EDR), não HID over GATT.** Prova
tripla: UUID `0x1124` e ausência de `0x1812`; `AddressType=public`; e o objeto
D-Bus expõe `org.bluez.Bearer.BREDR1` e nenhuma interface LE. **Nenhum ajuste de
conexão LE (intervalo, latência de GATT) se aplica a estes aparelhos.** GRAU:
MEDIDO AQUI.

**A política de link, por conexão, MEDIDA AQUI às 19h41:**

| aparelho | link policy |
|---|---|
| **Pro genuíno** (`e0:f6:b5:00:00:53`) | **RSWITCH** — sem SNIFF, sem HOLD, sem PARK |
| 8BitDo em PS4 (`e4:17:d8:00:00:83`) | RSWITCH HOLD SNIFF PARK |
| DualSense (`a0:fa:9c:00:00:f0`) | RSWITCH HOLD SNIFF PARK |
| DualSense (`14:3a:9a:00:00:ab`) | RSWITCH HOLD SNIFF PARK |
| **default do adaptador** | RSWITCH HOLD SNIFF PARK |

**O no-sniff está VIVO e é POR-LINK**, exatamente como a cura de 23/07 desenhou.
É a primeira confirmação medida de que a cura ainda vale nesta sessão — e o
`scripts/bt_active_mode.sh` reaplica a cada 2 minutos (visto no journal às
19:31:20, 19:33:20, 19:35:20, 19:37:20 e 19:39:21). GRAU: MEDIDO AQUI.

ATENÇÃO — **a única regra da casa em que dois controles têm requisitos de
firmware OPOSTOS.** O 8BitDo **precisa** do sniff: com no-sniff **global** ele
acumulou 4 probes falhadas e 0 sucessos, sempre em `Failed to get joycon info;
ret=-110`; com o sniff devolvido, probou em 54 s na primeira tentativa. **O
default do adaptador tem de continuar COM sniff por causa dele**, e o escopo
por-OUI existe precisamente para não matar este aparelho. GRAU: ALTA (A/B de
23/07) + MEDIDO AQUI (o disco respeita).

### 6.4 O pareamento, e quem inicia a reconexão

Os quatro objetos D-Bus, MEDIDOS AQUI às 19h41: `Paired=true`, `Bonded=true`,
`Trusted=true`, `Blocked=false`, `WakeAllowed=true`, `ReconnectMode=device`,
`LegacyPairing=false`, `CablePairing=false`. São **quatro** bonds no adaptador —
eram **três** às 15h46 de hoje; o quarto é o segundo DualSense, pareado às
18:41.

`/var/lib/bluetooth` **não foi lido** (`ls` devolve `Permissão negada`, e a
máquina está em uso). **Não se inventa o conteúdo.** O D-Bus publica o
equivalente, sem senha e sem risco.

**`ReconnectMode=device` não é escolha do host:** o BlueZ o deriva dos atributos
SDP `HIDReconnectInitiate` e `HIDNormallyConnectable` que **o próprio controle
publica**. GRAU: MEDIDO AQUI para o valor; **MÉDIA** (documentação do BlueZ) para
a semântica.

ATENÇÃO — **e aqui esta página CORRIGE o estudo de hoje.** A seção 5.2 dele
conclui, de `ReconnectMode=device`, que *"o host não puxa"*. **O valor está
certo; a conclusão é forte demais.** Duas medições a corrigem:

1. **Direção dos links.** MEDIDO AQUI: `hcitool con` mostra os quatro com `<`
   (saída, iniciado pelo host). Às 19h12 o 8BitDo estava `>` (entrada); às 19h41
   está `<`. **O host pageia, sim.** A leitura do caractere vem do fonte do
   `hcitool`: GRAU MÉDIA para a semântica, MEDIDO AQUI para o valor.
2. **O `bluetoothd` tenta ativamente conectar ao perfil de entrada.** MEDIDO
   AQUI: `profiles/input/device.c:control_connect_cb() connect to <endereço>:
   Host is down (112)` — 12 ocorrências neste boot, para o Pro, o 8BitDo e um
   DualSense. Duas delas, às 22:20:58 e 22:21:04 de 06/08, **precedem em segundos
   a subida do Pro às 22:21:11**.

**A leitura correta:** `ReconnectMode=device` quer dizer *"o BlueZ não reconecta
sozinho por política"*, **não** *"o host nunca pageia"*. Alguém chama `Connect()`
e o page acontece. **Quem chama nestes 12 casos NÃO foi identificado — fica em
aberto.** GRAU: MEDIDO AQUI para as linhas; SEM PROVA para o autor.

O que **continua valendo** do estudo, e não muda: **não existe ajuste no host que
mantenha o link de pé com o controle DESLIGADO.**

### 6.5 Os dois modos de falha de reconexão que a casa já cura

1. **Bond sem trust: reconexão ENTRANTE recusada.** Duas linhas em par:
   `profiles/input/server.c:connect_event_cb() Refusing input device connect: No
   such file or directory (2)` e `confirm_event_cb() Refusing connection from
   <endereço>: unknown device`. MEDIDO AQUI hoje às 19:06:56 e 19:07:08 com o
   DualSense `a0:fa:9c:00:00:f0`. **É o mecanismo de queda mais barato de curar e
   o mais fácil de confundir com "o controle não liga".**
2. **Bond NOVO nasce sem trust, e fica assim até a vigia passar.** MEDIDO AQUI
   ponta a ponta no DualSense `14:3a:9a:00:00:ab`, pareado às 18:41:40: às
   18:43:16 o watchdog logou que ele *"tinha bond mas estava SEM trust"* e
   aplicou `Trusted=true`. **Janela de exposição medida: 96 segundos.** Nesse
   intervalo o controle não consegue voltar sozinho. **Não é defeito — é o preço
   estrutural de um vigia com período de 2 minutos.**

A cura dos dois é a vigia 2b do `scripts/bt_health_watchdog.sh`, que aplica
`Trusted=true` em todo aparelho bondado sem trust **sem exigir `Connected`**.
GRAU: MEDIDO AQUI.

### 6.6 O estado do adaptador — e por que ele muda o denominador

MEDIDO AQUI às 19h41 (`hciconfig -a`): OUI `d8:44:89`, alias
`Nintendo MeowSystem` (o prefixo do `scripts/bt_active_mode.sh` aplicado), Class
`0x6c0104`, HCI 5.1 Realtek, link policy default `RSWITCH HOLD SNIFF PARK`,
flags **`UP RUNNING PSCAN ISCAN`**.

ATENÇÃO: **o `ISCAN` é NOVO** em relação à leitura das 15h46 de hoje (que tinha
só `PSCAN`). `Discoverable=true` e `Discovering=true`, porque a tela de
Bluetooth do COSMIC está aberta desde 19:07:00. **Inquiry ativo consome ar do
mesmo rádio que os quatro links.** Não é o Hefesto — mas é estado de rádio que
**qualquer** medição desta frente tem de declarar, porque muda o denominador. E
é candidato a explicar parte da subida de perda de IMU das 19h (seção 3.5).
GRAU: MEDIDO AQUI para o estado; **BAIXA** para a contribuição à perda.

---

## 7. O que o Hefesto depende hoje — a dívida, visível

Esta seção existe porque a regra da casa manda: **se o produto se apoia numa
linha de grau baixo, isso é dívida e tem de estar à vista.**

### 7.1 A superfície inteira de escrita em externo — duas linhas de código

| caminho | escreve o quê | onde | estado |
|---|---|---|---|
| `apply_player_number` (`core/external_leds.py:314`) | número do jogador, lâmpada por lâmpada | `sysfs` | **DESLIGADO** desde 07/08 02:59 |
| `enable_imu` (`core/external_leds.py:155`) | pacote cru de 12 bytes | `hidraw` | vivo, **só por USB** |

### 7.2 O que o produto apoia, e em que grau

| # | o produto faz | apoiado em | GRAU do apoio | dívida |
|---|---|---|---|---|
| 1 | bifurca `nintendo` x `ds4` por driver em `resolve_external_leds` | a bifurcação de driver | **ALTA** | nenhuma |
| 2 | identifica o Pro genuíno por OUI em três lugares | a OUI ser o único discriminador por rádio | **ALTA** | nenhuma **para o modo PS4**; ver 7.3 |
| 3 | `ExternalImuEnabler` monta um `0x40`/`0x01` de **12 bytes** e o manda por `hidraw` | que o firmware honre um report `0x01` **curto**, contra os 48 bytes de corpo que o descritor declara | **SEM PROVA** | **dívida real** — e o item E-2 do estudo de hoje é quem a paga |
| 4 | o mesmo componente existe para ligar a IMU | o driver **já a liga**, em todo barramento, no probe | **ALTA de que é duplicado** | **provável código morto**; o porteiro `bus == "usb"` só impede que a duplicação vá ao rádio |
| 5 | `write_player_number` trata o `:blue:player-5` como o bit "+5" da numeração e escreve `1` nele | o nó é o **LED HOME**, escala 0-15, outro subcomando | **ALTA de que está errado** | **defeito conhecido**, hoje calado pelo portão. **Não voltar sem corrigir** |
| 6 | `write_player_number` faz cinco escritas de `sysfs` em sequência | cada escrita vira subcomando; a de verde reescreve os quatro | **ALTA** | **cinco subcomandos por chamada** — é a origem medida das 12 recusas e 3 `-110` por chamada, e é o que a escrita idempotente da E3 tem de curar |
| 7 | `discover_external_gamepads` conta o externo como presente e ele participa da numeração | presença de nó, não de tráfego | **ALTA de que é insuficiente** | o 8BitDo **mudo** contava como presente e disparava renumeração dos outros |
| 8 | o produto **não lê** bateria de externo | — | — | **é bom que não leia**: leria `AUSENTE` no Pro e `100%` mentiroso no 8BitDo |
| 9 | a vigia de zumbi do watchdog | `Connected=true` **e** zero `hidraw` **e** cache de SDP sem `[ServiceRecords]` | **ALTA de que tem buraco** | **duas** formas escapam: "link de pé + `hidraw` presente + mudo" e "link de pé + sem `hidraw` + cache completo" — esta segunda está viva **neste minuto** (seção 1.2) |

### 7.3 A dívida de doutrina, e é a mais escondida

As regras `udev` da casa casam por **`HID_UNIQ`**, isto é, **por endereço de
rádio**. A doutrina de identificar o clone por OUI está **certa e medida** — para
o modo PS4. Mas **que o clone mantenha o mesmo endereço ao trocar de modo é grau
BAIXA**, nunca medido aqui. Se ele trocar, as regras mudam de alvo sem avisar.

**Esta é a única linha desta página em que o produto se apoia, sem saber, num
grau BAIXO.** Fecha com o item 8.2.

---

## 8. O que falta medir — o protocolo

Convenção da casa: **P0** tranca (com o destrancar embutido); **ANTES** é a foto
numérica; **CONTRASTE** é o caso sem o qual nada se conclui; **PREVISÃO** é
falsificável e derivada do código; **LEITURA** é a tabela escrita **antes** de
medir.

Nenhum item aqui repete os cinco do
[estudo dos externos de 07/08](../process/estudos/2026-08-07-ISOLAR-os-externos-o-metodo-da-lightbar-no-pro-e-no-8bitdo.md)
(E-1 a E-5). Estes são os que **esta página** abriu.

### 8.1 P-1. O timeout de supervisão — o número que falta para tudo

**O que falta.** Intervalo de sniff negociado, latência e **timeout de
supervisão** de cada link. **É o coração da pergunta dela sobre conexão
permanente**, e é o que decide a hipótese de 4.5.

**Por que não fechou.** Os três caminhos falharam por permissão, e cada um do
seu jeito — MEDIDO AQUI: `btmon` roda e **imprime NADA** (sai 0, sem uma linha,
por falta de `CAP_NET_RAW`); `btmgmt info` devolve saída vazia;
`/sys/kernel/debug/bluetooth/hci0/` dá `Permissão negada`.

ATENÇÃO: **quem ler "o `btmon` saiu 0" como "não há tráfego" tira conclusão
falsa.** Está na lista de notas de instrumento pelo mesmo motivo.

**P0.** Roda como root, e **não** derruba nada — é captura passiva. Nada a
destrancar além de encerrar a captura.
**ELA.** Nada, além de autorizar o privilégio.
**PREVISÃO.** Se o timeout de supervisão do 8BitDo for da ordem de **dezenas de
segundos**, a hipótese do ciclo de 26 minutos morre. Se for de **minutos**, ela
ganha.
**CONSEQUÊNCIA.** **A casa nunca soube o timeout de supervisão de nenhum destes
controles.** Nenhum instrumento da árvore o lê.

### 8.2 P-2. O 8BitDo troca de endereço ao trocar de modo?

**Pergunta.** O clone mantém o mesmo endereço de rádio no modo Switch e no modo
PS4?

**Por que existe.** É a dívida 7.3 — a doutrina de escopo por OUI e as regras
`udev` por `HID_UNIQ` dependem disso, e **nunca foi medido**.

**P0.** Snapshot de bonds **antes** (há script e timer, e o timer está `active`,
tendo rodado às 19:37:20 com `estado idêntico ao último snapshot — no-op`).
**Destrancar:** o modo Switch **não tem bond** neste adaptador, então o teste
começa por um pareamento novo, e o desfecho esperado é ficar com **dois** bonds
do mesmo aparelho — ou com **um**, e é justamente essa a resposta.
**ELA.** Põe o 8BitDo em modo Switch (`Y+Start`), pareia, e avisa. Depois volta
para PS4 (`Start+A`).
**PREVISÃO.** Se surgir um **quinto** bond com OUI `e4:17:d8` e sufixo
**diferente**, o aparelho tem dois endereços, e a
`assets/82-nintendo-pro-nosniff.rules` está acertando por sorte. Se o bond
existente for **reusado**, a doutrina está certa e sobe de BAIXA para MEDIDO.
**CONTRASTE.** O Pro genuíno na mesma janela — se ele também perder ou ganhar
bond, foi no host.

### 8.3 P-3. O botão de taxa do DualShock 4 muda a permanência do 8BitDo?

**Pergunta.** O intervalo de poll de 4 ms que o Linux pede no probe tem relação
com o silêncio e com o ciclo de 26 minutos?

**Por que existe.** É o **único** parâmetro de rádio programável pelo host em
qualquer controle desta mesa (4.3), e **ninguém aqui mexeu nele**.

**P0.** **Só fecha ESCREVENDO no aparelho** (report de saída `0x11` com o
`hw_control` alterado), logo é protocolo e não experimento de assistente.
Trancar: o Hefesto **não escreve** nesse aparelho, então não há concorrência de
escritor — mas o driver escreve o valor **uma vez, no probe**, e qualquer
reconexão o restaura. **Destrancar:** desconectar e reconectar devolve os 4 ms.
**ANTES.** Contagem de relatórios no `hidraw` do 8BitDo por 60 s e a instância
HID atual.
**PREVISÃO.** Se ele está **mudo**, mexer no intervalo **não muda nada** — e
esse resultado negativo já vale, porque separa "ele não quer falar" de "ele não
consegue no ritmo pedido". **Se um intervalo maior o fizer falar**, o achado é
grande e muda o alvo inteiro.

### 8.4 P-4. A luz do 8BitDo acende? (cinco segundos de olho dela)

**Pergunta.** Os nós `:red`/`:green`/`:blue`/`:global` do 8BitDo acendem alguma
coisa física, ou são cache do kernel sobre hardware que não existe?

**Por que existe.** É a única linha desta página marcada MÉDIA por **nunca ter
sido olhada** (4.7), e o custo é o menor de toda a fila.

**ELA.** Olha o controle e diz se há luz colorida ou só os quatro LEDs azuis de
modo. **Cinco segundos.**
**PREVISÃO.** O SN30 Pro **não tem lightbar RGB**. Se confirmado, todo o caminho
`ds4` de LED externo é **escrita em nó que não acende**, e isso muda o valor da
E3.

### 8.5 P-5. Recontar a perda de IMU do Pro com a mesa vazia

**Pergunta.** A perda de IMU do Pro é função do **número de links no rádio**?

**Por que existe.** O histograma de 3.5 mostra a correlação com força (dezenas
por 10 min com dois controles; **439** com quatro), mas correlação com dois
controles a menos **e** a tela de Bluetooth aberta **e** o inquiry ativo é
confundida por três variáveis ao mesmo tempo.

**P0.** **Fechar a tela de Bluetooth do COSMIC** — ela liga o `ISCAN` e consome
ar (6.6). Anotar `hciconfig` antes e depois.
**ANTES.** Contagem de episódios por 10 minutos, com quatro links e `ISCAN`
ligado (já colhida: 103, 439, 208, 117, 155, 175).
**CONTRASTE.** A janela das 16h50 às 18h30 de hoje, com **dois** controles: 18,
25, 1, 2. **Já está medida e não se remede.**
**PREVISÃO.** Fechando só a tela, a perda cai **parcialmente**; tirando dois
controles, cai **para a ordem de dezenas**. Se não cair com nenhum dos dois, a
causa é outra e a hipótese de contenção morre.
**ELA.** Nada, além de fechar a tela quando não estiver usando.

---

## 9. Notas de instrumento — as armadilhas desta frente

As nove do
[estudo de 07/08](../process/estudos/2026-08-07-ISOLAR-os-externos-o-metodo-da-lightbar-no-pro-e-no-8bitdo.md),
seção 9, **valem inteiras aqui e não se repetem**. Estas são as que esta
varredura acrescentou:

1. **`stat` MENTE sobre o tamanho do descritor.** Ele devolve **4096**, que é a
   página do `sysfs`. O tamanho verdadeiro só sai com
   `wc -c < /sys/class/hidraw/hidrawN/device/report_descriptor`. **Uma das três
   frentes desta varredura caiu nisso**, e a divergência 3 da seção 2 é o
   registro.
2. **Janela curta arruína medição de taxa.** 3 s de `hidraw` deram 86,3/s; 5 s
   deram 89,1; 6 s deram 89,2. **Medir taxa em menos de 5 s produz um número que
   parece preciso e não é.**
3. **`btmon` sem privilégio sai 0 e imprime NADA.** Não é "não há tráfego" — é
   falta de `CAP_NET_RAW`. Instrumento silencioso é pior que instrumento que
   falha alto.
4. **Contador de perda de IMU: `N` são RELATÓRIOS, não amostras.** E o número
   **cresce enquanto se mede** — toda contagem tem de vir com o carimbo de hora.
   Pior: a mensagem sai por `hid_warn_ratelimited`, então a soma de `N` é um
   **piso**, nunca o total.
5. **O limiar do aviso é `> 3`, não `>= 3`.** Perdas de 1 a 3 relatórios **não
   aparecem no journal**. A perda real é maior que a medida, e por construção.
6. **`hidraw` renumera entre sessões.** O `hidraw2` era o DualSense às 15h46, o
   8BitDo às 19h30, e não existe às 19h41. **Nenhum passo pode gravar
   `/dev/hidrawN` como identidade** — resolver sempre por
   `HID_ID` em `/sys/class/hidraw/*/device/uevent`.
7. **`Connected=true` no BlueZ não implica HID vivo.** Medido nesta varredura:
   ACL autenticado e cifrado, `Connected=true`, e **zero** aparelhos HID. Um
   instrumento que confie no D-Bus para dizer "o controle está lá" mente.
8. **A tela de Bluetooth aberta muda o rádio.** `Discovering=true` liga o
   `ISCAN` e o inquiry consome ar. Toda medição desta frente tem de declarar se
   ela estava aberta.

---

## 10. Fontes

**Código do kernel — nesta árvore, e é o que a máquina dela carrega**

- `assets/dkms/hid-nintendo/hid-nintendo.c` (3303 linhas) e os remendos da casa
  em `assets/dkms/hid-nintendo/patch/`
- `assets/dkms/hid-playstation/hid-playstation.c` (3132 linhas) e
  `assets/dkms/hid-playstation/patch/0001-HID-playstation-retry-feature-reports-that-time-out-o.patch`,
  `assets/dkms/hid-playstation/patch/0002-HID-playstation-survive-a-DualShock4-pairing-info-rep.patch`

**Upstream**

- `hid-nintendo` no kernel —
  `https://github.com/torvalds/linux/blob/master/drivers/hid/hid-nintendo.c`
- `hid-playstation` no kernel (autor da SIE) —
  `https://github.com/torvalds/linux/blob/master/drivers/hid/hid-playstation.c`
- O remendo do relatório curto do DualShock 4 (Max Staudt, 15/01/2024) —
  `https://lkml.rescloud.iu.edu/2401.3/01396.html`

**Engenharia reversa de comunidade — SUSPEITA até conferida**

- dekuNukem, `Nintendo_Switch_Reverse_Engineering` —
  `https://github.com/dekuNukem/Nintendo_Switch_Reverse_Engineering`
  (`bluetooth_hid_notes.md`, `bluetooth_hid_subcommands_notes.md`,
  `rumble_data_table.md`). **Conferido nesta varredura:** o mapa do byte de
  bateria **concorda** com o driver; a taxa publicada (60/120 Hz) foi
  **refutada** na mesa dela
- `joycon-turnoff` (o modo de sleep do firmware) —
  `https://github.com/Sopsy/joycon-turnoff`. **Não conferido**; coerente com o
  medido
- Relato de queda do Pro com rumble por Bluetooth no Linux —
  `https://github.com/ValveSoftware/steam-for-linux/issues/7631`. **Não
  reproduzido aqui**
- Manual do 8BitDo SN30 Pro (semântica dos LEDs de modo) —
  `https://manuals.plus/8bitdo/8bitdo-sn30-pro-bluetooth-gamepad-user-manual`.
  **A parte física nunca foi olhada nesta casa** — ver 8.4

**Documentos desta casa**

- [a referência canônica do DualSense](dualsense-referencia-canonica.md) — o
  molde desta página, e o contraste em cada tabela
- [paridade Bluetooth versus cabo](paridade-bluetooth-versus-cabo.md)
- [o estudo dos externos de 07/08](../process/estudos/2026-08-07-ISOLAR-os-externos-o-metodo-da-lightbar-no-pro-e-no-8bitdo.md)
  — o método, o E-1 fechado e os cinco itens de protocolo que esta página **não**
  repete
- [a página de uso do 8BitDo](../usage/troubleshooting-8bitdo.md) — e a nota 3
  dela, que **continua aberta** (ver 4.8)

---

## 11. Ponteiro cruzado — a linha que falta na outra página

Esta página cita a
[referência canônica do DualSense](dualsense-referencia-canonica.md) em todas as
tabelas de contraste. **A recíproca ainda não existe**, e não foi escrita aqui de
propósito: outro trabalho pode estar naquele arquivo agora, e a casa não edita
documento que outra mão pode estar segurando.

A linha a ligar lá, quando houver mão livre — sugerida para o cabeçalho, logo
abaixo da "Regra de uso":

> **Documento irmão:** [os externos — Pro Controller e 8BitDo](externos-referencia-canonica.md).
> Esta página vale **só para o DualSense**. Os controles das outras linhagens têm
> envelope, escalas de IMU, régua de bateria e limitador de taxa **diferentes** —
> e um instrumento escrito para um deles escreve lixo no outro.

E os três pontos em que a página do DualSense **ganha** conteúdo desta:

1. **Seção 5 (IMU).** As escalas do Pro (4096 LSB/g e 14,247 LSB por grau/s) são
   o contraste que falta às do DualSense (8192 e 1024) — a diferença é de 2x e
   cerca de 14x, e é armadilha carregada para quem comparar eixos.
2. **Seção 7 (o checklist do virtual).** As sementes de CRC-32 `0xA1` (entrada) e
   `0xA3` (feature) são **compartilhadas** com o DualShock 4; a página só
   documenta a de saída (`0xA2`).
3. **`GYRO-EDGE-RATE-01`.** O Pro **declara** uma taxa (8 ms no comentário do
   driver, 15 ms no default) e **entrega outra** (11,2 ms, medida três vezes). É
   a mesma família de defeito da sprint aberta, com um segundo aparelho e um
   número medido.
