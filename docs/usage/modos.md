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
| **Jogar direto (Sony)** | O Hefesto solta o controle. O jogo fala com o DualSense físico, sem intermediário. | Jogos que já falam DualSense nativamente e fazem tudo sozinhos. |

Pela linha de comando os mesmos três estados são `mouse on`, `gamepad on` e
`native on`.

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

Recomendado também: Propriedades → Controlador → **Desativar Steam Input**. O
instalador já faz isso por padrão em todos os jogos; `--keep-steam-input` preserva.

## Modo jogo (suprimir mouse e teclado)

Com a emulação de mouse ligada, o stick "anda sozinho" dentro do jogo. O combo
**PS + Options** alterna o modo jogo: suspende a emulação de mouse/teclado
mantendo os atalhos de troca de perfil vivos, e avisa por notificação. É
transitório — não sobrevive ao reinício do daemon.

Ver [`hotkeys.md`](hotkeys.md) para os demais atalhos do controle.
