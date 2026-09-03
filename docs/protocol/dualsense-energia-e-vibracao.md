# DualSense — energia e vibração, o que terceiros já tinham mapeado

**03/09/2026.** Caça em repositórios públicos para preencher duas linhas do
`docs/data/mapa-controles.csv` que estavam com o caminho incompleto:
`energia.bateria.leitura_hefesto` e `vibracao.rumble.frequencia`.

**Grau desta página inteira: `afirmado-no-doc`.** Nada aqui foi ao aparelho.
Ela existe porque *"como é só informação eles trouxeram"* — o contrato é FATO
com ENDEREÇO, nunca código de outra pessoa. As fontes estão fixadas por commit
no fim.

Quando esta página e o
[`dualsense-referencia-canonica.md`](dualsense-referencia-canonica.md)
divergirem, a canônica manda; quando a canônica e o
`assets/dkms/hid-playstation/hid-playstation.c` divergirem, o driver manda —
ele é o que roda nesta máquina.

---

## 1. Bateria — quatro implementações independentes, zero divergência

O byte é o **52 do CORPO** do report de entrada, nos dois transportes. O que
muda é só o tamanho do cabeçalho:

| transporte | report | cabeçalho | o byte cai em |
| --- | --- | --- | --- |
| cabo | `0x01`, 64 B | 1 byte (id) | `report[53]` |
| rádio | `0x31`, 78 B | 2 bytes (id + sequência) | `report[54]` |

Nibble **baixo** = nível, `0x0`–`0x0A`. Nibble **alto** = estado de carga.
Porcentagem = `min(nível*10+5, 100)` — satura em 100 porque o nível para em 10.

| nibble alto | estado |
| --- | --- |
| `0x00` | descarregando |
| `0x01` | carregando |
| `0x02` | cheio |
| `0x0A` | tensão anormal |
| `0x0B` | temperatura anormal |
| `0x0F` | erro de carga |

**As quatro fontes, e nenhuma copia a outra:**

| fonte | onde | o que diz |
| --- | --- | --- |
| driver desta máquina | `hid-playstation.c:175-176`, `:1724-1725`, `:1733` | os dois `GENMASK` e a conta |
| SDL | `SDL_hidapi_ps5.c:129`, `:1432` | `ucBatteryLevel // 52`, e a mesma conta |
| pydualsense | em `readInput` | `states[53]` no cabo, `states[54]` no rádio |
| DS5Dongle | `utils.h:242-243`, `:152-159` | os dois nibbles **e o enum com os seis estados** |

**O que o DS5Dongle acrescentou, e esta casa não tinha escrito:** a FAIXA do
nibble baixo (`0x00`–`0x0A`) — que é a razão de a conta saturar — e o nome dos
seis estados, incluindo os três de erro. Os três códigos de erro são exatamente
os que o driver trata.

**A pydualsense está certa nos dois transportes para ESTE byte**, e vale dizer
por quê: ela normaliza o envelope antes de indexar (`states` descarta um byte no
Bluetooth). Ela **não** faz isso para giroscópio e touchpad, que indexam o
buffer cru — mas esse não é o assunto desta página, e o produto não depende
disso.

---

## 2. Frequência do rumble — a resposta é NÃO, e o não é demonstrável

**Não existe campo de frequência por motor no report de saída do DualSense.**

A prova é de **completude**, não de busca fracassada. Os **47 bytes** do corpo
estão nomeados um a um por três linhagens que não se copiam — o driver desta
máquina, o `SpecialK` e a família `DS5Dongle` — e o único byte que ninguém sabe
o que faz é o **40**. Nenhum dos 47 é frequência.

O que existe no lugar são **dois bits**, e os dois estão no mapa agora:

| o quê | byte do corpo | cabo (`0x02`) | rádio (`0x31`) | autorizado por |
| --- | --- | --- | --- | --- |
| modo da emulação (v1 → **v2**) | 38, bit 2 | `report[39]` | `report[41]` | — |
| **filtro passa-baixa** dos haptics | 39, bit 0 | `report[40]` | `report[42]` | `valid_flag1` bit 5 |
| amplitude por motor (não é frequência) | 2 e 3 | `report[3]`, `report[4]` | `report[5]`, `report[6]` | `valid_flag0` bit 0 |

Frequência de verdade neste aparelho é **forma de onda**, e ela entra pelo
caminho de **áudio** (canais 3-4 por USB) — outra chave do mapa,
`vibracao.haptics_vcm`.

### O efeito de amplitude da v2, em que duas fontes independentes concordam

Na emulação **v1** a força é para ir pela **metade**; na **v2**, o byte inteiro.
A SDL desloca o byte de um bit quando não está na v2; o `SpecialK` anota o mesmo
no campo `EnableRumbleEmulation`, com as palavras *"suggest halving rumble
strength"*. São dois projetos que não se copiam dizendo a mesma coisa.

---

## 3. O que é NOVO para esta casa

Quatro fatos, todos do lado da vibração, nenhum medido:

1. **`valid_flag2` bit 3 = `UseRumbleNotHaptics2`** — o gêmeo v2 do
   `valid_flag0` bit 1. O driver desta máquina **não tem constante para ele**.
   Quem o identificou diz tê-lo visto no tráfego de um jogo.
2. **Byte 39 bit 0 é o filtro passa-baixa dos haptics**, autorizado pelo
   `valid_flag1` bit 5. A canônica já trazia essa linha **sem fonte**; agora
   tem, e de uma família que se corrigiu em público — a nota antiga dela dizia
   que o filtro era o byte 40, e o próprio projeto registrou que estava
   deslocada de um.
3. **O aparelho DEVOLVE se o filtro está ligado**: bit 1 do byte **54** do
   report de ENTRADA. Esta árvore não lê esse byte — o leitor conhece o 52 e o
   53 e para aí.
4. **O byte 9 não é só o mudo do microfone.** Os oito bits têm nome, e dois são
   de vibração: bit 2 = `HapticPowerSave`, bit 7 = `HapticMute`. O driver desta
   máquina só escreve o bit 4.

---

## 4. As três contradições, sem escolher lado por conveniência

### 4.1. O limiar de firmware da v2 — 0x0215 contra 0x0224

Os três leem o **mesmo campo**: um `u16` little-endian no byte 44 do report de
firmware (`hid-playstation.c:1302`).

| fonte | limiar | como está escrito |
| --- | --- | --- |
| driver desta máquina | **0x0215** | `DS_FEATURE_VERSION(2, 21)`, que empacota o minor DECIMAL 21 (`hid-playstation.c:1920`) |
| SDL | **0x0224** | literal hexadecimal, com o comentário *"on 2.24 firmware and newer"* |
| SpecialK | **0x0224** | *"requires FW >= 0x0224"* |

Entre `0x0215` e `0x0223` o Linux liga a v2 e os outros dois não.

**Qual eu acho certo:** o `0x0224`. A versão do firmware é exibida em
hexadecimal, e `0x0224` lido assim é literalmente "2.24"; o macro do driver lê
"2.21" mas produz `0x0215`, que na mesma convenção seria "2.15". Isso tem cara
de conversão decimal/hexadecimal perdida no caminho.

**Mas não decide nada**, por duas razões: o driver é o que roda na máquina dela,
e o Edge não passa por esse teste em nenhuma das fontes (é sempre v2). **É
ensaio de um comando:** ler o report de firmware dos dois controles dela e ver
de que lado dos dois limiares eles caem.

### 4.2. O byte 36 — dois nibbles de redução de potência, e ninguém sabe quem é quem

O byte 36 (`reduce_motor_power` no driver) tem **dois campos de 4 bits**: uma
redução para o rumble e outra para os motores do gatilho, em passos de **12,5%**.
Qual nibble é de qual está **contestado**:

| fonte | rumble | gatilho |
| --- | --- | --- |
| SpecialK, dualsense-go | nibble **ALTO** | nibble baixo |
| família DS5Dongle | nibble **BAIXO** | nibble alto, faixa `0x0`–`0x0A` |

São duas linhagens de igual porte e nenhuma mediu na frente da outra. **Por
isso a atribuição não foi escrita no mapa** — só a existência dos dois campos e
o passo de 12,5%.

### 4.3. O byte 40 continua sem dono

É o único dos 47 que ninguém nomeia. Foi confundido com o filtro passa-baixa e
a correção está registrada em público.

---

## 5. O que a internet NÃO sabe — a lista para a bancada

Estas perguntas não têm resposta em repositório nenhum. Elas só se respondem
com o aparelho na mesa:

1. **Qual a frequência, em Hz, de cada emulação.** Ninguém publicou a medida.
   Os atuadores são voice-coil e a emulação é forma de onda gerada pelo
   firmware; nenhum projeto mediu com microfone ou acelerômetro.
2. **O que o filtro passa-baixa faz de audível.** Existe o bit, existe a
   autorização e existe a devolução no report de entrada. Não existe uma
   descrição do efeito.
3. **Se o passa-baixa alcança a emulação de rumble ou só o áudio háptico.** Os
   dois passam pelos mesmos atuadores, mas isso é dedução, não medida.
4. **Se `UseRumbleNotHaptics2` faz algo diferente do bit 1 do `valid_flag0`.** A
   única anotação que existe diz que o efeito é o mesmo.
5. **Qual nibble do byte 36 é do rumble** (§4.2).
6. **A versão de firmware dos controles dela** (§4.1).
7. **O byte 40** (§4.3).

---

## 6. As fontes, fixadas por commit

| projeto | commit | o que foi lido |
| --- | --- | --- |
| `libsdl-org/SDL` | `f443c429c667b752e2809efbdc7315bd4d7f90df` | `SDL_hidapi_ps5.c` — bateria, limiar da v2, amplitude |
| `SpecialKO/SpecialK` | `5e0c979e5a2a3d6168114cb5b6a531faffedf338` | `playstation.cpp` — a struct de 47 bytes comentada bit a bit |
| `awalol/DS5Dongle` | `17385f8beeef17129f0b39d9e5fc2195ea89b322` | `utils.h` — entrada e saída, com o bit 3 do byte 38 |
| `sqlCRT/ds5dongle-bl618-opensource` | `f7e36e1fb13151a7e9d376fe2f74f29cca104185` | `state_mgr.c` — o mapa dos 47 bytes em prosa |
| `nikashan02/dualsense-go` | `de6b07a20b7099d08741f901764f553de862bef5` | `outputReport.go` — a montagem do byte 36 |

O `awalol/DS5Dongle` já era fonte desta casa, no mesmo commit, para a linha
`audio.alto_falante` do mapa.

**Nada aqui é código copiado.** São números, offsets e nomes de campo — o que
ela pediu quando disse que a informação é o que se traz.
