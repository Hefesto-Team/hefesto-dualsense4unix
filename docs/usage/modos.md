# Como o controle chega ao jogo

A aba **Jogar** decide como o jogo enxerga os controles. São três escolhas: o
Status, o Modo e a máscara de cada controle. Para o que funciona em cada jogo,
veja [jogos-e-mascaras.md](jogos-e-mascaras.md).

## Status

- **Ligado**: o Hefesto cuida da luz, da vibração, dos gatilhos e do número de
  cada jogador, e escolhe como o jogo vê o controle.
- **Desligado**: o jogo fala direto com o controle, e quem conta os jogadores
  passa a ser o jogo.

Desligar não para o serviço; para isso, use a aba Sistema.

## Modo

| Modo | O que o jogo recebe |
|---|---|
| **Sony DualSense** | um DualSense virtual, pelo canal próprio do DualSense |
| **Xbox** | o controle pelo canal comum, o mesmo do controle de Xbox |
| **Steam Input** | os comandos pela Steam; a luz, os gatilhos e o número do jogador ficam com o Hefesto |
| **Navegação** | nenhum gamepad: o controle vira mouse e teclado do computador |
| **Modo Nativo** | o controle físico, sem o Hefesto no meio |

O Hefesto tenta os modos na ordem da lista e fica no primeiro que funciona
naquele jogo, e o perfil do jogo guarda o que deu certo. O **PS + R3** pula
para o próximo sem sair do jogo (ver [hotkeys.md](hotkeys.md)).

O jogo lê como o controle chega uma vez, quando abre. A troca de modo com o jogo
aberto recria o controle virtual, e alguns jogos só o reconhecem reabrindo. Cor,
brilho, gatilho, vibração e microfone mudam na hora, em qualquer modo.

No Modo Nativo, o jogo fala direto com o DualSense. É para jogos que já tratam o
controle sozinhos.

## A máscara

A máscara é de cada controle e diz que controle o jogo vê:

- **DualSense**: △ ○ ✕ ▢;
- **Xbox 360**: Y B A X;
- **Nintendo Pro**: X A B Y, com ZL, ZR, menos e mais.

Ela muda o desenho dos botões que o jogo mostra; o controle na sua mão continua
o mesmo. O **PS + L3** troca a máscara do controle de quem faz o gesto. A
máscara escolhida fica guardada no controle e passa a valer quando o Hefesto
volta a entregá-lo ao jogo.

Fora do Modo Nativo, o jogo vê só o controle virtual: o físico fica escondido
dele, para não aparecer duas vezes. Na Navegação, o jogo não vê gamepad nenhum
até um modo de jogo subir.

## O Modo Freestyle

Ligado, o perfil ativo continua valendo quando você abre outro jogo. Desligado,
o Hefesto volta a escolher o perfil de cada jogo quando ele abre.

## Vários jogadores

Com dois ou mais DualSense, cada controle vira um jogador, com um controle
virtual próprio e a luz de jogador de 1 a 4. O número é guardado pela
identidade do controle: ligar de novo, no cabo ou no rádio, devolve o mesmo
número.

Quando um controle sai, o lugar dele fica guardado por trinta segundos, e os
outros não trocam de número nesse tempo. Com um jogo aberto, o controle virtual
de quem saiu espera parado. Passado o prazo, a fila se fecha: quem estava atrás
sobe um número, e o jogo pode perder esse controle por cerca de um segundo.

O controle Nintendo Pro e o 8BitDo recebem luz de jogador própria, mas chegam
ao jogo como o controle que já são, sem controle virtual (ver
[troubleshooting-8bitdo.md](troubleshooting-8bitdo.md)).

## O touchpad

Em qualquer modo, o touchpad move o cursor do computador, como faz com o
controle ligado sem o Hefesto, e o clique dele é clique de mouse. Dentro do
jogo, o touchpad chega pelo controle virtual. O mouse do modo Navegação é outro
caminho: ele move o cursor pelo analógico esquerdo.

## A vibração

A força escolhida na aba Vibração vale para a vibração do jogo e para a do
Testar. No Modo Nativo não há controle virtual, e a vibração do jogo vai direto
ao controle, sem passar pela força escolhida.

## As Opções de Inicialização da Steam

O instalador põe o `hefesto-launch` nas Opções de Inicialização dos jogos da
Steam, com a Steam fechada. É ele que esconde o controle físico e entrega o
virtual. Para um jogo novo que aparecer com o controle duplicado, use o botão
da aba Sistema que aplica as opções aos jogos da Steam, com a Steam fechada.
Com o serviço parado, o `hefesto-launch` só abre o jogo, sem esconder nada: no
pior caso o jogo vê o controle duas vezes, e nunca nenhuma.

O instalador também desliga o Steam Input dos jogos (`--keep-steam-input`
preserva).
