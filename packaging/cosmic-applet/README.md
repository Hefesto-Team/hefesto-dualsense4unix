# Hefesto — Dualsense4Unix · Applet COSMIC

Applet **nativo do COSMIC** (Rust + [libcosmic]) que aparece em
**Configurações → Painel → Miniaplicativos** e fala com o daemon Python do
Hefesto via o IPC já existente (JSON-RPC 2.0 sobre Unix socket).

Ao contrário do tray `AppIndicator`/SNI (`app/tray.py`) — que, quando aparece,
fica *dentro* do applet "Área de status" — um applet COSMIC nativo registra-se
via `.desktop` com `X-CosmicApplet=true` e ganha sua própria entrada na lista de
Miniaplicativos, com botão **"Adicionar"**. É o "tray de verdade" no COSMIC.

## O que ele faz

- **Ícone no painel**: SEMPRE a logo do app (a bigorna com o martelo de
  `assets/hefesto-logo.svg`), em qualquer estado. Trocar o glifo conforme o
  daemon fazia a logo "sumir" da barra nas transições — o estado (offline,
  bateria, perfil) é mostrado DENTRO do popover, não no ícone.
- **Clique → popover** com:
  - bateria (% + transporte USB/Bluetooth);
  - perfil ativo;
  - **lista clicável de perfis** (clique troca o perfil via `profile.switch`);
  - **Abrir painel** → lança a GUI (`hefesto-dualsense4unix-gui`).
- Enquanto o popover está aberto, reconsulta o daemon (`daemon.state_full`) a
  ~1,5 Hz. Se o daemon não estiver rodando, **degrada graciosamente** (sem
  crash): mostra "Daemon desconectado".

## Requisitos

- **Rust / Cargo** (testado com cargo 1.95). Instale via [rustup] se necessário.
- Bibliotecas de sistema do libcosmic/Wayland (Debian/Ubuntu/Pop!_OS):

  ```bash
  sudo apt install libxkbcommon-dev libwayland-dev libgbm-dev libegl-dev \
      libinput-dev libudev-dev pkg-config
  ```

> A **primeira** compilação do libcosmic é longa (pode passar de 10 min) porque
> compila todo o stack iced/cosmic. Builds seguintes são rápidas (cache).

## Compilar

```bash
cd packaging/cosmic-applet
cargo build --release
```

O binário fica em `target/release/hefesto-dualsense4unix-applet`.

## Instalar

**Recomendado** (integrado ao instalador, a partir da raiz do repositório):

```bash
./install.sh --native --enable-cosmic-applet
```

Isso compila o applet, instala os artefatos e sobe o daemon nativo (que o
applet consome via IPC). Alternativa manual, direto deste diretório (requer
[`just`] e `sudo`):

```bash
just install
```

Ambos instalam:

| Artefato | Destino |
|---|---|
| binário | `/usr/local/bin/hefesto-dualsense4unix-applet` |
| `.desktop` | `/usr/share/applications/com.vitoriamaria.HefestoDualsense4Unix.desktop` |
| ícone colorido | `/usr/share/icons/hicolor/256x256/apps/com.vitoriamaria.HefestoDualsense4Unix.png` |
| ícone symbolic | `/usr/share/icons/hicolor/scalable/apps/com.vitoriamaria.HefestoDualsense4Unix-symbolic.svg` |

Depois rodam `gtk-update-icon-cache` e `update-desktop-database` (este último é
necessário para o COSMIC listar o applet em *Miniaplicativos*).

> Os dois ícones saem da MESMA identidade: o PNG é `assets/hefesto-logo.svg`
> rasterizado (`rsvg-convert -w 256 -h 256`) e o `-symbolic.svg` é a bigorna em
> silhueta — symbolic no COSMIC é monocromático e recolorido pelo tema, então
> não é o colorido reduzido. O `.desktop` pede `Icon=` sem sufixo (resolve no
> PNG); o symbolic atende quem pedir a variante monocromática.

Para remover: `just uninstall` (ou `./uninstall.sh`, que agora também limpa o
applet COSMIC).

## Adicionar ao painel

1. Abra **Configurações → Painel** (ou **Dock**) → **Miniaplicativos**
   (*Add applet*).
2. Procure por **"Hefesto - Dualsense4Unix"** e clique em **Adicionar**.
3. O ícone aparece no painel. Clique para abrir o popover.

> Se não aparecer logo, faça logout/login (o COSMIC relê os `.desktop` de
> applet na inicialização da sessão).

## Protocolo IPC

O applet espelha `src/hefesto_dualsense4unix/cli/ipc_client.py`:

- **Socket:** `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/hefesto-dualsense4unix.sock`
  (respeita `HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME` para o nome-base).
- **Framing:** uma linha JSON por requisição/resposta, terminada em `\n`, UTF-8.
- **Métodos usados:** `daemon.state_full`, `profile.list`, `profile.switch {name}`.
- Em Rust: `tokio::net::UnixStream` + `BufReader::read_line` + `serde_json`, com
  timeout de 250 ms por chamada. Socket ausente / timeout → "offline".

## Desenvolvimento

```bash
cargo fmt --check                 # formatação
cargo clippy --release -- -D warnings   # lint
just check                        # roda os dois acima
```

App-id: `com.vitoriamaria.HefestoDualsense4Unix` (mesmo padrão `com.vitoriamaria.*`
do `extra-cosmic-xkill-applet`, já validado no COSMIC).

## Licença

MIT.

[libcosmic]: https://github.com/pop-os/libcosmic
[rustup]: https://rustup.rs/
[`just`]: https://github.com/casey/just
