# Bluetooth

O Hefesto trata o cabo e o Bluetooth do mesmo jeito: gatilhos, vibração, luz,
número do jogador, giroscópio, microfone e alto-falante funcionam nos dois. O
que muda é o pareamento, e que o rádio tem um limite de controles por adaptador.

## Parear pela aba Conexões

1. Na aba **Conexões**, clique em **Conectar** no adaptador que vai receber o
   controle.
2. No controle, segure **PS + Create** até a barra de luz piscar rápido.
3. O controle aparece na lista e conecta. Se não conectar, a linha diz «Não
   Conectou», e **Tentar de Novo** reabre a espera.

Nas próximas vezes, um toque no PS liga o controle e ele volta sozinho.

Com mais de um adaptador, a aba Conexões também move um controle de um adaptador
para outro. Quantos controles cabem em cada um, e como dividi-los, está em
[bluetooth-varios-adaptadores.md](bluetooth-varios-adaptadores.md).

## Parear pelo terminal

```bash
bluetoothctl
power on
agent on
default-agent
scan on
# segure PS + Create no controle até a barra piscar rápido,
# e espere aparecer "Wireless Controller" com o endereço
pair  AA:BB:CC:00:00:FF      # o endereço que apareceu
trust AA:BB:CC:00:00:FF
connect AA:BB:CC:00:00:FF
exit
```

Em até cinco segundos o Hefesto encontra o controle; `hefesto-dualsense4unix
status` mostra `transport = bt`.

### Por que o PS + Create

O controle entra em modo de pareamento pelo PS + Create porque ninguém construiu
a alternativa, e não porque o controle a proíba. O DualSense tem uma porta para
gravar o pareamento pelo cabo, o feature report `0x0A` («Set Bluetooth
Pairing»), descrito em
[dualsense-plataforma-e-identidade.md](../protocol/dualsense-plataforma-e-identidade.md),
§3. Três ressalvas:

1. o grau do documento é `afirmado-no-doc`: nenhum byte foi mandado ao controle;
2. o Hefesto não o usa: não está implementado;
3. o próprio documento desaconselha, porque uma escrita mal formada troca o
   pareamento de um controle em uso.

## O que o instalador faz pelo Bluetooth

- ajustes do BlueZ para conectar rápido e parear de novo sem confirmação;
- o adaptador USB sem suspensão no meio do jogo;
- um agente de pareamento do sistema;
- uma cópia dos pareamentos a cada 15 minutos e a cada conexão, em
  `/var/lib/hefesto-dualsense4unix/bt-bonds/`, e um vigia que reinicia o
  Bluetooth quando ele trava.

O `uninstall.sh` desfaz tudo isso. A lista completa está em
[instalacao.md](instalacao.md).

## Quando o pareamento some

O `bluetoothd` pode travar com vários controles e perder pareamentos. No diário
aparece `malloc_consolidate(): unaligned fastbin chunk detected`, e o controle
acende, tenta conectar e desiste (`Refusing input device connect`). O gatilho
observado foi ligar dois controles Nintendo no mesmo instante.

- Ligue um controle por vez e espere ele conectar antes do próximo.
- O instalador oferece o BlueZ 5.86 corrigido
  ([receita-backport-bluez.md](receita-backport-bluez.md)).
- As cópias de pareamento ficam guardadas; `scripts/bt_bonds_restore.sh` as
  devolve. Ele é manual de propósito: se o controle já trocou a chave dele,
  impor a antiga cria um laço de falha.
- Parear de novo sempre resolve.

Um controle pareado pelo Bluetooth e ligado no cabo ao mesmo tempo também pode
perder o pareamento. Quando ele conecta pelo rádio, o Hefesto esquece a cópia que
sobrou em outro adaptador.

## O 8BitDo pelo Bluetooth

Use o modo DirectInput/PS4: nele o 8BitDo se apresenta como um DualShock 4
(`054c:05c4`) e conecta de primeira. No modo Switch (`057e:2009`) ele cai sob
carga pelo rádio. O endereço muda com o modo, então cada modo é um pareamento.
Detalhes em [troubleshooting-8bitdo.md](troubleshooting-8bitdo.md).

## O som pelo Bluetooth

O DualSense não tem perfil de áudio Bluetooth: o microfone e o alto-falante
passam pelo mesmo canal dos comandos do controle, e o Hefesto faz a ponte. A
`libopus` do sistema é necessária para os dois sentidos, e o instalador a
instala.

- **O microfone** de cada controle já vem ligado. Enquanto algum programa o
  escuta, ele divide o rádio com os comandos do controle, e a conta de quantos
  cabem por adaptador muda
  ([bluetooth-varios-adaptadores.md](bluetooth-varios-adaptadores.md)).
- O microfone pelo rádio precisa do módulo `hid-playstation` do Hefesto. O de
  fábrica lê o som como se fossem botões: desliga o microfone em um segundo e
  mexe o cursor sozinho. Sem o módulo (Secure Boot sem a chave inscrita, ou um
  kernel que o Hefesto ainda não conferiu), o Hefesto não liga o microfone pelo
  rádio. Depois de instalar, reinicie o computador.
- **O alto-falante e o fone** do controle recebem o som pelo mesmo canal.

A ponte do microfone pode ser conferida com
`hefesto-dualsense4unix mic bt-status` ([cli.md](cli.md)).
