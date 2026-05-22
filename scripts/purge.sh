#!/usr/bin/env bash
# purge.sh — descontaminação TOTAL do Hefesto - Dualsense4Unix.
#
# Remove TODAS as formas de instalação que possam ter sido misturadas no mesmo
# host (nativo + .deb + Flatpak + AppImage + applet COSMIC), incluindo rastros
# que versões antigas do uninstall.sh não cobriam (applet em /usr/local, regra
# udev 74, ghost do hotplug systemd). Idempotente e seguro.
#
# Por padrão PRESERVA a config do usuário (perfis/sessão/preferências) e faz um
# backup dela. Use --with-config para apagar a config também.
#
# Flags:
#   --yes, -y       não pergunta nada (assume sim).
#   --dry-run       só imprime o que faria, sem executar.
#   --with-config   apaga também a config do usuário (uninstall --purge-config).
#
# A senha de sudo é pedida pelo próprio sudo quando necessário (udev, /usr/local,
# apt). CHORE-PURGE-ALL-INSTALL-FORMS-01.

set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly UNINSTALL="${ROOT_DIR}/uninstall.sh"

AUTO_YES=0
DRY_RUN=0
WITH_CONFIG=0
for arg in "$@"; do
    case "$arg" in
        --yes|-y)       AUTO_YES=1 ;;
        --dry-run)      DRY_RUN=1 ;;
        --with-config)  WITH_CONFIG=1 ;;
        *) printf '[purge] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

log() { printf '[purge] %s\n' "$*"; }
run() {
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        printf '[purge][dry-run] %s\n' "$*"
    else
        "$@"
    fi
}

# 1) Backup dos perfis do usuário (curto + longo), independente de --with-config.
backup_profiles() {
    local stamp dest src found
    stamp="$(date +%s)"
    dest="${HOME}/.config/hefesto-dualsense4unix.backup-${stamp}"
    found=0
    for src in "${HOME}/.config/hefesto" "${HOME}/.config/hefesto-dualsense4unix"; do
        if [[ -d "${src}/profiles" || -f "${src}/session.json" ]]; then
            run mkdir -p "${dest}"
            run cp -a "${src}" "${dest}/$(basename "${src}")"
            found=1
        fi
    done
    if [[ "${found}" -eq 1 ]]; then
        log "backup de perfis em ${dest}"
    else
        log "nenhum perfil de usuário para backup"
    fi
}

# 2) uninstall.sh cobre nativo/.deb/flatpak/appimage/applet/udev/config.
run_uninstall() {
    local cfg_flag="--keep-config"
    [[ "${WITH_CONFIG}" -eq 1 ]] && cfg_flag="--purge-config"
    if [[ ! -f "${UNINSTALL}" ]]; then
        log "ERRO: uninstall.sh não encontrado em ${UNINSTALL}"
        return 1
    fi
    log "executando uninstall.sh --udev ${cfg_flag} --yes"
    run bash "${UNINSTALL}" --udev "${cfg_flag}" --yes
}

# 3) Reforço: rastros que versões antigas do uninstall.sh não removiam.
reinforce_leftovers() {
    local applet_bin applet_desktop applet_icon ghost
    applet_bin="/usr/local/bin/hefesto-dualsense4unix-applet"
    applet_desktop="/usr/share/applications/com.vitoriamaria.HefestoDualsense4Unix.desktop"
    applet_icon="/usr/share/icons/hicolor/scalable/apps/com.vitoriamaria.HefestoDualsense4Unix-symbolic.svg"
    if [[ -e "${applet_bin}" || -e "${applet_desktop}" || -e "${applet_icon}" ]]; then
        log "reforço: removendo applet COSMIC remanescente (sudo)"
        run sudo rm -f "${applet_bin}" "${applet_desktop}" "${applet_icon}"
        run sudo gtk-update-icon-cache -q -f /usr/share/icons/hicolor 2>/dev/null || true
        run sudo update-desktop-database -q /usr/share/applications 2>/dev/null || true
    fi
    if [[ -e /etc/udev/rules.d/74-ps5-controller-hotplug-bt.rules || -e /etc/modules-load.d/hefesto-dualsense4unix.conf ]]; then
        log "reforço: removendo regra udev 74 + modules-load (sudo)"
        run sudo rm -f /etc/udev/rules.d/74-ps5-controller-hotplug-bt.rules \
                       /etc/modules-load.d/hefesto-dualsense4unix.conf
        run sudo udevadm control --reload-rules 2>/dev/null || true
    fi
    ghost="${HOME}/.config/systemd/user/hefesto-dualsense4unix-gui-hotplug.service"
    if [[ -f "${ghost}" ]]; then
        log "reforço: removendo ghost do hotplug systemd --user"
        run systemctl --user disable --now hefesto-dualsense4unix-gui-hotplug.service 2>/dev/null || true
        run rm -f "${ghost}"
        run systemctl --user daemon-reload 2>/dev/null || true
    fi
}

# 4) .deb: purge (não só remove) p/ limpar conffiles, se instalado.
purge_deb() {
    if dpkg -l hefesto-dualsense4unix >/dev/null 2>&1; then
        log "purge do pacote .deb (sudo apt-get purge)"
        run sudo apt-get purge -y hefesto-dualsense4unix 2>/dev/null || true
    fi
}

# 5) Flatpak: garantir remoção (uninstall já tenta; reforço aqui).
purge_flatpak() {
    if flatpak list --app 2>/dev/null | grep -q "br.andrefarias.Hefesto"; then
        log "desinstalando Flatpak br.andrefarias.Hefesto"
        run flatpak uninstall -y br.andrefarias.Hefesto 2>/dev/null || true
    fi
}

main() {
    log "início (dry-run=${DRY_RUN}, with-config=${WITH_CONFIG})"
    if [[ "${AUTO_YES}" -eq 0 && "${DRY_RUN}" -eq 0 ]]; then
        read -r -n 1 -p "[purge] descontaminar TODAS as formas do Hefesto agora? [y/N] " resp
        echo
        [[ "${resp,,}" =~ ^y(es)?$ ]] || { log "abortado pelo usuário"; exit 0; }
    fi
    backup_profiles
    run_uninstall
    reinforce_leftovers
    purge_deb
    purge_flatpak
    printf '\n─────────────────────────────────────────\n'
    printf ' Hefesto - Dualsense4Unix: descontaminação concluída.\n'
    if [[ "${WITH_CONFIG}" -eq 0 ]]; then
        printf ' Perfis preservados (~/.config/hefesto + backup criado).\n'
    fi
    printf '─────────────────────────────────────────\n\n'
}

main
