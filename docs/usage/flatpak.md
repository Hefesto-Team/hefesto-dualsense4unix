# O Hefesto pelo Flatpak

O Hefesto também pode rodar como Flatpak. O caminho testado continua sendo o
`./install.sh`; esta página diz como instalar o Flatpak e o que muda dentro do
sandbox.

## Instalar

Com o arquivo `Hefesto-Dualsense4Unix-<versão>-x86_64.flatpak` da release em
mãos (ou o `io.github.hefesto_team.hefesto_dualsense4unix.flatpak` que o
`scripts/build_flatpak.sh --bundle` grava na raiz do repositório):

```bash
flatpak install --user Hefesto-Dualsense4Unix-<versão>-x86_64.flatpak
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

O sandbox não grava no sistema. O ajudante que grava mora dentro do pacote e roda
no sistema, num terminal fora do Flatpak, com a senha de administrador:

```bash
sudo bash "$(flatpak info --show-location io.github.hefesto_team.hefesto_dualsense4unix)/files/bin/install-host-udev.sh"
```

Rodado de dentro do Flatpak, o ajudante não grava nada: só imprime esse comando.
Depois de gravar, desconecte e reconecte o controle, e feche o Hefesto por inteiro
(inclusive na bandeja) antes de abri-lo de novo: o Flatpak só monta os caminhos de
`/run` ao abrir.

### O que o ajudante grava no sistema

Os mesmos arquivos do `install_udev.sh`, do `.deb` e do `install.sh` (os caminhos
estão em [instalacao.md](instalacao.md)):

```text
/etc/udev/rules.d/
  70-ps5-controller.rules (só é apagada: é o nome antigo da 73)
  71-uhid.rules  71-uinput.rules
  72-hefesto-touchpad-motion-uaccess.rules  72-ps5-controller-autosuspend.rules
  73-hefesto-ps5-controller.rules  76-dualsense-touchpad-libinput-ignore.rules
  77-dualsense-leds.rules  78-dualsense-motion-not-joystick.rules
  79-external-controller-leds.rules  80-motion-joydev-hide.rules
  81-hefesto-usb-host-power.rules  81-hefesto-usb-power.rules
  82-nintendo-pro-nosniff.rules  83-hefesto-bond-snapshot.rules
  84-nintendo-pro-variant.rules  85-hefesto-o-cabo-assume.rules
/etc/modules-load.d/hefesto-dualsense4unix.conf
/etc/modprobe.d/hefesto-dualsense-storm.conf  hefesto-btusb-no-autosuspend.conf
                hefesto-hid-nintendo.conf     hefesto-hid-playstation.conf
/etc/systemd/system/hefesto-hidraw-broker.service  hefesto-hidraw-broker.socket
                    hefesto-bt-bonds-snapshot.service
/usr/local/lib/hefesto-dualsense4unix/  o broker e os scripts do Bluetooth
/var/lib/hefesto-dualsense4unix/bt-bonds/  a pasta das cópias dos pareamentos
```

Mais o grupo `hefesto` (você entra nele) e os módulos de kernel `hefesto-hid-nintendo`,
`hefesto-hid-playstation`, `hefesto-rtw88-usb` e `hefesto-usb-f-hid`, que valem a partir
do próximo boot e exigem `dkms` no sistema.

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
e fecha com a janela. Para ele subir no login, ponha o comando acima no início
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
| `--socket=x11`, `--socket=wayland` | a janela e a troca automática de perfil. É `x11`, e não `fallback-x11`, porque a troca automática lê a janela dos jogos (a Steam, o Proton) pelo X11 mesmo com Wayland presente |
| `--socket=session-bus`, `--talk-name=org.freedesktop.portal.*` | portais e notificações |
| `--filesystem=xdg-run/hefesto-dualsense4unix:create` | a conversa entre a janela e o serviço |
| `--filesystem=xdg-config/hefesto-dualsense4unix:create` | os perfis |
| `--filesystem=~/.steam`, `--filesystem=~/.local/share/Steam` e as instalações da Steam por Flatpak e Snap (só leitura) | as opções dos jogos da Steam |
| `--allow=bluetooth`, `--share=network` | o medidor do rádio de cada adaptador |
| `--filesystem=/run/hefesto-hidraw-broker:ro` | o serviço que entrega o controle físico ao Hefesto |
| `--filesystem=/run/hefesto-dualsense4unix` | a trava comum do rádio, dividida com os serviços do sistema |
| `--filesystem=/run/udev/data:ro` | a base do udev: quem move o cursor, e a identidade do controle para a vibração |
| `--filesystem=/run/ostree-booted:ro` | saber se o sistema é de imagem (Silverblue, Bazzite), para não sugerir um comando de pacote que não vale lá |
| `--system-talk-name=org.bluez` | parear, reconectar, remover e mover controles de adaptador |
| `--system-talk-name=org.freedesktop.NetworkManager` | ler o canal do Wi-Fi, sem varrer |
| `--filesystem=/var/lib/hefesto-dualsense4unix:ro` | o diário dos serviços do sistema, só leitura |

### O BlueZ e o diário dos serviços do sistema

Pelo `org.bluez`, parear, reconectar, remover e mover de adaptador funcionam no
Flatpak como fora dele, e o agente de pareamento do Hefesto atravessa o
sandbox. O diário dos serviços do sistema entra só para leitura. Pelo
`org.freedesktop.NetworkManager` o Hefesto só lê o canal e a largura da rede
Wi-Fi em uso, para a aba Conexões; nunca varre.

O que continua sem alcançar: a ponte de administrador
(`bt_ponte_privilegiada.sh`, pelo `sudo`), que não existe no sandbox. Sem a ponte, o
Hefesto do Flatpak não derruba a conexão morta de um controle, e um controle
esquecido num adaptador pode voltar quando os pareamentos são restaurados.

## O teclado na tela

O L3 abre o teclado na tela no modo Navegação. No Flatpak ele vem dentro do
pacote (`wvkbd`), porque um programa do sistema é invisível no sandbox. O
`onboard` não vem: ele digita pelo X11 e, numa sessão Wayland, não alcançaria
as janelas.

## Desinstalar

Primeiro as regras e os arquivos do sistema, porque o ajudante que os tira mora no
Flatpak. Num terminal fora do Flatpak:

```bash
sudo bash "$(flatpak info --show-location io.github.hefesto_team.hefesto_dualsense4unix)/files/bin/install-host-udev.sh" --remover
```

Ele apaga tudo o que a lista acima mostra, para o serviço do broker, devolve os
nós do controle e remove os módulos DKMS. Ficam o grupo `hefesto` e as cópias dos
pareamentos Bluetooth em `/var/lib/hefesto-dualsense4unix/bt-bonds/`, se existirem.
Como os arquivos são os mesmos do `install.sh` e do `.deb`, o comando também tira os
deles: use-o só se você não vai mais usar o Hefesto por nenhum formato.

Depois, o aplicativo:

```bash
flatpak uninstall --user io.github.hefesto_team.hefesto_dualsense4unix
rm -rf ~/.var/app/io.github.hefesto_team.hefesto_dualsense4unix/   # opcional: os seus perfis
```
