#!/usr/bin/env bash
# uninstall.sh - WIPE do Hefesto - Dualsense4Unix.
# Remove artefatos do install nativo, o applet COSMIC, .deb (apt remove),
# Flatpak, AppImage em ~/Aplicativos, .venv, caches Python, runtime e dados.
#
# Config do usuário (perfis, sessão, preferências) é PRESERVADA por padrão e,
# quando apagada, é antes copiada para um backup. Cobre tanto o caminho atual
# (~/.config/hefesto-dualsense4unix) quanto o legado curto (~/.config/hefesto).
#
# Flags:
#   --udev          remove também as udev rules em /etc/udev/rules.d/ (sudo).
#   --purge-config  APAGA a config do usuário (com backup antes). Default: preserva.
#   --keep-config   preserva a config (default; mantido por retrocompatibilidade).
#   --yes,-y        responde 'sim' para prompts.

set -euo pipefail

readonly APP_ID="hefesto-dualsense4unix"
readonly DESKTOP_TARGET="${HOME}/.local/share/applications/${APP_ID}.desktop"
readonly ICON_TARGET="${HOME}/.local/share/icons/hicolor/256x256/apps/${APP_ID}.png"
readonly LAUNCHER="${HOME}/.local/bin/hefesto-dualsense4unix-gui"
readonly BIN_SYMLINK="${HOME}/.local/bin/hefesto-dualsense4unix"
readonly HOTPLUG_UNIT_TARGET="${HOME}/.config/systemd/user/hefesto-dualsense4unix-gui-hotplug.service"

# Artefatos do applet COSMIC (instalados por packaging/cosmic-applet via sudo).
# O uninstall nativo não os conhecia → sobreviviam ao wipe (rastro deixado).
readonly APPLET_BIN="/usr/local/bin/hefesto-dualsense4unix-applet"
readonly APPLET_DESKTOP="/usr/share/applications/com.vitoriamaria.HefestoDualsense4Unix.desktop"
readonly APPLET_ICON="/usr/share/icons/hicolor/scalable/apps/com.vitoriamaria.HefestoDualsense4Unix-symbolic.svg"
readonly APPLET_ICON_PNG="/usr/share/icons/hicolor/256x256/apps/com.vitoriamaria.HefestoDualsense4Unix.png"
# Drop-in do WirePlumber (fix de microfone) — só o nosso arquivo, nunca o dir.
readonly WIREPLUMBER_DROPIN="${HOME}/.config/wireplumber/wireplumber.conf.d/51-hefesto-dualsense-no-default-source.conf"

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly VENV_HEFESTO="${ROOT_DIR}/.venv/bin/hefesto-dualsense4unix"

REMOVE_UDEV=0
KEEP_CONFIG=1   # preserva config por padrão (perfis do user) — apagar exige --purge-config
AUTO_YES=0
for arg in "$@"; do
    case "$arg" in
        --udev)          REMOVE_UDEV=1 ;;
        --purge-config)  KEEP_CONFIG=0 ;;
        --keep-config)   KEEP_CONFIG=1 ;;
        --yes|-y)        AUTO_YES=1 ;;
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

# FEAT-ICON-MULTI-RES-01 (fix): install.sh gera PNGs em 11 resolucoes
# (16/22/24/32/48/64/96/128/192/256/512) + SVG escalavel + pixmap
# legacy. Limpa todos. Nunca remove dirs `<size>x<size>/apps/` (outros
# apps usam).
log "removendo icones multi-res hicolor + SVG + pixmap"
for size in 16 22 24 32 48 64 96 128 192 256 512; do
    rm -f "${HOME}/.local/share/icons/hicolor/${size}x${size}/apps/${APP_ID}.png"
done
rm -f "${HOME}/.local/share/icons/hicolor/scalable/apps/${APP_ID}.svg"
rm -f "${HOME}/.local/share/pixmaps/${APP_ID}.png"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -f "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q "${HOME}/.local/share/applications" 2>/dev/null || true
fi

# Applet COSMIC nativo (Rust): instalado em /usr/local + /usr/share via sudo
# por packaging/cosmic-applet. Remove só se existir (evita pedir sudo à toa).
if [[ -e "${APPLET_BIN}" || -e "${APPLET_DESKTOP}" || -e "${APPLET_ICON}" || -e "${APPLET_ICON_PNG}" ]]; then
    log "removendo applet COSMIC (sudo): binário + .desktop + ícones"
    sudo rm -f "${APPLET_BIN}" "${APPLET_DESKTOP}" "${APPLET_ICON}" "${APPLET_ICON_PNG}" 2>/dev/null || true
    sudo gtk-update-icon-cache -q -f /usr/share/icons/hicolor 2>/dev/null || true
    sudo update-desktop-database -q /usr/share/applications 2>/dev/null || true
    # cosmic-panel só relê a lista de applets ao reiniciar — sem isso o applet
    # fica fantasma na lista de Miniaplicativos mesmo após remover os arquivos.
    command -v killall >/dev/null 2>&1 && killall cosmic-panel 2>/dev/null || true
fi

# Drop-in do WirePlumber (fix de microfone). Remove só o nosso arquivo, nunca
# o diretório wireplumber.conf.d/ (outros apps/usuário podem ter configs lá).
if [[ -f "${WIREPLUMBER_DROPIN}" ]]; then
    log "removendo drop-in WirePlumber: ${WIREPLUMBER_DROPIN}"
    rm -f "${WIREPLUMBER_DROPIN}"
    systemctl --user restart wireplumber >/dev/null 2>&1 || true
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
                   /etc/udev/rules.d/74-ps5-controller-hotplug-bt.rules \
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

# Configs e dados do user. PRESERVADOS por padrão; --purge-config apaga (com
# backup antes). Cobre o caminho atual (longo) E o legado curto (~/.config/
# hefesto), onde versões pré-rename gravavam perfis/sessão/preferências.
if [[ "${KEEP_CONFIG}" -eq 0 ]]; then
    backup_dir="${HOME}/.config/hefesto-dualsense4unix.backup-$(date +%s)"
    backed_up=0
    for path in \
        "${HOME}/.config/hefesto-dualsense4unix" \
        "${HOME}/.local/share/hefesto-dualsense4unix" \
        "${HOME}/.cache/hefesto-dualsense4unix" \
        "${HOME}/.config/hefesto" \
        "${HOME}/.local/share/hefesto" \
        "${HOME}/.cache/hefesto"; do
        if [[ -d "$path" ]]; then
            mkdir -p "${backup_dir}"
            rel="${path#"${HOME}"/}"
            cp -a "$path" "${backup_dir}/${rel//\//_}" 2>/dev/null || true
            backed_up=1
            log "removendo ${path}"
            rm -rf "$path"
        fi
    done
    [[ "${backed_up}" -eq 1 ]] && log "backup da config em ${backup_dir}"
else
    log "configs preservadas (default): ~/.config/hefesto + ~/.config/hefesto-dualsense4unix"
    log "  (use --purge-config para apagar, com backup automático)"
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
