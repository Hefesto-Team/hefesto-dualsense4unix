# Solução de problemas

Cobre os 10 problemas mais comuns relatados. Cada seção tem **sintoma**,
**diagnóstico** (comandos para confirmar a causa) e **fix**.

Para problemas não cobertos aqui, abra issue com a label `bug` no repositório
([AndreBFarias/hefesto-dualsense4unix](https://github.com/AndreBFarias/hefesto-dualsense4unix/issues))
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

> **Storm `-71` / conecta-desconecta em loop** (`dmesg`: `error -71`,
> `device descriptor read/64`, `not accepting address`): a causa é a
> **enumeração das interfaces de áudio USB** do DualSense (driver
> `snd-usb-audio`) sob carga — uma rajada de control-transfers no endpoint 0
> derruba o link, gera o `-71` e dispara a re-enumeração. **Não é porta/cabo/BIOS**:
> o problema é *port-independente* (provado A/B — com o áudio USB desligado, zero
> storm em qualquer porta, inclusive a do chipset), e também **não é o daemon nem o
> WirePlumber** (ambos foram eliminados na investigação). Há duas alavancas de
> software — **use uma OU outra, nunca as duas**:
>
> - **Quirk de boot que preserva o áudio** (mic/fone continuam funcionando): espaça
>   a rajada de control-transfers via `usbcore.quirks`. Aplique com
>   `sudo bash scripts/install_usb_quirk.sh` ou `./install.sh --with-usb-quirk`.
> - **Áudio USB desligado** (sem mic/fone, controle vira pure-HID): regra udev `75`
>   que tira o `authorized` das interfaces de áudio. Aplique com
>   `sudo bash scripts/install_udev.sh --disable-usb-audio`.
>
> Detalhe e A/B completo:
> `docs/process/discoveries/2026-06-26-storm-audio-pesquisa-profunda-quirk-vs-audiooff.md`.

**Fix**:

1. **Regras udev ausentes** — re-aplicar manualmente (3 caminhos
   idempotentes, escolha conforme o formato instalado):

   ```bash
   # Source / dev (repositório clonado)
   sudo bash scripts/install_udev.sh

   # .deb instalado (helper bundled em /usr/share/)
   sudo bash /usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh

   # Flatpak instalado (helper exposto via flatpak run)
   flatpak run --command=install-host-udev.sh br.andrefarias.Hefesto
   ```

   Todos aplicam o mesmo conjunto canônico de 5 regras + uinput
   modules-load (origem única em `assets/`). Após rodar, desplugue e
   replugue o controle (USB) ou re-pareie (BT).

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

## 11. Interface em inglês não aparece (i18n) no Flatpak

A partir da v3.4.0 o Hefesto - Dualsense4Unix tem catálogo EN baseline
(`po/en.po`) e PT-BR identidade (`po/pt_BR.po`). Sintomas comuns:

### Sintoma A — labels continuam em PT-BR mesmo com `LANG=en_US.UTF-8`

```bash
LANG=en_US.UTF-8 flatpak run br.andrefarias.Hefesto
# Janela abre com "Aplicar", "Salvar", "Sair" mesmo após `LANG=` no shell.
```

**Causa**: o sandbox Flatpak **filtra `LANG`/`LANGUAGE`** do host. Sem
`--env=`, gettext dentro do sandbox cai no default `pt_BR.UTF-8` (do
runtime GNOME 47).

**Fix**:

```bash
flatpak run --env=LANG=en_US.UTF-8 --env=LANGUAGE=en br.andrefarias.Hefesto
```

Ou persistir o override de uma vez só:

```bash
flatpak override --user --env=LANG=en_US.UTF-8 --env=LANGUAGE=en \
    br.andrefarias.Hefesto
flatpak run br.andrefarias.Hefesto   # agora pega EN automaticamente
```

### Sintoma B — Flatpak v3.4.0 só traduzia EN; PT-BR ficava em fallback

**Causa**: bug `BUG-FLATPAK-LOCALE-SYMLINK-01` (corrigido em v3.4.1). O
runtime `org.gnome.Platform//47` injeta symlinks de Locale Extension
no deploy sobrescrevendo `/app/share/locale/<lang>/` para alguns
idiomas (incluindo pt_BR), tornando o `install -Dm644` do manifest
no-op.

**Fix**: atualizar para Flatpak ≥ v3.4.1 — que instala catálogos em
path próprio `/app/share/hefesto-dualsense4unix/locale/<lang>/LC_MESSAGES/`
não tocado pelo runtime.

```bash
# Atualizar a partir do bundle local v3.4.1:
flatpak install --user -y --reinstall \
    dist/flatpak/hefesto-dualsense4unix-3.4.1.flatpak

# Validar:
flatpak run --command=find br.andrefarias.Hefesto \
    /app/share/hefesto-dualsense4unix/locale/ -name "*.mo"
# Esperado:
#   /app/share/.../locale/en/LC_MESSAGES/hefesto-dualsense4unix.mo
#   /app/share/.../locale/pt_BR/LC_MESSAGES/hefesto-dualsense4unix.mo
```

### Sintoma C — `.deb` ou source install em EN mas tray ainda em PT-BR

`.deb` e source install (`./install.sh`) usam paths `/usr/share/locale/`
e `~/.local/share/locale/` respectivamente — não sofrem o bug do
Flatpak. Se EN não aparece, checar:

```bash
ls ~/.local/share/locale/en/LC_MESSAGES/hefesto-dualsense4unix.mo
# Esperado: arquivo de ~17 KB

# Re-instalar se ausente:
bash scripts/i18n_compile.sh && ./install.sh --yes
```

### Adicionar idioma novo (comunidade)

```bash
bash scripts/i18n_extract.sh --add fr_FR  # cria po/fr_FR.po vazio
$EDITOR po/fr_FR.po                        # preencher msgstr
bash scripts/i18n_compile.sh               # gera .mo
```

Ver `.github/CONTRIBUTING.md` → "Contribuir traduções" para convenções
de tom + glossário PT-BR  EN.

---

## 12. Sticks "encostados em ~253" em repouso (drift falso)

**Sintoma:** ao plugar o controle depois que o daemon já estava rodando, o `daemon.state_full` (via
CLI/applet/GUI) mostra `LX`/`LY`/`RX`/`RY` em torno de `253` em repouso (deveriam estar próximos
de `128`, o centro). Aparentemente o controle tem drift, mas mover/centrar o stick fisicamente não
muda o número.

**Causa-raiz (BUG-DAEMON-EVDEV-HOTPLUG-CACHE-01, corrigido em v3.8.1):** o kernel
`hid_playstation` captura o `evdev` do DualSense. O `EvdevReader` do daemon procura o evdev
**uma única vez no `__init__`** — se o daemon subiu **offline** (sem o controle plugado), o caminho
nasce `None` e nunca era reavaliado no hotplug, fazendo o daemon cair no fallback HID-raw cru (que
parseia os bytes dos sticks errado, devolvendo ~253 em repouso).

**Verificação:**

```bash
journalctl --user -u hefesto-dualsense4unix --since '5 min ago' \
  | grep -E 'controller_connected|evdev'
# Antes do fix: "controller_connected_without_evdev hint='input pode ficar zerado...'"
# Depois do fix: "evdev_started path=/dev/input/eventN" + "controller_connected_with_evdev"
```

**Workaround (pré-v3.8.1):** reinicie o daemon **com o controle já plugado** — o `__init__` acha
o evdev e segue normal até o próximo reboot.

```bash
systemctl --user restart hefesto-dualsense4unix
```

**Correção definitiva:** atualizar para a **v3.8.1** ou superior. O `EvdevReader` agora re-procura
o evdev a cada `connect()` (custo desprezível: só re-enumera quando `_device_path is None`).

---

## 13. GUI consumindo 100% de CPU e/ou crescendo até gigabytes de RAM

**Sintoma:** a GUI fica "épica de lenta" pra navegar, a janela trava ao trocar de aba ou interagir
com widgets. `top -H -p $(pgrep -x hefesto-dualsen)` mostra a thread principal próxima de 100% e
`%MEM` crescendo continuamente (chegou a 5+ GB em 6 minutos no caso reportado).

**Causa-raiz (BUG-GUI-IDLE-ADD-BUSY-LOOP-01, corrigido em v3.8.1):** `install_status_polling`
registrava os ticks de polling do estado em dois mecanismos GLib — `timeout_add` (para o tick
periódico) **e** `idle_add` (para uma primeira leitura imediata, evitando a janela em que o
default do Glade ("Consultando…") ficaria visível). Mas os callbacks dos ticks retornam `True`
para manter o `timeout_add` vivo, e `GLib.idle_add(fn)` **reagenda `fn` enquanto ela retornar
`True`** — então as duas chamadas viravam **dois busy-loops infinitos** disparando RPCs sem parar.

**Verificação (precisa `py-spy` no venv):**

```bash
.venv/bin/pip install py-spy
sudo .venv/bin/py-spy dump --pid <PID_DA_GUI>
# Se a MainThread mostrar call_async → _tick_live_state → main loop GTK em loop apertado,
# é esse bug.
```

**Workaround (pré-v3.8.1):** matar e reabrir a GUI mascara temporariamente — o busy-loop só começa
depois que `install_status_polling` roda no `on_mount`, então a janela "respira" por uns segundos
no boot antes de degradar. Não há workaround de runtime real até atualizar.

**Correção definitiva:** **v3.8.1** — wrappers one-shot (`lambda: fn() and False`) garantem que
`idle_add` execute o tick e retorne `False`, evitando o reagendamento. Pós-fix: ~2.4% CPU + ~90 MB
RAM em repouso, comportamento normal para GUI GTK3 polling a 10/2/0.5 Hz.

---

## 14. Aba Perfis travando ao clicar/digitar/recarregar

**Sintoma:** clicar num perfil na lista, digitar no editor de nome, ou clicar em "Recarregar" /
"Salvar" trava a janela inteira por segundos visíveis. Pior quando há vários perfis em disco.

**Causa-raiz (PERF-GUI-PROFILE-LOAD-NONBLOCKING-01, corrigido em v3.8.1):**
`load_all_profiles()` (glob de `~/.config/.../profiles/*.json` + `FileLock` + parse Pydantic de
cada perfil) rodava **síncrono na thread de UI** em vários pontos: clique em perfil, abertura da
aba, salvar, importar, e principalmente o `_build_profile_from_editor` chamado pelo
`_refresh_preview` **a cada tecla digitada** no editor.

**Correção definitiva:** **v3.8.1** — `_reload_profiles_store` carrega via worker thread
(`run_in_thread` no `ipc_bridge`); o resultado popula um cache em memória (`_profiles_cache`)
consultado por `on_profile_selection_changed` e `_build_profile_from_editor`. Clicar em perfil ou
digitar não toca mais o disco. O footer (salvar/importar) permanece síncrono — são ações raras e
deliberadas, e evitam detecção de conflito de nome contra cache stale.

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

## 12. Steam Input intercepta o DualSense (touchpad vira mouse, mic spam, botões em janela em background)

**Sintomas** (USB ou BT, com Steam rodando OU acabou de fechar):

- Tocar no touchpad do controle move o cursor do desktop.
- Botões (X, círculo, etc.) disparam `ENTER` / `SPACE` / setas em qualquer janela ativa, inclusive
  com Steam minimizada ou outra aplicação em foco.
- COSMIC notifica "Microfone mutado / desmutado" em loop ao plugar.

**Por quê.** A Steam, com **PlayStation Controller Support** em modo *Always Enabled*, pega o
`/dev/hidraw*` do DualSense exclusivamente e re-injeta como `Steam Virtual Gamepad` com bindings
do `desktop_ps4.vdf` (touchpad → mouse absoluto, botões → teclas globais). Não é o daemon do
Hefesto — esses sintomas aparecem **mesmo sem o Hefesto instalado**, e em Windows o driver Sony
nativo evita esse caminho (por isso "no Windows funciona").

**Onde as toggles ficam.** Em Steam moderno (cliente 2024+), `SteamController_PSSupport` e
`UseSteamControllerConfig` ficam em `~/.steam/steam/userdata/<userid>/config/localconfig.vdf`
(per-user), **não** no `config.vdf` global como em versões antigas.

**Solução automatizada (recomendada).** O projeto inclui um helper que cobre
`.deb / Flatpak / Snap`, todos os user-ids, com backup automático ao lado:

```bash
# diagnóstico (não modifica nada)
bash scripts/disable_steam_input.sh --status

# aplicação (fecha Steam, edita .vdf, reabre)
bash scripts/disable_steam_input.sh --apply

# reverter para o backup mais recente
bash scripts/disable_steam_input.sh --restore
```

**Integração com install/uninstall.** Desde v3.8.3+, o desligamento de Steam Input PSSupport é
**default** em ambos:

- `./install.sh` (step 11/11) — desliga durante a instalação para evitar conflito Steam-vs-daemon.
- `./uninstall.sh` (passo final) — desliga durante o uninstall, porque sem o daemon do Hefesto
  Steam Input PSSupport=2 reintroduz os 3 sintomas imediatamente.

Opt-out em ambos: `--keep-steam-input` (preserva a configuração atual da Steam).

`scripts/doctor.sh` também faz o check (`check_steam_input`) e aplica em `--fix`.

**Solução manual (alternativa).** Steam → Settings → Controller → PlayStation Controller Support
→ *Disabled*. Pode exigir reabrir a Steam para persistir.

**Plano de contingência (Fase B).** Se mesmo após desligar Steam Input o touchpad ainda mover o
cursor (raro — indica que o compositor consume `event10` diretamente via libinput), aplicar regra
udev defensiva:

```bash
sudo tee /etc/udev/rules.d/95-dualsense-touchpad-no-pointer.rules <<'EOF'
# Impede o touchpad do DualSense de virar ponteiro do desktop.
# Não afeta o joystick (event8/js0) nem motion sensors (event9).
ACTION=="add", SUBSYSTEM=="input", \
  ENV{ID_VENDOR_ID}=="054c", ENV{ID_MODEL_ID}=="0ce6", \
  ATTRS{name}=="*Touchpad*", \
  ENV{ID_INPUT_TOUCHPAD}="0", ENV{ID_INPUT_MOUSE}="0"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger --action=change --subsystem-match=input
```

Reconectar o controle após o trigger. Esta regra **não** é restauração do estado original — é uma
adição mínima — mas resolve o sintoma sem reinstalar o daemon.

---

## Recursos

- [README principal](../../README.md) — instalação e uso
- [Quickstart visual](quickstart.md) — primeiros passos com screenshots
- [ROADMAP](../process/ROADMAP.md) — o que vem nas próximas releases
- [ADR-014](../adr/014-cosmic-wayland-support.md) — decisão técnica COSMIC/Wayland
- [Diário de descobertas](../process/discoveries/) — bugs encontrados e fixes
- [CHANGELOG](../../CHANGELOG.md) — histórico completo
