# O Hefesto pelo Flatpak

O Hefesto também pode rodar como Flatpak. O caminho testado continua sendo o
`./install.sh`; esta página diz como instalar o Flatpak e o que muda dentro do
sandbox.

## Instalar

Com o arquivo `io.github.hefesto_team.hefesto_dualsense4unix.flatpak` em mãos
(gerado pelo CI ou por `scripts/build_flatpak.sh --bundle`):

```bash
flatpak install --user io.github.hefesto_team.hefesto_dualsense4unix.flatpak
```

Ou construa a partir do código (precisa do `flatpak-builder` e do remoto
Flathub configurado):

```bash
git clone https://github.com/Hefesto-Team/hefesto-dualsense4unix.git
cd hefesto-dualsense4unix
./scripts/build_flatpak.sh --install
```

O Hefesto ainda não está publicado no Flathub.

### As regras udev, uma vez só

O sandbox não instala regras udev. Rode uma vez, com a senha de administrador:

```bash
flatpak run --command=install-host-udev.sh io.github.hefesto_team.hefesto_dualsense4unix
```

Ele instala as mesmas regras do `install_udev.sh` (a lista está em
[instalacao.md](instalacao.md)). Depois, desconecte e reconecte o controle, e
feche o Hefesto por inteiro (inclusive na bandeja) antes de abri-lo de novo: o
Flatpak só monta os caminhos de `/run` ao abrir.

### Se você tem o id antigo

O aplicativo se chamava `br.andrefarias.Hefesto` e passou a ser
`io.github.hefesto_team.hefesto_dualsense4unix`, a forma que o Flathub exige. O
Flatpak trata id novo como outro aplicativo: os dois ficam no menu. Na primeira
vez que abre, o novo copia os seus perfis do antigo, sem apagar nada. Depois
disso, tire o antigo:

```bash
flatpak uninstall --user br.andrefarias.Hefesto
rm -rf ~/.var/app/br.andrefarias.Hefesto/   # opcional: a cópia antiga dos perfis
```

## Usar

```bash
flatpak run io.github.hefesto_team.hefesto_dualsense4unix
```

Ou pelo menu de aplicativos.

Dentro do Flatpak o serviço não é do systemd: ele roda como processo da janela
e fecha com ela. Para ele subir no login, ponha o comando acima no início
automático da sua sessão.

| Fora do Flatpak | Dentro do Flatpak |
|---|---|
| `~/.config/hefesto-dualsense4unix/` | `~/.var/app/io.github.hefesto_team.hefesto_dualsense4unix/config/hefesto-dualsense4unix/` |
| `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/` | `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/`, a mesma pasta |

Para levar perfis de fora para dentro:

```bash
mkdir -p ~/.var/app/io.github.hefesto_team.hefesto_dualsense4unix/config/hefesto-dualsense4unix/profiles/
cp ~/.config/hefesto-dualsense4unix/profiles/*.json \
   ~/.var/app/io.github.hefesto_team.hefesto_dualsense4unix/config/hefesto-dualsense4unix/profiles/
```

## As permissões do sandbox

| Permissão | Para quê |
|---|---|
| `--device=all` | o controle (`/dev/hidraw*`) e os dispositivos virtuais (`/dev/uinput`, `/dev/uhid`) |
| `--socket=x11`, `--socket=wayland` | a janela. É `x11`, e não `fallback-x11`, porque a janela abre pelo XWayland mesmo com Wayland presente |
| `--socket=session-bus`, `--talk-name=org.freedesktop.portal.*` | portais e notificações |
| `--filesystem=xdg-run/hefesto-dualsense4unix:create` | a conversa entre a janela e o serviço |
| `--filesystem=xdg-config/hefesto-dualsense4unix:create` | os perfis |
| `--filesystem=~/.steam`, `--filesystem=~/.local/share/Steam` e as instalações da Steam por Flatpak e Snap (só leitura) | as opções dos jogos da Steam |
| `--allow=bluetooth`, `--share=network` | o medidor do rádio de cada adaptador |
| `--filesystem=/run/hefesto-hidraw-broker:ro` | o serviço que entrega o controle físico ao Hefesto |
| `--filesystem=/run/hefesto-dualsense4unix` | a trava comum do rádio, dividida com os serviços do sistema |
| `--filesystem=/run/udev/data:ro` | a base do udev: quem move o cursor, e a identidade do controle para a vibração |
| `--system-talk-name=org.bluez` | parear, reconectar, remover e mover controles de adaptador |
| `--filesystem=/var/lib/hefesto-dualsense4unix:ro` | o diário dos serviços do sistema, só leitura |

### O BlueZ e o diário dos serviços do sistema

Pelo `org.bluez`, parear, reconectar, remover e mover de adaptador funcionam no
Flatpak como fora dele, e o agente de pareamento do Hefesto atravessa o
sandbox. O diário dos serviços do sistema entra só para leitura.

O que continua sem alcançar: a ponte de administrador
(`bt_ponte_privilegiada.sh`, pelo `sudo`), que não existe no sandbox. Sem ela, o
Hefesto do Flatpak não derruba a conexão morta de um controle, e um controle
esquecido num adaptador pode voltar quando os pareamentos são restaurados.

## O teclado na tela

O L3 abre o teclado na tela no modo Navegação. No Flatpak ele vem dentro do
pacote (`wvkbd`), porque um programa do sistema é invisível no sandbox. O
`onboard` não vem: ele digita pelo X11 e, numa sessão Wayland, não alcançaria
as janelas.

## Desinstalar

```bash
flatpak uninstall --user io.github.hefesto_team.hefesto_dualsense4unix
rm -rf ~/.var/app/io.github.hefesto_team.hefesto_dualsense4unix/   # opcional: os seus perfis
```

As regras udev do sistema ficam. Para tirá-las:

```bash
sudo rm -f /etc/udev/rules.d/73-hefesto-ps5-controller.rules \
        /etc/udev/rules.d/70-ps5-controller.rules \
        /etc/udev/rules.d/71-uinput.rules \
        /etc/udev/rules.d/72-ps5-controller-autosuspend.rules
sudo udevadm control --reload-rules
```

A `70-ps5-controller.rules` é o nome antigo da `73`, e pode existir numa
instalação antiga.
