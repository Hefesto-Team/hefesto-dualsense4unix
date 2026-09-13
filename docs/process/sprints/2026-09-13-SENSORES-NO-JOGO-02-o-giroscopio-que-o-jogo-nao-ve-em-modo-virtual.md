---
sprint: SENSORES-NO-JOGO-02
estado: aberta
onda: A-TERCEIRA-LISTA-DELA
posse:
  SENSORES-NO-JOGO-02:
    # 13/09/2026: a posse real, escrita pelo estudo.
    - scripts/ensaios/o_jogo_para_de_ver_o_giro.py
    - scripts/ensaios/quem_o_jogo_abre.py
    - src/hefesto_dualsense4unix/daemon/launch_env.py
    - assets/hefesto-launch.sh
    - tests/unit/test_launch_env.py
    - tests/unit/test_hefesto_launch_wrapper.py
    - src/hefesto_dualsense4unix/core/virtual_motion.py
    - docs/protocol/pilha-steam-input-xpad-sdl.md
    - docs/process/2026-09-09-OS-SENSORES-ATE-O-JOGO-o-que-a-bancada-mediu.md
    - docs/process/2026-09-11-A-AUDITORIA-DO-SOM-E-DO-GIROSCOPIO.md
    - docs/process/sprints/2026-09-08-SENSORES-NO-JOGO-01-o-giroscopio-e-o-acelerometro-provados-ate-o-jogo.md
    - docs/process/sprints/2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md
    - docs/process/agentes/2026-09-10/SENSORES-NO-JOGO-01-opus.md
cria:
  - tests/unit/test_o_jogo_recebe_a_dica_do_acelerometro.py
# 13/09/2026: a cura cabe sem aparelho; a prova dentro do jogo é da MESA-DE-QUATRO-01.
bancada: false
depois_de: []
nao_toca:
  - docs/data/ensaios.csv
  - docs/data/mapa-controles.csv
  - html/specs.html
  - src/hefesto_dualsense4unix/integrations/uhid_gamepad.py
  - src/hefesto_dualsense4unix/integrations/steam_launch_options.py
  - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
  - install.sh
---

# SENSORES-NO-JOGO-02 — o giroscópio que o jogo não vê em Modo Virtual

> **ROTA ESCRITA PELO ESTUDO — 13/09/2026.** O estudo inteiro, com as sondas e
> os endereços de fonte, fica fora do git:
> `/mnt/Apate/Desenvolvimento/hefesto-voo/_lotes/1309-onda1/ESTUDO-SENSORES-NO-JOGO-02.md`.

Nasce do §7 do laudo
[OS SENSORES ATÉ O JOGO](../2026-09-09-OS-SENSORES-ATE-O-JOGO-o-que-a-bancada-mediu.md),
como a §4 da
[SENSORES-NO-JOGO-01](2026-09-08-SENSORES-NO-JOGO-01-o-giroscopio-e-o-acelerometro-provados-ate-o-jogo.md)
mandava, e responde à pergunta dela na terceira lista:

> *"tenho receio que nossas features não cheguem aos jogos pelo mesmo motivo ou semelhantes"*

([o índice](2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md)).

## §1 — O que a bancada mediu (09/09), e o fato que o estudo trocou

* **Até o vpad, os dois sensores funcionam** nos dois transportes: 250
  relatórios por segundo, 222 valores distintos de giro. Continua valendo.
* **Em Modo Nativo chegam por HIDAPI:** 96 amostras distintas de giro e 586 de
  acelerômetro. Continua valendo.
* **FATO SUBSTITUÍDO em 13/09/2026.** O laudo dizia que em Modo Virtual o jogo
  recebe zero. Isso só vale para a **libSDL2 2.30.0 da Ubuntu**, que o ensaio
  carregava pelo loader do sistema e que nenhum jogo da Steam carrega. Nas
  bibliotecas dos runtimes da Steam o vpad expõe e entrega os dois sensores
  (sonda só-leitura, vpad P1 vivo, HIDAPI desligado na sonda):

  | biblioteca | o HIDAPI enumera o vpad? | o evdev pareia o «Motion Sensors»? | giros distintos em 2 s |
  | --- | --- | --- | --- |
  | libSDL2 2.30.0, sistema Ubuntu | não | não | 0 |
  | libSDL2 2.32.10, runtime scout | não | sim | 141 |
  | SDL3 3.4.14, runtime sniper | sim | sim | 137 |
  | sdl2-compat 2.32.70, sniper e SLR 4 | sim | sim | 144 |

* **FATO SUBSTITUÍDO:** a frase de que o SDL deixa o nó «Motion Sensors» de
  lado por desenho é falsa. O SDL o recusa como joystick e o aceita como sensor,
  pareado pelo `uniq` ao gamepad da mesma peça.

## §2 — As perguntas, respondidas pelo estudo

1. **Por que a SDL2 clássica não abre o hidraw do vpad por HIDAPI.** O
   `hid_enumerate` descarta todo hidraw de barramento USB sem pai `usb_device`,
   e o vpad uhid mora em `/devices/virtual/misc/uhid`. O ambiente do Hefesto não
   pesa: o vpad está `0660` com a permissão dela. O SDL3 e o sdl2-compat aceitam
   o vpad («uhid USB devices»). O físico, em Virtual, fica fora por outro motivo:
   o daemon deixa o hidraw dele em `0600`.
2. **Como o movimento chega em Virtual:** por evdev, pareado pelo `EVIOCGUNIQ`,
   em toda versão medida menos a 2.30.0 da Ubuntu. Ali o patch LP #2085140 exige
   a classe udev ACCELEROMETER, que a 2.30 nunca atribui enquanto
   `SDL_ACCELEROMETER_AS_JOYSTICK` estiver no padrão 1. A mordida vale nos dois
   sentidos: com a dica em 0 a 2.30.0 entrega (109 giros distintos); com a dica
   em 1 a 2.32.10 para de entregar.
3. **O instrumento também mentia.** A struct ctypes do ensaio não tinha
   `interface_class`, `interface_subclass` e `interface_protocol`; o `next` era
   lido no deslocamento errado, e a lista parava no primeiro item («1 de 8»).

## §3 — A decisão que já está registrada

Em máscara Xbox 360 e Nintendo Pro não há onde pôr o movimento: o aparelho que a
máscara imita não tem giroscópio. É decisão registrada na §2 da
SENSORES-NO-JOGO-01, não dívida.

## §D — Decisões (do estudo, com a base)

| decisão | base |
| --- | --- |
| `SDL_ACCELEROMETER_AS_JOYSTICK=0` em toda variante do env do jogo, também no Modo Nativo e nas máscaras. Nas bibliotecas dos runtimes a dica foi medida inócua | a palavra dela de 09/08, citada em `assets/72-hefesto-touchpad-motion-uaccess.rules` (touchpad e giroscópio por padrão em todos os modos), e a de 04/09, citada no topo de `scripts/ensaios/o_jogo_para_de_ver_o_giro.py`; o precedente de variável inócua em toda variante é o `SDL_GAMECONTROLLER_USE_BUTTON_LABELS` em `daemon/launch_env.py` |
| Nenhuma mudança no vpad para ganhar o HIDAPI da SDL2 clássica | trocar o barramento ou dar pai USB pede relatório 0x31 com CRC ou gadget USB, e aparelho; o evdev já entrega nas bibliotecas da Steam (`integrations/uhid_gamepad.py`, a escolha de `VPAD_PRODUCT` e `BUS_USB`) |
| As máscaras Xbox 360 e Nintendo Pro continuam sem movimento no jogo | a §3 acima |

## §I — IMPLEMENTA

1. **O ensaio mede contra a biblioteca que o jogo carrega.**
   `scripts/ensaios/o_jogo_para_de_ver_o_giro.py` recebe `--lib` (várias) e,
   sem ele, roda as bibliotecas dos runtimes achadas em `~/.steam`, sem inventar
   caminho. A `_InfoHid` ganha os três ints (e o `bus_type` no SDL3). O
   `--so-medir` força `SDL_JOYSTICK_HIDAPI=0`, para não abrir hidraw nem
   escrever. O veredito sai por biblioteca, com a revisão lida por
   `SDL_GetRevision`.
2. **O env do jogo ganha `SDL_ACCELEROMETER_AS_JOYSTICK=0`** em toda variante
   do `compose_env`. É nome novo, então entra nos dois lados da allowlist
   (`daemon/launch_env.py` e `assets/hefesto-launch.sh`) e na cópia do ensaio de
   ambiente (`scripts/ensaios/quem_o_jogo_abre.py`).
3. **O fato errado sai de todos os lugares:** o laudo de 09/09 (§0, §1, §6, §7,
   §8), a SENSORES-NO-JOGO-01, a auditoria de 11/09, `core/virtual_motion.py`, a
   entrega de 10/09 e o próprio ensaio. O zero ganha o endereço da biblioteca.
   As células do mapa continuam fora (são da MESA-DE-QUATRO-01), mas o texto que
   as acompanha ganha a ressalva.
4. **A pilha ganha a seção dos sensores do vpad por versão de SDL**
   (`docs/protocol/pilha-steam-input-xpad-sdl.md`): a tabela da §1, os endereços
   de fonte, o patch da Ubuntu e o grau de cada linha (ALTA para código, MEDIDO
   AQUI para sonda).

## §V — Prova

* A régua nova (`tests/unit/test_o_jogo_recebe_a_dica_do_acelerometro.py`):
  com a variável fora do `ENV_ALLOWLIST`, ou fora do `case` do wrapper, ela não
  chega ao `env(1)`, e o espelho da allowlist reprova.
* A mordida do ensaio: sem os três ints a enumeração volta a dar um item e o
  ensaio acusa contra a contagem de `/sys/class/hidraw`; na 2.30.0 sem a dica
  em 0, `HasSensor` volta a `False` e o veredito nomeia a biblioteca, não o vpad.
* A frase caída: a busca pelas formas antigas volta vazia nos arquivos
  versionados, fora as citações datadas de que ela caiu.
* A sonda só lê: `SDL_JOYSTICK_HIDAPI=0` em toda corrida, nenhum hidraw aberto,
  nenhum contêiner do sniper iniciado.

## §R — Riscos

* Nenhum jogo instalado dela traz SDL próprio: o ganho da dica fica para jogos
  que embutam a SDL2 2.30.x e para outros usuários.
* Variável nova sem os dois lados da allowlist morre sem erro.
* O laudo não pode perder o que mediu certo: o vpad íntegro, os 250 relatórios
  por segundo e o interruptor nos dois braços.

## O que só a MESA-DE-QUATRO-01 responde

* O jogo recebendo com o HIDAPI LIGADO no SDL3 e no sdl2-compat (o driver PS5
  escreve efeitos ao abrir o hidraw).
* O contêiner do Steam Linux Runtime sniper por dentro (o SDL entra em
  `ENUMERATION_FALLBACK`).
* O vpad que nasce com o jogo aberto (co-op, troca de máscara, reconexão) na
  SDL2 2.32.10: pelo fonte ele nasceria sem giroscópio. Se a mesa confirmar, vai
  para o mapa como limite, nunca para a tela.
* Quatro DualSense com quatro vpads, e o cabo.
* O caminho do Proton (winebus) com um jogo Windows real.
* O jogo reagindo à mira por giroscópio, e qual SDL cada jogo dela carrega
  (`/proc/<pid>/maps` com o jogo aberto).

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** | o vpad é o mesmo nos dois; a sonda de 13/09 viu só o rádio |
| **no perfil** | os interruptores por peça já existem (`ControllerSensoresOverride`) |
| **por controle** | o pareamento é por `uniq`, um par por peça |
