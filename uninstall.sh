#!/usr/bin/env bash
# uninstall.sh - WIPE COMPLETO do Hefesto - Dualsense4Unix.
# Remove TUDO: artefatos do install, .deb (apt remove), Flatpak, AppImage
# em ~/Aplicativos, .venv, caches Python, configs, runtime, dados do user.
# Após rodar, o sistema fica como se Hefesto nunca tivesse sido instalado.
#
# Flags:
#   --udev      remove também as udev rules em /etc/udev/rules.d/ (requer sudo).
#   --keep-config preserva ~/.config/hefesto-dualsense4unix (perfis do user).
#   --yes,-y    responde 'sim' para prompts.

set -euo pipefail

readonly APP_ID="hefesto-dualsense4unix"
readonly DESKTOP_TARGET="${HOME}/.local/share/applications/${APP_ID}.desktop"
readonly ICON_TARGET="${HOME}/.local/share/icons/hicolor/256x256/apps/${APP_ID}.png"
readonly LAUNCHER="${HOME}/.local/bin/hefesto-dualsense4unix-gui"
readonly BIN_SYMLINK="${HOME}/.local/bin/hefesto-dualsense4unix"
readonly HOTPLUG_UNIT_TARGET="${HOME}/.config/systemd/user/hefesto-dualsense4unix-gui-hotplug.service"

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly VENV_HEFESTO="${ROOT_DIR}/.venv/bin/hefesto-dualsense4unix"

REMOVE_UDEV=0
KEEP_CONFIG=0
AUTO_YES=0
for arg in "$@"; do
    case "$arg" in
        --udev)         REMOVE_UDEV=1 ;;
        --keep-config)  KEEP_CONFIG=1 ;;
        --yes|-y)       AUTO_YES=1 ;;
        *) printf '[uninstall] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

log() { printf '[uninstall] %s\n' "$*"; }

log "parando daemon hefesto-dualsense4unix (se ativo)"
timeout 5 systemctl --user stop hefesto-dualsense4unix.service >/dev/null 2>&1 || true
systemctl --user disable hefesto-dualsense4unix.service >/dev/null 2>&1 || true
rm -f "${HOME}/.config/systemd/user/hefesto-dualsense4unix.service"
systemctl --user daemon-reload >/dev/null 2>&1 || true

# Mata GUIs e daemons órfãos — qualquer processo do hefesto, mesmo se rodando
# fora do systemd (CLI manual, hotplug-gui spawn, foreground dev).
#
# BUG-UNINSTALL-PKILL-SELF-01 (fix): patterns precisam ser **específicos**
# pra não casar o próprio uninstall.sh. Quando o script roda a partir de
# `/home/.../hefesto-dualsense4unix/uninstall.sh`, o cmdline do bash que o
# executa contém "hefesto-dualsense4unix" e `pkill -f 'hefesto-dualsense4unix'`
# se mata (exit 144). Os patterns abaixo casam só processos legítimos:
# `daemon ` (espaço final) cobre `daemon start/run`, `-gui` cobre o launcher,
# `_dualsense4unix` (underscore) cobre processos Python que importam o módulo.
log "matando processos hefesto*"
for pat in 'hefesto-dualsense4unix daemon ' 'hefesto-dualsense4unix-gui' 'hefesto_dualsense4unix' 'br\.andrefarias\.Hefesto'; do
    pkill -TERM -f "$pat" 2>/dev/null || true
done
sleep 2
for pat in 'hefesto-dualsense4unix daemon ' 'hefesto-dualsense4unix-gui' 'hefesto_dualsense4unix' 'br\.andrefarias\.Hefesto'; do
    pkill -KILL -f "$pat" 2>/dev/null || true
done

# Unit user de hotplug-gui (se existir)
if [[ -f "${HOTPLUG_UNIT_TARGET}" ]]; then
    log "desabilitando hefesto-dualsense4unix-gui-hotplug.service"
    systemctl --user disable hefesto-dualsense4unix-gui-hotplug.service >/dev/null 2>&1 || true
    log "removendo ${HOTPLUG_UNIT_TARGET}"
    rm -f "${HOTPLUG_UNIT_TARGET}"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
else
    log "ausente: ${HOTPLUG_UNIT_TARGET}"
fi

for path in "${DESKTOP_TARGET}" "${ICON_TARGET}" "${LAUNCHER}" "${BIN_SYMLINK}"; do
    if [[ -e "${path}" ]]; then
        log "removendo ${path}"
        rm -f "${path}"
    else
        log "ausente: ${path}"
    fi
done

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -f "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q "${HOME}/.local/share/applications" 2>/dev/null || true
fi

if [[ "${REMOVE_UDEV}" -eq 1 ]]; then
    if [[ "${AUTO_YES}" -eq 0 ]]; then
        read -r -n 1 -p "      remover udev rules de /etc/udev/rules.d/? [y/N] " resp
        echo
        resp="${resp:-N}"
    else
        resp="Y"
    fi
    if [[ "${resp,,}" =~ ^y(es)?$ ]]; then
        log "removendo udev rules (sudo)"
        sudo rm -f /etc/udev/rules.d/70-ps5-controller.rules \
                   /etc/udev/rules.d/71-uinput.rules \
                   /etc/udev/rules.d/72-ps5-controller-autosuspend.rules \
                   /etc/udev/rules.d/73-ps5-controller-hotplug.rules \
                   /etc/modules-load.d/hefesto-dualsense4unix.conf 2>/dev/null || true
        sudo udevadm control --reload-rules 2>/dev/null || true
        sudo udevadm trigger --action=change --subsystem-match=usb 2>/dev/null || true
    else
        log "udev rules preservadas (rode com --udev --yes para forcar)"
    fi
fi

if [[ -d "${ROOT_DIR}/.venv" ]]; then
    log "removendo .venv"
    rm -rf "${ROOT_DIR}/.venv"
fi

# Caches Python e build (deixar resíduos quebra reinstall com module-rename).
for cache in .pytest_cache .ruff_cache .mypy_cache flatpak-build-dir .flatpak-builder dist build; do
    if [[ -d "${ROOT_DIR}/${cache}" ]]; then
        log "removendo ${cache}"
        rm -rf "${ROOT_DIR}/${cache}"
    fi
done

# Bytecode espalhado: __pycache__/ em src/ tests/ scripts/
find "${ROOT_DIR}" -type d -name "__pycache__" \
    -not -path "*/\.git/*" \
    -exec rm -rf {} + 2>/dev/null || true
find "${ROOT_DIR}" -type f -name "*.pyc" \
    -not -path "*/\.git/*" \
    -delete 2>/dev/null || true

# .deb instalado via apt: sudo apt remove (idempotente — silencioso se ausente).
if dpkg -l hefesto-dualsense4unix >/dev/null 2>&1; then
    log "removendo pacote .deb hefesto-dualsense4unix (sudo)"
    sudo apt-get remove -y hefesto-dualsense4unix >/dev/null 2>&1 || true
fi

# Flatpak: desinstalar app + cleanup runtime (mas não remove runtime GNOME
# se outras apps usam — flatpak gerencia rc).
if flatpak list --user --app 2>/dev/null | grep -q "br.andrefarias.Hefesto"; then
    log "desinstalando Flatpak br.andrefarias.Hefesto"
    flatpak uninstall --user -y br.andrefarias.Hefesto >/dev/null 2>&1 || true
fi
# Cache flatpak do app (logs, dados em runtime/sandbox)
rm -rf "${HOME}/.var/app/br.andrefarias.Hefesto" 2>/dev/null || true

# AppImage em locais convencionais
for appimg_dir in "${HOME}/Aplicativos" "${HOME}/Applications" "${HOME}/Downloads"; do
    [[ -d "$appimg_dir" ]] || continue
    for f in "$appimg_dir"/Hefesto-Dualsense4Unix*.AppImage "$appimg_dir"/hefesto-dualsense4unix*.AppImage; do
        if [[ -f "$f" ]]; then
            log "removendo AppImage ${f}"
            rm -f "$f"
        fi
    done
done

# Configs e dados do user (opt-out via --keep-config)
if [[ "${KEEP_CONFIG}" -eq 0 ]]; then
    for path in \
        "${HOME}/.config/hefesto-dualsense4unix" \
        "${HOME}/.local/share/hefesto-dualsense4unix" \
        "${HOME}/.cache/hefesto-dualsense4unix"; do
        if [[ -d "$path" ]]; then
            log "removendo ${path}"
            rm -rf "$path"
        fi
    done
else
    log "configs preservadas (--keep-config): ~/.config/hefesto-dualsense4unix"
fi

# BUG-UNINSTALL-LOCALE-NOT-REMOVED-01 (fix): catalogos .mo do install.sh
# step 4d (FEAT-I18N-CATALOGS-01) ficavam orfaos em ~/.local/share/locale/
# <lang>/LC_MESSAGES/. Removemos so o nosso domain (`hefesto-dualsense4unix.mo`),
# nunca o LC_MESSAGES/ ou <lang>/ inteiro — outros apps podem usar.
log "removendo catalogos i18n .mo do user"
for lang_dir in "${HOME}/.local/share/locale"/*/; do
    [[ -d "$lang_dir" ]] || continue
    mo="${lang_dir}LC_MESSAGES/${APP_ID}.mo"
    if [[ -f "$mo" ]]; then
        log "  ${mo}"
        rm -f "$mo"
    fi
done

# Runtime dir do socket IPC e pid files (sempre limpa, é volátil)
runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hefesto-dualsense4unix"
if [[ -d "$runtime_dir" ]]; then
    log "removendo ${runtime_dir}"
    rm -rf "$runtime_dir"
fi

# Pip user packages (deps modernas que install.sh ou usuário possa ter colocado)
# Não removidas por default — podem ser usadas por outros apps. Deixar como
# nota informativa.
log "(nota) deps Python via pip --user em ~/.local/lib/python*/site-packages preservadas"
log "       — remova manualmente se quiser wipe absoluto do user-site"

printf '\n─────────────────────────────────────────\n'
printf ' Hefesto - Dualsense4Unix desinstalado (wipe completo)\n'
printf '─────────────────────────────────────────\n\n'
