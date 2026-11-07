# O Hefesto é bom vizinho do sistema

Um programa de controle não pode quebrar o resto do computador. Em 05/11/2026, o compartilhamento de tela
ficou quebrado na máquina inteira por dias, em todo aplicativo, por um pedido do Hefesto feito cedo demais. O
defeito apareceu no aplicativo de reunião, e quem sofre assim não tem como ligar uma coisa à outra.

Este documento é a auditoria: as regras, o inventário do que o Hefesto instala e mantém, com as cinco respostas
de cada item, e a proposta de régua. Ele não cura nada: cada risco achado tem sprint própria.

As medidas são de 07/11/2026, na máquina de referência: Pop!_OS 24.04, COSMIC, xdg-desktop-portal 1.18.4 e BlueZ
5.87 e PipeWire 1.6.9 dos backports. O diário guarda só 25 h (desde 06/11, 05:52), e toda contagem de
diário vale nessa janela. O que veio só da leitura do código diz «lido».

## As regras da casa

1. **Perguntar não pode mudar o sistema.** Falar com um nome D-Bus ativável sobe o serviço. Leitura vai com
   `no_auto_start` (jeepney) ou `--auto-start=no` (`busctl`). Sem o dono de pé, a resposta é «não sei», e nada sobe.
2. **Nada antes da sessão gráfica.** O serviço sobe no `default.target`, antes da sessão. Até a sessão existir, nenhum
   serviço de sessão é tocado.
3. **Diálogo do sistema só com gesto e com nome.** Janela que nasce de processo de fundo, sem pedido de quem usa e
   sem dizer quem pede, é defeito.
4. **Serviço alheio não se reinicia** fora de dois casos: o gesto de instalar ou desinstalar, avisando o que cai, e
   o vigia do rádio, com as três travas que o inventário lista.
5. **O que muda a máquina toda é pergunta ou tem medida.** Efeito sobre aparelho que não é controle precisa de
   resposta de quem usa no install ou de um limite escrito (sem bateria, só driver X).
6. **Tudo tem desfazer**, no `uninstall.sh`. O que ele preserva de propósito, ele diz na saída e na ajuda.
7. **Falha nossa fica com a gente.** Vigia que se repete não enche o diário do sistema, e parada pedida não é falha.
   A exceção escrita é a troca do broker, no inventário.

## A ordem da subida, medida

Boot de 06/11, 18:21.

| quando | o quê |
| --- | --- |
| 18:21:44,727 | `pipewire.service` de pé |
| 18:21:44,746 | `hefesto-dualsense4unix.service` começa a subir |
| 18:21:48,438 | serviço pronto |
| 18:23:48,851 | `graphical-session.target` |
| 18:23:51,116 | `xdg-desktop-portal.service`, depois da sessão: a cura de 05/11 valeu neste boot |

São **124 s com o Hefesto no ar e sem sessão**. Tudo o que ele chama nesse intervalo encontra o sistema pela
metade. O comando é `journalctl --user -b 0 -t systemd`, filtrado pelas unidades.

## Os nomes D-Bus: quem acorda quem

| nome | ativável aqui | quem fala | proteção | estado |
| --- | --- | --- | --- | --- |
| `org.freedesktop.portal.Desktop` | sim | `integrations/tela_do_jogo.py` | só depois da sessão (`_sessao_ainda_nao_subiu`), e a leitura do `systemd1` vai com `no_auto_start` | curado em 05/11 |
| `org.bluez` | sim, pelo `dbus-org.bluez.service` | `integrations/bluez_dbus.py`, `scripts/bt_active_mode.sh`, `scripts/bt_health_watchdog.sh`, `scripts/bt_ponte_privilegiada.sh`; por gesto de diagnóstico, `scripts/doctor.sh` e `scripts/retrato_do_estado.sh` | nenhuma | **risco 1** |
| `org.freedesktop.Notifications` | aqui não; `dunst` e `mako` trazem arquivo de ativação (lido) | `integrations/desktop_notifications.py` | nenhuma | **risco 2** |
| `org.kde.StatusNotifierWatcher` | não | `desktop_notifications.statusnotifierwatcher_available` | `NameHasOwner`, que não ativa | ok |
| `org.freedesktop.NetworkManager` | não | `integrations/faixa_do_wifi.py` | não é ativável, e o serviço está sempre de pé | ok |
| `org.freedesktop.systemd1` (sessão) | o arquivo existe, com `Exec=/bin/false` | `tela_do_jogo.py` | `no_auto_start` | ok |
| `ca.desrt.dconf` | sim | a interface, por `Gio.Settings` em `interface/tema_da_sessao.py` | só roda com a janela aberta, logo depois da sessão | ok |

A base é `ls /usr/share/dbus-1/services /usr/share/dbus-1/system-services` e as linhas `dbus:` do
`docs/data/contratos-de-fora.csv`. O CSV tem dois falsos contatos: `dbus:org.gnome` e `dbus:org.kde` em
`profiles/simple_match.py` são nomes de janela, e não barramento.

**Prova da ativação por pergunta.** Num `dbus-daemon` próprio, com um `org.bluez` de mentira ativável:

| comando | ativou? |
| --- | --- |
| `busctl --address=<próprio> tree org.bluez --list`, o que `bt_active_mode.sh` faz | **sim** |
| o mesmo com `--auto-start=no` | não |
| `desktop_notifications.notify()`, do produto | **sim** |

## O inventário

As colunas são as cinco perguntas: **1** o que muda ou ativa, mesmo só perguntando; **2** antes da sessão, e o que
acontece se o alvo não existe; **3** se falha ou se repete, quem sofre; **4** sai algo visível sem gesto, e diz quem
pediu; **5** como desfazer.

### Serviços da sessão do usuário

| item | 1 | 2 | 3 | 4 | 5 | medida |
| --- | --- | --- | --- | --- | --- | --- |
| `hefesto-dualsense4unix.service` | abre os controles; `pactl`, `pw-*` e `parec`; portal só depois da sessão; `org.bluez` sem proteção | sim, 124 s; alvo ausente vira «sem som» ou «sem janela», sem erro | o Hefesto; o rádio pode acordar (risco 1) | janela do portal com a chave «Tela» (problemas #3 e #4 abaixo); notificações do modo jogo | `uninstall.sh` | `journalctl --user -b 0` |
| `-gui-hotplug` | abre a janela no início da sessão | não, vem depois do `graphical-session.target` | o Hefesto | a janela do Hefesto, por escolha feita no install (`--enable-hotplug-gui`) | `uninstall.sh`, ou `--no-hotplug-gui` | subiu às 18:23:48,871 |
| `-presenca` | um `--ping` no soquete do broker | sim; broker ausente não muda nada (`ExecStart=-`) | ninguém | nada | `uninstall.sh` | 9 inícios e 27 linhas em 24 h |
| `-storm-watch` | só lê o diário e chama o religar quando a porta perde a sonda | sim, e não depende de sessão | a própria unit: parada contada como falha (curado na sprint do storm-watch) | nada | `uninstall.sh` | 8 paradas contadas como falha desde 06/11, 10:30; 637 linhas «terminou inesperadamente» no registro |
| `hefesto-steam-input-guard` (`.path`, `.timer`, `.service`) | edita a configuração da Steam (Steam Input, atalho, Proton fixado, opções por jogo) | sim; sem Steam não faz nada, e com a Steam aberta o `--apply-quiet` adia | a Steam, se a edição sair errada; o diário | nada | `uninstall.sh` reverte os três (`--keep-steam-input` preserva) | **135 inícios e 2.969 linhas em 24 h**, contra 48 do timer (risco 5) |
| autostart da bandeja | ícone na barra | não: vem pelo autostart, depois da sessão | o Hefesto | o ícone, com o nome | `uninstall.sh` | subiu às 18:23:48,891 |

A máquina de referência tem mais uma unit de usuário, de desenvolvimento, fora do repositório: essa unit não vai com o
produto e fica fora da auditoria.

### Serviços do sistema

| item | 1 | 2 | 3 | 4 | 5 | medida |
| --- | --- | --- | --- | --- | --- | --- |
| `hefesto-hidraw-broker` (`.service`, `.socket`) | tira o físico dos outros programas; `modprobe` de `libcomposite`, `usb_f_hid`, `vhci-hcd` e `usbip-vudc num=8` em todo boot, com controle ou sem | sim, e não depende de sessão | **todo programa que quer o controle**; a saída é a `ExecStopPost`, que reabre os nós, e o `OnFailure` do serviço de usuário | nada | `uninstall.sh` | soquete 0666, com a autorização por `SO_PEERCRED` e pelo usuário da frente (lido); 6 `Failed with result 'signal'` em 06/11, ver abaixo |
| `hefesto-bt-agent` | agente `NoInputNoOutput` para o **rádio inteiro**, com qualquer aparelho | sim | **quem pareia outra coisa**: o pedido não chega ao aplicativo do sistema (lido; risco 4) | nada: o pareamento passa sem pergunta | `uninstall.sh` | no ar havia 45.115 s |
| `hefesto-desempenho` | perfil de energia em Desempenho, em todo boot; `nvidia`, `audio` e `aspm` só entram com prova no aparelho, e o padrão é nenhum | sim | a conta de luz e a bateria | só a pergunta do install | `desempenho.sh remover`, pelo `uninstall.sh` | só existe com resposta sim; sem terminal, o padrão é não |
| `hefesto-bt-health-watchdog` | `busctl` em `org.bluez`, a cada 2 min; `Trusted=true` só em controle (`_e_controle`); `Connect` em aparelho HID sem registro; pode reiniciar o `bluetooth.service` e, pela ponte, a porta do adaptador travado | sim; `bt_active_mode.sh` roda antes de conferir se o rádio está no ar (risco 1) | fone e teclado Bluetooth, no reinício; o diário | nada | `uninstall.sh` | 0 reinícios no diário; as travas são recusas repetidas, zero conectado e intervalo mínimo; **4.872 linhas em 24 h**, sendo 3.052 a mesma frase (risco 5) |
| `hefesto-bt-bonds-snapshot` | copia `/var/lib/bluetooth` para `/var/lib/hefesto-dualsense4unix` | sim | ninguém | nada | `uninstall.sh`; a cópia sai só com `--purge-config` | 284 linhas em 24 h |
| `hefesto-wifi-usb-vigia` | a cada 1 min, zera o scan de fundo e **reinicia a porta** do Wi-Fi USB travado | sim; sem Wi-Fi USB não faz nada | a rede de quem usa, se o diagnóstico errar | a queda de 2 s na rede, no reinício | `uninstall.sh` | as travas são 3 falhas seguidas, 600 s entre reinícios e 3 reinícios sem cura; 0 reinícios no diário; **3.902 linhas em 24 h** (risco 5) |

**O `Failed with result 'signal'` do broker é de propósito.** O install o mata com `SIGKILL` para trocar o binário sem
abrir os nós (`scripts/lib/camada_de_maquina.sh`), e 06/11 teve seis trocas. Declarar `SuccessExitStatus=SIGKILL`
esconderia um `SIGKILL` de verdade, que o `Restart=on-failure` precisa ver. Fica como está, sem sprint.

### Regras udev

Lido de `assets/`; a remoção foi conferida em `uninstall.sh`, regra por regra. O `--keep-udev` as preserva.

| regra | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- |
| `71-uinput`, `71-uhid` | `/dev/uinput` e `/dev/uhid` em 0660 no grupo `hefesto`, com `uaccess` | independe; o grupo vale desde o nó, antes do login | quem está no grupo cria aparelho de entrada virtual | nada | `uninstall.sh`, que tira também o grupo |
| `72-hefesto-touchpad-motion-uaccess` | acesso e `uaccess` nos nós de toque e movimento de Sony (`054c`) e Nintendo (`057e`); fecha o físico quando o soquete do broker existe | independe | só controles | nada | `uninstall.sh` |
| `72-ps5-controller-autosuspend` | energia do USB, só `054c:0ce6` e `054c:0df2` | independe | só controles | nada | `uninstall.sh` |
| `73-hefesto-ps5-controller` | `hidraw` do físico em 0600 de root; o virtual fica aberto | independe; o físico fechado não depende do broker estar de pé | sem o serviço no ar, o `hidraw` fica fechado para a Steam até o broker devolver o nó, avisado pela `-presenca` | nada | `uninstall.sh` |
| `75-ps5-controller-disable-usb-audio` | desliga o áudio USB do controle | não instalada nesta máquina | só controles | nada | `uninstall.sh` |
| `76-dualsense-touchpad-libinput-ignore` | o `libinput` ignora o touchpad virtual | independe | só controles | nada | `uninstall.sh` |
| `77-dualsense-leds` | `chmod 0666` em todo LED `*:rgb:indicator` e `*:white:player-*` | independe | **casa por nome, e não por aparelho** (lido); o pior é outro usuário local trocar uma cor | nada | `uninstall.sh` |
| `78-dualsense-motion-not-joystick` | o sensor de movimento deixa de ser joystick | independe | só controles | nada | `uninstall.sh` |
| `79-external-controller-leds` | `chmod 0666` nos LEDs de Nintendo e do driver `playstation` | independe | só controles | nada | `uninstall.sh` |
| `80-motion-joydev-hide` | `js*` de sensor de movimento em 0000 | independe | casa `*Motion Sensors*`, que é só controle na prática | nada | `uninstall.sh` |
| `81-hefesto-usb-host-power` | **todo controlador USB** sem economia de energia | independe | todo USB; só vale em máquina **sem bateria** | nada | `uninstall.sh` |
| `81-hefesto-usb-power` | energia do USB em Sony, Nintendo, 8BitDo e Microsoft; adaptador Bluetooth só sem bateria | independe | quatro fabricantes inteiros, sem olhar o produto; custo baixo | nada | `uninstall.sh` |
| `82-nintendo-pro-nosniff` | modo ativo no enlace do Pro Controller | independe | só controles | nada | `uninstall.sh` |
| `83-hefesto-bond-snapshot` | pede a cópia dos pareamentos a cada HID com `uniq`, de qualquer marca | independe; `--no-block` | ninguém | nada | `uninstall.sh` |
| `84-nintendo-pro-variant` | marca a variante do Pro Controller | independe | só controles | nada | `uninstall.sh` |
| `85-hefesto-o-cabo-assume` | na saída de um DualSense, reapresenta os outros ao driver | independe | só controles | nada | `uninstall.sh` |

**Sem sprint, e por quê:** a `77` não fere outro aparelho de verdade, e `chmod` em LED é o caminho sem daemon privilegiado.
A `81-hefesto-usb-power` só tira o sono USB de periférico daqueles fabricantes. As duas ficam no inventário, como o limite
da regra 5.

### Módulos do kernel

| arquivo | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- |
| `hefesto-btusb-no-autosuspend` | `btusb enable_autosuspend=0`: **todo adaptador Bluetooth**, sem olhar a bateria (risco 8) | no carregar do módulo | a bateria do notebook | nada | `uninstall.sh` |
| `hefesto-dualsense-storm` | `snd_usb_audio quirk_flags` só de `054c:0ce6` e `054c:0df2` | idem | só controles | nada | `uninstall.sh` |
| `hefesto-uhid`, `hefesto-hid-playstation`, `hefesto-hid-nintendo` | parâmetros dos módulos DKMS nossos | idem | só controles | nada | `uninstall.sh` |
| `/etc/modules-load.d/hefesto-dualsense4unix.conf` | carrega `uinput` e `uhid` em todo boot, com controle ou sem | no boot | ninguém | nada | `uninstall.sh` |
| `hefesto-wifi-powersave` (NetworkManager) | economia do Wi-Fi desligada, só nos drivers `rtw88` listados | idem | a rede daquele adaptador; recusa em máquina com bateria | nada | `uninstall.sh` |

### As regras de sudo e de som

| item | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- |
| `/etc/sudoers.d/49-hefesto-bt-ponte` | `NOPASSWD` do grupo `hefesto` para a ponte do rádio, verbo por verbo | independe | quem está no grupo pode os verbos | nada | `uninstall.sh` |
| `/etc/sudoers.d/49-hefesto-placa` | `NOPASSWD` para a placa acordada: três verbos, com o PID pelo stdin | independe | idem | nada | `uninstall.sh` |
| `51-hefesto-dualsense-no-default-source` (WirePlumber) | o microfone do DualSense nunca vira padrão sozinho | no início do WirePlumber | só o nó `*DualSense*` | nada | `uninstall.sh` |
| `54-hefesto-dualsense-alto-falante-nunca-dorme` (WirePlumber) | a saída do DualSense não suspende | idem | só o nó `*DualSense*` | nada | `uninstall.sh` |

### Os processos que o serviço mantém

| processo | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- |
| `pactl subscribe` | só escuta; o `pipewire-pulse` já estava de pé 19 ms antes | sim; sem som, o Hefesto segue sem ele | o Hefesto | nada | morre com a unit |
| `parec` | abre o microfone do controle | sim, se houver controle | o Hefesto; o nó fica aberto | nada | morre com a unit |
| `pw-loopback`, `pw-record` | nós `hefesto-*` no grafo de som | idem | aparecem na lista de fluxos do sistema, com o nome | nada | morrem com a unit |
| `bwrap` da extensão | sandbox, com `/home` e `/run/user/<uid>` em `tmpfs` | sim, se a extensão estiver ligada | a extensão; o barramento da sessão não entra na sandbox | nada | morre com o serviço (`setsid` e `PR_SET_PDEATHSIG`) |

### O que o inventário de 05/11 não listava

Tudo aqui vale desde o boot, sem depender da sessão, e sem nada visível: as colunas 2 e 4 são iguais em todas as linhas.

| item | 1 | 3 | 5 |
| --- | --- | --- | --- |
| backport do BlueZ | troca o pacote do sistema | todo aparelho Bluetooth | `--restore-bluez`, destrutivo; o padrão preserva, e a ajuda diz |
| backport do PipeWire e do WirePlumber, com `hefesto-pipewire` no apt | idem | todo o som da máquina | `--restore-pipewire`; o uninstall pergunta |
| **backport do portal do COSMIC**, com `hefesto-portal-cosmic` no apt | idem | toda captura de tela | **nenhum: o `uninstall.sh` não cita o portal** (risco 6) |
| módulos DKMS (`hid-playstation`, `hid-nintendo`, `uhid`, `usb-f-hid`, `rtw88-usb`) | trocam o módulo do kernel | controles e o Wi-Fi USB | `uninstall.sh` |
| `usbcore.autosuspend=-1` na cmdline | **todo USB**; o install olha a bateria | todo USB | o `uninstall.sh` devolve pelo registro de posse |
| `usbcore.quirks=054c:0ce6:gn` na cmdline | só o controle | só controles | `--remove-usb-quirk`; o padrão preserva, e a saída diz |
| `/etc/bluetooth/main.conf` e os dois `main.conf.d` | `FastConnectable` e `JustWorksRepairing=confirm` | todo o rádio | `bluez_config.sh remover`, pelo `uninstall.sh` |
| drop-in do `bluetooth.service` | `Restart=on-failure` e cópia dos pareamentos na parada | todo o rádio | `uninstall.sh` |
| perfil UCM do DualSense | cartão de som do controle | só controles | `uninstall.sh` |
| grupo de sistema `hefesto` | a conta de quem instala entra nele | quem está no grupo: `uinput`, `uhid`, a trava do rádio e os verbos do `sudo` | `uninstall.sh` |
| `hefesto-dualsense4unix-radio` (`tmpfiles.d`) | `/run/hefesto-dualsense4unix/radio.lock`, a trava comum do rádio | o Hefesto | `uninstall.sh` |
| `/etc/NetworkManager/dispatcher.d/90-hefesto-wifi-usb` | a cada `up` de rede, zera o scan de fundo do Wi-Fi USB | a rede daquele adaptador; sem Wi-Fi USB não faz nada | `uninstall.sh` |

## Os seis problemas de 05/11

| # | problema | estado em 07/11 | dono |
| --- | --- | --- | --- |
| 1 | o serviço acordou o portal antes da sessão | curado; o boot medido acima confirma | `A-CAPTURA-NAO-ACORDA-O-PORTAL-ANTES-DA-SESSAO-01` |
| 2 | janela do sistema em laço | curado | a mesma |
| 3 | a janela surpresa a cada início do serviço | **aberto**; a captura ainda nasce da assinatura, sem jogo | `A-TELA-SO-SE-CAPTURA-COM-JOGO-ABERTO-01` |
| 4 | a janela diz «Aplicativo desconhecido» | **aberto** | `A-JANELA-DO-PORTAL-DIZ-QUE-E-O-HEFESTO-01` |
| 5 | a ficha do portal parece não sobreviver | **explicado**, a cura é a do #3: o portal apaga a ficha no `SelectSources` e só a regrava ao fechar a sessão; a ficha sem identidade está no banco desde 05/11, 23:44 | `A-TELA-SO-SE-CAPTURA-COM-JOGO-ABERTO-01` |
| 6 | janela aberta e backend do portal travado | **sem sprint própria**, com motivo abaixo | condicional |

**Por que o #6 não tem sprint.** A ligação com o Hefesto é coincidência no tempo, e não causa provada. Nas 25 h do
diário há zero linhas `TrySendError`. O pacote do portal é nosso, mas o backport muda
só o `cosmic-protocols#92`. O gatilho suspeito, a janela sem gesto, sai com o #3. **Volta a ser sprint** se
`journalctl --user | grep TrySendError` acusar depois de o #3 chegar, com a medida do que estava pedido no momento.

**O #3 tem um limite a dizer antes de prometer:** o portal não oferece zero clique desde a instalação. A concessão mora
no `PermissionStore`, gravada pelo portal depois do clique, e não há `conf.d` para isso.

## Os riscos e os donos

| # | risco | medida | sprint |
| --- | --- | --- | --- |
| 1 | **Rádio parado acorda com uma pergunta.** Quem para o Bluetooth de propósito o vê voltar em até 2 min | `busctl` sem `--auto-start=no` ativou o nome no barramento próprio; `bt_active_mode.sh` roda antes da conferência do `is-active` | `O-RADIO-PARADO-NAO-ACORDA-COM-UMA-PERGUNTA-01` |
| 2 | **Notificação acorda serviço antes da sessão,** onde o serviço é ativável | `notify()` ativou o nome no barramento próprio, sem olhar a sessão; o perfil aplicado na subida alcança esse caminho (lido) | `A-NOTIFICACAO-NAO-ACORDA-O-SERVICO-ANTES-DA-SESSAO-01` |
| 3 | os problemas #3, #4 e #5 acima | ver a tabela | as duas sprints citadas |
| 4 | **O agente responde pelo rádio inteiro.** Pareamento de qualquer aparelho passa sem pergunta | lido da unit e da capacidade; falta medir o pedido de fora | `O-AGENTE-DE-PAREAMENTO-SO-RESPONDE-AO-GESTO-01` |
| 5 | **Os vigias repetem a mesma frase:** ~12 mil linhas por dia, 3,4% das 355 mil do diário, e a guarda da Steam roda 135 vezes. Risco baixo: quem enche o diário é o `cosmic-session`, com 246 mil | as contagens do inventário | `OS-VIGIAS-NAO-ENCHEM-O-DIARIO-DO-SISTEMA-01` |
| 6 | **O uninstall deixa o portal nosso e o pino do apt** | `grep -c portal-cosmic uninstall.sh` dá 0 | `O-UNINSTALL-DEVOLVE-O-PORTAL-DA-DISTRIBUICAO-01` |
| 7 | **Nada impede o próximo contato sem proteção** | a tabela dos nomes D-Bus foi feita à mão | `A-REGUA-DO-BOM-VIZINHO-01` |
| 8 | **O rádio do notebook nunca dorme.** A `81-hefesto-usb-power` guarda o adaptador com a bateria; o `btusb enable_autosuspend=0` vale em toda máquina | o passo 3d do install grava sem olhar a bateria (lido); o custo em bateria falta medir | `O-RADIO-DO-NOTEBOOK-DORME-NA-BATERIA-01` |

## O que caiu na medição

Para ninguém gastar de novo:

- **O WirePlumber não mexe em vídeo.** As regras só tocam nós de áudio do DualSense, e os `pw-loopback` são áudio.
- **O `pw-loopback` órfão não fica no grafo.** `integrations/laco_de_audio.py` lança sem `PR_SET_PDEATHSIG`, e com
  um dublê ele sobreviveu ao `SIGKILL` do pai. Só que, na unit, o `KillMode` padrão recolhe o cgroup. O órfão só
  existe rodando o serviço à mão, fora da unit. Sem sprint.
- **O PipeWire não é acordado pelo Hefesto.** O `pipewire.service` estava de pé 19 ms antes de o serviço começar.
- **`core_pattern` global não existe mais.** A regra de `sysctl.d` antiga não está no disco, e o `uninstall.sh`
  segue limpando quem a tem.
- **O `steam -shutdown` não roda em segundo plano.** O `pkill` da `disable_steam_input.sh` só vale no `--apply` do
  install; a guarda usa `--apply-quiet`, que adia com a Steam aberta.
- **Quem apresenta tela não vê a própria tela** em reunião. A prova é o segundo participante.

## A proposta de régua

Três peças, em `A-REGUA-DO-BOM-VIZINHO-01`:

1. **Coluna `ativa` no `docs/data/contratos-de-fora.csv`**, para cada `dbus:`: `nao`, `sim`, ou `sim-protegido`.
   `scripts/check_os_contratos_de_fora.py` reprova `sim` sem proteção.
2. **Uma porta só para o barramento.** Um módulo guarda a pergunta com `no_auto_start` e a guarda da sessão, e o portão
   reprova chamada a nome do sistema fora desse módulo. `_sessao_ainda_nao_subiu` sai de `tela_do_jogo.py` para essa porta.
3. **Prova de boot.** Um `dbus-daemon` próprio, com todo nome que o produto cita ativável e de mentira, sobe o serviço sem
   sessão e conta o que ativou. O certo é zero, e a mordida é tirar a guarda de um deles.

## Como medir de novo

```bash
journalctl --user -b 0 -t systemd | grep -E 'hefesto|ipewire|xdg-desktop|graphical-session'
journalctl --user -o cat | grep -E 'hefesto.*Failed with result'
for u in hefesto-bt-health-watchdog hefesto-wifi-usb-vigia; do journalctl -u "$u" --since '-24 hours' -o cat | wc -l; done
```

Item novo no install entra aqui com as cinco respostas, no mesmo commit.
