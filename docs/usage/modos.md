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
| **Xbox 360** | device evdev via `/dev/uinput` | botões, eixos e vibração |

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
> você, o Hefesto **ignora** a do jogo; sem ela, a do jogo passa pelo seu
> controle deslizante de intensidade. Registro em
> [CONTROLE-SONY-MEDIDO-01](../process/sprints/2026-08-06-CONTROLE-SONY-MEDIDO-01-o-experimento-que-decide-metade-da-doutrina.md).

A máscara Xbox 360 é o piso de compatibilidade — para jogos que só aceitam
gamepad da Microsoft. Ela é evdev, então só carrega botões, eixos e vibração:
nada de gatilho adaptativo, luz ou giroscópio.

> Se o `/dev/uhid` não estiver acessível, ou o kernel recusar o device, a máscara
> DualSense **cai para uinput** — e aí ela vira uma Xbox com botões de PlayStation,
> sem os extras. A aba Início mostra um aviso quando isso acontece, e diz por quê.
> É o campo `gamepad_emulation.degraded_motivo` no `status`.

## Co-op local

Com dois ou mais controles no modo "Jogar pelo Hefesto", cada controle vira um
jogador: um controle virtual por pessoa, LED de jogador de 1 a 4, numeração
estável por endereço MAC (replugar recupera o mesmo número).

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
mantendo os atalhos de troca de perfil vivos, e avisa por notificação. É
transitório — não sobrevive ao reinício do daemon.

Ver [`hotkeys.md`](hotkeys.md) para os demais atalhos do controle.
