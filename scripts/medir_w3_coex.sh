#!/usr/bin/env bash

set -euo pipefail

DUR=120
RUN=0
OUT=""
EVDEVS=()
URL="https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/ubuntu-base-24.04.3-base-amd64.tar.gz"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --run) RUN=1 ;;
        --dur) DUR="$2"; shift ;;
        --out) OUT="$2"; shift ;;
        --evdev) EVDEVS+=("$2"); shift ;;
        --url) URL="$2"; shift ;;
        *) echo "arg desconhecido: $1" >&2; exit 2 ;;
    esac
    shift
done

log() { printf '[w3] %s\n' "$*"; }

HCI=hci0
log "plano: 3 braços de ${DUR}s (A ocioso / B carga / C rfkill block wifi)"
if command -v hciconfig >/dev/null 2>&1; then
    log "métricas: delta hciconfig -a ${HCI} + btmon snoop + evdev + debugfs"
else
    log "métricas: btmon snoop + evdev + debugfs — SEM o delta de contadores HCI"
    log "  (o hciconfig foi depreciado pelo BlueZ e não está nesta máquina; os"
    log "   contadores RX/TX só saem do ioctl HCIGETDEVINFO e nenhuma ferramenta"
    log "   viva os devolve. Δ ausente = medida ausente, não rádio limpo. Para"
    log "   recuperar este braço: instale bluez-deprecated/bluez-deprecated-tools)"
fi
if [[ ${#EVDEVS[@]} -eq 0 ]]; then
    log "dica: passe --evdev /dev/input/eventN (1x por controle) p/ medir"
    log "  taxa de reports e lacunas; sem isso mede-se só o lado HCI."
fi

if [[ "${RUN}" -ne 1 ]]; then
    log "DRY-RUN: nada foi tocado. Re-execute com --run (gate humano!)."
    exit 0
fi

[[ "$(id -u)" -eq 0 ]] || { echo "precisa de root (btmon/debugfs)" >&2; exit 1; }
umask 077
OUT="${OUT:-/tmp/w3-coex-$(date +%Y%m%d-%H%M%S).txt}"

WIFI_BLOQUEADO=0
CAPTURAS=""
BTMON_PID=""
carga_pid=""
restaurar() {
    if [[ -n "${BTMON_PID}" ]]; then
        kill "${BTMON_PID}" 2>/dev/null || true
        wait "${BTMON_PID}" 2>/dev/null || true
    fi
    if [[ -n "${carga_pid}" ]]; then
        kill "${carga_pid}" 2>/dev/null || true
    fi
    if [[ "${WIFI_BLOQUEADO}" -eq 1 ]]; then
        log "restaurando rfkill unblock wifi"
        rfkill unblock wifi || true
    fi
    if [[ -n "${CAPTURAS}" ]]; then
        rm -rf "${CAPTURAS}"
    fi
}
trap restaurar EXIT
CAPTURAS="$(mktemp -d -t w3-coex-capturas.XXXXXX)"

medir_evdev() {
    python3 - "$1" "${DUR}" > "$2" 2>&1 <<'PY' &
import struct, sys, time
dev, dur = sys.argv[1], float(sys.argv[2])
fmt = "llHHi"; sz = struct.calcsize(fmt)
fim = time.monotonic() + dur
n = 0; last = None; gaps = []
try:
    with open(dev, "rb", buffering=0) as f:
        import os, select
        os.set_blocking(f.fileno(), False)
        while time.monotonic() < fim:
            r, _, _ = select.select([f], [], [], 0.5)
            if not r:
                continue
            data = f.read(sz * 64)
            if not data:
                continue
            agora = time.monotonic()
            n += len(data) // sz
            if last is not None:
                gaps.append((agora - last) * 1000.0)
            last = agora
except OSError as e:
    print(f"{dev}: erro {e}")
    sys.exit(0)
gaps.sort(reverse=True)
taxa = n / dur if dur else 0.0
print(f"{dev}: {n} eventos em {dur:.0f}s = {taxa:.1f} ev/s; "
      f"maiores lacunas (ms): {[round(g) for g in gaps[:3]]}")
PY
}

snapshot_hci() {
    if ! command -v hciconfig >/dev/null 2>&1; then
        echo "(sem hciconfig — contadores HCI NÃO medidos neste braço)"
        return 0
    fi
    hciconfig -a "${HCI}" 2>/dev/null | grep -E 'RX bytes|TX bytes' || true
}

delta_hci() {
    printf '%s\n===\n%s\n' "$1" "$2" | awk '
        /^===$/ { fase = 2; next }
        {
            pref = ($1 == "RX") ? "RX" : ($1 == "TX") ? "TX" : "?"
            for (j = 2; j <= NF; j++) {
                if (split($j, kv, ":") == 2 && kv[2] ~ /^[0-9]+$/) {
                    key = pref "." kv[1]
                    if (fase != 2) { a[key] = kv[2] }
                    else { printf "   Δ%s=%d\n", key, kv[2] - a[key] }
                }
            }
        }'
}

medir_braco() {
    local nome="$1" prep="$2" fin="$3" t0 t1 antes depois
    log "== braço ${nome} =="
    "${prep}"
    sleep 5
    t0="$(date '+%Y-%m-%d %H:%M:%S')"
    antes="$(snapshot_hci)"

    local snoop="${CAPTURAS}/w3-${nome}.snoop"
    btmon -w "${snoop}" >/dev/null 2>&1 &
    BTMON_PID=$!

    local pids=() i=0
    for ev in "${EVDEVS[@]:-}"; do
        [[ -n "${ev}" ]] || continue
        medir_evdev "${ev}" "${CAPTURAS}/w3-${nome}-ev${i}.txt"
        pids+=("$!")
        i=$((i + 1))
    done

    sleep "${DUR}"

    kill "${BTMON_PID}" 2>/dev/null || true
    wait "${BTMON_PID}" 2>/dev/null || true
    BTMON_PID=""
    for p in "${pids[@]:-}"; do [[ -n "${p}" ]] && wait "${p}" 2>/dev/null || true; done
    depois="$(snapshot_hci)"
    t1="$(date '+%Y-%m-%d %H:%M:%S')"
    "${fin}"

    {
        echo "### braço ${nome} ${t0} → ${t1}"
        echo "-- Δ contadores HCI (depois − antes):"
        delta_hci "${antes}" "${depois}"
        echo "-- hciconfig antes:";  echo "${antes}"
        echo "-- hciconfig depois:"; echo "${depois}"
        echo "-- btmon (eventos de interesse):"
        btmon -r "${snoop}" 2>/dev/null |
            grep -cE 'Hardware Error' | sed 's/^/   Hardware Error: /' || true
        btmon -r "${snoop}" 2>/dev/null |
            grep -A1 'Disconnect Complete' | grep -E 'Reason' | sort | uniq -c |
            sed 's/^/   /' || echo "   (sem Disconnection Complete)"
        echo "-- evdev:"
        cat "${CAPTURAS}/w3-${nome}"-ev*.txt 2>/dev/null || echo "   (sem --evdev)"
        echo "-- debugfs (${HCI}):"
        for f in conn_info_min_age conn_info_max_age supervision_timeout; do
            printf '   %s=' "${f}"
            cat "/sys/kernel/debug/bluetooth/${HCI}/${f}" 2>/dev/null || echo '?'
        done
    } >> "${OUT}"
    rm -f "${snoop}" "${CAPTURAS}/w3-${nome}"-ev*.txt
    printf -- '-- captura do btmon: %s (lida e apagada)\n\n' "${snoop}" >> "${OUT}"
}

prep_ocioso() { :; }
fin_ocioso() { :; }
prep_carga() {
    ( while :; do curl -sL --max-time "${DUR}" -o /dev/null "${URL}" || true; done ) &
    carga_pid=$!
}
fin_carga() { [[ -n "${carga_pid}" ]] && kill "${carga_pid}" 2>/dev/null || true; carga_pid=""; }
prep_rfkill() { WIFI_BLOQUEADO=1; rfkill block wifi; }
fin_rfkill() { rfkill unblock wifi; WIFI_BLOQUEADO=0; sleep 5; }

: > "${OUT}"
if [[ -n "${SUDO_UID:-}" ]]; then
    chown "${SUDO_UID}:${SUDO_GID:-${SUDO_UID}}" "${OUT}" || log "aviso: ${OUT} ficou do root"
fi
echo "# W3 — coexistência WiFi×BT (dur=${DUR}s/braço; capturas do btmon em ${CAPTURAS}, apagadas depois de lidas)" >> "${OUT}"
medir_braco A-ocioso prep_ocioso fin_ocioso
medir_braco B-carga  prep_carga  fin_carga
medir_braco C-rfkill prep_rfkill fin_rfkill

{
    echo "## Leitura"
    echo "- B ≈ C ruins e A bom  → culpa do TRÁFEGO (rádio 2.4G ou barramento sob carga)."
    echo "- B ruim e C bom       → culpa do RÁDIO WiFi (2.4G/5G TX), não do USB3."
    echo "- B ≈ A e C igual      → sem interferência mensurável no BT hoje."
    echo "- Piora até em C       → EMI do LINK USB3 (SuperSpeed) ou outro vizinho."
    echo "## Recomendação medível (não automática)"
    echo "- WiFi(4-3)+BT(3-1)+controles(3-2/3-4) dividem o xHCI 0c:00.3; o xHCI"
    echo "  02:00.0 tem 4 portas SuperSpeed LIVRES (bus 2). Mover o dongle p/ lá"
    echo "  é mudança de topologia interna — re-rodar este script depois e"
    echo "  comparar os braços A/B (mesmos números = não era o barramento)."
} >> "${OUT}"

log "capturas do btmon: ${CAPTURAS} (apagadas depois de lidas)"
log "relatório em ${OUT}"
