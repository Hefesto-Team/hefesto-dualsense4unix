# Firmware e modos dos externos — o 8BitDo SN30 Pro e o Pro Controller

- **Levantado em:** 11/08/2026, com os dois aparelhos ligados ao mesmo tempo —
  o 8BitDo no **cabo**, em modo Switch, e o Pro Controller genuíno no **rádio**
- **Por que existe:** a pergunta dela foi *"se o módulo DKMS importa para o Pro,
  não importaria também para o 8BitDo? e se houver firmware ou driver que o
  projeto deixou passar?"*. A metade do **driver** já estava respondida antes
  desta página começar — os dois caem no mesmo `hid_nintendo`, e **não falta
  driver**. O que faltava era a outra metade: os **modos** e o **firmware**
- **Limite de escopo, declarado antes de qualquer afirmação:** **nada foi
  baixado, nada foi gravado em aparelho nenhum, e nenhum binário de firmware
  entra neste repositório.** O `LICENSE` daqui é MIT e o firmware da 8BitDo e o
  da Nintendo são proprietários; e gravar firmware pode inutilizar o aparelho.
  **Quem decide atualizar é ela.** Esta página é documentação, e só

## Relação com as outras páginas

Esta página **complementa** três que já existem e não repete o que elas provam:

| página | o que ela já responde |
|---|---|
| `docs/usage/troubleshooting-8bitdo.md` | os combos, como identificar o modo agora, e a morte por Bluetooth em modo Switch |
| `docs/protocol/externos-referencia-canonica.md` | o comportamento observável dos quatro aparelhos, por barramento |
| `docs/protocol/driver-hid-nintendo-por-dentro.md` | o C que governa os dois `057E:2009`, com `arquivo.c:linha` |

Onde esta página **corrige** ou **fecha** um item daquelas, a linha diz isso na
cara, com a data.

---

## 0. Como ler

### 0.1 As fontes, e elas não têm o mesmo peso

| marca | o que significa |
|---|---|
| **[MEDIDO 11/08]** | medido nesta máquina hoje, com a régua descrita na seção 8.1 |
| **[CÓDIGO]** | lido no fonte instalado nesta máquina (driver DKMS, `fwupd`, `src/` do produto) ou no fonte público de kernel/SDL |
| **[FABRICANTE]** | documentação publicada pela 8BitDo ou pela Nintendo |
| **[COMUNIDADE]** | engenharia reversa ou relato público de terceiro |
| **[PREVISÃO]** | derivado de código, **não** exercitado. Vem sempre com o teste que o fecharia |

Graus: **ALTA**, **MÉDIA**, **SEM PROVA** — a mesma escala das outras páginas de
protocolo.

### 0.2 A resposta curta, para quem só quer ela

1. **Não falta driver.** Os dois aparelhos são `057E:2009` e caem no mesmo
   `hid_nintendo`; o fork DKMS da casa serve aos dois, e serve **melhor** ao
   clone, porque três dos onze parâmetros existem por causa dele.
2. **A versão de firmware do Pro Controller e a do clone CHEGAM ao kernel a
   cada probe — e o driver as joga fora.** Não há como lê-las sem escrever no
   aparelho. Seção 3.1.
3. **A versão do 8BitDo tem, sim, caminho pronto no Linux, e ele já está
   instalado aqui** — o `fwupd`, com o plugin `ebitdo`. Mas ele **só enxerga o
   aparelho num modo em que ele use o VID próprio**, e não é nenhum dos modos
   que esta casa usa. Seções 3.4 e 7.2.
4. **Há um modo do 8BitDo que esta casa nunca ligou**, e é justamente o que
   destrava o item 3. Seção 2.2.
5. **Atualizar não é recomendado hoje** — e o motivo não é medo. Seção 7.

---

## 1. O que está na mesa, medido agora

**[MEDIDO 11/08]**, grau **ALTA** para toda esta seção.

| | 8BitDo SN30 Pro | Pro Controller genuíno |
|---|---|---|
| barramento | **cabo (USB)** | **rádio (Bluetooth)** |
| VID:PID | `057e:2009` | `057e:2009` |
| `bcdDevice` | **`0200`** | **não existe por rádio** (é descritor USB) |
| serial USB | `000000000001` | — |
| driver | `nintendo` | `nintendo` |
| instância HID | `0003:057E:2009.0008` | `0005:057E:2009.0007` |
| `hidraw` | `hidraw7` | `hidraw6` |
| endereço reportado | `E4:17:D8:00:00:1A` | `E0:F6:B5:00:00:53` |
| OUI na base do sistema | `8BITDO TECHNOLOGY HK LIMITED` | `Nintendo Co.,Ltd` |
| descritor HID | 203 bytes | 170 bytes |
| LEDs registrados | 5 (4 verdes + 1 azul) | 5 |
| bateria | sim | sim |

Os endereços aparecem com os octetos 4 e 5 zerados — a máscara desta casa.

**O `bcdDevice` do genuíno não pôde ser medido hoje**, porque ele está no
rádio. O `0210` que o repositório usa como discriminador vem de medições
anteriores (`assets/84-nintendo-pro-variant.rules`, o estudo de 27/07 e o
`README.md` do DKMS, três lugares concordando). Aqui fica **não medido hoje**.

### 1.1 Duas perguntas abertas que fecharam hoje, por acidente

O `docs/protocol/driver-hid-nintendo-por-dentro.md`, seção 8, lista sete coisas
que aquela sessão **não** conseguiu verificar. As duas primeiras eram a mesma
medição, e o `journalctl` do boot atual a tinha:

```
nintendo 0003:057E:2009.0008: controller MAC = E4:17:D8:00:00:1A
nintendo 0003:057E:2009.0008: using factory cal for left stick
nintendo 0003:057E:2009.0008: using factory cal for right stick
nintendo 0003:057E:2009.0008: using factory cal for IMU
```

**O que isso prova, e é bastante:**

1. **O clone RESPONDE ao `REQ_DEV_INFO` (`0x02`).** O endereço só existe porque
   a resposta veio: `joycon_read_info` copia `subcmd_reply.data[4..9]`
   (`hid-nintendo.c:2712`). O item 2 da seção 8 fecha em **sim**.
2. **A identidade dele NÃO foi sintetizada.** O caminho degradado imprime
   `falling back to a synthesized identity` (`hid-nintendo.c:2906`) e fabrica um
   endereço começando em `02:`. O log do boot inteiro não tem essa linha, e o
   endereço começa em `E4:17:D8`, a OUI pública da 8BitDo. O item 1 fecha em
   **identidade real**.
3. **O clone tem calibração de fábrica de stick E de IMU na SPI, e o driver a
   leu.** A `docs/data/mapa-controles.csv` tem as duas linhas do `sn30` —
   *"Calibração de fábrica dos sticks"* e *"Calibração de fábrica da IMU"* —
   como `desconhecido`. As duas viram **tem**, por cabo e com prova no log.

**Uma diferença que sobra, e ela NÃO é firmware:** o genuíno diz `using **user**
cal` nos três, o clone diz `using **factory** cal`. Isso é conteúdo de SPI, não
versão de firmware — a calibração de usuário é o que um console Switch grava
quando alguém calibra o controle por lá. Atualizar firmware não muda isso;
calibrar num Switch muda. Grau **ALTA** para o mecanismo.

---

## 2. Os modos do 8BitDo — o mapa completo

### 2.1 Qual aparelho é o dela, e por que isso decide tudo

São **três** produtos com nome parecido e firmware independente: **SN30 Pro**
(2018, gêmeo do SF30 Pro), **SN30 Pro+** (2020) e **Pro 2** (2021, sem "SN30" no
nome oficial). Há ainda três primos **só cabo** — SN30 Pro USB, Pro 2 Wired e
Pro 2 for Xbox — que têm **menos** modos e outros IDs.

**Uma coisa já dá para eliminar sem tocar no aparelho:** o **Pro 2 não troca de
modo por combo**, e sim por uma **chave física de quatro posições** (S/X/D/A) na
traseira. **[FABRICANTE]**, grau **ALTA**. Como esta casa mediu com ela, em
03/08/2026, que o modo troca com `Start + A`, **o controle dela não é um Pro 2**.
É SN30 Pro ou SN30 Pro+ — e essa distinção continua aberta, porque ela decide
qual índice de firmware vale (seção 4).

### 2.2 A tabela dos modos, e a correção de vocabulário que ela traz

| modo (nome da 8BitDo) | combo | VID:PID cabo | VID:PID Bluetooth | driver no Linux |
|---|---|---|---|---|
| **D-input / Android** | `B + Start` | `2dc8:6001` (Pro) / `2dc8:6002` (Pro+) | `2dc8:6101` / `2dc8:6102` | `hid-generic` |
| **X-input / Windows** | `X + Start` | `045e:028e` | `045e:02e0` | `xpad` (cabo) / `hid-microsoft` (rádio) |
| **macOS / Apple** | `A + Start` | `054c:05c4` | `054c:05c4` | `hid-playstation` |
| **Switch** | `Y + Start` | `057e:2009` | `057e:2009` | `hid-nintendo` |
| **atualização de firmware** | `L1 + R1 + Start`, 3 s | `2dc8:5750` | — | (bootloader) |

**Fontes, por linha.** Os IDs de D-input e o bootloader vêm do `usb_ids.h` do
SDL, que traz o combo no próprio comentário, e da wiki do `fwupd`; os IDs de
X-input e macOS, da wiki do `fwupd` e da tabela cabo/rádio do
*gamepad-cheatsheet*; os combos, do manual e da FAQ da 8BitDo. **[CÓDIGO]** e
**[FABRICANTE]**, grau **ALTA** — exceto o `045e:02e0` do SN30 Pro (sem "+"),
que só está confirmado para o Pro+, e fica **MÉDIA**.

> **A CORREÇÃO, e ela é de vocabulário, não de número.**
>
> O que este repositório chama, em toda parte, de **"modo DirectInput/PS4"** é
> `Start + A` e produz `054c:05c4`. **Na nomenclatura da 8BitDo isso é o modo
> macOS**, e o "D-input" de verdade é outro combo — `B + Start` — que produz
> `2dc8:6001`.
>
> Os números do repositório estão **certos**: `Start + A` foi medido com ela em
> 03/08, `054c:05c4` foi medido em 25/07, e é o caminho bom por Bluetooth. O que
> estava errado era o **nome**. E o nome custou uma coisa concreta: enquanto o
> modo `Start + A` se chamou "DirectInput", **ninguém aqui procurou o modo
> D-input de verdade** — que é onde a seção 3.4 mostra que mora a resposta sobre
> firmware.
>
> **[FABRICANTE]** + **[CÓDIGO]**, grau **ALTA**. Data: 11/08/2026.

**Consequência direta: há um quinto estado que esta bancada nunca ligou.** Os
modos exercitados aqui são Switch (cabo e rádio) e macOS/`054c:05c4` (rádio). O
X-input nunca foi ligado, e o **D-input verdadeiro (`B + Start`,
`2dc8:6001`/`6002`) também não**.

### 2.3 Como saber em que modo ele está, pelas lâmpadas

A FAQ e o manual da 8BitDo **discordam na forma de dizer** — a FAQ escreve
"LED 2 blinking", o manual escreve "the 1st and 2nd LEDs start to blink" para o
mesmo modo. A leitura que reconcilia as duas é que o indicador é uma
**contagem**, não uma lâmpada específica:

| lâmpadas | modo |
|---|---|
| 1 piscando | D-input |
| 2 piscando | X-input |
| 3 piscando | macOS |
| girando de um lado ao outro | Switch (ou pareando) |
| acesa fixa | conectado |
| **vermelha piscando** | **bootloader / atualização** |

**[FABRICANTE]** para as linhas; **MÉDIA** para a reconciliação, que é leitura e
não citação. Bate com o que `docs/protocol/externos-referencia-canonica.md:753`
já registrava.

`Start` sozinho **liga no último modo usado** e reconecta ao aparelho já
pareado; `Start` por 3 s desliga; por 8 s força o desligamento. **[FABRICANTE]**,
grau **ALTA**.

**O modo de fábrica não foi encontrado** para o SN30 Pro nem para o Pro+ —
nenhuma fonte oficial declara em que modo o aparelho sai da caixa. Não invento.

**Modo teclado: não existe nestes modelos.** O modo teclado e o iCade eram da
geração anterior (N30/F30/NES30/SNES30/SN30/SF30, os **sem** "Pro") e foram
removidos no firmware 4.0 daquela família. **[COMUNIDADE]**, grau **MÉDIA**.

### 2.4 O que o produto DIRIA e FARIA em cada modo

Isto foi **executado**, não deduzido: as funções reais de
`app/actions/external_controllers.py` e de `core/external_leds.py` foram
chamadas com a entrada de cada modo. As duas primeiras linhas vêm dos aparelhos
que estão na mesa; as outras, de entrada sintética montada com o VID/PID/OUI
daquele modo. **[MEDIDO 11/08]** para as duas primeiras; **[CÓDIGO]** grau
**ALTA** para as demais, porque o que varia é só a entrada.

| modo | driver | o Hefesto vê? | `friendly_type` diz | `brand_of` diz | LED de posição |
|---|---|---|---|---|---|
| **Switch, cabo** | `nintendo` | **sim** | **"Pro Controller (modo Switch)"** | **"8BitDo"** | barra verde, funciona |
| **Switch, rádio** | `nintendo` | sim | **"Pro Controller (modo Switch)"** | "8BitDo" | barra verde |
| **macOS, rádio** | `playstation` | sim | "8BitDo" | "8BitDo" | lightbar RGB (ver `P-4`) |
| **macOS, cabo** | `playstation` | sim | **"Sony"** | **"Sony"** | lightbar RGB |
| **X-input, cabo** | `xpad` | sim | **"Xbox 360"** | "Xbox" | **nenhum** |
| **X-input, rádio** | `hid-microsoft` | sim | "Xbox" (por VID) | "Xbox" | **nenhum** |
| **D-input, cabo/rádio** | `hid-generic` | **ver 2.6** | "8BitDo" | "8BitDo" | **nenhum** |

**Os três erros de rótulo que a tabela expõe:**

1. **Em modo Switch o produto chama o clone de "Pro Controller".** A causa é
   conhecida e já documentada: `friendly_type` consulta o par VID/PID **antes**
   da OUI, e os dois aparelhos têm o mesmo par. Grau **ALTA**.
2. **Em modo macOS pelo CABO ele chama o clone de "Sony".** Este é novo. Por
   rádio o `uniq` é o endereço real e a OUI salva o rótulo; por cabo o
   `hid-playstation` da casa entrega ou um endereço truncado do pairing info
   (`ds4_short_pairing_info`) ou um **sintético começando em `02:`**
   (`hid-playstation.c:2308`). No caminho sintético a OUI vira `02054c`, que não
   está em `_BRAND_BY_OUI`, e a função cai em `_VENDOR_BY_VID["054c"]`. O
   comentário da própria `brand_of` supõe *"sem `uniq`, caso USB"* — e o caso
   real não é `uniq` ausente, é `uniq` **fabricado**. **[CÓDIGO]**, grau
   **ALTA**.
3. **Em X-input com o VID da Microsoft ele chama o clone de "Xbox 360"**, e não
   há sinal nenhum que o desminta: nem `xpad` nem `hid-microsoft` preenchem
   `uniq` com endereço de fabricante que caia em `_BRAND_BY_OUI`. Grau **ALTA**.

**A correção agradável, e ela contradiz o comentário do próprio código:** por
CABO, em modo Switch, o `brand_of` **acerta** e devolve "8BitDo". O comentário
da função supõe `uniq` vazio no USB; o `hid-nintendo` preenche `hdev->uniq` com
o endereço que o `REQ_DEV_INFO` devolveu (`hid-nintendo.c:2350` e `:2414`), e a
OUI chega. **[MEDIDO 11/08]** — a função foi chamada com o aparelho de verdade e
devolveu `8BitDo`. Grau **ALTA**.

### 2.5 Quem pega o aparelho, medido nos módulos desta máquina

| modo | driver | prova local | grau |
|---|---|---|---|
| Switch | `hid_nintendo` | o aparelho está nele agora | **[MEDIDO 11/08]** ALTA |
| macOS (`054c:05c4`) | `hid_playstation` | medido em 25/07 | ALTA |
| X-input **cabo** | `xpad` | o módulo casa **VID + classe de interface**, PID curinga | **[MEDIDO 11/08]** ALTA |
| X-input **rádio** | `hid-microsoft` | alias `hid:b0005g*v0000045Ep000002E0` no módulo instalado | **[MEDIDO 11/08]** ALTA |
| D-input | `hid-generic` | por eliminação: nenhum módulo daqui reivindica `2dc8:600x` como HID | **[MEDIDO 11/08]** MÉDIA |

Duas coisas que só aparecem lendo os módulos instalados, e que a página de uso
não tinha:

**(a) O `xpad` reivindica o VID da própria 8BitDo.** Três aliases, com PID
curinga:

```
usb:v2DC8p*d*dc*dsc*dp*icFFisc5Dip01in*     (protocolo Xbox 360 com fio)
usb:v2DC8p*d*dc*dsc*dp*icFFisc5Dip81in*
usb:v2DC8p*d*dc*dsc*dp*icFFisc47ipD0in*     (protocolo Xbox One)
```

São 54 VIDs distintos na lista dele, e a 8BitDo é um. **O casamento é por classe
de interface**, não por PID: um aparelho 8BitDo que fale HID comum (classe `03`)
**não** cai no `xpad`, mesmo tendo o PID que consta da tabela interna do módulo
— e a tabela tem `8BitDo SN30 Pro` nas strings do binário instalado.
**[MEDIDO 11/08]**, grau **ALTA**.

**(b) O `xpad` é USB puro.** 116 aliases `usb:`, **zero** aliases `hid:`. Por
rádio ele nunca entra — o que já estava certo na página de uso, e agora está
medido no módulo desta máquina. Quem pega o X-input por Bluetooth é o
`hid-microsoft`, e ele **conhece o SN30 Pro+ pelo nome**: o `045e:02e0` entrou
no kernel por um patch de *rumble support for the 8bitdo SN30 Pro+ controller*.
**[MEDIDO 11/08]** para o alias local; **[CÓDIGO]** para a origem do patch.

> **NOTA DATADA — 11/08/2026.** `docs/usage/troubleshooting-8bitdo.md` marca a
> linha do X-input por Bluetooth como **EXPERIMENTO**, com *"PID provável
> `02e0`/`02fd`"*. **O `02e0` está confirmado**, e o driver é o `hid-microsoft`,
> não o `hid-generic`. O que continua EXPERIMENTO é o **aparelho** naquele modo —
> ninguém aqui o ligou. O que saiu do experimento foi só a metade do **driver**.

### 2.6 A luz de posição, e o modo em que o Hefesto pode não ver nada

**A luz.** `resolve_external_leds` (`core/external_leds.py:297`) só conhece dois
formatos de nome de nó: `<instância>:green:player-N`, do `hid-nintendo`, e
`<inputNN>:red|:green|:blue`, da lightbar do `hid-playstation`. **O `xpad`
registra o nó como `xpad%d`** — lido das strings do módulo instalado. Logo, em
X-input: `resolve_external_leds` devolve `(None, None)`, `apply_player_number`
devolve `False`, e mesmo que casasse, a
`assets/79-external-controller-leds.rules` não daria permissão de escrita, porque
nenhuma das seis regras dela contempla esse nome. **Dois motivos independentes
para o mesmo resultado: sem número de jogador.** **[MEDIDO 11/08]**, grau
**ALTA**.

**O risco maior, e é ausência, não rótulo errado.** `discover_external_gamepads`
só enxerga um evdev que tenha `BTN_GAMEPAD` ou `BTN_SOUTH`
(`core/evdev_reader.py:628`) — e **os dois são o mesmo código, `0x130`**,
conferido no `input-event-codes.h` desta máquina. Para um aparelho servido pelo
`hid-generic`, o código base dos botões é decidido pela **collection de
aplicação** do descritor: `Gamepad` põe os botões em `0x130`; `Joystick` põe em
`0x120` (`BTN_JOYSTICK`/`BTN_TRIGGER`).

**Se o modo D-input declarar `Joystick` em vez de `Gamepad`, o Hefesto não vê o
controle — nem na lista de externos, nem em lugar nenhum.**

Que isso não é teoria, esta máquina mostra: o descritor do 8BitDo no cabo
**declara `Usage (Joystick)`** (`05 01 15 00 09 04 a1 01`) e o kernel o nomeia
`Joystick` no log de bind; o do Pro por rádio declara `Usage (Gamepad)`
(`05 01 09 05 a1 01`) e o log diz `Gamepad`. Em modo Switch isso não custa nada,
porque o `hid-nintendo` constrói o `input_dev` por conta própria e nunca usa o
mapeamento genérico. **Num modo servido pelo `hid-generic`, custaria tudo.**
**[MEDIDO 11/08]** para os descritores e para os nomes no log; **[PREVISÃO]**
grau **MÉDIA** para a consequência.

**Contraindício honesto:** o `SDL_GameControllerDB` tem entradas para
`2dc8:6001` e `2dc8:6002`, e o SDL costuma exigir semântica de gamepad. Isso
**enfraquece** a previsão sem matá-la, porque o SDL tem caminho próprio de
mapeamento e não depende do `BTN_` que o kernel escolheu.

**O teste que fecha, e cabe num comando** — com o controle no modo a
investigar, sem `sudo`:

```bash
.venv/bin/python -c "
from hefesto_dualsense4unix.core.evdev_reader import discover_external_gamepads
for e in discover_external_gamepads():
    print(e['name'], e['vid'], e['pid'], e['bus'], e['driver'])
"
```

Se o aparelho não aparecer na saída, a previsão está confirmada.

### 2.7 O endereço muda com o modo — e a P-2 já estava respondida

`docs/usage/troubleshooting-8bitdo.md` registra, **medido nesta bancada em
25/07**, que o 8BitDo usa **endereços de rádio diferentes em cada modo**, ambos
com a OUI `E4:17:D8`. O endereço que o `REQ_DEV_INFO` devolveu **hoje pelo
cabo**, em modo Switch, é `E4:17:D8:00:00:1A` — **o mesmo** que o log do BlueZ
daquele dia registrou para o modo Switch. Duas rotas independentes, 17 dias
entre elas, mesmo endereço. **[MEDIDO 11/08]**, grau **ALTA**.

> **NOTA DATADA — 11/08/2026.** A `P-2` da
> `docs/protocol/externos-referencia-canonica.md` (seção 8.2) pergunta *"o
> 8BitDo troca de endereço ao trocar de modo?"* e a marca como **nunca medida**,
> grau BAIXA, com um plano de pareamento novo como custo. **Ela já estava
> respondida** na página de uso, medida em 25/07/2026 — e a medição de hoje a
> corrobora por um terceiro caminho, sem parear nada. Isto não é achado novo: é
> a casa sabendo em duas páginas e a terceira não ter sido avisada. Fica aqui
> porque a canônica não é editável por esta sessão.

---

## 3. Firmware — como identificar cada um

### 3.1 A versão do Pro Controller CHEGA ao kernel e é jogada fora

Este é o achado de código desta página.

O subcomando `0x02` (`REQ_DEV_INFO`) devolve, segundo a engenharia reversa
pública (`dekuNukem/Nintendo_Switch_Reverse_Engineering`), este payload:

| offset | conteúdo |
|---|---|
| **0-1** | **versão de firmware** (maior, menor) |
| 2 | tipo de controle: 1 = Joy-Con E, 2 = Joy-Con D, **3 = Pro** |
| 3 | sempre `0x02` |
| 4-9 | endereço Bluetooth, **big-endian** |
| 10 | sempre `0x01` |
| 11 | `0x01` = usa as cores gravadas na SPI |

**[COMUNIDADE]** para o layout, grau **MÉDIA** — é a mesma fonte que o driver
credita, e ela já foi refutada nesta casa em pelo menos um número.

E o `joycon_read_info` do fonte instalado (`hid-nintendo.c:2696`) lê **dois** dos
seis campos:

```c
for (i = 4, j = 0; j < 6; i++, j++)
	ctlr->mac_addr[j] = report->subcmd_reply.data[i];
...
ctlr->ctlr_type = report->subcmd_reply.data[2];
```

**Os offsets 0 e 1 nunca são tocados.** Não há `DEVICE_ATTR` para versão, não há
campo na struct, e o único `hid_info` do caminho imprime o endereço.
**[CÓDIGO]**, grau **ALTA** — conferido no fonte que roda nesta máquina, byte a
byte o mesmo de `assets/dkms/hid-nintendo/hid-nintendo.c`.

**Consequência, e vale para os dois `057E:2009`:** a versão de firmware do Pro
genuíno e a do clone **passaram por este kernel hoje**, nos mesmos pacotes que
produziram as duas linhas `controller MAC = ...` da seção 1.1, e foram
descartadas. Ler o número exige mandar o `0x02` por `hidraw` — isto é,
**escrever no aparelho**, fora do escopo desta página, e disputando o `hidraw`
com o driver vivo (a terceira armadilha do `CLAUDE.md` da raiz).

**Ferramenta pronta no Linux para ler essa versão: não existe.** O
`joycon-python` não expõe device info; o `joycontrol` é emulação, não leitura; o
`ns-joycon` (Node.js) expõe, e o `jc_toolkit` mostra, mas é Windows.
**[COMUNIDADE]**, grau **MÉDIA**.

### 3.2 O contraste que dói: o DualSense entrega de graça

Medido no mesmo boot, no mesmo log:

```
playstation 0003:054C:0CE6.0009: Registered DualSense controller
                                 hw_version=0x00000711 fw_version=0x0110002a
```

**O `hid-playstation` imprime versão de hardware e de firmware em toda probe. O
`hid-nintendo` não imprime nenhuma das duas.** É assimetria de driver, não de
aparelho — os dois protocolos carregam a informação. **[MEDIDO 11/08]**, grau
**ALTA**.

Vale para quem pensar em pôr "firmware do controle" na interface: o DualSense já
tem o número de graça, o `057E:2009` exigiria código de `hidraw` próprio, e o
8BitDo exigiria que ele estivesse noutro modo (3.4). **Três caminhos diferentes
para um campo só** — é o tipo de promessa que se mede antes de desenhar.

### 3.3 O que dá para ler sem escrever no aparelho

| dado | Pro genuíno | 8BitDo | onde |
|---|---|---|---|
| versão de firmware | **não** | **não neste modo** | 3.1 e 3.4 |
| `bcdDevice` | só por cabo | **`0200`**, medido | `/sys/bus/usb/devices/*/bcdDevice` |
| endereço e OUI | sim | sim | `HID_UNIQ`, `dmesg` |
| tipo de controle | sim | sim | via driver |
| calibração de fábrica x de usuário | sim | sim | `dmesg` da probe |

**Sobre o `bcdDevice` como proxy de versão de firmware:** é tentador, e é **SEM
PROVA**. Ele é o *device release number* do descritor USB, e nada garante que a
8BitDo ou a Nintendo o incrementem a cada firmware. A pesquisa não achou fonte
nenhuma ligando os dois, e há um contraindício de código forte: o `fwupd` usa um
**comando proprietário** para obter a versão do 8BitDo, o que não faria sentido
se o descritor a carregasse. Não use `0200`/`0210` como número de firmware — use
para o que foi medido: separar clone de genuíno no cabo.

### 3.4 O 8BitDo: o caminho existe, está instalado, e destranca com um combo

**[CÓDIGO]** + **[MEDIDO 11/08]**, grau **ALTA**.

O `fwupd` tem um plugin `ebitdo`, protocolo `com.8bitdo`, que **lê a versão de
firmware do aparelho em modo normal** — não só em bootloader. A decodificação é
`versão_crua / 100` e `versão_crua % 100`, o que produz os `1.34`, `2.04` que
aparecem no `fwupdmgr`.

**Nesta máquina o plugin está presente e ligado** — `fwupd` 1.9.32, `ebitdo`
listado no `get-plugins`.

**E mesmo assim ele não enxerga o controle hoje.** `fwupdmgr get-devices`
devolve **placa-mãe, CPU, NVMe e TPM — nenhum gamepad**. O motivo está no
`builtin.quirk` instalado, que associa o plugin `ebitdo` a **24 pares VID/PID**,
e a nenhum outro:

```
2DC8: 1002 2100 2101 5006 5750 6000 6001 6002 9000 9001 9012 9015 AB11 AB12 AB20 AB21
1235: AB11 AB12 AB20 AB21
0483:5760   1002:9000   2002:9000   8000:1002
```

**Nem `057E:2009` nem `054C:05C4` estão na lista** — conferido com `grep` no
arquivo. E os dois são justamente os pares que o 8BitDo veste em modo Switch e
em modo macOS, que são os dois modos que esta casa usa.

**Mas `2DC8:6001` e `2DC8:6002` estão**, e são os pares do modo **D-input**. O
arquivo desta máquina diz, literalmente:

```
[USB\VID_2DC8&PID_6001]
Plugin = ebitdo
Flags = will-disappear
```

E o `2DC8:5750`, o bootloader, está com `Flags = is-bootloader`.

> **A resposta prática, e é a mais útil desta página.**
>
> Enquanto o 8BitDo estiver disfarçado de Nintendo ou de Sony, **nenhuma
> ferramenta que case por VID/PID consegue falar com ele como 8BitDo** — nem o
> `fwupd`, nem o atualizador oficial.
>
> **Pôr o controle em D-input (`B + Start`) e ligar o cabo o torna
> `2dc8:6001`/`6002` — um par que o `fwupd` desta máquina já reconhece.** A
> partir daí, `fwupdmgr get-devices` **lê a versão sem gravar nada.**

Isso é **medição, não palpite**, e explica sozinho por que "firmware do 8BitDo"
nunca apareceu neste repositório: o aparelho passa a vida inteira aqui vestido
de outra marca, e o modo que o desmascara é justamente o que ninguém ligou.

**Três ressalvas honestas:**

1. **Não sei o PID exato dela.** `6001` é SN30 Pro, `6002` é SN30 Pro+, e a
   seção 2.1 não resolveu qual dos dois é. **Os dois estão na lista**, então a
   ressalva não bloqueia o teste — só impede prometer o resultado.
2. **O `xpad` tem `2dc8:6001` na tabela interna dele.** Como o casamento real é
   por classe de interface `FF/5D` (2.5a) e um D-input é HID classe `03`, o
   esperado é que o `xpad` **não** o pegue. Mas se pegar, o `fwupd` pode ter de
   destacar o driver — e aí deixa de ser leitura pura. **[PREVISÃO]**, grau
   **MÉDIA**. Se `fwupdmgr get-devices` mostrar o aparelho, a ressalva morreu.
3. **`fwupdmgr get-devices` é leitura; `fwupdmgr update` grava.** Só o primeiro
   entra em qualquer recomendação desta página.

---

## 4. As versões que existem, e o que os changelogs dizem

Fonte: os `readme` originais da 8BitDo espelhados em `fwupd/8bitdo-firmware` e o
índice de firmware do suporte oficial. **[FABRICANTE]** para o conteúdo; grau
**MÉDIA**, com as ressalvas de 4.3.

### 4.1 SN30 Pro

| versão | data | mudança de comportamento |
|---|---|---|
| 1.10 | 08/12/2017 | modo de sono no Bluetooth; **vibração no modo X-input**; **latência menor com o Switch** |
| 1.20 | 12/12/2017 | "significant vibration optimization" |
| 1.21 | 13/12/2017 | **desconecta o Bluetooth quando o USB é usado** |
| 1.22 | 20/12/2017 | estabilidade do **pareamento Bluetooth** |
| 1.23 | 28/12/2017 | vibração no X-input; **adiciona modo USB para Mac** |
| 1.37 | — | "fixed the vibration issue on Switch mode" |
| **2.07** | — | "fixed an issue with abnormal vibration in Switch mode" (índice oficial de hoje) |

### 4.2 SN30 Pro+ e Pro 2

| modelo | versão | mudança |
|---|---|---|
| SN30 Pro+ | 3.01 (09/08/2019) | **pareamento Bluetooth pelo cabo USB em modo Switch**; corrige indicação de bateria |
| SN30 Pro+ | 5.02 | "optimized the accuracy of joystick"; vibração no modo Switch |
| Pro 2 | 3.07 | vibração anormal no modo Switch |

### 4.3 O que se lê disso, e o que NÃO se lê

**O tema recorrente é a VIBRAÇÃO** — aparece em sete das linhas acima. Depois
vêm **pareamento Bluetooth** e **latência**. Isso importa aqui porque as três
coisas são exatamente onde o clone diverge nesta mesa.

**O que os changelogs NÃO trazem:**

- **nada sobre IMU/giroscópio** no SN30 Pro ou no Pro+. Há relato de comunidade
  de que um firmware do **Pro 2** expôs o giroscópio no modo D-input; a versão
  citada não foi confirmada em fonte oficial. **SEM PROVA**, e não sustenta
  decisão;
- **nada sobre o handshake USB do modo Switch** — a divergência mais cara medida
  nesta casa (seção 6);
- **nada sobre sniff Bluetooth.**

**Duas ressalvas grandes, e elas limitam tudo acima:**

1. **O espelho do `fwupd` congela em 2020.** Naquele ano a 8BitDo parou de
   publicar os arquivos e passou a servi-los por uma interface fechada. Os
   changelogs pós-2020 vieram do índice do site, com menos detalhe.
2. **A numeração do índice oficial de hoje não bate com a do espelho.** O site
   lista "SN30 Pro (Bluetooth) v2.07"; o espelho vai até 1.37. E o site não
   lista um rótulo "SN30 Pro+". **Não há mapeamento seguro entre as duas
   numerações**, e esta página não inventa um.

Um dado lateral, mas útil: em junho de 2025 a 8BitDo publicou firmwares para
habilitar seus controles no **Switch 2**. **[COMUNIDADE]** (imprensa), grau
**MÉDIA** — irrelevante para esta máquina, mas explica movimento recente de
versão.

### 4.4 O Pro Controller genuíno

**A Nintendo não publica changelog de firmware de controle.** **[FABRICANTE]**,
grau **ALTA** para a ausência — o histórico oficial de atualizações de sistema
foi varrido e a única menção é a versão 9.0.0 do console (09/09/2019), dizendo
que *"pode ser necessária uma atualização de firmware do controle"*, sem número
e sem nota.

Números que circulam na comunidade — `3.89` na nota do dekuNukem — não têm
tabela confiável atrás. **SEM PROVA**, e é por isso que esta página não traz uma
lista de versões do Pro.

**Firmware do Pro que tenha mudado comportamento observável no Linux: não
encontrado.** Há muito relato de instabilidade de pareamento Bluetooth do Pro no
Linux, mas atribuído a kernel/BlueZ/driver, não a versão de firmware. Prefiro
dizer "não encontrado" a esticar evidência fraca.

**Prova de que firmware de gamepad PODE mexer no que o host vê**, e ela é do
lado 8BitDo: a nota oficial do firmware v2.00 do *SN30 Pro for Android* diz que
**"o serviço HID mudou; os aparelhos conectados precisam ser despareados e
reconectados"**. **[FABRICANTE]**, grau **ALTA**. É o argumento mais concreto
para tratar atualização como evento que muda o mapa, não como manutenção.

---

## 5. O procedimento oficial de atualização de cada um

**Documentação. Nada aqui foi executado.**

### 5.1 8BitDo

| item | o que diz |
|---|---|
| ferramenta | **8BitDo Firmware Updater** (`support.8bitdo.com/firmware-updater.html`) |
| sistemas declarados | **Windows 10 ou superior; macOS 10.13 ou superior** — **Linux não é declarado** |
| transporte | **cabo USB obrigatório** — Bluetooth e dongle não carregam o protocolo |
| modo de atualização | **`L1 + R1 + Start`** por cerca de 3 s, até o LED piscar em **vermelho**; então ligar o cabo. O aparelho vira `2dc8:5750` |
| arquivo | um `.dat` por modelo |
| ressalva do fabricante | a entrada automática em modo de upgrade *"não se aplica aos modelos antigos ou descontinuados"* |

**[FABRICANTE]**, grau **ALTA** para ferramenta e sistemas, **MÉDIA** para o
combo (confirmado de forma independente pela comunidade, lido de segunda mão).
O PID `2dc8:5750` do bootloader está **medido no `builtin.quirk` desta
máquina**, com `Flags = is-bootloader`.

**Riscos declarados: nenhum aviso formal de brick foi encontrado escrito pela
8BitDo.** O que existe é operacional e vem de fonte secundária — não desconectar
durante a gravação, e refazer sem desconectar se falhar. **Grau MÉDIA**, e a
ausência de aviso formal é ela mesma um dado.

**A rede de segurança real, e é de código:** o `fwupd` marca esses aparelhos com
`REPLUG_MATCH_GUID` porque **o bootloader re-enumera com VID e PID diferentes**
do modo normal — o que esta máquina confirma, com `5750` num par e `6001` noutro.
Bootloader separado do firmware de aplicação significa que uma gravação
interrompida tende a deixar o aparelho **no bootloader**, não morto.
**[CÓDIGO]**, grau **MÉDIA** — é o comportamento esperado do desenho, não uma
garantia do fabricante.

**Sobre Linux:** há um atualizador **web** da 8BitDo (`web.8bitdo.com`) que usa
WebUSB e por isso só roda em navegador da família Chromium, com relato de
comunidade de que funciona no Linux. **Mas ele cobre aparelhos novos e exclui
modelos antigos**, e **não há confirmação de que o SN30 Pro esteja na lista
dele**. **[COMUNIDADE]**, **SEM PROVA** para o modelo dela.

Há também três projetos de terceiros no Linux — um que baixa da interface
oficial e grava via `fwupd`, um TUI declaradamente inacabado, e um que roda o
atualizador oficial sob Wine. **Nenhum é afiliado à 8BitDo.** Não recomendados,
e citados só para que ninguém os "descubra" depois achando que a página não
olhou. Relato de comunidade a anotar: em bootloader o aparelho **some** da lista
do `fwupdmgr` e re-enumera com outra identidade — mais um motivo para nada aqui
ser automático.

### 5.2 Pro Controller

| item | o que diz |
|---|---|
| caminho | **só pelo console Switch**: HOME > Configurações > Controles e Sensores > **Atualizar Controles** |
| requisito | controle **pareado ao console e ligado**; console com a última atualização de sistema |
| cabo | **não exigido** |
| bateria mínima | **a Nintendo não declara nenhuma** |
| vários controles | um por vez |
| se parar no meio | *"tente atualizar o controle de novo"* |
| se persistir | *"o console e o controle precisarão ser enviados para assistência"* |

**[FABRICANTE]**, grau **ALTA**.

Dois pontos que mudam a decisão:

- **o firmware do controle vem embutido na atualização de sistema do console**,
  não é baixado à parte — atualizar o console já traz o firmware do controle
  junto, e o console o oferece assim que o controle conecta. **[COMUNIDADE]**,
  grau **MÉDIA**;
- **não há downgrade.** O consenso da comunidade é que, uma vez atualizado, não
  se volta. **Grau MÉDIA**, e é a razão pela qual "atualizar para testar" não é
  experimento reversível.

**Não há declaração formal de brick da Nintendo** — a frase sobre assistência
técnica é o mais perto que ela chega.

---

## 6. As divergências medidas, e quais o firmware explica

O projeto tem várias medições em que o clone diverge do genuíno. A pergunta é
qual delas o **firmware** plausivelmente explica — e onde isso é especulação.

| divergência medida | firmware explica? | grau |
|---|---|---|
| **não responde ao handshake USB `0x80 0x02` de 2 bytes** — o genuíno perdoa a transferência curta, o clone não | **sim, quase certamente.** É implementação de protocolo, e é o que firmware é | **MÉDIA** — mecanismo claro, sem changelog que o cite |
| **morre por Bluetooth em modo Switch** (cascata de timeout + rate limiter) | **provavelmente.** É a pilha de subcomando do firmware não acompanhando o ritmo | **MÉDIA** |
| **precisa de sniff Bluetooth, ao contrário do genuíno** | **sim** — é política de energia do rádio, que mora no firmware | **MÉDIA** |
| **usa endereço de rádio diferente por modo** | **sim, e é por desenho**, não defeito | **ALTA** |
| **`using factory cal` contra `using user cal`** | **NÃO.** É conteúdo da SPI, gravado por um console Switch | **ALTA** |
| **14,96 ms de IMU no cabo contra 11,27 ms do genuíno no rádio** | **indeterminável.** Os dois não estavam no mesmo barramento, e 15 ms é o ramo que o driver declara para **USB** | **não atribuível** |
| **acelerômetro do clone 4 a 6 vezes mais ruidoso em repouso** | **talvez** — pode ser a peça, pode ser filtragem no firmware | **SEM PROVA** |
| **`bcdDevice` `0200` contra `0210`** | não é versão de firmware. Ver 3.3 | **SEM PROVA** para leitura como versão |

**A leitura de conjunto:** as três divergências que o firmware plausivelmente
explica são **de protocolo e de rádio** — exatamente as áreas em que os
changelogs da 8BitDo dizem ter mexido (vibração, pareamento, latência). Mas
**nenhum changelog cita o handshake USB nem o rate limiter de subcomando**, que
são as duas causas medidas aqui. Isso é motivo para **querer a versão**, não
para prever o resultado de uma atualização.

### 6.1 A medição de IMU de hoje, e o que ela corrige

`docs/protocol/driver-hid-nintendo-por-dentro.md`, seção 6.2, afirma **"IMU de
verdade: sim — 200,5 amostras/s medidas"**. **A taxa sozinha não prova isso** —
o relatório `0x30` sempre carrega os bytes de IMU, e um firmware que mandasse
zeros produziria a mesma taxa. É exatamente a armadilha que esta casa já nomeou:
o instrumento mente mais que o produto.

**Medido hoje, por valor e não por taxa** — 6 s por controle, os dois em repouso,
contando amostra a amostra em cada eixo:

| | amostras/s | acelerômetro Z | desvio do acelerômetro (X/Y/Z) |
|---|---|---|---|
| 8BitDo, cabo | **199,4** | 4153 a 4269 | **7,3 / 5,5 / 9,1** |
| Pro genuíno, rádio | **267,2** | 4200 a 4207 | **1,8 / 1,5 / 1,4** |

**A conclusão sobe de "há dado chegando" para "há sensor de verdade":** os dois
reportam o eixo Z parado em torno de **4200**, que é a gravidade na mesma escala.
Um firmware que mentisse não acertaria a escala do genuíno por acaso. **A IMU do
clone é real e está calibrada na mesma unidade.** **[MEDIDO 11/08]**, grau
**ALTA**.

**E aparece uma diferença nova:** em repouso, o acelerômetro do clone é **4 a 6
vezes mais ruidoso** que o do genuíno. Isso é peça ou filtragem — **não dá para
dizer qual**, e nenhum changelog da 8BitDo menciona IMU para este modelo. **SEM
PROVA** para a causa; **ALTA** para o número.

As taxas de hoje (199,4 e 267,2) batem com as de mais cedo (200,5 e 266,1),
medidas por outra sessão com outra régua. **Duas rotas, mesmo número** — é o que
autoriza acreditar nelas.

### 6.2 Uma afirmação do repositório que NÃO se reproduziu hoje

`docs/usage/troubleshooting-8bitdo.md:190` diz, marcado **PROVADO**:

> *"no bind aparece `unknown main item tag 0x0` — descriptor HID malformado,
> típico de firmware clone; o original não produz isso"*

**Hoje, com o clone no cabo em modo Switch, isso não acontece.** Duas
verificações independentes:

1. o `journalctl -k` do boot inteiro **não tem uma única** linha
   `unknown main item tag`;
2. os 203 bytes do descritor dele foram parseados item a item, e **não há um só
   item malformado** — nem main desconhecido, nem item reservado.

**Isto não é contradição, é escopo.** Aquela linha é de 25/07 e o modo daquele
dia não está registrado; o descritor do modo macOS/`054c:05c4` tem **364
bytes**, outro aparelho HID inteiramente. O que fica corrigido é a
generalização: **o descritor malformado não é propriedade "do firmware clone"**
— no descritor de 203 bytes do modo Switch por cabo ele não existe. **[MEDIDO
11/08]**, grau **ALTA** para a ausência; **SEM PROVA** para em qual modo a linha
original apareceu.

### 6.3 O que o clone entrega igual, medido hoje

Para a página não parecer que só cataloga defeito: em modo Switch pelo cabo, o
que chega ao **jogo** é indistinguível do genuíno.

| | 8BitDo cabo | Pro genuíno rádio |
|---|---|---|
| botões no `evdev` | 14, o menor em `0x130` | 14, o menor em `0x130` |
| eixos | X, Y, RX, RY, HAT0X, HAT0Y | os mesmos |
| force feedback | RUMBLE, PERIODIC, SQUARE, TRIANGLE, SINE, GAIN | os mesmos |

**[MEDIDO 11/08]**, grau **ALTA**. É consequência de o `hid-nintendo` montar o
`input_dev` por conta própria: no lado do jogo, os dois são o mesmo aparelho.

---

## 7. A recomendação, e ela tem um preço na mesa

A pergunta foi *"vale ou não vale atualizar o firmware dos aparelhos dela?"*.

### 7.1 O Pro Controller genuíno — NÃO, e por três motivos

1. **Não há como saber o que ganharia.** A Nintendo não publica changelog de
   firmware de controle. Atualizar sem saber o que muda não é decisão, é aposta.
2. **Não há como voltar.** Sem downgrade, um comportamento que piore no Linux
   fica.
3. **Ele funciona.** Hoje ele entrega 267 amostras de IMU por segundo, 11,27 ms
   por relatório, calibração de usuário lida, cinco LEDs, bateria. Não há
   defeito aberto nesta casa que aponte para o firmware dele.

**Uma ressalva que não é recomendação, é aviso:** se ela atualizar o console
Switch e ele oferecer a atualização do controle, isso é assunto dela e do
console. Mas vale saber que **o Linux não avisa quando muda**, porque o
`hid-nintendo` não lê a versão. Se depois de uma atualização de console algo
aqui mudar de comportamento, **a correlação vai ser invisível** — e é o tipo de
coisa que esta casa costuma passar semanas caçando. **Isso é motivo para ANOTAR
a data**, não para atualizar nem para deixar de atualizar.

### 7.2 O 8BitDo — NÃO AINDA, e agora há um caminho barato para saber

**Não sei se vale, e digo por quê: não sei em que versão ele está.** Não saber a
versão instalada torna a tabela da seção 4 inútil para decidir — ela pode listar
correções que ele já tem.

**O que mudou com esta página:** até hoje, "descobrir a versão" parecia exigir
Windows. **Não exige.** O `fwupd` desta máquina já reconhece o par do modo
D-input, e `get-devices` é leitura pura.

**Os três passos, na ordem, e nenhum grava nada:**

1. **Descobrir o modelo.** SN30 Pro e SN30 Pro+ têm numerações independentes.
   **Já se sabe que não é um Pro 2** (aquele troca de modo por chave física, e o
   dela troca por combo). Falta separar Pro de Pro+ — é olhar o aparelho: o Pro+
   tem gatilhos maiores e o nome impresso atrás. **Cinco segundos de olho dela.**
2. **Ler a versão, sem gravar.** Com o controle **desligado**, segurar
   **`B + Start`** para ligar em D-input (uma lâmpada piscando), ligar o cabo, e
   rodar:

   ```bash
   fwupdmgr get-devices          # leitura pura; não atualiza nada
   ```

   Se aparecer um aparelho 8BitDo com `Current version`, a pergunta inteira ganha
   chão. Se não aparecer, sabemos que o caminho do `fwupd` não serve a este
   modelo — o que também é resposta, e das boas.

   **De brinde, o passo 2 resolve outra dívida:** enquanto ele estiver em
   D-input, o comando da seção 2.6 responde se o Hefesto **enxerga** o controle
   nesse modo. São dois resultados por uma ligada.

   Para voltar ao normal: desligar (`Start` por 3 s) e ligar de novo com o combo
   do modo de sempre.
3. **Só então comparar** a versão lida com o índice oficial do modelo certo, e
   decidir com changelog na mão.

**O que eu diria depois disso, e é previsão, não promessa:** se ele estiver numa
versão anterior às que corrigem *"abnormal vibration in Switch mode"* e a
estabilidade de pareamento Bluetooth, **atualizar tem chance real de mexer na
morte por Bluetooth em modo Switch** — o defeito mais antigo desta mesa. Mas
**é hipótese com mecanismo, grau SEM PROVA**: nenhum changelog menciona o
handshake USB nem o rate limiter de subcomando, que são as duas causas medidas
aqui.

**E o preço, porque ela pede o preço na mesa:**

- o atualizador oficial **não declara Linux**; o caminho realista para
  **gravar** é Windows ou macOS emprestado, ou o atualizador web, que pode não
  cobrir o modelo. **Ler**, ao contrário, roda aqui;
- **atualizar pode apagar os pareamentos** — há changelog oficial de outro
  modelo 8BitDo dizendo textualmente que *"o serviço HID mudou; os aparelhos
  conectados precisam ser despareados e reconectados"*. Nesta máquina isso custa
  re-parear e, provavelmente, uma identidade órfã em `controllers.json`;
- **e cada modo tem o próprio pareamento**, porque o endereço muda com o modo
  (2.7). Um firmware que mexa no serviço HID pode custar isso **vezes o número
  de modos que ela usa**;
- **não há downgrade documentado**;
- e o modo em que ele funciona bem hoje **funciona bem hoje**: o cabo em modo
  Switch está estável, com IMU real e rumble, e o `054c:05c4` por rádio é o
  caminho bom que a casa já escolheu.

**A recomendação de uma linha:** **fazer os três passos e não gravar nada até o
passo 3 responder.** O único passo que precisa dela é o primeiro, e é olhar o
aparelho.

---

## 8. O que NÃO foi medido, e o que eu tentei

Honestidade primeiro, porque cada linha aqui é trabalho de outra sessão.

1. **A versão de firmware dos dois aparelhos.** Não medida, e não por
   dificuldade: **por escopo.** Ler a do `057E:2009` exige escrever o subcomando
   `0x02` no `hidraw`; ler a do 8BitDo exige que ele esteja em D-input, e trocar
   o modo é dela. **Tentei:** `fwupdmgr get-devices` (devolveu só placa-mãe,
   CPU, NVMe e TPM) e uma varredura de todo atributo de `sysfs` do device HID e
   do `usb_device` (só `bcdDevice`, que não é versão de firmware).
2. **O `bcdDevice` do Pro genuíno.** Ele esteve no rádio o dia inteiro, e
   `bcdDevice` é descritor USB. O `0210` da árvore vem de medições anteriores.
3. **Qual dos dois modelos é o dela** — SN30 Pro ou SN30 Pro+. Eliminei o Pro 2
   pelo mecanismo de troca de modo; os outros dois só se separam olhando.
4. **Os modos D-input, X-input e macOS-pelo-cabo.** Tudo o que as seções 2.4,
   2.5 e 2.6 afirmam sobre eles vem dos **módulos e do código instalados nesta
   máquina**, não do aparelho naqueles modos. **Não pedi para ela trocar de
   modo**, por instrução.
5. **Se o `fwupd` realmente lê a versão do modelo dela.** O plugin existe, está
   ligado, e os dois PIDs candidatos (`6001` e `6002`) estão na lista. Se o PID
   exato dela é um deles, não dá para saber sem o aparelho no modo certo.
6. **O modo de fábrica do SN30 Pro / Pro+.** Nenhuma fonte oficial o declara.
7. **Em qual modo apareceu o `unknown main item tag 0x0` de 25/07.** A linha não
   está mais em nenhum journal legível.
8. **Os IDs `2dc8:6103` e `2dc8:3010`**, que aparecem no `SDL_GameControllerDB`
   sob o nome "8BitDo Pro 2". O `6103` segue o padrão "+0x0100 = Bluetooth" e
   sugere que houve firmware do Pro 2 em que o D-input por rádio era `6103`, e
   não `6006`. **SEM PROVA**, e só importaria se o aparelho dela fosse um Pro 2
   — e não é.

### 8.1 Notas de instrumento

**O parser de descritor foi validado antes de eu acreditar nele.** Ele é um
leitor de item HID escrito para esta medição, e um leitor errado teria produzido
um "não há anomalia" convincente e falso. A validação: rodado nos dois
descritores, devolveu os report IDs `0x01 0x10 0x21 0x30 0x80 0x81 0x82` para o
clone e `0x01 0x10 0x11 0x12 0x21 0x30 0x31 0x32 0x33 0x3F` para o genuíno —
**exatamente** as duas listas que a seção 6.2 do
`driver-hid-nintendo-por-dentro.md` publicou hoje, por outro caminho. Duas
rotas, mesmas listas, e só então a ausência de anomalia virou afirmação.

**A régua da IMU conta valor, não byte.** Contar eventos de `evdev` mede o
quanto o controle está tremendo, não a taxa; e contar `SYN_REPORT` mede a taxa,
mas **não** prova que o dado é real. Por isso a seção 6.1 registra as duas
coisas separadas: a taxa (`SYN_REPORT`) e a **distribuição de valor por eixo**.
A prova de que o sensor é real é a segunda, não a primeira.

**Sobre o `fwupdmgr`:** só `--version`, `get-plugins` e `get-devices` foram
usados — todos leitura. Nada de `update`, `install` ou `--force`.

**Nada foi escrito em `/dev/hidraw*`.** As leituras de `evdev` foram sem
`EVIOCGRAB`, e o produto não estava disputando os nós.

---

## 9. Fontes

**Primárias, desta máquina** — medidas em 11/08/2026:

- `journalctl -k -b`: as linhas de probe dos dois `057E:2009` e as de firmware
  dos DualSense;
- `/sys/bus/usb/devices/1-3/`, `/sys/class/hidraw/hidraw6|7/`,
  `/sys/class/leds/`, `/sys/class/power_supply/`;
- `/dev/input/event258` a `event261`, leitura pura, sem `EVIOCGRAB`;
- `modinfo xpad`, `modinfo hid-microsoft`, e as strings dos módulos instalados;
- `fwupdmgr --version`, `get-plugins`, `get-devices`;
- `/usr/share/fwupd/quirks.d/builtin.quirk.gz`;
- `/usr/src/linux-headers-7.0.11-76070011/include/uapi/linux/input-event-codes.h`;
- `systemd-hwdb query OUI:...`.

**Código lido:**

- `assets/dkms/hid-nintendo/hid-nintendo.c` (idêntico ao instalado em
  `/usr/src/hefesto-hid-nintendo-1.0.0/`);
- `assets/dkms/hid-playstation/hid-playstation.c`;
- `src/hefesto_dualsense4unix/app/actions/external_controllers.py`,
  `core/external_leds.py`, `core/evdev_reader.py`,
  `daemon/subsystems/external_identity.py`, `daemon/launch_env.py`;
- `assets/79-external-controller-leds.rules`, `81-hefesto-usb-power.rules`,
  `82-nintendo-pro-nosniff.rules`, `84-nintendo-pro-variant.rules`;
- o plugin `ebitdo` do `fwupd`; `usb_ids.h` do SDL; `xpad.c`, `hid-ids.h` e
  `hid-microsoft.c` do kernel; `SDL_GameControllerDB`.

**Do fabricante:**

- FAQ e manual do SN30 Pro, FAQ do SN30 Pro+, FAQ e página do Pro 2, FAQ do
  Pro 2 Wired e do SN30 Pro USB, em `support.8bitdo.com` e `8bitdo.com`;
- `support.8bitdo.com/firmware-updater.html` — a ferramenta, os sistemas
  suportados e a ressalva sobre modelos antigos;
- o índice de firmware do suporte da 8BitDo;
- `github.com/fwupd/8bitdo-firmware` — espelho dos `readme` originais da 8BitDo,
  congelado em 2020;
- Nintendo Support: como atualizar o firmware do controle, o artigo de falha de
  atualização, e o histórico de atualizações de sistema.

**Da comunidade:**

- `github.com/dekuNukem/Nintendo_Switch_Reverse_Engineering` — o layout da
  resposta ao subcomando `0x02`. **É a mesma fonte que o driver credita, e ela
  já foi refutada nesta casa em pelo menos um número**;
- a wiki do `fwupd` sobre controles 8BitDo;
- `linux-hardware.org` para `2dc8:6001`, `2dc8:6002` e `2dc8:6006`;
- o *gamepad-cheatsheet* do SN30 Pro+, única fonte achada com a tabela
  cabo/rádio completa;
- o manual comunitário da geração anterior (`clach04/8bitdo_manual`), para o
  modo teclado que deixou de existir;
- relatos de leitura e gravação de firmware 8BitDo no Linux por terceiros e o
  relato do atualizador web com WebUSB.

**Páginas desta casa:** `docs/usage/troubleshooting-8bitdo.md`,
`docs/protocol/externos-referencia-canonica.md`,
`docs/protocol/driver-hid-nintendo-por-dentro.md`,
`docs/data/mapa-controles.csv`.

---

## Nota de 11/08/2026 — duas medições ao vivo que fecham perguntas abertas

### O `fwupd` recusa o aparelho, e está registrado no journal

Com o SN30 Pro em **D-input** (`2dc8:6001`, o modo que o quirk embutido do
`fwupd` reconhece) e no cabo, `fwupdmgr get-devices` devolve **só** placa-mãe,
GPU, CPU, NVMe e TPM. O controle não aparece — nem como dispositivo ignorado.

O journal diz por quê:

```
fwupd[41114]: FuEngine failed to add device usb:01:00:03: unexpected device response
```

O par `USB\VID_2DC8&PID_6001` **está** no quirk embutido
(`/usr/share/fwupd/quirks.d/builtin.quirk.gz`), com `Plugin = ebitdo` e
`Flags = will-disappear`. O plugin está ligado. Ainda assim o daemon mandou o
comando de identificação do protocolo e o aparelho respondeu outra coisa.

**Leitura:** em D-input normal o controle não fala o protocolo de atualização.
Ele só falaria em **modo bootloader** — o estado em que fica esperando ser
regravado, e é onde se inutiliza um aparelho. O `will-disappear` do quirk é
coerente com isso: o `fwupd` espera que o dispositivo suma e reapareça durante a
gravação.

**Consequência prática:** ler a versão de firmware do 8BitDo pelo Linux, sem
risco, **não é possível hoje**. Isso deixa de ser "talvez dê" e passa a ser um
não com endereço.

### O remapeamento persistente não existe para este modelo

Medição dela, no aparelho: *"8bitdo ultimate software não funciona nem a pau no
meu controle"*.

Bate com o que se sabe da linha: o **Ultimate Software** atende os aparelhos
novos (Ultimate, Pro 2, e parte dos Pro+). O **SN30 Pro** de 2018 era servido
pela ferramenta antiga, que **atualiza firmware e não remapeia**.

**Consequência para o pedido dela** — trocar o botão do coração pelo da estrela
de modo que valha em qualquer console, inclusive no Switch: **não há caminho por
software.** O mapeamento vive no firmware, e a 8BitDo não expôs remapeamento
para este modelo.

O que sobra, e cada um com o seu alcance:

| caminho | alcance | risco |
|---|---|---|
| `hwdb` do kernel (`/etc/udev/hwdb.d/`) | só esta máquina, mas **abaixo da Steam** | nenhum; é um arquivo, e apagar reverte |
| Steam Input | só dentro dos jogos, configurado por jogo | nenhum |
| firmware | resolveria em todo console | **alto**, e não há ferramenta que o faça neste modelo |

Os dois botões, para quem for escrever a regra (medido no fonte do driver,
`assets/dkms/hid-nintendo/hid-nintendo.c:430-431`, `:458`, `:481`):

- **estrela** = `JC_BTN_HOME` -> `BTN_MODE`
- **coração** = `JC_BTN_CAP` -> `BTN_Z`

**Não medido:** qual botão físico o aparelho **dela** associa a cada bit. A
leitura por `evdev` foi tentada em 11/08 e não capturou nada — ficou pendente,
e é o que decide se o mapeamento no Linux já está igual ao do Switch ou
invertido.

### Os dois botões do meio, medidos — e não há o que trocar

Ela perguntou se dava para trocar, por firmware, o botão do coração pelo da
estrela, *"pra ele sempre funcionar nesse sentido"*. Medido em 11/08/2026, no
aparelho dela, pelo cabo e em modo Switch (`scripts/ver_botao.py`):

| botão no plástico | evdev | code | o que faz |
|---|---|---|---|
| **coração** | `BTN_MODE` | 316 | home |
| **estrela** | `BTN_Z` | 309 | captura (print) |

**É o mesmo comportamento que ela relata no Switch** — *"o botão coração traz o
input de home e o botão estrela de print"*. Console e Linux concordam; não há
divergência de plataforma.

**Mas o pedido dela não era corrigir divergência — era INVERTER os dois**, de
modo que a **estrela** acione o home e o coração acione o print, e que isso
valesse **também no Switch**. Registrado com todas as letras porque quem escreve
isto entendeu errado na primeira leitura e chegou a anotar "não há o que
corrigir": não há **defeito**, e há um **pedido**, que são coisas diferentes.

**No Switch: não dá.** O mapeamento vive no firmware, e o SN30 Pro de 2018 não
tem remapeamento persistente — medido por ela: *"8bitdo ultimate software não
funciona nem a pau no meu controle"*. O Ultimate Software atende os aparelhos
novos (Ultimate, Pro 2, parte dos Pro+); este modelo era servido pela ferramenta
antiga, que **atualiza firmware e não remapeia**. Some-se a isso que o `fwupd`
recusa o aparelho fora do modo bootloader (medido acima), e o caminho de
firmware fecha por dois lados.

**No Linux dá — mas NÃO por `hwdb`, e isto foi medido antes de escrever o
arquivo.** O `hwdb` remapeia por `KEYBOARD_KEY_<scancode>`, e este aparelho não
tem scancode: o `hid-nintendo` chama `input_report_key` direto
(`assets/dkms/hid-nintendo/hid-nintendo.c:1945`), e o dispositivo declara apenas
`EV_SYN`, `EV_KEY`, `EV_ABS` e `EV_FF` — **sem `EV_MSC`**. Um arquivo em
`/etc/udev/hwdb.d/` seria ignorado em silêncio, e quem o escrevesse acharia que
errou a sintaxe.

**O que funciona é o `input-remapper`**, que intercepta no nível do `evdev` em
vez do scancode — e ele já está instalado nesta máquina, ativo em três outros
dispositivos dela. É por interface: escolher o 8BitDo, apertar o botão, dizer o
que ele passa a emitir, salvar. A troca é `BTN_MODE` <-> `BTN_Z`, e desfazer é
apagar o preset.

**Cuidado ao escolher o dispositivo:** os dois controles compartilham VID/PID
(`057e:2009`). O que separa é o `bcdDevice` — `0200` no 8BitDo, `0210` no Pro
genuíno — ou o endereço, cuja OUI `e0:f6:b5` é da Nintendo. Na lista do
`input-remapper` os dois aparecem como "Pro Controller"; o do cabo, hoje, é o
clone.

O que **nada** disto resolve: o comportamento no console, que continua como o
plástico manda.

Fica registrado porque a pergunta foi feita e porque o caminho até a resposta
custou quatro tentativas. **O defeito não era do aparelho nem da captura: era
de sincronia.** As três primeiras tentativas rodaram um leitor por 60 a 180
segundos e imprimiam "aperte agora" — mas quem opera o terminal só lê essa
mensagem *depois* que o comando termina. Zero eventos, três vezes, e nenhuma
conclusão possível.

A cura foi inverter quem dá a partida: `scripts/ver_botao.py` é feito para ELA
rodar, com o retorno na própria tela no instante do aperto. A quarta tentativa
levou dez segundos. **A lição vale além deste caso:** medição que depende de a
pessoa agir dentro de uma janela que ela não enxerga não é medição — é sorte.
