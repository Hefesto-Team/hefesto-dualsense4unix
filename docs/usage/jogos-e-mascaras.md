# Que modo e que máscara usar em cada jogo

A pergunta do dia a dia: abri um jogo, o que escolho na aba **Jogar**? Os modos
e as máscaras estão explicados em [modos.md](modos.md).

## Como decidir

O Hefesto tenta os modos na ordem e guarda no perfil do jogo o que funcionou.
Na maioria dos jogos não é preciso escolher nada. Quando precisar:

- o controle funciona na Steam e **fica morto dentro do jogo**: o jogo aceita
  só controle de Xbox. Use a máscara Xbox 360, ou aperte PS + R3 até o modo
  Xbox;
- o jogo desenha os botões errados: troque a máscara (PS + L3, ou no cartão do
  controle na aba Jogar);
- o jogo já trata o DualSense sozinho e você prefere que ele fale direto com o
  controle: use o Modo Nativo.

## Jogos que pedem o Steam Input ligado

Alguns jogos pedem os recursos do DualSense à Steam, e o suporte deles só
funciona com o Steam Input daquele jogo ligado. Para um desses, use o chip
"Steam Input" da aba **Jogar**: ele liga a entrada da Steam só naquele jogo, que
é a exceção por jogo, e o vigia do instalador deixa de desligá-la.

Com a Steam aberta, a escolha espera, porque a Steam regrava as próprias opções
ao sair: a aba diz «Liga quando a Steam fechar». Um segundo clique no chip, em até
20 segundos, fecha a Steam, liga o Steam Input daquele jogo e a abre de novo.
Com um jogo aberto, o chip não oferece fechar a Steam.

Numa instalação com `--keep-steam-input` o vigia não mexe no Steam Input, e os
pacotes (.deb, AppImage, Flatpak) não o instalam: nesses casos, só o segundo
clique liga.

Como em todo jogo, o Hefesto esconde o controle físico do jogo, e o controle
virtual continua de pé. O co-op continua funcionando, e a cor e os gatilhos que
você escolheu continuam valendo.

### Desfazer

Na aba **Perfis**, abra o perfil do jogo (com «Jogo da Steam» e o número do jogo
preenchidos) e desmarque «Esconder os controles físicos neste jogo». A marca sai
na hora. Com um jogo aberto, a janela pergunta antes: feche e abra o jogo para
valer.

Pela linha de comando:

```bash
hefesto-dualsense4unix gamepad steam-input list              # os jogos marcados
hefesto-dualsense4unix gamepad steam-input remove <nome ou appid>
```

### O contrário: um jogo sem o Hefesto

«Adicionar à lista de exclusão», no cartão da Steam da aba **Lançadores**, faz o
jogo escolhido ver o controle como se o Hefesto não estivesse instalado.

## Jogos medidos

| Jogo | O que funcionou |
|---|---|
| Sackboy: A Big Adventure | DualSense completo: vibração, giroscópio e barra de luz |
| Pragmata | DualSense completo |
| Mad King Redemption | DualSense completo |
| Mullet Mad Jack | as três opções (Xbox 360, DualSense e Modo Nativo), sem marca nenhuma |

Os jogos com suporte próprio ao DualSense também escrevem no controle: a cor da
barra e a força dos gatilhos que o jogo pede vencem as suas enquanto ele está
aberto, e voltam quando ele fecha. A vibração é a exceção: a força que você
escolheu na aba Vibração continua valendo.

Testou outro jogo? Abra uma issue dizendo o que funcionou, em quais máscaras e
modos, e se ele precisou do Steam Input ligado.

## Não escolher toda vez

Salve um perfil (aba **Perfis**) com o modo e a máscara certos e diga como
reconhecer o jogo. Ele entra sozinho quando o jogo abre.

O botão «Detectar» lê o jogo aberto e monta a regra por você. Se for escrever à
mão, use a classe da janela: a Steam a marca como `steam_app_<número do jogo>`,
e é o único campo que funciona tanto no X11 quanto no Wayland. O nome do
processo não funciona no Wayland (o sistema não o entrega) e, com o Proton, é o
do Wine e não o do jogo. Os campos preenchidos precisam casar todos: um campo
que não casa impede o perfil de entrar.

Para o perfil ativo continuar valendo em qualquer jogo, ligue o Modo Freestyle
na aba Jogar.
