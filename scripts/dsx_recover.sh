#!/usr/bin/env bash
set -uo pipefail

readonly APP_ID="hefesto-dualsense4unix"
readonly THROTTLE_SECS=20
readonly WINDOW_SECS=10
readonly THRESHOLD=4
readonly BACKOFF_THRESHOLD=5
readonly LONG_BACKOFF_SECS=300

log() { printf '%(%Y-%m-%dT%H:%M:%S)T dsx-recover: %s\n' -1 "$*"; }

graphical_user() {
    local d uid
    for d in /run/user/*; do
        uid="$(basename "$d")"
        [[ "$uid" =~ ^[0-9]+$ ]] || continue
        [[ "$uid" -ge 1000 ]] || continue
        [[ -S "$d/bus" ]] || continue
        printf '%s\n' "$uid"
        return 0
    done
    return 1
}

repin_and_trigger() {
    local d
    for d in /sys/bus/usb/devices/*; do
        [[ -r "$d/idVendor" ]] || continue
        [[ "$(cat "$d/idVendor" 2>/dev/null)" == "054c" ]] || continue
        echo on > "$d/power/control" 2>/dev/null || true
        echo -1 > "$d/power/autosuspend_delay_ms" 2>/dev/null || true
    done
    local f
    for f in /sys/bus/pci/drivers/xhci_hcd/*/power/control; do
        [[ -w "$f" ]] && echo on > "$f" 2>/dev/null || true
    done
    udevadm trigger --subsystem-match=usb --attr-match=idVendor=054c 2>/dev/null || true
}

rebind_dualsense() {
    local d dev=""
    for d in /sys/bus/usb/devices/*; do
        [[ -r "$d/idVendor" ]] || continue
        [[ "$(cat "$d/idVendor" 2>/dev/null)" == "054c" ]] && dev="$(basename "$d")"
    done
    if [[ -z "${dev}" ]]; then
        log "DualSense ausente do barramento — nada a re-bindar (aguardando re-enumeração do kernel)"
        return
    fi
    log "re-bind do DualSense (${dev}) via authorized toggle"
    echo 0 > "/sys/bus/usb/devices/${dev}/authorized" 2>/dev/null || true
    sleep 1
    echo 1 > "/sys/bus/usb/devices/${dev}/authorized" 2>/dev/null || true
}

restart_daemon() {
    local uid user
    uid="$(graphical_user || true)"
    [[ -n "${uid}" ]] || { log "sem sessão gráfica ativa — pulo restart do daemon"; return; }
    user="$(id -nu "${uid}" 2>/dev/null || true)"
    [[ -n "${user}" ]] || return
    if runuser -u "${user}" -- env XDG_RUNTIME_DIR="/run/user/${uid}" \
         DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${uid}/bus" \
         systemctl --user cat "${APP_ID}.service" >/dev/null 2>&1; then
        runuser -u "${user}" -- env XDG_RUNTIME_DIR="/run/user/${uid}" \
            DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${uid}/bus" \
            systemctl --user restart "${APP_ID}.service" >/dev/null 2>&1 \
            && log "daemon ${APP_ID} reiniciado (user ${user})" \
            || log "restart do daemon falhou (não-fatal)"
    fi
}

last_recover=0
last_throttle_log=0
consecutive_recovers=0
recover() {
    local now; now="$(date +%s)"
    if (( now - last_recover < THROTTLE_SECS )); then
        if (( now - last_throttle_log >= THROTTLE_SECS )); then
            log "recovery throttled (storm contínuo; último recovery há $(( now - last_recover ))s)"
            last_throttle_log="$now"
        fi
        return
    fi
    if (( consecutive_recovers >= BACKOFF_THRESHOLD )); then
        if (( now - last_recover < LONG_BACKOFF_SECS )); then
            return
        fi
        log "storm PERSISTENTE após ${consecutive_recovers} recoveries — back-off ${LONG_BACKOFF_SECS}s (porta USB ruim? prefira Bluetooth ou outra porta)"
    fi
    last_recover="$now"
    consecutive_recovers=$(( consecutive_recovers + 1 ))
    log "STORM detectado — iniciando recovery (#${consecutive_recovers})"
    repin_and_trigger
    sleep 2
    rebind_dualsense
    sleep 2
    restart_daemon
    log "recovery concluído"
}

log "watcher iniciado (threshold ${THRESHOLD}/${WINDOW_SECS}s, throttle ${THROTTLE_SECS}s)"
count=0
window_start=0
journalctl -kf -o cat --since now 2>/dev/null | \
while IFS= read -r line; do
    case "$line" in
        *"error -71"*|*"device descriptor read/64, error"*|*"not accepting address"*|*"unable to enumerate USB device"*|*"USB disconnect"*)
            now="$(date +%s)"
            if (( now - window_start > WINDOW_SECS )); then
                window_start="$now"; count=0
                if (( now - last_recover > LONG_BACKOFF_SECS )); then
                    consecutive_recovers=0
                fi
            fi
            count=$((count + 1))
            if (( count >= THRESHOLD )); then
                recover
                count=0
            fi
            ;;
    esac
done
