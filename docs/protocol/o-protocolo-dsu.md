# O protocolo DSU (cemuhook) que o servidor do Hefesto fala

Só bytes e regras: o que um emulador (Azahar, Dolphin, Cemu) precisa receber
para aceitar o Hefesto como fonte de toque e de movimento. Cada fato leva a
fonte. **Nenhuma linha de código de terceiro está aqui**: o que se leu em
Azahar, Dolphin, Cemu, evdevhook2 e DS4Windows foi o comportamento, e o NOTICE
diz o porquê. Os endereços completos estão em «Fontes» no fim.

O código que segue este documento é o módulo `protocolo_dsu` do `core` (o
pacote, sem I/O) e o `servidor_dsu` do `daemon` (o socket). A decisão da porta é a
`docs/adr/022-udp-26760-compat-dsu.md`; o uso, `docs/usage/emuladores-pelo-dsu.md`.

## 1 · O cabeçalho (16 bytes) e o tipo

Todos os inteiros são little-endian. Fonte: [S1] (especificação), conferida
contra os pedidos que o cliente do Azahar monta [A1].

| offset | tamanho | campo | valor |
| ---: | ---: | --- | --- |
| 0 | 4 | magic | `DSUC` nos pedidos (cliente), `DSUS` nas respostas (servidor) |
| 4 | 2 | versão do protocolo | 1001 (`0x03E9`) |
| 6 | 2 | comprimento | bytes DEPOIS do cabeçalho, contando o tipo de 4 bytes |
| 8 | 4 | CRC-32 | do pacote inteiro, com estes 4 bytes ZERADOS durante o cálculo |
| 12 | 4 | id | do remetente (u32); o cliente do Azahar usa 24872 [A2] |
| 16 | 4 | tipo | ver abaixo |

CRC-32 é o do zlib (polinômio IEEE, o mesmo do `zlib.crc32`) [S1]. O CRC cobre
`16 + comprimento` bytes. A versão que o servidor aceita nos pedidos é só a
1001; a que ele anuncia é a máxima que entende, também 1001.

Tipos que o servidor trata:

| tipo | quem manda | para quê |
| --- | --- | --- |
| `0x100000` | cliente | pede a versão |
| `0x100001` | cliente | pede o estado das portas (slots) |
| `0x100002` | cliente | se inscreve para receber os dados de um slot |

Os tipos `0x110001` e `0x110002` (vibração e motor) existem na especificação
[S1] e **não** são implementados: o servidor os ignora e conta em
`dsu.recusado`.

## 2 · Os pedidos

**Versão (`0x100000`):** sem corpo. Comprimento 4, datagrama de 20 bytes.

**Portas (`0x100001`):** depois do tipo vem um `int32` com a quantidade de
slots pedidos (1 a 4) e, em seguida, essa quantidade de bytes, um por slot (0 a
3) [S1]. O cliente do Azahar manda sempre 4 bytes de slot com a quantidade 1,
então o pedido dele tem comprimento 12 e 28 bytes ao todo [A1]; um pedido com
só o byte necessário tem comprimento 9 e vale o mesmo. Regra do servidor:
comprimento ≥ 4 + 4 + quantidade; quantidade fora de 1..4 ou slot ≥ 4 descarta
o pedido inteiro.

**Dados (`0x100002`):** depois do tipo vêm `flags` (u8), `slot` (u8) e o MAC
do slot (6 bytes). Comprimento exato 12 [S1]. As flags são bits: 0 = todos os
slots, 1 = o slot dado, 2 = o MAC dado, 3 = os dois [S1].

Um pedido vale se tem o magic `DSUC`, a versão 1001, o datagrama tem pelo menos
`16 + comprimento` bytes (o que passar disso é truncado: *drop if too short,
truncate if too long* [S1]) e o CRC confere. O que falhar é descartado, sem
resposta.

## 3 · As respostas

**Versão (22 bytes, comprimento 6):** tipo `0x100000` em 16..19 e a versão
máxima (u16) em 20..21.

**Porta (32 bytes, comprimento 16), um por slot pedido:**

| offset | tamanho | campo |
| ---: | ---: | --- |
| 16 | 4 | tipo `0x100001` |
| 20 | 1 | slot |
| 21 | 1 | estado: 0 desconectado, 1 reservado, 2 conectado |
| 22 | 1 | modelo: 0 não se aplica, 1 sem giro ou parcial, 2 giro completo, 3 reservado |
| 23 | 1 | conexão: 0 nenhuma, 1 USB, 2 Bluetooth |
| 24 | 6 | MAC |
| 30 | 1 | bateria |
| 31 | 1 | zero |

Slot vazio leva o número do slot e zeros nos outros campos [S1]. A resposta
sai na hora: o Dolphin dá o servidor por morto em 1 s sem resposta [D1].

**Dados (100 bytes, comprimento 84):**

| offset | tamanho | campo |
| ---: | ---: | --- |
| 16 | 4 | tipo `0x100002` |
| 20 | 12 | os mesmos 12 bytes da porta (slot, estado, modelo, conexão, MAC, bateria) com o último sendo «conectado» (1) |
| 32 | 4 | contador do pacote (u32), um por cliente |
| 36 | 2 | botões |
| 38 | 1 | home |
| 39 | 1 | botão do touchpad |
| 40 | 4 | analógicos: esquerdo x, y e direito x, y (0..255, neutro 128) |
| 44 | 4 | direcional analógico |
| 48 | 8 | botões analógicos |
| 56 | 6 | toque 1: ativo (u8), id (u8), x (u16), y (u16) |
| 62 | 6 | toque 2, igual |
| 68 | 8 | timestamp em microssegundos (u64) |
| 76 | 12 | aceleração em g: x, y, z (f32) |
| 88 | 12 | giro em graus por segundo: pitch, yaw, roll (f32) |

O Azahar exige o campo de comprimento exato e confere o CRC só no tamanho do
tipo [A3]; por isso a saída tem 100 bytes, sem padding. O Azahar guarda o
último estado e não olha o byte «conectado» [A4].

## 4 · As regras do servidor

- **Cliente = (IP, porta de origem)**, nunca o id. O Azahar usa 24872 no
  cliente, no botão Test e na calibração [A2][A5], e o gcemuhook já erra ao
  indexar por id [G1].
- **Inscrição:** cada pedido de dados renova; vence em 5 s sem renovar, com
  limpeza a cada 1 s (o DS4Windows usa os mesmos 5 s [W1]). O cliente recebe só
  o slot que pediu, porque o Azahar não confere o slot do pacote [A1].
- **Envio:** um pacote por amostra nova, no máximo 250 por segundo por slot, e
  no mínimo um a cada 100 ms: o Test do Azahar espera 8 s por um pacote [A1].
  Sem amostra, o slot com número continua «conectado» e manda um pacote neutro
  (toques inativos, giro e aceleração 0) no ritmo mínimo [J1].
- **Antes de parar um slot** sai um pacote neutro, porque o Azahar guarda o
  último estado: sem ele, um dedo fica «apertado» para sempre [A4].
- **Timestamp:** nunca recua. O kernel recomeça o relógio a cada `hid_device`
  [K1] e o Cemu descarta `timestamp <= último`, integrando um intervalo enorme
  quando passa de 10 s [C1]; por isso o servidor mantém um relógio por slot,
  somando o delta do aparelho só quando vem da mesma época e fica entre 0 e 1 s.
- **Contador:** `max(anterior + 1, milissegundos do relógio monotônico)` com a
  máscara de 32 bits. O campo é u32 [S1].
- **Toque 1 é o contato ativo mais antigo**, a regra da emulação de ponteiro do
  kernel [K2]; o Azahar só lê o toque 1 [A6]. Coordenadas cruas do touchpad do
  DualSense (0..1919 por 0..1079, o que o kernel anuncia [K1]); o Azahar assume
  por padrão (100, 50)-(1800, 850) do DS4 se não houver máximo configurado [A4],
  o que a configuração do uso corrige.
- **Sinais:** aceleração (−x, −y, −z) e giro (pitch, yaw, roll) = (x, −y, −z)
  em relação ao que o kernel entrega [K1]; o evdevhook2 faz a mesma troca para
  este aparelho [E1], e o provedor SDL do Azahar acaba no mesmo sinal [A7].
- **Loopback:** o servidor escuta só em 127.0.0.1. Sem autenticação, como a
  porta do DSX (`docs/adr/003-udp-port-6969-compat.md`).

## 5 · Vetores (para quem implementa o outro lado)

Cliente 24872, slot 0. Pedido de portas (28 bytes) e de dados (28 bytes):

```
portas  44 53 55 43 e9 03 0c 00 c7 5b 8e 33 28 61 00 00 01 00 10 00 01 00 00 00 00 00 00 00
dados   44 53 55 43 e9 03 0c 00 37 89 10 44 28 61 00 00 02 00 10 00 01 00 00 00 00 00 00 00
```

O CRC dos dois confere com `zlib.crc32` sobre o pacote com os bytes 8..11
zerados; é o que o teste `test_o_protocolo_dsu_fala_o_que_o_emulador_aceita` afirma.

## Fontes (lidas, nunca copiadas)

- [S1] Especificação (Unlicense):
  <https://github.com/v1993/cemuhook-protocol/blob/82bf8a837cc7d2254e9257729f462a233d9ad184/README.md>
- [A1] Azahar 2126.1 (GPL-2.0), cliente:
  <https://github.com/azahar-emu/azahar/blob/2126.1/src/input_common/udp/client.cpp>
- [A2] Azahar 2126.1, id do cliente:
  <https://github.com/azahar-emu/azahar/blob/2126.1/src/input_common/udp/client.h>
- [A3] Azahar 2126.1, conferência do pacote:
  <https://github.com/azahar-emu/azahar/blob/2126.1/src/input_common/udp/protocol.cpp>
- [A4] Azahar 2126.1, estado guardado e calibração padrão:
  <https://github.com/azahar-emu/azahar/blob/2126.1/src/input_common/udp/udp.cpp>
- [A5] Azahar 2126.1, o Test e a calibração:
  <https://github.com/azahar-emu/azahar/blob/2126.1/src/citra_qt/configuration/configure_motion_touch.cpp>
- [A6] Azahar 2126.1, o toque que o HID lê:
  <https://github.com/azahar-emu/azahar/blob/2126.1/src/core/hle/service/hid/hid.cpp>
- [A7] Azahar 2126.1, o provedor SDL:
  <https://github.com/azahar-emu/azahar/blob/2126.1/src/input_common/sdl/sdl_impl.cpp>
- [K1] Kernel v6.16 (GPL-2.0), o DualSense:
  <https://github.com/torvalds/linux/blob/v6.16/drivers/hid/hid-playstation.c>
- [K2] Kernel v6.16, emulação de ponteiro dos contatos:
  <https://github.com/torvalds/linux/blob/v6.16/drivers/input/input-mt.c>
- [D1] Dolphin (GPL-2.0+), o cliente DSU:
  <https://github.com/dolphin-emu/dolphin/blob/465c652da1dc/Source/Core/InputCommon/ControllerInterface/DualShockUDPClient/DualShockUDPClient.cpp>
- [C1] Cemu (MPL-2.0), o cliente DSU:
  <https://github.com/cemu-project/Cemu/blob/f3fecba313f146d5cf822491f0b3786ad606fceb/src/input/api/DSU/DSUControllerProvider.cpp>
- [E1] evdevhook2 (GPL-3.0+), os sinais do aparelho:
  <https://github.com/v1993/evdevhook2/blob/95ed74b74804af387b9aeeabe517f360c0dad334/src/DeviceTypes.ini>
- [G1] gcemuhook (Apache-2.0), o defeito do id como chave:
  <https://github.com/v1993/gcemuhook/blob/91ef61cca809f5f3b9fa6e5304aba284a56c06dc/src/Server.vala>
- [J1] joycond-cemuhook (MIT), o pacote neutro:
  <https://github.com/joaorb64/joycond-cemuhook/blob/fc2f29e22640b6615a32941cbdc03d41e3ee6f26/src/joycond_cemuhook/__init__.py>
- [W1] DS4Windows (GPL-3.0), cliente por endereço e prazo de 5 s:
  <https://github.com/hbashton/DS4Windows/blob/36502408cbba17fd20d84e6b258f2258714a39c6/DS4Windows/DS4Control/UdpServer.cs>
- SDL (zlib), de onde vem o fato de o touchpad não passar pelo evdev do SDL:
  <https://github.com/libsdl-org/SDL/blob/release-2.32.10/src/hidapi/linux/hid.c>

## Grau de confiança

- **Medido contra os vetores** de cima e contra os testes do codec: tamanhos,
  offsets, CRC, comprimentos.
- **Lido no fonte, não rodado:** o comportamento de cada emulador (prazo do
  Dolphin, exigência do Azahar, descarte do Cemu). O ensaio no Azahar real é o
  degrau E8 da sprint e fica para a bancada.
