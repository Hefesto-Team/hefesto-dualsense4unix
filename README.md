<div align="center">

[![Licença](https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![GTK](https://img.shields.io/badge/GTK-3.0-green.svg)](https://www.gtk.org/)
[![Release](https://img.shields.io/github/v/release/AndreBFarias/hefesto?color=6a3fb4&label=release)](https://github.com/AndreBFarias/hefesto-dualsense4unix/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/AndreBFarias/hefesto-dualsense4unix/total?color=brightgreen&label=downloads)](https://github.com/AndreBFarias/hefesto-dualsense4unix/releases)
[![Testes](https://img.shields.io/badge/testes-2022%20unit-brightgreen.svg)](tests/unit/)
[![CI](https://github.com/AndreBFarias/hefesto-dualsense4unix/actions/workflows/release.yml/badge.svg)](https://github.com/AndreBFarias/hefesto-dualsense4unix/actions)

<div align="center">
<div style="text-align: center;">
  <h1 style="font-size: 2.2em;">Hefesto - Dualsense4Unix</h1>
  <img src="assets/appimage/Hefesto-Dualsense4Unix.png" width="120" alt="Logo Hefesto - Dualsense4Unix">
</div>
</div>
</div>

---

```
Versão: 4.0.0
Estado: runtime validado em Pop!_OS 22.04 e 24.04 COSMIC com DualSense USB+BT; 2022 testes unit, ruff clean, mypy zero; CURA DE RAIZ do travamento do USB (storm -71) instalada por padrão — ajuste do snd-usb-audio que acaba com as desconexões no meio do jogo PRESERVANDO mic e fone do controle (validado em gameplay: storm zero); VIBRAÇÃO dos jogos de ponta a ponta no modo "Jogar pelo Hefesto" com a máscara Xbox 360 (a máscara DualSense fazia o jogo ignorar o gamepad virtual e falar com o controle físico via hidraw); fim do CONTROLE DUPLICADO no jogo (botão "Copiar opções p/ jogos" cola as Opções de Inicialização da Steam); vibração dos jogos de ponta a ponta (force-feedback do gamepad virtual passa pelo gerenciador de rumble; Modo Nativo sem pisoteio de output/LEDs); MULTI-CONTROLE de verdade: identidade por MAC (fim da duplicação do 3º controle), co-op local por padrão com 2+ controles (um gamepad virtual POR jogador, player LED P1..P4 por controle), hotplug em ~2s; aba Início com o comutador "O que o controle faz agora" (Controlar o PC / Jogar pelo Hefesto / Jogar direto (Sony)) e "Desligar de verdade"; modo por perfil (sackboy_nativo, coop_local) + política de rumble por perfil; applet COSMIC com os modos; GUI COSMIC estabilizada (sem tela preta, sem jitter de hover); Modo Nativo solta o controle para os gatilhos adaptativos da Sony; point-and-click por perfil; diagnóstico anti-storm e do detector de janela no doctor/GUI; install.sh com seletor de formato (native/flatpak/appimage/deb), udev + uinput de cara e presets que se semeiam sozinhos
Alvo:   Linux com systemd-logind, Python 3.10+
Licença: MIT
```

> **Nota de release v3.8.1** — correções pós-V3.8 surgidas no review de UI/UX na máquina:
> a GUI subia a **104% de CPU consumindo ~5 GB de RAM** em poucos minutos por um busy-loop
> de `GLib.idle_add` com callbacks que retornavam `True` (caiu para **~2.4% CPU / ~90 MB**); os
> sticks ficavam lidos errado (~253 em repouso) quando o controle conectava após o boot do daemon,
> porque o `EvdevReader` cacheava o caminho do evdev no `__init__` e nunca o reavaliava no hotplug;
> a aba **Perfis** travava ao clicar/digitar porque `load_all_profiles()` rodava síncrono na thread
> GTK (agora vai pra worker thread + cache em memória); o item atualmente **selecionado do dropdown**
> ficava com fundo claro destoante no COSMIC (CSS cobre `:selected/:active/:checked`); e estreia o
> **modo jogo via long-press do PS** — segurar o botão PS por ~1s alterna a supressão da emulação de
> mouse/teclado mantendo os hotkeys de troca de perfil ativos (toque curto continua abrindo a Steam).
> Para o histórico das versões anteriores (V3.8 controle de ativação + applet visível, v3.7.x
> recuperação de instalação + áudio COSMIC, v3.6.x acabamento COSMIC + applet Rust, v3.4.0 i18n,
> v3.3.x tray fallback, v3.2.0 auditoria, v3.1.x hardening COSMIC, v3.0.0 rebrand) veja
> [`CHANGELOG.md`](CHANGELOG.md).

---

### Descrição

Daemon Linux para gatilhos adaptativos do controle DualSense (PS5). Porte espiritual do DualSenseX (Paliverse) para Unix, escrito em Python 3.10+ com GUI GTK3, TUI Textual e CLI. Compatível com jogos que usam o protocolo UDP do DSX (Cyberpunk 2077, Forza, Assetto Corsa) e com mods customizados via Unix socket JSON-RPC.

Projetado para Pop!\_OS, Ubuntu, Fedora, Arch, Debian e Mint. Usa `evdev` para entrada (contorna o driver `hid_playstation`) e `pydualsense` para saída HID — sem precisar de `HidHide` ou `unbind` manual do kernel.

---

### Principais Funcionalidades

| Categoria | Funcionalidade |
|-----------|----------------|
| **Gatilhos adaptativos** | 19 modos validados (Rigid, Pulse, Galloping, Machine, Bow, Automatic Gun, etc.) com fábricas pydantic |
| **Compatibilidade DSX** | Servidor UDP em `127.0.0.1:6969` aceita pacotes JSON no schema Paliverse |
| **IPC local** | Unix socket em `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/hefesto-dualsense4unix.sock`, JSON-RPC 2.0 sobre NDJSON, 10 métodos canônicos |
| **Perfis** | JSON validados com pydantic v2 em `~/.config/hefesto-dualsense4unix/profiles/`; 7 defaults (`navegacao`, `fps`, `aventura`, `acao`, `corrida`, `esportes`, `meu_perfil`) <!-- noqa: acentuacao --> |
| **Auto-switch** | Troca de perfil automática por janela ativa (X11 nativo, Wayland via portal XDG) com lock de 30 s após escolha manual via tray/CLI |
| **Resiliência** | Daemon sobe sem hardware presente; reconnect_loop probe 5 s; tolera plug/unplug em runtime sem morrer |
| **Hotkeys** | Combos sagrados PS+D-pad sem exigir grupo `input`; botão Mic físico muta microfone do sistema |
| **Lightbar e LEDs** | Barra RGB + luminosidade + 5 LEDs de jogador; presets rápidos (Todos, Player 1–4, Nenhum) |
| **Rumble** | Política global (Economia 0.3×, Balanceado 0.7×, Máximo 1.0×, Auto por bateria) aplicada também ao force-feedback dos JOGOS (vpad com FF_RUMBLE); persistível por perfil |
| **Emulação Xbox 360** | `uinput` virtual para jogos que só aceitam gamepads Microsoft |
| **Interface** | GUI GTK3 tema Drácula, TUI Textual com preview ao vivo, CLI `typer` com cores |
| **Plataforma** | `.deb` nativo (179 KB), bundle Flatpak `br.andrefarias.Hefesto`, AppImage, instalação via fonte |
| **Observabilidade** | Endpoint Prometheus opt-in em `127.0.0.1:9090/metrics` com 8 métricas canônicas |
| **Extensibilidade** | Plugins Python em `~/.config/hefesto-dualsense4unix/plugins/*.py` com hooks `on_tick` / `on_button_down` / `on_battery_change` |

---

### Interface

Status em tempo real com sticks L3/R3, barras de gatilho e grid 4×4 de glyphs acendendo em roxo quando pressionados.

<div align="center">
<img src="docs/usage/assets/readme_status.png" width="820" alt="Aba Status da GUI Hefesto - Dualsense4Unix com sticks, gatilhos e glyphs">
</div>

---

### Layout das abas (GUI GTK3)

A GUI principal expõe 10 abas no `GtkNotebook` central, cada uma cobrindo um eixo do controle. Pra cada aba, o que ela faz e o que você ajusta lá:

| Aba | Pra que serve | Controles principais |
|-----|---------------|----------------------|
| **Status** | Dashboard ao vivo do controle e do daemon. É a primeira aba e onde você confirma se conectou. | Conexão, Transporte (USB/BT), Bateria, Perfil ativo, Daemon (online/offline); barras L2/R2 0–255; sticks analógicos esquerdo (L3) e direito (R3) com X/Y; grid 4×4 de glyphs (X, O, □, , D-pad, L1/R1/L2/R2, Share, Options, PS, Touchpad) que acende em roxo quando pressionado. |
| **Gatilhos** | Configurar o efeito adaptativo de L2 e R2 separadamente. É a feature-flagship do projeto. | Por gatilho (L2 e R2): combobox **Modo** (19 modos: Off, Rigid, Pulse, Galloping, Machine, Bow, Automatic Gun, etc.), combobox **Preset** (intensidade leve/média/dura), botão **Aplicar**, botão **Desligar**. |
| **Lightbar** | Cor da barra LED frontal e LEDs de jogador. | Color picker RGB com prévia ao vivo, slider de **Luminosidade (%)**, botões **Aplicar no controle** / **Apagar**; checkboxes **LED 1–5** (player LEDs) com presets rápidos **Todos**, **Player 1–4**, **Nenhum** + botão **Aplicar LEDs**. |
| **Rumble** | Política global de vibração e teste dos motores. | Radios de política: **Economia** (0,3×), **Balanceado** (0,7×), **Máximo** (1,0×), **Auto** (dinâmico por bateria); slider **Intensidade global**; testar **Motor fraco (weak)** / **Motor forte (strong)** com **Testar por 500 ms**, **Aplicar**, **Parar**. |
| **Perfis** | Gerência de perfis JSON com auto-switch por janela. | Lista de perfis com prioridade; botões **Novo** / **Duplicar** / **Renomear** / **Excluir**; editor com modo **simples** (radios Steam / Navegador / Terminal / Editor / Jogo específico) e modo **avançado** (campos `window_class` / `title_regex` / `process_name`). |
| **Daemon** | Controle do service systemd `--user` que roda em background. | Status do daemon (online/offline), botões **Start** / **Stop** / **Restart**, **Instalar service** / **Desinstalar**; toggle de auto-start no boot; visualizador de log curto. |
| **Emulação** | Gamepad virtual Xbox 360 via `uinput`, pra jogos que só aceitam controles Microsoft. | Toggle **on/off** de `/dev/input/js*` virtual com forward 60 Hz; status do device emulado; mapeamento dos botões DualSense → Xbox360. |
| **Mouse** | Emulação de mouse usando o stick direito ou touchpad do DualSense. | Toggle **on/off**; sliders de sensibilidade X/Y; deadzone; modo touchpad vs stick; integração com daemon. |
| **Teclado** | Emulação de teclado/atalhos por botões (combos para hotkeys). | Mapeamento botão → keysym; persistência por perfil; testar combinação. |

> **Observação:** o footer global expõe **Aplicar**, **Salvar Perfil**, **Importar**, **Restaurar Default** — esses persistem o que está editado em qualquer aba ativa para o perfil corrente.

---

### Perfis e auto-switch

Editor dual: modo simples (radios Steam / Navegador / Terminal / Editor / Jogo específico) ou avançado (`window_class` / `title_regex` / `process_name`). Cada perfil tem prioridade; o matcher universal `fallback.json` (priority = -1000) garante comportamento de base.

<div align="center">
<img src="docs/usage/assets/readme_perfis.png" width="820" alt="Aba Perfis com lista, editor de matcher e presets">
</div>

---

### Gatilhos adaptativos

Cada gatilho (L2 e R2) expõe modo + preset. Presets de feedback (resistência contínua) ou vibração (pulsos) são salvos no perfil ativo. Custom permite editar os parâmetros brutos do DualSense.

<div align="center">
<img src="docs/usage/assets/readme_gatilhos.png" width="820" alt="Aba Gatilhos com seletores L2 e R2 lado a lado">
</div>

---

### Lightbar e LEDs de jogador

Cor RGB 24 bits, luminosidade 0-100 % e 5 indicadores inferiores. Checkboxes e presets enviam imediatamente ao hardware; o botão **Aplicar LEDs** reemite o padrão atual (útil após reconectar o controle ou trocar de perfil).

<div align="center">
<img src="docs/usage/assets/readme_lightbar.png" width="820" alt="Aba Lightbar com seletor de cor, slider de luminosidade e 5 LEDs de jogador">
</div>

---

### Rumble — política global

Escala a intensidade de todos os comandos de vibração antes de chegar ao hardware. Modo Auto lê a bateria do controle e suaviza o rumble quando ≤ 30 % (debounce de 5 s evita oscilação).

<div align="center">
<img src="docs/usage/assets/readme_rumble.png" width="820" alt="Aba Rumble com botões de política e sliders de teste">
</div>

---

### Daemon — systemd e logs

Status da unidade `hefesto-dualsense4unix.service` (`--user`), toggle de auto-start e janela ao vivo de `systemctl status` com histórico de `profile_activated`, `ipc_server_listening`, `udp_server_listening` e `hotkey_manager_started`.

<div align="center">
<img src="docs/usage/assets/readme_daemon.png" width="820" alt="Aba Daemon com saída do systemctl status ao vivo">
</div>

---

### Emulação Xbox 360

Para jogos que só aceitam gamepad Microsoft, o daemon expõe `/dev/input/js*` virtuais a partir do DualSense. Requer módulo `uinput` carregado e regra udev `71-uinput.rules` (aplicadas por `scripts/install_udev.sh`).

<div align="center">
<img src="docs/usage/assets/readme_emulacao.png" width="820" alt="Aba Emulação com device Xbox 360 virtual e combo sagrado">
</div>

---

### Jogar sem travar: vibração, controle duplicado e o travamento do USB

Três problemas clássicos do DualSense no Linux, e a receita que resolve os três (validada em gameplay):

**1. O controle desconecta sozinho no meio do jogo (travamento do USB).** É o kernel: ao reconectar, o driver de áudio USB (`snd-usb-audio`) sonda o mixer do controle e satura o canal de controle (EP0), o que derruba o USB (`can't add hid device: -71`) num laço. O Hefesto instala a **cura de raiz por padrão** — um ajuste do módulo (`/etc/modprobe.d/hefesto-dualsense-storm.conf`) que torna essa sondagem tolerante e espaçada, **preservando o microfone e o fone do controle**:

```bash
scripts/install_snd_quirk.sh --status   # a cura está ativa?
scripts/install_snd_quirk.sh            # (re)instala   ·   --remove reverte
```

O cartão **Anti-storm / Sistema** (aba Daemon) mostra o estado da cura e se o áudio do controle está sadio.

**2. A vibração não funciona nos jogos.** No modo "Jogar pelo Hefesto", use a máscara **Xbox 360** (aba Início, ou por perfil). Com a máscara DualSense, o jogo fala com o controle _físico_ por outro caminho e ignora o controle virtual — a vibração nunca chega. Ver a nota de máscara mais abaixo.

**3. O jogo enxerga o controle duplicado.** O Hefesto já cuida disso **sozinho**: o instalador (`./install.sh`, sem flags) coloca o atalho `hefesto-launch` nas Opções de inicialização dos seus jogos Steam e migra ajustes antigos — sempre com a Steam **fechada**. Você não precisa colar nada.

Se um jogo novo ainda aparecer com o controle duplicado, abra a aba **Sistema** e clique em **"Aplicar aos jogos da Steam"** (com a Steam fechada). Como último recurso manual, o botão **"Copiar opções p/ jogos"** (aba **Sistema**) copia a linha certa — `hefesto-launch %command%` — para você colar em Steam → jogo → **Propriedades** → **Opções de inicialização**. O `hefesto-launch` decide na hora o que cada jogo precisa; com o Hefesto desligado ele some do caminho (pior caso: controle duplicado, nunca zero). Recomendado também: **Propriedades → Controlador → Desativar Steam Input**.

---

### Limitações por modo — o que o "Jogar pelo Hefesto" não entrega (e por quê)

No modo **Jogar pelo Hefesto** (gamepad virtual) o daemon fica _entre_ o jogo e o controle: o jogo enxerga um `/dev/input/js*` virtual, não o DualSense. É isso que habilita co-op local, máscara Xbox/PS e a tradução de input — mas o `uinput` do Linux só carrega **botões, eixos e vibração** (force-feedback). Tudo que depende do canal HID cru do DualSense **não trafega pelo controle virtual**:

| Recurso | Jogar pelo Hefesto | Jogar direto (Nativo) | Por quê |
|---|:---:|:---:|---|
| Botões / sticks / gatilhos (input) | **sim** | **sim** | núcleo — paridade total nos dois modos |
| **Rumble do jogo** | **sim** _(máscara Xbox)_ | **sim** | ver nota abaixo |
| Gatilhos adaptativos | não | **sim** | `uinput` não tem canal de resistência de gatilho |
| Lightbar RGB pelo jogo | não | **sim** | `uinput` não expõe LED/RGB (só a cor do perfil) |
| Giroscópio / acelerômetro (aim) | não | **sim** | motion fica no device físico, não no virtual |
| Touchpad como touchpad | não | **sim** | o virtual não tem `BTN_TOUCH`/multitoque |
| Bateria dentro do jogo | não _(a GUI mostra)_ | **sim** | `uinput` não tem `power_supply` (SDL vê "wired") |

**Regra prática:** para gatilhos adaptativos, gyro-aim ou lightbar controlada pelo jogo, use **Jogar direto (Nativo)**. Para co-op local (cada controle = 1 jogador) e compatibilidade máxima com jogos Windows/Proton, use **Jogar pelo Hefesto**.

**Máscara e rumble:** a vibração do jogo no modo "Jogar pelo Hefesto" exige a máscara **Xbox 360** (aba Início, ou por perfil no editor). Com a máscara DualSense (prompts PlayStation), o driver HIDAPI do jogo adota o controle _físico_ pelo `/dev/hidraw` e ignora o controle virtual — o rumble nunca chega ao pipeline do Hefesto. Para manter os prompts PS e ainda ter vibração, inicie o jogo com `SDL_JOYSTICK_HIDAPI=0 %command%` (Steam → Propriedades → Opções de inicialização).

**Botão Mute (microfone):** mutar o microfone é função do controle **P1** por construção — o `mic_btn` só é lido do controle primário (via HID cru; não tem keycode evdev estável) e o sistema tem um único microfone. No co-op, o botão Mute dos jogadores 2+ não muta o mic nem acende o LED de mic; o P1 cobre a função para a máquina toda.

---

### Instalação

#### Ubuntu / Debian / Pop!\_OS / Mint (.deb — recomendado)

Baixe o `.deb` correspondente ao Python do seu sistema na página de releases (`releases/latest`) e instale com `apt`:

```bash
# Pop!_OS 22.04 / Ubuntu 22.04 → arquivo *_py310.deb
# Pop!_OS 24.04 / Ubuntu 24.04 → arquivo *_py312.deb
sudo apt install ./hefesto-dualsense4unix_3.8.1_amd64_py3XX.deb
```

Depois habilite o daemon (opcional — pode rodar só via GUI):

```bash
systemctl --user enable --now hefesto-dualsense4unix.service
hefesto-dualsense4unix-gui
```

Dependências Python que não têm pacote Debian oficial:

```bash
pip install pydualsense python-uinput
```

> **Ubuntu 22.04 (Jammy) e 24.04 (Noble):** o `python3-pydantic` do apt nesses releases é **versão 1.x** (Jammy 1.8.2, Noble 1.10.14 — confirmado empiricamente em 2026-04-24). O Hefesto - Dualsense4Unix usa API pydantic v2 (`ConfigDict`). O `.deb` declara `python3-pydantic` sem constraint de versão, então o `apt install` funciona; porém o Hefesto - Dualsense4Unix imprime `ImportWarning` em runtime e falha ao tocar schemas. **Solução recomendada (2 comandos):**
>
> ```bash
> pip install --user 'pydantic>=2'
> sudo apt install ./hefesto-dualsense4unix_*.deb
> ```
>
> O Python resolve `import pydantic` preferindo `~/.local/lib/python3.X/site-packages` (pydantic v2) antes de `/usr/lib/python3/dist-packages` (pydantic v1 do apt). Zero conflito.
>
> **Alternativas:**
>
> - Migrar para **Ubuntu 25.04 (Plucky)** ou superior — `python3-pydantic 2.10+` nativo.
> - Usar **AppImage** ou **Flatpak** (seções abaixo) — ambos trazem pydantic v2 empacotado.

#### AppImage (universal)

Baixe o `Hefesto-Dualsense4Unix-3.8.1-x86_64.AppImage` na página de releases e rode:

```bash
chmod +x Hefesto-Dualsense4Unix-3.8.1-x86_64.AppImage
./Hefesto-Dualsense4Unix-3.8.1-x86_64.AppImage
```

#### Flatpak (COSMIC, Flathub-compatível)

```bash
# Pré-requisito: runtime GNOME 47 + Flathub
flatpak remote-add --if-not-exists --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install -y --user flathub org.gnome.Platform//47

# Instala o bundle e roda
flatpak install --user hefesto-dualsense4unix-3.3.0.flatpak
flatpak run br.andrefarias.Hefesto

# Regras udev no host (uma vez só, fora do sandbox)
flatpak run --command=install-host-udev.sh br.andrefarias.Hefesto
```

> **Nota sobre sandbox**: o manifest Flatpak usa `--device=all` (necessário para
> `/dev/hidraw*` do DualSense + `/dev/uinput` da emulação Xbox) e
> `--talk-name=org.freedesktop.portal.*` (notificações D-Bus + tray + portal Wayland).
> O socket IPC do daemon vive em `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/`
> (mapeado via `--filesystem=xdg-run/hefesto-dualsense4unix:create`), então a CLI
> nativa (`.deb` ou source install) e a GUI Flatpak conversam pelo mesmo socket
> automaticamente. Perfis customizados ficam em
> `~/.var/app/br.andrefarias.Hefesto/config/hefesto-dualsense4unix/profiles/`.

> **Caveat COSMIC**: o cosmic-comp 1.0.x ainda não implementa o protocolo
> `org.kde.StatusNotifierWatcher` que os tray icons Ayatana usam. Habilite o
> applet **"Área de status"** no cosmic-panel (Configurações > Painel >
> Applets) para ter o ícone de bandeja, ou use a janela principal — fechá-la
> encerra o app quando não há bandeja. Opcionalmente, uma **janela compacta**
> 320×90 (bateria + perfil + botões) pode ser ativada com
> `HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW=1` (opt-in; default desligado).
> A GUI roda sob XWayland no COSMIC para os popups de dropdown funcionarem.

#### Via fonte (desenvolvimento)

```bash
git clone git@github.com:AndreBFarias/hefesto.git
cd hefesto
./scripts/dev-setup.sh                  # idempotente: garante .venv viva + pytest --collect-only + valida PyGObject
./scripts/dev_bootstrap.sh              # apt + venv + pip install -e (primeira vez)
./scripts/dev_bootstrap.sh --with-tray  # inclui PyGObject + libs GTK (obrigatório pra GUI e para tests/unit/test_status_actions_reconnect.py)
./scripts/install_udev.sh               # regras udev + módulo uinput (pede sudo)
```

Use `scripts/dev-setup.sh` no início de cada sessão: se `.venv/` falta ou está quebrada, invoca o bootstrap automaticamente; caso contrário valida rápido com `pytest --collect-only` e avisa se PyGObject está ausente (A-12).

**Para rodar a GUI localmente (`./run.sh --gui`):** o `PyGObject` precisa estar no `.venv`. Rode `./scripts/dev_bootstrap.sh --with-tray` pelo menos uma vez — sem a flag `--with-tray`, o bootstrap não instala o pacote (evita falha pesada em máquinas sem `libgirepository-1.0-dev`). O `dev-setup.sh` detecta ausência e imprime instrução acionável. Armadilha A-12 documentada em `VALIDATOR_BRIEF.md`.

> **GNOME 42+:** o `install.sh` detecta a extension `ubuntu-appindicators@ubuntu.com`
> e oferece habilitação automática (sem ela o ícone de bandeja não aparece). Em outras
> DEs (KDE, COSMIC, XFCE, Cinnamon, MATE) o tray Ayatana funciona nativamente.

#### Re-aplicar regras udev (3 caminhos idempotentes)

As regras udev são instaladas automaticamente pelo `install.sh` (source),
pelo `.deb` (apt install) e pelo bundle Flatpak. Para **re-aplicar
manualmente** (depois de troca de kernel, perda de permissão, ou simples
sanidade), escolha o caminho conforme o formato instalado:

```bash
# Source / dev (repositório clonado)
sudo bash scripts/install_udev.sh

# .deb instalado (helper bundled em /usr/share/)
sudo bash /usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh

# Flatpak instalado (helper exposto via flatpak run)
flatpak run --command=install-host-udev.sh br.andrefarias.Hefesto
```

Todos os 3 aplicam o mesmo conjunto canônico de **5 regras + uinput
modules-load** (sincronizados via `assets/`), recarregam o udev e
disparam triggers específicos para o vendor `054c` (Sony). Idempotentes
— pode rodar quantas vezes quiser sem efeito colateral. Após rodar,
desconecte e reconecte o controle (USB) ou re-pareie (BT).

Reconecte o DualSense depois de instalar as regras udev. Confira o acesso:

```bash
ls -l /dev/hidraw* /dev/uinput          # ACL via uaccess deve estar ativa (+)
```

---

### Requisitos

**Obrigatórios:**

- Linux com `systemd-logind` ativo (Pop!\_OS, Ubuntu, Fedora, Arch, Debian, Mint).
- Python 3.10+.
- Pacotes do sistema: `libhidapi-hidraw0`, `libhidapi-dev`, `libudev-dev`, `libxi-dev`.

**Recomendados:**

- GTK 3.0 + PyGObject (para GUI).
- Textual (para TUI).
- `AppIndicator and KStatusNotifierItem Support` no GNOME 42+ (para ícone de bandeja).

**Opcionais:**

- `python-uinput` (emulação Xbox 360).
- Endpoint Prometheus em `127.0.0.1:9090` (opt-in via `hefesto-dualsense4unix.conf`).

**Fora de escopo:**

- Distros sem `logind` (Alpine OpenRC, Void runit, Gentoo/Artix com OpenRC). Ver `docs/adr/009-systemd-logind-scope.md`.
- Windows, macOS. Bluetooth Audio do DualSense (protocolo fechado).

---

### Uso

**Via menu de aplicativos:** procure por "Hefesto - Dualsense4Unix" (ícone na bandeja do sistema).

**Via terminal (GUI):**

```bash
hefesto-dualsense4unix-gui
```

**Via CLI (headless, sem display):**

```bash
. .venv/bin/activate

hefesto-dualsense4unix daemon start --foreground           # sobe daemon em primeiro plano
hefesto-dualsense4unix status                              # estado do daemon e controle
hefesto-dualsense4unix battery                             # percentual colorido
hefesto-dualsense4unix profile list                        # perfis em ~/.config/hefesto-dualsense4unix/profiles/
hefesto-dualsense4unix profile show shooter                # JSON do perfil
hefesto-dualsense4unix profile activate shooter            # aplica direto no hardware
hefesto-dualsense4unix test trigger --side right \
    --mode Galloping --params 0,9,7,7,10    # testa efeito sem daemon
hefesto-dualsense4unix led --color "#FF0080"               # lightbar
hefesto-dualsense4unix tui                                 # interface Textual
```

**Service systemd `--user`:**

```bash
hefesto-dualsense4unix daemon install-service              # modo gráfico (default)
hefesto-dualsense4unix daemon install-service --headless   # modo headless (SSH/Big Picture remoto)
systemctl --user enable --now hefesto-dualsense4unix.service
journalctl --user -u hefesto-dualsense4unix -f
```

**Emulação Xbox 360:**

```bash
hefesto-dualsense4unix emulate xbox360 --on                # cria /dev/input/js*, forward 60 Hz
```

Steam e a maior parte dos jogos Proton reconhecem automaticamente o novo gamepad.

Guia visual com capturas cobrindo instalação, GUI, presets e solução de problemas: **[docs/usage/quickstart.md](docs/usage/quickstart.md)**.

---

### Conexão via Bluetooth

O Hefesto detecta o DualSense igual em USB e em Bluetooth — o backend é transport-agnóstico (ver `src/hefesto_dualsense4unix/core/backend_pydualsense.py`). Lightbar, gatilhos adaptativos, rumble, mic LED e LEDs de jogador funcionam em ambos os transportes; a única diferença é o pareamento inicial, que ainda é manual via `bluetoothctl` (não há UI dedicada na GUI).

Passo a passo (Pop!_OS / Ubuntu / Fedora):

```bash
bluetoothctl
# dentro do prompt interativo do bluetoothctl:
power on
agent on
default-agent
scan on
# no controle: segurar PS + Create por ~3 s até a barra de luz piscar rápido
# aguardar entrada "Wireless Controller" aparecer com o MAC
pair  AA:BB:CC:DD:EE:FF      # substituir pelo MAC mostrado no scan
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
exit
```

Após pareado, o daemon detecta automaticamente em ≤ 5 s; a GUI é trazida ao foco pela regra udev `74-ps5-controller-hotplug-bt.rules` (instalada por `./scripts/install_udev.sh`). Confirmar transporte ativo:

```bash
hefesto-dualsense4unix status
# esperado:
#   connected   = True
#   transport   = bt
#   battery_pct = <num>
```

Notas:

- Para reconectar nas próximas sessões basta ligar o controle (botão PS curto). O `bluetoothd` reaproveita o `trust` salvo.
- Se aparecer latência intermitente em adaptadores BT antigos (CSR / firmware desatualizado), é esperado — fora do escopo do projeto. Documentar como troubleshoot na issue própria.
- Áudio do DualSense via BT permanece fora de escopo (protocolo proprietário, ver "Fora de escopo" abaixo).

---

### Combo sagrado (trocar perfil durante o jogo)

| Tecla | Ação |
|-------|------|
| PS + D-pad Cima | Próximo perfil |
| PS + D-pad Baixo | Perfil anterior |
| PS (toque curto) | Steam Big Picture (ou comando custom via `hefesto-dualsense4unix.conf`) |
| **PS (segurar ~1s)** | **Modo jogo on/off** — alterna a supressão da emulação de mouse/teclado virtual mantendo os hotkeys ativos; notifica via D-Bus (v3.8.1, FEAT-EMULATION-GAMEMODE-LONGPRESS-01) |
| Mic (botão físico) | Muta / desmuta microfone padrão do sistema |

---

### Modos de gatilho disponíveis

| Modo | Descrição |
|------|-----------|
| **Off** | Gatilho sem resistência |
| **Rigid** | Resistência contínua ajustável |
| **Pulse** | Pulsos curtos com frequência configurável |
| **Galloping** | Padrão de galope (2 pulsos espaçados) |
| **Machine** | Rajada com frequência e força variáveis |
| **Bow** | Tensão crescente simulando arco |
| **Automatic Gun** | Rajada automática contínua |
| **Feedback** | 6 presets de resistência (Leve, Médio, Forte, Progressivo, Duro, Firme) |
| **Vibration** | 5 presets de vibração (Curto, Médio, Longo, Rajada, Pulso) |

Factories canônicas em `src/hefesto_dualsense4unix/profiles/trigger_modes.py`.

---

### Matriz de compatibilidade

Validações empíricas reais (mantenedor + CI matrix). Não inflamos
expectativa: o que não foi rodado em hardware está marcado como
"comunidade" e aceita relato via issue.

| Distro                  | DE / sessão       | USB | BT | Tray | Auto-switch | Notas                                                      |
|-------------------------|-------------------|-----|----|------|-------------|------------------------------------------------------------|
| Pop!\_OS 22.04          | GNOME 42 X11      | OK  | OK | OK   | OK          | Runtime primário do mantenedor                             |
| Pop!\_OS 24.04          | COSMIC alpha      | OK  | OK | janela compacta\* | OK (portal + wlrctl) | Validado 2026-05-15; tray nativo aguarda v3.4 |
| Ubuntu 24.04            | GNOME 46 Wayland  | OK  | OK | OK (com extension) | OK         | Cobertura CI matrix                                        |
| Ubuntu 22.04            | GNOME 42 X11      | OK  | OK | OK (com extension) | OK         | Cobertura CI matrix                                        |
| Fedora 40+              | GNOME 46 Wayland  | comunidade | comunidade | esperado OK | esperado OK | wlrctl no apt/dnf; relatos bem-vindos                    |
| Arch / EndeavourOS      | KDE Plasma 6      | comunidade | comunidade | esperado OK | esperado OK | applet SNI nativo do Plasma; relatos bem-vindos          |
| Debian 12 stable        | GNOME 43 X11      | comunidade | comunidade | esperado OK | esperado OK | python3-pydantic 1.x: `pip install --user pydantic>=2`   |
| Alpine / Void / Artix   | qualquer          | —   | —  | —    | —           | Fora de escopo (sem systemd-logind — ver ADR-009)         |

`*` Pop!_OS COSMIC: o cosmic-comp 1.0.x ainda não implementa
`org.kde.StatusNotifierWatcher`, então o tray clássico fica oculto. Habilite o
applet "Área de status" no cosmic-panel para o ícone de bandeja, ou use a
janela principal (fechá-la encerra o app quando não há bandeja). Uma **janela
compacta** 320×90 opcional pode ser ativada via
`HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW=1` (opt-in; default desligado).

Para reportar resultado em distro não listada: rode
[`CHECKLIST_VALIDACAO_v3.2.0.md`](CHECKLIST_VALIDACAO_v3.2.0.md) e abra
issue com a label `validation-report`.

---

### Pop!_OS COSMIC (Wayland)

A partir de v3.1.0 o projeto tem suporte explícito a **Pop!_OS 24.04 COSMIC** (cosmic-comp 1.0+). Estado real validado em hardware do mantenedor (2026-05-15):

**O que funciona:**
- Daemon completo: detecção USB do DualSense, lightbar, rumble, gatilhos adaptativos, hotkeys de hardware (combo PS+D-pad), bateria, perfis, IPC, UDP DSX, emulação Xbox 360.
- GUI GTK3 renderiza nativamente em Wayland (GDK Wayland backend).
- Autoswitch de perfil para janelas **XWayland** (Steam, Proton, browsers em modo X11): funciona via `XlibBackend`. Pop!_OS 24.04 vem com XWayland ativo por padrão.
- systemd `--user` service: `WantedBy=default.target` ativa resiliente em cosmic-session.
- Notificações D-Bus padrão freedesktop (cosmic-notifications): funcionam OOTB.

**Limitações conhecidas (2026-05):**
- Autoswitch para **apps Wayland nativos** (Firefox-Wayland, apps GNOME, etc.):
  - `xdg-desktop-portal-cosmic` ainda não implementa `org.freedesktop.portal.Window::GetActiveWindow`.
  - `cosmic-comp 1.0.0` ainda não expõe `wlr-foreign-toplevel-management` (testado com `wlrctl 0.2.2`).
  - **Workaround:** trocar perfil manualmente via tray/CLI/combo PS+D-pad.
- Tray icon (`cosmic-applet-status-area`): instalado em `cosmic-applets 1.0.12` mas **não vem habilitado por padrão no painel**. Hefesto detecta a ausência via D-Bus probe e emite notificação orientadora uma vez por execução. Para habilitar: **Configurações > Painel > Applets > Adicionar "Área de status"**.

**Comandos recomendados em COSMIC:**

```bash
# Instalação fonte com auto-detecção COSMIC + wlrctl + GDK_BACKEND=x11
./install.sh --yes --force-xwayland

# Confirmar backend selecionado
.venv/bin/python -c "
from hefesto_dualsense4unix.integrations.window_detect import detect_window_backend
print(type(detect_window_backend()).__name__)
"
# Em XWayland (default): XlibBackend
# Em Wayland puro (raro): _WaylandCascadeBackend

# Probe do StatusNotifierWatcher (tray)
.venv/bin/python -c "
from hefesto_dualsense4unix.integrations.desktop_notifications import statusnotifierwatcher_available
print('tray disponivel:', statusnotifierwatcher_available())
"
```

Detalhes empíricos em `docs/process/discoveries/2026-05-15-cosmic-1.0-validation.md`. Decisão arquitetural em `docs/adr/014-cosmic-wayland-support.md`.

---

### Solução de problemas

**Primeiro recurso — diagnóstico automático:**

- `hefesto-dualsense4unix doctor` roda um health-check ponta-a-ponta (daemon, regras udev, uinput,
  applet COSMIC, microfone/WirePlumber, controle) e aponta o que está errado. `doctor --fix` aplica
  as correções seguras (reaplica udev, reseta o WirePlumber). O daemon também avisa proativamente no
  boot se detectar udev/WirePlumber fora do lugar.

**Desativar sem desinstalar:**

- `hefesto-dualsense4unix daemon pause` faz o daemon parar de enviar input ao sistema mantendo-o
  vivo (retoma com `daemon resume`). `daemon disable` desliga e tira do auto-start (religa com
  `daemon enable`). Para remover de vez, use `scripts/purge.sh`.

**Modo jogo (segurar PS ~1s):**

- Em jogo, o stick do controle "anda sozinho" se a emulação de mouse virtual estiver ligada.
  Segure o botão **PS por ~1 segundo** para alternar o "modo jogo": a emulação de mouse/teclado é
  suprimida (os hotkeys de troca de perfil seguem ativos), e uma notificação D-Bus confirma o
  estado. Segure de novo para reativar. Toque curto no PS continua abrindo a Steam. (v3.8.1)

**Sticks ficam encostados em ~253 em repouso (drift falso):**

- Sintoma de `controller_connected_without_evdev` no log: o kernel `hid_playstation` capturou o
  `evdev` e o daemon caiu no fallback HID-raw cru. Corrigido em v3.8.1 — o `EvdevReader` agora
  re-procura o `/dev/input/event*` a cada conexão. Se você está numa versão anterior, basta
  reiniciar o daemon **com o controle já plugado**: `systemctl --user restart hefesto-dualsense4unix`.

**GUI consumindo CPU/RAM absurdos (~100% CPU, gigabytes de RAM):**

- Bug pré-existente até v3.8.0 — `install_status_polling` registrava `GLib.idle_add` com
  callbacks que retornavam `True` (corretos para `timeout_add`, mas viravam busy-loop infinito
  no `idle_add`). Corrigido em **v3.8.1** (BUG-GUI-IDLE-ADD-BUSY-LOOP-01); GUI agora roda em
  ~2.4% CPU / ~90 MB. Se reincidir, capture a stack com `sudo py-spy dump --pid <PID_GUI>` e abra
  issue.

**Controle não aparece em `/dev/hidraw*`:**

1. Verifique as regras udev: `ls /etc/udev/rules.d/7*-ps5-controller*.rules`.
2. Recarregue: `sudo udevadm control --reload-rules && sudo udevadm trigger`.
3. Desconecte e reconecte o controle.

**Daemon diz "offline" mesmo com controle plugado:**

- USB autosuspend pode estar derrubando o device. A regra `72-ps5-controller-autosuspend.rules` força `power/control=on` e `power/autosuspend_delay_ms=-1` para os VID/PID `054c:0ce6` e `054c:0df2`. Instalada automaticamente por `scripts/install_udev.sh` e pelo `.deb`.
- Verifique logs: `journalctl --user -u hefesto-dualsense4unix -f`.

**Emulação Xbox 360 não cria `/dev/input/js*`:**

- Carregue o módulo: `sudo modprobe uinput`.
- Confira a regra `71-uinput.rules` e permissão do `/dev/uinput` (precisa ACL via `uaccess`).

**Cursor "voando" ao ativar Mouse:**

- Sintoma de múltiplas instâncias de daemon rodando em paralelo. Desde v2.0.0 existe `single_instance` com `flock` — se o bug aparecer, rode `pkill -TERM -f hefesto_dualsense4unix.app.main && pkill -TERM -f 'hefesto-dualsense4unix daemon'` e reinicie via `systemctl --user restart hefesto-dualsense4unix.service`. Reporte em issue.

**Tray icon invisível no GNOME:**

- A partir do GNOME 42 (Pop!_OS 22.04, Ubuntu 22.04), a extension `ubuntu-appindicators@ubuntu.com` precisa estar habilitada para renderizar tray icons. O `install.sh --yes` (no formato nativo) detecta e habilita automaticamente. Após habilitar, faça **logout/login** do GNOME para o Shell carregar.
- Manualmente: `gnome-extensions enable ubuntu-appindicators@ubuntu.com`.

**Sair do tray não encerra o daemon:**

- A partir da v3.0.0, "Sair" mata via PID file também (não só via `systemctl stop`). Se você ainda observar daemon residual, anote o PID e abra issue com `journalctl --user -u hefesto-dualsense4unix -n 50`.

Mais detalhes em [`docs/usage/quickstart.md`](docs/usage/quickstart.md) e [`docs/usage/troubleshooting.md`](docs/usage/troubleshooting.md) (quando existir).

---

### Estrutura do projeto

```
Hefesto-DualSense_Unix/
  src/hefesto_dualsense4unix/
    app/            # GUI GTK3 + apptray + handlers
    cli/            # entry point typer
    daemon/         # 10 subsystems (poll, ipc, udp, autoswitch, mouse, rumble, hotkey, metrics, plugins, connection)
    gui/            # main.glade + theme.css + widgets customizados
    profiles/       # schemas pydantic + gerência + matchers
    tui/            # interface Textual
    testing/        # FakeController para smoke sem hardware
    utils/          # xdg_paths, single_instance, logging_config
  assets/
    appimage/       # ícones e manifesto AppImage
    glyphs/         # SVGs originais dos botões do DualSense
    profiles_default/  # 7 perfis default
    *.rules         # udev (70..74)
    hefesto-dualsense4unix.service, hefesto-dualsense4unix-gui-hotplug.service
  scripts/
    dev-setup.sh, dev_bootstrap.sh, install_udev.sh
    validar-acentuacao.py, check_anonymity.sh, check_version_consistency.py
  tests/unit/       # 1856 testes pytest
  docs/
    adr/            # 9 Architecture Decision Records
    protocol/       # UDP schema, IPC JSON-RPC, trigger modes
    usage/          # quickstart visual + assets
    process/        # decisões V2/V3, roadmap, discoveries
  run.sh, run_luna.sh
  install.sh, uninstall.sh
  pyproject.toml, CHANGELOG.md, AGENTS.md
```

---

### Documentação

- **Guia visual rápido:** [`docs/usage/quickstart.md`](docs/usage/quickstart.md)
- **Solução de problemas (troubleshooting):** [`docs/usage/troubleshooting.md`](docs/usage/troubleshooting.md)
- **8BitDo SN30 Pro (modos e morte por Bluetooth):** [`docs/usage/troubleshooting-8bitdo.md`](docs/usage/troubleshooting-8bitdo.md)
- **Roadmap público:** [`docs/process/ROADMAP.md`](docs/process/ROADMAP.md) — v3.3.0 / v3.4 / v4.0
- **Protocolo de colaboração:** [`AGENTS.md`](AGENTS.md) (anonimato, idioma PT-BR, workflow de issue)
- **Decisões arquiteturais:** [`docs/adr/`](docs/adr/) — 17 ADRs numeradas (ADR-014 cobre COSMIC/Wayland)
- **Schemas de protocolo:** [`docs/protocol/`](docs/protocol/) — UDP, IPC JSON-RPC, modos de gatilho
- **Decisões de processo:** [`docs/process/HEFESTO_DECISIONS_V2.md`](docs/process/HEFESTO_DECISIONS_V2.md), [`HEFESTO_DECISIONS_V3.md`](docs/process/HEFESTO_DECISIONS_V3.md)
- **Diário de descobertas:** [`docs/process/discoveries/`](docs/process/discoveries/) — uma jornada por arquivo
- **Changelog:** [`CHANGELOG.md`](CHANGELOG.md)
- **Ordem de sprints internas:** [`docs/process/SPRINT_ORDER.md`](docs/process/SPRINT_ORDER.md)

---

### Contribuindo

Leia [`AGENTS.md`](AGENTS.md) antes de abrir PR. Resumo:

1. Pegue issue com labels `status:ready` + `ai-task`.
2. `gh issue develop N --checkout`.
3. Ative o gate local de qualidade na primeira clonagem:
   ```bash
   pip install pre-commit
   pre-commit install
   ```
   O framework instala hooks que bloqueiam commit com acentuação PT-BR faltando (`acao`, `funcao`, `descricao`, etc.), menção a IA ou falha de `ruff check`. Script canônico: [`scripts/validar-acentuacao.py`](scripts/validar-acentuacao.py).
4. Implementar + testes (pytest), `ruff`, `mypy` strict — gate rígido no CI desde V2.2: `mypy src/hefesto_dualsense4unix` tem que fechar com zero erros; [`scripts/check_anonymity.sh`](scripts/check_anonymity.sh).
5. Se toca runtime, provar via smoke real (`run.sh --smoke`) ou com hardware conectado.
6. Se toca UI / TUI, screenshot + sha256 + descrição multimodal no PR.
7. Descoberta não-óbvia vira registro em [`docs/process/discoveries/`](docs/process/discoveries/).
8. Commit em PT-BR, sem menção a IA, zero emojis gráficos (glyphs Unicode de estado — ``, ``, box drawing — são permitidos).
9. Abrir PR com `Closes #N`, squash merge.

Testes manuais com hardware físico têm checklist em [`CHECKLIST_MANUAL.md`](CHECKLIST_MANUAL.md). Revisor com controle marca antes de cada release.

---

### Licença

MIT — veja [`LICENSE`](LICENSE) para detalhes.

---

*"A forja não revela o ferreiro. Só a espada."*
