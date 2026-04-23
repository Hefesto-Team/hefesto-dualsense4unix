# Hotplug da GUI — abrir o Hefesto ao conectar o DualSense

Quando o controle é conectado via USB, a GUI do Hefesto pode aparecer
automaticamente. Útil para quem pluga o DualSense e espera o painel já
pronto, sem abrir pelo menu ou lembrar do tray.

## Como funciona

Duas peças trabalham juntas:

1. **udev rule** `73-ps5-controller-hotplug.rules` — o kernel detecta o
   `ACTION=="add"` do USB com `idVendor==054c` (DualSense ou DualSense
   Edge) e marca o device com `TAG+="systemd"`. A variável
   `SYSTEMD_USER_WANTS=hefesto-gui-hotplug.service` instrui o systemd
   `--user` da sessão gráfica ativa a acionar a unit.

2. **systemd user unit** `hefesto-gui-hotplug.service` — unidade
   `Type=oneshot`, disparada pelo udev. O `ExecStart` faz um `pgrep`
   para detectar se a GUI já está aberta; se já está, aborta. Caso
   contrário, invoca `%h/.local/bin/hefesto-gui` (launcher desanexado
   criado pelo `install.sh`).

Efeito líquido: **plugar com GUI fechada abre o painel em ~2 s;
plugar com GUI aberta não faz nada** (idempotente).

## Habilitar

Já é instalado por padrão pelo `install.sh`. Para pular no momento da
instalação:

```bash
./install.sh --no-hotplug-gui
```

Para habilitar manualmente depois:

```bash
mkdir -p ~/.config/systemd/user
cp assets/hefesto-gui-hotplug.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable hefesto-gui-hotplug.service

sudo cp assets/73-ps5-controller-hotplug.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Desabilitar

Desabilita a unit mas mantém as udev rules de permissão:

```bash
systemctl --user disable hefesto-gui-hotplug.service
rm ~/.config/systemd/user/hefesto-gui-hotplug.service
systemctl --user daemon-reload
```

Para remover a udev rule também:

```bash
sudo rm /etc/udev/rules.d/73-ps5-controller-hotplug.rules
sudo udevadm control --reload-rules
```

O `uninstall.sh` já faz as duas remoções (`--udev` remove a regra).

## Limitações## Bluetooth (FEAT-HOTPLUG-BT-01)

Parear o DualSense via Bluetooth também dispara a GUI automaticamente.
A regra complementar `74-ps5-controller-hotplug-bt.rules` observa
`ACTION=="add" SUBSYSTEM=="hidraw" KERNELS=="0005:054C:0CE6.*"` (0005
= BUS_BLUETOOTH, 054C = Sony, 0CE6/0DF2 = DualSense/Edge).

Pareamento inicial continua manual — use `bluetoothctl` ou o painel
Bluetooth do GNOME/COSMIC:

```bash
bluetoothctl
# [bluetooth]# scan on
# segure Create+PS no controle até a lightbar piscar
# [bluetooth]# pair AA:BB:CC:DD:EE:FF
# [bluetooth]# trust AA:BB:CC:DD:EE:FF
```

Uma vez pareado, reconectar (plugar e desplugar o USB, ou `connect`
no bluetoothctl) aciona a GUI. Se o `KERNELS` real no seu kernel
divergir dos wildcards, confirme com:

```bash
udevadm info -a /dev/hidrawN | grep KERNELS
```

E adicione a variante em `74-ps5-controller-hotplug-bt.rules` localmente.

## Limitações e escopo remanescentes
- **Sessões GNOME/Pop!_OS modernas** herdam `DISPLAY`/`WAYLAND_DISPLAY`
  automaticamente para o systemd `--user`. Em sessões mais antigas, pode
  ser necessário exportar as variáveis manualmente no `ExecStart`.
- **Sem systemd-logind** (Alpine/Void/Gentoo OpenRC): o mecanismo
  `SYSTEMD_USER_WANTS` não se aplica. Ver
  `docs/adr/009-systemd-logind-scope.md`.
- **Múltiplos controles:** se dois DualSenses forem conectados em menos
  de 2 s, duas triggers são emitidas, mas o `pgrep` na segunda bloqueia
  o spawn duplicado.

## Verificar que está ativo

```bash
systemctl --user status hefesto-gui-hotplug.service
ls -l /etc/udev/rules.d/73-ps5-controller-hotplug.rules
```

Para testar sem plugar fisicamente:

```bash
systemctl --user start hefesto-gui-hotplug.service
```

Deve abrir a GUI se ainda não estiver aberta.
