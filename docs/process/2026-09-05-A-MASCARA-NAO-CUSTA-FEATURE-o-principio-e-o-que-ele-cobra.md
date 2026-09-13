# A MÁSCARA NÃO CUSTA FEATURE — o princípio, e o que ele cobra

**05/09/2026.** Esta é a decisão de produto mais larga do dia, e ela não é de
aba nenhuma. Ela nasceu de uma pergunta pequena — *"dá para tirar da tela o
aviso de que o rádio pode não aguentar a Conexão Nativa?"* — e a resposta dela
mudou o critério com que toda frase de limitação deste produto passa a ser
julgada.

---

## 1. A PALAVRA DELA

> *"Pode medir, mas a ideia é que o de falhas e limitações. Criamos mecanismos <!-- noqa-acento: citação literal dela — a grafia não se corrige; o FATO sim -->
> pra usarmos todas as feature. Exemplo controle do Xbox não tem microfone mas <!-- noqa-acento: citação literal dela -->
> se o Mic do dualsense passa a ser lido a parte via Mic virtual. Usaríamos <!-- noqa-acento: citação literal dela -->
> essa feature do controle mesmo no Xbox. Mesmo problema BT. Hj já funciona <!-- noqa-acento: citação literal dela -->
> assim, sem a parte do Mic virtual."* <!-- noqa-acento: citação literal dela -->

Ela não pediu uma frase melhor. Ela recusou a categoria inteira.

## 2. O PRINCÍPIO, EM UMA FRASE

**A máscara não custa feature: o que o aparelho FÍSICO sabe fazer continua
disponível, qualquer que seja a máscara que o jogo vê e qualquer que seja o
transporte — e quando a máscara não tem o canal, o Hefesto CONSTRÓI o canal.**

O corolário, e é ele que decide trabalho: **o Hefesto não explica a própria
falha — ele a conserta.** Cada linha do inventário abaixo que ainda se perde é
um defeito na fila, e não uma frase de tela a redigir.

**E o princípio não é novo — ela já o tinha aplicado, em outro nome.** Em
04/09, sobre o giroscópio e o acelerômetro, ela escreveu *"ele tem que
funcionar de verdade. ambos independente do modo e da mascara"*, e a frase está <!-- noqa-acento: citação literal dela -->
no cabeçalho do módulo que a materializou (`daemon/sensor_hub.py:54`). O que
mudou em 05/09 é o alcance: aquilo era sobre dois sensores, isto é sobre tudo.

---

## 3. O INVENTÁRIO MEDIDO — o que a máscara Xbox 360 custa hoje

Medido em 05/09/2026 lendo `src/hefesto_dualsense4unix/`. A pergunta é: quando
o jogo vê um Xbox 360 em vez de um DualSense, o que deixa de existir?

### 3.1 O caminho, em três linhas de código

A fábrica de gamepad virtual recebe **cinco** canais de volta do jogo para o
aparelho — `rumble_sink`, `trigger_sink`, `lightbar_sink`, `player_led_sink` e
`session_end_sink` (`integrations/virtual_pad.py:154-159`). O daemon monta os
quatro últimos em `make_primary_replica_sinks`
(`daemon/subsystems/gamepad.py:1484-1495`) e os entrega na criação do vpad
(`daemon/subsystems/gamepad.py:2251-2261`).

Na máscara `dualsense`, os cinco chegam ao backend uhid
(`integrations/virtual_pad.py:274-280`).

Na máscara `xbox`, o gate de `_try_uhid` devolve *"use o uinput"* sem sequer
tentar (`integrations/virtual_pad.py:267-270`), e a linha que cria o vpad é
esta:

    integrations/virtual_pad.py:231
        pad = UinputGamepad.for_flavor(key, rumble_sink=rumble_sink)

**Cinco canais entram na fábrica; UM sai.** Os outros quatro são recebidos pela
assinatura e não chegam a lugar nenhum.

O espelho de motion nem sobe: `daemon/subsystems/gamepad.py:1913` é
`if getattr(device, "backend", None) != "uhid": return`.

E o vpad uinput não tem onde pôr o que sobra — ele declara oito eixos e onze
botões (`integrations/uinput_gamepad.py:280-297`), mais `EV_FF` quando há
rumble (`:298-306`). Não existe `forward_motion`, `forward_touchpad_click`,
`forward_battery` nem `forward_jack` no arquivo inteiro: `grep` devolve zero.

### 3.2 Ela está CERTA — três features não custam nada, e a tela já o diz

| feature | por onde ela vai, e por que a máscara não a alcança |
| --- | --- |
| **Vibração** | O jogo pede por `EV_FF` no próprio vpad uinput, e o pedido volta aos motores do físico pelo `rumble_sink` (`integrations/uinput_gamepad.py:773`, ligado em `daemon/subsystems/gamepad.py:2257`). A máscara Xbox **tem** este canal. |
| **Microfone** | Não passa pelo gamepad. Vai por PipeWire — nó ALSA no cabo, ponte Opus-em-HID no rádio. |
| **Alto-falante** | Idem: sink do PipeWire, e o firmware escrito pelo daemon por um `hidraw` que é dele. |

**A medição que fecha o microfone.** `grep` por `native_mode`,
`gamepad_emulation_enabled`, `flavor` e `mascara` nos seis arquivos do caminho
do microfone — `daemon/subsystems/mic_da_mesa.py`,
`daemon/subsystems/luz_do_mic.py`, `daemon/subsystems/bt_mic.py`,
`integrations/eleicao_de_microfone.py`,
`integrations/dualsense_bt_audio.py` e `integrations/fontes_de_captura.py` —
devolve **uma** ocorrência, e ela é a palavra "mascara" num comentário sobre
bits (`daemon/subsystems/luz_do_mic.py:137`). **O microfone é cego à máscara
por construção, e não por acaso.**

E o próprio produto já afirma isso na tela, na frase de preço da máscara:

    app/actions/home_actions.py:377-382
        "Nesta máscara o jogo não recebe giroscópio, acelerômetro nem
         touchpad — o controle de Xbox não tem esses três, então não há onde
         eles caberem. Vibração, microfone e alto-falante continuam
         funcionando. (…)"

**Confirmada: ela está certa quando diz *"hoje já funciona assim"*.** O caso
que ela nomeia — o microfone do DualSense usado sob a máscara Xbox — já é
verdade, e é verdade nos dois transportes.

**E o precedente do princípio é mais velho que o princípio.** Por Bluetooth o
DualSense **não publica fonte de áudio nenhuma**: ele não implementa A2DP, HFP
nem HSP, e o SDP dele só anuncia HID e PnP
(`integrations/dualsense_bt_audio.py:6-16`, com a confirmação do mantenedor do
BlueZ citada ali). O Hefesto não escreveu na tela que o microfone se perde no
rádio: ele leu os quadros Opus tunelados dentro do HID e **construiu a fonte**,
um `module-pipe-source` alimentado por fifo
(`integrations/dualsense_bt_audio.py:542-558`). É exatamente o gesto que ela
descreve, feito em 25/07/2026, antes de ter nome.

### 3.3 Ela está INCOMPLETA — cinco canais ainda se perdem

Cada linha aqui é um defeito, pelo corolário da §2.

| # | o que se perde sob a máscara Xbox | a prova |
| --- | --- | --- |
| 1 | **Giroscópio e acelerômetro** entregues ao jogo pelo gamepad virtual | sem `forward_motion` no uinput; o espelho nem sobe (`daemon/subsystems/gamepad.py:1913`) |
| 2 | **Touchpad** entregue ao jogo pelo gamepad virtual | sem `forward_touchpad_click`; não há eixo de dedo nas capabilities (`integrations/uinput_gamepad.py:280-297`) |
| 3 | **Gatilhos adaptativos que O JOGO pede** | `trigger_sink` cai no chão em `integrations/virtual_pad.py:231` |
| 4 | **Lightbar que O JOGO pinta** | `lightbar_sink`, mesma linha |
| 5 | **LEDs de jogador que O JOGO acende** | `player_led_sink`, mesma linha |

Fora da conta, porque são anúncio e não feature: **bateria** e **jack de fone**
também deixam de ser encaminhados ao jogo (`forward_battery` e `forward_jack`
existem só no uhid).

**O que NÃO se perde nas cinco linhas, e é a metade que a frase da tela apaga:**
o Hefesto continua mandando nos gatilhos, na lightbar e nos LEDs do aparelho
FÍSICO em qualquer máscara — `grep` por `flavor`/`mascara`/`native_mode` em
`src/hefesto_dualsense4unix/core/` não devolve um único gate. **O que se perde é
a AUTORIA do jogo, não a feature.** E os sensores continuam publicados pelo
kernel no nó "Motion Sensors" do controle físico, livre nos dois modos — a
tabela medida está no cabeçalho de `core/virtual_motion.py`. **FATO SUBSTITUÍDO
em 13/09/2026:** o zero em Modo Virtual era da libSDL2 2.30.0 do sistema; nas
bibliotecas dos runtimes da Steam o vpad expõe os dois sensores, e o SDL pareia
o nó «Motion Sensors» pelo `uniq` (a tabela está na
[SENSORES-NO-JOGO-02](sprints/2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md),
§1). O canal alcança `evtest`, emuladores e o SDL; se ele leva o giro ao jogo
sob a máscara Xbox continua sem medição.

### 3.4 O DEFEITO QUE A MEDIÇÃO ACHOU DE LAMBUJA: o produto perde cinco e a tela conta dois

A lista que a interface usa para dizer *"esta máscara apaga este recurso"* tem
**dois** itens:

    app/widgets/controller_card.py:1352-1354
        RECURSOS_SEM_MASCARA_XBOX = frozenset({"giroscopio", "touchpad"})

A linha de recursos do card fala de **seis**: giroscópio, vibração, gatilho,
luz, clique do touchpad e som do controle
(`app/widgets/painel_no_jogo.py:97`, montada de
`app/widgets/controller_card.py:1426-1433`).

O que acontece com os três que sobram — gatilho, luz e som do controle — sob a
máscara Xbox: eles **não** caem no ramo do impossível
(`app/widgets/controller_card.py:1642-1644`), seguem para o carimbo de
atividade, e o carimbo é uma propriedade que **só o vpad uhid tem**
(`integrations/uhid_gamepad.py:1258`; o IPC lê com `getattr` e devolve `{}` para
o uinput, `daemon/ipc_handlers.py:391-393`). Sem carimbo, a situação é
`SITUACAO_NUNCA`, cuja palavra na tela é **"sem pedido ainda"**
(`app/widgets/painel_no_jogo.py:124-128`).

**Então a tela dela diz "sem pedido ainda" sobre três recursos que o jogo NÃO
PODE pedir naquela máscara.** É a mesma família de defeito que
`RECURSOS_SEM_MASCARA_XBOX` nasceu para matar — o comentário dele
(`app/widgets/controller_card.py:1435-1441`) diz com todas as letras que o
estado impossível *"é a mais valiosa das quatro"* situações. Ele foi escrito
para dois recursos e o buraco tinha cinco.

---

## 4. O QUE O PRINCÍPIO COBRA

**A regra de triagem, e ela é o produto desta página:** diante de uma feature
que a máscara não carrega, há duas perguntas, nesta ordem.

1. **A feature tem um canal PRÓPRIO, fora do gamepad?** Se tem, ela não é da
   máscara e o trabalho é usá-lo. Foi o que aconteceu com o microfone (PipeWire),
   com o alto-falante (PipeWire), com o giroscópio e o touchpad enquanto nós de
   evdev, e com o touchpad virando mouse na aba Navegação — nenhum desses
   caminhos consulta a máscara.
2. **Não tem? Então o Hefesto CONSTRÓI o canal**, como construiu a fonte de
   captura do rádio a partir de quadros Opus dentro do HID.

**Escrever na tela que a feature se perdeu não é resposta a nenhuma das duas.**

O que isso cobra, linha a linha do §3.3:

| linha | o que o princípio manda fazer |
| --- | --- |
| 1 · giroscópio e acelerômetro | O canal próprio EXISTE (nó de evdev do físico, livre nos dois modos). **FATO SUBSTITUÍDO em 13/09/2026:** o zero em Modo Virtual era da libSDL2 2.30.0 do sistema; nas bibliotecas dos runtimes da Steam o vpad expõe os dois sensores, e o SDL pareia o nó «Motion Sensors» pelo `uniq` (a tabela está na SENSORES-NO-JOGO-02, §1). A sprint que nasce aqui MEDE se há caminho até o jogo sob a máscara Xbox — e se não houver, a frase honesta diz o que FAZER, não pede desculpa. |
| 2 · touchpad | Idem, com um canal a mais já construído e já cego à máscara: o touchpad como mouse (`integrations/uinput_mouse.py`, sem um único gate de máscara). |
| 3, 4, 5 · gatilhos, lightbar e LEDs do jogo | Não há canal próprio: o jogo fala com o vpad ou não fala. **A cura barata e verdadeira é a §5** — parar de dizer que a feature morreu, porque ela não morreu: só o jogo deixou de ser o autor. |
| bateria e jack | Anúncio, e o anúncio tem dono fora do gamepad (o `state_full`). |

**E o primeiro trabalho concreto é o exemplo dela**, porque é o único em que ela
mesma nomeou o que falta: *"sem a parte do Mic virtual"*. Ele está escrito em
[ONDA5-MIC-VIRTUAL-01](sprints/2026-09-05-ONDA5-MIC-VIRTUAL-01-o-microfone-do-dualsense-sob-a-mascara-xbox.md).

---

## 5. A CONSEQUÊNCIA IMEDIATA: as duas frases do quadro Modo SAEM

A decisão **10-Q6** dela perguntava *onde* ficam, na aba Perfis, as duas frases
que a janela antiga tem dentro do quadro Modo
([DECISÕES DELA · 10 perfis](sprints/2026-09-04-DECISOES-DELA-10-perfis.md), §06).
As três opções que eu ofereci discutiam colocação: hover, linha, as duas
visíveis.

**A premissa das três é o que este princípio manda eliminar.** As frases são:

    app/actions/home_actions.py:377-382    o preço da máscara
    app/actions/home_actions.py:493-497    o aviso de rádio frágil

A primeira diz *"o jogo não recebe giroscópio, acelerômetro nem touchpad"* — e a
§3.4 mostra que ela conta dois de cinco, chama de perda o que é troca de autoria,
e é lida ao lado de uma linha que diz "sem pedido ainda" sobre o que não pode ser
pedido. A segunda diz *"Se o jogo não vir o controle, use o cabo USB ou volte
para a emulação de gamepad"* — que é o produto mandando ELA operar o contorno que
ele mesmo sabe fazer.

**As duas SAEM do quadro Modo da aba Perfis.** Não porque a informação seja
falsa, mas porque **o lugar dela não é a tela**: uma é um defeito de contagem que
a §3.4 nomeia, a outra é um contorno que o produto tem de executar sozinho.

**O que fica no lugar, e é decisão de produto, não de desenho:**

* o quadro Modo mostra a escolha, e só;
* onde houver diferença real entre as máscaras, ela aparece como **o que muda**,
  nunca como *"você vai perder"* — e depois de a §3.4 fechar, porque hoje a
  contagem está errada e publicá-la seria publicar o erro;
* o aviso de rádio frágil vira **trabalho**: o modo Nativo em Bluetooth com um
  jogo que não enxerga o controle é exatamente a situação para a qual o gamepad
  virtual existe.

**O que NÃO sai:** as duas funções continuam com dono único e continuam sendo
lidas pela janela estável (`app/actions/home_actions.py:385-392` e `:589-611`,
com a segunda chamada também de `app/actions/profiles_actions.py:162-186`).
Apagar função com dois leitores para tirar uma frase de UMA tela é como esta
casa fabrica divergência silenciosa. Sai a frase do quadro Modo da aba Perfis;
a função fica até o defeito que ela descreve estar fechado.

---

## 6. NADA SE PERDEU

O que existe hoje e tem de continuar existindo depois de tudo isto:

* **A máscara Xbox continua existindo, e continua sendo a escolha certa em
  jogos XInput-only.** Ela não é degradação: `_try_uhid` devolve
  `(None, None)` — motivo nenhum — para o sabor `xbox`, e o comentário diz por
  quê (`integrations/virtual_pad.py:267-270`). Máscara Xbox em uinput é o
  desenho normal, e o banner de degradação sabe disso
  (`app/actions/home_actions.py`, docstring de `vpad_degradation_text`).
* **A vibração continua atravessando a máscara Xbox.** Foi a razão de ela ter
  virado obrigatória um dia (`integrations/virtual_pad.py:6-14`).
* **O microfone continua cego à máscara.** O `grep` da §3.2 tem de continuar
  devolvendo uma ocorrência, e ela tem de continuar sendo o comentário sobre
  bits.
* **O mudo do firmware continua sendo do `hid-playstation`.** Nenhuma cura
  desta página escreve no `common[9]`
  (`integrations/eleicao_de_microfone.py:15-20`).
* **`RECURSOS_SEM_MASCARA_XBOX` não vira uma lista de cinco por decreto.** Três
  das cinco linhas do §3.3 são troca de autoria, não ausência de recurso —
  marcá-las "impossível" trocaria uma mentira por outra.
* **A regra da casa que isto NÃO revoga:** quando o aparelho não faz, o produto
  diz. `movimento.imu.ligar` continua `existe=nao-tem` no
  `docs/data/mapa-controles.csv` por busca fechada, e quem chama `sensor.set`
  continua recebendo esse limite ESCRITO na resposta
  (`core/virtual_motion.py`, cabeçalho). **O princípio é sobre a MÁSCARA e o
  TRANSPORTE, que são escolhas nossas — não sobre o silício.**
