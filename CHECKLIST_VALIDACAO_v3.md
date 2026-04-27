# Checklist de validação — pós-rebrand v3.0.0 + 6 sprints (2026-04-27)

Itens que precisam **execução manual com hardware ou ambiente real do usuário**.
Marcar `[x]` quando passar; logar evidência quando falhar.

---

## Setup obrigatório antes da validação

- [ ] `git pull` está em `rebrand/dualsense4unix` no commit `d698159` (ou superior).
- [ ] `cd ~/Desenvolvimento/Hefesto-Dualsense4Unix && ./install.sh --yes` rodou sem erros.
- [ ] `gnome-extensions list --enabled | grep ubuntu-appindicator` retorna a extension.
- [ ] **Logout/login** no GNOME para a extension recém-habilitada renderizar tray icons.

---

## #22 — BUG-DAEMON-NO-DEVICE-FATAL-01 (daemon resiliente sem hardware)

### Sem hardware conectado

- [ ] Desplugar DualSense (USB) e desconectar BT. `lsusb | grep 0ce6` → vazio.
- [ ] `systemctl --user restart hefesto-dualsense4unix.service && sleep 5 && systemctl --user is-active hefesto-dualsense4unix.service` → `active`.
- [ ] `ls $XDG_RUNTIME_DIR/hefesto-dualsense4unix/hefesto-dualsense4unix.sock` → existe.
- [ ] `hefesto-dualsense4unix status` → `connected: False`, `transport: n/d`, sem traceback.
- [ ] `hefesto-dualsense4unix profile list` → lista os 5+ perfis sem erro.

### Plug do hardware com daemon offline

- [ ] Plugar DualSense via USB.
- [ ] Esperar até 10s (probe roda a cada 5s).
- [ ] `hefesto-dualsense4unix status` → `connected: True`, `transport: usb`, `battery_pct: <num>`.
- [ ] `journalctl --user -u hefesto-dualsense4unix.service --since "30 sec ago" | grep -i "controller_connected\|reconnect"` → log de transição offline→online.

### Unplug com daemon online

- [ ] `lsusb | grep 0ce6` → presente, daemon `connected: True`.
- [ ] Desplugar DualSense (USB).
- [ ] Esperar 5s.
- [ ] `systemctl --user is-active hefesto-dualsense4unix.service` → `active` (daemon não morreu).
- [ ] `hefesto-dualsense4unix status` → `connected: False` (sem traceback).

---

## Cluster IPC (state-full + persist + autoswitch)

### Bug A — state_full retorna live (não snapshot stale)

- [ ] DualSense USB conectado.
- [ ] Mantenha o stick L empurrado para a direita.
- [ ] Em outro terminal:
  ```bash
  python3 -c "
  import asyncio
  from hefesto_dualsense4unix.cli.ipc_client import IpcClient
  async def main():
      async with IpcClient.connect(timeout=2) as c:
          st = await c.call('daemon.state_full')
          print('lx:', st.get('lx'))
          print('buttons:', st.get('buttons'))
  asyncio.run(main())
  "
  ```
- [ ] `lx` deve ser `> 150` (não 128 padrão).
- [ ] Aperte e segure CROSS (X). Repita o comando. `buttons` deve incluir `cross`.

### Bug B — profile.switch persiste em active_profile.txt

- [ ] `echo "browser" > ~/.config/hefesto-dualsense4unix/active_profile.txt`
- [ ] Trocar via IPC para `shooter`:
  ```bash
  python3 -c "
  import asyncio
  from hefesto_dualsense4unix.cli.ipc_client import IpcClient
  async def main():
      async with IpcClient.connect(timeout=2) as c:
          await c.call('profile.switch', {'name': 'shooter'})
  asyncio.run(main())
  "
  sleep 1
  cat ~/.config/hefesto-dualsense4unix/active_profile.txt
  ```
- [ ] Output esperado: `shooter` (não `browser`).

### Bug C — autoswitch respeita lock manual de 30s

- [ ] Abrir Firefox em primeiro plano (regra do `browser` profile casa `wm_class=firefox`).
- [ ] `hefesto-dualsense4unix profile activate shooter && sleep 5 && hefesto-dualsense4unix status | grep active`
  - [ ] `active_profile: shooter` (lock manual segurou).
- [ ] Esperar 35s e repetir o status:
  - [ ] `active_profile: browser` (lock expirou, autoswitch voltou).

---

## Cluster Install (appindicator + dualsensectl)

### appindicator

- [ ] `gnome-extensions disable ubuntu-appindicators@ubuntu.com`
- [ ] `./install.sh --yes 2>&1 | grep -i appindicator`
- [ ] Output deve mostrar mensagem de detecção e habilitação.
- [ ] `gnome-extensions list --enabled | grep ubuntu-appindicators` → presente.

### dualsensectl

- [ ] `which dualsensectl` → ausente.
- [ ] `./install.sh --yes 2>&1 | grep -iE "dualsensectl|firmware"`
- [ ] Output deve mostrar "Firmware é opcional" + sugestão flatpak.
- [ ] Install termina com exit 0 mesmo sem dualsensectl instalado.
- [ ] (Opcional) `flatpak install -y --user flathub com.github.nowrep.dualsensectl` se quiser usar a aba Firmware.

---

## Cluster Tray (quit + zombie + mnemonic)

### Bug A — Sair mata daemon avulso

- [ ] `systemctl --user stop hefesto-dualsense4unix.service && sleep 2`
- [ ] `nohup hefesto-dualsense4unix daemon start --foreground >/tmp/test_daemon.log 2>&1 &` (anote PID).
- [ ] `nohup hefesto-dualsense4unix-gui >/tmp/test_gui.log 2>&1 &`
- [ ] Esperar 5s. Clicar com mouse no tray icon → menu → "Sair do Hefesto - Dualsense4Unix".
- [ ] `pgrep -af hefesto | grep -v grep` → vazio (GUI E daemon avulso encerrados).
- [ ] Reabilitar daemon depois: `systemctl --user start hefesto-dualsense4unix.service`.

### Bug B — Submenu Perfis sem placeholder zombie

- [ ] GUI rodando. Clicar tray → "Perfis".
- [ ] Submenu deve listar **apenas perfis reais** (André, browser, etc.) — sem item desabilitado "(carregando)".

### Bug C — Perfil sem mnemonic incorreto

- [ ] Mesmo submenu Perfis. Item `meu_perfil` deve aparecer como `meu_perfil` (não `meu__perfil` com underline duplo).

---

## #29 — Bluetooth (PROTOCOL_READY)

### Pareamento (primeira vez)

- [ ] Botão PS + Create do DualSense por 4s → entra em pairing.
- [ ] `bluetoothctl scan on` em terminal.
- [ ] `bluetoothctl pair <MAC>` (MAC aparece como `Wireless Controller`).
- [ ] `bluetoothctl trust <MAC>`.
- [ ] `bluetoothctl connect <MAC>`.

### Detecção do daemon via BT

- [ ] DualSense conectado **só** via BT (USB desplugado).
- [ ] `systemctl --user restart hefesto-dualsense4unix.service && sleep 5`
- [ ] `hefesto-dualsense4unix status` → `connected: True`, `transport: bt`, `battery_pct: <num>`.

### Output via BT

- [ ] `hefesto-dualsense4unix led --color "#FF00FF"` → lightbar fica magenta.
- [ ] `hefesto-dualsense4unix profile activate shooter` → triggers L2/R2 sentem efeito Rigid.

### Hotplug GUI via BT (se habilitado)

- [ ] Se rodou `./install.sh --enable-hotplug-gui`: desconectar BT + reconectar → GUI auto-abre.

### Promoção a MERGED

Quando todos os itens BT acima passarem, atualizar status da sprint em `docs/process/sprints/FEAT-BLUETOOTH-CONNECTION-01.md` para MERGED e anexar:
- Logs de `controller_connected transport=bt`
- Captura PNG do header GUI: `Conectado Via BT`

---

## #21 — Validar-acentuacao defense-in-depth

### Idempotência em árvore limpa

- [ ] `git status --short` → vazio (commit/push de tudo).
- [ ] `python3 scripts/validar-acentuacao.py --all --fix` → `0 correções em 0 arquivos`.
- [ ] `git status --short` → ainda vazio (nada foi modificado).

### Defesa preventiva

- [ ] Em cópia de teste em `/tmp/`, criar arquivo com `● Online` + `funcao` (ASCII faltando ç/ã).
- [ ] Rodar `python3 scripts/validar-acentuacao.py --paths /tmp/teste.py --fix`.
- [ ] Conferir que `●` foi **preservado** mesmo com a correção de `funcao→função` aplicada na mesma linha.

---

## #32 — BUG-GUI-QUIT-RESIDUAL-01 (achado colateral, não-bloqueante)

Sprint aberta para investigar separadamente. **Não bloqueia merge do PR #103.**

- [ ] Reproduzir: GUI rodando, Sair → `pgrep -af "hefesto.*app.main"` ainda mostra PID Python em estado `S` (sleeping em futex).
- [ ] Workaround atual: `pkill -9 -f hefesto_dualsense4unix.app.main` se quiser garantir kill.
- [ ] Próxima sprint vai investigar `tray.stop()` D-Bus call que pode estar bloqueando GLib mainloop.

---

## Checklist de release (gate antes de merge para `main`)

- [ ] Todos os itens críticos acima `[x]` (exceto #29 BT se hardware BT não disponível, exceto #32 que é colateral).
- [ ] PR #103 aprovado por revisão visual (você).
- [ ] CHANGELOG 3.0.0 entry está completo.
- [ ] Tag `v3.0.0` criada após merge: `git tag -a v3.0.0 -m "Hefesto - Dualsense4Unix v3.0.0"`.
- [ ] Release notes do GitHub publicadas com link pro CHANGELOG.

---

## Atalhos úteis

```bash
# Reset para refazer cenário
systemctl --user restart hefesto-dualsense4unix.service
pkill -KILL -f hefesto_dualsense4unix
rm -f $XDG_RUNTIME_DIR/hefesto-dualsense4unix/*.pid

# Logs ao vivo do daemon
journalctl --user -u hefesto-dualsense4unix.service -f

# Suite de teste rápida (não precisa hardware)
.venv/bin/pytest tests/unit -q

# Smoke USB+BT FAKE (não precisa hardware)
HEFESTO_DUALSENSE4UNIX_FAKE=1 HEFESTO_DUALSENSE4UNIX_FAKE_TRANSPORT=usb ./run.sh --smoke
HEFESTO_DUALSENSE4UNIX_FAKE=1 HEFESTO_DUALSENSE4UNIX_FAKE_TRANSPORT=bt ./run.sh --smoke --bt
```

---

*Gerado automaticamente após sessão de fix de 14 sprints (commits `d534a60..d698159` em `rebrand/dualsense4unix`).*
