# Os sensores até o JOGO — o que a bancada mediu

**Bancada de 10/09/2026**, dois DualSense na mesa (P1 no cabo, P2 no rádio),
SDL 2.30.0, daemon em Virtual com máscara DualSense. Instrumento:
`scripts/ensaios/o_jogo_para_de_ver_o_giro.py`.

A dúvida que encomendou isto é dela, 08/09/2026:

*"tambem tenho duvidas se a função giroscopio e acelerometro funcionam de fato."* <!-- noqa-acento: citação literal dela, palavra por palavra -->

E a irmã dela: *"e serão reconhecidos in game?"*

---

## §0 — A resposta, em três linhas

**Funcionam. Até o vpad, os dois, nos dois transportes — e isso está medido
hoje, não herdado.**

**Não chegam ao jogo em Modo Virtual.** E o defeito é pior do que a sprint
supunha: não é que o jogo receba pouco, ou receba tarde. **O SDL responde ao
jogo que o controle não tem giroscópio.** Um jogo que pergunta antes de usar
nem chega a ler.

**Em Modo Nativo chegam.** Mesmo instrumento, mesmo aparelho, minutos de
diferença. É essa diferença que diz que o problema tem endereço.

---

## §1 — O número que decide, e ele é uma comparação

O mesmo controle, o mesmo instrumento, a mesma mesa, com o modo trocado no
meio e devolvido no fim:

| o que o jogo pergunta | **Virtual** (máscara DualSense) | **Nativo** |
| --- | --- | --- |
| por onde o SDL abriu | `/dev/input/eventNN` — **evdev** | `/dev/hidraw5` — **HIDAPI** |
| `HasSensor(GYRO)` | **False** | True |
| `HasSensor(ACCEL)` | **False** | True |
| giro, amostras distintas em 3 s | **0** | 96 |
| acelerômetro, distintas em 3 s | **0** | 586 |
| `hidraw` do FÍSICO | `0600` — o daemon o esconde do jogo | `0660` |

Em Virtual o zero valeu para os **quatro** nós que o SDL abriu: os dois vpads
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

**O dado está lá. O caminho até o jogo é que não existe.**

---

## §3 — Os passos da sprint, um a um

| # | condição | o que se mediu |
| --- | --- | --- |
| 1 | Nativo · cabo | **controle POSITIVO, e passou.** HIDAPI no `hidraw` do físico, `HasSensor=True`, 96 amostras distintas de giro e 586 de acelerômetro em 3 s |
| 2 | Nativo · rádio | **não medido** — a peça do rádio caiu da mesa sozinha antes deste passo (ver §5) |
| 3 | Virtual · DualSense · **cabo** | **ZERO.** O SDL abriu o vpad por evdev; `HasSensor(GYRO)` e `HasSensor(ACCEL)` = **False** |
| 4 | Virtual · DualSense · **rádio** | **ZERO**, idêntico, medido enquanto a peça ainda estava na mesa |
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
| **o que o SDL vê** | 0 | 0 |

A resposta do daemon foi `{"report": "aplicado", "evdev": "held"}`, e o religar
devolveu tudo: 85 e 84 valores distintos de giro nos dois nós, conferidos
depois. **A mesa ficou como estava.**

A leitura: **os dois braços do interruptor fazem exatamente o que prometem.**
O que não se pode medir é o efeito deles no jogo — porque no jogo já não havia
nada a desligar.

---

## §5 — O que caiu do enunciado

**A mordida da §5 da sprint não é medível hoje.** Ela pedia: *"em Virtual,
`sensor.set` desligar o giroscópio → as amostras do SDL param no mesmo
minuto"*. **Não há amostra do SDL a parar** — são zero com o sensor ligado. A
mordida existe e está medida, mas um degrau abaixo (§4).

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
já reporta **zero e `HasSensor=False` para todos os quatro nós**, físicos
inclusive, com a máscara DualSense. Não há giro a atribuir ao nó errado.
Trocar a máscara da máquina dela para confirmar um zero que já é zero paga um
preço real — ela está usando a máquina — por nenhuma informação nova.
**Fica declarado, não escondido.**

**A causa dentro do SDL não está medida.** A tentação é dizer *"o hidapi do SDL
não enumera o vpad"* — `SDL_hid_enumerate` devolve um dispositivo dos oito
`hidraw` da máquina, e nenhum dos dois vpads, que estão `0660` e abrem sem
esforço. **Isso não sustenta a conclusão, e o controle em Nativo derrubou a
ideia:** aquela mesma chamada continuou devolvendo só aquele um enquanto o SDL
tinha `/dev/hidraw5` ABERTO por HIDAPI. O `SDL_hid_enumerate` público não é a
enumeração que o subsistema de joystick usa.

O que sobra medido é o comportamento; o porquê é a primeira pergunta de quem
for curar.

---

## §7 — O que isto desbloqueia

A §4 da sprint previa o desfecho: *"se o passo 3 der ZERO por evdev e o vpad
estiver íntegro: nasce uma sprint de produto"*. **É o caso, e as duas metades
estão medidas** — o vpad íntegro (§2) e o zero no jogo (§1).

A sprint de produto tem de responder, nesta ordem:

1. **por que o SDL não abre o `hidraw` do vpad por HIDAPI**, sendo ele `0660` e
   legível — é a pergunta que decide se a cura é barata ou cara;
2. se não houver caminho por HIDAPI, **como o movimento chega ao jogo em
   Virtual** — o nó "Motion Sensors" do vpad existe e publica, mas o SDL o pula
   por desenho, e quem o lê são `evtest` e emuladores com backend evdev.

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
| `movimento.giroscopio.jogo@dualsense` | cabo | **O APARELHO OBEDECEU** (não alcança `O JOGO RECEBEU`) | vpad entrega 250 relatórios/s com 222 valores distintos; o SDL abre por evdev e responde `HasSensor=False` — **o jogo recebe zero** |
| `movimento.giroscopio.jogo@dualsense` | rádio | **O APARELHO OBEDECEU** (não alcança `O JOGO RECEBEU`) | idêntico ao cabo no que o SDL vê: evdev, `HasSensor=False`, zero |
| `movimento.acelerometro.jogo@dualsense` | cabo | **O APARELHO OBEDECEU** (não alcança `O JOGO RECEBEU`) | 1.241 valores distintos no `hidraw` do vpad; zero no SDL, `HasSensor=False` |
| `movimento.acelerometro.jogo@dualsense` | rádio | **O APARELHO OBEDECEU** (não alcança `O JOGO RECEBEU`) | idem |
| `movimento.giroscopio@dualsense` | cabo | **O JOGO RECEBEU** — em Modo NATIVO | 96 valores distintos por HIDAPI, `HasSensor=True` |
| `movimento.acelerometro@dualsense` | cabo | **O JOGO RECEBEU** — em Modo NATIVO | 586 valores distintos por HIDAPI, `HasSensor=True` |

**A ressalva que não pode se perder na transcrição:** as duas últimas linhas
valem **só em Modo Nativo**. Em Virtual as mesmas duas chaves entregam à
interface e param no vpad.

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
  documento, e documento é arquivo versionado.
