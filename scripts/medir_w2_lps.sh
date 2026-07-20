#!/usr/bin/env bash
# medir_w2_lps.sh — Onda W2: medição A/B do LPS raso (power save do firmware)
# do rtw88 em USB, via NetworkManager wifi.powersave (2=off vs 3=on).
#
# POR QUE NÃO modprobe.d/disable_lps_deep: em USB o deep PS NUNCA engaja —
# rtw_usb_deep_ps é função vazia (usb.c:836-839 do v7.0.11); quem seta
# RTW_FLAG_LEISURE_PS_DEEP são só pci.c/sdio.c/wow.c. disable_lps_deep=Y
# neste dongle é NO-OP (estudo 2026-07-20-estudo-premissas-onda-w-rtw88.md
# §4). O vilão ATIVO é o LPS raso: rtw_watch_dog → rtw_enter_lps quando o
# mac80211 pede PS — e o NM liga PS por default (wifi.powersave=3 em
# /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf).
#
# ESTE SCRIPT SÓ MEDE E RELATA. Ele NÃO persiste configuração nenhuma:
# a decisão de fixar powersave=2 (se ganhar) entra por asset próprio
# (assets/NetworkManager/hefesto-wifi-powersave.conf), gateada pela
# evidência produzida aqui. Ao final, o valor ORIGINAL da conexão é
# restaurado (trap EXIT), ganhe quem ganhar.
#
# Uso:   ./medir_w2_lps.sh            # dry-run: mostra o plano, não toca nada
#        ./medir_w2_lps.sh --run      # executa (interrompe o WiFi! ~6 min)
#        [--dur 120] [--out ARQ] [--url URL_DOWNLOAD]
#
# Gate humano: rodar só com a mantenedora ciente (o WiFi cai e volta 2x).

set -euo pipefail

DUR=120
RUN=0
OUT=""
# Arquivo grande de mirror rápido; troque à vontade (só leitura, /dev/null).
URL="https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/ubuntu-base-24.04.3-base-amd64.tar.gz"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --run) RUN=1 ;;
        --dur) DUR="$2"; shift ;;
        --out) OUT="$2"; shift ;;
        --url) URL="$2"; shift ;;
        *) echo "arg desconhecido: $1" >&2; exit 2 ;;
    esac
    shift
done

log() { printf '[w2] %s\n' "$*"; }

# --- Descoberta (read-only, roda até no dry-run) -------------------------
WIFI_DEV="$(nmcli -t -f DEVICE,TYPE device status 2>/dev/null |
    awk -F: '$2 == "wifi" {print $1; exit}')"
[[ -n "${WIFI_DEV}" ]] || { echo "nenhum device wifi no NetworkManager" >&2; exit 1; }

WIFI_CONN="$(nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null |
    awk -F: -v d="${WIFI_DEV}" '$2 == d {print $1; exit}')"
[[ -n "${WIFI_CONN}" ]] || { echo "nenhuma conexão ativa em ${WIFI_DEV}" >&2; exit 1; }

PS_ORIG="$(nmcli -g 802-11-wireless.powersave connection show "${WIFI_CONN}")"
GW="$(ip route show default dev "${WIFI_DEV}" 2>/dev/null | awk '{print $3; exit}')"
[[ -n "${GW}" ]] || { echo "sem gateway default via ${WIFI_DEV}" >&2; exit 1; }

log "device=${WIFI_DEV} conexão='${WIFI_CONN}' powersave_atual=${PS_ORIG} gateway=${GW}"
log "braços: A) powersave=2 (disable)  B) powersave=3 (enable) — ${DUR}s cada"
log "métricas: ping -i 0.2 (mediana/p95/perda) + curl throughput + journal (lps/beacon/rsvd)"

if [[ "${RUN}" -ne 1 ]]; then
    log "DRY-RUN: nada foi tocado. Re-execute com --run (gate humano!) para medir."
    exit 0
fi

OUT="${OUT:-/tmp/w2-lps-$(date +%Y%m%d-%H%M%S).txt}"

# --- Restauração garantida (fail-safe): valor original SEMPRE volta ------
restaurar() {
    log "restaurando 802-11-wireless.powersave=${PS_ORIG} em '${WIFI_CONN}'"
    nmcli connection modify "${WIFI_CONN}" 802-11-wireless.powersave "${PS_ORIG}" || true
    nmcli connection up "${WIFI_CONN}" >/dev/null 2>&1 || true
}
trap restaurar EXIT

medir_braco() {
    local nome="$1" ps_val="$2" t0 t1
    log "== braço ${nome}: powersave=${ps_val} =="
    nmcli connection modify "${WIFI_CONN}" 802-11-wireless.powersave "${ps_val}"
    nmcli connection up "${WIFI_CONN}" >/dev/null
    sleep 10 # assentar associação/DHCP antes de medir

    t0="$(date '+%Y-%m-%d %H:%M:%S')"

    # ping: amostras POR-PACOTE a 5Hz (sem -q: o modo quiet descarta as
    # amostras individuais e mediana/p95 ficam impossíveis de derivar depois).
    ping -i 0.2 -w "${DUR}" "${GW}" > "/tmp/w2-ping-${nome}.txt" 2>&1 &
    local ping_pid=$!

    # throughput: download contínuo (re-dispara se acabar antes de DUR)
    local bytes=0 fim=$((SECONDS + DUR))
    while (( SECONDS < fim )); do
        local b
        b="$(curl -sL --max-time $((fim - SECONDS + 1)) -o /dev/null \
              -w '%{size_download}' "${URL}" || true)"
        bytes=$((bytes + ${b:-0}))
    done
    wait "${ping_pid}" || true
    t1="$(date '+%Y-%m-%d %H:%M:%S')"

    {
        echo "### braço ${nome} (powersave=${ps_val}) ${t0} → ${t1}"
        echo "-- ping (ping -i 0.2 -w ${DUR} ${GW}):"
        grep -E 'packet loss' "/tmp/w2-ping-${nome}.txt" || true
        # mediana/p95 calculados das amostras por-pacote (time=<ms>), ordenadas.
        awk -F'time=' '/time=/{split($2,a," ");print a[1]}' \
            "/tmp/w2-ping-${nome}.txt" | sort -n > "/tmp/w2-rtt-${nome}.txt"
        awk '{v[NR]=$1;n=NR} END{
                 if(n==0){print "-- rtt ms: sem amostras (ping falhou?)";exit}
                 md=(n%2)?v[int(n/2)+1]:(v[n/2]+v[n/2+1])/2
                 pi=int(0.95*n); if(pi<1)pi=1; if(pi>n)pi=n
                 printf "-- rtt ms (n=%d): mediana=%.3f  p95=%.3f  min=%.3f  max=%.3f\n",\
                        n,md,v[pi],v[1],v[n]
             }' "/tmp/w2-rtt-${nome}.txt"
        echo "-- throughput download: ${bytes} bytes em ${DUR}s = $(( bytes / DUR / 1024 )) KiB/s"
        echo "-- journal do kernel na janela (assinaturas LPS/beacon/rsvd):"
        journalctl _TRANSPORT=kernel --since "${t0}" --until "${t1}" --no-pager 2>/dev/null |
            grep -Ei 'failed to leave lps state|error beacon valid|failed to download (rsvd page|firmware)|rtw_8822bu|rtw88' |
            tail -30 || echo "   (nada)"
        echo
    } >> "${OUT}"
}

: > "${OUT}"
echo "# W2 — LPS raso A/B (${WIFI_DEV}/'${WIFI_CONN}', dur=${DUR}s/braço)" >> "${OUT}"
medir_braco A 2
medir_braco B 3

log "relatório em ${OUT} — mediana/p95 do ping calculados por braço (linha 'rtt ms')"
log "decisão: powersave=2 só entra como asset se A ganhar de B com margem"
log "  clara (p95/perda/estabilidade) E sem regressão de throughput."
