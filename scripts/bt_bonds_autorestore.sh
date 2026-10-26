#!/usr/bin/env bash
set -euo pipefail

SRC_ROOT="${HEFESTO_BT_BONDS_SRC:-/var/lib/hefesto-dualsense4unix/bt-bonds}"
DST="${HEFESTO_BT_DST:-/var/lib/bluetooth}"
MAX_IDADE_H="${HEFESTO_BT_AUTORESTORE_IDADE_H:-24}"
FREIO_MAX="${HEFESTO_BT_AUTORESTORE_FREIO_MAX:-1}"
AGORA="${HEFESTO_BT_AGORA:-$(date +%s)}"
BOOT_ID="${HEFESTO_BT_BOOT_ID:-$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo desconhecido)}"

LEDGER="${SRC_ROOT}/.autorestore-ledger"
LAPIDES="${SRC_ROOT}/.lapides"

_MAC_RE='^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$'

QUIET=0
FORCE=0
DRY=0
STATUS=0
for _arg in "$@"; do
    case "${_arg}" in
        --quiet)   QUIET=1 ;;
        --force)   FORCE=1 ;;
        --dry-run) DRY=1 ;;
        --status)  STATUS=1 ;;
        *) printf 'bt_bonds_autorestore.sh: argumento desconhecido: %s\n' "${_arg}" >&2; exit 2 ;;
    esac
done

LOG_TAG=hefesto-bt-autorestore
LOG_DEST="${HEFESTO_BT_LOG_DEST:-}"
_registrar() {
    case "${LOG_DEST}" in
        "")   logger -t "${LOG_TAG}" "$*" 2>/dev/null || true ;;
        none) : ;;
        *)    printf '%s %s: %s\n' "$(date -Is 2>/dev/null || true)" "${LOG_TAG}" "$*" \
                  2>/dev/null >>"${LOG_DEST}" || true ;;
    esac
}

log() {
    [[ "${QUIET}" -eq 1 ]] || printf '%s\n' "$*"
    _registrar "$*"
}

if [[ "${STATUS}" -eq 1 ]]; then
    if [[ -f "${LEDGER}" ]]; then
        cat "${LEDGER}"
    else
        printf 'nenhuma restauração automática registrada\n'
    fi
    exit 0
fi

if [[ "${FORCE}" -eq 0 ]]; then
    case "${SERVICE_RESULT:-}" in
        success)
            log "parada limpa do bluetooth.service (SERVICE_RESULT=success) — nada a restaurar"
            exit 0
            ;;
        "")
            log "sem SERVICE_RESULT (execução fora da unit) — nada a restaurar; use --force para forçar"
            exit 0
            ;;
    esac
    log "bluetooth.service morreu (SERVICE_RESULT=${SERVICE_RESULT}${EXIT_STATUS:+/${EXIT_STATUS}}) — conferindo bonds"
fi

if [[ "${DST}" == "/var/lib/bluetooth" ]]; then
    if [[ "$(id -u)" -ne 0 ]]; then
        printf 'bt_bonds_autorestore.sh: requer root\n' >&2
        exit 1
    fi
    if [[ "${DRY}" -eq 0 ]] \
       && command -v systemctl >/dev/null 2>&1 \
       && systemctl is-active --quiet bluetooth.service 2>/dev/null; then
        log "bluetooth.service ainda ATIVO — não escrevo no storage por baixo dele"
        exit 0
    fi
fi

[[ -d "${SRC_ROOT}" ]] || { log "sem acervo em ${SRC_ROOT} — nada a restaurar"; exit 0; }
[[ -d "${DST}" ]] || { log "sem ${DST} — nada a restaurar"; exit 0; }

_arquivo_confiavel() {
    local caminho="$1" nlink
    [[ -L "${caminho}" ]] && return 1
    [[ -f "${caminho}" ]] || return 1
    nlink="$(stat -c '%h' "${caminho}" 2>/dev/null || echo 1)"
    [[ "${nlink}" -eq 1 ]] || return 1
    return 0
}

_tem_chave() {
    grep -qE '^\[(LinkKey|LongTermKey|PeripheralLongTermKey)\]' "$1" 2>/dev/null
}

_epoch_do_snapshot() {
    local n="$1"
    [[ "${n}" =~ ^([0-9]{8})-([0-9]{6}) ]] || return 1
    local d="${BASH_REMATCH[1]}" t="${BASH_REMATCH[2]}"
    date -d "${d:0:4}-${d:4:2}-${d:6:2} ${t:0:2}:${t:2:2}:${t:4:2}" +%s 2>/dev/null
}

_restauros_neste_boot() {
    local chave="$1" n=0 boot ts alvo
    [[ -f "${LEDGER}" ]] || { printf '0\n'; return 0; }
    while read -r boot ts alvo; do
        [[ "${ts}" =~ ^[0-9]+$ ]] || continue
        [[ "${boot}" == "${BOOT_ID}" ]] || continue
        [[ "${alvo}" == "${chave}" ]] || continue
        n=$((n + 1))
    done < "${LEDGER}"
    printf '%s\n' "${n}"
}

CORTE_IDADE=$((AGORA - MAX_IDADE_H * 3600))

declare -A LAPIDE=()
if [[ -f "${LAPIDES}" && ! -L "${LAPIDES}" ]]; then
    while read -r _quando _adaptador _controle _resto; do
        [[ "${_quando}" =~ ^[0-9]+$ ]] || continue
        [[ "${_adaptador}" =~ ${_MAC_RE} && "${_controle}" =~ ${_MAC_RE} ]] || continue
        _par="${_adaptador^^}/${_controle^^}"
        if [[ -z "${LAPIDE[${_par}]:-}" || "${_quando}" -gt "${LAPIDE[${_par}]}" ]]; then
            LAPIDE["${_par}"]="${_quando}"
        fi
    done < "${LAPIDES}"
fi

RESTAURADOS=0
SUSPENSOS=0
ENTERRADOS=0
declare -A JA_VISTO=()

while IFS= read -r SNAP; do
    NOME="$(basename "${SNAP}")"
    [[ "${NOME}" == .* ]] && continue
    EPOCH="$(_epoch_do_snapshot "${NOME}" || true)"
    [[ -n "${EPOCH}" ]] || continue
    [[ "${EPOCH}" -ge "${CORTE_IDADE}" ]] || continue

    while IFS= read -r -d '' ADAPTER; do
        ABASE="$(basename "${ADAPTER}")"
        [[ "${ABASE}" =~ ${_MAC_RE} ]] || continue
        [[ -L "${ADAPTER}" ]] && continue

        while IFS= read -r -d '' DEVDIR; do
            DBASE="$(basename "${DEVDIR}")"
            [[ "${DBASE}" == "cache" ]] && continue
            [[ "${DBASE}" =~ ${_MAC_RE} ]] || continue
            [[ -L "${DEVDIR}" ]] && continue

            CHAVE="${ABASE}/${DBASE}"
            [[ -n "${JA_VISTO[${CHAVE}]:-}" ]] && continue

            SRC_INFO="${DEVDIR}/info"
            _arquivo_confiavel "${SRC_INFO}" || continue
            _tem_chave "${SRC_INFO}" || continue

            DST_INFO="${DST}/${CHAVE}/info"
            if [[ -f "${DST_INFO}" ]] && _tem_chave "${DST_INFO}"; then
                JA_VISTO["${CHAVE}"]=vivo
                continue
            fi

            _enterrado_em="${LAPIDE[${CHAVE^^}]:-}"
            if [[ -n "${_enterrado_em}" && "${EPOCH}" -le "${_enterrado_em}" ]]; then
                JA_VISTO["${CHAVE}"]=enterrado
                ENTERRADOS=$((ENTERRADOS + 1))
                log "LÁPIDE: ${DBASE} foi esquecido de propósito em ${ABASE} — o snapshot ${NOME} é de antes disso, e ele não volta"
                continue
            fi

            JA_VISTO["${CHAVE}"]=tratado

            N_NESTE_BOOT="$(_restauros_neste_boot "${CHAVE}")"
            if [[ "${N_NESTE_BOOT}" -ge "${FREIO_MAX}" ]]; then
                log "QUARENTENA: ${DBASE} já voltou ${N_NESTE_BOOT}x neste boot e sumiu de novo — restauração SUSPENSA (chave provavelmente rotacionada pelo controle; insistir realimenta o laço de autenticação). O gesto que resolve: bluetoothctl remove ${DBASE} e parear outra vez"
                SUSPENSOS=$((SUSPENSOS + 1))
                continue
            fi

            if [[ "${DRY}" -eq 1 ]]; then
                log "DRY-RUN: restauraria ${CHAVE} de ${NOME}"
                RESTAURADOS=$((RESTAURADOS + 1))
                continue
            fi

            install -d -m 700 "${DST}/${ABASE}" 2>/dev/null || true
            install -d -m 700 "${DST}/${CHAVE}" 2>/dev/null || {
                log "não consegui criar ${DST}/${CHAVE} — pulando"
                continue
            }
            install -m 600 "${SRC_INFO}" "${DST_INFO}"
            SRC_ATTR="${DEVDIR}/attributes"
            if _arquivo_confiavel "${SRC_ATTR}"; then
                install -m 600 "${SRC_ATTR}" "${DST}/${CHAVE}/attributes"
            fi
            SRC_CACHE="${ADAPTER}/cache/${DBASE}"
            DST_CACHE="${DST}/${ABASE}/cache/${DBASE}"
            if [[ ! -e "${DST_CACHE}" ]] && _arquivo_confiavel "${SRC_CACHE}" \
               && grep -q '^\[ServiceRecords\]' "${SRC_CACHE}" 2>/dev/null; then
                install -d -m 700 "${DST}/${ABASE}/cache" 2>/dev/null || true
                install -m 600 "${SRC_CACHE}" "${DST_CACHE}" 2>/dev/null || true
            fi

            printf '%s %s %s\n' "${BOOT_ID}" "${AGORA}" "${CHAVE}" >> "${LEDGER}"
            chmod 600 "${LEDGER}" 2>/dev/null || true
            RESTAURADOS=$((RESTAURADOS + 1))
            log "bond de ${DBASE} restaurado do snapshot ${NOME} (sumiu do disco; nenhuma chave viva foi sobrescrita)"
        done < <(find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
    done < <(find "${SNAP}" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
done < <(find "${SRC_ROOT}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort -r)

if [[ "${RESTAURADOS}" -eq 0 && "${SUSPENSOS}" -eq 0 && "${ENTERRADOS}" -eq 0 ]]; then
    log "nenhum bond faltando — nada a restaurar"
elif [[ "${ENTERRADOS}" -eq 0 ]]; then
    log "restauração automática: ${RESTAURADOS} bond(s) de volta, ${SUSPENSOS} suspenso(s) pelo freio"
else
    log "restauração automática: ${RESTAURADOS} bond(s) de volta, ${SUSPENSOS} suspenso(s) pelo freio, ${ENTERRADOS} esquecido(s) de propósito ficaram onde estão"
fi
exit 0
