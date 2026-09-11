---
sprint: TOUCHPAD-NO-3DS-01
estado: feita
posse:
  TOUCHPAD-NO-3DS-01:
    - scripts/ensaios/o_touchpad_chega_na_tela_de_baixo.py
cria:
  - scripts/ensaios/o_touchpad_chega_na_tela_de_baixo.py
bancada: true
depois_de: []
nao_toca:
  - src/
  - docs/data/ensaios.csv
  - docs/data/mapa-controles.csv
---

> **ESTADO 12/09/2026: continua ABERTA, e o motivo não é falta de
> trabalho.** Ela foi ENTREGUE em `voo/TOUCHPAD-NO-3DS-01-opus` e **não está na costura** —
> medido com `git cherry` contra `onda/0911c`, que não a tem:
>
>   · `a2fcd275bab4` feat(ensaio): o touchpad na tela de baixo do 3DS, medido em quatro deg
>
> Ela ficou de fora da arrumação de estados de 12/09 DE PROPÓSITO:
> carimbá-la `feita` porque existe uma branch faria o trabalho
> desaparecer — ninguém mais abriria essa branch. **O que falta é a
> costura, não o código.**

# TOUCHPAD-NO-3DS-01 — o preço do `ignore`, medido na tela de baixo

> **ESTADO 2026-09-10: feita** — nasceu
> `scripts/ensaios/o_touchpad_chega_na_tela_de_baixo.py`, que mede QUATRO
> degraus e fecha três: o **degrau 0**, que a sprint não tinha (o recurso está
> **DESLIGADO** na configuração do emulador, `use_touchpad=false` e nunca
> tocado — sem ele o dedo não faria nada mesmo com o descritor aberto); o
> **degrau 1** (os dois nós de touchpad existem); e o **degrau 2**, VERMELHO
> como previsto — com a cura, o emulador abre e segura só o nó principal e o de
> movimento do vpad, **zero `hidraw`**. A mordida mediu a outra ponta: sem a
> cura, a janela **nunca nasce** e o que muda é o emulador abrir o **evdev do
> DualSense físico**. O **degrau 3 continua dela** — ROM e dedo. Entrega:
> `docs/process/agentes/2026-09-10/TOUCHPAD-NO-3DS-01-opus.md`. **O `hidraw7`
> do §0 caiu:** o número não é endereço, e com o daemon vivo o `hidraw` do
> físico é `0600 root:root`; o travamento aconteceu três vezes com ZERO
> `hidraw` aberto. Medido no CABO — o rádio não estava na mesa.

**Nasce de uma ressalva escrita e NÃO medida, em 10/09/2026.** A sprint existe
porque a ressalva não pode ficar só em prosa: ou ela vira medição, ou vira
crença.

## §0 — O que foi medido, e o que ficou aberto

O Azahar (emulador de Nintendo 3DS) **não abria janela** nesta máquina. Medido
com `eu-stack` e `/proc`, o processo travado dizia:

```
tid=1852075  futex_do_wait   HIDAPI Rumble       ← a thread travada
fd 53 -> /dev/hidraw7                             ← o DualSense FÍSICO, por rádio
tid=1852045  futex_do_wait   (principal)          ← esperando aquela, para sempre
```

O SDL abria o `hidraw` do DualSense por rádio, a thread de rumble do HIDAPI
prendia num futex, e a principal ficava esperando. Sem erro, sem uma linha no
log do próprio Azahar: o Qt subia inteiro e o processo dormia.

**A cura é UMA variável, e o daemon desta casa JÁ A PUBLICA:**

```
SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6
```

Sozinha basta — provado isolando-a das outras quatro do `default.env`. Com ela,
o Azahar abre, e o que ele passa a ler é exatamente o que este produto entrega:

```
/dev/input/event21   DualSense Wireless Controller (Hefesto P1)
/dev/input/event22   DualSense Wireless Controller (Hefesto P1) Motion Sensors
hidraw               ZERO
```

**Isto é a tese desta casa confirmada num app de terceiro:** o Hefesto manda o
SDL ignorar o aparelho físico e entregar o virtual, e um emulador real depende
disso para *sequer abrir*. Não é conforto — é requisito.

**O QUE FICOU ABERTO, e é o assunto desta sprint:** o Azahar tem, na própria
interface, um recurso que diz *"Map touchpads on controllers like the DualSense
directly to touch"* — o touchpad do DualSense virando a **tela de baixo do
3DS**. Com o `IGNORE_DEVICES` no lugar, esse recurso **provavelmente se perde**.
A palavra é «provavelmente» porque **ninguém mediu**.

## §1 — O que «o touchpad funciona» quer dizer, em três degraus

| degrau | o que é | como se mede | estado em 10/09/2026 |
| --- | --- | --- | --- |
| 1. **O nó existe** | o daemon publica um nó de touchpad para o controle | `cat /sys/class/input/eventNN/device/name` | **MEDIDO — existe.** `event23` = `DualSense Wireless Controller (Hefesto P1) Touchpad` |
| 2. **O emulador ABRE o nó** | o processo tem o descritor aberto | `ls -l /proc/<pid>/fd` | **MEDIDO — NÃO abre.** Com o `IGNORE_DEVICES`, só `event21` e `event22` |
| 3. **O toque vira toque na tela de baixo** | arrastar o dedo move o ponteiro no jogo | dedo no touchpad, olho na tela | **NUNCA MEDIDO** — falta ROM de 3DS |

O degrau 2 já está vermelho, e ele **explica** o 3 sem prová-lo: o descritor não
está aberto, então o toque não tem por onde chegar.

## §2 — Por que o degrau 2 está vermelho, e a razão não é acidente

O Azahar lê o touchpad pela API de **game controller do SDL2**
(`SDL_CONTROLLERTOUCHPADMOTION`), e essa API **só é alimentada pelo driver
HIDAPI** do SDL. Um joystick que chega por `evdev` é um joystick — eixos e
botões, e nada mais. O `evdev` do Linux não tem, no perfil de gamepad, um canal
por onde um touchpad de controle apareça para o SDL.

Daí a tensão que a sprint tem de resolver, e ela é real:

> **Ou o Azahar ABRE (sem o touchpad), ou ele VÊ o touchpad (e trava).**
> A variável que cura o travamento é a mesma que apaga o recurso.

Não é um trade-off inventado para a prosa: as duas pontas foram medidas no
mesmo dia, no mesmo aparelho.

## §3 — A BANCADA, e ela é a hora dela

Nada aqui se resolve lendo código. Precisa de **um DualSense na mesa e uma ROM
de 3DS** — e a ROM é dela, não se baixa aqui.

O roteiro, na ordem:

1. **Abrir o Azahar e carregar a ROM.** O atalho já leva a cura:
   `~/Lançadores/azahar/rodar.sh`, que lê o `default.env` vivo a cada abertura.
2. **Arrastar o dedo no touchpad do controle.** A pergunta é uma só: *a tela de
   baixo do 3DS respondeu?*
3. **Medir por baixo, no mesmo instante** — o descritor conta a verdade antes
   do olho:
   `ls -l /proc/<pid-do-azahar>/fd | grep event23`
4. **A mordida:** repetir o passo 2 com o Azahar aberto **sem** o
   `IGNORE_DEVICES` (isto é, com o app travando). Se ele nem abre, o recurso não
   existe na prática — e isso é resultado, não falha do ensaio.

O ensaio que esta sprint cria automatiza os passos 1 e 3, e **deixa o 2 para
ela** — é o degrau que só o olho fecha.

## §4 — As três saídas, e duas delas mudam o produto

Medido o degrau 3, uma destas três é verdade:

1. **O touchpad chega assim mesmo.** A ressalva estava errada, e a linha certa
   substitui a errada em todo lugar onde ela aparecer. Custo: zero.
2. **Não chega, e o preço é aceitável.** O 3DS ganha o touch pelo mouse ou pelo
   analógico, o recurso do DualSense fica fora, e isso vira **linha declarada no
   mapa** — nunca frase de tela, que é decisão dela de 07/09.
3. **Não chega, e o produto pode dar um jeito.** É a saída cara e a mais
   interessante: o vpad publica hoje um nó de touchpad separado (`event23`), e
   *nada* o consome. Entregar esse toque por um caminho que o SDL enxergue —
   ou o Hefesto oferecer o touchpad como ponteiro absoluto, que ele já sabe
   fazer no mouse emulado — é sprint nova, e nasce daqui.

**Qual das três é decisão dela, e só depois da medição.**

## §5 — O que MORDE

- **A régua tem de reprovar o degrau 2 hoje.** Se o ensaio passar com o
  `event23` fechado, ele não está medindo o touchpad — está medindo que o
  processo existe. Arranque o `IGNORE_DEVICES`, veja o Azahar travar, e confirme
  que o ensaio ACUSA em vez de esperar para sempre: um ensaio que trava junto
  com o alvo é um ensaio que não reprova nunca.
- **O ensaio não pode nascer com a janela na tela dela.** Ela tem uma tela só. A
  regra desta casa vale aqui como em todo o resto: a janela nasce e morre fora
  da vista dela.
- **Não afirme o degrau 3 a partir do 2.** O descritor fechado é evidência
  forte, não prova: o Azahar poderia ler o toque por um caminho que ninguém
  procurou. O que fecha é o dedo dela no touchpad.
