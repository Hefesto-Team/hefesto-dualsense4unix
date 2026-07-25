# Forense de 25/07/2026 — o cabo que parou de enumerar e os 163 mil CRC do Bluetooth

> **O que este documento é.** O registro medido de duas falhas distintas que
> apareceram juntas e foram confundidas uma com a outra: o DualSense deixou de
> conectar por cabo, e o DualSense conectado por Bluetooth passou a perder
> pacotes em massa. São causas diferentes, em camadas diferentes, e nenhuma das
> duas é do Hefesto. O valor deste texto está nos números datados — não na
> conclusão, que pode mudar quando houver mais medição.

## O relato que abriu a investigação

> "ele não está conectando via cabo, nenhum dos DualSense, imagino que algum
> teste esteja ativado e motivando isso"

A hipótese embutida no relato — "algum teste ativado" — foi **refutada por
medição**, e a refutação é o achado mais útil aqui: quando o kernel não registra
o dispositivo, nenhuma configuração de espaço de usuário pode ser a causa.

## Método

Todos os números vêm do journal do kernel da máquina de desenvolvimento
(`journalctl -k -b <n>`), que nesta instalação **é persistente entre boots** —
quinze boots disponíveis, de 21/07 a 25/07. Isso permitiu datar a regressão em
vez de apenas descrevê-la.

O comando que separa "o Hefesto rejeitou" de "o kernel não viu" é a busca pelo
identificador do fabricante no barramento:

```bash
journalctl -k -b <n> | grep -c "idVendor=054c"
```

Se esse contador é zero, o dispositivo **nunca se apresentou**. Não há regra de
udev, política do broker, filtro do daemon ou suíte de testes capaz de produzir
esse resultado: todos eles agem depois da enumeração.

## Achado 1 — o cabo: a porta não energiza

### A regressão tem data

| boot | terminou em | DualSense por USB | DualSense por Bluetooth |
|---|---|---|---|
| -6 | 24/07 15:38 | **4** | 34 |
| -5 | 24/07 17:36 | 0 | 0 |
| -4 | 25/07 00:00 | 0 | 7 |
| -3 | 25/07 03:00 | 0 | 24 |
| -2 | 25/07 15:25 | 0 | 35 |
| -1 | 25/07 15:31 | 0 | 2 |
| 0 | em curso | 0 | 2 |

A última enumeração bem-sucedida por cabo foi em **23/07 às 22:56**, dentro do
boot -6, e foram dois controles em sequência:

```
jul 23 22:56:15 usb 3-1: New USB device found, idVendor=054c, idProduct=0ce6
jul 23 22:56:25 playstation 0003:054C:0CE6.0018: hidraw4: USB HID v1.11 Gamepad
                [Sony Interactive Entertainment DualSense Wireless Controller]
                on usb-0000:0c:00.3-1/input3
jul 23 22:56:29 usb 3-4: New USB device found, idVendor=054c, idProduct=0ce6
jul 23 22:56:40 playstation 0003:054C:0CE6.0019: hidraw5: ... on usb-...-4/input3
```

Detalhe que orienta o teste: naquele dia os dois estavam no **barramento 3**
(`usb 3-1` e `usb 3-4`).

### A mensagem do kernel

Nos boots em que a conexão falhou, o kernel registrou 24 vezes:

```
usb usb1-port3: Cannot enable. Maybe the USB cable is bad?
usb usb1-port4: Cannot enable. Maybe the USB cable is bad?
```

Distribuição por boot:

| boot | ocorrências | portas |
|---|---|---|
| -6 a -3 | 0 | — |
| -2 | 20 | `usb1-port4` (11:52), `usb1-port3` (15:20) |
| -1 | ~10 | `usb1-port3` (15:28), `usb1-port4` (15:28, 15:29) |
| 0 | 4 | `usb1-port4` (15:32, durante o boot) |

`Cannot enable` é emitido pelo núcleo USB (`drivers/usb/core/hub.c`) quando o
*hub* falha repetidamente em habilitar a porta depois do reset. O dispositivo
nunca chega a responder ao descritor. A sugestão de cabo ruim é literal e vem do
próprio kernel, não de interpretação.

**As portas afetadas pertencem ao barramento 1** — não ao barramento 3, onde a
conexão funcionava em 23/07.

### O que foi descartado, e por quê

- **Regra udev que desautoriza áudio USB** (`75-...-disable-usb-audio.rules`):
  não está instalada nesta máquina. Verificado em `/etc/udev/rules.d/`.
- **Quirks de cmdline**: `usbcore.quirks=054c:0ce6:gn,054c:0df2:gn` está
  presente, mas estava igualmente presente no boot -6, quando o cabo funcionava.
  O mesmo vale para `usbcore.autosuspend=-1`.
- **Suíte de testes / modo fake**: agiria depois da enumeração e não deixaria o
  contador de `idVendor=054c` em zero.
- **Broker de hidraw**: idem — ele esconde ACL de um `hidraw` que precisa existir
  primeiro.

### Fator ambiental que merece registro

No boot atual, um adaptador WiFi USB migrou entre quatro portas em dois minutos:

```
15:32:37 usb 4-2: new SuperSpeed ... 2357:012d
15:32:39 usb 4-2: USB disconnect
15:32:43 usb 1-6: new high-speed ... 2357:012d
15:32:58 usb 1-6: USB disconnect
15:34:39 usb 3-3: new high-speed ... 2357:012d
15:34:41 usb 3-3: USB disconnect
15:34:41 usb 4-3: new SuperSpeed ... 2357:012d
```

Esse mesmo adaptador já está registrado em investigação anterior como gerador de
degradação de rádio. Aqui ele importa por outro motivo: indica **disputa por
porta física**, e a troca de porta é justamente a variável que separa o
barramento que funcionava do que falha.

### Próximo passo de medição

O experimento que decide é trivial e ainda **não foi executado**: plugar o
controle numa porta do barramento 3 e observar o journal. Três resultados
possíveis, com leituras distintas:

1. **Enumera** — o problema é a porta ou o cabo do barramento 1, não o controle.
2. **`Cannot enable` também no barramento 3** — o cabo é o suspeito principal;
   trocar o cabo é o teste seguinte.
3. **Enumera e cai depois** — aí sim entra a classe de falhas já conhecida do
   projeto (enumeração da interface de áudio sob carga), e o quirk passa a ser
   relevante.

Sem esse dado, qualquer conserto em software seria adivinhação.

## Achado 2 — Bluetooth: 163.925 falhas de CRC num único boot

### O número

```
playstation 0005:054C:0CE6: DualSense input CRC's check failed
```

| boot | ocorrências |
|---|---|
| -6 | 20 |
| -5 | 0 |
| -4 | 3 |
| -3 | 20 |
| **-2** | **163.925** |
| -1 | 0 |
| 0 | 0 |

O boot -2 (25/07, das 10:20 às 15:25) concentra sozinho **99,97%** de todas as
falhas registradas. Ele tem 167.577 linhas de kernel contra 1.290 a 6.586 dos
demais — a diferença é inteiramente esse laço.

O prefixo `0005:` do identificador é o barramento HID **Bluetooth** (`0003:`
seria USB). Trata-se de um DualSense conectado por rádio, e a falha é de
integridade do quadro de entrada: o `hid-playstation` calcula o CRC-32 do report
`0x31` e descarta o que não bate.

### O que a medição de rádio mostrou

Com um DualSense conectado, no boot atual:

```
RSSI return value: -30
Link quality: 0
Current transmit power level: 0
```

RSSI de −30 dBm é sinal forte — o controle está perto do adaptador. **Qualidade
de link 0 com RSSI forte é a assinatura de interferência, não de distância.**
Sinal alto e quadro corrompido significam que algo está ocupando o meio, não que
falta potência.

O contexto físico sustenta a leitura: o adaptador Bluetooth (`2357:0604`) e o
adaptador WiFi (`2357:012d`) são do mesmo fabricante, compartilham a faixa de
2,4 GHz e estão em portas do mesmo conjunto de controladores. A coexistência
WiFi/Bluetooth nessa faixa já foi objeto de medição anterior neste projeto.

### Por que isso importa para o objetivo de quatro jogadores

O co-op local de quatro controles depende de rádio para pelo menos parte dos
jogadores. Um enlace que descarta quadros em massa degrada latência de entrada e
janelas de giroscópio de forma difusa — o sintoma que chega ao usuário é "o
controle está travando", sem erro visível na interface. **Nenhuma correção de
software no Hefesto compensa quadro corrompido na camada de enlace**; o que o
projeto pode fazer é *medir e mostrar*, para que a causa não seja atribuída ao
lugar errado.

### O que ainda não se sabe

- Se as 163 mil falhas se concentram numa janela curta (rajada) ou se espalham
  pelo boot inteiro. A distribuição temporal não foi extraída.
- Se havia atividade de WiFi intensa na mesma janela.
- Se o número cai com o adaptador WiFi removido. **É o experimento A/B que
  fecharia a questão, e ele não foi feito.**
- Se o contador de CRC do projeto (exposto pelo diagnóstico) reflete esse mesmo
  laço ou conta outra coisa.

## Conclusões, com o grau de certeza de cada uma

| afirmação | grau |
|---|---|
| O DualSense não enumera por cabo desde 24/07 | **medido** |
| O kernel falha em habilitar as portas 3 e 4 do barramento 1 | **medido** |
| A causa do cabo está abaixo do espaço de usuário | **medido** (contador zero) |
| A causa específica é cabo, porta ou hub | **indeterminado** — falta o A/B |
| Houve 163.925 falhas de CRC por Bluetooth no boot -2 | **medido** |
| A qualidade de link é 0 com RSSI −30 | **medido** |
| A causa do CRC é interferência de rádio | **inferido**, consistente com a assinatura |
| O adaptador WiFi é o interferente | **hipótese** — falta o A/B com ele removido |

## Regra de método que este episódio confirma

Um relato de usuário traz junto uma hipótese de causa, e a hipótese é parte do
relato — não da evidência. Aqui, "algum teste está ativado" apontava para o
espaço de usuário; um único contador do journal mostrou que a falha acontecia
antes de qualquer código do projeto rodar. **Medir a camada mais baixa primeiro
custa um comando e economiza uma auditoria inteira na camada errada.**

---

*Endereços de rádio deste documento estão mascarados conforme a convenção de
anonimato do projeto. Os identificadores de fabricante e produto são públicos e
necessários para reproduzir a medição.*
