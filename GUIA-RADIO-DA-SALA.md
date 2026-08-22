# Guia de rádio da sala

**Como dispor as conexões do PC para 5 DualSense em Bluetooth com microfone,
mais teclado, mouse, Wi-Fi, webcam e Ethernet — todos funcionando ao mesmo
tempo.**

```
Máquina alvo: MeowSystem / Andromeda-OS
Placa:        Gigabyte B450M S2H · Ryzen 7 5800X · RTX 4060 · EVGA 600 BR
Sistema:      Pop!_OS 24.04 · kernel 7.0.11 · BlueZ 5.86
Levantado em: 21/08/2026
Comprado em:  21/08/2026 — três adaptadores, não dois
```

---

## 1. O problema, em uma frase

Bluetooth Classic tem **1.600 slots de tempo por segundo**, e todos os
dispositivos de um mesmo adaptador dividem esses slots. Não é banda de dados
que falta — é vez de falar.

Tudo neste guia decorre disso.

---

## 2. Inventário: o que precisa funcionar junto

| Dispositivo | Rádio | Consumo de slots |
|---|---|---|
| 5 × DualSense em BT, mic ligado | Bluetooth Classic | ~277 pacotes/s **cada** |
| Teclado sem fio | 2,4 GHz proprietário | Desprezível |
| Mouse sem fio | 2,4 GHz proprietário | Desprezível |
| Teclado BT 5.0 (`E2:83:23:17:B8:08`) | Bluetooth LE | Baixo |
| Archer T3U | Wi-Fi 5 GHz (canal 161) | Fora da banda |
| Webcam Logitech C920 | Nenhum (USB) | — |
| Ethernet | Nenhum (cabo) | — |

**Nenhum item precisa ser removido.** O que muda é onde cada antena mora.

### A conta que decide tudo

Medição do próprio projeto, em `daemon/subsystems/bt_mic.py`
(A/B no mesmo controle, 25/07/2026):

```
mic DESLIGADO   : input 260.4 Hz   audio   0.0 Hz   total 260.4 Hz
mic LIGADO      : input 170.5 Hz   audio 106.2 Hz   total 276.7 Hz
desligado again : input 274.3 Hz   audio   0.0 Hz   total 274.6 Hz
```

O **total** de pacotes por segundo não se move. O áudio não abre canal novo:
ele ocupa lugar na mesma fila. É a prova de que o gargalo é slot de tempo, e
não largura de banda.

Daí a aritmética:

```
5 controles × 277 pacotes/s   ≈  1.385 transações/s
Um adaptador Bluetooth Classic ≈  1.600 slots/s

→ um dongle só não comporta a mesa cheia com microfone.
→ TRÊS adaptadores = três piconets = 4.800 slots/s.
```

Com três, a folga deixa de ser apertada e passa a ser confortável: dá para
dividir 2 / 2 / 1 e ainda dedicar um adaptador ao teclado Bluetooth, tirando-o
da disputa com os controles.

Isso não é otimização. É o que faz o cenário caber.

> **Detalhe que salva o plano:** o microfone do DualSense aqui trafega dentro
> do canal HID, em agente — **não** por HFP/SCO. Se fosse SCO, a especificação
> limitaria a 3 links SCO por piconet e 4 microfones simultâneos seria
> impossível com qualquer hardware. Sendo HID, o problema é só banda, e banda
> se compra.

---

## 3. Hardware

| Peça | Papel |
|---|---|
| Hub TP-Link UH700, 7 portas, **fonte de 30 W inclusa** | Leva os dongles para cima do rack e os alimenta |
| Cabo Ugreen 30127, USB 3.0, 3 m, macho-fêmea | Liga o PC ao hub |
| 2 × TP-Link UB500 novos (RTL8761BU) | Somados ao UB500 que já estava na máquina |

**São três adaptadores, não dois.** A compra saiu com duas unidades do UB500, e o
que era erro virou o melhor arranjo possível: três dongles idênticos, todos com o
mesmo firmware que já se sabe que carrega limpo nesta máquina. Melhor que a lista
original, que previa dois UB500 mais um genérico de R$ 15 — o genérico era o elo
fraco.

**Sobre o cabo ser USB 3.0.** Não faz diferença de velocidade: o dongle é
full-speed, 12 Mbps, e o SuperSpeed nunca chega a ser ativado com só dongles 2.0
na ponta. Por isso ele também não gera o ruído de 2,4 GHz que um cabo 3.0 com
dispositivo 3.0 geraria. O que se ganha é blindagem e bitola melhores, de graça.


**Por que a fonte externa importa mais que o cabo:** com ela, os dongles são
alimentados pelo hub e o cabo carrega só dados. A queda de tensão dos 3 metros
deixa de existir como variável. Hub sem fonte, com três dongles na ponta de um
cabo longo, é a causa clássica da desconexão aleatória que não aparece em log
nenhum.

**Por que o cabo é USB 2.0 e não 3.0:** o dongle é full-speed (12 Mbps) e
ignora os 5 Gbps. Com o hub alimentado, os dois argumentos a favor do 3.0
(bitola do par de energia e os 900 mA da porta) deixam de valer. Sobra
blindagem — e o StarTech é o único com especificação confirmada em fonte
oficial: 24/28 AWG, folha de alumínio-mylar com malha, garantia vitalícia.

---

## 4. O mapa das conexões

### 4.1 Traseira do PC

```
        ┌──────────────────────────┐
        │  3 ──────┐  │  4  Wi-Fi  │   USB 3.0 (azul)
        │  cabo 3m │  │  Archer    │
        ├──────────┼──┼────────────┤
        │  5 vazia │  │  6 vazia   │   USB 3.0 (azul)
        ├──────────┼──┼────────────┤
        │  7 mouse │  │  8 webcam  │   USB 2.0 (preto)
        └──────────┴──┴────────────┘
                 │
                 └──→ 3 m até o hub, no topo do rack
```

| Porta | Ocupante | Motivo |
|---|---|---|
| **3** (3.0) | Cabo de 3 m → hub | Sai por cima; nenhum rádio fica aqui |
| **4** (3.0) | Archer T3U | Precisa de 3.0; fica no canto oposto ao mouse |
| **5, 6** | Vazias | Zona tampão entre o Wi-Fi e os 2,4 GHz de baixo |
| **7** (2.0) | Dongle do mouse | Diagonal máxima em relação ao Wi-Fi |
| **8** (2.0) | Webcam C920 | É USB 2.0; não desperdiça porta azul |
| RJ45 | Ethernet | Rota principal (métrica 100) |

### 4.2 Frente do PC

```
        ┌───────────┐
        │ 1  teclado│   ← dongle 2,4 GHz do teclado
        │ 2  vazia  │
        │  [ power ]│
        └───────────┘
```

**O teclado fica numa porta direta do PC, nunca no hub.** Hub USB externo nem
sempre é inicializado pelo firmware, e você precisa de teclado no BIOS e nas
telas de recuperação. É a única alocação deste guia que não é sobre rádio.

A porta 2 fica vazia de propósito: os dois dongles empilhados ali estavam a
~1,5 cm um do outro, dois rádios de 2,4 GHz colados. O mouse mudou para a
traseira e ganhou 40 cm de separação.

### 4.3 Hub, no topo do rack

```
   ┌─────────────────────────────────────────────┐
   │ [1]  [2]  [3]  [4]  [5]  [6]  [7]           │  TP-Link UH700
   │                                          │  165 mm de face
   │ UB500          UB500          UB500         │  fonte 30 W
   └─────────────────────────────────────────────┘
      └── 60 mm ──┘   └── 60 mm ──┘
```

| Porta | Ocupante | Atende |
|---|---|---|
| **1** | UB500 #1 | Controles 1 e 2 |
| **2, 3** | Vazias | Separação |
| **4** | UB500 #2 | Controles 3 e 4 |
| **5, 6** | Vazias | Separação |
| **7** | UB500 #3 | Controle 5 e o teclado BT |

Os três são idênticos e intercambiáveis. Como o bond fica preso ao adaptador em
que foi criado, **anote qual endereço ficou em qual porta** — com três unidades
iguais, o BD Address é a única forma de saber quem é quem.

**Use 1, 4 e 7 — pule as intermediárias.** Com passo de ~20 mm entre portas,
isso dá ~60 mm entre dongles: três vezes mais separação do que qualquer hub
compacto de 4 portas oferece. É de graça, e resolve o problema que hubs com
braçadeira de R$ 176 prometem resolver.

### 4.4 Altura

**O fator mais subestimado.** Água absorve 2,4 GHz muito bem, e cinco pessoas
sentadas entre a antena e os controles são cinco obstáculos.

Um dongle na altura do peito atravessa gente. Um dongle acima da linha das
cabeças passa por cima de todo mundo. **Subir 40 cm costuma render mais que
aproximar 5 metros.**

Monte o hub no ponto mais alto que o rack permitir, com linha de visada limpa
até onde as pessoas sentam.

---

## 5. Montagem

1. Desligue o PC.
2. Cabo StarTech na porta traseira **3**.
3. Passe o cabo por trás do rack, subindo. Não deixe correr pelo chão.
4. Hub no topo do rack, ligado ao cabo, **com a fonte de 30 W conectada**.
5. Os três UB500 nas portas **1, 4 e 7** do hub — pulando as intermediárias.
6. Archer T3U na porta traseira **4**.
7. Dongle do mouse na porta traseira **7**; webcam na **8**.
8. Dongle do teclado na porta frontal **1**.
9. Ligue o PC.

### Verificação

```bash
# Todos os adaptadores subiram?
bluetoothctl list

# Firmware carregou sem erro em cada um?
sudo dmesg | grep -i -E "bluetooth|rtl87" | tail -20

# Topologia: quem está em qual controlador?
lsusb -t
```

O esperado, por dongle Realtek saudável:

```
Bluetooth: hci0: RTL: loading rtl_bt/rtl8761bu_fw.bin
Bluetooth: hci0: RTL: fw version 0xdfc6d922
```

---

## 6. Distribuir os controles entre os adaptadores

O BlueZ **não** balanceia carga. Cada bond fica preso ao adaptador em que foi
criado, em `/var/lib/bluetooth/<MAC_DO_DONGLE>/<MAC_DO_CONTROLE>/`, e o
controle sempre reconecta onde tem a LinkKey. Plugar o segundo dongle não move
ninguém sozinho.

### 6.1 Nunca use `hciN` como identidade

A numeração `hci0`/`hci1` **inverte entre boots**, conforme a ordem de
enumeração USB. Use sempre o BD Address, que é estável.

O `scripts/bt_health_watchdog.sh` já carrega a cicatriz disso:

> *"Concatenar 'hci0' fazia a vigia virar no-op MUDO num adaptador hci1 — e
> hci1 acontece nesta máquina."*

### 6.2 Descobrir quem é quem

```bash
bluetoothctl list
# Controller D8:44:89:04:13:C4 Nintendo MeowSystem [default]   ← o UB500 antigo
# Controller XX:XX:XX:XX:XX:XX ...
```

Anote os MACs num papel colado no rack. Com dois UB500 idênticos, o BD Address
é a única forma de distinguir.

### 6.3 Migrar um controle

```bash
# 1. Tirar do adaptador antigo — com o cache junto
bluetoothctl select D8:44:89:04:13:C4
bluetoothctl remove <MAC_CONTROLE>
sudo rm -f /var/lib/bluetooth/*/cache/<MAC_CONTROLE>

# 2. Parear no adaptador de destino (controle em PS + Create)
bluetoothctl
> select <MAC_DO_DONGLE_DESTINO>
> scan on
> pair <MAC_CONTROLE>
> trust <MAC_CONTROLE>
> scan off
```

**O `rm` do cache não é zelo.** É o `SDP-CACHE-01`, que o `scripts/doctor.sh`
já documenta: sem apagar, o pareamento novo nasce com SDP vazio e o BlueZ
recusa a reconexão como *unknown device* — o link cai sozinho e parece defeito
do controle.

### 6.4 Divisão sugerida

Divida pelo microfone, que é o que pesa:

| Adaptador | Ocupantes |
|---|---|
| Hub porta 1 | Controles 1 e 2 (com mic) |
| Hub porta 4 | Controles 3 e 4 (com mic) |
| Hub porta 7 | Controle 5 e o teclado BT 5.0 |

Cada par com microfone consome ~554 transações/s de 1.600 — cerca de um terço do
adaptador. É folga de sobra, e é o que os três dongles compraram.

---

## 7. O que o software já resolve

Nada a ajustar. O levantamento de 21/08 encontrou tudo no lugar:

| Item | Estado |
|---|---|
| Autosuspend USB do dongle | Desligado (`power/control = on`) |
| `btusb enable_autosuspend` | `N` |
| `FastConnectable` | `true` |
| `JustWorksRepairing` | `confirm` |
| `hid-playstation` | Presente via DKMS |
| Firmware `rtl8761bu` | Carrega limpo, sem erro |

**O daemon é agnóstico ao adaptador.** Ele descobre os controles por `hidraw` e
`bustype` — não há `hci0` fixo em lugar nenhum do código Python. Controle
pareado em qualquer dongle funciona sem tocar em uma linha do projeto.

---

## 8. Quando der problema

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Desconexão aleatória, nada no log | Queda de tensão no hub | Confirme que a fonte de 30 W está ligada |
| Um dongle some do `bluetoothctl list` | `btusb` sensível a hub | Plugue esse dongle direto no cabo |
| Controle não reconecta, vira *unknown device* | Cache SDP sujo | `rm` do cache e pareie de novo (§6.3) |
| Input engasga só com mic ligado | Piconet saturado | Mova um controle para outro adaptador |
| Mouse ou teclado falhando | Dois rádios 2,4 GHz colados | Separe os dongles (§4.1) |
| Tudo pior depois de um reboot | `hciN` inverteu | Confira pelo BD Address, não pelo índice |

### Medir em vez de adivinhar

O gargalo é observável. Compare os reports por segundo de um controle sozinho
contra a mesa cheia: se cair muito abaixo dos ~170 Hz que a medição de
referência registra com mic ligado, o piconet daquele adaptador está cheio, e a
cura é redistribuir — não trocar hardware.

---

## 9. Energia

Sem preocupação. RTX 4060 (115 W) mais 5800X (142 W de PPT) mais o resto dá
~350 W em jogo pesado, contra os 600 W da EVGA 600 BR: 40% de folga, dentro da
faixa de melhor eficiência.

O hub alimentado ainda tira a carga dos dongles do rail de 5 V da fonte.

---

## Apêndice: o que não funciona

**Gateways BLE Mesh / Zigbee (Tuya, Smart Life e similares).** Não servem, por
três motivos independentes:

1. O DualSense fala **Bluetooth Classic (BR/EDR + HID)**. BLE Mesh e Zigbee são
   outras pilhas — nenhuma transporta HID.
2. Esses aparelhos **não expõem HCI**. Não são adaptadores Bluetooth: são
   dispositivos de nuvem que só falam com o app do fabricante. Nunca aparecem
   em `hciconfig`, com gambiarra ou sem.
3. Zigbee opera em 2,4 GHz, com canais que se sobrepõem a Wi-Fi e Bluetooth.
   Ligar um na sala **piora** o ruído durante as sessões.

**Repetidor de Bluetooth.** Não existe como categoria de produto, e não por
falta de mercado: o enlace Bluetooth Classic é ponto a ponto, sem camada de
roteamento. Essa ausência é justamente o que garante a latência baixa. Um
repetidor teria de terminar e reabrir o enlace, somando latência exatamente
onde ela dói.

**Placa Wi-Fi AX210 no lugar dos dongles.** Tentador pelo driver `btintel`, mas
resolve o problema errado: continua sendo **um** adaptador, com os mesmos 1.600
slots/s, e as antenas têm pouco mais de um metro de cabo — não chegam ao sofá.
Dois dongles baratos entregam 3.200 slots. A aritmética de slots ganha da
qualidade do controlador.

> Se um dia for instalar um AX210 assim mesmo: no módulo Intel, o Wi-Fi vai por
> PCIe mas **o Bluetooth vai por USB**. Sem o cabo de 9 pinos até o header da
> placa-mãe, o Wi-Fi funciona e o Bluetooth simplesmente não existe. A B450M
> S2H tem 2 headers USB 2.0 — confira se sobra um antes de comprar.
