# Hefesto

> Daemon Linux para gatilhos adaptativos do controle DualSense. Porte espiritual do DualSenseX para Unix em Python.

```
Versão:  2.0.0
Estado:  runtime validado em Pop!_OS 22.04 com DualSense USB/BT; 917 testes unit
Alvo:    Linux com systemd-logind, Python 3.10+
Licença: MIT
```

Roadmap em andamento: ver `docs/process/SPRINT_ORDER.md`.

## Começar em 2 minutos

Se você só quer plugar o DualSense e fazer funcionar, pule direto para
**`docs/usage/quickstart.md`** — guia visual com screenshots cobrindo
instalação, GUI, presets de trigger, política de rumble e solução de
problemas comuns. O resto deste README é referência técnica.

---

## O que faz

### Núcleo (desde 1.0)
- Comunicação híbrida: `evdev` para input (contorna `hid_playstation`), `pydualsense` para output HID.
- 19 modos de gatilho adaptativo com factories validadas (`Rigid`, `Pulse`, `Galloping`, `Machine`, `Bow`, etc.).
- UDP em `127.0.0.1:6969` compatível com mods DSX (Cyberpunk, Forza, Assetto Corsa).
- IPC via Unix socket (NDJSON JSON-RPC 2.0) em `$XDG_RUNTIME_DIR/hefesto.sock`, permissão `0600`.
- Emulação Xbox 360 via `uinput` para jogos que não reconhecem DualSense.
- Perfis JSON validados com pydantic v2 em `~/.config/hefesto/profiles/`.
- Auto-switch de perfil por janela ativa (X11 nativo, Wayland via portal XDG).
- Hotkeys via combo sagrado (PS+D-pad) sem exigir grupo `input`.
- Systemd `--user` service; TUI Textual com preview ao vivo.

### UX + GUI (1.1)
- GUI GTK3 com tema Drácula: bordas roxas, cards `.hefesto-card`, 19 SVGs originais dos botões do DualSense.
- Aba Status redesenhada: sticks L3/R3 lado-a-lado + grid 4×4 de glyphs acendendo em roxo quando pressionados.
- Rodapé global: Aplicar (envia config inteira), Salvar Perfil, Importar JSON, Restaurar Default — operando sobre `DraftConfig` central.
- Editor de perfil dual: modo simples (radios Steam/Navegador/Terminal/Editor/Jogo específico) ou avançado (window_class/title_regex/process_name).
- 7 perfis pré-configurados (navegacao/fps/aventura/acao/corrida/esportes/meu_perfil) com identidade cromática e mecânica própria.
- Presets de trigger por posição: 6 Feedback + 5 Vibração + Custom.
- Política global de rumble: Economia (0.3×), Balanceado (0.7×), Máximo (1.0×), Auto (dinâmico por bateria com debounce 5s).
- Single-instance: daemon "última vence" (SIGTERM→SIGKILL), GUI "primeira vence" (traz ao foco). Resolve cursor voando + PIDs renascendo.

### Plataforma (1.2)
- `.deb` nativo para Debian/Ubuntu/Pop!_OS/Mint (179KB, `dpkg-deb` direto).
- Bundle Flatpak `br.andrefarias.Hefesto` para COSMIC e Flathub-compatível.
- Hotplug BT: GUI abre automaticamente ao parear via Bluetooth (regra udev 74).
- Wayland via portal XDG (`org.freedesktop.portal.Window.GetActiveWindow`) — autoswitch funciona no COSMIC.
- Hot-reload do daemon via IPC `daemon.reload {config_overrides}` sem restart.

### Infra + extensibilidade (2.0)
- Botão Mic físico muta/desmuta o microfone padrão do sistema (wpctl/pactl) e sincroniza com o LED vermelho do controle.
- Daemon refatorado em 10 subsystems modulares (`poll`, `ipc`, `udp`, `autoswitch`, `mouse`, `rumble`, `hotkey`, `metrics`, `plugins`, `connection`) compartilhando `DaemonContext` único.
- Endpoint Prometheus opt-in em `127.0.0.1:9090/metrics` (8 métricas canônicas).
- Sistema de plugins Python: `~/.config/hefesto/plugins/*.py` com hooks `on_tick`/`on_button_down`/`on_battery_change`. Watchdog desativa plugin lento (>5ms/tick).

## O que não faz

- Suporte a Windows ou macOS.
- Bluetooth Audio do DualSense (protocolo fechado).
- HidHide (não é necessário — backend híbrido resolve sem `unbind` do driver).
- Sandbox forte de plugins (cgroups/bubblewrap) — plugins rodam com privilégios do daemon; usuário é responsável.

---

## Requisitos do sistema

- Linux com `systemd-logind` ativo (Pop!\_OS, Ubuntu, Fedora, Arch, Debian, Mint).
  Distros sem logind (Alpine OpenRC, Void runit, Gentoo/Artix com OpenRC) **não são suportadas oficialmente** — ver `docs/adr/009-systemd-logind-scope.md`.
- Pacotes do SO: `libhidapi-hidraw0` (runtime), `libhidapi-dev`, `libudev-dev`, `libxi-dev`.
- Python 3.10+.
- Tray (opcional): extensão `AppIndicator and KStatusNotifierItem Support` no GNOME 42+.

---

## Instalação via .deb (Ubuntu / Pop!\_OS / Debian)

Baixe o pacote da pagina de releases e instale com apt:

```bash
curl -LO https://github.com/AndreBFarias/hefesto/releases/download/v2.0.0/hefesto_2.0.0_amd64.deb
sudo apt install ./hefesto_2.0.0_amd64.deb
```

Depois habilite o daemon (opcional — pode usar so a GUI):

```bash
systemctl --user enable --now hefesto.service
hefesto-gui
```

Dependencias Python sem pacote Debian oficial (instale se precisar):

```bash
pip install pydualsense python-uinput
```

---

## Instalação (dev)

```bash
git clone git@github.com:AndreBFarias/hefesto.git
cd hefesto
./scripts/dev_bootstrap.sh              # apt + venv + pip install -e
./scripts/dev_bootstrap.sh --with-tray  # inclui PyGObject + libs GTK
./scripts/install_udev.sh               # udev rules + modprobe uinput (pede sudo)
```

Reconectar o DualSense depois de instalar as udev rules. Conferir acesso:

```bash
ls -l /dev/hidraw* /dev/uinput          # ACL via uaccess deve estar ativa (+)
```

---

## Primeiro uso

### Ativação direta pelo CLI

```bash
. .venv/bin/activate

hefesto daemon start --foreground           # sobe daemon em primeiro plano
hefesto status                              # estado do daemon e controle
hefesto battery                             # percentual colorido
hefesto profile list                        # perfis em ~/.config/hefesto/profiles/
hefesto profile show shooter                # JSON do perfil
hefesto profile activate shooter            # aplica direto no hardware
hefesto test trigger --side right \
    --mode Galloping --params 0,9,7,7,10    # testa efeito sem daemon
hefesto led --color "#FF0080"               # lightbar
hefesto tui                                 # interface Textual
```

### Service systemd --user

```bash
hefesto daemon install-service              # modo gráfico (default)
hefesto daemon install-service --headless   # modo headless (SSH/Big Picture remoto)
systemctl --user enable --now hefesto.service
journalctl --user -u hefesto -f
```

### Emulação Xbox 360 (para jogos que não reconhecem DualSense)

```bash
hefesto emulate xbox360 --on                # cria /dev/input/js*, forward 60Hz
```

Steam e a maior parte dos jogos Proton veem automaticamente o novo gamepad.

---

## Matriz de compatibilidade

| Distro          | Kernel        | Systemd | USB | BT  | Tray | Notas                                  |
|-----------------|---------------|---------|-----|-----|------|----------------------------------------|
| Pop!\_OS 22.04  | 6.17          | 249+    | OK  | ?   | ?    | Runtime primário; backend híbrido ativo |
| Ubuntu 22.04+   | 5.19+         | 249+    | ?   | ?   | ?    | Mesmo ecossistema do Pop!\_OS           |
| Fedora 39+      | 6.5+          | 254+    | ?   | ?   | ?    | Esperado funcionar                     |
| Arch (rolling)  | rolling       | atual   | ?   | ?   | ?    | Comunidade                             |
| Debian 12 stable| 6.1           | 252     | ?   | ?   | ?    | Esperado funcionar                     |
| Alpine / Void   | qualquer      | —       | —   | —   | —    | Fora de escopo (sem logind)            |

`?` = não validado. Contribuições bem-vindas em `CHECKLIST_MANUAL.md` ou via issues `needs-device`.

---

## Testes manuais com hardware

Sprints que exigem DualSense físico têm checklist em `CHECKLIST_MANUAL.md`. Revisor com hardware marca antes de cada release.

---

## Documentação

- `AGENTS.md` — protocolo de colaboração (anonimato, idioma, workflow de issue, validação runtime).
- `docs/adr/` — 9 Architecture Decision Records numeradas.
- `docs/protocol/` — UDP schema, IPC JSON-RPC, trigger modes canônicos.
- `docs/usage/` — guias do usuário (quickstart, criação de perfis, integração com mods).
- `docs/process/` — decisões V2/V3, roadmap, dúvidas.
- `docs/process/discoveries/` — diário de descobertas (uma jornada por arquivo).
- `CHANGELOG.md` — histórico de versões.

---

## Contribuindo

Leia `AGENTS.md` antes de abrir PR. Resumo:

1. Pegue issue `status:ready` + `ai-task`.
2. `gh issue develop N --checkout`.
3. Implementar + testes (pytest), ruff, mypy strict, `scripts/check_anonymity.sh`.
4. Se toca runtime, provar via smoke real (`run.sh --smoke` ou hardware).
5. Se toca UI/TUI, screenshot + sha256 + descrição multimodal no PR.
6. Descoberta não-óbvia vira registro em `docs/process/discoveries/`.
7. Commit em PT-BR, sem menção a IA, zero emojis.
8. Abrir PR com `Closes #N`, squash merge.

---

*"A forja não revela o ferreiro. Só a espada."*
