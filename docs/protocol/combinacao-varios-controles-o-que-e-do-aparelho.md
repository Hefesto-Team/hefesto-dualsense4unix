# Vários controles na mesa — o que é canal do aparelho e o que é do host

> Escrito em 03/09/2026, na frente **COMBINAÇÃO** da leva que ela encomendou:
> *"lançar novo workflow pra agentes procurarem no GitHub tais canais ou tais
> id (…) como é só informação eles trouxeram e me ajudaram no mapa do
> controle"*.
>
> **Nada aqui foi ao aparelho.** Esta página traz FATO LIDO — em fonte de
> driver, em fonte de biblioteca pública e em relato de terceiro — com o
> endereço de cada afirmação. O que foi medido nesta casa está no
> `docs/data/mapa-controles.csv` e nos ensaios; o que está aqui é o que a
> busca externa acrescentou, e o grau de cada linha diz de onde veio.

---

## 1. A decisão que vem antes de caçar

A pergunta "dois controles na mesa continuam funcionando?" **não tem
`report_id`**. Ela não é um canal do DualSense: o aparelho não sabe que existe
outro aparelho. Quem sabe é o host — o controlador USB, o adaptador de rádio, o
BlueZ, o kernel e o nosso daemon.

Isso não fecha a busca; **desloca** o alvo. Debaixo de cada linha de combinação
há um canal por aparelho, e ESSE tem endereço:

| a pergunta da linha | é canal do aparelho? | o que TEM endereço |
| --- | --- | --- |
| a entrada dos dois continua chegando | **não** | o report de entrada de cada um, e a promoção do rádio para `0x31` |
| a saída dos dois sobrevive | **não** | o envelope do report de saída de cada um |
| a taxa de cada um, medida junta | **não** — e ver a §4 | nada no DualSense. O DS4 tem. |
| dois no rádio ao mesmo tempo | **não** | o mesmo envelope `0x31` |
| três/quatro na mesa | **não** | os mesmos reports de entrada |
| rumble simultâneo | **não** | os dois bytes de motor de cada um |
| o número de jogador se mantém | **não** — o número é do host | os 5 LEDs brancos que o MOSTRAM |

**Em todas as sete, a simultaneidade é do host.** É por isso que este documento
existe: para que a próxima pessoa não gaste um dia procurando um `report_id`
de "dois na mesa".

---

## 2. O envelope de saída, e as TRÊS implementações que concordam

O report de saída do DualSense é o mesmo bloco `common` de **47 bytes** nos dois
transportes; o que muda é o cabeçalho e o rodapé.

| | cabo | rádio |
| --- | --- | --- |
| `report[0]` | `0x02` | `0x31` |
| `report[1]` | *(já é `common[0]`)* | sequência no nibble alto, tag no baixo |
| `report[2]` | `common[1]` | `0x10` — tag mágico, obrigatório |
| início do `common` | `report[1]` | `report[3]` |
| motor DIREITO (`common[2]`) | `report[3]` | `report[5]` |
| motor ESQUERDO (`common[3]`) | `report[4]` | `report[6]` |
| LEDs de jogador (`common[43]`) | `report[44]` | `report[46]` |
| lightbar R/G/B (`common[44..46]`) | `report[45..47]` | `report[47..49]` |
| rodapé | *(sem CRC)* | CRC32 little-endian em `report[74..77]` |

**Quem afirma isto, e são fontes independentes:**

1. **`hid-playstation.c`**, o driver compilado nesta máquina
   (`assets/dkms/hid-playstation/hid-playstation.c`): `struct
   dualsense_output_report_common` com `static_assert(… == 47)`;
   `dualsense_output_report_bt` = `report_id` + `seq_tag` + `tag` + `common` +
   24 reservados + `crc32`; `dualsense_output_report_usb` = `report_id` +
   `common` + 15 reservados. O tag mágico é `#define DS_OUTPUT_TAG 0x10`, com o
   comentário do próprio driver dizendo *"Magic value required in tag field of
   Bluetooth output report"*. A semente do CRC de saída é
   `PS_OUTPUT_CRC32_SEED 0xA2`.
2. **SDL3**, `src/joystick/hidapi/SDL_hidapi_ps5.c`, no caminho que envia
   efeitos: em Bluetooth escreve `0x31`, depois *"Tag and sequence"*, depois
   `0x10` com o comentário *"Magic value"*, e usa **offset 3** para o corpo;
   em USB escreve `0x02` e usa **offset 1**. O CRC ele calcula prefixando o byte
   `0xA2` — o comentário diz *"hidp header is part of the CRC calculation"*.
3. **Esta casa**, `src/hefesto_dualsense4unix/core/ds_output_report.py`
   (`build_bt_report`), que monta exatamente esse envelope — e o aparelho
   obedeceu, medido em 11 e 12/08/2026.

Três implementações escritas por gente diferente chegando ao mesmo byte é o
grau mais alto que uma leitura pode ter sem tocar no aparelho.

### 2.1 A quarta implementação DISCORDA — e é a biblioteca que usamos

`pydualsense` (`pydualsense/pydualsense.py`, `prepareReport`) monta o report BT
com **um byte a menos de cabeçalho**: escreve `0x31` em `[0]`, a constante
`0x02` em `[1]`, e começa o `common` em `[2]`. O resultado é que, na visão dela,
o motor direito cai em `report[4]` e os LEDs de jogador em `report[45]` — um
byte antes de onde o kernel, o SDL3 e esta casa os põem.

**Quem está certo:** o kernel, o SDL3 e nós. A prova não é aritmética, é
bancada: esta casa envia pelo `build_bt_report` (`common` em `[3]`, tag `0x10`)
e o aparelho obedeceu no rádio, com o olho dela, em 11 e 12/08/2026. O caminho
BT da `pydualsense` **não é o que este produto usa** — o `ds_output_report.py`
existe precisamente por isso.

O lado USB da `pydualsense` concorda com todo mundo (motor direito em
`report[3]`, LEDs de jogador em `report[44]`), então a divergência é só do BT.

> **Fica registrado como armadilha:** quem for conferir um offset de BT contra a
> `pydualsense` vai achar que o mapa desta casa está deslocado. Não está.

### 2.2 Um desacordo de TAMANHO que não é defeito

São **três tamanhos** para o mesmo report USB de saída, e os três funcionam: o
kernel emite **63 bytes** (`DS_OUTPUT_REPORT_USB_SIZE`), o SDL3 emite **48**, e
esta casa emite **64** (`USB_REPORT_LEN` em `core/ds_output_report.py`).
`1 + 47 = 48` é o mínimo que carrega o `common` inteiro; o resto é enchimento.
Anotado para que ninguém trate a diferença como bug — e para que ninguém
"corrija" o nosso 64 achando que é erro.

---

## 3. A entrada, e a promoção que é POR APARELHO

No cabo o DualSense emite `0x01` de 64 bytes desde o enumerate, sempre completo.

No rádio, **não**. Ele começa emitindo um `0x01` mínimo (sem movimento e sem
touch) e só passa a emitir o `0x31` de 78 bytes depois que o host **toca nele
uma vez**. O SDL3 documenta os gatilhos em comentário, e são três famílias:

- ler qualquer feature report — `0x05` (calibração), `0x09` (serial) ou `0x20`
  (firmware): *"This will also enable enhanced reports over Bluetooth"*;
- enviar qualquer report de saída, **mesmo inválido**: *"We can't even send an
  invalid effects packet, or it will put the controller in enhanced mode"*;
- e a promoção **é de mão única** — *"enhanced mode is a one-way ticket"*. Só o
  desligamento do aparelho desfaz.

O `hid-playstation` faz o mesmo sem comentar: `dualsense_get_calibration_data()`
lê o feature `0x05` durante o `create`.

**Por que isto pertence à família COMBINAÇÃO:** a promoção é **estado do
aparelho, por aparelho**. Um controle promovido não promove o vizinho. Numa mesa
de quatro, quatro promoções acontecem — e se uma falhar, aquele controle fica no
`0x01` mínimo e o sintoma que ela vê é *"esse aqui não tem giroscópio"*, não
*"esse aqui não conecta"*.

### 3.1 O CRC de entrada é o pedágio do rádio — e ele DESCARTA o quadro

O `0x31` de entrada carrega CRC32 nos últimos 4 bytes (`report[74..77]`,
little-endian, semente `PS_INPUT_CRC32_SEED 0xA1` sobre `report[0..73]`). Se ele
não bater, o `hid-playstation` **devolve `-EILSEQ` e descarta o quadro inteiro**
— nenhum evento evdev sai — e escreve `DualSense input CRC's check failed` no
dmesg (`hid-playstation.c`, no tratador de entrada).

O cabo não tem esse caminho: lá o quadro é aceito pelo tamanho e mais nada.

**É a assimetria que importa na mesa cheia.** Com o ar congestionado, o rádio
não avisa que está devagar: ele perde quadro em silêncio, e a única testemunha é
o dmesg. Esta casa mediu **0 falhas de CRC em 35.351 quadros** (E-3, 15/08) com
quatro controles na mesa — o que é um resultado, não uma ausência de risco: diz
que a mesa dela, naquela janela, não chegou perto do limite.

---

## 4. O canal de TAXA que o DualSense NÃO tem — e o DS4 tem

Este é o achado que mais economiza tempo de quem vier depois.

**No DualShock 4 existe um canal de taxa, e ele é do host para o aparelho.** No
report de saída BT `0x11`, os **6 bits baixos de `hw_control` (`report[1]`)**
mandam o intervalo em que o controle relata:

```
0x00 - 1 ms      0x02 - 2 ms      0x3E - 62 ms      0x3F - desligado
```

O `hid-playstation` escreve 4 ms ali no `create`
(`DS4_BT_DEFAULT_POLL_INTERVAL_MS`), e o comentário do próprio driver diz o
motivo: *"Default to 4ms poll interval, which is same as USB (not adjustable)"*.

**No DualSense não existe campo equivalente.** O `0x31` de saída é
`report_id`, `seq_tag`, `tag`, 47 bytes de `common`, 24 reservados e o CRC — e
nenhum dos 47 é intervalo. A `struct dualsense` do driver não tem
`bt_poll_interval`; a `struct dualshock4` tem.

**O que isso responde, e é uma resposta de verdade:** na mesa cheia **não há
botão no aparelho** para trocar taxa por espaço no ar. Não adianta procurar. O
único freio disponível é do host — nesta casa, o cap de
`core/physical_report_reader.py`.

De quebra, o comentário do DS4 é uma **confirmação independente** do que esta
casa mediu por `readlink`/`lsusb` em 15/08: 4 ms no cabo, ou seja 250 Hz, e não
ajustável.

### 4.1 A folclore de taxa está errada, e a fonte que a derruba é o SDL3

Circula em sites de "polling rate test" que o DualSense faz *1000 Hz no USB e
250 Hz no Bluetooth*. **Os dois números estão trocados em relação ao que o
código diz.**

O SDL3, ao declarar a taxa dos sensores do DualSense, escreve o contrário:

- USB: `250.0f`, com o comentário *"Standard DualSense sensor update rate is 250
  Hz over USB"*;
- Bluetooth: `1000.0f`, com o comentário *"Bluetooth sensor update rate appears
  to be 1000 Hz"*;
- e 1000 Hz no USB **só no DualSense Edge**.

O `appears to be` é do SDL, e é honesto: eles inferiram, não mediram. Mas a
DIREÇÃO bate com o que esta casa mediu e ninguém tinha explicado — o rádio
entregando **mais** relatórios que o cabo, e de forma instável (157,8 a 402,9 Hz
pelo laço em Python; ~398-400 Hz pelo relógio do próprio aparelho; 780 Hz num nó
lido sozinho). Os 250,0 Hz cravados do cabo são o teto do `bInterval`; o rádio
não tem teto declarado, e é por isso que ele varia.

> **O que continua aberto:** ninguém — nem o SDL — sabe dizer QUAL é a taxa do
> rádio. O SDL chuta 1000; a régua do relógio do sensor desta casa deu ~400; o
> laço em Python deu de 157 a 403. Isso é ensaio de bancada, não de busca.

---

## 5. O número de jogador: três donos, um mostrador

A pergunta `combinacao.slot_jogador.estabilidade` — *"o número se mantém quando
outro controle entra ou sai?"* — não tem um dono. **Tem três**, e cada um numera
por conta própria:

| quem | como numera | estável quando alguém sai? |
| --- | --- | --- |
| **o kernel** (`hid-playstation`) | `ida_alloc()` — o menor id livre; `ida_free()` na remoção | **não.** O id volta para o poço e o próximo a chegar o pega |
| **o SDL3 / Steam** | índice de jogador próprio, e ele ESCREVE nos LEDs | **não** — e há relato de embaralhamento (§5.2) |
| **o daemon desta casa** | chaveado pelo MAC (`identity.py`, `slot_for`) | **em tese sim** — e medido `parcial` em 12/08 |

**O mostrador é um só:** os cinco LEDs brancos abaixo do touchpad, em
`common[43]` (= `report[44]` no cabo, `report[46]` no rádio), autorizados pelo
bit `0x10` de `valid_flag1` (`common[1]`).

### 5.1 Os cinco valores, confirmados por duas implementações independentes

O kernel e o SDL3 escrevem **os mesmos cinco bytes**, e nenhum dos dois cita o
outro:

| jogador | byte | desenho |
| --- | --- | --- |
| 1 | `0x04` | `--x--` |
| 2 | `0x0A` | `-x-x-` |
| 3 | `0x15` | `x-x-x` |
| 4 | `0x1B` | `xx-xx` |
| 5 | `0x1F` | `xxxxx` |

O kernel monta a tabela com `BIT()` e explica em comentário que centraliza o
número, *"Behavior on the PlayStation 5 console is to center the player id
across the LEDs"*. O SDL3 traz a lista literal, na mesma ordem.

**E o SDL3 acrescenta um bit que o kernel não usa:** ele soma `0x20` ao valor,
com o comentário *"0x1F enables all lights, 0x20 changes instantly instead of
fade"*. Ou seja: **`common[43]` bit `0x20` = aplicar na hora, sem transição**. O
`hid-playstation` nunca liga esse bit, então o LED de jogador escrito pelo
kernel **entra com fade** e o escrito pelo Steam **entra seco**. Informação
nova para esta casa, e ela é visível a olho nu na mesa.

### 5.2 O que os outros relataram sobre a instabilidade do número

- **Ymir (emulador de Saturn), issue #102** — o autor, depurando dois DualSense,
  escreve que *"SDL is getting massively confused when assigning player indices
  (especially when inserting and removing controllers)"*, e acaba fazendo o
  emulador atribuir os números à mão. **Ressalva honesta:** a causa-raiz que ele
  achou é do caminho **rawinput do Windows**, que não roda aqui; o que
  atravessa para o Linux é o formato do problema, não aquele defeito.
- **O SDL escreve o LED por padrão.** O hint
  `SDL_HINT_JOYSTICK_HIDAPI_PS5_PLAYER_LED` nasce **ligado**, e o SDL também
  pinta a lightbar por índice de jogador (azul, vermelho, verde, rosa, laranja,
  turquesa, branco — com o comentário dizendo que a lista é a mesma do
  `hid-sony.c` do kernel). Logo, **com Steam aberto há um terceiro escritor** no
  mesmo byte, e a cor da barra passa a contar o índice DELE.

**A leitura que isso dá para o mapa:** o número que o produto usa é nosso e é
estável por MAC; o número que o APARELHO MOSTRA não é nosso — é de quem escreveu
por último. São duas perguntas, e a linha do mapa estava juntando as duas.

---

## 6. Gente que nem a gente — o que outros mediram sobre a mesa cheia

Nenhum destes é canal, e nenhum destes é medição desta bancada. São relatos de
terceiros, com hardware diferente do dela, e valem pelo que confirmam ou
derrubam.

### 6.1 Dois DualSense no rádio funcionam — confirmação independente

**`bluez/bluez` issue #2163** (06/2026, MediaTek MT7925, BlueZ 5.86, CachyOS).
O relator está caçando outra coisa — um controle de Xbox que fica lento quando
um DualSense está junto —, e no caminho publica a tabela de combinações que ele
testou:

- Xbox no rádio, sozinho: funciona.
- DualSense no rádio, sozinho: funciona.
- **Dois DualSense no rádio, juntos: funcionam.**
- Xbox no CABO + DualSense no rádio: funciona.
- Xbox no rádio + DualSense no rádio: o **Xbox** fica lento; o DualSense não.

E ele conclui, com todas as letras: *"This does not appear to be a Bluetooth
bandwidth limitation because two DualSense controllers can be used
simultaneously without issues."*

**Isto confirma o que esta casa mediu em 12/08** (`comb-dois-no-radio-saida-2235`,
olho dela: os dois obedeceram nas duas rotas) — em outro adaptador, em outra
distribuição, por outra pessoa, dez meses depois. É a confirmação independente
mais forte que esta frente achou.

**E acrescenta o que a nossa medição não tinha:** quando alguém sofre na mesa,
**quem sofre não é o DualSense**. A análise automática do trace anexado ao
issue fechou como `INCONCLUSIVE` — ninguém achou a causa. Fica como observação,
não como mecanismo.

### 6.2 O DualSense atropela vizinho no mesmo adaptador

**`bluez/bluez` issue #922** (08/2024). Dois relatores, dois adaptadores Intel
diferentes, o mesmo formato de queixa: com um DualSense conectado, os outros
dispositivos do mesmo adaptador degradam. Um deles perde os DualShock 4 depois
de ~30 s; o outro perde fones Sony. A hipótese do segundo, dita por ele:
*"The DualSense NEVER goes on standby mode, it's always active"* — enquanto os
fones entram em repouso e cedem o ar.

**Os dois marcadores que eles publicam são o que interessa para nós**, porque
são o que se procura no log quando a mesa dela engasgar:

- `bluetoothd: profiles/input/device.c:hidp_send_message() BT socket write
  error: Resource temporarily unavailable (11)` — a fila de SAÍDA do HID sobre
  BT enchendo;
- `kernel: playstation …: DualSense input CRC's check failed` — o quadro de
  ENTRADA chegando corrompido e sendo descartado (§3.1).

**Grau:** relato de usuário, não medição instrumentada. A hipótese do "nunca
dorme" é dele e **não foi confirmada por trace nenhum** — nem por mim. Vale
como pista para um ensaio de `btmon`, não como fato.

### 6.3 O que NÃO serve, e por que está escrito aqui

- **Fórum Arch #288754 e amigos** — "4 DualSense pararam de funcionar no Linux e
  funcionam no Windows com o mesmo adaptador". Parece da nossa família e **não
  é**: a causa achada no fio é o defeito de PAREAMENTO do BlueZ 5.69, curado
  por downgrade. É falha de conectar, não de dividir o ar.
- **`ublue-os/bazzite` issue #4364** — "polling rate baixa e instável no BT
  desde a build tal". Sem um número medido no issue inteiro; a suspeita do
  relator (o touchpad virando mouse) não foi confirmada. Registrado só para que
  ninguém o persiga de novo achando que tem dado dentro.
- **Sites de "polling rate test"** — os números se contradizem entre si e
  contradizem o descritor USB (§4.1). Não foram usados como fonte.

---

## 7. O que a busca NÃO achou

Escrito porque a lista do que a internet não sabe diz onde só o aparelho
responde — e é o que sobra para ela ensaiar.

1. **Quantos DualSense cabem num adaptador.** Não há uma única medição pública
   com três ou quatro DualSense de rádio ao mesmo tempo, dizendo o que degrada
   primeiro. O melhor que existe é o "dois funcionam" da §6.1. A mesa dela já é
   maior que qualquer relato que eu tenha achado.
2. **Qual é a taxa real do rádio.** Ninguém publicou. O SDL chuta 1000 Hz e diz
   que chuta.
3. **Se o DualSense de fato nunca entra em sniff.** É hipótese de um usuário
   (§6.2). Nenhum trace público sustenta ou derruba.
4. **Se o rumble simultâneo tem custo no aparelho.** Nada encontrado: o
   `dualsense_play_effect` do kernel só aceita `FF_RUMBLE`, divide as magnitudes
   de 16 bits por 256 e agenda o `output_worker` **daquele** aparelho — cada
   controle tem o seu `INIT_WORK`, e **não há fila comum no driver**. O
   afunilamento de N>1, se existe, está no transporte, não no motorista.
5. **O que acontece com a promoção para `0x31` quando dois processos disputam o
   mesmo controle.** A promoção é de mão única e por aparelho (§3); ninguém
   documentou o caso de dois donos.

---

## 8. Onde isto entrou no mapa

As sete linhas de `familia = combinacao` do `dualsense` em
`docs/data/mapa-controles.csv`. Nenhuma ganhou `ate_onde_foi` — **nada foi ao
aparelho nesta leva** —, e todo `de_onde_sei` que esta frente escreveu do zero é
`afirmado-no-doc`.

Régua desta página: `tests/unit/test_mapa_combinacao_enderecos.py`, que
recalcula os offsets a partir do layout declarado do `common` e os confere
contra o CSV. Se alguém deslocar um byte no mapa, ela reprova.
