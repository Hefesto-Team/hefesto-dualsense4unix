# Instalação — detalhes

O caminho curto está no [`README.md`](../../README.md). Esta página é o detalhe:
todas as formas de instalar, o que o instalador toca no sistema, e como reverter.

## Requisitos

**Obrigatórios**

- Linux com `systemd-logind` ativo. Distros sem `logind` (Alpine OpenRC, Void
  runit, Artix) estão fora de escopo — ver [ADR-009](../adr/009-systemd-logind-scope.md).
- Python 3.10 ou superior.
- Bibliotecas do sistema: `libhidapi-hidraw0`, `libhidapi-dev`, `libudev-dev`, `libxi-dev`.

**Recomendados**

- GTK 3 + PyGObject — sem eles não há janela, só CLI e TUI.
- `wlrctl` em sessões Wayland (o instalador oferece instalar em COSMIC).
- Extensão `ubuntu-appindicators@ubuntu.com` no GNOME 42+, para o ícone de bandeja.

**Opcionais**

- `python-uinput` — extra `[emulation]`, para o controle virtual pela via uinput.
- `dkms` + `linux-headers-$(uname -r)` — para os módulos de kernel (abaixo).
  Sem eles o instalador só avisa e segue; os módulos do kernel continuam valendo.

## Do código-fonte

A versão corrente é a alfa **0.7.0** (01/08/2026) e o ponto de instalação é a
**tag `v0.7.0`** do fork `[REDACTED]/hefesto-dualsense4unix` — tag, não branch:
as branches de trabalho recebem commits durante a sessão e não são um ponto
estável para instalar. O `main` do repositório de origem
(`AndreBFarias/hefesto-dualsense4unix`) está na v3.0.0, de abril de 2026, e
**não** contém o que esta página descreve — ver a caixa "Onde esta versão mora"
no [`README.md`](../../README.md).

```bash
git clone https://github.com/[REDACTED]/hefesto-dualsense4unix.git
cd hefesto-dualsense4unix
git checkout v0.7.0
./install.sh
```

Sem flags, o `install.sh` mostra um seletor de formato (1 native · 2 flatpak ·
3 appimage · 4 deb; Enter = native), pede a senha de administrador **uma vez** no
começo e conduz 11 passos. As perguntas que ele faz têm padrão seguro — dá para
sair apertando Enter em todas.

Flags úteis:

| Flag | Efeito |
|---|---|
| `--yes`, `-y` | responde sim a tudo e assume o formato `native` (sem TTY, use esta) |
| `--format=native\|flatpak\|appimage\|deb` | pula o seletor |
| `--force-xwayland` | grava `GDK_BACKEND=x11` no `.desktop` — recomendado em COSMIC |
| `--no-udev` | pula as regras udev e a maioria dos passos que escrevem em `/etc` (cmdline, BlueZ, broker, `modprobe.d` do btusb e do storm). **Não** cobre os passos de DKMS: eles gravam `/etc/modprobe.d/hefesto-hid-nintendo.conf` e `hefesto-hid-playstation.conf` e só param com `--no-dkms` |
| `--no-dkms` | não instala os três módulos de kernel (nem as duas `modprobe.d` que os configuram) |
| `--no-systemd` | não instala a unit do daemon — nem no passo 6, nem no 7a (nada é copiado, habilitado ou iniciado) |
| `--no-snd-quirk` | não grava `/etc/modprobe.d/hefesto-dualsense-storm.conf` (o quirk do `snd_usb_audio` que cura o travamento do USB e é padrão) |
| `--no-proton-pin` | não trava a versão de Proton dos jogos |
| `--keep-steam-input` | preserva o Steam Input (o padrão é desligá-lo) |
| `--no-kernel-watch` | não instala a vigia do journal |
| `--no-cosmic-applet` | não compila o applet COSMIC |
| `--with-usb-quirk` | redundante hoje: os mesmos tokens `usbcore.quirks` já entram no cmdline por padrão (passo 3e). A flag só adianta o passo 3b |
| `--wifi-powersave-off` | opt-in: desliga o powersave de WiFi do NetworkManager |
| `--no-dev` | cria o ambiente virtual sem as ferramentas de desenvolvimento |

`./install.sh --help` imprime a lista completa.

## O que o instalador mexe no sistema

O Hefesto não é um aplicativo de espaço de usuário puro: boa parte das curas mora
em regra de udev, módulo de kernel e serviço de sistema. O que ele grava fora do
seu `$HOME`, com os padrões de fábrica:

| Caminho | O que é |
|---|---|
| `/etc/udev/rules.d/` | 14 regras (permissão, autosuspend, LEDs, touchpad, motion, energia do USB, sniff e variante dos Nintendo-class, snapshot de bonds). Uma 15ª, a `75` que desliga o áudio USB do controle, só entra com `--disable-usb-audio` |
| `/etc/modules-load.d/hefesto-dualsense4unix.conf` | carrega `uinput` e `uhid` no boot |
| `/etc/modprobe.d/hefesto-dualsense-storm.conf` | a cura do travamento do USB (mantém mic e fone do controle) |
| `/etc/modprobe.d/hefesto-btusb-no-autosuspend.conf` | evita o adaptador BT dormir no meio do jogo |
| `/etc/modprobe.d/hefesto-hid-nintendo.conf` | parâmetros do módulo de controles Nintendo-class |
| `/etc/modprobe.d/hefesto-hid-playstation.conf` | parâmetros do módulo do DualSense (retry dos feature reports da probe) |
| `/etc/bluetooth/main.conf.d/` | dois drop-ins do BlueZ (conexão rápida, re-pareamento) |
| `/etc/systemd/system/` | broker de hidraw, agente Bluetooth, 2 timers de resiliência BT, drop-in do `bluetooth.service` |
| `/usr/local/lib/hefesto-dualsense4unix/` | binário do broker + scripts de manutenção Bluetooth |
| `/var/lib/hefesto-dualsense4unix/bt-bonds/` | cópias de segurança dos pareamentos Bluetooth |
| cmdline do kernel | `usbcore.autosuspend=-1` **e** `usbcore.quirks=054c:0ce6:gn,054c:0df2:gn`, via kernelstub ou grub (passo 3e, padrão). O passo funde o token de quirks que já existir em vez de somar um segundo, registra que a atribuição é do Hefesto e o `uninstall.sh` reverte só a nossa; um valor posto por terceiros é registrado e preservado |
| **DKMS** | `hefesto-hid-nintendo`, `hefesto-hid-playstation` e `hefesto-rtw88-usb` — três módulos fora da árvore |
| configuração da Steam | desliga o Steam Input, migra as Opções de Inicialização, trava o Proton (sempre com cópia de segurança ao lado) |

Quatro curas de Bluetooth entram **por padrão** e merecem nome, porque mexem em
serviço de sistema:

- **Backport local do BlueZ (alvo 5.86)** — o `bluez` 5.72 do Ubuntu 24.04
  travou seis vezes em cinco dias com controles BT em uso, e um dos travamentos
  comeu um pareamento recém-feito. O instalador **não compila** nada: ele só
  instala os `.deb` que já estiverem em
  `~/.cache/hefesto-dualsense4unix/bluez-backport/`, conferindo o `SHA256SUMS`.
  Sem esse cache, ele avisa como gerar e segue — nada falha. Se a troca de versão
  acontecer, é o `postinst` do próprio `bluez` que reinicia o `bluetoothd`, e a
  migração descarta os pareamentos antigos: parear de novo uma vez resolve.
  `uninstall.sh --keep-bluez` preserva a versão instalada.
- **Agente de pareamento persistente** — um serviço de sistema com `bt-agent`
  (`--capability=NoInputNoOutput`) fica registrado no D-Bus para responder aos
  pedidos de confirmação do BlueZ. Sem ele nasce o pareamento pela metade
  (`Paired: yes` / `Bonded: no`), que trava o controle até um novo pareamento
  manual. Exige o pacote `bluez-tools`; ausente, o passo só avisa.
- **Dois timers de resiliência** — `hefesto-bt-bonds-snapshot.timer` (a cada 15
  minutos) e `hefesto-bt-health-watchdog.timer` (a cada 2 minutos). O watchdog
  reinicia o `bluetooth.service` apenas quando o estado está de fato doente, com
  limite de frequência.
- **Snapshot dos pareamentos** — cópias em
  `/var/lib/hefesto-dualsense4unix/bt-bonds/`, tiradas pelo timer acima e também
  na borda da conexão (regra udev `83`), com deduplicação por conteúdo. É a rede
  de segurança para quando o `bluetoothd` perde um bond: o
  `scripts/bt_bonds_restore.sh` devolve.

Sobre os três módulos DKMS: eles **não apagam** os módulos originais do kernel —
entram por precedência (`updates/dkms`) e só valem no próximo boot ou replug. Se
o `dkms` ou os headers do kernel faltarem, ou se a compilação falhar, o instalador
avisa e continua; o kernel segue com os módulos de fábrica. Para não instalá-los,
use `--no-dkms` (a flag cobre os três de uma vez).

O `hefesto-hid-playstation` existe por causa de um caso medido em julho de 2026:
com dois DualSense pareando com cerca de um segundo de diferença, o segundo
perdia o canal de controle L2CAP, o `GET_REPORT` estourava o tempo no BlueZ e o
controle inteiro se perdia. O patch faz o driver repetir os feature reports que
expiram durante a probe. Detalhe em `assets/dkms/hid-playstation/README.md`.

O `hefesto-rtw88-usb` mexe no driver de um **dongle WiFi RTL8822BU** — ele existe
porque esse dongle específico derrubava o Bluetooth do controle. Se você não tem
esse hardware, `--no-dkms` não custa nada.

## Pacotes

Os formatos abaixo existem, mas para a alfa o caminho testado é o do código-fonte.

- **`.deb`** — `scripts/build_deb.sh` gera `dist/hefesto-dualsense4unix_<versão>_amd64_<pytag>.deb`
  com o ambiente virtual embutido em `/opt/hefesto-dualsense4unix/venv/`.
  Metadados em `packaging/debian/`.
- **Flatpak** — manifesto em `flatpak/br.andrefarias.Hefesto.yml`; build por
  `scripts/build_flatpak.sh`. Detalhes de sandbox em [`flatpak.md`](flatpak.md).
- **AppImage** — `scripts/build_appimage.sh` (só CLI) e `scripts/build_appimage_gui.sh`
  (com GTK3 embutido).
- **Arch** — `packaging/arch/PKGBUILD`, `makepkg -si`.
- **Fedora** — `packaging/fedora/hefesto-dualsense4unix.spec`, `rpmbuild`.
- **Nix** — `packaging/nix/package.nix`, consumido pelo `flake.nix` da raiz.

> **Atenção com pydantic no Ubuntu/Pop!\_OS 22.04 e 24.04:** o `python3-pydantic`
> do apt nessas versões é 1.x, e o projeto usa API 2.x. Se instalar por `.deb`,
> rode antes `pip install --user 'pydantic>=2'` — o Python prefere
> `~/.local/lib/.../site-packages` ao pacote do sistema. Flatpak e AppImage já
> trazem a versão certa.

## Regras udev: reaplicar

São instaladas automaticamente. Para reaplicar depois de trocar de kernel ou
perder permissão:

```bash
# código-fonte
sudo bash scripts/install_udev.sh

# .deb instalado
sudo bash /usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh

# Flatpak
flatpak run --command=install-host-udev.sh br.andrefarias.Hefesto
```

Os três aplicam o mesmo conjunto e são idempotentes. Depois de rodar, desconecte
e reconecte o controle. Para conferir o acesso:

```bash
ls -l /dev/hidraw* /dev/uinput /dev/uhid   # a ACL via uaccess deve aparecer com '+'
```

## Desinstalar

```bash
./uninstall.sh
```

Reverte o que o `install.sh` fez: units, regras udev, drop-ins de modprobe e do
BlueZ, timers de resiliência, broker, applet, módulos DKMS, parâmetros de cmdline
registrados como do Hefesto, e as Opções de Inicialização da Steam.

Não remove por padrão: a **sua configuração** (`--purge-config` remove, com cópia
de segurança), o quirk de boot do USB (`--remove-usb-quirk`) e regras udev de
terceiros. `--keep-bluez` preserva a versão de BlueZ instalada.

Para descontaminação total, cobrindo instalações antigas em outros formatos:

```bash
bash scripts/purge.sh --dry-run   # mostra o que faria
bash scripts/purge.sh --yes
```

## Ambiente de desenvolvimento

```bash
./scripts/dev_bootstrap.sh --with-tray   # apt + venv + pip install -e (primeira vez)
./scripts/dev-setup.sh                   # início de cada sessão: valida a venv
./scripts/install_udev.sh                # regras udev (pede senha)
```

A flag `--with-tray` é obrigatória para rodar a janela localmente (`./run.sh --gui`)
e para os testes que importam PyGObject — sem ela o bootstrap não instala os
bindings GTK, e é isso que evita uma falha pesada em máquinas sem
`libgirepository-1.0-dev`.

## Onde o Hefesto foi testado

Sendo alfa, a validação é honesta e curta:

| Distro | Sessão | Estado |
|---|---|---|
| Pop!\_OS 24.04 | COSMIC (Wayland + XWayland) | ambiente principal de desenvolvimento e validação |
| Pop!\_OS 22.04 | GNOME 42 X11 | validado em versões anteriores |
| Ubuntu 22.04 / 24.04 | GNOME | cobertura de integração contínua (sem hardware) |
| Fedora, Arch, Debian, Mint | qualquer | **não testado** — relatos são bem-vindos |

Os pacotes de Arch, Fedora e Nix são mantidos, mas nenhum foi validado em hardware
nesta linha. Se você rodar em alguma dessas, um relato de issue vale ouro.
