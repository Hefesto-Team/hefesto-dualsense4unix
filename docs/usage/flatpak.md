# Hefesto - Dualsense4Unix via Flatpak

Este documento explica como instalar e usar o Hefesto - Dualsense4Unix empacotado como Flatpak,
destinado principalmente a usuários do Pop!_OS COSMIC e outras distribuições que
adotam o Flatpak como formato canônico de distribuição de aplicativos.

---

## Requisitos

- Flatpak instalado (`sudo apt install flatpak` ou equivalente).
- Remote Flathub configurado:

  ```bash
  flatpak remote-add --if-not-exists flathub \
    https://dl.flathub.org/repo/flathub.flatpakrepo
  ```

- Política polkit funcional (para instalar regras udev — necessário apenas uma vez).

---

## Instalação

### Instalar a partir do bundle local

Se você baixou o arquivo `br.andrefarias.Hefesto.flatpak` (gerado pelo CI ou por
`scripts/build_flatpak.sh --bundle`):

```bash
flatpak install --user br.andrefarias.Hefesto.flatpak
```

### Construir localmente a partir do código-fonte

```bash
# Clonar o repositório pela TAG da versão (ver a caixa "Onde esta versão mora"
# no README). Esta página mandava clonar a branch sprint/harmonia-uhid até
# 29/07/2026; aquela branch parou dois lançamentos atrás.
git clone https://github.com/[REDACTED]/hefesto-dualsense4unix.git
cd hefesto-dualsense4unix
git checkout v0.9.1

# Construir o Flatpak (requer flatpak-builder)
./scripts/build_flatpak.sh --install
```

O script cuida de:

1. Construir o wheel Python (`python -m build`).
2. Chamar `flatpak-builder` com o manifest `flatpak/br.andrefarias.Hefesto.yml`.
3. Instalar no repositório local do usuário (`--user`).

---

## Configuração inicial de udev (obrigatória, apenas uma vez)

O Flatpak roda em sandbox e não pode instalar regras udev automaticamente. É
necessário executar o script de instalação de udev no host uma vez, com senha
de administrador:

```bash
flatpak run --command=install-host-udev.sh br.andrefarias.Hefesto
```

O script copia o mesmo conjunto canônico que o `install_udev.sh` do código-fonte
— hoje **15 regras** — para `/etc/udev/rules.d/`, mais o `modules-load` de
`uinput`/`uhid` e os drop-ins de `modprobe` do BlueZ e dos módulos HID. As
principais:

| Arquivo                               | Finalidade                                          |
|---------------------------------------|-----------------------------------------------------|
| `70-ps5-controller.rules`             | Acesso a `/dev/hidraw*` sem root (grupo `hefesto` + ACL por `uaccess`) |
| `71-uinput.rules`                     | Acesso a `/dev/uinput` para emulação de mouse       |
| `71-uhid.rules`                       | Acesso a `/dev/uhid` — o controle virtual como DualSense de verdade |
| `72-ps5-controller-autosuspend.rules` | Previne autosuspend USB que derruba a conexão       |
| `77-dualsense-leds.rules`             | Torna graváveis os nós de LED (lightbar e jogador)  |
| `81-hefesto-usb-power.rules`          | Controles e adaptadores BT nunca dormem no USB      |

A lista completa, item por item, está em
[`instalacao.md`](instalacao.md#o-que-o-instalador-mexe-no-sistema). O
`scripts/check_packaging_parity.sh` existe justamente para travar a paridade
entre os três caminhos de instalação — se uma regra entra no `install_udev.sh`
e não no helper do Flatpak, o gate reprova.

Após a instalação, desconecte e reconecte o controle DualSense.

---

## Executar o Hefesto - Dualsense4Unix

```bash
flatpak run br.andrefarias.Hefesto
```

Ou pelo lançador de aplicativos do sistema (Menu de aplicativos / COSMIC Store
exibe o Hefesto - Dualsense4Unix após instalação).

---

## Localização dos perfis e configurações

Dentro do sandbox Flatpak, os caminhos XDG são redirecionados:

| Caminho original (nativo)    | Caminho dentro do Flatpak                                      |
|------------------------------|----------------------------------------------------------------|
| `~/.config/hefesto-dualsense4unix/`         | `~/.var/app/br.andrefarias.Hefesto/config/hefesto-dualsense4unix/`            |
| `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/`  | `$XDG_RUNTIME_DIR/app/br.andrefarias.Hefesto/hefesto-dualsense4unix/`         |

Para copiar perfis criados fora do Flatpak:

```bash
mkdir -p ~/.var/app/br.andrefarias.Hefesto/config/hefesto-dualsense4unix/profiles/
cp ~/.config/hefesto-dualsense4unix/profiles/*.json \
   ~/.var/app/br.andrefarias.Hefesto/config/hefesto-dualsense4unix/profiles/
```

---

## Arquitetura dentro do sandbox

O Flatpak não tem acesso ao systemd do usuário; por isso o **daemon é executado
como processo filho da GUI** (sem `--install-service`). O ciclo de vida é:

1. `flatpak run br.andrefarias.Hefesto` inicia a GUI.
2. A GUI verifica se há daemon ativo; se não, inicia um processo filho interno.
3. Ao fechar a janela principal, o daemon filho é encerrado junto.

Para manter o daemon ativo com a janela fechada na área de notificação (tray),
o Hefesto - Dualsense4Unix usa o portal `org.freedesktop.portal.Background` para solicitar
permissão de execução em segundo plano ao compositor.

**Limitação conhecida**: o daemon Flatpak não é gerenciado pelo systemd do
usuário. Reinicializações do sistema não reiniciam o daemon automaticamente.
Para autostart, o usuário pode adicionar `flatpak run br.andrefarias.Hefesto`
ao autostart do ambiente gráfico.

---

## Localização (i18n)

> **A língua do Hefesto é o português do Brasil — decisão de 07/08/2026.**
> Esta seção descreve o que o bundle embarca e como forçar o catálogo EN. Ela
> **não** é convite a acrescentar idiomas: o catálogo alcança o esqueleto fixo
> da janela, e não alcança o texto que as abas escrevem enquanto rodam.
> **Medido em 07/08/2026:** dos 18 módulos de
> `src/hefesto_dualsense4unix/app/actions/`, **15** não importam a função de
> tradução e carregam 561 literais acentuados em português. Motivo e registro em
> `docs/process/sprints/2026-08-07-LINGUA-DO-PRODUTO-01-o-convite-a-traduzir-era-falso.md`.
>
> **Nota datada — 08/08/2026:** são **19** módulos desde a `RELANCAR-01`, que
> acrescentou `relancar.py`. Ele **não** importa a função de tradução, então a
> proporção passou a **16 de 19** — o quadro não mudou de natureza.

A partir da v3.4.0 o bundle Flatpak embarca **EN baseline** + **PT-BR
identidade** em `/app/share/hefesto-dualsense4unix/locale/{en,pt_BR}/
LC_MESSAGES/hefesto-dualsense4unix.mo`. O default é PT-BR (source
language).

Para forçar o catálogo EN (lembrando o alcance dito acima — a janela **não**
fica em inglês, só os rótulos do esqueleto fixo):

```bash
flatpak run --env=LANG=en_US.UTF-8 --env=LANGUAGE=en \
    br.andrefarias.Hefesto
```

Ou persistir o override permanentemente:

```bash
flatpak override --user --env=LANG=en_US.UTF-8 --env=LANGUAGE=en \
    br.andrefarias.Hefesto
# Próxima execução já pega EN sem precisar passar --env:
flatpak run br.andrefarias.Hefesto
```

> **Importante**: o sandbox Flatpak **filtra `LANG`/`LANGUAGE`** do
> host por padrão. Sem `--env=` ou `flatpak override --env=`, a GUI
> sempre cai no PT-BR (default do runtime GNOME 47).

Por que path próprio (e não `/app/share/locale/`): o runtime
`org.gnome.Platform//47` injeta symlinks de Locale Extension no deploy
sobrescrevendo `/app/share/locale/<lang>/` para vários idiomas
(incluindo pt_BR). Para sobreviver a essa intercepção, instalamos em
`/app/share/hefesto-dualsense4unix/locale/`, que o runtime não toca.
Detalhe técnico em `arquivo/processo-pre-1.0:docs/process/sprints/BUG-FLATPAK-LOCALE-SYMLINK-01.md`.

O encanamento de i18n **continua vivo e correto** — catálogos, scripts e os 308
`translatable="yes"` de `gui/main.glade` estão onde sempre estiveram. O que
mudou em 07/08/2026 é que o projeto parou de prometer que traduzi-los entrega
uma janela em outro idioma. Ver `.github/CONTRIBUTING.md`, seção "A língua do
produto".

---

## Permissões do sandbox

O manifest `flatpak/br.andrefarias.Hefesto.yml` declara as seguintes permissões:

| Permissão                                  | Motivo                                              |
|--------------------------------------------|-----------------------------------------------------|
| `--device=all`                             | Acesso a `/dev/hidraw*` (DualSense) e `/dev/uinput` |
| `--socket=wayland`                         | Interface GTK3 nativa no COSMIC/GNOME Wayland       |
| `--socket=x11`                             | X11 e XWayland — **não** é `fallback-x11`, ver nota  |
| `--socket=session-bus`                     | D-Bus de sessão (portals, notificações)             |
| `--filesystem=xdg-run/hefesto-dualsense4unix:create`      | Socket IPC entre GUI e daemon                       |
| `--filesystem=xdg-config/hefesto-dualsense4unix:create`   | Leitura e escrita de perfis                         |
| `--talk-name=org.freedesktop.portal.*`     | Portals do freedesktop (tray, background)           |

> **Por que `--socket=x11` e não `--socket=fallback-x11`.** O `fallback-x11` só
> monta o socket X11 quando **não** há Wayland — e no COSMIC há. Como esta
> interface roda com XWayland forçado, o `fallback-x11` deixava o sandbox sem
> socket nenhum e a janela não abria. O manifesto declara `--socket=x11` desde
> então, com o motivo escrito ao lado da linha. Esta tabela dizia
> `fallback-x11` até 29/07/2026: descrevia a versão que foi corrigida.

---

## Limitações conhecidas

1. **udev obrigatória no host**: as regras em `/etc/udev/rules.d/` precisam ser
   instaladas fora do sandbox. Execute `install-host-udev.sh` uma vez.

2. **Daemon sem systemd**: o daemon não é gerenciado pelo systemd do usuário
   dentro do Flatpak. Autostart depende do ambiente gráfico.

3. **Bluetooth**: o acesso a Bluetooth dentro do sandbox exige permissão adicional
   via D-Bus (`--talk-name=org.bluez.*`). Se o DualSense via BT não for detectado,
   execute `flatpak override --user --talk-name=org.bluez.* br.andrefarias.Hefesto`.

4. **Flathub**: o Hefesto - Dualsense4Unix não está publicado no Flathub ainda. A instalação é
   via bundle local ou build a partir do código-fonte.

5. **Teclado na tela: só `wvkbd`, e ele vem embutido** (desde 10/08/2026). O
   **L3** do controle abre o teclado na tela — o único caminho de fábrica para
   escrever texto. Nos outros formatos o programa vem do sistema (`wvkbd` em
   Wayland, `onboard` em X11); aqui não pode: **dentro do sandbox um pacote do
   host é invisível**. Este manifesto não pede
   `--talk-name=org.freedesktop.Flatpak` nem nada que permita
   `flatpak-spawn --host`, então o daemon só enxerga o que está em `/app` — sem
   um módulo próprio, a busca pelo binário devolveria "não existe" **para
   sempre, por construção**. Por isso o manifesto constrói o `wvkbd` (v0.14.3,
   binário `wvkbd-mobintl`) como módulo do bundle.

   **O `onboard` não é embutido, e é decisão, não esquecimento:** o sandbox
   monta `--socket=wayland` e o `onboard` digita por XTEST — dentro daqui ele
   abriria e não digitaria fora do XWayland. Embutir um teclado que abre e não
   digita é pior do que não embutir nenhum.

---

## Construir e distribuir

### Gerar bundle .flatpak para distribuição

```bash
./scripts/build_flatpak.sh --bundle
# Gera: br.andrefarias.Hefesto.flatpak no diretório raiz
```

### CI/CD

O workflow `.github/workflows/flatpak.yml` constrói o Flatpak automaticamente
em cada push para `main` e disponibiliza o artifact `hefesto-dualsense4unix-flatpak` por 30 dias.

---

## Desinstalar

```bash
flatpak uninstall --user br.andrefarias.Hefesto

# Opcional: remover dados do usuário
rm -rf ~/.var/app/br.andrefarias.Hefesto/
```

As regras udev instaladas no host permanecem. Para removê-las:

```bash
sudo rm /etc/udev/rules.d/70-ps5-controller.rules \
        /etc/udev/rules.d/71-uinput.rules \
        /etc/udev/rules.d/72-ps5-controller-autosuspend.rules
sudo udevadm control --reload-rules
```
