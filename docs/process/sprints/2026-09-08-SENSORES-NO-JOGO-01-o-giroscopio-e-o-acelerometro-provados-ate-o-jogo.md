---
sprint: SENSORES-NO-JOGO-01
estado: feita
posse:
  SENSORES-NO-JOGO-01:
    - scripts/ensaios/o_jogo_para_de_ver_o_giro.py
cria:
  - docs/process/2026-09-09-OS-SENSORES-ATE-O-JOGO-o-que-a-bancada-mediu.md
bancada: true
depois_de: []
nao_toca:
  - docs/data/ensaios.csv
  - docs/data/mapa-controles.csv
  - src/
---

> **COSTURADA EM 13/09/2026** na `onda/1309` (triagem das branches entregues):
> o ensaio e o laudo entraram sem tocar `src/`. O que sobra NÃO é desta sprint:
> o passo 7 (o jogo REAGIU, com o olho dela) é da MESA-DE-QUATRO-01, e o zero em
> Modo Virtual virou a sprint de produto
> [SENSORES-NO-JOGO-02](2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md),
> como a §4 mandava. A nota de 12/09 que a mantinha aberta cumpriu o papel dela.

# SENSORES-NO-JOGO-01 — o giroscópio e o acelerômetro, provados até o JOGO

> **ESTADO 2026-09-10: feita** — medido na bancada: os dois sensores chegam
> íntegros ao vpad nos dois transportes (250 relatórios/s, 222 valores
> distintos de giro), e em Modo Virtual **a libSDL2 2.30.0 do sistema** abre
> o vpad por evdev e responde `HasSensor=False`, não é decimação. Em Modo
> Nativo o mesmo instrumento recebe 96 amostras de giro e 586 de
> acelerômetro. O laudo é
> [OS SENSORES ATÉ O JOGO](../2026-09-09-OS-SENSORES-ATE-O-JOGO-o-que-a-bancada-mediu.md).
>
> **FATO SUBSTITUÍDO em 13/09/2026** —
> [SENSORES-NO-JOGO-02](2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md):
> esta nota atribuía ao jogo o zero em Modo Virtual. O zero é da 2.30.0 da
> Ubuntu, que o ensaio carregava e que nenhum jogo da Steam carrega; nas
> bibliotecas dos runtimes da Steam o mesmo vpad expõe e entrega os dois
> sensores pelo evdev.

**A dúvida é dela, 08/09/2026:** *"tambem tenho duvidas se a função giroscopio e acelerometro funcionam de fato."* <!-- noqa-acento: citação literal dela, palavra por palavra -->
E, na mesma noite, a pergunta que a NADA-MOCKADO-01 guarda: *"e serão
reconhecidos in game?"*

**A dúvida tem razão de ser, e o mapa a explica em uma linha:** os sensores
estão **medidos até o vpad** e **nunca medidos no jogo**. A escada de entrada do
mapa (`O JOGO RECEBEU` → `O JOGO REAGIU`) existe desde 19/08 e tem **zero
células** em toda a família `movimento` — em todo o mapa, aliás.

## §1 — O que «funciona» quer dizer, em três degraus — e o que cada um tem HOJE

| degrau | célula | o que está medido |
| --- | --- | --- |
| **1. aparelho → daemon** | `movimento.giroscopio@dualsense` cabo e rádio: `medido`, 15/08 (E-8, `scripts/ensaios/giro_e_buraco.py`) | parados na mesa, \|w\| mediano 0,9–1,6 °/s com a régua do feature 0x05 de cada unidade; o acelerômetro do MESMO report 0,98 g; **o transporte foi inocentado** (a mesma unidade no rádio de manhã e no cabo à noite: ≤ 0,06 °/s de diferença). E desde 04/09 os QUATRO publicam `sensores` — antes só o primário (`inputs: null` nos outros) |
| **2. daemon → vpad** (máscara DualSense, `uhid`) | `movimento.giroscopio.jogo@dualsense`: cabo `medido` 19/08, rádio `medido` 16/08 | rádio: os bytes 16-27 do report de 64 B do vpad VARIAM (é por onde o `winedevice.exe` lê); o vpad entrega **~37 %** dos eventos do físico e *"ninguém sabe se é decimação legítima ou perda"*. Cabo: 36 % das amostras caíam por um teto mal contado, curado em 19/08 — **"ainda NÃO reconferido no aparelho depois da cura"**. `movimento.acelerometro.jogo@dualsense`: só `inferido-do-codigo` |
| **3. vpad → jogo** | `O JOGO RECEBEU` · `O JOGO REAGIU` | **zero células.** E há um precedente no mesmo caminho: o touchpad, medido íntegro até o vpad em 16/08, e *"dentro do jogo o touchpad não responde no rádio"* — palavras dela, sem causa até hoje |

## §2 — O que já se sabe do degrau 3, e é o que faz a dúvida dela ser a certa

Medido em 04/09 com SDL 2.30 headless, um DualSense no cabo
(`core/virtual_motion.py`, a tabela do cabeçalho):

| caminho | Nativo | Virtual (uhid, máscara DualSense) |
| --- | --- | --- |
| o que o SDL abre | `/dev/hidraw` do FÍSICO, por HIDAPI — **`tem_giro=true`, 192 valores distintos em 2 s** | `event21`/`event25` — **por evdev** |
| o `hidraw` do vpad | não existe | `0660` + ACL, 249 relatórios/s — **e o SDL não o abriu** |

**A tabela registra o que o SDL abriu, não se o giro chegou por ali.** A
hipótese que esta sprint levou à bancada: **em Virtual, um jogo SDL abre o vpad
por evdev e NÃO recebe giroscópio** — apesar de o vpad estar entregando os
bytes certos no report HID. A bancada de 10/09 a confirmou só na libSDL2 2.30.0
do sistema.

**FATO SUBSTITUÍDO em 13/09/2026** (SENSORES-NO-JOGO-02): este parágrafo se
apoiava no ensaio, que dizia que o SDL não lia o nó evdev «Motion Sensors». O
SDL o casa ao gamepad da mesma peça pelo `uniq`, e nas bibliotecas dos runtimes
da Steam o vpad aberto por evdev expõe e entrega os dois sensores.

**E as máscaras decidem sozinhas metade da resposta**, antes de qualquer
bancada (`integrations/ponte_escada.py`, cabeçalho; `virtual_pad._try_uhid`,
`:285`):

| máscara | o vpad | movimento |
| --- | --- | --- |
| **DualSense** (`054c:0df2`) | `uhid`, report `0x01` com a janela de motion | é o ÚNICO caminho com giroscópio em Virtual |
| **Xbox 360** (`045e:028e`) | `uinput` | *"o pacote do Xbox 360 é fixo desde 2005, sete eixos"* — **não há onde pôr** |
| **Nintendo Pro** (`057e:2009`) | `uinput` (o `uhid` só nasce para `dualsense`) | idem — **não há onde pôr** |
| **Nativo** | não há vpad | o jogo lê o `hidraw` do físico; o daemon não está no caminho |

A decisão dela de 04/09 — *"ele tem que funcionar de verdade. ambos
independente do modo e da mascara"* — foi cumprida no INTERRUPTOR (o desligar
alcança os dois modos). A ENTREGA não pode ser independente da máscara, porque
o aparelho que a máscara imita não tem giroscópio. Isso é **decisão a
registrar no mapa como decisão**, não dívida — e a tela não confessa
(decisão dela de 07/09).

## §3 — A BANCADA, e ela é a hora dela

Instrumento: `scripts/ensaios/o_jogo_para_de_ver_o_giro.py` — SDL2 headless,
abre os controles como um jogo abre, conta amostras DISTINTAS de giroscópio e
de acelerômetro, e repete depois de `sensor.set` desligar. **Nada nasce na tela
dela.** Reserve a bancada antes: ele abre os controles.

| # | condição | o que se espera | o que decide |
| --- | --- | --- | --- |
| 1 | Nativo · cabo | giro e acelerômetro chegam por HIDAPI (é o 04/09 de novo) | controle POSITIVO |
| 2 | Nativo · rádio | idem | o transporte no degrau 3 |
| 3 | Virtual · **DualSense** · cabo | **a pergunta desta sprint** — chega por evdev? por HIDAPI no vpad? | `movimento.giroscopio.jogo@dualsense` e `.acelerometro.jogo` ganham `O JOGO RECEBEU` ou perdem o `sim` |
| 4 | Virtual · **DualSense** · rádio | idem | idem, no outro lado |
| 5 | Virtual · **Xbox 360** | zero amostras | controle NEGATIVO — se chegar giro aqui, o instrumento está lendo o físico |
| 6 | o degrau 2, reconferido | `evtest` no nó do espelho contra o do físico, 25 s | fecha o *"ainda NÃO reconferido depois da cura"* de 19/08 |
| 7 | **`O JOGO REAGIU`**, com um jogo que USA giroscópio | ela mira com o controle e o jogo vira | só fecha com `olho-dela` — a régua não lê o estado de um jogo sob Proton |

E, para o **7**, o instrumento irmão: `scripts/ensaios/o_jogo_segura_o_nosso_no.py`
diz se o processo do jogo abriu o NOSSO nó (pelo inode, em `/proc/<pid>/fd`) ou
foi abrir o físico por fora — é o critério escrito de `O JOGO RECEBEU`.

**O jogo do passo 7 é escolha dela** — precisa ser um que tenha mira por
giroscópio; sem isso o passo não mede nada.

## §4 — O que sai daqui

* o documento de `cria:` com a tabela acima preenchida, hora a hora;
* as células do mapa e a linha do caderno são escritas por **quem coordena a
  bancada** (é a §3 da
  [MESA-DE-QUATRO-01](2026-09-06-MESA-DE-QUATRO-01-quatro-dualsense-por-cabo-e-por-radio-com-ela.md)),
  não por esta sprint — por isso `nao_toca` os dois CSV;
* se o passo 3 der ZERO por evdev e o vpad estiver íntegro: **nasce uma sprint
  de produto** (o SDL tem de abrir o vpad por HIDAPI, ou o vpad tem de existir
  de outra forma), com a medição desta bancada como §1.

## §5 — O que MORDE

* em Virtual, `sensor.set` desligar o giroscópio → as amostras do SDL param
  **no mesmo minuto** (é o teste que o instrumento já faz);
* em Nativo, o mesmo comando → o instrumento tem de dizer o **limite** (o
  daemon não está no caminho), não «aplicado»;
* o controle negativo (Xbox) tem de dar zero. Instrumento que acha giro na
  máscara Xbox está olhando para outro nó.

## Critério de pronto — por cabo · por BT · no perfil · por controle

É a régua dela de 08/09 ([CABO-BT-PERFIL-CONTROLE-01](2026-09-08-CABO-BT-PERFIL-CONTROLE-01-a-regua-de-pronto-de-toda-feature-da-tela.md)); a sprint só fecha com as quatro respondidas.

| | |
| --- | --- |
| cabo / BT | é o que a bancada mede (passos 1-4): o transporte está inocentado até o daemon; até o JOGO, nunca medido em nenhum dos dois |
| no perfil | ✓ `ControllerSensoresOverride` (`giroscopio`, `acelerometro`) |
| por controle | ✓ o interruptor é por peça (`core/virtual_motion.py`, registro por `uniq`); pronto = desligar o giro do P3 e o jogo parar de ver SÓ o P3 |
