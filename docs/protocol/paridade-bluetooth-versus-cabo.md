# Paridade Bluetooth × cabo — o que funciona em cada transporte

- **Levantado em:** 03/08/2026, por quatro agentes com verificação adversarial,
  e **medido no hardware dela** na mesma sessão
- **Por que existe:** ela definiu o requisito em uma frase — *"deixar o projeto
  robusto de tal forma que eu não note que estou no bt ou cabo, a ideia é termos
  tudo funcionando via bt principalmente"*. Este documento é a régua desse
  requisito
- **Regra de uso:** quando este documento e outro discordarem sobre o que
  funciona por Bluetooth, **este vence nas linhas MEDIDO AO VIVO** — as outras
  são leitura de código e estão marcadas como tal

---

## A distinção que este documento existe para impedir

Em 03/08 o assistente afirmou à mantenedora:

> *"no BT o DualSense não tem placa de som, logo mic e alto-falante não
> funcionam."*

**A premissa é verdadeira e está medida duas vezes nesta casa. A conclusão é
falsa, e o erro está no "logo".**

Por Bluetooth o áudio **não passa por placa de som — passa dentro do HID**
(Opus, 48 kHz, quadros de 10 ms no report `0x31`). O microfone funciona porque
alguém escreveu esse túnel neste projeto.

**Três perguntas diferentes, que precisam de três respostas:**

| pergunta | exemplo em que as respostas divergem |
|---|---|
| **(a) o hardware suporta?** | o alto-falante por BT: provavelmente sim |
| **(b) o projeto implementa?** | o alto-falante por BT: **não** — `BLOCO_SPEAKER` declarado e sem uso |
| **(c) está ligado por padrão?** | o microfone por BT: implementado, **opt-in**, não sobe sozinho |

Confundir (b) com (a) transforma *trabalho não feito* em *impossibilidade*.
Confundir (c) com (b) faz sumir um recurso que existe.

---

## A tabela

| recurso | hardware suporta? | projeto implementa? | ligado por padrão? | grau |
|---|---|---|---|---|
| **Lightbar** | sim (via kernel/sysfs) | sim — a cor sai por `core/sysfs_leds.py`; por BT a escrita da pydualsense é suprimida (`LIGHTBAR-BT-NEVER-01`) | sim | **MEDIDO AO VIVO** (03/08) — **e com uma condição medida em 12/08: ver a nota logo abaixo da tabela** |
| **Player-LEDs** | sim | sim, pelo mesmo caminho | sim | **MEDIDO AO VIVO** |
| **Gatilhos adaptativos** | sim | sim, **sem ramo de transporte** — o `common` é idêntico nos dois envelopes | com preset aplicado | **MEDIDO AO VIVO** (*"l2 funciona"*, 03/08) |
| **Rumble** | sim (kernel implementa rumble + CRC-32 do BT) | sim, **zero gate de transporte** | exige o vpad | **MEDIDO AO VIVO** (03/08 — vibrou e parou); os dois motores separados e o zero que para de verdade, **medidos no rádio em 10/08**; a vibração que o **jogo** manda ao nó físico, **medida nos dois transportes em 11/08** — ver a nota |
| **Giroscópio / acelerômetro** | sim | sim, cópia byte a byte da janela de motion | sim, com o vpad uhid | **taxa do aparelho MEDIDA em 11/08:** cabo 250,0 Hz exatos, rádio variável em rajadas (ver abaixo). Chegada ao **jogo**: continua não medida, nos dois transportes |
| **Touchpad (dedo e clique)** | sim | sim, mesma janela + `payload[9] & 0x02` | sim | **IMPLEMENTADO, NÃO MEDIDO** em jogo |
| **Microfone** | **sim** — Opus em HID | **sim, inteiro** (`integrations/dualsense_bt_audio.py`) | **não** — opt-in por privacidade e banda | **MEDIDO AO VIVO** (WAV em 25/07 e em 03/08) |
| **Alto-falante — volume/rota/pré-amp** | sim (são registradores no `common`) | sim, sem gate de transporte | só depois do primeiro `speaker.set` | **IMPLEMENTADO, NÃO MEDIDO** |
| **Alto-falante — som saindo** | não confirmado | **NÃO** — `BLOCO_SPEAKER = 0x13` declarado e **sem uso** | — | **NÃO IMPLEMENTADO** |
| **Áudio de sistema (card/sink no PipeWire)** | **impossível** — sem A2DP/HFP/HSP | — | — | **MEDIDO**: zero cards com o controle no rádio |

> **NOTA DATADA — 12/08/2026: duas linhas da tabela ganharam condição, e as duas
> condições foram medidas com quatro DualSense na mesa dela (dois no cabo, dois
> no rádio).** Nenhuma das duas é diferença **de transporte** — e é por isso que
> elas moram numa nota e não viraram coluna nova.
>
> **1. A lightbar por rádio depende de QUEM tinha o `hidraw` aberto na probe.**
> Com a Steam viva no instante em que o controle sobe, a cor escrita pela rota
> `sysfs` — a **única** que o produto usa por Bluetooth — **não pega**: um em
> três obedeceu. Com ninguém no `hidraw` antes da conexão, **três em três**
> obedeceram a verde puro. **No cabo a assimetria é gritante e foi medida no
> mesmo instante:** em 11/08, com a Steam aberta e o daemon parado, a mesma
> escrita acendeu os **dois** controles do cabo e **nenhum** dos dois do rádio
> (`docs/data/ensaios.csv:26-27`, literal dela: *"só os cabo ficaram branco e o
> do bt não"*). A medição no fio, o contraste de 98 contra 6 pacotes de
> saída e a rota que vence (`hidraw` cru) estão em
> [a pilha do Steam Input](pilha-steam-input-xpad-sdl.md), seção 6-bis; os
> ensaios são `docs/data/ensaios.csv:41-51`, todos com o olho dela.
>
> **2. A vibração que o JOGO manda ao nó físico era cancelada pelo produto, nos
> dois transportes.** Quando o jogo escreve força-feedback pelo `evdev` do
> DualSense físico — o que acontece quando não há gamepad virtual e não é
> Conexão Nativa —, o keepalive do daemon reescrevia `common[2]`/`common[3]`
> zerados a cada 0,5 s e apagava o motor. **A causa foi isolada com número**
> (a constante em 8,0 s produziu **oito segundos exatos** de vibração) e a cura
> é `RUMBLE-SEM-DONO-01`: o keepalive deixou de ser perpétuo. **O defeito não
> distinguia cabo de rádio** — foi medido igual nos dois
> (`docs/data/ensaios.csv:16-24`).

---

## As três diferenças reais entre os transportes

Tudo o mais é paridade. Estas três não são:

### 1. O canal de áudio é outro — não é o mesmo degradado

| | cabo (USB) | rádio (Bluetooth) |
|---|---|---|
| o que é | placa USB Audio de **4 canais** | **nenhum áudio nativo** |
| canais | 1-2 fone/alto-falante · 3-4 os motores voice-coil | — |
| como o som anda | ALSA/PipeWire, como qualquer placa | **tunelado no HID** (`0x31` entrada, saída não implementada) |
| quem entrega | o sistema | **este projeto**, decodificando na mão |

É por isso que no cabo o DualSense aparece em `pactl list sources` e por rádio
não aparece nada.

### 2. O silêncio do rádio

Por Bluetooth o firmware pode emudecer, e o projeto trata isso com um teto de
silêncio **por transporte**: 30 s no rádio contra 1 s no cabo
(`core/physical_report_reader.py`, `GYRO-BT-SILENCIO-01`). Quando o teto vence,
o reader solta o fd, zera a janela de motion e **solta o clique do touchpad** no
vpad, depois reabre.

> **NOTA DATADA — 03/08/2026, e a régua fica registrada porque é reutilizável
> e barata:** com os controles **parados na mesa**, medindo por **contagem de
> bytes**, os dois emitiram **~300 Hz** (1.402.128 bytes em 60 s). O rádio
> **não** emudeceu nesta medição. O teto continua justificado pelo defeito que
> o originou.
>
> **NOTA DATADA — 11/08/2026: a régua de 03/08 acertou a faixa; o que ela não
> podia ver é que o número era a média de UMA janela.** Remedido com duas
> réguas independentes sobre o nó evdev `Motion Sensors` — relógio do host e
> `sensor_timestamp` do próprio controle — em cinco janelas de 8 a 10 s, com o
> controle parado: **363,3 · 239,9 · 334,1 · 55,4 · 69,7 Hz**. Os ~300 Hz de
> 03/08 caem dentro dessa faixa, e é por isso que a régua antiga **fica**: ela
> mostrou primeiro que o rádio não é 1000 Hz, é uma contagem de bytes, e
> corrobora a nova por um caminho que não compartilha nenhum instrumento com
> ela.
>
> **O que a medição nova acrescenta é a instabilidade, e ela é o achado:** a
> taxa caiu de ~334 para ~55 Hz entre duas janelas consecutivas, sem que nada
> mudasse. O p05 do intervalo é teimosamente 1255 us (~797 Hz **instantâneos**)
> enquanto o p95 chega a 187 ms — **o fluxo é em rajadas**, e o que varia é o
> silêncio entre elas. **O rádio não tem taxa típica**: quem citar um número só
> está citando uma janela. Números completos em
> [o driver `hid-playstation` por dentro](driver-hid-playstation.md), seção 6.

### 3. A contenção com múltiplos controles

Com 2+ controles no mesmo rádio o link degrada
(`BUG-MULTI-CONTROLLER-BT-CRC-CONTENTION-01`). A assinatura aparece no `dmesg`:

```
playstation 0005:054C:0CE6.0007: DualSense input CRC's check failed
```

Por isso o throttle do report thread escala com o número de controles.

---

## O que falta para "não notar se estou no BT ou cabo"

Ordenado por (impacto ÷ custo):

1. **o desmute do microfone com dono** — o mic BT funciona, mas o firmware retém
   o mudo e ninguém o limpa no ciclo de vida da ponte. Custo: baixo.
   Ver [a noite em que o microfone do Bluetooth voltou](../process/estudos/2026-08-03-a-noite-em-que-o-microfone-do-bluetooth-voltou.md);
2. **ligar a ponte de mic pela interface** — hoje só por CLI (`mic bt`), sem
   widget, e o daemon publica campo morto no status. Custo: baixo;
3. **o filtro do bit de áudio no espelho de motion** —
   `core/physical_report_reader.py` aceita qualquer `0x31` de 78 bytes com CRC
   bom, e o pacote de Opus **passa pelo mesmo CRC**. Enquanto isso não for
   filtrado, mic por BT e giroscópio **não coexistem**. Custo: uma condição.
   É pré-requisito duro dos itens 1 e 2;
4. **o rumble na borda de queda do rádio** — o motor fica preso quando o link
   cai; a primitiva existe (`force_rumble_stop`) e não é chamada ali.
   Custo: baixo;
5. **a ponte de SAÍDA de áudio (alto-falante) por BT** — o único recurso que
   **não existe** no rádio. Custo: **sprint inteira**, e antes da primeira linha
   é preciso resolver uma contradição interna: `dualsense_bt_audio.py` diz report
   `0x39`, a referência canônica diz `0x32`. Nenhuma das duas foi medida aqui;

   > **NOTA DATADA — 11/08/2026: a contradição é mais estreita do que parece,
   > e a precisão importa para não fechá-la com a medição errada.** O `0x32`
   > que esta casa mediu ao vivo em 25/07 é o de **controle** (142 bytes, TLV
   > `0x11` AudioControl, o byte que destrava o microfone —
   > `integrations/dualsense_bt_audio.py:210`). O report em disputa é o que
   > leva os **dados**: o módulo o dá como `0x39`, com os blocos `0x12`
   > (háptico) e `0x13`/`0x16` (alto-falante), em `:31` e `:213-219`; a
   > canônica o dá como `0x32` com tag `0x12`. **Continuam os dois de fonte
   > única e nenhum medido** — o `0x32` medido **não** é evidência para
   > nenhum dos lados. Fecha por leitura do *report descriptor* por BT, sem
   > escrever no controle;
6. **o slider do alto-falante por BT promete som que não sai** — enquanto o item
   5 não vier, a tela precisa dizer isso. Custo: baixo.

---

## O que só medição no hardware responde

- **o alto-falante por BT existe, e por qual report?** As duas fontes internas
  divergem e nenhuma foi medida aqui;
- **o dado de sensor chega ao JOGO?** Nunca validado, nem por cabo nem por
  rádio. E esta é pergunta de **chegada**, não de taxa: a taxa do aparelho está
  medida desde 11/08 nos dois transportes (cabo 250,0 Hz, rádio em rajadas);
- **a taxa que o SDL DECLARA ao jogo** — e é só essa metade que falta. O
  gamepad virtual se anuncia DualSense Edge (`VPAD_PRODUCT = 0x0DF2`,
  `integrations/uhid_gamepad.py:123`), e o SDL atribui **1000 Hz a um Edge por
  USB**. O que o aparelho entrega **está medido desde 11/08, e por transporte**:
  **250,0 Hz exatos no cabo**, e no rádio uma taxa **variável em rajadas**, de
  ~38 a ~392 Hz de média conforme a janela. A razão de 4× que preocupa é a do
  **cabo** — 1000 declarados contra 250 entregues. Um jogo que integre
  velocidade angular pela taxa declarada teria escala errada.

  A metade que falta é **só medível contra a SDL3 que a Steam distribui** —
  medir contra a `libSDL2` do sistema já produziu um alarme falso inteiro nesta
  casa.

  > **NOTA DATADA — 11/08/2026: o par transporte-número que estava escrito aqui
  > misturava os dois transportes, e a correção importa mais que o número.** A
  > frase antiga dizia *"o SDL atribui 1000 Hz a um Edge por **USB** enquanto o
  > espelho entrega ~300"*: os ~300 Hz são do **rádio**, não do cabo. Por cabo
  > o físico entrega 250,0 Hz, medidos por duas réguas independentes e
  > previstos pelo `bInterval = 6` do descritor. Comparar o declarado de um
  > transporte com o entregue do outro produz uma razão que não existe.
  >
  > **`GYRO-EDGE-RATE-01` é NOME DE DIVERGÊNCIA, não sprint.** Não existe
  > arquivo com esse nome em `docs/process/sprints/`, e chamá-lo de sprint faz
  > parecer que alguém está com o trabalho na mão. O apelido está registrado em
  > [divergências nomeadas](../process/DIVERGENCIAS-NOMEADAS.md).
  >
  > **Continua não existindo nesta árvore uma linha que reconcilie a taxa
  > declarada com a real** — nem conversão, nem aviso, nem número guardado. E o
  > aparelho vizinho já tem o análogo MEDIDO: o Pro declara 8 ms e entrega
  > 11,2 ms, três medições em 07/08 (canônica dos externos, seção 3.5). Isso
  > torna a hipótese plausível e **não** a prova aqui.

---

## Documentos que contradizem esta tabela (dívida aberta)

- **`docs/usage/bluetooth.md`** afirma que o áudio por BT *"(fone e microfone)
  continua fora de escopo"* — **falso desde 25/07**, e contradiz o `README.md`
  e o `docs/usage/cli.md` no mesmo repositório. **Foi a fonte do erro de 03/08
  registrado no topo deste documento**;
- **`README.md`** publica *"~40% do sinal, causa em aberto"* para o mic por BT —
  número medido sob uma condição que deixou de existir quatro minutos depois;
- **`cli/cmd_mic.py`** afirma que o install instala os drop-ins 52/53 — não
  instala (`install.sh` os deixa em opt-in, desligados).

**Acrescentado em 11/08/2026:**

- **`docs/adr/008-bt-vs-usb-polling.md:9`** afirma que *"gatilho adaptativo via
  BT tem comportamento ligeiramente diferente em `Machine` e `Galloping`"*.
  **Essa linha não tem fonte, medição nem rastro em lugar nenhum deste
  repositório**, e contradiz a linha "Gatilhos adaptativos" da tabela desta
  página, que é **MEDIDO AO VIVO** e diz o contrário: o `common` é idêntico nos
  dois envelopes e não há ramo de transporte no caminho do gatilho. Grau da
  afirmação da ADR: **BAIXA, sem procedência**. Enquanto ninguém sentir os dois
  modos por rádio e por cabo lado a lado, esta página vence — e a diferença, se
  existir, é do **firmware**, não deste projeto;
- **[a referência canônica do DualSense](dualsense-referencia-canonica.md)** foi
  reconciliada em 11/08 em oito pontos que estavam vencidos (o byte 53, o
  pré-amp, os modos de gatilho, o P4, a taxa do giroscópio, entre outros). Onde
  era **fato errado** — o padrão do jogador 4 e o *"nunca medido"* das taxas — o
  texto foi **substituído**, não riscado; onde era **decisão medida**, ficou nota
  datada. O índice fica no topo daquela página, em *"O que caducou em
  11/08/2026"*. Nenhum deles muda a tabela desta — o que muda são os dois
  números de taxa desta página, já corrigidos acima.
