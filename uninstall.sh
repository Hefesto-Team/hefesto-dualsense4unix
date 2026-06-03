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
#   --keep-udev          PRESERVA udev rules + modules-load (default: remove, sudo).
#   --udev               [DEPRECATED] no-op — remoção é default desde v3.8.3.
#   --purge-config       APAGA a config do usuário (com backup antes). Default: preserva.
#   --keep-config        preserva a config (default; mantido por retrocompatibilidade).
#   --keep-steam-input   PRESERVA Steam Input PSSupport (default: desliga em TODOS os
#                        localconfig.vdf de todos os Steam users em todos os formatos).
#                        Simétrico ao install.sh — se sai sem desligar, o sintoma
#                        "controle vira mouse / botões em background" volta na hora.
#                        Reverter desligamento: scripts/disable_steam_input.sh --restore.
#   --yes,-y             responde 'sim' para prompts.
#
# BUG-UNINSTALL-UDEV-DEFAULT-01 (fix): install.sh aplica as 5 udev rules + modules-
# load por default (--no-udev é o opt-out). Symmetric, o uninstall.sh deve REMOVER
# por default. Versões anteriores exigiam --udev explícito, deixando 6 arquivos no
# /etc/ que continuavam disparando hotplug-units inexistentes ao plugar o controle.
#
# FEAT-DISABLE-STEAM-INPUT-PSSUPPORT-01: install.sh, por default, desliga Steam
# Input PSSupport+UseSteamControllerConfig em todos os localconfig.vdf para evitar
# conflito Steam-vs-daemon. O uninstall, simétrico, repete o desligar — porque sem
# o daemon do Hefesto domesticando o DualSense, Steam Input PSSupport=2 reproduz
# imediatamente os 3 sintomas (touchpad → cursor, mic spam, botões em background)
# que motivam o usuário a desinstalar.

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
# Variante --disable-source (node.disabled). Removida incondicionalmente (não tem
# caso de "workaround standalone" — é gerada só pelo nosso --disable-source).
readonly WIREPLUMBER_DROPIN_DISABLE="${HOME}/.config/wireplumber/wireplumber.conf.d/52-hefesto-dualsense-disable-source.conf"

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly VENV_HEFESTO="${ROOT_DIR}/.venv/bin/hefesto-dualsense4unix"

# Default: remove udev rules + modules-load (espelha install.sh, que aplica por default).
# Ver BUG-UNINSTALL-UDEV-DEFAULT-01 no cabeçalho.
REMOVE_UDEV=1
KEEP_CONFIG=1            # preserva config por padrão (perfis do user) — apagar exige --purge-config
KEEP_STEAM_INPUT=0       # desliga Steam Input PSSupport por default (FEAT-DISABLE-STEAM-INPUT-PSSUPPORT-01)
AUTO_YES=0
for arg in "$@"; do
    case "$arg" in
        --keep-udev)         REMOVE_UDEV=0 ;;
        --udev)              REMOVE_UDEV=1 ;;  # deprecated: já é default; mantido p/ compat
        --purge-config)      KEEP_CONFIG=0 ;;
        --keep-config)       KEEP_CONFIG=1 ;;
        --keep-steam-input)  KEEP_STEAM_INPUT=1 ;;
        --yes|-y)            AUTO_YES=1 ;;
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

# Guard do Steam Input (path + timer, --user) — FEAT-STEAM-INPUT-SELF-HEAL-01
log "removendo guard do Steam Input (path/timer/service --user)"
systemctl --user disable --now hefesto-steam-input-guard.path hefesto-steam-input-guard.timer >/dev/null 2>&1 || true
rm -f "${HOME}/.config/systemd/user/hefesto-steam-input-guard.path" \
      "${HOME}/.config/systemd/user/hefesto-steam-input-guard.timer" \
      "${HOME}/.config/systemd/user/hefesto-steam-input-guard.service"
systemctl --user daemon-reload >/dev/null 2>&1 || true

# Watcher de auto-recuperação (serviço de sistema/root) — FEAT-DSX-RECOVER-01
if [[ -e /etc/systemd/system/hefesto-dsx-recover.service ]]; then
    log "removendo watcher hefesto-dsx-recover.service (precisa sudo)"
    sudo systemctl disable --now hefesto-dsx-recover.service >/dev/null 2>&1 || true
    sudo rm -f /etc/systemd/system/hefesto-dsx-recover.service /usr/local/sbin/dsx_recover.sh || true
    sudo systemctl daemon-reload >/dev/null 2>&1 || true
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
#
# BUG-UNINSTALL-WIREPLUMBER-WORKAROUND-PRESERVE-01 (fix): se o header do drop-in
# contiver o marker "Recriado manualmente" (ou "Recriado manualmente apos"), o
# usuário decidiu mantê-lo como workaround standalone (sem o daemon do hefesto).
# Nesse caso, preservamos — caso contrário, removemos como antes. O reinstall
# sobrescreve com a versão canônica do hefesto via --with-wireplumber-fix.
if [[ -f "${WIREPLUMBER_DROPIN}" ]]; then
    if head -5 "${WIREPLUMBER_DROPIN}" 2>/dev/null | grep -qiE 'recriado manualmente|workaround|standalone'; then
        log "preservando drop-in WirePlumber (marker 'recriado manualmente' no header)"
        log "  ${WIREPLUMBER_DROPIN}"
        log "  remova manualmente se não quiser mais o filtro do DualSense"
    else
        log "removendo drop-in WirePlumber: ${WIREPLUMBER_DROPIN}"
        rm -f "${WIREPLUMBER_DROPIN}"
        systemctl --user restart wireplumber >/dev/null 2>&1 || true
    fi
fi
# Variante --disable-source (52): remove incondicional + restart (simetria com
# o --with-wireplumber-disable-mic do install.sh).
if [[ -f "${WIREPLUMBER_DROPIN_DISABLE}" ]]; then
    log "removendo drop-in WirePlumber (disable-source): ${WIREPLUMBER_DROPIN_DISABLE}"
    rm -f "${WIREPLUMBER_DROPIN_DISABLE}"
    systemctl --user restart wireplumber >/dev/null 2>&1 || true
fi

if [[ "${REMOVE_UDEV}" -eq 1 ]]; then
    # Conjunto canônico sincronizado com scripts/install_udev.sh + install-host-udev.sh.
    # As 5 rules + modules-load uinput são SEMPRE instaladas em conjunto e devem
    # ser SEMPRE removidas em conjunto — não há combinação parcial suportada.
    #
    # BUG-UNINSTALL-SUDO-SILENT-FAIL-01 (fix): a versão anterior tinha
    # `sudo rm ... 2>/dev/null || true`, que mascarava falha de TTY para senha
    # (script chamado de subshell sem terminal) — log dizia "removendo" mas
    # nada saía. Agora cacheamos credenciais sudo upfront e falhamos visível
    # se sudo for recusado, mantendo idempotência em arquivo-ausente (rm -f).
    log "removendo udev rules + modules-load uinput (sudo)"
    if ! sudo -v 2>/dev/null; then
        log "ERRO: sudo recusado/sem TTY — udev rules NÃO foram removidas."
        log "      rode: sudo bash $0 ${*:-} (ou re-execute interativamente)"
    else
        sudo rm -f /etc/udev/rules.d/70-ps5-controller.rules \
                   /etc/udev/rules.d/71-uinput.rules \
                   /etc/udev/rules.d/72-ps5-controller-autosuspend.rules \
                   /etc/udev/rules.d/73-ps5-controller-hotplug.rules \
                   /etc/udev/rules.d/74-ps5-controller-hotplug-bt.rules \
                   /etc/udev/rules.d/75-ps5-controller-disable-usb-audio.rules \
                   /etc/modules-load.d/hefesto-dualsense4unix.conf
        sudo udevadm control --reload-rules
        # Re-trigger eventos para que devices PS5 já plugados percam os
        # atributos injetados pelas rules removidas (autosuspend forçado,
        # SYSTEMD_USER_WANTS de unit inexistente). Sem isso, comportamento
        # residual persiste até desplugar/replugar ou reboot.
        sudo udevadm trigger --action=change --subsystem-match=usb 2>/dev/null || true
        sudo udevadm trigger --action=change --subsystem-match=hidraw 2>/dev/null || true
    fi
else
    log "udev rules preservadas (--keep-udev). Para remover depois:"
    log "  sudo rm /etc/udev/rules.d/{70..74}-*ps5*.rules /etc/udev/rules.d/71-uinput.rules /etc/modules-load.d/hefesto-dualsense4unix.conf"
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

# Glyphs SVG copiados pelo install.sh (step 4b) — sao artefatos do pacote, não
# dados do usuário, entao removemos sempre (independente de --purge-config).
# BUG-UNINSTALL-GLYPHS-ORPHAN-01: ficavam em ~/.local/share/hefesto-dualsense4unix/
# glyphs/ apos uninstall, criando rastro.
if [[ -d "${HOME}/.local/share/hefesto-dualsense4unix/glyphs" ]]; then
    log "removendo glyphs do user"
    rm -rf "${HOME}/.local/share/hefesto-dualsense4unix/glyphs"
fi

# BUG-UNINSTALL-SHARE-DIR-ORPHAN-01 (fix): após remover glyphs/ (e quaisquer
# outros subdirs no futuro), o diretório-pai fica vazio mas presente, marcando
# ~/.local/share/hefesto-dualsense4unix/ como rastro órfão. Removemos só se
# estiver vazio — preserva dados se algo foi colocado lá fora do install.sh.
if [[ -d "${HOME}/.local/share/hefesto-dualsense4unix" ]] \
   && [[ -z "$(ls -A "${HOME}/.local/share/hefesto-dualsense4unix" 2>/dev/null)" ]]; then
    log "removendo diretório-pai vazio ~/.local/share/hefesto-dualsense4unix"
    rmdir "${HOME}/.local/share/hefesto-dualsense4unix" 2>/dev/null || true
fi

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
    # paused.flag (FEAT-DAEMON-PAUSE-RESUME-01) fica em ~/.config/hefesto-dualsense4unix/
    # e e propositalmente preservado junto com a config, para o usuário retomar
    # do mesmo estado se reinstalar. Use --purge-config para apaga-lo tambem.
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

# BUG-UNINSTALL-OUT-OF-SCOPE-CLARITY-01: documentar o que o uninstall
# explicitamente NÃO toca, pra evitar atribuição equivocada de problemas
# de outras toolchains ao hefesto.
log ""
log "fora do escopo (não removido — não é do hefesto):"
log "  /etc/udev/rules.d/99-usb-*.rules         — toolchain de power-mgmt do user (ex: Aurora self-heal)"
log "  /etc/udev/rules.d/99-storage-no-link-pm.rules — idem (storage PM)"
log "  /etc/udev/rules.d/50-system76-power.rules    — polkit pra system76-power (Pop_OS)"
log "  kernel cmdline (usbcore.autosuspend, pcie_aspm, etc.) — kernelstub/grub, não hefesto"
log "  ~/.config/wireplumber/wireplumber.conf.d/   — dir compartilhado, só nosso .conf é removido"
log "  ~/.local/lib/python*/site-packages/         — pip --user pode ser compartilhado"

# FEAT-DISABLE-STEAM-INPUT-PSSUPPORT-01: desliga Steam Input PSSupport em
# todos os localconfig.vdf por default. Simétrico com install.sh — sem isso,
# o usuário desinstala o Hefesto e os sintomas que o levaram a desinstalar
# (touchpad como mouse, mic spam, botões em background) voltam IMEDIATAMENTE
# porque a Steam preenche o vácuo do controle. Reverter:
# scripts/disable_steam_input.sh --restore (mantém os backups .bak.steam-input-<ts>).
DISABLE_STEAM_INPUT_SCRIPT="${ROOT_DIR}/scripts/disable_steam_input.sh"
if [[ "${KEEP_STEAM_INPUT}" -eq 1 ]]; then
    log "Steam Input PSSupport preservado (--keep-steam-input)"
elif [[ ! -x "${DISABLE_STEAM_INPUT_SCRIPT}" ]]; then
    log "scripts/disable_steam_input.sh ausente — pulei o desligar do Steam Input"
    log "  (rode depois: bash scripts/disable_steam_input.sh --apply)"
else
    log "desligando Steam Input PSSupport em todos os localconfig.vdf"
    if bash "${DISABLE_STEAM_INPUT_SCRIPT}" --apply; then
        log "  reverter: bash scripts/disable_steam_input.sh --restore"
    else
        log "  ERRO: disable_steam_input.sh falhou — rode manualmente"
    fi
fi

printf '\n─────────────────────────────────────────\n'
printf ' Hefesto - Dualsense4Unix desinstalado (wipe completo)\n'
printf '─────────────────────────────────────────\n\n'
