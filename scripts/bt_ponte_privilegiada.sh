#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${SUDO_UID:-}" || -n "${SUDO_USER:-}" ]]; then
    unset HEFESTO_BT_LIB HEFESTO_PONTE_DRY_RUN HEFESTO_BT_LOG_DEST HEFESTO_BT_BIN \
        HEFESTO_BT_LAPIDES HEFESTO_RADIO_DIARIO_ROOT HEFESTO_SYSFS_RAIZ \
        HEFESTO_BT_JOURNAL HEFESTO_PONTE_STAMPS HEFESTO_USB_PAUSA_S \
        HEFESTO_USB_ESPERA_S HEFESTO_SYSFS_BLUETOOTH \
        HEFESTO_HID_DEVICES_DIR HEFESTO_USB_DEVICES_DIR
fi

LIB="${HEFESTO_BT_LIB:-/var/lib/bluetooth}"
LIB="${LIB%/}"
LIB_REAL="/var/lib/bluetooth"
ALVO_INSTALADO="/usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh"
SECOS="${HEFESTO_PONTE_DRY_RUN:-0}"

SYSFS="${HEFESTO_SYSFS_RAIZ:-/sys}"
SYSFS="${SYSFS%/}"
SYSFS_REAL="/sys"

LAPIDES_REAIS="/var/lib/hefesto-dualsense4unix/bt-bonds/.lapides"
DIARIO_REAL="/var/lib/hefesto-dualsense4unix/radio-diario.jsonl"

BIN_DE_TESTE="${HEFESTO_BT_BIN:-}"
if [[ -n "${BIN_DE_TESTE}" ]]; then
    PATH="${BIN_DE_TESTE}:${PATH}"
    export PATH
fi

SEGUNDOS_MAX=120

LOG_TAG=hefesto-bt-ponte
LOG_DEST="${HEFESTO_BT_LOG_DEST:-}"
_registrar() {
    case "${LOG_DEST}" in
        "")   logger -t "${LOG_TAG}" "$*" 2>/dev/null || true ;;
        none) : ;;
        *)    printf '%s %s: %s\n' "$(date -Is 2>/dev/null || true)" "${LOG_TAG}" "$*" \
                  2>/dev/null >>"${LOG_DEST}" || true ;;
    esac
}

_erro() { printf '%s: %s\n' "${0##*/}" "$*" >&2; }

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

_diario_alvo() {
    if [[ -n "${HEFESTO_RADIO_DIARIO_ROOT:-}" ]]; then
        printf '%s\n' "${HEFESTO_RADIO_DIARIO_ROOT}"
    elif [[ "${LIB}" == "${LIB_REAL}" && "${SYSFS}" == "${SYSFS_REAL}" ]]; then
        printf '%s\n' "${DIARIO_REAL}"
    fi
}

_diario() { _diario_escrever "$(_diario_alvo)" "$@"; }

_recusar() { _erro "$*"; exit 2; }

_uso() {
    cat >&2 <<'FIM'
uso: bt_ponte_privilegiada.sh <verbo> [segundos]   (os dados vêm pelo STDIN)

  verbo              o STDIN, uma linha por dado, nesta ordem
  adaptadores        —
  bonds              MAC do adaptador
  renomear           MAC do adaptador, nome novo
  esquecer           MAC do adaptador, MAC do controle
  descobrir <SEG>    MAC do adaptador
  parear             MAC do adaptador, MAC do controle
  desconectar        MAC do adaptador, MAC do controle
  reiniciar-travado  —
  religar-orfaos     —
  regra-sudo <USUARIA|%GRUPO>...

  exemplo: printf '%s\n%s\n' <adaptador> <controle> | sudo bt_ponte_privilegiada.sh esquecer

  --dry-run como PRIMEIRO argumento: não muda nada, imprime o que faria.
FIM
    exit 2
}

VALIDADO=""

_MAC_FORMA='^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$'

_mac() {
    local valor="${1:-}" papel="${2:-MAC}"
    [[ -n "${valor}" ]] || _recusar "${papel} ausente"
    [[ "${valor}" =~ ${_MAC_FORMA} ]] \
        || _recusar "${papel} inválido: esperava aa:bb:cc:dd:ee:ff, recebi '${valor}'"
    VALIDADO="${valor^^}"
}

_segundos() {
    local valor="${1:-}"
    [[ "${valor}" =~ ^[0-9]{1,3}$ ]] \
        || _recusar "segundos inválido: esperava 1 a ${SEGUNDOS_MAX}, recebi '${valor}'"
    (( 10#${valor} >= 1 && 10#${valor} <= SEGUNDOS_MAX )) \
        || _recusar "segundos fora da faixa: 1 a ${SEGUNDOS_MAX}, recebi '${valor}'"
    VALIDADO="$((10#${valor}))"
}

_usuaria() {
    local valor="${1:-}"
    [[ "${valor}" =~ ^[A-Za-z_][A-Za-z0-9._-]{0,31}$ ]] \
        || _recusar "nome de usuária inválido: '${valor}'"
    [[ "${valor}" != "ALL" ]] \
        || _recusar "'ALL' é palavra reservada do sudoers (concederia a TODO MUNDO), não um nome de usuária"
    VALIDADO="${valor}"
}

_principal_do_sudoers() {
    local valor="${1:-}"
    if [[ "${valor}" == %* ]]; then
        _usuaria "${valor#%}"
        VALIDADO="%${VALIDADO}"
        return 0
    fi
    _usuaria "${valor}"
}

_mac_do_stdin() {
    local papel="$1" linha
    IFS= read -r -t 10 linha || _recusar "${papel} não veio pelo stdin (o endereço vem pelo stdin, uma linha por dado)"
    _mac "${linha}" "${papel}"
}

_fim_do_stdin() {
    local sobra="" rc=0
    IFS= read -r -t 10 sobra || rc=$?
    (( rc <= 128 )) || _recusar "o stdin não fechou em 10 s depois dos dados do verbo"
    [[ "${rc}" -ne 0 && -z "${sobra}" ]] \
        || _recusar "o stdin trouxe uma linha a mais do que o verbo lê"
}

_sem_dado_no_argv() {
    local verbo="$1"; shift
    [[ $# -eq 0 ]] || _recusar "${verbo}: o endereço vem pelo stdin, uma linha por dado, e não no argv"
}

_nome_do_stdin() {
    local nome resto
    IFS= read -r -t 10 nome || _recusar "nome novo não veio pelo stdin"
    [[ -n "${nome}" ]] || _recusar "nome novo vazio"
    (( ${#nome} <= 64 )) || _recusar "nome novo longo demais (máximo 64)"
    [[ "${nome}" != " "* && "${nome}" != *" " ]] \
        || _recusar "nome novo não pode começar nem terminar com espaço"
    if [[ "${nome}" =~ [[:cntrl:]] ]]; then
        _recusar "nome novo tem caractere de controle"
    fi
    resto="${nome//[A-Za-z0-9 ._#+()-]/}"
    resto="$(LC_ALL=C printf '%s' "${resto}" | tr -d '\200-\377')"
    [[ -z "${resto}" ]] \
        || _recusar "nome novo tem caractere proibido: '${resto}'"
    VALIDADO="${nome}"
}

_higienizar() {
    printf '%s' "${1:-}" | tr '\t\n\r' '   ' | tr -d '\000-\037\177'
}

_exige_root() {
    [[ "${LIB}" == "${LIB_REAL}" ]] || return 0
    [[ "$(id -u)" -eq 0 ]] || { _erro "'$1' requer root (é a ponte privilegiada)"; exit 1; }
}

_seco() { [[ "${SECOS}" == "1" ]]; }

_dizer_seco() { printf '[dry-run] %s\n' "$*"; }

_no_do_dispositivo() { printf 'dev_%s\n' "${1//:/_}"; }

_onde() {
    if [[ -n "${1:-}" ]]; then
        printf 'do adaptador %s' "$1"
    else
        printf 'de um adaptador fora da mesa'
    fi
}

_hci_do_mac() {
    local alvo="$1" caminho hci endereco
    [[ "${LIB}" == "${LIB_REAL}" || -n "${BIN_DE_TESTE}" ]] || return 1
    command -v busctl >/dev/null 2>&1 || return 1
    while read -r caminho; do
        [[ -n "${caminho}" ]] || continue
        hci="${caminho##*/}"
        endereco="$(busctl get-property org.bluez "${caminho}" org.bluez.Adapter1 Address 2>/dev/null \
            | sed -E 's/^s "?//; s/"?$//' || true)"
        if [[ "${endereco^^}" == "${alvo}" ]]; then
            printf '%s\n' "${hci}"
            return 0
        fi
    done <<<"$(busctl tree org.bluez --list 2>/dev/null \
        | grep -oE '^/org/bluez/hci[0-9]+$' | sort -u || true)"
    return 1
}

verbo_adaptadores() {
    local caminho hci endereco apelido ligado achou=0
    if command -v busctl >/dev/null 2>&1; then
        while read -r caminho; do
            [[ -n "${caminho}" ]] || continue
            hci="${caminho##*/}"
            endereco="$(busctl get-property org.bluez "${caminho}" org.bluez.Adapter1 Address 2>/dev/null \
                | sed -E 's/^s "?//; s/"?$//' || true)"
            [[ -n "${endereco}" ]] || continue
            apelido="$(busctl get-property org.bluez "${caminho}" org.bluez.Adapter1 Alias 2>/dev/null \
                | sed -E 's/^s "?//; s/"?$//' || true)"
            ligado="$(busctl get-property org.bluez "${caminho}" org.bluez.Adapter1 Powered 2>/dev/null \
                | sed -E 's/^b //' || true)"
            printf '%s\t%s\t%s\t%s\n' "${endereco^^}" "$(_higienizar "${apelido}")" \
                "$([[ "${ligado}" == "true" ]] && printf 'ligado' || printf 'desligado')" "${hci}"
            achou=1
        done <<<"$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE '^/org/bluez/hci[0-9]+$' | sort -u || true)"
    fi
    [[ "${achou}" -eq 1 ]] && return 0
    for caminho in "${HEFESTO_SYSFS_BLUETOOTH:-/sys/class/bluetooth}"/hci*; do
        [[ -e "${caminho}" ]] || continue
        hci="${caminho##*/}"
        [[ "${hci}" =~ ^hci[0-9]+$ ]] || continue
        endereco="$(cat "${caminho}/address" 2>/dev/null || true)"
        [[ -n "${endereco}" ]] || continue
        printf '%s\t\t%s\t%s\n' "${endereco^^}" "desconhecido" "${hci}"
        achou=1
    done
    [[ "${achou}" -eq 1 ]] && return 0
    if command -v hcitool >/dev/null 2>&1; then
        while read -r hci endereco; do
            [[ "${hci}" =~ ^hci[0-9]+$ ]] || continue
            [[ "${endereco}" =~ ${_MAC_FORMA} ]] || continue
            printf '%s\t\t%s\t%s\n' "${endereco^^}" "desconhecido" "${hci}"
        done <<<"$(LC_ALL=C hcitool dev 2>/dev/null | tail -n +2 || true)"
    fi
    return 0
}

verbo_bonds() {
    local adaptador="$1" pasta alvo nome chave
    _exige_root bonds
    pasta="${LIB}/${adaptador}"
    [[ -d "${pasta}" ]] || { _erro "adaptador ${adaptador} não tem árvore em ${LIB}"; exit 1; }
    for alvo in "${pasta}"/*; do
        [[ -d "${alvo}" ]] || continue
        [[ "${alvo##*/}" =~ ${_MAC_FORMA} ]] || continue
        [[ -f "${alvo}/info" ]] || continue
        nome="$(sed -n 's/^Name=//p' "${alvo}/info" 2>/dev/null | head -1 || true)"
        chave='sem-chave'
        grep -q '^\[LinkKey\]' "${alvo}/info" 2>/dev/null && chave='com-chave'
        printf '%s\t%s\t%s\n' "${alvo##*/}" "$(_higienizar "${nome}")" "${chave}"
    done
    return 0
}

verbo_renomear() {
    local adaptador="$1" nome="$2" hci
    hci="$(_hci_do_mac "${adaptador}" || true)"
    [[ -n "${hci}" ]] || { _erro "adaptador ${adaptador} não está na mesa (plugado e ligado?)"; exit 1; }
    if _seco; then
        _dizer_seco "busctl set-property org.bluez /org/bluez/${hci} org.bluez.Adapter1 Alias s <${nome}>"
        return 0
    fi
    if busctl set-property org.bluez "/org/bluez/${hci}" org.bluez.Adapter1 Alias s "${nome}" 2>/dev/null; then
        _registrar "o adaptador ${hci} foi renomeado"
        return 0
    fi
    _erro "não consegui escrever o alias de ${adaptador} (${hci})"
    exit 1
}

verbo_esquecer() {
    local adaptador="$1" controle="$2" hci no pasta_bond
    _exige_root esquecer
    hci="$(_hci_do_mac "${adaptador}" || true)"
    no="$(_no_do_dispositivo "${controle}")"
    if [[ -n "${hci}" ]]; then
        if _seco; then
            _dizer_seco "busctl call org.bluez /org/bluez/${hci} org.bluez.Adapter1 RemoveDevice o /org/bluez/${hci}/${no}"
        else
            busctl call org.bluez "/org/bluez/${hci}" org.bluez.Adapter1 \
                RemoveDevice o "/org/bluez/${hci}/${no}" >/dev/null 2>&1 || true
        fi
    fi
    pasta_bond="${LIB}/${adaptador}/${controle}"
    _apagar "${pasta_bond}" "bond"
    _apagar "${LIB}/${adaptador}/cache/${controle}" "cache SDP da origem"
    _enterrar "${adaptador}" "${controle}"
    if ! _seco; then
        _registrar "um controle esquecido $(_onde "${hci}") (bond + cache da origem + lápide)"
        _diario "bt-ponte" "esqueceu o controle" "pedido à ponte privilegiada" \
            "{\"bond\": $(_json_texto "no adaptador")}" \
            "{\"bond\": null, \"lapide\": true}" \
            "\"adaptador\": $(_json_texto "${adaptador}"), \"controle\": $(_json_texto "${controle}"), \"pedido_por\": $(_json_texto "${SUDO_USER:-}")"
    fi
    return 0
}

_lapides_alvo() {
    if [[ -n "${HEFESTO_BT_LAPIDES:-}" ]]; then
        printf '%s\n' "${HEFESTO_BT_LAPIDES}"
    elif [[ "${LIB}" == "${LIB_REAL}" ]]; then
        printf '%s\n' "${LAPIDES_REAIS}"
    fi
}

_enterrar() {
    local adaptador="$1" controle="$2" alvo
    alvo="$(_lapides_alvo)"
    [[ -n "${alvo}" ]] || return 0
    if _seco; then
        _dizer_seco "gravaria a lápide de ${controle} em ${adaptador}: ${alvo}"
        return 0
    fi
    if [[ -L "${alvo}" ]]; then
        _erro "recusando a lápide: ${alvo} é link simbólico"
        return 0
    fi
    install -d -m 700 "${alvo%/*}" 2>/dev/null || true
    printf '%s %s %s\n' "$(date +%s)" "${adaptador}" "${controle}" >>"${alvo}"
    chmod 600 "${alvo}" 2>/dev/null || true
}

_apagar() {
    local caminho="$1" rotulo="$2" relativo
    [[ -e "${caminho}" ]] || return 0
    relativo="${caminho#"${LIB}/"}"
    if [[ ! "${relativo}" =~ ^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}/(cache/)?[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$ ]]; then
        _erro "recusando apagar caminho fora da forma esperada: ${caminho}"
        exit 1
    fi
    if _seco; then
        _dizer_seco "apagaria ${rotulo}: ${caminho}"
        return 0
    fi
    rm -rf -- "${caminho}"
}

BUSCA_PID=""
BUSCA_ROTEIRO=""
BUSCA_JAVISTOS=""

_fechar_a_busca() {
    if [[ -n "${BUSCA_PID}" ]]; then
        kill "${BUSCA_PID}" 2>/dev/null || true
        BUSCA_PID=""
    fi
    [[ -n "${BUSCA_ROTEIRO}" ]] && rm -f -- "${BUSCA_ROTEIRO}"
    [[ -n "${BUSCA_JAVISTOS}" ]] && rm -f -- "${BUSCA_JAVISTOS}"
    return 0
}

_candidatos_novos() {
    local hci="$1" javistos="$2" caminho endereco nome pareado classe
    while read -r caminho; do
        [[ -n "${caminho}" ]] || continue
        grep -qxF -- "${caminho}" "${javistos}" 2>/dev/null && continue
        endereco="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Address 2>/dev/null \
            | sed -E 's/^s "?//; s/"?$//' || true)"
        [[ "${endereco}" =~ ${_MAC_FORMA} ]] || continue
        nome="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Alias 2>/dev/null \
            | sed -E 's/^s "?//; s/"?$//' || true)"
        pareado="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Paired 2>/dev/null \
            | sed -E 's/^b //' || true)"
        classe="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Class 2>/dev/null \
            | sed -E 's/^u //' || true)"
        [[ "${classe}" =~ ^[0-9]+$ ]] || classe=""
        printf '%s\t%s\t%s\t%s\n' "${endereco^^}" "$(_higienizar "${nome}")" \
            "$([[ "${pareado}" == "true" ]] && printf 'pareado' || printf 'novo')" "${classe}"
        printf '%s\n' "${caminho}" >>"${javistos}"
    done <<<"$(busctl tree org.bluez --list 2>/dev/null \
        | grep -oE "^/org/bluez/${hci}/dev_[0-9A-Fa-f_]+$" | sort -u || true)"
}

verbo_descobrir() {
    local adaptador="$1" segundos="$2" hci fim quantos
    hci="$(_hci_do_mac "${adaptador}" || true)"
    [[ -n "${hci}" ]] || { _erro "adaptador ${adaptador} não está na mesa (plugado e ligado?)"; exit 1; }
    command -v bluetoothctl >/dev/null 2>&1 \
        || { _erro "bluetoothctl ausente — sem ele não há janela de busca"; exit 1; }
    if _seco; then
        _dizer_seco "bluetoothctl --timeout ${segundos} (select ${adaptador}; power on; pairable on; scan on)"
        _dizer_seco "e, a cada segundo da janela, uma linha por candidato novo de ${hci}: MAC \\t NOME \\t novo|pareado \\t CLASSE"
        return 0
    fi
    BUSCA_ROTEIRO="$(mktemp)" || { _erro "não consegui criar o roteiro temporário"; exit 1; }
    BUSCA_JAVISTOS="$(mktemp)" || { _erro "não consegui criar a lista de já-vistos"; exit 1; }
    chmod 600 "${BUSCA_ROTEIRO}" "${BUSCA_JAVISTOS}"
    trap _fechar_a_busca EXIT
    printf 'select %s\npower on\npairable on\nscan on\n' "${adaptador}" >"${BUSCA_ROTEIRO}"
    _registrar "janela de busca de ${segundos}s aberta no adaptador ${hci}"
    timeout "$((segundos + 10))" bluetoothctl --timeout "${segundos}" \
        --init-script "${BUSCA_ROTEIRO}" >/dev/null 2>&1 &
    BUSCA_PID=$!
    fim=$(( $(date +%s) + segundos ))
    while kill -0 "${BUSCA_PID}" 2>/dev/null && (( $(date +%s) < fim )); do
        _candidatos_novos "${hci}" "${BUSCA_JAVISTOS}"
        sleep 1
    done
    _candidatos_novos "${hci}" "${BUSCA_JAVISTOS}"
    wait "${BUSCA_PID}" 2>/dev/null || true
    BUSCA_PID=""
    quantos="$(wc -l <"${BUSCA_JAVISTOS}" 2>/dev/null || printf '0')"
    _registrar "janela de busca fechada no adaptador ${hci}: ${quantos} candidato(s)"
    return 0
}

verbo_parear() {
    local adaptador="$1" controle="$2" hci no caminho
    hci="$(_hci_do_mac "${adaptador}" || true)"
    [[ -n "${hci}" ]] || { _erro "adaptador ${adaptador} não está na mesa (plugado e ligado?)"; exit 1; }
    no="$(_no_do_dispositivo "${controle}")"
    caminho="/org/bluez/${hci}/${no}"
    if _seco; then
        _dizer_seco "busctl call org.bluez ${caminho} org.bluez.Device1 Pair"
        _dizer_seco "busctl set-property org.bluez ${caminho} org.bluez.Device1 Trusted b true"
        return 0
    fi
    if ! _parear_o_no "${caminho}"; then
        _erro "Pair() falhou em ${controle} via ${adaptador} — o controle está em modo de pareamento (PS + Create) e dentro da janela de busca?"
        exit 1
    fi
    busctl set-property org.bluez "${caminho}" org.bluez.Device1 Trusted b true >/dev/null 2>&1 || true
    _registrar "um controle pareado e confiado no adaptador ${hci}"
    return 0
}

verbo_desconectar() {
    local adaptador="$1" controle="$2" hci indice
    hci="$(_hci_do_mac "${adaptador}" || true)"
    [[ -n "${hci}" ]] || { _erro "adaptador ${adaptador} não está na mesa (plugado e ligado?)"; exit 1; }
    indice="${hci#hci}"
    if _seco; then
        _dizer_seco "hcitool -i ${hci} dc ${controle}   (plano B: btmgmt --index ${indice} disconnect ${controle})"
        return 0
    fi
    if command -v hcitool >/dev/null 2>&1; then
        if timeout 10 hcitool -i "${hci}" dc "${controle}" >/dev/null 2>&1; then
            _registrar "o link de um controle derrubado no adaptador ${hci} por hcitool dc"
            return 0
        fi
    fi
    if command -v btmgmt >/dev/null 2>&1; then
        if timeout 10 btmgmt --index "${indice}" disconnect "${controle}" >/dev/null 2>&1; then
            _registrar "o link de um controle derrubado no adaptador ${hci} por btmgmt disconnect"
            return 0
        fi
    fi
    if ! command -v hcitool >/dev/null 2>&1 && ! command -v btmgmt >/dev/null 2>&1; then
        _erro "não há como derrubar o link de ${controle}: nem 'hcitool' (depreciado pelo BlueZ, pacote bluez-deprecated / bluez-deprecated-tools) nem 'btmgmt' estão nesta máquina"
        exit 1
    fi
    _erro "não consegui derrubar o link de ${controle} em ${adaptador} (${hci}) — o link ainda estava de pé quando tentei?"
    exit 1
}

LIMIAR_DO_LACO=5
JANELA_DO_LACO_S=150
LACO_VIVO_S=15
INTERVALO_ENTRE_RESETS_S=900
MAX_REINICIOS_SEGUIDOS=3
JANELA_DA_CURA_S=3600
_PORTA_FORMA='^[0-9]{1,3}-[0-9]{1,3}(\.[0-9]{1,3}){0,6}$'

_linhas_do_kernel() {
    if [[ -n "${HEFESTO_BT_JOURNAL:-}" ]]; then
        cat -- "${HEFESTO_BT_JOURNAL}" 2>/dev/null || true
        return 0
    fi
    command -v journalctl >/dev/null 2>&1 || return 0
    journalctl -k -b --since "-${JANELA_DO_LACO_S}s" -o short-unix -q --no-pager 2>/dev/null || true
}

_timeouts_por_hci() {
    local desde="${1:-0}"
    _linhas_do_kernel \
        | grep -iE '^[0-9]+(\.[0-9]+)? .*hci[0-9]+: command 0x[0-9a-f]{4} tx timeout' \
        | awk -v desde="${desde}" '
            {
                quando = int($1)
                if (quando <= desde) next
                texto = tolower($0)
                if (!match(texto, /hci[0-9]+: command 0x/)) next
                hci = substr(texto, RSTART, RLENGTH)
                sub(/: command 0x$/, "", hci)
                n[hci]++
                if (!(hci in mais_novo) || quando > mais_novo[hci]) mais_novo[hci] = quando
            }
            END { for (h in n) print h, n[h], mais_novo[h] }' \
        | sort || true
}

_hcis_em_laco() {
    _timeouts_por_hci 0 | awk -v limiar="${LIMIAR_DO_LACO}" '$2 >= limiar' || true
}

_timeouts_desde() {
    local hci="$1" desde="$2" h n _u
    while read -r h n _u; do
        [[ "${h}" == "${hci}" ]] && { printf '%s\n' "${n}"; return 0; }
    done < <(_timeouts_por_hci "${desde}")
    printf '0\n'
}

_porta_do_hci() {
    local hci="$1" real interface aparelho porta
    real="$(readlink -f -- "${SYSFS}/class/bluetooth/${hci}" 2>/dev/null)" || return 1
    [[ "${real}" == */bluetooth/"${hci}" ]] || return 1
    interface="${real%/bluetooth/*}"
    aparelho="${interface%/*}"
    porta="${aparelho##*/}"
    [[ "${porta}" =~ ${_PORTA_FORMA} ]] || return 1
    [[ "${interface##*/}" == "${porta}:"* ]] || return 1
    printf '%s\n' "${porta}"
}

_hci_da_porta() {
    local porta="$1" achado
    for achado in "${SYSFS}/bus/usb/devices/${porta}/${porta}":*/bluetooth/hci*; do
        [[ -e "${achado}" ]] || continue
        [[ "${achado##*/}" =~ ^hci[0-9]+$ ]] || continue
        printf '%s\n' "${achado##*/}"
        return 0
    done
    return 1
}

_ha_conexao() {
    local hci="$1" porta="$2" no
    for no in "${SYSFS}/class/bluetooth/${hci}":* \
              "${SYSFS}/bus/usb/devices/${porta}/${porta}":*/bluetooth/"${hci}/${hci}":*; do
        [[ -e "${no}" ]] && return 0
    done
    return 1
}

_estampas() { printf '%s\n' "${HEFESTO_PONTE_STAMPS:-/run/hefesto-bt-ponte}"; }

_soltar_o_freio_curado() {
    local marca porta hci h n _u curado por_que
    for marca in "$(_estampas)"/reset-*.desistiu; do
        [[ -e "${marca}" ]] || continue
        porta="${marca##*/reset-}"
        porta="${porta%.desistiu}"
        [[ "${porta}" =~ ${_PORTA_FORMA} ]] || continue
        curado=1
        hci="$(_hci_da_porta "${porta}" || true)"
        if [[ -n "${hci}" ]]; then
            while read -r h n _u; do
                [[ "${h}" == "${hci}" && "${n}" =~ ^[0-9]+$ && "${n}" -gt 0 ]] && curado=0
            done < <(_timeouts_por_hci 0)
        fi
        [[ "${curado}" -eq 1 ]] || continue
        _seco && { _dizer_seco "soltaria o freio da porta ${porta}: o laço sumiu"; continue; }
        rm -f -- "${marca}" "${marca%.desistiu}.seguidos" 2>/dev/null || true
        if [[ -n "${hci}" ]]; then
            por_que="o laço sumiu do journal: nenhum «command tx timeout» do ${hci} da porta ${porta} em ${JANELA_DO_LACO_S} s"
        else
            por_que="a porta ${porta} ficou sem adaptador: o laço saiu com ele"
        fi
        _diario "bt-ponte" "soltou o freio do reinício" \
            "${por_que}" \
            null "{\"hci\": $(_json_texto "${hci}")}" \
            "\"porta\": $(_json_texto "${porta}"), \"familia\": \"3\""
    done
}

verbo_reiniciar_travado() {
    local hci quantos mais_novo porta agora_hci carimbo anterior agora pausa espera
    local recusou=0 achou=0 volta frase seguidos
    if [[ "${SYSFS}" == "${SYSFS_REAL}" && "$(id -u)" -ne 0 ]]; then
        _erro "'reiniciar-travado' requer root (é a ponte privilegiada)"
        exit 1
    fi
    agora="$(date +%s)"
    _soltar_o_freio_curado
    while read -r hci quantos mais_novo; do
        [[ "${hci}" =~ ^hci[0-9]+$ ]] || continue
        [[ "${quantos}" =~ ^[0-9]+$ && "${mais_novo}" =~ ^[0-9]+$ ]] || continue
        (( agora - mais_novo <= LACO_VIVO_S )) || continue
        achou=1
        if ! porta="$(_porta_do_hci "${hci}")"; then
            printf 'recusado\t-\t%s\tsem porta USB\n' "${hci}"
            _diario "bt-ponte" "recusou reiniciar o adaptador" \
                "${quantos} «command tx timeout» seguidos, mas o ${hci} não tem porta USB legível" \
                "{\"hci\": $(_json_texto "${hci}"), \"timeouts\": ${quantos}}" null \
                "\"familia\": \"3\""
            recusou=1
            continue
        fi
        agora_hci="$(_hci_da_porta "${porta}" || true)"
        if [[ "${agora_hci}" != "${hci}" ]]; then
            printf 'recusado\t%s\t%s\to hci da porta agora é %s\n' "${porta}" "${hci}" "${agora_hci:-nenhum}"
            recusou=1
            continue
        fi
        carimbo="$(_estampas)/reset-${porta}"
        anterior="$(cat -- "${carimbo}" 2>/dev/null || echo 0)"
        [[ "${anterior}" =~ ^[0-9]+$ ]] || anterior=0
        if (( anterior > 0 )); then
            quantos="$(_timeouts_desde "${hci}" "${anterior}")"
            (( quantos >= LIMIAR_DO_LACO )) || continue
        fi
        if _ha_conexao "${hci}" "${porta}"; then
            printf 'recusado\t%s\t%s\thá conexão de pé\n' "${porta}" "${hci}"
            _diario "bt-ponte" "recusou reiniciar o adaptador" \
                "o kernel acusa laço, mas há conexão de pé nele — reiniciar derrubaria quem está ligado" \
                "{\"hci\": $(_json_texto "${hci}"), \"timeouts\": ${quantos}}" null \
                "\"porta\": $(_json_texto "${porta}"), \"familia\": \"3\""
            recusou=1
            continue
        fi
        if [[ -e "${carimbo}.desistiu" ]]; then
            printf 'segurado\t%s\t%s\tparou depois de %s reinícios\n' \
                "${porta}" "${hci}" "${MAX_REINICIOS_SEGUIDOS}"
            continue
        fi
        if (( agora - anterior < INTERVALO_ENTRE_RESETS_S )); then
            printf 'segurado\t%s\t%s\treiniciado há %ss\n' "${porta}" "${hci}" "$((agora - anterior))"
            if [[ "$(cat -- "${carimbo}.dito" 2>/dev/null || true)" != "${anterior}" ]]; then
                _diario "bt-ponte" "não insistiu no reinício" \
                    "o adaptador voltou a travar depois de reiniciado há $(( (agora - anterior) / 60 )) min — tire e ponha o adaptador da porta ${porta}" \
                    "{\"hci\": $(_json_texto "${hci}"), \"timeouts\": ${quantos}}" null \
                    "\"porta\": $(_json_texto "${porta}"), \"familia\": \"3\", \"frase\": $(_json_texto "O adaptador da porta ${porta} travou de novo. Tire e ponha ele.")"
                _seco || printf '%s\n' "${anterior}" >"${carimbo}.dito" 2>/dev/null || true
            fi
            continue
        fi
        seguidos="$(cat -- "${carimbo}.seguidos" 2>/dev/null || echo 0)"
        [[ "${seguidos}" =~ ^[0-9]+$ ]] || seguidos=0
        if (( anterior <= 0 || agora - anterior > JANELA_DA_CURA_S )); then
            seguidos=0
        fi
        if (( seguidos >= MAX_REINICIOS_SEGUIDOS )); then
            printf 'segurado\t%s\t%s\tparou depois de %s reinícios\n' \
                "${porta}" "${hci}" "${seguidos}"
            if _seco; then
                _dizer_seco "pararia de reiniciar a porta ${porta}: ${seguidos} reinícios sem cura"
                continue
            fi
            printf '%s\n' "${anterior}" >"${carimbo}.desistiu" 2>/dev/null || true
            _diario "bt-ponte" "parou de reiniciar o adaptador" \
                "${seguidos} reinícios seguidos e o laço voltou depois de cada um — reiniciar de novo só faria o adaptador sumir e voltar na porta" \
                "{\"hci\": $(_json_texto "${hci}"), \"timeouts\": ${quantos}, \"reinicios\": ${seguidos}}" null \
                "\"porta\": $(_json_texto "${porta}"), \"familia\": \"3\", \"frase\": $(_json_texto "O adaptador da porta ${porta} não se cura sozinho. Tire e ponha ele.")"
            continue
        fi
        if _seco; then
            _dizer_seco "reiniciaria a porta ${porta} (${hci}, ${quantos} timeouts): authorized 0 -> 1"
            continue
        fi
        pausa="${HEFESTO_USB_PAUSA_S:-2}"
        [[ "${pausa}" =~ ^[0-9]+$ ]] || pausa=2
        if ! printf '0' >"${SYSFS}/bus/usb/devices/${porta}/authorized" 2>/dev/null; then
            printf 'recusado\t%s\t%s\to kernel não aceitou desautorizar\n' "${porta}" "${hci}"
            recusou=1
            continue
        fi
        sleep "${pausa}"
        printf '1' >"${SYSFS}/bus/usb/devices/${porta}/authorized" 2>/dev/null || true
        install -d -m 700 "$(_estampas)" 2>/dev/null || true
        printf '%s\n' "$(date +%s)" >"${carimbo}" 2>/dev/null || true
        printf '%s\n' "$((seguidos + 1))" >"${carimbo}.seguidos" 2>/dev/null || true
        espera="${HEFESTO_USB_ESPERA_S:-30}"
        [[ "${espera}" =~ ^[0-9]+$ ]] || espera=30
        volta=""
        while :; do
            volta="$(_hci_da_porta "${porta}" || true)"
            [[ -n "${volta}" || "${espera}" -le 0 ]] && break
            sleep 1
            espera=$((espera - 1))
        done
        printf 'reiniciado\t%s\t%s\t%s\n' "${porta}" "${hci}" "${quantos}"
        _registrar "adaptador da porta ${porta} (${hci}) reiniciado: ${quantos} «command tx timeout» seguidos"
        if [[ -n "${volta}" ]]; then
            frase="O adaptador da porta ${porta} travou e foi reiniciado."
        else
            frase="O adaptador da porta ${porta} travou e não voltou. Tire e ponha ele."
        fi
        _diario "bt-ponte" "reiniciou o adaptador" \
            "${quantos} «command tx timeout» seguidos no ${hci}: o controlador travou em laço" \
            "{\"hci\": $(_json_texto "${hci}"), \"timeouts\": ${quantos}}" \
            "{\"hci\": $(_json_texto "${volta}"), \"voltou\": $([[ -n "${volta}" ]] && echo true || echo false)}" \
            "\"porta\": $(_json_texto "${porta}"), \"familia\": \"3\", \"frase\": $(_json_texto "${frase}")"
    done < <(_hcis_em_laco)
    [[ "${achou}" -eq 1 ]] || return 0
    [[ "${recusou}" -eq 0 ]] || exit 1
    return 0
}

_o_religar() {
    local aqui alvo modo
    aqui="$(readlink -f -- "${BASH_SOURCE[0]}" 2>/dev/null)" || return 1
    alvo="${aqui%/*}/bt_rebind_orphans.sh"
    [[ -f "${alvo}" && ! -L "${alvo}" ]] || return 1
    if [[ "$(id -u)" -eq 0 ]]; then
        [[ "$(stat -c %u -- "${alvo}" 2>/dev/null)" == "0" ]] || return 1
        modo="$(stat -c %a -- "${alvo}" 2>/dev/null)" || return 1
        [[ "${modo}" =~ ^[0-7]{3,4}$ ]] || return 1
        (( (8#${modo} & 8#022) == 0 )) || return 1
    fi
    printf '%s\n' "${alvo}"
}

verbo_religar_orfaos() {
    local religar
    if [[ -z "${HEFESTO_HID_DEVICES_DIR:-}" && -z "${HEFESTO_USB_DEVICES_DIR:-}" \
          && "$(id -u)" -ne 0 ]]; then
        _erro "'religar-orfaos' requer root (é a ponte privilegiada)"
        exit 1
    fi
    if ! religar="$(_o_religar)"; then
        _erro "o religar (bt_rebind_orphans.sh) não está ao lado desta ponte, ou não é só do root — nada foi feito"
        exit 1
    fi
    if _seco; then
        bash "${religar}" --dry-run --evento --quiet
        return 0
    fi
    bash "${religar}" --evento --quiet
}

verbo_regra_sudo() {
    local principal
    cat <<FIM
# /etc/sudoers.d/49-hefesto-bt-ponte — gerado por
# ${ALVO_INSTALADO} regra-sudo $*
#
# A ponte privilegiada do Bluetooth: o sudo é do install e vale para o app
# inteiro. NÃO editar à mão: o install regrava.
#
# A regra é estreita de propósito — caminho absoluto, verbos nomeados um a um e
# NENHUM curinga. O endereço e o nome novo entram pelo STDIN, não por argv:
# assim não sobra argumento livre a casar aqui, e o registro do sudo diz o
# verbo e nenhum aparelho.
Cmnd_Alias HEFESTO_BT_PONTE = \\
    ${ALVO_INSTALADO} adaptadores, \\
    ${ALVO_INSTALADO} bonds, \\
    ${ALVO_INSTALADO} renomear, \\
    ${ALVO_INSTALADO} esquecer, \\
    ${ALVO_INSTALADO} parear, \\
    ${ALVO_INSTALADO} desconectar, \\
    ${ALVO_INSTALADO} reiniciar-travado, \\
    ${ALVO_INSTALADO} religar-orfaos, \\
    ${ALVO_INSTALADO} descobrir [0-9], \\
    ${ALVO_INSTALADO} descobrir [0-9][0-9], \\
    ${ALVO_INSTALADO} descobrir [0-9][0-9][0-9]

FIM
    for principal in "$@"; do
        printf '%s ALL=(root) NOPASSWD: HEFESTO_BT_PONTE\n' "${principal}"
    done
}

_vinculado() {
    local nome valor
    for nome in Paired Bonded; do
        valor="$(busctl get-property org.bluez "$1" org.bluez.Device1 "${nome}" 2>/dev/null \
            | sed -E 's/^b //' || true)"
        [[ "${valor}" == "true" ]] || return 1
    done
    return 0
}

_parear_o_no() {
    local caminho="$1" hci="${1#/org/bluez/}" ja_vinculado=0
    hci="${hci%%/*}"
    _vinculado "${caminho}" && ja_vinculado=1
    timeout 45 busctl call org.bluez "${caminho}" org.bluez.Device1 Pair >/dev/null 2>&1 && return 0
    (( ja_vinculado == 0 )) && _vinculado "${caminho}" || return 1
    _registrar "o Pair não respondeu no adaptador ${hci}, e o bond está feito"
    return 0
}

if [[ "${1:-}" == "--dry-run" ]]; then
    SECOS=1
    shift
fi

VERBO="${1:-}"
[[ -n "${VERBO}" ]] || _uso
shift || true

case "${VERBO}" in
    adaptadores)
        [[ $# -eq 0 ]] || _recusar "adaptadores não recebe argumento"
        verbo_adaptadores
        ;;
    bonds)
        _sem_dado_no_argv bonds "$@"
        _mac_do_stdin 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _fim_do_stdin
        verbo_bonds "${ARG_ADAPTADOR}"
        ;;
    renomear)
        _sem_dado_no_argv renomear "$@"
        _mac_do_stdin 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _nome_do_stdin;                    ARG_NOME="${VALIDADO}"
        _fim_do_stdin
        verbo_renomear "${ARG_ADAPTADOR}" "${ARG_NOME}"
        ;;
    esquecer)
        _sem_dado_no_argv esquecer "$@"
        _mac_do_stdin 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _mac_do_stdin 'MAC do controle';  ARG_CONTROLE="${VALIDADO}"
        _fim_do_stdin
        verbo_esquecer "${ARG_ADAPTADOR}" "${ARG_CONTROLE}"
        ;;
    descobrir)
        [[ $# -eq 1 ]] || _recusar "descobrir recebe só os segundos no argv; o endereço vem pelo stdin, uma linha por dado"
        _segundos "${1}";                  ARG_SEGUNDOS="${VALIDADO}"
        _mac_do_stdin 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _fim_do_stdin
        verbo_descobrir "${ARG_ADAPTADOR}" "${ARG_SEGUNDOS}"
        ;;
    parear)
        _sem_dado_no_argv parear "$@"
        _mac_do_stdin 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _mac_do_stdin 'MAC do controle';  ARG_CONTROLE="${VALIDADO}"
        _fim_do_stdin
        verbo_parear "${ARG_ADAPTADOR}" "${ARG_CONTROLE}"
        ;;
    desconectar)
        _sem_dado_no_argv desconectar "$@"
        _mac_do_stdin 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _mac_do_stdin 'MAC do controle';  ARG_CONTROLE="${VALIDADO}"
        _fim_do_stdin
        verbo_desconectar "${ARG_ADAPTADOR}" "${ARG_CONTROLE}"
        ;;
    reiniciar-travado)
        [[ $# -eq 0 ]] || _recusar "reiniciar-travado não recebe argumento (quem escolhe a porta é o kernel)"
        verbo_reiniciar_travado
        ;;
    religar-orfaos)
        [[ $# -eq 0 ]] || _recusar "religar-orfaos não recebe argumento (quem escolhe o controle é o /sys)"
        verbo_religar_orfaos
        ;;
    regra-sudo)
        [[ $# -ge 1 ]] || _recusar "regra-sudo recebe ao menos 1 argumento (nome da usuária ou %grupo)"
        _principais=()
        for _p in "$@"; do
            _principal_do_sudoers "${_p}"; _principais+=("${VALIDADO}")
        done
        verbo_regra_sudo "${_principais[@]}"
        ;;
    ajuda|--help|-h)
        _uso
        ;;
    *)
        _recusar "verbo desconhecido: '${VERBO}'"
        ;;
esac
