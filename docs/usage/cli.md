# A linha de comando

A referência da linha de comando `hefesto-dualsense4unix`. Todo subcomando
aceita `--help`, e `hefesto-dualsense4unix --install-completion <shell>`
instala o completar pelo Tab no bash e no zsh.

## Resumo

| Comando | O que faz |
|---|---|
| `version` | a versão instalada |
| `status` | o serviço e os controles |
| `doctor` | o diagnóstico (`--fix`, `--fix-safe`, `--quiet`, `--perfis`) |
| `battery` | a bateria |
| `led --color …` | a cor da barra de luz (`--brightness` opcional) |
| `mouse on/off/status` | o controle como mouse e teclado |
| `profile list/show/activate/create/delete/apply/save` | os perfis |
| `profile historico/restore` | as versões guardadas de um perfil, e a volta |
| `daemon start/stop/restart/status/pause/resume/enable/disable/install-service/uninstall-service` | o serviço |
| `gamepad on/off/status` | o controle virtual |
| `gamepad steam-input list/remove` | os jogos com o Steam Input ligado |
| `native on/off/status` | o Modo Nativo |
| `coop on/status` | os jogadores |
| `controller list/target` | a quem os comandos de saída se aplicam |
| `mic …` | o microfone do controle |
| `speaker …` | o alto-falante e o fone do controle |
| `esquecer-controles` | esquece os controles, como numa máquina nova, e os devolve |
| `plugin list/reload/ligar/desligar` | os plugins (ligados só pela mão, valem na próxima subida do serviço) |
| `metrics ligar/desligar` | as métricas Prometheus (desligadas por padrão, valem na próxima subida do serviço) |
| `tui` / `tray` | a interface de terminal / o ícone da bandeja |

Os instrumentos `test`, `lightbar-reset` e `player-leds` estão no fim da página.

## `led`

```bash
hefesto-dualsense4unix led --color '#ff8800' --brightness 50   # ou --color '255,136,0'
```

Com o serviço rodando, o pedido vai por ele e os perfis continuam valendo; com
o serviço parado, vai direto ao controle. O `--brightness` vai de 0 a 100 e
escala a cor.

## `mouse`

```bash
hefesto-dualsense4unix mouse on --speed 8 --scroll-speed 3
hefesto-dualsense4unix mouse off
hefesto-dualsense4unix mouse status --json
```

`--speed` vai de 1 a 12 e `--scroll-speed` de 1 a 5. Sai com `1` quando o
serviço não ligou o mouse, `2` quando recusou o pedido e `3` com o serviço
parado.

## `profile`

```bash
hefesto-dualsense4unix profile list
hefesto-dualsense4unix profile show <nome>
hefesto-dualsense4unix profile create <nome> [--match-class X] [--match-exe X] [--match-regex …] [--priority N] [--fallback]
hefesto-dualsense4unix profile create <nome> --manual      # só entra pela janela ou pelo activate
hefesto-dualsense4unix profile delete <nome> --yes
hefesto-dualsense4unix profile activate <nome>
hefesto-dualsense4unix profile apply --file rascunho.json   # confere, salva e ativa
hefesto-dualsense4unix profile save <novo_nome> --from-active
```

O `apply` confere o arquivo contra o formato do perfil antes de salvar; com
`--no-save`, só ativa um perfil que já existe. O `save --from-active` copia o
perfil ativo com outro nome.

### O histórico

Cada vez que um perfil é gravado (ou apagado), a versão anterior vai para
`~/.config/hefesto-dualsense4unix/profiles/.historico/<nome>/`, e ficam as dez
mais recentes.

```bash
hefesto-dualsense4unix profile historico <nome>
hefesto-dualsense4unix profile restore <nome>                   # volta à versão de antes da última gravação
hefesto-dualsense4unix profile restore <nome> --em <carimbo>    # volta a uma versão específica
```

O `restore` guarda a versão atual antes de substituí-la, então restaurar por
engano também tem volta. Uma versão que não passa na conferência do formato
aparece como ilegível e não volta ao disco.

## `daemon`

```bash
hefesto-dualsense4unix daemon start      # em primeiro plano, sem o systemd
hefesto-dualsense4unix daemon stop       # systemctl --user stop
hefesto-dualsense4unix daemon restart
hefesto-dualsense4unix daemon status
hefesto-dualsense4unix daemon pause      # o serviço para de despachar e continua vivo
hefesto-dualsense4unix daemon resume
hefesto-dualsense4unix daemon disable    # para e tira do início automático
hefesto-dualsense4unix daemon enable
```

Não existe `daemon reload` na linha de comando; o método `daemon.reload` do
socket está em [hotkeys.md](hotkeys.md).

## `gamepad`

```bash
hefesto-dualsense4unix gamepad on --flavor xbox   # ou dualsense, ou nintendo
hefesto-dualsense4unix gamepad off
```

### `gamepad steam-input`

Os jogos em que o Steam Input fica ligado. Marcar é na janela (o chip «Steam
Input» da aba Jogar, ou a caixinha do perfil na aba Perfis); a linha de comando
lista e desmarca:

```bash
hefesto-dualsense4unix gamepad steam-input list
hefesto-dualsense4unix gamepad steam-input remove 2111190      # pelo número do jogo
hefesto-dualsense4unix gamepad steam-input remove 'mullet'     # ou por parte do nome
```

Ver [jogos-e-mascaras.md](jogos-e-mascaras.md).

## `coop` e `controller`

`coop on` refaz a numeração dos jogadores agora, e `coop status` conta os
jogadores do Hefesto e os controles ligados. Cada DualSense conectado é um
jogador; `coop off` explica isso e sai com `2`. Controles de outras marcas
entram na conta dos ligados, e não na dos jogadores.

`controller list` mostra os controles (`--json` para scripts, `--external` para
incluir os de outras marcas), e `controller target <n|all>` escolhe a quem os
comandos de saída (luz, vibração, gatilhos) se aplicam.

## `mic`

| Ações | O que fazem |
|---|---|
| `on`, `off`, `status` | a política do sistema de som para o microfone do controle, no cabo |
| `promote`, `demote` | torna o microfone do controle a entrada padrão, ou devolve a escolha ao sistema |
| `mute`, `unmute`, `release` | o mudo do próprio controle, o mesmo do botão. `release` devolve o botão ao controle |
| `led-on`, `led-off`, `led-release` | a luz do botão do microfone: acesa diz que o microfone está vivo. `led-release` devolve a luz ao driver |
| `bt`, `bt-status` | a ponte do microfone pelo Bluetooth, e o seu diagnóstico ([bluetooth.md](bluetooth.md)) |

Com vários controles, `--uniq <endereço>` escolhe o controle das ações de mudo
e de luz.

## `speaker`

```bash
hefesto-dualsense4unix speaker volume 60   # também: status, mute, unmute, release
```

É um volume só para o alto-falante e o fone do controle, e exige o serviço. O
controle não informa o volume dele, então o Hefesto passa a mandá-lo a partir da
primeira escrita; `release` devolve o volume ao controle. `mute` precisa de um
volume já escrito. `--uniq` escolhe o controle.

## `doctor`

`doctor` confere a instalação de ponta a ponta; `--fix` corrige o que puder.
`doctor --perfis` só confere os perfis entre si (um perfil geral vencendo o de
um jogo, prioridades empatadas) e sai com `1` quando acha algo grave. Ele avisa e
não reescreve arquivo nenhum.

## `esquecer-controles`

Faz o Hefesto esquecer os controles, como numa máquina nova, e os devolve
depois. Ver [esquecer-os-controles.md](esquecer-os-controles.md).

## Instrumentos

Estes servem para medir, e não para configurar: não gravam nada em perfil, e a
próxima troca de perfil passa por cima.

```bash
hefesto-dualsense4unix test trigger --side right --mode Rigid --params '5,200'
hefesto-dualsense4unix test led --color '#ff0000' --brightness 40
hefesto-dualsense4unix test rumble --weak 128 --strong 64
```

Os três pedem ao serviço primeiro e só vão direto ao controle com ele parado.
`test trigger --raw` escreve o efeito cru e recusa com o serviço rodando: o
serviço sobrescreveria o efeito em menos de meio segundo. Para usá-lo, pare o
serviço (`systemctl --user stop hefesto-dualsense4unix`), rode e religue.

`lightbar-reset` manda o pedido de «Reset LED state» ao controle. O envio
automático dele saiu do produto no commit `108b711`, porque ele travava a barra
de luz até o controle ser desligado; o comando fica para medir. Ele apaga também
as luzes de jogador. `player-leds` liga e desliga a escrita das luzes de
jogador, para isolar quem trava a barra.

O protocolo está em [ipc-unix-socket.md](../protocol/ipc-unix-socket.md) e na
[referência do DualSense](../protocol/dualsense-referencia-canonica.md).
