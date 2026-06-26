#!/usr/bin/env bash
# doctor.sh — diagnóstico de saúde do Hefesto - Dualsense4Unix.
#
# Verifica daemon, serviço, socket IPC, regras udev (incluindo a consistência do
# nome de unit do hotplug), uinput, applet COSMIC (.desktop + ícone resolvível),
# o sequestro do microfone pelo WirePlumber e o alcance do controle. Saída
# PASS/FAIL/WARN por item. Marcadores ASCII (compat sanitizer de anonimato).
#
# Uso: scripts/doctor.sh [--fix] [--quiet] [--watch-dropout] [--suggest-port]
#   --fix             aplica correções seguras: reaplica udev e instala/reseta o
#                     fix de áudio do WirePlumber.
#   --quiet           só mostra FAIL/WARN.
#   --watch-dropout   vigia o journal do kernel e bloqueia até o primeiro sintoma
#                     de dropout USB (-71); imprime a linha e sai. (Ctrl-C para sair.)
#   --suggest-port    diz em qual controlador USB o DualSense está e recomenda a
#                     rota definitiva (chipset robusto ou Bluetooth) se estiver no
#                     controlador Matisse/CPU (frágil sob carga de GPU).
#
# Exit code != 0 se houver qualquer FAIL. FEAT-DOCTOR-HEALTHCHECK-01,
# FEAT-DOCTOR-USB-DROPOUT-DIAGNOSTIC-01.

set -uo pipefail   # sem -e de propósito: cada check trata a própria falha.

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly APP_ID="hefesto-dualsense4unix"
readonly HOTPLUG_UNIT="hefesto-dualsense4unix-gui-hotplug.service"
readonly APPLET_DESKTOP="/usr/share/applications/com.vitoriamaria.HefestoDualsense4Unix.desktop"

DO_FIX=0
QUIET=0
WATCH_DROPOUT=0
SUGGEST_PORT=0
for arg in "$@"; do
    case "$arg" in
        --fix)            DO_FIX=1 ;;
        --quiet)          QUIET=1 ;;
        --watch-dropout)  WATCH_DROPOUT=1 ;;
        --suggest-port)   SUGGEST_PORT=1 ;;
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
    # DOCTOR-UDEV-CANONICAL-FIX-01: o conjunto CANÔNICO pós-fix-storm é 70/71/72.
    # As regras 73/74 (hotplug-GUI) foram REMOVIDAS por alimentarem a
    # re-enumeração do storm -71 (install_udev.sh faz `rm -f`). Antes o doctor
    # exigia 5 (70-74) e reportava "3/5 — faltam 73 74" PARA SEMPRE após um
    # install limpo (falso-negativo permanente). 75 (audio-off) e 76
    # (touchpad-ignore) são opt-in e não entram na contagem canônica.
    local r found=0 missing=""
    local rules=(70-ps5-controller.rules 71-uinput.rules 72-ps5-controller-autosuspend.rules)
    for r in "${rules[@]}"; do
        if [[ -e "/etc/udev/rules.d/${r}" || -e "/usr/lib/udev/rules.d/${r}" ]]; then
            found=$((found + 1))
        else
            missing+=" ${r}"
        fi
    done
    if [[ "${found}" -eq 3 ]]; then
        pass "3 regras udev canônicas presentes (70/71/72)"
    elif [[ "${found}" -eq 0 ]]; then
        fail "nenhuma regra udev instalada — rode: sudo bash scripts/install_udev.sh"
    else
        warn "regras udev incompletas (${found}/3) — faltam:${missing}"
    fi
    # 73/74 (hotplug-GUI) foram DESCONTINUADAS (amplificavam o storm -71). Se
    # sobraram de uma instalação antiga, avisa para limpar.
    for r in 73-ps5-controller-hotplug.rules 74-ps5-controller-hotplug-bt.rules; do
        if [[ -e "/etc/udev/rules.d/${r}" || -e "/usr/lib/udev/rules.d/${r}" ]]; then
            warn "${r}: regra descontinuada presente (amplificava o storm -71) — remova: sudo bash scripts/install_udev.sh"
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

# BUG-WIREPLUMBER-FIX-FALSE-SUCCESS-01 / ADR-019: checa o microfone ATIVO
# (pactl get-default-source; fallback ao '*' do wpctl), não o `configured`.
# 3 estados: OK (ativo != DualSense); WARN (DualSense por ser a única fonte);
# FAIL (DualSense ativo COM outra fonte available — drop-in não pegou).
check_wireplumber_source() {
    local cur=""
    if command -v pactl >/dev/null 2>&1; then
        cur="$(pactl get-default-source 2>/dev/null || true)"
    fi
    if [[ -z "${cur}" ]] && command -v wpctl >/dev/null 2>&1; then
        cur="$(wpctl status 2>/dev/null | awk '
            /Sources:/{s=1;next} s&&(/Filters:/||/Sinks:/||/Streams:/||/Video/){s=0}
            s&&/\*/{sub(/.*\*[[:space:]]+[0-9]+\.[[:space:]]*/,"");print;exit}')"
    fi
    if [[ -z "${cur}" ]]; then
        warn "não consegui ler o microfone ativo (pactl/wpctl ausentes ou WirePlumber parado)"
        return
    fi
    # O '.monitor' do sink do DualSense casa "DualSense" no nome mas é o loopback
    # da saída, não o mic — inofensivo. Só o alsa_input (mic) é o sintoma real.
    if [[ ! "${cur}" =~ [Dd]ual[Ss]ense ]] || [[ "${cur}" == *[Mm]onitor* ]]; then
        pass "microfone ativo não é o mic do DualSense (${cur})"
        return
    fi
    # ativo É o DualSense — distingue escassez (única fonte) de falha real.
    local has_other=""
    if command -v wpctl >/dev/null 2>&1; then
        has_other="$(wpctl status 2>/dev/null | awk '
            /Sources:/{s=1;next} s&&(/Filters:/||/Sinks:/||/Streams:/||/Video/){s=0}
            s&&/[0-9]+\./&&!/[Dd]ual[Ss]ense/{print;exit}')"
    fi
    if [[ -n "${has_other}" ]]; then
        fail "DualSense é o microfone ATIVO com outra fonte disponível — rode: scripts/doctor.sh --fix"
    else
        warn "DualSense é o microfone ATIVO por ser a única fonte — conecte mic/webcam, ou desligue de vez: fix_wireplumber_default_source.sh --disable-source"
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

# FEAT-DOCTOR-USB-DROPOUT-DIAGNOSTIC-01.
# Resolve o controlador PCI (xHCI) onde um device USB (sysfs path) está pendurado:
# o último 0000:XX:YY.Z na cadeia antes do /usbN é o controlador.
usb_pci_controller() {
    local devpath="$1" real
    real="$(readlink -f "${devpath}" 2>/dev/null || true)"
    printf '%s\n' "${real}" | grep -oE '0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]' | tail -1
}

pci_label() {
    case "$1" in
        *0c:00.3) echo "Matisse/CPU (0c:00.3)" ;;   # controlador integrado do Ryzen
        *02:00.0) echo "chipset (02:00.0)" ;;        # southbridge — mais resiliente
        "")       echo "desconhecido" ;;
        *)        echo "$1" ;;
    esac
}

# Mapeia um número de bus USB para o rótulo do controlador PCI do seu root hub.
bus_to_label() {
    pci_label "$(usb_pci_controller "/sys/bus/usb/devices/usb${1}" 2>/dev/null)"
}

# Conta sintomas de dropout -71 (EPROTO) e ATRIBUI corretamente a fonte.
check_usb_dropout() {
    command -v journalctl >/dev/null 2>&1 || { info "journalctl ausente — pulo o check de dropout"; return; }

    # Localização: em qual controlador o DualSense (vendor 054c) está agora.
    local d ds_dev="" ds_pci="" ds_devname=""
    for d in /sys/bus/usb/devices/*; do
        [[ -r "$d/idVendor" ]] || continue
        [[ "$(cat "$d/idVendor" 2>/dev/null)" == "054c" ]] && ds_dev="$d"
    done
    if [[ -n "$ds_dev" ]]; then
        ds_pci="$(usb_pci_controller "$ds_dev")"
        ds_devname="$(basename "$ds_dev")"
        info "DualSense no controlador $(pci_label "$ds_pci"), Bus $(cat "$ds_dev/busnum" 2>/dev/null), power/control=$(cat "$ds_dev/power/control" 2>/dev/null)"
    else
        info "DualSense não conectado via USB agora (pode estar via Bluetooth) — pulo a localização de barramento"
    fi

    # Sintomas de -71 no boot atual (read-only).
    local lines n
    lines="$(journalctl -b -k --no-pager 2>/dev/null \
              | grep -iE 'error -71|device descriptor read/64, error|not accepting address|unable to enumerate USB device' || true)"
    n="$(printf '%s' "$lines" | grep -c . || true)"; n="${n:-0}"
    if [[ "${n}" -eq 0 ]]; then
        pass "sem dropout -71 neste boot"
        return
    fi
    warn "dropout USB: ${n} sintoma(s) -71/enum neste boot"

    # ATRIBUIÇÃO HONESTA (corrige a heurística antiga que culpava o Matisse só por
    # o dsx estar lá): extrai QUAIS devices 'usb X-Y' geraram o -71 e mapeia o
    # bus -> controlador. O -71 de boot costuma ser OUTRO device (ex: webcam no
    # chipset), não o DualSense.
    local devs dev busnum hits dsx_hits=0 other_count=0
    devs="$(printf '%s\n' "$lines" | grep -oE 'usb [0-9]+-[0-9.]+' | awk '{print $2}' | sort -u)"
    [[ -n "$devs" ]] && info "fonte(s) do -71 neste boot:"
    for dev in $devs; do
        busnum="${dev%%-*}"
        hits="$(printf '%s\n' "$lines" | grep -c "usb ${dev}:" || true)"
        if [[ -n "$ds_devname" && "$dev" == "$ds_devname" ]]; then
            dsx_hits="$hits"
            info "  - usb ${dev} = DualSense (Bus ${busnum} = $(bus_to_label "$busnum")) -- ${hits}x"
        else
            other_count=$((other_count + 1))
            info "  - usb ${dev} = outro device (Bus ${busnum} = $(bus_to_label "$busnum")) -- ${hits}x"
        fi
    done

    if [[ "${dsx_hits:-0}" -gt 0 ]]; then
        info "o -71 ATINGE o DualSense -- fix definitivo: Bluetooth ou porta do chipset (rode: scripts/doctor.sh --suggest-port)"
    else
        info "o -71 deste boot NÃO é do DualSense -- provável outro device/porta (ex: webcam). Valide o dsx abrindo a Steam com --watch-dropout."
    fi

    # rede de segurança (watcher) — NÃO é a solução, só mitigação.
    if systemctl is-enabled --quiet hefesto-dsx-recover.service 2>/dev/null \
       || systemctl is-active --quiet hefesto-dsx-recover.service 2>/dev/null; then
        info "watcher de auto-recuperação ativo (hefesto-dsx-recover.service)"
    else
        info "auto-recuperação NÃO instalada -- rode ./dsx.sh para instalar o watcher"
    fi
    info "ver em tempo real: scripts/doctor.sh --watch-dropout"
}

# --suggest-port: diz em qual controlador o DualSense está e recomenda a rota
# definitiva (chipset robusto / Bluetooth) se estiver no Matisse/CPU frágil.
suggest_port() {
    local d ds_dev=""
    for d in /sys/bus/usb/devices/*; do
        [[ -r "$d/idVendor" ]] || continue
        [[ "$(cat "$d/idVendor" 2>/dev/null)" == "054c" ]] && ds_dev="$d"
    done
    if [[ -z "$ds_dev" ]]; then
        if command -v bluetoothctl >/dev/null 2>&1 && timeout 4 bluetoothctl devices 2>/dev/null | grep -qi 'DualSense'; then
            pass "DualSense via Bluetooth (sem caminho USB) -- rota ótima, -71 impossível para o controle"
        else
            info "DualSense não conectado via USB nem Bluetooth -- conecte para avaliar"
        fi
        return
    fi
    local ds_pci bus
    ds_pci="$(usb_pci_controller "$ds_dev")"
    bus="$(cat "$ds_dev/busnum" 2>/dev/null)"
    info "DualSense em Bus ${bus}, controlador $(pci_label "$ds_pci")"
    case "$ds_pci" in
        *0c:00.3*)
            warn "dsx no controlador Matisse/CPU -- frágil sob carga de GPU/Steam (storm -71)"
            info "  RECOMENDADO: parear por Bluetooth (remove o USB) OU mover para porta do CHIPSET (02:00.0)"
            info "  as portas do chipset são as mesmas do teclado/mouse, que nunca caem"
            ;;
        *02:00.0*)
            pass "dsx no controlador do chipset (02:00.0) -- robusto (mesmo do teclado/mouse). Boa rota."
            ;;
        *)
            info "  controlador não reconhecido (${ds_pci}) -- avalie manualmente"
            ;;
    esac
}

# Modo --watch-dropout: bloqueia até o primeiro sintoma de dropout e sai.
watch_dropout() {
    printf 'vigiando o journal do kernel por dropout -71 (Ctrl-C para sair)...\n'
    journalctl -kf -o cat --since now 2>/dev/null \
      | grep -m1 -iE 'error -71|device descriptor read/64, error|not accepting address|device not responding' \
      && printf '\n[WATCH] primeiro sinal de dropout capturado acima.\n'
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
    [[ "${WATCH_DROPOUT}" -eq 1 ]] && { watch_dropout; exit 0; }
    [[ "${SUGGEST_PORT}" -eq 1 ]] && { suggest_port; exit 0; }
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
    hdr "USB / dropout"
    check_usb_dropout

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
