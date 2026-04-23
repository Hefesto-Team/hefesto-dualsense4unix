# Hefesto

> Daemon Linux para gatilhos adaptativos do controle DualSense. Porte espiritual do DualSenseX para Unix em Python.

```
Versão:  1.2.0
Estado:  runtime validado em Pop!_OS 22.04 com DualSense USB/BT; v2.0 em preparação
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

- Comunicação híbrida: `evdev` para input (contorna `hid_playstation`), `pydualsense` para output HID.
- 19 modos de gatilho adaptativo com factories validadas (`Rigid`, `Pulse`, `Galloping`, `Machine`, `Bow`, etc.).
- UDP em `127.0.0.1:6969` compatível com mods DSX (Cyberpunk, Forza, Assetto Corsa).
- IPC via Unix socket (NDJSON JSON-RPC 2.0) em `$XDG_RUNTIME_DIR/hefesto.sock`, permissão `0600`.
- Emulação Xbox 360 via `uinput` para jogos que não reconhecem DualSense.
- Auto-switch de perfil por janela ativa X11 (debounce 500 ms).
- Hotkeys via combo sagrado (PS+D-pad) sem exigir grupo `input`.
- Perfis JSON validados com pydantic v2 em `~/.config/hefesto/profiles/`.
- Systemd `--user` service (unidade normal ou headless, `Conflicts=` mútuo).
- TUI Textual com preview de gatilhos, bateria e sticks.

## O que não faz

- Suporte a Windows ou macOS.
- Wayland nativo (fallback para perfil `MatchAny`; ver `docs/adr/007-wayland-deferral.md`).
- Bluetooth Audio do DualSense (protocolo fechado).
- HidHide (não é necessário — backend híbrido resolve sem `unbind` do driver).

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
curl -LO https://github.com/AndreBFarias/hefesto/releases/download/v1.1.0/hefesto_1.1.0_amd64.deb
sudo apt install ./hefesto_1.1.0_amd64.deb
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
