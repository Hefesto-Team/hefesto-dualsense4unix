# Hefesto - Dualsense4Unix no COSMIC DE (Pop!_OS 24.04, Wayland)

Guia de uso do Hefesto - Dualsense4Unix no ambiente COSMIC, o desktop Wayland nativo do Pop!_OS.

---

## Estado atual do suporte (v3.8.1)

| Recurso | Estado | Observação |
|---|---|---|
| Deteccao DualSense USB/BT | OK | evdev, independente de display |
| Polling de botoes/eixos | OK | hidraw, independente de display |
| Hotkeys globais | OK | /dev/input, independente de display; long-press do PS = modo jogo (v3.8.1) |
| Mouse emulado (uinput) | OK | nivel kernel; suprimível pelo modo jogo |
| Autoswitch de perfil | Parcial | XWayland OK; Wayland puro depende do portal — ver seção abaixo |
| GUI GTK3 | OK via XWayland | dropdown Drácula legível (v3.8.1); sem busy-loop de CPU (v3.8.1) |
| Tray AppIndicator | OK via XWayland | Ayatana funciona em XWayland |
| **Applet nativo COSMIC panel** | **OK** | Rust + libcosmic (v3.6); aparece em Miniaplicativos com `X-HostWaylandDisplay=true` + PNG 256x256 (v3.8.0) |
| **Modo jogo (long-press PS)** | **OK (v3.8.1)** | Segurar PS ~1s alterna a supressão da emulação mouse/teclado mantendo hotkeys |

---

## Autoswitch de perfil no COSMIC

O Hefesto - Dualsense4Unix detecta automaticamente o backend de janela ativa com base nas
variaveis de ambiente do compositor:

### Cenario 1 — XWayland ativo (padrão no COSMIC 1.0+)

Quando `DISPLAY` e `WAYLAND_DISPLAY` estao presentes simultaneamente (XWayland
em execução), o Hefesto - Dualsense4Unix usa o backend X11 (`XlibBackend`). O autoswitch de
perfil funciona normalmente.

Verificar:
```bash
echo "DISPLAY=$DISPLAY  WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
```

Esperado: ambas as variaveis preenchidas.

### Cenario 2 — Wayland puro (sem XWayland)

Quando apenas `WAYLAND_DISPLAY` esta presente, o Hefesto - Dualsense4Unix tenta usar o portal
XDG D-Bus `org.freedesktop.portal.Window.GetActiveWindow` (disponivel no
COSMIC 1.0+ e GNOME 46+).

Para que o portal funcione, instale uma das bibliotecas opcionais:

```bash
# Opcao A: jeepney (puro Python, recomendado)
.venv/bin/pip install jeepney

# Opcao B: dbus-fast (assincrono)
.venv/bin/pip install dbus-fast
```

Se nenhuma biblioteca estiver disponivel, o autoswitch fica em modo silencioso
(sempre usa `fallback.json`). O log mostra `autoswitch_compositor_unsupported`.

### Cenario 3 — Sem display (servidor headless)

O Hefesto - Dualsense4Unix inicia em modo silencioso. Daemon e polling funcionam; GUI não abre.

---

## Instalação no COSMIC

```bash
# Clone do repositório (veja a página principal para a URL atual)
cd hefesto-dualsense4unix
./install.sh --yes --enable-cosmic-applet --with-wireplumber-fix --enable-hotplug-gui
```

Flags relevantes no COSMIC:

- `--enable-cosmic-applet` — compila e instala o applet nativo em Rust/libcosmic. Sem isso, o
  Hefesto fica acessível só pela GUI GTK3 (XWayland) e pelo tray Ayatana (se o
  `cosmic-applet-status-area` estiver habilitado em Configurações > Painel > Miniaplicativos).
- `--with-wireplumber-fix` — instala o drop-in que impede o DualSense de virar o microfone padrão
  (problema clássico do `wireplumber.conf` ao plugar o controle).
- `--keep-steam-input` — opt-out do desligamento default de `SteamController_PSSupport`. Sem essa
  flag, o install zera as toggles do Steam Input nos `localconfig.vdf` para evitar conflito Steam
  Input vs daemon. Vide [troubleshooting seção 12](troubleshooting.md).
- `--enable-hotplug-gui` — copia a unit `hefesto-dualsense4unix-gui-hotplug.service` que abre a
  GUI automaticamente ao plugar/parear o controle.

Após instalar o applet, recarregue o painel: `killall cosmic-panel`. Ele reaparece no segundo
seguinte e o Hefesto deve aparecer em **Configurações > Painel > Miniaplicativos**.

---

## Verificar backend ativo

No log do daemon (journal ou stdout com `--dev`):

```
# Backend X11 (XWayland ou X11 puro):
window_backend_selected backend=xlib xwayland=True

# Backend Wayland portal:
window_backend_selected backend=wayland_portal

# Modo silencioso (sem display):
autoswitch_compositor_unsupported
```

---

## Captura de tela no COSMIC (Wayland)

As ferramentas X11 (`scrot`, `import`) não funcionam em Wayland puro. Use:

```bash
# Captura de regiao (requer grim + slurp)
grim -g "$(slurp)" /tmp/hefesto_captura.png

# Captura de tela completa
grim /tmp/hefesto_tela.png
```

Instalar no Pop!_OS:
```bash
sudo apt install grim slurp
```

---

## Problemas conhecidos

- **Applet COSMIC ausente em Miniaplicativos (resolvido em v3.8.0)**: o `.desktop` do applet
  precisa de `X-HostWaylandDisplay=true` + um ícone PNG 256x256, e o `cosmic-panel` precisa ser
  recarregado (`killall cosmic-panel`) após instalar. O `install.sh --enable-cosmic-applet` faz
  isso. Se o applet não aparecer, conferir com `ls /usr/local/bin/hefesto-dualsense4unix-applet
  /usr/share/applications/com.vitoriamaria.HefestoDualsense4Unix.desktop` — ambos devem existir.

- **`wlrctl` não funciona no COSMIC**: o cosmic-comp não implementa
  `wlr-foreign-toplevel-management-unstable-v1`, então `wlrctl toplevel list --json` retorna
  vazio. Isso afeta o autoswitch em Wayland **puro** — em XWayland (default no COSMIC 1.0+), o
  `XlibBackend` funciona normalmente.

- **Portal GetActiveWindow não disponivel**: compositors Wayland que não
  implementam `org.freedesktop.portal.Window` (Sway, Hyprland, COSMIC < 1.0)
  resultam em autoswitch silencioso. Funcionalidade completa requer XWayland
  ativo ou portal disponivel.

- **Tray AppIndicator some no COSMIC**: o `cosmic-applet-status-area` pode estar desabilitado em
  Configurações > Painel > Miniaplicativos. Habilite-o ou use o **applet nativo COSMIC** (preferível
  no COSMIC — fala direto com o daemon via IPC JSON-RPC e tem ações de Pausar/Retomar + Modo jogo
  no popover).
