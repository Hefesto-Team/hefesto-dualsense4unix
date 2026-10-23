# A identidade do pad virtual

Que modelo de DualSense o pad virtual do modo DualSense apresenta a cada jogo, e por quê.
Escrito em 22/10/2026. O código é
`src/hefesto_dualsense4unix/integrations/a_roupa_do_jogo.py` (`_a_regra`).

## A regra

O pad veste o DualSense comum (`054c:0ce6`) só quando as três coisas valem juntas:

1. o jogo nomeia o comum (um perfil do InControl, o `Sony DualSense` do Rewired, o par
   `054c:0ce6` no executável);
2. o jogo não nomeia o Edge (o perfil `…Edge…`, o `DualSense Edge` do Rewired ou da SDL, o par
   `054c:0df2`);
3. nada no caminho do jogo pede o Edge: a biblioteca Sony (`libScePad`, `scePad`,
   `WinDualSense`, `WinDualShock`), o Modo Xbox, a lista do Steam Input, a Launch Option que
   esconde o `0x054c/0x0ce6`.

Em todo outro caso, o Edge (`054c:0df2`). A regra vale igual para os quatro jogadores, no cabo e
no rádio, porque o pad é sempre um aparelho USB virtual (`BUS_USB`) e o transporte do controle
físico não chega ao jogo. Nada se decide por appid, por nome ou por pasta do jogo.

| jogo (22/10/2026) | o que o disco nomeia | roupa | a cláusula que decide |
| --- | --- | --- | --- |
| Sackboy | `WinDualSense`, `0ce6` e `0df2` no executável | Edge | 2: nomeia o Edge |
| Minecraft Dungeons II | `WinDualShock`, só `0ce6` no executável | Edge | 3: a biblioteca Sony |
| Mullet Mad Jack | só os perfis do comum no `global-metadata.dat` | `0ce6` | as três valem |

Nos 43 jogos instalados da biblioteca medida em 22/10/2026, a regra única dá a mesma roupa e a
mesma fonte da escada anterior, linha a linha: ela muda a forma da decisão, não o resultado.

## Por que o Edge é o padrão

O Edge não nasceu pelo Bluetooth. O que se lê na história:

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

O que muda entre os dois modelos, lido no fonte (os trechos estão em
[driver-hid-playstation.md](driver-hid-playstation.md) e
[pilha-steam-input-xpad-sdl.md](pilha-steam-input-xpad-sdl.md), §3.4 e §3.5):

| camada | o Edge (`0df2`) | o comum (`0ce6`) |
| --- | --- | --- |
| `hid_playstation` | vibração v2 sempre | v2 só com o firmware 2.21 ou mais novo |
| `winebus` (Wine e Proton) | o `hidraw` por padrão | o `hidraw` por padrão |
| SDL (HIDAPI PS5) | 17 botões, sensores a 1000 Hz no USB | 13 botões, 250 Hz no USB |
| banco de mapeamentos da SDL da Steam | só uma entrada, de Bluetooth | cinco, cabo e Bluetooth |
| o jogo com tabela própria | só quem conhece o `0df2` | todo jogo do DualSense |
| o gadget USB do Hefesto | sobe | fica no uhid (a quirk `n`) |

Nenhuma linha muda pelo transporte do controle físico: o pad é `BUS_USB` nos dois casos. O
Edge segue padrão porque é o único que sobe no gadget (o contêiner que a biblioteca Sony
procura) e o único que a Launch Option antiga não esconde; o comum entra onde o jogo não
reconheceria o Edge.

## O que a regra não cobre ainda

- A SDL só conta pelo `DualSense Edge`: uma SDL2 anterior ao Edge, que só conhece o comum, cai
  no Edge (nenhum jogo instalado tem uma; não se mediu).
- O jogo de fora da Steam e o jogo sem o wrapper não têm o arme: o pad fica no Edge.
- A roupa não faz o Minecraft Dungeons II vibrar. Ele pede a vibração só pelo GameInput (o Wwise
  Motion, `AkMotion.dll`, exige o `IGameInput` v2 e um aparelho com motores de rumble), e o
  `GameInputCreate` do Proton é stub: com o Edge ou com o `0ce6`, nenhum `SetRumbleState` chega
  ao pad. A cura é uma peça da casa (o GameInput de `assets/gdk-runtime/`), não a identidade.
