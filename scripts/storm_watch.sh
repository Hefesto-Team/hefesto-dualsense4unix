#!/usr/bin/env bash
set -uo pipefail

GREP_UNION="error -71|can.t add hid device|device descriptor read/64, error|not accepting address|unable to enumerate usb device|joycon_enforce_subcmd_rate|probe - fail = -|failed to get joycon info|init over bluetooth failed|output queue is full|bt socket write error|link tx timeout|killing stalled connection|command 0x[0-9a-f]{4} tx timeout|read reg16 failed|failed to generate devcoredump|crc.s check failed|bluetooth: hci[0-9].*(timeout|failed|error)|xhci_hcd.*(reset|died|timeout|halt)|: reset [a-z -]+ usb device number [0-9]+ using|usb [0-9]+-[0-9.]+: usb disconnect, device number [0-9]+|usb [0-9]+-[0-9.]+: new [a-z -]+ usb device number [0-9]+ using|playstation 0005:[0-9a-f:.]+: probe with driver playstation failed"

_escolher_awk() {
    if [[ -z "$(awk -W interactive 'BEGIN { exit 0 }' </dev/null 2>&1 || echo falhou)" ]]; then
        echo "awk -W interactive"
    else
        echo "awk"
    fi
}
_AWK_CMD="$(_escolher_awk)"

classify() {
    ${_AWK_CMD:-awk} \
        -v janela="${HEFESTO_KERNELWATCH_JANELA_S:-10}" \
        -v resumo="${HEFESTO_KERNELWATCH_RESUMO_S:-60}" \
        -v queda_s="${HEFESTO_KERNELWATCH_QUEDA_S:-1}" '
    # "2026-09-22T16:46:32-03:00" -> segundos. O fuso é ignorado de propósito:
    # só se compara hora com hora do MESMO fluxo. Aritmética de calendário
    # (dias desde 1970) em vez de mktime(), que nem todo awk tem.
    function segundos(ts,   y, mo, d, yy, era, yoe, mm, doy, doe) {
        y = substr(ts, 1, 4) + 0; mo = substr(ts, 6, 2) + 0; d = substr(ts, 9, 2) + 0
        if (y < 1970 || mo < 1 || mo > 12 || d < 1) return -1
        yy = (mo <= 2) ? y - 1 : y
        era = int(yy / 400); yoe = yy - era * 400
        mm = (mo > 2) ? mo - 3 : mo + 9
        doy = int((153 * mm + 2) / 5) + d - 1
        doe = yoe * 365 + int(yoe / 4) - int(yoe / 100) + doy
        return (era * 146097 + doe - 719468) * 86400 \
            + substr(ts, 12, 2) * 3600 + substr(ts, 15, 2) * 60 + substr(ts, 18, 2)
    }
    # ".691289" da hora precisa do journal ("...:28.691289-03:00"); 0 quando a hora não a traz.
    # Os dígitos viram inteiro e se dividem depois: o ponto decimal "+0" quebra no locale pt_BR.
    function fracao(ts,   d, m, i) {
        if (substr(ts, 20, 1) != ".") return 0
        if (!match(substr(ts, 20), /^\.[0-9]+/)) return 0
        d = substr(ts, 21, RLENGTH - 1)
        m = 1
        for (i = 0; i < length(d); i++) m *= 10
        return (d + 0) / m
    }
    function fechar(k) {
        if (extra[k] > 0)
            print ultts[k] " " tagk[k] " repetiu +" extra[k] " (" total[k] " desde " inits[k] ", " (ult[k] - ini[k]) " s): " texto[k]
        delete ult[k]; delete ini[k]; delete extra[k]; delete total[k]
        delete ultts[k]; delete inits[k]; delete tagk[k]; delete texto[k]; delete rep[k]
    }
    {
        low = tolower($0)
        tag = "[KERNEL]"
        borda = 0
        if (low ~ /joycon_enforce_subcmd_rate/) tag = "[JOYCON]"
        else if (low ~ /probe - fail = -|failed to get joycon info|init over bluetooth failed/) tag = "[JOYCON-PROBE]"
        else if (low ~ /playstation 0005:[0-9a-f:.]+: probe with driver playstation failed/) tag = "[PROBE-PERDIDA]"
        else if (low ~ /: reset [a-z -]+ usb device number [0-9]+ using/) tag = "[USB-RESET]"
        else if (low ~ /error -71|can.t add hid device|device descriptor read\/64, error|not accepting address|unable to enumerate usb device/) tag = "[USB-71]"
        else if (low ~ /output queue is full/) { tag = "[FILA-CHEIA]"; borda = 1 }
        else if (low ~ /bt socket write error/) { tag = "[BT-SOCKET]"; borda = 1 }
        else if (low ~ /link tx timeout|killing stalled connection/) { tag = "[ENLACE-PARADO]"; borda = 1 }
        else if (low ~ /command 0x[0-9a-f][0-9a-f][0-9a-f][0-9a-f] tx timeout|read reg16 failed|failed to generate devcoredump/) { tag = "[BT-TRAVADO]"; borda = 1 }
        else if (low ~ /crc.s check failed/) { tag = "[CRC]"; borda = 1 }
        else if (low ~ /xhci_hcd.*(reset|died|timeout|halt)/) { tag = "[XHCI]"; borda = 1 }
        else if (low ~ /bluetooth: hci[0-9].*(timeout|failed|error)/) { tag = "[BT-HCI]"; borda = 1 }
        # short-iso: "TS host identificador: msg" → "TS [TAG] msg"
        ts = $1
        tsp = ts
        sub(/\.[0-9]+/, "", ts)      # o log segue com a hora em segundos; a precisa é só da queda
        rest = $0
        sub(/^[^ ]+ +/, "", rest)     # remove o timestamp
        sub(/^[^ ]+ +/, "", rest)     # remove o hostname
        sub(/^[^ ]+: +/, "", rest)    # remove "kernel:" / "bluetoothd[pid]:"
        t = segundos(ts)
        # Rajadas de OUTRA chave que esfriaram também fecham aqui: sem timer,
        # a chegada de qualquer linha é o relógio. A distância é em módulo: o
        # journal intercala kernel e bluetoothd, e um salto para trás também é
        # outra rajada.
        if (t >= 0) {
            for (j in ult) {
                dist = t - ult[j]
                if (dist < 0) dist = -dist
                if (dist > janela) fechar(j)
            }
        }
        # A queda: "USB disconnect" e o "new ... USB device number" da MESMA porta em até queda_s
        # (21/11/2026: 353 ms, na 3-1.4, sem reset no meio). Só controladora física: o pad virtual
        # do produto (vhci_hcd) é desfeito e recriado pelo serviço, e não é queda de cabo. Quem
        # sai de vez (o disconnect sem aparelho novo) não gera linha.
        if (t >= 0) {
            tf = t + fracao(tsp)
            for (pq in saiu_em) if (tf - saiu_em[pq] > queda_s) delete saiu_em[pq]
            baixo = tolower(rest)
            if (baixo ~ /^usb [0-9]+-[0-9.]+: usb disconnect, device number [0-9]+/) {
                split(rest, dq, " ")
                pq = dq[2]; sub(/:$/, "", pq)
                nq = rest; sub(/^.*device number /, "", nq); sub(/[^0-9].*$/, "", nq)
                saiu_em[pq] = tf; saiu_n[pq] = nq
                next
            }
            if (baixo ~ /^usb [0-9]+-[0-9.]+: new [a-z -]+ usb device number [0-9]+ using /) {
                split(rest, dq, " ")
                pq = dq[2]; sub(/:$/, "", pq)
                if (pq in saiu_em) {
                    hq = rest; sub(/^.* using /, "", hq); sub(/[^A-Za-z0-9_.-].*$/, "", hq)
                    if (hq != "vhci_hcd") {
                        vq = rest; sub(/^[^:]*: new /, "", vq); sub(/ USB device number.*$/, "", vq)
                        dn = rest; sub(/^.*USB device number /, "", dn); sub(/[^0-9].*$/, "", dn)
                        print tsp " [USB-QUEDA] usb " pq ": USB disconnect, device number " saiu_n[pq] ", voltou em " int((tf - saiu_em[pq]) * 1000 + 0.5) " ms como new " vq " USB device number " dn " using " hq
                        fflush()
                    }
                    delete saiu_em[pq]; delete saiu_n[pq]
                }
                next
            }
        }
        if (!borda || t < 0) {
            print ts " " tag " " rest
            fflush()
            next
        }
        split(rest, campo, " ")
        k = tag " " campo[1] " " campo[2]
        if (k in ult) {
            extra[k]++; total[k]++; ult[k] = t; ultts[k] = ts
            if (t - rep[k] >= resumo) {
                print ts " " tag " segue +" extra[k] " (" total[k] " desde " inits[k] ", " (t - ini[k]) " s): " texto[k]
                extra[k] = 0; rep[k] = t
                fflush()
            }
            next
        }
        ini[k] = t; ult[k] = t; rep[k] = t; extra[k] = 0; total[k] = 1
        inits[k] = ts; ultts[k] = ts; tagk[k] = tag; texto[k] = rest
        print ts " " tag " " rest
        fflush()
    }
    END {
        for (j in ult) fechar(j)
        fflush()
    }'
}

bt_read_errors() {
    local dev="$1"
    hciconfig "${dev}" 2>/dev/null | awk '
        /RX bytes/ { for (i = 1; i <= NF; i++) if ($i ~ /^errors:/) { split($i, a, ":"); rx = a[2] } }
        /TX bytes/ { for (i = 1; i <= NF; i++) if ($i ~ /^errors:/) { split($i, a, ":"); tx = a[2] } }
        END { if (rx == "") rx = 0; if (tx == "") tx = 0; print rx, tx }'
}

bt_emit_delta() {
    local prev_rx="$1" prev_tx="$2" cur_rx="$3" cur_tx="$4" dev="$5"
    local d_rx=$((cur_rx - prev_rx)) d_tx=$((cur_tx - prev_tx))
    if (( d_rx > 0 || d_tx > 0 )); then
        printf '%s [BT-ERR] %s delta rx_errors=+%d tx_errors=+%d (acumulado %d/%d)\n' \
            "$(date '+%Y-%m-%dT%H:%M:%S%z')" "${dev}" "${d_rx}" "${d_tx}" \
            "${cur_rx}" "${cur_tx}"
    fi
}

bt_sem_contador() {
    printf '%s [BT-SEM-CONTADOR] contadores de erro do rádio não medidos: o hciconfig (única fonte do ioctl HCIGETDEVINFO) foi depreciado pelo BlueZ e não está nesta máquina; btmgmt/bluetoothctl não o substituem. Sem [BT-ERR] neste log = medida ausente, NÃO rádio limpo\n' \
        "$(date '+%Y-%m-%dT%H:%M:%S%z')"
}

bt_delta_loop() {
    if ! command -v hciconfig >/dev/null 2>&1; then
        bt_sem_contador >>"${LOG}"
        return 0
    fi
    local interval="${HEFESTO_KERNELWATCH_BT_INTERVAL:-300}"
    declare -A prev_rx prev_tx
    local path dev rx tx
    while :; do
        for path in /sys/class/bluetooth/hci*; do
            [[ -e "${path}" ]] || continue
            dev="$(basename "${path}")"
            [[ "${dev}" =~ ^hci[0-9]+$ ]] || continue
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

desde_do_journal() {
    local marca="$1" boot="$2"
    if [[ -n "${boot}" && "$(cat "${marca}" 2>/dev/null || true)" != "${boot}" ]]; then
        printf '%s\n' "${boot}" >"${marca}" 2>/dev/null || true
        printf '%s\n' -b --lines=all
    else
        printf '%s\n' -n0
    fi
}

SYSFS_USB="${HEFESTO_KERNELWATCH_SYSFS_USB:-/sys/bus/usb/devices}"

PONTE="${HEFESTO_KERNELWATCH_PONTE:-/usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh}"
SUDO="${HEFESTO_KERNELWATCH_SUDO:-sudo}"

RELIGAR_ESPERAS="${HEFESTO_KERNELWATCH_RELIGAR_ESPERAS:-3 7 10}"

porta_da_mensagem() {
    local alvo
    [[ "$1" =~ ^[[:space:]]*[^[:space:]]+[[:space:]]+([^[:space:]]+):[[:space:]] ]] || return 0
    alvo="${BASH_REMATCH[1]}"
    if [[ "${alvo}" =~ ^usb([0-9]+)-port([0-9]+)$ ]]; then
        printf '%s-%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
    elif [[ "${alvo}" =~ ^([0-9]+-[0-9]+(\.[0-9]+)*)-port([0-9]+)$ ]]; then
        printf '%s.%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[3]}"
    elif [[ "${alvo}" =~ ^([0-9]+-[0-9]+(\.[0-9]+)*):[0-9]+\.[0-9]+$ ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
    elif [[ "${alvo}" =~ ^[0-9]+-[0-9]+(\.[0-9]+)*$ ]]; then
        printf '%s\n' "${alvo}"
    fi
}

lugar_da_porta() {
    local porta="$1" real parte pci=""
    local -a partes
    [[ "${porta}" =~ ^[0-9]+-[0-9]+(\.[0-9]+)*$ ]] || return 0
    real="$(readlink -f -- "${SYSFS_USB}/usb${porta%%-*}" 2>/dev/null)" || return 0
    IFS=/ read -ra partes <<<"${real}"
    for parte in "${partes[@]}"; do
        [[ "${parte}" =~ ^0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]$ ]] && pci="${parte}"
    done
    [[ -n "${pci}" ]] && printf 'pci-%s-usb-0:%s\n' "${pci}" "${porta#*-}"
    return 0
}

python_do_produto() {
    local py="${HEFESTO_KERNELWATCH_PYTHON:-}" lancador linha=""
    lancador="${HEFESTO_KERNELWATCH_LANCADOR:-${HOME}/.local/bin/hefesto-dualsense4unix}"
    if [[ -z "${py}" && -r "${lancador}" ]]; then
        IFS= read -r linha <"${lancador}" || true
        [[ "${linha}" == "#!"* ]] && py="${linha#\#!}"
    fi
    [[ -n "${py}" && -x "${py}" ]] && printf '%s\n' "${py}"
    return 0
}

levar_ao_diario() {
    local o_que="$1" quando="$2" mensagem="$3" py rc artigo="o"
    [[ "${o_que}" == "queda" ]] && artigo="a"
    py="$(python_do_produto)"
    if [[ -z "${py}" ]]; then
        printf '# %s kernel-watch: %s %s não entrou no usb-diario, o python do produto não foi achado: %s\n' \
            "$(date '+%F %T')" "${artigo}" "${o_que}" "${mensagem}"
        return 0
    fi
    timeout 30 "${py}" -m hefesto_dualsense4unix.integrations.diario_do_usb "${o_que}" \
        --quando "${quando}" --mensagem "${mensagem}" --raiz-usb "${SYSFS_USB}" \
        </dev/null >/dev/null 2>&1
    rc=$?
    if (( rc != 0 && rc != 3 )); then
        printf '# %s kernel-watch: %s %s não entrou no usb-diario (saída %d): %s\n' \
            "$(date '+%F %T')" "${artigo}" "${o_que}" "${rc}" "${mensagem}"
    fi
    return 0
}

_RELIGA_O_CABO='\[usb-71\] usbhid [0-9.:-]+: (can.t add hid device|probe with driver usbhid failed)'
pede_religar() {
    local baixa="${1,,}"
    [[ "${baixa}" =~ ${_RELIGA_O_CABO} ]] && return 0
    [[ "${baixa}" == *" [probe-perdida] "* ]]
}

RELIGAR_VOLTAS=3
religar_em_fundo() {
    local trava="$1"
    printf '.' >>"${trava}" 2>/dev/null || true
    # shellcheck disable=SC2094
    (
        if command -v flock >/dev/null 2>&1; then
            flock -n 9 || exit 0
        fi
        [[ -x "${PONTE}" ]] || exit 0
        "${SUDO}" -n -l "${PONTE}" religar-orfaos >/dev/null 2>&1 || exit 0
        volta=1
        while :; do
            esvaziar=1
            for espera in ${RELIGAR_ESPERAS}; do
                sleep "${espera}"
                if (( esvaziar )); then
                    : >"${trava}" 2>/dev/null || true
                    esvaziar=0
                fi
                timeout 60 "${SUDO}" -n "${PONTE}" religar-orfaos >/dev/null 2>&1 || true
            done
            if [[ ! -s "${trava}" ]] || (( volta >= RELIGAR_VOLTAS )); then
                break
            fi
            volta=$((volta + 1))
        done
    ) 9>>"${trava}" </dev/null >/dev/null 2>&1 &
}

anotar() {
    local trava="${1:-}" linha porta lugar reset_de="" reset_em="" queda_de="" queda_em=""
    while IFS= read -r linha || [[ -n "${linha}" ]]; do
        reset_de=""
        queda_de=""
        if [[ "${linha}" == *" [USB-RESET] "* && "${linha}" != *" · lugar "* ]]; then
            reset_em="${linha%% *}"
            reset_de="${linha#* \[USB-RESET\] }"
            porta="$(porta_da_mensagem "${reset_de}")"
            lugar=""
            [[ -n "${porta}" ]] && lugar="$(lugar_da_porta "${porta}")"
            [[ -n "${lugar}" ]] && linha="${linha} · lugar ${lugar}"
        elif [[ "${linha}" == *" [USB-QUEDA] "* && "${linha}" != *" · lugar "* ]]; then
            queda_em="${linha%% *}"
            queda_de="${linha#* \[USB-QUEDA\] }"
            porta="$(porta_da_mensagem "${queda_de}")"
            lugar=""
            [[ -n "${porta}" ]] && lugar="$(lugar_da_porta "${porta}")"
            [[ -n "${lugar}" ]] && linha="${linha} · lugar ${lugar}"
        elif [[ "${linha}" == *" [USB-71] "* && "${linha}" != *" · lugar "* ]]; then
            porta="$(porta_da_mensagem "${linha#* \[USB-71\] }")"
            lugar=""
            [[ -n "${porta}" ]] && lugar="$(lugar_da_porta "${porta}")"
            [[ -n "${lugar}" ]] && linha="${linha} · lugar ${lugar}"
        fi
        printf '%s\n' "${linha}"
        [[ -n "${reset_de}" ]] && levar_ao_diario reset "${reset_em}" "${reset_de}"
        [[ -n "${queda_de}" ]] && levar_ao_diario queda "${queda_em}" "${queda_de}"
        if [[ -n "${trava}" ]] && pede_religar "${linha}"; then
            religar_em_fundo "${trava}"
        fi
    done
}

case "${1:-}" in
    --classify)
        classify
        exit 0
        ;;
    --test-lugar)
        while IFS= read -r mensagem || [[ -n "${mensagem}" ]]; do
            porta="$(porta_da_mensagem "${mensagem}")"
            lugar=""
            [[ -n "${porta}" ]] && lugar="$(lugar_da_porta "${porta}")"
            printf '%s\t%s\n' "${porta}" "${lugar}"
        done
        exit 0
        ;;
    --test-anotar)
        if [[ -z "${HEFESTO_KERNELWATCH_SUDO:-}" || -z "${2:-}" ]]; then
            echo "storm_watch.sh --test-anotar: precisa de HEFESTO_KERNELWATCH_SUDO e da trava" >&2
            exit 2
        fi
        anotar "$2"
        wait
        exit 0
        ;;
    --test-bt-delta)
        shift
        bt_emit_delta "$@"
        exit 0
        ;;
    --test-bt-sem-contador)
        bt_sem_contador
        exit 0
        ;;
    --test-desde)
        desde_do_journal "${2:-}" "${3:-}"
        exit 0
        ;;
esac

STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/hefesto-dualsense4unix"
mkdir -p "${STATE_DIR}"
LOG="${STATE_DIR}/kernel.log"
LEGACY_LOG="${STATE_DIR}/storm.log"

TRAVA_DO_RELIGAR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hefesto-dualsense4unix"
if mkdir -p "${TRAVA_DO_RELIGAR}" 2>/dev/null && [[ -w "${TRAVA_DO_RELIGAR}" ]]; then
    TRAVA_DO_RELIGAR="${TRAVA_DO_RELIGAR}/kernel-watch.religar"
else
    TRAVA_DO_RELIGAR="${STATE_DIR}/kernel-watch.religar"
fi

if [[ ! -e "${LEGACY_LOG}" && ! -L "${LEGACY_LOG}" ]]; then
    ln -s "kernel.log" "${LEGACY_LOG}" 2>/dev/null || true
fi

if ! command -v journalctl >/dev/null 2>&1; then
    echo "# $(date '+%F %T') kernel-watch: journalctl ausente — abortando" >>"${LOG}"
    exit 1
fi

if ! journalctl -k -n1 >/dev/null 2>&1; then
    {
        echo "# $(date '+%F %T') kernel-watch: sem permissão p/ 'journalctl -k'."
        echo "#   Adicione seu usuário ao grupo: sudo usermod -aG systemd-journal \"\$USER\""
        echo "#   (relogin necessário). Re-tentando em background."
    } >>"${LOG}"
    exit 1
fi

mapfile -t DESDE < <(desde_do_journal "${STATE_DIR}/kernel-watch.boot" \
    "$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)")
if [[ "${DESDE[0]:-}" == "-b" ]]; then
    echo "# $(date '+%F %T') kernel-watch: primeira volta deste boot — relendo o arranque (o -71 da enumeração nasce antes da vigia)" >>"${LOG}"
fi
echo "# $(date '+%F %T') kernel-watch iniciado (padrões: USB-71 USB-RESET USB-QUEDA JOYCON JOYCON-PROBE PROBE-PERDIDA FILA-CHEIA BT-SOCKET ENLACE-PARADO BT-TRAVADO CRC BT-HCI XHCI + contadores hci; preventivos ficam silenciosos até a 1ª ocorrência; rajada vira borda + resumo; o -71, o reset e a queda levam o lugar, e o reset e a queda entram no usb-diario; a probe perdida chama o religar)" >>"${LOG}"

bt_delta_loop &
trap 'kill $(jobs -p) 2>/dev/null' EXIT
trap 'exit 0' INT TERM

journalctl -f "${DESDE[@]}" -o short-iso-precise --case-sensitive=false --grep="${GREP_UNION}" \
    _TRANSPORT=kernel + _SYSTEMD_UNIT=bluetooth.service \
    2>>"${LOG}" | classify | anotar "${TRAVA_DO_RELIGAR}" >>"${LOG}" &
wait "$!"

echo "# $(date '+%F %T') kernel-watch terminou inesperadamente (journalctl caiu?) — a unit re-tenta" >>"${LOG}"
exit 1
