# Atalhos no controle

O Hefesto reconhece combinações com o botão PS. Elas valem com o jogo aberto e
sem largar o controle.

**O PS e as combinações valem em qualquer um dos quatro controles.** O gesto
que muda um cartão da aba Jogar muda o de quem o fez: o PS + L3 no controle do
jogador 3 troca a máscara do jogador 3. O cursor do PC continua um só, e o
mouse e o teclado do controle saem do controle marcado «Navega o PC» na aba
Navegação, que é o do jogador 1. No Modo Nativo nenhum controle tem atalho:
sair dele é pela aba Jogar.

## Os gestos

| Gesto | O que faz |
|---|---|
| PS + direcional para cima | próximo perfil |
| PS + direcional para baixo | perfil anterior |
| PS + R3 | próximo modo: Sony DualSense, Xbox, Navegação e de volta ao Sony DualSense |
| PS + L3 | próxima máscara: DualSense, Xbox 360, Nintendo Pro e de volta à DualSense |
| PS + Options | pausa e devolve o mouse e o teclado do controle |
| PS, sozinho | abre a Steam, ou a traz para a frente se já estiver aberta |
| L3 / R3, no modo Navegação | abre / fecha o teclado na tela |
| botão do microfone | liga e desliga o microfone daquele controle |

Os dois botões de uma combinação contam juntos se chegarem em até 0,15 s. O PS
sozinho só age quando você o solta sem ter feito combinação nenhuma, então um
PS + direcional nunca abre a Steam.

Comece pelo PS. Com o L3 ou o R3 afundado antes do PS, o teclado na tela abre
antes de a combinação valer. Afundar os dois analógicos com o PS dispara um
gesto só.

## A cor que confirma

O PS + R3 e o PS + L3 piscam a barra de luz três vezes na cor do que ficou, em
todos os controles, e a barra volta à cor do perfil em seguida.

| Cor | Modo (PS + R3) | Máscara (PS + L3) |
|---|---|---|
| rosa | Sony DualSense | DualSense |
| verde claro | Xbox | Xbox 360 |
| laranja | Navegação | |
| roxo | | Nintendo Pro |

O Steam Input (azul claro) e o Modo Nativo (branco) não entram no ciclo do
gesto; a cor deles aparece quando você os escolhe na aba Jogar.

Com um jogo aberto, dois pulsos vermelhos vêm antes da troca: trocar o modo ou a
máscara recria o controle virtual, e alguns jogos só o reconhecem reabrindo.
Dois pulsos vermelhos e um longo dizem que a troca não aconteceu.

Num jogo que ainda não achou o modo que funciona, o PS + R3 também diz ao
Hefesto que o modo de agora não serve: ele passa para a próxima tentativa, e o
modo que ficar de pé é guardado no perfil do jogo.

## O botão PS sozinho

O que o PS faz sozinho é o campo `ps_button_action`:

- `steam` (o padrão): abre a Steam, ou traz a janela da Steam para a frente;
- `none`: não faz nada;
- `custom`: roda o comando de `ps_button_command`, uma lista de argumentos
  (nunca uma linha de shell). Por exemplo,
  `["xdg-open", "steam://open/bigpicture"]` abre o Big Picture.

Para mudar sem reiniciar o serviço, use o método `daemon.reload` do socket do
Hefesto (a mudança vale até o serviço reiniciar):

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"daemon.reload",
       "params":{"config_overrides":{"ps_button_action":"none"}}}' \
  | nc -U "$XDG_RUNTIME_DIR/hefesto-dualsense4unix/hefesto-dualsense4unix.sock"
```

Segurar o PS por um tempo não faz nada por padrão. `ps_long_press_ms` maior
que zero liga esse gesto (ele pausa o mouse e o teclado, como o PS + Options),
com o risco de disparar sem querer ao abrir a Steam.

## O PS + Options

Pausa o mouse e o teclado que o controle emula, e o mesmo gesto os devolve. Os
atalhos de perfil continuam valendo durante a pausa. Uma notificação confirma
cada troca. A pausa dura até o serviço reiniciar; para guardá-la num perfil,
use o interruptor da aba Navegação e o Salvar Perfil.

Pelo socket, o estado está no campo `emulation_suppressed` de `daemon.status`,
e `daemon.emulation.suppress` alterna.

## O teclado na tela

No modo Navegação, o L3 abre e o R3 fecha o teclado na tela do sistema: `wvkbd`
numa sessão Wayland, `onboard` no X11. O instalador instala o certo; sem nenhum
dos dois, o L3 avisa na tela. É o único jeito de digitar texto pelo controle.
Quando o L3 não abre nada, veja «O L3 não abre o teclado na tela» em
[troubleshooting.md](troubleshooting.md).

## As variáveis de ambiente

O serviço não lê arquivo de configuração para os atalhos. Na subida, ele lê
variáveis de ambiente, e hoje são seis:

- `HEFESTO_DUALSENSE4UNIX_POLL_HZ`: quantas leituras do controle por segundo;
- `HEFESTO_DUALSENSE4UNIX_PS_LONG_PRESS_MS`: o tempo do PS segurado (`0`
  desliga, o padrão);
- `HEFESTO_DUALSENSE4UNIX_KEYBOARD_EMULATION`: `0` desliga o teclado emulado. A
  escolha feita na aba Navegação vence esta variável;
- `HEFESTO_DUALSENSE4UNIX_NICE`: a prioridade do processo;
- `HEFESTO_DUALSENSE4UNIX_FAKE` e `HEFESTO_DUALSENSE4UNIX_FAKE_TRANSPORT`: um
  controle simulado, para desenvolvimento.

Para o serviço ler uma delas, ponha-a no ambiente do systemd do usuário e
reinicie o serviço:

```bash
systemctl --user set-environment HEFESTO_DUALSENSE4UNIX_PS_LONG_PRESS_MS=1000
systemctl --user restart hefesto-dualsense4unix.service
```
