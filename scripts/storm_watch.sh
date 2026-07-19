#!/usr/bin/env bash
# storm_watch.sh — kernel-watch: vigia do ecossistema USB/BT/xHCI do hefesto.
#
# Evolução do FEAT-DSX-STORM-WATCH-01 (PLAT-06 item 4, estudo
# 2026-07-18-estudo-kernel-hardening.md §6). O NOME do arquivo não mudou de
# propósito: a unit de usuário `hefesto-dualsense4unix-storm-watch.service`
# aponta para ele — compat preservada, nenhuma mudança de wiring obrigatória.
#
# O que vigia (journal do kernel + bluetoothd), com TAG por linha:
#   [USB-71]  o storm clássico (-71/enum) — mesmos padrões do doctor.sh;
#   [JOYCON]  joycon_enforce_subcmd_rate — o rate-limit do hid-nintendo que
#             derruba o 8BitDo/Pro Controller em BT (provado ao vivo 2026-07-18);
#   [BT-HCI]  timeout/erro do hci no kernel — PREVENTIVO (zero histórico local:
#             silencioso até a 1ª ocorrência real, nada de alarmar o leigo);
#   [XHCI]    reset/morte do host USB — PREVENTIVO (idem);
#   [BT-ERR]  delta dos contadores RX/TX errors do adaptador (hciconfig), lido a
#             cada HEFESTO_KERNELWATCH_BT_INTERVAL s (default 300) — só loga
#             quando o contador PIOROU (pega rádio sujo sem btmon intrusivo).
#
# Log: ~/.local/state/hefesto-dualsense4unix/kernel.log (novo nome). O antigo
# storm.log é PRESERVADO se existir (histórico); se não existir, vira symlink
# para kernel.log (compat para humanos e scripts antigos).
#
# Não precisa de sudo se o usuário puder ler o journal do kernel (grupo
# systemd-journal/adm — padrão no Pop!_OS). Se não puder, registra a orientação
# e sai com erro (o serviço re-tenta com backoff, RestartSec=300).
#
# Hooks de teste (PUROS: stdin/args → stdout; não tocam journal nem estado):
#   --classify                              lê linhas short-iso do stdin e as
#                                           escreve com a TAG classificada
#   --test-bt-delta P_RX P_TX C_RX C_TX DEV emite a linha [BT-ERR] se delta > 0
#
# Uso manual: bash scripts/storm_watch.sh   (Ctrl+C encerra)
set -uo pipefail

# União dos padrões vigiados (case-insensitive; `can.t` cobre o apóstrofo).
# [USB-71] = regexes já provadas do doctor.sh (batalha de maio) + can't add hid.
GREP_UNION="error -71|can.t add hid device|device descriptor read/64, error|not accepting address|unable to enumerate usb device|joycon_enforce_subcmd_rate|bluetooth: hci[0-9].*(timeout|failed|error)|xhci_hcd.*(reset|died|timeout|halt)"

# Classificador: linha short-iso do journal → "TIMESTAMP [TAG] mensagem".
# Ordem: do mais específico para o mais genérico (JOYCON antes de USB-71 etc.).
# mawk-compatível (sem IGNORECASE): casa sobre tolower($0).
classify() {
    awk '
    {
        low = tolower($0)
        tag = "[KERNEL]"
        if (low ~ /joycon_enforce_subcmd_rate/) tag = "[JOYCON]"
        else if (low ~ /error -71|can.t add hid device|device descriptor read\/64, error|not accepting address|unable to enumerate usb device/) tag = "[USB-71]"
        else if (low ~ /xhci_hcd.*(reset|died|timeout|halt)/) tag = "[XHCI]"
        else if (low ~ /bluetooth: hci[0-9].*(timeout|failed|error)/) tag = "[BT-HCI]"
        # short-iso: "TS host identificador: msg" → "TS [TAG] msg"
        ts = $1
        rest = $0
        sub(/^[^ ]+ +/, "", rest)     # remove o timestamp
        sub(/^[^ ]+ +/, "", rest)     # remove o hostname
        sub(/^[^ ]+: +/, "", rest)    # remove "kernel:" / "bluetoothd[pid]:"
        print ts " " tag " " rest
    }'
}

# Contadores de erro do adaptador BT: imprime "RX TX" (0 0 se ilegível).
bt_read_errors() {
    local dev="$1"
    hciconfig "${dev}" 2>/dev/null | awk '
        /RX bytes/ { for (i = 1; i <= NF; i++) if ($i ~ /^errors:/) { split($i, a, ":"); rx = a[2] } }
        /TX bytes/ { for (i = 1; i <= NF; i++) if ($i ~ /^errors:/) { split($i, a, ":"); tx = a[2] } }
        END { if (rx == "") rx = 0; if (tx == "") tx = 0; print rx, tx }'
}

# Linha [BT-ERR] SÓ quando o delta é positivo (silencioso enquanto saudável).
bt_emit_delta() {
    local prev_rx="$1" prev_tx="$2" cur_rx="$3" cur_tx="$4" dev="$5"
    local d_rx=$((cur_rx - prev_rx)) d_tx=$((cur_tx - prev_tx))
    if (( d_rx > 0 || d_tx > 0 )); then
        printf '%s [BT-ERR] %s delta rx_errors=+%d tx_errors=+%d (acumulado %d/%d)\n' \
            "$(date '+%Y-%m-%dT%H:%M:%S%z')" "${dev}" "${d_rx}" "${d_tx}" \
            "${cur_rx}" "${cur_tx}"
    fi
}

# Loop lateral: snapshot dos contadores por adaptador; emite só o delta.
bt_delta_loop() {
    command -v hciconfig >/dev/null 2>&1 || return 0
    local interval="${HEFESTO_KERNELWATCH_BT_INTERVAL:-300}"
    declare -A prev_rx prev_tx
    local path dev rx tx
    while :; do
        for path in /sys/class/bluetooth/hci*; do
            [[ -e "${path}" ]] || continue
            dev="$(basename "${path}")"
            read -r rx tx <<<"$(bt_read_errors "${dev}")"
            if [[ -n "${prev_rx[${dev}]:-}" ]]; then
                bt_emit_delta "${prev_rx[${dev}]}" "${prev_tx[${dev}]}" \
                    "${rx}" "${tx}" "${dev}" >>"${LOG}"
            fi
            prev_rx[${dev}]="${rx}"
            prev_tx[${dev}]="${tx}"
        done
        sleep "${interval}"
    done
}

# ---- hooks de teste (puros, saem antes de tocar estado/journal) --------------
case "${1:-}" in
    --classify)
        classify
        exit 0
        ;;
    --test-bt-delta)
        shift
        bt_emit_delta "$@"
        exit 0
        ;;
esac

# ---- serviço de verdade ------------------------------------------------------
STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/hefesto-dualsense4unix"
mkdir -p "${STATE_DIR}"
LOG="${STATE_DIR}/kernel.log"
LEGACY_LOG="${STATE_DIR}/storm.log"

# Compat: storm.log preservado se for arquivo real; symlink se não existir.
if [[ ! -e "${LEGACY_LOG}" && ! -L "${LEGACY_LOG}" ]]; then
    ln -s "kernel.log" "${LEGACY_LOG}" 2>/dev/null || true
fi

if ! command -v journalctl >/dev/null 2>&1; then
    echo "# $(date '+%F %T') kernel-watch: journalctl ausente — abortando" >>"${LOG}"
    exit 1
fi

# Probe de permissão: lê 1 linha do kernel. Se falhar, o usuário não tem acesso
# ao journal do kernel — orienta e sai (serviço re-tenta com RestartSec).
if ! journalctl -k -n1 >/dev/null 2>&1; then
    {
        echo "# $(date '+%F %T') kernel-watch: sem permissão p/ 'journalctl -k'."
        echo "#   Adicione seu usuário ao grupo: sudo usermod -aG systemd-journal \"\$USER\""
        echo "#   (relogin necessário). Re-tentando em background."
    } >>"${LOG}"
    exit 1
fi

echo "# $(date '+%F %T') kernel-watch iniciado (padrões: USB-71 JOYCON BT-HCI XHCI + contadores hci; preventivos ficam silenciosos até a 1ª ocorrência)" >>"${LOG}"

bt_delta_loop &
BT_LOOP_PID=$!
trap 'kill "${BT_LOOP_PID}" 2>/dev/null' EXIT INT TERM

# -f follow, -n0 começa do agora (o journald já guarda histórico), short-iso p/
# timestamp estável. Fontes: kernel (+ = OU lógico) e o bluetoothd (unit).
# --case-sensitive=false: sem smartcase surpresa ("Bluetooth: hci" tem maiúscula).
journalctl -f -n0 -o short-iso --case-sensitive=false --grep="${GREP_UNION}" \
    _TRANSPORT=kernel + _SYSTEMD_UNIT=bluetooth.service \
    2>>"${LOG}" | classify >>"${LOG}"

echo "# $(date '+%F %T') kernel-watch terminou inesperadamente (journalctl caiu?) — a unit re-tenta" >>"${LOG}"
exit 1
