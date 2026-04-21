#!/usr/bin/env bash
# uninstall.sh - remove os artefatos criados pelo install.sh.
# Nao toca no .venv/ (o usuario pode querer manter o ambiente dev).
# Para wipe completo: `rm -rf .venv` manualmente.

set -euo pipefail

readonly APP_ID="hefesto"
readonly DESKTOP_TARGET="${HOME}/.local/share/applications/${APP_ID}.desktop"
readonly ICON_TARGET="${HOME}/.local/share/icons/hicolor/256x256/apps/${APP_ID}.png"
readonly LAUNCHER="${HOME}/.local/bin/hefesto-gui"
readonly BIN_SYMLINK="${HOME}/.local/bin/hefesto"

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly VENV_HEFESTO="${ROOT_DIR}/.venv/bin/hefesto"

log() { printf '[uninstall] %s\n' "$*"; }

if [[ -x "${VENV_HEFESTO}" ]]; then
    log "desinstalando unit systemd --user (se existir)"
    "${VENV_HEFESTO}" daemon stop >/dev/null 2>&1 || true
    "${VENV_HEFESTO}" daemon uninstall-service >/dev/null 2>&1 || true
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

log "OK. Para remover o venv local: rm -rf .venv"
