#!/usr/bin/env bash
set -euo pipefail
_ajuda() {
  cat <<'AJUDA'
bt_rebind_orphans.sh — recupera o controle Bluetooth que PERDEU A PROBE e
ficou órfão (device HID existente, driver NENHUM). Cura de PRIMEIRA LINHA da
contenção de probe: um rebind no driver VANILLA in-tree, sem patch de kernel,
sem reboot e sem tocar em quem já está funcionando.

Uso:
  bt_rebind_orphans.sh              cura (requer root p/ escrever no sysfs)
  bt_rebind_orphans.sh --dry-run    só relata o que faria (não requer root)
  bt_rebind_orphans.sh --quiet      só fala quando age ou falha
  bt_rebind_orphans.sh --evento     a passada do aviso do kernel
AJUDA
}
if [[ -n "${SUDO_UID:-}" || -n "${SUDO_USER:-}" ]]; then
    unset HEFESTO_REBIND_MAX_TENTATIVAS HEFESTO_REBIND_STAMP_DIR HEFESTO_HID_DEVICES_DIR HEFESTO_HID_DRIVERS_DIR HEFESTO_USB_DEVICES_DIR HEFESTO_USB_DRIVERS_DIR
fi

MAX_TENTATIVAS="${HEFESTO_REBIND_MAX_TENTATIVAS:-3}"
STAMP_DIR="${HEFESTO_REBIND_STAMP_DIR:-/run/hefesto-bt-rebind}"
LOG_TAG=hefesto-bt-rebind
HID_DEVICES="${HEFESTO_HID_DEVICES_DIR:-/sys/bus/hid/devices}"
HID_DRIVERS="${HEFESTO_HID_DRIVERS_DIR:-/sys/bus/hid/drivers}"
if [[ -n "${HEFESTO_USB_DEVICES_DIR:-}" ]]; then
    USB_DEVICES="${HEFESTO_USB_DEVICES_DIR}"
elif [[ -n "${HEFESTO_HID_DEVICES_DIR:-}" ]]; then
    USB_DEVICES=""
else
    USB_DEVICES=/sys/bus/usb/devices
fi
USB_DRIVERS="${HEFESTO_USB_DRIVERS_DIR:-/sys/bus/usb/drivers}"

DRY_RUN=0
QUIET=0
EVENTO=0
for arg in "$@"; do
    case "${arg}" in
        --dry-run) DRY_RUN=1 ;;
        --quiet)   QUIET=1 ;;
        --evento)  EVENTO=1 ;;
        -h|--help)
            _ajuda
            exit 0
            ;;
        *)
            printf 'uso: %s [--dry-run] [--quiet] [--evento]\n' "$(basename "$0")" >&2
            exit 2
            ;;
    esac
done

PREFIXO=""
DE_NOVO="nova tentativa na próxima passagem do watchdog"
QUAL=""
if [[ "${EVENTO}" -eq 1 ]]; then
    PREFIXO="evento-"
    DE_NOVO="o kernel-watch tenta de novo em segundos, e depois o watchdog"
    QUAL=", na hora do aviso do kernel"
fi

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
    _registrar "$*"
    printf '%s\n' "$*"
}
log_info() { [[ "${QUIET}" -eq 1 ]] && return 0; log "$*"; }

_bus_de() { printf '%s' "${1%%:*}"; }
_vid_de() { local r="${1#*:}"; printf '%s' "${r%%:*}"; }

_e_candidato() {
    local id="$1" bus vid
    bus="$(_bus_de "${id}")"
    vid="$(_vid_de "${id}" | tr 'a-f' 'A-F')"
    [[ "${bus}" == "0005" ]] || return 1
    [[ "${vid}" == "054C" ]] || return 1
    return 0
}

curados=0
falhados=0
ignorados=0
esgotados=0
orfaos=0

shopt -s nullglob
for dev in "${HID_DEVICES}"/*; do
    [[ -e "${dev}/driver" ]] && continue
    id="$(basename "${dev}")"
    orfaos=$((orfaos + 1))

    if ! _e_candidato "${id}"; then
        log_info "device HID órfão FORA do escopo, ignorado: ${id} (só curamos Sony 054C no barramento 0005/Bluetooth)"
        ignorados=$((ignorados + 1))
        continue
    fi

    bind="${HID_DRIVERS}/playstation/bind"
    if [[ ! -w "${bind}" && "${DRY_RUN}" -eq 0 ]]; then
        if [[ ! -e "${bind}" ]]; then
            log "driver playstation ausente em ${HID_DRIVERS} — módulo não carregado; NÃO carregamos módulo aqui (derrubaria os DualSense em uso). ${id} segue órfão"
        else
            log "sem permissão de escrita em ${bind} (rode como root) — ${id} segue órfão"
        fi
        falhados=$((falhados + 1))
        continue
    fi

    stamp="${STAMP_DIR}/${PREFIXO}${id}"
    tentativas=0
    [[ -f "${stamp}" ]] && tentativas="$(cat "${stamp}" 2>/dev/null || printf '0')"
    [[ "${tentativas}" =~ ^[0-9]+$ ]] || tentativas=0

    if [[ "${tentativas}" -ge "${MAX_TENTATIVAS}" ]]; then
        if [[ "${EVENTO}" -eq 0 && ! -f "${stamp}.desisti" ]]; then
            [[ "${DRY_RUN}" -eq 0 ]] && : > "${stamp}.desisti" 2>/dev/null || true
            log "DESISTINDO de ${id} após ${MAX_TENTATIVAS} rebinds sem sucesso — não é a contenção transiente de probe (essa cura de primeira); provável controle travado ou link ruim. Cura manual: desligue o controle (PS 10 s), reconecte; se insistir, 'bluetoothctl remove <MAC>' e re-pareie"
        fi
        esgotados=$((esgotados + 1))
        continue
    fi

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "[dry-run] faria: echo '${id}' > ${bind} (tentativa $((tentativas + 1))/${MAX_TENTATIVAS}${QUAL})"
        curados=$((curados + 1))
        continue
    fi

    mkdir -p "${STAMP_DIR}" 2>/dev/null || true
    printf '%s' "$((tentativas + 1))" > "${stamp}" 2>/dev/null || true

    if printf '%s' "${id}" > "${bind}" 2>/dev/null && [[ -e "${dev}/driver" ]]; then
        log "controle órfão RECUPERADO por rebind${QUAL}: ${id} (perdeu a probe por contenção de canal de controle; o device estava íntegro)"
        rm -f "${STAMP_DIR}/${id}" "${STAMP_DIR}/${id}.desisti" "${STAMP_DIR}/evento-${id}" 2>/dev/null || true
        curados=$((curados + 1))
    else
        log "rebind de ${id} NÃO pegou (tentativa $((tentativas + 1))/${MAX_TENTATIVAS}${QUAL}) — ${DE_NOVO}"
        falhados=$((falhados + 1))
    fi
done
shopt -u nullglob

_cabo_do_stamp_vive() {
    local resto="${1#cabo-}" intf devnum
    intf="${resto%-*}"
    devnum="${resto##*-}"
    [[ -n "${USB_DEVICES}" && -e "${USB_DEVICES}/${intf}" ]] || return 1
    [[ "$(cat "${USB_DEVICES}/${intf%%:*}/devnum" 2>/dev/null || true)" == "${devnum}" ]]
}

if [[ -n "${USB_DEVICES}" ]]; then
    shopt -s nullglob
    for intf in "${USB_DEVICES}"/*:*; do
        nome="$(basename "${intf}")"
        [[ "${nome}" =~ ^[0-9]+-[0-9]+(\.[0-9]+)*:[0-9]+\.[0-9]+$ ]] || continue
        [[ "$(cat "${intf}/bInterfaceClass" 2>/dev/null || true)" == "03" ]] || continue
        [[ -e "${intf}/driver" ]] && continue
        [[ "$(cat "${intf}/authorized" 2>/dev/null || true)" == "0" ]] && continue
        porta="${nome%%:*}"
        orfaos=$((orfaos + 1))

        vid="$(cat "${USB_DEVICES}/${porta}/idVendor" 2>/dev/null || true)"
        if [[ "${vid,,}" != "054c" ]]; then
            log_info "interface HID órfã FORA do escopo, ignorada: ${nome} (só religamos a HID de um controle Sony 054c no cabo)"
            ignorados=$((ignorados + 1))
            continue
        fi

        bind="${USB_DRIVERS}/usbhid/bind"
        if [[ ! -w "${bind}" && "${DRY_RUN}" -eq 0 ]]; then
            if [[ ! -e "${bind}" ]]; then
                log "driver usbhid ausente em ${USB_DRIVERS} — NÃO carregamos módulo aqui. ${nome} segue sem o HID"
            else
                log "sem permissão de escrita em ${bind} (rode como root) — ${nome} segue sem o HID"
            fi
            falhados=$((falhados + 1))
            continue
        fi

        devnum="$(cat "${USB_DEVICES}/${porta}/devnum" 2>/dev/null || true)"
        [[ "${devnum}" =~ ^[0-9]+$ ]] || devnum=0
        chave="cabo-${nome}-${devnum}"
        stamp="${STAMP_DIR}/${PREFIXO}${chave}"
        tentativas=0
        [[ -f "${stamp}" ]] && tentativas="$(cat "${stamp}" 2>/dev/null || printf '0')"
        [[ "${tentativas}" =~ ^[0-9]+$ ]] || tentativas=0

        if [[ "${tentativas}" -ge "${MAX_TENTATIVAS}" ]]; then
            if [[ "${EVENTO}" -eq 0 && ! -f "${stamp}.desisti" ]]; then
                [[ "${DRY_RUN}" -eq 0 ]] && : > "${stamp}.desisti" 2>/dev/null || true
                log "DESISTINDO do controle do cabo em ${porta} após ${MAX_TENTATIVAS} religadas da HID sem sucesso — não é a probe perdida por um -71 solto; o cabo ou a entrada seguem falhando. Tire e ponha o cabo; se voltar a cair ali, troque de entrada"
            fi
            esgotados=$((esgotados + 1))
            continue
        fi

        if [[ "${DRY_RUN}" -eq 1 ]]; then
            log "[dry-run] faria: echo '${nome}' > ${bind} (tentativa $((tentativas + 1))/${MAX_TENTATIVAS}${QUAL})"
            curados=$((curados + 1))
            continue
        fi

        mkdir -p "${STAMP_DIR}" 2>/dev/null || true
        printf '%s' "$((tentativas + 1))" > "${stamp}" 2>/dev/null || true

        if printf '%s' "${nome}" > "${bind}" 2>/dev/null && [[ -e "${intf}/driver" ]]; then
            log "controle do cabo RELIGADO em ${porta}${QUAL}: a HID (${nome}) tinha perdido a probe no -71; o aparelho estava inteiro"
            rm -f "${STAMP_DIR}/${chave}" "${STAMP_DIR}/${chave}.desisti" "${STAMP_DIR}/evento-${chave}" 2>/dev/null || true
            curados=$((curados + 1))
        else
            log "religar a HID de ${nome} NÃO pegou (tentativa $((tentativas + 1))/${MAX_TENTATIVAS}${QUAL}) — ${DE_NOVO}"
            falhados=$((falhados + 1))
        fi
    done
    shopt -u nullglob
fi

if [[ "${DRY_RUN}" -eq 0 && -d "${STAMP_DIR}" ]]; then
    shopt -s nullglob
    for stamp in "${STAMP_DIR}"/*; do
        alvo="$(basename "${stamp}")"
        alvo="${alvo%.desisti}"
        alvo="${alvo#evento-}"
        case "${alvo}" in
            cabo-*) _cabo_do_stamp_vive "${alvo}" || rm -f "${stamp}" 2>/dev/null || true ;;
            *) [[ -e "${HID_DEVICES}/${alvo}" ]] || rm -f "${stamp}" 2>/dev/null || true ;;
        esac
    done
    shopt -u nullglob
fi

if [[ "${orfaos}" -eq 0 ]]; then
    log_info "nenhum device HID órfão, nem no rádio nem no cabo — todos os controles têm driver"
else
    log_info "órfãos=${orfaos} curados=${curados} falhados=${falhados} esgotados=${esgotados} ignorados=${ignorados}"
fi
exit 0
