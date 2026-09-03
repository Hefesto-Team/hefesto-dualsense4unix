# DualSense — o que NÃO é canal do aparelho, e os bytes que o driver não nomeia

> **Levantamento em fonte pública, 03/09/2026. NADA AQUI FOI MEDIDO NESTA
> BANCADA.** Nenhum byte foi ao aparelho nesta leva: ela estava usando a
> máquina com dois controles vivos. Toda linha deste documento é
> `afirmado-no-doc` — leitura cruzada de repositórios de terceiros contra o
> `hid-playstation.c` que está compilado nesta máquina.
>
> Ele nasceu do pedido dela: *"lançar novo workflow pra agentes procurarem no
> Github tais canais ou tais id (…) como é só informação eles trouxeram e me
> ajudaram no mapa do controle"*. O contrato é FATO com ENDEREÇO — um número,
> um offset, um formato de comando. Não há uma linha de código de terceiro
> copiada aqui.

---

## 1. A pergunta que vem ANTES de caçar: isto é canal do aparelho?

Seis linhas do mapa foram atacadas. **Três não têm canal nenhum, e isso é a
entrega** — dizer "não existe report para isto, e aqui está o porquê" evita que
a próxima pessoa cace um fantasma.

| linha do mapa | veredito | por quê |
| --- | --- | --- |
| `plataforma.camera_ir` | **não é canal — o aparelho NÃO TEM** | não há câmera nem sensor de IR no DualSense. A câmera IR desta família é a do Joy-Con **direito**, e isso já está escrito na linha `@pro`. O PS5 HD Camera é um aparelho USB separado |
| `plataforma.vpad` | **não é canal — é FEATURE NOSSA** | o gamepad virtual nasce do nosso código, por `uhid`. Não tem `report_id` no DualSense porque não existe no DualSense. Mas ele **imita** um, e por isso a tabela da §3 vale ouro para ele |
| `plataforma.adocao` | **não é canal — é FEATURE NOSSA** | grab de evdev, vpad e perfil são atos do sistema operacional sobre o nó. O DualSense **não tem protocolo de posse**: nenhum report de saída, nenhum feature report e nenhum bit de estado dizem "este host me tomou" |
| `plataforma.slot_jogador` | **metade e metade** | a ATRIBUIÇÃO do número é nossa e o aparelho não a conhece. A EXIBIÇÃO tem canal — e ele não mora nesta linha, mora em `luz.led_jogador*` (§6) |
| `plataforma.transporte_radio` | **TEM canal, e não é o que lemos** | §5 |
| `plataforma.vigia_zumbi` | **é feature nossa, mas o aparelho oferece sinais** | §7 |

---

## 2. Por que a ausência de câmera é afirmável

O argumento forte não é "ninguém menciona IR". É **não sobra endereço**.

O corpo do report de entrada tem 63 bytes e o `common` do report de saída tem
47 — os dois números são `static_assert` no driver desta máquina
(`assets/dkms/hid-playstation/hid-playstation.c`). As duas faixas estão hoje
nomeadas **byte a byte** (§3 e §6). Não há vaga onde uma câmera coubesse, e o
inventário de reports mapeados pela comunidade para o DualSense é curto:
entrada `0x01` e `0x31`, saída `0x02` e `0x31`, feature `0x05` (calibração),
`0x09` (pareamento) e `0x20` (versão de firmware). Nenhum é câmera.

Somando: uma busca de código no GitHub por `dualsense infrared` devolveu **zero
resultado**.

**A ressalva que fica de pé:** ausência de evidência em fonte pública não é
prova de ausência no silício. O que muda o grau aqui é que a faixa de endereços
está fechada, não que ninguém falou do assunto.

---

## 3. Os 63 bytes do corpo de entrada — e as 26 posições que o nosso vpad zera

O mapa registrava, desde 19/08/2026, um buraco medido e honesto na linha
`plataforma.vpad@dualsense`:

> *"O que o DualSense FÍSICO põe nessas 26 posições NÃO ESTÁ REGISTRADO em lugar
> nenhum desta casa, e enquanto não estiver ninguém pode afirmar que mandar zero
> ali é inofensivo."*

**As 26 posições agora têm nome.** Elas não são 26 desconhecidas: **24 são
`reserved` no próprio driver desta máquina, e duas carregam dado vivo.** E as
doze do meio — que o driver chama `reserved3[12]` — **não são reserva nenhuma**.

Os offsets abaixo são do **corpo** do report, isto é, depois do byte de
`report id`. No cabo o corpo começa no byte 1; no rádio começa no byte **2**
(há um byte de cabeçalho a mais — §5).

| corpo | o driver do Linux chama | o mapeamento público chama | o vpad escreve? |
| --- | --- | --- | --- |
| 0-3 | `x, y, rx, ry` | sticks esquerdo e direito | sim |
| 4-5 | `z, rz` | L2 e R2 analógicos | sim |
| 6 | `seq_number` | `SeqNo` | sim |
| 7 | `buttons[0]` | direcional (bits 0-3) + quadrado/x/bola/triângulo | sim |
| 8 | `buttons[1]` | L1 R1 L2 R2 Create Options L3 R3 | sim |
| 9 | `buttons[2]` | PS, touchpad, mudo — **e os quatro botões extras do DualSense Edge nos bits 4-7** | sim |
| **10** | `buttons[3]` | `UNK2`, "aparentemente sem uso" | **NÃO — zerado** |
| **11-14** | `reserved[4]` | `UNK_COUNTER`, um `uint32` que anda sozinho | **NÃO — zerado** |
| 15-20 | `gyro[3]` | velocidade angular | sim |
| 21-26 | `accel[3]` | acelerômetro | sim |
| 27-30 | `sensor_timestamp` | `SensorTimestamp` (`uint32`) | sim |
| 31 | `reserved2` | **`Temperature`, um `int8`** | sim (dentro da janela de movimento) |
| 32-39 | `points[2]` | dois dedos do touchpad | sim |
| **40** | `reserved3[12]` começa | **carimbo do bloco de toque** (o 9.º byte do bloco, que o driver não lê) | **NÃO — zerado** |
| **41** | `reserved3` | **R2: ponto de parada nos bits 0-3, estado nos bits 4-7** | **NÃO — zerado** |
| **42** | `reserved3` | **L2: ponto de parada nos bits 0-3, estado nos bits 4-7** | **NÃO — zerado** |
| **43-46** | `reserved3` | **`HostTimestamp` (`uint32`) — o ECO do carimbo que o HOST escreveu no report de saída** | **NÃO — zerado** |
| **47** | `reserved3` | **efeito ativo: R2 nos bits 0-3, L2 nos bits 4-7** | **NÃO — zerado** |
| **48-51** | `reserved3` termina | **`DeviceTimeStamp` (`uint32`)** | **NÃO — zerado** |
| 52 | `status[0]` | carga nos bits 0-3, estado de energia nos bits 4-7 | sim |
| 53 | `status[1]` | fone, mic, mic mudo — **e os dois bits do cabo (§5)** | sim |
| **54** | `status[2]` | **bit 0: mic externo ativo · bit 1: filtro passa-baixa do háptico ativo** | **NÃO — zerado** |
| **55-62** | `reserved4[8]` | `AesCmac[8]` | **NÃO — zerado** |

### 3.1 O que isso significa para o produto

**Os doze bytes 40-51 são o ECO DO GATILHO ADAPTATIVO.** O aparelho devolve, a
cada report, em que ponto o gatilho travou, qual efeito está carregado e dois
carimbos de tempo — um deles sendo a devolução do carimbo que o próprio host
mandou, o que permite a um jogo medir a ida e volta.

Nosso vpad zera os doze. **Consequência: um jogo que leia o retorno do gatilho
adaptativo através do nosso gamepad virtual vê "nenhum efeito carregado, nenhuma
parada, carimbos parados em zero" — para sempre, em qualquer transporte.**

O argumento mais forte de que isso não é inofensivo não é teórico. O
`cgutman/WinUHid` é um **DualSense virtual para Windows** — exatamente o trabalho
que o nosso vpad faz. Ele preenche sticks, gatilhos, sequência, botões, IMU,
carimbo do sensor, temperatura, toque, **o bloco 41-51 inteiro** e a bateria
(52), e para ali: o resto (53-62) fica declarado como não implementado. **O
único bloco que ele achou necessário preencher e nós não preenchemos é
justamente 40-51.**

Os outros zeros são mais defensáveis: 10 é "aparentemente sem uso" nas três
fontes, e 11-14 é `reserved` no driver e um contador livre no mapeamento
público — zerá-lo congela um contador que ninguém lê.

**O que continua não sabido:** se o `AesCmac[8]` em 55-62 é mesmo um MAC
criptográfico. A afirmação vem de uma única linhagem de mapeamento e nenhuma
fonte independente a corrobora aqui. O driver do Linux não lê esses oito bytes,
e o vpad os zera; se algum jogo os validasse, o vpad já teria quebrado.

**A tarde de bancada que o mapa pedia continua de pé** — o que mudou é que ela
agora tem hipótese endereçada para confirmar, em vez de 26 posições cegas.

---

## 4. O que CONFIRMA o driver, e o que o CONTRADIZ

O driver do Linux é o que roda na máquina dela. Um achado que o contradiz é
suspeito; um que o confirma por caminho independente vale mais que achado
solitário.

**CONFIRMAM, por duas implementações que não compartilham código:**

1. **A máscara dos LEDs de jogador.** O driver desta máquina monta
   `player_ids[]` como `BIT(2)`, `BIT(3)|BIT(1)`, `BIT(4)|BIT(2)|BIT(0)`,
   `BIT(4)|BIT(3)|BIT(1)|BIT(0)`, e os cinco bits — ou seja **0x04, 0x0A, 0x15,
   0x1B, 0x1F**. O `WinUHid` documenta, para os jogadores 1 a 5, exatamente
   **0x04, 0x0A, 0x15, 0x1B, 0x1F**. Um é driver de kernel, o outro é aparelho
   virtual de Windows.
2. **O apagar da lightbar.** O driver escreve `lightbar_setup = BIT(1)` no
   `common[41]` com o comentário "fade light out"; o dissector de tráfego do
   `DS5Dongle` decodifica o mesmo `common[41]` com o valor 2 como
   `FadeOut (blue->black)`.
3. **O bloco 41-51.** O `WinUHid` e o mapeamento do `duaLib`/wiki chegam à mesma
   ordem de campos, e o `WinUHid` não cita a wiki no cabeçalho.
4. **Os offsets 10-14 sem uso.** O `WinUHid` os declara como um `Reserved` de
   cinco bytes; o driver os declara como `buttons[3]` (que ele nunca lê) mais
   `reserved[4]`.

**CONTRADIZ, e a contradição é de ORDEM, não de endereço:** o driver comenta o
campo de giroscópio como `x, y, z`; três mapeamentos públicos independentes
escrevem a ordem do fio como **X, Z, Y**. Os endereços são os mesmos (corpo
15-20) e o tamanho é o mesmo; o que muda é qual eixo mora no meio.

**Eu não decido esta.** Ela não é do meu tema — é de quem cuida de movimento — e
decidir por leitura seria trocar o comentário de um driver que funciona pela
palavra de um documento. O que se pode dizer sem medir: o driver aplica a
calibração do feature `0x05` na mesma ordem em que lê, então uma troca de rótulo
entre dois eixos pode ser invisível em teste de eixo único e aparecer só em
rotação composta. **Fica registrada como pergunta de bancada, não como
correção.**

---

## 5. "Estou no cabo?" — o aparelho responde, e ninguém pergunta

**Como decidimos hoje.** A `pydualsense` chama `determineConnectionType`, lê um
report e olha o **tamanho**: 64 bytes é cabo, 78 é rádio. Pela perna de evdev,
o bus sai do sysfs. Os dois números batem com o driver
(`DS_INPUT_REPORT_USB_SIZE 64`, `DS_INPUT_REPORT_BT_SIZE 78`).

O enquadramento, para quem for ler byte cru:

| | entrada | saída |
| --- | --- | --- |
| **cabo** | `0x01`, 64 B — corpo de 63 a partir do byte 1 | `0x02`, 63 B — `common` de 47 a partir do byte 1 |
| **rádio** | `0x31`, 78 B — byte 1 é cabeçalho (bit 0 "traz estado", bit 1 "traz mic", bits 4-7 sequência), corpo de 63 a partir do byte **2**, CRC32 na cauda | `0x31`, 78 B — byte 1 sequência+tag, byte 2 tag, `common` a partir do byte 3, CRC32 na cauda |

Antes de entrar no modo cheio, o controle no rádio emite uma `0x01` **mínima de
10 bytes**, com um arranjo diferente (os gatilhos vão para o fim). Quem casar
por `report id` sem casar por tamanho lê lixo.

**O ACHADO.** O aparelho carrega a resposta **dentro do report de entrada**, e
nem o driver nem nós lemos:

- **corpo 53, bit 3** — há **dado** vindo por USB
- **corpo 53, bit 4** — há **energia** vindo por USB

O `hid-playstation.c` nomeia só os bits 0, 1 e 2 desse byte (`HP_DETECT`,
`MIC_DETECT`, `MIC_MUTE`) e para ali. A `pydualsense` lê o byte 52 (bateria) e
não toca no 53.

**Por que isso importa nesta mesa.** Tamanho de report e bus do sysfs
respondem "por onde vem o input". Eles **não separam cabo de dado de cabo de
só-carga** — e o aparelho separa, nesses dois bits. Um DualSense carregando num
cabo mudo enquanto manda input pelo rádio é configuração real, e é exatamente o
caso em que a régua de hoje pode responder com confiança a pergunta errada.

---

## 6. O sexto bit do byte dos LEDs de jogador

O `common` do report de saída, na parte de luz:

| `common` | driver do Linux | mapeamento público |
| --- | --- | --- |
| 41 | `lightbar_setup` | animação de fade: 0 nada, 1 fade-in, 2 fade-out |
| 42 | `led_brightness` | 0 forte, 1 médio, 2 fraco, 3 sem ação |
| 43 | `player_leds` | bits 0-4 as cinco luzes · **bit 5: se ligado, as luzes trocam na hora; se desligado, entram em fade** · bits 6-7 sem uso |
| 44-46 | `lightbar_red/green/blue` | RGB |

O portão de escrita é o `valid_flag1` no `common[1]`: `BIT(4)` libera o
indicador de jogador — o driver e o dissector concordam na máscara `0x10`.

**O bit 5 do `common[43]` o driver NUNCA escreve** — ele escreve só a máscara de
cinco bits. Confirmado pelo dissector de tráfego, que decodifica esse bit com a
máscara `0x20`.

**Onde isso entra no mapa:** em `luz.led_jogador*`, **não** em
`plataforma.slot_jogador`. O slot é atribuído por nós, chaveado pelo MAC, e o
aparelho não sabe que número ele é. Não há `report_id` a caçar naquela linha.

E o `valid_flag1` tem outro bit que o driver não nomeia: `BIT(5)`, máscara
`0x20`, que o dissector chama de liberação do **filtro passa-baixa do háptico**.
Ele fecha com o bit 1 do corpo 54 na entrada, que diz se o filtro está ativo —
um par controle/leitura completo que o driver ignora dos dois lados.

---

## 7. A vigia de zumbi — os sinais que o aparelho oferece

A vigia é nossa: ela cruza "HID conectado" com "evdev mudo ou obsoleto". O
aparelho não tem canal de "estou vivo". Mas oferece **quatro contadores**, e
três deles nós não lemos:

| sinal | onde | o que vale |
| --- | --- | --- |
| `seq_number` | corpo 6 | anda a cada report **no cabo** |
| `SensorTimestamp` | corpo 27-30 | relógio livre do aparelho |
| `DeviceTimeStamp` | corpo 48-51 | segundo relógio, dentro do bloco que o vpad zera |
| **contador de falha de CRC do rádio** | **corpo 64 — absoluto 66 no report `0x31`** | **o aparelho conta os pacotes que chegaram corrompidos** |

**O último é o que vale a viagem.** Um link que está de pé e apodrecendo é
exatamente o que a vigia quer pegar, e o aparelho já conta isso. Nada nesta casa
lê esse byte.

**E há uma armadilha de transporte, que é a razão de eu não escrever `medido`
em lugar nenhum.** O mapeamento público afirma que o `seq_number` do corpo 6
**fica congelado em `0x01` no rádio** — quem anda passa a ser o nibble alto do
byte 1 do `0x31`, um contador de 4 bits. As duas afirmações se explicam: o
enquadramento do rádio traz sequência própria. **Se for verdade, uma checagem de
vivacidade construída sobre o corpo 6 funciona no cabo e é CEGA no rádio** — a
pior forma de defeito, porque passa em todo teste feito com o cabo espetado.

**Não medi.** É a primeira coisa que eu poria na bancada dela: ligar no rádio,
capturar N reports parado na mesa, e olhar se o corpo 6 anda.

---

## 8. O que eu NÃO achei

A lista do que a internet não sabe é informação — ela diz onde só o aparelho
responde.

1. **Nenhum canal de IR ou câmera no DualSense.** Busca de código por
   `dualsense infrared` no GitHub: zero. Aqui "não achei" é a resposta, não a
   falta dela.
2. **Nenhum protocolo de posse/adoção.** Nada em report de saída, feature report
   ou bit de estado diz "este host me tomou". A exclusividade que o Hefesto usa
   é do sistema operacional, não do aparelho.
3. **Nenhum canal que diga ao aparelho qual é o número do jogador.** Só a
   máscara de luzes. O aparelho exibe; quem sabe é o host.
4. **A posição absoluta do contador de CRC não está fechada por fonte.** O
   `corpo 64` é firme; o absoluto 66 sai de somar o cabeçalho de 2 bytes do
   `0x31`, e a struct pública que o publica tem uma inconsistência de tamanho de
   um byte na cauda. **Confirmar com captura antes de confiar.**
5. **O significado real do `AesCmac[8]`** (corpo 55-62). Uma linhagem só.
6. **O que o `UNK_COUNTER` (corpo 11-14) conta.** Ninguém sabe; e "as duas metades
   altas parecem aleatórias" é o melhor que a fonte oferece.
7. **A ordem verdadeira dos eixos do giroscópio** — §4. Contradição viva entre o
   driver e três fontes públicas.

---

## 9. As fontes, fixadas por commit

Todas foram lidas por informação. **Nenhuma linha de código de terceiro foi
copiada para esta árvore.**

| fonte | o que sustenta |
| --- | --- |
| `assets/dkms/hid-playstation/hid-playstation.c` — nesta máquina | os tamanhos, os `report id`, e a fronteira de cada campo `reserved`. É a fonte que VENCE quando há divergência |
| `WujekFoliarz/duaLib@03bad1bea2a36561b520846776f2a07ced6773e0`, `src/include/dataStructures.h` <!-- ref-externa: arquivo de repositório de terceiro, citado como fonte --> | a tabela byte a byte da §3, o enquadramento do `0x31`, o contador de CRC |
| `cgutman/WinUHid@d6cebbef5c7909168d1f881185be8f607d6aefd4`, `WinUHidDevs/WinUHidPS5.h` <!-- ref-externa: arquivo de repositório de terceiro, citado como fonte --> | a confirmação independente do bloco 41-51 e da máscara dos LEDs de jogador |
| `awalol/DS5Dongle@17385f8beeef17129f0b39d9e5fc2195ea89b322`, `tools/wireshark_dualsense_setstate.lua` <!-- ref-externa: arquivo de repositório de terceiro, citado como fonte --> | o report de saída decodificado a partir de tráfego capturado — o bit de fade, o brilho, as máscaras de `valid_flag` |
| `nikashan02/dualsense-go`, `inputReport.go` <!-- ref-externa: arquivo de repositório de terceiro, citado como fonte --> | a mesma tabela em outra linguagem; **credita a wiki, então NÃO é fonte independente** |
| `pydualsense`, instalada na venv desta máquina | o que o nosso próprio caminho lê e o que ele não lê |

A wiki `controllers.fandom.com/wiki/Sony_DualSense/Data_Structures` é a origem
provável de boa parte dessa linhagem. Ela recusou leitura automática nesta
sessão (HTTP 402), e por isso **não é citada como fonte** — o que está aqui foi
lido nos repositórios acima.

---

## 10. Como isto entra no mapa

As seis linhas do tema receberam escrita em `docs/data/mapa-controles.csv`, com
`de_onde_sei = afirmado-no-doc` onde o fato é de fora, e `ate_onde_foi` **vazio
em todas** — nada foi ao aparelho nesta leva.

A régua que amarra este documento ao driver é
`tests/unit/test_os_bytes_que_o_driver_nao_nomeia.py`: ela calcula os offsets a
partir do fonte C compilado nesta máquina e reprova se um número desta página
divergir dele.
