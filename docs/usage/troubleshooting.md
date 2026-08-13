# Solução de problemas

Cada seção tem **sintoma**, **diagnóstico** (comandos para confirmar a causa) e
**fix**.

> **Sobre os números de versão citados aqui.** Várias seções dizem "corrigido em
> v3.8.1", "desde v3.2.0" e afins. Essa é a numeração **antiga**: em 24/07/2026
> o projeto recomeçou em 0.1.0 para o primeiro lançamento público em alfa, e as
> versões 0.1.0…4.0.0 anteriores foram desenvolvimento interno (ver
> [CHANGELOG](../../CHANGELOG.md)). Se você está na 0.1.x, **todas** essas
> correções já estão no seu código — as referências ficam porque explicam *o
> que* era o bug, que é o que importa quando o sintoma reaparece.

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
> `arquivo/processo-pre-1.0:docs/process/discoveries/2026-06-26-storm-audio-pesquisa-profunda-quirk-vs-audiooff.md`.

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

   Todos aplicam o mesmo conjunto canônico — **15 regras** por padrão (mais a
   `75`, que só entra com `--disable-usb-audio`) + o `modules-load` de
   `uinput`/`uhid`, com origem única em `assets/`. Após rodar, desplugue e
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
   `cosmic-applet-status-area` no Pop!_OS estável. O projeto já traz um applet
   COSMIC nativo em Rust (`packaging/cosmic-applet/`), instalado por padrão
   **em sessões COSMIC** (fora do COSMIC, só com `--enable-cosmic-applet`;
   `--no-cosmic-applet` desliga). Se `cargo`/`just` faltarem, o instalador
   avisa e segue sem o applet.
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
3. **Wayland sem portal nem wlrctl**: `sudo apt install wlrctl` resolve nos
   compositores que implementam `wlr-foreign-toplevel-management` (Sway,
   River, Wayfire).

   **No COSMIC isso não resolve.** O `cosmic-comp` não implementa esse
   protocolo — `wlrctl toplevel list --json` volta vazio — e o portal
   `GetActiveWindow` também não está disponível. No COSMIC o autoswitch
   funciona pelo **XWayland** (que é o padrão), via `XlibBackend`; para
   janelas Wayland nativas ele não vê nada e você troca de perfil pela
   janela, pela CLI ou pelo combo no controle. Veja
   [ADR-014](../adr/014-cosmic-wayland-support.md) e
   [`cosmic.md`](cosmic.md).

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
sudo apt install ./dist/hefesto-dualsense4unix_<versão>_amd64_<pytag>.deb
```

O `.deb` empacota um virtualenv com pydantic 2.x em
`/opt/hefesto-dualsense4unix/venv/`, então também resolve. Use
**AppImage** ou **Flatpak** se preferir zero-config.

---

## 9. Cursor voador / mouse emulado fora de controle

**Sintoma**: ao ativar emulação de mouse (aba Navegação DSX), o cursor sai
voando ou pula para o canto da tela.

**Diagnóstico**:

```bash
hefesto-dualsense4unix mouse status   # confirma toggle on/off
```

**Fix**:

1. **Recalibrar deadzone do giroscópio**: aba Navegação DSX → slider "Deadzone"
   → aumente para 8-12%.
2. **Desativar mouse via giroscópio**: a aba Navegação DSX permite só pad ou só
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

Desde v3.2.0, a GUI mostra "Desconectado — abra a aba Sistema e clique
em Iniciar" após 5s sem resposta IPC (UI-STATUS-OFFLINE-FALLBACK-01).
Se ainda vê "Consultando..." indefinidamente, está rodando uma versão
antiga — atualize via:

```bash
# .deb
sudo apt install --reinstall ./dist/hefesto-dualsense4unix_<versão>_amd64_<pytag>.deb

# Flatpak
flatpak update br.andrefarias.Hefesto

# Fonte
git pull && ./scripts/dev_bootstrap.sh --with-tray
```

Se já está em v3.2.0+ e o problema persiste, abra issue com o output de
`journalctl --user -u hefesto-dualsense4unix.service -n 100`.

---

## 11. Interface em inglês não aparece (i18n) no Flatpak

> **Antes dos sintomas, o alcance real.** A língua do Hefesto é o **português
> do Brasil** — decisão de 07/08/2026. O catálogo EN existe e funciona, mas
> alcança só o **esqueleto fixo** da janela (os 308 `translatable="yes"` de
> `gui/main.glade`). O texto que as abas escrevem enquanto rodam continua em
> português mesmo com `LANG=en_US.UTF-8`. **Medido em 07/08/2026:** dos 18
> módulos de `src/hefesto_dualsense4unix/app/actions/`, **15** não importam a
> função de tradução e carregam 561 literais acentuados em português.
>
> **Nota datada — 08/08/2026:** são **19** módulos desde a `RELANCAR-01`, que
> acrescentou `relancar.py`. Ele **não** importa a função de tradução, então a
> proporção passou a **16 de 19** — o quadro não mudou de natureza.
> Se você chegou aqui esperando uma janela inteiramente em inglês, o problema
> não é a sua instalação — é a promessa antiga, e ela foi retirada. Registro em
> `docs/process/sprints/2026-08-07-LINGUA-DO-PRODUTO-01-o-convite-a-traduzir-era-falso.md`.

A partir da v3.4.0 o Hefesto - Dualsense4Unix tem catálogo EN baseline
(`po/en.po`) e PT-BR identidade (`po/pt_BR.po`). Os sintomas abaixo são
defeitos **de carregamento do catálogo** — reais, medidos e curados — e
continuam valendo:

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

### O que saiu daqui em 07/08/2026, e por quê

Esta seção terminava com uma receita de três linhas ensinando a comunidade a
acrescentar um idioma. Ela **saiu**: o que ela entregaria não é o que ela
prometia, pela medição do quadro no início desta seção.

O encanamento de i18n **não** foi removido junto — ele está correto, e
arrancá-lo destruiria trabalho bom para provar um ponto. Catálogos, scripts e o
esqueleto marcado continuam funcionando, e os três sintomas acima continuam
sendo defeitos de verdade, com cura de verdade.

Contexto completo em `.github/CONTRIBUTING.md`, seção "A língua do produto".

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
venv/bin/pip install py-spy
sudo venv/bin/py-spy dump --pid <PID_DA_GUI>
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

## 15. Steam Input intercepta o DualSense (touchpad vira mouse, mic spam, botões em janela em background)

**Sintomas** (USB ou BT, com Steam rodando OU acabou de fechar):

- Tocar no touchpad do controle move o cursor do desktop. **Ver a nota datada
  abaixo antes de tratar isto como defeito.**
- Botões (X, círculo, etc.) disparam `ENTER` / `SPACE` / setas em qualquer janela ativa, inclusive
  com Steam minimizada ou outra aplicação em foco.
- COSMIC notifica "Microfone mutado / desmutado" em loop ao plugar.

> **NOTA DATADA — 09/08/2026: o primeiro sintoma deixou de ser sintoma.**
> *"Tocar no touchpad do controle move o cursor do desktop"* é, hoje, o
> **comportamento correto e pretendido** do Hefesto, nos três modos — decisão
> dela, `TOUCHPAD-DO-SISTEMA-01`: *"a ideia do touchpad é ele voltar a funcionar
> assim, seja no modo nativo ou dualsense"*. O touchpad do DualSense é o
> touchpad do **sistema**, pelo libinput, como é quando o controle é plugado sem
> o Hefesto instalado. Ver
> [`modos.md`](modos.md#o-touchpad-é-touchpad-do-sistema).
>
> **Como separar um do outro, pela própria descrição desta seção** (GRAU:
> DERIVADO do parágrafo "Por quê" abaixo, não medido de novo): o mapeamento do
> `desktop_ps4.vdf` é touchpad → mouse **absoluto** — o dedo leva o ponteiro
> para a posição correspondente na tela. O ponteiro do libinput é **relativo**,
> como o de um touchpad de notebook. Os outros dois sintomas (teclas globais em
> janela de fundo, e o loop de mute) continuam valendo inteiros e são o sinal
> mais seguro de que é a Steam.

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

**Plano de contingência (Fase B).**

> **NOTA DATADA — 09/08/2026: este plano briga com o produto de hoje. Não o
> aplique para "curar" o cursor.** A regra abaixo tira o touchpad do DualSense
> do libinput — que é exatamente o comportamento que o Hefesto **desfez** em
> 09/08, por decisão dela. A premissa que a justificava (*"o compositor consumir
> `event10` diretamente via libinput" é anomalia*) caducou: hoje isso é o
> desenho. Aplicá-la devolve o touchpad ao estado que ela chamou de defeito, e
> ainda o faz por fora do produto — o `uninstall.sh` não conhece esta regra e
> não a remove.
>
> **Quando ela ainda serve:** só se você **quiser** que o touchpad deixe de ser
> ponteiro do sistema. Nesse caso, o caminho de dentro do produto é o descrito
> no cabeçalho de `assets/76-dualsense-touchpad-libinput-ignore.rules` (uma
> linha, com o curinga de volta), e ele tem a vantagem de o Hefesto **saber** —
> o leitor de touchpad lê a mesma flag e devolve o cursor e as três regiões de
> clique ao Hefesto sozinho. A regra abaixo não avisa ninguém.

Registro do que este plano era, preservado por não se apagar decisão medida —
se mesmo após desligar Steam Input o touchpad ainda mover o cursor de forma
**absoluta**, a regra defensiva era:

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

## 16. "Emular teclado" está ligado e o controle não escreve letra nenhuma

**Sintoma.** O interruptor "Emular teclado" da aba Navegação está ligado, o
Alt+Tab funciona, e mesmo assim não sai uma letra em campo de texto nenhum.

**Não é defeito — é o que o produto entrega hoje, e a tela passou a dizer.**
**GRAU: MEDIDO** em 09/08/2026: o motor funciona (34 teclas emitidas no journal
dela, e o Alt+Tab pegou). O que não existe é a promessa: **nenhum dos nove
atalhos de fábrica digita uma letra** — são Super, PrintScreen, Alt+Tab,
Alt+Shift+Tab, Enter, Delete e Backspace. Além disso, onze dos vinte botões
nascem **sem tecla nenhuma**, e a lista da aba os **escondia**: quem ligava a
emulação via seis linhas, apertava X, Círculo, Quadrado e o direcional, e
concluía, com razão, que "o teclado não funciona".

**O caminho para escrever texto é o teclado na tela, no L3.** Hoje a lista
mostra os vinte botões, inclusive os sem tecla, e a legenda diz isso com todas
as letras.

**Para dar uma letra a um botão:** aba **Navegação**, clique duas vezes na
coluna "Tecla do teclado" da linha do botão. Botões que o **mouse** emulado já
usa aparecem marcados — dar uma tecla a um deles não substitui o mouse: o botão
passa a fazer as duas coisas ao mesmo tempo, cada uma pelo seu dispositivo
virtual.

---

## 17. O L3 não abre o teclado na tela

**Sintoma.** Clicar o analógico esquerdo (L3) não abre teclado nenhum, ou a
janela avisa que o teclado na tela não está disponível.

**Causa.** O teclado na tela é um programa do sistema, e ele não está instalado.
Até 10/08/2026 o Hefesto **prometia** o L3 e não instalava, não declarava e não
conferia nada — `grep -c onboard install.sh` devolvia zero. Hoje o `install.sh`
o instala sozinho, sem flag (passo 4f), mas uma máquina provisionada antes disso
segue sem ele.

**Cura:**

```bash
sudo apt install wvkbd     # sessão Wayland (COSMIC, GNOME Wayland, KDE Wayland)
sudo apt install onboard   # sessão X11

# em que sessão você está:
echo "$XDG_SESSION_TYPE"   # wayland | x11
```

Não é preciso reiniciar o daemon: ele reconsulta o sistema a cada 10 segundos —
o cache era **eterno** até 10/08, e por isso instalar com o daemon no ar não
resolvia nada até o próximo start.

**Por que o pacote depende da sessão, e por que não instalar os dois.** O
`onboard` digita por **XTEST** (`Depends: libxtst6`); numa sessão Wayland ele
abre por XWayland e as teclas só chegam a clientes XWayland — **abre e não
digita**, que é pior que não abrir, porque parece que funcionou. O `wvkbd` é
cliente Wayland puro e digita pelo `zwp_virtual_keyboard_manager_v1`. Com os
dois instalados o Hefesto escolhe pela **sessão viva** (`WAYLAND_DISPLAY`
primeiro, `DISPLAY` só depois) — até 10/08 a ordem era fixa, com o `onboard`
primeiro, e numa sessão Wayland ele escolheria justamente o que não digita.

**Diagnóstico:** `hefesto-dualsense4unix doctor` confere, e distingue as quatro
histórias por trás de um `command -v` vazio: você escolheu pular no install, o
install tentou e falhou (com o motivo), o install nunca passou nesta máquina, ou
estava instalado e sumiu. Nesse último caso o veredito diz também que não fomos
nós: **o `uninstall.sh` nunca remove pacote de sistema.**

No **Flatpak** o `wvkbd` vem embutido no bundle e nada precisa ser instalado —
ver [`flatpak.md`](flatpak.md).

---

## 18. O perfil daquele jogo existe, e o jogo abriu sem ele

**Sintoma.** Você escreveu um perfil para o jogo, o arquivo está no disco com o
`appid` certo, e ao abrir o jogo vale outro perfil — normalmente o `fallback`.

**A causa mais comum, medida em 10/08/2026: um `process_name` na regra.** O
match é **AND** entre os campos preenchidos, e sob Proton o `process_name`
**nunca** casa: ele compara com o basename de `/proc/PID/exe`, e sob Proton esse
binário é o do wine, não o `.exe` do jogo. O AND com `process_name` não
estreita — **anula**.

No caso dela: `window_class` batia (`steam_app_3357650`), o perfil exigia
`PRAGMATA.exe`, a máquina via `wine64-preloader`, e o journal registrava
`profile_select_catch_all_sem_autoridade_em_jogo candidatos=['fallback']`.
Tirando **só** o `process_name`, os candidatos viraram
`['fallback', 'Pragmata']`.

**Onde ver isso sem abrir journal:** a aba **No jogo**, com o jogo na frente,
diz qual perfil daquele jogo não entrou e o que ele exigiu, lado a lado com o
que a máquina vê. É uma linha amarela acima dos painéis, e ela aparece nos três
modos.

**Cura:** aba **Perfis** → o perfil do jogo → **Modo avançado** → apague o campo
"nome do processo". A janela **não** o apaga sozinha: o que você escreveu é seu.
Detalhe e a medição completa em
[`creating-profiles.md`](creating-profiles.md#a-armadilha-do-process_name-em-jogo-da-steam-medido-em-10082026).

**A outra causa, quando não há `process_name` envolvido:** o cadeado **"Não
trocar de perfil sozinho ao abrir um jogo"**, na aba Início, está marcado. E
lembre-se de que a prioridade é o **segundo** critério: um perfil com regra de
janela sempre vence um "Vale sempre", por mais alta que seja a prioridade deste.

---

## 19. A vibração do jogo dura um instante e morre

**Sintoma.** O jogo vibra o controle e a vibração **morre logo no começo** — um
tranco e silêncio, ou nada. Não é vibração fraca nem intermitente: é
cancelamento. Acontece com o controle no cabo **e** no rádio.

**Onde isso aparece:** quando o jogo está falando com o **DualSense físico** em
vez de com o controle virtual do Hefesto — ou seja, com **"Jogar pelo Hefesto"
desligado** e sem estar na **Conexão Nativa (Sony)**. Nos outros casos uma das
duas coisas protegia, e por isso o defeito parecia intermitente.

**Como confirmar em dez segundos:** abra a aba **Rumble**. Se a linha em cima
dos quatro botões disser *"A intensidade acima não está chegando a jogo nenhum:
não há gamepad virtual, e é por ele que ela passa"*, você está exatamente nesse
estado.

**A causa, medida em 11/08/2026** com quatro DualSense na mesa, dois no cabo e
dois no rádio: o Hefesto reconfirmava o estado do controle a cada meio segundo,
e essa reconfirmação **zerava os motores** que o jogo tinha acabado de ligar. A
prova não foi por argumento — subindo o intervalo de 0,5 s para 8,0 s, a
vibração passou a durar **oito segundos exatos**, e a duração seguiu o número.

**Corrigido**: a reconfirmação deixou de ser eterna. Ela agora só acontece na
janela logo depois de uma mudança de verdade, que é para o que ela servia
(garantir que a mudança chegou); passado isso, o Hefesto **cala** e não pisa mais
no motor de quem está tocando.

**A cura foi conferida no aparelho em 12/08/2026, com o serviço LIGADO** — grau
*o aparelho obedeceu*, ensaios `rumble-ff-cura-cabo-so`, `rumble-ff-cura-cabo-par`
e `rumble-ff-cura-radio-par` (`../data/ensaios.csv:59-61`), com o olho dela:

- **no cabo**, um controle sozinho vibrou **8,26 s** contínuos numa janela de
  8 s pedida — *"contínuo os 8 segundos"*, e a barra de luz não apagou junto;
- **no cabo e no rádio disparados na mesma janela** (0,0 ms de diferença),
  **8,28 s** nos dois: *"funcionou em ambos, aparentemente iguais"*. É a
  **primeira** vez que a vibração por **rádio** dura a janela inteira com o
  serviço vivo — em 11/08, o mesmo ensaio dava **um tranco** e morria.

**Se o sintoma continuar depois de atualizar:** o serviço em memória pode ser
mais velho que o código no disco. Aba **Sistema** → **Reiniciar**, ou:

```bash
systemctl --user restart hefesto-dualsense4unix.service
```

**Os quatro ao mesmo tempo: a duração ficou IGUAL** (medido em 12/08/2026,
ensaios `rumble-quatro-duracao-igual-r1` e `-r2`, `../data/ensaios.csv:68-69`).
Este parágrafo dizia, até 12/08, que o caso de quatro controles **não estava
explicado**: com o serviço no estado antigo eles vibravam *"por duração
diferente"* em vez de nenhum vibrar, e o contraste ficou sem dono. Com a cura
ligada, os quatro receberam o efeito e ela comparou **dois por vez, um em cada
mão** — um do cabo e um do rádio, porque duas mãos é comparação inequívoca e
olhar quatro na mesa não é. **Duas rodadas, as duas iguais.** A observação de
11/08 continua valendo como o que era: o retrato do defeito **antes** da cura.

---

## 20. A barra de luz não pega a cor por Bluetooth

**Sintoma.** O controle conecta por Bluetooth, a barra de luz **nasce apagada**
(ou com uma cor que não é a sua), e **"Aplicar no controle"** na aba Lightbar não
muda nada. O mesmo controle, no cabo, obedece na hora.

**A causa, medida em 12/08/2026 e conferida no ar:** com a **Steam aberta**, ela
mantém uma via de escrita para **cada** DualSense e **repinta a barra de todos
eles a cada conexão nova** — uma rajada de alguns segundos, que se repete a cada
controle que você liga. A cor que o Hefesto pinta chega junto com a dela, e a
última palavra fica sendo a da Steam.

Passada a rajada, ela **cala** — e em regime **não apaga** a barra: abrindo a
Steam com as barras já acesas, elas mudaram para as cores dela e continuaram
acesas. O que a Steam estraga é o **começo** da conexão.

Os números, para quem quiser conferir: com a Steam viva no momento da conexão,
**um em três** controles aceitou a cor; com **ninguém** disputando antes da
conexão, **três em três** aceitaram — e no fio saíram **98** escritas contra
**6**. A medição inteira está em
[a pilha do Steam Input](../protocol/pilha-steam-input-xpad-sdl.md), seção
6-bis.

**O que fazer hoje:**

1. **Ligue os controles ANTES de abrir a Steam.** É o único gesto com medição
   limpa atrás: os três nasceram acesos e os três aceitaram a cor escolhida.
2. **Se já ligou com a Steam aberta:** feche a Steam, desligue o controle
   (segure o botão PS até a barra apagar) e ligue de novo. **Reconectar com a
   Steam ainda aberta às vezes funciona e às vezes não** — foi um em três nos
   ensaios —, e a diferença não é preciosismo: o que decide não é a reconexão, é
   **quem está disputando a barra no instante em que o controle sobe**.
   *"Reconectar cura"* já foi concluído e derrubado quatro vezes neste projeto
   justamente por isso.
3. **No cabo o problema não aparece.** No ensaio de 11/08 em que os dois
   controles do rádio **não** aceitaram a cor, os dois do cabo aceitaram **no
   mesmo instante** — e a Steam estava aberta.

**Insistir em "Aplicar no controle" adianta menos do que parece — mas não pelo
motivo que esta página dava até 12/08.** Estava escrito aqui que *"por Bluetooth
a cor sai por um caminho que perde essa disputa"*, como se a rota fosse ruim.
**Não é a rota.** Na bancada de 12/08 à noite, com a **Steam fechada** e o
serviço parado, as duas rotas obedeceram nos mesmos controles do rádio: magenta
escrito pelo caminho cru e, logo depois, verde escrito pelo caminho do sistema —
*"todos os controles estão verdes"* (ensaios `cor-rota-hidraw-sem-steam-2235` e
`cor-rota-sysfs-sem-steam-2237`, `../data/ensaios.csv:71-72`). O que derruba a
cor é **quem mais está escrevendo na hora**, e a hora é a **conexão**.

**O controle não esquece a cor — 136 s cronometrados.** Ainda na mesma bancada,
sem serviço e sem Steam, a cor escrita ficou de pé por **dois minutos e dezesseis
segundos** sem ninguém reforçar nada, o dobro do prazo que o ensaio pedia. Uma
barra apagada, portanto, **não** é o controle esquecendo: é alguém mandando
apagar. Não adianta clicar de novo para *"segurar"* a cor.

**Mirar UM controle funciona, e isso foi conferido:** com quatro na mesa, o verde
aplicado só no controle do cabo pintou **só ele** — *"verde inequívoco, os demais
mostrando a cor de antes"* (ensaio `lightbar-cabo-isolado-2229`,
`../data/ensaios.csv:70`). Os outros três são o controle negativo do ensaio.

**O que ainda não medimos, e vale registro se você testar:** se desligar o
*PlayStation Controller Support* da Steam (a [seção 15](#15-steam-input-intercepta-o-dualsense-touchpad-vira-mouse-mic-spam-botões-em-janela-em-background)
desta página) evita a repintura. Ninguém aqui rodou esse ensaio.

**A cura ENTROU no produto em 12/08/2026** — escrever a cor depois que a sequência
de conexões sossega, e escrevê-la em **todos** os controles, não só no que
chegou, pelo caminho que vence a disputa. O aceite dela na bancada, quando o
desenho foi mostrado, foi *"perfeito"*.

> **A ressalva, dita porque a casa não confunde as duas coisas:** o que está
> provado é que **o comando certo sai pelo caminho certo na hora certa** — isso
> tem teste. **Ninguém viu ainda a barra acender pelo produto com a Steam viva
> na conexão**, que é o ensaio de um minuto que falta. Até essa volta acontecer,
> os três contornos acima continuam sendo o que se recomenda.

---

## Recursos

- [README principal](../../README.md) — instalação e uso
- [Quickstart](quickstart.md) — primeiros passos
- [A janela, aba por aba](interface.md) — o que cada aba faz
- [8BitDo SN30 Pro](troubleshooting-8bitdo.md) — modos, identificação e qual usar
  por Bluetooth (DirectInput/PS4) contra qual usar no cabo (Switch). Controle não
  gerenciado pelo hefesto.
- [ADR-014](../adr/014-cosmic-wayland-support.md) — decisão técnica COSMIC/Wayland
- [CHANGELOG](../../CHANGELOG.md) — histórico completo

O diário de descobertas e o roadmap interno ficam no arquivo de processo, fora
da `main` (`git show arquivo/processo-pre-1.0:docs/process/ROADMAP.md`). Essa
tag só existe no fork — se o comando acima disser "unknown revision", veja como
buscá-la na seção final do [`README.md`](../../README.md).
