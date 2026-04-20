# Hefesto

> Daemon Linux para gatilhos adaptativos do controle DualSense. Porte espiritual do DualSenseX para Unix em Python.

```
Versão: 0.1.0 (alpha)
Status: scaffold
Alvo: Linux com systemd-logind, Python 3.10+
```

---

## O que faz

- Comunicação HID direta com DualSense e DualSense Edge (USB e Bluetooth).
- 19 modos de gatilho adaptativo mapeados (Rigid, Pulse, Galloping, Machine, etc.).
- Protocolo UDP em `127.0.0.1:6969` compatível com mods existentes para DSX.
- IPC via Unix socket (JSON-RPC 2.0) para TUI e CLI.
- Emulação Xbox360 via `uinput` para jogos que não reconhecem DualSense.
- Auto-switch de perfil por janela ativa X11.
- Perfis JSON versionados em `~/.config/hefesto/profiles/`.
- systemd `--user` service (unidades normal e headless).

## O que não faz

- Suporte a Windows ou macOS.
- Wayland nativo na v0.x (fallback para perfil padrão; ADR-007).
- Bluetooth Audio do DualSense (protocolo fechado).

---

## Requisitos do sistema

- Linux com `systemd-logind` ativo (Pop!\_OS, Ubuntu, Fedora, Arch, Debian, etc.). Distros sem logind (Alpine, Void, Gentoo/OpenRC) não são suportadas oficialmente — ver ADR-009.
- `libhidapi-hidraw0` (runtime) e `libhidapi-dev` (build).
- `libudev-dev`, `libxi-dev`.
- Python 3.10+.
- Tray opcional: extensão `AppIndicator and KStatusNotifierItem Support` no GNOME 42+.

---

## Instalação (dev)

```bash
./scripts/dev_bootstrap.sh              # instala deps e cria venv
./scripts/dev_bootstrap.sh --with-tray  # inclui PyGObject + libs GTK
./scripts/install_udev.sh               # udev rules + modules-load.d (pede sudo)
```

Reconectar o DualSense depois de instalar as udev rules. Conferir acesso:

```bash
ls -l /dev/hidraw*
```

---

## Primeiro uso

```bash
hefesto daemon start --foreground      # roda em primeiro plano
hefesto status                         # status do daemon e controle
hefesto profile list                   # perfis disponíveis
hefesto test trigger --side right --mode Galloping --params 0,9,7,7,10
```

Instalar como serviço do usuário:

```bash
hefesto daemon install-service              # modo gráfico (default)
hefesto daemon install-service --headless   # modo headless (SSH/Big Picture remoto)
systemctl --user enable --now hefesto.service
```

---

## Testes manuais com hardware

Sprints que exigem DualSense físico têm checklist em `CHECKLIST_MANUAL.md`. Revisor com hardware marca antes de cada release.

---

## Contribuindo

Ver `AGENTS.md` para protocolo de colaboração (anonimato, idioma, workflow de issue, validação runtime).

---

*"A forja não revela o ferreiro. Só a espada."*
