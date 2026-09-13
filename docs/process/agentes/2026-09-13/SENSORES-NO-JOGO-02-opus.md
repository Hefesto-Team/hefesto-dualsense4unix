# SENSORES-NO-JOGO-02 — opus

Agente IMPLEMENTA do lote 1309-onda2, na árvore `voo/SENSORES-NO-JOGO-02-opus`,
nascida de `onda/1309` (`e1c7d96b`). **Nada foi escrito em aparelho e a bancada
não foi reservada:** tudo o que tocou controle foi sonda só-leitura, com
`SDL_JOYSTICK_HIDAPI=0`, sem `EVIOCGRAB`, sem daemon e sem contêiner da Steam.
**A tela não muda:** nenhuma página regerada, nenhum botão, nenhuma foto.

## O que mudou

### 1. O jogo recebe `SDL_ACCELEROMETER_AS_JOYSTICK=0` em toda variante

* `src/hefesto_dualsense4unix/daemon/launch_env.py` — `compose_env` escreve a
  dica sem `if`, logo depois da `SDL_GAMECONTROLLER_USE_BUTTON_LABELS`, que é o
  precedente de variável inócua em toda variante; `ENV_ALLOWLIST` ganha o nome
  no fim. **As linhas que o mapa cita ficaram no lugar** (`:85`, a
  `USE_BUTTON_LABELS`, e `:1550-1553`): um comentário de duas linhas entre as
  duas virou uma.
* `assets/hefesto-launch.sh` — o `case` ganha a linha. O comentário de cima
  virou uma linha, e as sete entradas ocupam exatamente `:85-91`, a faixa que a
  pilha cita.
* `scripts/ensaios/quem_o_jogo_abre.py` — `VARS` lê a dica do `/proc` do jogo.
* `tests/unit/test_o_jogo_recebe_a_dica_do_acelerometro.py` (o `cria:`) — as
  nove variantes do `compose_env` (nativo, emulação desligada, sem vpad, uhid,
  degradado, co-op misto, sem cobertura, Xbox, Nintendo); a allowlist; **o
  espelho do `case` contra a allowlist nos dois sentidos** (o de
  `test_launch_env.py` só olha um); **a travessia inteira**:
  `materialize_launch_env` grava o `default.env`, o `hefesto-launch.sh` real
  roda contra um socket de mentira, e o processo embrulhado lê `0`; e os dois
  ensaios medindo com o valor que o jogo recebe.
* **O strip de LaunchOptions não precisa conhecer a variável**
  (`integrations/steam_launch_options.py`, da JOGO-SEM-EXCLUSIVIDADE-01, era a
  pergunta da `## colide`): a dica nunca vai para a LaunchOptions. A string da
  Steam é constante, e a dica só existe no arquivo que o wrapper lê; os
  `_COOCCURRING_TOKENS` do strip são do veneno legado de antes do wrapper.

### 2. O ensaio mede a biblioteca que o jogo carrega

`scripts/ensaios/o_jogo_para_de_ver_o_giro.py`:

* `--lib`, repetível; sem ele, `bibliotecas_dos_runtimes()` acha as libSDL de
  64 bits da instalação (`ubuntu12_32/steam-runtime` e
  `SteamLinuxRuntime_*/*_platform_*`, nas pastas do `libraryfolders.vdf`).
  Nesta máquina, nove;
* cada biblioteca roda em **dois processos próprios**, sem `DISPLAY` e sem
  `WAYLAND_DISPLAY`: um enumera o HIDAPI, o outro abre os controles como o jogo
  abre. O sdl2-compat é reconhecido pelos bytes e vai com o SDL3 da mesma pasta
  (ou da de cima, no soldier) — nunca sem ele;
* `_InfoHid` com os três ints de interface, `_InfoHid3` com o `bus_type`; a
  lista é conferida contra `piso_da_enumeracao_hid()` — os `hidraw` que passam
  em `access()` e têm barramento de verdade;
* `--so-medir` força `SDL_JOYSTICK_HIDAPI=0` e `SDL_HIDAPI_LIBUSB=0` e não
  sonda o `EVIOCGRAB` do nó de movimento;
* `--dica-do-acelerometro {0,1,ausente}`, com padrão `0`, que é o que o jogo
  recebe; `ausente` tira a variável, como um jogo aberto por fora do Hefesto;
* o veredito nomeia versão, revisão (`SDL_GetRevision`), caminho e dica, e
  termina em `rc=3` quando uma biblioteca não pôde ser medida ou não alcançou o
  piso;
* a docstring perdeu as frases caídas e ganhou a tabela de 13/09 e a causa.

**O que o estudo não previa, e foi medido antes de desenhar o piso:** o SDL3
filtra o `SDL_hid_enumerate` para só controles, por padrão. Com o filtro, o
3.4.14 lista 2 nós; sem ele, 17 entradas em 6 nós. Um piso comparado contra a
lista filtrada acusaria o SDL3 de struct errada. Por isso a enumeração roda num
processo à parte, com `SDL_HIDAPI_ENUMERATE_ONLY_CONTROLLERS=0`, e o processo dos
controles fica igual ao do jogo.

### 3. O fato errado saiu dos arquivos da posse

O laudo de 09/09 (nota no topo e as §0, §1, §2, §3, §4, §5, §6, §7, §8 e §9), a
SENSORES-NO-JOGO-01 (a nota de estado e a §2), a auditoria de 11/09 (a §5 e o
J2), `core/virtual_motion.py` (a linha do instrumento e o item 1, com o mesmo
número de linhas), a entrega de 10/09 (nota no topo e seis trechos) e o próprio
ensaio. **O que esses documentos mediram certo ficou:** o vpad a 250
relatórios/s, o nó de movimento, o interruptor nos dois braços, o Modo Nativo.

### 4. A pilha ganhou a seção 5-bis

`docs/protocol/pilha-steam-input-xpad-sdl.md`: o que cada biblioteca entrega, a
dica nos dois sentidos, a SDL2 clássica sem pai USB, o filtro do SDL3, o
pareamento por `uniq`, o patch da Ubuntu e o que a seção não mede — cada linha
com o grau (ALTA para fonte, MEDIDO AQUI para sonda, NÃO MEDIDO). A §4 passou a
**sete** variáveis, com a `ENV_ALLOWLIST` apontada pelo símbolo; a §7 ganhou a
linha 10, e a §8 as fontes.

## Qual mordida prova

### A dica, arrancada lado a lado

Cada lado arrancado por um script que confere a restauração por md5; a régua é a
nova mais `test_launch_env.py`.

```
== CURA ARRANCADA (compose_env): rc=1
FAILED ...::test_toda_variante_do_env_do_jogo_leva_a_dica_em_zero[coop_misto]
FAILED ...::test_toda_variante_do_env_do_jogo_leva_a_dica_em_zero[dualsense_degradado]
FAILED ...::test_toda_variante_do_env_do_jogo_leva_a_dica_em_zero[dualsense_uhid]
FAILED ...::test_toda_variante_do_env_do_jogo_leva_a_dica_em_zero[emulacao_desligada]
FAILED ...::test_toda_variante_do_env_do_jogo_leva_a_dica_em_zero[nativo]
FAILED ...::test_toda_variante_do_env_do_jogo_leva_a_dica_em_zero[nintendo]
FAILED ...::test_toda_variante_do_env_do_jogo_leva_a_dica_em_zero[sem_cobertura]
FAILED ...::test_toda_variante_do_env_do_jogo_leva_a_dica_em_zero[sem_vpad_vivo]
FAILED ...::test_toda_variante_do_env_do_jogo_leva_a_dica_em_zero[xbox]
FAILED ...::test_a_dica_atravessa_o_arquivo_e_o_wrapper_ate_o_processo_do_jogo
FAILED ...::test_o_ensaio_do_giro_mede_com_a_dica_que_o_jogo_recebe
11 failed, 22 passed in 0.76s
== CURA ARRANCADA (allowlist): rc=1
FAILED ...::test_a_dica_mora_na_allowlist
FAILED ...::test_o_case_do_wrapper_e_a_allowlist_sao_o_mesmo_conjunto
FAILED tests/unit/test_launch_env.py::test_compose_env_so_emite_vars_da_allowlist
3 failed, 30 passed in 0.96s
== CURA ARRANCADA (case-do-wrapper): rc=1
FAILED ...::test_o_case_do_wrapper_e_a_allowlist_sao_o_mesmo_conjunto
FAILED ...::test_a_dica_atravessa_o_arquivo_e_o_wrapper_ate_o_processo_do_jogo
FAILED tests/unit/test_launch_env.py::test_allowlist_espelhada_no_wrapper_sh
3 failed, 30 passed in 0.94s
== CURA DEVOLVIDA: rc=0
33 passed in 0.93s
```

### A struct do ensaio

Os três ints tirados de `_CAMPOS_ATE_A_INTERFACE`, o ensaio contra a 2.32.10 do
scout e o SDL3 3.4.14 do sniper, restauração conferida por md5:

```
== cura-arrancada: rc=3
   2.32.10: entradas=1 nos=1 piso=4 faltam=3
   V: A ENUMERAÇÃO HID NÃO ALCANÇA O PISO: 1 nó(s) listado(s), e faltam 3 dos 4
      que toda biblioteca medida lista. A struct deste ensaio não casa com esta
      biblioteca: não conclua nada da lista.
   [SDL3 3.4.14] NÃO MEDIDA — o processo «enumerar» saiu com rc=-11
== cura-devolvida: rc=0
   2.32.10: entradas=4 nos=4 piso=4 faltam=0
   3.4.14: entradas=17 nos=6 piso=4 faltam=0
```

No SDL3 a struct sem os três ints lê um `next` que não é NULL, e o processo da
biblioteca morre por `SIGSEGV`. **O ensaio sobrevive e acusa** — é para isso que
cada biblioteca tem processo próprio. Isso difere do que a §V previa («volta a
dar um item»): um item é o que a SDL2 dá; o SDL3 dá um processo morto.

### A biblioteca, com a dica nos três valores

`--so-medir --segundos 2`, no vpad P1 (rádio). `HasSensor(GYRO)` e giros
distintos:

| biblioteca | sem a variável | `=1` | `=0` |
| --- | --- | --- | --- |
| libSDL2 2.30.0, sistema Ubuntu | False, 0 | False, 0 | True, 162 |
| libSDL2 2.32.10, scout | True, 145 | False, 0 | True, 150 |

E o veredito nomeia a biblioteca, não o vpad:

```
[libSDL 2.30.0 «SDL-release-2.30.0-0-g859844eae (Ubuntu 2.30.0+dfsg-1ubuntu3.1)»
 em /usr/lib/x86_64-linux-gnu/libSDL2-2.0.so.0.3000.0,
 SDL_ACCELEROMETER_AS_JOYSTICK=padrão (1)] DualSense Wireless Controller (Hefesto P1):
 ESTA BIBLIOTECA NÃO EXPÕE GIROSCÓPIO neste controle (aberto por evdev;
 HasSensor=False) — e o nó de movimento desta MESMA peça entregou N amostras
 distintas de giro: o dado existe. É a resposta da biblioteca com esta dica,
 não do vpad …
```

### O ensaio contra as nove bibliotecas dos runtimes

`--so-medir --segundos 2`, `rc=0`, dica em 0, piso de 4 nós alcançado por todas.
No vpad:

| biblioteca | HIDAPI lista o vpad? | HasSensor | giros · acelerômetros distintos |
| --- | --- | --- | --- |
| sdl2-compat 2.32.70, SLR 4 | sim | True | 126 · 331 |
| SDL3 3.4.14, SLR 4 | sim | True | 157 · 326 |
| sdl2-compat 2.32.70, sniper | sim | True | 149 · 342 |
| SDL3 3.4.14, sniper | sim | True | 134 · 322 |
| libSDL2 2.32.10, `sdl2-classic` do sniper | não | True | 141 · 314 |
| SDL3 3.4.14, soldier | sim | True | 134 · 321 |
| libSDL2 2.32.10, `sdl2-classic` do soldier | não | True | 143 · 327 |
| sdl2-compat 2.32.70, soldier | sim | True | 139 · 335 |
| libSDL2 2.32.10, scout | não | True | 144 · 336 |

O nó «Motion Sensors» do vpad, lido direto na mesma corrida: 116 giros e 207
acelerômetros distintos em 1 s.

### A frase caída

A busca pelas quatro formas da §V («pula por desenho», «o SDL o pula», «não é a
enumeração que o subsistema», «SDL não lê este nó») com `git grep --untracked`,
fora `*.html` e `*.csv`, **volta vazia**; e nos `*.html` e `*.csv` também. As
notas de substituição foram escritas sem repetir a frase caída, para o aviso não
virar a primeira ocorrência dela. Duas formas vizinhas sobram, fora da posse —
item 1 de «O que sobrou».

### A sonda só leu

Toda corrida com `SDL_JOYSTICK_HIDAPI=0` e `SDL_HIDAPI_LIBUSB=0`, o nó de
movimento lido sem `EVIOCGRAB`, nenhum contêiner iniciado, nenhuma chamada ao
daemon. Os perfis dela conferidos por md5 antes e depois: idênticos.

## O que NÃO verifiquei

* **O jogo.** HIDAPI ligado no SDL3 e no sdl2-compat, o contêiner do sniper por
  dentro, o vpad que nasce com o jogo aberto na 2.32.10, quatro vpads, o
  caminho do Proton, o jogo reagindo à mira e qual SDL cada jogo carrega — é a
  MESA-DE-QUATRO-01, e a pilha tem a linha 10 da §7 para isso.
* **O cabo.** A sonda viu só o controle do rádio e o vpad dele.
* **Por que a 2.32.10 sem a variável se comporta como `=0`.** Medido, não lido
  no fonte.
* **As bibliotecas de 32 bits** dos runtimes: o python é de 64.
* **`tests/unit/test_hefesto_launch_wrapper.py` depois da mudança.** Rodei-o uma
  vez na base, antes de ver o Game Mode (item 3 abaixo); o `case` novo está
  coberto pela régua nova e por `test_launch_env.py`.
* **A suíte inteira**, que é de quem coordena.
* **As outras sprints de 13/09** além do cabeçalho de posse das duas que citam
  os meus arquivos — JOGO-SEM-EXCLUSIVIDADE-01 e LIGHTBAR-NA-STEAM-01, que
  declaram `launch_env.py` em `nao_toca`.

## O que sobrou para o próximo

1. **O mesmo fato errado vive fora da posse desta sprint**, e não o editei.
   Conferido lendo cada trecho:
   * `src/hefesto_dualsense4unix/daemon/sensor_hub.py`, docstring de
     `_reconciliar_grabs`: diz que o SDL não lê o nó «Motion Sensors»;
   * `src/hefesto_dualsense4unix/daemon/ipc_handlers.py`, docstring do
     `sensor.set`: diz que o SDL não lê o nó e que, em Virtual, lê o giro pelo
     `hidraw` do vpad — as duas metades caíram (a SDL2 clássica nem lista o
     `hidraw` do vpad; o giro chega pelo evdev);
   * `scripts/check_ate_onde_a_prova_chegou.py`, a frente `sensor`: a hipótese
     de que em Virtual o jogo não recebe giroscópio;
   * `docs/process/agentes/2026-09-04/ONDA1-D3.md`, o item 1 das afirmações
     caídas;
   * `docs/process/agentes/2026-09-11/AUDITORIA-SOM-GIRO-01-opus.md` e a §1 de
     `docs/process/sprints/2026-09-11-AUDITORIA-SOM-GIRO-01-todas-as-features-por-controle-e-dentro-do-jogo.md`.
2. **O mapa e o `specs.html`** (`nao_toca`): as células
   `movimento.giroscopio.jogo@dualsense` e `movimento.acelerometro.jogo@dualsense`
   precisam da ressalva de biblioteca antes de a MESA-DE-QUATRO-01 escrevê-las.
   As medições com a `chave` estão acima.
3. **`tests/unit/test_hefesto_launch_wrapper.py` roda o wrapper com o `PATH` da
   máquina.** Com `system76-power` instalado aqui, o Game Mode do wrapper pede
   Performance a cada teste e devolve o perfil anterior ~2 s depois — a suíte
   mexe no perfil de energia dela. A régua nova roda com `PATH` mínimo; a
   antiga ficou como estava.
4. **`quem_o_jogo_abre.py` decide `wrapper_rodou` pela `PROTON_DISABLE_HIDRAW`**,
   que não sai em Modo Nativo: com o jogo em Nativo ele acusaria o wrapper de
   não ter rodado. As duas variáveis que saem em toda variante dariam o sinal
   certo. Fora do §I.
5. **O runtime `SteamLinuxRuntime/`, sem sufixo**, traz outra cópia da 2.32.10 e
   fica fora do padrão de busca do ensaio — é a mesma versão do scout, que entra.
