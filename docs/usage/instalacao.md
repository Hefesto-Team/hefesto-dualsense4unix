# Instalação

O caminho curto está no [`README.md`](../../README.md). Esta página traz o
resto: os requisitos, as opções do instalador, o que ele muda no sistema e como
desfazer.

## Requisitos

- Linux com `systemd-logind` ativo. Distribuições sem ele (Alpine com OpenRC,
  Void, Artix) não são suportadas; ver [ADR-009](../adr/009-systemd-logind-scope.md).
- Python 3.10 ou mais novo.
- Bibliotecas do sistema: `libhidapi-hidraw0`, `libhidapi-dev`, `libudev-dev` e
  `libxi-dev`. O instalador as instala pelo gerenciador de pacotes (apt, dnf ou
  pacman).
- Para os módulos de kernel: `dkms`, as ferramentas de compilação e os headers
  do kernel em uso. Se faltarem, o instalador pergunta antes de instalá-los. Sem
  eles o produto funciona com os drivers de fábrica, só sem as correções.
- Teclado na tela: `wvkbd` no Wayland, `onboard` no X11. O instalador instala o
  certo para a sua sessão; é ele que o L3 abre no modo Navegação.
- No GNOME, uma extensão de indicadores para o ícone da bandeja
  (`ubuntu-appindicators@ubuntu.com` ou `appindicatorsupport@rgcjonas.gmail.com`).

As versões conferidas de cada peça estão em [versoes-validadas.md](versoes-validadas.md).

## Do código-fonte

A versão corrente é a alfa **0.9.4.5**. Instale pelo ramo padrão, que é o que
as fotos e as páginas descrevem:

```bash
git clone https://github.com/Hefesto-Team/hefesto-dualsense4unix.git
cd hefesto-dualsense4unix
./install.sh
```

Sem opções, o instalador pergunta o formato (Enter escolhe o nativo), pede a
senha de administrador uma vez e pergunta antes de cada passo opcional. Enter
aceita a resposta padrão em todas. Não rode com `sudo` na frente: o `HOME`
passaria a ser o do root.

| Opção | Efeito |
|---|---|
| `--yes`, `-y` | responde sim a tudo e usa o formato nativo (sem terminal interativo, use esta) |
| `--dry-run`, `-n` | mostra cada mudança que faria e não escreve nada |
| `--format=native\|flatpak\|appimage\|deb` | pula a pergunta do formato |
| `--no-udev` | pula as regras udev e os passos que escrevem em `/etc`, menos os dos módulos de kernel |
| `--no-dkms` | não instala os módulos de kernel, nem os arquivos de `modprobe.d` que os configuram (`hefesto-hid-nintendo.conf` e `hefesto-hid-playstation.conf`) |
| `--no-systemd` | não instala o serviço |
| `--no-snd-quirk` | não grava a correção do áudio USB do controle |
| `--no-proton-pin` | não fixa a versão do Proton dos jogos |
| `--keep-steam-input` | mantém o Steam Input ligado (o padrão é desligá-lo) |
| `--no-kernel-watch` | não instala a vigia do diário do kernel |
| `--force-xwayland` | abre a janela pelo XWayland |
| `--no-dev` | cria o ambiente sem as ferramentas de desenvolvimento |

`./install.sh --help` mostra a lista completa.

Com o Secure Boot ligado, os módulos de kernel só carregam depois de você
inscrever a chave do DKMS e reiniciar. O instalador diz qual chave inscrever:
`/var/lib/shim-signed/mok/MOK.der` no Ubuntu e no Pop!_OS, e
`/var/lib/dkms/mok.pub` nas outras distribuições.

## O que o instalador muda no sistema

| Caminho | O que é |
|---|---|
| `/etc/udev/rules.d/` | as regras dos controles, do touchpad, do giroscópio, da energia do USB e da cópia dos pareamentos |
| `/etc/modules-load.d/hefesto-dualsense4unix.conf` | carrega `uinput` e `uhid` no boot |
| `/etc/modprobe.d/` | a correção do áudio USB do controle, o adaptador Bluetooth sem suspensão e os parâmetros dos módulos (`hefesto-hid-nintendo.conf`, `hefesto-hid-playstation.conf`) |
| `/etc/bluetooth/main.conf.d/` | conexão rápida e novo pareamento no BlueZ |
| `/etc/systemd/system/` | o serviço que entrega o controle físico ao Hefesto, o agente de pareamento, dois timers do Bluetooth e um ajuste do `bluetooth.service` |
| `~/.config/systemd/user/` | as suas unidades, que ficam rodando: o serviço (`hefesto-dualsense4unix.service`), a vigia do USB (`hefesto-dualsense4unix-storm-watch.service`) e o vigia do Steam Input (`hefesto-steam-input-guard.path`, `hefesto-steam-input-guard.timer` e `hefesto-steam-input-guard.service`). A que abre a janela no início da sessão (`hefesto-dualsense4unix-gui-hotplug.service`) só entra se você aceitar |
| `/usr/local/lib/hefesto-dualsense4unix/` | o programa desse serviço e os scripts de manutenção do Bluetooth |
| `/var/lib/hefesto-dualsense4unix/bt-bonds/` | cópias de segurança dos pareamentos Bluetooth |
| cmdline do kernel | `usbcore.autosuspend=-1` e `usbcore.quirks=054c:0ce6:gn,054c:0df2:gn`, pelo kernelstub ou pelo grub. Um valor que já existia é preservado, e o desinstalador tira só o que o Hefesto pôs |
| módulos de kernel (DKMS) | `hefesto-hid-playstation`, `hefesto-hid-nintendo` e `hefesto-rtw88-usb`. Eles não apagam os módulos de fábrica e valem a partir do próximo boot |
| teclado na tela | `wvkbd` ou `onboard`, pelo gerenciador de pacotes |
| a Steam | desliga o Steam Input, põe o Hefesto nas Opções de Inicialização dos jogos e fixa o Proton, sempre com cópia de segurança |

O `hefesto-rtw88-usb` corrige um adaptador Wi-Fi USB (RTL8822BU) que derrubava
o Bluetooth do controle. Sem esse aparelho, ele não faz nada.

### O vigia do Steam Input

O Steam Input não é desligado uma vez só: o vigia volta a desligá-lo e repõe o
Hefesto nas Opções de Inicialização. Ele acorda quando a Steam grava em
`userdata/` (o `.path`) e a cada 30 minutos (o `.timer`). Com a Steam aberta ele
espera. Se o vigia parar, a aba Sistema avisa.

Para desligar só o vigia:

```bash
systemctl --user disable --now hefesto-steam-input-guard.path hefesto-steam-input-guard.timer
```

### O Bluetooth

Quatro ajustes entram por padrão:

- **O BlueZ corrigido (5.86).** O BlueZ 5.72 do Ubuntu 24.04 trava com vários
  controles e pode perder pareamentos. O instalador só instala o BlueZ corrigido
  se os pacotes já estiverem em `~/.cache/hefesto-dualsense4unix/bluez-backport/`;
  a receita está em [receita-backport-bluez.md](receita-backport-bluez.md). Depois
  da troca, pareie os controles de novo uma vez.
- **O agente de pareamento** (`bt-agent`, do pacote `bluez-tools`) responde aos
  pedidos do BlueZ. Sem ele o pareamento pode ficar pela metade.
- **Dois timers:** `hefesto-bt-bonds-snapshot.timer` copia os pareamentos a cada
  15 minutos, e `hefesto-bt-health-watchdog.timer` reinicia o Bluetooth quando
  ele trava.
- **A cópia dos pareamentos** em `/var/lib/hefesto-dualsense4unix/bt-bonds/`,
  tirada pelo timer e a cada conexão. `scripts/bt_bonds_restore.sh` a devolve.

## Pacotes

Os formatos abaixo existem, mas o caminho testado é o do código-fonte.

- **`.deb`**: `scripts/build_deb.sh`. No Ubuntu e no Pop!_OS 22.04 e 24.04, o
  `pydantic` do apt é o 1.x; rode antes `pip install --user 'pydantic>=2'`.
- **Flatpak**: `scripts/build_flatpak.sh`; ver [flatpak.md](flatpak.md).
- **AppImage**: `scripts/build_appimage_gui.sh`.
- **Arch**: `packaging/arch/PKGBUILD`. **Fedora**: `packaging/fedora/hefesto-dualsense4unix.spec`.
  **Nix**: `packaging/nix/package.nix`, pelo `flake.nix` da raiz.

## Reaplicar as regras udev

Depois de trocar de kernel ou perder a permissão do controle:

```bash
sudo bash scripts/install_udev.sh                                        # código-fonte
sudo bash /usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh # .deb
flatpak run --command=install-host-udev.sh io.github.hefesto_team.hefesto_dualsense4unix
```

Desconecte e reconecte o controle. `ls -l /dev/hidraw* /dev/uinput /dev/uhid`
deve mostrar um `+` (a permissão da sessão).

## Desinstalar

```bash
./uninstall.sh
```

Desfaz o que o instalador fez: serviços, regras udev, arquivos de `modprobe.d` e
do BlueZ, timers, módulos de kernel, os parâmetros de boot que o Hefesto pôs e
as Opções de Inicialização da Steam.

Ficam, por padrão: a sua configuração, as cópias de pareamento do Bluetooth, o
quirk de boot do USB (`--remove-usb-quirk` o tira) e o BlueZ corrigido
(`--restore-bluez` devolve o da distribuição).

Cada desinstalação guarda as cópias de pareamento numa pasta com a data,
`/var/lib/hefesto-dualsense4unix/bt-bonds.pre-uninstall-<data>`, e diz como
restaurá-las. `--purge-config` apaga a configuração (depois de uma cópia de
segurança) e todas essas cópias, inclusive as de uninstalls anteriores.
`--dry-run` mostra o que sairia, sem tirar nada.

Para limpar instalações antigas de outros formatos:

```bash
bash scripts/purge.sh --dry-run
bash scripts/purge.sh --yes
```

## Onde foi testado

| Distribuição | Sessão | Estado |
|---|---|---|
| Pop!\_OS 24.04 | COSMIC | testado com controles |
| Ubuntu 22.04 e 24.04 | GNOME | integração contínua, sem controle |
| Fedora, Arch, Debian, Mint | qualquer | não testado; relatos são bem-vindos |
