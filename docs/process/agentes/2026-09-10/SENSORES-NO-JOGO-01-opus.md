# SENSORES-NO-JOGO-01 — opus

Bancada de 10/09/2026, reservada e liberada. Dois DualSense na mesa (P1 no
cabo, P2 no rádio), a libSDL2 2.30.0 do sistema. **Nenhuma janela nasceu na
tela dela** — o ensaio é SDL headless com `SDL_VIDEODRIVER=dummy`.

> **FATO SUBSTITUÍDO em 13/09/2026** —
> [SENSORES-NO-JOGO-02](../../sprints/2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md).
> Todo zero desta entrega é da libSDL2 2.30.0 do sistema Ubuntu, que o ensaio
> carregava pelo loader e que nenhum jogo da Steam carrega. Nas bibliotecas dos
> runtimes da Steam o mesmo vpad expõe e entrega os dois sensores pelo evdev,
> com o nó «Motion Sensors» casado ao gamepad pelo `uniq`; a 2.30.0 passa a
> entregar com `SDL_ACCELEROMETER_AS_JOYSTICK=0`. As frases que diziam o
> contrário foram trocadas abaixo.

## O que mudou

**A resposta desta bancada vale para a libSDL2 2.30.0 do sistema: em Modo
Virtual ela não entrega giroscópio nem acelerômetro.** E não é decimação, é
recusa: a 2.30.0 abre o vpad por **evdev** e responde `HasSensor(GYRO)=False`.
Um jogo que carregasse essa biblioteca e perguntasse antes de usar nem chegaria
a ler.

O controle positivo, o mesmo instrumento no mesmo aparelho minutos depois:

| o que a 2.30.0 respondeu | **Virtual** (máscara DualSense) | **Nativo** |
| --- | --- | --- |
| por onde o SDL abriu | `/dev/input/eventNN` — evdev | `/dev/hidraw5` — HIDAPI |
| `HasSensor(GYRO)` / `(ACCEL)` | **False** / **False** | True / True |
| giro · acelerômetro, distintos em 3 s | **0** · **0** | 96 · 586 |

Em Virtual o zero valeu para os **quatro** nós que o SDL abriu — os dois vpads
e os dois físicos.

**E o degrau 2 está íntegro, medido hoje** (era o passo 6 da sprint, o
*"ainda NÃO reconferido no aparelho depois da cura"* de 19/08): o `hidraw` do
vpad do cabo entrega **250 relatórios/s, 64 B, 222 valores distintos de giro e
1.241 de acelerômetro em 5 s**. **O dado está lá; é a 2.30.0 que não o
entrega.**

Dois arquivos:

* `docs/process/2026-09-09-OS-SENSORES-ATE-O-JOGO-o-que-a-bancada-mediu.md`
  (o `cria:` da sprint) — os sete passos um a um, o interruptor dela medido nos
  dois braços, e as células para quem escreve o mapa;
* `scripts/ensaios/o_jogo_para_de_ver_o_giro.py` (a `posse:`) — **curado em
  quatro pontos que esta bancada mostrou que faltavam**:
  1. **`HasSensor` antes de contar amostra.** Sem isso "0 amostras" tinha duas
     causas indistinguíveis, e o veredito escolhia a errada;
  2. **amostras DISTINTAS no nó de movimento**, não só a contagem de eventos —
     é o controle que mata a explicação "o controle estava parado";
  3. **junção por `uniq`, nunca por rótulo** — os dois vpads desta mesa chegam
     com o mesmo nome, "(Hefesto P1)";
  4. **máscara de endereço na saída** (octetos 4 e 5 zerados) — o ensaio existe
     para ter a saída colada num documento, e documento é arquivo versionado.

**Uma afirmação minha caiu no meio do trabalho, e a leitura que a substituiu
também caiu.** Eu escrevi no cabeçalho do ensaio que a causa era *"o hidapi do
SDL não enumera o vpad"* — `SDL_hid_enumerate` devolvia 1 dos 8 `hidraw` da
máquina e nenhum dos dois vpads. Em Nativo aquela mesma chamada continuou
devolvendo só aquele um enquanto o SDL tinha `/dev/hidraw5` aberto por HIDAPI,
e eu concluí que a chamada pública era outra enumeração. **FATO SUBSTITUÍDO em
13/09/2026:** o "só um" era defeito da struct do ensaio, sem os três ints de
interface, que parava a lista no primeiro item. A chamada é a do subsistema de
joystick, e a SDL2 clássica de fato não lista o vpad, por falta de pai USB. A
função hoje se chama `o_hidapi_da_biblioteca_enumera`.

## Qual mordida prova

**Arranquei a cura e vi a régua mentir.** A linha arrancada:

```python
tem = bool(sdl.SDL_GameControllerHasSensor(gc, tipo))
tem = True  # CURA ARRANCADA
```

Com a cura ARRANCADA — o instrumento afirma o contrário do que o SDL responde:

```
  DualSense Wireless Controller (Hefesto P1) | expoe_giro = True | giro_distintos = 0
  PS5 Controller | expoe_giro = True | giro_distintos = 0
VEREDITO COM A CURA ARRANCADA:
  - DualSense Wireless Controller (Hefesto P1): o SDL expõe giroscópio e recebeu 0 amostras distintas por evdev.
  - PS5 Controller: o SDL expõe giroscópio e recebeu 0 amostras distintas por evdev.
```

Com a cura DEVOLVIDA — e o número de controle ao lado, na mesma janela:

```
  - DualSense Wireless Controller (Hefesto P1): O SDL NÃO EXPÕE GIROSCÓPIO neste
    controle (aberto por evdev; HasSensor=False) — e o nó de movimento desta MESMA
    peça entregou 63 amostras distintas de giro na mesma janela: o dado existe, o
    caminho até o jogo é que não. Não há amostra a decimar nem a desligar: o jogo
    pergunta e ouve NÃO.
```

**A mordida do interruptor, medida no degrau em que ele existe.**
`sensor.set giroscopio=False` no controle do cabo, resposta do daemon
`{"report": "aplicado", "evdev": "held"}`:

| braço | antes | depois |
| --- | --- | --- |
| report (janela de motion do vpad) | 101 valores distintos de giro | **1** — os seis bytes zerados |
| evdev (`EVIOCGRAB` no nó do físico) | 1.517 eventos, livre | **0 eventos**, `grabado=True` |
| o que a 2.30.0 vê | 0 | 0 |

**A mesa ficou como estava:** o religar devolveu 85 e 84 valores distintos de
giro nos dois nós, conferidos numa leitura à parte depois; `native_mode` voltou
a `False` e as permissões dos oito `hidraw` voltaram byte a byte ao que eram
antes do controle positivo.

## O que NÃO verifiquei

* **`O JOGO REAGIU` (passo 7) — é dela, e nenhuma régua o alcança.** Precisa de
  um jogo com mira por giroscópio, e a escolha do jogo é dela.
* **O controle negativo da máscara Xbox (passo 5) não rodou.** Ele existe para
  pegar um instrumento que ache giro onde não há; hoje seria vazio, porque o
  instrumento já reporta zero e `HasSensor=False` para os quatro nós **com a
  máscara DualSense**, físicos inclusive. Trocar a máscara da máquina dela para
  confirmar um zero que já é zero paga um preço real — ela está usando a
  máquina — por nenhuma informação nova.
* **Nativo pelo rádio (passo 2) e o degrau 2 pelo rádio (passo 6).** A peça do
  rádio **caiu da mesa sozinha no meio da bancada** (desconectou, e o vpad dela
  foi junto). O que ela alcançou a dar está medido: o passo 4, com o SDL
  abrindo o vpad do rádio por evdev e `HasSensor=False`. Reconectar um controle
  dela é gesto dela.
* **A causa dentro do SDL.** Está medido o COMPORTAMENTO; o porquê de o SDL não
  pegar o `hidraw` do vpad, que está `0660` e abre sem esforço, não está — e é
  a primeira pergunta de quem for curar. Respondida em 13/09/2026 pela
  SENSORES-NO-JOGO-02: o `hid_enumerate` da SDL2 clássica descarta o `hidraw`
  USB sem pai `usb_device`.
* **Não rodei a suíte** (é de quem coordena) nem toquei em `src/`,
  `docs/data/mapa-controles.csv` ou `docs/data/ensaios.csv` — os três são
  `nao_toca` desta sprint.

## O estado dos portões, e os dois vermelhos que NÃO são meus

`bash scripts/portoes.sh` fecha **54 verdes de 56**. Os dois vermelhos são
`mac-por-oui` e `mac-de-fixture`, e os dois apontam para o MESMO arquivo:
`tests/unit/test_o_no_do_radio_conta_como_placa.py`, linhas 26 e 28.

**A prova de que são herdados, e ela é de três linhas:**

* `git diff HEAD -- tests/unit/test_o_no_do_radio_conta_como_placa.py` é
  **vazio** — eu nunca toquei esse arquivo, e ele não está na minha `posse:`;
* o commit que o criou é **`315d912b`**, que é exatamente a base desta árvore —
  a cura de som que o `dev` recebeu hoje;
* ele **continua assim no topo do `dev`** (`21a1853e`, conferido). **Logo o
  `dev` está vermelho nesses dois portões agora**, e todo agente deste lote vai
  tropeçar no mesmo.

**O que é, e por que os dois portões pegam:** as duas constantes de fixture
foram montadas com o **OUI REAL** das duas peças desta bancada e um sufixo
sintético colado atrás. A máscara desta casa é o contrário — o OUI fica, e os
octetos 4 e 5 é que zeram (`OUI:00:00:NN`) —, e o `mac-de-fixture` exige a
faixa sintética inteira (`02:fe` / `aa:bb:cc` / `e8:47:3a`). Um OUI real
identifica o aparelho tanto quanto o sufixo: são as duas peças que estavam na
mesa hoje.

**Não corrigi**, e é de propósito: arquivo de outra pessoa se RELATA, não se
edita — senão a costura vira conflito. A cura é de duas linhas, e quem tem a
posse do arquivo a faz em um minuto: trocar as duas constantes por endereços
da faixa sintética inteira, que é o que o portão pede no próprio texto do erro.

**Um terceiro vermelho apareceu na primeira volta e NÃO se repetiu:**
`casa-sabe`, com os 42 testes passando e o `rc=1` vindo do canário
CANARIO-FS-01 (*"a suíte ESCREVEU nos diretórios reais da usuária"*: um
histórico de perfil criado, `maquina.json` e `personalizado.json` mudados). Na
segunda volta ele fechou verde. É o daemon VIVO dela reagindo ao que a suíte
faz em `/dev/input` — o próprio canário descreve o caso. Fica registrado porque
é vermelho intermitente, e vermelho intermitente que ninguém nomeia vira hora
perdida do próximo.

## O que sobrou para o próximo

1. **Nasce a sprint de produto que a §4 da sprint previa**, e as duas metades
   da condição estão medidas: vpad íntegro e zero na 2.30.0 do sistema. Ela tem
   de responder, nesta ordem: (a) por que o SDL não abre o `hidraw` do vpad por
   HIDAPI; (b) se não houver caminho por HIDAPI, como o movimento chega ao jogo
   em Virtual. **FATO SUBSTITUÍDO em 13/09/2026:** esta linha dizia que o SDL
   deixava o nó «Motion Sensors» de fora; ele o casa ao gamepad pelo `uniq`.
2. **As células, para a MESA-DE-QUATRO-01 escrever no mapa** — estão na §8 do
   laudo, com a ressalva que não pode se perder: `movimento.giroscopio@dualsense`
   e `movimento.acelerometro@dualsense` alcançam `O JOGO RECEBEU` **só em Modo
   Nativo**; as quatro chaves `.jogo` param no vpad nos dois transportes, na
   2.30.0 do sistema.
3. **Os DOIS vpads desta mesa chegam com o mesmo rótulo, "(Hefesto P1)"**, com
   `uniq` diferentes, estando o P2 conectado como índice 1. Um jogo vê dois
   controles dizendo-se P1. Não editei: é `src/`, e é `nao_toca` aqui.
4. **A reserva da bancada não sobrevive a um agente cujo shell morre a cada
   comando.** `scripts/bancada.sh reservar` grava `$PPID`, e a prova de vida do
   kernel liberou a bancada debaixo de mim no meio da medição — sem aviso, e o
   `status` seguinte já dizia LIVRE. Contornei declarando um detentor
   longevo (`HEFESTO_BANCADA_PID`, que o script já prevê para o dublê do
   portão), mas quem despacha agente devia imprimir isso no preâmbulo, ou dois
   agentes se atropelam achando que reservaram.
