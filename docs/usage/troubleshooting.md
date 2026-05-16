# Solução de problemas

Cobre os 10 problemas mais comuns relatados. Cada seção tem **sintoma**,
**diagnóstico** (comandos para confirmar a causa) e **fix**.

Para problemas não cobertos aqui, abra issue com a label `bug` no fork
[[REDACTED]/hefesto-dualsense4unix](https://github.com/[REDACTED]/hefesto-dualsense4unix/issues)
ou upstream [AndreBFarias/hefesto-dualsense4unix](https://github.com/AndreBFarias/hefesto-dualsense4unix/issues)
incluindo `journalctl --user -u hefesto-dualsense4unix.service -n 100`.

---

## 1. Controle DualSense não detectado via USB

**Sintoma**: `hefesto-dualsense4unix status` mostra `connected: False`
com cabo conectado.

**Diagnóstico**:

```bash
lsusb | grep -i "0ce6\|sony"          # esperado: linha com 054c:0ce6
ls -l /dev/hidraw* | head -5          # confirma device hidraw existe
groups $USER | grep -E 'input|plugdev'  # opcional, ACL via udev tag uaccess é o caminho canônico
```

**Fix**:

1. **Regras udev ausentes**: rode `./scripts/install_udev.sh` (instalação
   via fonte) ou reinstale `.deb` (regras vão para `/lib/udev/rules.d/`).
   Após instalação, desplugue e replugue o controle.
2. **systemd-logind ausente** (Alpine/Void/Artix/Gentoo sem systemd): o
   projeto requer logind para a TAG `uaccess` funcionar — ver
   [ADR-009](../adr/009-systemd-logind-scope.md). Fallback temporário:
   `sudo chmod 0666 /dev/hidraw*`.
3. **Permissão hidraw específica**: `sudo udevadm trigger
   --action=change` força reaplicação das regras sem reboot.

---

## 2. Controle DualSense não detectado via Bluetooth

**Sintoma**: `bluetoothctl info` mostra `Connected: yes` mas Hefesto
reporta `connected: False`.

**Diagnóstico**:

```bash
bluetoothctl info <MAC>               # confirma "Connected: yes"
ls /dev/hidraw*                       # esperado: device extra após pareamento
journalctl --user -u hefesto-dualsense4unix.service -n 50 | grep -i bt
```

**Fix**:

1. **Reparear**: `bluetoothctl` →`remove <MAC>` → `scan on` → `pair <MAC>`
   → `trust <MAC>` → `connect <MAC>`.
2. **Restart daemon**: `systemctl --user restart hefesto-dualsense4unix.service`
   (a sprint v3.2.0 corrigiu BUG-TRANSPORT-CACHE-STALE-01 — daemons
   anteriores a v3.2.0 mostravam `transport=usb` incorreto via BT).
3. **Auto-suspend USB**: se você tem o cabo plugado e BT ao mesmo tempo,
   o pydualsense pega o primeiro disponível. Desplugue o cabo para
   forçar BT.

---

## 3. Tray icon oculto no Pop!_OS COSMIC

**Sintoma**: GUI abre mas não há ícone no painel.

**Diagnóstico**:

```bash
echo $XDG_CURRENT_DESKTOP             # esperado: COSMIC
busctl --user list | grep -i StatusNotifierWatcher  # provavelmente vazio
```

**Fix**:

1. **Janela compacta (default v3.3.0+)**: o Hefesto detecta automatic-
   amente e abre uma janela 320×90 sempre-on-top com bateria + perfil +
   botões. Se ela não aparecer, garantir que não há
   `HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW=0` no ambiente:
   ```bash
   env | grep COMPACT_WINDOW          # esperado: vazio (default ligado)
   ```
2. **Habilitar cosmic-applets de status**: aguardando lançamento do
   `cosmic-applet-status-area` no Pop!_OS estável. Acompanhe
   [ROADMAP v3.4](../process/ROADMAP.md) para applet Rust nativo.
3. **Desativar janela compacta** se preferir só GUI principal:
   `HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW=0 hefesto-dualsense4unix-gui`.

---

## 4. Tray icon oculto no GNOME 42+

**Sintoma**: GUI abre mas não há ícone no top-bar do GNOME.

**Diagnóstico**:

```bash
gnome-extensions list --enabled | grep ubuntu-appindicators
# esperado: presente; se vazio → extension não habilitada
```

**Fix**:

```bash
gnome-extensions enable ubuntu-appindicators@ubuntu.com
# Faça logout/login do GNOME (a extension carrega no Shell startup).
```

O `install.sh --yes` faz isso automaticamente em Pop!_OS / Ubuntu
GNOME, mas precisa de logout/login depois.

---

## 5. Flatpak: controle não detectado dentro do sandbox

**Sintoma**: `flatpak run br.andrefarias.Hefesto` abre GUI mas
`status` reporta `connected: False`.

**Diagnóstico**:

```bash
# Confirma que o host vê o controle:
lsusb | grep -i 0ce6
ls /dev/hidraw*

# Confirma regras udev instaladas no host:
ls /etc/udev/rules.d/70-ps5-controller.rules 2>&1
```

**Fix**:

```bash
# As regras udev precisam estar no host (fora do sandbox).
# Use o helper bundled:
flatpak run --command=install-host-udev.sh br.andrefarias.Hefesto

# Replug o controle (udev reaplica).
```

O sandbox usa `--device=all` que dá acesso a todos os `/dev/hidraw*`,
mas as regras udev precisam ter sido aplicadas no host antes para o
device existir.

---

## 6. Daemon offline / serviço falha ao iniciar

**Sintoma**: `systemctl --user status hefesto-dualsense4unix.service`
mostra `failed` ou `inactive`.

**Diagnóstico**:

```bash
systemctl --user status hefesto-dualsense4unix.service --no-pager
journalctl --user -u hefesto-dualsense4unix.service -n 50 --no-pager
ls -l $XDG_RUNTIME_DIR/hefesto-dualsense4unix/hefesto-dualsense4unix.sock
```

**Fix**:

1. **Start request repeated too quickly**: `systemctl --user reset-failed
   hefesto-dualsense4unix.service && systemctl --user restart
   hefesto-dualsense4unix.service`.
2. **Stale lock file**: `rm -f
   $XDG_RUNTIME_DIR/hefesto-dualsense4unix/*.pid
   $XDG_RUNTIME_DIR/hefesto-dualsense4unix/*.sock` e re-start.
3. **PyGObject ausente** (instalação via fonte): rode
   `./scripts/dev_bootstrap.sh --with-tray` ou
   `sudo apt install python3-gi gir1.2-gtk-3.0
   gir1.2-ayatanaappindicator3-0.1`.
4. **Múltiplas instâncias**: `pkill -KILL -f hefesto_dualsense4unix`
   limpa tudo; o single_instance v2.0+ deveria evitar, mas processos
   zumbi podem aparecer após crash.

---

## 7. Perfis não trocam automaticamente (auto-switch travado)

**Sintoma**: trocar de janela não dispara troca de perfil.

**Diagnóstico**:

```bash
hefesto-dualsense4unix status | grep -E "active_profile|wm"
journalctl --user -u hefesto-dualsense4unix.service | grep autoswitch | tail -10
```

**Fix**:

1. **Lock manual de 30s ativo**: se você acabou de trocar via tray/CLI,
   o auto-switch fica congelado por 30s para não conflitar com sua
   escolha. Espere ou troque para `fallback` para destravar.
2. **X11 sem python-xlib**: `pip install --user python-xlib` se via
   fonte. Em `.deb` já vem como Recommends.
3. **Wayland sem portal nem wlrctl**: `sudo apt install wlrctl` (Wayland
   compositors com wlr-foreign-toplevel-management). No COSMIC, o portal
   ainda não expõe a API; cascade cai em wlrctl. Veja
   [ADR-014](../adr/014-cosmic-wayland-support.md).

---

## 8. pydantic v1 quebrando schemas em Ubuntu 22.04/24.04

**Sintoma**: `ImportWarning: pydantic X detectado; Hefesto requer
pydantic >= 2.0` ou crash com
`AttributeError: module 'pydantic' has no attribute 'ConfigDict'`.

**Diagnóstico**:

```bash
python3 -c "import pydantic; print(pydantic.VERSION)"
# Ubuntu 22.04 Jammy: 1.8.2  →  problema
# Ubuntu 24.04 Noble: 1.10.14 →  problema
# Ubuntu 25.04 Plucky+: 2.10+ →  OK
```

**Fix recomendado** (2 comandos):

```bash
pip install --user 'pydantic>=2'
sudo apt install ./hefesto-dualsense4unix_3.3.0_amd64.deb
```

O `.deb` empacota um virtualenv com pydantic 2.x em
`/opt/hefesto-dualsense4unix/venv/`, então também resolve. Use
**AppImage** ou **Flatpak** se preferir zero-config.

---

## 9. Cursor voador / mouse emulado fora de controle

**Sintoma**: ao ativar emulação de mouse (aba Mouse), o cursor sai
voando ou pula para o canto da tela.

**Diagnóstico**:

```bash
hefesto-dualsense4unix mouse status   # confirma toggle on/off
```

**Fix**:

1. **Recalibrar deadzone do giroscópio**: aba Mouse → slider "Deadzone"
   → aumente para 8-12%.
2. **Desativar mouse via giroscópio**: a aba Mouse permite só pad ou só
   giroscópio. Pad é mais previsível.
3. **`uinput` permission denied**: `sudo modprobe uinput && sudo chmod
   0660 /dev/uinput`. O `install_udev.sh` cuida disso via regra
   `71-uinput.rules`.

---

## 10. Janela mostra "Consultando..." e nunca atualiza

**Sintoma**: aba Status fica em "Consultando..." indefinidamente.

**Diagnóstico**:

```bash
ls -l $XDG_RUNTIME_DIR/hefesto-dualsense4unix/hefesto-dualsense4unix.sock
systemctl --user is-active hefesto-dualsense4unix.service
```

**Fix**:

Desde v3.2.0, a GUI mostra "Desconectado — abra a aba Daemon e clique
em Iniciar" após 5s sem resposta IPC (UI-STATUS-OFFLINE-FALLBACK-01).
Se ainda vê "Consultando..." indefinidamente, está rodando uma versão
antiga — atualize via:

```bash
# .deb
sudo apt install --reinstall ./hefesto-dualsense4unix_3.3.0_amd64.deb

# Flatpak
flatpak update br.andrefarias.Hefesto

# Fonte
git pull && ./scripts/dev_bootstrap.sh --with-tray
```

Se já está em v3.2.0+ e o problema persiste, abra issue com o output de
`journalctl --user -u hefesto-dualsense4unix.service -n 100`.

---

## Diagnóstico geral (script para issue)

Quando reportar problema, anexe a saída de:

```bash
cat <<EOF
=== Sistema ===
$(lsb_release -d 2>/dev/null || cat /etc/os-release | head -3)
Kernel: $(uname -r)
DE: $XDG_CURRENT_DESKTOP / sessão: $XDG_SESSION_TYPE

=== Hefesto ===
Versão: $(hefesto-dualsense4unix version 2>/dev/null || echo "não instalado")
Daemon: $(systemctl --user is-active hefesto-dualsense4unix.service 2>/dev/null || echo "n/a")

=== Hardware ===
USB: $(lsusb | grep -iE "0ce6|sony" || echo "sem DualSense USB")
BT:  $(bluetoothctl devices 2>/dev/null | grep -i dualsense || echo "sem DualSense pareado")

=== Permissões ===
hidraw: $(ls -l /dev/hidraw* 2>/dev/null | head -3)
uinput: $(ls -l /dev/uinput 2>/dev/null)

=== Logs recentes ===
EOF
journalctl --user -u hefesto-dualsense4unix.service -n 30 --no-pager 2>/dev/null
```

---

## Recursos

- [README principal](../../README.md) — instalação e uso
- [Quickstart visual](quickstart.md) — primeiros passos com screenshots
- [ROADMAP](../process/ROADMAP.md) — o que vem nas próximas releases
- [ADR-014](../adr/014-cosmic-wayland-support.md) — decisão técnica COSMIC/Wayland
- [Diário de descobertas](../process/discoveries/) — bugs encontrados e fixes
- [CHANGELOG](../../CHANGELOG.md) — histórico completo
