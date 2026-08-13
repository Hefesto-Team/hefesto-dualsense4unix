# Os três modos do controle

> **Qual máscara para qual jogo?** A lista de compatibilidade, com o que foi
> medido em cada título, está em [jogos-e-mascaras.md](jogos-e-mascaras.md) —
> é a fonte da verdade sobre jogos específicos.

A aba **Início** tem um seletor chamado *"O que o controle faz agora"*. Ele decide
quem fala com o DualSense. Escolher errado é a origem da maior parte dos
"não funciona": o controle está no modo de mesa e o jogo não o vê, ou está solto
para a Sony e a sua configuração de luzes não vale.

| Modo | O que acontece | Quando usar |
|---|---|---|
| **Controlar o PC** | O controle move o cursor e digita: stick e touchpad viram mouse, botões viram teclas. | Navegar no sofá, Big Picture, escolher jogo. |
| **Jogar pelo Hefesto** | O Hefesto cria um **controle virtual** e é ele que o jogo enxerga. | O padrão para jogar. É o único modo com co-op local. |
| **Conexão Nativa (Sony)** | O Hefesto solta o controle. O jogo fala com o DualSense físico, sem intermediário. | Jogos que já falam DualSense nativamente e fazem tudo sozinhos. |

Pela linha de comando os mesmos três estados são `mouse on`, `gamepad on` e
`native on`.

> **O seletor mora no quadro "Quando o jogo abrir", e o nome é literal**
> (08/08/2026). O jogo lê modo e máscara **uma vez, na abertura** — clicar num
> modo com o jogo já aberto não muda nada dentro dele. O clique **marca** a
> escolha; é o **Aplicar** do rodapé que a aplica, e quando a mudança só valeria
> na próxima abertura com um jogo na frente, a janela **pergunta** em vez de
> aplicar por cima. Cor, brilho, gatilho, vibração e microfone — esses sim mudam
> na hora — moram em outras abas.

## O touchpad é touchpad do sistema

**Em qualquer um dos três modos**, o dedo no touchpad do DualSense move o cursor
do desktop pelo libinput, exatamente como move quando o controle é plugado sem o
Hefesto instalado. O clique dele é clique de mouse.

Isso é decisão dela, de 09/08/2026, a partir do que ela mediu com o controle na
mão: *"quando eu conecto o controle DualSense no PC via BT ou cabo, ANTES do
Hefesto, o touchpad funciona como mouse. No Hefesto impedimos isso de funcionar
em todos os modos. A ideia do touchpad é ele voltar a funcionar assim, seja no
modo nativo ou dualsense"*.

> **NOTA DATADA — 09/08/2026: até esta data o Hefesto apagava o touchpad
> físico, e em todos os modos.** Uma regra udev com curinga tirava o touchpad do
> libinput em USB, Bluetooth e no controle virtual, nos três modos — inclusive
> na **Conexão Nativa**, onde não há emulação nenhuma com que brigar.
> **GRAU: MEDIDO** no nó vivo dela (`/run/udev/data/c13:68`):
> `ID_INPUT_TOUCHPAD=1` **e** `LIBINPUT_IGNORE_DEVICE=1` — o dedo andava e o
> cursor não. A regra nasceu de duas brigas reais, e as duas continuam curadas,
> cada uma pelo lado certo da cerca:
>
> - **o toque em dobro** (21/07) era o libinput enxergando dois ponteiros
>   alimentados por um dedo — o touchpad físico e o do **controle virtual**, que
>   recebe os pontos de toque copiados do report cru. Hoje quem fica fora do
>   libinput é **só o do controle virtual**, para sempre e em todos os modos: o
>   jogo lê o touchpad pelo HID do vpad, nunca pelo ponteiro do libinput. Nada
>   se perde e o dobro não volta;
> - **o cursor engasgado** (26/06) era o Hefesto e o libinput movendo o mesmo
>   cursor a partir do mesmo dedo. A cura agora é de **runtime** e mora no
>   produto: quando o sistema é o ponteiro, o leitor de touchpad do Hefesto não
>   acumula movimento nem entrega região de clique ao teclado emulado. Um dono
>   por vez, decidido pelo estado real do nó.
>
> **O preço, aceito por ela com o número na mesa:** as três regiões do touchpad
> (esquerda / meio / direita) saíram da aba Navegação. Com o clique já sendo
> clique de mouse, somar a tecla faria um clique **apagar texto** — o padrão de
> fábrica da região esquerda era Backspace. Voltar é a mesma decisão do outro
> lado, e as duas coisas andam juntas.
>
> **Validado por ela** no desktop e dentro do jogo, sem dobrar.

Nada disso é o **mouse emulado**, que é outra coisa e mora na aba Navegação: o
mouse emulado move o cursor pelo **analógico esquerdo**, só existe no modo
"Controlar o PC" e tem interruptor próprio. Os dois podem estar de pé ao mesmo
tempo — dois caminhos até o mesmo cursor, cada um com o seu gesto. Ver
[`interface.md`](interface.md#navegação).

> **Mudou de nome em 06/08/2026.** O terceiro modo se chamava
> **"Jogar direto (Sony)"**. O nome caducou por decisão dela — *"Jogar direto é
> péssimo também. Já tinha pedido pra deixarmos: Conexão Nativa (Sony)"* — e o
> motivo está na própria tabela acima: os outros dois rótulos dizem para ONDE o
> controle fala (o PC, o Hefesto), e "direto" não dizia o que a coisa é. O que
> acontece de fato é o Hefesto **soltar a conexão** e o jogo falar com o
> DualSense físico. Só o rótulo mudou: na linha de comando continua `native on`,
> e perfis salvos com `"kind": "native"` seguem valendo.

## Jogar pelo Hefesto: a máscara

No modo "Jogar pelo Hefesto" existe um segundo seletor — *"O jogo vê o controle
como:"*. Ele muda que tipo de controle virtual sobe:

| Máscara | Como sobe | O que o jogo recebe |
|---|---|---|
| **DualSense (botões PlayStation)** — padrão | device HID real via `/dev/uhid` | botões e eixos, vibração, gatilhos adaptativos, lightbar, LEDs de jogador, giroscópio e touchpad |
| **Xbox 360** | device evdev via `/dev/uinput` | botões, eixos e vibração — e só |

A máscara DualSense é a completa: o controle virtual é um DualSense de verdade
para o kernel, o `hid_playstation` faz bind nele, e o que o jogo escreve nesse
controle (efeito de gatilho, cor da lightbar, LEDs de jogador) é **replicado no
controle físico**. O movimento do giroscópio segue no sentido inverso: é lido do
físico e espelhado no virtual, para o jogo receber a mira por movimento.

> **NOTA DATADA — 06/08/2026: essa replicação SOBRESCREVE o que você escolheu, e
> este texto não dizia.** Medido com o Sackboy aberto: a lightbar voltou ao
> **azul da Sony** (aplicar a sua cor muda por um instante e o jogo devolve) e os
> gatilhos ficaram **moles** apesar da Resistência aplicada. Quando o jogo pede
> luz ou gatilho, **é o pedido do jogo que chega ao seu controle** — o Hefesto
> repassa fiel, sem escalar e sem trocar, porque mexer nisso seria mentir sobre o
> que o jogo pediu. Você recupera a sua cor e os seus gatilhos quando o jogo
> fecha.
>
> **A vibração é a exceção, e nela você vence:** com uma vibração fixada por
> você, o Hefesto **ignora** a do jogo. Registro em
> [CONTROLE-SONY-MEDIDO-01](../process/sprints/2026-08-06-CONTROLE-SONY-MEDIDO-01-o-experimento-que-decide-metade-da-doutrina.md).

A **intensidade** da aba Rumble vale para as duas vibrações, e não só para a do
jogo — este texto dizia que ela só valia sem vibração fixada, e o rodapé da
própria aba dizia o contrário (*"os valores acima ainda passam pela intensidade
escolhida ali em cima"*). Quem tem razão é o rodapé, e são três caminhos no
código, todos com a mesma conta `bruto × intensidade`, saturando em 255:

| o que vibra | onde a intensidade entra |
|---|---|
| o que o **jogo** pede | `daemon/subsystems/gamepad.py`, `apply_game_rumble` |
| o que **você fixa** em "Testar motores" | `daemon/ipc_handlers.py`, `_handle_rumble_set` |
| o mesmo, re-afirmado a cada 200 ms | `daemon/subsystems/rumble.py`, `reassert_rumble` |

A diferença entre eles é outra, e é a que importa aqui: **o do jogo só existe
quando existe controle virtual.** Ele mora no caminho de saída do gamepad
virtual; na Conexão Nativa (Sony) não há gamepad virtual nenhum, e a intensidade
não alcança a vibração do jogo — que sai direto do DualSense, sem nós no meio.
Nesses casos a aba Rumble avisa em cima dos quatro botões, em vez de deixar você
mexer num controle deslizante que não está ligado a nada.

> **NOTA DATADA — 11/08/2026: nesse mesmo estado a vibração do jogo não só
> escapava da intensidade — ela MORRIA.** Sem controle virtual e fora da Conexão
> Nativa, o jogo escreve a vibração no DualSense físico, e o Hefesto
> reconfirmava o estado daquele controle a cada meio segundo **zerando os
> motores** que o jogo tinha acabado de ligar. **GRAU: MEDIDO** com quatro
> DualSense na mesa, dois no cabo e dois no rádio: com o serviço vivo, 40 s de
> vibração produziram nada no cabo e um único tranco no rádio; com o serviço
> parado, os mesmos 40 s foram contínuos nos dois. E a causa fechou **com
> número** — subindo o intervalo da reconfirmação de 0,5 s para 8,0 s, a
> vibração passou a durar **oito segundos exatos**.
>
> **Corrigido:** a reconfirmação deixou de ser eterna e passou a valer só na
> janela logo depois de uma mudança de verdade. Na **Conexão Nativa (Sony)** o
> defeito nunca existiu, porque ali o Hefesto já não escrevia nada no controle —
> e é por isso que ele parecia intermitente. Sintoma, confirmação e o que fazer
> se voltar: [`troubleshooting.md`](troubleshooting.md#19-a-vibração-do-jogo-dura-um-instante-e-morre).

A máscara Xbox 360 é o piso de compatibilidade — para jogos que só aceitam
gamepad da Microsoft. Ela carrega botões, eixos e vibração, e nada mais: você
perde **cinco coisas** — giroscópio, touchpad, cor da lightbar, gatilhos
adaptativos e leitura de bateria.

Isso não é limitação do Linux nem falta de trabalho aqui: é o **formato do
controle que a máscara imita**. O relatório de um Xbox 360 tem vinte bytes,
treze deles usados por botões, analógicos e gatilhos, e não sobra lugar para
movimento, toque, cor ou carga. A demonstração, em três camadas independentes,
está em [a pilha do Steam Input](../protocol/pilha-steam-input-xpad-sdl.md),
seção 1.5.

> Se o `/dev/uhid` não estiver acessível, ou o kernel recusar o device, a máscara
> DualSense **cai para uinput** — e aí ela vira uma Xbox com botões de PlayStation,
> sem os extras. A aba Início mostra um aviso quando isso acontece, e diz por quê.
> É o campo `gamepad_emulation.degraded_motivo` no `status`.

## Co-op local

Com dois ou mais controles no modo "Jogar pelo Hefesto", cada controle vira um
jogador: um controle virtual por pessoa, LED de jogador de 1 a 4, numeração
estável por endereço MAC (replugar recupera o mesmo número).

> **NOTA DATADA — 12/08/2026: o número é estável para QUEM VOLTA, e não para
> quem ficou.** Grau *o aparelho obedeceu*, com resultado **parcial** — ensaio
> `comb-slot-jogador-2200` ([`../data/ensaios.csv`](../data/ensaios.csv), linha
> 78), observado com quatro DualSense na mesa quando um deles caiu sozinho.
>
> Quando o controle caiu, o Hefesto **renumerou os que ficaram**: quem era
> **jogador 4 virou jogador 3**. Quando o controle voltou, o mesmo controle
> voltou a ser jogador 4. Ou seja: a recuperação é **reversível e simétrica**, e
> a frase acima continua verdadeira **para o controle que sai e volta** — mas o
> número dos **outros** se mexe no meio do caminho.
>
> **Se isso é o desejado é DECISÃO DELA**, e está registrada como aberta: num
> co-op em andamento, o jogador 4 virar 3 troca quem é quem no meio da partida.

Controles externos (Nintendo Pro; 8BitDo em modo Switch no cabo ou em modo
DirectInput/PS4 por Bluetooth — ver
[`troubleshooting-8bitdo.md`](troubleshooting-8bitdo.md)) entram na contagem como
jogadores e recebem número de LED próprio, acima da faixa reservada aos DualSense.

> **NOTA DATADA — 06/08/2026: metade da frase acima caducou. A luz é verdade; a
> contagem, não.** Os dois parágrafos desta seção ficam registrados porque
> decisão medida não se apaga — e o *"cada controle vira um jogador"* de cima
> vale para **DualSense**, não para controle de outra marca.
>
> **O que continua verdade:** o externo **recebe número e luz próprios**. O
> daemon escreve isso de fato — no journal de 06/08 às 21h08,
> `external_led_written slot=2` no Pro Controller e `slot=3` no 8BitDo.
>
> **O que caducou:** *"entram na contagem como jogadores"*. **GRAU: MEDIDO** em
> 06/08/2026 às 22h40, com um DualSense, um Nintendo Pro e um 8BitDo ligados:
>
> ```
> $ hefesto-dualsense4unix coop status
> jogadores ativos: 1
>
> $ hefesto-dualsense4unix controller list
>   Controle 1 — BT
> ```
>
> Três controles na mesa, **um** jogador contado e **um** controle listado. O
> co-op só conta DualSense; o externo não ganha controle virtual próprio e chega
> ao jogo como o gamepad nativo que já era.
>
> **Duas ressalvas sobre a luz, medidas na mesma noite:** o número escrito pelo
> Hefesto **não é** o número que o jogo usa, e o plástico pode mostrar outra
> coisa — o Pro Controller acendeu **jogador 1 e jogador 2 juntos** (é o padrão
> do `hid-nintendo` para "não numerado"), e o controle virtual e o DualSense
> físico acenderam **o mesmo jogador 3** ao mesmo tempo.
>
> **CORREÇÃO DATADA — 07/08/2026: as duas ressalvas acima estavam mal lidas.** Na
> barra do DualSense, o número do jogador é o **desenho** das cinco lâmpadas, não
> o nome de uma delas: só a do meio acesa é o **jogador 1**; a primeira, a do meio
> e a última acesas são o **jogador 3**. A medição foi refeita em 07/08 lendo as
> cinco: o controle virtual era o jogador **1** e o DualSense físico era o jogador
> **3** — **nunca houve dois controles no mesmo número.** Ela mesma tinha lido
> certo, de olho: *"o dualsense branco dessa vez conectado como player 3"*. E o
> padrão do Pro Controller (verdes 1 e 2) é **jogador 2 escrito pelo próprio
> Hefesto**, não um padrão do `hid-nintendo`.
>
> **O que continua verdade, e é o que importa para você:** o número que o Hefesto
> acende **não é** o número que o jogo usa. Um mesmo controle pode mostrar `3` no
> plástico e chegar ao jogo como jogador 1.
>
> **GRAU: SEM PROVA** — que o jogo veja os três como jogador 1; é o relato dela,
> e o caminho até o jogo não foi instrumentado. A cura são as entregas E3 e E4 da
> [LUGAR-À-MESA-01](../process/sprints/2026-08-06-LUGAR-A-MESA-01-tres-controles-ligados-e-um-jogador-so.md),
> autorizadas por ela em 07/08/2026 **só depois da MÁSCARA-01**.

Uma função continua sendo exclusiva do jogador 1: o **botão de microfone**. Ele é
lido só do controle primário e o sistema tem um microfone só — o botão Mute dos
jogadores 2 em diante não muta nada.

## Steam: as Opções de Inicialização

Um jogo pode enxergar o controle **duas vezes**: o físico e o virtual. O
instalador resolve isso sozinho — ele coloca o atalho `hefesto-launch` nas Opções
de Inicialização dos seus jogos (sempre com a Steam fechada) e migra ajustes
antigos.

Se um jogo novo aparecer com o controle duplicado:

1. Aba **Sistema** → **"Aplicar aos jogos da Steam"**, com a Steam fechada.
2. Como recurso manual, o botão **"Copiar opções p/ jogos"** copia a linha certa
   para você colar em Steam → jogo → Propriedades → Opções de inicialização.

O `hefesto-launch` decide na hora o que cada jogo precisa. Com o Hefesto desligado
ele sai do caminho: o pior caso é o controle duplicado, nunca zero controles.

> **NOTA DATADA — 06/08/2026, para evitar uma confusão que esta página convida
> (e que a `CONTROLE-SONY-MEDIDO-01` **refuta** do outro lado).**
> A frase acima — *"com o Hefesto desligado ele sai do caminho"* — fala do
> lançador com o **serviço parado**, e **não** da lista de exceções de Steam
> Input. São coisas diferentes, e esta página nunca mencionou a segunda. Quem
> procura *"marquei um jogo e ele mudou de comportamento"* está em
> [jogos-e-mascaras.md](jogos-e-mascaras.md), na seção *"suporte a DualSense pela
> Steam"*. E o que foi medido em 06/08 vale registrar aqui também: **na lista de
> exceções o Hefesto continua escrevendo no seu controle** — a sua cor fica, os
> seus gatilhos seguram; o que ele entrega ao jogo é a **entrada**. O registro
> da medição, com journal e carimbo, é a sprint `CONTROLE-SONY-MEDIDO-01`
> (seção *A INVERSÃO*), e é ela que **refuta** a leitura antiga da casa, que
> descrevia a lista como "o Hefesto sai da frente".

Recomendado também: Propriedades → Controlador → **Desativar Steam Input**. O
instalador já faz isso por padrão em todos os jogos; `--keep-steam-input` preserva.

## Modo jogo (suprimir mouse e teclado)

Com a emulação de mouse ligada, o stick "anda sozinho" dentro do jogo. O combo
**PS + Options** alterna o modo jogo: suspende a emulação de mouse/teclado
mantendo os atalhos de troca de perfil vivos, e avisa por notificação. O gesto
em si é transitório — não sobrevive ao reinício do daemon.

> **NOTA DATADA — 09/08/2026: "é transitório" deixou de ser a história
> completa.** O **gesto** continua transitório, e é isso que a frase acima diz
> hoje. O que mudou é que a janela passou a **guardar** o modo jogo no perfil: o
> interruptor da aba Emulação escreve no rascunho e o **Salvar Perfil** do
> rodapé o persiste em `suppress_desktop_emulation`, **inclusive** em perfil
> "Vale sempre" — a recusa que existia nesse caso caiu por decisão dela, *"a
> vontade na GUI prevalece sempre"*. Num perfil "Vale sempre" o valor fica
> guardado no arquivo mas o daemon **não o liga sozinho** na ativação seguinte,
> e isso é de propósito: é o que impede o desktop de acordar sem ponteiro depois
> de um boot. Detalhe do campo em
> [`creating-profiles.md`](creating-profiles.md#seção-opcional-mouse-e-suppress_desktop_emulation).

Ver [`hotkeys.md`](hotkeys.md) para os demais atalhos do controle.
