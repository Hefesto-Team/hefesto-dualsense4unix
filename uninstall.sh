#!/usr/bin/env bash
# uninstall.sh - remove os artefatos criados pelo install.sh.
# Não toca no .venv/ (o usuário pode querer manter o ambiente dev).
# Para wipe completo: `rm -rf .venv` manualmente.
#
# Flags:
#   --udev   remove também as udev rules em /etc/udev/rules.d/ (requer sudo).
#   --yes,-y responde 'sim' para prompts.

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
AUTO_YES=0
for arg in "$@"; do
    case "$arg" in
        --udev)   REMOVE_UDEV=1 ;;
        --yes|-y) AUTO_YES=1 ;;
        *) printf '[uninstall] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

log() { printf '[uninstall] %s\n' "$*"; }

log "parando daemon hefesto-dualsense4unix (se ativo)"
timeout 5 systemctl --user stop hefesto-dualsense4unix.service >/dev/null 2>&1 || true
systemctl --user disable hefesto-dualsense4unix.service >/dev/null 2>&1 || true
rm -f "${HOME}/.config/systemd/user/hefesto-dualsense4unix.service"
systemctl --user daemon-reload >/dev/null 2>&1 || true

# BUG-MULTI-INSTANCE-01: garantia extra — mata GUIs e daemons órfãos que
# possam ter escapado do systemctl stop (ex.: processo lançado fora do
# systemd, ou residual de sessão anterior).
pkill -TERM -f 'hefesto_dualsense4unix\.app\.main' 2>/dev/null || true
pkill -TERM -f 'hefesto-dualsense4unix daemon start' 2>/dev/null || true
sleep 2
pkill -KILL -f 'hefesto_dualsense4unix\.app\.main' 2>/dev/null || true
pkill -KILL -f 'hefesto-dualsense4unix daemon start' 2>/dev/null || true

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

printf '\n─────────────────────────────────────────\n'
printf ' Hefesto - Dualsense4Unix desinstalado\n'
printf '─────────────────────────────────────────\n\n'
