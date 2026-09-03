# O report de ENTRADA do DualSense — os três layouts, byte a byte

Escrito em 03/09/2026, num levantamento em fonte externa. **Nada aqui foi
enviado a aparelho nenhum, e nada aqui foi medido nesta bancada** — salvo onde
a linha diz o contrário e nomeia a data.

Ele existe porque o mapa de canais tinha uma lacuna estreita e cara: as linhas
de `entrada.*` e `gatilho.analogico` sabiam **por onde** o dado chega (`evdev`)
e não sabiam **em que byte**. Enquanto o produto lê pelo nó de evdev isso não
custa nada; no dia em que alguém precisa ler `hidraw` cru — porque o
`EVIOCGRAB` do co-op silencia o evdev físico para leitor externo — custa a
tarde inteira.

> **A regra de leitura desta página.** Onde ela diz *corpo*, o offset é
> relativo ao **começo do corpo do report**, que não é o começo do buffer. Onde
> ela diz *absoluto*, é o índice no buffer que o `hidraw` entrega, contando o
> byte de id. As duas formas aparecem porque as fontes usam as duas, e
> confundi-las é o erro mais comum deste assunto.

---

## 1. São TRÊS reports de entrada, não dois

| report | transporte | tamanho | corpo começa em | assinatura |
|---|---|---|---|---|
| `0x01` | cabo | 64 B | `data[1]` | — |
| `0x01` | **rádio, mínimo** | **10 B** | `data[1]` | — |
| `0x31` | rádio, estendido | 78 B | `data[2]` | CRC-32 nos 4 últimos bytes, semente `0xA1` |

O `0x01` de rádio é o que quase todo levantamento esquece. O driver desta
máquina o menciona e **não o decodifica** —
`assets/dkms/hid-playstation/hid-playstation.c:1574-1578`, no comentário
*«Bluetooth uses a minimal HID report for reportID 1 and reports the full
report using reportID 49»*. Ele é o layout de compatibilidade com DualShock 4,
o que o aparelho publica antes de alguém pedir o modo estendido.

**Por que ele importa mesmo sem o driver ler:** quem abrir `hidraw` por rádio e
ancorar pelo id vai receber os dois, e o `0x01` de rádio **não tem o mesmo
arranjo** do `0x01` de cabo. Ver a §4.

---

## 2. O corpo do `0x01` de cabo e do `0x31` de rádio — é o MESMO corpo

A única diferença entre os dois é onde o corpo começa: `data[1]` no cabo,
`data[2]` no rádio (`hid-playstation.c:1579-1592`).

| corpo | absoluto (cabo) | absoluto (`0x31`) | campo | quem nomeia |
|---|---|---|---|---|
| 0 | 1 | 2 | LX | todos |
| 1 | 2 | 3 | LY | todos |
| 2 | 3 | 4 | RX | todos |
| 3 | 4 | 5 | RY | todos |
| 4 | 5 | 6 | **L2 analógico** | todos |
| 5 | 6 | 7 | **R2 analógico** | todos |
| 6 | 7 | 8 | contador de quadro | todos |
| 7-10 | 8-11 | 9-12 | **`buttons[4]`** | todos |
| 11-14 | 12-15 | 13-16 | `reserved[4]` no driver; **contador de pacote uint32 LE** no SDL | divergem no NOME |
| 15-20 | 16-21 | 17-22 | giroscópio (3 × int16 LE) | driver e SDL |
| 21-26 | 22-27 | 23-28 | acelerômetro (3 × int16 LE) | driver e SDL |
| 27-30 | 28-31 | 29-32 | `sensor_timestamp` (uint32 LE, unidade 0,33 µs) | todos |
| 31 | 32 | 33 | `reserved2` no driver; `ucSensorTemp` no SDL | divergem no NOME |
| 32-39 | 33-40 | 34-41 | dois pontos de toque, 4 B cada | todos |
| 40-51 | 41-52 | 42-53 | `reserved3[12]` no driver — ver a §5 | ninguém nomeia inteiro |
| 52-54 | 53-55 | 54-56 | `status[3]`: bateria, jack, terceiro | driver |

O driver fecha a conta com um `static_assert` de que o struct tem exatamente
`DS_INPUT_REPORT_USB_SIZE - 1` = 63 bytes (`hid-playstation.c:317`). Os offsets
acima fecham 63 sem buraco e sem sobreposição.

### O mapa de bits dos quatro bytes de botão

Isto é o que faltava ao mapa: o `entrada.botoes@dualsense` tinha o **offset**
medido nesta bancada em 15/08/2026 (`buttons[4]` = `08 00 00 00` em 8 de 8 nós)
e dizia, na própria ressalva, que **qual bit é qual botão** não estava medido.
Continua não estando — mas agora está **escrito**, com cinco fontes que
concordam bit a bit.

| byte | bit | botão |
|---|---|---|
| `buttons[0]` | 3..0 | **hat**, como valor: 0 N, 1 NE, 2 L, 3 SE, 4 S, 5 SO, 6 O, 7 NO, **8 = centro** |
| `buttons[0]` | 4 | quadrado |
| `buttons[0]` | 5 | cruz |
| `buttons[0]` | 6 | círculo |
| `buttons[0]` | 7 | triângulo |
| `buttons[1]` | 0 | L1 |
| `buttons[1]` | 1 | R1 |
| `buttons[1]` | 2 | L2 (digital) |
| `buttons[1]` | 3 | R2 (digital) |
| `buttons[1]` | 4 | Create |
| `buttons[1]` | 5 | Options |
| `buttons[1]` | 6 | L3 |
| `buttons[1]` | 7 | R3 |
| `buttons[2]` | 0 | PS |
| `buttons[2]` | 1 | touchpad |
| `buttons[2]` | 2 | mudo do microfone |
| `buttons[3]` | — | ninguém decodifica |

O hat é **valor, não bitmap** — `8` é o repouso, e um valor fora de 0..7 é
tratado como centro (`hid-playstation.c:1605-1609`). Quem ler o nibble como
quatro bits vê o D-pad neutro como "cima+baixo apertados".

**O acréscimo do DualSense Edge, e ele vem de UMA fonte só.** O `pydualsense`,
sob `if self.is_edge`, lê também `buttons[2]` bit4 = L4, bit5 = R4, bit6 = L5 e
bit7 = R5. O driver desta máquina define **três** máscaras para esse byte
(`hid-playstation.c:170-172`) e nenhuma delas alcança os bits 4-7 — de modo que
**as costas de um Edge não chegam por evdev nesta máquina**. É lacuna do
driver, não do aparelho, e ninguém desta casa tem um Edge para conferir.

---

## 3. As fontes, e o que cada uma acrescenta

| fonte | o que ela é | o que ela acrescenta aqui |
|---|---|---|
| `hid-playstation.c` desta árvore | o driver **compilado nesta máquina** | é a régua; vence as outras onde houver disputa |
| `libsdl-org/SDL` `f443c429` `src/joystick/hidapi/SDL_hidapi_ps5.c:72-133` | a camada que os jogos usam | comenta o offset de **cada** campo; nomeia dois campos que o driver chama `reserved` |
| `Ohjurot/DualSense-Windows` `a78fbab1` `.../DS5_Input.cpp` | leitor em C++ | é o **único** que nomeia o feedback de gatilho — e erra o vizinho (§5) |
| `flok/pydualsense` `01445f5e` `pydualsense/pydualsense.py:286-332` | a biblioteca que **este** projeto usa | os bits do Edge; e o `[1:]` que alinha rádio com cabo |
| `BadMagic100/DualSenseAPI` `a121e53e` `.../DualSenseInputState.cs:26-54` | leitor em C# | guarda os índices **alternativos** do `0x01` de rádio |
| `bentiss/hid-tools` `hidtools/device/sony_gamepad.py:3361-3390` | a suíte de regressão do **kernel** | monta o `0x31` de 78 B na mesma ordem de campo |
| `nondebug.github.io/dualsense` | explorador de descritor HID | os absolutos do `0x01`, dos dois lados |

As cinco primeiras foram lidas verbatim em 03/09/2026 e conferidas campo a
campo contra o driver. **Nenhuma linha de código foi copiada para esta árvore:
o que atravessou foi número, offset e formato de comando.**

---

## 4. O `0x01` MÍNIMO de rádio — 10 bytes, e a ordem MUDA

Nove bytes de corpo, ancorados em `data[1]`:

| corpo | absoluto | campo |
|---|---|---|
| 0-3 | 1-4 | LX, LY, RX, RY |
| 4 | 5 | `buttons[0]` — hat e face |
| 5 | 6 | `buttons[1]` — L1..R3 |
| 6 | 7 | `buttons[2]`, **só os bits 0 e 1** (PS, touchpad); o resto do byte é contador |
| 7 | 8 | **L2 analógico** |
| 8 | 9 | **R2 analógico** |

**Os gatilhos vão para o FIM.** No cabo eles estão antes dos botões; aqui,
depois. Quem levar o offset de um para o outro lê um byte de bits achando que lê
curso de gatilho — e o valor não parece lixo, porque passeia entre 0 e 255
conforme os dedos.

**O mudo do microfone não viaja neste report.** O SDL lê apenas `& 0x03` do
terceiro byte (`SDL_hidapi_ps5.c:1236`); o `DualSenseAPI` diz, em comentário,
que o mudo *«not supported on the broken BT protocol»*. Três fontes concordam
com o arranjo inteiro: SDL (`:72-81`, com o campo chamado
`rgucButtonsHatAndCounter[3]`, e `:1618-1620`, onde ele é escolhido por
`size == 10`), `nondebug` e `DualSenseAPI` (`:27-54`, nos índices alternativos).

**O que os sticks têm de especial:** eles são o **único bloco que não se move**
entre os dois reports de rádio. Botões e gatilhos trocam de lugar; os quatro
eixos ficam no corpo 0..3 nos três reports. Quem escrever leitor de `hidraw`
cru pode ancorar os sticks primeiro e decidir o resto pelo tamanho do quadro.

---

## 5. O feedback de gatilho — endereço de fonte única, e ela erra o vizinho

A canônica já dizia, em *«Leitura de estado — recurso que ninguém usa aqui»*,
que o **nibble alto** de um byte de status por gatilho conta o que o gatilho
está sentindo. Ela nunca disse **onde**.

Uma fonte, e uma só, dá o offset: `DualSense-Windows` `.../DS5_Input.cpp:79-80`
põe o feedback do gatilho **esquerdo** no corpo **42** (`0x2A`) e o do
**direito** no corpo **41** (`0x29`). Os dois caem dentro do `reserved3[12]` do
driver (`hid-playstation.c:312`) e dentro do `rgucUnknown1[8]` do SDL
(`SDL_hidapi_ps5.c:127`) — nenhum dos dois **nomeia** o campo, então não há
segunda testemunha.

**E a fonte erra dois campos ao lado.** O mesmo arquivo, em `:56` e `:59`,
troca acelerômetro por giroscópio: põe o acelerômetro no corpo 15 e o giro no
21, quando o driver (`:304-305`) e o SDL (`:94-99`) concordam no contrário.
Some-se que a ordem esquerda-antes-de-direita **se inverte** aqui, ao contrário
de todo o resto do report — que é exatamente o que um erro de transcrição
produz.

**Grau: `incerto`.** O ensaio que resolve os dois pontos de uma vez custa dez
segundos: aplicar um efeito num gatilho, ler o corpo 41 e o 42, soltar. Se o
campo existe, e qual é qual, saem juntos.

---

## 6. A calibração dos sticks — a linha que estava muda

O mapa carregava `entrada.stick.calibracao@dualsense` com `existe =
desconhecido` e **as duas células de transporte vazias**, e a nota explicava
por quê: as duas coisas que parecem responder não respondem. O feature `0x05`
de 41 bytes é calibração da **IMU** (`hid-playstation.c:149-150` e
`:1149-1192`); o `absinfo` do evdev é a faixa **declarada pelo kernel**, não a
calibração daquela unidade.

**As duas continuam não respondendo. Existe uma terceira, e ela responde.**

### Ler — e é leitura pura

```
SET_FEATURE 0x80  payload [12, 2]
GET_FEATURE 0x81 -> 64 bytes
    buf[0] == 0x81      (eco do id)
    buf[1] == 12        (base)
    buf[2] == 2  ou  4  (num)
    buf[3] == 2         (o carimbo de "isto é dado, não erro")
    buf[4..27] = DOZE uint16 LITTLE-ENDIAN
```

Se qualquer um dos quatro testes falhar, a fonte **descarta a leitura inteira**
em vez de parsear.

**É a mesma forma `[base, num]` do comando que esta bancada já mediu nos dois
transportes** para achar a cor do plástico — `[1, 19]` devolve o serial de 17
caracteres em `buf[4..20]`, com o mesmo `buf[3] == 2`. Muda o par de números,
não o mecanismo. Isso é o que sustenta a expectativa de que o `[12, 2]`
responda aqui; **não é medição**, e a distinção é o ponto.

### Os doze valores, e a ordem é do arquivo

`["LL", "LT", "RL", "RT", "LR", "LB", "RR", "RB", "LX", "LY", "RX", "RY"]`

| índice | valor | o que é |
|---|---|---|
| 0, 4 | `LL`, `LR` | stick **esquerdo**, extremos de curso em X |
| 1, 5 | `LT`, `LB` | stick **esquerdo**, extremos de curso em Y |
| 2, 6 | `RL`, `RR` | stick **direito**, extremos de curso em X |
| 3, 7 | `RT`, `RB` | stick **direito**, extremos de curso em Y |
| 8, 9 | `LX`, `LY` | **centro** do stick esquerdo |
| 10, 11 | `RX`, `RY` | **centro** do stick direito |

Que a primeira letra seja o **stick** e não uma direção não é leitura minha: o
próprio arquivo agrupa `left: {suffixes: ['LL','LT','LR','LB'], axisX: 'LX',
axisY: 'LY'}` e `right: {suffixes: ['RL','RT','RR','RB'], axisX: 'RX', axisY:
'RY'}` (`js/modals/finetune-modal.js:9-28`).

**O achado que mais ensina é o tipo.** São `uint16` num aparelho que publica
stick de **8 bits**. A calibração vive numa resolução **maior** que a do report
de entrada — o byte 0..255 que este projeto lê já é produto dela. É a
explicação candidata para o que esta bancada mediu em 15/08/2026 e não soube
explicar: o centro de repouso não é 128 em unidade nenhuma, e passeia 1 LSB em
escala de minutos.

### Calibrar — e isto NÃO é leitura

O ciclo mora em `0x82` (comando) / `0x83` (confirmação). Cada passo devolve um
`uint32` **big-endian** que tem de bater exato:

| passo | `SET 0x82` | `GET 0x83` tem de ser |
|---|---|---|
| centro, começar | `[1, 1, 1]` | `0x83010101` |
| centro, amostrar | `[3, 1, 1]` | `0x83010101` |
| centro, fechar e **gravar** | `[2, 1, 1]` | `0x83010102` |
| curso, começar | `[1, 1, 2]` | `0x83010201` |
| curso, fechar e **gravar** | `[2, 1, 2]` | `0x83010202` |

E os doze podem ser escritos à mão: `SET_FEATURE 0x80` com
`[12, 1, lo, hi, lo, hi, …]` — vinte e seis bytes.

### A família de fábrica inteira, e por que ela não é de agente

O `0x80`/`0x81` é **uma família**, e a metade dela mexe no aparelho:

| payload | o que faz |
|---|---|
| `[1, 1]` | **reseta o controle** |
| `[3, 1]` | tranca a memória não-volátil |
| `[3, 2, 101, 50, 64, 12]` | **destrava** a memória não-volátil — a senha está em claro na fonte |
| `[3, 3]` | status da trava (`0x03030200` destravado, `0x03030201` trancado, `0x15010100` esperando reinício) |
| `[9, 2]` | devolve o endereço de rádio da unidade em `buf[4..9]` |
| `[1, 19]` | o serial de 17 caracteres — o caminho da cor, medido nesta bancada em 27/08/2026 |
| `[12, 2]` | **lê** os doze de calibração |
| `[12, 1, …]` | **grava** os doze |

O autor do levantamento externo avisa, com estas palavras, que *«there are
chances that it may brick your controller»*, e que o firmware muda com
frequência. **Ler é `[12, 2]`; qualquer outro `num` sai da leitura.** A metade
de escrita não entra em ensaio nenhum sem a palavra dela.

**Um brinde do mesmo levantamento, e é conferência de graça:** o `[9, 2]`
devolve o endereço de rádio pelo **mesmo** par `0x80`/`0x81` que o feature
`0x09` já devolve por outro caminho. Duas rotas para o mesmo dado é régua
independente — o tipo de coisa que esta casa usa para casar unidade com nó.

---

## 7. O que a internet NÃO sabe

Escrito para que ninguém repita a busca:

1. **Nenhuma fonte pública documenta o `buttons[3]`.** Quatro bytes de botão, e
   o quarto é ignorado por todos os cinco leitores lidos. Ou é reserva de
   verdade, ou carrega algo que só um aparelho responde.
2. **O feedback de gatilho tem endereço de fonte única** (§5), e a mesma fonte
   erra o campo vizinho. É o candidato número um a ensaio de bancada deste tema.
3. **Ninguém publicou os doze valores de calibração de uma unidade concreta**,
   nem a faixa que eles ocupam. Sabe-se o formato, não a grandeza.
4. **Se o `[12, 2]` responde por RÁDIO, ninguém escreveu.** A ferramenta de
   comunidade é WebHID sobre USB e não computa CRC nenhum. Que responda por
   rádio é extrapolação desta casa, apoiada na medição de 27/08/2026 sobre o
   mesmo par de reports com outro par de números.
5. **O `reserved3[12]` não é descrito inteiro por ninguém.** Doze bytes, e o
   máximo que se acha são dois nomes (o feedback de gatilho) e um `rgucTimer2`
   uint32 nos quatro últimos, no SDL (`:128`).
6. **A escala real do stick não está publicada.** O `uint16` da calibração diz
   que existe resolução acima de 8 bits; **quanto** acima, ninguém disse.

---

## 8. A armadilha que quase virou contradição

O SDL guarda **dois** layouts para o report estendido: `PS5StatePacket_t`, que
bate com o driver, e `PS5StatePacketAlt_t`, em que **a bateria está no corpo 29
e o touchpad no 31**. Quem ler o SDL de cima para baixo e pegar o segundo
conclui que ele contradiz o Linux.

**Não contradiz.** O `alt` só é escolhido quando `use_alternate_report` está
ligado, e ele só liga para **clones de terceiros** — Nacon Revolution 5 Pro,
Razer Wolverine V2 Pro, Razer Kitsune, Razer Raiju V3 Pro
(`SDL_hidapi_ps5.c:522`, `:537`, `:545`). Para um DualSense da Sony, o SDL usa
o layout que bate com o driver, campo a campo.

Fica registrado porque a contradição é convincente e falsa — e este arquivo
existe, em parte, para que a próxima pessoa não gaste a manhã nela.
