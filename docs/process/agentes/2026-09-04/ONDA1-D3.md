# ONDA1-D3 · O SENSOR — o interruptor que desliga de verdade

**Sprint:** `2026-09-04-ONDA1-D3-O-SENSOR-01-o-interruptor-que-desliga-de-verdade.md`
**Árvore:** `hefesto-voo/ONDA1-D3-O-SENSOR-D3` · branch `voo/ONDA1-D3-O-SENSOR-D3`
**Bancada:** reservada (`ONDA1-D3 o sensor`), medida com **um** DualSense no cabo
— o segundo não estava na mesa, e isso está em *O que NÃO verifiquei*.

> **FATO SUBSTITUÍDO em 13/09/2026** —
> [SENSORES-NO-JOGO-02](../../sprints/2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md).
> A sonda desta entrega carregava a libSDL2 2.30.0 do sistema, e o zero em Modo
> Virtual era dessa biblioteca; nas bibliotecas dos runtimes da Steam o vpad
> expõe os dois sensores, e o SDL pareia o nó «Motion Sensors» pelo `uniq` (a
> tabela está na SENSORES-NO-JOGO-02, §1). No item 1 das afirmações abaixo cai
> a razão dada sobre o SDL: o grab do nó do FÍSICO alcança também quem abriu o
> físico, e o jogo que abriu o vpad só o braço do report alcança. O achado do
> item 2 de «O que sobrou» cai; a hipótese dele, o vpad `uhid` sem pai USB, se
> confirmou para o HIDAPI da SDL2 clássica e não era a causa do zero (§2 daquela
> sprint). O corpo fica como o registro do que esta bancada viu.

---

## A MEDIÇÃO VEIO PRIMEIRO — e ela derrubou três frases do plano

A sprint manda medir **por onde o jogo lê o giro em cada modo** antes de
qualquer linha de cura. O instrumento não foi o `state_full` do daemon (que
mede o que a INTERFACE vê): foi uma sonda **SDL 2.30.0 headless** — a mesma
biblioteca que o jogo usa —, abrindo os controles como um jogo abre, mais a
leitura direta dos nós evdev e dos `hidraw`. Sem janela, nada na tela dela.

| caminho | **Nativo** | **Virtual (uhid)** |
| --- | --- | --- |
| `hidraw` do FÍSICO | `0660`+ACL — **o SDL ABRE, e o giro chega POR AQUI**: `tem_giro=true`, 192 amostras distintas em 2 s | `0600 root` — o jogo **não** abre (o daemon esconde) |
| `hidraw` do VPAD | não existe | `0660`+ACL, 249 relatórios/s — **e o SDL não o abre por HIDAPI** |
| nó evdev "Motion Sensors" | livre, ~1950 ev/s | livre nos **DOIS** (físico *e* vpad), ~1950 ev/s cada |
| o que o SDL de fato abriu | `/dev/hidraw4` (HIDAPI) | `event21` e `event25` (evdev) |
| **o jogo (SDL) vê giro?** | **SIM** | **NÃO** — `tem_giro=false`, com máscara DualSense, com máscara Xbox e sem env nenhuma |

**As três afirmações que caíram**, e as três estavam no enunciado do trabalho:

1. §0 da sprint-mãe: *"o `hid_playstation` publica o movimento num nó evdev
   separado — agarrar ESSE nó esconde o giro do jogo sem tocar um botão"*.
   **Falso para o SDL:** ele não enumera o nó de movimento (`SDL_NumJoysticks`
   devolve 2, só os controles; o nó carrega `ID_INPUT_ACCELEROMETER` e o SDL o
   pula). O grab alcança o consumidor evdev DIRETO — `evtest`, emulador com
   backend evdev —, não o SDL;
2. §0: *"Em Virtual o giro já passa pelo vpad (…) o interruptor já tem metade
   do motor: parar o espelho"*. **Em Virtual o nó de movimento do FÍSICO
   continua livre e publicando**, ao lado do espelho. Parar o espelho não é
   metade: é um quarto;
3. §2 da minha sprint: *"Nativo — o `hid_playstation` publica os nós de
   movimento direto [e o jogo os lê]"*. O kernel publica o nó; **quem entrega
   ao jogo é o `hidraw`**.

**A consequência de desenho, e é a razão de a entrega ter DOIS braços:** nenhum
caminho sozinho é o interruptor.

---

## O que mudou

### `core/virtual_motion.py` (NOVO) — a peça pura + o registro
* `janela_com_sensores(janela, giroscopio=, acelerometro=)`: zera **só** os 6
  bytes do sensor desligado (`gyro[3]` em 0-5, `accel[3]` em 6-11 da janela de
  25 B) e devolve o resto verbatim — `sensor_timestamp` (o `dt` com que o SDL
  integra) e os dois pontos de toque **atravessam intactos**, que é a decisão
  dela sobre o touchpad;
* com os dois ligados devolve **o mesmo objeto**: o caminho quente roda a
  ~250 Hz e o caso normal não paga um `bytearray`;
* `RegistroDeSensores` / `REGISTRO`: quem está desligado, **por peça**,
  thread-safe. Mora no PROCESSO e não no objeto do vpad — e essa escolha é o
  *"independente da máscara"* dela: trocar a máscara **derruba e recria o
  vpad**, e estado guardado nele voltaria a ligar sozinho, calado.

### `core/physical_report_reader.py` — o braço do REPORT (2 hunks)
* `uniq_do_hidraw(path)`: traduz `/dev/hidrawN` → a peça, pelo `HID_UNIQ` do
  sysfs. Resolvido **no open** (uma vez por conexão, não por report);
* `_emit` entrega `REGISTRO.filtrar(self._uniq_aberto, window)` ao vpad —
  **depois** de gravar `_last_window`, de propósito: o cache guarda o que o
  FÍSICO mandou (é ele que decide "mudou?"), e guardar a janela filtrada
  congelaria o dedup e pararia o touchpad junto;
* `uniq` desconhecido = **não filtra**. Errar para o lado de não desligar:
  desligar o sensor da peça errada é pior.

### `core/evdev_reader.py` — o braço do EVDEV
A máquina de `EVIOCGRAB` (`_grab`, `_grab_state`, `grab_state`, `set_grab`,
`_reapply_grab`) **subiu de `EvdevReader` para `_EvdevReconnectLoop`**, sem
duplicá-la: o nó "Motion Sensors" é outra subclasse e precisa do mesmo grab,
com as mesmas duas cicatrizes (o EBUSY duplo e o `pending` da reconexão).
`MotionSensorReader._reset_on_disconnect` passa a devolver o grab a `pending`
— é o que faz o interruptor **sobreviver ao replug e à troca de máscara**.

### `daemon/sensor_hub.py` — quem segura o grab, e o que o mantém vivo
* `_reconciliar_grabs`: o nó de movimento fica grabado enquanto houver sensor
  desligado naquela peça — e **só então**; sem pedido dela o hub continua sendo
  o observador que não disputa nada;
* a linha que faz o interruptor durar: quem tem sensor desligado entra na lista
  de `motion` **mesmo sem ninguém pedir leitura**. Sem ela o TTL de 5 s
  derrubaria o reader — e com ele o grab — **cinco segundos depois de ela
  fechar a janela**, com a tela ainda dizendo "desligado";
* `grab_do_movimento(uniq)`: `off|pending|held|failed|sem_reader`, para a
  resposta poder dizer o que o aparelho concedeu em vez de afirmar pelo desenho.

### `profiles/schema.py` + `profiles/manager.py` — o disco
* `ControllerSensoresOverride` (`giroscopio`/`acelerometro`, `None` = ligado) e
  o campo `sensores` em `ControllerOverrides` — **o sexto**;
* `manager.apply_controller_sensores`: só quem tem opinião; perfil sem a seção
  não mexe em nada;
* a fila da docstring de `ControllerOverrides` perdeu o item 2 (*"não existe no
  produto nada que desligue um sensor"*), com o fato SUBSTITUÍDO e datado.

### `daemon/ipc_handlers.py` + `ipc_server.py` + `app/ipc_bridge.py` — o método
* **`sensor.set {uniq?, giroscopio?, acelerometro?}`** — campo omitido não mexe
  no irmão. O ato são três escritas: registro vivo → perfil → grab;
* a resposta traz **`alcance` (`report` e `evdev`, separados) e `ressalva`**;
* `state_full` publica `sensores.{giroscopio_ligado, acelerometro_ligado,
  grab_do_movimento}` por controle — o **interruptor** ao lado do **valor**,
  que continua sendo publicado (o Hefesto ainda lê; quem deixa de ler é o jogo);
* ponte: `sensor_set_detalhado`, `sensor_set`, `frase_do_interruptor_de_sensor`.

### O DEFEITO QUE A RÉGUA PEGOU, e ele valia o dia inteiro
A primeira versão de `chave_de_sensor` só fazia `strip().lower()`. A mesma peça
tem **duas grafias** nesta casa: o `uniq` do evdev vem com dois-pontos e a chave
do perfil vem sem (`norm_mac`). Com a normalização fraca, ela desligava o giro
pela tela e o perfil gravava sob outra chave — **o interruptor valia até o
replug e voltava calado**. Achado por `test_o_perfil_desliga_o_sensor_daquela_peca`,
e agora há régua comparando `chave_de_sensor` com `norm_mac` diretamente.

---

## Qual mordida prova

`tests/unit/test_o_sensor_desliga_de_verdade.py` — **40 testes**. Quatro
mordidas, cada uma arrancando uma metade diferente:

```
### MORDIDA 1 — arrancado o filtro do _emit (o braço do report)
FAILED ...::test_a_janela_que_chega_ao_vpad_perde_o_giro
FAILED ...::test_o_filtro_e_a_ultima_coisa_antes_do_vpad
2 failed, 26 passed

### MORDIDA 2 — arrancada a união que mantém o reader vivo
FAILED ...::test_o_reader_do_movimento_sobrevive_a_gui_fechada
1 failed, 27 passed

### MORDIDA 3 — arrancado o _reconciliar_grabs (o braço evdev)
FAILED ...::test_o_no_de_movimento_fica_exclusivo_quando_ela_desliga
FAILED ...::test_ligar_de_volta_solta_o_no
FAILED ...::test_desligar_uma_peca_nao_graba_o_no_da_vizinha
FAILED ...::test_o_reader_do_movimento_sobrevive_a_gui_fechada
4 failed, 24 passed

### MORDIDA 4 — arrancada a ressalva do Modo Nativo (a frase honesta)
FAILED ...::test_em_modo_nativo_a_resposta_diz_o_que_nao_alcanca
1 failed, 39 passed

### CURA DEVOLVIDA
40 passed
```

### A PROVA DE BANCADA — os dois braços, com o kernel e o controle de verdade

```json
{
  "peca": "d42f4b0000d8",
  "no_de_movimento": "/dev/input/event22",
  "evdev_antes_do_grab": 2906,
  "grab_state": "held",
  "evdev_com_o_grab": 0,
  "evdev_depois_de_soltar": 2890,
  "grab_state_final": "off",
  "giro_que_a_interface_ainda_le": {"x": 2.62, "y": 0.31, "z": -2.26},

  "hidraw_do_vpad": "/dev/hidraw5",
  "dono_do_hidraw": "02:fe:00:00:00:01",
  "janelas_reais_lidas": 400,
  "cru__quadros_com_giro": 400,
  "cru__quadros_com_accel": 400,
  "filtrado__quadros_com_giro": 0,
  "filtrado__quadros_com_accel": 400,
  "o_resto_da_janela_sobreviveu": true
}
```

Três coisas que este bloco prova, e nenhuma delas é opinião:

* **o braço evdev funciona no kernel de verdade**: 2906 eventos → **0** com o
  grab → 2890 ao soltar (o nó não foi quebrado, o fluxo volta);
* **a interface continua enxergando o giro** com o nó grabado
  (`x=2.62 y=0.31 z=-2.26`) — é o §4 da sprint-mãe cumprido: *"a moldura
  Giroscópio do card continua mostrando o valor"*;
* **o braço do report funciona sobre bytes REAIS** — 400 janelas lidas do
  `hidraw` do vpad: 400/400 com giro no cru, **0/400** depois do filtro,
  **400/400 com acelerômetro intacto**, e o resto da janela (timestamp +
  touchpad) idêntico byte a byte.

### O ensaio

`scripts/ensaios/o_jogo_para_de_ver_o_giro.py` — a sonda SDL headless, o nó de
movimento em paralelo, e um veredito por controle que **recusa concluir** com
basal pobre (`INCONCLUSIVO` abaixo de 5 amostras distintas: controle parado
torna "parou de chegar" indistinguível de "nunca chegou"). Ele **sempre religa**
o sensor ao sair — a bancada é dela.

---

## O que NÃO verifiquei

* **`sensor.set` ponta a ponta contra um daemon vivo.** Medido, não contornado:
  o daemon instalado é o da árvore DELA e é anterior a hoje —
  `~/.local/bin/hefesto-dualsense4unix → …/hefesto-dualsense4unix/.venv/…`,
  symlink de 04/09 05:11. A chamada devolve
  `[-32601] método desconhecido: sensor.set`. O que existe no lugar é o teste
  do handler por dentro (7 casos, incluindo o ramo do Modo Nativo) mais a prova
  de bancada acima. **Depois do próximo `install.sh`, o comando é um só:**
  `scripts/ensaios/o_jogo_para_de_ver_o_giro.py --segundos 3`;
* **o segundo DualSense.** Só um estava na mesa; o caso de duas peças está
  coberto por régua (`test_desligar_uma_peca_nao_graba_o_no_da_vizinha`), não
  por bancada;
* **o Bluetooth.** Toda a medição foi no cabo. A janela de motion do BT é a
  mesma fatia (o `extract_motion_window` já cobre `0x31`), mas o `hidraw` do
  rádio não foi exercitado;
* **um jogo de verdade, com janela.** A sprint pedia *"com o jogo aberto"*; ela
  tem UMA tela, e a instrução do despacho é parar e relatar em vez de abrir
  janela. A sonda SDL é o jogo desta medição — mesma biblioteca, mesmo caminho
  de abertura, sem janela;
* **POR QUE o SDL não abre o `hidraw` do vpad por HIDAPI.** O FATO está medido
  e é reprodutível (em Virtual, com e sem a env do produto, com as duas
  máscaras: `tem_giro=false`); a CAUSA é hipótese não verificada — ver abaixo.
  **MEDIDO EM 05/09/2026, depois do install:** a coluna Virtual desta tabela
  foi reproduzida linha a linha (o `hidraw` do físico em `0600 root` porque o
  `hidraw_broker_hidden` o esconde por desenho; o do vpad legível e não aberto;
  o SDL abrindo `event21`+`event25` por evdev; `GYRO=NAO` nos dois). E a
  pergunta ganhou UM PASSO — não a resposta inteira:

  `SDL_hid_enumerate(0x054C, 0)` devolve **ZERO** dispositivos Sony, e
  `SDL_hid_enumerate(0,0)` devolve **UM** de seis nós `hidraw` — ou seja, o SDL
  não deixa de ABRIR o vpad: ele não o **ENUMERA**. E a diferença de forma
  entre o único que ele enxerga e o vpad está no udev:

  | nó | cadeia de pais | o SDL enumera? |
  | --- | --- | --- |
  | `hidraw0` | `hid` → **`usb`** | SIM |
  | `hidraw5` (vpad) | `hid` → **`misc`** (uhid) | NÃO |

  Um dispositivo `uhid` não tem pai USB, e a enumeração do hidapi do SDL
  caminha por ele. **É o mecanismo provável, e não está provado suficiente:**
  `hidraw1` também pendura em `usb` e também ficou de fora, por razão que esta
  medição não isolou. Quem for fechar isto começa por aí, e a sonda está em
  `scripts/ensaios/o_jogo_para_de_ver_o_giro.py`.

  **O QUE NÃO MUDA, e vale dizer porque é o que ela pergunta:** o giroscópio
  **não morre** no Modo Virtual. O nó de movimento do vpad emite no mesmo
  ritmo do físico — 5901 eventos contra 5854 em quatro segundos. O dado
  atravessa; o que falta é o SDL amarrá-lo ao controle.

---

## O que sobrou para o próximo

### 1. A METADE DE TELA — aba 02, e o endereço é exato
Os botões Giroscópio e Acelerômetro do cartão **continuam recusando dizendo**.
Quem os liga ao método novo é a frente da aba 02. O caminho se fecha em:

* `src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py:1861` — o
  gesto `sensor`, que hoje recusa. Passa a chamar
  `app.ipc_bridge.sensor_set_detalhado(giroscopio=…/acelerometro=…, uniq=…)`;
* o botão pinta de `state_full → controllers[i].inputs`… **não**: de
  `controllers[i]["sensores"]["giroscopio_ligado"]` / `["acelerometro_ligado"]`,
  que é chave NOVA do payload, irmã de `inputs` e publicada mesmo quando o
  controle não tem leitor;
* a linha de ressalva sai de
  `app.ipc_bridge.frase_do_interruptor_de_sensor(corpo)` — `None` quando não há
  nada a dizer, e é ela que carrega o limite do Modo Nativo para a tela;
* `PONTE` do pacote (`a02_controles.py:2735`) precisa ganhar
  `"sensor_set_detalhado"` e `"frase_do_interruptor_de_sensor"`.

### 2. O ACHADO QUE NÃO É MEU, e pode ser grande
**Em Modo Virtual, o SDL não vê giroscópio nenhum** — nem do vpad, nem do
físico, com máscara DualSense, com máscara Xbox e sem env. Se isso valer para
os jogos dela, `D-AUDIO-E-GIRO-NASCEM-LIGADOS` (*"giroscópio nasce LIGADO em
todo jogo"*) está quebrado **no modo padrão**, e não foi este trabalho que
quebrou.

**A hipótese, e ela é NÃO VERIFICADA:** o vpad declara `BUS_USB`
(`integrations/uhid_gamepad.py:94`) sendo um device `uhid` **virtual, sem pai
USB no sysfs**; o backend hidraw do hidapi que o SDL embute pode descartar
exatamente esse caso. O que sustenta: o SDL abriu o `hidraw` do FÍSICO por
HIDAPI sem problema no mesmo processo e na mesma máquina, então udev e hidapi
funcionam — a diferença entre os dois nós é o pai no sysfs.

**O experimento que decide, e é barato:** publicar um vpad declarando
`BUS_BLUETOOTH` e repetir a sonda. Se ele aparecer com `tem_giro=true`, a
hipótese está provada — e aí a decisão (mudar o bus muda o formato de report
esperado) é de outra frente, não desta. `docs/data/mapa-controles.csv`,
`movimento.giroscopio.jogo@dualsense`, afirma hoje `cabo_aciona=sim` com
`cabo_canal=uhid`: a afirmação continua verdadeira sobre a PONTE (os bytes
chegam ao vpad — provado acima, 400/400) e **não** foi verificada sobre o
CONSUMO por um jogo. Duas coisas diferentes, e é a confusão que esta sprint
existiu para não cometer.

### 3. O QUE O INTERRUPTOR NÃO ALCANÇA — e por que não é bug
Em **Modo Nativo** o jogo lê o movimento pelo `hidraw` do FÍSICO, e ali o daemon
não escreve byte nenhum: o kernel entrega o report direto. As três saídas, e as
três estão fechadas:

* zerar bytes — impossível, o daemon não está no caminho;
* esconder o `hidraw` do físico — mataria rumble, gatilhos e lightbar do jogo
  junto;
* comando de firmware que desligue a IMU — **não existe**:
  `docs/data/mapa-controles.csv`, `movimento.imu.ligar` = `existe=nao-tem`, por
  busca fechada em 15/08/2026.

O que sobra em Nativo é o braço evdev, e a resposta do método **diz isso**.
Se ela quiser o desligamento completo em Nativo, a única rota é uma frente
nova: o daemon interpor um vpad também em Nativo — que é o Modo Virtual com
outro nome, e portanto **decisão dela**, não engenharia.

### 4. Arquivos que toquei fora da minha posse declarada
Nenhum deles é `nao_toca` e nenhum é reivindicado por sprint desta onda:

| arquivo | o que entrou |
| --- | --- |
| `core/physical_report_reader.py` | 2 hunks: o `uniq_do_hidraw` e o filtro no `_emit` |
| `integrations/…` | **nada** — `uhid_gamepad.py` não foi tocado |
| `daemon/ipc_server.py` | 1 linha na tabela de despacho (a mesma que a D1 e a D2 usaram) |
| `profiles/manager.py` | `apply_controller_sensores` + 1 chamada no `activate` |
| `tests/unit/test_perfil_por_controle_o_campo_espera_o_caminho.py` | o fio de gatilho `test_os_sensores_nao_tem_por_onde_ser_desligados` virou `test_o_interruptor_de_sensor_existe_e_e_por_peca` — era o que a própria docstring dele mandava fazer no dia em que o interruptor nascesse |

### 5. A ARMADILHA DESTE DIA — `git stash` numa worktree é para tudo, menos para o que você pediu

Custou a árvore inteira por dez minutos, e o erro foi meu. Para conferir se um
portão vermelho era herdado ou meu, tentei tirar UM arquivo do caminho:

```bash
git stash push --staged -- docs/data/mapa-controles.csv   # a intenção: um arquivo
```

O `--staged` **ignorou o pathspec** e guardou o índice INTEIRO — as 16 mudanças
da leva, os quatro arquivos novos incluídos —, e o `stash pop` seguinte
devolveu o índice sem devolver os arquivos ao disco: `git status` passou a
mostrar `AD` (no índice, ausente na árvore) e `virtual_motion.py`,
`test_o_sensor_desliga_de_verdade.py`, o ensaio e este relatório sumiram do
disco na frente do comando seguinte.

**O que salvou foi o índice**, e a recuperação é uma linha:

```bash
git checkout-index -a -f     # reescreve a árvore inteira a partir do índice
```

O que se perdeu foram só as edições posteriores ao último `git add -A` (as
citações do CSV e o docstring do `ipc_server`), refeitas em dois minutos.

**A regra que isso deixa, e ela é maior que este dia:** nesta casa o `.git` é
**um só para todas as worktrees**, e a pilha de `stash` também — a própria lista
já carrega três entradas chamadas *"devolvido: pop cruzado de outra worktree"*.
Um `stash` aqui não é local: é um objeto compartilhado com sete árvores de
agente em voo. **Para isolar uma mudança e medir, o caminho é `git add -A`
seguido de `git checkout-index -a -f` quando precisar voltar** — ou uma cópia
do arquivo em `/tmp`, que foi o que usei nas quatro mordidas e não custou nada.

