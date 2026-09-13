# Os sensores até o JOGO — o que a bancada mediu

**Bancada de 10/09/2026**, dois DualSense na mesa (P1 no cabo, P2 no rádio),
**a libSDL2 2.30.0 do sistema Ubuntu**, daemon em Virtual com máscara
DualSense. Instrumento: `scripts/ensaios/o_jogo_para_de_ver_o_giro.py`.

A dúvida que encomendou isto é dela, 08/09/2026:

*"tambem tenho duvidas se a função giroscopio e acelerometro funcionam de fato."* <!-- noqa-acento: citação literal dela, palavra por palavra -->

E a irmã dela: *"e serão reconhecidos in game?"*

> **FATO SUBSTITUÍDO em 13/09/2026** —
> [SENSORES-NO-JOGO-02](sprints/2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md).
> Todo zero em Modo Virtual deste laudo é da libSDL2 2.30.0 do sistema, que o
> ensaio carregava pelo loader do host e que nenhum jogo da Steam carrega. As
> bibliotecas dos runtimes da Steam — a 2.32.10 do scout, o SDL3 3.4.14 e o
> sdl2-compat 2.32.70 do sniper, do SLR 4 e do soldier — expõem e entregam o
> giroscópio e o acelerômetro do mesmo vpad, pelo evdev. O que este laudo mediu
> no vpad, no nó de movimento e no interruptor continua valendo; as frases que
> diziam o contrário foram trocadas abaixo.

---

## §0 — A resposta, em três linhas

**Funcionam. Até o vpad, os dois, nos dois transportes — e isso está medido
hoje, não herdado.**

**Em Modo Virtual, a libSDL2 2.30.0 do sistema não os entrega.** Não é que
receba pouco, ou tarde: **a 2.30.0 responde que o controle não tem
giroscópio.** As bibliotecas que os jogos da Steam carregam entregam (a nota de
13/09, acima).

**Em Modo Nativo chegam.** Mesmo instrumento, mesmo aparelho, minutos de
diferença. É essa diferença que diz que o problema tem endereço — e o endereço,
medido em 13/09, é a biblioteca.

---

## §1 — O número que decide, e ele é uma comparação

O mesmo controle, o mesmo instrumento, a mesma mesa, com o modo trocado no
meio e devolvido no fim:

| o que a 2.30.0 do sistema respondeu | **Virtual** (máscara DualSense) | **Nativo** |
| --- | --- | --- |
| por onde o SDL abriu | `/dev/input/eventNN` — **evdev** | `/dev/hidraw5` — **HIDAPI** |
| `HasSensor(GYRO)` | **False** | True |
| `HasSensor(ACCEL)` | **False** | True |
| giro, amostras distintas em 3 s | **0** | 96 |
| acelerômetro, distintas em 3 s | **0** | 586 |
| `hidraw` do FÍSICO | `0600` — o daemon o esconde do jogo | `0660` |

Em Virtual o zero valeu para os **quatro** nós que a 2.30.0 abriu: os dois vpads
(o do cabo e o do rádio) e os dois físicos.

---

## §2 — Por que o zero é conclusivo, e não "o controle estava parado"

É a ressalva que o próprio instrumento carrega, e ela é séria: um aparelho
imóvel repete o mesmo valor, e "zero amostras distintas" não provaria nada.

Foi por isso que o controle foi medido **na mesma janela**, um degrau abaixo:

| onde | o que entregou |
| --- | --- |
| nó evdev "Motion Sensors" de cada peça | 1.300–1.500 eventos por segundo, **63 a 112 valores DISTINTOS de giro** |
| `hidraw` do vpad do cabo | **250 relatórios/s**, 64 B, **222 valores distintos de giro** e 1.241 de acelerômetro em 5 s |

**O dado está lá. É a 2.30.0 do sistema que não o entrega.**

---

## §3 — Os passos da sprint, um a um

| # | condição | o que se mediu |
| --- | --- | --- |
| 1 | Nativo · cabo | **controle POSITIVO, e passou.** HIDAPI no `hidraw` do físico, `HasSensor=True`, 96 amostras distintas de giro e 586 de acelerômetro em 3 s |
| 2 | Nativo · rádio | **não medido** — a peça do rádio caiu da mesa sozinha antes deste passo (ver §5) |
| 3 | Virtual · DualSense · **cabo** | **ZERO na 2.30.0 do sistema.** Ela abriu o vpad por evdev; `HasSensor(GYRO)` e `HasSensor(ACCEL)` = **False** |
| 4 | Virtual · DualSense · **rádio** | **ZERO na 2.30.0**, idêntico, medido enquanto a peça ainda estava na mesa |
| 5 | Virtual · Xbox 360 | **não rodado** — ver §6, e a razão não é preguiça |
| 6 | degrau 2, reconferido | **ÍNTEGRO no cabo.** 250 relatórios/s com 222 valores distintos de giro. Fecha o *"ainda NÃO reconferido no aparelho depois da cura"* de 19/08. No rádio, não alcançado |
| 7 | `O JOGO REAGIU` | **é dela.** Nenhuma régua lê o estado de um jogo sob Proton |

---

## §4 — O interruptor dela, e ele FUNCIONA — no degrau em que existe

`sensor.set giroscopio=False` no controle do cabo, medido nos dois braços:

| braço | antes | depois |
| --- | --- | --- |
| **report** (a janela de motion do vpad) | 101 valores distintos de giro | **1** — os seis bytes zerados, valor constante |
| **evdev** (o `EVIOCGRAB` no nó do físico) | 1.517 eventos, livre | **0 eventos**, `grabado=True` |
| **o que a 2.30.0 vê** | 0 | 0 |

A resposta do daemon foi `{"report": "aplicado", "evdev": "held"}`, e o religar
devolveu tudo: 85 e 84 valores distintos de giro nos dois nós, conferidos
depois. **A mesa ficou como estava.**

A leitura: **os dois braços do interruptor fazem exatamente o que prometem.**
O que não se mediu é o efeito deles no jogo — porque na 2.30.0 já não havia
nada a desligar.

---

## §5 — O que caiu do enunciado

**A mordida da §5 da sprint não foi medível na 2.30.0.** Ela pedia: *"em Virtual,
`sensor.set` desligar o giroscópio → as amostras do SDL param no mesmo
minuto"*. **Na 2.30.0 não há amostra a parar** — são zero com o sensor ligado. A
mordida existe e está medida, mas um degrau abaixo (§4); com a biblioteca que o
jogo carrega ela volta a ser medível, e é da MESA-DE-QUATRO-01.

**A §2 da sprint supunha decimação, e a bancada mediu recusa.** O texto dizia
que o vpad entrega *"~37 % dos eventos do físico"* e perguntava se era
*"decimação legítima ou perda"*. Essa pergunta é do degrau 2 e continua de pé
lá. No degrau 3 ela não se aplica: não há amostra decimada, há um `False`.

**A peça do rádio caiu da mesa sozinha no meio da bancada** — o P2 desconectou
e o vpad dele foi junto. O que ele alcançou a dar (passo 4) está medido; o que
faltava (passos 2 e 6 no rádio) não foi refeito, porque reconectar um controle
dela é gesto dela.

---

## §6 — O que NÃO foi medido, e a razão de cada um

**O controle negativo da máscara Xbox (passo 5) não rodou.** Ele existe para
pegar um instrumento que ache giro onde não há — *"instrumento que acha giro na
máscara Xbox está olhando para outro nó"*. Hoje ele seria vazio: o instrumento
já reporta, na 2.30.0, **zero e `HasSensor=False` para todos os quatro nós**, físicos
inclusive, com a máscara DualSense. Não há giro a atribuir ao nó errado.
Trocar a máscara da máquina dela para confirmar um zero que já é zero paga um
preço real — ela está usando a máquina — por nenhuma informação nova.
**Fica declarado, não escondido.**

**A causa dentro do SDL foi medida em 13/09/2026** (SENSORES-NO-JOGO-02), e o
parágrafo que ficava aqui caiu inteiro. O `SDL_hid_enumerate` do ensaio devolvia
um só dispositivo porque a struct dele não tinha os três ints de interface, e a
lista parava no primeiro item; com a struct certa, a chamada é a mesma do
subsistema de joystick, e a SDL2 clássica não lista o vpad porque o
`hid_enumerate` dela descarta o `hidraw` USB sem pai `usb_device`. Sem HIDAPI o
movimento viaja pelo evdev, e só a 2.30.0 da Ubuntu não o casa ao gamepad — a
menos que receba `SDL_ACCELEROMETER_AS_JOYSTICK=0`, que o wrapper passou a
entregar. O fonte e as medições estão na seção 5-bis da
[pilha](../protocol/pilha-steam-input-xpad-sdl.md).

---

## §7 — O que isto desbloqueia

A §4 da sprint previa o desfecho: *"se o passo 3 der ZERO por evdev e o vpad
estiver íntegro: nasce uma sprint de produto"*. **Foi o caso na 2.30.0 do
sistema** — o vpad íntegro (§2) e o zero dessa biblioteca (§1) —, e a sprint
nasceu: [SENSORES-NO-JOGO-02](sprints/2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md).

As duas perguntas que ela recebeu, respondidas em 13/09/2026:

1. **por que o SDL não abre o `hidraw` do vpad por HIDAPI**, sendo ele `0660` e
   legível — a SDL2 clássica descarta o `hidraw` USB sem pai USB, e o vpad
   `uhid` não tem pai USB; o SDL3 e o sdl2-compat o listam;
2. se não houver caminho por HIDAPI, **como o movimento chega ao jogo em
   Virtual** — pelo evdev: o SDL casa o nó "Motion Sensors" ao gamepad da mesma
   peça pelo `uniq`, em toda biblioteca medida menos a 2.30.0 da Ubuntu sem a
   dica.

E há uma decisão que é dela, já registrada na §2 da sprint e que a bancada não
muda: **em máscara Xbox 360 e Nintendo Pro não há onde pôr o movimento** — o
aparelho que a máscara imita não tem giroscópio. A entrega não pode ser
independente da máscara, e isso é decisão a registrar, não dívida a esconder.

---

## §8 — As células, para quem escreve o mapa

Quem escreve `docs/data/mapa-controles.csv` é a MESA-DE-QUATRO-01 (§3), a
partir daqui. Esta sprint declara `nao_toca` os dois CSV.

| chave | transporte | até onde foi | o que se viu |
| --- | --- | --- | --- |
| `movimento.giroscopio.jogo@dualsense` | cabo | **O APARELHO OBEDECEU** (não alcança `O JOGO RECEBEU`) | vpad entrega 250 relatórios/s com 222 valores distintos; a libSDL2 2.30.0 do sistema abre por evdev e responde `HasSensor=False`. Nas bibliotecas dos runtimes da Steam o vpad expõe e entrega (sonda de 13/09, só o rádio) |
| `movimento.giroscopio.jogo@dualsense` | rádio | **O APARELHO OBEDECEU** (não alcança `O JOGO RECEBEU`) | idêntico ao cabo no que a 2.30.0 vê: evdev, `HasSensor=False`, zero; nas bibliotecas da Steam o vpad expõe e entrega (sonda de 13/09) |
| `movimento.acelerometro.jogo@dualsense` | cabo | **O APARELHO OBEDECEU** (não alcança `O JOGO RECEBEU`) | 1.241 valores distintos no `hidraw` do vpad; zero na 2.30.0, `HasSensor=False`; nas bibliotecas da Steam o acelerômetro chega (sonda de 13/09) |
| `movimento.acelerometro.jogo@dualsense` | rádio | **O APARELHO OBEDECEU** (não alcança `O JOGO RECEBEU`) | idem |
| `movimento.giroscopio@dualsense` | cabo | **O JOGO RECEBEU** — em Modo NATIVO | 96 valores distintos por HIDAPI, `HasSensor=True` |
| `movimento.acelerometro@dualsense` | cabo | **O JOGO RECEBEU** — em Modo NATIVO | 586 valores distintos por HIDAPI, `HasSensor=True` |

**As ressalvas que não podem se perder na transcrição:** as duas últimas linhas
valem **só em Modo Nativo**; e as quatro de cima dizem o que a libSDL2 2.30.0
do sistema respondeu. A sonda de 13/09 viu as bibliotecas dos runtimes da Steam
entregarem os dois sensores do vpad a um consumidor SDL — o que ainda não é
`O JOGO RECEBEU`, que pede o processo de um jogo.

---

## §9 — Como remedir, em um comando

```bash
scripts/bancada.sh reservar "ensaio do sensor"
scripts/ensaios/o_jogo_para_de_ver_o_giro.py --so-medir --segundos 3
```

O `--so-medir` não escreve em nada e já dá o veredito. Sem janela: o
`SDL_INIT_GAMECONTROLLER` não inicia vídeo. **Nada nasce na tela dela.**

O que o instrumento ganhou nesta leva, e cada um porque a bancada mostrou que
faltava:

* **`HasSensor` antes de contar amostra.** Sem isso, "0 amostras" tinha duas
  causas indistinguíveis, e o veredito escolhia a errada: dizia *"INCONCLUSIVO
  — mexa no controle"*, mandando quem estava medindo sacudir um aparelho que nunca teve
  por onde entregar;
* **amostras DISTINTAS no nó de movimento**, e não só a contagem de eventos —
  é o controle que mata a explicação "o controle estava parado";
* **junção por `uniq`, nunca por rótulo.** Os dois vpads desta mesa chegam com
  o mesmo nome, "(Hefesto P1)"; casar por nome poria o dado de uma peça ao lado
  do veredito da outra;
* **máscara de endereço na saída.** O ensaio existe para ter a saída colada num
  documento, e documento é arquivo versionado;
* **a biblioteca que o jogo carrega** (13/09/2026): `--lib`, ou as dos runtimes
  da Steam achadas na instalação, cada uma num processo, com a revisão e a dica
  no veredito; e a struct da enumeração com os três ints de interface,
  conferida contra um piso de `/sys/class/hidraw`.
