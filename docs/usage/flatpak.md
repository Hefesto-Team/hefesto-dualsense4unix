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
# Clonar o repositório
git clone https://github.com/AndreBFarias/hefesto.git
cd hefesto

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

O script copia três arquivos para `/etc/udev/rules.d/`:

| Arquivo                               | Finalidade                                          |
|---------------------------------------|-----------------------------------------------------|
| `70-ps5-controller.rules`             | Acesso a `/dev/hidraw*` sem root para o grupo input |
| `71-uinput.rules`                     | Acesso a `/dev/uinput` para emulação de mouse       |
| `72-ps5-controller-autosuspend.rules` | Previne autosuspend USB que derruba a conexão       |

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

A partir da v3.4.0 o bundle Flatpak embarca **EN baseline** + **PT-BR
identidade** em `/app/share/hefesto-dualsense4unix/locale/{en,pt_BR}/
LC_MESSAGES/hefesto-dualsense4unix.mo`. O default é PT-BR (source
language).

Para rodar a GUI em inglês:

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
Detalhe técnico em `docs/process/sprints/BUG-FLATPAK-LOCALE-SYMLINK-01.md`.

Para adicionar um novo idioma (ES, FR, DE, etc.), ver
`.github/CONTRIBUTING.md` seção "Contribuir traduções".

---

## Permissões do sandbox

O manifest `flatpak/br.andrefarias.Hefesto.yml` declara as seguintes permissões:

| Permissão                                  | Motivo                                              |
|--------------------------------------------|-----------------------------------------------------|
| `--device=all`                             | Acesso a `/dev/hidraw*` (DualSense) e `/dev/uinput` |
| `--socket=wayland`                         | Interface GTK3 nativa no COSMIC/GNOME Wayland       |
| `--socket=fallback-x11`                    | Fallback para ambientes X11                         |
| `--socket=session-bus`                     | D-Bus de sessão (portals, notificações)             |
| `--filesystem=xdg-run/hefesto-dualsense4unix:create`      | Socket IPC entre GUI e daemon                       |
| `--filesystem=xdg-config/hefesto-dualsense4unix:create`   | Leitura e escrita de perfis                         |
| `--talk-name=org.freedesktop.portal.*`     | Portals do freedesktop (tray, background)           |

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
