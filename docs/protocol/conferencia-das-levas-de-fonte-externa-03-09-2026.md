# A conferência das três levas de fonte externa — 03/09/2026

Três levas saíram para preencher a lacuna da Sony em repositórios públicos:
**entrada** (`fc4f2471`), **luz** (`36056616`) e **energia/vibração**
(`4baf9b23`). Elas mexeram em **doze linhas** do `docs/data/mapa-controles.csv`
e deixaram três documentos novos em `docs/protocol/`.

Este arquivo é a conferência delas. Não caça nada: abre cada fonte citada e
pergunta quatro coisas — **a fonte abre e diz aquilo? contradiz o driver desta
máquina? o grau está alto demais? copiaram código?** — e mais uma: **já estava
na casa?**

**O veredicto curto:** as três levas são de qualidade alta e incomum. Conferi
**cerca de quarenta citações de linha** — no driver, em oito repositórios e numa
wiki — e a esmagadora maioria bate **byte a byte, constante a constante**.
Nenhum achado contradiz o `hid-playstation.c`. Nenhuma linha de código de
terceiro entrou na árvore.

**Mas há um endereço errado no mapa, e ele é do tipo que vira comportamento
errado depois.** É o §1.

---

## 1. O DEFEITO: as costas do DualSense Edge estão no byte errado

**Onde:** `docs/data/mapa-controles.csv`, linha `entrada.botoes@dualsense`,
célula `cabo_offset` (commit `fc4f2471`).

**O que a célula diz:**

> `payload[10] = report[11]` o driver não lê; no DualSense EDGE é onde vivem os
> quatro botões de trás (bits 4 a 7), **segundo o pydualsense**.

**O que a `pydualsense` diz** — a que está instalada na venv desta casa,
`pydualsense/pydualsense.py:324-332`:

| o que ela lê | de onde |
| --- | --- |
| `ps`, `touchBtn`, `micBtn` | `misc2`, bits 0, 1 e 2 |
| `L4`, `R4`, `L5`, `R5` (só `if self.is_edge`) | `misc2`, bits 4, 5, 6 e 7 |

E `misc2 = states[10]`. O `states[10]` é o **byte 10 do report**, que é
`payload[9]` — o **`buttons[2]`** do driver. **É o mesmo byte do PS, do touchpad
e do mudo**, e não o `payload[10]`/`buttons[3]` que a célula aponta.

**A leva se contradiz sozinha:** o documento que ela mesma escreveu acerta.
`docs/protocol/dualsense-report-de-entrada.md:103-105` diz, com todas as letras, <!-- ref-externa: nasce no commit fc4f2471, que está sob conferência numa branch irmã e ainda não foi integrado; esta conferência é escrita ANTES da integração, por definição. Quando as três levas entrarem, o arquivo existe e o marcador sai. -->
que a `pydualsense` lê `buttons[2]` bit4 = L4, bit5 = R4, bit6 = L5 e bit7 = R5.
**O documento está certo; o mapa está errado** — e o mapa é o hub que o resto do
projeto lê.

**O que fica de pé na mesma célula, conferido:** que o driver **não lê**
`buttons[3]` (as três únicas leituras são `buttons[0]`, `[1]` e `[2]`), e que as
três máscaras `DS_BUTTONS2_*` param no bit 2 (`hid-playstation.c:170-172`) — de
modo que as costas de um Edge realmente **não chegam por evdev nesta máquina**.
Esse achado é bom e é novo. Só está pendurado no byte errado.

**O conserto** é trocar, na célula, o `payload[10] = report[11]` pelo
`payload[9] = report[10]` na frase do Edge, mantendo a observação de que o
`buttons[3]` continua sem dono conhecido. Não o fiz aqui: a linha vive numa
branch que ainda não foi integrada, e um conserto meu viraria conflito. **Quem
integrar conserta em um lugar só.**

---

## 2. As fontes que abriram e disseram exatamente aquilo

Esta é a maior parte, e é o motivo do veredicto bom. Cada linha abaixo foi
aberta por mim, hoje, e conferida contra o texto citado.

### O driver desta máquina — 17 citações, todas exatas

`assets/dkms/hid-playstation/hid-playstation.c`:

| citação | o que confirma |
| --- | --- |
| `:149-150` | `DS_FEATURE_REPORT_CALIBRATION 0x05`, 41 bytes |
| `:157-172` | os dezessete `DS_BUTTONS*`, bit a bit |
| `:170-172` | as três máscaras de `buttons[2]`, todas ≤ `BIT(2)` |
| `:183-186` | `MINOR = GENMASK(7,0)`, `MAJOR = GENMASK(15,8)` |
| `:219` | `VALID_FLAG2_COMPATIBLE_VIBRATION2 = BIT(2)` |
| `:295-317` | `struct dualsense_input_report`, com `buttons[4]` |
| `:320-349` | a struct de saída; `static_assert` de **47** bytes |
| `:351-355` | o envelope de rádio: `report_id`, `seq_tag`, `tag` |
| `:1149-1274` | `dualsense_get_calibration_data` — **só giroscópio e acelerômetro** |
| `:1302` | `update_version = get_unaligned_le16(&buf[44])` |
| `:1348-1354` | a leitura de LED devolve RAM do driver, não o aparelho |
| `:1461-1462` | `use_vibration_v2` → `valid_flag2` |
| `:1479-1484` | `common->player_leds = ds->player_leds_state` |
| `:1574-1592` | as âncoras `data[1]` (cabo) e `data[2]` (rádio) |
| `:1605-1623` | qual botão cada bit acende |
| `:1724-1733` | a bateria: nibble alto = estado, baixo = carga, `×10+5` |
| `:1836-1842` | os cinco padrões de jogador |
| `:1920` | `DS_FEATURE_VERSION(2, 21)` |

**A conta do `0x0215` está certa:** `(2 << 8) | 21 = 0x0215`. A leva de
energia fez essa conta à mão e acertou.

### Os repositórios e a wiki

| fonte | citação da leva | conferido |
| --- | --- | --- |
| `nondebug/dualsense` `report-descriptor-usb.txt:88-95` | `0x80` e `0x81` são Feature, 63 B | **exato, linha a linha** |
| idem, `report-descriptor-bluetooth.txt` | os mesmos `0x80`/`0x81` por rádio | **confirmado** (`:112-119`) |
| idem, `README.md` | o mapa de bits do `0x01` de cabo | **exato**, bit a bit |
| idem | o `0x01` de rádio truncado, 10 B | **exato** — ver §3 |
| `dualshock-tools` `ds5-controller.js` | `[12,2]` lê, `[12,1,…]` grava | **exato**, com as quatro validações |
| idem | `[1,1]` reseta, `[3,3]` status da trava | **exato**, com as três constantes |
| idem | `[9,2]` devolve o rádio em `buf[4..]` | **exato** |
| `dualshock-tools` `finetune-modal.js` | a ordem `LL LT RL RT LR LB RR RB LX LY RX RY` | **exato**, e os centros ficam nos índices 8..11 |
| `blog.the.al` (02/04/2024) | `SET 0x80 0x0d 0x03 GG RR BB WW XX YY ZZ` | **exato**, e a citação `"which seems to test…"` é verbatim |
| idem | bateria conectada; GET de 63 B, não 256; *"may brick your controller"* | **exatos, os três** |
| GCC Wiki `Data_Structures` | `43.5 PlayerLightFade`, `43.6 PlayerLightUNK : 2` | **verbatim** |
| idem | `42 LightBrightness`, `38.0 AllowLightBrightnessChange` | **verbatim** |
| idem | `38.3 UseRumbleNotHaptics2`, `39.0 HapticLowPassFilter`, `40 UNKBYTE` | **verbatim** |
| GCC Wiki `Sony DualSense` | Hardware Revisions, Gen `0x03` × `0x04` | **verbatim** — ver §5 |
| `Ohjurot/DualSense-Windows` `DS5_Output.cpp:16,17-22,25-27` | `0x2B` lâmpadas, `0x2A` brilho, fade no bit 5 | **exato** |
| `libsdl-org/SDL` `SDL_hidapi_ps5.c` | limiar `0x0224` com o comentário *"on 2.24 firmware and newer"* | **exato** |
| idem `:128` | `rgucTimer2` nos quatro últimos do `reserved3[12]` | **exato** |
| idem `:522,:537,:545` | o `alt` só liga para clones Nacon e Razer | **exato** |
| `SpecialK` `playstation.cpp:745,749,943` | `0x0224`, o passa-baixa no 39, a devolução no 54.1 | **exato** |
| `awalol/DS5Dongle` `utils.h:363-364,371-382` | `UseRumbleNotHaptics2`, o `UNKBYTE` do 40 | **exato** |
| `nikashan02/dualsense-go` `outputReport.go:55` | os oito bits do byte 9 | **exato** |

---

## 3. O melhor achado das três levas

É da leva de entrada, e resiste a toda conferência: **o `0x01` que o DualSense
emite por rádio antes do modo estendido tem outro desenho.**

Os dois mapas do `nondebug`, lado a lado:

| | cabo, `0x01`, 64 B | rádio, `0x01`, 10 B |
| --- | --- | --- |
| `report[5]` | **gatilho L2** | **hat + botões de face** |
| `report[6]` | gatilho R2 | L1 R1 L2 R2 Create Options L3 R3 |
| `report[7]` | *vendor* | PS, touchpad |
| `report[8]` | hat + face | **gatilho L2** |
| `report[9]` | L1 R1 L2 R2 … | **gatilho R2** |
| `report[10]` | PS, touchpad, mudo | — |

A amostra em repouso que a própria fonte publica — `01 7d 7e 83 82 08 00 00 00
00` — fecha a conta: o `08` (hat neutro) cai no byte 5, onde o cabo tem o
gatilho. **Quem ler o `0x01` de rádio com os offsets do `0x01` de cabo lê o hat
onde estava o gatilho**, exatamente como a leva escreveu.

Uma correção pequena para quem for usar: no `0x01` truncado o terceiro byte de
botão **não tem o mudo do microfone** — a fonte marca o bit 2 dali como
*vendor defined*. São três bytes de botão, mas o terceiro é mais curto.

---

## 4. Grau alto demais — dois casos, e nos dois o problema é a INDEPENDÊNCIA

Nenhuma das três levas escreveu `medido`, nenhuma preencheu `ate_onde_foi`,
nenhuma tocou `provado_em` ou `provado_por`. As três células novas de
`de_onde_sei` dizem `afirmado-no-doc`. **Isso está certo e é para registrar.**

O que está alto é o campo `existe`, nos dois casos em que ele saiu de
`desconhecido`.

### 4.1 `vibracao.rumble.frequencia` → `nao-tem`

A leva justifica assim: *"os 47 bytes do corpo estão nomeados um a um por três
linhagens que **não se copiam** — o driver desta máquina, o SpecialK e a família
DS5Dongle"*.

**Elas se copiam.** A prova é textual e não depende de opinião:

- o erro de digitação `// LED_BRIHTNESS_CONTROL` (falta o `G`) aparece **igual**
  na GCC Wiki (`38.0`), no `DS5Dongle` (`utils.h:371`) e no `SpecialK`;
- o comentário `// previous notes suggested this was HLPF, was probably off by
  1` aparece **igual** na wiki (`40`) e no `DS5Dongle` (`utils.h:382`);
- o comentário do byte 36 do `DS5Dongle` mistura a redação do `SpecialK`
  (`0x0-0x7 (no 0x8?) Applied in 12.5% reductions`) com a da wiki (`0x0-0xA`) —
  numa linha só;
- o `dualsense-go` **declara** a procedência no seu próprio cabeçalho:
  *"References C++ structures defined at https://controllers.fandom.com/…"*.

Ou seja: o inventário dos 47 bytes tem **uma linhagem** (a GCC Wiki) mais o
driver do Linux — não três.

**Isso derruba o `nao-tem`?** Não derruba o fato, mas afrouxa a prova. O
`nao-tem` continua bem apoiado por caminhos que são de fato independentes: o
`static_assert` de 47 no driver, o `Report Count (47)` do descritor HID do
próprio aparelho, e o `DualSense-Windows`, que escreve os mesmos offsets a
partir de outra leitura. O que não se sustenta é a frase *"três linhagens que
não se copiam"* — e ela é justamente a que faz o `nao-tem` soar fechado.

### 4.2 `entrada.stick.calibracao` → `tem`

Três ferramentas são citadas, e a própria leva já avisou que a terceira
(`sense-calibrator`) declara derivar da primeira. Falta dizer que a quarta fonte
— `blog.the.al` — é, como a própria célula reconhece, *"a escrita de engenharia
reversa do mantenedor"* do `dualshock-tools`. **É uma linhagem, não três.**

O `tem` continua defensável: a ferramenta funciona, com aparelho na mesa de
outra gente, e o descritor HID desta casa confirma que `0x80`/`0x81`/`0x82`/`0x83`
existem nos dois transportes. Mas é **um** projeto que sabe fazer isso.

---

## 5. As contradições, conferidas uma a uma

### 5.1 O envelope de rádio: a wiki tem DOIS bytes, o driver tem TRÊS

**A leva da luz está certa, e a conferência a reforça.** O `ReportOut31` da GCC
Wiki tem `ReportID` mais um byte de bitfield (`UNK1`, `EnableHID`, `UNK2`,
`UNK3`, `SeqNo:4`) — dois bytes. O driver tem `report_id`, `seq_tag`, `tag` —
três. A leva escolheu o driver, apoiada na medição desta casa
(`luz.led_microfone`: `common[8] = report[11]`, `medido`, olho dela,
31/08/2026): `11 − 8 = 3`.

**Duas corroborações que a leva não usou e que fecham o caso:**

1. A linha vizinha `luz.lightbar.brilho` já dizia `common[42] = report[45]` —
   diferença de **3**. O mapa já era coerente com o driver.
2. A própria wiki confessa a incerteza **naquela linha**:
   `SeqNo : 4; // increment for every write // we have no proof of this, need to
   see some PS5 captures`.

### 5.2 O `common[42]` é brilho de quem? — A LITERATURA DESEMPATA, E CONTRA NÓS

A leva da luz reportou isto como empate e não mexeu na linha — o que foi o certo
a fazer, porque a linha (`luz.lightbar.brilho@dualsense`) não é do tema dela.
**Mas não é empate.** Fui à fonte que a nossa própria linha cita:

| fonte | o que diz do byte 42 |
| --- | --- |
| **`pydualsense`** — a fonte que a nossa linha cita | `pydualsense.py:808`, docstring: ***"Defines the brightness of the Player LEDs"*** |
| `Ohjurot/DualSense-Windows` | `// Player led brightness`, campo `playerLeds.brightness` |
| GCC Wiki | `LightBrightness` — genérico, não desempata |
| `hid-playstation` | nunca escreve esse byte — cala-se |

**As duas fontes que se pronunciam dizem *player LED*, e uma delas é a que
citamos.** A linha `luz.lightbar.brilho@dualsense` atribui à `pydualsense` uma
afirmação que a `pydualsense` não faz.

Isto **não é defeito desta leva** — a linha é anterior e ninguém a tocou hoje.
Fica registrado aqui porque é o achado mais valioso que a conferência produziu
por conta própria, e porque o conserto é barato: ou a linha muda de nome, ou
ganha a ressalva de que a fonte citada diz outra coisa.

### 5.3 O byte 36: qual nibble é do rumble — e aqui a leva errou a contagem

A leva de energia escreveu: *"SpecialK e dualsense-go põem o rumble no nibble
ALTO, a família DS5Dongle põe no BAIXO"* — e chamou isso de *"duas linhagens de
igual porte, duas contra duas"*.

O que as fontes dizem, conferido:

| fonte | nibble baixo (`36.0`) | nibble alto (`36.4`) |
| --- | --- | --- |
| **GCC Wiki** | `RumbleMotorPowerReduction` | `TriggerMotorPowerReduction` |
| `DS5Dongle` `utils.h:363` | `RumbleMotorPowerReduction` | `TriggerMotorPowerReduction` |
| `ds5dongle-bl618` | rumble | gatilho |
| `SpecialK` `playstation.cpp:734` | `TriggerMotorPowerReduction` | `RumbleMotorPowerReduction` |
| `dualsense-go` `outputReport.go:210` | gatilho | rumble |

**Não é dois contra dois.** É a wiki mais a família do dongle de um lado; e do
outro, dois projetos que **declaram a wiki como sua referência** e saíram
trocados em relação a ela — o `SpecialK` cita a wiki em `playstation.cpp:662`, o
`dualsense-go` no cabeçalho do arquivo. A evidência pende para **rumble no
nibble baixo**.

**A decisão da leva — não escrever a atribuição no mapa — continua certa.** Só a
razão publicada engana: quem ler *"duas contra duas"* vai achar que é cara ou
coroa, e não é.

O passo de **12,5%** está confirmado (`SpecialK`, comentário literal
`Applied in 12.5% reductions`).

### 5.4 O limiar de firmware: `0x0215` contra `0x0224`

**Real, e a leva de energia reportou com precisão.** Conferi as três pontas:

- driver: `DS_FEATURE_VERSION(2, 21)` → `0x0215` (`:1920`);
- SDL: `ctx->firmware_version >= 0x0224`, comentário *"on 2.24 firmware and
  newer"*;
- `SpecialK` e `DS5Dongle`: ambos `requires FW >= 0x0224`.

E os quatro leem o mesmo campo: `u16` little-endian no byte 44 do report de
firmware (driver `:1302`). **Entre `0x0215` e `0x0223` o Linux liga a v2 e os
outros três não.** É ensaio de um comando, sem escrever nada no aparelho.

---

## 6. Copiou código? Não

Os três documentos novos somam 777 linhas e têm **dois** blocos cercados:

1. `SET 0x80 0x0d 0x03 GG RR BB WW XX YY ZZ` — formato de fio, citado do relato
   junto com a aspa do autor;
2. a descrição do par `[12, 2]` / `0x81` em notação da casa, com os quatro
   testes de validação **descritos em prosa**, não transcritos.

Nenhum dos dois é fonte de terceiro. **O contrato dela — *"como é só
informação"* — foi respeitado nas três levas.**

---

## 7. Já estava na casa

Para a próxima leva começar do que já se sabe:

1. **O mecanismo `0x80`/`0x81` com o par `[base, num]` já era medido aqui**, nos
   dois transportes, desde 27/08/2026 — é o caminho da cor do plástico
   (`[1, 19]`, o serial). O que a leva de entrada trouxe de novo é o
   sub-comando `[12, 2]`, não a família. A própria leva diz isso; fica repetido
   aqui porque o mapa não diz.
2. **Os cinco padrões de lâmpada do jogador já saíam do driver desta árvore**
   (`:1836-1842`) e a linha já estava `provado_por = fonte-do-driver` desde
   11/08. O array do SDL é corroboração, não descoberta. O que é novo ali é o
   `PlayerLightFade` no bit 5 e a revisão de hardware.
3. **A prova negativa do feature `0x05`** — que ele é da IMU e só dela — já
   estava escrita na célula `nota` de `entrada.stick.calibracao` desde 11/08.
   A leva a reencontrou lendo o driver. Confirmá-la foi barato e valeu; procurar
   de novo, não.

---

## 8. Erros menores, para o registro

1. **O array de lâmpadas do SDL tem SETE valores, não cinco.** A leva da luz
   citou `0x04/0x0A/0x15/0x1B/0x1F`; o `SetLightsForPlayerIndex` traz também
   `0x11` e `0x0E`. **Não muda a conclusão dela — melhora:** `0x11` = `10001` e
   `0x0E` = `01110` também são palíndromos, então **os sete** padrões do SDL são
   simétricos e nenhum deles serve para detectar o par soldado da revisão
   `0x04`. O argumento dela fica mais forte com o dado completo.
2. **Caminho incompleto do `DualSense-Windows`.** A leva citou
   `src/DualSenseWindows/DS5_Output.cpp`; o caminho real começa em
   `VS19_Solution/`. As linhas (`16`, `17-22`, `25-27`) estão exatas.
3. **Uma atribuição que não existe.** O relatório da leva de entrada afirma que
   *"nondebug diz que [ler a calibração] dispara o modo estendido"*, montando uma
   discordância com o `dsremap`. O `README` do `nondebug` tem 191 linhas e **zero**
   ocorrências de `0x31`, `extended` ou `calibrat`; o repositório tem sete
   arquivos. A discordância não existe do lado do `nondebug`.
   **Isto não chegou à árvore** — a §7 do documento publicado não traz o item.
   Fica anotado para que ninguém vá conferir uma fonte que não fala do assunto.

---

## 9. A régua que esta conferência deixa

`tests/unit/test_a_conferencia_das_tres_levas_de_fonte_externa.py` — oito
testes que leem **a fonte**, não o mapa: o `hid-playstation.c` versionado nesta
árvore e a `pydualsense` que o projeto importa. Ele não depende de rede.

**Ele existe porque um teste que lê o mapa só repete o erro do mapa.** O teste
de `misc2 = states[10]` reprova exatamente o defeito da §1.

As seis mordidas, arrancadas e devolvidas em 03/09/2026:

| o que arranquei | reprovou? |
| --- | --- |
| tirei o campo `tag` do envelope de rádio | sim |
| troquei `led_brightness` de lugar com `player_leds` | sim |
| troquei o limiar `2,21` por `2,36` (= `0x0224`) | sim |
| troquei os 47 bytes do corpo por 48 | sim |
| fiz a `pydualsense` ler `states[11]` — **o erro do mapa** | sim |
| fiz o driver ler `buttons[3]` | sim |

---

## 10. O que só o aparelho responde

As três levas deixaram listas de perguntas em aberto, e elas são boas. As
conferi e não as repito. Acrescento só a ordem em que eu as faria, porque três
delas custam **um comando de leitura** e destravam o resto — e **nenhuma escreve
no aparelho**:

1. **`GET FEATURE 0x20` nos dois controles dela.** Devolve a versão de firmware
   (byte 44) **e** a revisão de hardware. Resolve de uma vez o limiar
   `0x0215`/`0x0224` (§5.4) e diz se a quinta lâmpada daqui é endereçável
   sozinha (§5.1). É o ensaio mais barato das três levas.
2. **Ler o `0x31` cru por rádio e comparar com o `0x01` truncado.** Confirma na
   bancada o desenho da §3 e mede se o `[12, 2]` responde por rádio.
3. **`SET 0x80 [12, 2]` + `GET 0x81`** — leitura pura, a metade inócua. Dá os
   doze valores de uma unidade concreta, que ninguém publicou.

A metade de **escrita** do `0x80` não entra em ensaio nenhum sem a palavra dela:
é a mesma família em que `[1, 1]` reseta o aparelho.
