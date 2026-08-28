# Onde a porta USB mora — o `physical_location` do kernel

O kernel publica a posição **física** de cada porta USB no chassi. Medido nesta
bancada em **23/08/2026**, kernel `7.0.11-76070011-generic`, uid 1000, sem root.

Esta página responde três perguntas e para: **o que o campo entrega**, **por que
ele some em metade das portas desta máquina**, e **até onde o produto pode
falar com ele na mão**. O que ele entrega sobre o *aparelho* ligado na porta é
outro assunto — a [referência canônica](dualsense-referencia-canonica.md)
descreve o DualSense, e esta descreve o buraco onde ele entra.

## Como ler os graus de confiança

Mesma convenção da [canônica](dualsense-referencia-canonica.md#como-ler-os-graus-de-confiança),
com um grau que esta página usa muito:

| grau | significa |
|---|---|
| **MEDIDO AQUI** | conferido nesta máquina, em 23/08/2026, com o comando escrito ao lado |
| **ALTA** | lido no fonte do mainline, em **tag fixada** (`v7.0`), com arquivo e função citados |
| **LIDO NA ABI** | o que `Documentation/ABI/testing/sysfs-devices-physical_location` declara, na mesma tag |
| **HIPÓTESE** | não medido. Marcado assim para que ninguém cite como fato |

**Grau geral desta página: MEDIDO AQUI**, com a causa em **ALTA**. Onde o
grau cai, está dito na linha.

---

## 1. O que cada campo entrega

`/sys/bus/usb/devices/usb1/1-0:1.0/usb1-port4/physical_location/` é um
diretório com cinco arquivos. **GRAU: LIDO NA ABI + MEDIDO AQUI.**

| arquivo | o que diz | valores vistos nesta bancada |
|---|---|---|
| `panel` | a **face do chassi** onde o conector está | `left`, `right` |
| `horizontal_position` | posição na largura daquela face | `left`, `center` |
| `vertical_position` | posição na altura daquela face | `lower`, `upper` |
| `lid` | o conector está na **tampa** (laptop)? | `no` em todas as 14 |
| `dock` | o conector está numa **dock**/replicador? | `no` em todas as 14 |

A ABI declara mais valores do que esta bancada produziu — `panel` admite as seis
faces (`top`, `bottom`, `front`, `back`, `left`, `right`) mais `unknown`. Um
gabinete que só use duas delas não prova que as outras não existam; é por isso
que `secao_mesa.py` traduz **as seis**, e não as duas que o desenho previa.

**O que o campo NÃO entrega, e isto é a metade importante:**

- **não é um identificador.** Três conectores desta placa dizem exatamente
  `left/left/lower`. Ver §6.
- **não diz "frente" nem "trás" numa caixa qualquer.** `panel` é a face da
  *carcaça*, e quem decide qual face fica virada para o sofá é quem montou o
  gabinete. Ver §6.
- **não segue o cabo.** O valor descreve o buraco na placa-mãe, não onde o
  aparelho está. Um hub de mesa a dois metros de distância continua reportando
  a porta traseira em que ele foi espetado — quando reporta.

### O aparelho herda a posição da porta

**GRAU: MEDIDO AQUI.** O nó do *aparelho* (`/sys/bus/usb/devices/1-4/`) carrega
o mesmo diretório, com os mesmos valores da porta em que ele está:

```sh
cat /sys/bus/usb/devices/usb1/1-0:1.0/usb1-port4/physical_location/panel   # right
cat /sys/bus/usb/devices/1-4/physical_location/panel                       # right
readlink /sys/bus/usb/devices/usb1/1-0:1.0/usb1-port4/device               # ../../1-4
```

Conferido nos dois aparelhos que estavam em portas descritas (`1-4`, o adaptador
Bluetooth TP-Link UB500, e `1-6`): panel, horizontal e vertical batem casa a
casa com os da porta. **Consequência prática:** ler pelo nó do aparelho — que é
o que `censo_do_barramento.py` já faz — e ler pelo nó da porta dão o mesmo
número. A diferença é que **a porta responde com o buraco vazio**, e o aparelho
só existe enquanto está ligado.

---

## 2. De onde vem o dado

**GRAU: ALTA.** `drivers/base/physical_location.c` (mainline, tag `v7.0`):
`dev_add_physical_location()` exige que o `struct device` tenha um **companion
ACPI**, chama `acpi_get_physical_device_location()`, e copia campo a campo do
`struct acpi_pld_info` — `pld->panel`, `pld->horizontal_position`,
`pld->vertical_position`, `pld->dock`, `pld->lid`. Sem companion ACPI, ou sem
`_PLD` no objeto, a função sai e **o diretório inteiro não é criado**.

Ou seja: **o dado é do firmware da placa-mãe, escrito pela fabricante no objeto
ACPI `_PLD` de cada porta.** Não é medição do kernel, não é do dispositivo, não
é da controladora. É o que a Gigabyte escreveu na DSDT desta B450M S2H.

**Consequência de procedência, e é a mais dura desta página:** o dado tem a
qualidade da tabela do firmware. Uma BIOS que copie o mesmo `_PLD` para várias
portas produz um valor **presente, plausível e errado como identificador** — e
foi exatamente o que esta bancada mediu (§6).

Confirmado no `/sys` desta máquina, e é a mesma coisa dita pelo outro lado:

```sh
readlink /sys/bus/usb/devices/usb1/1-0:1.0/usb1-port4/firmware_node
# ...../LNXSYSTM:00/LNXSYBUS:00/PNP0A08:00/device:2e/device:3e/device:3f/device:4e
cat /sys/bus/acpi/devices/*/path | grep RHUB.POT8      # \_SB_.PCI0.GPP2.PTXH.RHUB.POT8
```

Cada porta descrita tem um `firmware_node` apontando para um objeto ACPI
`\_SB_.PCI0.GPP2.PTXH.RHUB.POTn`. Nenhuma porta sem descrição tem esse link.

---

## 3. A cobertura é PARCIAL, e a causa está provada

**Esta é a informação mais importante da página.** Nesta máquina, **14 das 22
portas** respondem. A divisão não é aleatória: **uma controladora responde
tudo, a outra não responde nada.**

| root hub | PCI | USB | portas | com `physical_location` |
|---|---|---|---|---|
| `usb1` | `0000:02:00.0` — AMD 400 Series **Chipset** `[1022:43d5]` | 2.00 | 10 | **10** |
| `usb2` | `0000:02:00.0` — mesma | 3.10 | 4 | **4** |
| `usb3` | `0000:0c:00.3` — AMD **Matisse** (na CPU) `[1022:149c]` | 2.00 | 4 | **0** |
| `usb4` | `0000:0c:00.3` — mesma | 3.10 | 4 | **0** |

### A causa: o firmware descreve uma controladora e ignora a outra

**GRAU: MEDIDO AQUI.** Não é diferença de kernel, nem de driver — as quatro root
hubs são o mesmo `xhci_hcd`. É o **namespace ACPI**, e ele foi lido:

```sh
for d in /sys/bus/acpi/devices/*/; do cat $d/path 2>/dev/null; done | grep -E 'PTXH|XHC0'
```

- A do chipset é `\_SB_.PCI0.GPP2.PTXH`, e **tem um `RHUB` com 22 objetos de
  porta** (`POT1`..`POT9`, `PO10`..`PO22`), cada um com o `_PLD` que o kernel lê.
- A da CPU é `\_SB_.PCI0.GP13.XHC0`, e **não tem `RHUB` nenhum**. Seus únicos
  irmãos sob `GP13` são `APSP` e `AZAL`. Não há objeto de porta para descrever,
  logo não há `_PLD`, logo não há `physical_location`.

O amarrado dos dois lados, medido:

```sh
readlink -f /sys/bus/pci/devices/0000:02:00.0/firmware_node  # -> ...\_SB_.PCI0.GPP2.PTXH
readlink -f /sys/bus/pci/devices/0000:0c:00.3/firmware_node  # -> ...\_SB_.PCI0.GP13.XHC0
```

**A causa é do firmware, não do kernel.** A DSDT desta placa descreve as portas
do chipset e cala sobre as da CPU. Nada em Linux corrige isso — não há quirk,
não há módulo, não há permissão que faça aparecer o que a BIOS não escreveu.

**HIPÓTESE, e continua hipótese:** que isso seja *padrão* em placas AM4 —
descrever o chipset e ignorar o controlador direto da CPU. Uma placa não é uma
amostra. **Esta bancada não prova nada sobre outras placas**; ver §7.

### O detalhe que engana: 22 e 22 é coincidência

`ls -d /sys/bus/usb/devices/usb*/*/usb*-port* | wc -l` dá **22**, e o ACPI
declara **22** objetos de porta. **Os dois 22 não são o mesmo 22.** Os 22
objetos ACPI estão **todos** sob `PTXH` (o chipset), e só 14 deles se ligaram a
uma porta real — os oito restantes (`PO15`..`PO22`) descrevem conectores que
esta placa não tem populados. Ler a igualdade como "o firmware descreve todas as
portas" é o erro que esta seção existe para impedir.

---

## 4. A régua, validada

A casa já tomou decisão errada por acreditar num instrumento. **Quatro contagens
independentes do mesmo fato**, e todas fecham em 14/22:

```sh
# 1. o diretório existe?
ls -d /sys/bus/usb/devices/usb*/*/usb*-port*                      | wc -l   # 22
ls -d /sys/bus/usb/devices/usb*/*/usb*-port*/physical_location    | wc -l   # 14

# 2. o companion ACPI existe? (causa, medida por outro arquivo)
ls /sys/bus/usb/devices/usb*/*/usb*-port*/firmware_node           | wc -l   # 14

# 3. o objeto ACPI se ligou a um nó físico? (medido do lado do ACPI)
for d in /sys/bus/acpi/devices/*/; do
    case "$(cat $d/path 2>/dev/null)" in *RHUB.PO*)
        ls $d | grep -q physical_node && echo ligado;; esac
done | wc -l                                                               # 14

# 4. a palavra `location`, que o kernel deriva do mesmo _PLD
ls /sys/bus/usb/devices/usb*/*/usb*-port*/location                         | wc -l  # 22
cat /sys/bus/usb/devices/usb*/*/usb*-port*/location | grep -vc 0x00000000  # 14
```

As quatro réguas são de arquivos diferentes, e **duas delas são do lado do ACPI,
não do lado do USB** — que é o que faz a medição valer. Um quinto sinal
acompanha na mesma divisão: `connect_type` diz `hotplug` nas 14 e `unknown` nas
8 (ele vem do `_UPC`, objeto irmão do `_PLD`).

**A régua que NÃO vale:** contar aparelhos conectados. Só dois dos onze
aparelhos ligados agora estão em porta descrita, e isso mede onde ela plugou os
cabos, não o que o firmware descreve.

---

## 5. O que isto permite ao produto

**Primeiro, o registro se corrige:** não é verdade que o produto ignore este
campo. `censo_do_barramento.py` já lê `physical_location/panel` pelo nó do
aparelho, e `secao_mesa.py` já traduz as seis faces para a tela, com `"Não sei"`
quando o kernel cala. O que esta medição acrescenta são **três coisas que o
produto ainda não usa**:

1. **`horizontal_position` e `vertical_position`.** O produto lê só `panel`.
   Nesta bancada, `panel` sozinho separa as 14 portas em 2 grupos; com os três
   campos, em 5. Não resolve tudo (§6), mas triplica a resolução de graça.
2. **A leitura pelo nó da PORTA.** O aparelho só responde ligado; **a porta
   responde vazia**. É o que permite dizer *"a porta ao lado está livre e é
   melhor"* — hoje impossível, porque uma porta livre não tem nó de aparelho.
3. **A causa da ausência.** Hoje, ausência é um `"Não sei"` mudo. Com a §3 na
   mão, o produto pode distinguir *"seu firmware não descreve esta
   controladora"* de *"você está atrás de um hub"* — que são conselhos
   diferentes para quem usa.

**E isto muda o que a aba Configurações pode PERGUNTAR.** O
[VETO 3](../process/sprints/2026-08-21-ABA-CONFIGURACOES/CONFIG-08-a-aba-entra-na-documentacao.md)
proíbe declarar o que o produto pode medir. Onde a controladora responde, **o
produto sabe**, e perguntar vira a tela fingindo ignorância. A pergunta legítima
encolhe para onde o dado não existe — e a §3 diz exatamente onde é. A
[sprint das portas](../process/sprints/2026-08-27-A-FAXINA-o-que-saiu-e-por-que.md)
depende desta página para desenhar essa fronteira.

---

## 6. O que isto NÃO permite

### `panel=left` não é "a frente"

`panel` é a face **da carcaça**, no eixo em que a fabricante a definiu. Um
gabinete de pé e um horizontal apoiado sob a TV orientam a mesma placa de
maneiras diferentes, e nenhum dos dois avisa o firmware. **Onde a leitura para
de ser confiável:** no instante em que a tela troca a palavra do kernel por uma
palavra de móvel — "frente", "atrás", "do lado do sofá". `Direita` é o que o
kernel disse; `frente` é interpretação, e o produto não mediu a caixa dela.

É por isso que a pergunta ao usuário **continua legítima**, mas com outro texto:
não *"onde está o adaptador?"* (o produto sabe) e sim *"a face que o kernel
chama de direita é a que fica virada para você?"* — uma pergunta que se faz uma
vez e vale para todas as portas daquele gabinete.

### O valor NÃO identifica a porta

**GRAU: MEDIDO AQUI, e é o achado mais afiado desta página.** As 14 portas
descritas produzem apenas **5 triplas distintas**:

```sh
for p in /sys/bus/usb/devices/usb*/*/usb*-port*/physical_location; do
    echo "$(cat $p/panel)/$(cat $p/horizontal_position)/$(cat $p/vertical_position)"
done | sort | uniq -c | sort -rn
#   5 left/center/lower      3 right/left/lower      3 left/left/lower
#   2 right/left/upper       1 right/center/lower
```

Parte dessa repetição é **correta**: um conector USB 3 aparece duas vezes, uma
via de alta velocidade e uma via SuperSpeed, e as duas devem descrever o mesmo
buraco. O kernel diz quais são, e são só três pares:

```sh
readlink /sys/bus/usb/devices/usb1/1-0:1.0/usb1-port5/peer   # ../../../usb2/2-0:1.0/usb2-port1
```

Descontados os três pares legítimos, sobram **11 conectores físicos para 5
descrições**. As colisões reais:

- `usb1-port1`, `usb1-port8` e `usb1-port9` — **três** conectores distintos, sem
  `peer` entre si, todos `left/left/lower` e todos `location=0x80000105`. O
  firmware copiou o mesmo `_PLD` para os três.
- `usb1-port2` e `usb1-port10` — dois conectores, ambos `left/center/lower`.
- `usb1-port3` e o par `usb1-port6`/`usb2-port2` — `location` **diferente**
  (`0x80000107` contra `0x80000102`), e mesmo assim a mesma tripla
  `right/left/lower`.

Essa última é a mais instrutiva: **`location` distingue portas que
`physical_location` não distingue.** A palavra de 32 bits carrega o grupo e a
posição do `_PLD`; as três palavras de tela são uma descrição grossa que perde
essa informação. Quem precisar de identidade usa `location`; quem precisa de
frase para humano usa as três palavras — e aceita que elas podem apontar para
três buracos.

**A única porta unicamente descrita nesta placa é `usb1-port4`
(`right/center/lower`, `0x80000108`)** — que é, por acaso, onde o adaptador
Bluetooth TP-Link UB500 estava no momento da medição. Para esse aparelho, e só
para ele, o produto pode dizer o buraco. Para os outros, pode dizer a região.

### A regra que sai daqui

> O produto pode afirmar **a face e a região**. Não pode afirmar **o buraco**,
> a menos que a tripla seja única naquela máquina — e isso se verifica
> contando, não presumindo.

---

## 7. Para outras máquinas — o que é pergunta aberta

Uma placa não é uma amostra, e o que segue **não foi medido**. Está aqui como
pergunta, para que ninguém cite como fato:

| pergunta | grau | o que se sabe |
|---|---|---|
| Laptop responde? | **HIPÓTESE** | O campo `lid` existe justamente para laptop, o que sugere que alguém escreveu `_PLD` neles. Sugerir não é medir. Esta casa não tem laptop na bancada. |
| Placa antiga responde? | **ABERTA** | O suporte entrou no kernel em 2022 (autoria de Won Chung, `Documentation/ABI/testing/sysfs-devices-physical_location`). O **kernel** é recente; o `_PLD` é do firmware e existe desde ACPI 3.0. Uma placa velha com BIOS caprichada pode responder mais que uma nova relaxada. |
| Todo AM4 ignora o controlador da CPU? | **HIPÓTESE** | Medido em UMA B450M S2H. Nada além disso. |
| Placa Intel responde? | **ABERTA** | Nenhuma medição. |
| Hub externo some sempre? | **PARCIAL** | Nesta bancada, os dois hubs estão na Matisse, que já não descreve nada — as duas causas estão **confundidas** e a medição não as separa. O que sustenta a expectativa é estrutural, não medido: o `_PLD` descreve a placa-mãe, e o firmware não pode conhecer um hub que a pessoa comprou depois. Quem tiver um hub no barramento do chipset fecha esta linha em um comando. |

**O que qualquer pessoa pode rodar para responder pela máquina dela**, sem root:

```sh
ls -d /sys/bus/usb/devices/usb*/*/usb*-port*                   | wc -l  # portas
ls -d /sys/bus/usb/devices/usb*/*/usb*-port*/physical_location | wc -l  # descritas
```

Se os dois números forem iguais, aquela máquina não tem o problema da §3. Se o
segundo for zero, o firmware dela não descreve porta nenhuma, e todo desenho que
dependa desta página tem de sobreviver a isso.

---

## Vizinhos

- [dualsense-referencia-canonica.md](dualsense-referencia-canonica.md) — o que
  o aparelho entende, do outro lado do cabo que entra nesta porta.
- [GUIA-RADIO-DA-SALA.md](../../GUIA-RADIO-DA-SALA.md) — por que a posição
  física de um rádio 2,4 GHz importa. Esta página é o instrumento; aquela é o
  motivo.
- [PORTAS-DA-CASA-01](../process/sprints/2026-08-27-A-FAXINA-o-que-saiu-e-por-que.md)
  — a leva que consome esta medição.
