# Hefesto no COSMIC DE (Pop!_OS 24.04, Wayland)

Guia de uso do Hefesto no ambiente COSMIC, o desktop Wayland nativo do Pop!_OS.

---

## Estado atual do suporte

| Recurso | Estado | Observacao |
|---|---|---|
| Deteccao DualSense USB/BT | OK | evdev, independente de display |
| Polling de botoes/eixos | OK | hidraw, independente de display |
| Hotkeys globais | OK | /dev/input, independente de display |
| Mouse emulado (uinput) | OK | nivel kernel |
| Autoswitch de perfil | Parcial | ver secao abaixo |
| GUI GTK3 | OK via XWayland | XWayland ativado por padrao no COSMIC |
| Tray AppIndicator | OK via XWayland | Ayatana funciona em XWayland |
| Applet nativo COSMIC panel | Nao implementado | V1.2, sprint futura |

---

## Autoswitch de perfil no COSMIC

O Hefesto detecta automaticamente o backend de janela ativa com base nas
variaveis de ambiente do compositor:

### Cenario 1 — XWayland ativo (padrao no COSMIC 1.0+)

Quando `DISPLAY` e `WAYLAND_DISPLAY` estao presentes simultaneamente (XWayland
em execucao), o Hefesto usa o backend X11 (`XlibBackend`). O autoswitch de
perfil funciona normalmente.

Verificar:
```bash
echo "DISPLAY=$DISPLAY  WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
```

Esperado: ambas as variaveis preenchidas.

### Cenario 2 — Wayland puro (sem XWayland)

Quando apenas `WAYLAND_DISPLAY` esta presente, o Hefesto tenta usar o portal
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

O Hefesto inicia em modo silencioso. Daemon e polling funcionam; GUI nao abre.

---

## Instalacao no COSMIC

```bash
git clone https://github.com/AndreBFarias/hefesto
cd hefesto
./install.sh
```

O instalador detecta automaticamente se o sistema usa systemd user session e
oferece instalar o servico de daemon.

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

As ferramentas X11 (`scrot`, `import`) nao funcionam em Wayland puro. Use:

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

- **AppIndicator nao aparece no painel COSMIC nativo**: o COSMIC usa uma API de
  applet propria (cosmic-panel). O tray Ayatana funciona via XWayland, mas pode
  nao integrar ao painel nativo do COSMIC. Contorno: usar apenas a janela GTK3
  ou a CLI (`hefesto status`). Integracao nativa esta planejada para V1.2.

- **Portal GetActiveWindow nao disponivel**: compositors Wayland que nao
  implementam `org.freedesktop.portal.Window` (Sway, Hyprland, COSMIC < 1.0)
  resultam em autoswitch silencioso. Funcionalidade completa requer XWayland
  ativo ou portal disponivel.
