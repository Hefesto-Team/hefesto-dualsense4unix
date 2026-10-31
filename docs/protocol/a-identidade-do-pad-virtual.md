# A identidade do pad virtual

Que modelo de DualSense o pad virtual do modo DualSense apresenta a cada jogo, e por quê.
Escrito em 22/10/2026; a regra se inverteu em 31/10/2026, e no mesmo dia o jogo que conhece os
dois modelos passou a vestir o comum. O código é
`src/hefesto_dualsense4unix/integrations/a_roupa_do_jogo.py` (`_a_regra`).

## A regra

O pad veste o Edge (`054c:0df2`) quando qualquer uma vale:

1. o caminho do jogo pede o Edge: a biblioteca Sony (`libScePad`, `scePad`, `WinDualSense`,
   `WinDualShock`), que procura o contêiner USB da háptica, e só o Edge sobe no gadget; o Modo
   Xbox; a lista do Steam Input; a Launch Option que esconde o `0x054c/0x0ce6`;
2. o jogo conhece o Edge e NÃO conhece o comum.

O disco dá duas marcas independentes, em toda fonte, e o jogo conhece um modelo se qualquer
fonte o conhece:

| fonte | conhece o Edge | conhece o comum |
| --- | --- | --- |
| InControl (`global-metadata.dat`, `InControl.dll`) | um perfil `…Edge…Profile` | um perfil do PS5 ou do DualSense sem `Edge` (os `Hori…` não contam) |
| SDL (`SDL2.dll`, `SDL3.dll`) e `Rewired_Core.dll` | `DualSense Edge` | `DualSense Wireless Controller` |
| os assets do Rewired (`sharedassets<N>.assets`, `resources.assets`) | `DualSense Edge` | `Sony DualSense` sem o ` Edge` logo depois |
| o executável e a `libScePad` | o par `054c:0df2` | o par `054c:0ce6` |

Em todo outro caso (o jogo que conhece os dois modelos, só o comum ou nenhum), o DualSense comum
(`054c:0ce6`), que todo jogo do DualSense conhece: conhecer o Edge numa tabela que também lista o
comum não é pedir o Edge. A fonte da decisão diz quem conhece o quê (`o executável conhece os dois
modelos: o DualSense comum`, `SDL3.dll conhece só o DualSense Edge`) ou, sem sinal, `nenhum sinal
do controle: o DualSense comum`; a fonte que conhece os dois modelos responde pelos dois. A regra
vale igual para os quatro jogadores, no cabo e no rádio, porque o pad é sempre um aparelho USB
virtual (`BUS_USB`) e o transporte do controle físico não chega ao jogo. Nada se decide por
appid, por nome ou por pasta do jogo.

| jogo (31/10/2026) | o que o disco nomeia | roupa | a cláusula que decide |
| --- | --- | --- | --- |
| Sackboy | `WinDualSense`, `0ce6` e `0df2` no executável | Edge | 1: a biblioteca Sony |
| Minecraft Dungeons II | `WinDualShock`, só `0ce6` no executável | Edge | 1: a biblioteca Sony |
| Mina the Hollower | `0ce6` e `0df2` junto do `054c` no executável (a tabela da SDL) | `0ce6` | conhece os dois |
| Um jogo com SDL3 | `DualSense Edge` e `DualSense Wireless Controller` no `SDL3.dll` | `0ce6` | conhece os dois |
| Mullet Mad Jack | só os perfis do comum no `global-metadata.dat` | `0ce6` | conhece só o comum |
| REANIMAL | nenhum sinal do controle | `0ce6` | nada pede o Edge |

Nos 25 jogos instalados da biblioteca medida em 31/10/2026, a inversão troca a roupa de nove,
todos do Edge para o comum e todos sem sinal do controle. Na mesma biblioteca, com 27 jogos,
a leitura das duas marcas troca mais cinco do Edge para o comum, todos com a tabela da SDL que
lista os dois modelos (Mina the Hollower, The Dark Queen of Mortholme, Avatar Legends, Godot
Engine e um jogo com SDL3): ficam no Edge os cinco da biblioteca Sony ou do Steam Input (Sackboy,
Minecraft Dungeons II, Black Myth: Wukong, PRAGMATA e Pro Jank Footy). O único que conhece só o
Edge, o Black Myth: Wukong, já ficava pela biblioteca Sony.

## Por que o comum é o padrão, e onde o Edge fica

O Edge foi o padrão até 31/10/2026, e não nasceu pelo Bluetooth. O que se lê na história:

- **16/07/2026, `389e429ab`:** o pad uhid passou de `0ce6` para `0df2` para ter um
  VID:PID diferente do físico. Com o físico `0ce6` e o pad `0df2`, a Launch Option
  `SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6` esconde só o físico, e o jogo vê um
  controle só, com o layout PlayStation e a vibração (validado no Sackboy, no cabo).
- **16/07/2026, `6d01f6d64` (a Fase 1):** o pad passou a nascer do blueprint canônico embutido,
  sem ler o físico. É ESTE o ganho do rádio: o sono do firmware no Bluetooth (o `EIO` de 5 s)
  deixou de derrubar o pad. O ganho vem do blueprint, e vale para qualquer PID.
- **07/10/2026, `D-0710-O-PAD-E-UM-GADGET-SO-HID`:** o pad sobe num gadget USB só HID, que dá a
  ele o pai USB. Sem o pai, a biblioteca Sony do Sackboy não acha o contêiner da háptica e o
  buffer cresce (o engasgo). O `0ce6` fica no uhid, sem o gadget, porque a quirk `n` do usbcore
  para o par do físico custa 200 ms por pedido ao gadget
  (`D-2210-O-PAD-PODE-VESTIR-O-DUALSENSE-COMUM`).
- **22/10/2026:** com o dono escondendo o físico pelo broker, o pad pode vestir o `0ce6` sem se
  esconder junto (`D-2210-O-PAD-PODE-VESTIR-O-DUALSENSE-COMUM`, que fez caducar a
  `D-0810-PAD-USB-VESTIDOS`); a roupa se lê no disco
  (`D-2210-A-ROUPA-DO-PAD-SE-LE-NO-BINARIO`) e vale só enquanto o jogo roda
  (`D-2210-A-ROUPA-VALE-PARA-O-JOGO-E-VOLTA-NO-FIM`).
- **31/10/2026:** a regra se inverte. O comum é o modelo que todo jogo do DualSense conhece, e o
  Edge, que só o jogo com tabela própria do `0df2` reconhece, fica onde o jogo o nomeia ou onde o
  caminho dele só mostra o Edge.
- **31/10/2026, depois:** «o jogo nomeia o Edge» caducou como cláusula. A leitura do disco
  marcava o Edge sempre que achava o `0df2` e o deixava vencer o comum, e toda tabela da SDL lista
  os dois modelos: o Mina the Hollower e mais quatro caíam no Edge sem pedir. O Edge ficou para o
  jogo que conhece só ele (`D-3110-O-JOGO-QUE-CONHECE-OS-DOIS-MODELOS-VESTE-O-COMUM`).

O que muda entre os dois modelos, lido no fonte (os trechos estão em
[driver-hid-playstation.md](driver-hid-playstation.md) e
[pilha-steam-input-xpad-sdl.md](pilha-steam-input-xpad-sdl.md), §3.4 e §3.5):

| camada | o Edge (`0df2`) | o comum (`0ce6`) |
| --- | --- | --- |
| `hid_playstation` | vibração v2 sempre | v2 só com o firmware 2.21 ou mais novo |
| `winebus` (Wine e Proton) | o `hidraw` por padrão | o `hidraw` por padrão |
| SDL (HIDAPI PS5) | 17 botões, sensores a 1000 Hz no USB | 13 botões, 250 Hz no USB |
| banco de mapeamentos da SDL da Steam | só uma entrada, de Bluetooth | cinco, cabo e Bluetooth |
| o jogo com tabela própria | só quem conhece o `0df2` | todo jogo do DualSense (a tabela da SDL lista os dois) |
| o gadget USB do Hefesto | sobe | fica no uhid (a quirk `n`) |

Nenhuma linha muda pelo transporte do controle físico: o pad é `BUS_USB` nos dois casos. O
comum é o padrão porque todo jogo do DualSense o reconhece; o Edge fica onde ele é o único que
serve: o gadget (o contêiner que a biblioteca Sony procura), o pad Sony que o Modo Xbox e o
Steam Input não mostram, o PID que a Launch Option antiga não esconde e o jogo que conhece só o
`0df2`.

## O que a regra não cobre ainda

- O jogo de fora da Steam e o jogo sem o wrapper não têm o arme: o pad fica no Edge.
- Sem o broker escondendo o físico, a env do comum não se escreve e o pad fica no Edge: o comum
  divide o par com o físico, e o jogo veria os dois.
- O jogo que o cache ainda não leu fica sem env própria até o fio da roupa ler o disco, e quem
  abre nesse intervalo joga com o Edge.
- A roupa não faz o Minecraft Dungeons II vibrar. Ele pede a vibração só pelo GameInput (o Wwise
  Motion, `AkMotion.dll`, exige o `IGameInput` v2 e um aparelho com motores de rumble), e o
  `GameInputCreate` do Proton é stub: com o Edge ou com o `0ce6`, nenhum `SetRumbleState` chega
  ao pad. A cura é uma peça da casa (o GameInput de `assets/gdk-runtime/`), não a identidade.
