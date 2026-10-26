#!/usr/bin/env bash
set -euo pipefail

QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

SRC="${HEFESTO_BT_SRC:-/var/lib/bluetooth}"
DST_ROOT="${HEFESTO_BT_SNAP_ROOT:-/var/lib/hefesto-dualsense4unix/bt-bonds}"
KEEP=12

LOG_TAG=hefesto-bt-bonds
LOG_DEST="${HEFESTO_BT_LOG_DEST:-}"
_registrar() {
    case "${LOG_DEST}" in
        "")   logger -t "${LOG_TAG}" "$*" 2>/dev/null || true ;;
        none) : ;;
        *)    printf '%s %s: %s\n' "$(date -Is 2>/dev/null || true)" "${LOG_TAG}" "$*" \
                  2>/dev/null >>"${LOG_DEST}" || true ;;
    esac
}

log() { [[ "${QUIET}" -eq 1 ]] || printf '%s\n' "$*"; _registrar "$*"; }

if [[ "${SRC}" == "/var/lib/bluetooth" ]] && [[ "$(id -u)" -ne 0 ]]; then
    printf 'bt_bonds_snapshot.sh: requer root\n' >&2
    exit 1
fi

[[ -d "${SRC}" ]] || { log "sem ${SRC} — nada a fotografar"; exit 0; }

mapfile -t INFOS < <(find "${SRC}" -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | sort)
if [[ "${#INFOS[@]}" -eq 0 ]]; then
    log "zero bonds em disco — snapshot recusado de propósito (não sobrescrevo backup bom com vazio)"
    exit 0
fi

mapfile -t SIG_ARQUIVOS < <(
    {
        printf '%s\n' "${INFOS[@]}"
        find "${SRC}" -mindepth 2 -maxdepth 2 -type f 2>/dev/null
        find "${SRC}" -mindepth 3 -maxdepth 3 -type f ! -name info 2>/dev/null
        for _I in "${INFOS[@]}"; do
            _DEV="$(dirname "${_I}")"
            _C="$(dirname "${_DEV}")/cache/$(basename "${_DEV}")"
            [[ -f "${_C}" ]] && printf '%s\n' "${_C}"
        done
    } | sort -u
)
SIG="$( { printf 'FMT=2\n'; printf '%s\n' "${SIG_ARQUIVOS[@]}"; cat "${SIG_ARQUIVOS[@]}" 2>/dev/null; } | sha256sum | awk '{print $1}')"

install -d -m 700 "${DST_ROOT}"

if [[ -n "${SERVICE_RESULT:-}" ]]; then
    ESPERA_LOCK=(-n)
else
    ESPERA_LOCK=(-w 30)
fi
exec 9>"${DST_ROOT}/.lock"
if ! flock "${ESPERA_LOCK[@]}" 9; then
    if [[ -n "${SERVICE_RESULT:-}" ]]; then
        log "outro snapshot em andamento e este é o gancho de parada — desisto na hora (esperar aqui é Bluetooth fora do ar; o timer e a borda udev cobrem)"
    else
        log "outro snapshot em andamento há >30s — desisto (o timer cobre)"
    fi
    exit 0
fi

LAST_SIG_FILE="${DST_ROOT}/.last-signature"
if [[ -f "${LAST_SIG_FILE}" ]] && [[ "$(cat "${LAST_SIG_FILE}" 2>/dev/null)" == "${SIG}" ]]; then
    log "estado idêntico ao último snapshot — no-op"
    exit 0
fi

TS="$(date +%Y%m%d-%H%M%S)-$$"
DST="${DST_ROOT}/${TS}"
if ! install -d -m 700 "${DST}" 2>/dev/null; then
    log "não consegui criar ${DST} (ambiente restrito no stop?) — snapshot fica pro próximo timer"
    exit 0
fi

while IFS= read -r -d '' ADAPTER; do
    BASE="$(basename "${ADAPTER}")"
    install -d -m 700 "${DST}/${BASE}"
    find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type f -exec cp -a {} "${DST}/${BASE}/" \;
    while IFS= read -r -d '' DEVDIR; do
        [[ "$(basename "${DEVDIR}")" == "cache" ]] && continue
        cp -a "${DEVDIR}" "${DST}/${BASE}/"
    done < <(find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type d -print0)
    if [[ -d "${ADAPTER}/cache" ]]; then
        N_CACHE=0
        while IFS= read -r -d '' DEVDIR; do
            MAC="$(basename "${DEVDIR}")"
            [[ -f "${ADAPTER}/cache/${MAC}" ]] || continue
            install -d -m 700 "${DST}/${BASE}/cache"
            cp -a "${ADAPTER}/cache/${MAC}" "${DST}/${BASE}/cache/"
            N_CACHE=$((N_CACHE + 1))
        done < <(find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type d ! -name cache -print0)
        [[ "${N_CACHE}" -gt 0 ]] && log "cache SDP de ${N_CACHE} device(s) com bond incluído"
    fi
done < <(find "${SRC}" -mindepth 1 -maxdepth 1 -type d -print0)

chmod -R go-rwx "${DST}"
printf '%s' "${SIG}" > "${LAST_SIG_FILE}"
chmod 600 "${LAST_SIG_FILE}"
log "snapshot de bonds gravado em ${DST} (${#INFOS[@]} bond(s))"

mapfile -t TODOS < <(find "${DST_ROOT}" -mindepth 1 -maxdepth 1 -type d | sort)
MELHOR=""
MELHOR_N=-1
for D in "${TODOS[@]:-}"; do
    [[ -n "${D}" ]] || continue
    N_D="$(find "${D}" -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | wc -l)"
    if [[ "${N_D}" -ge "${MELHOR_N}" ]]; then
        MELHOR_N="${N_D}"
        MELHOR="${D}"
    fi
done
mapfile -t OLD < <(printf '%s\n' "${TODOS[@]:-}" | head -n -"${KEEP}")
for D in "${OLD[@]:-}"; do
    [[ -n "${D}" ]] || continue
    if [[ "${D}" == "${MELHOR}" ]]; then
        log "poda: ${D##*/} é o melhor snapshot do acervo (${MELHOR_N} bond(s)) — preservado"
        continue
    fi
    rm -rf "${D}"
done
exit 0
