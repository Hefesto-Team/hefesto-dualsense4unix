#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${SUDO_UID:-}" || -n "${SUDO_USER:-}" ]]; then
    unset HEFESTO_SYS_BLUETOOTH HEFESTO_BT_LIB HEFESTO_MAQUINA_JSON HEFESTO_RADIO_TRAVA HEFESTO_RADIO_TRAVA_PRAZO_S
fi
SYS_BLUETOOTH="${HEFESTO_SYS_BLUETOOTH:-/sys/class/bluetooth}"
SYS_BLUETOOTH="${SYS_BLUETOOTH%/}"
LIB="${HEFESTO_BT_LIB:-/var/lib/bluetooth}"
LIB="${LIB%/}"

LOG_TAG=hefesto-bt-active
LOG_DEST="${HEFESTO_BT_LOG_DEST:-}"
_registrar() {
    case "${LOG_DEST}" in
        "")   logger -t "${LOG_TAG}" "$*" 2>/dev/null || true ;;
        none) : ;;
        *)    printf '%s %s: %s\n' "$(date -Is 2>/dev/null || true)" "${LOG_TAG}" "$*" \
                  2>/dev/null >>"${LOG_DEST}" || true ;;
    esac
}
log() { _registrar "$*"; [[ "${QUIET:-0}" -eq 1 ]] || printf '%s\n' "$*"; }

if [[ "$(id -u)" -ne 0 ]]; then
    printf 'bt_active_mode.sh: requer root\n' >&2
    exit 1
fi

QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

_adaptadores() {
    local p nome achou=0
    for p in "${SYS_BLUETOOTH}"/hci*; do
        [[ -e "${p}" ]] || continue
        nome="${p##*/}"
        [[ "${nome}" =~ ^hci[0-9]+$ ]] || continue
        printf '%s\n' "${nome}"
        achou=1
    done
    [[ "${achou}" -eq 1 ]] && return 0
    if command -v busctl >/dev/null 2>&1; then
        nome="$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE '/org/bluez/hci[0-9]+' | sed 's#.*/##' | sort -u || true)"
        if [[ -n "${nome}" ]]; then printf '%s\n' "${nome}"; return 0; fi
    fi
    if command -v btmgmt >/dev/null 2>&1; then
        nome="$(timeout 5 btmgmt info 2>/dev/null | grep -oE '^hci[0-9]+' | sort -u || true)"
        if [[ -n "${nome}" ]]; then printf '%s\n' "${nome}"; return 0; fi
    fi
    command -v hciconfig >/dev/null 2>&1 || return 0
    hciconfig 2>/dev/null | awk -F: '/^hci/{print $1}' || true
}

_macs_conectados() {
    local p mac saida="" achou=0
    if command -v busctl >/dev/null 2>&1; then
        while IFS= read -r p; do
            [[ -z "${p}" ]] && continue
            [[ "$(busctl get-property org.bluez "${p}" org.bluez.Device1 Connected 2>/dev/null \
                | tr -d '[:space:]')" == "btrue" ]] || continue
            mac="${p##*/dev_}"
            printf '%s\n' "${mac//_/:}"
            achou=1
        done <<<"$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE '/org/bluez/hci[0-9]+/dev_[0-9A-Fa-f_]+$' | sort -u || true)"
        [[ "${achou}" -eq 1 ]] && return 0
    fi
    if command -v btmgmt >/dev/null 2>&1; then
        saida="$(timeout 5 btmgmt con 2>/dev/null | grep -oE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' || true)"
        if [[ -n "${saida}" ]]; then printf '%s\n' "${saida^^}"; return 0; fi
    fi
    command -v hcitool >/dev/null 2>&1 || return 0
    saida="$(hcitool con 2>/dev/null | grep -oE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' || true)"
    [[ -n "${saida}" ]] && printf '%s\n' "${saida^^}"
    return 0
}

OUIS_LINHAGEM=("e0:f6:b5" "e4:17:d8")
NOMES_LINHAGEM=("pro controller" "nintendo")

OUIS_CLONE=("e4:17:d8")
OUIS_NINTENDO_VISTAS=("e0:f6:b5")
NOMES_PRO=("pro controller")

TETO_DE_BYTES=247

declare -A HCI_DE=()

_e_linhagem_nintendo() {
    local mac="${1,,}" nome="${2,,}" marca
    for marca in "${OUIS_LINHAGEM[@]}"; do
        [[ "${mac}" == "${marca}"* ]] && return 0
    done
    for marca in "${NOMES_LINHAGEM[@]}"; do
        [[ "${nome}" == *"${marca}"* ]] && return 0
    done
    return 1
}

_nome_do_controle() {
    local mac="${1^^}" alvo caminho nome
    alvo="dev_${mac//:/_}"
    if command -v busctl >/dev/null 2>&1; then
        caminho="$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE "/org/bluez/hci[0-9]+/${alvo}$" | head -1 || true)"
        if [[ -n "${caminho}" ]]; then
            nome="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Alias 2>/dev/null \
                | sed -E 's/^s "?//; s/"?$//' || true)"
            [[ -n "${nome}" ]] && { printf '%s\n' "${nome}"; return 0; }
        fi
    fi
    sed -n 's/^Name=//p' "${LIB}"/*/"${mac}"/info 2>/dev/null | head -1 || true
}

_e_pro_genuino() {
    local mac="${1,,}" nome="${2,,}" marca
    for marca in "${OUIS_CLONE[@]}"; do
        [[ "${mac}" == "${marca}"* ]] && return 1
    done
    for marca in "${OUIS_NINTENDO_VISTAS[@]}"; do
        [[ "${mac}" == "${marca}"* ]] && return 0
    done
    for marca in "${NOMES_PRO[@]}"; do
        [[ "${nome}" == *"${marca}"* ]] && return 0
    done
    return 1
}

_prop_adaptador() {
    { busctl get-property org.bluez "/org/bluez/$1" org.bluez.Adapter1 "$2" --json=short 2>/dev/null | sed -nE 's/^.*"data":"(.*)"\}$/\1/p' | grep . \
        || busctl get-property org.bluez "/org/bluez/$1" org.bluez.Adapter1 "$2" 2>/dev/null | sed -E 's/^s "?//; s/"?$//'; } | grep -v '\\' || true
}

_hci_com_nintendo() {
    local caminho mac nome info dir end
    if command -v busctl >/dev/null 2>&1; then
        while IFS= read -r caminho; do
            [[ -n "${caminho}" ]] || continue
            mac="${caminho##*/dev_}"
            mac="${mac//_/:}"
            nome="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Alias 2>/dev/null \
                | sed -E 's/^s "?//; s/"?$//' || true)"
            _e_linhagem_nintendo "${mac}" "${nome}" || continue
            caminho="${caminho%/dev_*}"
            printf '%s\n' "${caminho##*/}"
        done <<<"$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE '/org/bluez/hci[0-9]+/dev_[0-9A-Fa-f_]+$' | sort -u || true)"
    fi
    while IFS= read -r info; do
        [[ -n "${info}" ]] || continue
        dir="${info%/info}"
        mac="${dir##*/}"
        nome="$(sed -n 's/^Name=//p' "${info}" 2>/dev/null | head -1 || true)"
        _e_linhagem_nintendo "${mac}" "${nome}" || continue
        end="${dir%/*}"
        end="${end##*/}"
        if [[ -n "${HCI_DE[${end^^}]:-}" ]]; then
            printf '%s\n' "${HCI_DE[${end^^}]}"
        fi
    done <<<"$(find "${LIB}" -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null || true)"
}

mapfile -t ADAPTADORES < <(_adaptadores)
[[ "${#ADAPTADORES[@]}" -eq 0 ]] && { log "nenhum adaptador HCI — nada a fazer"; exit 0; }

if command -v busctl >/dev/null 2>&1; then
    for HCI in "${ADAPTADORES[@]}"; do
        END="$(_prop_adaptador "${HCI}" Address)"
        [[ -n "${END}" ]] && HCI_DE["${END^^}"]="${HCI}"
    done
    mapfile -t COM_NINTENDO < <(_hci_com_nintendo | sort -u)
    TRAVA_DO_RADIO="${HEFESTO_RADIO_TRAVA:-}"
    if [[ -z "${TRAVA_DO_RADIO}" && -z "${HEFESTO_SYS_BLUETOOTH:-}" \
        && -z "${HEFESTO_BT_LIB:-}" ]]; then
        TRAVA_DO_RADIO="/run/hefesto-dualsense4unix/radio.lock"
    fi
    PRAZO_DA_TRAVA_S="${HEFESTO_RADIO_TRAVA_PRAZO_S:-5}"
    [[ "${PRAZO_DA_TRAVA_S}" =~ ^[0-9]+$ ]] || PRAZO_DA_TRAVA_S=5
    TRAVA_FD=""
    TRAVA_E_MINHA=0
    _na_trava() {
        local fd alvo
        [[ -n "${TRAVA_FD}" || -z "${TRAVA_DO_RADIO}" ]] && return 0
        [[ -d "${TRAVA_DO_RADIO%/*}" ]] || return 0
        if [[ -L "${TRAVA_DO_RADIO}" ]]; then
            log "recusando a trava do rádio: ${TRAVA_DO_RADIO} é link simbólico; sigo sem ela"
            return 0
        fi
        for fd in "/proc/$$/fd/"*; do
            alvo="$(readlink -- "${fd}" 2>/dev/null || true)"
            [[ "${alvo}" == "${TRAVA_DO_RADIO}" ]] || continue
            if flock -n "${fd##*/}" 2>/dev/null; then
                TRAVA_FD="${fd##*/}"
                return 0
            fi
        done
        if ! exec {TRAVA_FD}<>"${TRAVA_DO_RADIO}"; then
            TRAVA_FD=""
            return 0
        fi
        if ! flock -w "${PRAZO_DA_TRAVA_S}" "${TRAVA_FD}"; then
            exec {TRAVA_FD}>&-
            TRAVA_FD=""
            return 1
        fi
        TRAVA_E_MINHA=1
        printf 'bt-active-mode %s\n' "$$" 1>&"${TRAVA_FD}" 2>/dev/null || true
        return 0
    }
    declare -A NOME_DO_ADAPTADOR=()
    _maquina_json() {
        local nome uid casa arquivo achados=()
        if [[ -n "${HEFESTO_MAQUINA_JSON:-}" ]]; then
            printf ':%s\n' "${HEFESTO_MAQUINA_JSON}"
            return 0
        fi
        [[ -n "${HEFESTO_SYS_BLUETOOTH:-}" || -n "${HEFESTO_BT_LIB:-}" ]] && return 0
        while IFS=: read -r nome _ uid _ _ casa _; do
            [[ "${uid}" =~ ^[0-9]+$ ]] || continue
            (( uid >= 1000 && uid < 60000 )) || continue
            arquivo="${casa}/.config/hefesto-dualsense4unix/maquina.json"
            [[ -f "${arquivo}" && ! -L "${arquivo}" ]] && achados+=("${uid}:${arquivo}")
        done < <(getent passwd 2>/dev/null || cat /etc/passwd 2>/dev/null || true)
        [[ "${#achados[@]}" -eq 1 ]] && printf '%s\n' "${achados[0]}"
        return 0
    }
    _ler_os_nomes_dos_adaptadores() {
        local alvo dono arquivo chave nome
        alvo="$(_maquina_json)"
        [[ -n "${alvo}" ]] || return 0
        command -v python3 >/dev/null 2>&1 || return 0
        dono="${alvo%%:*}"
        arquivo="${alvo#*:}"
        while IFS=$'\t' read -r chave nome; do
            if [[ -n "${chave}" && -n "${nome}" ]]; then
                NOME_DO_ADAPTADOR["${chave}"]="${nome}"
            fi
        done < <(python3 -I -c '
import json, os, stat, sys
arquivo, dono = sys.argv[1], sys.argv[2]
try:
    fd = os.open(arquivo, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
except OSError:
    sys.exit(0)
with os.fdopen(fd, "rb") as fh:
    info = os.fstat(fh.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_size > 1 << 20:
        sys.exit(0)
    if dono and str(info.st_uid) != dono:
        sys.exit(0)
    try:
        doc = json.loads(fh.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        sys.exit(0)
if not isinstance(doc, dict) or doc.get("version", 1) != 1:
    sys.exit(0)
adaptadores = doc.get("adaptadores")
for chave, dele in sorted(adaptadores.items() if isinstance(adaptadores, dict) else ()):
    nome = dele.get("nome") if isinstance(dele, dict) else None
    if not isinstance(nome, str) or not isinstance(chave, str):
        continue
    nome = nome.strip()
    if nome and len(nome) <= 60 and nome.isprintable() and len(chave) == 12 and chave.isalnum():
        print(chave.lower() + "\t" + nome)
' "${arquivo}" "${dono}" 2>/dev/null || true)
    }
    _ler_os_nomes_dos_adaptadores
    for HCI in "${ADAPTADORES[@]}"; do
        ADAPTER_OBJ="/org/bluez/${HCI}"
        HOSPEDA=0
        for UM in ${COM_NINTENDO[@]+"${COM_NINTENDO[@]}"}; do
            [[ "${UM}" == "${HCI}" ]] && HOSPEDA=1
        done
        NOME=""
        if [[ "${#NOME_DO_ADAPTADOR[@]}" -gt 0 ]]; then
            CHAVE="$(_prop_adaptador "${HCI}" Address)"
            CHAVE="${CHAVE//:/}"
            CHAVE="${CHAVE,,}"
            [[ -n "${CHAVE}" ]] && NOME="${NOME_DO_ADAPTADOR[${CHAVE}]:-}"
        fi
        [[ -n "${NOME}" || "${HOSPEDA}" -eq 1 ]] || continue
        ALIAS_ATUAL="$(_prop_adaptador "${HCI}" Alias)"
        BASE="${NOME:-${ALIAS_ATUAL}}"
        [[ -n "${BASE}" ]] || continue
        if [[ "${HOSPEDA}" -eq 1 && "${BASE}" != Nintendo* ]]; then
            NOVO="Nintendo ${BASE}"
        else
            NOVO="${BASE}"
        fi
        [[ "${NOVO}" != "${ALIAS_ATUAL}" ]] || continue
        if [[ "$(printf '%s' "${NOVO}" | LC_ALL=C wc -c)" -gt "${TETO_DE_BYTES}" ]]; then
            log "NÃO prefixei o alias de ${HCI}: 'Nintendo ' mais o nome de hoje passa de ${TETO_DE_BYTES} bytes, o teto do BlueZ — encurte o nome do adaptador pela aba do produto e o Pro volta a ficar protegido"
            continue
        fi
        if ! _na_trava; then
            log "NÃO prefixei o alias de ${HCI}: outro motor segura a trava do rádio há mais de ${PRAZO_DA_TRAVA_S} s — o watchdog re-tenta"
            break
        fi
        if busctl set-property org.bluez "${ADAPTER_OBJ}" org.bluez.Adapter1 Alias s "${NOVO}" 2>/dev/null; then
            if [[ -n "${NOME}" ]]; then
                log "alias do adaptador ${HCI} -> '${NOVO}' (o nome dado a ele na aba Conexões)"
            else
                log "alias do adaptador ${HCI} -> '${NOVO}' (tira o Pro do sniff frágil)"
            fi
        else
            log "falha ao setar alias de ${HCI} (adaptador não pronto?) — o watchdog re-tenta"
        fi
    done
    if [[ "${TRAVA_E_MINHA}" -eq 1 ]]; then
        exec {TRAVA_FD}>&-
    fi
fi

if ! command -v hciconfig >/dev/null 2>&1; then
    log "NÃO apliquei o SNIFF default de ${ADAPTADORES[*]}: o 'hciconfig' foi depreciado pelo BlueZ e não está nesta máquina, e nenhuma ferramenta viva escreve link policy — instale bluez-deprecated (ou bluez-deprecated-tools). O alias 'Nintendo*' acima segue valendo; o 8BitDo pode não completar a probe se o adaptador estiver sem SNIFF"
else
    for HCI in "${ADAPTADORES[@]}"; do
        _lp="$(hciconfig "${HCI}" lp 2>/dev/null || true)"
        if [[ "${_lp}" != *SNIFF* ]]; then
            hciconfig "${HCI}" lp rswitch,hold,sniff,park 2>/dev/null \
                && log "link policy default de ${HCI} -> RSWITCH,HOLD,SNIFF,PARK (o clone 8BitDo precisa do SNIFF para probar)" \
                || log "falha ao devolver o SNIFF ao default de ${HCI} (adaptador não pronto?)"
        fi
    done
fi

while read -r MAC; do
    [[ -z "${MAC}" ]] && continue
    _e_pro_genuino "${MAC}" "$(_nome_do_controle "${MAC}")" || continue
    if ! command -v hcitool >/dev/null 2>&1; then
        log "Pro genuíno ${MAC} conectado e NÃO consegui tirá-lo do SNIFF: o 'hcitool' foi depreciado pelo BlueZ e não está nesta máquina (pacote bluez-deprecated / bluez-deprecated-tools), e a mgmt API não escreve link policy. Ele vai cair sob carga até isso ser resolvido"
        continue
    fi
    hcitool lp "${MAC}" RSWITCH >/dev/null 2>&1 \
        && log "link policy de ${MAC} -> RSWITCH (sem SNIFF; Pro genuíno)" || true
done <<<"$(_macs_conectados)"

exit 0
