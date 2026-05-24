#!/usr/bin/env bash
# doctor.sh — diagnóstico de saúde do Hefesto - Dualsense4Unix.
#
# Verifica daemon, serviço, socket IPC, regras udev (incluindo a consistência do
# nome de unit do hotplug), uinput, applet COSMIC (.desktop + ícone resolvível),
# o sequestro do microfone pelo WirePlumber e o alcance do controle. Saída
# PASS/FAIL/WARN por item. Marcadores ASCII (compat sanitizer de anonimato).
#
# Uso: scripts/doctor.sh [--fix] [--quiet]
#   --fix    aplica correções seguras: reaplica udev e instala/reseta o fix de
#            áudio do WirePlumber.
#   --quiet  só mostra FAIL/WARN.
#
# Exit code != 0 se houver qualquer FAIL. FEAT-DOCTOR-HEALTHCHECK-01.

set -uo pipefail   # sem -e de propósito: cada check trata a própria falha.

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly APP_ID="hefesto-dualsense4unix"
readonly HOTPLUG_UNIT="hefesto-dualsense4unix-gui-hotplug.service"
readonly APPLET_DESKTOP="/usr/share/applications/com.vitoriamaria.HefestoDualsense4Unix.desktop"

DO_FIX=0
QUIET=0
for arg in "$@"; do
    case "$arg" in
        --fix)   DO_FIX=1 ;;
        --quiet) QUIET=1 ;;
        *) printf '[doctor] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

FAILS=0
WARNS=0
pass() { [[ "${QUIET}" -eq 1 ]] || printf '[ OK ] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*"; FAILS=$((FAILS + 1)); }
warn() { printf '[WARN] %s\n' "$*"; WARNS=$((WARNS + 1)); }
info() { [[ "${QUIET}" -eq 1 ]] || printf '       %s\n' "$*"; }
hdr()  { [[ "${QUIET}" -eq 1 ]] || printf '\n== %s ==\n' "$*"; }

runtime_socket() {
    printf '%s/%s/%s.sock' "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}" "${APP_ID}" "${APP_ID}"
}

check_daemon_installed() {
    local found
    found="$(command -v hefesto-dualsense4unix 2>/dev/null || true)"
    [[ -z "${found}" && -e "${HOME}/.local/bin/hefesto-dualsense4unix" ]] && found="${HOME}/.local/bin/hefesto-dualsense4unix"
    [[ -z "${found}" && -e /usr/bin/hefesto-dualsense4unix ]] && found="/usr/bin/hefesto-dualsense4unix"
    if [[ -n "${found}" ]]; then
        pass "daemon/CLI instalado (${found})"
    else
        fail "CLI hefesto-dualsense4unix não encontrado — instale: ./install.sh --native"
    fi
}

check_service() {
    command -v systemctl >/dev/null 2>&1 || { warn "systemctl ausente — não checo o serviço"; return; }
    local state
    state="$(systemctl --user is-active "${APP_ID}.service" 2>/dev/null || true)"
    if [[ "${state}" == "active" ]]; then
        pass "serviço ${APP_ID}.service ativo"
    elif systemctl --user cat "${APP_ID}.service" >/dev/null 2>&1; then
        warn "serviço instalado mas ${state:-inativo} (start: systemctl --user start ${APP_ID}.service, ou abra a GUI)"
    else
        warn "serviço não instalado (autostart é opt-in: ./install.sh --enable-autostart)"
    fi
}

check_socket() {
    local sock; sock="$(runtime_socket)"
    if [[ -S "${sock}" ]]; then
        pass "socket IPC presente"
    else
        warn "socket IPC ausente (daemon parado?): ${sock}"
    fi
}

check_udev() {
    local r found=0 missing=""
    local rules=(70-ps5-controller.rules 71-uinput.rules 72-ps5-controller-autosuspend.rules \
                 73-ps5-controller-hotplug.rules 74-ps5-controller-hotplug-bt.rules)
    for r in "${rules[@]}"; do
        if [[ -e "/etc/udev/rules.d/${r}" || -e "/usr/lib/udev/rules.d/${r}" ]]; then
            found=$((found + 1))
        else
            missing+=" ${r}"
        fi
    done
    if [[ "${found}" -eq 5 ]]; then
        pass "5 regras udev presentes"
    elif [[ "${found}" -eq 0 ]]; then
        fail "nenhuma regra udev instalada — rode: sudo bash scripts/install_udev.sh"
    else
        warn "regras udev incompletas (${found}/5) — faltam:${missing}"
    fi
    # Consistência do hotplug: 73/74 devem apontar para a unit real.
    for r in 73-ps5-controller-hotplug.rules 74-ps5-controller-hotplug-bt.rules; do
        local path=""
        [[ -e "/etc/udev/rules.d/${r}" ]] && path="/etc/udev/rules.d/${r}"
        [[ -z "${path}" && -e "/usr/lib/udev/rules.d/${r}" ]] && path="/usr/lib/udev/rules.d/${r}"
        [[ -n "${path}" ]] || continue
        if grep -q 'SYSTEMD_USER_WANTS}="hefesto-gui-hotplug.service"' "${path}" 2>/dev/null; then
            fail "${r}: aponta para unit ERRADA (hefesto-gui-hotplug.service) — reinstale as regras (sudo bash scripts/install_udev.sh)"
        elif grep -q "SYSTEMD_USER_WANTS}=\"${HOTPLUG_UNIT}\"" "${path}" 2>/dev/null; then
            pass "${r}: hotplug aponta para ${HOTPLUG_UNIT}"
        fi
    done
}

check_uinput() {
    if [[ -e /dev/uinput ]]; then
        pass "/dev/uinput presente"
    else
        fail "/dev/uinput ausente — rode: sudo modprobe uinput (ou reinstale udev)"
    fi
}

check_applet() {
    if [[ ! -e "${APPLET_DESKTOP}" ]]; then
        warn "applet COSMIC não instalado (.desktop ausente) — opcional: ./install.sh --enable-cosmic-applet"
        return
    fi
    if grep -q '^X-CosmicApplet=true' "${APPLET_DESKTOP}"; then
        pass "applet .desktop com X-CosmicApplet=true"
    else
        fail "applet .desktop sem X-CosmicApplet=true"
    fi
    if grep -q '^X-HostWaylandDisplay=true' "${APPLET_DESKTOP}"; then
        pass "applet .desktop com X-HostWaylandDisplay=true"
    else
        warn "applet .desktop sem X-HostWaylandDisplay=true — recomendado p/ falar com o sistema (reinstale o applet)"
    fi
    local icon
    icon="$(sed -n 's/^Icon=//p' "${APPLET_DESKTOP}" | head -1)"
    if [[ -n "${icon}" ]] && ls /usr/share/icons/hicolor/*/apps/"${icon}".* >/dev/null 2>&1; then
        pass "ícone do applet resolvível (${icon})"
    else
        fail "ícone do applet NÃO resolvível (Icon=${icon}) — falta o arquivo correspondente"
    fi
    if [[ -e "/usr/share/icons/hicolor/256x256/apps/com.vitoriamaria.HefestoDualsense4Unix.png" ]]; then
        pass "ícone PNG 256x256 do applet presente"
    else
        warn "ícone PNG 256x256 do applet ausente — a lista de Miniaplicativos pode não mostrar o ícone colorido"
    fi
    if command -v desktop-file-validate >/dev/null 2>&1; then
        if desktop-file-validate "${APPLET_DESKTOP}" >/dev/null 2>&1; then
            pass "desktop-file-validate sem erros"
        else
            info "desktop-file-validate emitiu avisos (não-fatal)"
        fi
    fi
}

check_wireplumber_source() {
    local state="${HOME}/.local/state/wireplumber/default-nodes"
    if [[ -f "${state}" ]] && grep -qiE '^default.configured.audio.source=.*dualsense' "${state}" 2>/dev/null; then
        fail "WirePlumber fixa o DualSense como microfone padrão — rode: scripts/doctor.sh --fix"
    else
        pass "WirePlumber não fixa o DualSense como fonte padrão"
    fi
    if command -v wpctl >/dev/null 2>&1; then
        local cur
        cur="$(wpctl status 2>/dev/null | sed -n '/Default Configured/,$p' | grep -i 'Audio/Source' | head -1)"
        [[ -n "${cur}" ]] && info "fonte configurada:${cur#*Audio/Source}"
    fi
}

check_steam_input() {
    local script="${ROOT_DIR}/scripts/disable_steam_input.sh"
    if [[ ! -x "$script" ]]; then
        info "scripts/disable_steam_input.sh ausente — skip"
        return
    fi
    # Reusa o --status do próprio script (cobre deb/flatpak/snap, todos os users).
    local out
    out="$(bash "$script" --status 2>&1)"
    if printf '%s\n' "$out" | grep -q 'tudo limpo'; then
        pass "Steam Input PSSupport desligado em todos os localconfig.vdf"
    elif printf '%s\n' "$out" | grep -q 'ação sugerida'; then
        fail "Steam Input ATIVO (PSSupport=2 ou UseSteamControllerConfig=2) — conflita com o daemon; rode: scripts/doctor.sh --fix"
    elif printf '%s\n' "$out" | grep -q 'nenhum localconfig.vdf encontrado'; then
        info "Steam não detectada (sem localconfig.vdf)"
    else
        info "Steam Input status:"
        printf '%s\n' "$out" | sed 's/^/         /'
    fi
}

check_controller() {
    local h hidraw=0
    for h in /dev/hidraw*; do [[ -e "$h" ]] && hidraw=1; done
    [[ "${hidraw}" -eq 1 ]] && info "nós hidraw: $(ls /dev/hidraw* 2>/dev/null | tr '\n' ' ')"
    if command -v lsusb >/dev/null 2>&1 && lsusb 2>/dev/null | grep -qiE '054c'; then
        pass "DualSense conectado via USB (vendor 054c)"
    elif command -v bluetoothctl >/dev/null 2>&1 && timeout 4 bluetoothctl devices 2>/dev/null | grep -qi 'DualSense'; then
        pass "DualSense pareado via Bluetooth (conecte para usar)"
    else
        warn "controle não detectado agora — conecte o DualSense para testar"
    fi
}

check_perms_soft() {
    local h mode
    for h in /dev/hidraw*; do
        [[ -e "$h" ]] || continue
        mode="$(stat -c '%a' "$h" 2>/dev/null || echo '?')"
        [[ "${mode}" == "666" ]] && warn "${h} está 0666 (rw global) — provável ajuste manual; esperado é 0660+uaccess"
    done
}

apply_fixes() {
    hdr "aplicando correções (--fix)"
    if command -v sudo >/dev/null 2>&1; then
        if sudo bash "${ROOT_DIR}/scripts/install_udev.sh" >/dev/null 2>&1; then
            pass "regras udev reaplicadas"
        else
            warn "falha ao reaplicar udev"
        fi
    else
        warn "sudo ausente — não reapliquei udev"
    fi
    if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --install >/dev/null 2>&1; then
        pass "fix de áudio do WirePlumber aplicado"
    else
        warn "fix de áudio do WirePlumber falhou"
    fi
    if [[ -x "${ROOT_DIR}/scripts/disable_steam_input.sh" ]]; then
        if bash "${ROOT_DIR}/scripts/disable_steam_input.sh" --apply >/dev/null 2>&1; then
            pass "Steam Input PSSupport desligado (todos os localconfig.vdf)"
        else
            warn "disable_steam_input.sh falhou"
        fi
    fi
}

main() {
    [[ "${DO_FIX}" -eq 1 ]] && apply_fixes
    hdr "daemon"
    check_daemon_installed
    check_service
    check_socket
    hdr "kernel / udev"
    check_udev
    check_uinput
    hdr "applet COSMIC"
    check_applet
    hdr "áudio (microfone)"
    check_wireplumber_source
    hdr "Steam Input"
    check_steam_input
    hdr "controle"
    check_controller
    check_perms_soft

    printf '\n─────────────────────────────────────────\n'
    if [[ "${FAILS}" -eq 0 ]]; then
        printf ' Diagnóstico: tudo OK (%d aviso(s))\n' "${WARNS}"
    else
        printf ' Diagnóstico: %d FALHA(s), %d aviso(s)\n' "${FAILS}" "${WARNS}"
    fi
    printf '─────────────────────────────────────────\n'
    [[ "${FAILS}" -eq 0 ]]
}

main
