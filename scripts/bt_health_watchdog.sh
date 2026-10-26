#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${SUDO_UID:-}" || -n "${SUDO_USER:-}" ]]; then
    unset HEFESTO_BT_SRC HEFESTO_BT_STAMP_DIR HEFESTO_HIDRAW_ROOT HEFESTO_RADIO_DIARIO_ROOT HEFESTO_RADIO_TRAVA HEFESTO_RADIO_TRAVA_PRAZO_S
fi
JANELA_MIN=10
LIMIAR_RECUSAS=8
LIMIAR_APARELHOS=2
RATE_LIMIT_S=600
STAMP_RESTART=/run/hefesto-bt-watchdog.restart-stamp
STAMP_DIR=/run/hefesto-bt-watchdog
LOG_TAG=hefesto-bt-watchdog

LOG_DEST="${HEFESTO_BT_LOG_DEST:-}"
_registrar() {
    case "${LOG_DEST}" in
        "")   logger -t "${LOG_TAG}" "$*" 2>/dev/null || true ;;
        none) : ;;
        *)    printf '%s %s: %s\n' "$(date -Is 2>/dev/null || true)" "${LOG_TAG}" "$*" \
                  2>/dev/null >>"${LOG_DEST}" || true ;;
    esac
}
log() { _registrar "$*"; printf '%s\n' "$*"; }

_json_texto() {
    local s="${1:-}"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="$(printf '%s' "${s}" | tr '\000-\037' ' ')"
    printf '"%s"' "${s}"
}

_diario_escrever() {
    local alvo="${1:-}" linha tamanho
    [[ -n "${alvo}" ]] || return 0
    [[ -L "${alvo}" ]] && return 0
    linha="{\"quando\": $(_json_texto "$(date -Iseconds 2>/dev/null || true)"), \"carimbo\": $(date +%s), \"quem\": $(_json_texto "$2"), \"o_que\": $(_json_texto "$3"), \"por_que\": $(_json_texto "$4"), \"antes\": ${5:-null}, \"depois\": ${6:-null}${7:+, $7}}"
    install -d -m 0755 "${alvo%/*}" 2>/dev/null || true
    tamanho="$(stat -c %s "${alvo}" 2>/dev/null || echo 0)"
    if [[ "${tamanho}" -gt 524288 ]]; then
        mv -f -- "${alvo}" "${alvo}.1" 2>/dev/null || true
    fi
    printf '%s\n' "${linha}" >>"${alvo}" 2>/dev/null || true
    return 0
}

DIARIO_DO_RADIO="${HEFESTO_RADIO_DIARIO_ROOT:-}"
if [[ -z "${DIARIO_DO_RADIO}" && -z "${HEFESTO_BT_SRC:-}" ]]; then
    DIARIO_DO_RADIO="/var/lib/hefesto-dualsense4unix/radio-diario.jsonl"
fi
_diario() { _diario_escrever "${DIARIO_DO_RADIO}" "bt-watchdog" "$@"; }

TRAVA_DO_RADIO="${HEFESTO_RADIO_TRAVA:-}"
if [[ -z "${TRAVA_DO_RADIO}" && -z "${HEFESTO_BT_SRC:-}" ]]; then
    TRAVA_DO_RADIO="/run/hefesto-dualsense4unix/radio.lock"
fi
PRAZO_DA_TRAVA_S="${HEFESTO_RADIO_TRAVA_PRAZO_S:-60}"
[[ "${PRAZO_DA_TRAVA_S}" =~ ^[0-9]+$ ]] || PRAZO_DA_TRAVA_S=60
TRAVA_FD=""

_pegar_a_trava() {
    local dono inicio fim milis
    if [[ -z "${TRAVA_DO_RADIO}" ]]; then
        log "árvore do BlueZ desviada e sem HEFESTO_RADIO_TRAVA: sigo sem a trava (a comum é a da máquina)"
        return 0
    fi
    if [[ ! -d "${TRAVA_DO_RADIO%/*}" ]]; then
        log "sem a trava comum do rádio (${TRAVA_DO_RADIO%/*} não existe — é o install que a cria); sigo sem ela"
        return 0
    fi
    if [[ -L "${TRAVA_DO_RADIO}" ]]; then
        log "recusando a trava do rádio: ${TRAVA_DO_RADIO} é link simbólico; sigo sem ela"
        return 0
    fi
    if ! exec {TRAVA_FD}<>"${TRAVA_DO_RADIO}"; then
        log "não consegui abrir a trava do rádio (${TRAVA_DO_RADIO}); sigo sem ela"
        TRAVA_FD=""
        return 0
    fi
    if ! flock -n "${TRAVA_FD}"; then
        dono="$(head -n1 -- "${TRAVA_DO_RADIO}" 2>/dev/null | cut -c1-120 || true)"
        inicio="$(date +%s%N)"
        if ! flock -w "${PRAZO_DA_TRAVA_S}" "${TRAVA_FD}"; then
            _diario "desistiu da trava" "${dono:-outro motor} segurou a trava por mais de ${PRAZO_DA_TRAVA_S} s" \
                "{\"dono\": $(_json_texto "${dono}")}" "{\"espera_s\": ${PRAZO_DA_TRAVA_S}}"
            log "a trava do rádio ficou com ${dono:-outro motor} por ${PRAZO_DA_TRAVA_S} s — pulo este tique"
            return 1
        fi
        fim="$(date +%s%N)"
        milis=$(( (fim - inicio) / 1000000 ))
        _diario "esperou a trava" "${dono:-outro motor} estava com ela" \
            "{\"dono\": $(_json_texto "${dono}")}" \
            "{\"espera_s\": $(printf '%d.%03d' $((milis / 1000)) $((milis % 1000)))}"
    fi
    printf 'bt-watchdog %s\n' "$$" 1>&"${TRAVA_FD}" 2>/dev/null || true
    return 0
}

_dbus_device_paths() {
    busctl tree org.bluez --list 2>/dev/null \
        | grep -oE '/org/bluez/hci[0-9]+/dev_[0-9A-Fa-f_]+$' | sort -u || true
}
_dbus_device_prop() {
    busctl get-property org.bluez "$1" org.bluez.Device1 "$2" 2>/dev/null \
        | awk '{print $2}' || true
}
_btctl_lento() {
    local espera="$1"; shift
    { printf '%s\n' "$*"; sleep "${espera}"; printf 'quit\n'; } \
        | command timeout "$((espera + 10))" bluetoothctl >/dev/null 2>&1
}

BT_STORAGE="${HEFESTO_BT_SRC:-/var/lib/bluetooth}"
HIDRAW_ROOT="${HEFESTO_HIDRAW_ROOT:-/sys/class/hidraw}"
_uniqs_hidraw() {
    local f u
    for f in "${HIDRAW_ROOT}"/*/device/uevent; do
        [[ -r "${f}" ]] || continue
        u="$(grep -m1 '^HID_UNIQ=' "${f}" 2>/dev/null | cut -d= -f2)"
        if [[ -n "${u}" ]]; then
            printf '%s\n' "${u,,}"
        fi
    done
}

if [[ "$(id -u)" -ne 0 ]] && [[ "${BT_STORAGE}" == "/var/lib/bluetooth" ]]; then
    printf 'bt_health_watchdog.sh: requer root\n' >&2
    exit 1
fi
STAMP_DIR="${HEFESTO_BT_STAMP_DIR:-${STAMP_DIR}}"
install -d -m 700 "${STAMP_DIR}"

vigia_sdp_cache() {
    local UNIQS PATHS INFO DEVDIR MAC ADPDIR CACHE OBJ TENTATIVA
    UNIQS="$(_uniqs_hidraw)"
    PATHS="$(_dbus_device_paths)"
    while IFS= read -r INFO; do
        [[ -z "${INFO}" ]] && continue
        DEVDIR="$(dirname "${INFO}")"
        MAC="$(basename "${DEVDIR}")"
        ADPDIR="$(dirname "${DEVDIR}")"
        CACHE="${ADPDIR}/cache/${MAC}"

        grep -qi '^Services=.*00001124-0000-1000-8000-00805f9b34fb' "${INFO}" 2>/dev/null || continue

        OBJ="$(grep -im1 "/dev_${MAC//:/_}\$" <<<"${PATHS}" || true)"
        if [[ -z "${OBJ}" ]]; then
            log "device ${MAC} tem bond em disco mas nenhum objeto D-Bus (adaptador ausente?) — pulando nesta rodada"
            continue
        fi
        [[ "$(_dbus_device_prop "${OBJ}" Connected)" == "true" ]] || continue
        grep -qix "${MAC,,}" <<<"${UNIQS}" && continue
        grep -q '^\[ServiceRecords\]' "${CACHE}" 2>/dev/null && continue

        log "controle ${MAC} ZUMBI (conectado, SDP não-resolvido, zero hidraw) — forçando SDP browse via Connect()"
        _diario "forçou o SDP por Connect()" "conectado, sem registro SDP e sem hidraw" \
            "{\"sdp\": false}" null "\"controle\": $(_json_texto "${MAC}")"
        for TENTATIVA in 1 2 3 4 5 6; do
            busctl call org.bluez "${OBJ}" org.bluez.Device1 Connect >/dev/null 2>&1 || true
            sleep 2
            if grep -q '^\[ServiceRecords\]' "${CACHE}" 2>/dev/null; then
                log "SDP de ${MAC} resolvido na tentativa ${TENTATIVA} — [ServiceRecords] gravado; o HID sobe sozinho"
                break
            fi
            [[ "$(_dbus_device_prop "${OBJ}" Connected)" == "true" ]] || {
                log "ACL de ${MAC} caiu durante o browse — retomo no próximo tick (ou aperte PS)"
                break
            }
        done
        if ! grep -q '^\[ServiceRecords\]' "${CACHE}" 2>/dev/null; then
            if ! command -v sdptool >/dev/null 2>&1; then
                log "SDP de ${MAC} não resolveu em 6 tentativas e NÃO SEI dizer qual das duas causas é: o browse direto exigia o 'sdptool', depreciado pelo BlueZ e ausente nesta máquina (pacote bluez-deprecated / bluez-deprecated-tools), e nenhuma ferramenta viva o substitui. Instale-o para a vigia voltar a distinguir 'direção da conexão' de 'controle travado'. Enquanto isso: se o próximo tick também não resolver, trate como controle travado — reset de hardware do controle (furinho atrás, ~5 s com um clipe)"
            elif ! timeout 20 sdptool browse "${MAC}" >/dev/null 2>&1; then
                log "controle ${MAC} NÃO responde SDP (browse direto estoura) — o link sobe mas o stack do controle está travado; re-parear NÃO resolve. Cura: reset de hardware do controle (furinho atrás, ~5 s com um clipe) e ligar de novo"
            else
                log "SDP de ${MAC} não resolveu em 6 tentativas mas o device responde ao browse direto — o doctor aponta; último recurso é bluetoothctl remove ${MAC} + re-parear"
            fi
        fi
    done < <(find "${BT_STORAGE}" -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | sort)
}

if [[ "${1:-}" == "--sdp-cache-only" ]]; then
    vigia_sdp_cache
    exit 0
fi

_inteiro_ou_nada() {
    local v="${1:-}"
    if [[ "${v}" =~ ^0[xX][0-9a-fA-F]{1,16}$ ]]; then
        printf '%d' "$((v))"
        return 0
    fi
    if [[ "${v}" =~ ^(0+|[1-9][0-9]{0,17})$ ]]; then
        printf '%d' "$((10#${v}))"
        return 0
    fi
    return 1
}
_e_controle_pelo_anuncio() {
    local c a
    if c="$(_inteiro_ou_nada "${1:-}")"; then
        if (( ((c >> 8) & 0x1F) == 0x05 && (c & 0xC0) == 0 )); then
            case $(( (c >> 2) & 0x0F )) in
                1|2) return 0 ;;
            esac
        fi
    fi
    if a="$(_inteiro_ou_nada "${2:-}")"; then
        if (( a == 0x03C3 || a == 0x03C4 )); then
            return 0
        fi
    fi
    return 1
}
_e_controle() {
    _e_controle_pelo_anuncio "$(_dbus_device_prop "$1" Class)" "$(_dbus_device_prop "$1" Appearance)"
}
if [[ "${1:-}" == "--e-controle" ]]; then
    if _e_controle_pelo_anuncio "${2:-}" "${3:-}"; then
        exit 0
    fi
    exit 1
fi

if [[ "${1:-}" == "--so-a-trava" ]]; then
    _pegar_a_trava || exit 3
    sleep "${2:-0}"
    exit 0
fi

_pegar_a_trava || exit 0

_ACTIVE=/usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh
[[ -x "${_ACTIVE}" ]] && "${_ACTIVE}" --quiet 2>/dev/null || true

vigia_rebind_orfaos() {
    local _s
    for _s in \
        /usr/local/lib/hefesto-dualsense4unix/bt_rebind_orphans.sh \
        "$(dirname "$(readlink -f "$0")")/bt_rebind_orphans.sh" \
    ; do
        if [[ -x "${_s}" ]]; then
            "${_s}" --quiet || true
            return 0
        fi
    done
    return 0
}

command -v busctl >/dev/null 2>&1 || { log "busctl ausente — nada a vigiar no rádio"; vigia_rebind_orfaos; exit 0; }
systemctl is-active --quiet bluetooth.service || { log "bluetooth.service inativo — nada a vigiar no rádio"; vigia_rebind_orfaos; exit 0; }

DEVICE_PATHS="$(_dbus_device_paths)"
RECUSAS=0
RECUSAS_ORFAS=0
MACS_RECUSADOS=""
while IFS= read -r MAC; do
    [[ -z "${MAC}" ]] && continue
    if grep -qi "dev_${MAC//:/_}$" <<<"${DEVICE_PATHS}"; then
        RECUSAS=$((RECUSAS + 1))
        MACS_RECUSADOS+="${MAC,,}"$'\n'
    else
        RECUSAS_ORFAS=$((RECUSAS_ORFAS + 1))
    fi
done < <(journalctl -u bluetooth --since "-${JANELA_MIN} min" --no-pager 2>/dev/null \
    | grep -E 'Refusing connection from .*: unknown device|error updating services' \
    | grep -oE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' || true)
if [[ "${RECUSAS_ORFAS}" -gt 0 ]]; then
    log "${RECUSAS_ORFAS} recusa(s) de MAC sem objeto no BlueZ ignoradas (órfão re-tentando; daemon são)"
fi
APARELHOS_RECUSADOS=0
if [[ -n "${MACS_RECUSADOS}" ]]; then
    APARELHOS_RECUSADOS="$(printf '%s' "${MACS_RECUSADOS}" | sort -u | grep -c . || true)"
fi

CONECTADOS=0
while IFS= read -r OBJ; do
    [[ -z "${OBJ}" ]] && continue
    if [[ "$(_dbus_device_prop "${OBJ}" Connected)" == "true" ]]; then
        CONECTADOS=$((CONECTADOS + 1))
    fi
done <<<"${DEVICE_PATHS}"

if [[ "${RECUSAS}" -ge "${LIMIAR_RECUSAS}" ]]; then
    if [[ "${APARELHOS_RECUSADOS}" -lt "${LIMIAR_APARELHOS}" ]]; then
        log "AVISO: ${RECUSAS} recusa(s)/${JANELA_MIN}min concentradas em ${APARELHOS_RECUSADOS} aparelho(s) — parece bond perdido do aparelho, não daemon doente; restart NÃO resolveria (ver VIGIA-QUE-DERRUBA-01)"
    elif [[ "${CONECTADOS}" -gt 0 ]]; then
        log "estado doente suspeito (${RECUSAS} recusas/${JANELA_MIN}min) mas há ${CONECTADOS} device(s) conectado(s) — restart adiado (nunca derrubo sessão viva)"
    else
        AGORA="$(date +%s)"
        ULTIMO=0
        [[ -f "${STAMP_RESTART}" ]] && ULTIMO="$(cat "${STAMP_RESTART}" 2>/dev/null || echo 0)"
        if (( AGORA - ULTIMO < RATE_LIMIT_S )); then
            log "estado doente (${RECUSAS} recusas/${JANELA_MIN}min) — restart segurado pelo rate-limit"
        else
            log "estado doente confirmado (${RECUSAS} recusas/${JANELA_MIN}min, 0 conectados) — reiniciando bluetooth.service"
            printf '%s' "${AGORA}" > "${STAMP_RESTART}"
            _diario "reiniciou o bluetooth.service" \
                "estado doente: ${RECUSAS} recusas de ${APARELHOS_RECUSADOS} aparelhos em ${JANELA_MIN} min, nenhum conectado" \
                "{\"recusas\": ${RECUSAS}, \"conectados\": 0}" null
            systemctl restart bluetooth.service || log "restart do bluetooth.service FALHOU"
        fi
    fi
fi

while IFS= read -r OBJ; do
    [[ -z "${OBJ}" ]] && continue
    [[ "$(_dbus_device_prop "${OBJ}" Bonded)" == "true" ]] || continue
    [[ "$(_dbus_device_prop "${OBJ}" Trusted)" == "false" ]] || continue
    _e_controle "${OBJ}" || continue
    MAC_TRUST="${OBJ##*dev_}"
    MAC_TRUST="${MAC_TRUST//_/:}"
    if busctl set-property org.bluez "${OBJ}" org.bluez.Device1 Trusted b true 2>/dev/null; then
        log "device ${MAC_TRUST} tinha bond mas estava SEM trust (reconexão entrante recusada como 'unknown device') — Trusted=true aplicado"
        _diario "aplicou Trusted=true" "bond sem trust: a reconexão entrante era recusada" \
            "{\"trusted\": false}" "{\"trusted\": true}" \
            "\"controle\": $(_json_texto "${MAC_TRUST}"), \"hci\": $(_json_texto "$(cut -d/ -f4 <<<"${OBJ}")")"
    else
        log "falha ao aplicar Trusted=true em ${MAC_TRUST} — o doctor vai apontar"
    fi
done <<<"${DEVICE_PATHS}"

while IFS= read -r OBJ; do
    [[ -z "${OBJ}" ]] && continue
    [[ "$(_dbus_device_prop "${OBJ}" Connected)" == "true" ]] || continue
    MAC_U="${OBJ##*dev_}"
    MAC="${MAC_U//_/:}"
    PAIRED="$(_dbus_device_prop "${OBJ}" Paired)"
    BONDED="$(_dbus_device_prop "${OBJ}" Bonded)"
    [[ -z "${BONDED}" ]] && continue
    if [[ "${BONDED}" == "false" ]]; then
        _e_controle "${OBJ}" || continue
        STAMP="${STAMP_DIR}/promoted-${MAC//:/-}"
        if [[ -f "${STAMP}" ]]; then
            log "bond temporário persiste em ${MAC} (Paired=${PAIRED}, Bonded=false) — promoção já tentada neste boot; re-pair manual necessário (bluetoothctl remove + pair)"
            continue
        fi
        : > "${STAMP}"
        log "device conectado com bond TEMPORÁRIO (${MAC}: Paired=${PAIRED}, Bonded=false) — tentando promover via Pair() explícito"
        _btctl_lento 25 pair "${MAC}" || true
        _btctl_lento 5 trust "${MAC}" || true
        BONDED2="$(_dbus_device_prop "${OBJ}" Bonded)"
        _diario "promoveu o bond temporário" "conectado com Paired e sem Bonded: o bond evaporaria no desligar" \
            "{\"bonded\": false}" "{\"bonded\": $([[ "${BONDED2}" == "true" ]] && echo true || echo false)}" \
            "\"controle\": $(_json_texto "${MAC}")"
        if [[ "${BONDED2}" == "true" ]]; then
            log "bond de ${MAC} promovido e persistido (Bonded=true)"
            /usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh --quiet 2>/dev/null || true
        else
            log "promoção de ${MAC} NÃO persistiu (Bonded=${BONDED2:-?}) — o doctor vai apontar; cura manual: bluetoothctl remove ${MAC} e re-parear em modo pareamento"
        fi
    fi
done <<<"${DEVICE_PATHS}"


vigia_sdp_cache

vigia_rebind_orfaos

vigia_adaptador_travado() {
    local _s
    [[ -z "${HEFESTO_BT_SRC:-}" ]] || return 0
    for _s in \
        /usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh \
        "$(dirname "$(readlink -f "$0")")/bt_ponte_privilegiada.sh" \
    ; do
        if [[ -x "${_s}" ]]; then
            "${_s}" reiniciar-travado >/dev/null 2>&1 || true
            return 0
        fi
    done
    return 0
}

vigia_adaptador_travado
exit 0
